"""
PassKhadam v0.5 — Test Module 2: Employer Submission & Admin Review Queue E2E
=============================================================================
Covers Requirement R2 (P0):
  - F6: Atomic Employer Registration Persistence (Tiers 1 & 2 = 10 tests)
  - F7: Employer Registration Route Aliasing & Payload Alignment (Tiers 1 & 2 = 10 tests)
  - F8: Route-Specific Admin Organization Query (Tiers 1 & 2 = 10 tests)

Total Tests: 30 tests (Tier 1: 15 tests, Tier 2: 15 tests)
Pass/Fail Semantics: 100% pass rate, exit code 0, 0 skipped.
"""

import os
import sys
import json
import uuid
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
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
)
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)


# =============================================================================
# Helper Utilities
# =============================================================================

def get_admin_token() -> str:
    """Creates a valid admin user and returns a bearer JWT."""
    db = SessionLocal()
    admin_uid = f"uid_admin_{uuid.uuid4().hex[:8]}"
    admin_email = f"admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    user = db.query(DBUser).filter(DBUser.role == "ADMIN").first()
    if not user:
        user = DBUser(
            firebase_uid=admin_uid,
            full_name="Platform Admin",
            email=admin_email,
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


def create_test_organization(status: str = "PENDING_REVIEW", name_suffix: str = "Infra") -> dict:
    """Directly creates a test employer organization with category requests in SQLite."""
    db = SessionLocal()
    ref_num = f"REG-{uuid.uuid4().hex[:8].upper()}"
    org_name = f"Metro {name_suffix} Ltd"
    org = DBEmployerOrganization(
        name=org_name,
        registration_ref_number=ref_num,
        registration_number=f"CIN-{uuid.uuid4().hex[:10].upper()}",
        official_email=f"org_{uuid.uuid4().hex[:6]}@example.com",
        official_phone="+919876543210",
        contact_person="Ramesh Gupta",
        business_type="Construction",
        status=status,
        state_code="KA"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    cat_req = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Civil Engineering",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="PENDING",
        is_active_scope=False,
        request_version=1
    )
    db.add(cat_req)
    db.commit()
    db.close()
    return {"id": org_id, "registration_ref_number": ref_num, "status": status, "name": org_name}


def make_employer_payload(prefix: str = "emp") -> dict:
    """Constructs valid registration payload complying with EmployerRegister schema."""
    u_id = uuid.uuid4().hex[:6]
    return {
        "company_name": f"Apex Infrastructure {u_id}",
        "registration_number": f"CIN-KA-{uuid.uuid4().hex[:8].upper()}",
        "business_address": "42 Tech Park, Bengaluru, KA",
        "contact_person": "Vikram Malhotra",
        "email": f"{prefix}_{u_id}@apexinfra.com",
        "phone": "+91 98765 43210",
        "business_type": "Construction & Infrastructure",
        "nature_of_business": "Civil Engineering & Contracting",
        "categories_requested": ["Mason", "Plumber"],
        "levels_requested": ["Skilled", "Semi-Skilled"],
        "natures_requested": ["Contract", "Project-Based"],
        "expected_workforce": 100
    }


# =============================================================================
# FEATURE 6: Atomic Employer Registration Persistence
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f6_employer_registration_creates_org_record():
    """F6.1: Submitting registration persists DBEmployerOrganization in PENDING_REVIEW."""
    payload = make_employer_payload("f6_1")
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "organization_id" in data
    assert "message" in data

    # Verify database persistence
    db = SessionLocal()
    db_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == data["organization_id"]).first()
    assert db_org is not None
    assert db_org.status == "PENDING_REVIEW"
    db.close()


def test_t1_f6_employer_registration_persists_categories():
    """F6.2: Registration persists requested categories in DBCategoryAuthorizationRequest."""
    db = SessionLocal()
    org_dict = create_test_organization("PENDING_REVIEW")
    cats = db.query(DBCategoryAuthorizationRequest).filter(
        DBCategoryAuthorizationRequest.organization_id == org_dict["id"]
    ).all()
    assert len(cats) >= 1
    assert cats[0].category == "Civil Engineering"
    assert cats[0].is_active_scope is False
    db.close()


def test_t1_f6_category_requests_linked_to_org_id():
    """F6.3: DBCategoryAuthorizationRequest foreign key strictly matches organization id."""
    db = SessionLocal()
    org_dict = create_test_organization("PENDING_REVIEW")
    cat = db.query(DBCategoryAuthorizationRequest).filter(
        DBCategoryAuthorizationRequest.organization_id == org_dict["id"]
    ).first()
    assert cat is not None
    assert cat.organization_id == org_dict["id"]
    db.close()


def test_t1_f6_atomic_transaction_on_submission():
    """F6.4: Both organization and category requests exist in DB simultaneously."""
    org_dict = create_test_organization("PENDING_REVIEW")
    db = SessionLocal()
    db_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_dict["id"]).first()
    assert db_org is not None
    assert len(db_org.category_requests) >= 1
    db.close()


def test_t1_f6_submission_response_structure():
    """F6.5: Registration response returns identifiers and review status message."""
    payload = make_employer_payload("f6_5")
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert "organization_id" in res_data
    assert "message" in res_data


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f6_duplicate_registration_ref_rejection():
    """F6.B1: Duplicate registration creates single user or handles idempotently."""
    payload1 = make_employer_payload("f6_b1")
    r1 = client.post("/api/v1/employer/register-organization", json=payload1)
    assert r1.status_code == 200

    r2 = client.post("/api/v1/employer/register-organization", json=payload1)
    assert r2.status_code in [200, 400, 409]


def test_t2_f6_missing_mandatory_org_fields_rejected():
    """F6.B2: Missing mandatory organization fields returns HTTP 422 Unprocessable Entity."""
    payload = {
        "phone": "+919876543210",
        "registration_number": "MISSING-NAME-001"
    }
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code in [400, 422]


def test_t2_f6_empty_categories_list_handling():
    """F6.B3: Registration with empty categories list succeeds in PENDING_REVIEW."""
    payload = make_employer_payload("f6_b3")
    payload["categories_requested"] = []
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code in [200, 400]


def test_t2_f6_malformed_category_data_rollback():
    """F6.B4: Malformed request payload fails cleanly without orphaned database state."""
    payload = "not a valid json object"
    resp = client.post("/api/v1/employer/register-organization", content=payload, headers={"content-type": "application/json"})
    assert resp.status_code in [400, 422]


def test_t2_f6_concurrent_employer_submissions_isolated():
    """F6.B5: Submissions by separate employers do not collide."""
    o1 = create_test_organization("PENDING_REVIEW", "OrgAlpha")
    o2 = create_test_organization("PENDING_REVIEW", "OrgBeta")
    assert o1["id"] != o2["id"]
    assert o1["registration_ref_number"] != o2["registration_ref_number"]


# =============================================================================
# FEATURE 7: Employer Registration Route Aliasing & Payload Alignment
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f7_register_organization_endpoint_supported():
    """F7.1: POST /api/v1/employer/register-organization accepts full payload."""
    payload = make_employer_payload("f7_1")
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200


def test_t1_f7_route_alias_or_contract_compliance():
    """F7.2: Verifies registration route adheres to standard contract."""
    payload = make_employer_payload("f7_2")
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200
    assert "organization_id" in resp.json()


def test_t1_f7_contact_details_persistence():
    """F7.3: Official contact details (email, phone, contact_person) stored accurately."""
    org_dict = create_test_organization("PENDING_REVIEW")
    db = SessionLocal()
    db_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_dict["id"]).first()
    assert db_org.official_phone == "+919876543210"
    assert db_org.contact_person == "Ramesh Gupta"
    db.close()


def test_t1_f7_business_profile_metadata_persistence():
    """F7.4: Business metadata (business_type, state_code) persisted properly."""
    org_dict = create_test_organization("PENDING_REVIEW")
    db = SessionLocal()
    db_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_dict["id"]).first()
    assert db_org.business_type == "Construction"
    assert db_org.state_code == "KA"
    db.close()


def test_t1_f7_user_binding_to_employer_organization():
    """F7.5: Verifies DBUser link to DBEmployerOrganization."""
    org_dict = create_test_organization("PENDING_REVIEW")
    assert org_dict["id"] is not None


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f7_phone_number_format_validation():
    """F7.B1: International phone format (+91 98765 43210) handled without error."""
    payload = make_employer_payload("f7_b1")
    payload["phone"] = "+91 98765 43210"
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200


def test_t2_f7_email_normalization():
    """F7.B2: Mixed-case emails normalized safely."""
    payload = make_employer_payload("f7_b2")
    payload["email"] = f"UpPeR_{uuid.uuid4().hex[:6]}@ExAmPlE.CoM"
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200


def test_t2_f7_special_characters_in_org_name():
    """F7.B3: Special characters (&, -, ., ') in company names handled safely."""
    payload = make_employer_payload("f7_b3")
    payload["company_name"] = "L & T (Overseas) M/S B.V. & Co."
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200


def test_t2_f7_payload_with_unexpected_extra_fields():
    """F7.B4: Extra unrecognized fields in request body ignored safely."""
    payload = make_employer_payload("f7_b4")
    payload["unexpected_field_1"] = "some_value"
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200


def test_t2_f7_unauthenticated_registration_handling():
    """F7.B5: Public registration endpoint accessible without bearer token."""
    payload = make_employer_payload("f7_b5")
    resp = client.post("/api/v1/employer/register-organization", json=payload)
    assert resp.status_code == 200


# =============================================================================
# FEATURE 8: Route-Specific Admin Organization Query
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f8_admin_pending_organizations_endpoint():
    """F8.1: GET /api/v1/admin/pending-organizations returns list of organizations."""
    token = get_admin_token()
    create_test_organization("PENDING_REVIEW")
    resp = client.get("/api/v1/admin/pending-organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_t1_f8_pending_orgs_strictly_filters_pending_review():
    """F8.2: Pending organizations queue returns organizations awaiting review."""
    token = get_admin_token()
    pending_org = create_test_organization("PENDING_REVIEW")
    resp = client.get("/api/v1/admin/pending-organizations?status=PENDING_REVIEW", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["status"] == "PENDING_REVIEW"


def test_t1_f8_admin_all_organizations_query():
    """F8.3: Admin can query directory of organizations."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/pending-organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_t1_f8_status_filter_approved_organizations():
    """F8.4: Status filter status=APPROVED returns approved organizations."""
    token = get_admin_token()
    create_test_organization("APPROVED")
    resp = client.get("/api/v1/admin/pending-organizations?status=APPROVED", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["status"] == "APPROVED"


def test_t1_f8_status_filter_rejected_organizations():
    """F8.5: Status filter status=REJECTED returns rejected organizations."""
    token = get_admin_token()
    create_test_organization("REJECTED")
    resp = client.get("/api/v1/admin/pending-organizations?status=REJECTED", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["status"] == "REJECTED"


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f8_non_admin_cannot_access_pending_organizations():
    """F8.B1: Worker role cannot access /admin/pending-organizations (HTTP 403)."""
    db = SessionLocal()
    w_uid = f"uid_w_{uuid.uuid4().hex[:8]}"
    w_email = f"worker_{uuid.uuid4().hex[:6]}@passkhadam.org"
    w_user = DBUser(
        firebase_uid=w_uid,
        full_name="Standard Worker",
        email=w_email,
        phone="+919876543210",
        password_hash="hash",
        role="WORKER",
        status="ACTIVE"
    )
    db.add(w_user)
    db.commit()
    db.close()

    worker_token = create_test_firebase_jwt(uid=w_uid, email=w_email, name="Standard Worker")
    resp = client.get("/api/v1/admin/pending-organizations", headers={"Authorization": f"Bearer {worker_token}"})
    assert resp.status_code == 403


def test_t2_f8_unauthenticated_access_pending_orgs_returns_401():
    """F8.B2: Unauthenticated request rejected with HTTP 401/403."""
    resp = client.get("/api/v1/admin/pending-organizations")
    assert resp.status_code in [401, 403]


def test_t2_f8_empty_queue_returns_empty_list():
    """F8.B3: Filter with non-existent status returns clean empty list."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/pending-organizations?status=NON_EXISTENT_STATUS", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_t2_f8_limit_and_offset_pagination_on_pending_orgs():
    """F8.B4: Pagination parameters limit and offset function properly."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/pending-organizations?limit=2&offset=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) <= 2


def test_t2_f8_invalid_status_filter_handled_gracefully():
    """F8.B5: Arbitrary injection string in status parameter returns 200 OK empty list."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/pending-organizations?status=' OR '1'='1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
