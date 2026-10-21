"""
PassKhadam v0.5 — Milestone 2 (R2 & R3) Adversarial Challenge Test Suite
========================================================================
Adversarial stress harness authored by m2_v05_challenger_1.
Validates:
1. Route Aliases Equivalence (/register vs /onboard vs /register-organization)
2. Response field guarantees: status: PENDING_REVIEW & verification_status: PENDING_REVIEW
3. Atomic rollback: zero orphaned DBEmployerOrganization records on category failure
4. Duplicate submission conflict handling (HTTP 409 and clear detail messages)
5. Payload field normalization matrix (whitespace, casing, comma-separated categories, aliases)
6. Decoupling invariant: category suspension/discontinuation preserves employer ACTIVE status
7. Decoupled Admin review queues strictly filtering PENDING_REVIEW
"""

import os
import sys
import uuid
import hashlib
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBActivationEmail,
    DBGovernanceAuditLog,
)
from app.models.schemas import EmployerRegister
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)


# =============================================================================
# Adversarial Helper Fixtures & Context Utilities
# =============================================================================

def get_admin_token() -> str:
    """Creates or retrieves a platform admin user and returns a valid Bearer JWT."""
    db: Session = SessionLocal()
    admin_user = db.query(DBUser).filter(DBUser.role == "ADMIN").first()
    if not admin_user:
        admin_uid = f"uid_adv_admin_{uuid.uuid4().hex[:8]}"
        admin_email = f"adv_admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
        admin_user = DBUser(
            firebase_uid=admin_uid,
            full_name="Adversarial Admin",
            email=admin_email,
            phone="+919876500000",
            password_hash=hashlib.sha256("admin_pass".encode()).hexdigest(),
            role="ADMIN",
            status="ACTIVE",
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    token = create_test_firebase_jwt(uid=admin_user.firebase_uid, email=admin_user.email, name=admin_user.full_name)
    db.close()
    return token


def make_unique_employer_payload(tag: str = "adv") -> dict:
    """Generates unique valid employer registration payload."""
    uid = uuid.uuid4().hex[:8]
    return {
        "company_name": f"Adversarial Construction {tag}_{uid} Ltd",
        "registration_number": f"CIN-KA-{uid.upper()}",
        "business_address": f"{uid} Industrial Zone, Bengaluru, KA",
        "contact_person": f"Officer {uid}",
        "email": f"corp_{tag}_{uid}@example.com",
        "phone": "+91 98765 43210",
        "business_type": "Construction & Infrastructure",
        "nature_of_business": "Civil Engineering & Contracting",
        "categories_requested": ["Mason", "Electrician"],
        "levels_requested": ["Skilled"],
        "natures_requested": ["Contract"],
        "expected_workforce": 120
    }


# =============================================================================
# 1. ROUTE ALIASES EQUIVALENCE & RESPONSE INTEGRITY
# =============================================================================

def test_adv_route_aliases_register_and_onboard_identical_payloads():
    """Verify POST /api/v1/employer/register and POST /api/v1/employer/onboard

    both accept identical payloads and return 200 OK.
    """
    payload_reg = make_unique_employer_payload("route_reg")
    resp_reg = client.post("/api/v1/employer/register", json=payload_reg)
    assert resp_reg.status_code == 200, f"Failed at /register: {resp_reg.text}"

    payload_onb = make_unique_employer_payload("route_onb")
    resp_onb = client.post("/api/v1/employer/onboard", json=payload_onb)
    assert resp_onb.status_code == 200, f"Failed at /onboard: {resp_onb.text}"


def test_adv_route_aliases_status_and_verification_status_fields():
    """Verify that both aliases return status: PENDING_REVIEW

    and verification_status: PENDING_REVIEW in top-level JSON response.
    """
    for route in ["/api/v1/employer/register", "/api/v1/employer/onboard", "/api/v1/employer/register-organization"]:
        payload = make_unique_employer_payload("status_chk")
        resp = client.post(route, json=payload)
        assert resp.status_code == 200, f"Failed at {route}: {resp.text}"
        data = resp.json()

        assert "status" in data, f"Missing 'status' key in response from {route}"
        assert data["status"] == "PENDING_REVIEW", f"Expected PENDING_REVIEW, got {data['status']}"

        assert "verification_status" in data, f"Missing 'verification_status' key in response from {route}"
        assert data["verification_status"] == "PENDING_REVIEW", f"Expected PENDING_REVIEW, got {data['verification_status']}"

        # Verify underlying DB model
        db: Session = SessionLocal()
        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == data["organization_id"]).first()
        assert org is not None
        assert org.status == "PENDING_REVIEW"
        assert org.verification_status == "PENDING_REVIEW"
        db.close()


def test_adv_route_aliases_persists_initial_pending_categories():
    """Verify that registration via route aliases creates DBCategoryAuthorizationRequest

    with status='PENDING' and is_active_scope=False.
    """
    payload = make_unique_employer_payload("cat_scope")
    payload["categories_requested"] = ["Plumber", "HVAC Technician"]
    resp = client.post("/api/v1/employer/register", json=payload)
    assert resp.status_code == 200
    org_id = resp.json()["organization_id"]

    db: Session = SessionLocal()
    cats = db.query(DBCategoryAuthorizationRequest).filter(
        DBCategoryAuthorizationRequest.organization_id == org_id
    ).all()
    assert len(cats) == 2
    for c in cats:
        assert c.status == "PENDING"
        assert c.verification_status == "PENDING"
        assert c.is_active_scope is False
        assert c.request_version == 1
    db.close()


# =============================================================================
# 2. ATOMIC ROLLBACK: ZERO ORPHANED ORGANIZATIONS IN SQLITE
# =============================================================================

def test_adv_atomic_rollback_on_category_creation_failure():
    """Simulate a failure during category authorization request creation

    and prove that the entire transaction is rolled back, leaving ZERO orphaned
    DBEmployerOrganization and ZERO DBUser records.
    """
    payload = make_unique_employer_payload("atomic_fail")
    clean_email = payload["email"].lower().strip()
    reg_num = payload["registration_number"].strip()

    # Pre-condition check: records do not exist
    db: Session = SessionLocal()
    assert db.query(DBUser).filter(DBUser.email == clean_email).first() is None
    assert db.query(DBEmployerOrganization).filter(
        DBEmployerOrganization.registration_ref_number == reg_num
    ).first() is None
    db.close()

    # Force an exception inside the transaction during category authorization request insertion
    with patch("app.api.endpoints.employer.DBCategoryAuthorizationRequest", side_effect=RuntimeError("Simulated Category Creation Failure")):
        resp = client.post("/api/v1/employer/register", json=payload)
        # Should return 500 transaction failure
        assert resp.status_code == 500
        assert "Database transaction failure" in resp.json()["detail"]

    # Post-condition verification: ZERO orphaned records in SQLite
    db = SessionLocal()
    org_after = db.query(DBEmployerOrganization).filter(
        DBEmployerOrganization.registration_ref_number == reg_num
    ).first()
    user_after = db.query(DBUser).filter(DBUser.email == clean_email).first()
    act_email_after = db.query(DBActivationEmail).filter(
        DBActivationEmail.recipient_email == clean_email
    ).first()

    assert org_after is None, "ATOMIC ROLLBACK FAILED: Orphaned DBEmployerOrganization found in SQLite!"
    assert user_after is None, "ATOMIC ROLLBACK FAILED: Orphaned DBUser found in SQLite!"
    assert act_email_after is None, "ATOMIC ROLLBACK FAILED: Orphaned DBActivationEmail found in SQLite!"
    db.close()


def test_adv_atomic_rollback_on_commit_integrity_error():
    """Simulate an IntegrityError during db.commit() and verify complete rollback."""
    payload = make_unique_employer_payload("commit_fail")
    reg_num = payload["registration_number"].strip()

    with patch.object(Session, "commit", side_effect=Exception("Simulated SQLite Lock/Constraint Failure")):
        resp = client.post("/api/v1/employer/onboard", json=payload)
        assert resp.status_code == 500
        assert "Database transaction failure" in resp.json()["detail"]

    # Assert no partial organization was committed
    db = SessionLocal()
    org = db.query(DBEmployerOrganization).filter(
        DBEmployerOrganization.registration_ref_number == reg_num
    ).first()
    assert org is None, "Transaction commit failure leaked uncommitted organization into DB!"
    db.close()


# =============================================================================
# 3. DUPLICATE SUBMISSION & CONFLICT REJECTION
# =============================================================================

def test_adv_duplicate_registration_ref_different_user_returns_409():
    """Verify that attempting to register an already-registered registration_number

    under a different existing user account is rejected with HTTP 409 Conflict
    and descriptive error details.
    """
    db = SessionLocal()
    # Create User 1
    u1_uid = f"uid_adv_u1_{uuid.uuid4().hex[:6]}"
    u1_email = f"u1_{uuid.uuid4().hex[:6]}@apexinfra.com"
    user1 = DBUser(
        firebase_uid=u1_uid,
        full_name="User One",
        email=u1_email,
        phone="+919876543210",
        password_hash="pw1",
        role="EMPLOYER",
        status="ACTIVE"
    )
    db.add(user1)
    db.commit()
    db.refresh(user1)

    # Create User 2
    u2_uid = f"uid_adv_u2_{uuid.uuid4().hex[:6]}"
    u2_email = f"u2_{uuid.uuid4().hex[:6]}@apexinfra.com"
    user2 = DBUser(
        firebase_uid=u2_uid,
        full_name="User Two",
        email=u2_email,
        phone="+919876543211",
        password_hash="pw2",
        role="EMPLOYER",
        status="ACTIVE"
    )
    db.add(user2)
    db.commit()
    db.refresh(user2)

    shared_reg_num = f"CIN-SHARED-{uuid.uuid4().hex[:8].upper()}"

    # Register Org 1 under User 1
    payload1 = {
        "company_name": "Org One Infrastructure",
        "registration_number": shared_reg_num,
        "email": u1_email,
        "phone": "+919876543210"
    }
    r1 = client.post("/api/v1/employer/register", json=payload1)
    assert r1.status_code == 200
    db.close()

    # User 2 attempts to claim the same registration_number
    payload2 = {
        "company_name": "Org Two Competitor",
        "registration_number": shared_reg_num,
        "email": u2_email,
        "phone": "+919876543211"
    }
    r2 = client.post("/api/v1/employer/register", json=payload2)
    assert r2.status_code == 409, f"Expected 409 Conflict, got {r2.status_code}: {r2.text}"
    assert f"Registration reference '{shared_reg_num}' is already registered under another account." in r2.json()["detail"]


def test_adv_duplicate_submission_same_account_is_idempotent():
    """Verify that re-submitting registration by the SAME account updates the organization

    without creating duplicate organization records.
    """
    payload = make_unique_employer_payload("idem")
    r1 = client.post("/api/v1/employer/register", json=payload)
    assert r1.status_code == 200
    org_id1 = r1.json()["organization_id"]

    # Re-submit with identical payload
    r2 = client.post("/api/v1/employer/register", json=payload)
    assert r2.status_code == 200
    org_id2 = r2.json()["organization_id"]

    assert org_id1 == org_id2, "Duplicate submission for same user created duplicate organization IDs!"

    # Verify only 1 organization exists in SQLite for this user
    db = SessionLocal()
    org_count = db.query(DBEmployerOrganization).filter(
        DBEmployerOrganization.registration_ref_number == payload["registration_number"]
    ).count()
    assert org_count == 1
    db.close()


# =============================================================================
# 4. PAYLOAD FIELD NORMALIZATION MATRIX
# =============================================================================

def test_adv_payload_normalization_whitespace_and_casing():
    """Verify whitespace trimming and casing normalization across fields."""
    u_hex = uuid.uuid4().hex[:6]
    payload = {
        "company_name": "   Apex Mega Construction Ltd   ",
        "registration_number": f"   CIN-TRIM-{u_hex.upper()}   ",
        "email": f"   UpPeR_CaSe_{u_hex}@ExAmPlE.CoM   ",
        "phone": "  +91 98765 43210  ",
        "categories_requested": ["  Mason  ", "  Plumber  "]
    }
    resp = client.post("/api/v1/employer/register", json=payload)
    assert resp.status_code == 200

    db = SessionLocal()
    org = db.query(DBEmployerOrganization).filter(
        DBEmployerOrganization.registration_ref_number == f"CIN-TRIM-{u_hex.upper()}"
    ).first()
    assert org is not None
    assert org.name == "Apex Mega Construction Ltd"
    assert org.registration_number == f"CIN-TRIM-{u_hex.upper()}"
    assert org.official_email == f"upper_case_{u_hex}@example.com"
    db.close()


def test_adv_payload_normalization_comma_separated_category_string():
    """Verify that a comma-separated string in 'category' or 'categories'

    is normalized into clean individual category request entries.
    """
    u_hex = uuid.uuid4().hex[:6]
    payload = {
        "company_name": f"String Cats {u_hex} Ltd",
        "registration_number": f"CIN-CATS-{u_hex.upper()}",
        "email": f"cats_{u_hex}@example.com",
        "phone": "+91 98765 43210",
        "category": "  Carpentry , Welding ,   Painting  ,  Electrician  "
    }
    resp = client.post("/api/v1/employer/onboard", json=payload)
    assert resp.status_code == 200
    org_id = resp.json()["organization_id"]

    db = SessionLocal()
    cats = db.query(DBCategoryAuthorizationRequest).filter(
        DBCategoryAuthorizationRequest.organization_id == org_id
    ).order_by(DBCategoryAuthorizationRequest.category).all()

    cat_names = [c.category for c in cats]
    assert cat_names == ["Carpentry", "Electrician", "Painting", "Welding"]
    db.close()


def test_adv_payload_normalization_field_aliases():
    """Verify schema field aliases:

    organization_name -> company_name
    org_reg_no -> registration_number
    official_email -> email
    official_phone -> phone
    """
    u_hex = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Aliased Infra {u_hex} Ltd",
        "org_reg_no": f"REG-ALIAS-{u_hex.upper()}",
        "official_email": f"alias_{u_hex}@example.com",
        "official_phone": "+91 98765 43210"
    }
    resp = client.post("/api/v1/employer/register", json=payload)
    assert resp.status_code == 200
    org_id = resp.json()["organization_id"]

    db = SessionLocal()
    org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
    assert org is not None
    assert org.name == f"Aliased Infra {u_hex} Ltd"
    assert org.registration_number == f"REG-ALIAS-{u_hex.upper()}"
    assert org.official_email == f"alias_{u_hex}@example.com"
    db.close()


def test_adv_payload_validation_missing_mandatory_fields_rejected():
    """Verify that omitting mandatory fields returns HTTP 422 with descriptive detail."""
    # 1. Missing company name
    resp1 = client.post("/api/v1/employer/register", json={
        "registration_number": "CIN-001",
        "email": "valid@example.com",
        "phone": "+919876543210"
    })
    assert resp1.status_code == 422

    # 2. Missing registration number
    resp2 = client.post("/api/v1/employer/register", json={
        "company_name": "Valid Name",
        "email": "valid@example.com",
        "phone": "+919876543210"
    })
    assert resp2.status_code == 422

    # 3. Missing/invalid email
    resp3 = client.post("/api/v1/employer/register", json={
        "company_name": "Valid Name",
        "registration_number": "CIN-001",
        "email": "invalid_email_format",
        "phone": "+919876543210"
    })
    assert resp3.status_code == 422


# =============================================================================
# 5. CATEGORY SCOPE GOVERNANCE & DECOUPLING INVARIANT
# =============================================================================

def test_adv_decoupling_invariant_suspend_category_preserves_employer_active():
    """Decoupling Invariant: Admin suspending a category scope mutates

    category request status to SUSPENDED, but employer organization status
    and verification_status MUST REMAIN 'ACTIVE'.
    """
    token = get_admin_token()
    db = SessionLocal()
    ref_num = f"REG-DECOUP-{uuid.uuid4().hex[:8].upper()}"
    org = DBEmployerOrganization(
        name="Decoupling Test Infrastructure",
        registration_ref_number=ref_num,
        registration_number=ref_num,
        status="ACTIVE",
        business_type="Construction",
        state_code="KA"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    cat = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Crane Operations",
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
    db.close()

    # Admin suspends the category via PATCH /api/v1/admin/category-requests/{id}
    patch_resp = client.patch(
        f"/api/v1/admin/category-requests/{cat_id}",
        json={"action": "SUSPEND", "reason": "Operator certification expired"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
    patch_data = patch_resp.json()
    assert patch_data["status"] == "SUSPENDED"
    assert patch_data["is_active_scope"] is False

    # VERIFY DECOUPLING INVARIANT: Parent employer org MUST REMAIN ACTIVE
    db = SessionLocal()
    org_after = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
    assert org_after.status == "ACTIVE", f"Decoupling Invariant Violated! Org status became {org_after.status}"
    assert org_after.verification_status == "ACTIVE", f"Decoupling Invariant Violated! Org verification_status became {org_after.verification_status}"
    db.close()


def test_adv_decoupling_invariant_discontinue_category_preserves_employer_active():
    """Decoupling Invariant: Discontinuing an approved category preserves

    employer organization ACTIVE status and verification_status.
    """
    token = get_admin_token()
    db = SessionLocal()
    ref_num = f"REG-DISC-{uuid.uuid4().hex[:8].upper()}"
    org = DBEmployerOrganization(
        name="Discontinue Invariant Builder",
        registration_ref_number=ref_num,
        registration_number=ref_num,
        status="ACTIVE",
        business_type="Construction",
        state_code="KA"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    cat = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Demolition Works",
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
    db.close()

    # Discontinue via POST /api/v1/admin/category-requests/{id}/discontinue
    disc_resp = client.post(
        f"/api/v1/admin/category-requests/{cat_id}/discontinue",
        json={"reason": "Project phase concluded"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert disc_resp.status_code == 200, f"Discontinue failed: {disc_resp.text}"

    # Verify parent org is still ACTIVE
    db = SessionLocal()
    org_after = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
    assert org_after.status == "ACTIVE"
    assert org_after.verification_status == "ACTIVE"
    db.close()


# =============================================================================
# 6. ADMIN QUEUE DECOUPLING
# =============================================================================

def test_adv_admin_pending_organizations_queue_strictly_filters_pending_review():
    """Verify that GET /api/v1/admin/pending-organizations strictly defaults to

    returning organizations where status == 'PENDING_REVIEW', never returning
    APPROVED, ACTIVE, or REJECTED organizations when status is omitted.
    """
    token = get_admin_token()
    db = SessionLocal()
    # Create orgs in multiple statuses
    u_hex = uuid.uuid4().hex[:6]
    for st in ["PENDING_REVIEW", "APPROVED", "ACTIVE", "REJECTED", "SUSPENDED"]:
        o = DBEmployerOrganization(
            name=f"Org {st} {u_hex}",
            registration_ref_number=f"REG-{st}-{u_hex}",
            registration_number=f"REG-{st}-{u_hex}",
            status=st,
            business_type="Construction",
            state_code="KA"
        )
        db.add(o)
    db.commit()
    db.close()

    # Query /pending-organizations without query params
    resp = client.get("/api/v1/admin/pending-organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    for item in items:
        assert item["status"] == "PENDING_REVIEW", f"Leaked non-pending organization: status={item['status']}"
        assert item["verification_status"] == "PENDING_REVIEW"
