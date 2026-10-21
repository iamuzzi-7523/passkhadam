"""
backend/tests/test_m3_challenger.py
Adversarial Stress Harness for Milestone 3 Worker Onboarding Lifecycle:
1. Sequential State Machine Transitions:
   NOT_STARTED -> AADHAAR_SUBMITTED -> DID_GENERATED -> VC_ISSUED -> EVM_ANCHORED -> ACTIVE
2. Strict Idempotency Stress Testing:
   - Repeated POST /api/v1/worker/register (10x successive calls -> 0 duplicates, 0 ValueError)
   - Repeated POST /api/v1/worker/verify-aadhaar/me (10x successive calls -> 0 duplicate on-chain tx, 0 ValueError)
3. Partial Failure Handling & Resumption:
   - Network / RPC timeout -> FAILED state with failure_reason recorded
   - EVM transaction revert -> FAILED state with failure_reason recorded
   - Mock Aadhaar failure -> FAILED state with failure_reason recorded
   - Resumption after failure -> retrying transitions cleanly to ACTIVE
4. Negative Boundaries & Security Invariants:
   - Client DID injection rejection across all entrypoints
   - Cross-account Aadhaar identity collision defense
   - Cross-role access denial on /lifecycle-status/me
"""

import os
import sys
import uuid
import json
import hashlib
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service
from app.services.ipfs_service import ipfs_service
from app.core.crypto import generate_worker_did

client = TestClient(app)


def _create_worker_user(name="Challenger Worker", initial_state="NOT_STARTED"):
    db = SessionLocal()
    uid = f"uid_challenger_{uuid.uuid4().hex[:12]}"
    email = f"challenger_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name=name,
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
        full_name=name,
        origin_state="Maharashtra",
        current_state="Maharashtra",
        worker_category="Plumber",
        skills_json=json.dumps(["Plumber", "Pipefitting"]),
        did_state=initial_state
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=name)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = user.id
    db.close()
    return user_id, email, token, headers


# ============================================================================
# 1. Sequential State Machine Transitions
# ============================================================================

def test_challenger_01_sequential_state_machine_steps():
    """Verify that worker profile progresses through the strict 6-state sequence."""
    user_id, _, _, headers = _create_worker_user(name="Mohammed Uzair", initial_state="NOT_STARTED")

    db = SessionLocal()
    initial_p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert initial_p.did_state == "NOT_STARTED"
    assert initial_p.is_credential_anchored is False
    assert initial_p.did is None
    db.close()

    # Step: Execute verification
    payload = {"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["did_state"] == "ACTIVE"
    assert body["status"] == "ANCHORED_ON_BLOCKCHAIN"
    assert body["did"].startswith("did:passkhadam:worker:")
    assert body["ipfs_cid"].startswith("Qm")
    assert body["credential_hash"].startswith("0x")
    assert body["tx_hash"] is not None
    assert body["block_number"] is not None

    # Verify lifecycle-status endpoint reflects completed steps
    status_res = client.get("/api/v1/worker/lifecycle-status/me", headers=headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["current_state"] == "ACTIVE"
    assert status_data["is_aadhaar_verified"] is True
    assert status_data["is_credential_anchored"] is True
    expected_steps = ["NOT_STARTED", "AADHAAR_SUBMITTED", "DID_GENERATED", "VC_ISSUED", "EVM_ANCHORED", "ACTIVE"]
    assert status_data["steps_completed"] == expected_steps
    assert "VIEW_WALLET" in status_data["allowed_next_actions"]
    assert "GENERATE_QR_CARD" in status_data["allowed_next_actions"]


# ============================================================================
# 2. Strict Idempotency Stress Testing (Zero Duplicate Records, Zero ValueError)
# ============================================================================

def test_challenger_02_registration_10x_repeated_idempotency():
    """Call POST /api/v1/worker/register 10 times consecutively with identical payload.
    Must return 200 every time with 0 duplicate records and 0 ValueError exceptions."""
    email = f"stress_reg_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Idempotent Stress Worker",
        "email": email,
        "phone": "+91 9876543210",
        "password": "strong_password_123",
        "origin_state": "Karnataka",
        "worker_category": "Carpenter"
    }

    initial_res = client.post("/api/v1/worker/register", json=payload)
    assert initial_res.status_code == 200
    initial_user_id = initial_res.json()["user"]["id"]

    # Replay 9 more times
    for i in range(9):
        replay_res = client.post("/api/v1/worker/register", json=payload)
        assert replay_res.status_code == 200, f"Failed on iteration {i+1}: {replay_res.text}"
        data = replay_res.json()
        assert data["success"] is True
        assert data["user"]["id"] == initial_user_id
        assert "Existing worker profile resolved idempotently" in data["message"]

    # Verify database has strictly 1 record
    db = SessionLocal()
    user_count = db.query(DBUser).filter(DBUser.email == email.lower()).count()
    profile_count = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == initial_user_id).count()
    db.close()

    assert user_count == 1, f"Expected 1 user record, found {user_count}"
    assert profile_count == 1, f"Expected 1 profile record, found {profile_count}"


def test_challenger_03_verify_aadhaar_10x_repeated_idempotency():
    """Call POST /api/v1/worker/verify-aadhaar/me 10 times consecutively on an ACTIVE worker.
    Must return 200 every time with 0 duplicate on-chain transactions and 0 ValueError exceptions."""
    user_id, _, _, headers = _create_worker_user(name="Mohammed Uzair", initial_state="NOT_STARTED")
    payload = {"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}

    # Initial verification to reach ACTIVE
    first_res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert first_res.status_code == 200
    first_data = first_res.json()
    canonical_did = first_data["did"]
    canonical_tx = first_data["tx_hash"]
    canonical_cid = first_data["ipfs_cid"]

    # Replay 10 times consecutively
    for i in range(10):
        replay_res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        assert replay_res.status_code == 200, f"Replay {i+1} failed with {replay_res.status_code}: {replay_res.text}"
        rep_data = replay_res.json()
        assert rep_data["did"] == canonical_did
        assert rep_data["tx_hash"] == canonical_tx
        assert rep_data["ipfs_cid"] == canonical_cid
        assert rep_data.get("is_idempotent_replay") is True
        assert rep_data["did_state"] == "ACTIVE"

    # Confirm profile state remains undisturbed
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "ACTIVE"
    assert p.is_credential_anchored is True
    assert p.did == canonical_did
    db.close()


# ============================================================================
# 3. Partial Failure Handling & Resumption Stress Testing
# ============================================================================

def test_challenger_04_evm_rpc_timeout_sets_failed_and_resumes():
    """Simulate RPC ConnectionError during EVM anchoring:
    - Profile must transition to FAILED
    - failure_reason must record connection failure details
    - HTTP 503 is returned
    - Retrying when RPC recovers transitions cleanly to ACTIVE"""
    user_id, _, _, headers = _create_worker_user(name="Sunita Devi", initial_state="NOT_STARTED")
    payload = {"aadhaar_number": "554433221100", "full_name": "Sunita Devi"}

    # Simulate RPC failure
    with patch.object(blockchain_service, "register_worker", side_effect=ConnectionError("HTTPConnectionPool(host='127.0.0.1', port=8545): Max retries exceeded")):
        fail_res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        assert fail_res.status_code == 503
        assert "RPC connection failure" in fail_res.json()["detail"]

    # Verify database state after failure
    db = SessionLocal()
    p_fail = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p_fail.did_state == "FAILED"
    assert p_fail.is_credential_anchored is False
    assert "RPC connection failure" in p_fail.failure_reason
    db.close()

    # Verify lifecycle-status endpoint reflects FAILED
    status_fail = client.get("/api/v1/worker/lifecycle-status/me", headers=headers)
    assert status_fail.status_code == 200
    assert status_fail.json()["current_state"] == "FAILED"
    assert "RETRY_VERIFICATION" in status_fail.json()["allowed_next_actions"]

    # Retry when RPC recovered
    retry_res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert retry_res.status_code == 200
    retry_data = retry_res.json()
    assert retry_data["did_state"] == "ACTIVE"
    assert retry_data["status"] == "ANCHORED_ON_BLOCKCHAIN"

    # Verify database state after recovery
    db = SessionLocal()
    p_rec = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p_rec.did_state == "ACTIVE"
    assert p_rec.is_credential_anchored is True
    assert p_rec.failure_reason is None
    db.close()


def test_challenger_05_evm_revert_sets_failed_and_records_reason():
    """Simulate on-chain execution revert:
    - Profile transitions to FAILED
    - failure_reason captures the revert error
    - HTTP 502 returned"""
    user_id, _, _, headers = _create_worker_user(name="Sunita Devi", initial_state="NOT_STARTED")
    payload = {"aadhaar_number": "554433221100", "full_name": "Sunita Devi"}

    with patch.object(blockchain_service, "register_worker", side_effect=RuntimeError("Transaction failed on-chain (reverted)")):
        fail_res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        assert fail_res.status_code == 502
        assert "reverted" in fail_res.json()["detail"]

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "FAILED"
    assert p.is_credential_anchored is False
    assert "reverted" in p.failure_reason
    db.close()


def test_challenger_06_mock_aadhaar_failure_sets_failed():
    """Name mismatch or invalid Aadhaar records FAILED state in DB."""
    user_id, _, _, headers = _create_worker_user(name="Impostor", initial_state="NOT_STARTED")
    payload = {"aadhaar_number": "123456784821", "full_name": "Wrong Name"}

    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert res.status_code == 400
    assert "Name mismatch" in res.json()["detail"]

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "FAILED"
    assert "Name mismatch" in p.failure_reason
    db.close()


# ============================================================================
# 4. Security Invariants & Defensive Guardrails
# ============================================================================

def test_challenger_07_client_supplied_did_rejected_in_registration():
    """Submitting client-supplied DID during registration must be rejected with 400/422."""
    payload = {
        "full_name": "Attacker Worker",
        "email": f"attacker_{uuid.uuid4().hex[:8]}@example.com",
        "phone": "+91 9876543210",
        "did": "did:passkhadam:worker:attacker_injected_did"
    }
    res = client.post("/api/v1/worker/register", json=payload)
    assert res.status_code in [400, 422]
    assert "Client-supplied DID is strictly forbidden" in res.text


def test_challenger_08_cross_account_aadhaar_theft_rejected():
    """Worker B cannot hijack Worker A's verified Aadhaar identity."""
    # Worker A verifies
    _, _, _, headers_a = _create_worker_user(name="Mohammed Uzair", initial_state="NOT_STARTED")
    res_a = client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers_a)
    assert res_a.status_code == 200

    # Worker B tries to claim Worker A's Aadhaar
    _, _, _, headers_b = _create_worker_user(name="Attacker Worker", initial_state="NOT_STARTED")
    res_b = client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers_b)
    assert res_b.status_code == 409
    assert "already registered and anchored to another account" in res_b.json()["detail"]


def test_challenger_09_unanchored_qr_card_access_denied():
    """Worker in NOT_STARTED state is forbidden from generating QR presentation card."""
    _, _, _, headers = _create_worker_user(name="Unanchored Worker", initial_state="NOT_STARTED")
    res = client.get("/api/v1/worker/presentation/qr-card/me", headers=headers)
    assert res.status_code == 400
    assert "not anchored a verified decentralized identity" in res.json()["detail"]


def test_challenger_10_cross_role_access_to_lifecycle_status_forbidden():
    """Non-worker principal (Employer or Government) cannot query /lifecycle-status/me."""
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200
    emp_token = emp_login.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    res = client.get("/api/v1/worker/lifecycle-status/me", headers=emp_headers)
    assert res.status_code == 403
    assert "Only workers can access this endpoint" in res.json()["detail"]
