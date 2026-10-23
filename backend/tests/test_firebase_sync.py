import pytest
import time
import hashlib
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile
from app.core.auth import create_test_firebase_jwt, base64url_encode
import json

client = TestClient(app)

def test_target_account_clean_registration_and_login():
    """Verify target account passkhadam@gmail.com can register and login cleanly."""
    target_email = "passkhadam@gmail.com"
    target_uid = "uid_passkhadam_test"
    target_pw = "UzairPass2026!"

    # Ensure clean slate in DB
    db = SessionLocal()
    existing = db.query(DBUser).filter(DBUser.email == target_email).first()
    if existing:
        db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == existing.id).delete()
        db.delete(existing)
        db.commit()
    db.close()

    try:
        # 1. Clean Registration
        reg_resp = client.post("/api/v1/auth/register", json={
            "full_name": "Mohammed Uzair",
            "email": target_email,
            "phone": "+91 9876543210",
            "password": target_pw,
            "role": "WORKER",
            "firebase_uid": target_uid
        })
        assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
        reg_data = reg_resp.json()
        assert reg_data["user"]["email"] == target_email
        assert reg_data["user"]["firebase_uid"] == target_uid
        assert reg_data["user"]["role"] == "WORKER"

        # 2. Login with valid credentials
        login_resp = client.post("/api/v1/auth/login", json={
            "email": target_email,
            "password": target_pw
        })
        assert login_resp.status_code == 200
        assert login_resp.json()["user"]["email"] == target_email
    finally:
        # 3. Clean up target user from DB after verification so workspace stays clean
        db = SessionLocal()
        u = db.query(DBUser).filter(DBUser.email == target_email).first()
        if u:
            db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == u.id).delete()
            db.delete(u)
            db.commit()
        db.close()

def test_login_with_direct_firebase_id_token_sync():
    """Verify direct Firebase ID token login synchronizes out-of-sync password and provisions context."""
    sync_email = f"sync_test_{uuid.uuid4().hex[:6]}@passkhadam.org"
    sync_uid = f"uid_sync_{uuid.uuid4().hex[:6]}"
    old_pw = "OldPassword123!"
    new_pw = "NewPassword456!"

    # 1. Register user with old password
    reg_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Sync Test User",
        "email": sync_email,
        "phone": "+91 9876500010",
        "password": old_pw,
        "role": "WORKER",
        "firebase_uid": sync_uid
    })
    assert reg_resp.status_code == 200

    # 2. Login with new password and valid Firebase ID token (simulating password change in Firebase)
    token = create_test_firebase_jwt(
        uid=sync_uid,
        email=sync_email,
        name="Sync Test User"
    )

    login_resp = client.post("/api/v1/auth/login", json={
        "email": sync_email,
        "password": new_pw,
        "id_token": token
    })
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["email"] == sync_email

    # 3. Confirm password hash was synchronized in DB to new password
    db = SessionLocal()
    try:
        user = db.query(DBUser).filter(DBUser.email == sync_email).first()
        assert user is not None
        assert user.password_hash == hashlib.sha256(new_pw.encode("utf-8")).hexdigest()
    finally:
        # Cleanup
        if user:
            db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).delete()
            db.delete(user)
            db.commit()
        db.close()

def test_registration_with_preexisting_unlinked_account():
    """Verify registration seamlessly updates an existing user whose firebase_uid was None."""
    preseed_email = f"preseed_{uuid.uuid4().hex[:6]}@passkhadam.org"
    user_pw = "PreseedPass123!"
    new_uid = f"uid_preseed_{uuid.uuid4().hex[:6]}"

    db = SessionLocal()
    u = DBUser(
        full_name="Preseeded User",
        email=preseed_email,
        phone="+91 9876500020",
        password_hash=hashlib.sha256(user_pw.encode("utf-8")).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=None,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(u)
    db.commit()
    db.close()

    # Register with matching password and new firebase_uid -> should link cleanly without 400
    reg_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Preseeded User Updated",
        "email": preseed_email,
        "phone": "+91 9876500020",
        "password": user_pw,
        "role": "WORKER",
        "firebase_uid": new_uid
    })
    assert reg_resp.status_code == 200
    assert reg_resp.json()["user"]["firebase_uid"] == new_uid
    assert reg_resp.json()["user"]["full_name"] == "Preseeded User Updated"

    # Cleanup
    db = SessionLocal()
    try:
        user = db.query(DBUser).filter(DBUser.email == preseed_email).first()
        if user:
            db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).delete()
            db.delete(user)
            db.commit()
    finally:
        db.close()

def test_login_rejects_token_with_mismatched_or_missing_email():
    """Verify login rejects token if email does not match requested email."""
    # 1. Token with foreign email
    foreign_token = create_test_firebase_jwt(
        uid="uid_foreign",
        email="foreign@passkhadam.org",
        name="Foreign"
    )

    resp = client.post("/api/v1/auth/login", json={
        "email": "worker@passkhadam.org",
        "password": "wrong_password_attempt",
        "id_token": foreign_token
    })
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]

    # 2. Token with missing email claim cannot impersonate admin
    now = int(time.time())
    h = base64url_encode(json.dumps({"alg": "RS256", "kid": "mock", "typ": "JWT"}).encode("utf-8"))
    p = base64url_encode(json.dumps({
        "iss": "https://securetoken.google.com/passkhadam-live",
        "aud": "passkhadam-live",
        "sub": "attacker_sub_999",
        "user_id": "attacker_sub_999",
        "iat": now,
        "exp": now + 3600
    }).encode("utf-8"))
    s = base64url_encode(b"sig")
    token_no_email = f"{h}.{p}.{s}"

    resp_no_email = client.post("/api/v1/auth/login", json={
        "email": "admin@passkhadam.org",
        "password": "wrong_password_attempt",
        "id_token": token_no_email
    })
    assert resp_no_email.status_code == 401

def test_demo_presets_remain_functional_and_active():
    """Verify all 5 demo presets remain active and functional."""
    roles = ["WORKER", "EMPLOYER", "GOVERNMENT", "ADMIN", "AADHAAR"]
    for role in roles:
        resp = client.post(f"/api/v1/auth/demo-login/{role}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == role
        assert data["user"]["status"] == "ACTIVE"

def test_registration_with_stale_firebase_uid_updates_cleanly():
    """Verify registration with valid Firebase ID token updates user whose existing firebase_uid is stale."""
    email = f"stale_uid_{uuid.uuid4().hex[:6]}@passkhadam.org"
    old_uid = f"uid_old_{uuid.uuid4().hex[:6]}"
    new_uid = f"uid_new_{uuid.uuid4().hex[:6]}"
    pw = "StalePass123!"

    db = SessionLocal()
    u = DBUser(
        full_name="Stale User",
        email=email,
        phone="+91 9876500077",
        password_hash=hashlib.sha256(pw.encode()).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=old_uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(u)
    db.commit()
    db.close()

    try:
        new_token = create_test_firebase_jwt(
            uid=new_uid,
            email=email,
            name="Stale User Updated"
        )

        reg_resp = client.post("/api/v1/auth/register", json={
            "full_name": "Stale User Updated",
            "email": email,
            "phone": "+91 9876500077",
            "password": pw,
            "role": "WORKER",
            "firebase_uid": new_uid,
            "id_token": new_token
        })
        assert reg_resp.status_code == 200, f"Expected 200, got {reg_resp.status_code}: {reg_resp.text}"
        data = reg_resp.json()
        assert data["user"]["firebase_uid"] == new_uid
        assert data["user"]["full_name"] == "Stale User Updated"
    finally:
        db = SessionLocal()
        usr = db.query(DBUser).filter(DBUser.email == email).first()
        if usr:
            db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == usr.id).delete()
            db.delete(usr)
            db.commit()
        db.close()

def test_mixed_case_email_normalization_registration_and_login():
    """Verify mixed-case and lowercase emails authenticate interchangeably without split accounts."""
    suffix = uuid.uuid4().hex[:6]
    mixed_email = f"MixedCase_{suffix}@PassKhadam.Org"
    lower_email = mixed_email.lower()
    pw = "CasePass123!"

    try:
        # Register with mixed case
        reg_resp = client.post("/api/v1/auth/register", json={
            "full_name": "Case Sensitive User",
            "email": mixed_email,
            "phone": "+91 9876500088",
            "password": pw,
            "role": "WORKER"
        })
        assert reg_resp.status_code == 200
        assert reg_resp.json()["user"]["email"] == lower_email

        # Login with lowercase email
        login_resp_lower = client.post("/api/v1/auth/login", json={
            "email": lower_email,
            "password": pw
        })
        assert login_resp_lower.status_code == 200
        assert login_resp_lower.json()["user"]["email"] == lower_email

        # Login with uppercase email
        login_resp_upper = client.post("/api/v1/auth/login", json={
            "email": mixed_email.upper(),
            "password": pw
        })
        assert login_resp_upper.status_code == 200
        assert login_resp_upper.json()["user"]["email"] == lower_email
    finally:
        db = SessionLocal()
        usr = db.query(DBUser).filter(DBUser.email == lower_email).first()
        if usr:
            db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == usr.id).delete()
            db.delete(usr)
            db.commit()
        db.close()

def test_duplicate_firebase_uid_collision_rejection():
    """Verify cross-account Firebase UID hijacking/collision is rejected with HTTP 400."""
    uid_collision = f"uid_coll_{uuid.uuid4().hex[:6]}"
    email_a = f"alice_{uuid.uuid4().hex[:6]}@passkhadam.org"
    email_b = f"bob_{uuid.uuid4().hex[:6]}@passkhadam.org"
    pw = "SecretPass123!"

    try:
        # User A registers with uid_collision
        res_a = client.post("/api/v1/auth/register", json={
            "full_name": "Alice Collision",
            "email": email_a,
            "phone": "+91 9876500091",
            "password": pw,
            "role": "WORKER",
            "firebase_uid": uid_collision
        })
        assert res_a.status_code == 200

        # User B attempts to register with the SAME firebase_uid
        res_b = client.post("/api/v1/auth/register", json={
            "full_name": "Bob Hijacker",
            "email": email_b,
            "phone": "+91 9876500092",
            "password": pw,
            "role": "WORKER",
            "firebase_uid": uid_collision
        })
        assert res_b.status_code == 400
        assert "already associated" in res_b.json()["detail"].lower()
    finally:
        db = SessionLocal()
        for em in [email_a, email_b]:
            usr = db.query(DBUser).filter(DBUser.email == em).first()
            if usr:
                db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == usr.id).delete()
                db.delete(usr)
        db.commit()
        db.close()

def test_get_me_auto_provisioning_organization_metadata():
    """Verify auto-provisioning via /me populates organization fields for non-worker roles."""
    gov_email = f"gov_autotest_{uuid.uuid4().hex[:6]}@maharashtra.gov.in"
    gov_uid = f"uid_gov_{uuid.uuid4().hex[:6]}"

    tok = create_test_firebase_jwt(
        uid=gov_uid,
        email=gov_email,
        name="Maharashtra Officer"
    )

    try:
        me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == gov_email.lower()
        assert data["role"] == "GOVERNMENT"
        assert data["organization_status"] == "APPROVED"
        assert data["organization_name"] is not None
        assert data["organization"] is not None
        assert data["organization"]["status"] == "APPROVED"
    finally:
        db = SessionLocal()
        usr = db.query(DBUser).filter(DBUser.email == gov_email.lower()).first()
        if usr:
            db.delete(usr)
            db.commit()
        db.close()

def test_registration_owner_recognition_without_firebase_uid():
    """Verify registration succeeds with 200 when existing user registers with matching password without firebase_uid."""
    email = f"owner_nopass_{uuid.uuid4().hex[:6]}@passkhadam.org"
    pw = "OwnerSecret2026!"

    db = SessionLocal()
    u = DBUser(
        full_name="Owner User",
        email=email,
        phone="+91 9876500111",
        password_hash=hashlib.sha256(pw.encode()).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=None,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(u)
    db.commit()
    db.close()

    try:
        reg_resp = client.post("/api/v1/auth/register", json={
            "full_name": "Owner User Updated",
            "email": email,
            "phone": "+91 9876500111",
            "password": pw,
            "role": "WORKER",
            "firebase_uid": None,
            "id_token": None
        })
        assert reg_resp.status_code == 200, f"Expected 200, got {reg_resp.status_code}: {reg_resp.text}"
        data = reg_resp.json()
        assert data["user"]["email"] == email
        assert data["user"]["full_name"] == "Owner User Updated"
    finally:
        db = SessionLocal()
        usr = db.query(DBUser).filter(DBUser.email == email).first()
        if usr:
            db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == usr.id).delete()
            db.delete(usr)
            db.commit()
        db.close()

def test_registration_token_via_authorization_header():
    """Verify register_user extracts and validates Firebase ID token from Authorization header."""
    email = f"auth_hdr_{uuid.uuid4().hex[:6]}@passkhadam.org"
    old_uid = f"uid_old_{uuid.uuid4().hex[:6]}"
    new_uid = f"uid_new_{uuid.uuid4().hex[:6]}"
    pw = "AuthHdrPass123!"

    db = SessionLocal()
    u = DBUser(
        full_name="Header User",
        email=email,
        phone="+91 9876500222",
        password_hash=hashlib.sha256(pw.encode()).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=old_uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(u)
    db.commit()
    db.close()

    try:
        new_token = create_test_firebase_jwt(
            uid=new_uid,
            email=email,
            name="Header User Updated"
        )

        reg_resp = client.post(
            "/api/v1/auth/register",
            headers={"Authorization": f"Bearer {new_token}"},
            json={
                "full_name": "Header User Updated",
                "email": email,
                "phone": "+91 9876500222",
                "password": pw,
                "role": "WORKER"
                # id_token omitted from body, passed solely via Authorization header
            }
        )
        assert reg_resp.status_code == 200, f"Expected 200, got {reg_resp.status_code}: {reg_resp.text}"
        data = reg_resp.json()
        assert data["user"]["firebase_uid"] == new_uid
    finally:
        db = SessionLocal()
        usr = db.query(DBUser).filter(DBUser.email == email).first()
        if usr:
            db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == usr.id).delete()
            db.delete(usr)
            db.commit()
        db.close()

def test_login_uid_collision_auto_clears_stale_mapping():
    """Verify login gracefully unbinds stale UID mapping from older account to avoid 500 SQLite UNIQUE error."""
    shared_uid = f"uid_shared_{uuid.uuid4().hex[:6]}"
    email_a = f"alice_stale_{uuid.uuid4().hex[:6]}@passkhadam.org"
    email_b = f"bob_new_{uuid.uuid4().hex[:6]}@passkhadam.org"
    pw_b = "BobSecretPass123!"

    db = SessionLocal()
    # User A has stale shared_uid
    u_a = DBUser(
        full_name="Alice Stale",
        email=email_a,
        phone="+91 9876500331",
        password_hash=hashlib.sha256("AlicePass1!".encode()).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=shared_uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    # User B exists without firebase_uid
    u_b = DBUser(
        full_name="Bob New",
        email=email_b,
        phone="+91 9876500332",
        password_hash=hashlib.sha256(pw_b.encode()).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=None,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(u_a)
    db.add(u_b)
    db.commit()
    db.close()

    try:
        token_b = create_test_firebase_jwt(
            uid=shared_uid,
            email=email_b,
            name="Bob New"
        )
        login_resp = client.post("/api/v1/auth/login", json={
            "email": email_b,
            "password": pw_b,
            "id_token": token_b
        })
        assert login_resp.status_code == 200, f"Expected 200, got {login_resp.status_code}: {login_resp.text}"
        data = login_resp.json()
        assert data["user"]["firebase_uid"] == shared_uid

        # Verify User A's stale mapping was cleared to satisfy unique constraint
        db = SessionLocal()
        user_a = db.query(DBUser).filter(DBUser.email == email_a).first()
        user_b = db.query(DBUser).filter(DBUser.email == email_b).first()
        assert user_a.firebase_uid is None
        assert user_b.firebase_uid == shared_uid
        db.close()
    finally:
        db = SessionLocal()
        for em in [email_a, email_b]:
            usr = db.query(DBUser).filter(DBUser.email == em).first()
            if usr:
                db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == usr.id).delete()
                db.delete(usr)
        db.commit()
        db.close()

def test_otp_schemas_whitespace_email_normalization():
    """Verify SendEmailOTPRequest and VerifyEmailOTPRequest gracefully strip whitespace from email."""
    from app.models.schemas import SendEmailOTPRequest, VerifyEmailOTPRequest

    # SendEmailOTPRequest with whitespace
    req_send = SendEmailOTPRequest.model_validate({"email": "  test_otp@passkhadam.org  "})
    assert req_send.email == "test_otp@passkhadam.org"

    # VerifyEmailOTPRequest with whitespace and integer OTP code
    req_verify = VerifyEmailOTPRequest.model_validate({
        "email": "  test_otp@passkhadam.org  ",
        "otp": 847291
    })
    assert req_verify.email == "test_otp@passkhadam.org"
    assert req_verify.otp_code == "847291"
    assert req_verify.otp == "847291"

def test_get_me_token_with_email_prefers_authoritative_email_over_stale_uid():
    """Verify /me resolves user by token email even if token sub was previously linked to another user."""
    shared_uid = f"uid_shared_{uuid.uuid4().hex[:6]}"
    email_alice = f"alice_{uuid.uuid4().hex[:6]}@passkhadam.org"
    email_bob = f"bob_{uuid.uuid4().hex[:6]}@passkhadam.org"

    db = SessionLocal()
    # User Alice holds shared_uid
    u_alice = DBUser(
        full_name="Alice Owner",
        email=email_alice,
        phone="+91 9876500441",
        password_hash=hashlib.sha256("pass123".encode()).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=shared_uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    # User Bob exists
    u_bob = DBUser(
        full_name="Bob Authoritative",
        email=email_bob,
        phone="+91 9876500442",
        password_hash=hashlib.sha256("pass123".encode()).hexdigest(),
        role="WORKER",
        status="ACTIVE",
        firebase_uid=None,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(u_alice)
    db.add(u_bob)
    db.commit()
    db.close()

    try:
        # Token issued for Bob with sub=shared_uid
        token_bob = create_test_firebase_jwt(
            uid=shared_uid,
            email=email_bob,
            name="Bob Authoritative"
        )
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_bob}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == email_bob
        assert data["full_name"] == "Bob Authoritative"
    finally:
        db = SessionLocal()
        for em in [email_alice, email_bob]:
            usr = db.query(DBUser).filter(DBUser.email == em).first()
            if usr:
                db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == usr.id).delete()
                db.delete(usr)
        db.commit()
        db.close()

