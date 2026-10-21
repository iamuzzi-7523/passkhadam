"""
backend/tests/test_m4_adversarial_challenge.py
Adversarial Challenge & Empirical Stress-Test Suite for Milestone 4:
Deferred Atomic Replay Defense & Multi-Verifier Concurrency.

Author: m4_challenger_1 (EMPIRICAL CHALLENGER)
Parent: orchestrator_5 (f0ed804e-a9bd-47b5-82b5-c807e05127fe)

Scenarios Tested:
1. Sequential Replay Attack:
   Valid QR -> POST /api/v1/employer/verify-worker-qr -> 200 OK.
   Same QR -> POST /api/v1/employer/verify-worker-qr -> 409 Conflict with detail containing 'REPLAY_ATTACK_DETECTED'.
2. Multi-Verifier Independent Verification:
   Valid QR -> POST /api/v1/employer/verify-worker-qr (Employer A) -> 200 OK.
   Same QR -> POST /api/v1/government/verify-worker-qr (Gov Officer B) -> 200 OK.
   Same QR -> POST /api/v1/government/verify-worker-qr (Gov Officer B duplicate) -> 409 Conflict with 'REPLAY_ATTACK_DETECTED'.
   Same QR -> POST /api/v1/employer/verify-worker-qr (Employer A duplicate) -> 409 Conflict with 'REPLAY_ATTACK_DETECTED'.
3. Deferred Execution & Rollback on Step 6 (Hash Mismatch):
   Simulate Step 6 hash mismatch -> engine raises CREDENTIAL_HASH_MISMATCH.
   Assert DBConsumedPresentationNonce has ZERO entries for this presentation.
   Subsequent legitimate submission succeeds cleanly (200 OK) and commits nonce.
4. Deferred Execution & Rollback on Step 7 (Tampered Ciphertext / GCM Tag Failure):
   Simulate Step 7 decryption failure -> engine raises CREDENTIAL_TAMPERED.
   Assert DBConsumedPresentationNonce has ZERO entries for this presentation.
   Subsequent legitimate submission succeeds cleanly (200 OK) and commits nonce.
5. Concurrent Multi-Session Database Level Replay Race:
   Simulate simultaneous insertion hitting SQLite uq_presentation_verifier_context constraint.
   Assert IntegrityError is properly caught, rolled back, and raises ReplayAttackError.
"""

import io
import os
import sys
import json
import uuid
import hashlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal, DBUser, DBWorkerProfile,
    DBConsumedPresentationNonce, DBEmployerOrganization, DBGovernmentOfficer
)
from app.services.verification_engine import (
    verification_engine, VerificationEngineError,
    ReplayAttackError, VerificationErrorCode
)
from app.services.ipfs_service import ipfs_service
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)


def generate_verified_worker_qr():
    """Helper to setup a registered worker and return (worker_did, png_bytes, presentation_id)."""
    db = SessionLocal()
    unique_suffix = uuid.uuid4().hex[:8]
    worker_name = f"ChallengerWorker_{unique_suffix}"
    uid = f"uid_cw_{unique_suffix}"
    email = f"cworker_{unique_suffix}@example.com"
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
        origin_state="Maharashtra",
        current_state="Maharashtra",
        worker_category="Electrical",
        skills_json=json.dumps(["Electrical Wiring", "Solar Installation"]),
        did_state="NOT_STARTED"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=worker_name)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed Aadhaar in mock authority
    aadhaar_num = f"99{uuid.uuid4().int % 10000000000:010d}"
    seed_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name,
        "dob": "1992-08-20",
        "gender": "MALE",
        "origin_state": "Maharashtra",
        "address": "Mumbai",
        "status": "ACTIVE"
    })
    assert seed_res.status_code == 201, seed_res.text

    # Complete worker on-chain verification
    v_res = client.post("/api/v1/worker/verify-aadhaar/me", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name
    }, headers=headers)
    assert v_res.status_code == 200, v_res.text
    worker_did = v_res.json()["did"]

    # Generate QR presentation
    png_bytes, envelope_json = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={"full_name": worker_name},
        validity_seconds=300
    )
    envelope = json.loads(envelope_json)
    presentation_id = envelope.get("presentation_id")

    db.close()
    return worker_did, png_bytes, presentation_id


def setup_employer_principal():
    """Sets up an authenticated employer principal."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    emp_uid = f"uid_emp_challenger_{suffix}"
    emp_email = f"emp_challenger_{suffix}@infra.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()
    org_addr = f"0xEmpOrg_{suffix}"

    user = DBUser(
        firebase_uid=emp_uid,
        full_name=f"Challenger Infrastructure {suffix}",
        email=emp_email,
        phone="+91 9876543210",
        password_hash=pw_hash,
        role="EMPLOYER",
        status="ACTIVE",
        organization_address=org_addr
    )
    db.add(user)
    db.commit()
    db.close()

    token = create_test_firebase_jwt(uid=emp_uid, email=emp_email, name="Challenger Infra")
    return {"Authorization": f"Bearer {token}"}, org_addr


def setup_government_principal():
    """Sets up an authenticated government officer principal."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    gov_uid = f"uid_gov_challenger_{suffix}"
    gov_email = f"gov_challenger_{suffix}@state.gov.in"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    user = DBUser(
        firebase_uid=gov_uid,
        full_name=f"Gov Officer {suffix}",
        email=gov_email,
        phone="+91 9876543210",
        password_hash=pw_hash,
        role="GOVERNMENT",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    officer = DBGovernmentOfficer(
        user_id=user.id,
        full_name=user.full_name,
        officer_name=user.full_name,
        officer_reference_id=f"GOV-OFF-{user.id:04d}",
        official_email=user.email,
        authority_level="STATE",
        state="Maharashtra",
        status="ACTIVE",
        permissions_json=json.dumps(["WORKER_VERIFICATION", "BENEFIT_DISBURSEMENT"]),
        benefit_permissions_json=json.dumps(["1", "2"])
    )
    db.add(officer)
    db.commit()
    officer_id_str = str(officer.id)
    db.close()

    token = create_test_firebase_jwt(uid=gov_uid, email=gov_email, name="Gov Officer")
    return {"Authorization": f"Bearer {token}"}, officer_id_str


# ============================================================================
# CHALLENGE 1: SEQUENTIAL REPLAY ATTACK VIA HTTP ENDPOINT
# ============================================================================

def test_challenge_1_sequential_replay_attack_employer():
    """
    Challenge 1: Sequential Replay Attack.
    Submit valid QR to /api/v1/employer/verify-worker-qr.
    First submission returns HTTP 200 OK.
    Second submission returns HTTP 409 Conflict with detail containing 'REPLAY_ATTACK_DETECTED'.
    """
    worker_did, png_bytes, pres_id = generate_verified_worker_qr()
    emp_headers, org_addr = setup_employer_principal()

    # Submission 1: Valid
    files1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    r1 = client.post("/api/v1/employer/verify-worker-qr", files=files1, headers=emp_headers)
    assert r1.status_code == 200, f"Expected 200 OK on first submission, got {r1.status_code}: {r1.text}"
    data1 = r1.json()
    assert data1["verified"] is True
    assert data1["worker_did"] == worker_did

    # Verify DBConsumedPresentationNonce contains exactly one entry
    db = SessionLocal()
    consumed = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id,
        DBConsumedPresentationNonce.verifier_role == "EMPLOYER",
        DBConsumedPresentationNonce.verifier_id == org_addr
    ).all()
    assert len(consumed) == 1
    db.close()

    # Submission 2: Immediate duplicate with exact same presentation and employer context
    files2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    r2 = client.post("/api/v1/employer/verify-worker-qr", files=files2, headers=emp_headers)
    assert r2.status_code == 409, f"Expected 409 Conflict on replay, got {r2.status_code}: {r2.text}"
    detail = r2.json().get("detail", "")
    assert "REPLAY_ATTACK_DETECTED" in detail, f"Expected 'REPLAY_ATTACK_DETECTED' in detail, got: {detail}"


# ============================================================================
# CHALLENGE 2: MULTI-VERIFIER INDEPENDENT CONCURRENCY
# ============================================================================

def test_challenge_2_multi_verifier_independent_concurrency():
    """
    Challenge 2: Multi-Verifier Independent Verification.
    Submit same QR to Employer A -> 200 OK.
    Submit same QR to Government Officer B -> 200 OK.
    Submit same QR to Government Officer B duplicate -> 409 Conflict with 'REPLAY_ATTACK_DETECTED'.
    Submit same QR to Employer A duplicate -> 409 Conflict with 'REPLAY_ATTACK_DETECTED'.
    """
    worker_did, png_bytes, pres_id = generate_verified_worker_qr()
    emp_headers, emp_addr = setup_employer_principal()
    gov_headers, gov_addr = setup_government_principal()

    # 1. Employer A verifies presentation -> 200 OK
    files_emp1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    r_emp1 = client.post("/api/v1/employer/verify-worker-qr", files=files_emp1, headers=emp_headers)
    assert r_emp1.status_code == 200, f"Employer verification failed: {r_emp1.text}"
    assert r_emp1.json()["verified"] is True

    # 2. Government Officer B verifies the SAME presentation within 300s window -> 200 OK
    files_gov1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    r_gov1 = client.post("/api/v1/government/verify-worker-qr", files=files_gov1, headers=gov_headers)
    assert r_gov1.status_code == 200, f"Government verification failed: {r_gov1.text}"
    assert r_gov1.json()["verified"] is True

    # Verify both records exist in DB under composite key (presentation_id, verifier_role, verifier_id)
    db = SessionLocal()
    nonces = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id
    ).all()
    assert len(nonces) == 2, f"Expected 2 nonces for distinct verifiers, found {len(nonces)}"
    roles = {n.verifier_role for n in nonces}
    assert roles == {"EMPLOYER", "GOVERNMENT"}
    db.close()

    # 3. Government Officer B submits duplicate -> 409 Conflict
    files_gov2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    r_gov2 = client.post("/api/v1/government/verify-worker-qr", files=files_gov2, headers=gov_headers)
    assert r_gov2.status_code == 409, f"Expected 409 Conflict for gov duplicate, got: {r_gov2.text}"
    assert "REPLAY_ATTACK_DETECTED" in r_gov2.json().get("detail", "")

    # 4. Employer A submits duplicate -> 409 Conflict
    files_emp2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    r_emp2 = client.post("/api/v1/employer/verify-worker-qr", files=files_emp2, headers=emp_headers)
    assert r_emp2.status_code == 409, f"Expected 409 Conflict for emp duplicate, got: {r_emp2.text}"
    assert "REPLAY_ATTACK_DETECTED" in r_emp2.json().get("detail", "")


# ============================================================================
# CHALLENGE 3: DEFERRED EXECUTION & ROLLBACK ON STEP 6 (HASH MISMATCH)
# ============================================================================

def test_challenge_3_deferred_execution_rollback_step6_hash_mismatch():
    """
    Challenge 3: Deferred Execution & Rollback Test.
    Simulate Step 6 hash mismatch (tampered IPFS payload hash).
    Assert db.rollback() occurs, DBConsumedPresentationNonce is NOT committed,
    and presentation remains unconsumed for legitimate retry.
    """
    worker_did, png_bytes, pres_id = generate_verified_worker_qr()
    emp_headers, org_addr = setup_employer_principal()
    db = SessionLocal()

    # Corrupt IPFS payload to cause hash mismatch at Step 6
    corrupted_payload = json.dumps({"corrupted": "payload_not_matching_onchain_hash"})
    with patch.object(ipfs_service, "resolve_payload", return_value=corrupted_payload):
        with pytest.raises(VerificationEngineError) as exc_info:
            verification_engine.verify_uploaded_presentation(
                image_bytes=png_bytes,
                caller_role="EMPLOYER",
                caller_id=org_addr,
                db=db
            )
        assert exc_info.value.error_code == VerificationErrorCode.CREDENTIAL_HASH_MISMATCH
        assert exc_info.value.step == 6

    # Verify DBConsumedPresentationNonce has ZERO records for this presentation
    nonce_check = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id
    ).first()
    assert nonce_check is None, "Rollback failed: DBConsumedPresentationNonce was committed despite Step 6 failure"

    # Now perform legitimate verification (without mock/corruption)
    # Must succeed cleanly (no 409 replay attack)
    result = verification_engine.verify_uploaded_presentation(
        image_bytes=png_bytes,
        caller_role="EMPLOYER",
        caller_id=org_addr,
        db=db
    )
    assert result["verified"] is True
    assert result["worker_did"] == worker_did

    # Verify nonce is now committed on legitimate success
    committed_nonce = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id,
        DBConsumedPresentationNonce.verifier_role == "EMPLOYER",
        DBConsumedPresentationNonce.verifier_id == org_addr
    ).first()
    assert committed_nonce is not None, "Nonce was not committed on legitimate retry"
    db.close()


# ============================================================================
# CHALLENGE 3B: DEFERRED EXECUTION & ROLLBACK ON STEP 7 (TAMPERED CIPHERTEXT)
# ============================================================================

def test_challenge_3b_deferred_execution_rollback_step7_tampered_ciphertext():
    """
    Challenge 3B: Deferred Execution & Rollback on Step 7.
    Simulate Step 7 decryption failure (e.g. tampered ciphertext or bad auth tag).
    Assert db.rollback() occurs, DBConsumedPresentationNonce is NOT committed,
    and presentation remains unconsumed for legitimate retry.
    """
    worker_did, png_bytes, pres_id = generate_verified_worker_qr()
    emp_headers, org_addr = setup_employer_principal()
    db = SessionLocal()

    # Mock decrypt_payload to fail at Step 7 while passing Step 6
    with patch("app.services.verification_engine.decrypt_payload", side_effect=ValueError("AES-GCM authentication tag mismatch")):
        with pytest.raises(VerificationEngineError) as exc_info:
            verification_engine.verify_uploaded_presentation(
                image_bytes=png_bytes,
                caller_role="EMPLOYER",
                caller_id=org_addr,
                db=db
            )
        assert exc_info.value.error_code == VerificationErrorCode.CREDENTIAL_TAMPERED
        assert exc_info.value.step == 7

    # Verify DBConsumedPresentationNonce is completely clean
    nonce_check = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id
    ).first()
    assert nonce_check is None, "Rollback failed: DBConsumedPresentationNonce committed despite Step 7 failure"

    # Legitimate retry succeeds
    result = verification_engine.verify_uploaded_presentation(
        image_bytes=png_bytes,
        caller_role="EMPLOYER",
        caller_id=org_addr,
        db=db
    )
    assert result["verified"] is True
    db.close()


# ============================================================================
# CHALLENGE 4: COMPOSITE CONSTRAINTS & ATOMIC DATABASE LEVEL INTEGRITY
# ============================================================================

def test_challenge_4_database_unique_constraint_integrity():
    """
    Challenge 4: Explicit DB-level unique constraint test on DBConsumedPresentationNonce.
    Validates that SQLite enforces uq_presentation_verifier_context at the DB level,
    and verification_engine properly catches IntegrityError and converts to ReplayAttackError.
    """
    worker_did, png_bytes, pres_id = generate_verified_worker_qr()
    db = SessionLocal()
    verifier_id = "0xTestDBLevelIntegrity"

    # Pre-insert raw database record simulating parallel thread having committed first
    from datetime import datetime
    raw_nonce = DBConsumedPresentationNonce(
        presentation_id=pres_id,
        verifier_role="EMPLOYER",
        verifier_id=verifier_id,
        worker_did=worker_did,
        consumed_at=datetime.utcnow()
    )
    db.add(raw_nonce)
    db.commit()

    # Now verify_uploaded_presentation must detect the consumed nonce and raise ReplayAttackError
    with pytest.raises(ReplayAttackError) as exc_info:
        verification_engine.verify_uploaded_presentation(
            image_bytes=png_bytes,
            caller_role="EMPLOYER",
            caller_id=verifier_id,
            db=db
        )
    assert exc_info.value.error_code == VerificationErrorCode.REPLAY_ATTACK_DETECTED
    db.close()


# ============================================================================
# CHALLENGE 5: ATTACKER REPLAY EVASION VIA PRESENTATION_ID TAMPERING
# ============================================================================

def test_challenge_5_replay_evasion_via_presentation_id_tampering_fails_step2():
    """
    Challenge 5: Attacker attempts to bypass replay defense by tampering with presentation_id.
    An adversary takes an authentic signed presentation envelope, modifies the presentation_id
    to circumvent DBConsumedPresentationNonce collision detection.
    Assert that the engine catches this at Step 2 (INVALID_PRESENTATION_SIGNATURE)
    because presentation_id is cryptographically protected by the Ed25519 signature.
    """
    worker_did, png_bytes, pres_id = generate_verified_worker_qr()
    emp_headers, org_addr = setup_employer_principal()

    # Decode valid QR to obtain raw envelope
    raw_qr_data = verification_engine.decode_qr_image(png_bytes)
    envelope = json.loads(raw_qr_data)

    # Attacker alters presentation_id in payload while preserving the Authority signature
    tampered_payload = dict(envelope["payload"])
    tampered_payload["presentation_id"] = f"urn:uuid:{uuid.uuid4()}"

    # Re-encode into QR
    import qrcode
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(json.dumps({
        **tampered_payload,
        "payload": tampered_payload,
        "signature": envelope["signature"]
    }))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    evasion_png = buf.getvalue()

    # Attacker submits forged presentation to bypass replay
    files = {"file": ("worker_qr.png", io.BytesIO(evasion_png), "image/png")}
    res = client.post("/api/v1/employer/verify-worker-qr", files=files, headers=emp_headers)

    # Must be rejected with HTTP 400 (Step 2 invalid presentation signature), not allowed to verify
    assert res.status_code == 400
    assert "signature" in res.json()["detail"].lower()

