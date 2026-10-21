"""
Milestone 5 Round 3 Empirical Adversarial Stress Suite (m5_challenger_6)
=======================================================================
Adversarially stress-tests:
1. Government welfare claim disbursement:
   - Complete rejection of unauthenticated callers with HTTP 401 across token permutations
   - Rejection of suspended and provisioned officers with HTTP 403 across status permutations
2. Geographic hierarchy boundaries (NATIONAL, STATE, DISTRICT, BLOCK):
   - Strict rejection at ORM validator level (@validates)
   - Strict rejection at SQLite CheckConstraint level (ck_officer_geographic_hierarchy)
     tested on in-memory engine and active database files
   - Admin API rejection of invalid NATIONAL boundary configurations
"""

import os
import sys
import uuid
import hashlib
import sqlite3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
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


def create_admin_jwt() -> str:
    uid = f"adv6_admin_{uuid.uuid4().hex[:8]}"
    email = f"adv6_admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Gov Security Admin 6",
            email=email,
            phone="+91 9999988886",
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
    return create_test_firebase_jwt(uid=uid, email=email, name="Gov Security Admin 6")


def provision_and_activate_officer(
    admin_jwt: str,
    authority_level: str = "STATE",
    state: str = "Maharashtra",
    district: str = None,
    block: str = None,
    permissions: list = None,
    benefit_permissions: list = None
) -> tuple[int, str, str]:
    suffix = uuid.uuid4().hex[:6]
    email = f"officer_adv6_{suffix}@gov.in"
    if permissions is None:
        permissions = ["DISBURSE_BENEFIT", "WORKER_VERIFICATION"]
    if benefit_permissions is None:
        benefit_permissions = ["1", "2"]

    payload = {
        "full_name": f"Officer {suffix}",
        "official_email": email,
        "department": "Welfare Board",
        "authority_level": authority_level,
        "state": state,
        "district": district,
        "block": block,
        "permissions": permissions,
        "benefit_permissions": benefit_permissions
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        json=payload
    )
    assert resp.status_code == 200, resp.text
    officer_id = resp.json()["id"]
    token = resp.json()["activation_link"].split("token=")[1]

    # Activate
    act_resp = client.post("/api/v1/government/activate", json={"activation_token": token})
    assert act_resp.status_code == 200, act_resp.text

    db = SessionLocal()
    try:
        user = db.query(DBUser).filter(DBUser.email == email).first()
        jwt = create_test_firebase_jwt(uid=user.firebase_uid, email=email, name=user.full_name)
    finally:
        db.close()

    return officer_id, email, jwt


# ============================================================================
# Mandate 1: Welfare Claim Disbursement Unauthenticated Rejection (HTTP 401)
# ============================================================================

class TestWelfareDisbursementUnauthenticatedRejection:
    """Empirically stress-tests HTTP 401 rejection on unauthenticated callers."""

    def test_disburse_without_authorization_header_rejected_401(self):
        resp = client.post(
            "/api/v1/government/disburse-claim",
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_1",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 401
        assert "not provided" in resp.json().get("detail", "").lower() or "unauthorized" in resp.json().get("detail", "").lower()

    def test_disburse_with_empty_bearer_token_rejected_401(self):
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": "Bearer "},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_2",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 401

    def test_disburse_with_garbage_token_rejected_401(self):
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": "Bearer not_a_valid_token_at_all"},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_3",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 401

    def test_disburse_with_basic_auth_scheme_rejected_401(self):
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_4",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 401

    def test_disburse_with_nonexistent_user_token_rejected_401(self):
        token = create_test_firebase_jwt(
            uid=f"truly_ghost_adv6_{uuid.uuid4().hex}",
            email=None,
            name="Ghost Caller"
        )
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_5",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 401
        assert "Invalid or unrecognized authentication token" in resp.json().get("detail", "")

    def test_disburse_with_unregistered_mock_token_rejected_401(self):
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": "Bearer mock_firebase_token_nonexistent@unknown.org"},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_6",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 401
        assert "Invalid or unrecognized authentication token" in resp.json().get("detail", "")

    def test_disburse_with_authenticated_worker_role_rejected_403(self):
        token = create_test_firebase_jwt(
            uid=f"worker_adv6_{uuid.uuid4().hex[:6]}",
            email=f"worker_adv6_{uuid.uuid4().hex[:6]}@random.org",
            name="Ordinary Worker"
        )
        resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheme_id": 1,
                "worker_did": "did:passkhadam:test_worker_7",
                "officer_state": "Maharashtra"
            }
        )
        assert resp.status_code == 403
        assert "Only government officers or admins can disburse welfare claims" in resp.json().get("detail", "")


# ============================================================================
# Mandate 2: Suspended and Provisioned Officers Rejection (HTTP 403)
# ============================================================================

class TestSuspendedAndProvisionedOfficersRejection:
    """Empirically stress-tests HTTP 403 rejection on suspended and provisioned officers."""

    def test_provisioned_officer_disbursement_rejected_403(self):
        admin_jwt = create_admin_jwt()
        suffix = uuid.uuid4().hex[:6]
        email = f"officer_prov_{suffix}@gov.in"

        # Provision officer but DO NOT activate (user and officer remain PROVISIONED)
        resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Provisioned Officer {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        assert resp.status_code == 200

        db = SessionLocal()
        try:
            u = db.query(DBUser).filter(DBUser.email == email).first()
            jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        finally:
            db.close()

        disb_resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": f"did:passkhadam:prov_worker_{suffix}",
                "officer_state": "Maharashtra"
            }
        )
        assert disb_resp.status_code == 403
        assert "PROVISIONED" in disb_resp.json().get("detail", "")

    def test_user_active_but_officer_record_provisioned_rejected_403(self):
        """Edge case: DBUser.status is ACTIVE but DBGovernmentOfficer.status is PROVISIONED."""
        admin_jwt = create_admin_jwt()
        suffix = uuid.uuid4().hex[:6]
        email = f"officer_split_prov_{suffix}@gov.in"

        resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": f"Split Prov Officer {suffix}",
                "official_email": email,
                "authority_level": "STATE",
                "state": "Maharashtra",
                "permissions": ["DISBURSE_BENEFIT"],
                "benefit_permissions": ["1"]
            }
        )
        assert resp.status_code == 200

        db = SessionLocal()
        try:
            u = db.query(DBUser).filter(DBUser.email == email).first()
            u.status = "ACTIVE"
            db.commit()
            jwt = create_test_firebase_jwt(uid=u.firebase_uid, email=email, name=u.full_name)
        finally:
            db.close()

        disb_resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": f"did:passkhadam:split_worker_{suffix}",
                "officer_state": "Maharashtra"
            }
        )
        assert disb_resp.status_code == 403
        assert "PROVISIONED" in disb_resp.json().get("detail", "")

    def test_suspended_officer_disbursement_rejected_403(self):
        admin_jwt = create_admin_jwt()
        officer_id, email, jwt = provision_and_activate_officer(admin_jwt)

        # Suspend the officer via Admin governance endpoint
        susp_resp = client.post(
            f"/api/v1/admin/government-officers/{officer_id}/status",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"status": "SUSPENDED", "reason": "Investigation into misconduct"}
        )
        assert susp_resp.status_code == 200

        disb_resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": f"did:passkhadam:susp_worker_{uuid.uuid4().hex[:6]}",
                "officer_state": "Maharashtra"
            }
        )
        assert disb_resp.status_code == 403
        assert "SUSPENDED" in disb_resp.json().get("detail", "")

    def test_user_active_but_officer_record_suspended_rejected_403(self):
        """Edge case: DBUser.status is ACTIVE, but DBGovernmentOfficer.status is SUSPENDED."""
        admin_jwt = create_admin_jwt()
        officer_id, email, jwt = provision_and_activate_officer(admin_jwt)

        db = SessionLocal()
        try:
            off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
            off.status = "SUSPENDED"
            u = db.query(DBUser).filter(DBUser.id == off.user_id).first()
            u.status = "ACTIVE"
            db.commit()
        finally:
            db.close()

        disb_resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": f"did:passkhadam:split_susp_{uuid.uuid4().hex[:6]}",
                "officer_state": "Maharashtra"
            }
        )
        assert disb_resp.status_code == 403
        assert "SUSPENDED" in disb_resp.json().get("detail", "")

    def test_user_suspended_but_officer_record_active_rejected_403(self):
        """Edge case: DBUser.status is SUSPENDED, but DBGovernmentOfficer.status is ACTIVE."""
        admin_jwt = create_admin_jwt()
        officer_id, email, jwt = provision_and_activate_officer(admin_jwt)

        db = SessionLocal()
        try:
            off = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == officer_id).first()
            off.status = "ACTIVE"
            u = db.query(DBUser).filter(DBUser.id == off.user_id).first()
            u.status = "SUSPENDED"
            db.commit()
        finally:
            db.close()

        disb_resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": f"did:passkhadam:user_susp_{uuid.uuid4().hex[:6]}",
                "officer_state": "Maharashtra"
            }
        )
        assert disb_resp.status_code == 403
        assert "SUSPENDED" in disb_resp.json().get("detail", "")

    def test_disabled_officer_disbursement_rejected_403(self):
        admin_jwt = create_admin_jwt()
        officer_id, email, jwt = provision_and_activate_officer(admin_jwt)

        # Disable officer via Admin governance endpoint
        dis_resp = client.post(
            f"/api/v1/admin/government-officers/{officer_id}/status",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"status": "DISABLED", "reason": "Retirement"}
        )
        assert dis_resp.status_code == 200

        disb_resp = client.post(
            "/api/v1/government/disburse-claim",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "scheme_id": 1,
                "worker_did": f"did:passkhadam:disabled_{uuid.uuid4().hex[:6]}",
                "officer_state": "Maharashtra"
            }
        )
        assert disb_resp.status_code == 403


# ============================================================================
# Mandate 3: Geographic Hierarchy Boundaries (ORM & Check Constraint Level)
# ============================================================================

class TestGeographicHierarchyBoundariesStress:
    """Empirically stress-tests geographic hierarchy invariants at ORM, DB, and API levels."""

    # --- ORM Layer (@validates) ---

    def test_orm_state_level_requires_state(self):
        for invalid_state in [None, "", "   "]:
            with pytest.raises(ValueError, match="State is mandatory for STATE authority level"):
                DBGovernmentOfficer(
                    officer_name="Invalid State Officer",
                    official_email=f"orm_st_{uuid.uuid4().hex[:6]}@gov.in",
                    authority_level="STATE",
                    state=invalid_state
                )

    def test_orm_district_level_requires_state_and_district(self):
        for invalid_district in [None, "", "   "]:
            with pytest.raises(ValueError, match="District is mandatory for DISTRICT authority level"):
                DBGovernmentOfficer(
                    officer_name="Invalid District Officer",
                    official_email=f"orm_dist_{uuid.uuid4().hex[:6]}@gov.in",
                    authority_level="DISTRICT",
                    state="Karnataka",
                    district=invalid_district
                )

        for invalid_state in [None, "", "   "]:
            with pytest.raises(ValueError, match="State is mandatory for DISTRICT authority level"):
                DBGovernmentOfficer(
                    officer_name="Invalid District State Officer",
                    official_email=f"orm_dist_st_{uuid.uuid4().hex[:6]}@gov.in",
                    authority_level="DISTRICT",
                    state=invalid_state,
                    district="Bengaluru Urban"
                )

    def test_orm_block_level_requires_state_district_and_block(self):
        for invalid_block in [None, "", "   "]:
            with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
                DBGovernmentOfficer(
                    officer_name="Invalid Block Officer",
                    official_email=f"orm_blk_{uuid.uuid4().hex[:6]}@gov.in",
                    authority_level="BLOCK",
                    state="Karnataka",
                    district="Bengaluru Urban",
                    block=invalid_block
                )

        for invalid_district in [None, "", "   "]:
            with pytest.raises(ValueError, match="District is mandatory for BLOCK authority level"):
                DBGovernmentOfficer(
                    officer_name="Invalid Block Dist Officer",
                    official_email=f"orm_blk_dist_{uuid.uuid4().hex[:6]}@gov.in",
                    authority_level="BLOCK",
                    state="Karnataka",
                    district=invalid_district,
                    block="Anekal"
                )

        for invalid_state in [None, "", "   "]:
            with pytest.raises(ValueError, match="State is mandatory for BLOCK authority level"):
                DBGovernmentOfficer(
                    officer_name="Invalid Block State Officer",
                    official_email=f"orm_blk_st_{uuid.uuid4().hex[:6]}@gov.in",
                    authority_level="BLOCK",
                    state=invalid_state,
                    district="Bengaluru Urban",
                    block="Anekal"
                )

    def test_orm_local_level_normalizes_to_block_and_validates(self):
        with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                officer_name="Invalid Local Officer",
                official_email=f"orm_loc_{uuid.uuid4().hex[:6]}@gov.in",
                authority_level="LOCAL",
                state="Karnataka",
                district="Bengaluru Urban",
                block=None
            )

    # --- SQLite Database CheckConstraint Layer (ck_officer_geographic_hierarchy) ---

    def test_db_check_constraint_rejects_state_officer_with_null_state(self, memory_db):
        # Bypassing ORM validator by omitting state from kwargs
        officer = DBGovernmentOfficer(
            officer_name="Bypass State Officer",
            official_email=f"db_st_{uuid.uuid4().hex[:6]}@gov.in",
            authority_level="STATE"
        )
        memory_db.add(officer)
        with pytest.raises(IntegrityError) as exc_info:
            memory_db.commit()
        memory_db.rollback()
        assert "ck_officer_geographic_hierarchy" in str(exc_info.value).lower() or "check constraint" in str(exc_info.value).lower()

    def test_db_check_constraint_rejects_district_officer_with_null_district(self, memory_db):
        officer = DBGovernmentOfficer(
            officer_name="Bypass District Officer",
            official_email=f"db_dist_{uuid.uuid4().hex[:6]}@gov.in",
            authority_level="DISTRICT",
            state="Karnataka"
        )
        memory_db.add(officer)
        with pytest.raises(IntegrityError) as exc_info:
            memory_db.commit()
        memory_db.rollback()
        assert "ck_officer_geographic_hierarchy" in str(exc_info.value).lower() or "check constraint" in str(exc_info.value).lower()

    def test_db_check_constraint_rejects_block_officer_with_null_block(self, memory_db):
        officer = DBGovernmentOfficer(
            officer_name="Bypass Block Officer",
            official_email=f"db_blk_{uuid.uuid4().hex[:6]}@gov.in",
            authority_level="BLOCK",
            state="Karnataka",
            district="Bengaluru Urban"
        )
        memory_db.add(officer)
        with pytest.raises(IntegrityError) as exc_info:
            memory_db.commit()
        memory_db.rollback()
        assert "ck_officer_geographic_hierarchy" in str(exc_info.value).lower() or "check constraint" in str(exc_info.value).lower()

    def test_db_check_constraint_rejects_invalid_authority_level_via_sql(self):
        """Direct SQL insert with unknown authority level ('VILLAGE') violates check constraint."""
        db_path = os.path.join(BACKEND_DIR, "app", "storage", "passkhadam.db")
        if not os.path.exists(db_path):
            pytest.skip("passkhadam.db not found at storage path")

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        try:
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cur.execute("""
                    INSERT INTO government_officers (
                        officer_name, department, authority_level, state, official_email
                    ) VALUES (
                        'Village Officer', 'Rural Dept', 'VILLAGE', 'Karnataka', 'village_sql@gov.in'
                    )
                """)
                conn.commit()
            assert "check constraint" in str(exc_info.value).lower()
        finally:
            conn.rollback()
            conn.close()

    def test_all_sqlite_databases_contain_check_constraint_ddl(self):
        """Verifies ck_officer_geographic_hierarchy exists in DDL of all project SQLite databases."""
        db_paths = [
            os.path.join(BACKEND_DIR, "passkhadam.db"),
            os.path.join(BACKEND_DIR, "app", "storage", "passkhadam.db"),
            os.path.join(os.path.dirname(BACKEND_DIR), "passkhadam.db")
        ]
        for path in db_paths:
            if os.path.exists(path):
                conn = sqlite3.connect(path)
                cur = conn.cursor()
                ddl = cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='government_officers'").fetchone()
                conn.close()
                assert ddl is not None and ddl[0] is not None, f"government_officers table missing in {path}"
                assert "ck_officer_geographic_hierarchy" in ddl[0], f"Constraint missing in {path}"

    # --- API Layer: NATIONAL boundary enforcement ---

    def test_admin_api_rejects_national_officer_with_assigned_state_district_or_block(self):
        admin_jwt = create_admin_jwt()

        # National with state
        resp = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": "National Officer Illegal State",
                "official_email": f"nat_bad1_{uuid.uuid4().hex[:6]}@gov.in",
                "authority_level": "NATIONAL",
                "state": "Maharashtra"
            }
        )
        assert resp.status_code == 400
        assert "NATIONAL authority level cannot have state, district, or block assigned" in resp.json()["detail"]

        # National with district
        resp2 = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": "National Officer Illegal Dist",
                "official_email": f"nat_bad2_{uuid.uuid4().hex[:6]}@gov.in",
                "authority_level": "NATIONAL",
                "district": "Pune"
            }
        )
        assert resp2.status_code == 400

        # National with block
        resp3 = client.post(
            "/api/v1/admin/government-officers",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "full_name": "National Officer Illegal Block",
                "official_email": f"nat_bad3_{uuid.uuid4().hex[:6]}@gov.in",
                "authority_level": "NATIONAL",
                "block": "Haveli"
            }
        )
        assert resp3.status_code == 400
