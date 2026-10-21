"""
Adversarial Stress Test Suite: Milestone 1 Iteration 2 (R1 Revalidation & Replay Hardening)
Agent: m1_v05_challenger_1_r2

Adversarially challenges:
1. Idempotent verification replay when citizen record is suspended in UIDAI: confirm rejection with HTTP 400.
2. Unlinked anchored workers: confirm resolve_worker_aadhaar_status returns ("UNVERIFIED", None)
   and QR generation strictly returns HTTP 403.
3. Rapid status oscillation and cross-worker isolation.
4. Client DID injection, role spoofing, IDOR, casing/whitespace variations, and unlinked recovery.
"""

import json
import uuid
import hashlib
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
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


def create_test_worker(
    prefix: str,
    status: str = "ACTIVE",
    is_active: bool = True,
    anchored: bool = True,
    verified: bool = True,
    link_record: bool = True
) -> Dict[str, Any]:
    """Helper to instantiate isolated worker and optionally linked DBAadhaarRecord."""
    db = SessionLocal()
    uid = f"uid_r2chal_{uuid.uuid4().hex[:10]}"
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@passkhadam.org"
    pw_hash = hashlib.sha256("test_pass_123".encode()).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name=f"Worker {prefix}",
        email=email,
        phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
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

    if link_record:
        record = DBAadhaarRecord(
            record_id=rec_id,
            aadhaar_hash=a_hash,
            masked_aadhaar=masked,
            full_name=user.full_name,
            dob="1992-05-15",
            gender="Male",
            origin_state="Uttar Pradesh",
            status=status,
            is_active=is_active
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    else:
        rec_id = None

    did = generate_worker_did(raw_num, user.full_name) if anchored else None
    req_id = f"req_{uuid.uuid4().hex[:12]}"

    profile = DBWorkerProfile(
        user_id=user.id,
        full_name=user.full_name,
        dob="1992-05-15",
        gender="Male",
        origin_state="Uttar Pradesh",
        current_state="Maharashtra",
        worker_category="Mason",
        skills_json=json.dumps(["Bricklaying"]),
        is_aadhaar_verified=verified,
        masked_aadhaar=masked if verified else None,
        aadhaar_request_id=req_id if verified else None,
        aadhaar_record_id=rec_id,
        did=did,
        ipfs_cid=f"Qm{uuid.uuid4().hex[:30]}" if anchored else None,
        credential_hash=f"0x{hashlib.sha256(did.encode()).hexdigest()}" if did else None,
        is_credential_anchored=anchored,
        did_state="ACTIVE" if anchored else "NOT_STARTED"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=user.full_name)
    user_id = user.id
    profile_id = profile.id
    db.close()

    return {
        "user_id": user_id,
        "profile_id": profile_id,
        "record_id": rec_id,
        "token": token,
        "did": did,
        "raw_num": raw_num,
        "full_name": user.full_name,
        "email": email,
        "aadhaar_hash": a_hash
    }


def create_test_admin() -> Dict[str, Any]:
    db = SessionLocal()
    uid = f"uid_adm_{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:8]}@passkhadam.org"
    user = DBUser(
        firebase_uid=uid,
        full_name="Test Admin",
        email=email,
        phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
        password_hash=hashlib.sha256("test_pass".encode()).hexdigest(),
        role="ADMIN",
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_test_firebase_jwt(uid=uid, email=email, name=user.full_name)
    user_id = user.id
    db.close()
    return {"user_id": user_id, "token": token}


# =============================================================================
# GROUP 1: IDEMPOTENT VERIFICATION REPLAY & SUSPENSION HARDENING
# =============================================================================

def test_c1_idempotent_replay_suspended_citizen_rejected_400():
    """Adversarial C1.1: Replaying verification when citizen record is SUSPENDED must return HTTP 400."""
    w = create_test_worker("c1_susp", status="ACTIVE", is_active=True, anchored=True, verified=True)

    # Operator suspends citizen record
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "SUSPENDED"
    rec.is_active = False
    db.commit()
    db.close()

    # Worker attempts Aadhaar verification replay with identical details
    payload = {
        "aadhaar_number": w["raw_num"],
        "full_name": w["full_name"]
    }
    resp = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json=payload,
        headers={"Authorization": f"Bearer {w['token']}"}
    )
    assert resp.status_code == 400
    assert "Aadhaar record is suspended" in resp.json().get("detail", "")


def test_c1_idempotent_replay_inactive_citizen_rejected_400():
    """Adversarial C1.2: Replaying verification when citizen record is INACTIVE must return HTTP 400."""
    w = create_test_worker("c1_inact", status="ACTIVE", is_active=True, anchored=True, verified=True)

    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "INACTIVE"
    rec.is_active = False
    db.commit()
    db.close()

    payload = {
        "aadhaar_number": w["raw_num"],
        "full_name": w["full_name"]
    }
    resp = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json=payload,
        headers={"Authorization": f"Bearer {w['token']}"}
    )
    assert resp.status_code == 400
    assert "Aadhaar record is currently inactive" in resp.json().get("detail", "")


def test_c1_idempotent_replay_discrepant_is_active_false_rejected_400():
    """Adversarial C1.3: Replaying verification when status is ACTIVE but is_active=False must return HTTP 400."""
    w = create_test_worker("c1_disc", status="ACTIVE", is_active=True, anchored=True, verified=True)

    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "ACTIVE"
    rec.is_active = False
    db.commit()
    db.close()

    payload = {
        "aadhaar_number": w["raw_num"],
        "full_name": w["full_name"]
    }
    resp = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json=payload,
        headers={"Authorization": f"Bearer {w['token']}"}
    )
    assert resp.status_code == 400
    assert "Aadhaar record is currently inactive" in resp.json().get("detail", "")


def test_c1_idempotent_replay_unlinked_profile_with_suspended_hash_rejected_400():
    """Adversarial C1.4: Anchored profile with unlinked aadhaar_record_id but suspended record by hash must return HTTP 400."""
    w = create_test_worker("c1_unlinked_susp", status="ACTIVE", is_active=True, anchored=True, verified=True)

    # Clear aadhaar_record_id and aadhaar_request_id on profile, suspend citizen record
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "SUSPENDED"
    rec.is_active = False
    db.commit()
    db.close()

    payload = {
        "aadhaar_number": w["raw_num"],
        "full_name": w["full_name"]
    }
    resp = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json=payload,
        headers={"Authorization": f"Bearer {w['token']}"}
    )
    assert resp.status_code == 400
    assert "Aadhaar record is suspended" in resp.json().get("detail", "")


def test_c1_idempotent_replay_reactivated_citizen_recovers_cleanly():
    """Adversarial C1.5: Suspended citizen that is reactivated must succeed on replay without duplicate DIDs."""
    w = create_test_worker("c1_react", status="ACTIVE", is_active=True, anchored=True, verified=True)

    # 1. Suspend
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "SUSPENDED"
    rec.is_active = False
    db.commit()
    db.close()

    payload = {"aadhaar_number": w["raw_num"], "full_name": w["full_name"]}
    r_susp = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers={"Authorization": f"Bearer {w['token']}"})
    assert r_susp.status_code == 400

    # 2. Reactivate
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "ACTIVE"
    rec.is_active = True
    db.commit()
    db.close()

    r_act = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers={"Authorization": f"Bearer {w['token']}"})
    assert r_act.status_code == 200
    data = r_act.json()
    assert data["verified"] is True
    assert data["is_idempotent_replay"] is True
    assert data["did"] == w["did"]

    # Assert 0 duplicate worker profiles
    db = SessionLocal()
    profiles = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).all()
    assert len(profiles) == 1
    db.close()


def test_c1_client_supplied_did_strictly_rejected_400():
    """Adversarial C1.6: Client-supplied DID injection attempt on verify endpoint must return HTTP 400."""
    w = create_test_worker("c1_inject", status="ACTIVE", is_active=True, anchored=True, verified=True)
    payload = {
        "aadhaar_number": w["raw_num"],
        "full_name": w["full_name"],
        "did": "did:passkhadam:0xmaliciousinjecteddid1234567890"
    }
    resp = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers={"Authorization": f"Bearer {w['token']}"})
    assert resp.status_code == 400
    assert "Client-supplied DID is strictly forbidden" in resp.json().get("detail", "")


def test_c1_mismatched_identity_replay_rejected_409():
    """Adversarial C1.7: Anchored worker attempting verification replay with different name must return HTTP 409."""
    w = create_test_worker("c1_mismatch", status="ACTIVE", is_active=True, anchored=True, verified=True)
    payload = {
        "aadhaar_number": w["raw_num"],
        "full_name": "Different Name Completely"
    }
    resp = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers={"Authorization": f"Bearer {w['token']}"})
    assert resp.status_code == 409
    assert "different Aadhaar identity" in resp.json().get("detail", "")


# =============================================================================
# GROUP 2: UNLINKED ANCHORED WORKERS & QR GATING RIGOR (HTTP 403)
# =============================================================================

def test_c2_unit_resolve_worker_aadhaar_status_unlinked_anchored():
    """Adversarial C2.1: resolve_worker_aadhaar_status MUST return ('UNVERIFIED', None) for unlinked anchored worker."""
    w = create_test_worker("c2_unit", status="ACTIVE", is_active=True, anchored=True, verified=True, link_record=False)

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    p.is_credential_anchored = True
    p.did_state = "ACTIVE"
    db.commit()

    # Direct unit call
    status_str, record = resolve_worker_aadhaar_status(p, db)
    assert status_str == "UNVERIFIED"
    assert record is None
    db.close()


def test_c2_unit_resolve_worker_aadhaar_status_dangling_record():
    """Adversarial C2.2: resolve_worker_aadhaar_status MUST return ('UNAVAILABLE', None) for dangling record_id."""
    w = create_test_worker("c2_dangle", status="ACTIVE", is_active=True, anchored=True, verified=True, link_record=False)

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).first()
    p.aadhaar_record_id = str(uuid.uuid4())  # does not exist
    db.commit()

    status_str, record = resolve_worker_aadhaar_status(p, db)
    assert status_str == "UNAVAILABLE"
    assert record is None
    db.close()


def test_c2_unlinked_anchored_worker_qr_generation_strictly_403_across_all_endpoints():
    """Adversarial C2.3: Unlinked anchored worker MUST be rejected with HTTP 403 on ALL 4 presentation endpoints."""
    w = create_test_worker("c2_unlink_qr", status="ACTIVE", is_active=True, anchored=True, verified=True, link_record=False)

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {w['token']}"}

    # 1. /presentation/qr-card/me -> 403
    r1 = client.get("/api/v1/worker/presentation/qr-card/me", headers=headers)
    assert r1.status_code == 403
    assert "QR generation forbidden" in r1.json().get("detail", "") or "UNVERIFIED" in r1.json().get("detail", "")

    # 2. /presentation/download-qr/me -> 403
    r2 = client.get("/api/v1/worker/presentation/download-qr/me", headers=headers)
    assert r2.status_code == 403
    assert "QR generation forbidden" in r2.json().get("detail", "") or "UNVERIFIED" in r2.json().get("detail", "")

    # 3. /presentation/qr-card/{user_id} (self) -> 403
    r3 = client.get(f"/api/v1/worker/presentation/qr-card/{w['user_id']}", headers=headers)
    assert r3.status_code == 403
    assert "QR generation forbidden" in r3.json().get("detail", "") or "UNVERIFIED" in r3.json().get("detail", "")

    # 4. /presentation/download-qr/{user_id} (self) -> 403
    r4 = client.get(f"/api/v1/worker/presentation/download-qr/{w['user_id']}", headers=headers)
    assert r4.status_code == 403
    assert "QR generation forbidden" in r4.json().get("detail", "") or "UNVERIFIED" in r4.json().get("detail", "")


def test_c2_admin_cannot_generate_qr_for_unlinked_worker_403():
    """Adversarial C2.4: Admin attempting to generate QR for an unlinked anchored worker must receive HTTP 403."""
    w = create_test_worker("c2_adm_unlink", status="ACTIVE", is_active=True, anchored=True, verified=True, link_record=False)
    adm = create_test_admin()

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {adm['token']}"}
    r_card = client.get(f"/api/v1/worker/presentation/qr-card/{w['user_id']}", headers=headers)
    assert r_card.status_code == 403

    r_dl = client.get(f"/api/v1/worker/presentation/download-qr/{w['user_id']}", headers=headers)
    assert r_dl.status_code == 403


def test_c2_unverified_unanchored_worker_strictly_403():
    """Adversarial C2.5: Fresh unanchored worker must receive HTTP 403 (not 400) on all presentation endpoints."""
    w = create_test_worker("c2_fresh", status="ACTIVE", is_active=True, anchored=False, verified=False, link_record=False)
    headers = {"Authorization": f"Bearer {w['token']}"}

    r1 = client.get("/api/v1/worker/presentation/qr-card/me", headers=headers)
    assert r1.status_code == 403

    r2 = client.get("/api/v1/worker/presentation/download-qr/me", headers=headers)
    assert r2.status_code == 403


def test_c2_unlinked_anchored_worker_recovers_after_successful_verification():
    """Adversarial C2.6: Unlinked anchored worker performs genuine verification and QR generation restores to 200."""
    w = create_test_worker("c2_recover", status="ACTIVE", is_active=True, anchored=True, verified=True, link_record=False)

    # Initially unlinked -> 403
    r_init = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w['token']}"})
    assert r_init.status_code == 403

    # Add active citizen record in DBAadhaarRecord matching worker
    db = SessionLocal()
    rec_id = str(uuid.uuid4())
    record = DBAadhaarRecord(
        record_id=rec_id,
        aadhaar_hash=w["aadhaar_hash"],
        masked_aadhaar=f"XXXX-XXXX-{w['raw_num'][-4:]}",
        full_name=w["full_name"],
        dob="1992-05-15",
        gender="Male",
        origin_state="Uttar Pradesh",
        status="ACTIVE",
        is_active=True
    )
    db.add(record)
    db.commit()
    db.close()

    # Worker calls verification replay
    payload = {"aadhaar_number": w["raw_num"], "full_name": w["full_name"]}
    r_verif = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers={"Authorization": f"Bearer {w['token']}"})
    assert r_verif.status_code == 200

    # Profile is now linked and ACTIVE -> QR card generation must succeed with 200
    r_after = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w['token']}"})
    assert r_after.status_code == 200
    assert r_after.json()["worker_did"] == w["did"]


# =============================================================================
# GROUP 3: RAPID STATUS OSCILLATION & CROSS-WORKER ISOLATION
# =============================================================================

def test_c3_rapid_status_oscillation_and_cross_worker_isolation():
    """
    Adversarial C3.1: Worker Alpha undergoes rapid 8-stage status oscillation.
    Worker Beta remains constant.
    Assert strict gating on Alpha, total isolation on Beta, and zero duplicate DIDs/profiles.
    """
    w_alpha = create_test_worker("alpha", status="ACTIVE", is_active=True, anchored=True, verified=True)
    w_beta = create_test_worker("beta", status="ACTIVE", is_active=True, anchored=True, verified=True)

    h_alpha = {"Authorization": f"Bearer {w_alpha['token']}"}
    h_beta = {"Authorization": f"Bearer {w_beta['token']}"}

    # Baseline: both ACTIVE -> 200
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=h_alpha).status_code == 200
    assert client.get("/api/v1/worker/presentation/qr-card/me", headers=h_beta).status_code == 200

    transitions = [
        # (status, is_active, expected_alpha_status, expected_alpha_qr, expected_alpha_replay_code)
        ("SUSPENDED", False, "SUSPENDED", 403, 400),
        ("ACTIVE", True, "ACTIVE", 200, 200),
        ("INACTIVE", False, "INACTIVE", 403, 400),
        ("ACTIVE", False, "INACTIVE", 403, 400),  # Discrepant: ACTIVE but is_active=False
        ("ACTIVE", True, "ACTIVE", 200, 200),
        ("SUSPENDED", False, "SUSPENDED", 403, 400),
        ("INACTIVE", False, "INACTIVE", 403, 400),
        ("ACTIVE", True, "ACTIVE", 200, 200),
    ]

    for step_idx, (t_status, t_is_act, exp_status, exp_qr, exp_replay) in enumerate(transitions):
        # Mutate Alpha's citizen record ONLY
        db = SessionLocal()
        r_alpha = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w_alpha["record_id"]).first()
        r_alpha.status = t_status
        r_alpha.is_active = t_is_act
        db.commit()
        db.close()

        # 1. Verify Alpha's status in /profile/me
        resp_alpha_prof = client.get("/api/v1/worker/profile/me", headers=h_alpha)
        assert resp_alpha_prof.status_code == 200
        assert resp_alpha_prof.json()["aadhaar_status"] == exp_status

        # 2. Verify Alpha's QR presentation access
        resp_alpha_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers=h_alpha)
        assert resp_alpha_qr.status_code == exp_qr

        # 3. Verify Alpha's verification replay behavior
        payload_alpha = {"aadhaar_number": w_alpha["raw_num"], "full_name": w_alpha["full_name"]}
        resp_alpha_rep = client.post("/api/v1/worker/verify-aadhaar/me", json=payload_alpha, headers=h_alpha)
        assert resp_alpha_rep.status_code == exp_replay

        # 4. CRITICAL ISOLATION CHECK: Assert Worker Beta is completely unaffected!
        resp_beta_prof = client.get("/api/v1/worker/profile/me", headers=h_beta)
        assert resp_beta_prof.status_code == 200
        assert resp_beta_prof.json()["aadhaar_status"] == "ACTIVE"

        resp_beta_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers=h_beta)
        assert resp_beta_qr.status_code == 200

        payload_beta = {"aadhaar_number": w_beta["raw_num"], "full_name": w_beta["full_name"]}
        resp_beta_rep = client.post("/api/v1/worker/verify-aadhaar/me", json=payload_beta, headers=h_beta)
        assert resp_beta_rep.status_code == 200

    # Post-oscillation invariant checks
    db = SessionLocal()
    # Exactly 1 profile each
    assert db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w_alpha["user_id"]).count() == 1
    assert db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w_beta["user_id"]).count() == 1

    # DIDs unchanged
    p_alpha = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w_alpha["user_id"]).first()
    p_beta = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w_beta["user_id"]).first()
    assert p_alpha.did == w_alpha["did"]
    assert p_beta.did == w_beta["did"]
    db.close()


def test_c3_cross_worker_idor_and_role_isolation():
    """Adversarial C3.2: Verify strict IDOR blocks between workers and cross-role protection."""
    w1 = create_test_worker("idor1", status="ACTIVE", is_active=True)
    w2 = create_test_worker("idor2", status="ACTIVE", is_active=True)

    h1 = {"Authorization": f"Bearer {w1['token']}"}
    h2 = {"Authorization": f"Bearer {w2['token']}"}

    # Worker 1 cannot generate QR for Worker 2
    r_idor1 = client.get(f"/api/v1/worker/presentation/qr-card/{w2['user_id']}", headers=h1)
    assert r_idor1.status_code == 403

    # Worker 2 cannot generate QR for Worker 1
    r_idor2 = client.get(f"/api/v1/worker/presentation/qr-card/{w1['user_id']}", headers=h2)
    assert r_idor2.status_code == 403

    # Unauthenticated request rejected with 401
    r_unauth = client.get("/api/v1/worker/presentation/qr-card/me")
    assert r_unauth.status_code == 401


# =============================================================================
# GROUP 4: RESILIENCE TO STATUS CASING & WHITESPACE
# =============================================================================

def test_c4_whitespace_and_casing_variations_in_status():
    """Adversarial C4.1: Status strings with whitespace or mixed casing correctly evaluate non-ACTIVE."""
    w = create_test_worker("c4_case", status="ACTIVE", is_active=True)

    # Set status to "  suspended  "
    db = SessionLocal()
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    r.status = "  suspended  "
    db.commit()
    db.close()

    resp_prof = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {w['token']}"})
    # upper().strip() or non-active fallback: should NOT be ACTIVE
    assert resp_prof.json()["aadhaar_status"] != "ACTIVE"

    # QR generation must be 403
    resp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w['token']}"})
    assert resp_qr.status_code == 403
