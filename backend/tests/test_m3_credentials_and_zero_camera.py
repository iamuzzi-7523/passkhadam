"""
backend/tests/test_m3_credentials_and_zero_camera.py
Milestone 3 Test Suite: Authoritative Credential Verification, Zero-Camera Simulation & Blockchain RPC Fallback.
Covers Features 10, 11, and 12 with genuine verification logic.
"""

import io
import json
import base64
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import (
    Base, get_db, SessionLocal,
    DBUser, DBWorkerProfile, DBWorkerCredential, DBGovernmentOfficer
)
from app.services.blockchain_service import BlockchainService, blockchain_service
from app.services.ipfs_service import ipfs_service
from app.services.verification_engine import (
    verification_engine,
    generate_demo_worker_presentation_response
)
from app.core.crypto import (
    encrypt_payload, sign_credential, keccak_hash
)
from app.core.auth import create_test_firebase_jwt


# Setup test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_shared_state():
    yield
    blockchain_service.last_claim_times.pop("did:passkhadam:worker:welfare-v3-test", None)


def register_test_worker_credential_and_anchor(worker_did: str, full_name: str = "Amina Khatun", skills: list = None) -> str:
    """Helper to create genuine encrypted and IPFS-pinned W3C VC for testing."""
    if skills is None:
        skills = ["Mason", "Tiling"]
    cred_payload = {
        "full_name": full_name,
        "worker_category": skills[0],
        "employment_level": "Skilled",
        "nature_of_employment": "Contract",
        "skills": skills,
        "origin_state": "Bihar",
        "current_state": "Karnataka"
    }
    enc_blob = encrypt_payload({"credentialSubject": cred_payload, "proof": {"signatureValue": sign_credential(cred_payload)}})
    cid = ipfs_service.pin_payload(enc_blob)
    cred_hash = keccak_hash(enc_blob)

    try:
        blockchain_service.register_worker(worker_did, cred_hash, cid)
    except Exception:
        blockchain_service.worker_registry[worker_did] = {
            "did": worker_did,
            "credential_hash": cred_hash,
            "ipfs_cid": cid,
            "timestamp": int(datetime.utcnow().timestamp()),
            "block_number": 1,
            "is_registered": True,
            "is_revoked": False,
            "status": 1
        }
    return cid


# ============================================================================
# FEATURE 12: BLOCKCHAIN RPC FALLBACK IN IS_WORKER_VALID
# ============================================================================

def test_f12_is_worker_valid_onchain_true():
    """F12.1: Contract returns True -> is_worker_valid returns True."""
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = True

    assert bs.is_worker_valid("did:passkhadam:worker:chain-valid-1") is True


def test_f12_is_worker_valid_contract_false_memory_fallback():
    """F12.2: Contract returns False on external testnet, but worker is in memory cache -> True."""
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    did = "did:passkhadam:worker:mem-fallback-2"
    bs.worker_registry[did] = {"did": did, "is_registered": True, "is_revoked": False}
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    assert bs.is_worker_valid(did) is True


def test_f12_is_worker_valid_contract_false_sqlite_profile_fallback():
    """F12.3: Contract returns False, but worker exists in SQLite DBWorkerProfile -> True."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    MemSession = sessionmaker(bind=engine)
    db = MemSession()

    u = DBUser(id=101, email="worker_f12@test.org", phone="+919876543210", password_hash="h", firebase_uid="uid_f12", full_name="SQLite Worker", role="WORKER", status="ACTIVE")
    p = DBWorkerProfile(user_id=101, did="did:passkhadam:worker:sqlite-valid-3", full_name="SQLite Worker", is_credential_anchored=True, did_state="ACTIVE")
    db.add_all([u, p])
    db.commit()

    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    with patch("app.models.db.SessionLocal", MemSession):
        assert bs.is_worker_valid("did:passkhadam:worker:sqlite-valid-3") is True
    db.close()


def test_f12_is_worker_valid_preserves_sqlite_revocation():
    """F12.4: Revoked worker in SQLite DBWorkerProfile (did_state='REVOKED') returns False."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    MemSession = sessionmaker(bind=engine)
    db = MemSession()

    u = DBUser(id=102, email="revoked_f12@test.org", phone="+919876543211", password_hash="h", firebase_uid="uid_f12_r", full_name="Revoked Worker", role="WORKER", status="ACTIVE")
    p = DBWorkerProfile(user_id=102, did="did:passkhadam:worker:sqlite-rev-4", full_name="Revoked Worker", is_credential_anchored=True, did_state="REVOKED")
    db.add_all([u, p])
    db.commit()

    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    with patch("app.models.db.SessionLocal", MemSession):
        assert bs.is_worker_valid("did:passkhadam:worker:sqlite-rev-4") is False
    db.close()


def test_f12_is_worker_valid_preserves_onchain_revocation():
    """F12.5: Worker registered and revoked on-chain returns False."""
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    did = "did:passkhadam:worker:onchain-rev-5"
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = (did, b'', 'QmCID', 1000, 1000, True, True, 'Revoked')

    assert bs.is_worker_valid(did) is False


def test_f12_is_worker_valid_unregistered_returns_false():
    """F12.6: DID unregistered on-chain and in local DB returns False."""
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    assert bs.is_worker_valid("did:passkhadam:worker:unregistered-999") is False


def test_f12_is_worker_valid_rpc_exception_falls_back_to_cache():
    """F12.7: RPC network exception gracefully falls back to local cache/database."""
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    did = "did:passkhadam:worker:glitch-cache-7"
    bs.worker_registry[did] = {"did": did, "is_registered": True, "is_revoked": False}

    mock_contract.functions.isWorkerValid.return_value.call.side_effect = ConnectionError("RPC network timeout")
    mock_contract.functions.getWorkerByDid.return_value.call.side_effect = ConnectionError("RPC network timeout")

    assert bs.is_worker_valid(did) is True


def test_f12_is_worker_valid_empty_did():
    """F12.8: Empty, None, or invalid DID string safely returns False."""
    bs = BlockchainService()
    assert bs.is_worker_valid("") is False
    assert bs.is_worker_valid(None) is False


# ============================================================================
# FEATURE 10: AUTHORITATIVE CREDENTIAL VERIFICATION
# ============================================================================

def test_f10_verification_engine_headless_fallback():
    """
    F10.1: When db is None (headless unit test mode), verification engine returns
    the legacy mock certifications to retain backward compatibility with test_backend.py:111.
    """
    worker_did = "did:passkhadam:worker:headless-m3-fallback"
    register_test_worker_credential_and_anchor(worker_did, full_name="Headless Worker")

    png_bytes, _ = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={"full_name": "Headless Worker"},
        validity_seconds=300
    )
    result = verification_engine.verify_uploaded_presentation(
        image_bytes=png_bytes,
        caller_role="EMPLOYER",
        caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
        db=None
    )
    assert result["verified"] is True
    certs = result["data"]["verified_certifications"]
    assert any("BOCW" in cert["type"] for cert in certs)
    assert any("Workplace Safety Induction" in cert["type"] for cert in certs)
    assert any("Identity Credential" in cert["type"] for cert in certs)


def test_f10_verification_engine_authoritative_db_credentials():
    """
    F10.2: When db is provided, verification engine dynamically queries DBWorkerCredential
    for the worker DID and populates verified_certifications reflecting genuine issuances.
    """
    db = SessionLocal()
    try:
        worker_did = "did:passkhadam:worker:auth-test-cred-102"
        register_test_worker_credential_and_anchor(worker_did, full_name="Amina Khatun")

        # Clear any prior credentials for this DID
        db.query(DBWorkerCredential).filter(DBWorkerCredential.worker_did == worker_did).delete()
        db.commit()

        # Add genuine active BOCW Welfare Credential
        bocw_cred = DBWorkerCredential(
            credential_id="BOCW-KA-2026-AUTH-01",
            worker_did=worker_did,
            title="Karnataka BOCW Construction Welfare Card",
            credential_type="Welfare",
            issuer_name="Karnataka Building & Other Construction Workers Welfare Board",
            issuer_role="GOVERNMENT",
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=365)
        )
        # Add genuine Employer Trade Experience Credential
        emp_cred = DBWorkerCredential(
            credential_id="EXP-APEX-2026-AUTH-02",
            worker_did=worker_did,
            title="Master Electrician Trade Certification",
            credential_type="Skill",
            issuer_name="Apex Infrastructure Pvt Ltd",
            issuer_role="EMPLOYER",
            skills_json=json.dumps(["Industrial Wiring", "Conduit Bending"]),
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=180)
        )
        # Add expired Safety Credential
        exp_cred = DBWorkerCredential(
            credential_id="SAFE-2025-EXPIRED-03",
            worker_did=worker_did,
            title="Crane Operations Safety Induction",
            credential_type="Safety",
            issuer_name="Safety Authority",
            issuer_role="GOVERNMENT",
            status="VALID",
            expires_at=datetime.utcnow() - timedelta(days=10)  # Expired!
        )
        db.add_all([bocw_cred, emp_cred, exp_cred])
        db.commit()

        # Generate QR presentation
        png_bytes, _ = verification_engine.generate_qr_presentation(
            worker_did=worker_did,
            worker_profile={"full_name": "Amina Khatun", "origin_state": "Bihar", "current_state": "Karnataka"},
            validity_seconds=300
        )

        # 1. Verify as EMPLOYER
        emp_res = verification_engine.verify_uploaded_presentation(
            image_bytes=png_bytes,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            db=db
        )
        assert emp_res["verified"] is True
        certs = emp_res["data"]["verified_certifications"]
        # Identity Credential + 3 genuine DB credentials
        assert len(certs) == 4
        cert_types = [c["type"] for c in certs]
        assert "Identity Credential" in cert_types
        assert "Welfare" in cert_types
        assert "Skill" in cert_types
        assert "Safety" in cert_types

        # Check expired credential status
        expired_entry = next(c for c in certs if c.get("id") == "SAFE-2025-EXPIRED-03")
        assert expired_entry["status"] == "EXPIRED"

        # Check active skill credential
        skill_entry = next(c for c in certs if c.get("id") == "EXP-APEX-2026-AUTH-02")
        assert skill_entry["status"] == "VALID"
        assert "Industrial Wiring" in skill_entry["skills"]

        # 2. Verify as GOVERNMENT (new ephemeral QR since first was consumed by employer)
        gov_png, _ = verification_engine.generate_qr_presentation(
            worker_did=worker_did,
            worker_profile={"full_name": "Amina Khatun", "origin_state": "Bihar", "current_state": "Karnataka"},
            validity_seconds=300
        )
        # Look up active government officer
        gov_officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.status == "ACTIVE").first()
        gov_caller_id = str(gov_officer.id) if gov_officer else "GOV-OFF-0028"

        gov_res = verification_engine.verify_uploaded_presentation(
            image_bytes=gov_png,
            caller_role="GOVERNMENT",
            caller_id=gov_caller_id,
            db=db
        )
        assert gov_res["verified"] is True
        gov_data = gov_res["data"]
        assert gov_data["bocw_registered"] is True
        assert gov_data["bocw_registration_id"] == "BOCW-KA-2026-AUTH-01"
        assert len(gov_data["verified_certifications"]) == 4

    finally:
        db.query(DBWorkerCredential).filter(DBWorkerCredential.worker_did == worker_did).delete()
        db.commit()
        db.close()


def test_f10_worker_with_only_identity_credential():
    """
    F10.3: Worker with no DB credentials returns only the verified Identity Credential.
    """
    db = SessionLocal()
    try:
        worker_did = "did:passkhadam:worker:only-identity-103"
        register_test_worker_credential_and_anchor(worker_did, full_name="Fresh Uncertified Worker")
        db.query(DBWorkerCredential).filter(DBWorkerCredential.worker_did == worker_did).delete()
        db.commit()

        png_bytes, _ = verification_engine.generate_qr_presentation(
            worker_did=worker_did,
            worker_profile={"full_name": "Fresh Uncertified Worker"},
            validity_seconds=300
        )

        res = verification_engine.verify_uploaded_presentation(
            image_bytes=png_bytes,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            db=db
        )
        assert res["verified"] is True
        certs = res["data"]["verified_certifications"]
        # Only base Identity Credential
        assert len(certs) == 1
        assert certs[0]["type"] == "Identity Credential"
        assert certs[0]["status"] == "VALID"
    finally:
        db.close()


# ============================================================================
# FEATURE 11: ZERO-CAMERA SIMULATION & DEMO QR ENDPOINTS
# ============================================================================

def test_f11_generate_demo_worker_presentation_helper():
    """
    F11.1: generate_demo_worker_presentation_response returns a fresh ephemeral
    presentation payload with valid base64 image data and metadata.
    """
    db = SessionLocal()
    try:
        payload = generate_demo_worker_presentation_response(db)
        assert "worker_did" in payload
        assert payload["worker_did"].startswith("did:passkhadam:worker:")
        assert "full_name" in payload
        assert payload["expires_in_seconds"] == 300
        assert "qr_base64_data_uri" in payload
        assert payload["qr_base64_data_uri"].startswith("data:image/png;base64,")
        assert "filename" in payload
        assert payload["filename"].endswith(".png")

        # Confirm the returned base64 image decodes to valid PNG bytes
        b64_data = payload["qr_base64_data_uri"].split(",")[1]
        raw_bytes = base64.b64decode(b64_data)
        assert raw_bytes.startswith(b"\x89PNG\r\n\x1a\n")

        # Confirm that passing these raw PNG bytes into the verification engine succeeds 100%
        result = verification_engine.verify_uploaded_presentation(
            image_bytes=raw_bytes,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            db=db
        )
        assert result["verified"] is True
        assert len(result["audit_steps"]) == 11
        assert result["audit_steps"][-1]["status"] == "SUCCESS"
    finally:
        db.close()


def test_f11_employer_demo_worker_qr_endpoint():
    """
    F11.2: GET /api/v1/employer/demo-worker-qr allows Employer/Admin access,
    and forbids unauthorized roles.
    """
    emp_token = create_test_firebase_jwt(uid="uid_employer_apex", email="employer@apexinfra.com")
    resp = client.get("/api/v1/employer/demo-worker-qr", headers={"Authorization": f"Bearer {emp_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "qr_base64_data_uri" in data
    assert data["expires_in_seconds"] == 300

    # Worker token rejected with 403
    worker_token = create_test_firebase_jwt(uid="uid_worker_pass", email="worker@passkhadam.org")
    resp_forbidden = client.get("/api/v1/employer/demo-worker-qr", headers={"Authorization": f"Bearer {worker_token}"})
    assert resp_forbidden.status_code == 403


def test_f11_government_demo_worker_qr_endpoint():
    """
    F11.3: GET /api/v1/government/demo-worker-qr allows Government/Admin access,
    and forbids unauthorized roles.
    """
    gov_token = create_test_firebase_jwt(uid="uid_gov_mh", email="gov@maharashtra.gov.in")
    resp = client.get("/api/v1/government/demo-worker-qr", headers={"Authorization": f"Bearer {gov_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "qr_base64_data_uri" in data
    assert data["expires_in_seconds"] == 300

    # Worker token rejected with 403
    worker_token = create_test_firebase_jwt(uid="uid_worker_pass", email="worker@passkhadam.org")
    resp_forbidden = client.get("/api/v1/government/demo-worker-qr", headers={"Authorization": f"Bearer {worker_token}"})
    assert resp_forbidden.status_code == 403


def test_f11_worker_presentation_demo_qr_fallback_endpoint():
    """
    F11.4: GET /api/v1/worker/presentation/demo-qr provides a fallback simulation endpoint.
    """
    resp = client.get("/api/v1/worker/presentation/demo-qr")
    assert resp.status_code == 200
    data = resp.json()
    assert "qr_base64_data_uri" in data
    assert "worker_did" in data
    assert data["expires_in_seconds"] == 300
