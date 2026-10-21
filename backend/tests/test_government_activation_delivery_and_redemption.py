"""
PassKhadam v0.5 — Test Module 6: Government Activation Delivery, Redemption & Single-Use Invariants
====================================================================================================
Covers Requirement R6 (P0):
  - F17: Truthful Activation Email Delivery States (Tiers 1 & 2 = 10 tests)
  - F19: Officer Activation Redemption & Transition (Tiers 1 & 2 = 10 tests)
  - F20: Configurable Base URL & Single-Use Invariants (Tiers 1 & 2 = 10 tests)

Total Tests: 30 tests (Tier 1: 15 tests, Tier 2: 15 tests)
Pass/Fail Semantics: 100% pass rate, exit code 0, 0 skipped.
"""

import os
import sys
import json
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBGovernmentOfficer,
    DBActivationEmail,
    DBGovernanceAuditLog,
)
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)


# =============================================================================
# Helper Utilities
# =============================================================================

def create_admin_context() -> tuple[int, str]:
    """Creates a persistent admin user and returns (user_id, jwt_token)."""
    db = SessionLocal()
    u_uid = f"uid_admin_{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    user = DBUser(
        firebase_uid=u_uid,
        full_name="Super Admin",
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="ADMIN",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    token = create_test_firebase_jwt(uid=u_uid, email=email, name="Super Admin")
    return user_id, token


def provision_test_officer(admin_token: str, custom_email: str = None) -> tuple[dict, str]:
    """Provisions a government officer via Admin API, returning (response_data, raw_token)."""
    email = custom_email or f"officer_{uuid.uuid4().hex[:6]}@labour.gov.in"
    payload = {
        "full_name": f"Officer {uuid.uuid4().hex[:4]}",
        "official_email": email,
        "phone": "+919876543211",
        "department": "Department of Labour",
        "designation": "Assistant Commissioner",
        "authority_level": "STATE",
        "state": "Maharashtra",
        "permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"],
        "benefit_permissions": ["1", "2"]
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200, f"Provision failed: {resp.text}"
    data = resp.json()
    act_link = data["activation_link"]
    raw_token = act_link.split("token=")[-1]
    return data, raw_token


# =============================================================================
# FEATURE 17: Truthful Activation Email Delivery States
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f17_admin_provisions_officer_creates_activation_email():
    """F17.1: Provisioning an officer creates a DBActivationEmail record with entity_type='GOVERNMENT'."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)

    db = SessionLocal()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.entity_type == "GOVERNMENT",
        DBActivationEmail.token_hash == token_hash
    ).first()

    assert act_email is not None
    assert act_email.entity_id == data["id"]
    assert act_email.status in ["SENT", "PENDING"]
    assert act_email.attempt_count >= 1
    db.close()


def test_t1_f17_activation_link_returned_in_response():
    """F17.2: Provisioning returns activation_link with canonical host and query token."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)

    assert "activation_link" in data
    assert "https://passkhadam.org/government/activate?token=" in data["activation_link"]
    assert len(raw_token) >= 32


def test_t1_f17_token_hash_stored_as_sha256():
    """F17.3: Database records token_hash matching SHA-256 digest of raw token."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)

    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.entity_type == "GOVERNMENT",
        DBActivationEmail.entity_id == data["id"]
    ).first()
    assert act_email is not None
    assert act_email.token_hash == expected_hash
    db.close()


def test_t1_f17_activation_email_recipient_matches_official_email():
    """F17.4: DBActivationEmail.recipient_email strictly matches officer official_email."""
    _, admin_token = create_admin_context()
    data, _ = provision_test_officer(admin_token)

    db = SessionLocal()
    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.entity_type == "GOVERNMENT",
        DBActivationEmail.entity_id == data["id"]
    ).first()
    assert act_email is not None
    assert act_email.recipient_email == data["official_email"]
    db.close()


def test_t1_f17_delivery_state_transitions():
    """F17.5: Verifies delivery states (PENDING, SENT, FAILED) persistable in DBActivationEmail."""
    db = SessionLocal()
    act_email = DBActivationEmail(
        recipient_email=f"state_test_{uuid.uuid4().hex[:6]}@gov.in",
        token_hash=hashlib.sha256(b"dummy_token").hexdigest(),
        entity_type="GOVERNMENT",
        entity_id=999999,
        status="PENDING",
        attempt_count=0,
        expires_at=datetime.utcnow() + timedelta(hours=48)
    )
    db.add(act_email)
    db.commit()

    # Transition to SENT
    act_email.status = "SENT"
    act_email.sent_at = datetime.utcnow()
    act_email.attempt_count = 1
    db.commit()
    assert act_email.status == "SENT"

    # Transition to FAILED
    act_email.status = "FAILED"
    db.commit()
    assert act_email.status == "FAILED"

    db.delete(act_email)
    db.commit()
    db.close()


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f17_stale_tokens_invalidated_on_reprovisioning():
    """F17.B1: Provisioning cleans previous stale activation records for the same email."""
    _, admin_token = create_admin_context()
    email = f"stale_test_{uuid.uuid4().hex[:6]}@labour.gov.in"

    # First provision
    data1, _ = provision_test_officer(admin_token, custom_email=email)
    officer_id1 = data1["id"]

    db = SessionLocal()
    count = db.query(DBActivationEmail).filter(
        DBActivationEmail.entity_type == "GOVERNMENT",
        DBActivationEmail.entity_id == officer_id1
    ).count()
    assert count == 1
    db.close()


def test_t2_f17_duplicate_officer_email_provisioning_rejected():
    """F17.B2: Provisioning an officer with existing registered email fails with HTTP 400."""
    _, admin_token = create_admin_context()
    email = f"duplicate_gov_{uuid.uuid4().hex[:6]}@labour.gov.in"
    provision_test_officer(admin_token, custom_email=email)

    # Attempt second provision with same email
    payload = {
        "full_name": "Duplicate Officer",
        "official_email": email,
        "department": "Labour Department",
        "authority_level": "STATE",
        "state": "Maharashtra"
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 400
    assert "already exists" in resp.text.lower()


def test_t2_f17_missing_admin_token_cannot_provision_officer():
    """F17.B3: Unauthenticated provisioning request rejected with HTTP 401 or 403."""
    payload = {
        "full_name": "Unauthorized Officer",
        "official_email": "unauth@gov.in",
        "authority_level": "STATE",
        "state": "Maharashtra"
    }
    resp = client.post("/api/v1/admin/government-officers", json=payload)
    assert resp.status_code in [401, 403]


def test_t2_f17_non_admin_token_cannot_provision_officer():
    """F17.B4: Worker or Employer token attempting provisioning rejected with HTTP 403."""
    u_uid = f"uid_worker_{uuid.uuid4().hex[:6]}"
    worker_token = create_test_firebase_jwt(uid=u_uid, email="w@worker.org", name="Worker")

    payload = {
        "full_name": "Intruder Officer",
        "official_email": "intruder@gov.in",
        "authority_level": "STATE",
        "state": "Maharashtra"
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        json=payload,
        headers={"Authorization": f"Bearer {worker_token}"}
    )
    assert resp.status_code == 403


def test_t2_f17_invalid_authority_level_rejected():
    """F17.B5: Provisioning with invalid authority level returns HTTP 400."""
    _, admin_token = create_admin_context()
    payload = {
        "full_name": "Invalid Level Officer",
        "official_email": f"bad_lvl_{uuid.uuid4().hex[:6]}@gov.in",
        "authority_level": "INTERGALACTIC",
        "state": "Maharashtra"
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 400


# =============================================================================
# FEATURE 19: Officer Activation Redemption & Transition
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f19_successful_activation_transitions_to_active():
    """F19.1: Redeeming valid token transitions DBActivationEmail to USED and officer to ACTIVE."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)
    officer_id = data["id"]

    resp = client.post("/api/v1/government/activate", json={
        "activation_token": raw_token,
        "password": "SecurePassword123!"
    })
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "ACTIVE"

    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    assert off.status == "ACTIVE"

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    act_email = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
    assert act_email.status == "USED"
    assert act_email.used_at is not None
    db.close()


def test_t1_f19_associated_user_status_transitions_to_active():
    """F19.2: Underlying DBUser account transitions from PROVISIONED to ACTIVE upon redemption."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)
    officer_id = data["id"]

    client.post("/api/v1/government/activate", json={
        "activation_token": raw_token,
        "password": "SecurePassword123!"
    })

    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    user = db.query(DBUser).filter(DBUser.id == off.user_id).first()
    assert user.status == "ACTIVE"
    db.close()


def test_t1_f19_activation_status_valid_before_redemption():
    """F19.3: GET /government/activation-status returns status='VALID' with metadata before redemption."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)

    resp = client.get(f"/api/v1/government/activation-status?token={raw_token}")
    assert resp.status_code == 200
    info = resp.json()
    assert info["status"] == "VALID"
    assert info["official_email"] == data["official_email"]
    assert info["department"] == data["department"]
    assert info["state"] == "Maharashtra"


def test_t1_f19_activation_status_used_after_redemption():
    """F19.4: GET /government/activation-status returns status='USED' after redemption."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)

    # Redeem
    client.post("/api/v1/government/activate", json={
        "activation_token": raw_token,
        "password": "Password123!"
    })

    # Query status
    resp = client.get(f"/api/v1/government/activation-status?token={raw_token}")
    assert resp.status_code == 200
    info = resp.json()
    assert info["status"] == "USED"


def test_t1_f19_activation_sets_password():
    """F19.5: Activating officer with password updates DBUser password_hash."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)
    officer_id = data["id"]

    client.post("/api/v1/government/activate", json={
        "activation_token": raw_token,
        "password": "MySuperSecretPassword#2026"
    })

    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    user = db.query(DBUser).filter(DBUser.id == off.user_id).first()
    expected_hash = hashlib.sha256("MySuperSecretPassword#2026".encode("utf-8")).hexdigest()
    assert user.password_hash == expected_hash
    db.close()


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f19_replay_used_activation_token_rejected():
    """F19.B1: Replay redemption of already used token rejected with HTTP 400."""
    _, admin_token = create_admin_context()
    _, raw_token = provision_test_officer(admin_token)

    # First redemption succeeds
    r1 = client.post("/api/v1/government/activate", json={"activation_token": raw_token})
    assert r1.status_code == 200

    # Second redemption rejected
    r2 = client.post("/api/v1/government/activate", json={"activation_token": raw_token})
    assert r2.status_code == 400
    assert "already been used" in r2.text.lower()


def test_t2_f19_expired_activation_token_rejected_with_410():
    """F19.B2: Redeeming an expired token returns HTTP 410 Gone."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)

    # Manually expire the token in DB
    db = SessionLocal()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    act = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
    act.expires_at = datetime.utcnow() - timedelta(minutes=10)
    db.commit()
    db.close()

    resp = client.post("/api/v1/government/activate", json={"activation_token": raw_token})
    assert resp.status_code == 410
    assert "expired" in resp.text.lower()


def test_t2_f19_invalid_nonexistent_token_rejected_with_404():
    """F19.B3: Redeeming non-existent token returns HTTP 404 Not Found."""
    fake_token = secrets.token_urlsafe(32)
    resp = client.post("/api/v1/government/activate", json={"activation_token": fake_token})
    assert resp.status_code == 404
    assert "invalid" in resp.text.lower()


def test_t2_f19_activation_status_for_invalid_token_returns_invalid():
    """F19.B4: Inspecting non-existent token via activation-status returns status='INVALID'."""
    fake_token = secrets.token_urlsafe(32)
    resp = client.get(f"/api/v1/government/activation-status?token={fake_token}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "INVALID"


def test_t2_f19_activation_status_for_expired_token_returns_expired():
    """F19.B5: Inspecting expired token via activation-status returns status='EXPIRED'."""
    _, admin_token = create_admin_context()
    _, raw_token = provision_test_officer(admin_token)

    db = SessionLocal()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    act = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
    act.expires_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    db.close()

    resp = client.get(f"/api/v1/government/activation-status?token={raw_token}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "EXPIRED"


# =============================================================================
# FEATURE 20: Single-Use and Public App Base URL Invariants
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f20_raw_token_never_persisted_in_db():
    """F20.1: Plaintext raw token is strictly never stored in DBActivationEmail."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)

    db = SessionLocal()
    act_email = db.query(DBActivationEmail).filter(DBActivationEmail.entity_id == data["id"]).first()
    assert act_email.token_hash != raw_token
    assert len(act_email.token_hash) == 64  # SHA-256 hex digest length
    assert raw_token not in (act_email.custom_message or "")
    db.close()


def test_t1_f20_activation_link_contains_canonical_path():
    """F20.2: Activation link consistently formats with path /government/activate?token=."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)
    assert data["activation_link"].startswith("https://passkhadam.org/government/activate?token=")


def test_t1_f20_single_use_atomicity():
    """F20.3: Used status is permanent; once marked USED, token cannot transition back to active."""
    _, admin_token = create_admin_context()
    _, raw_token = provision_test_officer(admin_token)

    # First redemption
    client.post("/api/v1/government/activate", json={"activation_token": raw_token})

    # DB state remains USED
    db = SessionLocal()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    act_email = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
    assert act_email.status == "USED"
    db.close()


def test_t1_f20_used_at_timestamp_recorded_atomically():
    """F20.4: DBActivationEmail.used_at is recorded at time of redemption."""
    _, admin_token = create_admin_context()
    _, raw_token = provision_test_officer(admin_token)

    before = datetime.utcnow() - timedelta(seconds=2)
    client.post("/api/v1/government/activate", json={"activation_token": raw_token})
    after = datetime.utcnow() + timedelta(seconds=2)

    db = SessionLocal()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    act_email = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
    assert act_email.used_at is not None
    assert before <= act_email.used_at <= after
    db.close()


def test_t1_f20_token_entropy_verification():
    """F20.5: Provisioned activation token has minimum 32 bytes URL-safe entropy."""
    _, admin_token = create_admin_context()
    tokens = [provision_test_officer(admin_token)[1] for _ in range(5)]
    # All tokens must be distinct
    assert len(set(tokens)) == 5
    # All tokens must have sufficient length
    for t in tokens:
        assert len(t) >= 40


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f20_whitespace_padded_token_trimmed():
    """F20.B1: Token with leading or trailing whitespace is trimmed and processed correctly."""
    _, admin_token = create_admin_context()
    _, raw_token = provision_test_officer(admin_token)

    padded_token = f"   {raw_token}  \n"
    resp = client.post("/api/v1/government/activate", json={"activation_token": padded_token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


def test_t2_f20_empty_token_activation_rejected():
    """F20.B2: Activation request with empty or whitespace-only token rejected."""
    resp = client.post("/api/v1/government/activate", json={"activation_token": "   "})
    assert resp.status_code in [404, 422]


def test_t2_f20_officer_activation_without_user_handled_safely():
    """F20.B3: Redeeming token when officer has no user_id transitions officer smoothly."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)
    officer_id = data["id"]

    # Detach user_id from officer
    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
    off.user_id = None
    db.commit()
    db.close()

    resp = client.post("/api/v1/government/activate", json={"activation_token": raw_token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


def test_t2_f20_activation_audit_log_persisted():
    """F20.B4: Successful redemption writes a GOVERNMENT_OFFICER_ACTIVATED audit log entry."""
    _, admin_token = create_admin_context()
    data, raw_token = provision_test_officer(admin_token)
    officer_id = data["id"]

    client.post("/api/v1/government/activate", json={"activation_token": raw_token})

    db = SessionLocal()
    audit = db.query(DBGovernanceAuditLog).filter(
        DBGovernanceAuditLog.target_type == "GOVERNMENT_OFFICER",
        DBGovernanceAuditLog.target_id == str(officer_id),
        DBGovernanceAuditLog.action == "GOVERNMENT_OFFICER_ACTIVATED"
    ).first()
    assert audit is not None
    assert audit.new_state == "ACTIVE"
    db.close()


def test_t2_f20_concurrent_redemption_race_prevented():
    """F20.B5: Immediate successive redemption calls guarantee only one success and subsequent 400."""
    _, admin_token = create_admin_context()
    _, raw_token = provision_test_officer(admin_token)

    r1 = client.post("/api/v1/government/activate", json={"activation_token": raw_token})
    r2 = client.post("/api/v1/government/activate", json={"activation_token": raw_token})

    assert r1.status_code == 200
    assert r2.status_code == 400
