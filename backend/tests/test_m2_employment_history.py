"""
backend/tests/test_m2_employment_history.py
Milestone 2 Test Suite: Cross-Role Employment Lifecycle & Historical Ledger Portability (R2)

Covers:
1. Authentication & RBAC on /employment-history/me (401 unauthenticated, 403 non-worker)
2. Empty state and lifecycle partitioning (ACTIVE -> COMPLETED -> active_count / historical_count)
3. Permanence Invariant: DISCONTINUED status acceptance, persistence, and preservation in history
4. Parameterized endpoint RBAC & IDOR prevention (/employment-history/{user_id})
5. Worker Skills & Trade profile updates (/skills/me and /profile/me aliases/normalization)
6. SQLite DBEmployment persistence across server restart / sync_from_database rehydration
"""

import time
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployment, DBEmployerOrganization
from app.services.blockchain_service import blockchain_service

client = TestClient(app)

DEFAULT_EMPLOYER_ADDR = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"


def create_test_worker(category="Electrician", skills=None):
    """Helper to register a fresh worker with unique email."""
    uid = uuid.uuid4().hex[:8]
    email = f"m2_worker_{uid}@passkhadam.org"
    skills = skills or ["Wiring", "Solar Installation"]
    payload = {
        "full_name": f"M2 Worker {uid}",
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

    # Ensure worker has a valid decentralized DID anchored
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


def test_employment_history_me_requires_worker_auth():
    """Verify endpoint is strictly guarded by WORKER role requirement."""
    # 1. Unauthenticated -> 401
    res = client.get("/api/v1/worker/employment-history/me")
    assert res.status_code == 401

    # 2. Employer token -> 403 Forbidden
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200
    emp_token = emp_login.json()["access_token"]
    res_emp = client.get(
        "/api/v1/worker/employment-history/me",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert res_emp.status_code == 403
    assert "Only workers" in res_emp.json()["detail"]

    # 3. Government officer token -> 403 Forbidden
    gov_login = client.post("/api/v1/auth/demo-login/GOVERNMENT")
    assert gov_login.status_code == 200
    gov_token = gov_login.json()["access_token"]
    res_gov = client.get(
        "/api/v1/worker/employment-history/me",
        headers={"Authorization": f"Bearer {gov_token}"}
    )
    assert res_gov.status_code == 403


def test_employment_history_me_lifecycle_and_partitioning():
    """Verify empty state, active state, completion transition, and count partitioning."""
    worker = create_test_worker(category="Electrician")

    # 1. Initial Empty State
    res = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert res.status_code == 200
    data = res.json()
    assert data["worker_did"] == worker["worker_did"]
    assert data["active_count"] == 0
    assert data["historical_count"] == 0
    assert data["employments"] == []

    # 2. Employer creates employment stint
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200
    emp_token = emp_login.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    create_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Industrial Mason",
        "work_location": "Panaji Smart City Project"
    })
    assert create_res.status_code == 200, create_res.text
    emp_id = create_res.json()["employment_record"]["id"]

    # 3. Worker history reflects ACTIVE stint
    hist_res = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert hist_res.status_code == 200
    h_data = hist_res.json()
    assert h_data["active_count"] == 1
    assert h_data["historical_count"] == 0
    assert len(h_data["employments"]) == 1
    stint = h_data["employments"][0]
    assert stint["id"] == emp_id
    assert stint["status"] == "ACTIVE"
    assert stint["job_role"] == "Industrial Mason"

    # 4. Employer transitions stint to COMPLETED
    upd_res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": emp_id,
        "new_status": "COMPLETED",
        "reason": "Project phase 1 successfully completed"
    })
    assert upd_res.status_code == 200, upd_res.text

    # 5. Worker history reflects COMPLETED stint in historical partition
    hist_res2 = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert hist_res2.status_code == 200
    h_data2 = hist_res2.json()
    assert h_data2["active_count"] == 0
    assert h_data2["historical_count"] == 1
    assert len(h_data2["employments"]) == 1
    stint2 = h_data2["employments"][0]
    assert stint2["id"] == emp_id
    assert stint2["status"] == "COMPLETED"
    assert stint2["status_reason"] == "Project phase 1 successfully completed"
    assert stint2["end_date"] > 0


def test_permanence_invariant_discontinued_stints():
    """
    CRITICAL PERMANENCE INVARIANT TEST:
    Verify that DISCONTINUED status is accepted, persisted, and remains permanently visible
    in worker history, while excluded from employer's active workforce roster.
    """
    worker = create_test_worker(category="Welder")

    # Authorize Welder category for employer
    blockchain_service.authorize_category(DEFAULT_EMPLOYER_ADDR, "Welder")

    # 1. Create employment stint
    stint_rec = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Welder",
        job_role="Structural Arc Welder",
        location="Marine Dockyard Goa",
        level="Skilled",
        nature_of_employment="Contract"
    )
    stint_id = stint_rec["id"]

    # 2. Transition status to DISCONTINUED
    blockchain_service.update_employment_status(
        emp_id=stint_id,
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="DISCONTINUED",
        reason="Trade scope discontinued by platform governance"
    )

    # 3. Direct DB check in SQLite
    db = SessionLocal()
    try:
        db_rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert db_rec is not None
        assert db_rec.status == "DISCONTINUED"
        assert db_rec.status_reason == "Trade scope discontinued by platform governance"
        assert db_rec.end_date > 0
    finally:
        db.close()

    # 4. Check worker employment history endpoint
    res = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert res.status_code == 200
    data = res.json()
    assert data["active_count"] == 0
    assert data["historical_count"] >= 1
    matching = [e for e in data["employments"] if e["id"] == stint_id]
    assert len(matching) == 1, "Discontinued stint vanished from worker history!"
    assert matching[0]["status"] == "DISCONTINUED"
    assert matching[0]["job_role"] == "Structural Arc Welder"

    # 5. Active workforce roster must NOT contain this stint
    active_roster = blockchain_service.get_active_workforce(DEFAULT_EMPLOYER_ADDR)
    assert not any(e["id"] == stint_id for e in active_roster)


def test_parameterized_employment_history_rbac_and_idor():
    """Verify horizontal IDOR prevention and authorized multi-role access."""
    worker1 = create_test_worker(category="Painter")
    worker2 = create_test_worker(category="Carpenter")

    # 1. Worker 1 tries to access Worker 2's history -> 403 Forbidden
    res_idor = client.get(
        f"/api/v1/worker/employment-history/{worker2['user_id']}",
        headers=worker1["headers"]
    )
    assert res_idor.status_code == 403
    assert "Workers can only view their own" in res_idor.json()["detail"]

    # 2. Worker 1 accesses Worker 1's own history -> 200 OK
    res_self = client.get(
        f"/api/v1/worker/employment-history/{worker1['user_id']}",
        headers=worker1["headers"]
    )
    assert res_self.status_code == 200

    # 3. Admin accesses Worker 2's history -> 200 OK
    admin_login = client.post("/api/v1/auth/demo-login/ADMIN")
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    res_admin = client.get(
        f"/api/v1/worker/employment-history/{worker2['user_id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["worker_did"] == worker2["worker_did"]

    # 4. Approved Employer accesses Worker 2's history -> 200 OK
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200
    emp_token = emp_login.json()["access_token"]
    res_emp = client.get(
        f"/api/v1/worker/employment-history/{worker2['user_id']}",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert res_emp.status_code == 200
    assert res_emp.json()["worker_did"] == worker2["worker_did"]

    # 5. Active Government Officer accesses Worker 2's history -> 200 OK
    gov_login = client.post("/api/v1/auth/demo-login/GOVERNMENT")
    assert gov_login.status_code == 200
    gov_token = gov_login.json()["access_token"]
    res_gov = client.get(
        f"/api/v1/worker/employment-history/{worker2['user_id']}",
        headers={"Authorization": f"Bearer {gov_token}"}
    )
    assert res_gov.status_code == 200

    # 6. Unauthenticated caller -> 401 Unauthorized
    res_unauth = client.get(f"/api/v1/worker/employment-history/{worker2['user_id']}")
    assert res_unauth.status_code == 401


def test_worker_skills_and_trade_updates():
    """Verify dedicated /skills/me and profile trade normalization."""
    worker = create_test_worker(category="Mason", skills=["Bricklaying"])

    # 1. Update skills via PUT /api/v1/worker/skills/me
    res = client.put(
        "/api/v1/worker/skills/me",
        headers=worker["headers"],
        json={
            "worker_category": "Plumber",
            "skills": ["Pipe Fitting", "Drainage Systems", "Leak Detection"]
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["worker_category"] == "Plumber"
    assert "Pipe Fitting" in data["skills"]
    assert len(data["skills"]) == 3

    # 2. Update trade with aliases and comma-separated string skills
    res2 = client.put(
        "/api/v1/worker/skills/me",
        headers=worker["headers"],
        json={
            "trade": "Heavy Machinery Operator",
            "skills": "Excavator Operation, Backhoe Loader, Safety Rigging"
        }
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["worker_category"] == "Heavy Machinery Operator"
    assert "Excavator Operation" in data2["skills"]
    assert len(data2["skills"]) == 3

    # 3. Security check: Client-supplied DID is strictly forbidden
    res_bad = client.put(
        "/api/v1/worker/skills/me",
        headers=worker["headers"],
        json={
            "worker_did": "did:attacker:fake",
            "skills": ["Hacking"]
        }
    )
    assert res_bad.status_code == 400
    assert "Client-supplied DID is strictly forbidden" in res_bad.json()["detail"]

    # 4. Update profile via PUT /api/v1/worker/profile/me with profession alias
    res_prof = client.put(
        "/api/v1/worker/profile/me",
        headers=worker["headers"],
        json={
            "profession": "Master Scaffolder",
            "skills": ["Tubular Scaffolding", "Suspended Platform Setup"]
        }
    )
    assert res_prof.status_code == 200, res_prof.text
    prof_data = res_prof.json()
    assert prof_data["profile"]["worker_category"] == "Master Scaffolder"
    assert "Tubular Scaffolding" in prof_data["profile"]["skills"]


def test_sqlite_persistence_across_service_restart():
    """
    CRITICAL RESTARTS & PERSISTENCE TEST:
    Verify that status updates commit to SQLite DBEmployment and survive sync_from_database().
    """
    worker = create_test_worker(category="Electrician")

    # 1. Create two employment stints
    emp1 = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Electrician",
        job_role="Site Electrician",
        location="Site A"
    )
    emp2 = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Electrician",
        job_role="Switchgear Specialist",
        location="Site B"
    )

    # 2. Update emp1 to COMPLETED and emp2 to DISCONTINUED
    blockchain_service.update_employment_status(
        emp_id=emp1["id"],
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="COMPLETED",
        reason="Finished stint"
    )
    blockchain_service.update_employment_status(
        emp_id=emp2["id"],
        caller_address=DEFAULT_EMPLOYER_ADDR,
        new_status="DISCONTINUED",
        reason="Scope concluded"
    )

    # 3. Inspect direct SQLite database
    db = SessionLocal()
    try:
        rec1 = db.query(DBEmployment).filter(DBEmployment.id == emp1["id"]).first()
        assert rec1.status == "COMPLETED"
        assert rec1.end_date > 0

        rec2 = db.query(DBEmployment).filter(DBEmployment.id == emp2["id"]).first()
        assert rec2.status == "DISCONTINUED"
        assert rec2.end_date > 0
    finally:
        db.close()

    # 4. Simulate server restart via sync_from_database()
    blockchain_service.sync_from_database()

    # 5. Assert memory reflects SQLite DB and did NOT revert to ACTIVE
    assert blockchain_service.employments[emp1["id"]]["status"] == "COMPLETED"
    assert blockchain_service.employments[emp2["id"]]["status"] == "DISCONTINUED"
    assert blockchain_service.employments[emp1["id"]]["end_date"] > 0
    assert blockchain_service.employments[emp2["id"]]["end_date"] > 0

    # 6. Worker history API returns both historical stints
    res = client.get("/api/v1/worker/employment-history/me", headers=worker["headers"])
    assert res.status_code == 200
    h_data = res.json()
    assert h_data["active_count"] == 0
    assert h_data["historical_count"] >= 2
    matching1 = [e for e in h_data["employments"] if e["id"] == emp1["id"]]
    matching2 = [e for e in h_data["employments"] if e["id"] == emp2["id"]]
    assert len(matching1) == 1 and matching1[0]["status"] == "COMPLETED"
    assert len(matching2) == 1 and matching2[0]["status"] == "DISCONTINUED"
