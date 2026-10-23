import time
import json
import base64
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile

client = TestClient(app)

def create_mock_jwt(email: str, uid: str, email_verified: bool = True, phone: str = None) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "iss": "https://securetoken.google.com/passkhadam-live",
        "aud": "passkhadam-live",
        "sub": uid,
        "user_id": uid,
        "email": email,
        "email_verified": email_verified,
        "exp": int(time.time()) + 3600
    }
    if phone:
        payload["phone_number"] = phone
        payload["phone"] = phone
    
    h_str = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_str = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{h_str}.{p_str}.mock_sig"

def test_unregistered_token_rejected_from_me():
    """Unregistered Firebase token must be rejected with 401 instead of auto-provisioning unverified account."""
    new_email = f"unregistered_{int(time.time())}@example.com"
    token = create_mock_jwt(new_email, f"uid_{int(time.time())}", email_verified=False)
    
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "not found" in res.json()["detail"].lower() or "unrecognized" in res.json()["detail"].lower()

def test_registration_and_dual_verification_flags():
    """Registering a new worker sets is_email_verified=True and is_phone_verified=True."""
    db = SessionLocal()
    reg_email = f"worker_test_{int(time.time())}@example.com"
    uid = f"uid_worker_{int(time.time())}"
    token = create_mock_jwt(reg_email, uid, email_verified=True, phone="+919876543210")
    
    try:
        reg_payload = {
            "full_name": "Test Worker Dual",
            "email": reg_email,
            "password": "Password123!",
            "phone": "+91 98765 43210",
            "role": "WORKER",
            "worker_category": "Electrician",
            "origin_state": "Karnataka",
            "current_state": "Maharashtra",
            "id_token": token,
            "firebase_uid": uid
        }
        res = client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["user"]["is_email_verified"] is True
        assert data["user"]["is_phone_verified"] is True
        
        # Verify in database directly
        user = db.query(DBUser).filter(DBUser.email == reg_email).first()
        assert user is not None
        assert user.is_email_verified is True
        assert user.is_phone_verified is True
    finally:
        db.close()

def test_sync_verification_endpoint():
    """Test sync-verification endpoint updates unverified user upon valid Firebase token."""
    db = SessionLocal()
    test_email = f"sync_test_{int(time.time())}@example.com"
    uid = f"uid_sync_{int(time.time())}"
    
    try:
        # Create user with is_email_verified=False, is_phone_verified=False
        u = DBUser(
            email=test_email,
            full_name="Sync Test",
            phone="+91 98765 43210",
            password_hash="hash_dummy_test_123",
            role="WORKER",
            firebase_uid=uid,
            is_email_verified=False,
            is_phone_verified=False,
            status="ACTIVE"
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        
        # Token showing email is now verified and phone is verified
        token = create_mock_jwt(test_email, uid, email_verified=True, phone="+919876543210")
        
        # Call sync-verification
        res = client.post("/api/v1/auth/sync-verification", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["is_email_verified"] is True
        assert data["is_phone_verified"] is True
        
        # Verify in DB
        db.refresh(u)
        assert u.is_email_verified is True
        assert u.is_phone_verified is True
    finally:
        db.close()
