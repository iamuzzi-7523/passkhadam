"""
PassKhadam Milestone 1 - Backend API Adversarial Challenge Suite
Agent: challenger_m1_2 (empirical_challenger)

Empirical Test Coverage:
1. Worker registration API boundaries:
   - Preset trades vs custom trades with complex symbols, numbers, and punctuation.
   - Exact 100-character custom trade strings.
   - Boundary tests for length and whitespace handling.
   - Comprehensive coverage of all 12 supported origin states:
     [Karnataka, Bihar, Uttar Pradesh, West Bengal, Odisha, Maharashtra,
      Kerala, Rajasthan, Tamil Nadu, Madhya Pradesh, Assam, Jharkhand]
   - Interstate migration (origin_state != current_state).
2. Profile re-registration and synchronization:
   - Worker profile sync updating origin_state and current_state.
   - Safe preservation when origin_state is omitted/null.
   - Direct self-service update via PUT /api/v1/worker/profile/me.
3. Security invariants:
   - Email OTP rate-limiting cooldown (cached delivery within 30 seconds).
   - Phone OTP brute force lockout (locks out after 5 failed attempts for 60s, resets on new OTP).
   - Email OTP brute force lockout (locks out after 5 failed attempts for 60s, resets on new OTP).
   - Session ID binding integrity (mismatched session_id rejected).
   - Single-use consumption (replayed OTP rejected after successful verification).
"""

import time
import json
import base64
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile
import app.api.endpoints.auth as auth_module

client = TestClient(app)

SUPPORTED_12_STATES = [
    "Karnataka",
    "Bihar",
    "Uttar Pradesh",
    "West Bengal",
    "Odisha",
    "Maharashtra",
    "Kerala",
    "Rajasthan",
    "Tamil Nadu",
    "Madhya Pradesh",
    "Assam",
    "Jharkhand"
]

def make_test_jwt(email: str, uid: str, email_verified: bool = True, phone: str = "+919876543210") -> str:
    """Creates a mock Firebase ID token for testing."""
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "iss": "https://securetoken.google.com/passkhadam-live",
        "aud": "passkhadam-live",
        "sub": uid,
        "user_id": uid,
        "email": email.strip().lower(),
        "email_verified": email_verified,
        "phone_number": phone,
        "exp": int(time.time()) + 3600
    }
    h_str = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_str = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{h_str}.{p_str}.mock_sig"


# ============================================================================
# 1. WORKER REGISTRATION API BOUNDARIES: CUSTOM TRADES & 12 STATES
# ============================================================================

@pytest.mark.parametrize("origin_state", SUPPORTED_12_STATES)
def test_boundary_all_12_origin_states_registration(origin_state: str):
    """Verify registration succeeds and accurately persists across all 12 supported origin states."""
    uid = uuid.uuid4().hex[:8]
    email = f"worker_state_{origin_state.lower().replace(' ', '_')}_{uid}@passkhadam.org"
    custom_trade = f"Technician-{origin_state[:3]}-#01"
    
    payload = {
        "full_name": f"Migrant Worker {origin_state}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": "SecurePassword123!",
        "role": "WORKER",
        "worker_category": custom_trade,
        "skills": [custom_trade, "General Labour"],
        "origin_state": origin_state,
        "current_state": "Karnataka"
    }

    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200, f"Registration failed for state {origin_state}: {res.text}"
    token = res.json()["access_token"]

    # Verify context in GET /api/v1/auth/me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200, me_res.text
    profile = me_res.json()["worker_profile"]
    assert profile is not None, "worker_profile must not be None"
    assert profile["origin_state"] == origin_state, f"Expected origin_state={origin_state}, got {profile['origin_state']}"
    assert profile["current_state"] == "Karnataka"
    assert profile["worker_category"] == custom_trade

    # Verify persistence in SQLite
    with SessionLocal() as db:
        user = db.query(DBUser).filter(DBUser.email == email).first()
        assert user is not None
        db_profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).first()
        assert db_profile is not None
        assert db_profile.origin_state == origin_state
        assert db_profile.current_state == "Karnataka"


def test_custom_trades_with_symbols_and_numbers():
    """Verify custom trades with symbols, numbers, punctuation, and industry notations persist cleanly."""
    complex_trades = [
        "Solar PV & Wind Turbine Tech (Level-3) + Battery Storage [100% Certified]",
        "Plumber & Pipefitter (IS:1239 / Class-C) - 2026 Edition",
        "Scaffolder (CISRS Part-2) #987 & Rigger @ Zone-4",
        "Electrician <Industrial & Commercial> 440V/11kV! #12"
    ]

    for i, trade in enumerate(complex_trades):
        uid = uuid.uuid4().hex[:8]
        email = f"complex_trade_{i}_{uid}@passkhadam.org"
        origin = SUPPORTED_12_STATES[i % len(SUPPORTED_12_STATES)]
        current = SUPPORTED_12_STATES[(i + 1) % len(SUPPORTED_12_STATES)]

        payload = {
            "full_name": f"Specialist Worker {i}",
            "email": email,
            "phone": "+91 98765 43210",
            "password": "SecurePassword123!",
            "role": "WORKER",
            "worker_category": trade,
            "skills": [trade, "Specialist Inspection"],
            "origin_state": origin,
            "current_state": current
        }

        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 200, f"Registration failed for trade '{trade}': {res.text}"
        token = res.json()["access_token"]

        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        profile = me_res.json()["worker_profile"]
        assert profile["worker_category"] == trade
        assert trade in profile["skills"]
        assert profile["origin_state"] == origin
        assert profile["current_state"] == current


def test_exact_100_character_trade_boundary():
    """Verify custom trade with exactly 100 characters persists and returns without truncation."""
    # Exactly 100 characters:
    exact_100_trade = "Certified Industrial Rigging & Heavy Machinery Specialist (Class-IV Heavy Crane & Derrick IS:13367)"
    if len(exact_100_trade) < 100:
        exact_100_trade = exact_100_trade.ljust(100, "X")
    elif len(exact_100_trade) > 100:
        exact_100_trade = exact_100_trade[:100]

    assert len(exact_100_trade) == 100, f"Length must be exactly 100, got {len(exact_100_trade)}"

    uid = uuid.uuid4().hex[:8]
    email = f"hundred_char_{uid}@passkhadam.org"
    payload = {
        "full_name": "Rigging Specialist 100",
        "email": email,
        "phone": "+91 98765 43210",
        "password": "SecurePassword123!",
        "role": "WORKER",
        "worker_category": exact_100_trade,
        "skills": [exact_100_trade],
        "origin_state": "Odisha",
        "current_state": "Maharashtra"
    }

    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    returned_category = me_res.json()["worker_profile"]["worker_category"]
    assert returned_category == exact_100_trade
    assert len(returned_category) == 100

    with SessionLocal() as db:
        user = db.query(DBUser).filter(DBUser.email == email).first()
        db_profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).first()
        assert db_profile.worker_category == exact_100_trade
        assert len(db_profile.worker_category) == 100


# ============================================================================
# 2. PROFILE RE-REGISTRATION / SYNC UPDATING ORIGIN_STATE & CURRENT_STATE
# ============================================================================

def test_profile_re_registration_updates_origin_and_current_state():
    """Verify that a worker re-registering updates origin_state and current_state cleanly."""
    uid = uuid.uuid4().hex[:8]
    email = f"rereg_worker_{uid}@passkhadam.org"
    fb_uid = f"fb_{uid}"
    password = "InitialPassword123!"

    # Initial registration: Bihar -> Karnataka
    payload_1 = {
        "full_name": f"Migrant Worker {uid}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "firebase_uid": fb_uid,
        "worker_category": "Mason",
        "skills": ["Mason"],
        "origin_state": "Bihar",
        "current_state": "Karnataka"
    }
    res1 = client.post("/api/v1/auth/register", json=payload_1)
    assert res1.status_code == 200, res1.text

    # Re-registration / Profile Sync: updates location to West Bengal -> Tamil Nadu and new trade
    new_trade = "Advanced Scaffolder Level-2"
    payload_2 = {
        "full_name": f"Migrant Worker {uid}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "firebase_uid": fb_uid,
        "worker_category": new_trade,
        "skills": [new_trade, "Formwork"],
        "origin_state": "West Bengal",
        "current_state": "Tamil Nadu"
    }
    res2 = client.post("/api/v1/auth/register", json=payload_2)
    assert res2.status_code == 200, res2.text
    token = res2.json()["access_token"]

    # Verify updated values in GET /me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    profile = me_res.json()["worker_profile"]
    assert profile["worker_category"] == new_trade
    assert profile["origin_state"] == "West Bengal"
    assert profile["current_state"] == "Tamil Nadu"

    # Verify database record
    with SessionLocal() as db:
        user = db.query(DBUser).filter(DBUser.email == email).first()
        db_profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).first()
        assert db_profile.worker_category == new_trade
        assert db_profile.origin_state == "West Bengal"
        assert db_profile.current_state == "Tamil Nadu"


def test_re_registration_preserves_origin_state_when_omitted():
    """Verify that re-registration with omitted origin_state preserves previously set origin_state."""
    uid = uuid.uuid4().hex[:8]
    email = f"omit_state_{uid}@passkhadam.org"
    fb_uid = f"fb_omit_{uid}"
    password = "InitialPassword123!"

    # Initial registration with origin_state="Rajasthan"
    payload_1 = {
        "full_name": f"Worker {uid}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "firebase_uid": fb_uid,
        "worker_category": "Carpenter",
        "skills": ["Carpenter"],
        "origin_state": "Rajasthan",
        "current_state": "Gujarat"
    }
    res1 = client.post("/api/v1/auth/register", json=payload_1)
    assert res1.status_code == 200

    # Re-registration without origin_state (None/omitted) but updating current_state
    payload_2 = {
        "full_name": f"Worker {uid}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "firebase_uid": fb_uid,
        "current_state": "Maharashtra"
    }
    res2 = client.post("/api/v1/auth/register", json=payload_2)
    assert res2.status_code == 200
    token = res2.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    profile = me_res.json()["worker_profile"]
    assert profile["origin_state"] == "Rajasthan", "Origin state must be preserved when omitted in sync"
    assert profile["current_state"] == "Maharashtra"


def test_put_profile_me_self_service_state_update():
    """Verify worker can update origin_state and current_state via PUT /api/v1/worker/profile/me."""
    uid = uuid.uuid4().hex[:8]
    email = f"put_worker_{uid}@passkhadam.org"
    fb_uid = f"fb_put_{uid}"
    password = "InitialPassword123!"

    payload = {
        "full_name": f"PUT Worker {uid}",
        "email": email,
        "phone": "+91 98765 43210",
        "password": password,
        "role": "WORKER",
        "firebase_uid": fb_uid,
        "worker_category": "Painter",
        "origin_state": "Assam",
        "current_state": "Karnataka"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200
    token = res.json()["access_token"]

    # Call PUT /api/v1/worker/profile/me
    update_payload = {
        "origin_state": "Jharkhand",
        "current_state": "Kerala",
        "worker_category": "Master Painter & Texture Specialist",
        "skills": ["Master Painter", "Epoxy Coating"]
    }
    put_res = client.put(
        "/api/v1/worker/profile/me",
        headers={"Authorization": f"Bearer {token}"},
        json=update_payload
    )
    assert put_res.status_code == 200, put_res.text
    put_data = put_res.json()
    assert put_data["profile"]["origin_state"] == "Jharkhand"
    assert put_data["profile"]["current_state"] == "Kerala"
    assert put_data["profile"]["worker_category"] == "Master Painter & Texture Specialist"

    # Confirm via GET /api/v1/auth/me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["worker_profile"]["origin_state"] == "Jharkhand"
    assert me_res.json()["worker_profile"]["current_state"] == "Kerala"


# ============================================================================
# 3. SECURITY INVARIANTS: RATE LIMITS, BRUTE FORCE LOCKOUTS & SESSION BINDING
# ============================================================================

def test_email_otp_rate_limiting_cooldown():
    """
    SECURITY INVARIANT TEST:
    Verify that rapid repeated Email OTP requests within 30s return cached session (delivery_mode='cached').
    EXPECTED BEHAVIOR:
    When a user requests an email OTP multiple times in rapid succession (< 30s cooldown),
    the endpoint must return delivery_mode='cached' to prevent email spamming / SMTP resource exhaustion.
    """
    uid = uuid.uuid4().hex[:8]
    email = f"ratelimit_email_{uid}@example.com"

    # Request 1
    res1 = client.post("/api/v1/auth/send-email-otp", json={"email": email})
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["success"] is True
    assert d1["delivery_mode"] in ["simulated", "smtp"]
    sess_id_1 = d1["session_id"]
    otp_code_1 = d1["otp_code"]

    # Request 2 immediately (<30s)
    res2 = client.post("/api/v1/auth/send-email-otp", json={"email": email})
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["delivery_mode"] == "cached", (
        f"Rapid repeated request within cooldown returned delivery_mode='{d2['delivery_mode']}' instead of 'cached'. "
        "ACTIVE_EMAIL_OTPS[email] is being overwritten at line 790 before the existing_session cooldown check at line 813."
    )
    assert d2["session_id"] == sess_id_1
    assert d2["otp_code"] == otp_code_1


def test_phone_otp_brute_force_lockout_and_reset():
    """Verify phone OTP locks out after 5 consecutive failed attempts, and resets on new OTP dispatch."""
    random_digits = f"{int(time.time() * 1000) % 10000000000:010d}"
    phone = f"+91{random_digits}"

    # Send OTP
    send_res = client.post("/api/v1/auth/send-otp", json={"phone": phone})
    assert send_res.status_code == 200, send_res.text
    session_id = send_res.json()["session_id"]

    # 4 failed attempts with invalid OTP
    for attempt in range(1, 5):
        fail_res = client.post("/api/v1/auth/verify-otp", json={
            "phone": phone,
            "otp": f"99990{attempt}",
            "session_id": session_id
        })
        assert fail_res.status_code == 400
        assert "Invalid OTP code" in fail_res.json()["detail"]

    # 5th failed attempt must trigger lockout
    lockout_res = client.post("/api/v1/auth/verify-otp", json={
        "phone": phone,
        "otp": "999905",
        "session_id": session_id
    })
    assert lockout_res.status_code == 400
    assert "Too many failed verification attempts" in lockout_res.json()["detail"]

    # 6th attempt while locked out must be immediately rejected even with correct code
    attempt_6 = client.post("/api/v1/auth/verify-otp", json={
        "phone": phone,
        "otp": "123456",
        "session_id": session_id
    })
    assert attempt_6.status_code == 400
    assert "Too many failed verification attempts" in attempt_6.json()["detail"]

    # Reset lockout by requesting a new OTP
    reset_send = client.post("/api/v1/auth/send-otp", json={"phone": phone})
    assert reset_send.status_code == 200
    new_sess_id = reset_send.json()["session_id"]

    # Verify with standard demo code now works
    success_verify = client.post("/api/v1/auth/verify-otp", json={
        "phone": phone,
        "otp": "123456",
        "session_id": new_sess_id
    })
    assert success_verify.status_code == 200
    assert success_verify.json()["verified"] is True


def test_email_otp_brute_force_lockout_and_reset():
    """Verify email OTP locks out after 5 consecutive failed attempts, and resets on new OTP dispatch."""
    uid = uuid.uuid4().hex[:8]
    email = f"brute_email_{uid}@example.com"

    # Send OTP
    send_res = client.post("/api/v1/auth/send-email-otp", json={"email": email})
    assert send_res.status_code == 200
    session_id = send_res.json()["session_id"]

    # 4 failed attempts
    for attempt in range(1, 5):
        fail_res = client.post("/api/v1/auth/verify-email-otp", json={
            "email": email,
            "otp_code": f"88880{attempt}",
            "session_id": session_id
        })
        assert fail_res.status_code == 400
        assert "Invalid verification code" in fail_res.json()["detail"]

    # 5th attempt triggers lockout
    lockout_res = client.post("/api/v1/auth/verify-email-otp", json={
        "email": email,
        "otp_code": "888805",
        "session_id": session_id
    })
    assert lockout_res.status_code == 400
    assert "Too many failed verification attempts" in lockout_res.json()["detail"]

    # 6th attempt while locked out is rejected
    attempt_6 = client.post("/api/v1/auth/verify-email-otp", json={
        "email": email,
        "otp_code": "123456",
        "session_id": session_id
    })
    assert attempt_6.status_code == 400
    assert "Too many failed verification attempts" in attempt_6.json()["detail"]

    # Requesting a new OTP clears the lockout
    if email in auth_module.ACTIVE_EMAIL_OTPS:
        auth_module.ACTIVE_EMAIL_OTPS[email]["created_at"] = 0

    new_send = client.post("/api/v1/auth/send-email-otp", json={"email": email})
    assert new_send.status_code == 200
    new_sess = new_send.json()["session_id"]
    new_otp = new_send.json()["otp_code"]

    # Now verify with correct code succeeds
    verify_res = client.post("/api/v1/auth/verify-email-otp", json={
        "email": email,
        "otp_code": new_otp,
        "session_id": new_sess
    })
    assert verify_res.status_code == 200
    assert verify_res.json()["verified"] is True


def test_session_id_mismatch_rejected():
    """Verify mismatched session_id is rejected on OTP verification endpoints."""
    uid = uuid.uuid4().hex[:8]
    email = f"sess_mismatch_{uid}@example.com"
    random_digits = f"{int(time.time() * 1000) % 10000000000:010d}"
    phone = f"+91{random_digits}"

    # Send email OTP
    s_email = client.post("/api/v1/auth/send-email-otp", json={"email": email})
    assert s_email.status_code == 200
    otp = s_email.json()["otp_code"]

    # Verify email OTP with wrong session_id
    v_email = client.post("/api/v1/auth/verify-email-otp", json={
        "email": email,
        "otp_code": otp,
        "session_id": "fb_em_sess_wrongsessionid123"
    })
    assert v_email.status_code == 400
    assert "mismatched" in v_email.json()["detail"].lower()

    # Send phone OTP
    s_phone = client.post("/api/v1/auth/send-otp", json={"phone": phone})
    assert s_phone.status_code == 200, s_phone.text

    # Verify phone OTP with wrong session_id
    v_phone = client.post("/api/v1/auth/verify-otp", json={
        "phone": phone,
        "otp": "123456",
        "session_id": "fb_sess_wrongsessionid123"
    })
    assert v_phone.status_code == 400
    assert "mismatched" in v_phone.json()["detail"].lower()


def test_otp_single_use_consumption():
    """Verify that an OTP session is consumed upon successful verification and cannot be reused."""
    uid = uuid.uuid4().hex[:8]
    email = f"single_use_{uid}@example.com"

    s_res = client.post("/api/v1/auth/send-email-otp", json={"email": email})
    assert s_res.status_code == 200
    otp = s_res.json()["otp_code"]
    sess_id = s_res.json()["session_id"]

    # First verification succeeds
    v1 = client.post("/api/v1/auth/verify-email-otp", json={
        "email": email,
        "otp_code": otp,
        "session_id": sess_id
    })
    assert v1.status_code == 200
    assert v1.json()["verified"] is True

    # Second verification with same OTP code and session must fail (session consumed)
    v2 = client.post("/api/v1/auth/verify-email-otp", json={
        "email": email,
        "otp_code": otp,
        "session_id": sess_id
    })
    assert v2.status_code == 400
    assert "No active email OTP session found" in v2.json()["detail"]
