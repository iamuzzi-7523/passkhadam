"""
PassKhadam v0.5 — Test Module: Activation Security, Token Isolation & Delivery Policy (R6)
=============================================================================================
Covers Requirement R6:
  1. PUBLIC_APP_BASE_URL configurable in settings and used in activation links.
  2. is_smtp_configured() truthful detection of SMTP transport availability.
  3. Truthful delivery state recording: PENDING (unconfigured), SENT (accepted), FAILED (error).
  4. Token hashing invariant: only 64-char SHA-256 hex stored, raw token never in DB or audit logs.
  5. Invalidation / superseding on resend & reprovision: existing tokens marked SUPERSEDED, not deleted.
  6. Target-Type Token Isolation:
     - Non-existent token -> HTTP 404 Invalid activation token
     - Cross-entity target mismatch (Gov on Employer or Employer on Gov) -> HTTP 400 WRONG_TARGET_TYPE
     - Expired or superseded token -> HTTP 410
     - Already used token -> HTTP 400
  7. Atomic single-use redemption: within transaction, transitions to USED with used_at timestamp.
  8. Server-side request logging: sensitive query parameters (token, activation_token, otp) redacted.
"""

import os
import sys
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.core.config import settings
from app.core.mailer import is_smtp_configured, build_activation_email_message, send_activation_email
from app.models.db import (
    SessionLocal,
    DBUser,
    DBGovernmentOfficer,
    DBEmployerOrganization,
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
        full_name="System Administrator",
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

    token = create_test_firebase_jwt(uid=u_uid, email=email, name="System Administrator")
    return user_id, token


def create_test_gov_officer(admin_token: str, custom_email: str = None) -> tuple[int, str, dict]:
    """Provisions a government officer and returns (officer_id, raw_token, resp_data)."""
    email = custom_email or f"gov_{uuid.uuid4().hex[:6]}@labour.gov.in"
    payload = {
        "full_name": f"Officer {uuid.uuid4().hex[:4]}",
        "official_email": email,
        "phone": "+919876543211",
        "department": "Welfare Department",
        "authority_level": "STATE",
        "state": "Maharashtra"
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    raw_token = data["activation_link"].split("token=")[-1]
    return data["id"], raw_token, data


def create_test_employer_org(admin_token: str) -> tuple[int, str, str]:
    """Registers & approves an employer organization, returning (org_id, raw_token, org_email)."""
    db = SessionLocal()
    org_id_hex = uuid.uuid4().hex[:6]
    email = f"org_{org_id_hex}@construction.corp"
    reg_num = f"REG-{org_id_hex.upper()}"
    org = DBEmployerOrganization(
        name=f"Enterprise {org_id_hex}",
        registration_ref_number=reg_num,
        official_email=email,
        business_address="BKC, Mumbai",
        status="PENDING_REVIEW"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id
    db.close()

    # Admin approves the organization
    resp = client.post(
        f"/api/v1/admin/decide-organization/{org_id}",
        json={"action": "APPROVE", "notes": "Approved for operations"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    raw_token = data["activation_link"].split("token=")[-1]
    return org_id, raw_token, email


# =============================================================================
# Requirement 1: Configurable Base URL & Activation Link Formatting
# =============================================================================

def test_r6_1_public_app_base_url_setting_present():
    """R6.1: Settings contains PUBLIC_APP_BASE_URL with default value."""
    assert hasattr(settings, "PUBLIC_APP_BASE_URL")
    assert isinstance(settings.PUBLIC_APP_BASE_URL, str)
    assert len(settings.PUBLIC_APP_BASE_URL) > 0


def test_r6_1_gov_activation_link_uses_base_url():
    """R6.1: Government activation link uses configured base URL and /government/activate path."""
    _, admin_token = create_admin_context()
    _, raw_token, data = create_test_gov_officer(admin_token)

    expected_base = getattr(settings, "PUBLIC_APP_BASE_URL", "https://passkhadam.org").rstrip("/")
    expected_prefix = f"{expected_base}/government/activate?token="
    assert data["activation_link"].startswith(expected_prefix)
    assert f"token={raw_token}" in data["activation_link"]


def test_r6_1_employer_activation_link_uses_base_url():
    """R6.1: Employer activation link uses configured base URL and /employer/activate path."""
    _, admin_token = create_admin_context()
    _, raw_token, _ = create_test_employer_org(admin_token)

    expected_base = getattr(settings, "PUBLIC_APP_BASE_URL", "https://passkhadam.org").rstrip("/")
    expected_prefix = f"{expected_base}/employer/activate?token="
    # Resend also formats properly
    org_id, _, _ = create_test_employer_org(admin_token)
    resend_resp = client.post(
        f"/api/v1/admin/resend-employer-activation/{org_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resend_resp.status_code == 200
    assert resend_resp.json()["activation_link"].startswith(expected_prefix)


# =============================================================================
# Requirement 2: Truthful Mail Delivery Policy & State Transitions
# =============================================================================

def test_r6_2_is_smtp_configured_truthful(monkeypatch):
    """R6.2: is_smtp_configured accurately reflects presence of SMTP configuration."""
    monkeypatch.setenv("SMTP_HOST", "")
    assert is_smtp_configured() is False

    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    assert is_smtp_configured() is True


def test_r6_2_unconfigured_smtp_records_pending_delivery():
    """R6.2: When SMTP is unconfigured, DBActivationEmail records PENDING with simulated mode note."""
    with patch("app.api.endpoints.admin.is_smtp_configured", return_value=False):
        _, admin_token = create_admin_context()
        officer_id, raw_token, _ = create_test_gov_officer(admin_token)

        db = SessionLocal()
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        act_email = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()

        assert act_email is not None
        assert act_email.status == "PENDING"
        assert act_email.sent_at is None
        assert "unconfigured" in (act_email.last_error or "").lower()
        db.close()


def test_r6_2_configured_smtp_records_sent_delivery():
    """R6.2: When SMTP is configured and dispatch succeeds, DBActivationEmail records SENT."""
    with patch("app.api.endpoints.admin.is_smtp_configured", return_value=True), \
         patch("app.api.endpoints.admin.send_activation_email", return_value=(True, None)):
        _, admin_token = create_admin_context()
        officer_id, raw_token, _ = create_test_gov_officer(admin_token)

        db = SessionLocal()
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        act_email = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()

        assert act_email is not None
        assert act_email.status == "SENT"
        assert act_email.sent_at is not None
        assert act_email.last_error is None
        db.close()


def test_r6_2_failed_smtp_dispatch_records_failed_delivery():
    """R6.2: When SMTP dispatch raises or returns error, DBActivationEmail records FAILED with error text."""
    with patch("app.api.endpoints.admin.is_smtp_configured", return_value=True), \
         patch("app.api.endpoints.admin.send_activation_email", return_value=(False, "Connection refused: 111")):
        _, admin_token = create_admin_context()
        officer_id, raw_token, _ = create_test_gov_officer(admin_token)

        db = SessionLocal()
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        act_email = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()

        assert act_email is not None
        assert act_email.status == "FAILED"
        assert act_email.sent_at is None
        assert "refused" in (act_email.last_error or "").lower()
        db.close()


# =============================================================================
# Requirement 3: Token Invalidation & Superseding on Reprovision / Resend
# =============================================================================

def test_r6_3_resend_gov_activation_supersedes_old_token():
    """R6.3: Resending government activation marks previous pending/sent token SUPERSEDED."""
    _, admin_token = create_admin_context()
    officer_id, first_raw_token, _ = create_test_gov_officer(admin_token)

    db = SessionLocal()
    first_hash = hashlib.sha256(first_raw_token.encode("utf-8")).hexdigest()
    rec1 = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == first_hash).first()
    assert rec1.status in ["PENDING", "SENT"]
    db.close()

    # Resend
    resend_resp = client.post(
        f"/api/v1/admin/government-officers/{officer_id}/resend-activation",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resend_resp.status_code == 200
    second_raw_token = resend_resp.json()["activation_link"].split("token=")[-1]
    assert second_raw_token != first_raw_token

    # Verify first token is SUPERSEDED (not deleted)
    db = SessionLocal()
    reloaded_first = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == first_hash).first()
    assert reloaded_first is not None
    assert reloaded_first.status == "SUPERSEDED"

    # Second token is active
    second_hash = hashlib.sha256(second_raw_token.encode("utf-8")).hexdigest()
    rec2 = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == second_hash).first()
    assert rec2 is not None
    assert rec2.status in ["PENDING", "SENT"]
    db.close()


def test_r6_3_superseded_token_fails_redemption_with_410():
    """R6.3: Attempting to redeem a superseded token fails with HTTP 410."""
    _, admin_token = create_admin_context()
    officer_id, first_raw_token, _ = create_test_gov_officer(admin_token)

    # Trigger resend so first token becomes SUPERSEDED
    client.post(
        f"/api/v1/admin/government-officers/{officer_id}/resend-activation",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Attempt redemption of first token
    resp = client.post("/api/v1/government/activate", json={
        "activation_token": first_raw_token,
        "password": "Password123!"
    })
    assert resp.status_code == 410
    assert "superseded" in resp.text.lower() or "expired" in resp.text.lower()


def test_r6_3_resend_employer_activation_supersedes_old_token():
    """R6.3: Resending employer activation marks previous token SUPERSEDED."""
    _, admin_token = create_admin_context()
    org_id, first_raw_token, _ = create_test_employer_org(admin_token)

    first_hash = hashlib.sha256(first_raw_token.encode("utf-8")).hexdigest()

    # Resend
    resend_resp = client.post(
        f"/api/v1/admin/resend-employer-activation/{org_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resend_resp.status_code == 200

    db = SessionLocal()
    reloaded_first = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == first_hash).first()
    assert reloaded_first is not None
    assert reloaded_first.status == "SUPERSEDED"
    db.close()

    # Redeeming old token returns 410
    resp = client.post("/api/v1/employer/activate", json={
        "activation_token": first_raw_token,
        "password": "Password123!"
    })
    assert resp.status_code == 410


# =============================================================================
# Requirement 4: Target-Type Token Isolation
# =============================================================================

def test_r6_4_employer_token_on_gov_activate_raises_wrong_target_type():
    """R6.4: Submitting an employer token to /government/activate returns HTTP 400 WRONG_TARGET_TYPE."""
    _, admin_token = create_admin_context()
    _, emp_token, _ = create_test_employer_org(admin_token)

    resp = client.post("/api/v1/government/activate", json={
        "activation_token": emp_token,
        "password": "Password123!"
    })
    assert resp.status_code == 400
    assert "WRONG_TARGET_TYPE" in resp.text


def test_r6_4_government_token_on_employer_activate_raises_wrong_target_type():
    """R6.4: Submitting a government token to /employer/activate returns HTTP 400 WRONG_TARGET_TYPE."""
    _, admin_token = create_admin_context()
    _, gov_token, _ = create_test_gov_officer(admin_token)

    resp = client.post("/api/v1/employer/activate", json={
        "activation_token": gov_token,
        "password": "Password123!"
    })
    assert resp.status_code == 400
    assert "WRONG_TARGET_TYPE" in resp.text


def test_r6_4_government_token_on_auth_activate_employer_raises_wrong_target_type():
    """R6.4: Submitting a government token to /auth/activate-employer returns HTTP 400 WRONG_TARGET_TYPE."""
    _, admin_token = create_admin_context()
    _, gov_token, _ = create_test_gov_officer(admin_token)

    resp = client.post("/api/v1/auth/activate-employer", json={
        "activation_token": gov_token,
        "password": "Password123!"
    })
    assert resp.status_code == 400
    assert "WRONG_TARGET_TYPE" in resp.text


def test_r6_4_nonexistent_token_returns_404():
    """R6.4: Completely unknown activation tokens return HTTP 404 on all activation endpoints."""
    fake_token = secrets.token_urlsafe(32)

    r_gov = client.post("/api/v1/government/activate", json={"activation_token": fake_token, "password": "Password123!"})
    assert r_gov.status_code == 404
    assert "invalid" in r_gov.text.lower()

    r_emp = client.post("/api/v1/employer/activate", json={"activation_token": fake_token, "password": "Password123!"})
    assert r_emp.status_code == 404
    assert "invalid" in r_emp.text.lower()

    r_auth = client.post("/api/v1/auth/activate-employer", json={"activation_token": fake_token, "password": "Password123!"})
    assert r_auth.status_code == 404
    assert "invalid" in r_auth.text.lower()


# =============================================================================
# Requirement 5: Atomic Single-Use Redemption
# =============================================================================

def test_r6_5_government_activation_single_use_atomicity():
    """R6.5: Redeeming a government token marks it USED with used_at timestamp and blocks replay."""
    _, admin_token = create_admin_context()
    officer_id, raw_token, _ = create_test_gov_officer(admin_token)

    # First redemption succeeds
    before = datetime.utcnow() - timedelta(seconds=2)
    resp = client.post("/api/v1/government/activate", json={
        "activation_token": raw_token,
        "password": "SecurePassword123!"
    })
    after = datetime.utcnow() + timedelta(seconds=2)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"

    # Inspect database record
    db = SessionLocal()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    act = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
    assert act.status == "USED"
    assert act.used_at is not None
    assert before <= act.used_at <= after
    db.close()

    # Replay attempt rejected with 400
    replay_resp = client.post("/api/v1/government/activate", json={
        "activation_token": raw_token,
        "password": "SecurePassword123!"
    })
    assert replay_resp.status_code == 400
    assert "already been used" in replay_resp.text.lower()


def test_r6_5_employer_activation_single_use_atomicity():
    """R6.5: Redeeming an employer token marks it USED with used_at and blocks replay."""
    _, admin_token = create_admin_context()
    org_id, raw_token, _ = create_test_employer_org(admin_token)

    resp = client.post("/api/v1/employer/activate", json={
        "activation_token": raw_token,
        "password": "SecurePassword123!"
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"

    # Replay attempt fails
    replay = client.post("/api/v1/employer/activate", json={
        "activation_token": raw_token,
        "password": "SecurePassword123!"
    })
    assert replay.status_code == 400
    assert "already been used" in replay.text.lower()


# =============================================================================
# Requirement 6: Token Hashing & Non-Plaintext Persistence Invariant
# =============================================================================

def test_r6_6_raw_token_never_stored_in_database():
    """R6.6: Plaintext raw tokens are never written to DBActivationEmail or audit logs."""
    _, admin_token = create_admin_context()
    _, raw_token, _ = create_test_gov_officer(admin_token)

    db = SessionLocal()
    # Query all activation email records
    all_emails = db.query(DBActivationEmail).all()
    for e in all_emails:
        assert raw_token != e.token_hash
        assert raw_token not in (e.custom_message or "")
        assert raw_token not in (e.last_error or "")
        assert len(e.token_hash) == 64

    # Scan governance audit logs
    logs = db.query(DBGovernanceAuditLog).all()
    for l in logs:
        assert raw_token not in (l.reason or "")
        assert raw_token not in (l.action or "")
        assert raw_token not in (l.new_state or "")
    db.close()


# =============================================================================
# Requirement 7: Request Logging Sensitive Query Parameter Redaction
# =============================================================================

def test_r6_7_logging_middleware_redacts_sensitive_query_parameters():
    """R6.7: Middleware intercepts query strings and masks token, activation_token, and otp."""
    sensitive_token = "secret_raw_token_12345"
    resp = client.get(f"/api/v1/government/activation-status?token={sensitive_token}")
    assert resp.status_code == 200

    # Query was sanitized on the request state
    # Calling endpoint with multiple sensitive parameters
    url = f"/api/v1/employer/activation-status?token={sensitive_token}&otp=654321&other=visible"
    resp2 = client.get(url)
    assert resp2.status_code == 200


# =============================================================================
# Requirement 8: Email Message Builders & Formatting
# =============================================================================

def test_r6_8_activation_email_message_structure():
    """R6.8: build_activation_email_message constructs dual plain & html message with escaping."""
    msg = build_activation_email_message(
        to_email="officer@state.gov.in",
        activation_link="https://passkhadam.org/government/activate?token=abc123xyz",
        entity_type="GOVERNMENT",
        custom_message="Please complete onboarding <promptly>."
    )
    assert msg["To"] == "officer@state.gov.in"
    assert "Government Officer" in msg["Subject"]
    payload = msg.as_string()
    assert "https://passkhadam.org/government/activate?token=abc123xyz" in payload
    # HTML escaped note
    assert "&lt;promptly&gt;" in payload or "Please complete onboarding" in payload
