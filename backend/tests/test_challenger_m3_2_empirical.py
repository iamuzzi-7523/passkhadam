"""
backend/tests/test_challenger_m3_2_empirical.py
Milestone 3 Empirical Challenger Test Suite:
Authoritative Credentials, Zero-Camera Simulation & Blockchain RPC Fallback Invariant Matrix.

Challenge Matrix Coverage:
1. Blockchain RPC Fallback Invariant (Full 7-condition matrix on is_worker_valid):
   - Test 1: On-chain valid -> True (including adversarial check that local revocation overrides onchain).
   - Test 2: In memory cache, contract returns False -> True (and cache revocation returns False).
   - Test 3: In SQLite DBWorkerProfile, contract returns False -> True (and unanchored returns False).
   - Test 4: SQLite profile revoked ('REVOKED') -> False.
   - Test 5: On-chain revoked -> False (on-chain revocation takes precedence over SQLite ACTIVE).
   - Test 6: Non-existent DID -> False (empty, None, malformed, non-existent).
   - Test 7: Network timeout / RPC exception -> fallback to cache and SQLite.
2. Dynamic Credentials Invariants:
   - Multiple credentials with mixed states (VALID, EXPIRED, REVOKED).
   - Authoritative DID isolation: Only matching credentials for the presented DID appear.
   - Zero-Leakage: Unassociated credentials from other worker DIDs are NEVER leaked.
   - Headless fallback: verify_uploaded_presentation(..., db=None) returns legacy mock array without exception.
   - Worker with zero credentials returns base Identity Credential.
"""

import io
import json
import base64
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.db import (
    Base, SessionLocal,
    DBUser, DBWorkerProfile, DBWorkerCredential,
    DBGovernmentOfficer, DBEmployerOrganization
)
from app.services.blockchain_service import BlockchainService, blockchain_service
from app.services.ipfs_service import ipfs_service
from app.services.verification_engine import verification_engine
from app.core.crypto import encrypt_payload, sign_credential, keccak_hash


@pytest.fixture(autouse=True)
def clean_shared_state():
    """Ensure shared singleton cache and cooldown state are reset between tests."""
    yield
    test_dids = [
        "did:passkhadam:worker:challenger-a-101",
        "did:passkhadam:worker:challenger-b-102",
        "did:passkhadam:worker:zero-cred-103",
        "did:passkhadam:worker:headless-m32-test",
    ]
    for d in test_dids:
        blockchain_service.last_claim_times.pop(d, None)
        blockchain_service.worker_registry.pop(d, None)


def _anchor_test_worker(worker_did: str, full_name: str = "Test Worker", skills: list = None) -> str:
    """Helper to create real encrypted and IPFS-pinned W3C VC for testing."""
    if skills is None:
        skills = ["Mason", "Plumber"]
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
# 1. BLOCKCHAIN RPC FALLBACK INVARIANT: 7-CONDITION TEST MATRIX
# ============================================================================

def test_rpc_matrix_cond1_onchain_valid_returns_true():
    """
    Test 1: On-chain valid -> True.
    - Contract isWorkerValid returns True and cache does not mark revoked -> returns True.
    - Adversarial check: If local cache explicitly marks revoked -> returns False (invariant preserved).
    """
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = True

    did = "did:passkhadam:worker:chain-valid-matrix-1"
    assert bs.is_worker_valid(did) is True

    # Adversarial check: Even if on-chain returns True, explicit local cache revocation overrides
    bs.worker_registry[did] = {"did": did, "is_registered": True, "is_revoked": True}
    assert bs.is_worker_valid(did) is False


def test_rpc_matrix_cond2_contract_false_memory_cache_fallback():
    """
    Test 2: In memory cache, contract returns False -> True.
    - Contract returns False (e.g. unregistered on remote testnet).
    - Contract getWorkerByDid returns not registered.
    - Worker exists in memory cache (worker_registry) with is_registered=True, is_revoked=False.
    - Result MUST fall back to memory cache and return True.
    - Adversarial check: If memory cache has is_revoked=True -> returns False.
    - Adversarial check: If memory cache has is_registered=False -> returns False.
    """
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    did = "did:passkhadam:worker:mem-matrix-2"
    bs.worker_registry[did] = {"did": did, "is_registered": True, "is_revoked": False}
    assert bs.is_worker_valid(did) is True

    # Adversarial check 1: Revoked in cache
    bs.worker_registry[did]["is_revoked"] = True
    assert bs.is_worker_valid(did) is False

    # Adversarial check 2: Not registered in cache
    bs.worker_registry[did]["is_revoked"] = False
    bs.worker_registry[did]["is_registered"] = False
    assert bs.is_worker_valid(did) is False


def test_rpc_matrix_cond3_contract_false_sqlite_profile_fallback():
    """
    Test 3: In SQLite DBWorkerProfile, contract returns False -> True.
    - Contract isWorkerValid returns False.
    - Contract getWorkerByDid returns not registered.
    - Not in memory cache.
    - Exists in SQLite DBWorkerProfile with is_credential_anchored=True, did_state='ACTIVE'.
    - Result MUST fall back to SQLite profile and return True, caching in worker_registry.
    - Adversarial check: If is_credential_anchored=False -> returns False (unanchored worker).
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    MemSession = sessionmaker(bind=engine)
    db = MemSession()

    u = DBUser(id=201, email="sqlite_m32@test.org", phone="+919876543220", password_hash="h", firebase_uid="uid_m32_1", full_name="SQLite Active", role="WORKER", status="ACTIVE")
    p = DBWorkerProfile(user_id=201, did="did:passkhadam:worker:sqlite-matrix-3", full_name="SQLite Active", is_credential_anchored=True, did_state="ACTIVE")
    p_unanchored = DBWorkerProfile(user_id=201, did="did:passkhadam:worker:sqlite-unanchored-3", full_name="Unanchored", is_credential_anchored=False, did_state="ACTIVE")
    db.add_all([u, p, p_unanchored])
    db.commit()

    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    with patch("app.models.db.SessionLocal", MemSession):
        assert bs.is_worker_valid("did:passkhadam:worker:sqlite-matrix-3") is True
        # Verify it cached the record into worker_registry
        assert "did:passkhadam:worker:sqlite-matrix-3" in bs.worker_registry
        assert bs.worker_registry["did:passkhadam:worker:sqlite-matrix-3"]["is_registered"] is True

        # Unanchored worker profile should NOT return True
        assert bs.is_worker_valid("did:passkhadam:worker:sqlite-unanchored-3") is False

    db.close()


def test_rpc_matrix_cond4_sqlite_profile_revoked_returns_false():
    """
    Test 4: SQLite profile revoked ('REVOKED') -> False.
    - Worker exists in SQLite DBWorkerProfile with did_state='REVOKED'.
    - Contract returns False or throws RPC exception.
    - Result MUST return False.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    MemSession = sessionmaker(bind=engine)
    db = MemSession()

    u = DBUser(id=202, email="revoked_m32@test.org", phone="+919876543221", password_hash="h", firebase_uid="uid_m32_2", full_name="SQLite Revoked", role="WORKER", status="ACTIVE")
    p = DBWorkerProfile(user_id=202, did="did:passkhadam:worker:sqlite-rev-matrix-4", full_name="SQLite Revoked", is_credential_anchored=True, did_state="REVOKED")
    db.add_all([u, p])
    db.commit()

    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    with patch("app.models.db.SessionLocal", MemSession):
        assert bs.is_worker_valid("did:passkhadam:worker:sqlite-rev-matrix-4") is False

        # Even on RPC exception, SQLite REVOKED profile returns False
        mock_contract.functions.isWorkerValid.return_value.call.side_effect = ConnectionError("RPC timeout")
        mock_contract.functions.getWorkerByDid.return_value.call.side_effect = ConnectionError("RPC timeout")
        assert bs.is_worker_valid("did:passkhadam:worker:sqlite-rev-matrix-4") is False

    db.close()


def test_rpc_matrix_cond5_onchain_revoked_returns_false():
    """
    Test 5: On-chain revoked -> False.
    - Contract isWorkerValid returns False.
    - Contract getWorkerByDid returns isRegistered=True, isRevoked=True.
    - Even if SQLite DBWorkerProfile claims did_state='ACTIVE', onchain revocation is authoritative.
    - Result MUST return False.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    MemSession = sessionmaker(bind=engine)
    db = MemSession()

    did = "did:passkhadam:worker:onchain-rev-matrix-5"
    u = DBUser(id=203, email="chain_rev@test.org", phone="+919876543222", password_hash="h", firebase_uid="uid_m32_3", full_name="Worker", role="WORKER", status="ACTIVE")
    p = DBWorkerProfile(user_id=203, did=did, full_name="Worker", is_credential_anchored=True, did_state="ACTIVE")
    db.add_all([u, p])
    db.commit()

    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    # onchain_tuple: (did, cred_hash, ipfs_cid, issue_ts, update_ts, isRegistered=True, isRevoked=True, reason)
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = (did, b'\x00' * 32, 'QmCID', 1000, 1000, True, True, 'Revoked by authority')

    with patch("app.models.db.SessionLocal", MemSession):
        assert bs.is_worker_valid(did) is False
        # Verify worker_registry recorded the on-chain revocation
        assert bs.worker_registry[did]["is_revoked"] is True

    db.close()


def test_rpc_matrix_cond6_non_existent_did_returns_false():
    """
    Test 6: Non-existent DID -> False.
    - DID absent from on-chain contract, in-memory cache, and SQLite DB.
    - Must return False safely.
    - Edge cases: empty string, None, whitespace, SQL injection string.
    """
    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract
    mock_contract.functions.isWorkerValid.return_value.call.return_value = False
    mock_contract.functions.getWorkerByDid.return_value.call.return_value = ('', b'', '', 0, 0, False, False, '')

    assert bs.is_worker_valid("did:passkhadam:worker:ghost-matrix-6") is False
    assert bs.is_worker_valid("") is False
    assert bs.is_worker_valid(None) is False
    assert bs.is_worker_valid("   ") is False
    assert bs.is_worker_valid("' OR 1=1; --") is False


def test_rpc_matrix_cond7_rpc_exception_falls_back_to_cache_and_db():
    """
    Test 7: Network timeout / RPC exception -> fallback to cache and SQLite.
    - Contract throws network timeout / connection exceptions on both isWorkerValid and getWorkerByDid.
    - Subcase 7a: Worker present in memory cache -> returns True without throwing exception.
    - Subcase 7b: Worker present in SQLite DB -> returns True without throwing exception.
    - Subcase 7c: Worker not present anywhere -> returns False without throwing exception.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    MemSession = sessionmaker(bind=engine)
    db = MemSession()

    u = DBUser(id=204, email="rpc_fall@test.org", phone="+919876543223", password_hash="h", firebase_uid="uid_m32_4", full_name="Worker", role="WORKER", status="ACTIVE")
    p = DBWorkerProfile(user_id=204, did="did:passkhadam:worker:rpc-db-fallback-7", full_name="Worker", is_credential_anchored=True, did_state="ACTIVE")
    db.add_all([u, p])
    db.commit()

    bs = BlockchainService()
    bs.is_connected = True
    mock_contract = MagicMock()
    bs.worker_identity_contract = mock_contract

    # Simulate fatal RPC timeout
    mock_contract.functions.isWorkerValid.return_value.call.side_effect = TimeoutError("504 Gateway Timeout")
    mock_contract.functions.getWorkerByDid.return_value.call.side_effect = TimeoutError("504 Gateway Timeout")

    # Subcase 7a: In memory cache
    bs.worker_registry["did:passkhadam:worker:rpc-mem-fallback-7"] = {
        "did": "did:passkhadam:worker:rpc-mem-fallback-7",
        "is_registered": True,
        "is_revoked": False
    }
    assert bs.is_worker_valid("did:passkhadam:worker:rpc-mem-fallback-7") is True

    # Subcase 7b: In SQLite DB
    with patch("app.models.db.SessionLocal", MemSession):
        assert bs.is_worker_valid("did:passkhadam:worker:rpc-db-fallback-7") is True

    # Subcase 7c: Ghost DID under RPC outage
    assert bs.is_worker_valid("did:passkhadam:worker:ghost-during-outage") is False

    db.close()


# ============================================================================
# 2. DYNAMIC CREDENTIALS INVARIANTS: MULTI-STATE, ISOLATION & ZERO-LEAKAGE
# ============================================================================

def test_dynamic_credentials_mixed_states_and_zero_leakage_employer():
    """
    Dynamic Credentials Test:
    - Multiple credentials with mixed states (VALID, EXPIRED, REVOKED).
    - Presented by Worker A.
    - Worker B has separate credentials.
    - Verifies only matching credentials for Worker A appear in verified_certifications.
    - Verifies unassociated credentials from Worker B are NEVER leaked to Employer view.
    """
    db = SessionLocal()
    worker_did_a = "did:passkhadam:worker:challenger-a-101"
    worker_did_b = "did:passkhadam:worker:challenger-b-102"

    try:
        # Anchor both test workers
        _anchor_test_worker(worker_did_a, full_name="Amina Worker A", skills=["Electrician", "Solar Installer"])
        _anchor_test_worker(worker_did_b, full_name="Bilal Worker B", skills=["Crane Operator", "Rigging"])

        # Clean prior test rows
        db.query(DBWorkerCredential).filter(
            DBWorkerCredential.worker_did.in_([worker_did_a, worker_did_b])
        ).delete()
        db.commit()

        # Seed Worker A credentials (mixed states: VALID, EXPIRED, REVOKED)
        cred_a_valid = DBWorkerCredential(
            credential_id="CRED-A-VALID-01",
            worker_did=worker_did_a,
            title="Karnataka BOCW Electrician Welfare Card",
            credential_type="Welfare",
            issuer_name="Karnataka BOCW Board",
            issuer_role="GOVERNMENT",
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=180)
        )
        cred_a_expired = DBWorkerCredential(
            credential_id="CRED-A-EXPIRED-02",
            worker_did=worker_did_a,
            title="High Voltage Safety Induction",
            credential_type="Safety",
            issuer_name="National Safety Council",
            issuer_role="GOVERNMENT",
            status="VALID", # status says VALID in DB, but expires_at is past -> engine must dynamically flag EXPIRED
            expires_at=datetime.utcnow() - timedelta(days=15)
        )
        cred_a_revoked = DBWorkerCredential(
            credential_id="CRED-A-REVOKED-03",
            worker_did=worker_did_a,
            title="Disciplinary Revoked Stint License",
            credential_type="Skill",
            issuer_name="Apex Infrastructure Pvt Ltd",
            issuer_role="EMPLOYER",
            status="REVOKED",
            revocation_reason="Safety Protocol Violation",
            expires_at=datetime.utcnow() + timedelta(days=200)
        )
        cred_a_skills = DBWorkerCredential(
            credential_id="CRED-A-SKILLS-04",
            worker_did=worker_did_a,
            title="Master Solar PV Installer",
            credential_type="Skill",
            issuer_name="Green Power Tech Ltd",
            issuer_role="EMPLOYER",
            skills_json=json.dumps(["Solar PV", "Grid Inverter Setup"]),
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=365)
        )

        # Seed Worker B credentials (must NEVER leak into Worker A verification)
        cred_b_valid = DBWorkerCredential(
            credential_id="CRED-B-CONFIDENTIAL-01",
            worker_did=worker_did_b,
            title="Confidential Defense Infrastructure Clearance",
            credential_type="Security",
            issuer_name="Ministry of Defense",
            issuer_role="GOVERNMENT",
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=400)
        )
        cred_b_revoked = DBWorkerCredential(
            credential_id="CRED-B-REVOKED-02",
            worker_did=worker_did_b,
            title="Heavy Crane Rigging License",
            credential_type="Skill",
            issuer_name="Heavy Machinery Corp",
            issuer_role="EMPLOYER",
            status="REVOKED",
            expires_at=datetime.utcnow() + timedelta(days=100)
        )

        db.add_all([cred_a_valid, cred_a_expired, cred_a_revoked, cred_a_skills, cred_b_valid, cred_b_revoked])
        db.commit()

        # Worker A generates presentation QR
        png_bytes, _ = verification_engine.generate_qr_presentation(
            worker_did=worker_did_a,
            worker_profile={"full_name": "Amina Worker A", "origin_state": "Bihar", "current_state": "Karnataka"},
            validity_seconds=300
        )

        # Employer verifies Worker A presentation
        emp_result = verification_engine.verify_uploaded_presentation(
            image_bytes=png_bytes,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            db=db
        )

        assert emp_result["verified"] is True
        certs = emp_result["data"]["verified_certifications"]

        # Base Identity Credential + 4 Worker A credentials = 5 total
        assert len(certs) == 5

        cert_ids = [c.get("id") for c in certs]
        expected_ids = {"cred-identity-authority", "CRED-A-VALID-01", "CRED-A-EXPIRED-02", "CRED-A-REVOKED-03", "CRED-A-SKILLS-04"}
        assert set(cert_ids) == expected_ids

        # ZERO-LEAKAGE INVARIANT: Worker B's credentials must NEVER appear
        assert "CRED-B-CONFIDENTIAL-01" not in cert_ids
        assert "CRED-B-REVOKED-02" not in cert_ids
        for c in certs:
            assert "Confidential Defense" not in c.get("title", "")
            assert "Heavy Crane" not in c.get("title", "")

        # Status and dynamic expiration assertions
        expired_entry = next(c for c in certs if c.get("id") == "CRED-A-EXPIRED-02")
        assert expired_entry["status"] == "EXPIRED"

        revoked_entry = next(c for c in certs if c.get("id") == "CRED-A-REVOKED-03")
        assert revoked_entry["status"] == "REVOKED"

        valid_entry = next(c for c in certs if c.get("id") == "CRED-A-VALID-01")
        assert valid_entry["status"] == "VALID"

        skills_entry = next(c for c in certs if c.get("id") == "CRED-A-SKILLS-04")
        assert skills_entry["status"] == "VALID"
        assert "Solar PV" in skills_entry["skills"]
        assert "Grid Inverter Setup" in skills_entry["skills"]

    finally:
        db.query(DBWorkerCredential).filter(
            DBWorkerCredential.worker_did.in_([worker_did_a, worker_did_b])
        ).delete()
        db.commit()
        db.close()


def test_dynamic_credentials_mixed_states_and_zero_leakage_government():
    """
    Dynamic Credentials Test for GOVERNMENT view:
    - Verifies welfare credential populates bocw_registration_id.
    - Verifies expired credential maps to 'EXPIRED'.
    - Verifies revoked credential remains 'REVOKED'.
    - Verifies Worker B's credentials are never leaked to Government officer view.
    """
    db = SessionLocal()
    worker_did_a = "did:passkhadam:worker:challenger-a-101"
    worker_did_b = "did:passkhadam:worker:challenger-b-102"

    try:
        _anchor_test_worker(worker_did_a, full_name="Amina Worker A")
        _anchor_test_worker(worker_did_b, full_name="Bilal Worker B")

        db.query(DBWorkerCredential).filter(
            DBWorkerCredential.worker_did.in_([worker_did_a, worker_did_b])
        ).delete()
        db.commit()

        # Worker A BOCW credential
        bocw_a = DBWorkerCredential(
            credential_id="BOCW-KA-AUTH-9999",
            worker_did=worker_did_a,
            title="Karnataka BOCW Construction Welfare Card",
            credential_type="Welfare",
            issuer_name="Karnataka BOCW Board",
            issuer_role="GOVERNMENT",
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=200)
        )
        exp_a = DBWorkerCredential(
            credential_id="EXP-OLD-SAFETY-8888",
            worker_did=worker_did_a,
            title="Excavation Safety 2024",
            credential_type="Safety",
            issuer_name="Safety Board",
            issuer_role="GOVERNMENT",
            status="VALID",
            expires_at=datetime.utcnow() - timedelta(days=5) # Expired
        )
        rev_a = DBWorkerCredential(
            credential_id="REV-OFFENSE-7777",
            worker_did=worker_did_a,
            title="Restricted Chemical Handling",
            credential_type="Skill",
            issuer_name="Chemical Board",
            issuer_role="GOVERNMENT",
            status="REVOKED",
            expires_at=datetime.utcnow() + timedelta(days=100)
        )

        # Worker B credential
        bocw_b = DBWorkerCredential(
            credential_id="BOCW-MH-LEAK-PREVENT",
            worker_did=worker_did_b,
            title="Maharashtra BOCW Card for Bilal",
            credential_type="Welfare",
            issuer_name="Maharashtra BOCW Board",
            issuer_role="GOVERNMENT",
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=300)
        )
        db.add_all([bocw_a, exp_a, rev_a, bocw_b])
        db.commit()

        # Fresh presentation for Worker A
        png_bytes, _ = verification_engine.generate_qr_presentation(
            worker_did=worker_did_a,
            worker_profile={"full_name": "Amina Worker A", "origin_state": "Bihar", "current_state": "Karnataka"},
            validity_seconds=300
        )

        # Look up active government officer for caller_id
        gov_officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.status == "ACTIVE").first()
        gov_caller_id = str(gov_officer.id) if gov_officer else "GOV-OFF-0028"

        gov_res = verification_engine.verify_uploaded_presentation(
            image_bytes=png_bytes,
            caller_role="GOVERNMENT",
            caller_id=gov_caller_id,
            db=db
        )

        assert gov_res["verified"] is True
        gov_data = gov_res["data"]
        certs = gov_data["verified_certifications"]

        # Invariants
        assert len(certs) == 4 # Identity + 3 Worker A credentials
        cert_ids = [c.get("id") for c in certs]
        assert "BOCW-KA-AUTH-9999" in cert_ids
        assert "EXP-OLD-SAFETY-8888" in cert_ids
        assert "REV-OFFENSE-7777" in cert_ids

        # ZERO-LEAKAGE: Worker B BOCW card must NOT appear
        assert "BOCW-MH-LEAK-PREVENT" not in cert_ids
        for c in certs:
            assert "Maharashtra BOCW" not in c.get("title", "")

        # BOCW registration ID resolution
        assert gov_data["bocw_registered"] is True
        assert gov_data["bocw_registration_id"] == "BOCW-KA-AUTH-9999"

        # Check status mapping
        exp_entry = next(c for c in certs if c.get("id") == "EXP-OLD-SAFETY-8888")
        assert exp_entry["status"] == "EXPIRED"

        rev_entry = next(c for c in certs if c.get("id") == "REV-OFFENSE-7777")
        assert rev_entry["status"] == "REVOKED"

    finally:
        db.query(DBWorkerCredential).filter(
            DBWorkerCredential.worker_did.in_([worker_did_a, worker_did_b])
        ).delete()
        db.commit()
        db.close()


def test_dynamic_credentials_worker_b_strict_isolation():
    """
    Reverse Isolation Test:
    - Worker B presents QR.
    - Verify that Worker B receives only their own credentials.
    - Zero credentials from Worker A leak to Worker B's verification.
    """
    db = SessionLocal()
    worker_did_a = "did:passkhadam:worker:challenger-a-101"
    worker_did_b = "did:passkhadam:worker:challenger-b-102"

    try:
        _anchor_test_worker(worker_did_a, full_name="Amina Worker A")
        _anchor_test_worker(worker_did_b, full_name="Bilal Worker B")

        db.query(DBWorkerCredential).filter(
            DBWorkerCredential.worker_did.in_([worker_did_a, worker_did_b])
        ).delete()
        db.commit()

        # Seed Worker A credential
        cred_a = DBWorkerCredential(
            credential_id="CRED-A-ONLY",
            worker_did=worker_did_a,
            title="Worker A Exclusive Credential",
            credential_type="Skill",
            issuer_name="Issuer A",
            issuer_role="EMPLOYER",
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=100)
        )
        # Seed Worker B credential
        cred_b = DBWorkerCredential(
            credential_id="CRED-B-ONLY",
            worker_did=worker_did_b,
            title="Worker B Exclusive Credential",
            credential_type="Skill",
            issuer_name="Issuer B",
            issuer_role="EMPLOYER",
            status="VALID",
            expires_at=datetime.utcnow() + timedelta(days=100)
        )
        db.add_all([cred_a, cred_b])
        db.commit()

        # Worker B generates QR
        png_bytes, _ = verification_engine.generate_qr_presentation(
            worker_did=worker_did_b,
            worker_profile={"full_name": "Bilal Worker B", "origin_state": "UP", "current_state": "Maharashtra"},
            validity_seconds=300
        )

        emp_result = verification_engine.verify_uploaded_presentation(
            image_bytes=png_bytes,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            db=db
        )

        assert emp_result["verified"] is True
        certs = emp_result["data"]["verified_certifications"]
        cert_ids = [c.get("id") for c in certs]

        assert "CRED-B-ONLY" in cert_ids
        assert "CRED-A-ONLY" not in cert_ids
        assert len(certs) == 2 # Base Identity + CRED-B-ONLY

    finally:
        db.query(DBWorkerCredential).filter(
            DBWorkerCredential.worker_did.in_([worker_did_a, worker_did_b])
        ).delete()
        db.commit()
        db.close()


def test_dynamic_credentials_headless_fallback_returns_legacy_mock_array():
    """
    Headless Fallback Test:
    - When db is None (headless unit testing), verify_uploaded_presentation:
      1. Must NOT raise an exception.
      2. Must return verified=True.
      3. Must return the legacy mock certification array:
         [Identity Credential, BOCW Safety Certification, Workplace Safety Induction].
    - Verified for both EMPLOYER and GOVERNMENT caller roles.
    """
    worker_did = "did:passkhadam:worker:headless-m32-test"
    _anchor_test_worker(worker_did, full_name="Headless Test Worker")

    # Employer Role
    png_emp, _ = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={"full_name": "Headless Test Worker"},
        validity_seconds=300
    )
    emp_res = verification_engine.verify_uploaded_presentation(
        image_bytes=png_emp,
        caller_role="EMPLOYER",
        caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
        db=None # Explicit headless mode
    )
    assert emp_res["verified"] is True
    emp_certs = emp_res["data"]["verified_certifications"]
    assert len(emp_certs) == 3
    emp_types = [c["type"] for c in emp_certs]
    assert "Identity Credential" in emp_types
    assert "BOCW Safety Certification" in emp_types
    assert "Workplace Safety Induction" in emp_types

    # Government Role
    png_gov, _ = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={"full_name": "Headless Test Worker"},
        validity_seconds=300
    )
    gov_res = verification_engine.verify_uploaded_presentation(
        image_bytes=png_gov,
        caller_role="GOVERNMENT",
        caller_id="GOV-OFF-TEST-MOCK",
        db=None # Explicit headless mode
    )
    assert gov_res["verified"] is True
    gov_certs = gov_res["data"]["verified_certifications"]
    assert len(gov_certs) == 3
    gov_types = [c["type"] for c in gov_certs]
    assert "Identity Credential" in gov_types
    assert "BOCW Safety Certification" in gov_types
    assert "Workplace Safety Induction" in gov_types


def test_dynamic_credentials_worker_with_zero_credentials_returns_base_identity():
    """
    Zero Credentials Invariant:
    - When a worker has 0 credentials in DBWorkerCredential, verified_certifications
      contains strictly the base verified Identity Credential ('cred-identity-authority')
      and no phantom mock records.
    """
    db = SessionLocal()
    worker_did = "did:passkhadam:worker:zero-cred-103"
    try:
        _anchor_test_worker(worker_did, full_name="Uncertified New Worker")

        # Ensure no credentials exist
        db.query(DBWorkerCredential).filter(DBWorkerCredential.worker_did == worker_did).delete()
        db.commit()

        png_bytes, _ = verification_engine.generate_qr_presentation(
            worker_did=worker_did,
            worker_profile={"full_name": "Uncertified New Worker"},
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
        assert len(certs) == 1
        assert certs[0]["id"] == "cred-identity-authority"
        assert certs[0]["type"] == "Identity Credential"
        assert certs[0]["status"] == "VALID"
    finally:
        db.close()
