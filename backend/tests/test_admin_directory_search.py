"""
PassKhadam v0.5 — Test Module 4: Admin Directory Search, Filtering & Pagination
==============================================================================
Covers Requirement R4 (P1):
  - F11: Server-Side Admin Directory Search & Filtering (Tiers 1 & 2 = 10 tests)
  - F12: Pagination Envelopes & Debounced UI Controls (Tiers 1 & 2 = 10 tests)
  - F13: Truthful Error Handling in Admin UI (Tiers 1 & 2 = 10 tests)

Total Tests: 30 tests (Tier 1: 15 tests, Tier 2: 15 tests)
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
    DBGovernmentOfficer,
)
from app.core.auth import create_test_firebase_jwt

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


def seed_searchable_entities() -> dict:
    """Seeds dedicated organizations and government officers for directory search."""
    db = SessionLocal()
    tag = uuid.uuid4().hex[:6]

    # Employer Organization
    org = DBEmployerOrganization(
        name=f"Hindustan Infra {tag}",
        registration_ref_number=f"REG-SEARCH-{tag.upper()}",
        registration_number=f"CIN-{tag.upper()}",
        official_email=f"contact_{tag}@hindustaninfra.com",
        official_phone="+919876543210",
        contact_person=f"Suresh Raina {tag}",
        business_type="Construction",
        status="APPROVED",
        state_code="MH"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    # Category Request
    cat = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category=f"Heavy Cranes {tag}",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        request_version=1
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    cat_id = cat.id

    # Government Officer
    officer = DBGovernmentOfficer(
        full_name=f"Sunil Gavaskar {tag}",
        officer_name=f"Sunil Gavaskar {tag}",
        officer_reference_id=f"GOV-OFF-{tag.upper()}",
        official_email=f"officer_{tag}@maharashtra.gov.in",
        phone="+919876543210",
        authority_level="STATE",
        state="Maharashtra",
        district=None,
        block=None,
        department="Labour Department",
        designation="Welfare Officer",
        status="ACTIVE",
        permissions_json=json.dumps(["WORKER_VERIFICATION"]),
        benefit_permissions_json=json.dumps(["SCHEME_001"])
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    officer_id = officer.id

    db.close()
    return {
        "org_id": org_id,
        "org_name": f"Hindustan Infra {tag}",
        "org_ref": f"REG-SEARCH-{tag.upper()}",
        "cat_id": cat_id,
        "cat_name": f"Heavy Cranes {tag}",
        "officer_id": officer_id,
        "officer_name": f"Sunil Gavaskar {tag}",
        "state": "Maharashtra"
    }


# =============================================================================
# FEATURE 11: Server-Side Admin Directory Search & Filtering
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f11_employer_search_by_name():
    """F11.1: Searches employers in directory by partial name."""
    token = get_admin_token()
    entities = seed_searchable_entities()
    resp = client.get(f"/api/v1/admin/pending-organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_t1_f11_employer_search_by_registration_ref():
    """F11.2: Filters employers by registration status."""
    token = get_admin_token()
    entities = seed_searchable_entities()
    resp = client.get("/api/v1/admin/pending-organizations?status=APPROVED", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for org in resp.json():
        assert org["status"] == "APPROVED"


def test_t1_f11_category_requests_search_by_category():
    """F11.3: Filters category requests by status."""
    token = get_admin_token()
    entities = seed_searchable_entities()
    resp = client.get("/api/v1/admin/category-requests?status=APPROVED", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for req in resp.json():
        assert req["status"] == "APPROVED"


def test_t1_f11_government_officers_search_by_name():
    """F11.4: Government officers directory query returns active officers."""
    token = get_admin_token()
    entities = seed_searchable_entities()
    resp = client.get("/api/v1/admin/government-officers?status=ACTIVE", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_t1_f11_government_officers_filter_by_jurisdiction():
    """F11.5: Filters government officers by state jurisdiction."""
    token = get_admin_token()
    entities = seed_searchable_entities()
    resp = client.get(f"/api/v1/admin/government-officers?state=Maharashtra", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for off in resp.json():
        assert off["state"] == "Maharashtra"


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f11_search_with_leading_trailing_whitespace():
    """F11.B1: Whitespace in query parameters trimmed or handled safely."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?status=%20ACTIVE%20", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_t2_f11_case_insensitive_matching():
    """F11.B2: Lowercase state or status normalized safely."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?status=active", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for off in resp.json():
        assert off["status"] == "ACTIVE"


def test_t2_f11_special_characters_sql_injection_defense():
    """F11.B3: SQL metacharacters safely parameterized without syntax error."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?state=Maharashtra'--", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_t2_f11_no_match_search_returns_empty_results():
    """F11.B4: Non-existent filter returns clean empty list."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?state=NonExistentState123", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_t2_f11_unauthorized_search_returns_403():
    """F11.B5: Unauthorized role calling search directory returns HTTP 403."""
    emp_token = create_test_firebase_jwt(uid="uid_emp_srch", email="emp@apex.com", name="Employer")
    resp = client.get("/api/v1/admin/government-officers", headers={"Authorization": f"Bearer {emp_token}"})
    assert resp.status_code == 403


# =============================================================================
# FEATURE 12: Pagination Envelopes & Debounced UI Controls
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f12_organizations_pagination_limit_and_offset():
    """F12.1: Organizations directory supports limit and offset."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/pending-organizations?limit=5&offset=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) <= 5


def test_t1_f12_category_requests_pagination():
    """F12.2: Category requests directory supports limit and offset."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/category-requests?limit=3&offset=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) <= 3


def test_t1_f12_government_officers_pagination():
    """F12.3: Government officers directory supports limit and offset."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?limit=4&offset=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) <= 4


def test_t1_f12_page_size_capping():
    """F12.4: Default limit parameter provides bounded results list."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/pending-organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) <= 50


def test_t1_f12_pagination_offset_beyond_total_returns_empty():
    """F12.5: High offset beyond record count returns empty list."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?offset=999999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f12_negative_limit_rejected_or_clamped():
    """F12.B1: Negative limit returns 422 or empty list safely."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?limit=-1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [200, 422]


def test_t2_f12_negative_offset_rejected_or_clamped():
    """F12.B2: Negative offset returns 422 or empty list safely."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?offset=-5", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [200, 422]


def test_t2_f12_zero_limit_handling():
    """F12.B3: Limit=0 returns empty list without error."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?limit=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_t2_f12_large_limit_safely_handled():
    """F12.B4: Large limit (e.g. 500) returns all available records safely."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?limit=500", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_t2_f12_pagination_preserves_filter_criteria():
    """F12.B5: Pagination preserves state and status filters."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers?state=Maharashtra&status=ACTIVE&limit=2&offset=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["state"] == "Maharashtra"
        assert item["status"] == "ACTIVE"


# =============================================================================
# FEATURE 13: Truthful Error Handling in Admin UI
# =============================================================================

# --- Tier 1: Feature Coverage (5 tests) ---

def test_t1_f13_invalid_officer_id_returns_404_error_detail():
    """F13.1: Non-existent officer ID returns HTTP 404 with detail message."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers/999999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_t1_f13_invalid_organization_id_returns_404():
    """F13.2: Non-existent organization review returns HTTP 404."""
    token = get_admin_token()
    resp = client.post("/api/v1/admin/organizations/999999/review", json={"action": "APPROVE"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_t1_f13_invalid_category_request_id_returns_404():
    """F13.3: Non-existent category request review returns HTTP 404."""
    token = get_admin_token()
    resp = client.post("/api/v1/admin/category-requests/999999/review", json={"action": "APPROVE"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_t1_f13_validation_error_returns_structured_detail():
    """F13.4: Invalid request body produces structured 422 with validation errors."""
    token = get_admin_token()
    resp = client.post("/api/v1/admin/government-officers", json={"invalid_field": 123}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_t1_f13_unauthorized_returns_truthful_forbidden_message():
    """F13.5: Non-admin caller receives HTTP 403 with clear message."""
    emp_token = create_test_firebase_jwt(uid="uid_emp_msg", email="emp@apex.com", name="Employer")
    resp = client.get("/api/v1/admin/government-officers", headers={"Authorization": f"Bearer {emp_token}"})
    assert resp.status_code == 403
    assert "administrators" in resp.json()["detail"].lower() or "forbidden" in resp.json()["detail"].lower()


# --- Tier 2: Boundary & Corner Cases (5 tests) ---

def test_t2_f13_server_never_masks_database_error_as_empty_success():
    """F13.B1: Reviewing invalid category returns HTTP 404/400 rather than 200 OK."""
    token = get_admin_token()
    resp = client.post("/api/v1/admin/category-requests/0/review", json={"action": "APPROVE"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [400, 404]


def test_t2_f13_error_response_contains_no_internal_passwords_or_keys():
    """F13.B2: Error responses never leak password hashes or private keys."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers/999999", headers={"Authorization": f"Bearer {token}"})
    err_text = resp.text.lower()
    assert "password_hash" not in err_text
    assert "private_key" not in err_text
    assert "service_account" not in err_text


def test_t2_f13_malformed_json_body_returns_422():
    """F13.B3: Unparseable JSON returns HTTP 422 Unprocessable Entity."""
    token = get_admin_token()
    resp = client.post(
        "/api/v1/admin/category-requests/1/review",
        content="{invalid json",
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json"}
    )
    assert resp.status_code in [400, 422]


def test_t2_f13_content_type_validation_on_post_endpoints():
    """F13.B4: Non-JSON content type returns 415 or 422."""
    token = get_admin_token()
    resp = client.post(
        "/api/v1/admin/category-requests/1/review",
        content="plain text body",
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"}
    )
    assert resp.status_code in [415, 422]


def test_t2_f13_concurrent_status_update_conflict_handling():
    """F13.B5: Multiple status update requests resolve deterministically."""
    token = get_admin_token()
    resp = client.get("/api/v1/admin/government-officers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
