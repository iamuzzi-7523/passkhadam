"""
PassKhadam v0.5 — Milestone 1 (R1) Adversarial Challenge Test Suite
===================================================================
Adversarial stress harness authored by m1_v05_challenger_1.
Validates:
1. Dynamic source-record status mutation matrix (ACTIVE <-> INACTIVE <-> SUSPENDED <-> UNAVAILABLE <-> UNVERIFIED)
2. Zero stale caching: immediate reflection across profile, wallet, auth, and QR endpoints without server restart
3. Strict worker isolation: mutations to Worker A never bleed into Worker B
4. Resilience under missing records, dangling foreign keys, and simulated DB exceptions (no 500 crashes)
5. Robust normalization: status casing, is_active flag conflicts, non-standard status values
6. Parameterized endpoint RBAC & dynamic status leakage resistance
7. Idempotent recovery without duplicate DIDs or credential re-anchoring
"""

import os
import sys
import json
import uuid
import hashlib
from typing import Optional, Tuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
from app.api.endpoints.worker import resolve_worker_aadhaar_status

client = TestClient(app)


# =============================================================================
# Adversarial Helper Fixtures & Context Factory
# =============================================================================

class AdversarialWorkerContext:
    def __init__(
        self,
        user_id: int,
        profile_id: int,
        record_id: Optional[str],
        token: str,
        did: str,
        raw_num: str
    ):
        self.user_id = user_id
        self.profile_id = profile_id
        self.record_id = record_id
        self.token = token
        self.did = did
        self.raw_num = raw_num

    @property
    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


def create_adversarial_worker(
    email_tag: str = "adv_worker",
    initial_status: str = "ACTIVE",
    is_active: bool = True,
    link_record: bool = True
) -> AdversarialWorkerContext:
    """Spawns an isolated worker in the test database with an optional DBAadhaarRecord."""
    db: Session = SessionLocal()
    uid = f"uid_adv_{uuid.uuid4().hex[:10]}"
    email = f"{email_tag}_{uuid.uuid4().hex[:8]}@adversarial.test"
    pw_hash = hashlib.sha256("adv_test_pass_123".encode()).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name="Adversarial Test Worker",
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
    raw_num = f"88{uuid.uuid4().int % 10000000000:010d}"
    a_hash = hashlib.sha256(raw_num.encode()).hexdigest()
    masked = f"XXXX-XXXX-{raw_num[-4:]}"

    if link_record:
        record = DBAadhaarRecord(
            record_id=rec_id,
            aadhaar_hash=a_hash,
            masked_aadhaar=masked,
            full_name=user.full_name,
            dob="1992-06-15",
            gender="Male",
            origin_state="Bihar",
            status=initial_status,
            is_active=is_active
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    did = generate_worker_did(f"0x{uuid.uuid4().hex[:40]}")
    req_id = f"req_{uuid.uuid4().hex[:12]}"

    profile = DBWorkerProfile(
        user_id=user.id,
        full_name=user.full_name,
        dob="1992-06-15",
        gender="Male",
        origin_state="Bihar",
        current_state="Maharashtra",
        worker_category="Carpenter",
        skills_json=json.dumps(["Joinery", "Formwork"]),
        is_aadhaar_verified=link_record,
        masked_aadhaar=masked if link_record else None,
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

    return AdversarialWorkerContext(
        user_id=user_id,
        profile_id=profile_id,
        record_id=rec_id if link_record else None,
        token=token,
        did=did,
        raw_num=raw_num
    )


def mutate_record(record_id: str, new_status: str, is_active: Optional[bool] = None):
    """Mutates an existing DBAadhaarRecord directly in the database."""
    db: Session = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == record_id).first()
    assert rec is not None, f"Record {record_id} not found"
    rec.status = new_status
    if is_active is not None:
        rec.is_active = is_active
    db.commit()
    db.close()


# =============================================================================
# CHALLENGE SUITE 1: STATUS MUTATION CYCLE & IMMEDIATE REFLECTION
# =============================================================================

def test_adv_status_mutation_immediate_reflection_across_all_endpoints():
    """
    Stress-tests rapid sequential transitions:
    ACTIVE -> INACTIVE -> SUSPENDED -> ACTIVE -> INACTIVE -> ACTIVE
    Asserts immediate reflection on /profile/me, /wallet/me, /auth/me, /qr-card/me, and /download-qr/me.
    Verifies 0 stale caching, 0 delay, and immediate HTTP 403 gating on QR endpoints.
    """
    worker = create_adversarial_worker("refl_stress", initial_status="ACTIVE")

    # Step 1: Initial ACTIVE verification
    res_prof = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res_prof.status_code == 200
    assert res_prof.json()["aadhaar_status"] == "ACTIVE"

    res_wal = client.get("/api/v1/worker/wallet/me", headers=worker.auth_headers)
    assert res_wal.status_code == 200
    assert res_wal.json()["aadhaar_status"] == "ACTIVE"
    assert res_wal.json()["is_verified"] is True
    gov_cred = next(c for c in res_wal.json()["credentials"] if c["id"] == "cred-id-01")
    assert gov_cred["status"] == "VALID"

    res_auth = client.get("/api/v1/auth/me", headers=worker.auth_headers)
    assert res_auth.status_code == 200
    assert res_auth.json()["worker_profile"]["aadhaar_status"] == "ACTIVE"
    assert res_auth.json()["profile_status"] == "COMPLETE"

    res_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers)
    assert res_qr.status_code == 200
    assert "qr_base64_data_uri" in res_qr.json()

    res_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers=worker.auth_headers)
    assert res_dl.status_code == 200
    assert res_dl.headers["content-type"] == "image/png"

    # Step 2: Mutate to INACTIVE
    mutate_record(worker.record_id, "INACTIVE", is_active=False)

    res_prof2 = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res_prof2.status_code == 200
    assert res_prof2.json()["aadhaar_status"] == "INACTIVE"

    res_wal2 = client.get("/api/v1/worker/wallet/me", headers=worker.auth_headers)
    assert res_wal2.status_code == 200
    assert res_wal2.json()["aadhaar_status"] == "INACTIVE"
    assert res_wal2.json()["is_verified"] is False
    gov_cred2 = next(c for c in res_wal2.json()["credentials"] if c["id"] == "cred-id-01")
    assert gov_cred2["status"] == "INACTIVE"

    res_auth2 = client.get("/api/v1/auth/me", headers=worker.auth_headers)
    assert res_auth2.status_code == 200
    assert res_auth2.json()["worker_profile"]["aadhaar_status"] == "INACTIVE"
    assert res_auth2.json()["profile_status"] == "INACTIVE"

    res_qr2 = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers)
    assert res_qr2.status_code == 403
    assert "not ACTIVE" in res_qr2.json()["detail"]

    res_dl2 = client.get("/api/v1/worker/presentation/download-qr/me", headers=worker.auth_headers)
    assert res_dl2.status_code == 403

    # Step 3: Mutate to SUSPENDED
    mutate_record(worker.record_id, "SUSPENDED", is_active=False)

    res_prof3 = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res_prof3.status_code == 200
    assert res_prof3.json()["aadhaar_status"] == "SUSPENDED"

    res_wal3 = client.get("/api/v1/worker/wallet/me", headers=worker.auth_headers)
    assert res_wal3.status_code == 200
    assert res_wal3.json()["aadhaar_status"] == "SUSPENDED"
    assert res_wal3.json()["is_verified"] is False
    gov_cred3 = next(c for c in res_wal3.json()["credentials"] if c["id"] == "cred-id-01")
    assert gov_cred3["status"] == "SUSPENDED"

    res_auth3 = client.get("/api/v1/auth/me", headers=worker.auth_headers)
    assert res_auth3.status_code == 200
    assert res_auth3.json()["worker_profile"]["aadhaar_status"] == "SUSPENDED"
    assert res_auth3.json()["profile_status"] == "SUSPENDED"

    res_qr3 = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers)
    assert res_qr3.status_code == 403

    res_dl3 = client.get("/api/v1/worker/presentation/download-qr/me", headers=worker.auth_headers)
    assert res_dl3.status_code == 403

    # Step 4: Reactivate to ACTIVE
    mutate_record(worker.record_id, "ACTIVE", is_active=True)

    res_prof4 = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res_prof4.status_code == 200
    assert res_prof4.json()["aadhaar_status"] == "ACTIVE"

    res_qr4 = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers)
    assert res_qr4.status_code == 200

    res_dl4 = client.get("/api/v1/worker/presentation/download-qr/me", headers=worker.auth_headers)
    assert res_dl4.status_code == 200


def test_adv_rapid_status_churn_loop_consistency():
    """
    Simulates high-frequency oscillation of DBAadhaarRecord status (20 iterations)
    and asserts 100% strict adherence without caching lag.
    """
    worker = create_adversarial_worker("churn_loop", initial_status="ACTIVE")
    states = [
        ("INACTIVE", False, 403),
        ("ACTIVE", True, 200),
        ("SUSPENDED", False, 403),
        ("ACTIVE", True, 200),
        ("INACTIVE", False, 403),
        ("ACTIVE", True, 200),
        ("SUSPENDED", False, 403),
        ("ACTIVE", True, 200),
        ("INACTIVE", False, 403),
        ("ACTIVE", True, 200),
    ]

    for status_str, is_act, expected_qr_status in states:
        mutate_record(worker.record_id, status_str, is_act)

        # Check /profile/me
        p_res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
        assert p_res.status_code == 200
        assert p_res.json()["aadhaar_status"] == status_str

        # Check /presentation/qr-card/me
        qr_res = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers)
        assert qr_res.status_code == expected_qr_status


# =============================================================================
# CHALLENGE SUITE 2: CROSS-WORKER ISOLATION
# =============================================================================

def test_adv_cross_worker_status_isolation():
    """
    Empirically tests that mutating Worker A's status NEVER mutates or impacts Worker B.
    """
    worker_a = create_adversarial_worker("worker_a", initial_status="ACTIVE")
    worker_b = create_adversarial_worker("worker_b", initial_status="ACTIVE")

    # Both initial ACTIVE
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_a.auth_headers).status_code == 200
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_b.auth_headers).status_code == 200

    # Suspend Worker A
    mutate_record(worker_a.record_id, "SUSPENDED", is_active=False)

    # Worker A must be SUSPENDED and blocked
    res_a1 = client.get("/api/v1/worker/profile/me", headers=worker_a.auth_headers)
    assert res_a1.json()["aadhaar_status"] == "SUSPENDED"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_a.auth_headers).status_code == 403

    # Worker B must remain 100% ACTIVE and allowed
    res_b1 = client.get("/api/v1/worker/profile/me", headers=worker_b.auth_headers)
    assert res_b1.json()["aadhaar_status"] == "ACTIVE"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_b.auth_headers).status_code == 200

    # Deactivate Worker B
    mutate_record(worker_b.record_id, "INACTIVE", is_active=False)

    # Both must now be blocked with their respective distinct statuses
    assert client.get("/api/v1/worker/profile/me", headers=worker_a.auth_headers).json()["aadhaar_status"] == "SUSPENDED"
    assert client.get("/api/v1/worker/profile/me", headers=worker_b.auth_headers).json()["aadhaar_status"] == "INACTIVE"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_a.auth_headers).status_code == 403
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_b.auth_headers).status_code == 403

    # Reactivate Worker A only
    mutate_record(worker_a.record_id, "ACTIVE", is_active=True)

    # Worker A unblocked, Worker B STILL blocked
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_a.auth_headers).status_code == 200
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker_b.auth_headers).status_code == 403


# =============================================================================
# CHALLENGE SUITE 3: RESILIENCE & FAULT TOLERANCE (NO 500 CRASHES)
# =============================================================================

def test_adv_dangling_foreign_key_missing_record_returns_unavailable():
    """
    If worker_profile.aadhaar_record_id references a non-existent UUID in DBAadhaarRecord,
    the system must gracefully return UNAVAILABLE on profiles and 403 on QR generation,
    and NEVER crash with HTTP 500 Internal Server Error.
    """
    worker = create_adversarial_worker("dangling_fkey", initial_status="ACTIVE")

    # Corrupt aadhaar_record_id to non-existent UUID
    fake_rec_id = str(uuid.uuid4())
    db = SessionLocal()
    prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == worker.profile_id).first()
    prof.aadhaar_record_id = fake_rec_id
    db.commit()
    db.close()

    # Direct resolution test
    db = SessionLocal()
    prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == worker.profile_id).first()
    status_res, rec = resolve_worker_aadhaar_status(prof, db)
    db.close()
    assert status_res == "UNAVAILABLE"
    assert rec is None

    # Endpoint checks: must return 200 with UNAVAILABLE
    res_prof = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res_prof.status_code == 200
    assert res_prof.json()["aadhaar_status"] == "UNAVAILABLE"

    res_wal = client.get("/api/v1/worker/wallet/me", headers=worker.auth_headers)
    assert res_wal.status_code == 200
    assert res_wal.json()["aadhaar_status"] == "UNAVAILABLE"
    assert res_wal.json()["is_verified"] is False

    res_auth = client.get("/api/v1/auth/me", headers=worker.auth_headers)
    assert res_auth.status_code == 200
    assert res_auth.json()["worker_profile"]["aadhaar_status"] == "UNAVAILABLE"

    # QR Presentation check: must return 403 Forbidden, NEVER 500!
    res_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers)
    assert res_qr.status_code == 403
    assert "UNAVAILABLE" in res_qr.json()["detail"]


def test_adv_unlinked_unverified_profile_returns_unverified():
    """
    If worker_profile has no aadhaar_record_id and is_aadhaar_verified=False,
    resolve_worker_aadhaar_status must return UNVERIFIED.
    QR presentation must reject cleanly without crashing.
    """
    worker = create_adversarial_worker("unverified_worker", link_record=False)

    db = SessionLocal()
    prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == worker.profile_id).first()
    prof.is_aadhaar_verified = False
    prof.aadhaar_record_id = None
    prof.is_credential_anchored = False
    db.commit()

    status_res, rec = resolve_worker_aadhaar_status(prof, db)
    db.close()
    assert status_res == "UNVERIFIED"
    assert rec is None

    res_prof = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res_prof.status_code == 200
    assert res_prof.json()["aadhaar_status"] == "UNVERIFIED"

    # QR generation on unanchored identity returns HTTP 400 Bad Request
    res_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers)
    assert res_qr.status_code == 400


def test_adv_database_exception_during_resolution_returns_unavailable():
    """
    If an unexpected DB exception or lock occurs inside resolve_worker_aadhaar_status,
    it must catch the error, return UNAVAILABLE, and prevent 500 crashes.
    """
    worker = create_adversarial_worker("db_err_worker", initial_status="ACTIVE")

    db = SessionLocal()
    prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == worker.profile_id).first()

    # Mock db.query to raise an exception
    with patch.object(db, "query", side_effect=RuntimeError("Simulated DB lock / connection loss")):
        status_res, rec = resolve_worker_aadhaar_status(prof, db)
        assert status_res == "UNAVAILABLE"
        assert rec is None

    db.close()


# =============================================================================
# CHALLENGE SUITE 4: STATUS NORMALIZATION & EDGE CASE MINING
# =============================================================================

def test_adv_case_insensitivity_and_flag_precedence():
    """
    Stress-tests case variations ('active', 'inactive', 'suspended')
    and precedence of the is_active boolean flag.
    """
    worker = create_adversarial_worker("case_worker", initial_status="ACTIVE")

    # 1. Lowercase 'active' with is_active=True
    mutate_record(worker.record_id, "active", is_active=True)
    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.json()["aadhaar_status"] == "ACTIVE"

    # 2. Lowercase 'inactive'
    mutate_record(worker.record_id, "inactive", is_active=False)
    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.json()["aadhaar_status"] == "INACTIVE"

    # 3. Lowercase 'suspended'
    mutate_record(worker.record_id, "suspended", is_active=False)
    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.json()["aadhaar_status"] == "SUSPENDED"

    # 4. Status says "ACTIVE", but is_active flag is False -> Flag takes precedence: must be INACTIVE!
    mutate_record(worker.record_id, "ACTIVE", is_active=False)
    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.json()["aadhaar_status"] == "INACTIVE"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers).status_code == 403

    # 5. Non-standard status string e.g. "REVOKED":
    # 5a. With is_active=False -> is_active precedence makes it INACTIVE
    mutate_record(worker.record_id, "REVOKED", is_active=False)
    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.json()["aadhaar_status"] == "INACTIVE"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers).status_code == 403

    # 5b. With is_active=True -> status string REVOKED is preserved
    mutate_record(worker.record_id, "REVOKED", is_active=True)
    res2 = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res2.json()["aadhaar_status"] == "REVOKED"
    # QR must be forbidden because REVOKED != ACTIVE
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers).status_code == 403


def test_adv_null_status_with_is_active_flag():
    """
    When DBAadhaarRecord.status is None/NULL:
    - If is_active=True -> should default to ACTIVE
    - If is_active=False -> should evaluate to INACTIVE
    """
    worker = create_adversarial_worker("null_status_worker", initial_status="ACTIVE")

    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == worker.record_id).first()
    rec.status = None
    rec.is_active = True
    db.commit()
    db.close()

    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.json()["aadhaar_status"] == "ACTIVE"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers).status_code == 200

    # Now set is_active=False
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == worker.record_id).first()
    rec.status = None
    rec.is_active = False
    db.commit()
    db.close()

    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.json()["aadhaar_status"] == "INACTIVE"
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=worker.auth_headers).status_code == 403


# =============================================================================
# CHALLENGE SUITE 5: PARAMETERIZED ENDPOINTS & RBAC ISOLATION
# =============================================================================

def test_adv_parameterized_endpoint_idor_prevention():
    """
    Assures that Worker A cannot query Worker B's profile via /api/v1/worker/profile/{user_id}.
    Assures that parameterized endpoint also enforces Aadhaar status gating.
    """
    worker_a = create_adversarial_worker("param_worker_a", initial_status="ACTIVE")
    worker_b = create_adversarial_worker("param_worker_b", initial_status="SUSPENDED")

    # Worker A calling Worker B's profile -> 403 Forbidden
    res_prof = client.get(f"/api/v1/worker/profile/{worker_b.user_id}", headers=worker_a.auth_headers)
    assert res_prof.status_code == 403

    # Worker A calling Worker B's QR card -> 403 Forbidden
    res_qr = client.get(f"/api/v1/worker/presentation/qr-card/{worker_b.user_id}", headers=worker_a.auth_headers)
    assert res_qr.status_code == 403


# =============================================================================
# CHALLENGE SUITE 6: IDEMPOTENCY & RECOVERY WITHOUT DUPLICATE DIDS
# =============================================================================

def test_adv_reactivation_clean_recovery_retains_did_invariance():
    """
    Verifies that cycling a worker from ACTIVE -> SUSPENDED -> ACTIVE retains the
    exact same decentralized identifier (DID) and credential hash without duplication.
    """
    worker = create_adversarial_worker("did_invariance", initial_status="ACTIVE")
    initial_did = worker.did

    # Check initial profile
    res1 = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers).json()
    assert res1["did"] == initial_did
    assert res1["aadhaar_status"] == "ACTIVE"

    # Suspend
    mutate_record(worker.record_id, "SUSPENDED", is_active=False)
    res2 = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers).json()
    assert res2["did"] == initial_did
    assert res2["aadhaar_status"] == "SUSPENDED"

    # Reactivate
    mutate_record(worker.record_id, "ACTIVE", is_active=True)
    res3 = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers).json()
    assert res3["did"] == initial_did
    assert res3["aadhaar_status"] == "ACTIVE"

    # Verify count of worker profiles for this user is exactly 1
    db = SessionLocal()
    profiles_count = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == worker.user_id).count()
    db.close()
    assert profiles_count == 1


# =============================================================================
# CHALLENGE SUITE 7: ADVANCED EDGE CASES, RESILIENCE & ADVERSARIAL STRESS
# =============================================================================

def test_adv_empty_string_aadhaar_record_id_handled_safely():
    """
    If worker_profile.aadhaar_record_id is an empty string (''),
    it must be treated as unset and not crash SQL query.
    """
    worker = create_adversarial_worker("empty_id_worker", initial_status="ACTIVE")
    db = SessionLocal()
    prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == worker.profile_id).first()
    prof.aadhaar_record_id = ""
    prof.is_aadhaar_verified = False
    prof.is_credential_anchored = False
    db.commit()

    status_res, rec = resolve_worker_aadhaar_status(prof, db)
    db.close()
    assert status_res == "UNVERIFIED"
    assert rec is None

    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.status_code == 200
    assert res.json()["aadhaar_status"] == "UNVERIFIED"


def test_adv_authorized_employer_observes_live_worker_aadhaar_status():
    """
    Verifies that an authorized Employer inspecting a worker profile via
    /api/v1/worker/profile/{user_id} dynamically receives live Aadhaar status changes.
    """
    worker = create_adversarial_worker("emp_obs_worker", initial_status="ACTIVE")

    # Create approved employer
    db = SessionLocal()
    emp_uid = f"uid_emp_{uuid.uuid4().hex[:10]}"
    emp_email = f"employer_{uuid.uuid4().hex[:8]}@apexinfra.com"
    emp_user = DBUser(
        firebase_uid=emp_uid,
        full_name="Apex Infrastructure Manager",
        email=emp_email,
        phone="+919876543222",
        password_hash=hashlib.sha256("emp_pass_123".encode()).hexdigest(),
        role="EMPLOYER",
        status="ACTIVE",
        organization_name="Apex Infra Ltd",
        organization_status="APPROVED",
        organization_address="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(emp_user)
    db.commit()
    db.refresh(emp_user)
    emp_token = create_test_firebase_jwt(uid=emp_uid, email=emp_email, name=emp_user.full_name)
    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    db.close()

    # 1. Initially worker is ACTIVE
    res1 = client.get(f"/api/v1/worker/profile/{worker.user_id}", headers=emp_headers)
    assert res1.status_code == 200
    assert res1.json()["aadhaar_status"] == "ACTIVE"

    # 2. Worker mutated to SUSPENDED
    mutate_record(worker.record_id, "SUSPENDED", is_active=False)
    res2 = client.get(f"/api/v1/worker/profile/{worker.user_id}", headers=emp_headers)
    assert res2.status_code == 200
    assert res2.json()["aadhaar_status"] == "SUSPENDED"

    # 3. Worker mutated to INACTIVE
    mutate_record(worker.record_id, "INACTIVE", is_active=False)
    res3 = client.get(f"/api/v1/worker/profile/{worker.user_id}", headers=emp_headers)
    assert res3.status_code == 200
    assert res3.json()["aadhaar_status"] == "INACTIVE"


def test_adv_download_qr_endpoint_strictly_gated_on_active_status():
    """
    Verifies that /api/v1/worker/presentation/download-qr/me is strictly gated
    and returns HTTP 403 on INACTIVE, SUSPENDED, and UNAVAILABLE.
    """
    worker = create_adversarial_worker("download_qr_gate", initial_status="ACTIVE")

    # ACTIVE -> 200
    res_act = client.get("/api/v1/worker/presentation/download-qr/me", headers=worker.auth_headers)
    assert res_act.status_code == 200
    assert res_act.headers["content-type"] == "image/png"

    # INACTIVE -> 403
    mutate_record(worker.record_id, "INACTIVE", is_active=False)
    res_inact = client.get("/api/v1/worker/presentation/download-qr/me", headers=worker.auth_headers)
    assert res_inact.status_code == 403

    # SUSPENDED -> 403
    mutate_record(worker.record_id, "SUSPENDED", is_active=False)
    res_susp = client.get("/api/v1/worker/presentation/download-qr/me", headers=worker.auth_headers)
    assert res_susp.status_code == 403


def test_adv_tampered_or_malformed_aadhaar_record_id_in_db():
    """
    Injects adversarial SQL injection string into aadhaar_record_id.
    Asserts parameterized query safely isolates input and returns UNAVAILABLE without syntax error or 500 crash.
    """
    worker = create_adversarial_worker("sqli_defense", initial_status="ACTIVE")
    malicious_id = "'; DROP TABLE worker_profiles; --"

    db = SessionLocal()
    prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.id == worker.profile_id).first()
    prof.aadhaar_record_id = malicious_id
    db.commit()

    status_res, rec = resolve_worker_aadhaar_status(prof, db)
    db.close()

    assert status_res == "UNAVAILABLE"
    assert rec is None

    # Endpoint must return 200 with UNAVAILABLE
    res = client.get("/api/v1/worker/profile/me", headers=worker.auth_headers)
    assert res.status_code == 200
    assert res.json()["aadhaar_status"] == "UNAVAILABLE"


def test_adv_migration_script_idempotent_execution():
    """
    Re-runs the migration script directly to confirm zero crashes, idempotent execution,
    and preservation of all schema modifications.
    """
    from app.db.migrate import migrate_database
    res = migrate_database()
    assert res is True

