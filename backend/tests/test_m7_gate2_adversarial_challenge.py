"""
backend/tests/test_m7_gate2_adversarial_challenge.py
Adversarial Stress Test & Empirical Verification Harness for Milestone 7 Gate 2:
1. Replay Attack Defense: POST /api/v1/employer/verify-worker-qr rejects duplicate presentations with HTTP 409 Conflict.
2. Multi-Verifier Isolation: Independent verification by different verifiers (Employer vs Government, Employer A vs Employer B) during valid presentation window.
3. Transient Infrastructure Failure Resilience: Transient RPC/IPFS errors do not burn nonces in DBConsumedPresentationNonce.
4. Cryptographic / Expiration Pre-Validation: Expired or tampered envelopes reject cleanly without nonce consumption.
"""

import io
import json
import uuid
import time
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.db import (
    SessionLocal, DBUser, DBEmployerOrganization, DBGovernmentOfficer,
    DBConsumedPresentationNonce
)
from app.core.crypto import (
    encrypt_payload, decrypt_payload, sign_credential,
    verify_credential_signature, keccak_hash
)
from app.services.ipfs_service import ipfs_service
from app.services.blockchain_service import blockchain_service
from app.services.verification_engine import (
    verification_engine, VerificationEngineError, VerificationErrorCode,
    ReplayAttackError
)
from app.api.endpoints.employer import DEFAULT_EMPLOYER_ADDR
from app.api.endpoints.government import DEFAULT_GOV_ADDR


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def employer_token(client):
    res = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert res.status_code == 200, f"Employer login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture
def government_token(client):
    from app.core.auth import create_test_firebase_jwt
    import hashlib
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    gov_uid = f"uid_gov_m7_{suffix}"
    gov_email = f"gov_m7_{suffix}@state.gov.in"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()
    gov_addr = f"0xGovOfficer_m7_{suffix}"

    user = DBUser(
        firebase_uid=gov_uid,
        full_name=f"Gov Officer {suffix}",
        email=gov_email,
        phone="+91 9876543210",
        password_hash=pw_hash,
        role="GOVERNMENT",
        status="ACTIVE",
        organization_address=gov_addr
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    officer = DBGovernmentOfficer(
        user_id=user.id,
        officer_name=f"Gov Officer {suffix}",
        department="Welfare",
        authority_level="STATE",
        state="Maharashtra",
        status="ACTIVE",
        wallet_address=gov_addr,
        official_email=gov_email,
        officer_reference_id=f"GOV-{suffix.upper()}"
    )
    db.add(officer)
    db.commit()
    token = create_test_firebase_jwt(uid=gov_uid, email=gov_email, name="Gov Officer")
    db.close()
    return token


def create_anchored_worker(did: str, name: str = "Test Worker"):
    """Helper to anchor a test worker credential in mock IPFS and blockchain registry."""
    vc_body = {
        "full_name": name,
        "worker_category": "Mason",
        "origin_state": "Karnataka",
        "current_state": "Maharashtra",
        "skills": ["Mason", "Tiling"]
    }
    sig = sign_credential(vc_body)
    enc = encrypt_payload({"credentialSubject": vc_body, "proof": {"signatureValue": sig}})
    cid = ipfs_service.pin_payload(enc)
    blockchain_service.register_worker(did, keccak_hash(enc), cid)
    return vc_body


# ============================================================================
# 1. EMPIRICAL CHALLENGE 1: HTTP 409 CONFLICT ON DUPLICATE QR PRESENTATION
# ============================================================================

class TestDuplicateQRRejectionEndpoint:
    """
    Empirically verifies that POST /api/v1/employer/verify-worker-qr:
    - Accepts legitimate fresh presentation with HTTP 200.
    - Atomically persists consumption in DBConsumedPresentationNonce.
    - Rejects duplicate presentation submission with HTTP 409 Conflict.
    - Preserves rejection across multiple repeated attempts.
    """

    def test_duplicate_qr_rejected_with_http_409_conflict(self, client, db_session):
        did = f"did:passkhadam:worker:adv1-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "Adversarial Target Worker 1")
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body)
        pres_id = json.loads(envelope_json)["payload"]["presentation_id"]

        # 1. First legitimate verification -> HTTP 200 OK
        files_1 = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp1 = client.post("/api/v1/employer/verify-worker-qr", files=files_1)
        assert resp1.status_code == 200, f"First submission failed: {resp1.text}"
        data1 = resp1.json()
        assert data1["verified"] is True
        assert data1["presentation_id"] == pres_id

        # Assert persistence in database
        nonce_row = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id,
            DBConsumedPresentationNonce.verifier_role == "EMPLOYER"
        ).first()
        assert nonce_row is not None, "DBConsumedPresentationNonce record was not persisted"
        assert nonce_row.worker_did == did

        # 2. Immediate duplicate replay submission -> HTTP 409 Conflict
        files_2 = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp2 = client.post("/api/v1/employer/verify-worker-qr", files=files_2)
        assert resp2.status_code == 409, f"Expected HTTP 409, got {resp2.status_code}: {resp2.text}"
        err_detail = resp2.json().get("detail", "").lower()
        assert "replay attack detected" in err_detail or "already verified" in err_detail

        # 3. Third replay submission -> HTTP 409 Conflict
        files_3 = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp3 = client.post("/api/v1/employer/verify-worker-qr", files=files_3)
        assert resp3.status_code == 409, f"Expected HTTP 409 on 3rd attempt, got {resp3.status_code}: {resp3.text}"

    def test_authenticated_employer_duplicate_qr_rejected_with_http_409(self, client, employer_token, db_session):
        did = f"did:passkhadam:worker:adv1-auth-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "Adversarial Target Worker Auth")
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body)
        pres_id = json.loads(envelope_json)["payload"]["presentation_id"]

        headers = {"Authorization": f"Bearer {employer_token}"}

        # 1. First legitimate verification with auth token -> HTTP 200 OK
        files_1 = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp1 = client.post("/api/v1/employer/verify-worker-qr", files=files_1, headers=headers)
        assert resp1.status_code == 200, f"Authenticated verification failed: {resp1.text}"

        # 2. Duplicate submission with auth token -> HTTP 409 Conflict
        files_2 = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp2 = client.post("/api/v1/employer/verify-worker-qr", files=files_2, headers=headers)
        assert resp2.status_code == 409, f"Expected HTTP 409 for duplicate auth, got {resp2.status_code}: {resp2.text}"


# ============================================================================
# 2. EMPIRICAL CHALLENGE 2: MULTI-VERIFIER INDEPENDENT VERIFICATION
# ============================================================================

class TestMultiVerifierIndependentVerification:
    """
    Empirically verifies that:
    - Employer vs Government can independently verify the same presentation during its valid window.
    - Employer A vs Employer B can independently verify the same presentation.
    - Each verifier context receives its own role-redacted view.
    - Duplicate submission within the same verifier context is rejected with HTTP 409.
    - SQLite composite unique constraint `uq_presentation_verifier_context` enforces exact scoping.
    """

    def test_employer_and_government_cross_role_independent_verification(
        self, client, employer_token, government_token, db_session
    ):
        did = f"did:passkhadam:worker:cross-role-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "Cross Role Worker")
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body, validity_seconds=300)
        pres_id = json.loads(envelope_json)["payload"]["presentation_id"]

        emp_headers = {"Authorization": f"Bearer {employer_token}"}
        gov_headers = {"Authorization": f"Bearer {government_token}"}

        # 1. Employer verifies via /api/v1/employer/verify-worker-qr -> HTTP 200
        files_emp = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_emp = client.post("/api/v1/employer/verify-worker-qr", files=files_emp, headers=emp_headers)
        assert resp_emp.status_code == 200, f"Employer verification failed: {resp_emp.text}"
        emp_data = resp_emp.json()
        assert emp_data["verified"] is True
        assert "skills" in emp_data["data"]
        assert "current_employment_status" in emp_data["data"]

        # 2. Government verifies the SAME presentation via /api/v1/government/verify-worker-qr -> HTTP 200
        files_gov = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_gov = client.post("/api/v1/government/verify-worker-qr", files=files_gov, headers=gov_headers)
        assert resp_gov.status_code == 200, f"Government verification failed: {resp_gov.text}"
        gov_data = resp_gov.json()
        assert gov_data["verified"] is True
        assert "bocw_registered" in gov_data["data"]
        assert "is_interstate_worker" in gov_data["data"]

        # 3. Assert DB contains distinct nonces for both verifier roles
        nonces = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id
        ).all()
        roles = {n.verifier_role for n in nonces}
        assert "EMPLOYER" in roles, "Missing EMPLOYER nonce record"
        assert "GOVERNMENT" in roles, "Missing GOVERNMENT nonce record"

        # 4. Employer re-submission -> HTTP 409 Conflict
        files_emp_replay = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_emp_replay = client.post("/api/v1/employer/verify-worker-qr", files=files_emp_replay, headers=emp_headers)
        assert resp_emp_replay.status_code == 409, f"Expected HTTP 409 on Employer replay: {resp_emp_replay.text}"

        # 5. Government re-submission -> HTTP 409 Conflict
        files_gov_replay = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_gov_replay = client.post("/api/v1/government/verify-worker-qr", files=files_gov_replay, headers=gov_headers)
        assert resp_gov_replay.status_code == 409, f"Expected HTTP 409 on Government replay: {resp_gov_replay.text}"

    def test_employer_a_and_employer_b_cross_verifier_independent_verification(self, db_session):
        """Two different employer organizations independently verify the same presentation."""
        did = f"did:passkhadam:worker:cross-emp-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "Cross Employer Worker")
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body, validity_seconds=300)
        pres_id = json.loads(envelope_json)["payload"]["presentation_id"]

        org_a = DEFAULT_EMPLOYER_ADDR
        org_b = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

        # 1. Employer A verifies successfully
        res_a = verification_engine.verify_uploaded_presentation(png_bytes, "EMPLOYER", org_a, db=db_session)
        assert res_a["verified"] is True

        # 2. Employer B independently verifies the SAME presentation successfully
        res_b = verification_engine.verify_uploaded_presentation(png_bytes, "EMPLOYER", org_b, db=db_session)
        assert res_b["verified"] is True

        # 3. Assert DB contains 2 records with same role and presentation_id but different verifier_id
        nonces = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id,
            DBConsumedPresentationNonce.verifier_role == "EMPLOYER"
        ).all()
        verifier_ids = {n.verifier_id for n in nonces}
        assert org_a in verifier_ids
        assert org_b in verifier_ids

        # 4. Employer A duplicate attempt -> ReplayAttackError
        with pytest.raises(ReplayAttackError):
            verification_engine.verify_uploaded_presentation(png_bytes, "EMPLOYER", org_a, db=db_session)

        # 5. Employer B duplicate attempt -> ReplayAttackError
        with pytest.raises(ReplayAttackError):
            verification_engine.verify_uploaded_presentation(png_bytes, "EMPLOYER", org_b, db=db_session)


# ============================================================================
# 3. EMPIRICAL CHALLENGE 3: TRANSIENT FAILURES DO NOT BURN NONCES
# ============================================================================

class TestTransientErrorsDoNotBurnNonces:
    """
    Empirically verifies that:
    - Step 4 (RPC node unavailable) raises 503 and rolls back without burning nonce.
    - Step 5 (IPFS retrieval failure) raises 503 and rolls back without burning nonce.
    - After transient issue clears, the SAME presentation can be successfully verified.
    - Nonce is consumed ONLY upon complete success at Step 11.
    """

    def test_transient_rpc_error_does_not_burn_nonce(self, client, monkeypatch, db_session):
        did = f"did:passkhadam:worker:rpc-transient-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "RPC Transient Worker")
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body)
        pres_id = json.loads(envelope_json)["payload"]["presentation_id"]

        # Simulate transient RPC node outage at Step 4
        orig_get_worker = blockchain_service.get_worker
        def mock_get_worker_failure(worker_did):
            raise ConnectionError("Geth JSON-RPC endpoint connection refused: dial tcp 127.0.0.1:8545")

        monkeypatch.setattr(blockchain_service, "get_worker", mock_get_worker_failure)

        # Attempt verification during RPC outage -> HTTP 503 Service Unavailable
        files_err = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_err = client.post("/api/v1/employer/verify-worker-qr", files=files_err)
        assert resp_err.status_code == 503, f"Expected HTTP 503 on RPC outage, got {resp_err.status_code}: {resp_err.text}"

        # EMPIRICAL ASSERTION: Verify nonce is NOT burned in DBConsumedPresentationNonce
        nonce_count = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id
        ).count()
        assert nonce_count == 0, "FATAL: Nonce was burned during transient RPC failure!"

        # Restore RPC node functionality
        monkeypatch.setattr(blockchain_service, "get_worker", orig_get_worker)

        # Retry with the EXACT SAME presentation -> HTTP 200 OK
        files_ok = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_ok = client.post("/api/v1/employer/verify-worker-qr", files=files_ok)
        assert resp_ok.status_code == 200, f"Expected HTTP 200 after RPC recovery: {resp_ok.text}"
        assert resp_ok.json()["verified"] is True

        # Assert nonce IS now burned
        nonce_count_after = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id
        ).count()
        assert nonce_count_after == 1, "Nonce was not persisted after successful verification"

        # Replay attempt now correctly rejected with HTTP 409
        files_replay = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_replay = client.post("/api/v1/employer/verify-worker-qr", files=files_replay)
        assert resp_replay.status_code == 409, f"Expected HTTP 409 on replay, got {resp_replay.status_code}"

    def test_transient_ipfs_error_does_not_burn_nonce(self, client, monkeypatch, db_session):
        did = f"did:passkhadam:worker:ipfs-transient-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "IPFS Transient Worker")
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body)
        pres_id = json.loads(envelope_json)["payload"]["presentation_id"]

        # Simulate transient IPFS gateway timeout at Step 5
        orig_resolve = ipfs_service.resolve_payload
        def mock_resolve_failure(cid):
            raise TimeoutError("IPFS cluster gateway timed out while fetching CID")

        monkeypatch.setattr(ipfs_service, "resolve_payload", mock_resolve_failure)

        # Attempt verification during IPFS outage -> HTTP 503 Service Unavailable
        files_err = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_err = client.post("/api/v1/employer/verify-worker-qr", files=files_err)
        assert resp_err.status_code == 503, f"Expected HTTP 503 on IPFS outage, got {resp_err.status_code}: {resp_err.text}"

        # EMPIRICAL ASSERTION: Verify nonce is NOT burned in DBConsumedPresentationNonce
        nonce_count = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id
        ).count()
        assert nonce_count == 0, "FATAL: Nonce was burned during transient IPFS failure!"

        # Restore IPFS functionality
        monkeypatch.setattr(ipfs_service, "resolve_payload", orig_resolve)

        # Retry with the EXACT SAME presentation -> HTTP 200 OK
        files_ok = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_ok = client.post("/api/v1/employer/verify-worker-qr", files=files_ok)
        assert resp_ok.status_code == 200, f"Expected HTTP 200 after IPFS recovery: {resp_ok.text}"
        assert resp_ok.json()["verified"] is True

        # Assert nonce IS now burned
        nonce_count_after = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id
        ).count()
        assert nonce_count_after == 1

        # Replay attempt now correctly rejected with HTTP 409
        files_replay = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp_replay = client.post("/api/v1/employer/verify-worker-qr", files=files_replay)
        assert resp_replay.status_code == 409


# ============================================================================
# 4. EMPIRICAL CHALLENGE 4: PRE-VALIDATION FAILURES DO NOT BURN NONCES
# ============================================================================

class TestPreValidationFailuresDoNotBurnNonces:
    """
    Verifies that early cryptographic or expiration failures reject before Step 11:
    - Expired presentations reject at Step 3 without burning nonce.
    - Tampered digital signatures reject at Step 2 without burning nonce.
    """

    def test_expired_presentation_rejected_without_burning_nonce(self, client, db_session):
        did = f"did:passkhadam:worker:exp-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "Expired Target Worker")
        # Generate with negative validity -> immediately expired
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body, validity_seconds=-10)
        pres_id = json.loads(envelope_json)["payload"]["presentation_id"]

        files = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
        resp = client.post("/api/v1/employer/verify-worker-qr", files=files)
        assert resp.status_code == 400, f"Expected HTTP 400 for expired QR, got {resp.status_code}: {resp.text}"
        assert "expired" in resp.json().get("detail", "").lower()

        # Nonce must NOT be consumed
        nonce_count = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id
        ).count()
        assert nonce_count == 0, "Nonce was burned on expired presentation"

    def test_tampered_envelope_rejected_without_burning_nonce(self, client, db_session):
        did = f"did:passkhadam:worker:tamp-{uuid.uuid4().hex[:8]}"
        vc_body = create_anchored_worker(did, "Tamper Target Worker")
        png_bytes, envelope_json = verification_engine.generate_qr_presentation(did, vc_body)
        envelope = json.loads(envelope_json)
        pres_id = envelope["payload"]["presentation_id"]

        # Tamper payload worker DID without re-signing
        envelope["payload"]["worker_did"] = "did:passkhadam:worker:attacker"

        # Re-encode into QR
        import qrcode
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(json.dumps(envelope))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        tampered_png = buf.getvalue()

        files = {"file": ("tampered_presentation.png", io.BytesIO(tampered_png), "image/png")}
        resp = client.post("/api/v1/employer/verify-worker-qr", files=files)
        assert resp.status_code == 400, f"Expected HTTP 400 for tampered QR, got {resp.status_code}: {resp.text}"
        assert "tampered" in resp.json().get("detail", "").lower() or "signature" in resp.json().get("detail", "").lower()

        # Nonce must NOT be consumed
        nonce_count = db_session.query(DBConsumedPresentationNonce).filter(
            DBConsumedPresentationNonce.presentation_id == pres_id
        ).count()
        assert nonce_count == 0, "Nonce was burned on tampered presentation"
