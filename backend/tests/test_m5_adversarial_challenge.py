"""
backend/tests/test_m5_adversarial_challenge.py
Adversarial Challenge & Empirical Stress-Test Suite for Milestone 5:
Employer Dual State Machine, Decoupling Invariants, Partial Unique Index,
Activation Token Security & Governance Audit Immutability.

Author: m5_challenger_1 (EMPIRICAL CHALLENGER)
Parent: orchestrator_5 (f0ed804e-a9bd-47b5-82b5-c807e05127fe)

Challenge Vectors Tested:
1. Decoupling Invariant Attack:
   - Approved employer hiring under unauthorized / pending / discontinued category.
   - Unapproved employer (PENDING_REVIEW / SUSPENDED) hiring under approved category.
2. Partial Unique Index Attack:
   - Admin approving two identical active scopes -> rejected with HTTP 409 Conflict.
   - Direct SQLite insertion of duplicate active scopes -> raises IntegrityError.
   - Coexistence of multiple inactive scopes with identical scope parameters.
3. Category Discontinuation Attack:
   - Discontinuing Category A revokes active scope, preserves parent org & sibling Category B.
   - Updating existing active stint under discontinued category to COMPLETED.
4. Activation Token Security Attack:
   - Single-use token replay -> rejected with HTTP 400 Bad Request.
   - Expired token redemption -> rejected with HTTP 410 Gone.
   - Resend-activation invalidation of older tokens.
5. Audit Trail Immutability & Vulnerability Probing:
   - Instance update & delete blocked by SQLAlchemy event listeners (RuntimeError).
   - Bulk update vulnerability demonstration (ORM mapper hooks bypassed without SQL triggers).
   - Read-only API surface (no mutation endpoints).
6. Production Implementation Defect Verification:
   - POST /api/v1/employer/register-organization crashes with 500 (missing password_hash & invalid phone arg).
"""

import os
import sys
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
import sqlite3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

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
    DBAdminAuditLog
)
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service

client = TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Helpers
# ============================================================================

def make_admin():
    uid = f"admin_{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Platform Admin",
            email=email,
            phone="+91 9999999999",
            password_hash=hashlib.sha256(b"adminpass").hexdigest(),
            role="ADMIN",
            status="ACTIVE",
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    return create_test_firebase_jwt(uid=uid, email=email, name="Platform Admin")


def make_employer(org_status="APPROVED", categories=None):
    if categories is None:
        categories = []
    suffix = uuid.uuid4().hex[:6]
    uid = f"emp_{suffix}"
    email = f"emp_{suffix}@builder.com"
    org_addr = f"0xemp_{suffix}"

    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name=f"Builder {suffix}",
            email=email,
            phone="+91 9777777777",
            password_hash=hashlib.sha256(b"emppass").hexdigest(),
            role="EMPLOYER",
            status="ACTIVE" if org_status == "ACTIVE" else "PENDING_REVIEW",
            organization_address=org_addr,
            organization_name=f"Builder Corp {suffix}",
            organization_status=org_status,
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(user)
        db.flush()

        org = DBEmployerOrganization(
            user_id=user.id,
            name=f"Builder Corp {suffix}",
            registration_ref_number=f"REG-{suffix.upper()}",
            registration_number=f"U12345KA202{suffix[:4].upper()}",
            business_type="Private Limited",
            nature_of_business="Civil Infrastructure",
            official_email=email,
            contact_person=f"Director {suffix}",
            official_phone="+91 9777777777",
            contact_phone="+91 9777777777",
            org_address=org_addr,
            status=org_status
        )
        db.add(org)
        db.flush()

        # Seed in-memory blockchain service organization status
        blockchain_service.organizations[org_addr] = {
            "name": org.name,
            "status": org_status,
            "categories": [],
            "levels": ["Skilled", "Semi-Skilled"],
            "natures": ["Contract", "Full-Time"]
        }

        created_cat_ids = []
        for cat_info in categories:
            cat_name = cat_info.get("name", "Masonry")
            cat_status = cat_info.get("status", "APPROVED")
            is_active = cat_info.get("is_active", True)
            cat_req = DBCategoryAuthorizationRequest(
                organization_id=org.id,
                category=cat_name,
                skill_level="Skilled",
                nature_of_employment="Contract",
                status=cat_status,
                is_active_scope=is_active,
                request_version=cat_info.get("version", 1)
            )
            db.add(cat_req)
            db.flush()
            created_cat_ids.append(cat_req.id)
            if is_active:
                blockchain_service.organizations[org_addr]["categories"].append(cat_name)

        db.commit()
        db.refresh(user)
        db.refresh(org)
        token = create_test_firebase_jwt(uid=uid, email=email, name=f"Builder {suffix}")
        return user.id, org.id, org_addr, token, created_cat_ids
    finally:
        db.close()


# ============================================================================
# 1. Decoupling Invariant Stress Tests
# ============================================================================

class TestDecouplingInvariantStress:

    def test_approved_employer_cannot_hire_under_unauthorized_category(self):
        """Vector 1a: Approved employer hiring under category with zero scopes."""
        _, _, org_addr, emp_token, _ = make_employer(org_status="APPROVED", categories=[
            {"name": "Masonry", "status": "APPROVED", "is_active": True}
        ])
        headers = {"Authorization": f"Bearer {emp_token}"}

        resp = client.post("/api/v1/employer/create-employment", headers=headers, json={
            "worker_did": "did:passkhadam:worker123",
            "category": "Plumbing",  # Unauthorized category
            "job_role": "Master Plumber",
            "work_location": "Bengaluru",
            "level": "Skilled",
            "nature_of_employment": "Contract"
        })
        assert resp.status_code == 400
        assert "does not have an active approved scope" in resp.json()["detail"]

    def test_approved_employer_cannot_hire_under_pending_category(self):
        """Vector 1b: Approved employer hiring under category with PENDING scope."""
        _, _, org_addr, emp_token, _ = make_employer(org_status="APPROVED", categories=[
            {"name": "Electrical", "status": "PENDING", "is_active": False}
        ])
        headers = {"Authorization": f"Bearer {emp_token}"}

        resp = client.post("/api/v1/employer/create-employment", headers=headers, json={
            "worker_did": "did:passkhadam:worker123",
            "category": "Electrical",
            "job_role": "Electrician",
            "work_location": "Bengaluru",
            "level": "Skilled",
            "nature_of_employment": "Contract"
        })
        assert resp.status_code == 400
        assert "does not have an active approved scope" in resp.json()["detail"]

    def test_approved_employer_cannot_hire_under_discontinued_category(self):
        """Vector 1c: Approved employer hiring under category with DISCONTINUED scope."""
        _, _, org_addr, emp_token, _ = make_employer(org_status="APPROVED", categories=[
            {"name": "Carpentry", "status": "DISCONTINUED", "is_active": False}
        ])
        headers = {"Authorization": f"Bearer {emp_token}"}

        resp = client.post("/api/v1/employer/create-employment", headers=headers, json={
            "worker_did": "did:passkhadam:worker123",
            "category": "Carpentry",
            "job_role": "Carpenter",
            "work_location": "Bengaluru",
            "level": "Skilled",
            "nature_of_employment": "Contract"
        })
        assert resp.status_code == 400
        assert "does not have an active approved scope" in resp.json()["detail"]

    def test_unapproved_employer_cannot_hire_even_if_category_marked_active(self):
        """Vector 1d: Unapproved employer (PENDING_REVIEW or SUSPENDED) blocked from hiring."""
        # Test PENDING_REVIEW
        _, _, _, emp_token_pending, _ = make_employer(org_status="PENDING_REVIEW", categories=[
            {"name": "Masonry", "status": "APPROVED", "is_active": True}
        ])
        resp1 = client.post("/api/v1/employer/create-employment", headers={"Authorization": f"Bearer {emp_token_pending}"}, json={
            "worker_did": "did:passkhadam:worker123",
            "category": "Masonry",
            "job_role": "Mason",
            "work_location": "Bengaluru",
            "level": "Skilled",
            "nature_of_employment": "Contract"
        })
        assert resp1.status_code == 403
        assert "Employer organization is PENDING_REVIEW" in resp1.json()["detail"]

        # Test SUSPENDED
        _, _, _, emp_token_susp, _ = make_employer(org_status="SUSPENDED", categories=[
            {"name": "Masonry", "status": "APPROVED", "is_active": True}
        ])
        resp2 = client.post("/api/v1/employer/create-employment", headers={"Authorization": f"Bearer {emp_token_susp}"}, json={
            "worker_did": "did:passkhadam:worker123",
            "category": "Masonry",
            "job_role": "Mason",
            "work_location": "Bengaluru",
            "level": "Skilled",
            "nature_of_employment": "Contract"
        })
        assert resp2.status_code == 403
        assert "Employer organization is SUSPENDED" in resp2.json()["detail"]


# ============================================================================
# 2. Partial Unique Index Stress Tests
# ============================================================================

class TestPartialUniqueIndexStress:

    def test_admin_cannot_approve_two_identical_active_scopes_returns_409(self):
        """Vector 2a: Admin approving a second identical active scope returns HTTP 409 Conflict."""
        admin_jwt = make_admin()
        _, org_id, _, _, cat_ids = make_employer(org_status="APPROVED", categories=[
            {"name": "Welding", "status": "APPROVED", "is_active": True}
        ])

        # Create a second PENDING request for identical scope
        db = SessionLocal()
        try:
            req2 = DBCategoryAuthorizationRequest(
                organization_id=org_id,
                category="Welding",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="PENDING",
                is_active_scope=False,
                request_version=2
            )
            db.add(req2)
            db.commit()
            req2_id = req2.id
        finally:
            db.close()

        # Admin attempts to APPROVE req2 -> collision with active req1
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        resp = client.post(
            f"/api/v1/admin/category-requests/{req2_id}/review",
            headers=headers,
            json={"action": "APPROVE"}
        )
        assert resp.status_code == 409
        assert "Active scope already exists" in resp.json()["detail"]

    def test_sqlite_partial_unique_index_raises_integrity_error(self):
        """Vector 2b: Database level partial unique index blocks duplicate active scope."""
        _, org_id, _, _, _ = make_employer(org_status="APPROVED", categories=[
            {"name": "Crane_Operator", "status": "APPROVED", "is_active": True}
        ])

        db = SessionLocal()
        try:
            duplicate_active = DBCategoryAuthorizationRequest(
                organization_id=org_id,
                category="Crane_Operator",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="APPROVED",
                is_active_scope=True
            )
            db.add(duplicate_active)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()

    def test_multiple_inactive_scopes_coexist_under_partial_unique_index(self):
        """Vector 2c: Inactive scopes (REJECTED/DISCONTINUED/PENDING) coexist cleanly."""
        _, org_id, _, _, _ = make_employer(org_status="APPROVED", categories=[
            {"name": "Rigging", "status": "DISCONTINUED", "is_active": False, "version": 1}
        ])

        db = SessionLocal()
        try:
            # Second inactive version
            v2 = DBCategoryAuthorizationRequest(
                organization_id=org_id,
                category="Rigging",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="REJECTED",
                is_active_scope=False,
                request_version=2
            )
            db.add(v2)
            db.commit()

            # Third inactive pending version
            v3 = DBCategoryAuthorizationRequest(
                organization_id=org_id,
                category="Rigging",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="PENDING",
                is_active_scope=False,
                request_version=3
            )
            db.add(v3)
            db.commit()

            count = db.query(DBCategoryAuthorizationRequest).filter(
                DBCategoryAuthorizationRequest.organization_id == org_id,
                DBCategoryAuthorizationRequest.category == "Rigging"
            ).count()
            assert count == 3
        finally:
            db.close()


# ============================================================================
# 3. Category Discontinuation & Stint Preservation Stress Tests
# ============================================================================

class TestCategoryDiscontinuationStress:

    def test_discontinuation_preserves_employer_and_sibling_categories(self):
        """Vector 3a: Discontinuing Cat A keeps Org ACTIVE and Cat B APPROVED."""
        admin_jwt = make_admin()
        _, org_id, org_addr, _, cat_ids = make_employer(org_status="ACTIVE", categories=[
            {"name": "Masonry", "status": "APPROVED", "is_active": True},
            {"name": "Electrician", "status": "APPROVED", "is_active": True}
        ])
        cat_masonry_id = cat_ids[0]
        cat_elec_id = cat_ids[1]

        headers = {"Authorization": f"Bearer {admin_jwt}"}
        resp = client.post(
            f"/api/v1/admin/discontinue-category/{cat_masonry_id}",
            headers=headers,
            json={"reason": "Regulatory license expired for masonry work"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DISCONTINUED"
        assert data["is_active_scope"] is False
        assert data["organization_status"] == "ACTIVE"

        # Verify DB state
        db = SessionLocal()
        try:
            masonry_row = db.query(DBCategoryAuthorizationRequest).filter_by(id=cat_masonry_id).first()
            elec_row = db.query(DBCategoryAuthorizationRequest).filter_by(id=cat_elec_id).first()
            org_row = db.query(DBEmployerOrganization).filter_by(id=org_id).first()

            assert masonry_row.status == "DISCONTINUED"
            assert masonry_row.is_active_scope is False
            assert elec_row.status == "APPROVED"
            assert elec_row.is_active_scope is True
            assert org_row.status == "ACTIVE"
        finally:
            db.close()

    def test_existing_employment_stint_under_discontinued_category_can_be_completed(self):
        """Vector 3b: Stints created prior to discontinuation can be updated to COMPLETED."""
        admin_jwt = make_admin()
        _, org_id, org_addr, emp_token, cat_ids = make_employer(org_status="ACTIVE", categories=[
            {"name": "Excavation", "status": "APPROVED", "is_active": True}
        ])
        cat_id = cat_ids[0]

        # 1. Create valid employment while category is active
        emp_resp = client.post(
            "/api/v1/employer/create-employment",
            headers={"Authorization": f"Bearer {emp_token}"},
            json={
                "worker_did": "did:passkhadam:worker_excavator",
                "category": "Excavation",
                "job_role": "Excavator Driver",
                "work_location": "Bengaluru Site A",
                "level": "Skilled",
                "nature_of_employment": "Contract"
            }
        )
        assert emp_resp.status_code == 200
        emp_record_id = emp_resp.json()["employment_record"]["id"]

        # 2. Admin discontinues Excavation
        disc_resp = client.post(
            f"/api/v1/admin/discontinue-category/{cat_id}",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"reason": "Project phase finished"}
        )
        assert disc_resp.status_code == 200

        # 3. Direct engine update succeeds: demonstrates business logic invariant is supported
        blockchain_service.update_employment_status(
            emp_id=emp_record_id,
            caller_address=org_addr,
            new_status="COMPLETED",
            reason="Contract stint completed successfully"
        )
        assert blockchain_service.employments[emp_record_id]["status"] == "COMPLETED"

        # 4. API endpoint test: PUT /employment-status dynamically resolves employer address from authenticated user
        api_update_resp = client.put(
            "/api/v1/employer/employment-status",
            headers={"Authorization": f"Bearer {emp_token}"},
            json={
                "employment_id": emp_record_id,
                "new_status": "TERMINATED",
                "reason": "Administrative termination"
            }
        )
        assert api_update_resp.status_code == 200
        assert api_update_resp.json()["status"] == "TERMINATED"


# ============================================================================
# 4. Activation Token Security Stress Tests
# ============================================================================

class TestActivationTokenSecurityStress:

    def test_employer_activation_single_use_token_cannot_be_replayed(self):
        """Vector 4a: Redeemed activation token cannot be reused (HTTP 400)."""
        admin_jwt = make_admin()
        _, org_id, _, _, _ = make_employer(org_status="PENDING_REVIEW")

        # Admin approves -> generates token
        review_resp = client.post(
            f"/api/v1/admin/organizations/{org_id}/review",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"action": "APPROVE"}
        )
        assert review_resp.status_code == 200
        act_link = review_resp.json()["activation_link"]
        raw_token = act_link.split("token=")[1]

        # 1st Redemption -> Success (200)
        act_resp1 = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_token,
            "password": "newSecurePassword123"
        })
        assert act_resp1.status_code == 200
        assert act_resp1.json()["status"] == "ACTIVE"

        # 2nd Redemption -> Replay Rejection (400)
        act_resp2 = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_token,
            "password": "attackerPassword"
        })
        assert act_resp2.status_code == 400
        assert "already been used" in act_resp2.json()["detail"]

    def test_expired_activation_token_rejected_with_410(self):
        """Vector 4b: Expired token redemption returns HTTP 410 Gone."""
        _, org_id, _, _, _ = make_employer(org_status="APPROVED")

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # Seed expired token directly
        db = SessionLocal()
        try:
            act_email = DBActivationEmail(
                recipient_email="expired@builder.com",
                token_hash=token_hash,
                entity_type="EMPLOYER",
                entity_id=org_id,
                status="SENT",
                attempt_count=1,
                expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hr ago
                sent_at=datetime.utcnow() - timedelta(hours=49)
            )
            db.add(act_email)
            db.commit()
        finally:
            db.close()

        resp = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_token,
            "password": "somePassword123"
        })
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_resend_activation_invalidates_prior_token(self):
        """Vector 4c: Resending activation token marks older token EXPIRED."""
        admin_jwt = make_admin()
        _, org_id, _, _, _ = make_employer(org_status="APPROVED")

        # 1. Issue initial token
        raw_token1 = secrets.token_urlsafe(32)
        token1_hash = hashlib.sha256(raw_token1.encode("utf-8")).hexdigest()
        db = SessionLocal()
        try:
            act1 = DBActivationEmail(
                recipient_email="builder@test.com",
                token_hash=token1_hash,
                entity_type="EMPLOYER",
                entity_id=org_id,
                status="SENT",
                attempt_count=1,
                expires_at=datetime.utcnow() + timedelta(hours=48),
                sent_at=datetime.utcnow()
            )
            db.add(act1)
            db.commit()
        finally:
            db.close()

        # 2. Admin calls resend-activation
        resend_resp = client.post(
            f"/api/v1/admin/resend-employer-activation/{org_id}",
            headers={"Authorization": f"Bearer {admin_jwt}"}
        )
        assert resend_resp.status_code == 200
        raw_token2 = resend_resp.json()["activation_link"].split("token=")[1]

        # 3. Older token1 is now EXPIRED
        resp_token1 = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_token1,
            "password": "pass1"
        })
        assert resp_token1.status_code == 410

        # 4. Fresh token2 works cleanly
        resp_token2 = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_token2,
            "password": "pass2"
        })
        assert resp_token2.status_code == 200
        assert resp_token2.json()["status"] == "ACTIVE"


# ============================================================================
# 5. Audit Trail Immutability & Vulnerability Probing
# ============================================================================

class TestAuditTrailImmutabilityStress:

    def test_audit_log_instance_update_prevented(self):
        """Vector 5a: Instance level update blocked with RuntimeError."""
        db = SessionLocal()
        try:
            log = DBGovernanceAuditLog(
                actor_firebase_uid="admin_test_uid",
                actor_role="ADMIN",
                action="TEST_ACTION",
                target_type="TEST_TYPE",
                target_id="123"
            )
            db.add(log)
            db.commit()
            db.refresh(log)

            log.action = "TAMPERED_ACTION"
            with pytest.raises(RuntimeError, match="immutable; update operations are strictly prohibited"):
                db.commit()
            db.rollback()
        finally:
            db.close()

    def test_audit_log_instance_delete_prevented(self):
        """Vector 5b: Instance level delete blocked with RuntimeError."""
        db = SessionLocal()
        try:
            log = DBGovernanceAuditLog(
                actor_firebase_uid="admin_test_uid",
                actor_role="ADMIN",
                action="TEST_ACTION_DELETE",
                target_type="TEST_TYPE",
                target_id="456"
            )
            db.add(log)
            db.commit()
            db.refresh(log)

            db.delete(log)
            with pytest.raises(RuntimeError, match="immutable; delete operations are strictly prohibited"):
                db.commit()
            db.rollback()
        finally:
            db.close()

    def test_audit_log_bulk_update_flaw_demonstrated(self):
        """Vector 5c: Bulk Query.update() is rejected by SQLite DDL immutability trigger."""
        db = SessionLocal()
        try:
            log = DBGovernanceAuditLog(
                actor_firebase_uid="admin_bulk_test",
                actor_role="ADMIN",
                action="ORIGINAL_ACTION",
                target_type="BULK_TEST",
                target_id="789"
            )
            db.add(log)
            db.commit()
            log_id = log.id

            # ORM bulk update emits direct SQL UPDATE rejected by SQLite trigger
            with pytest.raises((Exception, sqlite3.IntegrityError, OperationalError, IntegrityError)) as exc_info:
                db.query(DBGovernanceAuditLog).filter_by(id=log_id).update({
                    "action": "MUTATED_VIA_BULK_UPDATE"
                })
                db.commit()
            db.rollback()
            assert "immutable" in str(exc_info.value).lower()
        finally:
            db.close()

    def test_admin_api_is_strictly_read_only_for_audit_logs(self):
        """Vector 5d: Admin API provides GET only; PUT/DELETE endpoints return 404/405."""
        admin_jwt = make_admin()
        headers = {"Authorization": f"Bearer {admin_jwt}"}

        # GET is allowed
        get_resp = client.get("/api/v1/admin/governance-audit-logs", headers=headers)
        assert get_resp.status_code == 200

        # PUT is not exposed
        put_resp = client.put("/api/v1/admin/governance-audit-logs/1", headers=headers, json={"action": "TAMPER"})
        assert put_resp.status_code in [404, 405]

        # DELETE is not exposed
        del_resp = client.delete("/api/v1/admin/governance-audit-logs/1", headers=headers)
        assert del_resp.status_code in [404, 405]


# ============================================================================
# 6. Production Implementation Defects Found
# ============================================================================

class TestProductionImplementationDefects:

    def test_employer_registration_succeeds_with_password_hash_and_official_phone(self):
        """Remediation Verification: POST /api/v1/employer/register-organization succeeds with 200."""
        resp = client.post("/api/v1/employer/register-organization", json={
            "company_name": "Apex Infra Test",
            "registration_number": "U45200KA2026",
            "email": f"emp_{uuid.uuid4().hex[:6]}@test.com",
            "contact_person": "Apex Manager",
            "phone": "+91 9876543210",
            "categories_requested": ["Masonry"]
        })
        assert resp.status_code == 200, f"Expected 200 on register-organization, got {resp.status_code}: {resp.text}"
        assert "organization_id" in resp.json()
        assert "Pending admin review" in resp.json()["message"]
