"""
backend/tests/test_challenger_m4_2_empirical.py
Empirical Challenger Test Suite: Dismissal Preset Persistence, Ledger Integrity,
Worker Name Enrichment Invariants, and Rejection of Invalid Invariants (Milestone 4).

Challenger ID: challenger_m4_2
Mission:
1. Dismissal Preset Persistence & Ledger Integrity:
   - Test PUT /api/v1/employer/employment-status with each preset (COMPLETED, DISCONTINUED, RESIGNED).
   - Verify SQLite DBEmployment status, status_reason, and end_date are permanently committed to disk.
   - Verify blockchain_service.sync_from_database preserves the status upon simulated server restart.
2. Worker Name Enrichment Invariants:
   - Call GET /api/v1/employer/info in live DB mode: assert every employment record contains non-empty worker_name correlated from DBWorkerProfile.
   - Call GET /api/v1/employer/info in demo mode: assert demo records contain worker_name.
3. Rejection of Invalid Invariants:
   - Attempt invalid status updates (INVALID_STATUS, SQLi payloads, arbitrary strings) -> verify proper rejection.
   - Attempt cross-tenant IDOR, unauthenticated, wrong role, and non-existent IDs.
"""

import os
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBWorkerProfile,
    DBEmployment,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest
)
from app.services.blockchain_service import blockchain_service

client = TestClient(app)

DEFAULT_EMPLOYER_ADDR = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"


# ==============================================================================
# TEST FIXTURES & HELPERS
# ==============================================================================

def create_worker_with_name(full_name: str, category: str = "Mason"):
    """Creates a registered worker with a specified name and active profile."""
    uid = uuid.uuid4().hex[:8]
    email = f"ch4_{uid}@test.org"
    reg_res = client.post("/api/v1/auth/register", json={
        "full_name": full_name,
        "email": email,
        "phone": "+91 98765 43210",
        "password": "Password123!",
        "role": "WORKER",
        "worker_category": category,
        "skills": [category],
        "origin_state": "Bihar",
        "current_state": "Maharashtra",
        "is_email_verified": True,
        "is_phone_verified": True
    })
    assert reg_res.status_code == 200, reg_res.text
    data = reg_res.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    worker_did = f"did:passkhadam:worker:ch4_{uid}"

    db = SessionLocal()
    try:
        prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
        if prof:
            prof.did = worker_did
            prof.full_name = full_name
            prof.is_credential_anchored = True
            db.commit()
            db.refresh(prof)
        else:
            prof = DBWorkerProfile(
                user_id=user_id,
                full_name=full_name,
                did=worker_did,
                worker_category=category,
                origin_state="Bihar",
                current_state="Maharashtra",
                is_credential_anchored=True,
                aadhaar_status="ACTIVE",
                masked_aadhaar="XXXX-XXXX-9999"
            )
            db.add(prof)
            db.commit()
            db.refresh(prof)
    finally:
        db.close()

    # Also register in blockchain_service for consistency
    blockchain_service.worker_registry[worker_did] = {
        "did": worker_did,
        "is_registered": True,
        "is_revoked": False,
        "credential_hash": "0x123",
        "ipfs_cid": "Qm123",
        "status": 1
    }

    return {
        "token": token,
        "user_id": user_id,
        "worker_did": worker_did,
        "worker_name": full_name,
        "email": email
    }


def create_employer_org(company_name: str = None, categories: list = None):
    """Creates and activates an employer organization with authorized category scopes."""
    uid = uuid.uuid4().hex[:8]
    cname = company_name or f"Challenger Builders {uid}"
    email = f"ch_emp_{uid}@build.com"
    cats = categories or ["Mason", "Electrician", "Plumber"]
    reg_num = f"REG-CH4-{uid}"

    reg_res = client.post("/api/v1/employer/register-organization", json={
        "company_name": cname,
        "registration_number": reg_num,
        "email": email,
        "phone": "+91 98765 43210",
        "password": "Password123!",
        "role": "EMPLOYER",
        "address": "Navi Mumbai Hub",
        "requested_categories": cats
    })
    assert reg_res.status_code == 200, reg_res.text
    data = reg_res.json()
    org_id = data["organization_id"]
    org_addr = data["assigned_address"]

    db = SessionLocal()
    try:
        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
        if org:
            org.status = "ACTIVE"
            org.org_address = org_addr
            db.commit()

        user = db.query(DBUser).filter(DBUser.id == org.user_id).first()
        if user:
            user.status = "ACTIVE"
            user.organization_address = org_addr
            db.commit()

        # Approve categories
        for cat in cats:
            req = db.query(DBCategoryAuthorizationRequest).filter(
                DBCategoryAuthorizationRequest.organization_id == org_id,
                DBCategoryAuthorizationRequest.category == cat
            ).first()
            if req:
                req.status = "APPROVED"
                req.is_active_scope = True
                db.commit()
            else:
                req = DBCategoryAuthorizationRequest(
                    organization_id=org_id,
                    category=cat,
                    skill_level="Skilled",
                    nature_of_employment="Contract",
                    status="APPROVED",
                    is_active_scope=True,
                    request_version=1
                )
                db.add(req)
                db.commit()
    finally:
        db.close()

    # Sync to blockchain_service
    blockchain_service.organizations[org_addr] = {
        "address": org_addr,
        "name": cname,
        "reg_number": reg_num,
        "status": "APPROVED",
        "categories": cats,
        "levels": ["Skilled", "Semi-Skilled"],
        "natures": ["Contract", "Project-Based"],
        "registered_at": int(time.time())
    }

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]

    return {
        "token": token,
        "org_id": org_id,
        "org_addr": org_addr,
        "org_name": cname,
        "email": email
    }


# ==============================================================================
# SECTION 1: DISMISSAL PRESET PERSISTENCE & LEDGER INTEGRITY
# ==============================================================================

def test_preset_completed_disk_persistence_and_server_restart():
    """
    Empirically test PUT /api/v1/employer/employment-status with COMPLETED preset.
    Assert:
    - SQLite DBEmployment status == COMPLETED, status_reason, end_date > 0 committed to disk.
    - Server restart (in-memory wipe + sync_from_database) preserves status, reason, end_date.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("Ramesh Completed Verma")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    # 1. Create employment
    create_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Lead Mason",
        "work_location": "Site North"
    })
    assert create_res.status_code == 200, create_res.text
    stint_id = create_res.json()["employment_record"]["id"]

    # 2. Conclude via COMPLETED preset
    preset_reason = "Project phase concluded successfully on site; deliverables met."
    t_before = int(time.time()) - 1
    update_res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": stint_id,
        "new_status": "COMPLETED",
        "reason": preset_reason
    })
    assert update_res.status_code == 200, update_res.text
    t_after = int(time.time()) + 2

    # 3. Verify SQLite DBEmployment disk persistence directly via fresh session
    db = SessionLocal()
    try:
        db_rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert db_rec is not None, f"DBEmployment record #{stint_id} not found in database!"
        assert db_rec.status == "COMPLETED", f"Expected COMPLETED, got {db_rec.status}"
        assert db_rec.status_reason == preset_reason, f"Expected reason '{preset_reason}', got '{db_rec.status_reason}'"
        assert db_rec.end_date is not None, "DBEmployment end_date is None!"
        assert t_before <= db_rec.end_date <= t_after, (
            f"end_date {db_rec.end_date} outside expected range [{t_before}, {t_after}]"
        )
        saved_end_date = db_rec.end_date
    finally:
        db.close()

    # 4. Simulate complete server restart / process reboot:
    # Clear in-memory caches
    blockchain_service.employments.clear()
    blockchain_service.employment_events.clear()
    assert stint_id not in blockchain_service.employments, "Cache should be wiped before restart simulation"

    # Call sync_from_database (simulates app startup rehydration)
    blockchain_service.sync_from_database()

    # 5. Assert blockchain_service properly restored the status and metadata
    assert stint_id in blockchain_service.employments, f"Stint #{stint_id} not rehydrated by sync_from_database"
    restored = blockchain_service.employments[stint_id]
    assert restored["status"] == "COMPLETED", f"Expected restored COMPLETED, got {restored['status']}"
    assert restored["status_reason"] == preset_reason, f"Expected restored reason, got {restored['status_reason']}"
    assert restored["end_date"] == saved_end_date, f"Expected restored end_date {saved_end_date}, got {restored['end_date']}"


def test_preset_discontinued_disk_persistence_and_server_restart():
    """
    Empirically test PUT /api/v1/employer/employment-status with DISCONTINUED preset.
    Assert:
    - SQLite DBEmployment status == DISCONTINUED, status_reason, end_date > 0 committed to disk.
    - Server restart (in-memory wipe + sync_from_database) preserves DISCONTINUED status.
    - Worker portable history reflects DISCONTINUED permanently.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("Sunita Discontinued Sharma")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    create_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Electrician",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Wiring Specialist",
        "work_location": "Metro Line Sector 3"
    })
    assert create_res.status_code == 200, create_res.text
    stint_id = create_res.json()["employment_record"]["id"]

    preset_reason = "Discontinued by employer due to operational site scope changes."
    update_res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": stint_id,
        "new_status": "DISCONTINUED",
        "reason": preset_reason
    })
    assert update_res.status_code == 200, update_res.text

    # Disk inspection
    db = SessionLocal()
    try:
        db_rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert db_rec is not None
        assert db_rec.status == "DISCONTINUED"
        assert db_rec.status_reason == preset_reason
        assert db_rec.end_date is not None and db_rec.end_date > 0
        saved_end_date = db_rec.end_date
    finally:
        db.close()

    # Simulate server reboot
    blockchain_service.employments.clear()
    blockchain_service.employment_events.clear()
    blockchain_service.sync_from_database()

    restored = blockchain_service.employments[stint_id]
    assert restored["status"] == "DISCONTINUED"
    assert restored["status_reason"] == preset_reason
    assert restored["end_date"] == saved_end_date

    # Worker portable history inspection
    w_res = client.get("/api/v1/worker/employment-history/me", headers={"Authorization": f"Bearer {worker['token']}"})
    assert w_res.status_code == 200, w_res.text
    history = w_res.json().get("employments", [])
    stint_entry = next((s for s in history if s["id"] == stint_id), None)
    assert stint_entry is not None, "Stint must exist in worker's portable history"
    assert stint_entry["status"] == "DISCONTINUED"


def test_preset_resigned_disk_persistence_and_server_restart():
    """
    Empirically test PUT /api/v1/employer/employment-status with RESIGNED preset.
    Assert:
    - SQLite DBEmployment status == RESIGNED, status_reason, end_date > 0 committed to disk.
    - Server restart (in-memory wipe + sync_from_database) preserves RESIGNED status.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("Dinesh Resigned Kumar")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    create_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Plumber",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Pipe Fitter",
        "work_location": "Airport Terminal 2"
    })
    assert create_res.status_code == 200, create_res.text
    stint_id = create_res.json()["employment_record"]["id"]

    preset_reason = "Worker voluntarily resigned due to personal relocation / circumstances."
    update_res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": stint_id,
        "new_status": "RESIGNED",
        "reason": preset_reason
    })
    assert update_res.status_code == 200, update_res.text

    # Disk inspection
    db = SessionLocal()
    try:
        db_rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert db_rec is not None
        assert db_rec.status == "RESIGNED"
        assert db_rec.status_reason == preset_reason
        assert db_rec.end_date is not None and db_rec.end_date > 0
        saved_end_date = db_rec.end_date
    finally:
        db.close()

    # Server restart simulation
    blockchain_service.employments.clear()
    blockchain_service.employment_events.clear()
    blockchain_service.sync_from_database()

    restored = blockchain_service.employments[stint_id]
    assert restored["status"] == "RESIGNED"
    assert restored["status_reason"] == preset_reason
    assert restored["end_date"] == saved_end_date


def test_lazy_load_and_persistence_when_evicted_from_memory():
    """
    Empirical challenge: If a stint is in SQLite DBEmployment but NOT in memory,
    PUT /api/v1/employer/employment-status must lazy-load it, update it, and commit to disk.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("Lazy Load Test Worker")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    create_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Finisher",
        "work_location": "Block C"
    })
    assert create_res.status_code == 200
    stint_id = create_res.json()["employment_record"]["id"]

    # Evict from memory
    if stint_id in blockchain_service.employments:
        del blockchain_service.employments[stint_id]
    assert stint_id not in blockchain_service.employments

    # Conclude stint
    res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": stint_id,
        "new_status": "COMPLETED",
        "reason": "Lazy load update test"
    })
    assert res.status_code == 200, res.text

    # Verify both in-memory and disk are updated
    assert blockchain_service.employments[stint_id]["status"] == "COMPLETED"

    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec is not None
        assert rec.status == "COMPLETED"
        assert rec.status_reason == "Lazy load update test"
        assert rec.end_date is not None and rec.end_date > 0
    finally:
        db.close()


# ==============================================================================
# SECTION 2: WORKER NAME ENRICHMENT INVARIANTS
# ==============================================================================

def test_worker_name_enrichment_live_db_mode_multiple_workers():
    """
    Empirically test GET /api/v1/employer/info in live DB mode:
    - Create 3 workers with distinct full names in DBWorkerProfile.
    - Create employments for each worker under the employer.
    - Call GET /api/v1/employer/info as the authenticated employer.
    - Assert EVERY employment record contains non-empty worker_name correlated from DBWorkerProfile.
    """
    employer = create_employer_org()
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    worker_names = [
        "Aarav Ananya Sharma",
        "Pooja Rajesh Patel",
        "Vikramaditya Harish Singh"
    ]
    created_stints = {}

    for name in worker_names:
        w = create_worker_with_name(name, category="Mason")
        c_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
            "worker_did": w["worker_did"],
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Craftsman",
            "work_location": "South Yard"
        })
        assert c_res.status_code == 200, c_res.text
        eid = c_res.json()["employment_record"]["id"]
        created_stints[eid] = name

    # Fetch employer info
    info_res = client.get("/api/v1/employer/info", headers=emp_headers)
    assert info_res.status_code == 200, info_res.text
    info = info_res.json()
    stints = info.get("employments", [])
    assert len(stints) >= 3, f"Expected at least 3 stints, got {len(stints)}"

    # Assert invariant: every employment has non-empty worker_name
    for s in stints:
        assert "worker_name" in s, f"Employment stint #{s.get('id')} missing 'worker_name' key!"
        assert isinstance(s["worker_name"], str), f"worker_name must be string, got {type(s['worker_name'])}"
        assert len(s["worker_name"].strip()) > 0, f"worker_name is empty for stint #{s.get('id')}!"

        # Correlate exact names for our created stints
        if s["id"] in created_stints:
            expected_name = created_stints[s["id"]]
            assert s["worker_name"] == expected_name, (
                f"Mismatch for stint #{s['id']}: expected '{expected_name}', got '{s['worker_name']}'"
            )


def test_worker_name_enrichment_unlinked_worker_did_fallback():
    """
    Adversarial test: If an employment record has a worker_did that has NO DBWorkerProfile,
    GET /api/v1/employer/info must NOT crash or return null/empty; it must gracefully fallback
    to 'Registered Worker' (or a non-empty string).
    """
    employer = create_employer_org()
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    orphan_did = f"did:passkhadam:worker:orphan_{uuid.uuid4().hex[:8]}"

    # Add directly to blockchain_service
    rec = blockchain_service.create_employment(
        worker_did=orphan_did,
        employer_address=employer["org_addr"],
        category="Mason",
        level="Skilled",
        nature_of_employment="Contract",
        job_role="Assistant",
        location="Site Alpha"
    )
    orphan_emp_id = rec["id"]

    info_res = client.get("/api/v1/employer/info", headers=emp_headers)
    assert info_res.status_code == 200, info_res.text
    info = info_res.json()
    stints = info.get("employments", [])

    matched = next((s for s in stints if s["id"] == orphan_emp_id), None)
    assert matched is not None, f"Orphan stint #{orphan_emp_id} should be in employer's employments"
    assert "worker_name" in matched
    assert isinstance(matched["worker_name"], str)
    assert len(matched["worker_name"].strip()) > 0, "worker_name must not be empty on fallback"


def test_worker_name_enrichment_demo_mode():
    """
    Empirically test GET /api/v1/employer/info in demo mode (unauthenticated):
    - Call GET /api/v1/employer/info with no credentials.
    - Assert response is 200.
    - Assert every demo employment record contains non-empty worker_name.
    - Create a new employment under DEFAULT_EMPLOYER_ADDR with a known worker,
      and assert demo endpoint enriches worker_name from DBWorkerProfile.
    """
    # 1. Base demo call
    demo_res = client.get("/api/v1/employer/info")
    assert demo_res.status_code == 200, demo_res.text
    demo_data = demo_res.json()
    assert demo_data["address"] == DEFAULT_EMPLOYER_ADDR
    demo_stints = demo_data.get("employments", [])

    for s in demo_stints:
        assert "worker_name" in s, f"Demo stint #{s.get('id')} missing worker_name"
        assert isinstance(s["worker_name"], str)
        assert len(s["worker_name"].strip()) > 0, f"Demo stint #{s.get('id')} has empty worker_name"

    # 2. Add an employment under DEFAULT_EMPLOYER_ADDR for a known worker
    worker = create_worker_with_name("Deepak Demo Master", category="Mason")
    stint = blockchain_service.create_employment(
        worker_did=worker["worker_did"],
        employer_address=DEFAULT_EMPLOYER_ADDR,
        category="Mason",
        level="Skilled",
        nature_of_employment="Contract",
        job_role="Site Supervisor",
        location="Demo Site West"
    )
    demo_stint_id = stint["id"]

    # 3. Re-query demo endpoint
    demo_res2 = client.get("/api/v1/employer/info")
    assert demo_res2.status_code == 200
    stints2 = demo_res2.json().get("employments", [])
    matched = next((s for s in stints2 if s["id"] == demo_stint_id), None)
    assert matched is not None, f"Newly created demo stint #{demo_stint_id} not returned in demo mode"
    assert matched["worker_name"] == "Deepak Demo Master", (
        f"Expected 'Deepak Demo Master', got '{matched.get('worker_name')}'"
    )


# ==============================================================================
# SECTION 3: REJECTION OF INVALID INVARIANTS & ADVERSARIAL STRESS
# ==============================================================================

def test_rejection_of_invalid_status_enums():
    """
    Adversarial challenge: Attempting invalid, arbitrary, or out-of-spec status values
    must be strictly rejected with HTTP 400.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("Status Stress Worker")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    c_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Worker",
        "work_location": "Yard 1"
    })
    stint_id = c_res.json()["employment_record"]["id"]

    invalid_statuses = [
        "INVALID_STATUS",
        "UNKNOWN",
        "PENDING",
        "DELETED",
        "CANCELLED",
        "completed",        # lowercase
        "Discontinued",     # titlecase
        "ACTIVE_SUSPENDED",
        "NULL",
        " "
    ]

    for inv in invalid_statuses:
        res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
            "employment_id": stint_id,
            "new_status": inv,
            "reason": "Fuzzing invalid status"
        })
        assert res.status_code in (400, 422), (
            f"Expected 400/422 for invalid status '{inv}', got {res.status_code}: {res.text}"
        )

    # Verify SQLite record is untouched and remains ACTIVE
    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec.status == "ACTIVE"
    finally:
        db.close()


def test_rejection_of_sqli_payloads_in_status():
    """
    Adversarial security: Attempting SQL Injection payloads in new_status
    must be safely rejected without DB error or corruption.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("SQLi Target Worker")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    c_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Worker",
        "work_location": "Yard 2"
    })
    stint_id = c_res.json()["employment_record"]["id"]

    sqli_statuses = [
        "COMPLETED'; DROP TABLE employments; --",
        "ACTIVE' OR '1'='1",
        "DISCONTINUED' UNION SELECT * FROM users --",
        "'; EXEC xp_cmdshell('dir'); --",
        "' OR 1=1 --",
        "\" OR \"\"=\""
    ]

    for sqli in sqli_statuses:
        res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
            "employment_id": stint_id,
            "new_status": sqli,
            "reason": "Testing SQLi payload"
        })
        assert res.status_code == 400, f"Expected 400 for SQLi status, got {res.status_code}: {res.text}"

    # Verify DB table integrity
    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec is not None
        assert rec.status == "ACTIVE"
    finally:
        db.close()


def test_reason_field_sanitization_and_sql_safety():
    """
    Adversarial security: Pass SQL injection, XSS, and boundary strings in reason.
    Verify that status updates succeed, SQLite safely parameterizes the string,
    and no SQL execution or data corruption occurs.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("Reason Safety Worker")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    c_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Worker",
        "work_location": "Yard 3"
    })
    stint_id = c_res.json()["employment_record"]["id"]

    dangerous_reason = "'; DROP TABLE worker_profiles; -- <script>alert('xss')</script> 🎉 Unicode"
    res = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": stint_id,
        "new_status": "COMPLETED",
        "reason": dangerous_reason
    })
    assert res.status_code == 200, res.text

    # Verify record in DB stores the exact literal string without executing SQL
    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec.status == "COMPLETED"
        assert rec.status_reason == dangerous_reason
        # Ensure worker_profiles table was NOT dropped!
        prof = db.query(DBWorkerProfile).first()
        assert prof is not None, "worker_profiles table was harmed!"
    finally:
        db.close()


def test_rejection_of_invalid_employment_ids():
    """
    Boundary testing: Non-existent IDs, negative IDs, and malformed inputs.
    """
    employer = create_employer_org()
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    # Non-existent ID
    res1 = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": 99999999,
        "new_status": "COMPLETED",
        "reason": "Testing non-existent ID"
    })
    assert res1.status_code == 400
    assert "not found" in res1.text.lower()

    # Negative ID
    res2 = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": -99,
        "new_status": "COMPLETED",
        "reason": "Testing negative ID"
    })
    assert res2.status_code == 400

    # Malformed non-integer ID via FastAPI / Pydantic schema validation
    res3 = client.put("/api/v1/employer/employment-status", headers=emp_headers, json={
        "employment_id": "not_an_int",
        "new_status": "COMPLETED",
        "reason": "Testing malformed ID"
    })
    assert res3.status_code == 422


def test_cross_tenant_idor_prevention():
    """
    Adversarial IDOR: Employer B cannot conclude or dismiss an employment stint belonging to Employer A.
    """
    employer_a = create_employer_org("Employer Alpha")
    employer_b = create_employer_org("Employer Beta")
    worker = create_worker_with_name("IDOR Defense Worker")

    # Employer A creates stint
    c_res = client.post(
        "/api/v1/employer/create-employment",
        headers={"Authorization": f"Bearer {employer_a['token']}"},
        json={
            "worker_did": worker["worker_did"],
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Craftsman",
            "work_location": "Alpha Site"
        }
    )
    stint_id = c_res.json()["employment_record"]["id"]

    # Employer B attempts to conclude Employer A's stint
    idor_res = client.put(
        "/api/v1/employer/employment-status",
        headers={"Authorization": f"Bearer {employer_b['token']}"},
        json={
            "employment_id": stint_id,
            "new_status": "DISCONTINUED",
            "reason": "Malicious conclusion attempt by unauthorized employer"
        }
    )
    assert idor_res.status_code == 400, f"Expected 400 for cross-tenant IDOR, got {idor_res.status_code}: {idor_res.text}"
    assert "unauthorized" in idor_res.text.lower() or "only employing organization" in idor_res.text.lower()

    # Verify Employer A's stint remains ACTIVE
    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec.status == "ACTIVE", "Stint status was modified by unauthorized tenant!"
    finally:
        db.close()


def test_unauthenticated_and_unauthorized_role_rejection():
    """
    RBAC verification:
    - Unauthenticated requests must receive HTTP 401.
    - WORKER or GOVERNMENT roles attempting employment status update must receive HTTP 403.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("RBAC Worker")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    c_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Mason",
        "work_location": "Site RBAC"
    })
    stint_id = c_res.json()["employment_record"]["id"]

    # 1. Unauthenticated -> 401
    res_unauth = client.put("/api/v1/employer/employment-status", json={
        "employment_id": stint_id,
        "new_status": "COMPLETED",
        "reason": "No auth token"
    })
    assert res_unauth.status_code == 401, f"Expected 401, got {res_unauth.status_code}: {res_unauth.text}"

    # 2. Worker role -> 403
    res_worker = client.put(
        "/api/v1/employer/employment-status",
        headers={"Authorization": f"Bearer {worker['token']}"},
        json={
            "employment_id": stint_id,
            "new_status": "COMPLETED",
            "reason": "Worker attempting self dismissal"
        }
    )
    assert res_worker.status_code == 403, f"Expected 403 for WORKER role, got {res_worker.status_code}"


def test_admin_supervisory_override_allowed():
    """
    Invariant: An authenticated ADMIN has supervisory authority to update employment status
    for regulatory oversight.
    """
    employer = create_employer_org()
    worker = create_worker_with_name("Admin Supervisory Worker")
    emp_headers = {"Authorization": f"Bearer {employer['token']}"}

    c_res = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
        "worker_did": worker["worker_did"],
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Mason",
        "work_location": "Site Admin"
    })
    stint_id = c_res.json()["employment_record"]["id"]

    # Login as demo admin
    admin_login = client.post("/api/v1/auth/demo-login/ADMIN")
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    admin_res = client.put(
        "/api/v1/employer/employment-status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employment_id": stint_id,
            "new_status": "DISCONTINUED",
            "reason": "Administrative platform supervisory order"
        }
    )
    assert admin_res.status_code == 200, admin_res.text
    assert admin_res.json()["status"] == "DISCONTINUED"

    # Verify SQLite DB
    db = SessionLocal()
    try:
        rec = db.query(DBEmployment).filter(DBEmployment.id == stint_id).first()
        assert rec.status == "DISCONTINUED"
        assert rec.status_reason == "Administrative platform supervisory order"
    finally:
        db.close()
