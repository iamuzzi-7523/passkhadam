"""
backend/tests/test_m2_frontend_contract_challenger.py

Empirical Challenger Test Suite for Milestone 2 Frontend-Backend Contract:
- Employment History endpoint serialization & count partitioning symmetry
- Permanence Invariant: DISCONTINUED & COMPLETED status retention across service queries
- Worker skills update endpoint (/skills/me) and fallback (/profile/me) contract
- Client DID injection rejection on skills updates

Author: challenger_m2_1 (EMPIRICAL CHALLENGER)
Target Codebase: PassKhadam_Exportable
"""

import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployment
from app.services.blockchain_service import blockchain_service

client = TestClient(app)


def create_verified_worker(unique_id: str):
    email = f"w_challenger_{unique_id}@passkhadam.org"
    password = "TestPassword123!"
    reg_payload = {
        "full_name": f"Challenger Worker {unique_id}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "worker_category": "Mason",
        "origin_state": "Bihar",
        "skills": ["Bricklaying", "Plastering"]
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    user_id = res.json()["user"]["id"]

    # Auto-anchor Aadhaar in DB
    db = SessionLocal()
    try:
        profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user_id).first()
        profile.is_aadhaar_verified = True
        profile.is_credential_anchored = True
        profile.did = f"did:passkhadam:worker:{unique_id}"
        profile.masked_aadhaar = "XXXX-XXXX-9911"
        profile.aadhaar_status = "ACTIVE"
        db.commit()
        db.refresh(profile)
        worker_did = profile.did
    finally:
        db.close()

    return token, user_id, worker_did


def test_employment_history_me_contract_and_count_symmetry():
    """Verify GET /api/v1/worker/employment-history/me returns contract fields and exact count partition."""
    uid = uuid.uuid4().hex[:8]
    token, user_id, worker_did = create_verified_worker(uid)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Empty state
    res = client.get("/api/v1/worker/employment-history/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["worker_did"] == worker_did
    assert data["employments"] == []
    assert data["active_count"] == 0
    assert data["historical_count"] == 0
    assert data["total_count"] == 0

    # 2. Add an ACTIVE stint, a DISCONTINUED stint, and a COMPLETED stint in DBEmployment
    db = SessionLocal()
    try:
        active_emp = DBEmployment(
            worker_did=worker_did,
            employer_address="0x1111111111111111111111111111111111111111",
            employer_name="BuildCorp Infrastructure",
            category="Masonry",
            job_role="Lead Mason",
            location="Panaji, Goa",
            start_date=1700000000,
            status="ACTIVE",
            status_reason="Project initiated"
        )
        disc_emp = DBEmployment(
            worker_did=worker_did,
            employer_address="0x2222222222222222222222222222222222222222",
            employer_name="Coastal Projects",
            category="Excavation",
            job_role="Trench Specialist",
            location="Margao, Goa",
            start_date=1690000000,
            end_date=1699000000,
            status="DISCONTINUED",
            status_reason="Category authorization revoked by admin"
        )
        comp_emp = DBEmployment(
            worker_did=worker_did,
            employer_address="0x3333333333333333333333333333333333333333",
            employer_name="Urban Heights",
            category="Plastering",
            job_role="Plasterer",
            location="Vasco, Goa",
            start_date=1680000000,
            end_date=1689000000,
            status="COMPLETED",
            status_reason="Contract successfully completed"
        )
        db.add_all([active_emp, disc_emp, comp_emp])
        db.commit()
    finally:
        db.close()

    # 3. Query history endpoint
    res2 = client.get("/api/v1/worker/employment-history/me", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["total_count"] == 3
    assert data2["active_count"] == 1
    assert data2["historical_count"] == 2
    assert len(data2["employments"]) == 3

    statuses = [e["status"] for e in data2["employments"]]
    assert "ACTIVE" in statuses
    assert "DISCONTINUED" in statuses
    assert "COMPLETED" in statuses

    # Verify active stints vs historical stints
    active_items = [e for e in data2["employments"] if e["status"] == "ACTIVE"]
    hist_items = [e for e in data2["employments"] if e["status"] != "ACTIVE"]
    assert len(active_items) == data2["active_count"]
    assert len(hist_items) == data2["historical_count"]


def test_worker_skills_update_and_fallback_contract():
    """Verify PUT /api/v1/worker/skills/me and fallback /api/v1/worker/profile/me."""
    uid = uuid.uuid4().hex[:8]
    token, user_id, worker_did = create_verified_worker(uid)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Update skills via dedicated /skills/me endpoint
    skills_payload = {
        "worker_category": "Electrician",
        "skills": ["Conduit Wiring", "Switchgear", "Solar PV"]
    }
    res = client.put("/api/v1/worker/skills/me", json=skills_payload, headers=headers)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["worker_category"] == "Electrician"
    assert "Solar PV" in res_data["skills"]

    # Verify profile reflects update
    prof_res = client.get("/api/v1/worker/profile/me", headers=headers)
    assert prof_res.status_code == 200
    prof = prof_res.json()
    assert prof["worker_category"] == "Electrician"
    assert prof["skills"] == ["Conduit Wiring", "Switchgear", "Solar PV"]

    # 2. Update custom profession via fallback /profile/me
    custom_payload = {
        "worker_category": "Solar & Microgrid Technician",
        "skills": ["Battery Storage", "Inverter Commissioning"]
    }
    fallback_res = client.put("/api/v1/worker/profile/me", json=custom_payload, headers=headers)
    assert fallback_res.status_code == 200
    fallback_data = fallback_res.json()
    assert fallback_data["profile"]["worker_category"] == "Solar & Microgrid Technician"
    assert fallback_data["profile"]["skills"] == ["Battery Storage", "Inverter Commissioning"]


def test_worker_skills_client_did_tampering_rejected():
    """Verify that attempting to pass client-supplied DID in skills update is rejected (400 Bad Request)."""
    uid = uuid.uuid4().hex[:8]
    token, user_id, worker_did = create_verified_worker(uid)
    headers = {"Authorization": f"Bearer {token}"}

    # Malicious payload trying to hijack or inject DID
    tampered_payload = {
        "worker_category": "Master Welder",
        "skills": ["TIG Welding"],
        "worker_did": "did:passkhadam:hijacked:admin"
    }
    res = client.put("/api/v1/worker/skills/me", json=tampered_payload, headers=headers)
    assert res.status_code == 400
    assert "Client-supplied DID is strictly forbidden" in res.text
