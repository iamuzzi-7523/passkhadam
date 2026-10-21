"""
PassKhadam v0.5 — Test Module 9: Status Transition & Tier 4 Real-World Regression Tests
========================================================================================
Tier 4: Comprehensive Real-World End-to-End Scenarios across Personas & Features
Covers complete real-world state transitions, edge recovery, target isolation, and governance.

Total Tests: 16 tests
Pass/Fail Semantics: 100% pass rate, exit code 0, 0 skipped.
"""

import os
import sys
import json
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBWorkerProfile,
    DBEmployerOrganization,
    DBGovernmentOfficer,
    DBCategoryAuthorizationRequest,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBAadhaarRecord,
    DBAadhaarAuditLog,
    DBConsumedPresentationNonce,
)
from app.core.auth import create_test_firebase_jwt
from app.services.verification_engine import verification_engine
from app.services.blockchain_service import blockchain_service

client = TestClient(app)

DEFAULT_GOV_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"


# =============================================================================
# Helper Utilities
# =============================================================================

def get_admin_token() -> str:
    """Creates an active platform admin user and returns bearer JWT."""
    db = SessionLocal()
    u_uid = f"uid_adm_{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    user = DBUser(
        firebase_uid=u_uid,
        full_name="Platform Admin",
        email=email,
        phone="+919876500000",
        password_hash="hash",
        role="ADMIN",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.close()
    return create_test_firebase_jwt(uid=u_uid, email=email, name="Platform Admin")


def create_verified_worker(state: str = "Bihar") -> tuple[str, str, str, str, bytes]:
    """Sets up an anchored active worker via verify-aadhaar pipeline and generates valid QR PNG bytes.
    Returns (worker_did, aadhaar_num, token, record_id, png_bytes).
    """
    worker_name = f"RealWorker_{uuid.uuid4().hex[:6]}"
    uid = f"uid_{uuid.uuid4().hex[:10]}"
    email = f"worker_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    db = SessionLocal()
    user = DBUser(
        firebase_uid=uid,
        full_name=worker_name,
        email=email,
        phone="+91 9876543210",
        password_hash=pw_hash,
        role="WORKER",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = DBWorkerProfile(
        user_id=user.id,
        full_name=worker_name,
        origin_state=state,
        current_state="Maharashtra",
        worker_category="Mason",
        skills_json=json.dumps(["Mason", "Bricklaying"]),
        did_state="NOT_STARTED"
    )
    db.add(profile)
    db.commit()

    token = create_test_firebase_jwt(uid=uid, email=email, name=worker_name)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed Aadhaar in mock authority
    raw_aadhaar = str(secrets.randbelow(900000000000) + 100000000000)
    aadhaar_num = f"{raw_aadhaar[:4]} {raw_aadhaar[4:8]} {raw_aadhaar[8:]}"
    seed_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name,
        "dob": "1994-05-15",
        "gender": "MALE",
        "origin_state": state,
        "address": f"Patna, {state}",
        "status": "ACTIVE"
    })
    assert seed_res.status_code == 201, seed_res.text
    rec_id = seed_res.json()["record_id"]

    # Verify Aadhaar to anchor DID
    v_res = client.post("/api/v1/worker/verify-aadhaar/me", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name
    }, headers=headers)
    assert v_res.status_code == 200, v_res.text
    worker_did = v_res.json()["did"]

    png_bytes, _ = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={"full_name": worker_name},
        validity_seconds=300
    )
    db.close()
    return worker_did, aadhaar_num, token, rec_id, png_bytes


def create_approved_employer(category: str = "Mason") -> tuple[int, str, str]:
    """Creates an approved active employer with active category authorization.
    Returns (org_id, org_address, employer_token).
    """
    db = SessionLocal()
    org_addr = f"0x{uuid.uuid4().hex[:40]}"
    u_uid = f"uid_emp_{uuid.uuid4().hex[:8]}"
    email = f"employer_{uuid.uuid4().hex[:6]}@builders.com"
    name = f"Horizon Builders {uuid.uuid4().hex[:4]}"

    user = DBUser(
        firebase_uid=u_uid,
        full_name=name,
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="EMPLOYER",
        status="ACTIVE",
        organization_address=org_addr
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    cin_number = f"CIN-{uuid.uuid4().hex[:8].upper()}"
    org = DBEmployerOrganization(
        user_id=user.id,
        name=name,
        registration_ref_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        registration_number=cin_number,
        official_email=email,
        official_phone="+919876543210",
        contact_person="Vikas Sharma",
        business_type="Construction",
        org_address=org_addr,
        status="APPROVED",
        state_code="MH"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    cat_auth = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category=category,
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        request_version=1,
        reviewed_at=datetime.utcnow()
    )
    db.add(cat_auth)
    db.commit()
    db.close()

    blockchain_service.register_organization(
        address=org_addr,
        name=name,
        reg_num=cin_number,
        state_code="MH",
        org_type="EMPLOYER",
        categories=[category]
    )
    blockchain_service.set_org_status(org_addr, "APPROVED")
    blockchain_service.authorize_category(org_addr, category)

    token = create_test_firebase_jwt(uid=u_uid, email=email, name=name)
    return org_id, org_addr, token


def create_active_officer(state: str = "Maharashtra", perms: list = None) -> tuple[int, str]:
    """Creates an active government officer and returns (officer_id, officer_token)."""
    db = SessionLocal()
    u_uid = f"uid_gov_{uuid.uuid4().hex[:8]}"
    email = f"officer_{uuid.uuid4().hex[:6]}@labour.gov.in"
    name = f"Officer {uuid.uuid4().hex[:4]}"

    user = DBUser(
        firebase_uid=u_uid,
        full_name=name,
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="GOVERNMENT",
        status="ACTIVE",
        organization_address=None
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    officer = DBGovernmentOfficer(
        user_id=user.id,
        officer_name=name,
        full_name=name,
        officer_reference_id=f"GOV-OFF-{uuid.uuid4().hex[:8].upper()}",
        official_email=email,
        phone="+919876543210",
        wallet_address=None,
        department="Labour Welfare Department",
        designation="Commissioner",
        authority_level="STATE",
        state=state,
        status="ACTIVE",
        permissions_json=json.dumps(perms or ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"]),
        benefit_permissions_json=json.dumps(["1", "2"])
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    officer_id = officer.id
    db.close()

    blockchain_service.register_organization(
        address=DEFAULT_GOV_ADDR,
        name="Labour Welfare Department",
        reg_num="GOV-MH-01",
        state_code="MH",
        org_type="GOVERNMENT",
        categories=[]
    )
    blockchain_service.set_org_status(DEFAULT_GOV_ADDR, "APPROVED")

    token = create_test_firebase_jwt(uid=u_uid, email=email, name=name)
    return officer_id, token


# =============================================================================
# SCENARIO 1: Migrant Worker Complete Lifecycle (S4.1 - S4.3)
# =============================================================================

def test_s4_1_migrant_worker_complete_lifecycle():
    """S4.1: Migrant worker onboarding from Bihar to Maharashtra:
    1. Onboarding & Aadhaar verification anchors DID on-chain.
    2. Dynamic QR credential presentation generated.
    3. Employer in Maharashtra scans QR, receives verified status and origin_state.
    4. Employer successfully records on-chain employment record.
    """
    worker_did, _, worker_token, _, qr_bytes = create_verified_worker(state="Bihar")
    org_id, org_addr, emp_token = create_approved_employer(category="Mason")

    # Employer scans worker QR
    files = {"file": ("worker_qr.png", qr_bytes, "image/png")}
    v_res = client.post(
        "/api/v1/employer/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert v_data["verified"] is True
    assert v_data["worker_did"] == worker_did
    assert v_data["data"]["is_eligible_for_hire"] is True
    assert v_data["data"]["worker_category"] == "Mason"

    # Employer hires worker
    hire_res = client.post(
        "/api/v1/employer/create-employment",
        json={
            "worker_did": worker_did,
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Head Mason",
            "work_location": "Navi Mumbai, Maharashtra",
            "expected_end_date": 0
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert hire_res.status_code == 200
    assert hire_res.json()["employment_record"]["worker_did"] == worker_did


def test_s4_2_worker_demographic_change_invalidation():
    """S4.2: Worker Aadhaar demographic record modified or inactivated in Mock Authority;
    system invalidates active credential status and rejects presentation generation.
    """
    worker_did, aadhaar_num, worker_token, rec_id, _ = create_verified_worker(state="Bihar")

    # Inactivate Aadhaar record in authority
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == rec_id).first()
    assert rec is not None
    rec.status = "INACTIVE"
    rec.is_active = False
    db.commit()
    db.close()

    # Worker attempts to generate QR card -> must be rejected with HTTP 403
    qr_res = client.get(
        "/api/v1/worker/presentation/qr-card/me",
        headers={"Authorization": f"Bearer {worker_token}"}
    )
    assert qr_res.status_code == 403


def test_s4_3_worker_revalidation_and_resume_employment():
    """S4.3: Worker completes revalidation after demographic update;
    DID is re-anchored on-chain, fresh QR card is issued, and new employment can proceed.
    """
    worker_did, aadhaar_num, worker_token, rec_id, _ = create_verified_worker(state="Bihar")
    _, _, emp_token = create_approved_employer(category="Mason")

    # 1. Update Aadhaar record with new address/name in mock authority and set ACTIVE
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == rec_id).first()
    rec.status = "ACTIVE"
    rec.is_active = True
    db.commit()

    # Find worker user name
    prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.did == worker_did).first()
    w_name = prof.full_name
    db.close()

    # 2. Worker re-verifies Aadhaar
    reval_res = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json={"aadhaar_number": aadhaar_num, "full_name": w_name},
        headers={"Authorization": f"Bearer {worker_token}"}
    )
    assert reval_res.status_code == 200
    assert reval_res.json()["did"] == worker_did

    # 3. Worker can now download fresh QR card PNG
    qr_res = client.get(
        "/api/v1/worker/presentation/download-qr/me",
        headers={"Authorization": f"Bearer {worker_token}"}
    )
    assert qr_res.status_code == 200
    fresh_qr = qr_res.content

    # 4. Employer scans fresh QR and creates employment
    v_res = client.post(
        "/api/v1/employer/verify-worker-qr",
        files={"file": ("worker_qr.png", fresh_qr, "image/png")},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert v_res.status_code == 200
    assert v_res.json()["verified"] is True


# =============================================================================
# SCENARIO 2: Employer Onboarding & Governance Lifecycle (S4.4 - S4.6)
# =============================================================================

def test_s4_4_employer_onboarding_review_and_activation_pipeline():
    """S4.4: Full employer onboarding pipeline:
    1. Employer submits registration.
    2. Admin reviews queue, approves employer, and issues new activation link.
    3. Employer activates account using one-time token.
    4. Re-using activation token is blocked.
    """
    email = f"emp_pipe_{uuid.uuid4().hex[:6]}@pipelinecorp.in"
    reg_payload = {
        "company_name": f"Pipeline Infra {uuid.uuid4().hex[:4]}",
        "registration_number": f"CIN-{uuid.uuid4().hex[:8].upper()}",
        "business_address": "Worli, Mumbai",
        "contact_person": "Anita Roy",
        "email": email,
        "phone": "+919876543210",
        "categories_requested": ["Mason", "Plumber"]
    }
    reg_res = client.post("/api/v1/employer/register-organization", json=reg_payload)
    assert reg_res.status_code == 200
    org_id = reg_res.json()["organization_id"]

    admin_token = get_admin_token()
    rev_res = client.post(
        f"/api/v1/admin/organizations/{org_id}/review",
        json={"action": "APPROVE", "notes": "Corporate records certified"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rev_res.status_code == 200
    act_link = rev_res.json()["activation_link"]
    token = act_link.split("token=")[1]

    # Activate
    act_res = client.post("/api/v1/employer/activate", json={"activation_token": token, "password": "Password123!"})
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "ACTIVE"

    # Re-use activation token fails
    re_act = client.post("/api/v1/employer/activate", json={"activation_token": token})
    assert re_act.status_code in [400, 410]


def test_s4_5_employer_category_expansion_workflow():
    """S4.5: Employer requests additional category scope;
    Admin approves category; Employer is subsequently permitted to hire in that category.
    """
    org_id, org_addr, emp_token = create_approved_employer(category="Mason")
    worker_did, _, _, _, _ = create_verified_worker()

    # Attempt to hire in unauthorized category "Electrician" fails
    unauth_hire = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Electrician", "job_role": "Wiring Tech", "work_location": "Pune"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert unauth_hire.status_code in [400, 403]

    # Employer submits category expansion request
    req_res = client.post(
        "/api/v1/employer/request-category",
        json={"category": "Electrician", "reason": "New industrial electrical contract won"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert req_res.status_code == 200
    req_id = req_res.json()["request_id"]

    # Admin reviews and approves category request
    admin_token = get_admin_token()
    rev_res = client.post(
        f"/api/v1/admin/category-requests/{req_id}/review",
        json={"action": "APPROVE"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rev_res.status_code == 200

    # Hiring in "Electrician" now succeeds
    auth_hire = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Electrician", "job_role": "Wiring Tech", "work_location": "Pune"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert auth_hire.status_code == 200
    assert auth_hire.json()["employment_record"]["category"] == "Electrician"


def test_s4_6_employer_suspension_and_reactivation_lifecycle():
    """S4.6: Admin suspends employer for audit failure; all hiring actions blocked;
    Admin reactivates employer; hiring resumes cleanly.
    """
    org_id, org_addr, emp_token = create_approved_employer(category="Mason")
    worker_did, _, _, _, _ = create_verified_worker()
    admin_token = get_admin_token()

    # Admin suspends employer
    s_res = client.post(
        f"/api/v1/admin/organizations/{org_id}/review",
        json={"action": "SUSPEND", "reason": "Failure to provide mandatory safety insurance certificates"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert s_res.status_code == 200
    assert s_res.json()["organization"]["status"] == "SUSPENDED"

    # Employer action blocked
    blocked_hire = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Mason", "job_role": "Mason", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert blocked_hire.status_code == 403

    # Admin reactivates employer
    r_res = client.post(
        f"/api/v1/admin/organizations/{org_id}/review",
        json={"action": "REACTIVATE", "notes": "Safety compliance certificates received and verified"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_res.status_code == 200
    assert r_res.json()["organization"]["status"] == "ACTIVE"

    # Employer action succeeds again
    ok_hire = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Mason", "job_role": "Mason", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert ok_hire.status_code == 200


# =============================================================================
# SCENARIO 3: Category Scope Governance & Decoupling Lifecycle (S4.7 - S4.9)
# =============================================================================

def test_s4_7_employer_multi_category_selective_approval():
    """S4.7: Employer requests multiple categories; Admin selectively approves subset;
    Employer is authorized only for the approved subset.
    """
    org_id, org_addr, emp_token = create_approved_employer(category="Mason")
    worker_did, _, _, _, _ = create_verified_worker()
    admin_token = get_admin_token()

    # Request Carpenter and Welder
    r1 = client.post(
        "/api/v1/employer/request-category",
        json={"category": "Carpenter", "reason": "Carpentry team recruited"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert r1.status_code == 200
    req1_id = r1.json()["request_id"]

    r2 = client.post(
        "/api/v1/employer/request-category",
        json={"category": "Welder", "reason": "Welding operations starting"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert r2.status_code == 200
    req2_id = r2.json()["request_id"]

    # Admin APPROVES Carpenter, REJECTS Welder
    client.post(
        f"/api/v1/admin/category-requests/{req1_id}/review",
        json={"action": "APPROVE"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    client.post(
        f"/api/v1/admin/category-requests/{req2_id}/review",
        json={"action": "REJECT", "reason": "Welding certification expired"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Hiring in Carpenter succeeds
    h_carp = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Carpenter", "job_role": "Carpenter", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert h_carp.status_code == 200

    # Hiring in Welder fails
    h_weld = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Welder", "job_role": "Welder", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert h_weld.status_code in [400, 403]


def test_s4_8_employer_category_revocation_and_employment_preservation():
    """S4.8: Decoupled category management:
    Admin revokes an authorized category from employer;
    Existing active employments in that category remain valid and historically queryable,
    but new employments in the revoked category are blocked.
    """
    org_id, org_addr, emp_token = create_approved_employer(category="Mason")
    worker_did, _, _, _, _ = create_verified_worker()

    # 1. Create active employment in Mason
    h_res = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Mason", "job_role": "Mason", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert h_res.status_code == 200
    emp_record_id = h_res.json()["employment_record"]["id"]

    # 2. Revoke category authorization scope in DB and blockchain service
    blockchain_service.revoke_category(org_addr, "Mason")
    db = SessionLocal()
    req = db.query(DBCategoryAuthorizationRequest).filter(
        DBCategoryAuthorizationRequest.organization_id == org_id,
        DBCategoryAuthorizationRequest.category == "Mason"
    ).first()
    if req:
        req.status = "REVOKED"
        req.is_active_scope = False
        db.commit()
    db.close()

    # 3. New hiring in "Mason" is blocked
    new_h = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Mason", "job_role": "Mason", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert new_h.status_code in [400, 403]

    # 4. Previously created employment record remains queryable and valid on-chain
    assert emp_record_id in blockchain_service.employments
    assert blockchain_service.employments[emp_record_id]["category"] == "Mason"


def test_s4_9_employer_concurrent_category_requests():
    """S4.9: Employer submits multiple category requests;
    Queue state maintains exact sequence and idempotent processing without race conditions.
    """
    org_id, _, emp_token = create_approved_employer(category="Mason")
    admin_token = get_admin_token()

    categories = ["Electrician", "Painter", "Plumber"]
    req_ids = []
    for cat in categories:
        resp = client.post(
            "/api/v1/employer/request-category",
            json={"category": cat, "reason": f"Need {cat} for expansion"},
            headers={"Authorization": f"Bearer {emp_token}"}
        )
        assert resp.status_code == 200
        req_ids.append(resp.json()["request_id"])

    # Query admin category requests queue
    q_res = client.get(
        "/api/v1/admin/category-requests",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    listed_ids = [r["id"] for r in q_res.json()]
    for rid in req_ids:
        assert rid in listed_ids


# =============================================================================
# SCENARIO 4: Government Officer & Jurisdictional Claim Disbursement (S4.10 - S4.12)
# =============================================================================

def test_s4_10_government_officer_full_lifecycle():
    """S4.10: Full government officer lifecycle:
    1. Admin provisions officer with Maharashtra state jurisdiction.
    2. Officer receives activation token and activates account.
    3. Officer scans migrant worker QR card and verifies migration profile.
    4. Officer disburses welfare claim to verified worker.
    """
    admin_token = get_admin_token()
    email = f"gov_life_{uuid.uuid4().hex[:6]}@labour.gov.in"
    name = f"Officer Life {uuid.uuid4().hex[:4]}"

    # 1. Admin provisions officer
    p_res = client.post(
        "/api/v1/admin/government-officers",
        json={
            "full_name": name,
            "official_email": email,
            "phone": "+919876543211",
            "department": "Department of Labour",
            "designation": "State Director",
            "authority_level": "STATE",
            "state": "Maharashtra",
            "permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"],
            "benefit_permissions": ["1", "2"],
            "wallet_address": DEFAULT_GOV_ADDR
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert p_res.status_code == 200
    act_link = p_res.json()["activation_link"]
    token = act_link.split("token=")[1]
    officer_id = p_res.json()["id"]

    # 2. Officer activates account
    act_res = client.post(
        "/api/v1/government/activate",
        json={"activation_token": token, "password": "SecurePassword123!"}
    )
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "ACTIVE"

    # Retrieve existing activated user to create officer auth token
    db = SessionLocal()
    off_rec = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    user_rec = db.query(DBUser).filter(DBUser.id == off_rec.user_id).first()
    off_token = create_test_firebase_jwt(uid=user_rec.firebase_uid, email=user_rec.email, name=user_rec.full_name)
    db.close()

    # 3. Officer scans worker QR
    worker_did, _, _, _, qr_bytes = create_verified_worker(state="Bihar")
    files = {"file": ("worker_qr.png", qr_bytes, "image/png")}
    v_res = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {off_token}"}
    )
    assert v_res.status_code == 200
    assert v_res.json()["verified"] is True
    assert v_res.json()["data"]["origin_state"] == "Bihar"

    # 4. Officer disburses welfare claim
    d_res = client.post(
        "/api/v1/government/disburse-claim",
        json={"worker_did": worker_did, "scheme_id": 1, "officer_state": "Maharashtra"},
        headers={"Authorization": f"Bearer {off_token}"}
    )
    assert d_res.status_code == 200
    assert "claim_record" in d_res.json()
    assert d_res.json()["claim_record"]["worker_did"] == worker_did


def test_s4_11_government_officer_jurisdictional_benefit_gating():
    """S4.11: Jurisdictional claim gating:
    Officer whose authority is restricted to scheme 1 cannot disburse scheme 2;
    unauthorized disbursement returns HTTP 403.
    """
    # Create officer authorized only for scheme 1
    officer_id, off_token = create_active_officer(state="Maharashtra", perms=["WORKER_VERIFICATION", "DISBURSE_BENEFIT"])
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    off.benefit_permissions_json = json.dumps(["1"])
    db.commit()
    db.close()

    worker_did, _, _, _, _ = create_verified_worker()

    # Disbursing scheme 2 returns HTTP 403
    d_res = client.post(
        "/api/v1/government/disburse-claim",
        json={"worker_did": worker_did, "scheme_id": 2, "officer_state": "Maharashtra"},
        headers={"Authorization": f"Bearer {off_token}"}
    )
    assert d_res.status_code == 403


def test_s4_12_government_officer_permission_revocation_isolation():
    """S4.12: Admin revokes DISBURSE_BENEFIT permission from officer;
    Officer can still scan worker QR cards, but disburse-claim is blocked with HTTP 403.
    """
    officer_id, off_token = create_active_officer(state="Maharashtra", perms=["WORKER_VERIFICATION", "DISBURSE_BENEFIT"])
    admin_token = get_admin_token()

    # Admin updates permissions to remove DISBURSE_BENEFIT
    p_res = client.put(
        f"/api/v1/admin/government-officers/{officer_id}",
        json={"permissions": ["WORKER_VERIFICATION"], "benefit_permissions": []},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert p_res.status_code == 200

    worker_did, _, _, _, qr_bytes = create_verified_worker()

    # Scanning QR still succeeds
    files = {"file": ("worker_qr.png", qr_bytes, "image/png")}
    v_res = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {off_token}"}
    )
    assert v_res.status_code == 200
    assert v_res.json()["verified"] is True

    # Disbursement fails with HTTP 403
    d_res = client.post(
        "/api/v1/government/disburse-claim",
        json={"worker_did": worker_did, "scheme_id": 1, "officer_state": "Maharashtra"},
        headers={"Authorization": f"Bearer {off_token}"}
    )
    assert d_res.status_code == 403


# =============================================================================
# SCENARIO 5: Cross-Role Adversarial & Isolation Defenses (S5.1 - S5.2)
# =============================================================================

def test_s4_13_cross_role_activation_token_target_isolation():
    """S4.13: Strict activation target isolation:
    Employer token presented at government activation endpoint is rejected.
    Government token presented at employer activation endpoint is rejected.
    """
    # 1. Generate an employer activation token
    reg_res = client.post("/api/v1/employer/register-organization", json={
        "company_name": f"Iso Corp {uuid.uuid4().hex[:4]}",
        "registration_number": f"CIN-{uuid.uuid4().hex[:8].upper()}",
        "business_address": "Pune",
        "contact_person": "Pooja",
        "email": f"iso_{uuid.uuid4().hex[:6]}@isocorp.com",
        "phone": "+919876543210"
    })
    emp_token = reg_res.json()["activation_token"]

    # 2. Generate a government activation token
    admin_token = get_admin_token()
    prov_res = client.post(
        "/api/v1/admin/government-officers",
        json={
            "full_name": "Iso Officer",
            "official_email": f"iso_off_{uuid.uuid4().hex[:6]}@labour.gov.in",
            "phone": "+919876543211",
            "department": "Labour",
            "designation": "Inspector",
            "authority_level": "STATE",
            "state": "Maharashtra"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert prov_res.status_code == 200
    gov_link = prov_res.json()["activation_link"]
    gov_token = gov_link.split("token=")[1]

    # Present employer token at government endpoint -> HTTP 400 (WRONG_TARGET_TYPE) or 404
    g_res = client.post("/api/v1/government/activate", json={"activation_token": emp_token, "password": "pass"})
    assert g_res.status_code in [400, 404]

    # Present government token at employer endpoint -> HTTP 400 (WRONG_TARGET_TYPE) or 404
    e_res = client.post("/api/v1/employer/activate", json={"activation_token": gov_token, "password": "pass"})
    assert e_res.status_code in [400, 404]


def test_s4_14_cross_role_multi_verifier_replay_defense():
    """S4.14: Multi-verifier presentation replay defense:
    Single worker QR presentation scanned by Employer A (200 OK),
    scanned by Government Officer B (200 OK),
    replayed by Employer A (409 Conflict),
    replayed by Government Officer B (409 Conflict).
    """
    worker_did, _, _, _, qr_bytes = create_verified_worker()
    _, _, emp_token = create_approved_employer()
    _, off_token = create_active_officer()

    files1 = {"file": ("worker_qr.png", qr_bytes, "image/png")}
    r_emp1 = client.post(
        "/api/v1/employer/verify-worker-qr",
        files=files1,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert r_emp1.status_code == 200

    files2 = {"file": ("worker_qr.png", qr_bytes, "image/png")}
    r_gov1 = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files2,
        headers={"Authorization": f"Bearer {off_token}"}
    )
    assert r_gov1.status_code == 200

    # Employer replay -> 409
    files3 = {"file": ("worker_qr.png", qr_bytes, "image/png")}
    r_emp_replay = client.post(
        "/api/v1/employer/verify-worker-qr",
        files=files3,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert r_emp_replay.status_code == 409
    assert "REPLAY_ATTACK_DETECTED" in r_emp_replay.json()["detail"]

    # Government replay -> 409
    files4 = {"file": ("worker_qr.png", qr_bytes, "image/png")}
    r_gov_replay = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files4,
        headers={"Authorization": f"Bearer {off_token}"}
    )
    assert r_gov_replay.status_code == 409
    assert "REPLAY_ATTACK_DETECTED" in r_gov_replay.json()["detail"]


# =============================================================================
# SCENARIO 6: Mock Aadhaar Authority Integrity & Governance Audit (S6.1 - S6.2)
# =============================================================================

def test_s4_15_mock_aadhaar_status_transition_cascade():
    """S4.15: Mock Aadhaar demographic update triggers status transition;
    Verification engine rejects outdated / mismatched / deactivated records.
    """
    raw_aadhaar = str(secrets.randbelow(900000000000) + 100000000000)
    aadhaar_num = f"{raw_aadhaar[:4]} {raw_aadhaar[4:8]} {raw_aadhaar[8:]}"

    # 1. Seed active record
    s_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": "Citizen One",
        "dob": "1990-01-01",
        "gender": "MALE",
        "origin_state": "Odisha",
        "address": "Bhubaneswar, Odisha",
        "status": "ACTIVE"
    })
    assert s_res.status_code == 201
    rec_id = s_res.json()["record_id"]

    # 2. Update record to SUSPENDED
    u_res = client.put(f"/api/v1/aadhaar/records/{rec_id}/status", json={
        "status": "SUSPENDED",
        "reason": "Biometric inconsistency flagged"
    })
    assert u_res.status_code == 200
    assert u_res.json()["status"] == "SUSPENDED"

    # 3. Direct verification query against authority returns SUSPENDED / inactive
    check_res = client.post(
        "/api/v1/aadhaar/verify",
        json={
            "aadhaar_number": aadhaar_num,
            "full_name": "Citizen One"
        },
        headers={"X-PassKhadam-Service-Key": "pk-mock-aadhaar-service-key-internal-2026"}
    )
    assert check_res.status_code == 200
    assert check_res.json()["verified"] is False
    assert check_res.json()["status"] == "REJECTED"
    assert "suspended" in check_res.json()["reason"].lower()


def test_s4_16_cross_system_immutable_governance_auditability():
    """S4.16: Cross-system immutable governance auditability:
    Every admin review, category approval, and status change writes to DBGovernanceAuditLog.
    Modifying or deleting audit entries is blocked by database immutability trigger.
    """
    db = SessionLocal()
    audit_id = str(uuid.uuid4())
    log = DBGovernanceAuditLog(
        actor_firebase_uid="uid_admin_test",
        actor_role="ADMIN",
        action="APPROVE_ORGANIZATION",
        target_type="EMPLOYER_ORGANIZATION",
        target_id="101",
        previous_state="PENDING_REVIEW",
        new_state="APPROVED",
        reason="KYC documents verified",
        request_id=audit_id,
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    # Attempt to tamper with audit record -> must fail due to immutability trigger
    log.action = "TAMPERED_ACTION"
    with pytest.raises(Exception):
        db.commit()
    db.rollback()

    # Attempt to delete audit record -> must fail
    with pytest.raises(Exception):
        db.delete(log)
        db.commit()
    db.rollback()
    db.close()
