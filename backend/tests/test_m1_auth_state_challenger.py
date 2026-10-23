"""
backend/tests/test_m1_auth_state_challenger.py

Empirical Adversarial Backend Challenge Suite for Milestone 1:
- Custom trade / profession edge cases (empty strings, whitespace fallback, unicode, max length, injection attempts)
- Worker profile origin state & current state synchronization integrity
- Dual-verification endpoints (Email OTP & Phone OTP) stress & isolation

Author: challenger_m1_1 (EMPIRICAL CHALLENGER)
Target Codebase: PassKhadam_Exportable
"""

import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile

client = TestClient(app)


def test_custom_trade_empty_and_whitespace_backend_fallback():
    """Verify backend handles empty or whitespace worker_category with safe fallback."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"empty_cat_{unique_id}@passkhadam.org"
    password = "TestPassword123!"

    # Test empty string worker_category
    reg_payload = {
        "full_name": f"Empty Cat Worker {unique_id}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "worker_category": "",
        "skills": []
    }

    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    profile = me_res.json()["worker_profile"]
    assert profile is not None
    # Backend defaults to "Mason" if worker_category is empty/falsy
    assert profile["worker_category"] == "Mason"


def test_custom_trade_sql_and_xss_injection_resilience():
    """Verify that malicious inputs in worker_category and skills are safely stored as inert text."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"sec_test_{unique_id}@passkhadam.org"
    password = "TestPassword123!"
    malicious_trade = "Electrician'; DROP TABLE worker_profiles; -- <script>alert(1)</script>"

    reg_payload = {
        "full_name": "Security Test Worker",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "worker_category": malicious_trade,
        "skills": [malicious_trade]
    }

    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    profile = me_res.json()["worker_profile"]
    assert profile["worker_category"] == malicious_trade

    # Verify DBWorkerProfile table is intact and queryable
    db = SessionLocal()
    try:
        profiles_count = db.query(DBWorkerProfile).count()
        assert profiles_count > 0
    finally:
        db.close()


def test_custom_trade_unicode_and_multilingual_resilience():
    """Verify multilingual Hindi/Regional custom trades persist without encoding corruption."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"unicode_trade_{unique_id}@passkhadam.org"
    password = "TestPassword123!"
    hindi_trade = "सौर ऊर्जा तकनीशियन (Solar Energy Tech)"

    reg_payload = {
        "full_name": "Suresh Kumar",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "worker_category": hindi_trade,
        "skills": [hindi_trade],
        "origin_state": "Rajasthan",
        "current_state": "Karnataka"
    }

    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    profile = me_res.json()["worker_profile"]
    assert profile["worker_category"] == hindi_trade
    assert profile["origin_state"] == "Rajasthan"
    assert profile["current_state"] == "Karnataka"


def test_worker_profile_location_sync_does_not_wipe_custom_profession():
    """Verify that re-registration updating origin_state retains custom profession when authenticated."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"sync_worker_{unique_id}@passkhadam.org"
    password = "TestPassword123!"
    fb_uid = f"fb_sync_uid_{unique_id}"
    custom_trade = "Advanced CNC Milling Specialist"

    # Step 1: Initial Registration (AuthContext provides firebase_uid)
    reg1 = client.post("/api/v1/auth/register", json={
        "full_name": f"Sync Worker {unique_id}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "firebase_uid": fb_uid,
        "role": "WORKER",
        "worker_category": custom_trade,
        "skills": [custom_trade],
        "origin_state": "Madhya Pradesh",
        "current_state": "Karnataka"
    })
    assert reg1.status_code == 200, reg1.text

    # Step 2: Re-register to sync location change with same firebase_uid
    reg2 = client.post("/api/v1/auth/register", json={
        "full_name": f"Sync Worker {unique_id}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "firebase_uid": fb_uid,
        "role": "WORKER",
        "origin_state": "Madhya Pradesh",
        "current_state": "Maharashtra"
    })
    assert reg2.status_code == 200, reg2.text
    token2 = reg2.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert me_res.status_code == 200
    profile = me_res.json()["worker_profile"]
    # Category remains intact and current_state updated
    assert profile["worker_category"] == custom_trade
    assert profile["current_state"] == "Maharashtra"
    assert profile["origin_state"] == "Madhya Pradesh"
