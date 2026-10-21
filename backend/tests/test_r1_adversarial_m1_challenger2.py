"""
Adversarial Challenge & Stress Test Suite: Milestone 1 (R1)
Author: m1_v05_challenger_2 (Formal Integration by m1_v05_worker_2)

Integrates all 34 adversarial scenarios covering:
- Suite 1: Direct Non-ACTIVE Status Gating on /me endpoints (Scenarios 1.1a - 1.5d, 14 scenarios)
- Suite 2: Bypass Vectors and Adversarial Attempts (Scenarios 2.1a - 2.8, 12 scenarios)
- Suite 3: Reactivation Recovery & Identity Integrity (Scenarios 3.1a - 3.2, 6 scenarios)
- Suite 4: Demographic & Unlinked Edge Cases (Scenarios 4.1 - 4.2, 2 scenarios)
Total: 34 adversarial scenarios.
"""

import json
import uuid
import hashlib
from typing import Optional, Dict, Any, List

from fastapi.testclient import TestClient
from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBWorkerProfile,
    DBAadhaarRecord,
    DBAadhaarAuditLog,
    DBEmployerOrganization,
    DBGovernmentOfficer,
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
    uid = f"uid_chal_{uuid.uuid4().hex[:10]}"
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
        "raw_num": raw_num
    }


def create_test_user_with_role(role: str, prefix: str) -> Dict[str, Any]:
    """Helper to instantiate isolated non-worker user."""
    db = SessionLocal()
    uid = f"uid_{role.lower()}_{uuid.uuid4().hex[:8]}"
    email = f"{prefix}_{uuid.uuid4().hex[:8]}_{role.lower()}@passkhadam.org"
    user = DBUser(
        firebase_uid=uid,
        full_name=f"Test {role.capitalize()}",
        email=email,
        phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
        password_hash=hashlib.sha256("test_pass".encode()).hexdigest(),
        role=role,
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_test_firebase_jwt(uid=uid, email=email, name=user.full_name)
    u_id = user.id
    db.close()
    return {"user_id": u_id, "token": token}


# =============================================================================
# SUITE 1: DIRECT NON-ACTIVE STATUS GATING ON /me ENDPOINTS (14 scenarios)
# =============================================================================

def test_adv_1_1_inactive_status_blocks_qr_card_and_download():
    """Scenarios 1.1a & 1.1b: INACTIVE Aadhaar state strictly blocks QR card and download with 403."""
    w_inactive = create_test_worker("sw1_inactive", status="INACTIVE", is_active=False)
    r_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_inactive['token']}"})
    assert r_qr.status_code == 403
    assert "not ACTIVE" in r_qr.json().get("detail", "") or "INACTIVE" in r_qr.json().get("detail", "")

    r_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w_inactive['token']}"})
    assert r_dl.status_code == 403


def test_adv_1_2_suspended_status_blocks_qr_card_and_download():
    """Scenarios 1.2a & 1.2b: SUSPENDED Aadhaar state strictly blocks QR card and download with 403."""
    w_suspended = create_test_worker("sw1_suspended", status="SUSPENDED", is_active=False)
    r_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_suspended['token']}"})
    assert r_qr.status_code == 403
    assert "not ACTIVE" in r_qr.json().get("detail", "") or "SUSPENDED" in r_qr.json().get("detail", "")

    r_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w_suspended['token']}"})
    assert r_dl.status_code == 403


def test_adv_1_3_unavailable_dangling_record_blocks_qr():
    """Scenarios 1.3a & 1.3b: UNAVAILABLE state (dangling record deleted from DB) blocks with 403."""
    w_unavail = create_test_worker("sw1_unavail", status="ACTIVE", is_active=True)
    db = SessionLocal()
    db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w_unavail['record_id']).delete()
    db.commit()
    db.close()

    r_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_unavail['token']}"})
    assert r_qr.status_code == 403
    assert "not ACTIVE" in r_qr.json().get("detail", "") or "UNAVAILABLE" in r_qr.json().get("detail", "")

    r_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w_unavail['token']}"})
    assert r_dl.status_code == 403


def test_adv_1_4_unverified_unanchored_and_anchored_blocks_with_403():
    """Scenarios 1.4a - 1.4d: UNVERIFIED unanchored and anchored profiles strictly blocked with 403."""
    # Case A: Normal unverified worker (not anchored, not verified)
    w_unverif_normal = create_test_worker("sw1_unv_norm", status="ACTIVE", is_active=True, anchored=False, verified=False, link_record=False)
    r_qr_unv_norm = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_unverif_normal['token']}"})
    r_dl_unv_norm = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w_unverif_normal['token']}"})
    assert r_qr_unv_norm.status_code == 403
    assert r_dl_unv_norm.status_code == 403

    # Case B: Anchored but unverified (is_aadhaar_verified=False, aadhaar_record_id=None, is_credential_anchored=True)
    w_unverif_anch = create_test_worker("sw1_unv_anch", status="ACTIVE", is_active=True, anchored=True, verified=False, link_record=False)
    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w_unverif_anch['user_id']).first()
    p.did_state = "NOT_STARTED"
    db.commit()
    db.close()

    r_qr_unv_anch = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_unverif_anch['token']}"})
    r_dl_unv_anch = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w_unverif_anch['token']}"})
    assert r_qr_unv_anch.status_code == 403
    assert r_dl_unv_anch.status_code == 403


def test_adv_1_5_subtle_discrepant_status_configurations_blocked():
    """Scenarios 1.5a - 1.5d: Subtle discrepant status configs correctly treated as non-ACTIVE and blocked with 403."""
    # 1.5a: status="ACTIVE", but is_active=False
    w_disc1 = create_test_worker("sw1_disc1", status="ACTIVE", is_active=False)
    r_qr_disc1 = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_disc1['token']}"})
    assert r_qr_disc1.status_code == 403

    # 1.5b: status="SUSPENDED", but is_active=True
    w_disc2 = create_test_worker("sw1_disc2", status="SUSPENDED", is_active=True)
    r_qr_disc2 = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_disc2['token']}"})
    assert r_qr_disc2.status_code == 403

    # 1.5c: Case insensitivity check: status="suspended" (lowercase)
    w_lower = create_test_worker("sw1_lower", status="suspended", is_active=False)
    r_qr_lower = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_lower['token']}"})
    assert r_qr_lower.status_code == 403

    # 1.5d: Unknown status string: status="REVOKED"
    w_revoked = create_test_worker("sw1_revoked", status="REVOKED", is_active=False)
    r_qr_rev = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_revoked['token']}"})
    assert r_qr_rev.status_code == 403


# =============================================================================
# SUITE 2: BYPASS VECTORS & ADVERSARIAL ATTEMPTS (12 scenarios)
# =============================================================================

def test_adv_2_1_parameterized_qr_for_self_while_suspended_returns_403():
    """Scenarios 2.1a & 2.1b: Calling parameterized QR endpoints for self while SUSPENDED returns 403."""
    w_suspended = create_test_worker("sw2_susp", status="SUSPENDED", is_active=False)
    r_param_qr = client.get(f"/api/v1/worker/presentation/qr-card/{w_suspended['user_id']}", headers={"Authorization": f"Bearer {w_suspended['token']}"})
    assert r_param_qr.status_code == 403
    assert "not ACTIVE" in r_param_qr.text

    r_param_dl = client.get(f"/api/v1/worker/presentation/download-qr/{w_suspended['user_id']}", headers={"Authorization": f"Bearer {w_suspended['token']}"})
    assert r_param_dl.status_code == 403
    assert "not ACTIVE" in r_param_dl.text


def test_adv_2_2_idor_attempt_on_active_worker_qr_rejected_with_403():
    """Scenarios 2.2a & 2.2b: IDOR attempt by suspended worker to access active worker's QR rejected with 403."""
    w_active = create_test_worker("sw2_active", status="ACTIVE", is_active=True)
    w_suspended = create_test_worker("sw2_susp_idor", status="SUSPENDED", is_active=False)

    r_idor_qr = client.get(f"/api/v1/worker/presentation/qr-card/{w_active['user_id']}", headers={"Authorization": f"Bearer {w_suspended['token']}"})
    assert r_idor_qr.status_code == 403
    assert "Workers can only generate their own" in r_idor_qr.text

    r_idor_dl = client.get(f"/api/v1/worker/presentation/download-qr/{w_active['user_id']}", headers={"Authorization": f"Bearer {w_suspended['token']}"})
    assert r_idor_dl.status_code == 403
    assert "Workers can only download their own" in r_idor_dl.text


def test_adv_2_3_admin_parameterized_qr_for_suspended_worker_rejected_with_403():
    """Scenarios 2.3a & 2.3b: Admin calling parameterized QR on SUSPENDED worker rejected with 403."""
    w_suspended = create_test_worker("sw2_susp_adm", status="SUSPENDED", is_active=False)
    admin = create_test_user_with_role("ADMIN", "sw2_admin")

    r_admin_qr = client.get(f"/api/v1/worker/presentation/qr-card/{w_suspended['user_id']}", headers={"Authorization": f"Bearer {admin['token']}"})
    assert r_admin_qr.status_code == 403
    assert "not ACTIVE" in r_admin_qr.text

    r_admin_dl = client.get(f"/api/v1/worker/presentation/download-qr/{w_suspended['user_id']}", headers={"Authorization": f"Bearer {admin['token']}"})
    assert r_admin_dl.status_code == 403
    assert "not ACTIVE" in r_admin_dl.text


def test_adv_2_4_role_spoofing_employer_and_gov_rejected_with_403():
    """Scenarios 2.4a & 2.4b: Role spoofing by Employer and Government rejected with 403."""
    employer = create_test_user_with_role("EMPLOYER", "sw2_emp")
    gov = create_test_user_with_role("GOVERNMENT", "sw2_gov")

    r_emp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {employer['token']}"})
    assert r_emp_qr.status_code == 403

    r_gov_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {gov['token']}"})
    assert r_gov_qr.status_code == 403


def test_adv_2_5_query_param_tampering_rejected_with_403():
    """Scenario 2.5: Query parameter tampering attempts all strictly rejected with 403."""
    w_suspended = create_test_worker("sw2_susp_tamper", status="SUSPENDED", is_active=False)
    tamper_params = [
        {"status": "ACTIVE"},
        {"aadhaar_status": "ACTIVE"},
        {"force": "true"},
        {"bypass": "1"},
        {"is_active": "true"},
        {"admin_override": "true"},
    ]
    for p in tamper_params:
        r = client.get("/api/v1/worker/presentation/qr-card/me", params=p, headers={"Authorization": f"Bearer {w_suspended['token']}"})
        assert r.status_code == 403

        r_dl = client.get("/api/v1/worker/presentation/download-qr/me", params=p, headers={"Authorization": f"Bearer {w_suspended['token']}"})
        assert r_dl.status_code == 403


def test_adv_2_6_direct_download_without_prior_view_blocked_with_403():
    """Scenario 2.6: Direct download endpoint call while SUSPENDED rejected with 403."""
    w_suspended = create_test_worker("sw2_susp_direct", status="SUSPENDED", is_active=False)
    r_direct_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w_suspended['token']}"})
    assert r_direct_dl.status_code == 403


def test_adv_2_7_header_tampering_blocked_with_403():
    """Scenario 2.7: Direct download with cache, proxy, and key header tampering rejected with 403."""
    w_suspended = create_test_worker("sw2_susp_hdr", status="SUSPENDED", is_active=False)
    headers_tamper = {
        "Authorization": f"Bearer {w_suspended['token']}",
        "Accept": "image/png, */*",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "If-None-Match": "*",
        "X-Forwarded-For": "127.0.0.1",
        "X-PassKhadam-Service-Key": "mock_secret"
    }
    r_hdr_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers=headers_tamper)
    assert r_hdr_dl.status_code == 403


def test_adv_2_8_unauthenticated_qr_access_rejected_with_401():
    """Scenario 2.8: Unauthenticated access to QR endpoints rejected with 401."""
    r_unauth_qr = client.get("/api/v1/worker/presentation/qr-card/me")
    r_unauth_dl = client.get("/api/v1/worker/presentation/download-qr/me")
    assert r_unauth_qr.status_code == 401
    assert r_unauth_dl.status_code == 401


# =============================================================================
# SUITE 3: REACTIVATION RECOVERY & IDENTITY INTEGRITY (6 scenarios)
# =============================================================================

def test_adv_3_1_reactivation_clean_recovery_zero_duplicate_dids_and_profiles():
    """Scenarios 3.1a - 3.1g: Clean reactivation recovery with 0 duplicate profiles/DIDs and intact hashes."""
    w = create_test_worker("sw3_reactiv", status="ACTIVE", is_active=True)
    orig_did = w["did"]
    assert orig_did is not None

    db = SessionLocal()
    orig_prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).first()
    orig_cid = orig_prof.ipfs_cid
    orig_cred_hash = orig_prof.credential_hash
    db.close()

    # 3.1a: Initial ACTIVE worker obtains QR presentation card
    r_initial_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w['token']}"})
    assert r_initial_qr.status_code == 200

    # 3.1b: Deactivate worker to SUSPENDED -> 403 on both endpoints
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "SUSPENDED"
    rec.is_active = False
    db.commit()
    db.close()

    r_susp_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w['token']}"})
    r_susp_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w['token']}"})
    assert r_susp_qr.status_code == 403
    assert r_susp_dl.status_code == 403

    # 3.1c: Reactivate worker to ACTIVE -> immediate recovery (200)
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
    rec.status = "ACTIVE"
    rec.is_active = True
    db.commit()
    db.close()

    r_recov_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w['token']}"})
    r_recov_dl = client.get("/api/v1/worker/presentation/download-qr/me", headers={"Authorization": f"Bearer {w['token']}"})
    assert r_recov_qr.status_code == 200
    assert r_recov_dl.status_code == 200

    # 3.1d: Exact original DID preserved
    assert r_recov_qr.json().get("worker_did") == orig_did

    # 3.1e & 3.1f & 3.1g: Database Invariants
    db = SessionLocal()
    matching_profiles = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w["user_id"]).all()
    matching_dids = db.query(DBWorkerProfile).filter(DBWorkerProfile.did == orig_did).all()
    cur_prof = matching_profiles[0]
    db.close()

    assert len(matching_profiles) == 1
    assert len(matching_dids) == 1
    assert cur_prof.credential_hash == orig_cred_hash
    assert cur_prof.ipfs_cid == orig_cid


def test_adv_3_2_rapid_cycling_stress_test_6_transitions():
    """Scenario 3.2: Rapid cycling across 6 state transitions preserves strict gating and clean recovery."""
    w = create_test_worker("sw3_cycling", status="ACTIVE", is_active=True)
    states = ["SUSPENDED", "ACTIVE", "INACTIVE", "ACTIVE", "SUSPENDED", "ACTIVE"]

    for target_state in states:
        db = SessionLocal()
        r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w["record_id"]).first()
        r.status = target_state
        r.is_active = (target_state == "ACTIVE")
        db.commit()
        db.close()

        res_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w['token']}"})
        expected_code = 200 if target_state == "ACTIVE" else 403
        assert res_qr.status_code == expected_code


# =============================================================================
# SUITE 4: DEMOGRAPHIC & UNLINKED EDGE CASE STRESS TESTS (2 scenarios)
# =============================================================================

def test_adv_4_1_unlinked_anchored_profile_strictly_rejected_403():
    """Scenario 4.1: Unlinked worker (aadhaar_record_id=None, anchored=True, did_state='ACTIVE') strictly rejected with 403."""
    w_unlinked = create_test_worker("sw4_unlink", status="ACTIVE", is_active=True, anchored=True, verified=True, link_record=False)

    db = SessionLocal()
    p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == w_unlinked["user_id"]).first()
    p.aadhaar_record_id = None
    p.aadhaar_request_id = None
    db.commit()
    db.close()

    res_qr = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {w_unlinked['token']}"})
    assert res_qr.status_code == 403
    assert "not ACTIVE" in res_qr.json().get("detail", "") or "UNVERIFIED" in res_qr.json().get("detail", "")


def test_adv_4_2_reverification_of_suspended_record_rejected_with_400():
    """Scenario 4.2: Re-verification of SUSPENDED record rejected with 400."""
    w_reverif = create_test_worker("sw4_reverif", status="ACTIVE", is_active=True)

    # Suspend citizen record in DBAadhaarRecord
    db = SessionLocal()
    r = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == w_reverif["record_id"]).first()
    r.status = "SUSPENDED"
    r.is_active = False
    db.commit()
    db.close()

    # Worker calls verify-aadhaar/me again with the same number and name
    reverif_payload = {
        "aadhaar_number": w_reverif["raw_num"],
        "full_name": f"Worker sw4_reverif"
    }
    r_reverif = client.post("/api/v1/worker/verify-aadhaar/me", json=reverif_payload, headers={"Authorization": f"Bearer {w_reverif['token']}"})
    assert r_reverif.status_code == 400
    assert "Aadhaar record is suspended" in r_reverif.json().get("detail", "")
