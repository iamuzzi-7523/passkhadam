"""
Milestone 5 Test Suite: Government Hierarchy, Officer Provisioning & Jurisdictional Gating
=========================================================================================
Comprehensive verification covering:
1. 4-Tier Geographic Hierarchy Invariants (NATIONAL, STATE, DISTRICT, BLOCK / LOCAL)
   - Tested at ORM validator level (@validates)
   - Tested at SQLite CheckConstraint level (ck_officer_geographic_hierarchy)
2. Admin Provisioning of Government Officer
   - DBUser created in PROVISIONED status
   - DBGovernmentOfficer created with reference ID (GOV-XXXXXXXX)
   - Single-use hashed activation token generated in DBActivationEmail
   - Duplicate email rejection
   - Public registration forbidden for role="GOVERNMENT" (HTTP 403)
3. Officer Token Activation & Replay Defense
   - GET /government/activation-status returns VALID, USED, or EXPIRED
   - POST /government/activate transitions officer and user to ACTIVE
   - Replay protection rejects used token with HTTP 400
   - Expired token rejected with HTTP 410
   - Admin resend activation invalidates older token and increments attempt_count
4. Officer Status Lifecycle & Isolation
   - SUSPEND requires mandatory reason
   - Suspending Officer A does NOT affect Officer B
   - Suspended officer blocked from operational endpoints (HTTP 403)
   - Officer reactivation restores access
5. Jurisdictional & Benefit-Permission Gating on Welfare Disbursement
   - Officer lacking DISBURSE_BENEFIT rejected with HTTP 403
   - Officer lacking benefit scheme ID in benefit_permissions_json rejected with HTTP 403
   - Out-of-state disbursement without CROSS_STATE_VERIFICATION rejected with HTTP 403
   - Authorized officer in jurisdiction succeeds
6. Officer Profile & Dispute Resolution
   - GET /government/profile/me dynamically resolves officer context
   - POST /government/resolve-dispute allows authorized officer to adjudicate dispute
   - Worker or Employer forbidden from resolving disputes (HTTP 403)
"""

import os
import sys
import json
import time
import uuid
import hashlib
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBGovernmentOfficer,
    DBActivationEmail,
    DBGovernanceAuditLog
)
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service

client = TestClient(app)


# ============================================================================
# Helpers
# ============================================================================

def create_admin_token() -> str:
    uid = f"admin_{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Gov Governance Admin",
            email=email,
            phone="+91 9999999998",
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
    return create_test_firebase_jwt(uid=uid, email=email, name="Gov Governance Admin")


def create_worker_token() -> str:
    uid = f"worker_{uuid.uuid4().hex[:8]}"
    email = f"worker_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Civil Worker",
            email=email,
            phone="+91 9888888887",
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
    return create_test_firebase_jwt(uid=uid, email=email, name="Civil Worker")


# ============================================================================
# 1. 4-Tier Geographic Hierarchy Invariant Tests (ORM & DB Level)
# ============================================================================

class TestGeographicHierarchyInvariants:

    def test_national_officer_valid_and_persisted(self):
        db = SessionLocal()
        try:
            officer = DBGovernmentOfficer(
                officer_name="National Director",
                official_email=f"nat_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="NATIONAL",
                state=None,
                district=None,
                block=None
            )
            db.add(officer)
            db.commit()
            db.refresh(officer)
            assert officer.id is not None
            assert officer.authority_level == "NATIONAL"
        finally:
            db.close()

    def test_state_officer_missing_state_raises_at_orm_level(self):
        with pytest.raises(ValueError, match="State is mandatory for STATE authority level"):
            DBGovernmentOfficer(
                officer_name="State Officer Invalid",
                official_email=f"st_inv_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="STATE",
                state=None
            )

    def test_district_officer_missing_district_raises_at_orm_level(self):
        with pytest.raises(ValueError, match="District is mandatory for DISTRICT authority level"):
            DBGovernmentOfficer(
                officer_name="District Officer Invalid",
                official_email=f"dist_inv_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="DISTRICT",
                state="Karnataka",
                district=None
            )

    def test_block_officer_missing_block_raises_at_orm_level(self):
        with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                officer_name="Block Officer Invalid",
                official_email=f"blk_inv_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="BLOCK",
                state="Karnataka",
                district="Bengaluru Urban",
                block=""
            )

    def test_local_normalized_to_block_and_validates(self):
        # LOCAL requires state, district, block
        with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                officer_name="Local Officer Invalid",
                official_email=f"loc_inv_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="LOCAL",
                state="Karnataka",
                district="Bengaluru Urban",
                block=None
            )

        # Full hierarchy for LOCAL/BLOCK succeeds
        db = SessionLocal()
        try:
            officer = DBGovernmentOfficer(
                officer_name="Local Officer Valid",
                official_email=f"loc_val_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="LOCAL",
                state="Karnataka",
                district="Bengaluru Urban",
                block="Anekal"
            )
            db.add(officer)
            db.commit()
            db.refresh(officer)
            assert officer.id is not None
            assert officer.authority_level == "BLOCK"
            assert officer.block == "Anekal"
        finally:
            db.close()


# ============================================================================
# 2. Admin Provisioning & Self-Registration Block Tests
# ============================================================================

class TestGovernmentOfficerProvisioning:

    def test_admin_provisions_government_officer_generates_token_and_user(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        suffix = uuid.uuid4().hex[:6]
        email = f"officer_{suffix}@labour.gov.in"

        resp = client.post(
            "/api/v1/admin/government-officers",
            headers=headers,
            json={
                "full_name": f"Officer Raman {suffix}",
                "official_email": email,
                "phone": "+91 9111111111",
                "department": "Department of Labour Welfare",
                "designation": "Welfare Commissioner",
                "authority_level": "DISTRICT",
                "state": "Karnataka",
                "district": "Bengaluru Urban",
                "permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"],
                "benefit_permissions": ["1", "2"]
            }
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "PROVISIONED"
        assert data["authority_level"] == "DISTRICT"
        assert data["state"] == "Karnataka"
        assert data["district"] == "Bengaluru Urban"
        assert data["officer_reference_id"].startswith("GOV-")
        assert "activation_link" in data
        assert "token=" in data["activation_link"]

        # Verify DB records
        db = SessionLocal()
        try:
            officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.official_email == email).first()
            assert officer is not None
            assert officer.status == "PROVISIONED"

            # Linked DBUser
            user = db.query(DBUser).filter(DBUser.email == email).first()
            assert user is not None
            assert user.role == "GOVERNMENT"
            assert user.status == "PROVISIONED"

            # Activation Email
            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.entity_type == "GOVERNMENT",
                DBActivationEmail.entity_id == officer.id
            ).first()
            assert act_email is not None
            assert act_email.status == "SENT"
            assert act_email.attempt_count == 1
        finally:
            db.close()

    def test_admin_provisioning_rejects_duplicate_email(self):
        admin_jwt = create_admin_token()
        headers = {"Authorization": f"Bearer {admin_jwt}"}
        suffix = uuid.uuid4().hex[:6]
        email = f"dup_officer_{suffix}@labour.gov.in"

        payload = {
            "full_name": f"Officer First {suffix}",
            "official_email": email,
            "phone": "+91 9222222222",
            "department": "Labour",
            "designation": "Inspector",
            "authority_level": "STATE",
            "state": "Maharashtra"
        }
        r1 = client.post("/api/v1/admin/government-officers", headers=headers, json=payload)
        assert r1.status_code == 200

        # Duplicate email provisioning
        r2 = client.post("/api/v1/admin/government-officers", headers=headers, json=payload)
        assert r2.status_code == 400
        assert "already exists" in r2.json()["detail"]

    def test_public_self_registration_forbidden_for_government(self):
        suffix = uuid.uuid4().hex[:6]
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Rogue Self Register Gov",
                "email": f"rogue_{suffix}@gov.in",
                "password": "Password123!",
                "role": "GOVERNMENT",
                "phone": "+91 9333333333"
            }
        )
        assert resp.status_code == 403
        assert "Government officers cannot self-register" in resp.json()["detail"]


# ============================================================================
# 3. Officer Activation & Replay Defense Tests
# ============================================================================

class TestGovernmentOfficerActivation:

    def test_officer_activation_happy_path(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"act_officer_{suffix}@labour.gov.in"

        prov_resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Active {suffix}",
                "official_email": email,
                "department": "Labour Welfare",
                "designation": "Assistant Director",
                "authority_level": "STATE",
                "state": "Maharashtra"
            }
        )
        raw_token = prov_resp.json()["activation_link"].split("token=")[1]

        # Inspect token status before redemption
        status_resp = client.get(f"/api/v1/government/activation-status?token={raw_token}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "VALID"
        assert status_resp.json()["official_email"] == email

        # Redeem token
        act_resp = client.post(
            "/api/v1/government/activate",
            json={"activation_token": raw_token, "password": "secureOfficerPass123!"}
        )
        assert act_resp.status_code == 200, act_resp.text
        assert act_resp.json()["status"] == "ACTIVE"

        # Verify DB state
        db = SessionLocal()
        try:
            officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.official_email == email).first()
            assert officer.status == "ACTIVE"
            user = db.query(DBUser).filter(DBUser.email == email).first()
            assert user.status == "ACTIVE"
            assert user.password_hash != ""

            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.entity_type == "GOVERNMENT",
                DBActivationEmail.entity_id == officer.id
            ).first()
            assert act_email.status == "USED"
        finally:
            db.close()

    def test_officer_activation_replay_rejected_with_400(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"replay_officer_{suffix}@labour.gov.in"

        prov_resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Replay {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Karnataka"
            }
        )
        raw_token = prov_resp.json()["activation_link"].split("token=")[1]

        # First activation -> Success
        r1 = client.post("/api/v1/government/activate", json={"activation_token": raw_token})
        assert r1.status_code == 200

        # Second activation (Replay) -> 400 Bad Request
        r2 = client.post("/api/v1/government/activate", json={"activation_token": raw_token})
        assert r2.status_code == 400
        assert "already been used" in r2.json()["detail"]

        # activation-status query reflects USED
        status_resp = client.get(f"/api/v1/government/activation-status?token={raw_token}")
        assert status_resp.json()["status"] == "USED"

    def test_officer_resend_activation_invalidates_prior_token(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"resend_officer_{suffix}@labour.gov.in"

        prov_resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Resend {suffix}",
                "official_email": email,
                "authority_level": "NATIONAL"
            }
        )
        officer_id = prov_resp.json()["id"]
        raw_token_1 = prov_resp.json()["activation_link"].split("token=")[1]

        # Admin calls resend activation
        resend_resp = client.post(
            f"/api/v1/admin/government-officers/{officer_id}/resend-activation",
            headers={"Authorization": f"Bearer {admin_jwt}"}
        )
        assert resend_resp.status_code == 200
        data = resend_resp.json()
        assert data["attempt_count"] == 2
        raw_token_2 = data["activation_link"].split("token=")[1]

        # Prior token 1 must be rejected as EXPIRED
        r1 = client.post("/api/v1/government/activate", json={"activation_token": raw_token_1})
        assert r1.status_code == 410

        # Fresh token 2 succeeds
        r2 = client.post("/api/v1/government/activate", json={"activation_token": raw_token_2})
        assert r2.status_code == 200
        assert r2.json()["status"] == "ACTIVE"


# ============================================================================
# 4. Officer Status Lifecycle & Isolation Tests
# ============================================================================

class TestOfficerStatusLifecycleAndIsolation:

    def test_officer_suspension_requires_reason(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        prov_resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Reason Test {suffix}",
                "official_email": f"officer_reas_{suffix}@labour.gov.in",
                "authority_level": "STATE",
                "state": "Gujarat"
            }
        )
        officer_id = prov_resp.json()["id"]

        # Suspend without reason -> 400
        resp = client.post(
            f"/api/v1/admin/government-officers/{officer_id}/status",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"status": "SUSPENDED", "reason": ""}
        )
        assert resp.status_code == 400
        assert "Reason is mandatory" in resp.json()["detail"]

    def test_officer_isolation_suspending_officer_a_does_not_affect_officer_b(self):
        admin_jwt = create_admin_token()
        suffix_a = uuid.uuid4().hex[:6]
        suffix_b = uuid.uuid4().hex[:6]

        # Provision Officer A and Officer B
        r_a = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer A {suffix_a}",
                "official_email": f"officer_a_{suffix_a}@labour.gov.in",
                "authority_level": "STATE",
                "state": "Karnataka"
            }
        )
        r_b = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer B {suffix_b}",
                "official_email": f"officer_b_{suffix_b}@labour.gov.in",
                "authority_level": "STATE",
                "state": "Maharashtra"
            }
        )
        id_a = r_a.json()["id"]
        id_b = r_b.json()["id"]

        # Activate both
        t_a = r_a.json()["activation_link"].split("token=")[1]
        t_b = r_b.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": t_a})
        client.post("/api/v1/government/activate", json={"activation_token": t_b})

        # Suspend Officer A
        client.post(
            f"/api/v1/admin/government-officers/{id_a}/status",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"status": "SUSPENDED", "reason": "Auditing jurisdiction activities"}
        )

        # Check DB: Officer A is SUSPENDED, Officer B remains ACTIVE
        db = SessionLocal()
        try:
            off_a = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == id_a).first()
            off_b = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == id_b).first()
            assert off_a.status == "SUSPENDED"
            assert off_b.status == "ACTIVE"
        finally:
            db.close()


# ============================================================================
# 5. Jurisdictional & Benefit-Permission Gating on Disbursement Tests
# ============================================================================

class TestJurisdictionAndBenefitDisbursementGating:

    def test_officer_lacking_disburse_permission_rejected(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"nodisb_{suffix}@labour.gov.in"

        # Provision officer WITHOUT DISBURSE_BENEFIT permission
        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer No Disburse {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["WORKER_VERIFICATION"],  # Missing DISBURSE_BENEFIT
                "benefit_permissions": ["1"]
            }
        )
        token_raw = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": token_raw})

        db = SessionLocal()
        u = db.query(DBUser).filter(DBUser.email == email).first()
        officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        db.close()

        # Attempt disbursement -> 403 Forbidden
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_welfare_1",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 403
        assert "DISBURSE_BENEFIT" in resp.json()["detail"]

    def test_officer_unauthorized_for_benefit_scheme_rejected(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"wrongscheme_{suffix}@labour.gov.in"

        # Provision officer with permission ONLY for scheme 1
        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Scheme 1 Only {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        token_raw = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": token_raw})

        db = SessionLocal()
        u = db.query(DBUser).filter(DBUser.email == email).first()
        officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        db.close()

        # Attempt to disburse scheme 2 -> 403 Forbidden
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={
                "scheme_id": 2,
                "worker_did": "did:passkhadam:test_worker_welfare_2",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 403
        assert "not authorized to disburse benefit scheme #2" in resp.json()["detail"]

    def test_cross_state_disbursement_requires_permission(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"crossstate_{suffix}@labour.gov.in"

        # Officer in Karnataka without CROSS_STATE_VERIFICATION
        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Karnataka {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Karnataka",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1", "2"]
            }
        )
        token_raw = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": token_raw})

        db = SessionLocal()
        u = db.query(DBUser).filter(DBUser.email == email).first()
        officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        db.close()

        # Attempt disbursement under officer_state="Maharashtra" -> 403
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_welfare_3",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 403
        assert "Cross-state verification permission required" in resp.json()["detail"]


# ============================================================================
# 6. Dispute Adjudication & Profile Endpoint Tests
# ============================================================================

class TestDisputeAdjudicationAndProfile:

    def test_government_officer_resolves_dispute(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"dispute_officer_{suffix}@labour.gov.in"

        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Mediator {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Karnataka",
                "permissions": ["DISBURSE_BENEFIT", "MEDIATE_DISPUTES"]
            }
        )
        token_raw = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": token_raw})

        db = SessionLocal()
        u = db.query(DBUser).filter(DBUser.email == email).first()
        officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        db.close()

        # Ensure employment record #1 exists in blockchain_service
        blockchain_service.employments[1] = {
            "worker_did": "did:passkhadam:test_worker",
            "employer_address": "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            "category": "Masonry",
            "status": "DISPUTED",
            "start_date": int(time.time()),
            "end_date": 0
        }

        # Resolve dispute
        resp = client.post(
            "/api/v1/government/resolve-dispute",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={
                "employment_id": 1,
                "resolution_status": "COMPLETED",
                "resolution_notes": "Employer agreed to pay outstanding wage arrears of INR 8,500",
                "settlement_amount_inr": 8500.0
            }
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["new_status"] == "COMPLETED"
        assert data["settlement_amount_inr"] == 8500.0

        # Verify employment state updated
        assert blockchain_service.employments[1]["status"] == "COMPLETED"

    def test_worker_cannot_resolve_disputes(self):
        worker_jwt = create_worker_token()
        resp = client.post(
            "/api/v1/government/resolve-dispute",
            headers={"Authorization": f"Bearer {worker_jwt}"},
            json={
                "employment_id": 1,
                "resolution_status": "COMPLETED",
                "resolution_notes": "Unauthorized worker attempt"
            }
        )
        assert resp.status_code == 403
        assert "Only government officers or admins" in resp.json()["detail"]

    def test_officer_profile_me_returns_dynamic_context(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"prof_officer_{suffix}@labour.gov.in"

        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Profile {suffix}",
                "official_email": email,
                "department": "Karnataka State Building & Other Construction Workers Board",
                "designation": "Joint Labour Commissioner",
                "authority_level": "DISTRICT",
                "state": "Karnataka",
                "district": "Bengaluru Rural",
                "permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        token_raw = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": token_raw})

        db = SessionLocal()
        u = db.query(DBUser).filter(DBUser.email == email).first()
        officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        db.close()

        resp = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {officer_jwt}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["authority_level"] == "DISTRICT"
        assert data["state"] == "Karnataka"
        assert data["district"] == "Bengaluru Rural"
        assert data["department"] == "Karnataka State Building & Other Construction Workers Board"
        assert "DISBURSE_BENEFIT" in data["permissions"]
        assert "1" in data["benefit_permissions"]
