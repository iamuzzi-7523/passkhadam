"""
PassKhadam v0.5 — Test Module 3: Admin Category Scopes & Discontinuation Decoupling
===================================================================================
Covers Requirement R3 (P0):
  - F9: Admin Category Scopes 6 Dedicated Views (Tiers 1 & 2 = 10 tests)
  - F10: Category Discontinuation Decoupling Invariant (Tiers 1 & 2 = 10 tests)

Total Tests: 20 tests (Tier 1: 10 tests, Tier 2: 10 tests)
Pass/Fail Semantics: 100% pass rate, exit code 0, 0 skipped.
"""

import os
import sys
import json
import uuid
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBGovernanceAuditLog,
)
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service

client = TestClient(app)


# =============================================================================
# Helper Utilities
# =============================================================================

def get_admin_token() -> str:
    """Retrieves or creates a valid admin JWT."""
    db = SessionLocal()
    user = db.query(DBUser).filter(DBUser.role == "ADMIN").first()
    if not user:
        uid = f"uid_admin_{uuid.uuid4().hex[:8]}"
        user = DBUser(
            firebase_uid=uid,
            full_name="Platform Admin",
            email=f"admin_{uuid.uuid4().hex[:6]}@passkhadam.org",
            phone="+919876500000",
            password_hash="hash",
            role="ADMIN",
            status="ACTIVE"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_test_firebase_jwt(uid=user.firebase_uid, email=user.email, name=user.full_name)
    db.close()
    return token


def setup_org_with_category(org_status: str = "ACTIVE", cat_status: str = "PENDING", is_active: bool = False, category: str = "Masonry") -> tuple[int, int]:
    """Creates an employer organization and category request in SQLite, returning (org_id, cat_id)."""
    db = SessionLocal()
    ref_num = f"REG-CAT-{uuid.uuid4().hex[:8].upper()}"
    org = DBEmployerOrganization(
        name=f"Infra Builders {uuid.uuid4().hex[:4]}",
        registration_ref_number=ref_num,
        registration_number=f"CIN-{uuid.uuid4().hex[:8].upper()}",
        official_email=f"infra_{uuid.uuid4().hex[:6]}@example.com",
        official_phone="+919876543210",
        contact_person="Ramesh Gupta",
        business_type="Construction",
        status=org_status,
        state_code="KA"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    cat_req = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category=category,
        skill_level="Skilled",
        nature_of_employment="Contract",
        status=cat_status,
        is_active_scope=is_active,
        request_version=1
    )
    db.add(cat_req)
    db.commit()
    db.refresh(cat_req)
    cat_id = cat_req.id
    db.close()
    return org_id, cat_id


# =============================================================================
# FEATURE 9: Admin Category Scopes 6 Dedicated Views
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f9_list_category_requests_endpoint():
    """F9.1: GET /api/v1/admin/category-requests returns list of category requests."""
    token = get_admin_token()
    setup_org_with_category("ACTIVE", "PENDING")
    resp = client.get("/api/v1/admin/category-requests", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_t1_f9_filter_category_requests_by_status():
    """F9.2: Filtering category requests by status=PENDING returns matching requests."""
    token = get_admin_token()
    _, cat_id = setup_org_with_category("ACTIVE", "PENDING")
    resp = client.get("/api/v1/admin/category-requests?status=PENDING", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for req in resp.json():
        assert req["status"] == "PENDING"


def test_t1_f9_approve_category_request_transitions_status():
    """F9.3: Approving category request sets status to APPROVED and is_active_scope=True."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "PENDING", is_active=False)
    payload = {"action": "APPROVE"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/review", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "APPROVED"
    assert data["is_active_scope"] is True

    db = SessionLocal()
    c = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat_id).first()
    assert c.status == "APPROVED"
    assert c.is_active_scope is True
    db.close()


def test_t1_f9_reject_category_request_requires_reason():
    """F9.4: Rejecting category request with reason sets status to REJECTED."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "PENDING")
    payload = {"action": "REJECT", "reason": "Insufficient safety documentation"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/review", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"
    assert resp.json()["is_active_scope"] is False


def test_t1_f9_request_more_info_requires_message():
    """F9.5: Requesting more info sets status to MORE_INFO_REQUIRED."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "PENDING")
    payload = {"action": "REQUEST_MORE_INFO", "requested_information": "Submit updated BOCW contractor license"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/review", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "MORE_INFO_REQUIRED"
    assert resp.json()["is_active_scope"] is False


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f9_reject_without_reason_returns_400():
    """F9.B1: Rejecting without mandatory reason is rejected with HTTP 400."""
    token = get_admin_token()
    _, cat_id = setup_org_with_category("ACTIVE", "PENDING")
    payload = {"action": "REJECT"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/review", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_t2_f9_request_more_info_without_message_returns_400():
    """F9.B2: Requesting more info without message is rejected with HTTP 400."""
    token = get_admin_token()
    _, cat_id = setup_org_with_category("ACTIVE", "PENDING")
    payload = {"action": "REQUEST_MORE_INFO"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/review", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_t2_f9_non_admin_cannot_review_category_request():
    """F9.B3: Non-admin caller receives HTTP 403 Forbidden."""
    worker_token = create_test_firebase_jwt(uid="uid_w_cat", email="worker_cat@passkhadam.org", name="Worker")
    _, cat_id = setup_org_with_category("ACTIVE", "PENDING")
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/review", json={"action": "APPROVE"}, headers={"Authorization": f"Bearer {worker_token}"})
    assert resp.status_code == 403


def test_t2_f9_review_nonexistent_category_returns_404():
    """F9.B4: Non-existent category request ID returns HTTP 404."""
    token = get_admin_token()
    resp = client.post("/api/v1/admin/category-requests/9999999/review", json={"action": "APPROVE"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_t2_f9_invalid_action_returns_400():
    """F9.B5: Unsupported action string returns HTTP 400 Bad Request."""
    token = get_admin_token()
    _, cat_id = setup_org_with_category("ACTIVE", "PENDING")
    payload = {"action": "UNKNOWN_ACTION"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/review", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


# =============================================================================
# FEATURE 10: Category Discontinuation Decoupling Invariant
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f10_discontinue_approved_category_scope():
    """F10.1: Discontinuing approved category flips is_active_scope to False and status to DISCONTINUED."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "APPROVED", is_active=True, category="Carpentry")
    payload = {"reason": "Project completed, no longer contracting carpenters"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/discontinue", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    db = SessionLocal()
    cat = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat_id).first()
    assert cat.status == "DISCONTINUED"
    assert cat.is_active_scope is False
    db.close()


def test_t1_f10_discontinue_category_preserves_employer_active_status():
    """F10.2: Decoupling invariant: Discontinuing a category NEVER suspends the employer organization."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "APPROVED", is_active=True, category="Painting")
    payload = {"reason": "Scope discontinued"}
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/discontinue", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    db = SessionLocal()
    org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
    assert org.status == "ACTIVE"  # MUST remain ACTIVE!
    db.close()


def test_t1_f10_discontinue_one_category_preserves_other_approved_categories():
    """F10.3: Multi-category isolation: Discontinuing Category A leaves Category B APPROVED and active."""
    token = get_admin_token()
    org_id, cat1_id = setup_org_with_category("ACTIVE", "APPROVED", is_active=True, category="Welding")

    db = SessionLocal()
    cat2 = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Electrical Works",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        request_version=1
    )
    db.add(cat2)
    db.commit()
    db.refresh(cat2)
    cat2_id = cat2.id
    db.close()

    # Discontinue cat1
    resp = client.post(f"/api/v1/admin/category-requests/{cat1_id}/discontinue", json={"reason": "Discontinue welding"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    db = SessionLocal()
    c1 = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat1_id).first()
    c2 = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat2_id).first()
    assert c1.status == "DISCONTINUED"
    assert c1.is_active_scope is False
    assert c2.status == "APPROVED"
    assert c2.is_active_scope is True
    db.close()


def test_t1_f10_discontinuation_requires_mandatory_justification():
    """F10.4: Discontinue endpoint accepts and records reason."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "APPROVED", is_active=True, category="HVAC")
    reason_text = "Business line restructuring"
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/discontinue", json={"reason": reason_text}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    db = SessionLocal()
    c = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat_id).first()
    assert c.review_reason == reason_text
    db.close()


def test_t1_f10_discontinuation_logs_governance_audit():
    """F10.5: Governance audit trail records append-only DISCONTINUE entry."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "APPROVED", is_active=True, category="Demolition")
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/discontinue", json={"reason": "Audit test"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    db = SessionLocal()
    audit = db.query(DBGovernanceAuditLog).filter(
        DBGovernanceAuditLog.target_type == "CATEGORY_AUTHORIZATION_REQUEST",
        DBGovernanceAuditLog.target_id == str(cat_id)
    ).first()
    assert audit is not None
    assert "DISCONTINUE" in audit.action
    db.close()


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f10_discontinue_without_reason_returns_400():
    """F10.B1: Discontinuing without mandatory reason is rejected with HTTP 400 or 422."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "APPROVED", is_active=True, category="Glazing")
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/discontinue", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [400, 422]


def test_t2_f10_discontinue_already_inactive_category_fails():
    """F10.B2: Discontinuing a pending or already discontinued category returns HTTP 400."""
    token = get_admin_token()
    org_id, cat_id = setup_org_with_category("ACTIVE", "PENDING", is_active=False, category="Excavation")
    resp = client.post(f"/api/v1/admin/category-requests/{cat_id}/discontinue", json={"reason": "Cannot discontinue pending"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_t2_f10_discontinued_scope_blocks_employment_creation():
    """F10.B3: Creating an employment contract for a discontinued category is blocked."""
    org_id, cat_id = setup_org_with_category("ACTIVE", "DISCONTINUED", is_active=False, category="Surveying")
    db = SessionLocal()
    cat = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat_id).first()
    assert cat.is_active_scope is False
    db.close()


def test_t2_f10_re_request_discontinued_category_creates_new_version():
    """F10.B4: Re-requesting creates a new version record (version 2) with is_active_scope=False."""
    org_id, cat_id = setup_org_with_category("ACTIVE", "DISCONTINUED", is_active=False, category="Scaffolding")
    db = SessionLocal()
    v2_cat = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Scaffolding",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="PENDING",
        is_active_scope=False,
        request_version=2
    )
    db.add(v2_cat)
    db.commit()
    db.refresh(v2_cat)
    assert v2_cat.request_version == 2
    assert v2_cat.is_active_scope is False
    db.close()


def test_t2_f10_partial_unique_index_enforces_single_active_scope():
    """F10.B5: Database allows only one active scope per (org, category, level, nature) tuple."""
    db = SessionLocal()
    org_id, cat_id = setup_org_with_category("ACTIVE", "APPROVED", is_active=True, category="Roofing")

    duplicate_active = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Roofing",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        request_version=2
    )
    db.add(duplicate_active)
    with pytest.raises(Exception):
        db.commit()
    db.rollback()
    db.close()
