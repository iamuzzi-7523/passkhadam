"""
backend/tests/test_government_officer_authorization.py
Milestone 4: Canonical Government Officer Authorization Alignment (R5)
======================================================================
Comprehensive test suite verifying:
1. Active state officer with WORKER_VERIFICATION in matching state verifies worker QR successfully.
2. Zero EVM address checks (EVM address strings are never returned or checked).
3. Inactive/suspended officer rejected with HTTP 403.
4. Officer lacking WORKER_VERIFICATION permission rejected with HTTP 403.
5. Officer with mismatched jurisdiction rejected with HTTP 403.
6. Unlinked officer user rejected with HTTP 404.
7. Replay defense nonce record keyed by (presentation_id, "GOVERNMENT", str(officer.id)).
8. Calling verification engine with arbitrary EVM caller ID strictly fails Step 10 with OFFICER_NOT_FOUND.
9. Unlinked government account with EVM address returns 404 without auto-provisioning.
"""

import io
import os
import sys
import json
import uuid
import hashlib
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBGovernmentOfficer,
    DBWorkerProfile,
    DBConsumedPresentationNonce
)
from app.core.auth import create_test_firebase_jwt
from app.services.verification_engine import (
    verification_engine,
    VerificationEngineError,
    VerificationErrorCode
)

client = TestClient(app)


# =============================================================================
# Helper Utilities
# =============================================================================

def create_isolated_officer(
    status: str = "ACTIVE",
    authority_level: str = "STATE",
    state: str = "Maharashtra",
    district: str = None,
    block: str = None,
    permissions: list = None,
    wallet_address: str = None
) -> tuple[int, int, str]:
    """Creates a dedicated government officer and user, returning (user_id, officer_id, jwt_token)."""
    db = SessionLocal()
    u_uid = f"uid_gov_{uuid.uuid4().hex[:8]}"
    email = f"officer_{uuid.uuid4().hex[:6]}@maharashtra.gov.in"
    name = f"Officer {uuid.uuid4().hex[:4]}"

    user = DBUser(
        firebase_uid=u_uid,
        full_name=name,
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="GOVERNMENT",
        status="ACTIVE" if status == "ACTIVE" else status,
        organization_address=wallet_address
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    officer = DBGovernmentOfficer(
        user_id=user.id,
        full_name=name,
        officer_name=name,
        officer_reference_id=f"GOV-OFF-{uuid.uuid4().hex[:8].upper()}",
        official_email=email,
        phone="+919876543210",
        wallet_address=wallet_address,
        authority_level=authority_level,
        state=state,
        district=district,
        block=block,
        department="Labour Welfare Department",
        designation="Welfare Commissioner",
        status=status,
        permissions_json=json.dumps(permissions if permissions is not None else ["WORKER_VERIFICATION"]),
        benefit_permissions_json=json.dumps(["SCHEME_001"])
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)

    user_id = user.id
    officer_id = officer.id
    db.close()

    token = create_test_firebase_jwt(uid=u_uid, email=email, name=name)
    return user_id, officer_id, token


def setup_active_worker_qr(worker_state: str = "Maharashtra"):
    """Sets up an anchored active worker in worker_state and returns their QR presentation bytes."""
    db = SessionLocal()
    worker_name = f"VerifWorker_{uuid.uuid4().hex[:6]}"
    uid = f"uid_{uuid.uuid4().hex[:10]}"
    email = f"worker_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

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
        origin_state=worker_state,
        current_state=worker_state,
        worker_category="Mason",
        skills_json=json.dumps(["Mason", "Plumbing Assistance"]),
        did_state="NOT_STARTED"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=worker_name)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed Mock Aadhaar
    aadhaar_num = f"88{uuid.uuid4().int % 10000000000:010d}"
    seed_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name,
        "dob": "1994-05-15",
        "gender": "MALE",
        "origin_state": worker_state,
        "address": f"Capital City, {worker_state}",
        "status": "ACTIVE"
    })
    assert seed_res.status_code == 201, seed_res.text

    # Verify Aadhaar
    v_res = client.post("/api/v1/worker/verify-aadhaar/me", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name
    }, headers=headers)
    assert v_res.status_code == 200, v_res.text
    worker_did = v_res.json()["did"]

    # Generate QR presentation
    png_bytes, _ = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={
            "full_name": worker_name,
            "origin_state": worker_state,
            "current_state": worker_state
        },
        validity_seconds=300
    )
    db.close()
    return worker_did, worker_name, png_bytes


# =============================================================================
# Milestone 4 Tests: 7 Canonical Test Cases
# =============================================================================

def test_1_active_state_officer_verifies_worker_qr_successfully():
    """
    Test 1: Active state officer with WORKER_VERIFICATION in matching state
    verifies worker QR presentation successfully via both route endpoints.
    """
    _, officer_id, token = create_isolated_officer(
        status="ACTIVE",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"]
    )
    worker_did, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")

    headers = {"Authorization": f"Bearer {token}"}

    # Test via /verify-worker-qr
    files = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res = client.post("/api/v1/government/verify-worker-qr", files=files, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["verified"] is True
    assert data["worker_did"] == worker_did
    assert "masked_aadhaar" in data["data"]
    assert len(data["audit_steps"]) == 11
    assert "GOVERNMENT" in data["audit_steps"][9]["detail"]

    # Test via /verify-worker alias with a fresh presentation
    _, _, png_bytes_alias = setup_active_worker_qr(worker_state="Maharashtra")
    files_alias = {"file": ("worker_qr.png", io.BytesIO(png_bytes_alias), "image/png")}
    res_alias = client.post("/api/v1/government/verify-worker", files=files_alias, headers=headers)
    assert res_alias.status_code == 200, res_alias.text
    assert res_alias.json()["verified"] is True


def test_2_zero_evm_address_checks_and_isolation():
    """
    Test 2: Zero EVM address checks.
    The officer has wallet_address=None, no 0x... EVM address is required,
    and no EVM address is returned or evaluated in Step 10.
    """
    _, officer_id, token = create_isolated_officer(
        status="ACTIVE",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"],
        wallet_address=None
    )
    worker_did, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")

    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res = client.post("/api/v1/government/verify-worker", files=files, headers=headers)

    assert res.status_code == 200, res.text
    body_text = res.text
    assert "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65" not in body_text
    assert "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC" not in body_text

    # Verify officer profile does not enforce or require EVM address
    prof_res = client.get("/api/v1/government/profile/me", headers=headers)
    assert prof_res.status_code == 200
    assert "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65" not in prof_res.text


def test_3_inactive_or_suspended_officer_rejected_with_403():
    """
    Test 3: Suspended or inactive officer is rejected with HTTP 403.
    """
    # 3a. Suspended officer
    _, _, token_suspended = create_isolated_officer(
        status="SUSPENDED",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"]
    )
    _, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")
    files = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res_suspended = client.post("/api/v1/government/verify-worker", files=files, headers={"Authorization": f"Bearer {token_suspended}"})
    assert res_suspended.status_code == 403, res_suspended.text

    # 3b. Inactive / Provisioned officer
    _, _, token_inactive = create_isolated_officer(
        status="PROVISIONED",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"]
    )
    files2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res_inactive = client.post("/api/v1/government/verify-worker", files=files2, headers={"Authorization": f"Bearer {token_inactive}"})
    assert res_inactive.status_code == 403, res_inactive.text


def test_4_officer_lacking_worker_verification_permission_rejected_with_403():
    """
    Test 4: Officer lacking 'WORKER_VERIFICATION' permission is rejected with HTTP 403.
    """
    _, _, token_no_perm = create_isolated_officer(
        status="ACTIVE",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["BENEFIT_DISBURSEMENT"]  # Missing WORKER_VERIFICATION
    )
    _, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")
    files = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res = client.post("/api/v1/government/verify-worker", files=files, headers={"Authorization": f"Bearer {token_no_perm}"})

    assert res.status_code == 403, res.text
    assert "WORKER_VERIFICATION" in res.text or "permission" in res.text.lower()


def test_5_officer_with_mismatched_jurisdiction_rejected_with_403():
    """
    Test 5: Officer with Maharashtra jurisdiction attempting to verify a Karnataka worker
    (without CROSS_STATE_VERIFICATION) is rejected with HTTP 403.
    """
    _, _, token = create_isolated_officer(
        status="ACTIVE",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"]  # No CROSS_STATE_VERIFICATION
    )
    # Karnataka worker
    _, _, png_bytes = setup_active_worker_qr(worker_state="Karnataka")
    files = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res = client.post("/api/v1/government/verify-worker", files=files, headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 403, res.text
    assert "jurisdiction" in res.text.lower() or "cover" in res.text.lower()


def test_6_unlinked_officer_user_rejected_with_404():
    """
    Test 6: User with GOVERNMENT role but no linked DBGovernmentOfficer record
    is rejected with HTTP 404 (Government officer profile not found).
    """
    db = SessionLocal()
    u_uid = f"uid_gov_unlinked_{uuid.uuid4().hex[:6]}"
    email = f"unlinked_{uuid.uuid4().hex[:6]}@gov.in"
    user = DBUser(
        firebase_uid=u_uid,
        full_name="Unlinked Government User",
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="GOVERNMENT",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.close()

    token = create_test_firebase_jwt(uid=u_uid, email=email, name="Unlinked Government User")
    _, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")
    files = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res = client.post("/api/v1/government/verify-worker", files=files, headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 404, res.text
    assert "Government officer profile not found" in res.text


def test_7_replay_defense_nonce_keyed_by_canonical_officer_id():
    """
    Test 7: Replay defense nonce record is keyed by (presentation_id, 'GOVERNMENT', str(officer.id)).
    A duplicate upload by the same officer returns HTTP 409 Conflict.
    """
    _, officer_id, token = create_isolated_officer(
        status="ACTIVE",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"]
    )
    worker_did, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. First upload: HTTP 200 OK
    files1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res1 = client.post("/api/v1/government/verify-worker", files=files1, headers=headers)
    assert res1.status_code == 200, res1.text
    pres_id = res1.json()["presentation_id"]

    # Assert record in DBConsumedPresentationNonce is keyed with canonical str(officer.id)
    db = SessionLocal()
    nonce_rec = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id,
        DBConsumedPresentationNonce.verifier_role == "GOVERNMENT",
        DBConsumedPresentationNonce.verifier_id == str(officer_id)
    ).first()
    assert nonce_rec is not None
    assert nonce_rec.verifier_role == "GOVERNMENT"
    assert nonce_rec.verifier_id == str(officer_id)
    db.close()

    # 2. Replay presentation: HTTP 409 Conflict
    files2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res2 = client.post("/api/v1/government/verify-worker", files=files2, headers=headers)
    assert res2.status_code == 409, res2.text
    assert "already consumed" in res2.text.lower() or "replay" in res2.text.lower()


def test_8_arbitrary_evm_caller_id_strictly_fails_step_10():
    """
    Test 8: Calling verification_engine.verify_uploaded_presentation with caller_role="GOVERNMENT"
    and an arbitrary EVM address (e.g. "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65")
    strictly fails Step 10 with VerificationEngineError and detail="OFFICER_NOT_FOUND".
    Proves zero EVM address bypass paths exist in the verification engine.
    """
    worker_did, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")
    db = SessionLocal()

    evm_caller_ids = [
        "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
        "0xdeadbeef",
        "0x0000000000000000000000000000000000000000",
        "0XABCDEF"
    ]

    for evm_id in evm_caller_ids:
        with pytest.raises(VerificationEngineError) as exc_info:
            verification_engine.verify_uploaded_presentation(
                image_bytes=png_bytes,
                caller_role="GOVERNMENT",
                caller_id=evm_id,
                db=db
            )
        err = exc_info.value
        assert err.step == 10
        assert err.error_code == VerificationErrorCode.VERIFIER_UNAUTHORIZED
        assert err.detail == "OFFICER_NOT_FOUND"

    db.close()


def test_9_unlinked_government_account_with_evm_address_returns_404_no_autoprovision():
    """
    Test 9: Calling POST /api/v1/government/verify-worker and /verify-worker-qr with a government user
    having organization_address="0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65" and NO linked
    DBGovernmentOfficer returns HTTP 404 and creates ZERO DBGovernmentOfficer rows.
    Proves elimination of the auto-provisioning backdoor across both route endpoints.
    """
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    u_uid = f"uid_gov_backdoor_test_{suffix}"
    email = f"backdoor_test_{suffix}@state.gov.in"
    evm_address = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"

    user = DBUser(
        firebase_uid=u_uid,
        full_name="Unlinked EVM Gov User",
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="GOVERNMENT",
        status="ACTIVE",
        organization_address=evm_address
    )
    db.add(user)
    db.commit()
    user_id = user.id

    # Verify no DBGovernmentOfficer exists initially for this user or email
    initial_count = db.query(DBGovernmentOfficer).filter(
        (DBGovernmentOfficer.user_id == user_id) |
        (DBGovernmentOfficer.official_email == email)
    ).count()
    assert initial_count == 0

    token = create_test_firebase_jwt(uid=u_uid, email=email, name="Unlinked EVM Gov User")
    _, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test POST /api/v1/government/verify-worker
    files1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res1 = client.post("/api/v1/government/verify-worker", files=files1, headers=headers)
    assert res1.status_code == 404, f"Expected 404, got {res1.status_code}: {res1.text}"
    assert "Government officer profile not found" in res1.text

    # 2. Test POST /api/v1/government/verify-worker-qr
    files2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res2 = client.post("/api/v1/government/verify-worker-qr", files=files2, headers=headers)
    assert res2.status_code == 404, f"Expected 404, got {res2.status_code}: {res2.text}"
    assert "Government officer profile not found" in res2.text

    # Assert ZERO DBGovernmentOfficer records were created across both calls
    post_count = db.query(DBGovernmentOfficer).filter(
        (DBGovernmentOfficer.user_id == user_id) |
        (DBGovernmentOfficer.official_email == email)
    ).count()
    assert post_count == 0, "Security violation: DBGovernmentOfficer was auto-provisioned!"
    db.close()


def test_10_distinct_officers_verify_same_presentation_independently():
    """
    Test 10: Replay defense segregation under composite key (presentation_id, 'GOVERNMENT', str(officer.id)).
    Two distinct authorized officers can independently verify the same valid presentation.
    A duplicate submission by either officer returns HTTP 409 Conflict.
    """
    # Officer 1 in Maharashtra
    _, officer_id_1, token_1 = create_isolated_officer(
        status="ACTIVE",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"]
    )

    # Officer 2 in Maharashtra
    _, officer_id_2, token_2 = create_isolated_officer(
        status="ACTIVE",
        authority_level="STATE",
        state="Maharashtra",
        permissions=["WORKER_VERIFICATION"]
    )

    worker_did, _, png_bytes = setup_active_worker_qr(worker_state="Maharashtra")
    headers_1 = {"Authorization": f"Bearer {token_1}"}
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    # 1. Officer 1 verifies presentation: HTTP 200 OK
    files_1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res_1 = client.post("/api/v1/government/verify-worker-qr", files=files_1, headers=headers_1)
    assert res_1.status_code == 200, res_1.text
    pres_id_1 = res_1.json()["presentation_id"]

    # 2. Officer 2 independently verifies the SAME presentation: HTTP 200 OK
    files_2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res_2 = client.post("/api/v1/government/verify-worker-qr", files=files_2, headers=headers_2)
    assert res_2.status_code == 200, res_2.text
    pres_id_2 = res_2.json()["presentation_id"]
    assert pres_id_1 == pres_id_2

    # 3. Officer 1 submits again (duplicate replay): HTTP 409 Conflict
    files_replay_1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res_replay_1 = client.post("/api/v1/government/verify-worker-qr", files=files_replay_1, headers=headers_1)
    assert res_replay_1.status_code == 409, res_replay_1.text

    # 4. Officer 2 submits again (duplicate replay): HTTP 409 Conflict
    files_replay_2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res_replay_2 = client.post("/api/v1/government/verify-worker-qr", files=files_replay_2, headers=headers_2)
    assert res_replay_2.status_code == 409, res_replay_2.text

    # 5. Verify database contains exactly 2 nonce records (one for each officer context)
    db = SessionLocal()
    nonces = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id_1,
        DBConsumedPresentationNonce.verifier_role == "GOVERNMENT"
    ).all()
    assert len(nonces) == 2
    officer_ids_recorded = {n.verifier_id for n in nonces}
    assert officer_ids_recorded == {str(officer_id_1), str(officer_id_2)}
    db.close()

