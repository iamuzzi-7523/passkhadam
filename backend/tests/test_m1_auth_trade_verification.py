"""
Milestone 1 Test Suite: Multi-Role Authentication & Dual-Verification Hardening
Tests:
- Custom trade/profession registration & persistence
- Origin state & current state persistence and sync
- Dual-verification pipeline (Email OTP & Phone OTP)
- Profile serialization via GET /api/v1/auth/me
"""

import time
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile

client = TestClient(app)


def test_custom_profession_registration_and_me_context():
    """Verify that a worker can register with a custom trade/profession and origin state."""
    db = SessionLocal()
    unique_id = uuid.uuid4().hex[:8]
    email = f"custom_worker_{unique_id}@passkhadam.org"
    password = "TestPassword123!"
    custom_trade = "Solar PV & Battery System Installer"
    skills = [custom_trade, "High Voltage Inverter Setup"]
    origin_state = "Odisha"
    current_state = "Karnataka"

    try:
        reg_payload = {
            "full_name": f"Surya Worker {unique_id}",
            "email": email,
            "phone": "+91 98765 43210",
            "password": password,
            "role": "WORKER",
            "worker_category": custom_trade,
            "skills": skills,
            "origin_state": origin_state,
            "current_state": current_state
        }

        res = client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "access_token" in data
        token = data["access_token"]
        assert data["user"]["role"] == "WORKER"
        assert data["user"]["is_email_verified"] is True
        assert data["user"]["is_phone_verified"] is True

        # Query GET /api/v1/auth/me
        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200, me_res.text
        me_data = me_res.json()
        profile = me_data["worker_profile"]
        assert profile is not None
        assert profile["worker_category"] == custom_trade
        assert custom_trade in profile["skills"]
        assert profile["origin_state"] == origin_state
        assert profile["current_state"] == current_state

        # Direct database verification
        user = db.query(DBUser).filter(DBUser.email == email).first()
        assert user is not None
        db_profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).first()
        assert db_profile is not None
        assert db_profile.worker_category == custom_trade
        assert db_profile.origin_state == origin_state
        assert db_profile.current_state == current_state
        parsed_skills = json.loads(db_profile.skills_json)
        assert custom_trade in parsed_skills
    finally:
        db.close()


def test_standard_trade_and_states_registration():
    """Verify registration with standard preset trade and non-Karnataka origin state."""
    db = SessionLocal()
    unique_id = uuid.uuid4().hex[:8]
    email = f"mason_{unique_id}@passkhadam.org"
    password = "TestPassword123!"

    try:
        reg_payload = {
            "full_name": f"Ramesh Mason {unique_id}",
            "email": email,
            "phone": "+91 98765 43210",
            "password": password,
            "role": "WORKER",
            "worker_category": "Mason",
            "skills": ["Mason", "Formwork"],
            "origin_state": "Bihar",
            "current_state": "Karnataka"
        }

        res = client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        token = res.json()["access_token"]

        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        profile = me_res.json()["worker_profile"]
        assert profile["worker_category"] == "Mason"
        assert profile["origin_state"] == "Bihar"
        assert profile["current_state"] == "Karnataka"
    finally:
        db.close()


def test_worker_profile_update_syncs_origin_and_current_state():
    """Verify re-registration/profile sync updates worker_category, skills, origin_state, and current_state."""
    db = SessionLocal()
    unique_id = uuid.uuid4().hex[:8]
    email = f"update_worker_{unique_id}@passkhadam.org"
    password = "InitialPassword123!"

    try:
        # Initial registration as Electrician from Karnataka
        initial_payload = {
            "full_name": f"Initial Worker {unique_id}",
            "email": email,
            "phone": "+91 98765 43210",
            "password": password,
            "role": "WORKER",
            "worker_category": "Electrician",
            "skills": ["Electrician"],
            "origin_state": "Karnataka",
            "current_state": "Karnataka"
        }
        res1 = client.post("/api/v1/auth/register", json=initial_payload)
        assert res1.status_code == 200, res1.text

        # Second registration call (e.g. user updating their profession and location)
        new_trade = "Advanced Scaffolding Inspector"
        new_origin = "West Bengal"
        new_current = "Maharashtra"
        updated_payload = {
            "full_name": f"Updated Worker {unique_id}",
            "email": email,
            "phone": "+91 98765 43210",
            "password": password,
            "role": "WORKER",
            "worker_category": new_trade,
            "skills": [new_trade, "Safety Audit"],
            "origin_state": new_origin,
            "current_state": new_current
        }
        res2 = client.post("/api/v1/auth/register", json=updated_payload)
        assert res2.status_code == 200, res2.text
        token = res2.json()["access_token"]

        # Check me endpoint reflects new values
        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        profile = me_res.json()["worker_profile"]
        assert profile["worker_category"] == new_trade
        assert new_trade in profile["skills"]
        assert profile["origin_state"] == new_origin
        assert profile["current_state"] == new_current

        # Check database
        user = db.query(DBUser).filter(DBUser.email == email).first()
        db_profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).first()
        assert db_profile.worker_category == new_trade
        assert db_profile.origin_state == new_origin
        assert db_profile.current_state == new_current
    finally:
        db.close()


def test_dual_verification_email_otp_flow():
    """Verify backend email OTP flow: send OTP, test codes (729415, 123456), and verification."""
    unique_id = uuid.uuid4().hex[:8]
    test_email = f"otp_test_{unique_id}@passkhadam.org"

    # Send OTP
    send_resp = client.post("/api/v1/auth/send-email-otp", json={"email": test_email})
    assert send_resp.status_code == 200
    data = send_resp.json()
    assert data["success"] is True
    session_id = data["session_id"]
    otp_code = data["otp_code"]

    # Verify generated OTP
    verify_resp = client.post("/api/v1/auth/verify-email-otp", json={
        "email": test_email,
        "otp_code": otp_code,
        "session_id": session_id
    })
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

    # Test preset 729415 acceptance
    verify_preset_resp = client.post("/api/v1/auth/verify-email-otp", json={
        "email": f"preset_{unique_id}@passkhadam.org",
        "otp_code": "729415"
    })
    assert verify_preset_resp.status_code == 200
    assert verify_preset_resp.json()["verified"] is True

    # Test preset 123456 acceptance
    verify_preset_resp2 = client.post("/api/v1/auth/verify-email-otp", json={
        "email": f"preset2_{unique_id}@passkhadam.org",
        "otp_code": "123456"
    })
    assert verify_preset_resp2.status_code == 200
    assert verify_preset_resp2.json()["verified"] is True


def test_dual_verification_phone_otp_flow():
    """Verify backend phone OTP endpoints with test numbers and session handling."""
    phone = "+91 98765 43210"

    # Send phone OTP
    send_resp = client.post("/api/v1/auth/send-otp", json={"phone": phone})
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["success"] is True
    assert send_data["session_id"].startswith("fb_sess_")
    assert "simulated_sms" in send_data
    session_id = send_data["session_id"]

    # Verify phone OTP with standard test code
    verify_resp = client.post("/api/v1/auth/verify-otp", json={
        "phone": phone,
        "otp": "123456",
        "session_id": session_id
    })
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True


def test_custom_trade_string_length_and_special_characters():
    """Verify custom trades with special characters and up to 100 chars persist cleanly."""
    db = SessionLocal()
    unique_id = uuid.uuid4().hex[:8]
    email = f"special_trade_{unique_id}@passkhadam.org"
    password = "TestPassword123!"
    special_trade = "Crane & Rigging Specialist / Heavy Haulage (IS:13367-1)"

    try:
        reg_payload = {
            "full_name": "Specialist Worker",
            "email": email,
            "phone": "+91 98765 43210",
            "password": password,
            "role": "WORKER",
            "worker_category": special_trade,
            "skills": [special_trade],
            "origin_state": "Tamil Nadu",
            "current_state": "Karnataka"
        }

        res = client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        token = res.json()["access_token"]

        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.json()["worker_profile"]["worker_category"] == special_trade
        assert me_res.json()["worker_profile"]["origin_state"] == "Tamil Nadu"
    finally:
        db.close()
