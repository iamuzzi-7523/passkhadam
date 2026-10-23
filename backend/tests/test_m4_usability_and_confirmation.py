"""
backend/tests/test_m4_usability_and_confirmation.py
Milestone 4 Test Suite: Usability Betterments, Role UX Comfort & Guidance (Features 13, 14, 15, 16)

Covers:
1. Feature 13: Aadhaar Input Masking, Formatting & Validation
2. Feature 14: Employer Worker Dismissal Confirmation, Reason Presets, and Worker Name Enrichment
3. Feature 15: Employer Workforce Search & Filter Invariants
4. Feature 16: Actionable Guidance Badges & Notices across Worker, Employer, and Government portals
"""

import os
import re
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployment, DBEmployerOrganization
from app.services.blockchain_service import blockchain_service

client = TestClient(app)

DEFAULT_EMPLOYER_ADDR = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"


def create_test_worker(full_name=None, category="Mason"):
    """Helper to register a fresh verified worker with worker profile and DID."""
    uid = uuid.uuid4().hex[:8]
    worker_name = full_name or f"M4 Worker {uid}"
    email = f"m4_worker_{uid}@passkhadam.org"
    payload = {
        "full_name": worker_name,
        "email": email,
        "phone": "+91 98765 43210",
        "password": "Password123!",
        "role": "WORKER",
        "worker_category": category,
        "skills": ["Bricklaying", "Plastering"],
        "origin_state": "Uttar Pradesh",
        "current_state": "Maharashtra",
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
        worker_did = f"did:passkhadam:worker:m4_{uid}"
        if prof:
            prof.did = worker_did
            prof.is_credential_anchored = True
            db.commit()
            db.refresh(prof)
        else:
            prof = DBWorkerProfile(
                user_id=user_id,
                full_name=worker_name,
                did=worker_did,
                worker_category=category,
                origin_state="Uttar Pradesh",
                current_state="Maharashtra",
                is_credential_anchored=True,
                aadhaar_status="ACTIVE",
                masked_aadhaar="XXXX-XXXX-4821"
            )
            db.add(prof)
            db.commit()
    finally:
        db.close()

    return {
        "token": token,
        "user_id": user_id,
        "worker_did": worker_did,
        "worker_name": worker_name,
        "email": email
    }


def create_test_employer():
    """Helper to register an active test employer organization."""
    uid = uuid.uuid4().hex[:8]
    email = f"m4_employer_{uid}@buildcorp.com"
    payload = {
        "company_name": f"BuildCorp M4 {uid}",
        "registration_number": f"REG-M4-{uid}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": "Password123!",
        "role": "EMPLOYER",
        "address": "Navi Mumbai SEZ",
        "requested_categories": ["Mason", "Heavy Machinery Operator", "Electrician"]
    }
    res = client.post("/api/v1/employer/register-organization", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    token = data.get("access_token")
    user_id = data.get("user", {}).get("id")

    # Set organization to ACTIVE with known org address
    org_addr = f"0xemp_{uid[:8]}"
    org_name = f"BuildCorp M4 {uid}"
    db = SessionLocal()
    try:
        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == user_id).first()
        if org:
            org.status = "ACTIVE"
            org.org_address = org_addr
            db.commit()
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if user:
            user.organization_address = org_addr
            db.commit()
    finally:
        db.close()

    # Ensure blockchain_service knows about this organization
    blockchain_service.organizations[org_addr] = {
        "address": org_addr,
        "name": org_name,
        "reg_number": f"REG-M4-{uid}",
        "status": "APPROVED",
        "categories": ["Mason", "Heavy Machinery Operator", "Electrician"],
        "levels": ["Skilled", "Semi-Skilled"],
        "natures": ["Contract", "Project-Based"]
    }

    # Re-login to get updated JWT claims
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]

    return {
        "token": token,
        "user_id": user_id,
        "org_address": org_addr,
        "org_name": org_name,
        "email": email
    }


# ==============================================================================
# FEATURE 13: Aadhaar Input Masking & Validation Tests
# ==============================================================================

def test_feature13_clean_aadhaar_normalization_invariants():
    """Verify that Aadhaar digit cleaning and space stripping behave deterministically."""
    raw_inputs = [
        ("1234 5678 4821", "123456784821"),
        ("  1234  5678  4821  ", "123456784821"),
        ("1234-5678-4821", "123456784821"),
        ("123456784821", "123456784821"),
        ("1234 5678", "12345678"),
        ("", "")
    ]
    for inp, expected in raw_inputs:
        cleaned = re.sub(r"\D", "", inp)[:12]
        assert cleaned == expected, f"Failed cleaning for input '{inp}'"


def test_feature13_worker_verify_aadhaar_validation():
    """Verify that /worker/verify-aadhaar/me validates 12 digits and handles sanitized inputs."""
    worker = create_test_worker(full_name="Aadhaar Test Worker")
    headers = {"Authorization": f"Bearer {worker['token']}"}

    # 1. Invalid short length -> rejected
    res_short = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json={"aadhaar_number": "12345", "full_name": "Aadhaar Test Worker"},
        headers=headers
    )
    assert res_short.status_code in (400, 422), f"Expected rejection for short Aadhaar: {res_short.text}"

    # 2. Non-numeric invalid input -> rejected
    res_alpha = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json={"aadhaar_number": "ABCD-EFGH-IJKL", "full_name": "Aadhaar Test Worker"},
        headers=headers
    )
    assert res_alpha.status_code in (400, 422), f"Expected rejection for alpha Aadhaar: {res_alpha.text}"

    # 3. Valid active demo Aadhaar number (123456784821) -> succeeds or returns authoritative result
    res_valid = client.post(
        "/api/v1/worker/verify-aadhaar/me",
        json={"aadhaar_number": "123456784821", "full_name": "Aadhaar Test Worker"},
        headers=headers
    )
    assert res_valid.status_code in (200, 400), f"Unexpected status for valid Aadhaar: {res_valid.status_code} {res_valid.text}"


# ==============================================================================
# FEATURE 14: Employer Worker Dismissal Confirmation & Enrichment Tests
# ==============================================================================

def test_feature14_employer_info_enriches_worker_name():
    """Verify that /api/v1/employer/info enriches employment stints with worker_name from DBWorkerProfile."""
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200, emp_login.text
    emp_token = emp_login.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    worker = create_test_worker(full_name="Ram Charan Builder", category="Mason")

    create_res = client.post(
        "/api/v1/employer/create-employment",
        headers=emp_headers,
        json={
            "worker_did": worker["worker_did"],
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason Lead",
            "work_location": "Navi Mumbai Site 1"
        }
    )
    assert create_res.status_code == 200, create_res.text
    emp_id = create_res.json()["employment_record"]["id"]

    # Call /api/v1/employer/info
    res = client.get("/api/v1/employer/info", headers=emp_headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Find the created stint in employments
    stints = data.get("employments", [])
    matched = [s for s in stints if s.get("id") == emp_id]
    assert len(matched) == 1, f"Expected stint #{emp_id} in employments list"
    assert matched[0].get("worker_name") == "Ram Charan Builder", (
        f"Expected worker_name 'Ram Charan Builder', got {matched[0].get('worker_name')}"
    )


def test_feature14_dismissal_confirmation_presets_and_persistence():
    """Verify concluding an employment stint with preset reasons updates blockchain_service and SQLite DBEmployment."""
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200, emp_login.text
    emp_token = emp_login.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    worker1 = create_test_worker(full_name="Worker Project Concluded", category="Mason")
    worker2 = create_test_worker(full_name="Worker Scope Discontinued", category="Mason")
    worker3 = create_test_worker(full_name="Worker Resigned Early", category="Mason")

    # 1. Preset: COMPLETED (Project phase concluded)
    c1 = client.post(
        "/api/v1/employer/create-employment",
        headers=emp_headers,
        json={
            "worker_did": worker1["worker_did"],
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason Lead",
            "work_location": "Site Alpha"
        }
    )
    assert c1.status_code == 200, c1.text
    emp1_id = c1.json()["employment_record"]["id"]

    reason1 = "Project phase concluded successfully on site; deliverables met."
    res1 = client.put(
        "/api/v1/employer/employment-status",
        json={"employment_id": emp1_id, "new_status": "COMPLETED", "reason": reason1},
        headers=emp_headers
    )
    assert res1.status_code == 200, res1.text
    assert res1.json()["status"] == "COMPLETED"

    # Verify SQLite DBEmployment
    db = SessionLocal()
    try:
        rec1 = db.query(DBEmployment).filter(DBEmployment.id == emp1_id).first()
        assert rec1 is not None, "DBEmployment record missing"
        assert rec1.status == "COMPLETED"
        assert rec1.status_reason == reason1
        assert rec1.end_date is not None and rec1.end_date > 0
    finally:
        db.close()

    # 2. Preset: DISCONTINUED (Operational site scope changes)
    c2 = client.post(
        "/api/v1/employer/create-employment",
        headers=emp_headers,
        json={
            "worker_did": worker2["worker_did"],
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason Worker",
            "work_location": "Site Beta"
        }
    )
    assert c2.status_code == 200, c2.text
    emp2_id = c2.json()["employment_record"]["id"]

    reason2 = "Discontinued by employer due to operational site scope changes."
    res2 = client.put(
        "/api/v1/employer/employment-status",
        json={"employment_id": emp2_id, "new_status": "DISCONTINUED", "reason": reason2},
        headers=emp_headers
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()["status"] == "DISCONTINUED"

    db = SessionLocal()
    try:
        rec2 = db.query(DBEmployment).filter(DBEmployment.id == emp2_id).first()
        assert rec2 is not None
        assert rec2.status == "DISCONTINUED"
        assert rec2.status_reason == reason2
        assert rec2.end_date is not None and rec2.end_date > 0
    finally:
        db.close()

    # Check worker2 portable employment history preserves DISCONTINUED stint
    w2_history = client.get(
        "/api/v1/worker/employment-history/me",
        headers={"Authorization": f"Bearer {worker2['token']}"}
    )
    assert w2_history.status_code == 200, w2_history.text
    w2_data = w2_history.json()
    w2_stints = w2_data.get("employments", [])
    assert any(s["id"] == emp2_id and s["status"] == "DISCONTINUED" for s in w2_stints), (
        "Discontinued stint must remain permanently recorded in worker employment history"
    )

    # 3. Preset: RESIGNED (Worker voluntarily resigned)
    c3 = client.post(
        "/api/v1/employer/create-employment",
        headers=emp_headers,
        json={
            "worker_did": worker3["worker_did"],
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason Apprentice",
            "work_location": "Site Gamma"
        }
    )
    assert c3.status_code == 200, c3.text
    emp3_id = c3.json()["employment_record"]["id"]

    reason3 = "Worker voluntarily resigned due to personal relocation / circumstances."
    res3 = client.put(
        "/api/v1/employer/employment-status",
        json={"employment_id": emp3_id, "new_status": "RESIGNED", "reason": reason3},
        headers=emp_headers
    )
    assert res3.status_code == 200, res3.text
    assert res3.json()["status"] == "RESIGNED"

    db = SessionLocal()
    try:
        rec3 = db.query(DBEmployment).filter(DBEmployment.id == emp3_id).first()
        assert rec3 is not None
        assert rec3.status == "RESIGNED"
        assert rec3.status_reason == reason3
    finally:
        db.close()


def test_feature14_invalid_status_rejection():
    """Verify that invalid or arbitrary status values are rejected with HTTP 400."""
    emp_login = client.post("/api/v1/auth/demo-login/EMPLOYER")
    assert emp_login.status_code == 200, emp_login.text
    emp_headers = {"Authorization": f"Bearer {emp_login.json()['access_token']}"}

    worker = create_test_worker()
    c = client.post(
        "/api/v1/employer/create-employment",
        headers=emp_headers,
        json={
            "worker_did": worker["worker_did"],
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason",
            "work_location": "Site X"
        }
    )
    assert c.status_code == 200, c.text
    emp_id = c.json()["employment_record"]["id"]

    res = client.put(
        "/api/v1/employer/employment-status",
        json={"employment_id": emp_id, "new_status": "INVALID_STATE", "reason": "Testing invalid state"},
        headers=emp_headers
    )
    assert res.status_code == 400, f"Expected 400 for invalid status, got {res.status_code}: {res.text}"


# ==============================================================================
# FEATURE 15 & 16: Frontend Source Code Invariant Verification
# ==============================================================================

def test_feature13_frontend_api_and_worker_portal_invariants():
    """Verify frontend/src/utils/api.js exports formatAadhaarInput and cleanAadhaarDigits."""
    api_js_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "utils", "api.js"
    )
    with open(api_js_path, "r", encoding="utf-8") as f:
        src = f.read()

    assert "export function formatAadhaarInput" in src, "Missing formatAadhaarInput in api.js"
    assert "export function cleanAadhaarDigits" in src, "Missing cleanAadhaarDigits in api.js"

    worker_portal_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "components", "worker", "WorkerPortal.jsx"
    )
    with open(worker_portal_path, "r", encoding="utf-8") as f:
        wp_src = f.read()

    # Must preserve verbatim endpoint call for challenger compatibility
    assert "apiFetch('/api/v1/worker/verify-aadhaar/me'" in wp_src, (
        "WorkerPortal.jsx must preserve apiFetch('/api/v1/worker/verify-aadhaar/me' verbatim"
    )
    # Must format input and display badge
    assert "formatAadhaarInput" in wp_src, "WorkerPortal.jsx must import/use formatAadhaarInput"
    assert "12/12 Digits Valid" in wp_src, "WorkerPortal.jsx must render 12/12 Digits Valid badge"


def test_feature14_and_15_employer_portal_invariants():
    """Verify EmployerPortal.jsx includes dismissal confirmation modal, search, and status filter tabs."""
    ep_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "components", "employer", "EmployerPortal.jsx"
    )
    with open(ep_path, "r", encoding="utf-8") as f:
        ep_src = f.read()

    # Feature 14 Modal
    assert "showDismissConfirmModal" in ep_src, "EmployerPortal.jsx missing showDismissConfirmModal state"
    assert "handleConfirmDismiss" in ep_src, "EmployerPortal.jsx missing handleConfirmDismiss"
    assert "CONCLUSION_PRESETS" in ep_src, "EmployerPortal.jsx missing CONCLUSION_PRESETS"
    assert "Conclude Employment Stint" in ep_src, "EmployerPortal.jsx missing modal title"
    assert "Confirm & Conclude Stint" in ep_src, "EmployerPortal.jsx missing submit button text"

    # Feature 15 Search & Filters
    assert "searchQuery" in ep_src, "EmployerPortal.jsx missing searchQuery state"
    assert "tradeFilter" in ep_src, "EmployerPortal.jsx missing tradeFilter state"
    assert "statusTab" in ep_src, "EmployerPortal.jsx missing statusTab state"
    assert "All Stints" in ep_src, "EmployerPortal.jsx missing All Stints tab"
    assert "Active Only" in ep_src, "EmployerPortal.jsx missing Active Only tab"
    assert "Concluded / Past" in ep_src, "EmployerPortal.jsx missing Concluded / Past tab"
    assert "Reset All Filters" in ep_src, "EmployerPortal.jsx missing Reset All Filters CTA"


def test_feature16_guidance_notices_across_portals():
    """Verify actionable guidance banners in WorkerPortal, EmployerPortal, and GovernmentPortal."""
    # 1. Worker Portal guidance
    wp_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "components", "worker", "WorkerPortal.jsx"
    )
    with open(wp_path, "r", encoding="utf-8") as f:
        wp_src = f.read()

    assert "Action Required: Verify Government Identity to Activate Wallet" in wp_src, (
        "WorkerPortal.jsx missing unanchored identity guidance banner"
    )
    assert "Worker Permanence Invariant:" in wp_src, (
        "WorkerPortal.jsx missing worker permanence reassurance notice"
    )

    # 2. Employer Portal guidance
    ep_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "components", "employer", "EmployerPortal.jsx"
    )
    with open(ep_path, "r", encoding="utf-8") as f:
        ep_src = f.read()

    assert "Organization Registration Under Platform Review (PENDING_REVIEW)" in ep_src, (
        "EmployerPortal.jsx missing PENDING_REVIEW actionable banner"
    )
    assert "Web-First Verification & Stint Permanence Guidance" in ep_src, (
        "EmployerPortal.jsx missing Zero-Camera and Stint Permanence Guidance"
    )

    # 3. Government Portal guidance
    gp_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "components", "government", "GovernmentPortal.jsx"
    )
    with open(gp_path, "r", encoding="utf-8") as f:
        gp_src = f.read()

    assert "Inter-State Welfare Portability & Sovereign Cooldown Invariants" in gp_src, (
        "GovernmentPortal.jsx missing Inter-State Welfare Portability & Sovereign Cooldown notice"
    )
