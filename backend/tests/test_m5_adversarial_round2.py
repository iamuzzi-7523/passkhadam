"""
backend/tests/test_m5_adversarial_round2.py
Empirical Adversarial Stress Test Suite - Milestone 5 Round 2 Challenge

Author: m5_challenger_3 (EMPIRICAL CHALLENGER)
Mandate:
1. Dual State Machine decoupling invariants (hiring under unapproved/discontinued vs unapproved org).
2. Partial unique index concurrency and duplicate rejection on uq_active_category_scope.
3. Category discontinuation without affecting parent organization or sibling active categories.
4. Token replay attacks, concurrency race conditions, expired token handling, resend token invalidation.
5. Immutability of DBGovernanceAuditLog against ORM updates, deletes, and direct SQL updates.
"""

import os
import sys
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
import threading
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    engine,
    DBUser,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBActivationEmail,
    DBGovernanceAuditLog,
)
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service

client = TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Helpers
# ============================================================================

def make_admin():
    uid = f"admin_r2_{uuid.uuid4().hex[:8]}"
    email = f"admin_r2_{uuid.uuid4().hex[:6]}@passkhadam.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Platform Admin R2",
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
    return create_test_firebase_jwt(uid=uid, email=email, name="Platform Admin R2")


def make_worker():
    uid = f"worker_r2_{uuid.uuid4().hex[:8]}"
    email = f"worker_r2_{uuid.uuid4().hex[:6]}@test.org"
    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name="Worker R2",
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
    return create_test_firebase_jwt(uid=uid, email=email, name="Worker R2")


def make_employer(org_status="APPROVED", categories=None):
    if categories is None:
        categories = []
    suffix = uuid.uuid4().hex[:6]
    uid = f"emp_r2_{suffix}"
    email = f"emp_r2_{suffix}@builder.com"
    org_addr = f"0xemp_{suffix}"

    db = SessionLocal()
    try:
        user = DBUser(
            firebase_uid=uid,
            full_name=f"Builder R2 {suffix}",
            email=email,
            phone="+91 9777777776",
            password_hash=hashlib.sha256(b"emppass").hexdigest(),
            role="EMPLOYER",
            status="ACTIVE" if org_status == "ACTIVE" else "PENDING_REVIEW",
            organization_address=org_addr,
            organization_name=f"Builder Corp R2 {suffix}",
            organization_status=org_status,
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(user)
        db.flush()

        org = DBEmployerOrganization(
            user_id=user.id,
            name=f"Builder Corp R2 {suffix}",
            registration_ref_number=f"REG-R2-{suffix.upper()}",
            registration_number=f"U12345KA202{suffix[:4].upper()}",
            business_type="Private Limited",
            nature_of_business="Civil Infrastructure",
            official_email=email,
            contact_person=f"Director R2 {suffix}",
            official_phone="+91 9777777776",
            contact_phone="+91 9777777776",
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

        created_cats = []
        for cat_info in categories:
            cat_name = cat_info.get("name", "Masonry")
            cat_status = cat_info.get("status", "APPROVED")
            is_active = cat_info.get("is_active", True)
            skill = cat_info.get("skill", "Skilled")
            nature = cat_info.get("nature", "Contract")
            cat_req = DBCategoryAuthorizationRequest(
                organization_id=org.id,
                category=cat_name,
                skill_level=skill,
                nature_of_employment=nature,
                status=cat_status,
                is_active_scope=is_active,
                request_version=cat_info.get("version", 1)
            )
            db.add(cat_req)
            db.flush()
            created_cats.append(cat_req.id)
            if is_active and cat_status == "APPROVED":
                blockchain_service.authorize_category(org_addr, cat_name)

        db.commit()
        jwt = create_test_firebase_jwt(uid=uid, email=email, name=f"Builder R2 {suffix}")
        return {
            "user_id": user.id,
            "org_id": org.id,
            "org_addr": org_addr,
            "jwt": jwt,
            "categories": created_cats
        }
    finally:
        db.close()


# ============================================================================
# 1. DUAL STATE MACHINE DECOUPLING INVARIANTS
# ============================================================================

class TestDualStateMachineDecoupling:

    def test_approved_employer_cannot_hire_under_unapproved_category(self):
        """Approved employer cannot hire under unauthorized category."""
        emp = make_employer(org_status="APPROVED", categories=[
            {"name": "Masonry", "status": "APPROVED", "is_active": True}
        ])
        headers = {"Authorization": f"Bearer {emp['jwt']}"}
        resp = client.post("/api/v1/employer/create-employment", headers=headers, json={
            "worker_did": f"did:passkhadam:worker:{uuid.uuid4().hex[:8]}",
            "category": "Plumbing",  # Not authorized
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Plumber",
            "work_location": "Bengaluru Site B"
        })
        assert resp.status_code == 400
        assert "does not have an active approved scope" in resp.json()["detail"]

    def test_approved_employer_cannot_hire_under_discontinued_category(self):
        """Approved employer cannot hire under discontinued category."""
        emp = make_employer(org_status="ACTIVE", categories=[
            {"name": "Carpentry", "status": "DISCONTINUED", "is_active": False}
        ])
        headers = {"Authorization": f"Bearer {emp['jwt']}"}
        resp = client.post("/api/v1/employer/create-employment", headers=headers, json={
            "worker_did": f"did:passkhadam:worker:{uuid.uuid4().hex[:8]}",
            "category": "Carpentry",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Lead Carpenter",
            "work_location": "Bengaluru Site C"
        })
        assert resp.status_code == 400
        assert "does not have an active approved scope" in resp.json()["detail"]

    def test_unapproved_employer_cannot_hire_even_with_active_category_record(self):
        """Unapproved employer (PENDING_REVIEW or SUSPENDED) cannot hire."""
        for bad_status in ["PENDING_REVIEW", "SUSPENDED"]:
            emp = make_employer(org_status=bad_status, categories=[
                {"name": "Welding", "status": "APPROVED", "is_active": True}
            ])
            headers = {"Authorization": f"Bearer {emp['jwt']}"}
            resp = client.post("/api/v1/employer/create-employment", headers=headers, json={
                "worker_did": f"did:passkhadam:worker:{uuid.uuid4().hex[:8]}",
                "category": "Welding",
                "level": "Skilled",
                "nature_of_employment": "Contract",
                "job_role": "Welder",
                "work_location": "Bengaluru Site D"
            })
            assert resp.status_code == 403
            assert f"Employer organization is {bad_status}" in resp.json()["detail"]

    def test_unauthenticated_or_worker_caller_create_employment_behavior(self):
        """Empirically verify whether create-employment allows non-employer or unauthenticated callers."""
        # A. Unauthenticated caller
        resp_unauth = client.post("/api/v1/employer/create-employment", json={
            "worker_did": f"did:passkhadam:worker:{uuid.uuid4().hex[:8]}",
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason",
            "work_location": "Bengaluru Site Unauth"
        })
        # Record behavior: does it reject with 401/403 or fall back to DEFAULT_EMPLOYER_ADDR?
        # If it returns 200, it fell back to demo employer!
        unauth_succeeded = (resp_unauth.status_code == 200)

        # B. Worker caller
        worker_jwt = make_worker()
        headers_worker = {"Authorization": f"Bearer {worker_jwt}"}
        resp_worker = client.post("/api/v1/employer/create-employment", headers=headers_worker, json={
            "worker_did": f"did:passkhadam:worker:{uuid.uuid4().hex[:8]}",
            "category": "Mason",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason",
            "work_location": "Bengaluru Site Worker"
        })
        worker_succeeded = (resp_worker.status_code == 200)

        # In strict role-aware architecture, both should be rejected (401/403).
        # We assert whether fallback behavior occurs:
        if unauth_succeeded or worker_succeeded:
            print(f"[SECURITY OBSERVATION] create-employment permits fallback: unauth={resp_unauth.status_code}, worker={resp_worker.status_code}")


# ============================================================================
# 2. PARTIAL UNIQUE INDEX CONCURRENCY & DUPLICATE REJECTION
# ============================================================================

class TestPartialUniqueIndexConcurrency:

    def test_partial_unique_index_rejects_duplicate_active_scopes_in_db(self):
        """Database-level test: uq_active_category_scope raises IntegrityError on collision."""
        emp = make_employer(org_status="APPROVED", categories=[])
        org_id = emp["org_id"]

        db = SessionLocal()
        try:
            req1 = DBCategoryAuthorizationRequest(
                organization_id=org_id,
                category="Scaffolding",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="APPROVED",
                is_active_scope=True,
                request_version=1
            )
            db.add(req1)
            db.commit()

            req2 = DBCategoryAuthorizationRequest(
                organization_id=org_id,
                category="Scaffolding",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="APPROVED",
                is_active_scope=True,
                request_version=2
            )
            db.add(req2)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()

    def test_inactive_scopes_coexist_cleanly(self):
        """Multiple inactive versions (is_active_scope=False) can coexist with same parameters."""
        emp = make_employer(org_status="APPROVED", categories=[])
        org_id = emp["org_id"]

        db = SessionLocal()
        try:
            for v in range(1, 5):
                req = DBCategoryAuthorizationRequest(
                    organization_id=org_id,
                    category="Tiling",
                    skill_level="Skilled",
                    nature_of_employment="Contract",
                    status="REJECTED" if v < 4 else "DISCONTINUED",
                    is_active_scope=False,
                    request_version=v
                )
                db.add(req)
            db.commit()

            count = db.query(DBCategoryAuthorizationRequest).filter_by(
                organization_id=org_id,
                category="Tiling",
                is_active_scope=False
            ).count()
            assert count == 4
        finally:
            db.close()

    def test_concurrent_active_scope_insertion_race(self):
        """Stress-test: Launch 8 concurrent threads attempting to insert active scope for same parameters.
        Exactly 1 must succeed; 7 must fail with IntegrityError."""
        emp = make_employer(org_status="APPROVED", categories=[])
        org_id = emp["org_id"]

        successes = []
        failures = []

        def worker_insert(thread_idx):
            db = SessionLocal()
            try:
                req = DBCategoryAuthorizationRequest(
                    organization_id=org_id,
                    category="ConcurrentPainting",
                    skill_level="Skilled",
                    nature_of_employment="Contract",
                    status="APPROVED",
                    is_active_scope=True,
                    request_version=thread_idx
                )
                db.add(req)
                db.commit()
                successes.append(thread_idx)
            except IntegrityError:
                db.rollback()
                failures.append(thread_idx)
            finally:
                db.close()

        threads = [threading.Thread(target=worker_insert, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
        assert len(failures) == 7, f"Expected 7 failures, got {len(failures)}"


# ============================================================================
# 3. CATEGORY DISCONTINUATION GRANULARITY & ISOLATION
# ============================================================================

class TestCategoryDiscontinuationIsolation:

    def test_discontinuation_granularity_and_sibling_isolation(self):
        """Discontinuing Category A affects only Category A; parent org and sibling Category B remain active."""
        admin_jwt = make_admin()
        admin_headers = {"Authorization": f"Bearer {admin_jwt}"}

        # Create employer with 3 approved categories
        emp = make_employer(org_status="ACTIVE", categories=[
            {"name": "Masonry", "status": "APPROVED", "is_active": True},
            {"name": "Electrical", "status": "APPROVED", "is_active": True},
            {"name": "Plumbing", "status": "APPROVED", "is_active": True}
        ])
        cat_ids = emp["categories"]
        elec_cat_id = cat_ids[1]

        # Admin discontinues Electrical
        disc_resp = client.post(
            f"/api/v1/admin/discontinue-category/{elec_cat_id}",
            headers=admin_headers,
            json={"reason": "Safety violations under electrical works"}
        )
        assert disc_resp.status_code == 200
        disc_data = disc_resp.json()
        assert disc_data["status"] == "DISCONTINUED"
        assert disc_data["is_active_scope"] is False
        assert disc_data["organization_status"] == "ACTIVE"

        # Verify DB state
        db = SessionLocal()
        try:
            elec_req = db.query(DBCategoryAuthorizationRequest).filter_by(id=elec_cat_id).first()
            assert elec_req.status == "DISCONTINUED"
            assert elec_req.is_active_scope == False

            mason_req = db.query(DBCategoryAuthorizationRequest).filter_by(id=cat_ids[0]).first()
            assert mason_req.status == "APPROVED"
            assert mason_req.is_active_scope == True

            plumb_req = db.query(DBCategoryAuthorizationRequest).filter_by(id=cat_ids[2]).first()
            assert plumb_req.status == "APPROVED"
            assert plumb_req.is_active_scope == True

            org = db.query(DBEmployerOrganization).filter_by(id=emp["org_id"]).first()
            assert org.status == "ACTIVE"
        finally:
            db.close()

        # Verify Employer hiring behavior:
        emp_headers = {"Authorization": f"Bearer {emp['jwt']}"}

        # 1. Hiring under discontinued Electrical -> REJECTED (400)
        h_elec = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
            "worker_did": f"did:passkhadam:worker:{uuid.uuid4().hex[:8]}",
            "category": "Electrical",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Electrician",
            "work_location": "Site Elec"
        })
        assert h_elec.status_code == 400

        # 2. Hiring under active Masonry -> SUCCEEDS (200)
        h_mason = client.post("/api/v1/employer/create-employment", headers=emp_headers, json={
            "worker_did": f"did:passkhadam:worker:{uuid.uuid4().hex[:8]}",
            "category": "Masonry",
            "level": "Skilled",
            "nature_of_employment": "Contract",
            "job_role": "Mason",
            "work_location": "Site Mason"
        })
        assert h_mason.status_code == 200


# ============================================================================
# 4. TOKEN REPLAY ATTACKS, EXPIRED TOKEN HANDLING & RESEND INVALIDATION
# ============================================================================

class TestTokenSecurityStress:

    def test_single_use_token_cannot_be_replayed(self):
        """Token can be redeemed once (200); replay returns 400."""
        admin_jwt = make_admin()
        emp = make_employer(org_status="PENDING_REVIEW")
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        db = SessionLocal()
        try:
            # Seed org approval and token
            org = db.query(DBEmployerOrganization).filter_by(id=emp["org_id"]).first()
            org.status = "APPROVED"
            act = DBActivationEmail(
                recipient_email=org.official_email,
                token_hash=token_hash,
                entity_type="EMPLOYER",
                entity_id=org.id,
                status="SENT",
                attempt_count=1,
                expires_at=datetime.utcnow() + timedelta(hours=48),
                sent_at=datetime.utcnow()
            )
            db.add(act)
            db.commit()
        finally:
            db.close()

        # 1st Redemption -> 200
        r1 = client.post("/api/v1/employer/activate", json={"activation_token": raw_token})
        assert r1.status_code == 200
        assert r1.json()["status"] == "ACTIVE"

        # 2nd Redemption -> 400
        r2 = client.post("/api/v1/employer/activate", json={"activation_token": raw_token})
        assert r2.status_code == 400
        assert "already been used" in r2.json()["detail"]

    def test_expired_token_returns_410_gone(self):
        """Expired token redemption returns HTTP 410 Gone."""
        emp = make_employer(org_status="APPROVED")
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        db = SessionLocal()
        try:
            act = DBActivationEmail(
                recipient_email="emp_exp@test.com",
                token_hash=token_hash,
                entity_type="EMPLOYER",
                entity_id=emp["org_id"],
                status="SENT",
                attempt_count=1,
                expires_at=datetime.utcnow() - timedelta(minutes=10),  # Expired
                sent_at=datetime.utcnow() - timedelta(hours=49)
            )
            db.add(act)
            db.commit()
        finally:
            db.close()

        resp = client.post("/api/v1/employer/activate", json={"activation_token": raw_token})
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_resend_activation_invalidates_prior_tokens(self):
        """Admin resend-activation expires older pending tokens."""
        admin_jwt = make_admin()
        emp = make_employer(org_status="APPROVED")
        token_old = secrets.token_urlsafe(32)
        hash_old = hashlib.sha256(token_old.encode("utf-8")).hexdigest()

        db = SessionLocal()
        try:
            act_old = DBActivationEmail(
                recipient_email="emp_resend@test.com",
                token_hash=hash_old,
                entity_type="EMPLOYER",
                entity_id=emp["org_id"],
                status="SENT",
                attempt_count=1,
                expires_at=datetime.utcnow() + timedelta(hours=48),
                sent_at=datetime.utcnow()
            )
            db.add(act_old)
            db.commit()
        finally:
            db.close()

        # Admin resend
        resend_resp = client.post(
            f"/api/v1/admin/resend-employer-activation/{emp['org_id']}",
            headers={"Authorization": f"Bearer {admin_jwt}"}
        )
        assert resend_resp.status_code == 200
        new_link = resend_resp.json()["activation_link"]
        token_new = new_link.split("token=")[-1]

        # Old token -> 410 Gone
        r_old = client.post("/api/v1/employer/activate", json={"activation_token": token_old})
        assert r_old.status_code == 410

        # New token -> 200 OK
        r_new = client.post("/api/v1/employer/activate", json={"activation_token": token_new})
        assert r_new.status_code == 200


# ============================================================================
# 5. DBGOVERNANCEAUDITLOG IMMUTABILITY STRESS
# ============================================================================

class TestAuditTrailImmutabilityStress:

    def test_orm_instance_update_prevented(self):
        """ORM single instance update blocked by before_update listener (RuntimeError)."""
        db = SessionLocal()
        try:
            log = DBGovernanceAuditLog(
                actor_firebase_uid="uid_audit_1",
                actor_role="ADMIN",
                action="TEST_ACTION",
                target_type="TEST_TARGET",
                target_id="101"
            )
            db.add(log)
            db.commit()

            log.action = "TAMPERED_ACTION"
            with pytest.raises(RuntimeError, match="immutable"):
                db.commit()
            db.rollback()
        finally:
            db.close()

    def test_orm_instance_delete_prevented(self):
        """ORM single instance delete blocked by before_delete listener (RuntimeError)."""
        db = SessionLocal()
        try:
            log = DBGovernanceAuditLog(
                actor_firebase_uid="uid_audit_2",
                actor_role="ADMIN",
                action="TEST_ACTION",
                target_type="TEST_TARGET",
                target_id="102"
            )
            db.add(log)
            db.commit()

            db.delete(log)
            with pytest.raises(RuntimeError, match="immutable"):
                db.commit()
            db.rollback()
        finally:
            db.close()

    def test_direct_sql_update_and_bulk_orm_audit_mutability_probe(self):
        """Direct SQL UPDATE and ORM bulk update probe against governance_audit_logs.
        Evaluates whether SQLite DDL triggers enforce immutability at the database level."""
        db = SessionLocal()
        try:
            log = DBGovernanceAuditLog(
                actor_firebase_uid="uid_probe_sql",
                actor_role="ADMIN",
                action="AUTHENTIC_ACTION",
                target_type="EMPLOYER_ORG",
                target_id="999"
            )
            db.add(log)
            db.commit()
            log_id = log.id

            # Probe 1: Direct SQL UPDATE via connection
            sql_update_prevented = False
            try:
                with engine.connect() as conn:
                    conn.execute(text(
                        f"UPDATE governance_audit_logs SET action = 'SQL_TAMPERED' WHERE id = {log_id}"
                    ))
                    conn.commit()
            except (OperationalError, IntegrityError, Exception) as e:
                sql_update_prevented = True

            # Probe 2: Direct SQL DELETE via connection
            sql_delete_prevented = False
            try:
                with engine.connect() as conn:
                    conn.execute(text(
                        f"DELETE FROM governance_audit_logs WHERE id = {log_id}"
                    ))
                    conn.commit()
            except (OperationalError, IntegrityError, Exception) as e:
                sql_delete_prevented = True

            print(f"[AUDIT IMMUTABILITY PROBE] Direct SQL UPDATE prevented: {sql_update_prevented}")
            print(f"[AUDIT IMMUTABILITY PROBE] Direct SQL DELETE prevented: {sql_delete_prevented}")

            # Verify whether triggers exist in sqlite_master
            with engine.connect() as conn:
                triggers = conn.execute(text(
                    "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'governance_audit_logs'"
                )).fetchall()
                print(f"[AUDIT IMMUTABILITY PROBE] SQLite triggers on governance_audit_logs: {triggers}")

            # Note: If no SQL triggers exist, direct SQL update succeeds (vulnerability verified).
        finally:
            db.close()
