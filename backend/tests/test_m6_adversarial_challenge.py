"""
backend/tests/test_m6_adversarial_challenge.py
Adversarial Challenge & Empirical Verification Suite for Milestone 6:
Authentication, Session Context, Demo Fallbacks, RoleGuard Invariants,
and Worker Self-Service IDOR Elimination.

Author: m6_challenger_1 (EMPIRICAL CHALLENGER)
Parent: orchestrator_7 (aed00c7c-728a-49b5-b43c-63398eee1f01)
"""

import os
import sys
import uuid
import hashlib
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBWorkerProfile,
    DBGovernmentOfficer,
    DBEmployerOrganization
)
from app.core.auth import create_test_firebase_jwt

client = TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Helpers
# ============================================================================

def create_test_worker(name="Test Worker", email=None, is_email_verified=True, is_phone_verified=True, status="ACTIVE"):
    suffix = uuid.uuid4().hex[:6]
    uid = f"worker_uid_{suffix}"
    email = email or f"worker_{suffix}@example.com"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name=name,
            email=email,
            phone="+91 9876543210",
            password_hash=hashlib.sha256(b"pass123").hexdigest(),
            role="WORKER",
            status=status,
            is_email_verified=is_email_verified,
            is_phone_verified=is_phone_verified
        )
        db.add(user)
        db.flush()

        profile = DBWorkerProfile(
            user_id=user.id,
            full_name=name,
            origin_state="Karnataka",
            current_state="Maharashtra",
            worker_category="Construction",
            did=f"did:passkhadam:{suffix}",
            did_state="ACTIVE",
            is_aadhaar_verified=True,
            masked_aadhaar=f"XXXX-XXXX-{suffix[:4]}"
        )
        db.add(profile)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    token = create_test_firebase_jwt(uid=uid, email=email, name=name)
    return {"user_id": user_id, "token": token, "email": email, "uid": uid}


def create_test_gov_officer():
    suffix = uuid.uuid4().hex[:6]
    uid = f"gov_uid_{suffix}"
    email = f"officer_{suffix}@maharashtra.gov.in"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="District Officer",
            email=email,
            phone="+91 9876543212",
            password_hash=hashlib.sha256(b"govpass").hexdigest(),
            role="GOVERNMENT",
            status="ACTIVE",
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(user)
        db.flush()

        officer = DBGovernmentOfficer(
            user_id=user.id,
            officer_reference_id=f"GOV-{suffix.upper()}",
            officer_name="District Officer",
            full_name="District Officer",
            official_email=email,
            designation="Labour Commissioner",
            department="Labour Welfare Dept",
            authority_level="DISTRICT",
            state="Maharashtra",
            district="Pune",
            status="ACTIVE"
        )
        db.add(officer)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    token = create_test_firebase_jwt(uid=uid, email=email, name="District Officer")
    return {"user_id": user_id, "token": token, "email": email}


# ============================================================================
# Challenge Vector 1: Unauthenticated & Tampered Auth Leakage
# ============================================================================

def test_unauthenticated_auth_me_rejects():
    """Verify that unauthenticated GET /api/v1/auth/me returns 401 and does not assume Worker #1."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
    assert "detail" in resp.json()


def test_tampered_token_auth_me_rejects():
    """Verify that tampered / invalid Bearer token returns 401 and clears unauthenticated session."""
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_tampered_token_12345"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


# ============================================================================
# Challenge Vector 2: Demo Login Presets & Role Parameter Validation
# ============================================================================

def test_demo_login_presets_all_5_roles():
    """Verify demoLogin endpoint successfully issues tokens for all 5 canonical roles."""
    roles = ["WORKER", "EMPLOYER", "GOVERNMENT", "ADMIN", "AADHAAR"]
    for r in roles:
        resp = client.post(f"/api/v1/auth/demo-login/{r}")
        assert resp.status_code == 200, f"Failed demo-login for {r}: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["role"] == r


def test_demo_login_invalid_role_rejected():
    """Verify demo-login with invalid role is rejected with HTTP 400 Bad Request."""
    resp = client.post("/api/v1/auth/demo-login/SUPERADMIN")
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "Invalid demo role" in resp.json().get("detail", "")


# ============================================================================
# Challenge Vector 3: Demo Parameter Isolation & Anti-Spoofing
# ============================================================================

def test_demo_parameter_isolation_canonical_worker():
    """Verify is_demo=True is granted to canonical demo worker only when explicitly requested or via demo token."""
    # 1. Canonical worker authenticated via standard Firebase token
    canonical_jwt = create_test_firebase_jwt(
        uid="uid_worker_demo",
        email="worker@passkhadam.org",
        name="Mohammed Uzair"
    )

    # 1a. Standard login without ?is_demo=true -> is_demo must be False
    res_no_demo = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {canonical_jwt}"})
    assert res_no_demo.status_code == 200
    assert res_no_demo.json()["is_demo"] is False

    # 1b. Standard login with explicit ?is_demo=true -> is_demo must be True
    res_with_demo = client.get("/api/v1/auth/me?is_demo=true", headers={"Authorization": f"Bearer {canonical_jwt}"})
    assert res_with_demo.status_code == 200
    assert res_with_demo.json()["is_demo"] is True

    # 2. Demo token issued via explicit demo-login endpoint
    demo_login_resp = client.post("/api/v1/auth/demo-login/WORKER")
    assert demo_login_resp.status_code == 200
    demo_token = demo_login_resp.json()["access_token"]
    res_demo_token = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {demo_token}"})
    assert res_demo_token.status_code == 200
    assert res_demo_token.json()["is_demo"] is True


def test_demo_parameter_isolation_non_demo_user_anti_spoofing():
    """Verify non-demo real account CANNOT spoof is_demo=True even if client appends ?is_demo=true."""
    worker = create_test_worker(name="Real Worker Non-Demo")
    token = worker["token"]

    res = client.get("/api/v1/auth/me?is_demo=true", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    # Server-side canonical check must reject demo status for non-canonical emails
    assert res.json()["is_demo"] is False, "Non-canonical account must not acquire is_demo=True"


# ============================================================================
# Challenge Vector 4: Dual Verification Flags for RoleGuard Enforcement
# ============================================================================

def test_dual_verification_flags_unverified_email():
    """Verify unverified email flag is accurately reported for RoleGuard blocking."""
    worker = create_test_worker(is_email_verified=False, is_phone_verified=True)
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker['token']}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_email_verified"] is False
    assert data["is_phone_verified"] is True


def test_dual_verification_flags_unverified_phone():
    """Verify unverified phone flag is accurately reported for RoleGuard blocking."""
    worker = create_test_worker(is_email_verified=True, is_phone_verified=False)
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker['token']}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_email_verified"] is True
    assert data["is_phone_verified"] is False


def test_dual_verification_flags_fully_verified():
    """Verify dual verified status is accurately reported."""
    worker = create_test_worker(is_email_verified=True, is_phone_verified=True)
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker['token']}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_email_verified"] is True
    assert data["is_phone_verified"] is True


# ============================================================================
# Challenge Vector 5: Account Suspension & Access Denial
# ============================================================================

def test_suspended_account_denied_access():
    """Verify suspended user receives HTTP 403 Forbidden on /api/v1/auth/me."""
    worker = create_test_worker(status="SUSPENDED")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker['token']}"})
    assert res.status_code == 403, f"Expected 403 for suspended user, got {res.status_code}: {res.text}"


def test_disabled_account_denied_access():
    """Verify disabled user receives HTTP 403 Forbidden on /api/v1/auth/me."""
    worker = create_test_worker(status="DISABLED")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker['token']}"})
    assert res.status_code == 403, f"Expected 403 for disabled user, got {res.status_code}: {res.text}"


# ============================================================================
# Challenge Vector 6: WorkerPortal IDOR Elimination & /me Self-Service
# ============================================================================

def test_worker_self_service_me_endpoints():
    """Verify /me endpoints resolve strictly the authenticated worker's context."""
    worker1 = create_test_worker(name="Worker Alpha")
    worker2 = create_test_worker(name="Worker Beta")

    # Worker 1 calls /profile/me
    res1 = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {worker1['token']}"})
    assert res1.status_code == 200
    assert res1.json()["full_name"] == "Worker Alpha"
    assert res1.json()["user_id"] == worker1["user_id"]

    # Worker 2 calls /profile/me
    res2 = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {worker2['token']}"})
    assert res2.status_code == 200
    assert res2.json()["full_name"] == "Worker Beta"
    assert res2.json()["user_id"] == worker2["user_id"]


def test_worker_idor_cross_access_rejected():
    """Verify Worker 1 CANNOT view or update Worker 2's profile via parameterized endpoints."""
    worker1 = create_test_worker(name="Worker Alpha")
    worker2 = create_test_worker(name="Worker Beta")

    # Worker 1 tries to GET Worker 2's profile via parameterized endpoint
    res_get = client.get(
        f"/api/v1/worker/profile/{worker2['user_id']}",
        headers={"Authorization": f"Bearer {worker1['token']}"}
    )
    assert res_get.status_code == 403, f"IDOR Vulnerability! Worker 1 was able to view Worker 2: {res_get.text}"

    # Worker 1 tries to PUT Worker 2's profile
    res_put = client.put(
        f"/api/v1/worker/profile/{worker2['user_id']}",
        headers={"Authorization": f"Bearer {worker1['token']}"},
        json={"worker_category": "Plumber"}
    )
    assert res_put.status_code == 403, f"IDOR Vulnerability! Worker 1 was able to modify Worker 2: {res_put.text}"


def test_worker_profile_me_unauthenticated_rejected():
    """Verify unauthenticated GET /api/v1/worker/profile/me returns HTTP 401."""
    res = client.get("/api/v1/worker/profile/me")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"


# ============================================================================
# Challenge Vector 7: Government Portal Profile & Role Isolation
# ============================================================================

def test_government_profile_me_authenticated_resolution():
    """Verify Government Officer /profile/me resolves officer reference ID and jurisdiction."""
    gov = create_test_gov_officer()
    res = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {gov['token']}"})
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "Maharashtra"
    assert data["district"] == "Pune"
    assert data["authority_level"] == "DISTRICT"


def test_government_profile_me_unauthenticated_rejected():
    """Verify unauthenticated GET /api/v1/government/profile/me returns 401 (never defaults to Maharashtra)."""
    res = client.get("/api/v1/government/profile/me")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"


def test_government_profile_me_role_isolation():
    """Verify Worker role attempting to access Government profile/me is rejected with 403."""
    worker = create_test_worker()
    res = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {worker['token']}"})
    assert res.status_code == 403, f"Expected 403 for Worker accessing Gov profile, got {res.status_code}"
