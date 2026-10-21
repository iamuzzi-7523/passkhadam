"""
backend/tests/test_worker_location_and_replay_guidance.py

Comprehensive Verification Suite for:
1. Worker Portal Location Management (PUT /api/v1/worker/profile/me updating current_state)
2. Deferred Atomic Replay Protection Guidance Message (single-use token advisory)
3. Fresh QR generation allowing seamless worker re-verification / re-hiring
4. Goa Government Officer jurisdiction matching (current_state, origin_state, active employment)
5. Government Officer CROSS_STATE_VERIFICATION permission bypassing jurisdiction mismatch
"""

import io
import os
import sys
import json
import uuid
import base64
import hashlib
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal, DBUser, DBWorkerProfile,
    DBEmployerOrganization, DBCategoryAuthorizationRequest,
    DBGovernmentOfficer, DBConsumedPresentationNonce
)
from app.services.verification_engine import (
    verification_engine, ReplayAttackError, VerificationEngineError
)
from app.services.blockchain_service import blockchain_service
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)


def setup_worker(origin_state="Karnataka", current_state="Karnataka"):
    """Helper to set up an active, verified worker and return auth headers and profile."""
    db = SessionLocal()
    worker_name = f"MigrantWorker_{uuid.uuid4().hex[:6]}"
    uid = f"uid_worker_{uuid.uuid4().hex[:10]}"
    email = f"worker_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name=worker_name,
        email=email,
        phone="+91 9876543210",
        password_hash=pw_hash,
        role="WORKER",
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = DBWorkerProfile(
        user_id=user.id,
        full_name=worker_name,
        origin_state=origin_state,
        current_state=current_state,
        worker_category="Construction Worker",
        skills_json=json.dumps(["Masonry", "Carpentry"]),
        did_state="NOT_STARTED"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=worker_name)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed mock Aadhaar record
    aadhaar_num = f"99{uuid.uuid4().int % 10000000000:010d}"
    seed_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name,
        "dob": "1995-01-01",
        "gender": "MALE",
        "origin_state": origin_state,
        "district": "Bangalore Urban",
        "status": "ACTIVE"
    })
    assert seed_res.status_code == 201

    # Verify Aadhaar
    verif_res = client.post("/api/v1/worker/verify-aadhaar/me", headers=headers, json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name,
        "consent": True
    })
    assert verif_res.status_code == 200, f"Verify failed: {verif_res.text}"

    # Generate QR presentation
    qr_res = client.get("/api/v1/worker/presentation/qr-card/me", headers=headers)
    assert qr_res.status_code == 200, f"QR gen failed: {qr_res.text}"
    qr_b64 = qr_res.json()["qr_base64_data_uri"].split(",")[1]
    qr_png_bytes = base64.b64decode(qr_b64)

    u_id = user.id
    p_id = profile.id
    db.close()
    return {
        "uid": uid,
        "email": email,
        "name": worker_name,
        "headers": headers,
        "qr_bytes": qr_png_bytes,
        "user_id": u_id,
        "profile_id": p_id
    }


def setup_employer():
    """Helper to set up an active employer and return auth headers."""
    db = SessionLocal()
    org_name = f"Apex Construction {uuid.uuid4().hex[:4]}"
    uid = f"uid_emp_{uuid.uuid4().hex[:10]}"
    email = f"emp_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    org_addr = f"0xemp_{uuid.uuid4().hex[:8]}"
    user = DBUser(
        firebase_uid=uid,
        full_name="Employer Admin",
        email=email,
        phone="+91 9876543211",
        password_hash=pw_hash,
        role="EMPLOYER",
        status="ACTIVE",
        organization_address=org_addr,
        organization_status="APPROVED",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    org = DBEmployerOrganization(
        user_id=user.id,
        name=org_name,
        registration_ref_number=f"REG-{uuid.uuid4().hex[:6].upper()}",
        official_email=email,
        contact_person="Employer Admin",
        contact_phone="+91 9876543211",
        org_address=org_addr,
        status="ACTIVE"
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    cat_req = DBCategoryAuthorizationRequest(
        organization_id=org.id,
        category="Construction Worker",
        skill_level="Skilled",
        nature_of_employment="CONTRACT",
        status="APPROVED",
        is_active_scope=True
    )
    db.add(cat_req)
    db.commit()

    # Register in blockchain service
    blockchain_service.register_organization(
        address=org_addr,
        name=org_name,
        reg_num=org.registration_ref_number,
        state_code="KA",
        org_type="CONSTRUCTION",
        categories=["Construction Worker"]
    )
    blockchain_service.set_org_status(org_addr, "APPROVED", "Automated test setup")
    blockchain_service.authorize_category(org_addr, "Construction Worker")

    token = create_test_firebase_jwt(uid=uid, email=email, name="Employer Admin")
    headers = {"Authorization": f"Bearer {token}"}

    u_id = user.id
    db.close()
    return {"headers": headers, "org_addr": org_addr, "user_id": u_id}


def setup_government_officer(state="Goa", authority_level="STATE", cross_state=False):
    """Helper to set up an active government officer and return auth headers."""
    db = SessionLocal()
    officer_name = f"Goa Officer {uuid.uuid4().hex[:4]}"
    uid = f"uid_gov_{uuid.uuid4().hex[:10]}"
    email = f"gov_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name=officer_name,
        email=email,
        phone="+91 9876543212",
        password_hash=pw_hash,
        role="GOVERNMENT",
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    perms = ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"]
    if cross_state:
        perms.append("CROSS_STATE_VERIFICATION")

    officer = DBGovernmentOfficer(
        user_id=user.id,
        officer_name=officer_name,
        full_name=officer_name,
        officer_reference_id=f"GOV-OFF-{uuid.uuid4().hex[:6].upper()}",
        department="Goa Labour Welfare Board",
        designation="Labour Welfare Officer",
        official_email=email,
        phone="+91 9876543212",
        authority_level=authority_level,
        state=state if authority_level != "NATIONAL" else None,
        permissions_json=json.dumps(perms),
        benefit_permissions_json=json.dumps(["ALL", "1", "2"]),
        status="ACTIVE"
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)

    token = create_test_firebase_jwt(uid=uid, email=email, name=officer_name)
    headers = {"Authorization": f"Bearer {token}"}

    o_id = officer.id
    u_id = user.id
    db.close()
    return {"headers": headers, "officer_id": o_id, "user_id": u_id}


# ============================================================================
# Tests
# ============================================================================

def test_worker_can_update_current_location_to_goa():
    """Verify worker can update current_state to Goa via PUT /api/v1/worker/profile/me."""
    worker = setup_worker(origin_state="Karnataka", current_state="Karnataka")

    # Update location to Goa
    update_res = client.put(
        "/api/v1/worker/profile/me",
        headers=worker["headers"],
        json={"current_state": "Goa", "current_address": "Panaji, North Goa"}
    )
    assert update_res.status_code == 200, f"Update failed: {update_res.text}"
    data = update_res.json()
    assert data["current_state"] == "Goa"

    # Verify GET /profile/me reflects Goa
    get_res = client.get("/api/v1/worker/profile/me", headers=worker["headers"])
    assert get_res.status_code == 200
    assert get_res.json()["current_state"] == "Goa"


def test_replay_attack_returns_informative_refresh_guidance():
    """Verify scanning the same QR twice raises descriptive ReplayAttackError guiding worker to refresh."""
    worker = setup_worker(origin_state="Karnataka", current_state="Karnataka")
    employer = setup_employer()

    # First verification should succeed
    files = {"file": ("qr.png", io.BytesIO(worker["qr_bytes"]), "image/png")}
    res1 = client.post("/api/v1/employer/verify-worker-qr", headers=employer["headers"], files=files)
    assert res1.status_code == 200, f"First verification failed: {res1.text}"
    assert res1.json()["verified"] is True

    # Second verification of exact same QR must return 409 Conflict with clear guidance
    files2 = {"file": ("qr.png", io.BytesIO(worker["qr_bytes"]), "image/png")}
    res2 = client.post("/api/v1/employer/verify-worker-qr", headers=employer["headers"], files=files2)
    assert res2.status_code == 409, f"Expected 409 Conflict, got: {res2.status_code} {res2.text}"
    detail = res2.json()["detail"]
    assert "REPLAY_ATTACK_DETECTED" in detail
    assert "single-use tokens" in detail
    assert "Refresh" in detail


def test_worker_fresh_qr_succeeds_on_second_scan():
    """Verify worker generating a fresh QR presentation can be re-verified / re-hired smoothly."""
    worker = setup_worker(origin_state="Karnataka", current_state="Karnataka")
    employer = setup_employer()

    # First scan succeeds
    files1 = {"file": ("qr.png", io.BytesIO(worker["qr_bytes"]), "image/png")}
    res1 = client.post("/api/v1/employer/verify-worker-qr", headers=employer["headers"], files=files1)
    assert res1.status_code == 200

    # Worker taps "Refresh" -> fresh QR presentation generated
    fresh_qr_res = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker["headers"])
    assert fresh_qr_res.status_code == 200
    fresh_b64 = fresh_qr_res.json()["qr_base64_data_uri"].split(",")[1]
    fresh_qr_bytes = base64.b64decode(fresh_b64)

    # Second scan with fresh QR succeeds!
    files2 = {"file": ("fresh_qr.png", io.BytesIO(fresh_qr_bytes), "image/png")}
    res2 = client.post("/api/v1/employer/verify-worker-qr", headers=employer["headers"], files=files2)
    assert res2.status_code == 200, f"Fresh QR verification failed: {res2.text}"
    assert res2.json()["verified"] is True


def test_goa_officer_verifies_worker_with_updated_goa_location():
    """Verify Goa officer succeeds in verifying worker once current_state is updated to Goa."""
    worker = setup_worker(origin_state="Karnataka", current_state="Karnataka")
    goa_officer = setup_government_officer(state="Goa", authority_level="STATE", cross_state=False)

    # Initial scan while current_state is Karnataka should fail with jurisdiction error
    files1 = {"file": ("qr.png", io.BytesIO(worker["qr_bytes"]), "image/png")}
    res1 = client.post("/api/v1/government/verify-worker-qr", headers=goa_officer["headers"], files=files1)
    assert res1.status_code == 403
    assert "does not cover worker location" in res1.json()["detail"]

    # Worker moves to Goa and updates profile
    update_res = client.put(
        "/api/v1/worker/profile/me",
        headers=worker["headers"],
        json={"current_state": "Goa", "current_address": "Mapusa, Goa"}
    )
    assert update_res.status_code == 200

    # Worker generates fresh QR reflecting current location
    qr_res = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker["headers"])
    assert qr_res.status_code == 200
    qr_bytes_goa = base64.b64decode(qr_res.json()["qr_base64_data_uri"].split(",")[1])

    # Goa officer scans again: SUCCESS!
    files2 = {"file": ("qr_goa.png", io.BytesIO(qr_bytes_goa), "image/png")}
    res2 = client.post("/api/v1/government/verify-worker-qr", headers=goa_officer["headers"], files=files2)
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
    data = res2.json()
    assert data["verified"] is True
    assert data["data"]["is_interstate_worker"] is True


def test_cross_state_officer_can_verify_worker_from_any_state():
    """Verify government officer with CROSS_STATE_VERIFICATION permission can verify worker in any state."""
    worker = setup_worker(origin_state="Karnataka", current_state="Karnataka")
    # Goa officer with CROSS_STATE_VERIFICATION permission
    cross_state_officer = setup_government_officer(state="Goa", authority_level="STATE", cross_state=True)

    files = {"file": ("qr.png", io.BytesIO(worker["qr_bytes"]), "image/png")}
    res = client.post("/api/v1/government/verify-worker-qr", headers=cross_state_officer["headers"], files=files)
    assert res.status_code == 200, f"Expected 200 for cross-state officer, got: {res.status_code} {res.text}"
    assert res.json()["verified"] is True


def test_goa_officer_verifies_worker_with_active_employment_in_goa():
    """Verify Goa officer succeeds in verifying worker if worker has active on-chain employment in Goa."""
    worker = setup_worker(origin_state="Karnataka", current_state="Karnataka")
    employer = setup_employer()
    goa_officer = setup_government_officer(state="Goa", authority_level="STATE", cross_state=False)

    # First verify worker under employer
    files_emp = {"file": ("qr.png", io.BytesIO(worker["qr_bytes"]), "image/png")}
    res_emp = client.post("/api/v1/employer/verify-worker-qr", headers=employer["headers"], files=files_emp)
    assert res_emp.status_code == 200
    worker_did = res_emp.json()["worker_did"]

    # Employer creates employment contract in Goa
    offer_res = client.post("/api/v1/employer/create-employment", headers=employer["headers"], json={
        "worker_did": worker_did,
        "category": "Construction Worker",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Senior Mason",
        "work_location": "Vasco, Goa"
    })
    assert offer_res.status_code == 200, f"Offer failed: {offer_res.text}"

    # Worker generates fresh QR
    fresh_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker["headers"])
    assert fresh_qr.status_code == 200
    fresh_qr_bytes = base64.b64decode(fresh_qr.json()["qr_base64_data_uri"].split(",")[1])

    # Goa officer verifies worker: Recognized due to active employment location in Goa!
    files_gov = {"file": ("qr_active_emp.png", io.BytesIO(fresh_qr_bytes), "image/png")}
    res_gov = client.post("/api/v1/government/verify-worker-qr", headers=goa_officer["headers"], files=files_gov)
    assert res_gov.status_code == 200, f"Expected 200 via active employment in Goa, got: {res_gov.status_code} {res_gov.text}"
    assert res_gov.json()["verified"] is True


def test_provisioned_government_officer_can_disburse_benefit_claim():
    """Verify newly provisioned government officer (with 0xgov_... wallet) can disburse welfare claims."""
    worker = setup_worker(origin_state="Goa", current_state="Goa")
    goa_officer = setup_government_officer(state="Goa", authority_level="STATE", cross_state=False)

    # First verify worker under officer
    files = {"file": ("qr.png", io.BytesIO(worker["qr_bytes"]), "image/png")}
    v_res = client.post("/api/v1/government/verify-worker-qr", headers=goa_officer["headers"], files=files)
    assert v_res.status_code == 200
    worker_did = v_res.json()["worker_did"]

    # Disburse welfare benefit claim #1 (Interstate Migrant Worker Relief Scheme)
    disburse_res = client.post("/api/v1/government/disburse-claim", headers=goa_officer["headers"], json={
        "scheme_id": 1,
        "worker_did": worker_did,
        "officer_state": "Goa"
    })
    assert disburse_res.status_code == 200, f"Disburse claim failed: {disburse_res.text}"
    claim_data = disburse_res.json()
    assert claim_data["claim_record"]["is_disbursed"] is True
    assert claim_data["claim_record"]["scheme_id"] == 1
    assert "anchored on blockchain" in claim_data["message"]
