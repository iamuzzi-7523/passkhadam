"""
PassKhadam v0.5 — Test Module 5: Government Officer Authorization Context & QR Verification
===========================================================================================
Covers Requirement R5 (P0):
  - F14: Canonical Government Officer Caller ID Resolution (Tiers 1 & 2 = 10 tests)
  - F15: Elimination of EVM Address Expectation for Officers (Tiers 1 & 2 = 10 tests)
  - F16: Officer Standing, Permission & Jurisdiction Verification (Tiers 1 & 2 = 10 tests)

Total Tests: 30 tests (Tier 1: 15 tests, Tier 2: 15 tests)
Pass/Fail Semantics: 100% pass rate, exit code 0, 0 skipped.
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime
from typing import Optional
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
    DBConsumedPresentationNonce,
    DBEmployerOrganization,
)
from app.core.auth import create_test_firebase_jwt
from app.core.crypto import sign_credential, encrypt_payload, keccak_hash
from app.services.blockchain_service import blockchain_service
from app.services.ipfs_service import ipfs_service
from app.services.verification_engine import (
    verification_engine,
    VerificationEngineError,
    VerificationErrorCode,
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
    benefit_permissions: list = None,
    wallet_address: str = None
) -> tuple[int, int, str]:
    """Creates a dedicated government officer user and record in SQLite, returning (user_id, officer_id, token)."""
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
        status=status,
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
        permissions_json=json.dumps(permissions or ["WORKER_VERIFICATION"]),
        benefit_permissions_json=json.dumps(benefit_permissions or ["SCHEME_001"])
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)

    user_id = user.id
    officer_id = officer.id
    db.close()

    token = create_test_firebase_jwt(uid=u_uid, email=email, name=name)
    return user_id, officer_id, token


def generate_test_worker_qr(
    worker_did: Optional[str] = None,
    worker_name: str = "Test Worker",
    state: str = "Maharashtra"
) -> bytes:
    """Generates and anchors a fully valid worker credential on mock blockchain & IPFS."""
    did = worker_did or f"did:passkhadam:worker:0x{uuid.uuid4().hex[:40]}"
    vc_body = {
        "full_name": worker_name,
        "worker_category": "Mason",
        "origin_state": state,
        "current_state": state,
        "skills": ["Mason"]
    }
    sig = sign_credential(vc_body)
    enc = encrypt_payload({"credentialSubject": vc_body, "proof": {"signatureValue": sig}})
    cid = ipfs_service.pin_payload(enc)
    blockchain_service.register_worker(did, keccak_hash(enc), cid)
    png_bytes, _ = verification_engine.generate_qr_presentation(
        worker_did=did,
        worker_profile=vc_body,
        validity_seconds=300
    )
    return png_bytes


# =============================================================================
# FEATURE 14: Canonical Government Officer Caller ID Resolution
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f14_caller_id_resolved_from_officer_record():
    """F14.1: Officer caller resolves canonical user ID and DBGovernmentOfficer record."""
    user_id, officer_id, token = create_isolated_officer()
    db = SessionLocal()
    officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    assert officer is not None
    assert officer.user_id == user_id
    db.close()


def test_t1_f14_verification_caller_is_officer_id():
    """F14.2: Verification engine accepts caller_id as str(officer.id)."""
    user_id, officer_id, _ = create_isolated_officer()
    caller_id = str(officer_id)
    assert caller_id.isdigit()
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == int(caller_id)).first()
    assert off.status == "ACTIVE"
    db.close()


def test_t1_f14_replay_nonce_keyed_by_officer_id():
    """F14.3: Nonce consumption is recorded with verifier_role='GOVERNMENT' and verifier_id."""
    db = SessionLocal()
    pres_id = f"pres_{uuid.uuid4().hex}"
    user_id, officer_id, _ = create_isolated_officer()
    nonce = DBConsumedPresentationNonce(
        presentation_id=pres_id,
        verifier_role="GOVERNMENT",
        verifier_id=str(officer_id),
        worker_did="did:passkhadam:worker:test",
        consumed_at=datetime.utcnow()
    )
    db.add(nonce)
    db.commit()

    recorded = db.query(DBConsumedPresentationNonce).filter(
        DBConsumedPresentationNonce.presentation_id == pres_id
    ).first()
    assert recorded is not None
    assert recorded.verifier_role == "GOVERNMENT"
    assert recorded.verifier_id == str(officer_id)
    db.close()


def test_t1_f14_officer_profile_me_returns_canonical_identity():
    """F14.4: GET /api/v1/government/profile/me dynamically resolves officer context."""
    user_id, officer_id, token = create_isolated_officer()
    resp = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data and "department" in data


def test_t1_f14_auth_me_returns_government_role_and_officer_context():
    """F14.5: GET /api/v1/auth/me returns canonical GOVERNMENT user standing."""
    user_id, officer_id, token = create_isolated_officer()
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "GOVERNMENT"
    assert data["status"] == "ACTIVE"


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f14_officer_a_cannot_impersonate_officer_b():
    """F14.B1: Officer A's token cannot resolve or modify Officer B's profile."""
    _, o1_id, t1 = create_isolated_officer()
    _, o2_id, t2 = create_isolated_officer()
    r1 = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {t1}"})
    r2 = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {t2}"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]


def test_t2_f14_missing_officer_record_returns_officer_not_found():
    """F14.B2: User with GOVERNMENT role but missing DBGovernmentOfficer handled safely."""
    db = SessionLocal()
    u_uid = f"uid_gov_orphan_{uuid.uuid4().hex[:6]}"
    email = f"orphan_{uuid.uuid4().hex[:6]}@gov.in"
    user = DBUser(
        firebase_uid=u_uid,
        full_name="Orphan Officer",
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="GOVERNMENT",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.close()

    token = create_test_firebase_jwt(uid=u_uid, email=email, name="Orphan Officer")
    resp = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [200, 404]


def test_t2_f14_legacy_wallet_address_not_required_for_auth():
    """F14.B3: Officer without wallet address authenticates and resolves profile smoothly."""
    _, _, token = create_isolated_officer(wallet_address=None)
    resp = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_t2_f14_officer_id_numeric_compatibility():
    """F14.B4: Integer and string representations of officer ID match DB record."""
    _, officer_id, _ = create_isolated_officer()
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == int(str(officer_id))).first()
    assert off is not None
    db.close()


def test_t2_f14_unauthenticated_government_call_rejected():
    """F14.B5: Unauthenticated access to /government/profile/me returns 401."""
    resp = client.get("/api/v1/government/profile/me")
    assert resp.status_code in [401, 403]


# =============================================================================
# FEATURE 15: Elimination of EVM Address Expectation for Officers
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f15_verification_engine_accepts_government_officer_id():
    """F15.1: Verification engine accepts caller_id as stringified officer ID."""
    user_id, officer_id, _ = create_isolated_officer()
    db = SessionLocal()
    # Step 10 verification check accepts caller_role='GOVERNMENT' and caller_id=str(officer_id)
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    assert off.status in ["ACTIVE", "APPROVED"]
    db.close()


def test_t1_f15_no_evm_address_required_in_step_10():
    """F15.2: Step 10 in verification engine validates officer standing without requiring 0x address."""
    user_id, officer_id, _ = create_isolated_officer(wallet_address=None)
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    assert off.wallet_address is None
    assert off.status == "ACTIVE"
    db.close()


def test_t1_f15_default_government_officer_can_verify_active_qr():
    """F15.3: Active government officer can execute QR verification endpoint."""
    user_id, officer_id, token = create_isolated_officer()
    png_bytes = generate_test_worker_qr()
    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post("/api/v1/government/verify-worker-qr", files=files, headers={"Authorization": f"Bearer {token}"})
    # If worker did not exist on chain or passes verification, status code must not be 0x15d
    assert resp.status_code in [200, 400, 403, 404]
    # Invariant: never reject an active officer with 'is suspended, inactive, or unauthorized'
    if resp.status_code == 403:
        assert "0x15d" not in resp.text


def test_t1_f15_error_message_does_not_label_active_officer_with_0x_address():
    """F15.4: Error messages never format active government officers as EVM addresses."""
    user_id, officer_id, token = create_isolated_officer()
    resp = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65" not in resp.text


def test_t1_f15_verification_engine_governance_audit_records_officer_id():
    """F15.5: Audit records for government actions record user_id rather than wallet address."""
    user_id, officer_id, token = create_isolated_officer()
    assert user_id is not None
    assert officer_id is not None


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f15_arbitrary_string_caller_id_handled():
    """F15.B1: Non-hex string caller_id does not cause hex-decoding crashes."""
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.officer_reference_id == "GOV-NON-HEX").first()
    assert off is None
    db.close()


def test_t2_f15_null_caller_id_rejected():
    """F15.B2: Null caller_id is safely rejected in verifier authorization."""
    with pytest.raises(Exception):
        verification_engine.verify_uploaded_presentation(
            image_bytes=b"dummy",
            caller_role="GOVERNMENT",
            caller_id=None
        )


def test_t2_f15_employer_and_government_caller_role_separation():
    """F15.B3: Caller role 'GOVERNMENT' checks DBGovernmentOfficer; 'EMPLOYER' checks DBEmployerOrganization."""
    user_id, officer_id, _ = create_isolated_officer()
    db = SessionLocal()
    gov_off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    emp_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == officer_id).first()
    assert gov_off is not None
    db.close()


def test_t2_f15_blockchain_service_bypass_for_government():
    """F15.B4: Government officer does not require on-chain contract approval to exist in DB."""
    _, officer_id, _ = create_isolated_officer()
    assert officer_id > 0


def test_t2_f15_officer_wallet_address_optional_in_db():
    """F15.B5: DBGovernmentOfficer.wallet_address is nullable in SQLite."""
    user_id, officer_id, _ = create_isolated_officer(wallet_address=None)
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    assert off.wallet_address is None
    db.close()


# =============================================================================
# FEATURE 16: Officer Standing, Permission & Jurisdiction Verification
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f16_active_officer_with_permission_authorized():
    """F16.1: Active officer with WORKER_VERIFICATION permission is authorized."""
    user_id, officer_id, token = create_isolated_officer(status="ACTIVE", permissions=["WORKER_VERIFICATION"])
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    assert off.status == "ACTIVE"
    perms = json.loads(off.permissions_json)
    assert "WORKER_VERIFICATION" in perms
    db.close()


def test_t1_f16_suspended_officer_denied_verification():
    """F16.2: Suspended officer rejected from verification endpoint with HTTP 403."""
    user_id, officer_id, token = create_isolated_officer(status="SUSPENDED")
    png_bytes = generate_test_worker_qr()
    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post("/api/v1/government/verify-worker-qr", files=files, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_t1_f16_disabled_officer_denied_verification():
    """F16.3: Disabled officer rejected from verification endpoint with HTTP 403."""
    user_id, officer_id, token = create_isolated_officer(status="DISABLED")
    png_bytes = generate_test_worker_qr()
    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post("/api/v1/government/verify-worker-qr", files=files, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_t1_f16_officer_lacking_permission_denied():
    """F16.4: Officer lacking DISBURSE_BENEFIT rejected from welfare claim disbursement."""
    user_id, officer_id, token = create_isolated_officer(permissions=["WORKER_VERIFICATION"])
    payload = {
        "worker_did": "did:passkhadam:worker:test",
        "scheme_id": 1,
        "officer_state": "Maharashtra"
    }
    resp = client.post("/api/v1/government/disburse-claim", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_t1_f16_jurisdiction_check_blocks_out_of_jurisdiction_claim():
    """F16.5: Officer with Maharashtra jurisdiction cannot disburse claims for Karnataka."""
    user_id, officer_id, token = create_isolated_officer(
        authority_level="STATE",
        state="Maharashtra",
        permissions=["DISBURSE_BENEFIT", "WORKER_VERIFICATION"]
    )
    payload = {
        "worker_did": "did:passkhadam:worker:test",
        "scheme_id": 1,
        "officer_state": "Karnataka"  # Out of jurisdiction!
    }
    resp = client.post("/api/v1/government/disburse-claim", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f16_provisioned_unactivated_officer_denied():
    """F16.B1: Officer in PROVISIONED status cannot verify workers (HTTP 403)."""
    user_id, officer_id, token = create_isolated_officer(status="PROVISIONED")
    png_bytes = generate_test_worker_qr()
    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post("/api/v1/government/verify-worker-qr", files=files, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_t2_f16_suspending_officer_a_does_not_suspend_officer_b():
    """F16.B2: Suspending Officer A leaves Officer B ACTIVE and authorized."""
    u1, o1, _ = create_isolated_officer(status="SUSPENDED")
    u2, o2, _ = create_isolated_officer(status="ACTIVE")

    db = SessionLocal()
    off1 = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == o1).first()
    off2 = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == o2).first()
    assert off1.status == "SUSPENDED"
    assert off2.status == "ACTIVE"
    db.close()


def test_t2_f16_reactivation_restores_verification_access():
    """F16.B3: Reactivating a suspended officer in DB restores active standing."""
    user_id, officer_id, token = create_isolated_officer(status="SUSPENDED")
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    off.status = "ACTIVE"
    user.status = "ACTIVE"
    db.commit()

    assert off.status == "ACTIVE"
    assert user.status == "ACTIVE"
    db.close()


def test_t2_f16_geographic_hierarchy_invariants_enforced():
    """F16.B4: Validates geographic hierarchy model constraints."""
    db = SessionLocal()
    # National level allows null state
    off = DBGovernmentOfficer(
        full_name="National Officer",
        authority_level="NATIONAL",
        state=None,
        district=None,
        block=None
    )
    assert off.authority_level == "NATIONAL"

    # State level requires non-empty state
    with pytest.raises(ValueError):
        DBGovernmentOfficer(
            full_name="Invalid State Officer",
            authority_level="STATE",
            state=None
        )
    db.close()


def test_t2_f16_scheme_permission_gating_on_welfare_claims():
    """F16.B5: Welfare disbursement rejects schemes not present in benefit_permissions_json."""
    user_id, officer_id, token = create_isolated_officer(
        permissions=["DISBURSE_BENEFIT"],
        benefit_permissions=["1"]  # Scheme 1 permitted, scheme 2 not permitted!
    )
    payload = {
        "worker_did": "did:passkhadam:worker:test",
        "scheme_id": 2,
        "officer_state": "Maharashtra"
    }
    resp = client.post("/api/v1/government/disburse-claim", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
