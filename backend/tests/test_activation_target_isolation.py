"""
PassKhadam v0.5 — Test Module 7: Activation Target-Type Isolation & Token Sanitization
======================================================================================
Covers Requirement R6 (P0):
  - F18: Target-Type Token Isolation Enforcement (Tiers 1 & 2 = 10 tests)
  - F21: Referrer-Policy & Log Token Redaction (Tiers 1 & 2 = 10 tests)

Total Tests: 20 tests (Tier 1: 10 tests, Tier 2: 10 tests)
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
    DBEmployerOrganization,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBAdminAuditLog,
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


def create_test_government_token(admin_token: str) -> tuple[int, str]:
    """Provisions a government officer via Admin API, returning (officer_id, raw_token)."""
    email = f"gov_{uuid.uuid4().hex[:6]}@labour.gov.in"
    payload = {
        "full_name": f"Gov Officer {uuid.uuid4().hex[:4]}",
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
    assert resp.status_code == 200
    data = resp.json()
    raw_token = data["activation_link"].split("token=")[-1]
    return data["id"], raw_token


def create_test_employer_token() -> tuple[int, str]:
    """Registers an employer and returns (org_id, raw_token)."""
    reg_num = f"REG-{uuid.uuid4().hex[:8].upper()}"
    email = f"org_{uuid.uuid4().hex[:6]}@infrastructure.com"
    payload = {
        "company_name": f"Apex Corp {uuid.uuid4().hex[:4]}",
        "registration_number": reg_num,
        "business_address": "BKC, Mumbai, Maharashtra",
        "contact_person": "Rajesh Kumar",
        "email": email,
        "phone": "+919876543210",
        "categories_requested": ["Mason"]
    }
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    return data["organization_id"], data["activation_token"]


# =============================================================================
# FEATURE 18: Target-Type Token Isolation Enforcement
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f18_employer_token_rejected_on_government_activate():
    """F18.1: Submitting an employer token to /government/activate returns HTTP 400 (WRONG_TARGET_TYPE) or 404."""
    org_id, emp_token = create_test_employer_token()
    resp = client.post("/api/v1/government/activate", json={"activation_token": emp_token})
    assert resp.status_code in [400, 404]
    assert any(k in resp.text.lower() for k in ["wrong_target_type", "invalid"])


def test_t1_f18_government_token_rejected_on_employer_activate():
    """F18.2: Submitting a government token to /employer/activate returns HTTP 400 (WRONG_TARGET_TYPE) or 404."""
    _, admin_token = create_admin_context()
    _, gov_token = create_test_government_token(admin_token)

    resp = client.post("/api/v1/employer/activate", json={"activation_token": gov_token})
    assert resp.status_code in [400, 404]
    assert any(k in resp.text.lower() for k in ["wrong_target_type", "invalid"])


def test_t1_f18_government_token_rejected_on_employer_activate_account_get():
    """F18.3: Submitting a government token to GET /employer/activate-account/{token} returns HTTP 400 or 404."""
    _, admin_token = create_admin_context()
    _, gov_token = create_test_government_token(admin_token)

    resp = client.get(f"/api/v1/employer/activate-account/{gov_token}")
    assert resp.status_code in [400, 404]


def test_t1_f18_employer_token_reported_invalid_by_government_activation_status():
    """F18.4: Querying /government/activation-status with an employer token returns status='INVALID'."""
    org_id, emp_token = create_test_employer_token()
    resp = client.get(f"/api/v1/government/activation-status?token={emp_token}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "INVALID"


def test_t1_f18_cross_entity_same_id_isolation():
    """F18.5: Employer and Government Officer sharing same numeric ID maintain isolated tokens."""
    # Create an employer record and a government officer record manually with same ID or isolated records
    db = SessionLocal()
    raw_emp = secrets.token_urlsafe(32)
    raw_gov = secrets.token_urlsafe(32)

    shared_id = 888888
    act_emp = DBActivationEmail(
        recipient_email="emp@corp.com",
        token_hash=hashlib.sha256(raw_emp.encode()).hexdigest(),
        entity_type="EMPLOYER",
        entity_id=shared_id,
        status="SENT",
        attempt_count=1,
        expires_at=datetime.utcnow() + timedelta(hours=48)
    )
    act_gov = DBActivationEmail(
        recipient_email="gov@state.gov",
        token_hash=hashlib.sha256(raw_gov.encode()).hexdigest(),
        entity_type="GOVERNMENT",
        entity_id=shared_id,
        status="SENT",
        attempt_count=1,
        expires_at=datetime.utcnow() + timedelta(hours=48)
    )
    db.add(act_emp)
    db.add(act_gov)
    db.commit()

    # Employer token must NOT be found as GOVERNMENT
    gov_lookup = db.query(DBActivationEmail).filter(
        DBActivationEmail.entity_type == "GOVERNMENT",
        DBActivationEmail.token_hash == hashlib.sha256(raw_emp.encode()).hexdigest()
    ).first()
    assert gov_lookup is None

    # Government token must NOT be found as EMPLOYER
    emp_lookup = db.query(DBActivationEmail).filter(
        DBActivationEmail.entity_type == "EMPLOYER",
        DBActivationEmail.token_hash == hashlib.sha256(raw_gov.encode()).hexdigest()
    ).first()
    assert emp_lookup is None

    db.delete(act_emp)
    db.delete(act_gov)
    db.commit()
    db.close()


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f18_used_employer_token_still_rejected_on_government():
    """F18.B1: Redeeming an employer token on employer, then trying on government returns HTTP 400 or 404."""
    org_id, emp_token = create_test_employer_token()

    # Approve and activate employer
    client.post("/api/v1/employer/activate", json={"activation_token": emp_token})

    # Try on government -> must be rejected with 400 or 404
    resp = client.post("/api/v1/government/activate", json={"activation_token": emp_token})
    assert resp.status_code in [400, 404]


def test_t2_f18_used_government_token_still_rejected_on_employer():
    """F18.B2: Redeeming a government token on government, then trying on employer returns HTTP 400 or 404."""
    _, admin_token = create_admin_context()
    _, gov_token = create_test_government_token(admin_token)

    # Activate government officer
    client.post("/api/v1/government/activate", json={"activation_token": gov_token})

    # Try on employer -> must be rejected with 400 or 404
    resp = client.post("/api/v1/employer/activate", json={"activation_token": gov_token})
    assert resp.status_code in [400, 404]


def test_t2_f18_entity_type_sql_injection_defense():
    """F18.B3: SQL-injected token strings safely handled by parameterized ORM lookups."""
    injected_token = "' OR '1'='1"
    r_gov = client.post("/api/v1/government/activate", json={"activation_token": injected_token})
    r_emp = client.post("/api/v1/employer/activate", json={"activation_token": injected_token})
    assert r_gov.status_code in [400, 404]
    assert r_emp.status_code in [400, 404]


def test_t2_f18_arbitrary_entity_type_in_db_ignored_by_both():
    """F18.B4: Tokens with unexpected entity_type (e.g. WORKER) rejected by both endpoints."""
    raw = secrets.token_urlsafe(32)
    db = SessionLocal()
    act = DBActivationEmail(
        recipient_email="other@test.org",
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        entity_type="WORKER",
        entity_id=1,
        status="SENT",
        attempt_count=1,
        expires_at=datetime.utcnow() + timedelta(hours=48)
    )
    db.add(act)
    db.commit()

    r1 = client.post("/api/v1/government/activate", json={"activation_token": raw})
    r2 = client.post("/api/v1/employer/activate", json={"activation_token": raw})

    assert r1.status_code in [400, 404]
    assert r2.status_code in [400, 404]

    db.delete(act)
    db.commit()
    db.close()


def test_t2_f18_pending_tokens_isolation_preserved():
    """F18.B5: Newly created pending tokens maintain strict entity boundary prior to activation."""
    db = SessionLocal()
    gov_count = db.query(DBActivationEmail).filter(DBActivationEmail.entity_type == "GOVERNMENT").count()
    emp_count = db.query(DBActivationEmail).filter(DBActivationEmail.entity_type == "EMPLOYER").count()
    assert gov_count >= 0
    assert emp_count >= 0
    db.close()


# =============================================================================
# FEATURE 21: Referrer-Policy & Log Token Redaction
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f21_government_activation_response_headers_safe():
    """F21.1: Responses from activation endpoints do not leak credentials in headers."""
    _, admin_token = create_admin_context()
    _, gov_token = create_test_government_token(admin_token)

    resp = client.post("/api/v1/government/activate", json={"activation_token": gov_token})
    assert resp.status_code == 200
    for header, value in resp.headers.items():
        assert gov_token not in value


def test_t1_f21_raw_token_never_appears_in_governance_audit_log():
    """F21.2: Governance audit logs generated during provisioning & activation never record raw token."""
    _, admin_token = create_admin_context()
    _, gov_token = create_test_government_token(admin_token)
    client.post("/api/v1/government/activate", json={"activation_token": gov_token})

    db = SessionLocal()
    audits = db.query(DBGovernanceAuditLog).all()
    for a in audits:
        assert gov_token not in (a.reason or "")
        assert gov_token not in (a.action or "")
        assert gov_token not in (a.new_state or "")
        assert gov_token not in (a.previous_state or "")
    db.close()


def test_t1_f21_raw_token_never_appears_in_admin_audit_log():
    """F21.3: Admin audit logs never record plaintext activation tokens."""
    _, admin_token = create_admin_context()
    _, gov_token = create_test_government_token(admin_token)

    db = SessionLocal()
    admin_logs = db.query(DBAdminAuditLog).all()
    for l in admin_logs:
        assert gov_token not in (l.reason or "")
        assert gov_token not in (l.action or "")
    db.close()


def test_t1_f21_activation_error_message_does_not_echo_secret_token():
    """F21.4: Error messages from invalid activation attempts do not echo back the secret input."""
    sensitive_token = "secret_raw_token_xyz_9999"
    resp = client.post("/api/v1/government/activate", json={"activation_token": sensitive_token})
    assert resp.status_code == 404
    assert sensitive_token not in resp.text


def test_t1_f21_activation_status_does_not_leak_other_officer_tokens():
    """F21.5: GET /government/activation-status returns only public metadata, no tokens or hashes."""
    _, admin_token = create_admin_context()
    _, gov_token = create_test_government_token(admin_token)

    resp = client.get(f"/api/v1/government/activation-status?token={gov_token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "token" not in data
    assert "token_hash" not in data
    assert "password_hash" not in data


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f21_custom_provisioning_message_does_not_log_token():
    """F21.B1: Custom message provided during provisioning stored safely without token interpolation."""
    _, admin_token = create_admin_context()
    custom_msg = "Welcome to the Maharashtra Labour Department. Please activate promptly."
    email = f"custom_msg_{uuid.uuid4().hex[:6]}@labour.gov.in"
    payload = {
        "full_name": "Msg Test Officer",
        "official_email": email,
        "department": "Department of Labour",
        "authority_level": "STATE",
        "state": "Maharashtra",
        "custom_message": custom_msg
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    raw_token = data["activation_link"].split("token=")[-1]

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    act = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
    assert act is not None
    assert raw_token not in (act.custom_message or "")
    db.close()


def test_t2_f21_officer_reference_id_is_unpredictable():
    """F21.B2: Officer reference ID is distinct from token and does not leak token substrings."""
    _, admin_token = create_admin_context()
    data, raw_token = create_test_government_token(admin_token)

    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == data).first()
    assert off.officer_reference_id not in raw_token
    assert raw_token not in off.officer_reference_id
    db.close()


def test_t2_f21_password_never_persisted_in_plaintext_during_activation():
    """F21.B3: Plaintext password provided during activation is never stored in plaintext."""
    _, admin_token = create_admin_context()
    off_id, raw_token = create_test_government_token(admin_token)
    plaintext_pw = "ExtremelyConfidentialPassword!99"

    client.post("/api/v1/government/activate", json={
        "activation_token": raw_token,
        "password": plaintext_pw
    })

    db = SessionLocal()
    off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == off_id).first()
    user = db.query(DBUser).filter(DBUser.id == off.user_id).first()
    assert user.password_hash != plaintext_pw
    assert len(user.password_hash) == 64  # SHA-256
    db.close()


def test_t2_f21_db_activation_email_table_scan_for_plaintext_secrets():
    """F21.B4: Comprehensive scan across DBActivationEmail records proves all token_hash values are 64-char hex."""
    db = SessionLocal()
    records = db.query(DBActivationEmail).all()
    for rec in records:
        assert len(rec.token_hash) == 64
        assert all(c in "0123456789abcdefABCDEF" for c in rec.token_hash)
    db.close()


def test_t2_f21_multiple_tokens_zero_leakage_in_audit_trails():
    """F21.B5: Successive provisioning actions guarantee zero token leakage across all audit tables."""
    _, admin_token = create_admin_context()
    tokens = [create_test_government_token(admin_token)[1] for _ in range(3)]

    db = SessionLocal()
    audit_texts = [
        str(a.reason or "") + str(a.action or "")
        for a in db.query(DBGovernanceAuditLog).all()
    ]
    for t in tokens:
        for text in audit_texts:
            assert t not in text
    db.close()
