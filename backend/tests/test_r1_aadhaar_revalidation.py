"""
PassKhadam v0.5 — Test Suite: Live Aadhaar Source-Record Status Revalidation (R1)
================================================================================
Covers Requirement R1 (P0):
  - Live source-record status evaluation (ACTIVE, INACTIVE, SUSPENDED, UNAVAILABLE, UNVERIFIED)
  - Security gating on QR card presentation and download endpoints (HTTP 200 vs HTTP 403)
  - Reactivation clean recovery with zero duplicate DIDs
  - Isolation of status changes between distinct workers
  - Reflection of live status in /api/v1/auth/me and user context
  - Verification endpoint persistence of aadhaar_record_id
  - Mock Aadhaar Authority output contract including record_id
  - Parameterized QR endpoint security gating
  - Rapid status toggling idempotency
"""

import os
import sys
import json
import uuid
import hashlib
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
    DBWorkerProfile,
    DBAadhaarRecord,
    DBAadhaarAuditLog,
)
from app.core.auth import create_test_firebase_jwt
from app.core.crypto import generate_worker_did
from app.services.aadhaar_service import aadhaar_authority
from app.api.endpoints.worker import resolve_worker_aadhaar_status

client = TestClient(app)


# =============================================================================
# Helper Fixture & Context Utilities
# =============================================================================

class WorkerContext:
    def __init__(
        self,
        user_id: int,
        profile_id: int,
        record_id: Optional[str],
        token: str,
        did: Optional[str],
        raw_num: str
    ):
        self.user_id = user_id
        self.profile_id = profile_id
        self.record_id = record_id
        self.token = token
        self.did = did
        self.raw_num = raw_num


def create_worker_with_aadhaar_record(
    email_prefix: str = "reval_worker",
    status: str = "ACTIVE",
    link_record: bool = True
) -> WorkerContext:
    """
    Creates an isolated worker user, profile, linked DBAadhaarRecord, and returns WorkerContext.
    """
    db = SessionLocal()
    uid = f"uid_{uuid.uuid4().hex[:10]}"
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@passkhadam.org"
    pw_hash = hashlib.sha256("test_pass_123".encode()).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name="Deepak Kumar Sharma",
        email=email,
        phone="+919876543210",
        password_hash=pw_hash,
        role="WORKER",
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    rec_id = str(uuid.uuid4())
    raw_num = f"99{uuid.uuid4().int % 10000000000:010d}"
    a_hash = hashlib.sha256(raw_num.encode()).hexdigest()
    masked = f"XXXX-XXXX-{raw_num[-4:]}"

    record = DBAadhaarRecord(
        record_id=rec_id,
        aadhaar_hash=a_hash,
        masked_aadhaar=masked,
        full_name=user.full_name,
        dob="1994-08-22",
        gender="Male",
        origin_state="Rajasthan",
        status=status,
        is_active=(status == "ACTIVE")
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    did = generate_worker_did(f"0x{uuid.uuid4().hex[:40]}")
    req_id = f"req_{uuid.uuid4().hex[:12]}"

    profile = DBWorkerProfile(
        user_id=user.id,
        full_name=user.full_name,
        dob="1994-08-22",
        gender="Male",
        origin_state="Rajasthan",
        current_state="Gujarat",
        worker_category="Electrician",
        skills_json=json.dumps(["Wiring", "Panel Maintenance"]),
        is_aadhaar_verified=True,
        masked_aadhaar=masked,
        aadhaar_request_id=req_id,
        aadhaar_record_id=rec_id if link_record else None,
        did=did,
        ipfs_cid=f"Qm{uuid.uuid4().hex[:30]}",
        credential_hash=f"0x{hashlib.sha256(did.encode()).hexdigest()}",
        is_credential_anchored=True,
        did_state="ACTIVE"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    user_id = user.id
    profile_id = profile.id
    token = create_test_firebase_jwt(uid=uid, email=email, name=user.full_name)
    db.close()

    return WorkerContext(
        user_id=user_id,
        profile_id=profile_id,
        record_id=rec_id if link_record else None,
        token=token,
        did=did,
        raw_num=raw_num
    )


def create_unverified_worker(email_prefix: str = "unverified") -> WorkerContext:
    """Creates an unverified worker without any linked Aadhaar record or anchor."""
    db = SessionLocal()
    uid = f"uid_{uuid.uuid4().hex[:10]}"
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@passkhadam.org"
    pw_hash = hashlib.sha256("test_pass_123".encode()).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name="Anil Kumar Yadav",
        email=email,
        phone="+919876543210",
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
        full_name=user.full_name,
        dob="1996-03-11",
        gender="Male",
        origin_state="Bihar",
        current_state="Delhi",
        worker_category="Carpenter",
        skills_json=json.dumps(["Carpentry"]),
        is_aadhaar_verified=False,
        masked_aadhaar=None,
        aadhaar_request_id=None,
        aadhaar_record_id=None,
        did=None,
        ipfs_cid=None,
        credential_hash=None,
        is_credential_anchored=False,
        did_state=None
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    user_id = user.id
    profile_id = profile.id
    token = create_test_firebase_jwt(uid=uid, email=email, name=user.full_name)
    db.close()

    return WorkerContext(
        user_id=user_id,
        profile_id=profile_id,
        record_id=None,
        token=token,
        did=None,
        raw_num=""
    )


# =============================================================================
# TESTS: Requirement R1 Dynamic Revalidation & Security Gating
# =============================================================================

def test_worker_status_active_allows_qr_presentation_and_download():
    """R1.1: Worker with ACTIVE Aadhaar status can access profile, wallet, and generate/download QR."""
    ctx = create_worker_with_aadhaar_record(email_prefix="r1_active", status="ACTIVE")

    # 1. Profile reflects ACTIVE status and record_id
    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp.status_code == 200
    pdata = resp.json()
    assert pdata["aadhaar_status"] == "ACTIVE"
    assert pdata["aadhaar_record_id"] == ctx.record_id
    assert pdata["is_aadhaar_verified"] is True
    assert pdata["is_credential_anchored"] is True

    # 2. Wallet reflects ACTIVE status on identity credential
    resp_w = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_w.status_code == 200
    wdata = resp_w.json()
    assert wdata["aadhaar_status"] == "ACTIVE"
    creds = wdata.get("credentials", [])
    gov_cred = next((c for c in creds if "Government" in c.get("title", "") or "Identity" in c.get("title", "")), None)
    if gov_cred:
        assert gov_cred["status"] in ["VALID", "ACTIVE"]

    # 3. QR presentation card generation succeeds with HTTP 200
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr.status_code == 200
    qr_payload = resp_qr.json()
    assert "qr_base64_data_uri" in qr_payload
    assert qr_payload["qr_base64_data_uri"].startswith("data:image/png;base64,")
    assert qr_payload["expires_in_seconds"] == 300
    assert "raw_envelope" in qr_payload

    # 4. QR presentation image download succeeds with HTTP 200 and valid PNG bytes
    resp_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_dl.status_code == 200
    assert resp_dl.headers["content-type"] == "image/png"
    assert resp_dl.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_worker_status_inactive_blocks_qr_presentation_and_download_with_403():
    """R1.2: Citizen record set to INACTIVE causes dynamic revalidation to block QR presentation/download with HTTP 403."""
    ctx = create_worker_with_aadhaar_record(email_prefix="r1_inactive", status="ACTIVE")

    # Transition source citizen record to INACTIVE
    db = SessionLocal()
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
    r.status = "INACTIVE"
    r.is_active = False
    db.commit()
    db.close()

    # 1. Profile me dynamically reflects INACTIVE
    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp.status_code == 200
    assert resp.json()["aadhaar_status"] == "INACTIVE"

    # 2. Wallet me dynamically reflects INACTIVE
    resp_w = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_w.status_code == 200
    assert resp_w.json()["aadhaar_status"] == "INACTIVE"

    # 3. QR card generation is blocked with HTTP 403 Forbidden
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr.status_code == 403
    assert "not ACTIVE" in resp_qr.json()["detail"]

    # 4. QR download endpoint is blocked with HTTP 403 Forbidden
    resp_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_dl.status_code == 403
    assert "not ACTIVE" in resp_dl.json()["detail"]


def test_worker_status_suspended_blocks_qr_presentation_and_download_with_403():
    """R1.3: Citizen record set to SUSPENDED causes dynamic revalidation to block QR presentation/download with HTTP 403."""
    ctx = create_worker_with_aadhaar_record(email_prefix="r1_suspended", status="ACTIVE")

    # Transition source citizen record to SUSPENDED
    db = SessionLocal()
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
    r.status = "SUSPENDED"
    r.is_active = False
    db.commit()
    db.close()

    # 1. Profile me dynamically reflects SUSPENDED
    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp.status_code == 200
    assert resp.json()["aadhaar_status"] == "SUSPENDED"

    # 2. Wallet me reflects SUSPENDED
    resp_w = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_w.status_code == 200
    assert resp_w.json()["aadhaar_status"] == "SUSPENDED"

    # 3. QR card generation is blocked with HTTP 403 Forbidden
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr.status_code == 403
    assert "not ACTIVE" in resp_qr.json()["detail"]

    # 4. QR download is blocked with HTTP 403 Forbidden
    resp_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_dl.status_code == 403
    assert "not ACTIVE" in resp_dl.json()["detail"]


def test_worker_status_unavailable_blocks_qr_presentation_and_download_with_403():
    """R1.4: Dangling or missing citizen record produces UNAVAILABLE status and blocks QR presentation/download with HTTP 403."""
    ctx = create_worker_with_aadhaar_record(email_prefix="r1_unavail", status="ACTIVE")

    # Point profile to a nonexistent record_id
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
    p.aadhaar_record_id = str(uuid.uuid4())
    p.aadhaar_request_id = None
    db.commit()
    db.close()

    # 1. Profile me reflects UNAVAILABLE
    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp.status_code == 200
    assert resp.json()["aadhaar_status"] == "UNAVAILABLE"

    # 2. Wallet me reflects UNAVAILABLE
    resp_w = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_w.status_code == 200
    assert resp_w.json()["aadhaar_status"] == "UNAVAILABLE"

    # 3. QR card generation is blocked with HTTP 403 Forbidden
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr.status_code == 403
    assert "not ACTIVE" in resp_qr.json()["detail"]

    # 4. QR download is blocked with HTTP 403 Forbidden
    resp_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_dl.status_code == 403


def test_unverified_worker_status_blocks_qr_presentation():
    """R1.5: Unverified worker has UNVERIFIED status and cannot generate QR presentation."""
    ctx = create_unverified_worker("r1_unverif")

    # Profile me reflects UNVERIFIED
    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp.status_code == 200
    assert resp.json()["aadhaar_status"] == "UNVERIFIED"

    # QR endpoints block unverified worker strictly with HTTP 403 Forbidden
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr.status_code == 403

    resp_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_dl.status_code == 403


def test_reactivation_clean_recovery_zero_duplicate_dids():
    """R1.6: Toggling ACTIVE -> INACTIVE -> ACTIVE restores valid QR presentation with zero duplicate DIDs."""
    ctx = create_worker_with_aadhaar_record(email_prefix="r1_reactiv", status="ACTIVE")
    original_did = ctx.did
    assert original_did is not None

    db = SessionLocal()

    # Step 1: Deactivate citizen record
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
    r.status = "INACTIVE"
    r.is_active = False
    db.commit()

    resp_deact = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_deact.status_code == 403

    # Step 2: Reactivate citizen record
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
    r.status = "ACTIVE"
    r.is_active = True
    db.commit()

    # Profile reflects ACTIVE
    resp_prof = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_prof.status_code == 200
    assert resp_prof.json()["aadhaar_status"] == "ACTIVE"

    # QR generation recovers with HTTP 200
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr.status_code == 200
    assert resp_qr.json()["worker_did"] == original_did

    # Check database invariant: exactly 1 profile for this user with identical DID
    profiles = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == ctx.user_id).all()
    assert len(profiles) == 1
    assert profiles[0].did == original_did
    db.close()


def test_worker_status_isolation_between_workers():
    """R1.7: Status changes on Worker A's Aadhaar record have zero side effects on Worker B's standing."""
    ctx_a = create_worker_with_aadhaar_record(email_prefix="worker_a", status="ACTIVE")
    ctx_b = create_worker_with_aadhaar_record(email_prefix="worker_b", status="ACTIVE")

    # Suspend Worker A's record
    db = SessionLocal()
    r_a = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx_a.record_id).first()
    r_a.status = "SUSPENDED"
    r_a.is_active = False
    db.commit()
    db.close()

    # Worker A is SUSPENDED and blocked
    resp_a = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx_a.token}"})
    assert resp_a.json()["aadhaar_status"] == "SUSPENDED"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx_a.token}"}).status_code == 403

    # Worker B is unaffected: ACTIVE and permitted
    resp_b = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx_b.token}"})
    assert resp_b.json()["aadhaar_status"] == "ACTIVE"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx_b.token}"}).status_code == 200

    # Inactivate Worker B's record
    db = SessionLocal()
    r_b = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx_b.record_id).first()
    r_b.status = "INACTIVE"
    r_b.is_active = False
    db.commit()
    db.close()

    assert client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx_b.token}"}).status_code == 403

    # Restore Worker A to ACTIVE
    db = SessionLocal()
    r_a = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx_a.record_id).first()
    r_a.status = "ACTIVE"
    r_a.is_active = True
    db.commit()
    db.close()

    # Worker A recovers, Worker B remains blocked
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx_a.token}"}).status_code == 200
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx_b.token}"}).status_code == 403


def test_auth_me_reflects_dynamic_aadhaar_status():
    """R1.8: GET /api/v1/auth/me synchronizes dynamic aadhaar_status into user context worker_profile."""
    ctx = create_worker_with_aadhaar_record(email_prefix="auth_me_dyn", status="ACTIVE")

    # 1. Active state
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp.status_code == 200
    data = resp.json()
    wp = data.get("worker_profile", {})
    assert wp.get("aadhaar_status") == "ACTIVE"
    assert wp.get("aadhaar_record_id") == ctx.record_id
    assert data.get("profile_status") == "COMPLETE"

    # 2. Suspended state
    db = SessionLocal()
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
    r.status = "SUSPENDED"
    r.is_active = False
    db.commit()
    db.close()

    resp_susp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_susp.status_code == 200
    data_susp = resp_susp.json()
    assert data_susp.get("worker_profile", {}).get("aadhaar_status") == "SUSPENDED"
    assert data_susp.get("profile_status") == "SUSPENDED"

    # 3. Inactive state
    db = SessionLocal()
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
    r.status = "INACTIVE"
    r.is_active = False
    db.commit()
    db.close()

    resp_inact = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_inact.status_code == 200
    data_inact = resp_inact.json()
    assert data_inact.get("worker_profile", {}).get("aadhaar_status") == "INACTIVE"
    assert data_inact.get("profile_status") == "INACTIVE"

    # 4. Unverified worker
    ctx_unv = create_unverified_worker("auth_me_unv")
    resp_unv = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ctx_unv.token}"})
    assert resp_unv.status_code == 200
    data_unv = resp_unv.json()
    assert data_unv.get("worker_profile", {}).get("aadhaar_status") == "UNVERIFIED"
    assert data_unv.get("profile_status") == "PENDING_VERIFICATION"


def test_verify_aadhaar_endpoint_persists_aadhaar_record_id():
    """R1.9: POST /api/v1/worker/verify-aadhaar/me persists aadhaar_record_id to DBWorkerProfile."""
    db = SessionLocal()
    raw_num = f"99{uuid.uuid4().int % 10000000000:010d}"
    a_hash = hashlib.sha256(raw_num.encode()).hexdigest()
    rec_id = str(uuid.uuid4())

    citizen = DBAadhaarRecord(
        record_id=rec_id,
        aadhaar_hash=a_hash,
        masked_aadhaar=f"XXXX-XXXX-{raw_num[-4:]}",
        full_name="Pooja Devi Sharma",
        dob="1995-05-14",
        gender="Female",
        origin_state="Uttar Pradesh",
        status="ACTIVE",
        is_active=True
    )
    db.add(citizen)
    db.commit()
    db.refresh(citizen)
    db.close()

    # Create worker with matching name
    db = SessionLocal()
    uid = f"uid_{uuid.uuid4().hex[:10]}"
    email = f"verif_persist_{uuid.uuid4().hex[:8]}@passkhadam.org"
    pw_hash = hashlib.sha256("test_pass_123".encode()).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name="Pooja Devi Sharma",
        email=email,
        phone="+919876543210",
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
        full_name=user.full_name,
        dob="1995-05-14",
        gender="Female",
        origin_state="Uttar Pradesh",
        current_state="Delhi",
        worker_category="Tailor",
        skills_json=json.dumps(["Tailoring"]),
        is_aadhaar_verified=False,
        is_credential_anchored=False
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    user_id = user.id
    token = create_test_firebase_jwt(uid=uid, email=email, name=user.full_name)
    db.close()

    # Execute verification via self-service API
    resp = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"aadhaar_number": raw_num, "full_name": "Pooja Devi Sharma"}
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] in ["ANCHORED_ON_BLOCKCHAIN", "SUCCESS"]
    assert res_data.get("record_id") == rec_id or res_data.get("aadhaar_record_id") == rec_id

    # Confirm profile in database has persisted aadhaar_record_id
    db = SessionLocal()
    updated_prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
    assert updated_prof.aadhaar_record_id == rec_id
    assert updated_prof.is_aadhaar_verified is True
    assert updated_prof.is_credential_anchored is True
    db.close()

    # Confirm QR presentation now succeeds
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_qr.status_code == 200


def test_mock_aadhaar_authority_verify_identity_returns_record_id():
    """R1.10: MockAadhaarAuthority.verify_identity contract returns record_id in output dictionary."""
    db = SessionLocal()
    raw_num = f"99{uuid.uuid4().int % 10000000000:010d}"
    a_hash = hashlib.sha256(raw_num.encode()).hexdigest()
    rec_id = str(uuid.uuid4())

    rec = DBAadhaarRecord(
        record_id=rec_id,
        aadhaar_hash=a_hash,
        masked_aadhaar=f"XXXX-XXXX-{raw_num[-4:]}",
        full_name="Vikram Singh Rathore",
        dob="1990-11-20",
        gender="Male",
        origin_state="Rajasthan",
        status="ACTIVE",
        is_active=True
    )
    db.add(rec)
    db.commit()

    # 1. DB-backed verification returns exact DBAadhaarRecord.record_id
    out = aadhaar_authority.verify_identity(raw_num, submitted_name="Vikram Singh Rathore", db=db)
    assert out["verified"] is True
    assert "record_id" in out
    assert out["record_id"] == rec_id

    # 2. In-memory / fallback verification returns deterministic UUID record_id
    out_mem = aadhaar_authority.verify_identity("123456784821", submitted_name="Mohammed Uzair", db=None)
    assert out_mem["verified"] is True
    assert "record_id" in out_mem
    assert len(out_mem["record_id"]) == 36
    # Verify it is valid UUID format
    parsed_uuid = uuid.UUID(out_mem["record_id"])
    assert str(parsed_uuid) == out_mem["record_id"]

    db.close()


def test_parameterized_qr_endpoints_enforce_security_gate():
    """R1.11: Parameterized QR endpoints enforce same ACTIVE security gate."""
    ctx = create_worker_with_aadhaar_record(email_prefix="param_gate", status="ACTIVE")

    # When ACTIVE, worker can access parameterized endpoint for their own ID
    resp_qr = client.get(
        f"/api/v1/worker/presentation/qr-card/{ctx.user_id}",
        headers={"Authorization": f"Bearer {ctx.token}"}
    )
    assert resp_qr.status_code == 200

    resp_dl = client.get(
        f"/api/v1/worker/presentation/download-qr/{ctx.user_id}",
        headers={"Authorization": f"Bearer {ctx.token}"}
    )
    assert resp_dl.status_code == 200

    # When citizen record becomes INACTIVE, parameterized endpoints return HTTP 403
    db = SessionLocal()
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
    r.status = "INACTIVE"
    r.is_active = False
    db.commit()
    db.close()

    resp_qr_inact = client.get(
        f"/api/v1/worker/presentation/qr-card/{ctx.user_id}",
        headers={"Authorization": f"Bearer {ctx.token}"}
    )
    assert resp_qr_inact.status_code == 403

    resp_dl_inact = client.get(
        f"/api/v1/worker/presentation/download-qr/{ctx.user_id}",
        headers={"Authorization": f"Bearer {ctx.token}"}
    )
    assert resp_dl_inact.status_code == 403


def test_rapid_status_toggle_idempotence():
    """R1.12: Rapidly cycling status across states tracks source record without stale caching."""
    ctx = create_worker_with_aadhaar_record(email_prefix="rapid_cycle", status="ACTIVE")

    states_to_test = [
        ("INACTIVE", False, 403),
        ("ACTIVE", True, 200),
        ("SUSPENDED", False, 403),
        ("ACTIVE", True, 200),
        ("INACTIVE", False, 403),
        ("ACTIVE", True, 200)
    ]

    db = SessionLocal()
    for target_status, target_active, expected_qr_status in states_to_test:
        r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == ctx.record_id).first()
        r.status = target_status
        r.is_active = target_active
        db.commit()

        # Check resolve_worker_aadhaar_status directly
        p = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
        resolved_status, _ = resolve_worker_aadhaar_status(p, db)
        assert resolved_status == target_status

        # Check API profile/me
        resp_prof = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
        assert resp_prof.status_code == 200
        assert resp_prof.json()["aadhaar_status"] == target_status

        # Check QR endpoint gate
        resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
        assert resp_qr.status_code == expected_qr_status

    db.close()


# =============================================================================
# EXPLICIT UNLINKED ANCHORED TESTS (Fail-Open Prevention & Recovery)
# =============================================================================

def test_unlinked_anchored_profile_returns_unverified_status():
    """Unlinked anchored profile (aadhaar_record_id = None) strictly returns UNVERIFIED."""
    ctx = create_worker_with_aadhaar_record("unlinked_anch_1", link_record=False)
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    p.is_credential_anchored = True
    p.did_state = "ACTIVE"
    db.commit()

    resolved_status, rec = resolve_worker_aadhaar_status(p, db)
    db.close()
    assert resolved_status == "UNVERIFIED"
    assert rec is None

    resp_prof = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_prof.status_code == 200
    assert resp_prof.json()["aadhaar_status"] == "UNVERIFIED"


def test_unlinked_anchored_profile_blocks_qr_card_generation_with_403():
    """Unlinked anchored profile strictly blocked from generating QR card with HTTP 403."""
    ctx = create_worker_with_aadhaar_record("unlinked_anch_2", link_record=False)
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    p.is_credential_anchored = True
    p.did_state = "ACTIVE"
    db.commit()
    db.close()

    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr.status_code == 403
    assert "not ACTIVE" in resp_qr.json()["detail"] or "UNVERIFIED" in resp_qr.json()["detail"]


def test_unlinked_anchored_profile_blocks_qr_download_with_403():
    """Unlinked anchored profile strictly blocked from downloading QR image with HTTP 403."""
    ctx = create_worker_with_aadhaar_record("unlinked_anch_3", link_record=False)
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    p.is_credential_anchored = True
    p.did_state = "ACTIVE"
    db.commit()
    db.close()

    resp_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_dl.status_code == 403
    assert "not ACTIVE" in resp_dl.json()["detail"] or "UNVERIFIED" in resp_dl.json()["detail"]


def test_unlinked_anchored_profile_parameterized_qr_endpoints_block_with_403():
    """Parameterized QR card and download endpoints block unlinked anchored profile with HTTP 403."""
    ctx = create_worker_with_aadhaar_record("unlinked_anch_4", link_record=False)
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    p.is_credential_anchored = True
    p.did_state = "ACTIVE"
    db.commit()

    admin_user = DBUser(
        firebase_uid=f"uid_adm_{uuid.uuid4().hex[:8]}",
        full_name="Test Admin",
        email=f"admin_{uuid.uuid4().hex[:8]}@passkhadam.org",
        phone="+919876543000",
        password_hash="hash",
        role="ADMIN",
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(admin_user)
    db.commit()
    admin_token = create_test_firebase_jwt(uid=admin_user.firebase_uid, email=admin_user.email, name=admin_user.full_name)
    db.close()

    # Self parameterized call
    resp_self_qr = client.get(f"/api/v1/worker/presentation/qr-card/{ctx.user_id}", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_self_qr.status_code == 403

    resp_self_dl = client.get(f"/api/v1/worker/presentation/download-qr/{ctx.user_id}", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_self_dl.status_code == 403

    # Admin parameterized call
    resp_adm_qr = client.get(f"/api/v1/worker/presentation/qr-card/{ctx.user_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_adm_qr.status_code == 403

    resp_adm_dl = client.get(f"/api/v1/worker/presentation/download-qr/{ctx.user_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_adm_dl.status_code == 403


def test_unlinked_anchored_worker_subsequent_verification_recovery():
    """Unlinked anchored profile cleanly recovers active status and QR presentation after verification."""
    ctx = create_worker_with_aadhaar_record("unlinked_anch_5", link_record=False)
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    p.did = generate_worker_did(ctx.raw_num, "Deepak Kumar Sharma")
    p.is_credential_anchored = True
    p.did_state = "ACTIVE"
    orig_did = p.did
    db.commit()
    db.close()

    # Initially blocked
    resp_qr_init = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr_init.status_code == 403

    # Citizen record in DBAadhaarRecord is ACTIVE with raw_num
    # Worker performs verify-aadhaar/me with correct number and name
    reverif_payload = {
        "aadhaar_number": ctx.raw_num,
        "full_name": "Deepak Kumar Sharma"
    }
    resp_verif = client.post("/api/v1/worker/verify-aadhaar/me", json=reverif_payload, headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_verif.status_code == 200
    assert resp_verif.json()["verified"] is True

    # Assert aadhaar_record_id is now bound
    db = SessionLocal()
    p_after = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == ctx.profile_id).first()
    assert p_after.aadhaar_record_id is not None
    assert p_after.did == orig_did

    # Single profile, zero duplicate DIDs
    profiles_count = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == ctx.user_id).count()
    assert profiles_count == 1
    db.close()

    # Now QR generation succeeds
    resp_qr_after = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {ctx.token}"})
    assert resp_qr_after.status_code == 200
    assert resp_qr_after.json()["worker_did"] == orig_did
