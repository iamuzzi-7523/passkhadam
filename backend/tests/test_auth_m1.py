import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import SessionLocal, DBUser
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)

def test_auth_me_demo_tokens_all_roles():
    """Verify GET /api/v1/auth/me returns authoritative role, status, and permissions for all 5 roles."""
    roles = ["WORKER", "EMPLOYER", "GOVERNMENT", "ADMIN", "AADHAAR"]

    for role in roles:
        # 1. Login with demo preset to obtain access token
        login_resp = client.post(f"/api/v1/auth/demo-login/{role}")
        assert login_resp.status_code == 200, f"Demo login failed for {role}"
        token = login_resp.json()["access_token"]

        # 2. Query /api/v1/auth/me with Bearer token
        me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200, f"/me failed for {role}: {me_resp.text}"
        data = me_resp.json()

        assert data["role"] == role
        assert data["status"] == "ACTIVE"
        assert len(data["permissions"]) > 0

        # Verify role-specific invariant checks
        if role == "WORKER":
            assert "view_worker_portal" in data["permissions"]
            assert data["email"] == "worker@passkhadam.org"
            assert data["organization"] is None
        elif role == "EMPLOYER":
            assert "view_employer_portal" in data["permissions"]
            assert data["email"] == "employer@apexinfra.com"
            assert data["organization"] is not None
            assert data["organization"]["address"] == "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
            assert data["organization"]["name"] == "Apex Infrastructure & Construction Ltd"
            assert data["organization"]["status"] == "APPROVED"
            assert "Mason" in data["organization"]["categories"]
        elif role == "GOVERNMENT":
            assert "view_government_portal" in data["permissions"]
            assert data["email"] == "gov@maharashtra.gov.in"
            assert data["organization"] is not None
            assert data["organization"]["address"] == "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
            assert data["organization"]["name"] == "Maharashtra State Migrant Welfare Board"
            assert data["organization"]["status"] == "APPROVED"
        elif role == "ADMIN":
            assert "view_admin_portal" in data["permissions"]
            assert data["email"] == "admin@passkhadam.org"
        elif role == "AADHAAR":
            assert "view_aadhaar_portal" in data["permissions"]
            assert data["email"] == "authority@uidai.gov.in"

def test_auth_me_live_firebase_jwt_verification():
    """Verify GET /api/v1/auth/me accepts and validates Firebase ID token (JWT) for passkhadam-live."""
    jwt_token = create_test_firebase_jwt(
        uid="gz64njiIhYcxQs8C9aneVA5xuIM2",
        email="worker@passkhadam.org",
        name="Mohammed Uzair"
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "worker@passkhadam.org"
    assert data["role"] == "WORKER"
    assert data["status"] == "ACTIVE"
    assert data["firebase_uid"] == "gz64njiIhYcxQs8C9aneVA5xuIM2"

def test_auth_me_auto_provisions_new_firebase_user():
    """Verify GET /api/v1/auth/me auto-provisions a new account if authenticated in Firebase."""
    unique_email = f"new_worker_{int(time.time())}@passkhadam.org"
    unique_uid = f"uid_new_worker_{int(time.time())}"

    jwt_token = create_test_firebase_jwt(
        uid=unique_uid,
        email=unique_email,
        name="Sunita Devi"
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == unique_email
    assert data["role"] == "WORKER"
    assert data["status"] == "ACTIVE"
    assert data["firebase_uid"] == unique_uid

    # Verify SQLite database has new user record
    db = SessionLocal()
    try:
        user = db.query(DBUser).filter(DBUser.email == unique_email).first()
        assert user is not None
        assert user.firebase_uid == unique_uid
    finally:
        db.close()

def test_auth_me_rejects_expired_firebase_token():
    """Verify expired Firebase ID token is rejected with 401 Unauthorized."""
    expired_jwt = create_test_firebase_jwt(
        uid="expired_user_uid",
        email="expired@passkhadam.org",
        expired=True
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_jwt}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()

def test_auth_me_rejects_audience_mismatch():
    """Verify token from foreign Firebase project is rejected with 401."""
    foreign_jwt = create_test_firebase_jwt(
        uid="attacker_uid",
        email="attacker@evil.com",
        aud="malicious-project-id"
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {foreign_jwt}"})
    assert response.status_code == 401
    assert "audience" in response.json()["detail"].lower()

def test_auth_me_rejects_missing_or_invalid_authorization():
    """Verify missing and malformed Authorization header returns 401."""
    # 1. Missing header
    res_missing = client.get("/api/v1/auth/me")
    assert res_missing.status_code == 401

    # 2. Malformed token
    res_malformed = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not_a_valid_token"})
    assert res_malformed.status_code == 401

def test_auth_me_enforces_suspended_and_disabled_accounts():
    """Verify SUSPENDED and DISABLED accounts receive 403 Forbidden even with valid token."""
    db = SessionLocal()
    try:
        # 1. Create suspended user
        suspended_email = f"suspended_{int(time.time())}@passkhadam.org"
        suspended_user = DBUser(
            full_name="Suspended Worker",
            email=suspended_email,
            phone="+91 9999999991",
            password_hash="hash",
            role="WORKER",
            status="SUSPENDED",
            firebase_uid=f"uid_suspended_{int(time.time())}",
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(suspended_user)

        # 2. Create disabled user
        disabled_email = f"disabled_{int(time.time())}@passkhadam.org"
        disabled_user = DBUser(
            full_name="Disabled Employer",
            email=disabled_email,
            phone="+91 9999999992",
            password_hash="hash",
            role="EMPLOYER",
            status="DISABLED",
            firebase_uid=f"uid_disabled_{int(time.time())}",
            is_email_verified=True,
            is_phone_verified=True
        )
        db.add(disabled_user)
        db.commit()
        db.refresh(suspended_user)
        db.refresh(disabled_user)

        # Verify SUSPENDED returns 403
        token_susp = f"pk_token_{suspended_user.id}_worker"
        resp_susp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_susp}"})
        assert resp_susp.status_code == 403
        assert "suspended" in resp_susp.json()["detail"].lower()

        # Verify DISABLED returns 403
        token_dis = f"pk_token_{disabled_user.id}_employer"
        resp_dis = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_dis}"})
        assert resp_dis.status_code == 403
        assert "disabled" in resp_dis.json()["detail"].lower()

    finally:
        db.close()

def test_employer_activation_endpoint():
    """Verify POST /api/v1/auth/activate-employer completes employer activation."""
    act_resp = client.post("/api/v1/auth/activate-employer", json={
        "activation_token": "act_b906_secure",
        "password": "NewEmployerSecurePass123"
    })
    assert act_resp.status_code == 200
    act_data = act_resp.json()
    assert act_data["status"] == "SUCCESS"
    assert act_data["organization_status"] == "APPROVED"
    assert act_data["email"] == "employer@apexinfra.com"

    # Reset employer password and activation token back to baseline demo state for test isolation
    db = SessionLocal()
    try:
        user = db.query(DBUser).filter(DBUser.role == "EMPLOYER").first()
        if user:
            import hashlib
            user.password_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

        from app.models.db import DBActivationEmail, DBEmployerOrganization
        import hashlib
        act_token_hash = hashlib.sha256("act_b906_secure".encode("utf-8")).hexdigest()
        act_rec = db.query(DBActivationEmail).filter(DBActivationEmail.token_hash == act_token_hash).first()
        if act_rec:
            act_rec.status = "PENDING"
            act_rec.used_at = None
        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.official_email == "employer@apexinfra.com").first()
        if org:
            org.status = "APPROVED"
        if user:
            user.organization_status = "APPROVED"
        db.commit()
    finally:
        db.close()
