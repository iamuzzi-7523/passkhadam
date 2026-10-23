"""
backend/tests/test_challenger_m2_2_empirical.py
Milestone 2 Empirical Stress & Adversarial Challenge Suite (challenger_m2_2)

Comprehensive Empirical Verification of:
1. SQLite Status Persistence & Rehydration Stress across restarts and cache evictions
2. Permanence Invariant: Discontinued stints retained permanently in history, omitted from active workforce
3. IDOR & Security Stress: Horizontal worker isolation, parameterized role access, and client DID injection rejection
4. Lifecycle State Machine Edge Cases: Lazy loading, invalid status rejection, SUSPENDED -> DISCONTINUED transitions
"""

import time
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployment, DBEmployerOrganization
from app.services.blockchain_service import blockchain_service
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)

DEFAULT_EMPLOYER_ADDR = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"


def create_test_worker(category="Electrician", skills=None):
    """Helper to register a fresh worker with unique credentials and valid anchored DID."""
    uid = uuid.uuid4().hex[:8]
    email = f"emp_challenger_worker_{uid}@passkhadam.org"
    skills = skills or ["Wiring", "Solar Installation"]
    payload = {
        "full_name": f"Challenger Worker {uid}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": "Password123!",
        "role": "WORKER",
        "worker_category": category,
        "skills": skills,
        "origin_state": "Bihar",
        "current_state": "Goa",
        "is_email_verified": True,
        "is_phone_verified": True
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    token = data["access_token"]
    user_id = data["user"]["id"]

    db = SessionLocal()
    try:
        prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
        if prof and not prof.did:
            prof.did = f"did:passkhadam:worker:{uid}"
            prof.is_credential_anchored = True
            db.commit()
            db.refresh(prof)
            worker_did = prof.did
        else:
            worker_did = prof.did if prof else f"did:passkhadam:worker:{uid}"
    finally:
        db.close()

    return {
        "token": token,
        "user_id": user_id,
        "email": email,
        "worker_did": worker_did,
        "headers": {"Authorization": f"Bearer {token}"}
    }


def create_unapproved_employer():
    """Helper to register an unapproved employer organization in PENDING_REVIEW status."""
    uid = uuid.uuid4().hex[:8]
    email = f"pending_emp_{uid}@unapproved.org"
    res = client.post("/api/v1/employer/register", json={
        "company_name": f"Pending Corp {uid}",
        "registration_number": f"CIN-{uid}",
        "email": email,
        "phone": "+91 91234 56789",
        "password": "Password123!",
        "categories_requested": ["Mason"]
    })
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        emp_user = db.query(DBUser).filter(DBUser.email == email).first()
        assert emp_user is not None
        assert emp_user.status == "PENDING_REVIEW"
        user_id = emp_user.id
    finally:
        db.close()

    # Generate valid test JWT token for this unapproved employer user
    token = create_test_firebase_jwt(str(user_id), email)
    return {
        "user_id": user_id,
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


# ============================================================================
# 1. SQLITE STATUS PERSISTENCE & REHYDRATION STRESS
# ============================================================================

def test_sqlite_persistence_completed_and_sync_rehydration():
    """
    Empirical Test:
    Create employment -> update to COMPLETED -> inspect SQLite DBEmployment ->
    call sync_from_database() -> assert status remains COMPLETED.
    """
    worker = create_test_worker(category="Electrician")
    blockchain_service.authorize_category(DEFAULT_EMPLOYER_ADDR, "Electrician")

    # 1. Create employment stint in ACTIVE status
    emp = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Electrician",
        job_role="Control Panel Wiring",
        location="Site Alpha Goa"
    )
    stint_id = emp["id"]

    # Verify initial SQLite state
    db = SessionLocal()
    try:
        init_db = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert init_db is not None
        assert init_db.status == "ACTIVE"
        assert init_db.end_date == 0
    finally:
        db.close()

    # 2. Update status to COMPLETED with reason
    reason_text = "Phase 1 electrical installation verified and completed"
    blockchain_service.update_employment_status(
        emp_id=stint_id,
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="COMPLETED",
        reason=reason_text
    )

    # 3. Direct SQLite DB check: status must be COMPLETED, end_date > 0
    db = SessionLocal()
    try:
        rec_completed = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec_completed is not None
        assert rec_completed.status == "COMPLETED"
        assert rec_completed.status_reason == reason_text
        assert rec_completed.end_date > 0
        saved_end_date = rec_completed.end_date
    finally:
        db.close()

    # 4. Trigger rehydration via sync_from_database() (simulates service restart)
    blockchain_service.sync_from_database()

    # 5. Assert memory reflects SQLite DB and did NOT revert to ACTIVE
    assert stint_id in blockchain_service.employments
    mem_stint = blockchain_service.employments[stint_id]
    assert mem_stint["status"] == "COMPLETED"
    assert mem_stint["status_reason"] == reason_text
    assert mem_stint["end_date"] == saved_end_date

    # 6. Query worker history endpoint: status remains COMPLETED
    res = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert res.status_code == 200
    h_data = res.json()
    assert h_data["active_count"] == 0
    assert h_data["historical_count"] >= 1
    matching = [e for e in h_data["employments"] if e["id"] == stint_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "COMPLETED"
    assert matching[0]["end_date"] == saved_end_date


def test_sqlite_persistence_discontinued_and_sync_rehydration():
    """
    Empirical Test:
    Create employment -> update to DISCONTINUED -> inspect SQLite DBEmployment ->
    assert status is DISCONTINUED and end_date > 0 -> call sync_from_database() ->
    assert status remains DISCONTINUED.
    """
    worker = create_test_worker(category="Welder")
    blockchain_service.authorize_category(DEFAULT_EMPLOYER_ADDR, "Welder")

    # 1. Create employment stint in ACTIVE status
    emp = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Welder",
        job_role="Pipeline Argon Arc Welder",
        location="Offshore Dockyard Vasco"
    )
    stint_id = emp["id"]

    # 2. Update status to DISCONTINUED
    disc_reason = "Welding scope discontinued by municipal regulatory mandate"
    blockchain_service.update_employment_status(
        emp_id=stint_id,
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="DISCONTINUED",
        reason=disc_reason
    )

    # 3. Direct inspection of SQLite database
    db = SessionLocal()
    try:
        rec_disc = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec_disc is not None
        assert rec_disc.status == "DISCONTINUED"
        assert rec_disc.status_reason == disc_reason
        assert rec_disc.end_date > 0
        persisted_end_date = rec_disc.end_date
    finally:
        db.close()

    # 4. Invoke sync_from_database()
    blockchain_service.sync_from_database()

    # 5. Assert status remains DISCONTINUED and end_date preserved
    assert stint_id in blockchain_service.employments
    mem_stint = blockchain_service.employments[stint_id]
    assert mem_stint["status"] == "DISCONTINUED"
    assert mem_stint["status_reason"] == disc_reason
    assert mem_stint["end_date"] == persisted_end_date

    # 6. Verify via API endpoint
    res = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert res.status_code == 200
    h_data = res.json()
    assert h_data["active_count"] == 0
    assert h_data["historical_count"] >= 1
    matching = [e for e in h_data["employments"] if e["id"] == stint_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "DISCONTINUED"
    assert matching[0]["end_date"] == persisted_end_date


# ============================================================================
# 2. PERMANENCE INVARIANT & WORKFORCE ROSTER ISOLATION
# ============================================================================

def test_permanence_invariant_multistint_isolation_and_workforce():
    """
    Empirical Test:
    - Verify blockchain_service.get_worker_employments and GET /api/v1/worker/employment-history/me
      return discontinued stints permanently.
    - Verify blockchain_service.get_active_workforce omits discontinued stints.
    - Test across a multi-stint lifecycle: Stint 1 ACTIVE, Stint 2 COMPLETED, Stint 3 DISCONTINUED.
    """
    worker = create_test_worker(category="MultiCraft")
    blockchain_service.authorize_category(DEFAULT_EMPLOYER_ADDR, "MultiCraft")

    # Stint 1: ACTIVE
    emp1 = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="MultiCraft",
        job_role="Active Lead Craftsman",
        location="Site 101"
    )

    # Stint 2: COMPLETED
    emp2 = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="MultiCraft",
        job_role="Prior Site Specialist",
        location="Site 102"
    )
    blockchain_service.update_employment_status(
        emp_id=emp2["id"],
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="COMPLETED",
        reason="Prior site assignment concluded"
    )

    # Stint 3: DISCONTINUED
    emp3 = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="MultiCraft",
        job_role="Discontinued Auxiliary Role",
        location="Site 103"
    )
    blockchain_service.update_employment_status(
        emp_id=emp3["id"],
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="DISCONTINUED",
        reason="Operational scope discontinued"
    )

    # 1. Invariant A: blockchain_service.get_worker_employments returns all 3 stints
    all_worker_stints = blockchain_service.get_worker_employments(worker["worker_did"])
    all_stint_ids = {s["id"] for s in all_worker_stints}
    assert emp1["id"] in all_stint_ids
    assert emp2["id"] in all_stint_ids
    assert emp3["id"] in all_stint_ids

    disc_stint = next(s for s in all_worker_stints if s["id"] == emp3["id"])
    assert disc_stint["status"] == "DISCONTINUED"
    assert disc_stint["end_date"] > 0

    # 2. Invariant B: blockchain_service.get_active_workforce omits discontinued and completed
    active_roster = blockchain_service.get_active_workforce(DEFAULT_EMPLOYER_ADDR)
    roster_ids = {s["id"] for s in active_roster}
    assert emp1["id"] in roster_ids, "Active stint missing from active workforce roster!"
    assert emp2["id"] not in roster_ids, "Completed stint leaked into active workforce roster!"
    assert emp3["id"] not in roster_ids, "Discontinued stint leaked into active workforce roster!"

    # 3. Invariant C: GET /api/v1/worker/employment-history/me returns discontinued stint permanently
    res = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert res.status_code == 200
    h_data = res.json()
    assert h_data["active_count"] == 1
    assert h_data["historical_count"] == 2
    assert h_data["total_count"] == 3

    active_ids = {e["id"] for e in h_data["active_employments"]}
    historical_ids = {e["id"] for e in h_data["historical_employments"]}
    assert emp1["id"] in active_ids
    assert emp2["id"] in historical_ids
    assert emp3["id"] in historical_ids

    # 4. Stress wipe: clear memory, verify permanence from SQLite
    blockchain_service.employments.clear()
    res_post_wipe = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert res_post_wipe.status_code == 200
    w_data = res_post_wipe.json()
    assert w_data["active_count"] == 1
    assert w_data["historical_count"] == 2
    post_historical_ids = {e["id"] for e in w_data["historical_employments"]}
    assert emp3["id"] in post_historical_ids, "Discontinued stint vanished after memory wipe!"


# ============================================================================
# 3. IDOR & SECURITY STRESS
# ============================================================================

def test_idor_horizontal_worker_isolation():
    """
    Empirical Test:
    - Worker A attempts to query /employment-history/{worker_b_id} -> HTTP 403 Forbidden.
    - Worker A queries /employment-history/999999 (non-existent) -> HTTP 403 Forbidden (RBAC first).
    - Worker A queries /employment-history/{worker_a_id} -> HTTP 200 OK.
    - Unauthenticated request to /employment-history/{worker_b_id} -> HTTP 401 Unauthorized.
    - Unauthenticated request to /employment-history/me -> HTTP 401 Unauthorized.
    """
    worker_a = create_test_worker(category="Electrician")
    worker_b = create_test_worker(category="Carpenter")

    # 1. Worker A attempts to query Worker B's history -> 403 Forbidden
    res_idor = client.get(
        f"/api/v1/worker/employment-history/{worker_b['user_id']}",
        headers=worker_a["headers"]
    )
    assert res_idor.status_code == 403
    assert "Workers can only view their own" in res_idor.json()["detail"]

    # 2. Worker A attempts to query non-existent user_id -> 403 Forbidden (zero IDOR enumeration)
    res_nonexistent = client.get(
        "/api/v1/worker/employment-history/999999",
        headers=worker_a["headers"]
    )
    assert res_nonexistent.status_code == 403
    assert "Workers can only view their own" in res_nonexistent.json()["detail"]

    # 3. Worker A queries their own history via parameterized endpoint -> 200 OK
    res_self = client.get(
        f"/api/v1/worker/employment-history/{worker_a['user_id']}",
        headers=worker_a["headers"]
    )
    assert res_self.status_code == 200
    assert res_self.json()["worker_did"] == worker_a["worker_did"]

    # 4. Unauthenticated queries -> 401 Unauthorized
    res_unauth_param = client.get(f"/api/v1/worker/employment-history/{worker_b['user_id']}")
    assert res_unauth_param.status_code == 401

    res_unauth_me = client.get("/api/v1/worker/employment-history/me")
    assert res_unauth_me.status_code == 401


def test_cross_role_authorized_access_and_unapproved_rejection():
    """
    Empirical Test:
    - Employer (approved organization) queries /employment-history/{worker_b_id} -> HTTP 200 OK.
    - Admin queries /employment-history/{worker_b_id} -> HTTP 200 OK.
    - Government Welfare Officer queries /employment-history/{worker_b_id} -> HTTP 200 OK.
    - Unapproved / Pending Employer queries /employment-history/{worker_b_id} -> HTTP 403 Forbidden.
    """
    worker_target = create_test_worker(category="Plumber")

    # 1. Approved Employer queries history -> 200 OK
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200
    emp_token = emp_login.json()["access_token"]
    res_emp = client.get(
        f"/api/v1/worker/employment-history/{worker_target['user_id']}",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert res_emp.status_code == 200
    assert res_emp.json()["worker_did"] == worker_target["worker_did"]

    # 2. Admin queries history -> 200 OK
    admin_login = client.post("/api/v1/auth/demo-login/ADMIN")
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    res_admin = client.get(
        f"/api/v1/worker/employment-history/{worker_target['user_id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["worker_did"] == worker_target["worker_did"]

    # 3. Government Officer queries history -> 200 OK
    gov_login = client.post("/api/v1/auth/demo-login/GOVERNMENT")
    assert gov_login.status_code == 200
    gov_token = gov_login.json()["access_token"]
    res_gov = client.get(
        f"/api/v1/worker/employment-history/{worker_target['user_id']}",
        headers={"Authorization": f"Bearer {gov_token}"}
    )
    assert res_gov.status_code == 200
    assert res_gov.json()["worker_did"] == worker_target["worker_did"]

    # 4. Unapproved / Pending Employer queries history -> 403 Forbidden
    unapproved_emp = create_unapproved_employer()
    res_unapproved = client.get(
        f"/api/v1/worker/employment-history/{worker_target['user_id']}",
        headers=unapproved_emp["headers"]
    )
    assert res_unapproved.status_code == 403
    assert "approved" in res_unapproved.json()["detail"].lower()


def test_client_did_injection_stress_rejection():
    """
    Empirical Test:
    Client sends payload with `did` or `worker_did` to /skills/me or /profile/me ->
    verify HTTP 400 Bad Request rejection and assert database DID is untouched.
    """
    worker = create_test_worker(category="Mason", skills=["Bricklaying"])
    genuine_did = worker["worker_did"]

    # 1. Attack on /skills/me with 'did'
    res_skills_did = client.put(
        "/api/v1/worker/skills/me",
        headers=worker["headers"],
        json={"did": "did:attacker:hijacked_001", "skills": ["Wiring"]}
    )
    assert res_skills_did.status_code == 400
    assert "Client-supplied DID is strictly forbidden" in res_skills_did.json()["detail"]

    # 2. Attack on /skills/me with 'worker_did'
    res_skills_wdid = client.put(
        "/api/v1/worker/skills/me",
        headers=worker["headers"],
        json={"worker_did": "did:attacker:hijacked_002", "skills": ["Wiring"]}
    )
    assert res_skills_wdid.status_code == 400
    assert "Client-supplied DID is strictly forbidden" in res_skills_wdid.json()["detail"]

    # 3. Attack on /profile/me with 'did'
    res_prof_did = client.put(
        "/api/v1/worker/profile/me",
        headers=worker["headers"],
        json={"did": "did:attacker:hijacked_003", "current_state": "Delhi"}
    )
    assert res_prof_did.status_code == 400
    assert "Client-supplied DID is strictly forbidden" in res_prof_did.json()["detail"]

    # 4. Attack on /profile/me with 'worker_did'
    res_prof_wdid = client.put(
        "/api/v1/worker/profile/me",
        headers=worker["headers"],
        json={"worker_did": "did:attacker:hijacked_004", "current_state": "Delhi"}
    )
    assert res_prof_wdid.status_code == 400
    assert "Client-supplied DID is strictly forbidden" in res_prof_wdid.json()["detail"]

    # 5. Verify database integrity: worker's genuine DID remains intact
    db = SessionLocal()
    try:
        prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == worker["user_id"]).first()
        assert prof is not None
        assert prof.did == genuine_did, f"Worker DID was corrupted to {prof.did}!"
    finally:
        db.close()


# ============================================================================
# 4. LIFECYCLE STATE MACHINE EDGE CASES & LAZY LOADING
# ============================================================================

def test_lazy_loading_from_sqlite_when_not_in_memory():
    """
    Empirical Test:
    Verify that update_employment_status lazy-loads from SQLite DBEmployment
    when the stint is evicted from in-memory cache.
    """
    worker = create_test_worker(category="Painter")
    blockchain_service.authorize_category(DEFAULT_EMPLOYER_ADDR, "Painter")

    # 1. Create stint
    emp = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Painter",
        job_role="Industrial Spray Painter",
        location="Dry Dock Vasco"
    )
    stint_id = emp["id"]

    # 2. Evict stint from in-memory cache
    if stint_id in blockchain_service.employments:
        del blockchain_service.employments[stint_id]
    assert stint_id not in blockchain_service.employments

    # 3. Call update_employment_status -> must lazy-load from SQLite, update, and persist
    blockchain_service.update_employment_status(
        emp_id=stint_id,
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="DISCONTINUED",
        reason="Lazy load update verification"
    )

    # 4. Verify in-memory state restored
    assert stint_id in blockchain_service.employments
    assert blockchain_service.employments[stint_id]["status"] == "DISCONTINUED"

    # 5. Verify SQLite state committed
    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec is not None
        assert rec.status == "DISCONTINUED"
        assert rec.end_date > 0
    finally:
        db.close()


def test_invalid_status_rejection_preserves_sqlite_integrity():
    """
    Empirical Test:
    Attempting to update to an unapproved status enum raises ValueError and does
    not corrupt SQLite or memory.
    """
    worker = create_test_worker(category="Painter")
    emp = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Painter",
        job_role="Surface Finisher",
        location="Panaji"
    )
    stint_id = emp["id"]

    # Attempt update with illegal status
    with pytest.raises(ValueError) as excinfo:
        blockchain_service.update_employment_status(
            emp_id=stint_id,
            caller_address=DEFAULT_EMPLOYER_ADDR,
            new_status="PURGED",
            reason="Illegal attempt"
        )
    assert "Invalid status" in str(excinfo.value)

    # Verify SQLite DBEmployment record remains ACTIVE with end_date == 0
    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec.status == "ACTIVE"
        assert rec.end_date == 0
    finally:
        db.close()


def test_lifecycle_transition_active_to_suspended_to_discontinued():
    """
    Empirical Test:
    Verify status transition chain: ACTIVE -> SUSPENDED -> DISCONTINUED.
    - SUSPENDED retains end_date == 0.
    - DISCONTINUED triggers end_date > 0.
    - Both transitions persist in SQLite and survive sync_from_database().
    """
    worker = create_test_worker(category="Electrician")
    emp = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Electrician",
        job_role="High Voltage Lineman",
        location="Substation South Goa"
    )
    stint_id = emp["id"]

    # Transition 1: SUSPENDED
    blockchain_service.update_employment_status(
        emp_id=stint_id,
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="SUSPENDED",
        reason="Temporary safety audit suspension"
    )
    db = SessionLocal()
    try:
        rec_susp = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec_susp.status == "SUSPENDED"
        assert rec_susp.end_date == 0
    finally:
        db.close()

    # Transition 2: DISCONTINUED
    blockchain_service.update_employment_status(
        emp_id=stint_id,
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="DISCONTINUED",
        reason="Lineman project line discontinued"
    )
    db = SessionLocal()
    try:
        rec_disc = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec_disc.status == "DISCONTINUED"
        assert rec_disc.end_date > 0
    finally:
        db.close()

    # Rehydrate
    blockchain_service.sync_from_database()
    assert blockchain_service.employments[stint_id]["status"] == "DISCONTINUED"
    assert blockchain_service.employments[stint_id]["end_date"] > 0
