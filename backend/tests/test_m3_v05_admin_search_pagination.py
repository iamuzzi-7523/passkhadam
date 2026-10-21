"""
PassKhadam v0.5 — Test Suite: Milestone 3 (R4) Admin Search, Filtering & Pagination
==================================================================================
Covers:
  - Standardized PaginatedEnvelope[T] response format across all 4+ endpoints
  - Dual-mode backwards compatibility (raw List[T] when page omitted, PaginatedEnvelope when page or envelope=True provided)
  - Date range filtering (date_from, date_to) across organizations, category requests, and government officers
  - Multi-field and case-insensitive search across official_phone, category join on org name/ref, and officer block jurisdiction
  - Zero-limit backward compatibility (limit <= 0 returns [])
"""

import os
import sys
import json
import uuid
import math
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
# Fixtures & Helpers
# =============================================================================

@pytest.fixture(scope="module")
def admin_headers():
    db = SessionLocal()
    admin_user = db.query(DBUser).filter(DBUser.role == "ADMIN").first()
    if not admin_user:
        admin_uid = f"uid_m3_admin_{uuid.uuid4().hex[:8]}"
        admin_user = DBUser(
            firebase_uid=admin_uid,
            full_name="Milestone 3 Admin",
            email=f"admin_m3_{uuid.uuid4().hex[:6]}@passkhadam.org",
            phone="+919876540099",
            password_hash="hash",
            role="ADMIN",
            status="ACTIVE",
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    token = create_test_firebase_jwt(
        uid=admin_user.firebase_uid, email=admin_user.email, name=admin_user.full_name
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def seed_m3_data():
    db = SessionLocal()
    tag = uuid.uuid4().hex[:6]

    # 1. Active Organization
    org_approved = DBEmployerOrganization(
        name=f"Zenith Industrial Infra {tag}",
        registration_ref_number=f"REG-ZEN-{tag.upper()}",
        registration_number=f"CIN-ZEN-{tag.upper()}",
        official_email=f"contact_{tag}@zenithinfra.com",
        official_phone="+919123456789",
        contact_person=f"Aakash Verma {tag}",
        business_type="Manufacturing",
        status="APPROVED",
        state_code="KA",
        created_at=datetime(2026, 3, 15, 10, 0, 0),
    )
    db.add(org_approved)

    # 2. Pending Organization
    org_pending = DBEmployerOrganization(
        name=f"Horizon Builder Consortium {tag}",
        registration_ref_number=f"REG-HORIZON-{tag.upper()}",
        registration_number=f"CIN-HORIZON-{tag.upper()}",
        official_email=f"pending_{tag}@horizonbuild.com",
        official_phone="+919876543299",
        contact_person=f"Priya Nair {tag}",
        business_type="Construction",
        status="PENDING_REVIEW",
        state_code="MH",
        created_at=datetime(2026, 3, 20, 14, 30, 0),
    )
    db.add(org_pending)
    db.commit()
    db.refresh(org_approved)
    db.refresh(org_pending)

    # 3. Category Request with SQL Join link to org_approved
    cat_req_1 = DBCategoryAuthorizationRequest(
        organization_id=org_approved.id,
        category=f"Precision Welding {tag}",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        request_version=1,
        submitted_at=datetime(2026, 4, 5, 9, 0, 0),
    )
    # 4. Pending Category Request linked to org_pending
    cat_req_2 = DBCategoryAuthorizationRequest(
        organization_id=org_pending.id,
        category=f"Solar Panel Mounting {tag}",
        skill_level="Semi-Skilled",
        nature_of_employment="Project-Based",
        status="PENDING",
        is_active_scope=False,
        request_version=1,
        submitted_at=datetime(2026, 4, 10, 11, 0, 0),
    )
    db.add(cat_req_1)
    db.add(cat_req_2)
    db.commit()
    db.refresh(cat_req_1)
    db.refresh(cat_req_2)

    # 5. Government Officer with specific block jurisdiction
    officer_1 = DBGovernmentOfficer(
        full_name=f"Ramesh Officer {tag}",
        officer_name=f"Ramesh Officer {tag}",
        officer_reference_id=f"GOV-BLK-{tag.upper()}",
        official_email=f"ramesh_{tag}@welfare.gov.in",
        phone="+919876500111",
        authority_level="BLOCK",
        state="Maharashtra",
        district="Pune",
        block=f"Baramati_{tag}",
        department="Social Welfare Directorate",
        designation="Block Welfare Coordinator",
        status="ACTIVE",
        permissions_json=json.dumps(["VERIFY_WORKER"]),
        benefit_permissions_json=json.dumps(["RATION_BENEFIT", "HOUSING_SUBSIDY"]),
        created_at=datetime(2026, 2, 10, 8, 0, 0),
    )
    officer_2 = DBGovernmentOfficer(
        full_name=f"Kavita District Officer {tag}",
        officer_name=f"Kavita District Officer {tag}",
        officer_reference_id=f"GOV-DIST-{tag.upper()}",
        official_email=f"kavita_{tag}@welfare.gov.in",
        phone="+919876500222",
        authority_level="DISTRICT",
        state="Karnataka",
        district="Bengaluru Urban",
        block=None,
        department="Labour Department",
        designation="District Labour Officer",
        status="PROVISIONED",
        permissions_json=json.dumps(["VERIFY_WORKER"]),
        benefit_permissions_json=json.dumps(["HEALTHCARE_ASSISTANCE"]),
        created_at=datetime(2026, 3, 1, 12, 0, 0),
    )
    db.add(officer_1)
    db.add(officer_2)
    db.commit()
    db.refresh(officer_1)
    db.refresh(officer_2)

    # Extract all primitive attributes before closing session to avoid DetachedInstanceError
    data = {
        "tag": tag,
        "org_approved_id": org_approved.id,
        "org_approved_name": org_approved.name,
        "org_approved_ref": org_approved.registration_ref_number,
        "org_pending_id": org_pending.id,
        "org_pending_name": org_pending.name,
        "cat_req_1_id": cat_req_1.id,
        "cat_req_1_category": cat_req_1.category,
        "cat_req_2_id": cat_req_2.id,
        "cat_req_2_category": cat_req_2.category,
        "officer_1_id": officer_1.id,
        "officer_1_name": officer_1.full_name,
        "officer_2_id": officer_2.id,
        "officer_2_name": officer_2.full_name,
    }
    db.close()
    return data


# =============================================================================
# 1. Dual-Mode Pagination Envelopes vs Raw Lists
# =============================================================================

def test_organizations_paginated_envelope_mode(admin_headers, seed_m3_data):
    """When page is passed, returns standardized PaginatedEnvelope."""
    resp = client.get("/api/v1/admin/organizations?page=1&page_size=5", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, dict), "Must return dict envelope when page is provided"
    assert "total_count" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert "items" in data
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert isinstance(data["items"], list)
    assert len(data["items"]) <= 5
    assert data["total_count"] >= 1
    assert data["total_pages"] == math.ceil(data["total_count"] / 5)


def test_organizations_envelope_flag_mode(admin_headers, seed_m3_data):
    """When envelope=true is passed (even without page), returns envelope."""
    resp = client.get("/api/v1/admin/organizations?envelope=true&limit=5", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, dict), "Must return dict envelope when envelope=true"
    assert "total_count" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_organizations_raw_list_backward_compat(admin_headers, seed_m3_data):
    """When page is omitted and envelope is not true, returns raw list."""
    resp = client.get("/api/v1/admin/organizations?limit=5", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list), "Must return raw list when page is omitted"
    assert len(data) <= 5


def test_organizations_zero_limit_backward_compat(admin_headers, seed_m3_data):
    """When limit <= 0 in backward compatibility mode, returns empty list."""
    resp = client.get("/api/v1/admin/organizations?limit=0", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_pending_organizations_dual_mode(admin_headers, seed_m3_data):
    """Verifies envelope when page=1 and raw list when page omitted on pending-organizations."""
    # Envelope mode
    resp_env = client.get("/api/v1/admin/pending-organizations?page=1&page_size=10", headers=admin_headers)
    assert resp_env.status_code == 200, resp_env.text
    data_env = resp_env.json()
    assert isinstance(data_env, dict)
    assert "total_count" in data_env
    assert "items" in data_env

    # Raw list mode
    resp_raw = client.get("/api/v1/admin/pending-organizations?limit=10", headers=admin_headers)
    assert resp_raw.status_code == 200, resp_raw.text
    assert isinstance(resp_raw.json(), list)


def test_category_requests_dual_mode(admin_headers, seed_m3_data):
    """Verifies envelope when page=1 and raw list when page omitted on category-requests."""
    # Envelope mode
    resp_env = client.get("/api/v1/admin/category-requests?page=1&page_size=10", headers=admin_headers)
    assert resp_env.status_code == 200, resp_env.text
    data_env = resp_env.json()
    assert isinstance(data_env, dict)
    assert "total_count" in data_env
    assert "total_pages" in data_env
    assert "items" in data_env
    assert isinstance(data_env["items"], list)

    # Raw list mode
    resp_raw = client.get("/api/v1/admin/category-requests?limit=10", headers=admin_headers)
    assert resp_raw.status_code == 200, resp_raw.text
    assert isinstance(resp_raw.json(), list)


def test_pending_category_requests_dual_mode(admin_headers, seed_m3_data):
    """Verifies envelope when page=1 and raw list when page omitted on pending-category-requests."""
    resp_env = client.get("/api/v1/admin/pending-category-requests?page=1&page_size=5", headers=admin_headers)
    assert resp_env.status_code == 200, resp_env.text
    data_env = resp_env.json()
    assert isinstance(data_env, dict)
    assert "total_count" in data_env
    assert "items" in data_env

    resp_raw = client.get("/api/v1/admin/pending-category-requests?limit=5", headers=admin_headers)
    assert resp_raw.status_code == 200, resp_raw.text
    assert isinstance(resp_raw.json(), list)


def test_government_officers_dual_mode(admin_headers, seed_m3_data):
    """Verifies envelope when page=1 and raw list when page omitted on government-officers."""
    # Envelope mode
    resp_env = client.get("/api/v1/admin/government-officers?page=1&page_size=10", headers=admin_headers)
    assert resp_env.status_code == 200, resp_env.text
    data_env = resp_env.json()
    assert isinstance(data_env, dict)
    assert "total_count" in data_env
    assert "page" in data_env
    assert "items" in data_env

    # Raw list mode
    resp_raw = client.get("/api/v1/admin/government-officers?limit=10", headers=admin_headers)
    assert resp_raw.status_code == 200, resp_raw.text
    assert isinstance(resp_raw.json(), list)


# =============================================================================
# 2. Date Range Filtering (date_from, date_to)
# =============================================================================

def test_organizations_date_range_filtering(admin_headers, seed_m3_data):
    """Filters organizations within created_at timestamp window."""
    tag = seed_m3_data["tag"]
    # Created 2026-03-15 and 2026-03-20
    # Matching range
    resp = client.get(
        f"/api/v1/admin/organizations?search={tag}&date_from=2026-03-10T00:00:00&date_to=2026-03-25T23:59:59&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] >= 1
    found_ids = [item["id"] for item in data["items"]]
    assert seed_m3_data["org_approved_id"] in found_ids

    # Out of range (future)
    resp_future = client.get(
        f"/api/v1/admin/organizations?search={tag}&date_from=2026-05-01T00:00:00&page=1",
        headers=admin_headers,
    )
    assert resp_future.status_code == 200
    assert resp_future.json()["total_count"] == 0

    # Out of range (past)
    resp_past = client.get(
        f"/api/v1/admin/organizations?search={tag}&date_to=2026-01-01T00:00:00&page=1",
        headers=admin_headers,
    )
    assert resp_past.status_code == 200
    assert resp_past.json()["total_count"] == 0


def test_category_requests_date_range_filtering(admin_headers, seed_m3_data):
    """Filters category authorization requests on submitted_at date window."""
    tag = seed_m3_data["tag"]
    # cat_req_1 was submitted on 2026-04-05
    resp_match = client.get(
        f"/api/v1/admin/category-requests?search={tag}&date_from=2026-04-01T00:00:00&date_to=2026-04-07T23:59:59&page=1",
        headers=admin_headers,
    )
    assert resp_match.status_code == 200
    data = resp_match.json()
    assert data["total_count"] == 1
    assert data["items"][0]["id"] == seed_m3_data["cat_req_1_id"]

    # Non-matching window
    resp_none = client.get(
        f"/api/v1/admin/category-requests?search={tag}&date_from=2026-05-01T00:00:00&page=1",
        headers=admin_headers,
    )
    assert resp_none.status_code == 200
    assert resp_none.json()["total_count"] == 0


def test_government_officers_date_range_filtering(admin_headers, seed_m3_data):
    """Filters government officers on created_at date window."""
    tag = seed_m3_data["tag"]
    # officer_1 created 2026-02-10
    resp = client.get(
        f"/api/v1/admin/government-officers?search={tag}&date_from=2026-02-01T00:00:00&date_to=2026-02-15T23:59:59&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["items"][0]["id"] == seed_m3_data["officer_1_id"]


# =============================================================================
# 3. Multi-Field & Case-Insensitive Search
# =============================================================================

def test_organizations_official_phone_search(admin_headers, seed_m3_data):
    """Searches organization directory by official_phone number."""
    # Seeded phone "+919123456789"
    resp = client.get("/api/v1/admin/organizations?search=9123456789&page=1", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    matched = [o for o in data["items"] if o["id"] == seed_m3_data["org_approved_id"]]
    assert len(matched) == 1
    assert matched[0]["official_phone"] == "+919123456789"


def test_category_requests_sql_join_search_on_org_name(admin_headers, seed_m3_data):
    """Searches category requests across employer organization name via SQL outer join."""
    org_name = seed_m3_data["org_approved_name"]
    # searching org_name should match cat_req_1 without memory post-filtering
    resp = client.get(
        f"/api/v1/admin/category-requests?search={org_name}&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    matched = [c for c in data["items"] if c["id"] == seed_m3_data["cat_req_1_id"]]
    assert len(matched) == 1
    assert matched[0]["organization_name"] == org_name


def test_category_requests_sql_join_search_on_org_ref(admin_headers, seed_m3_data):
    """Searches category requests across employer organization registration_ref_number."""
    tag = seed_m3_data["tag"]
    # ref is f"REG-ZEN-{tag.upper()}"
    resp = client.get(
        f"/api/v1/admin/category-requests?search=REG-ZEN-{tag.upper()}&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    matched = [c for c in data["items"] if c["id"] == seed_m3_data["cat_req_1_id"]]
    assert len(matched) == 1


def test_category_requests_category_trade_search(admin_headers, seed_m3_data):
    """Case-insensitive search on category trade vertical name."""
    tag = seed_m3_data["tag"]
    # "Precision Welding {tag}"
    resp = client.get(
        f"/api/v1/admin/category-requests?search=precision welding {tag}&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["items"][0]["category"] == seed_m3_data["cat_req_1_category"]


def test_category_requests_multi_field_filtering(admin_headers, seed_m3_data):
    """Filters category requests by trade category, skill level, nature of employment, and status."""
    cat_category = seed_m3_data["cat_req_1_category"]
    resp = client.get(
        f"/api/v1/admin/category-requests?category={cat_category}&skill_level=Skilled&nature_of_employment=Contract&status=APPROVED&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    assert any(c["id"] == seed_m3_data["cat_req_1_id"] for c in data["items"])


def test_government_officers_block_jurisdiction_filter(admin_headers, seed_m3_data):
    """Filters government officers strictly by block jurisdiction name."""
    tag = seed_m3_data["tag"]
    block_name = f"Baramati_{tag}"
    resp = client.get(
        f"/api/v1/admin/government-officers?block={block_name}&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["items"][0]["block"] == block_name
    assert data["items"][0]["id"] == seed_m3_data["officer_1_id"]


def test_government_officers_free_text_search(admin_headers, seed_m3_data):
    """Searches government officers across name, email, department, designation, and reference ID."""
    tag = seed_m3_data["tag"]
    # Search by unique tag in officer name / ref ID
    resp = client.get(
        f"/api/v1/admin/government-officers?search={tag}&page=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 2
    officer_ids = [o["id"] for o in data["items"]]
    assert seed_m3_data["officer_1_id"] in officer_ids
    assert seed_m3_data["officer_2_id"] in officer_ids


# =============================================================================
# 4. Pagination Math & Boundary Semantics
# =============================================================================

def test_pagination_envelope_page_size_and_navigation(admin_headers, seed_m3_data):
    """Verifies page offset navigation and page size boundaries."""
    resp_p1 = client.get("/api/v1/admin/organizations?page=1&page_size=1", headers=admin_headers)
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert data_p1["page"] == 1
    assert data_p1["page_size"] == 1
    assert len(data_p1["items"]) == 1

    if data_p1["total_count"] >= 2:
        resp_p2 = client.get("/api/v1/admin/organizations?page=2&page_size=1", headers=admin_headers)
        assert resp_p2.status_code == 200
        data_p2 = resp_p2.json()
        assert data_p2["page"] == 2
        assert data_p2["items"][0]["id"] != data_p1["items"][0]["id"], "Page 2 must contain distinct items"
