"""
backend/tests/test_m3_adversarial_challenger2.py
Milestone 3 Empirical Adversarial Test Harness — Challenger 2

Adversarially attacks identity, DID, and privacy boundaries:
1. Client-supplied DID attack:
   - Requests containing "did" or "worker_did" in payload to:
     * POST /api/v1/worker/verify-aadhaar/me
     * PUT /api/v1/worker/profile/me
     * PUT /api/v1/worker/profile/{id} (worker and admin callers)
     * POST /api/v1/worker/verify-aadhaar/{id} (worker and admin callers)
     * POST /api/v1/worker/register
   - Confirm all rejected with HTTP 400 Bad Request.

2. Cross-account identity collision:
   - Worker B submits Aadhaar belonging to Worker A.
   - Confirm system returns HTTP 409 Conflict.
   - Confirm Worker A's identity and on-chain records remain uncorrupted.

3. Plaintext IPFS injection:
   - Attempt to pin plaintext JSON string to ipfs_service.pin_payload.
   - Attempt to pin JSON arrays, stripped JSON, short base64, invalid characters, empty strings.
   - Confirm defensive assertion raises ValueError on all plaintext attempts.

4. Privacy inspection:
   - Verify decrypted IPFS payloads contain RFC 8785 canonical VCs with Ed25519 signatures and ISO 8601 issuanceDate.
   - Verify signature verification passes on valid payload and fails on tampered payload.
   - Verify on-chain records leak zero raw Aadhaar or full demographic PII.
"""

import os
import sys
import re
import json
import uuid
import base64
import hashlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile
from app.core.crypto import (
    generate_worker_did,
    encrypt_payload,
    decrypt_payload,
    verify_credential_signature,
    canonical_json_bytes,
    build_w3c_verifiable_credential,
    keccak_hash,
)
from app.services.ipfs_service import ipfs_service
from app.services.blockchain_service import blockchain_service
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)

RAW_AADHAAR_REGEX = re.compile(r"\b\d{12}\b|\b\d{4}\s\d{4}\s\d{4}\b")
ISO_8601_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def create_test_user(role="WORKER", name="Test Worker", state="NOT_STARTED"):
    """Helper to create test user and profile."""
    db = SessionLocal()
    uid = f"uid_adv_{uuid.uuid4().hex[:12]}"
    email = f"adv_{uuid.uuid4().hex[:8]}@passkhadam.org"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name=name,
        email=email,
        phone="+91 9876543210",
        password_hash=pw_hash,
        role=role,
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = None
    if role == "WORKER":
        profile = DBWorkerProfile(
            user_id=user.id,
            full_name=name,
            origin_state="Karnataka",
            current_state="Karnataka",
            worker_category="Mason",
            skills_json=json.dumps(["Mason", "Plumbing Assistance"]),
            did_state=state
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    user_id = user.id
    token = create_test_firebase_jwt(uid=uid, email=email, name=name)
    headers = {"Authorization": f"Bearer {token}"}
    db.close()
    return user_id, email, token, headers


# ============================================================================
# 1. CLIENT-SUPPLIED DID ATTACK HARNESS
# ============================================================================

class TestClientSuppliedDidAttack:
    """
    Submits requests containing 'did' or 'worker_did' in the payload to:
    - POST /api/v1/worker/verify-aadhaar/me
    - PUT /api/v1/worker/profile/me
    - PUT /api/v1/worker/profile/{id}
    - POST /api/v1/worker/verify-aadhaar/{id}
    - POST /api/v1/worker/register
    Confirms that all are rejected with HTTP 400 Bad Request.
    """

    def test_attack_verify_aadhaar_me_with_did(self):
        """Attacker submits 'did' to /verify-aadhaar/me -> 400 Bad Request."""
        _, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "aadhaar_number": "123456784821",
            "full_name": "Mohammed Uzair",
            "did": "did:passkhadam:worker:injected_did_001"
        }
        res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_verify_aadhaar_me_with_worker_did(self):
        """Attacker submits 'worker_did' to /verify-aadhaar/me -> 400 Bad Request."""
        _, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "aadhaar_number": "123456784821",
            "full_name": "Mohammed Uzair",
            "worker_did": "did:passkhadam:worker:injected_did_002"
        }
        res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_profile_me_put_with_did(self):
        """Attacker submits 'did' to PUT /profile/me -> 400 Bad Request."""
        _, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "worker_category": "Electrician",
            "did": "did:passkhadam:worker:injected_did_003"
        }
        res = client.put("/api/v1/worker/profile/me", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_profile_me_put_with_worker_did(self):
        """Attacker submits 'worker_did' to PUT /profile/me -> 400 Bad Request."""
        _, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "worker_category": "Electrician",
            "worker_did": "did:passkhadam:worker:injected_did_004"
        }
        res = client.put("/api/v1/worker/profile/me", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_profile_id_put_with_did_as_worker(self):
        """Worker submits 'did' to PUT /profile/{id} -> 400 Bad Request."""
        user_id, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "worker_category": "Carpenter",
            "did": "did:passkhadam:worker:injected_did_005"
        }
        res = client.put(f"/api/v1/worker/profile/{user_id}", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_profile_id_put_with_worker_did_as_worker(self):
        """Worker submits 'worker_did' to PUT /profile/{id} -> 400 Bad Request."""
        user_id, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "worker_category": "Carpenter",
            "worker_did": "did:passkhadam:worker:injected_did_006"
        }
        res = client.put(f"/api/v1/worker/profile/{user_id}", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_profile_id_put_with_did_as_admin(self):
        """Admin submits 'did' to PUT /profile/{id} -> 400 Bad Request (guard applies to all callers)."""
        worker_id, _, _, _ = create_test_user(role="WORKER", name="Mohammed Uzair")
        _, _, _, admin_headers = create_test_user(role="ADMIN", name="Super Admin")
        payload = {
            "worker_category": "Plumber",
            "did": "did:passkhadam:worker:admin_injected_did"
        }
        res = client.put(f"/api/v1/worker/profile/{worker_id}", json=payload, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_verify_aadhaar_id_post_with_did_as_worker(self):
        """Worker submits 'did' to POST /verify-aadhaar/{id} -> 400 Bad Request."""
        user_id, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "aadhaar_number": "123456784821",
            "full_name": "Mohammed Uzair",
            "did": "did:passkhadam:worker:injected_did_007"
        }
        res = client.post(f"/api/v1/worker/verify-aadhaar/{user_id}", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_verify_aadhaar_id_post_with_worker_did_as_worker(self):
        """Worker submits 'worker_did' to POST /verify-aadhaar/{id} -> 400 Bad Request."""
        user_id, _, _, headers = create_test_user(role="WORKER", name="Mohammed Uzair")
        payload = {
            "aadhaar_number": "123456784821",
            "full_name": "Mohammed Uzair",
            "worker_did": "did:passkhadam:worker:injected_did_008"
        }
        res = client.post(f"/api/v1/worker/verify-aadhaar/{user_id}", json=payload, headers=headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_verify_aadhaar_id_post_with_did_as_admin(self):
        """Admin submits 'did' to POST /verify-aadhaar/{id} -> 400 Bad Request."""
        worker_id, _, _, _ = create_test_user(role="WORKER", name="Mohammed Uzair")
        _, _, _, admin_headers = create_test_user(role="ADMIN", name="Super Admin")
        payload = {
            "aadhaar_number": "123456784821",
            "full_name": "Mohammed Uzair",
            "did": "did:passkhadam:worker:admin_injected_did"
        }
        res = client.post(f"/api/v1/worker/verify-aadhaar/{worker_id}", json=payload, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Client-supplied DID is strictly forbidden" in res.text

    def test_attack_register_with_did_and_worker_did(self):
        """Client submits 'did' or 'worker_did' during registration -> 400 or 422 Bad Request."""
        p1 = {
            "full_name": "Malicious Worker",
            "email": f"mal_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+91 9999888877",
            "password": "passkhadam123",
            "did": "did:passkhadam:worker:injected_registration_did"
        }
        r1 = client.post("/api/v1/worker/register", json=p1)
        assert r1.status_code in [400, 422]
        assert "Client-supplied DID is strictly forbidden" in r1.text

        p2 = {
            "full_name": "Malicious Worker 2",
            "email": f"mal_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+91 9999888877",
            "password": "passkhadam123",
            "worker_did": "did:passkhadam:worker:injected_registration_did"
        }
        r2 = client.post("/api/v1/worker/register", json=p2)
        assert r2.status_code in [400, 422]
        assert "Client-supplied DID is strictly forbidden" in r2.text


# ============================================================================
# 2. CROSS-ACCOUNT IDENTITY COLLISION ATTACK HARNESS
# ============================================================================

class TestCrossAccountIdentityCollision:
    """
    Worker B submits Aadhaar belonging to Worker A.
    Confirm that system returns HTTP 409 Conflict.
    Confirm that Worker A's state is preserved and not hijacked.
    """

    def test_cross_account_collision_on_verify_aadhaar_me(self):
        """Worker B submits Worker A's Aadhaar to /verify-aadhaar/me -> 409 Conflict."""
        # Step 1: Worker A onboarded and ACTIVE with Aadhaar "123456784821" (Mohammed Uzair)
        worker_a_id, email_a, _, headers_a = create_test_user(role="WORKER", name="Mohammed Uzair")
        res_a = client.post(
            "/api/v1/worker/verify-aadhaar/me",
            json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"},
            headers=headers_a
        )
        assert res_a.status_code == 200
        did_a = res_a.json()["did"]
        tx_a = res_a.json()["tx_hash"]
        assert did_a.startswith("did:passkhadam:worker:")

        # Step 2: Worker B creates an account
        worker_b_id, email_b, _, headers_b = create_test_user(role="WORKER", name="Impostor Worker B")

        # Step 3: Worker B tries to claim Worker A's Aadhaar identity
        res_b = client.post(
            "/api/v1/worker/verify-aadhaar/me",
            json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"},
            headers=headers_b
        )
        assert res_b.status_code == 409, f"Expected 409, got {res_b.status_code}: {res_b.text}"
        assert "already registered and anchored to another account" in res_b.json()["detail"]

        # Step 4: Verify Worker A's state is uncorrupted
        db = SessionLocal()
        prof_a = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == worker_a_id).first()
        assert prof_a.did_state == "ACTIVE"
        assert prof_a.did == did_a
        assert prof_a.tx_hash == tx_a
        assert prof_a.is_credential_anchored is True

        # Verify Worker B's profile did NOT acquire Worker A's DID
        prof_b = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == worker_b_id).first()
        assert prof_b.did != did_a
        assert prof_b.did_state == "NOT_STARTED"
        db.close()

    def test_cross_account_collision_on_parameterized_verify_endpoint(self):
        """Worker B calls POST /verify-aadhaar/{worker_b_id} claiming Worker A's Aadhaar -> 409 Conflict."""
        # Worker A setup with Ramesh Kumar Verma ("987654321012")
        worker_a_id, _, _, headers_a = create_test_user(role="WORKER", name="Ramesh Kumar Verma")
        res_a = client.post(
            "/api/v1/worker/verify-aadhaar/me",
            json={"aadhaar_number": "987654321012", "full_name": "Ramesh Kumar Verma"},
            headers=headers_a
        )
        assert res_a.status_code == 200

        # Worker B setup
        worker_b_id, _, _, headers_b = create_test_user(role="WORKER", name="Attacker B")

        # Worker B targets their own ID but submits Ramesh's Aadhaar
        res_b = client.post(
            f"/api/v1/worker/verify-aadhaar/{worker_b_id}",
            json={"aadhaar_number": "987654321012", "full_name": "Ramesh Kumar Verma"},
            headers=headers_b
        )
        assert res_b.status_code == 409
        assert "already registered and anchored to another account" in res_b.json()["detail"]

    def test_cross_account_collision_via_registration_onboarding(self):
        """Worker B registering with immediate Aadhaar belonging to Worker A -> 409 Conflict."""
        # Worker A registered with Sunita Devi ("554433221100")
        _, _, _, headers_a = create_test_user(role="WORKER", name="Sunita Devi")
        res_a = client.post(
            "/api/v1/worker/verify-aadhaar/me",
            json={"aadhaar_number": "554433221100", "full_name": "Sunita Devi"},
            headers=headers_a
        )
        assert res_a.status_code == 200

        # Worker B registers with Sunita Devi's Aadhaar
        reg_payload = {
            "full_name": "Sunita Devi",
            "email": f"impostor_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+91 9123456789",
            "password": "password123",
            "aadhaar_number": "554433221100"
        }
        res_reg = client.post("/api/v1/worker/register", json=reg_payload)
        assert res_reg.status_code == 409
        assert "already registered and anchored to another account" in res_reg.json()["detail"]


# ============================================================================
# 3. PLAINTEXT IPFS INJECTION ATTACK HARNESS
# ============================================================================

class TestPlaintextIpfsInjection:
    """
    Attempts to pin plaintext JSON string to ipfs_service.pin_payload.
    Confirms that defensive assertion raises ValueError.
    """

    def test_rejects_plaintext_json_object(self):
        """Attempting to pin plaintext JSON object string raises ValueError."""
        plaintext = json.dumps({
            "aadhaar_number": "123456784821",
            "full_name": "Mohammed Uzair",
            "address": "45/2 BTM Layout, Bengaluru"
        })
        with pytest.raises(ValueError, match="Zero-PII violation: Plaintext JSON payload cannot be pinned"):
            ipfs_service.pin_payload(plaintext)

    def test_rejects_plaintext_json_array(self):
        """Attempting to pin plaintext JSON array raises ValueError."""
        plaintext_array = json.dumps([{"secret": "pii_leak"}])
        with pytest.raises(ValueError, match="Zero-PII violation: Plaintext JSON payload cannot be pinned"):
            ipfs_service.pin_payload(plaintext_array)

    def test_rejects_whitespace_padded_json(self):
        """Attempting to pin whitespace-padded plaintext JSON raises ValueError."""
        padded_json = '   \n\t {"leaked_pii": "value"}  \n '
        with pytest.raises(ValueError, match="Zero-PII violation: Plaintext JSON payload cannot be pinned"):
            ipfs_service.pin_payload(padded_json)

    def test_rejects_empty_string(self):
        """Attempting to pin empty string raises ValueError."""
        with pytest.raises(ValueError, match="non-empty base64 string"):
            ipfs_service.pin_payload("")

    def test_rejects_non_string_types(self):
        """Attempting to pin non-string types (dict, list, int) raises ValueError."""
        with pytest.raises(ValueError, match="non-empty base64 string"):
            ipfs_service.pin_payload({"key": "val"})  # type: ignore

        with pytest.raises(ValueError, match="non-empty base64 string"):
            ipfs_service.pin_payload(12345)  # type: ignore

    def test_rejects_invalid_base64_string(self):
        """Attempting to pin non-base64 plaintext string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid base64 ciphertext payload"):
            ipfs_service.pin_payload("This is plain English and not valid base64!!!@@@###$$$")

    def test_rejects_short_base64_payload(self):
        """Payload shorter than AES-GCM nonce (12 bytes) raises ValueError."""
        short_b64 = base64.b64encode(b"too_short").decode("utf-8")  # 9 bytes decoded
        with pytest.raises(ValueError, match="Ciphertext payload too short"):
            ipfs_service.pin_payload(short_b64)

    def test_accepts_valid_aes_gcm_ciphertext(self):
        """Legitimate AES-256-GCM encrypted payload pins successfully returning CIDv0."""
        valid_payload = encrypt_payload({"sub": "valid_data", "ts": 123456789})
        cid = ipfs_service.pin_payload(valid_payload)
        assert cid.startswith("Qm"), f"Expected CIDv0 starting with 'Qm', got {cid}"
        assert len(cid) == 46


# ============================================================================
# 4. PRIVACY INSPECTION & W3C VC CONFORMANCE HARNESS
# ============================================================================

class TestPrivacyAndW3cVcConformance:
    """
    Privacy inspection:
    - Decrypted IPFS payloads contain RFC 8785 canonical VCs with Ed25519 signatures and ISO 8601 issuanceDate.
    - Ed25519 cryptographic signature verifies over RFC 8785 canonical bytes.
    - On-chain records leak zero raw Aadhaar or full demographic PII.
    """

    def test_w3c_vc_conformance_and_canonicalization(self):
        """Verifies decrypted IPFS payload adheres to W3C VC v1.1, RFC 8785 canonical bytes, and ISO 8601."""
        vc_subject = {
            "id": "did:passkhadam:worker:adv_test_4821",
            "full_name": "Mohammed Uzair",
            "origin_state": "Karnataka",
            "current_state": "Karnataka",
            "worker_category": "Mason",
            "employment_level": "Skilled",
            "nature_of_employment": "Contract",
            "bocw_registered": True,
            "bocw_number": "BOCW-KA-2026-9921",
            "skills": ["Mason", "Plumbing Assistance"],
            "masked_aadhaar": "XXXX XXXX 4821",
            "verification_authority": "Mock Aadhaar Authority / PASSKHADAM Gateway"
        }

        # 1. Build VC
        vc = build_w3c_verifiable_credential(vc_subject)

        # 2. Encrypt & Pin
        enc_blob = encrypt_payload(vc)
        cid = ipfs_service.pin_payload(enc_blob)

        # 3. Resolve & Decrypt
        resolved = ipfs_service.resolve_payload(cid)
        decrypted = decrypt_payload(resolved)

        # Check W3C structure
        assert decrypted["@context"] == ["https://www.w3.org/2018/credentials/v1"]
        assert decrypted["id"].startswith("urn:uuid:vc-")
        assert decrypted["type"] == ["VerifiableCredential", "WorkerIdentityCredential"]
        assert decrypted["issuer"] == "did:passkhadam:authority:identity-gateway"

        # Check ISO 8601 issuanceDate
        issuance_date = decrypted["issuanceDate"]
        assert ISO_8601_REGEX.match(issuance_date), f"issuanceDate '{issuance_date}' does not match ISO 8601 UTC format"
        parsed_dt = datetime.strptime(issuance_date, "%Y-%m-%dT%H:%M:%SZ")
        assert parsed_dt.year >= 2026

        # Check Proof
        proof = decrypted["proof"]
        assert proof["type"] == "Ed25519Signature2020"
        assert proof["proofPurpose"] == "assertionMethod"
        assert proof["verificationMethod"] == "did:passkhadam:authority:identity-gateway#key-1"
        assert ISO_8601_REGEX.match(proof["created"])

        # Cryptographically verify Ed25519 signature
        sig_hex = proof["signatureValue"]
        assert verify_credential_signature(decrypted["credentialSubject"], sig_hex) is True

        # Tamper check: alter full_name
        tampered = dict(decrypted["credentialSubject"])
        tampered["full_name"] = "Malicious Impostor"
        assert verify_credential_signature(tampered, sig_hex) is False

        # Canonical JSON bytes test: RFC 8785 guarantees identical bytes regardless of dict key order
        shuffled_subject = {k: vc_subject[k] for k in sorted(vc_subject.keys(), reverse=True)}
        assert canonical_json_bytes(vc_subject) == canonical_json_bytes(shuffled_subject)

    def test_onchain_records_leak_zero_raw_aadhaar_or_demographics(self):
        """
        Registers worker through end-to-end API and inspects on-chain and database records.
        Asserts zero 12-digit Aadhaar numbers and zero full demographic PII on-chain.
        """
        raw_aadhaar = "123456784821"
        name = "Mohammed Uzair"
        addr = "45/2 BTM Layout, Bengaluru, Karnataka"

        _, _, _, headers = create_test_user(role="WORKER", name=name)
        res = client.post(
            "/api/v1/worker/verify-aadhaar/me",
            json={"aadhaar_number": raw_aadhaar, "full_name": name},
            headers=headers
        )
        assert res.status_code == 200
        did = res.json()["did"]

        # 1. Inspect on-chain record in BlockchainService
        onchain_record = blockchain_service.get_worker(did)
        assert onchain_record is not None
        record_dump = json.dumps(onchain_record)

        # Assert zero 12-digit numbers
        matches = RAW_AADHAAR_REGEX.findall(record_dump)
        assert len(matches) == 0, f"Raw Aadhaar detected in on-chain record: {matches}"
        assert raw_aadhaar not in record_dump, f"Raw Aadhaar {raw_aadhaar} leaked into on-chain record"

        # Assert zero residential addresses
        assert "btm layout" not in record_dump.lower()
        assert "45/2" not in record_dump

        # Assert zero human names
        assert name.lower() not in record_dump.lower()

        # 2. Inspect allowed on-chain fields
        allowed_fields = {
            "did", "credential_hash", "ipfs_cid", "issue_timestamp",
            "updated_at", "is_registered", "is_revoked", "revocation_reason",
            "tx_hash", "block_number", "chain_id", "contract_address", "status"
        }
        for k in onchain_record.keys():
            assert k in allowed_fields, f"Unexpected field '{k}' on on-chain record"

        # 3. Inspect SQLite Worker Profile caching
        db = SessionLocal()
        prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.did == did).first()
        assert prof is not None
        assert prof.masked_aadhaar == "XXXX XXXX 4821"
        assert not hasattr(prof, "aadhaar_number"), "raw aadhaar column must not exist on DBWorkerProfile"
        db.close()
