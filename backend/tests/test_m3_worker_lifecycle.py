"""
backend/tests/test_m3_worker_lifecycle.py
Comprehensive Milestone 3 Test Suite:
- 6-State Worker Onboarding Lifecycle Machine (NOT_STARTED -> ACTIVE)
- Duplicate Registration Idempotency on POST /api/v1/worker/register
- Duplicate Aadhaar Verification Idempotency on /verify-aadhaar/me
- Cross-Worker Aadhaar Collision Rejection (409 Conflict)
- Client-Supplied DID Rejection (HTTP 400 Bad Request)
- W3C Verifiable Credential Structure, RFC 8785 Canonicalization & ISO 8601 issuanceDate
- EVM Anchoring Failure, Recovery and Resumption
- Self-Service /lifecycle-status/me Inspection
- Zero-PII IPFS Defensive Validation
"""

import os
import sys
import json
import uuid
import base64
import hashlib
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.core.config import settings
from app.models.db import SessionLocal, DBUser, DBWorkerProfile
from app.models.schemas import (
    WorkerRegisterRequest, WorkerRegisterResponse,
    WorkerLifecycleStatusResponse, AadhaarVerifyRequest,
    WorkerProfileUpdate
)
from app.core.crypto import (
    generate_worker_did, encrypt_payload, decrypt_payload,
    sign_credential, verify_credential_signature, canonical_json_bytes,
    build_w3c_verifiable_credential, get_payload_secret_key
)
from app.services.blockchain_service import blockchain_service
from app.services.ipfs_service import ipfs_service
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)


# ----------------------------------------------------------------------------
# Test Fixtures & Helpers
# ----------------------------------------------------------------------------

def create_isolated_worker(name="Test Worker", aadhaar=None, initial_state="NOT_STARTED"):
    """Creates a clean, isolated worker user and profile in the database."""
    db = SessionLocal()
    uid = f"uid_worker_{uuid.uuid4().hex[:12]}"
    email = f"worker_{uuid.uuid4().hex[:8]}@example.com"
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
        origin_state="Karnataka",
        current_state="Karnataka",
        worker_category="Mason",
        skills_json=json.dumps(["Mason", "Plumbing Assistance"]),
        did_state=initial_state
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    user_id = user.id
    token = create_test_firebase_jwt(uid=uid, email=email, name=name)
    headers = {"Authorization": f"Bearer {token}"}
    db.close()
    return user_id, email, token, headers


# ----------------------------------------------------------------------------
# 1. Worker Registration Idempotency Tests (POST /api/v1/worker/register)
# ----------------------------------------------------------------------------

def test_01_worker_registration_fresh():
    """Fresh worker registration creates user and profile in NOT_STARTED state."""
    test_email = f"fresh_worker_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Fresh Worker",
        "email": test_email,
        "phone": "+91 9876543210",
        "password": "passkhadam123",
        "origin_state": "Karnataka",
        "worker_category": "Electrician",
        "skills": ["Electrician", "Wiring"]
    }
    res = client.post("/api/v1/worker/register", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["did_state"] == "NOT_STARTED"
    assert "access_token" in data
    assert data["user"]["email"] == test_email.lower()
    assert data["profile"]["worker_category"] == "Electrician"

    # Confirm in DB
    db = SessionLocal()
    u = db.query(DBUser).filter(DBUser.email == test_email.lower()).first()
    assert u is not None
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == u.id).first()
    assert p is not None
    assert p.did_state == "NOT_STARTED"
    db.close()


def test_02_worker_registration_duplicate_idempotent():
    """Duplicate registration with matching credentials returns existing profile cleanly (idempotent 200)."""
    test_email = f"idempotent_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Idempotent Worker",
        "email": test_email,
        "phone": "+91 9876543210",
        "password": "passkhadam123"
    }

    # First registration
    r1 = client.post("/api/v1/worker/register", json=payload)
    assert r1.status_code == 200
    user_id_1 = r1.json()["user"]["id"]

    # Re-registration with exact same credentials
    r2 = client.post("/api/v1/worker/register", json=payload)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["success"] is True
    assert data2["user"]["id"] == user_id_1
    assert "Existing worker profile resolved idempotently" in data2["message"]

    # Verify database count has not duplicated
    db = SessionLocal()
    count = db.query(DBUser).filter(DBUser.email == test_email.lower()).count()
    assert count == 1
    db.close()


def test_03_worker_registration_password_mismatch_conflict():
    """Duplicate registration with different password raises HTTP 409 Conflict."""
    test_email = f"conflict_{uuid.uuid4().hex[:8]}@example.com"
    payload1 = {
        "full_name": "Original Worker",
        "email": test_email,
        "phone": "+91 9876543210",
        "password": "correct_password"
    }
    r1 = client.post("/api/v1/worker/register", json=payload1)
    assert r1.status_code == 200

    # Submitting with different password
    payload2 = {
        "full_name": "Impostor Worker",
        "email": test_email,
        "phone": "+91 9876543210",
        "password": "wrong_password"
    }
    r2 = client.post("/api/v1/worker/register", json=payload2)
    assert r2.status_code == 409
    assert "User with this email already exists" in r2.json()["detail"]


def test_04_worker_registration_with_immediate_aadhaar():
    """Registration with immediate valid Aadhaar executes complete onboarding to ACTIVE."""
    test_email = f"auto_onboard_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Mohammed Uzair",
        "email": test_email,
        "phone": "+91 9876543210",
        "password": "passkhadam123",
        "aadhaar_number": "123456784821"
    }
    res = client.post("/api/v1/worker/register", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["did_state"] == "ACTIVE"
    assert data["profile"]["is_aadhaar_verified"] is True
    assert data["profile"]["is_credential_anchored"] is True
    assert data["profile"]["did"] is not None
    assert data["profile"]["did"].startswith("did:passkhadam:worker:")


# ----------------------------------------------------------------------------
# 2. 6-State Worker Lifecycle Progression & Idempotency
# ----------------------------------------------------------------------------

def test_05_lifecycle_state_progression_sequential():
    """Verifies complete 6-state progression: NOT_STARTED -> AADHAAR_SUBMITTED -> DID_GENERATED -> VC_ISSUED -> EVM_ANCHORED -> ACTIVE."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")

    # Step: Submit Aadhaar Verification
    req_body = {
        "aadhaar_number": "123456784821",
        "full_name": "Mohammed Uzair"
    }
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=req_body, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["verified"] is True
    assert data["did_state"] == "ACTIVE"
    assert data["status"] == "ANCHORED_ON_BLOCKCHAIN"
    assert data["did"].startswith("did:passkhadam:worker:")
    assert data["ipfs_cid"].startswith("Qm")
    assert data["credential_hash"].startswith("0x")
    assert data["tx_hash"] is not None
    assert data["block_number"] is not None


def test_06_verify_aadhaar_idempotency_for_active_worker():
    """Calling /verify-aadhaar/me again for an active worker returns existing anchored state without duplicate EVM calls."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    req_body = {"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}

    # Call 1
    r1 = client.post("/api/v1/worker/verify-aadhaar/me", json=req_body, headers=headers)
    assert r1.status_code == 200
    first_did = r1.json()["did"]
    first_tx = r1.json()["tx_hash"]

    # Call 2 (idempotent replay)
    r2 = client.post("/api/v1/worker/verify-aadhaar/me", json=req_body, headers=headers)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["did"] == first_did
    assert data2["tx_hash"] == first_tx
    assert data2.get("is_idempotent_replay") is True


def test_07_verify_aadhaar_mismatched_aadhaar_rejection():
    """An already ACTIVE worker attempting to verify a different Aadhaar identity is rejected with HTTP 409 Conflict."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    # Verify initially as Uzair
    client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers)

    # Attempt to re-verify using Ramesh's Aadhaar
    res = client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "987654321012", "full_name": "Ramesh Kumar Verma"}, headers=headers)
    assert res.status_code == 409
    assert "Worker already holds an active credential with a different Aadhaar identity" in res.json()["detail"]


def test_08_cross_account_aadhaar_collision_rejected():
    """Worker B attempting to verify Aadhaar identity already anchored to Worker A is rejected with HTTP 409 Conflict."""
    # Worker A verifies Aadhaar
    _, _, _, headers_a = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    r_a = client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers_a)
    assert r_a.status_code == 200

    # Worker B attempts to claim the same Aadhaar
    _, _, _, headers_b = create_isolated_worker(name="Worker B Impostor", initial_state="NOT_STARTED")
    r_b = client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers_b)
    assert r_b.status_code == 409
    assert "already registered and anchored to another account" in r_b.json()["detail"]


# ----------------------------------------------------------------------------
# 3. Client-Supplied DID Rejection Security Invariant
# ----------------------------------------------------------------------------

def test_09_client_supplied_did_rejected_on_verify():
    """Client submitting 'did' in /verify-aadhaar/me request payload is rejected with HTTP 400 Bad Request."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    payload = {
        "aadhaar_number": "123456784821",
        "full_name": "Mohammed Uzair",
        "did": "did:passkhadam:worker:attacker_crafted_did_123"
    }
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert res.status_code in [400, 422]
    assert "Client-supplied DID is strictly forbidden" in res.text


def test_10_client_supplied_worker_did_rejected_on_verify():
    """Client submitting 'worker_did' in /verify-aadhaar/me request payload is rejected with HTTP 400 Bad Request."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    payload = {
        "aadhaar_number": "123456784821",
        "full_name": "Mohammed Uzair",
        "worker_did": "did:passkhadam:worker:malicious_did"
    }
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert res.status_code in [400, 422]
    assert "Client-supplied DID is strictly forbidden" in res.text


def test_11_client_supplied_did_rejected_on_profile_update():
    """Client attempting to update profile with 'did' or 'worker_did' on PUT /profile/me is rejected."""
    _, _, _, headers = create_isolated_worker(name="Test Worker", initial_state="NOT_STARTED")
    payload = {
        "worker_category": "Carpenter",
        "did": "did:passkhadam:worker:spoofed_did"
    }
    res = client.put("/api/v1/worker/profile/me", json=payload, headers=headers)
    assert res.status_code in [400, 422]
    assert "Client-supplied DID is strictly forbidden" in res.text


def test_12_schema_validation_rejects_client_did_directly():
    """Direct Pydantic model instantiation with 'did' raises ValueError."""
    with pytest.raises(ValueError, match="Client-supplied DID is strictly forbidden"):
        AadhaarVerifyRequest.model_validate({
            "aadhaar_number": "123456784821",
            "full_name": "Mohammed Uzair",
            "did": "did:passkhadam:worker:fake"
        })

    with pytest.raises(ValueError, match="Client-supplied DID is strictly forbidden"):
        WorkerProfileUpdate.model_validate({
            "worker_category": "Mason",
            "worker_did": "did:passkhadam:worker:fake"
        })


# ----------------------------------------------------------------------------
# 4. Lifecycle Status Self-Service Inspection (/lifecycle-status/me)
# ----------------------------------------------------------------------------

def test_13_lifecycle_status_not_started():
    """Initial /lifecycle-status/me for fresh worker returns NOT_STARTED and VERIFY_AADHAAR next action."""
    _, _, _, headers = create_isolated_worker(name="Test Worker", initial_state="NOT_STARTED")
    res = client.get("/api/v1/worker/lifecycle-status/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["current_state"] == "NOT_STARTED"
    assert data["is_aadhaar_verified"] is False
    assert data["is_credential_anchored"] is False
    assert data["steps_completed"] == []
    assert "VERIFY_AADHAAR" in data["allowed_next_actions"]


def test_14_lifecycle_status_active():
    """Active worker /lifecycle-status/me reports all 6 steps completed and provenance fields."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers)

    res = client.get("/api/v1/worker/lifecycle-status/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["current_state"] == "ACTIVE"
    assert data["is_aadhaar_verified"] is True
    assert data["is_credential_anchored"] is True
    assert data["did"] is not None
    assert data["ipfs_cid"] is not None
    assert data["credential_hash"] is not None
    assert data["tx_hash"] is not None
    assert data["block_number"] is not None
    assert "ACTIVE" in data["steps_completed"]
    assert "VIEW_WALLET" in data["allowed_next_actions"]
    assert "GENERATE_QR_CARD" in data["allowed_next_actions"]


# ----------------------------------------------------------------------------
# 5. Mock Aadhaar Error Handling & Failure States
# ----------------------------------------------------------------------------

def test_15_mock_aadhaar_name_mismatch_failure():
    """Name mismatch against Aadhaar authority transitions profile to FAILED with 400 Bad Request."""
    user_id, _, _, headers = create_isolated_worker(name="Wrong Name", initial_state="NOT_STARTED")
    payload = {
        "aadhaar_number": "123456784821", # belogns to Mohammed Uzair
        "full_name": "Completely Wrong Name"
    }
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert res.status_code == 400
    assert "Name mismatch" in res.json()["detail"]

    # Check profile recorded FAILED state in database
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "FAILED"
    assert p.failure_reason is not None
    assert "Name mismatch" in p.failure_reason
    db.close()


def test_16_mock_aadhaar_inactive_record_failure():
    """Inactive Aadhaar number (998877665544) fails and records failure_reason."""
    user_id, _, _, headers = create_isolated_worker(name="Lakshmi Narayana", initial_state="NOT_STARTED")
    payload = {
        "aadhaar_number": "998877665544",
        "full_name": "Lakshmi Narayana"
    }
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert res.status_code == 400
    assert "inactive" in res.json()["detail"].lower()

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "FAILED"
    assert "inactive" in p.failure_reason.lower()
    db.close()


def test_17_mock_aadhaar_nonexistent_record_failure():
    """Non-existent Aadhaar number fails verification with 400."""
    user_id, _, _, headers = create_isolated_worker(name="Ghost Worker", initial_state="NOT_STARTED")
    payload = {
        "aadhaar_number": "000011112222",
        "full_name": "Ghost Worker"
    }
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert res.status_code == 400
    assert "not found" in res.json()["detail"].lower()

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "FAILED"
    db.close()


# ----------------------------------------------------------------------------
# 6. EVM Anchoring Failure & Resumption
# ----------------------------------------------------------------------------

def test_18_blockchain_anchoring_failure_transitions_to_failed():
    """Simulated EVM failure marks profile as FAILED without marking credential anchored."""
    user_id, _, _, headers = create_isolated_worker(name="Sunita Devi", initial_state="NOT_STARTED")
    payload = {"aadhaar_number": "554433221100", "full_name": "Sunita Devi"}

    with patch.object(blockchain_service, "register_worker", side_effect=RuntimeError("EVM node gas exhaustion revert")):
        res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        assert res.status_code == 502
        assert "EVM node gas exhaustion revert" in res.json()["detail"]

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "FAILED"
    assert p.is_credential_anchored is False
    assert "EVM node gas exhaustion revert" in p.failure_reason
    db.close()


def test_19_resumption_from_failed_state_to_active():
    """Retrying verification after a previous failure resumes and successfully reaches ACTIVE."""
    user_id, _, _, headers = create_isolated_worker(name="Sunita Devi", initial_state="NOT_STARTED")
    payload = {"aadhaar_number": "554433221100", "full_name": "Sunita Devi"}

    # Failure on 1st attempt
    with patch.object(blockchain_service, "register_worker", side_effect=ConnectionError("RPC timeout")):
        r1 = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        assert r1.status_code == 503

    # Retry on 2nd attempt (network recovered)
    r2 = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["did_state"] == "ACTIVE"

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert p.did_state == "ACTIVE"
    assert p.is_credential_anchored is True
    assert p.failure_reason is None
    db.close()


# ----------------------------------------------------------------------------
# 7. W3C Verifiable Credential Structure & RFC 8785 Compliance
# ----------------------------------------------------------------------------

def test_20_w3c_vc_canonical_structure():
    """build_w3c_verifiable_credential produces W3C VC v1.1 structure with all required fields."""
    subject = {
        "id": "did:passkhadam:worker:test12345678",
        "full_name": "Mohammed Uzair",
        "worker_category": "Mason",
        "skills": ["Mason"]
    }
    vc = build_w3c_verifiable_credential(subject)
    assert vc["@context"] == ["https://www.w3.org/2018/credentials/v1"]
    assert vc["id"].startswith("urn:uuid:vc-")
    assert vc["type"] == ["VerifiableCredential", "WorkerIdentityCredential"]
    assert vc["issuer"] == "did:passkhadam:authority:identity-gateway"
    assert "issuanceDate" in vc
    assert vc["credentialSubject"] == subject
    assert "proof" in vc
    assert vc["proof"]["type"] == "Ed25519Signature2020"
    assert vc["proof"]["proofPurpose"] == "assertionMethod"
    assert vc["proof"]["verificationMethod"] == "did:passkhadam:authority:identity-gateway#key-1"
    assert "signatureValue" in vc["proof"]


def test_21_w3c_vc_issuance_date_format():
    """issuanceDate adheres to ISO 8601 UTC representation (YYYY-MM-DDTHH:MM:SSZ)."""
    subject = {"id": "did:passkhadam:worker:test12345678", "full_name": "Test"}
    vc = build_w3c_verifiable_credential(subject)
    issuance_date = vc["issuanceDate"]
    assert issuance_date.endswith("Z")
    parsed = datetime.strptime(issuance_date, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed.year >= 2026


def test_22_w3c_vc_ed25519_proof_verification():
    """Ed25519 signature in VC proof cryptographically verifies against credentialSubject."""
    subject = {
        "id": "did:passkhadam:worker:test9999",
        "full_name": "Anil Sahu",
        "origin_state": "Odisha",
        "skills": ["Plumber"]
    }
    vc = build_w3c_verifiable_credential(subject)
    sig_hex = vc["proof"]["signatureValue"]
    assert verify_credential_signature(vc["credentialSubject"], sig_hex) is True

    # Tampered credentialSubject fails verification
    tampered_subject = dict(subject)
    tampered_subject["full_name"] = "Attacker"
    assert verify_credential_signature(tampered_subject, sig_hex) is False


def test_23_rfc8785_canonical_json_bytes_consistency():
    """canonical_json_bytes outputs identical bytes regardless of dict key insertion order."""
    d1 = {"b": 2, "a": 1, "c": {"y": 20, "x": 10}}
    d2 = {"a": 1, "c": {"x": 10, "y": 20}, "b": 2}
    assert canonical_json_bytes(d1) == canonical_json_bytes(d2)
    assert b" " not in canonical_json_bytes(d1) # compact separators


# ----------------------------------------------------------------------------
# 8. Zero-PII IPFS Defensive Validation
# ----------------------------------------------------------------------------

def test_24_ipfs_pin_payload_rejects_plaintext_json():
    """ipfs_service.pin_payload raises ValueError if passed plaintext JSON starting with '{' or '['."""
    with pytest.raises(ValueError, match="Zero-PII violation: Plaintext JSON payload cannot be pinned"):
        ipfs_service.pin_payload('{"name": "Mohammed Uzair", "aadhaar": "123456784821"}')

    with pytest.raises(ValueError, match="Zero-PII violation: Plaintext JSON payload cannot be pinned"):
        ipfs_service.pin_payload('[{"name": "Worker"}]')


def test_25_ipfs_pin_payload_rejects_empty_or_invalid_b64():
    """ipfs_service.pin_payload rejects empty or non-base64 input."""
    with pytest.raises(ValueError, match="non-empty base64 string"):
        ipfs_service.pin_payload("")

    with pytest.raises(ValueError, match="Invalid base64 ciphertext payload"):
        ipfs_service.pin_payload("NotValidBase64!@#$")


# ----------------------------------------------------------------------------
# 9. Presentation Card & Wallet Gate Invariants
# ----------------------------------------------------------------------------

def test_26_qr_presentation_requires_anchored_identity():
    """Worker in NOT_STARTED or FAILED state cannot generate QR card (returns 400)."""
    _, _, _, headers = create_isolated_worker(name="Unanchored Worker", initial_state="NOT_STARTED")
    res = client.get("/api/v1/worker/presentation/qr-card/me", headers=headers)
    assert res.status_code == 400
    assert "Worker has not anchored a verified decentralized identity yet" in res.json()["detail"]


def test_27_qr_presentation_succeeds_for_active_worker():
    """Active worker successfully receives time-bound QR card with signed presentation envelope."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers)

    res = client.get("/api/v1/worker/presentation/qr-card/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["qr_base64_data_uri"].startswith("data:image/png;base64,")
    assert data["expires_in_seconds"] == 300
    assert "raw_envelope" in data
    assert data["raw_envelope"]["worker_did"].startswith("did:passkhadam:worker:")


def test_28_generate_worker_did_determinism_and_salt():
    """generate_worker_did uses settings.DID_SALT and produces consistent, collision-resistant DIDs."""
    did1 = generate_worker_did("123456784821", "Mohammed Uzair")
    did2 = generate_worker_did("123456784821", "Mohammed Uzair")
    assert did1 == did2
    assert did1.startswith("did:passkhadam:worker:")

    # Different Aadhaar produces distinct DID
    did3 = generate_worker_did("987654321012", "Ramesh Kumar Verma")
    assert did1 != did3

    # Optional name works
    did_no_name = generate_worker_did("123456784821")
    assert did_no_name.startswith("did:passkhadam:worker:")


def test_29_aes_gcm_payload_encryption_roundtrip():
    """encrypt_payload and decrypt_payload roundtrip accurately using derived vault key."""
    test_dict = {
        "did": "did:passkhadam:worker:abcdef123456",
        "full_name": "Test Worker",
        "category": "Mason",
        "random_int": 42
    }
    encrypted = encrypt_payload(test_dict)
    assert isinstance(encrypted, str)
    assert not encrypted.startswith("{")
    assert not encrypted.startswith("[")

    decrypted = decrypt_payload(encrypted)
    assert decrypted == test_dict


def test_30_wallet_reflects_anchored_credentials():
    """Active worker wallet returns all 4 standard verifiable credentials."""
    _, _, _, headers = create_isolated_worker(name="Mohammed Uzair", initial_state="NOT_STARTED")
    client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=headers)

    res = client.get("/api/v1/worker/wallet/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_verified"] is True
    assert len(data["credentials"]) >= 4
    types = [c["type"] for c in data["credentials"]]
    assert "Worker Identity Credential" in types
    assert "Safety Credential" in types
    assert "Skill Credential" in types
