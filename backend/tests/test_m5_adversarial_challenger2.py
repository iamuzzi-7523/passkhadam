"""
Milestone 5 Adversarial Challenge Suite (m5_challenger_2)
=========================================================
Empirical stress-testing of Government Hierarchy, Officer Provisioning & Welfare Disbursement Security:

1. Attack Public Registration:
   - Self-registration with role="GOVERNMENT" rejected with HTTP 403 Forbidden.
   - Case-insensitive & trimmed variations ("government", " GOVERNMENT ") rejected.
   - Database remains free of unauthorized officer/user entries.

2. Attack Geographic Invariants:
   - STATE level with empty/missing state rejected at ORM (@validates) & DB (CheckConstraint).
   - DISTRICT level with missing district rejected at ORM & DB.
   - BLOCK level with missing block rejected at ORM & DB.
   - NATIONAL level with non-null state:
     * Tested at Admin API level (POST /api/v1/admin/government-officers).
     * Tested at ORM validator level and DB CheckConstraint level to surface invariant boundaries.

3. Attack Activation Tokens:
   - Single-use token cannot be redeemed twice (Replay defense -> HTTP 400).
   - Expired tokens cannot be redeemed (Expiry defense -> HTTP 410).
   - Admin resend-activation expires older pending tokens (Revocation on re-issue).

4. Attack Welfare Disbursement Gating:
   - Unauthenticated caller attempting claim disbursement (empirically uncovers get_optional_current_user flaw).
   - Officer in PROVISIONED status attempting claim disbursement (blocked with HTTP 403).
   - Officer in SUSPENDED status attempting profile access (blocked with HTTP 403) vs disbursement (flaw).
   - Officer lacking DISBURSE_BENEFIT permission attempting claim disbursement (blocked with HTTP 403).
   - Officer attempting to disburse scheme NOT in benefit_permissions_json (blocked with HTTP 403).
   - STATE officer attempting cross-state disbursement without CROSS_STATE_VERIFICATION (blocked with HTTP 403).
   - Non-government callers (WORKER / EMPLOYER) attempting claim disbursement (blocked with HTTP 403).

5. Attack Officer Isolation:
   - Admin suspends Officer 1 in a department -> profile blocked with HTTP 403.
   - Officer 2 in the same department continues normal operations uninterrupted (profile 200, disbursement 200).
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    Base,
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
# Fixtures & Helpers
# ============================================================================

@pytest.fixture
def memory_db():
    """Create an isolated in-memory SQLite database enforcing foreign keys and CheckConstraints."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def create_admin_token() -> str:
    uid = f"adv_admin_{uuid.uuid4().hex[:8]}"
    email = f"adv_admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Gov Security Admin",
            email=email,
            phone="+91 9999988881",
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
    return create_test_firebase_jwt(uid=uid, email=email, name="Gov Security Admin")


def create_user_token(role: str) -> str:
    uid = f"adv_{role.lower()}_{uuid.uuid4().hex[:8]}"
    email = f"adv_{role.lower()}_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name=f"Test {role.capitalize()}",
            email=email,
            phone="+91 9888877771",
            password_hash=hashlib.sha256(b"pass123").hexdigest(),
            role=role,
            status="ACTIVE",
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    return create_test_firebase_jwt(uid=uid, email=email, name=f"Test {role.capitalize()}")


# ============================================================================
# 1. Attack Public Registration
# ============================================================================

class TestAttackPublicRegistration:
    """Probes whether public self-registration can bypass administrative provisioning."""

    def test_attacker_cannot_register_as_government(self):
        suffix = uuid.uuid4().hex[:6]
        email = f"attacker_gov_{suffix}@test.gov.in"
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Rogue Government Official",
                "email": email,
                "password": "MaliciousPassword123!",
                "role": "GOVERNMENT",
                "phone": "+91 9100000001"
            }
        )
        assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}: {resp.text}"
        assert "Government officers cannot self-register" in resp.json()["detail"]

        # Verify no user or officer row was written to DB
        db = SessionLocal()
        try:
            assert db.query(DBUser).filter(DBUser.email == email).first() is None
            assert db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.official_email == email).first() is None
        finally:
            db.close()

    def test_attacker_case_and_whitespace_variations_rejected(self):
        for role_variant in ["government", " GOVERNMENT ", "Government", "  GoVeRnMeNt  "]:
            suffix = uuid.uuid4().hex[:6]
            email = f"var_gov_{suffix}@test.gov.in"
            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "full_name": "Variant Attacker",
                    "email": email,
                    "password": "MaliciousPassword123!",
                    "role": role_variant,
                    "phone": "+91 9100000002"
                }
            )
            assert resp.status_code == 403, f"Failed on role variant '{role_variant}': got {resp.status_code}"


# ============================================================================
# 2. Attack Geographic Invariants
# ============================================================================

class TestAttackGeographicInvariants:
    """Stress-tests geographic invariants at ORM, DB CheckConstraint, and API boundaries."""

    def test_state_level_empty_state_orm_and_db(self, memory_db):
        # 1. ORM Level
        with pytest.raises(ValueError, match="State is mandatory for STATE authority level"):
            DBGovernmentOfficer(
                officer_name="State Officer Invalid",
                official_email=f"st_empty_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="STATE",
                state=""
            )

        # 2. DB Level (omitted state in kwargs bypasses ORM init validator)
        officer = DBGovernmentOfficer(
            officer_name="Bypass State Officer",
            official_email=f"st_bypass_{uuid.uuid4().hex[:6]}@gov.in",
            authority_level="STATE"
        )
        memory_db.add(officer)
        with pytest.raises(IntegrityError):
            memory_db.commit()
        memory_db.rollback()

    def test_district_level_missing_district_orm_and_db(self, memory_db):
        # 1. ORM Level
        with pytest.raises(ValueError, match="District is mandatory for DISTRICT authority level"):
            DBGovernmentOfficer(
                officer_name="District Officer Invalid",
                official_email=f"dist_empty_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="DISTRICT",
                state="Karnataka",
                district=""
            )

        # 2. DB Level (omitted district)
        officer = DBGovernmentOfficer(
            officer_name="Bypass District Officer",
            official_email=f"dist_bypass_{uuid.uuid4().hex[:6]}@gov.in",
            authority_level="DISTRICT",
            state="Karnataka"
        )
        memory_db.add(officer)
        with pytest.raises(IntegrityError):
            memory_db.commit()
        memory_db.rollback()

    def test_block_level_missing_block_orm_and_db(self, memory_db):
        # 1. ORM Level
        with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                officer_name="Block Officer Invalid",
                official_email=f"blk_empty_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="BLOCK",
                state="Karnataka",
                district="Bengaluru Urban",
                block=""
            )

        # 2. DB Level (omitted block)
        officer = DBGovernmentOfficer(
            officer_name="Bypass Block Officer",
            official_email=f"blk_bypass_{uuid.uuid4().hex[:6]}@gov.in",
            authority_level="BLOCK",
            state="Karnataka",
            district="Bengaluru Urban"
        )
        memory_db.add(officer)
        with pytest.raises(IntegrityError):
            memory_db.commit()
        memory_db.rollback()

    def test_national_level_with_state_api_gating(self):
        """Admin API endpoint MUST reject NATIONAL officers with state assigned."""
        admin_jwt = create_admin_token()
        resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": "National With State Attacker",
                "official_email": f"nat_state_{uuid.uuid4().hex[:6]}@gov.in",
                "authority_level": "NATIONAL",
                "state": "Karnataka"  # Illegal for NATIONAL
            }
        )
        assert resp.status_code == 400
        assert "NATIONAL authority level cannot have state, district, or block assigned" in resp.json()["detail"]

    def test_national_level_with_state_orm_and_db_boundary_observation(self, memory_db):
        """
        Adversarial Observation:
        Inspect whether ORM validator or DB CheckConstraint rejects NATIONAL with non-null state.
        The Admin API endpoint enforces this (status 400), but at the lower DB level:
        ck_officer_geographic_hierarchy evaluates (authority_level = 'NATIONAL') to TRUE,
        and @validates only checks STATE/DISTRICT/BLOCK levels.
        """
        email = f"nat_orm_{uuid.uuid4().hex[:6]}@gov.in"
        officer = DBGovernmentOfficer(
            officer_name="Nat ORM Boundary Test",
            official_email=email,
            authority_level="NATIONAL",
            state="Karnataka"
        )
        memory_db.add(officer)
        memory_db.commit()
        memory_db.refresh(officer)
        # Confirmed: lower DB CheckConstraint allows NATIONAL with state,
        # meaning API layer is the authoritative barrier.
        assert officer.id is not None
        memory_db.delete(officer)
        memory_db.commit()


# ============================================================================
# 3. Attack Activation Tokens
# ============================================================================

class TestAttackActivationTokens:
    """Stress-tests token lifecycle, replay resistance, expiration, and revocation."""

    def test_token_cannot_be_redeemed_twice_replay_attack(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"replay_adv_{suffix}@gov.in"

        prov_resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Replay {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra"
            }
        )
        raw_token = prov_resp.json()["activation_link"].split("token=")[1]

        # 1st Redemption: Success
        r1 = client.post("/api/v1/government/activate", json={"activation_token": raw_token, "password": "Pass123!"})
        assert r1.status_code == 200
        assert r1.json()["status"] == "ACTIVE"

        # 2nd Redemption: Replay Rejected (400 Bad Request)
        r2 = client.post("/api/v1/government/activate", json={"activation_token": raw_token, "password": "Pass123!"})
        assert r2.status_code == 400
        assert "already been used" in r2.json()["detail"]

        # Status inspection reflects USED
        st = client.get(f"/api/v1/government/activation-status?token={raw_token}")
        assert st.json()["status"] == "USED"

    def test_expired_token_redemption_rejected(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"exp_adv_{suffix}@gov.in"

        prov_resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Expired {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra"
            }
        )
        officer_id = prov_resp.json()["id"]
        raw_token = prov_resp.json()["activation_link"].split("token=")[1]

        # Manually backdate token expiration in DB
        db = SessionLocal()
        try:
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.token_hash == token_hash
            ).first()
            act_email.expires_at = datetime.utcnow() - timedelta(hours=2)
            db.commit()
        finally:
            db.close()

        # Activation attempt MUST return 410 Gone
        resp = client.post("/api/v1/government/activate", json={"activation_token": raw_token, "password": "Pass123!"})
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_resend_activation_invalidates_older_token(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"resend_adv_{suffix}@gov.in"

        prov_resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Resend {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra"
            }
        )
        officer_id = prov_resp.json()["id"]
        token_1 = prov_resp.json()["activation_link"].split("token=")[1]

        # Resend activation
        resend_resp = client.post(
            f"/api/v1/admin/government-officers/{officer_id}/resend-activation",
            headers={"Authorization": f"Bearer {admin_jwt}"}
        )
        assert resend_resp.status_code == 200
        token_2 = resend_resp.json()["activation_link"].split("token=")[1]

        # Token 1 is now revoked/EXPIRED -> 410 Gone
        r_old = client.post("/api/v1/government/activate", json={"activation_token": token_1})
        assert r_old.status_code == 410

        # Token 2 succeeds
        r_new = client.post("/api/v1/government/activate", json={"activation_token": token_2, "password": "NewPass123!"})
        assert r_new.status_code == 200
        assert r_new.json()["status"] == "ACTIVE"


# ============================================================================
# 4. Attack Welfare Disbursement Gating
# ============================================================================

class TestAttackWelfareDisbursementGating:
    """Stress-tests authentication, status gating, permissions, scheme scope, and jurisdiction."""

    def test_unauthenticated_caller_disbursement_security_audit(self):
        """
        Adversarial Probe:
        Can an unauthenticated caller POST to /api/v1/government/disburse-claim?
        EMPIRICAL OBSERVATION:
        The route specifies `current_user: Optional[DBUser] = Depends(get_optional_current_user)`.
        If unauthenticated, `current_user` is None, and the handler falls back to
        DEFAULT_GOV_ADDR ("0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65") which is pre-approved
        in blockchain_service.organizations, allowing unauthenticated callers to disburse claims!
        This confirms the auth-bypass vulnerability on welfare disbursement.
        """
        resp = client.post(
            "/api/v1/government/disburse-claim",
            json={
                "scheme_id": 1,
                "worker_did": f"did:passkhadam:unauth_adv_{uuid.uuid4().hex[:6]}",
                "officer_state": "Maharashtra"
            }
        )
        # Remediated: unauthenticated callers are rejected with HTTP 401 Unauthorized!
        assert resp.status_code == 401

    def test_provisioned_officer_cannot_disburse(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"prov_disb_{suffix}@gov.in"

        # Provision officer but DO NOT activate (remains PROVISIONED)
        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Prov {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        db = SessionLocal()
        try:
            u = db.query(DBUser).filter(DBUser.email == email).first()
            officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        finally:
            db.close()

        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={"scheme_id": 1, "worker_did": "did:passkhadam:test_prov", "officer_state": "Maharashtra"}
        )
        assert resp.status_code == 403
        assert "PROVISIONED" in resp.json()["detail"]

    def test_suspended_officer_status_enforcement_audit(self):
        """
        Adversarial Probe:
        When an officer is suspended, are they blocked from operations?
        1. On GET /api/v1/government/profile/me:
           - Depends(get_current_user) correctly enforces status -> HTTP 403 Forbidden.
        2. On POST /api/v1/government/disburse-claim:
           - Depends(get_optional_current_user) catches the 403 exception and swallows it,
             converting current_user into None!
           - The endpoint then falls back to DEFAULT_GOV_ADDR and returns HTTP 200 OK!
        This is a critical security vulnerability: suspended officers can still disburse claims.
        """
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"susp_disb_{suffix}@gov.in"

        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Susp {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        raw_token = prov.json()["activation_link"].split("token=")[1]
        officer_id = prov.json()["id"]

        # Activate
        client.post("/api/v1/government/activate", json={"activation_token": raw_token})

        # Suspend
        client.post(
            f"/api/v1/admin/government-officers/{officer_id}/status",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"status": "SUSPENDED", "reason": "Audit review under investigation"}
        )

        db = SessionLocal()
        try:
            u = db.query(DBUser).filter(DBUser.email == email).first()
            officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        finally:
            db.close()

        # Operational query /profile/me is correctly blocked: 403 Forbidden
        p_resp = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {officer_jwt}"})
        assert p_resp.status_code == 403
        assert "Account is suspended" in p_resp.json()["detail"]

        # But disburse-claim suffers from get_optional_current_user exception-swallowing flaw
        d_resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={"scheme_id": 1, "worker_did": "did:passkhadam:test_susp", "officer_state": "Maharashtra"}
        )
        # Remediated: suspended officer is rejected with HTTP 403 Forbidden!
        assert d_resp.status_code == 403

    def test_officer_lacking_disburse_benefit_permission_rejected(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"noperm_disb_{suffix}@gov.in"

        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer No Perm {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["WORKER_VERIFICATION"],  # Missing DISBURSE_BENEFIT
                "benefit_permissions": ["1"]
            }
        )
        raw_token = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": raw_token})

        db = SessionLocal()
        try:
            u = db.query(DBUser).filter(DBUser.email == email).first()
            officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        finally:
            db.close()

        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={"scheme_id": 1, "worker_did": "did:passkhadam:test_noperm", "officer_state": "Maharashtra"}
        )
        assert resp.status_code == 403
        assert "DISBURSE_BENEFIT" in resp.json()["detail"]

    def test_officer_disbursing_unlisted_benefit_scheme_rejected(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"scheme_disb_{suffix}@gov.in"

        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Scheme 1 Only {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]  # ONLY Scheme 1
            }
        )
        raw_token = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": raw_token})

        db = SessionLocal()
        try:
            u = db.query(DBUser).filter(DBUser.email == email).first()
            officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        finally:
            db.close()

        # Attempt Scheme 2 -> 403 Forbidden
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={"scheme_id": 2, "worker_did": "did:passkhadam:test_unlisted_scheme", "officer_state": "Maharashtra"}
        )
        assert resp.status_code == 403
        assert "not authorized to disburse benefit scheme #2" in resp.json()["detail"]

    def test_state_officer_cross_state_disbursement_without_permission_rejected(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        email = f"jurisdiction_{suffix}@gov.in"

        # Karnataka Officer WITHOUT CROSS_STATE_VERIFICATION
        prov = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Karnataka {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Karnataka",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        raw_token = prov.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": raw_token})

        db = SessionLocal()
        try:
            u = db.query(DBUser).filter(DBUser.email == email).first()
            officer_jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        finally:
            db.close()

        # Attempt disbursement in Maharashtra -> 403 Forbidden
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {officer_jwt}"},
            json={"scheme_id": 1, "worker_did": "did:passkhadam:test_cross_state", "officer_state": "Maharashtra"}
        )
        assert resp.status_code == 403
        assert "Cross-state verification permission required" in resp.json()["detail"]

    def test_non_government_roles_cannot_disburse_claims(self):
        worker_jwt = create_user_token("WORKER")
        employer_jwt = create_user_token("EMPLOYER")

        for jwt in [worker_jwt, employer_jwt]:
            resp = client.post(
                "/api/v1/government/disburse-claim",
                headers={"Authorization": f"Bearer {jwt}"},
                json={
                    "scheme_id": 1,
                    "worker_did": "did:passkhadam:test_non_gov",
                    "officer_state": "Maharashtra"
                }
            )
            assert resp.status_code == 403
            assert "Only government officers or admins can disburse welfare claims" in resp.json()["detail"]


# ============================================================================
# 5. Attack Officer Isolation
# ============================================================================

class TestAttackOfficerIsolation:
    """Probes whether administrative actions against Officer 1 leak or affect Officer 2."""

    def test_suspending_officer_1_does_not_affect_officer_2(self):
        admin_jwt = create_admin_token()
        suffix = uuid.uuid4().hex[:6]
        dept = "State Department of Labour Welfare"

        # Provision Officer 1
        r1 = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer One {suffix}",
                "official_email": f"officer_1_{suffix}@labour.gov.in",
                "department": dept,
                "authority_level": "STATE",
                "state": "Karnataka",
                "wallet_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        # Provision Officer 2 in the SAME department
        r2 = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Officer Two {suffix}",
                "official_email": f"officer_2_{suffix}@labour.gov.in",
                "department": dept,
                "authority_level": "STATE",
                "state": "Karnataka",
                "wallet_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        id_1 = r1.json()["id"]
        id_2 = r2.json()["id"]

        # Activate both
        t_1 = r1.json()["activation_link"].split("token=")[1]
        t_2 = r2.json()["activation_link"].split("token=")[1]
        client.post("/api/v1/government/activate", json={"activation_token": t_1})
        client.post("/api/v1/government/activate", json={"activation_token": t_2})

        # Fetch JWTs
        db = SessionLocal()
        try:
            u1 = db.query(DBUser).filter(DBUser.email == f"officer_1_{suffix}@labour.gov.in").first()
            u2 = db.query(DBUser).filter(DBUser.email == f"officer_2_{suffix}@labour.gov.in").first()
            jwt_1 = create_test_firebase_jwt(uid=u1.firebase_uid, email=u1.email, name=u1.full_name)
            jwt_2 = create_test_firebase_jwt(uid=u2.firebase_uid, email=u2.email, name=u2.full_name)
        finally:
            db.close()

        # Both initially active
        p1 = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {jwt_1}"})
        p2 = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {jwt_2}"})
        assert p1.status_code == 200
        assert p2.status_code == 200

        # Suspend Officer 1
        client.post(
            f"/api/v1/admin/government-officers/{id_1}/status",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"status": "SUSPENDED", "reason": "Officer 1 under integrity inquiry"}
        )

        # Officer 1's profile access is blocked
        p1_susp = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {jwt_1}"})
        assert p1_susp.status_code == 403
        assert "Account is suspended" in p1_susp.json()["detail"]

        # Officer 2 remains fully operational: profile query succeeds
        prof_2 = client.get("/api/v1/government/profile/me", headers={"Authorization": f"Bearer {jwt_2}"})
        assert prof_2.status_code == 200
        assert prof_2.json()["department"] == dept

        # Officer 2 disbursement succeeds without interruption
        d2 = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {jwt_2}"},
            json={"scheme_id": 1, "worker_did": "did:passkhadam:test_iso_2", "officer_state": "Karnataka"}
        )
        assert d2.status_code == 200, f"Officer 2 disbursement failed: {d2.text}"
        assert d2.json()["claim_record"]["is_disbursed"] is True
