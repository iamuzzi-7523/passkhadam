import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBEmployerOrganization, DBActivationEmail
from app.services.blockchain_service import blockchain_service

client = TestClient(app)


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ==============================================================================
# CHALLENGE SUITE 1: Fake / Arbitrary / Malformed Tokens to POST /api/v1/auth/activate-employer
# ==============================================================================

def test_adv_c1_fake_tokens_with_password_cannot_hijack_apexinfra():
    """
    TASK OBJECTIVE 1:
    Submit fake / arbitrary / malformed tokens to POST /api/v1/auth/activate-employer with a password:
    Verify it rejects with HTTP 404 (or 400) and NEVER activates employer@apexinfra.com or overwrites their password.
    """
    db = SessionLocal()
    try:
        # 1. Query baseline employer@apexinfra.com state
        apex_user = db.query(DBUser).filter(DBUser.email == "employer@apexinfra.com").first()
        assert apex_user is not None, "employer@apexinfra.com user must exist"
        initial_pw_hash = apex_user.password_hash
        initial_status = apex_user.status
        initial_org_status = apex_user.organization_status

        apex_org = db.query(DBEmployerOrganization).filter(
            DBEmployerOrganization.official_email == "employer@apexinfra.com"
        ).first()
        initial_org_db_status = apex_org.status if apex_org else None

        adversarial_tokens = [
            ("totally_arbitrary_fake_token_xyz987", 404),
            ("act_sec_nonexistent_addr_9999", 404),
            ("' OR '1'='1' --", 404),
            ("../../etc/shadow", 404),
            ("ACT_B906_SECURE", 404),  # Case-sensitivity check
            ("act_b906_secure_extra_suffix", 404),
            ("   act_nonexistent_spaced   ", 404),
            ("0x90F79bf6EB2c4f870365E785982E1f101E93b906", 404),
            (secrets.token_urlsafe(64), 404),
            ("a" * 5000, 404),  # Extremely long input
            ("\x00\x01\x02malformed_hex", 404),
            ("", 400),  # Empty string
            ("     ", 400),  # Whitespace-only string
        ]

        malicious_password = "AttackerHijackedPassword2026!"

        for token_input, expected_status in adversarial_tokens:
            payload = {
                "activation_token": token_input,
                "password": malicious_password
            }
            resp = client.post("/api/v1/auth/activate-employer", json=payload)
            assert resp.status_code == expected_status, (
                f"Expected status {expected_status} for token '{token_input[:30]}', got {resp.status_code}: {resp.text}"
            )

            # Empirically verify DB state after EVERY adversarial attempt:
            # employer@apexinfra.com must NOT have its password overwritten or status mutated
            db.expire_all()
            reloaded_user = db.query(DBUser).filter(DBUser.email == "employer@apexinfra.com").first()
            assert reloaded_user.password_hash == initial_pw_hash, (
                f"CRITICAL VULNERABILITY: Password hash of employer@apexinfra.com was overwritten by token '{token_input[:30]}'!"
            )
            assert reloaded_user.status == initial_status, (
                f"Status of employer@apexinfra.com was unexpectedly altered by token '{token_input[:30]}'!"
            )
            assert reloaded_user.organization_status == initial_org_status

            if apex_org:
                reloaded_org = db.query(DBEmployerOrganization).filter(
                    DBEmployerOrganization.official_email == "employer@apexinfra.com"
                ).first()
                assert reloaded_org.status == initial_org_db_status

        # Also test None activation token
        resp_none = client.post("/api/v1/auth/activate-employer", json={
            "activation_token": None,
            "password": malicious_password
        })
        assert resp_none.status_code in [400, 422]
        db.expire_all()
        reloaded_user = db.query(DBUser).filter(DBUser.email == "employer@apexinfra.com").first()
        assert reloaded_user.password_hash == initial_pw_hash

    finally:
        db.close()


# ==============================================================================
# CHALLENGE SUITE 2: Submitting Tokens Without Password (No 500 AttributeError)
# ==============================================================================

def test_adv_c2_tokens_without_password_no_500_attribute_error():
    """
    TASK OBJECTIVE 2:
    Submit fake tokens without a password: verify it does not crash with HTTP 500 AttributeError.
    Also verify a genuine token redemption without password succeeds cleanly without crashing on hash_pw(None).
    """
    db = SessionLocal()
    try:
        # 1. Fake tokens without password
        fake_payloads = [
            {"activation_token": "fake_token_no_pw_1"},
            {"activation_token": "fake_token_no_pw_2", "password": None},
            {"activation_token": "fake_token_no_pw_3", "password": ""},
            {"activation_token": "", "password": None},
            {"activation_token": "   ", "password": None},
            {"activation_token": None, "password": None},
        ]

        for payload in fake_payloads:
            resp = client.post("/api/v1/auth/activate-employer", json=payload)
            # Must reject with 404, 400, or 422 - NEVER HTTP 500
            assert resp.status_code in [400, 404, 422], (
                f"Expected 400/404/422 but got {resp.status_code}: {resp.text}"
            )
            assert resp.status_code != 500, (
                f"CRASH DETECTED: Endpoint returned HTTP 500 for payload {payload}: {resp.text}"
            )

        # 2. Genuine token redemption WITHOUT password:
        # Create a fresh test organization and user
        unique_id = uuid.uuid4().hex[:8]
        test_email = f"emp_nopw_{unique_id}@testorg.com"
        initial_pw = "OriginalExistingPass123"
        test_user = DBUser(
            email=test_email,
            full_name=f"No Password Corp {unique_id}",
            phone="+91 9876543210",
            password_hash=hash_pw(initial_pw),
            role="EMPLOYER",
            status="PENDING_REVIEW",
            organization_status="APPROVED",
            is_email_verified=True,
            is_phone_verified=True,
            firebase_uid=f"uid_nopw_{unique_id}"
        )
        db.add(test_user)
        db.flush()

        test_org = DBEmployerOrganization(
            user_id=test_user.id,
            name=f"No Password Corp {unique_id}",
            registration_ref_number=f"REF-NOPW-{unique_id}",
            official_email=test_email,
            org_address=f"0xemp_nopw_{unique_id}",
            status="APPROVED"
        )
        db.add(test_org)
        db.flush()

        raw_token = f"act_nopw_{secrets.token_urlsafe(24)}"
        act_rec = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=test_org.id,
            recipient_email=test_email,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=7),
            attempt_count=1
        )
        db.add(act_rec)
        db.commit()

        # Submit activation request with NO password
        success_resp = client.post("/api/v1/auth/activate-employer", json={
            "activation_token": raw_token,
            "password": None
        })
        assert success_resp.status_code == 200, (
            f"Expected 200 for valid token with password=None, got {success_resp.status_code}: {success_resp.text}"
        )
        data = success_resp.json()
        assert data["status"] == "SUCCESS"
        assert data["email"] == test_email

        # Verify DB state: user is ACTIVE, but password_hash was NOT corrupted/None
        db.expire_all()
        reloaded = db.query(DBUser).filter(DBUser.id == test_user.id).first()
        assert reloaded.status == "ACTIVE"
        assert reloaded.password_hash == hash_pw(initial_pw), "Original password hash should be preserved when password is None"

    finally:
        db.close()


# ==============================================================================
# CHALLENGE SUITE 3: Double Activation / Replay on GET /activate-account/{token}
# ==============================================================================

def test_adv_c3_double_activation_replay_defense_and_cross_tenant_isolation():
    """
    TASK OBJECTIVE 3:
    Test double activation / replay on GET /api/v1/employer/activate-account/{token}:
    Verify that after a token is consumed, a second attempt rejects with HTTP 400 and NEVER activates a different organization.
    """
    db = SessionLocal()
    try:
        # Create Organization A (victim of replay)
        org_a_id = uuid.uuid4().hex[:6]
        org_a_addr = f"0xemp_rep_a_{org_a_id}"
        org_a_email = f"org_a_{org_a_id}@replaytest.org"
        org_a = DBEmployerOrganization(
            name=f"Replay Org A {org_a_id}",
            registration_ref_number=f"REF-A-{org_a_id}",
            official_email=org_a_email,
            org_address=org_a_addr,
            status="APPROVED"
        )
        db.add(org_a)
        db.flush()

        raw_token_a = f"act_sec_{secrets.token_urlsafe(20)}"
        act_email_a = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=org_a.id,
            recipient_email=org_a_email,
            token_hash=hashlib.sha256(raw_token_a.encode("utf-8")).hexdigest(),
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=7),
            attempt_count=1
        )
        db.add(act_email_a)

        # Create Organization B (foreign organization that must NEVER be activated by token A replay)
        org_b_id = uuid.uuid4().hex[:6]
        org_b_addr = f"0xemp_rep_b_{org_b_id}"
        org_b_email = f"org_b_{org_b_id}@replaytest.org"
        org_b = DBEmployerOrganization(
            name=f"Foreign Org B {org_b_id}",
            registration_ref_number=f"REF-B-{org_b_id}",
            official_email=org_b_email,
            org_address=org_b_addr,
            status="APPROVED"
        )
        db.add(org_b)
        db.flush()

        raw_token_b = f"act_sec_{secrets.token_urlsafe(20)}"
        act_email_b = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=org_b.id,
            recipient_email=org_b_email,
            token_hash=hashlib.sha256(raw_token_b.encode("utf-8")).hexdigest(),
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=7),
            attempt_count=1
        )
        db.add(act_email_b)
        db.commit()

        # Register both in blockchain service
        blockchain_service.register_organization(org_a_addr, org_a.name, org_a.registration_ref_number, "KA", "EMPLOYER", ["Mason"])
        blockchain_service.set_org_status(org_a_addr, "APPROVED", "Approved Org A")
        blockchain_service.register_organization(org_b_addr, org_b.name, org_b.registration_ref_number, "KA", "EMPLOYER", ["Electrician"])
        blockchain_service.set_org_status(org_b_addr, "APPROVED", "Approved Org B")

        # 1. First redemption: Org A activates successfully
        first_resp = client.get(f"/api/v1/employer/activate-account/{raw_token_a}")
        assert first_resp.status_code == 200
        assert first_resp.json()["status"] == "ACTIVE"

        # Verify Org A is now ACTIVE, token A is USED
        db.expire_all()
        reloaded_a = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_a.id).first()
        reloaded_tok_a = db.query(DBActivationEmail).filter(DBActivationEmail.id == act_email_a.id).first()
        assert reloaded_a.status == "ACTIVE"
        assert reloaded_tok_a.status == "USED"

        # Verify Org B is STILL APPROVED, token B is STILL PENDING
        reloaded_b = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_b.id).first()
        reloaded_tok_b = db.query(DBActivationEmail).filter(DBActivationEmail.id == act_email_b.id).first()
        assert reloaded_b.status == "APPROVED"
        assert reloaded_tok_b.status == "PENDING"

        # 2. Second attempt (REPLAY) of token A:
        # MUST reject with HTTP 400
        second_resp = client.get(f"/api/v1/employer/activate-account/{raw_token_a}")
        assert second_resp.status_code == 400, (
            f"Expected HTTP 400 on replay of token A, but got {second_resp.status_code}: {second_resp.text}"
        )
        assert "already been used" in second_resp.json()["detail"].lower()

        # CRITICAL ASSERTION: Org B must NEVER have been activated by token A replay!
        db.expire_all()
        reloaded_b_after = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_b.id).first()
        reloaded_tok_b_after = db.query(DBActivationEmail).filter(DBActivationEmail.id == act_email_b.id).first()
        assert reloaded_b_after.status == "APPROVED", (
            f"CRITICAL CROSS-TENANT FLAW: Org B status became '{reloaded_b_after.status}' after Org A token replay!"
        )
        assert reloaded_tok_b_after.status == "PENDING"

        # 3. Third and fourth repeated replay attempts
        for attempt in range(3, 6):
            multi_resp = client.get(f"/api/v1/employer/activate-account/{raw_token_a}")
            assert multi_resp.status_code == 400
            assert "already been used" in multi_resp.json()["detail"].lower()

        # 4. Cross-endpoint replay attack:
        # Attempting to replay token A via POST /api/v1/auth/activate-employer
        cross_resp_auth = client.post("/api/v1/auth/activate-employer", json={
            "activation_token": raw_token_a,
            "password": "AnyPassword123!"
        })
        assert cross_resp_auth.status_code == 400
        assert "already been used" in cross_resp_auth.json()["detail"].lower()

        # Attempting to replay token A via POST /api/v1/employer/activate
        cross_resp_emp = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_token_a,
            "password": "AnyPassword123!"
        })
        assert cross_resp_emp.status_code == 400
        assert "already been used" in cross_resp_emp.json()["detail"].lower()

    finally:
        db.close()


def test_adv_c3_legacy_suffix_token_cannot_cross_activate_foreign_org():
    """
    Stress-test the legacy backward compatibility resolver `act_sec_<suffix>`:
    Ensure that when multiple organizations exist with similar address suffixes,
    a reused legacy token rejects with 400 and NEVER jumps to another organization.
    """
    db = SessionLocal()
    try:
        suffix = "998877"
        addr_1 = f"0xemp_test1_{suffix}"
        addr_2 = f"0xemp_test2_{suffix}"

        org1 = DBEmployerOrganization(
            name="Org Suffix 1",
            registration_ref_number="REF-S1",
            official_email="s1@test.org",
            org_address=addr_1,
            status="APPROVED"
        )
        db.add(org1)
        db.flush()

        org2 = DBEmployerOrganization(
            name="Org Suffix 2",
            registration_ref_number="REF-S2",
            official_email="s2@test.org",
            org_address=addr_2,
            status="APPROVED"
        )
        db.add(org2)
        db.flush()

        legacy_token = f"act_sec_{suffix}"
        tok_hash = hashlib.sha256(legacy_token.encode("utf-8")).hexdigest()

        act1 = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=org1.id,
            recipient_email="s1@test.org",
            token_hash=tok_hash,
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=7),
            attempt_count=1
        )
        db.add(act1)
        db.commit()

        blockchain_service.register_organization(addr_1, "Org Suffix 1", "REF-S1", "KA", "EMPLOYER", ["Mason"])
        blockchain_service.set_org_status(addr_1, "APPROVED", "Approved S1")
        blockchain_service.register_organization(addr_2, "Org Suffix 2", "REF-S2", "KA", "EMPLOYER", ["Mason"])
        blockchain_service.set_org_status(addr_2, "APPROVED", "Approved S2")

        # 1. Activate Org 1
        resp1 = client.get(f"/api/v1/employer/activate-account/{legacy_token}")
        assert resp1.status_code == 200

        # 2. Replay token
        resp2 = client.get(f"/api/v1/employer/activate-account/{legacy_token}")
        assert resp2.status_code == 400
        assert "already been used" in resp2.json()["detail"].lower()

        # Org 2 must remain untouched
        db.expire_all()
        reloaded_org2 = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org2.id).first()
        assert reloaded_org2.status == "APPROVED"

    finally:
        db.close()


# ==============================================================================
# CHALLENGE SUITE 4: Expired Tokens Reject with HTTP 410
# ==============================================================================

def test_adv_c4_expired_tokens_reject_with_http_410_across_all_endpoints():
    """
    TASK OBJECTIVE 4:
    Verify that expired tokens reject with HTTP 410 across:
    1. GET /api/v1/employer/activate-account/{token}
    2. POST /api/v1/auth/activate-employer
    3. POST /api/v1/employer/activate
    Both for status="EXPIRED" and for time-based expiration (expires_at < utcnow()).
    """
    db = SessionLocal()
    try:
        # Case A: Explicit status="EXPIRED" in DB
        uid_a = uuid.uuid4().hex[:6]
        org_a = DBEmployerOrganization(
            name=f"Expired Org A {uid_a}",
            registration_ref_number=f"REF-EXP-A-{uid_a}",
            official_email=f"exp_a_{uid_a}@test.org",
            org_address=f"0xemp_exp_a_{uid_a}",
            status="APPROVED"
        )
        db.add(org_a)
        db.flush()

        raw_tok_a = f"act_expired_status_{uid_a}"
        act_a = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=org_a.id,
            recipient_email=org_a.official_email,
            token_hash=hashlib.sha256(raw_tok_a.encode("utf-8")).hexdigest(),
            status="EXPIRED",
            expires_at=datetime.utcnow() + timedelta(days=1),
            attempt_count=1
        )
        db.add(act_a)

        # Case B: status="PENDING" but time expired (expires_at < utcnow())
        uid_b = uuid.uuid4().hex[:6]
        org_b = DBEmployerOrganization(
            name=f"Expired Org B {uid_b}",
            registration_ref_number=f"REF-EXP-B-{uid_b}",
            official_email=f"exp_b_{uid_b}@test.org",
            org_address=f"0xemp_exp_b_{uid_b}",
            status="APPROVED"
        )
        db.add(org_b)
        db.flush()

        raw_tok_b = f"act_expired_time_{uid_b}"
        act_b = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=org_b.id,
            recipient_email=org_b.official_email,
            token_hash=hashlib.sha256(raw_tok_b.encode("utf-8")).hexdigest(),
            status="PENDING",
            expires_at=datetime.utcnow() - timedelta(minutes=30),  # expired 30 minutes ago
            attempt_count=1
        )
        db.add(act_b)
        db.commit()

        # 1. Test GET /api/v1/employer/activate-account/{token}
        resp_get_a = client.get(f"/api/v1/employer/activate-account/{raw_tok_a}")
        assert resp_get_a.status_code == 410, (
            f"Expected HTTP 410 for status='EXPIRED', got {resp_get_a.status_code}: {resp_get_a.text}"
        )
        assert "expired" in resp_get_a.json()["detail"].lower()

        resp_get_b = client.get(f"/api/v1/employer/activate-account/{raw_tok_b}")
        assert resp_get_b.status_code == 410, (
            f"Expected HTTP 410 for expires_at < utcnow(), got {resp_get_b.status_code}: {resp_get_b.text}"
        )
        assert "expired" in resp_get_b.json()["detail"].lower()

        # Verify DB status transitioned from PENDING to EXPIRED for token B
        db.expire_all()
        reloaded_act_b = db.query(DBActivationEmail).filter(DBActivationEmail.id == act_b.id).first()
        assert reloaded_act_b.status == "EXPIRED"

        # 2. Test POST /api/v1/auth/activate-employer with expired token
        resp_post_auth_a = client.post("/api/v1/auth/activate-employer", json={
            "activation_token": raw_tok_a,
            "password": "Password123!"
        })
        assert resp_post_auth_a.status_code == 410
        assert "expired" in resp_post_auth_a.json()["detail"].lower()

        resp_post_auth_b = client.post("/api/v1/auth/activate-employer", json={
            "activation_token": raw_tok_b,
            "password": "Password123!"
        })
        assert resp_post_auth_b.status_code == 410
        assert "expired" in resp_post_auth_b.json()["detail"].lower()

        # 3. Test POST /api/v1/employer/activate with expired token
        resp_post_emp_a = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_tok_a,
            "password": "Password123!"
        })
        assert resp_post_emp_a.status_code == 410
        assert "expired" in resp_post_emp_a.json()["detail"].lower()

        resp_post_emp_b = client.post("/api/v1/employer/activate", json={
            "activation_token": raw_tok_b,
            "password": "Password123!"
        })
        assert resp_post_emp_b.status_code == 410
        assert "expired" in resp_post_emp_b.json()["detail"].lower()

    finally:
        db.close()


# ==============================================================================
# CHALLENGE SUITE 5: Boundary & Lifecycle Invariants
# ==============================================================================

def test_adv_c5_unapproved_organization_cannot_activate_via_token():
    """
    Verify that an organization in PENDING_REVIEW or REJECTED state
    cannot be activated via a valid token, rejecting with HTTP 400.
    """
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:6]
        org = DBEmployerOrganization(
            name=f"Pending Org {uid}",
            registration_ref_number=f"REF-PEND-{uid}",
            official_email=f"pend_{uid}@test.org",
            org_address=f"0xemp_pend_{uid}",
            status="PENDING_REVIEW"  # Admin has not approved yet
        )
        db.add(org)
        db.flush()

        raw_tok = f"act_pend_{uid}"
        act = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=org.id,
            recipient_email=org.official_email,
            token_hash=hashlib.sha256(raw_tok.encode("utf-8")).hexdigest(),
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=7),
            attempt_count=1
        )
        db.add(act)
        db.commit()

        # 1. Attempt GET /api/v1/employer/activate-account/{token}
        resp_get = client.get(f"/api/v1/employer/activate-account/{raw_tok}")
        assert resp_get.status_code == 400
        assert "not approved organization yet" in resp_get.json()["detail"].lower()

        # 2. Attempt POST /api/v1/auth/activate-employer
        resp_post = client.post("/api/v1/auth/activate-employer", json={
            "activation_token": raw_tok,
            "password": "Password123!"
        })
        assert resp_post.status_code == 400
        assert "not approved organization yet" in resp_post.json()["detail"].lower()

        # Token must remain PENDING because activation was refused
        db.expire_all()
        reloaded_act = db.query(DBActivationEmail).filter(DBActivationEmail.id == act.id).first()
        assert reloaded_act.status == "PENDING"
        assert reloaded_act.used_at is None

    finally:
        db.close()


def test_adv_c5_activation_status_endpoint_invariants():
    """
    Verify GET /api/v1/employer/activation-status returns correct state transitions:
    - PENDING for fresh tokens
    - USED for consumed tokens
    - INVALID for nonexistent tokens
    """
    db = SessionLocal()
    try:
        # Nonexistent
        res_inv = client.get("/api/v1/employer/activation-status?token=nonexistent_token_123")
        assert res_inv.status_code == 200
        assert res_inv.json()["status"] == "INVALID"

        # Create pending token
        uid = uuid.uuid4().hex[:6]
        raw_tok = f"act_status_{uid}"
        act = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=99999,
            recipient_email=f"status_{uid}@test.org",
            token_hash=hashlib.sha256(raw_tok.encode("utf-8")).hexdigest(),
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=7),
            attempt_count=1
        )
        db.add(act)
        db.commit()

        res_pend = client.get(f"/api/v1/employer/activation-status?token={raw_tok}")
        assert res_pend.status_code == 200
        assert res_pend.json()["status"] == "VALID"

        # Mark USED
        act.status = "USED"
        db.commit()

        res_used = client.get(f"/api/v1/employer/activation-status?token={raw_tok}")
        assert res_used.status_code == 200
        assert res_used.json()["status"] == "USED"

        # Mark EXPIRED
        act.status = "EXPIRED"
        db.commit()

        res_exp = client.get(f"/api/v1/employer/activation-status?token={raw_tok}")
        assert res_exp.status_code == 200
        assert res_exp.json()["status"] == "EXPIRED"

    finally:
        db.close()
