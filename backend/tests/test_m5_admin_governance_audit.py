"""
Milestone 5 Test Suite: Employer Dual State Machine, Admin Governance & Audit Log Immutability
==============================================================================================
Comprehensive verification covering:
1. Organization Review Lifecycle (APPROVE, REJECT, SUSPEND, REACTIVATE, mandatory reason checks)
2. Token Creation in DBActivationEmail on APPROVE and Redemption via POST /employer/activate
3. Replay Protection (reject used token) and Expiration Rejection
4. Resend Activation Token (marks older token EXPIRED, increments attempt_count)
5. Category Review Lifecycle & Decoupling Invariant (is_active_scope True only on APPROVE)
6. Discontinuation of Single Category without affecting parent organization or other categories
7. Category Re-request Version Increment (request_version = max + 1)
8. Decoupling Invariant on create-employment (fails if org not active or category not active)
9. DBGovernanceAuditLog & DBAdminAuditLog canonical alias and immutability (RuntimeError on update/delete)
10. Admin RBAC protection (Worker / Employer rejected with HTTP 403, unauthenticated with HTTP 401)
"""

import os
import sys
import json
import time
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
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBAdminAuditLog
)
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service

client = TestClient(app)


# ============================================================================
# Helpers & Fixtures
# ============================================================================

def create_admin_token() -> str:
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


def create_worker_token() -> str:
    uid = f"worker_{uuid.uuid4().hex[:8]}"
    email = f"worker_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Test Worker",
            email=email,
            phone="+91 9888888888",
            password_hash=hashlib.sha256(b"workerpass").hexdigest(),
            role="WORKER",
            status="ACTIVE",
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    return create_test_firebase_jwt(uid=uid, email=email, name="Test Worker")


def create_employer_user_and_org(status: str = "PENDING_REVIEW"):
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        uid = f"emp_uid_{suffix}"
        email = f"employer_{suffix}@apexinfra.com"
        org_addr = f"0xemp_{suffix}"

        user = DBUser(
            firebase_uid=uid,
            full_name=f"Apex Director {suffix}",
            email=email,
            phone="+91 9777777777",
            password_hash=hashlib.sha256(b"emppass").hexdigest(),
            role="EMPLOYER",
            status=status,
            organization_address=org_addr,
            organization_name=f"Apex Infrastructure {suffix}",
            organization_status=status,
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(user)
        db.flush()

        org = DBEmployerOrganization(
            user_id=user.id,
            name=f"Apex Infrastructure {suffix}",
            registration_ref_number=f"REG-CIN-{suffix.upper()}",
            registration_number=f"U45200KA202{suffix[:4].upper()}",
            business_type="Private Limited",
            nature_of_business="Civil Infrastructure",
            official_email=email,
            contact_person=f"Apex Director {suffix}",
            official_phone="+91 9777777777",
            contact_phone="+91 9777777777",
            org_address=org_addr,
            status=status
        )
        db.add(org)
        db.commit()
        db.refresh(user)
        db.refresh(org)
        token = create_test_firebase_jwt(uid=uid, email=email, name=f"Apex Director {suffix}")
        return user, org, token
    finally:
        db.close()


# ============================================================================
# 1. Organization Review Lifecycle Tests
# ============================================================================

class TestOrganizationReviewLifecycle:

    def test_admin_approves_organization_generates_activation_token_and_audit(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        user, org, _ = create_employer_user_and_org(status="PENDING_REVIEW")

        resp = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers=headers,
            json={"action": "APPROVE", "notes": "KYC documentation verified"}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["organization"]["status"] == "APPROVED"
        assert "activation_link" in data
        assert data["activation_link"] is not None
        assert "token=" in data["activation_link"]

        # Verify DB state
        db = SessionLocal()
        try:
            refreshed_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org.id).first()
            assert refreshed_org.status == "APPROVED"

            # Check activation email entry
            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.entity_type == "EMPLOYER",
                DBActivationEmail.entity_id == org.id
            ).first()
            assert act_email is not None
            assert act_email.status == "SENT"
            assert act_email.token_hash is not None
            assert act_email.attempt_count == 1

            # Check audit log entry
            audit = db.query(DBGovernanceAuditLog).filter(
                DBGovernanceAuditLog.target_type == "EMPLOYER_ORGANIZATION",
                DBGovernanceAuditLog.target_id == str(org.id),
                DBGovernanceAuditLog.action == "APPROVE_ORGANIZATION"
            ).first()
            assert audit is not None
            assert audit.previous_state == "PENDING_REVIEW"
            assert audit.new_state == "APPROVED"
        finally:
            db.close()

    def test_admin_rejects_organization_requires_reason(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        _, org, _ = create_employer_user_and_org(status="PENDING_REVIEW")

        # Empty reason
        resp = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers=headers,
            json={"action": "REJECT", "reason": ""}
        )
        assert resp.status_code == 400
        assert "Reason is mandatory" in resp.json()["detail"]

    def test_admin_rejects_organization_success(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        user, org, _ = create_employer_user_and_org(status="PENDING_REVIEW")

        resp = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers=headers,
            json={"action": "REJECT", "reason": "Invalid registration certificate submitted"}
        )
        assert resp.status_code == 200
        assert resp.json()["organization"]["status"] == "REJECTED"

        db = SessionLocal()
        try:
            refreshed_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org.id).first()
            assert refreshed_org.status == "REJECTED"
            assert refreshed_org.rejection_reason == "Invalid registration certificate submitted"

            refreshed_user = db.query(DBUser).filter(DBUser.id == user.id).first()
            assert refreshed_user.status == "REJECTED"
        finally:
            db.close()

    def test_admin_suspends_and_reactivates_organization(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        user, org, _ = create_employer_user_and_org(status="ACTIVE")

        # Suspend without reason -> Fail
        resp_fail = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers=headers,
            json={"action": "SUSPEND", "reason": ""}
        )
        assert resp_fail.status_code == 400

        # Suspend with reason -> Success
        resp_suspend = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers=headers,
            json={"action": "SUSPEND", "reason": "Labour compliance audit pending"}
        )
        assert resp_suspend.status_code == 200
        assert resp_suspend.json()["organization"]["status"] == "SUSPENDED"

        # Reactivate -> Success
        resp_reactivate = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers=headers,
            json={"action": "REACTIVATE", "notes": "Compliance clear"}
        )
        assert resp_reactivate.status_code == 200
        assert resp_reactivate.json()["organization"]["status"] == "ACTIVE"


# ============================================================================
# 2. Employer Token Activation & Replay Protection Tests
# ============================================================================

class TestEmployerActivationLifecycle:

    def test_employer_activation_happy_path(self):
        admin_jwt = create_admin_token()
        user, org, _ = create_employer_user_and_org(status="PENDING_REVIEW")

        # Admin approves
        review_resp = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"action": "APPROVE"}
        )
        link = review_resp.json()["activation_link"]
        raw_token = link.split("token=")[1]

        # Employer redeems token
        activate_resp = client.post(
            "/api/v1/employer/activate",
            json={"activation_token": raw_token, "password": "newSecurePassword123!"}
        )
        assert activate_resp.status_code == 200, activate_resp.text
        data = activate_resp.json()
        assert data["status"] == "ACTIVE"
        assert data["organization_status"] == "ACTIVE"

        # Verify DB status
        db = SessionLocal()
        try:
            ref_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org.id).first()
            assert ref_org.status == "ACTIVE"
            ref_user = db.query(DBUser).filter(DBUser.id == user.id).first()
            assert ref_user.status == "ACTIVE"

            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.entity_type == "EMPLOYER",
                DBActivationEmail.entity_id == org.id
            ).first()
            assert act_email.status == "USED"
            assert act_email.used_at is not None
        finally:
            db.close()

    def test_employer_activation_replay_rejected_with_400(self):
        admin_jwt = create_admin_token()
        _, org, _ = create_employer_user_and_org(status="PENDING_REVIEW")

        review_resp = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"action": "APPROVE"}
        )
        raw_token = review_resp.json()["activation_link"].split("token=")[1]

        # First activation -> Success
        r1 = client.post("/api/v1/employer/activate", json={"activation_token": raw_token})
        assert r1.status_code == 200

        # Second activation (Replay) -> 400 Bad Request
        r2 = client.post("/api/v1/employer/activate", json={"activation_token": raw_token})
        assert r2.status_code == 400
        assert "already been used" in r2.json()["detail"]

    def test_employer_activation_expired_token_rejected_with_410(self):
        admin_jwt = create_admin_token()
        _, org, _ = create_employer_user_and_org(status="PENDING_REVIEW")

        review_resp = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"action": "APPROVE"}
        )
        raw_token = review_resp.json()["activation_link"].split("token=")[1]
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # Manually expire token in DB
        db = SessionLocal()
        try:
            act_email = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == token_hash).first()
            act_email.expires_at = datetime.utcnow() - timedelta(hours=1)
            act_email.status = "EXPIRED"
            db.commit()
        finally:
            db.close()

        # Attempt to redeem expired token -> HTTP 410 GONE
        resp = client.post("/api/v1/employer/activate", json={"activation_token": raw_token})
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_admin_resend_employer_activation_invalidates_prior_token(self):
        admin_jwt = create_admin_token()
        _, org, _ = create_employer_user_and_org(status="PENDING_REVIEW")

        review_resp = client.post(
            f"/api/v1/admin/organizations/{org.id}/review",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"action": "APPROVE"}
        )
        raw_token_1 = review_resp.json()["activation_link"].split("token=")[1]

        # Admin calls resend activation
        resend_resp = client.post(
            f"/api/v1/admin/resend-employer-activation/{org.id}",
            headers={"Authorization": f"Bearer {admin_jwt}"}
        )
        assert resend_resp.status_code == 200
        data = resend_resp.json()
        assert data["attempt_count"] == 2
        raw_token_2 = data["activation_link"].split("token=")[1]
        assert raw_token_1 != raw_token_2

        # Token 1 must now be EXPIRED and rejected
        r1 = client.post("/api/v1/employer/activate", json={"activation_token": raw_token_1})
        assert r1.status_code == 410

        # Token 2 must succeed
        r2 = client.post("/api/v1/employer/activate", json={"activation_token": raw_token_2})
        assert r2.status_code == 200
        assert r2.json()["status"] == "ACTIVE"


# ============================================================================
# 3. Category Authorization & Decoupling Invariant Tests
# ============================================================================

class TestCategoryAuthorizationAndDecoupling:

    def test_category_review_approval_enforces_decoupling_invariant(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        user, org, emp_jwt = create_employer_user_and_org(status="APPROVED")

        # Create category authorization request
        db = SessionLocal()
        cat_req = DBCategoryAuthorizationRequest(
            organization_id=org.id,
            category="Heavy Machinery Operation",
            skill_level="Skilled",
            nature_of_employment="Contract",
            status="PENDING",
            is_active_scope=False,
            request_version=1
        )
        db.add(cat_req)
        db.commit()
        db.refresh(cat_req)
        cat_req_id = cat_req.id
        db.close()

        # Admin approves category
        resp = client.post(
            f"/api/v1/admin/category-requests/{cat_req_id}/review",
            headers=headers,
            json={"action": "APPROVE", "reason": "Authorized for crane operations"}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["is_active_scope"] is True

        # Verify on-chain/in-memory state
        target_addr = org.org_address
        assert blockchain_service.is_category_authorized(target_addr, "Heavy Machinery Operation") is True

    def test_category_review_rejection_requires_reason(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        _, org, _ = create_employer_user_and_org(status="APPROVED")

        db = SessionLocal()
        cat_req = DBCategoryAuthorizationRequest(
            organization_id=org.id,
            category="Electrical High Voltage",
            skill_level="Skilled",
            nature_of_employment="Contract",
            status="PENDING",
            is_active_scope=False,
            request_version=1
        )
        db.add(cat_req)
        db.commit()
        cat_req_id = cat_req.id
        db.close()

        # Rejection without reason fails
        resp = client.post(
            f"/api/v1/admin/category-requests/{cat_req_id}/review",
            headers=headers,
            json={"action": "REJECT", "reason": ""}
        )
        assert resp.status_code == 400

        # Rejection with reason succeeds
        resp_ok = client.post(
            f"/api/v1/admin/category-requests/{cat_req_id}/review",
            headers=headers,
            json={"action": "REJECT", "reason": "High voltage certification missing"}
        )
        assert resp_ok.status_code == 200
        assert resp_ok.json()["status"] == "REJECTED"
        assert resp_ok.json()["is_active_scope"] is False

    def test_discontinue_single_category_preserves_employer_and_other_categories(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        user, org, emp_jwt = create_employer_user_and_org(status="ACTIVE")

        db = SessionLocal()
        cat1 = DBCategoryAuthorizationRequest(
            organization_id=org.id,
            category="Masonry",
            skill_level="Skilled",
            nature_of_employment="Contract",
            status="APPROVED",
            is_active_scope=True,
            request_version=1
        )
        cat2 = DBCategoryAuthorizationRequest(
            organization_id=org.id,
            category="Plumbing",
            skill_level="Skilled",
            nature_of_employment="Contract",
            status="APPROVED",
            is_active_scope=True,
            request_version=1
        )
        db.add_all([cat1, cat2])
        db.commit()
        db.refresh(cat1)
        db.refresh(cat2)
        cat1_id = cat1.id
        cat2_id = cat2.id
        db.close()

        # Register categories in blockchain_service
        blockchain_service.authorize_category(org.org_address, "Masonry")
        blockchain_service.authorize_category(org.org_address, "Plumbing")

        # Discontinue ONLY Masonry
        resp = client.post(
            f"/api/v1/admin/discontinue-category/{cat1_id}",
            headers=headers,
            json={"reason": "Safety incident during masonry work"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DISCONTINUED"
        assert data["is_active_scope"] is False
        assert data["organization_status"] == "ACTIVE"

        # Verify DB: Plumbing remains active, org remains active
        db = SessionLocal()
        try:
            ref_cat1 = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat1_id).first()
            assert ref_cat1.status == "DISCONTINUED"
            assert ref_cat1.is_active_scope is False

            ref_cat2 = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat2_id).first()
            assert ref_cat2.status == "APPROVED"
            assert ref_cat2.is_active_scope is True

            ref_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org.id).first()
            assert ref_org.status == "ACTIVE"
        finally:
            db.close()

        # Verify on-chain / service state
        assert blockchain_service.is_category_authorized(org.org_address, "Masonry") is False
        assert blockchain_service.is_category_authorized(org.org_address, "Plumbing") is True

    def test_category_re_request_increments_version_and_coexists_with_inactive(self):
        user, org, emp_jwt = create_employer_user_and_org(status="ACTIVE")

        # Setup discontinued version 1 in DB
        db = SessionLocal()
        v1 = DBCategoryAuthorizationRequest(
            organization_id=org.id,
            category="Carpentry",
            skill_level="Skilled",
            nature_of_employment="Contract",
            status="DISCONTINUED",
            is_active_scope=False,
            request_version=1
        )
        db.add(v1)
        db.commit()
        db.close()

        # Employer re-requests Carpentry
        resp = client.post(
            "/api/v1/employer/request-category",
            headers={"Authorization": f"Bearer {emp_jwt}"},
            json={"category": "Carpentry", "reason": "Re-applying with renewed carpentry supervisor"}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["request_version"] == 2

        # Verify in DB: both version 1 and version 2 exist cleanly
        db = SessionLocal()
        try:
            records = db.query(DBCategoryAuthorizationRequest).filter(
                DBCategoryAuthorizationRequest.organization_id == org.id,
                DBCategoryAuthorizationRequest.category == "Carpentry"
            ).order_by(DBCategoryAuthorizationRequest.request_version.asc()).all()
            assert len(records) == 2
            assert records[0].request_version == 1
            assert records[0].is_active_scope is False
            assert records[1].request_version == 2
            assert records[1].is_active_scope is False
            assert records[1].status == "PENDING"
        finally:
            db.close()

    def test_create_employment_fails_if_category_not_active(self):
        user, org, emp_jwt = create_employer_user_and_org(status="ACTIVE")

        # Employer tries to create employment for unauthorized category
        resp = client.post(
            "/api/v1/employer/create-employment",
            headers={"Authorization": f"Bearer {emp_jwt}"},
            json={
                "worker_did": "did:passkhadam:test_worker_1",
                "category": "Solar Installation",
                "level": "Skilled",
                "nature_of_employment": "Contract",
                "job_role": "Solar Rooftop Technician",
                "work_location": "Bengaluru",
                "expected_end_date": int(time.time()) + 86400 * 30
            }
        )
        assert resp.status_code == 400
        assert "does not have an active approved scope" in resp.json()["detail"]

    def test_create_employment_fails_if_organization_suspended(self):
        user, org, emp_jwt = create_employer_user_and_org(status="SUSPENDED")

        resp = client.post(
            "/api/v1/employer/create-employment",
            headers={"Authorization": f"Bearer {emp_jwt}"},
            json={
                "worker_did": "did:passkhadam:test_worker_2",
                "category": "Masonry",
                "level": "Skilled",
                "nature_of_employment": "Contract",
                "job_role": "Mason",
                "work_location": "Bengaluru"
            }
        )
        assert resp.status_code == 403
        assert "SUSPENDED" in resp.json()["detail"]


# ============================================================================
# 4. Governance Audit Log Immutability & DBAdminAuditLog Alias Tests
# ============================================================================

class TestGovernanceAuditLogImmutabilityAndQueries:

    def test_db_admin_audit_log_is_canonical_alias(self):
        assert DBAdminAuditLog is DBGovernanceAuditLog

    def test_audit_log_immutability_prevents_updates(self):
        db = SessionLocal()
        audit = DBGovernanceAuditLog(
            actor_firebase_uid="uid_admin_test",
            actor_role="ADMIN",
            action="TEST_ACTION",
            target_type="TEST_TARGET",
            target_id="123",
            previous_state="INITIAL",
            new_state="FINAL",
            reason="Integration test verification",
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)

        # Attempt to tamper with audit record
        audit.action = "TAMPERED_ACTION"
        with pytest.raises(RuntimeError, match="immutable; update operations are strictly prohibited"):
            db.commit()
        db.rollback()
        db.close()

    def test_audit_log_immutability_prevents_deletions(self):
        db = SessionLocal()
        audit = DBGovernanceAuditLog(
            actor_firebase_uid="uid_admin_test_del",
            actor_role="ADMIN",
            action="TEST_DELETE_ACTION",
            target_type="TEST_TARGET",
            target_id="456",
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)

        # Attempt to delete audit record
        db.delete(audit)
        with pytest.raises(RuntimeError, match="immutable; delete operations are strictly prohibited"):
            db.commit()
        db.rollback()
        db.close()

    def test_admin_can_query_governance_audit_logs(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}

        resp = client.get("/api/v1/admin/governance-audit-logs?limit=10", headers=headers)
        assert resp.status_code == 200, resp.text
        logs = resp.json()
        assert isinstance(logs, list)
        if logs:
            first = logs[0]
            assert "action" in first
            assert "actor_role" in first
            assert "target_type" in first
            assert "timestamp" in first


# ============================================================================
# 5. Admin RBAC Protection Tests
# ============================================================================

class TestAdminRBACProtection:

    def test_worker_cannot_access_admin_organizations(self):
        worker_jwt = create_worker_token()
        resp = client.get("/api/v1/admin/organizations", headers={"Authorization": f"Bearer {worker_jwt}"})
        assert resp.status_code == 403
        assert "Only administrators" in resp.json()["detail"]

    def test_worker_cannot_access_audit_logs(self):
        worker_jwt = create_worker_token()
        resp = client.get("/api/v1/admin/governance-audit-logs", headers={"Authorization": f"Bearer {worker_jwt}"})
        assert resp.status_code == 403

    def test_employer_cannot_provision_government_officers(self):
        _, _, emp_jwt = create_employer_user_and_org(status="ACTIVE")
        resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {emp_jwt}"},
            json={
                "full_name": "Rogue Officer",
                "official_email": "rogue@gov.in",
                "phone": "+91 9999999991",
                "department": "Labour",
                "designation": "Inspector",
                "authority_level": "STATE",
                "state": "Karnataka"
            }
        )
        assert resp.status_code == 403

    def test_unauthenticated_requests_rejected_with_401(self):
        resp = client.get("/api/v1/admin/organizations")
        assert resp.status_code == 401
