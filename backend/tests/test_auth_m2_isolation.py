"""
backend/tests/test_auth_m2_isolation.py
Milestone 2 Verification Suite: Canonical Authentication, Principal Isolation & IDOR Elimination
"""

import pytest
import uuid
import time
import json
import hashlib
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployerOrganization, DBAadhaarRecord
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)

class UserHolder:
    def __init__(self, id, firebase_uid, email, full_name, role):
        self.id = id
        self.firebase_uid = firebase_uid
        self.email = email
        self.full_name = full_name
        self.role = role

# Helper fixtures and functions
def create_test_worker(name="Test Worker", email=None, is_anchored=False) -> UserHolder:
    db = SessionLocal()
    email = email or f"worker_{uuid.uuid4().hex[:8]}@example.com"
    uid = f"uid_{uuid.uuid4().hex[:8]}"
    user = DBUser(
        full_name=name,
        email=email,
        phone="+919876543299",
        password_hash="hash",
        role="WORKER",
        status="ACTIVE",
        firebase_uid=uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_id = user.id

    rec_id = None
    masked = None
    if is_anchored:
        rec_id = str(uuid.uuid4())
        raw_num = f"99{uuid.uuid4().int % 10000000000:010d}"
        a_hash = hashlib.sha256(raw_num.encode()).hexdigest()
        masked = f"XXXX-XXXX-{raw_num[-4:]}"
        record = DBAadhaarRecord(
            record_id=rec_id,
            aadhaar_hash=a_hash,
            masked_aadhaar=masked,
            full_name=name,
            dob="1992-06-15",
            gender="Male",
            origin_state="Bihar",
            status="ACTIVE",
            is_active=True
        )
        db.add(record)
        db.commit()

    profile = DBWorkerProfile(
        user_id=user_id,
        full_name=name,
        origin_state="Bihar",
        current_state="Maharashtra",
        worker_category="Carpenter",
        skills_json='["Carpenter"]',
        is_credential_anchored=is_anchored,
        did=f"did:passkhadam:worker:{user_id}" if is_anchored else None,
        is_aadhaar_verified=is_anchored,
        masked_aadhaar=masked if is_anchored else None,
        aadhaar_record_id=rec_id if is_anchored else None,
        did_state="ACTIVE" if is_anchored else "NOT_STARTED"
    )
    db.add(profile)
    db.commit()
    db.close()
    return UserHolder(user_id, uid, email, name, "WORKER")

def get_token_for_user(user: UserHolder) -> str:
    return create_test_firebase_jwt(
        uid=user.firebase_uid,
        email=user.email,
        name=user.full_name
    )

# ---------------------------------------------------------------------------
# Dimension 1: Worker Self-Service Endpoints (/me)
# ---------------------------------------------------------------------------

def test_m2_worker_profile_me_authenticated():
    """Worker retrieves own profile via /profile/me using Bearer token."""
    worker = create_test_worker("Rohit Sharma")
    token = get_token_for_user(worker)
    
    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Rohit Sharma"
    assert data["user_id"] == worker.id
    assert data["worker_category"] == "Carpenter"

def test_m2_worker_profile_me_unauthenticated_rejected():
    """Accessing /profile/me without token returns 401 Unauthorized."""
    resp = client.get("/api/v1/worker/profile/me")
    assert resp.status_code in [401, 403]

def test_m2_worker_profile_me_update_authenticated():
    """Worker updates own profile via PUT /profile/me."""
    worker = create_test_worker("Sunil Chhetri")
    token = get_token_for_user(worker)
    
    update_data = {"worker_category": "Electrician", "current_state": "Karnataka"}
    resp = client.put("/api/v1/worker/profile/me", json=update_data, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    
    # Confirm change
    refreshed = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert refreshed["worker_category"] == "Electrician"
    assert refreshed["current_state"] == "Karnataka"

def test_m2_worker_wallet_me_authenticated():
    """Worker retrieves own wallet via GET /wallet/me."""
    worker = create_test_worker("Deepak Punia")
    token = get_token_for_user(worker)
    
    resp = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "credentials" in data
    assert "employments" in data

def test_m2_worker_presentation_qr_card_me_unanchored():
    """Worker requesting QR card before identity anchoring receives 400 Bad Request or 403 Forbidden."""
    worker = create_test_worker("Unanchored Worker", is_anchored=False)
    token = get_token_for_user(worker)
    
    resp = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [400, 403]
    detail_lower = resp.json()["detail"].lower()
    assert "anchored" in detail_lower or "not active" in detail_lower or "forbidden" in detail_lower or "unverified" in detail_lower

def test_m2_worker_presentation_qr_card_me_anchored():
    """Anchored worker can generate presentation QR card via /presentation/qr-card/me."""
    worker = create_test_worker("Anchored Worker", is_anchored=True)
    token = get_token_for_user(worker)

    resp = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["worker_did"] == f"did:passkhadam:worker:{worker.id}"
    assert "qr_base64_data_uri" in data
    assert data["expires_in_seconds"] == 300

# ---------------------------------------------------------------------------
# Dimension 2: Cross-Role Access Rejection (RBAC Enforcement)
# ---------------------------------------------------------------------------

def test_m2_employer_cannot_access_worker_profile_me():
    """Employer token accessing /worker/profile/me returns 403 Forbidden."""
    emp_token = client.post("/api/v1/auth/demo-login/EMPLOYER").json()["access_token"]
    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {emp_token}"})
    assert resp.status_code == 403
    assert "worker" in resp.json()["detail"].lower()

def test_m2_government_cannot_access_worker_wallet_me():
    """Government officer token accessing /worker/wallet/me returns 403 Forbidden."""
    gov_token = client.post("/api/v1/auth/demo-login/GOVERNMENT").json()["access_token"]
    resp = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {gov_token}"})
    assert resp.status_code == 403
    assert "worker" in resp.json()["detail"].lower()

def test_m2_government_cannot_access_worker_profile_by_id():
    """Government officer token accessing /worker/profile/{id} returns 403 Forbidden."""
    gov_token = client.post("/api/v1/auth/demo-login/GOVERNMENT").json()["access_token"]
    worker = create_test_worker("Worker Target")
    resp = client.get(f"/api/v1/worker/profile/{worker.id}", headers={"Authorization": f"Bearer {gov_token}"})
    assert resp.status_code == 403
    assert "unauthorized role" in resp.json()["detail"].lower()

# ---------------------------------------------------------------------------
# Dimension 3: IDOR Protection & Cross-User Isolation
# ---------------------------------------------------------------------------

def test_m2_worker_cannot_access_other_worker_profile_by_id():
    """Worker A attempting to access Worker B's profile via /profile/{id} is rejected with 403 Forbidden."""
    worker_a = create_test_worker("Worker A")
    worker_b = create_test_worker("Worker B")
    token_a = get_token_for_user(worker_a)
    
    resp = client.get(f"/api/v1/worker/profile/{worker_b.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 403
    assert "own profile" in resp.json()["detail"].lower() or "forbidden" in resp.json()["detail"].lower()

def test_m2_worker_cannot_modify_other_worker_profile():
    """Worker A attempting to update Worker B's profile via PUT /profile/{id} is rejected with 403 Forbidden."""
    worker_a = create_test_worker("Worker A")
    worker_b = create_test_worker("Worker B")
    token_a = get_token_for_user(worker_a)
    
    resp = client.put(
        f"/api/v1/worker/profile/{worker_b.id}",
        json={"worker_category": "Malicious Tampering"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 403
    assert "own profile" in resp.json()["detail"].lower()

def test_m2_worker_cannot_generate_other_worker_qr_card():
    """Worker A attempting to generate Worker B's QR card via /qr-card/{id} is rejected with 403 Forbidden."""
    worker_a = create_test_worker("Worker A")
    worker_b = create_test_worker("Worker B", is_anchored=True)
    token_a = get_token_for_user(worker_a)

    resp = client.get(f"/api/v1/worker/presentation/qr-card/{worker_b.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 403
    assert "own qr presentation" in resp.json()["detail"].lower()

def test_m2_worker_can_access_own_profile_by_id_if_matching():
    """Worker A querying /profile/{worker_a.id} succeeds because caller owns the resource."""
    worker_a = create_test_worker("Worker A Own Profile")
    token_a = get_token_for_user(worker_a)
    
    resp = client.get(f"/api/v1/worker/profile/{worker_a.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Worker A Own Profile"

def test_m2_admin_can_access_worker_profile_by_id():
    """Admin token can access any worker profile by ID for platform administration."""
    admin_token = client.post("/api/v1/auth/demo-login/ADMIN").json()["access_token"]
    worker = create_test_worker("Admin Inspected Worker")

    resp = client.get(f"/api/v1/worker/profile/{worker.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Admin Inspected Worker"

def test_m2_approved_employer_can_access_worker_profile_by_id():
    """Approved employer token can access worker profile by ID for hiring inspection."""
    emp_token = client.post("/api/v1/auth/demo-login/EMPLOYER").json()["access_token"]
    worker = create_test_worker("Employer Inspected Worker")

    resp = client.get(f"/api/v1/worker/profile/{worker.id}", headers={"Authorization": f"Bearer {emp_token}"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Employer Inspected Worker"

def test_m2_unapproved_employer_cannot_access_worker_profile_by_id():
    """Unapproved/pending employer token attempting to access worker profile receives 403 Forbidden."""
    db = SessionLocal()
    unapproved_email = f"pending_emp_{uuid.uuid4().hex[:6]}@example.com"
    uid = f"uid_{uuid.uuid4().hex[:6]}"
    name = "Pending Employer"
    user = DBUser(
        full_name=name,
        email=unapproved_email,
        phone="+919876543211",
        password_hash="hash",
        role="EMPLOYER",
        status="ACTIVE",
        organization_status="PENDING_REVIEW",
        firebase_uid=uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.close()

    emp_token = create_test_firebase_jwt(uid=uid, email=unapproved_email, name=name)
    worker = create_test_worker("Target Worker")

    resp = client.get(f"/api/v1/worker/profile/{worker.id}", headers={"Authorization": f"Bearer {emp_token}"})
    assert resp.status_code == 403
    assert "approved" in resp.json()["detail"].lower()

# ---------------------------------------------------------------------------
# Dimension 4: Principal Isolation & Explicit Demo Account Tagging
# ---------------------------------------------------------------------------

def test_m2_demo_login_tags_is_demo_true():
    """Demo login explicitly returns is_demo=True in auth context."""
    resp = client.post("/api/v1/auth/demo-login/WORKER")
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data.get("is_demo") is True

def test_m2_real_user_auth_tags_is_demo_false():
    """Real authenticated Firebase user receives is_demo=False."""
    unique_email = f"real_worker_{uuid.uuid4().hex[:6]}@gmail.com"
    jwt_token = create_test_firebase_jwt(
        uid=f"real_uid_{uuid.uuid4().hex[:6]}",
        email=unique_email,
        name="Real User"
    )
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data.get("is_demo") is False

def test_m2_real_employer_never_receives_apex_data():
    """A newly registered real employer receives their actual company details, NEVER Apex Infrastructure."""
    db = SessionLocal()
    emp_email = f"corp_{uuid.uuid4().hex[:6]}@buildwell.com"
    uid = f"uid_buildwell_{uuid.uuid4().hex[:6]}"
    name = "BuildWell Enterprise Admin"
    user = DBUser(
        full_name=name,
        email=emp_email,
        phone="+919876543200",
        password_hash="hash",
        role="EMPLOYER",
        status="PENDING_REVIEW",
        firebase_uid=uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    org = DBEmployerOrganization(
        user_id=user.id,
        name="BuildWell Infra Private Limited",
        registration_ref_number="CIN-U45200KA2026PTC998877",
        status="PENDING_REVIEW"
    )
    db.add(org)
    db.commit()
    db.close()
    
    token = create_test_firebase_jwt(uid=uid, email=emp_email, name=name)
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    
    # Assert ZERO Apex leakage
    assert data.get("is_demo") is False
    if data.get("organization"):
        assert data["organization"]["name"] != "Apex Infrastructure & Construction Ltd"
        assert data["organization"]["address"] != "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        assert data["organization"]["name"] == "BuildWell Infra Private Limited"

def test_m2_suspended_user_rejected_with_403():
    """Suspended user attempting to query /api/v1/auth/me receives 403 Forbidden."""
    db = SessionLocal()
    email = f"suspended_{uuid.uuid4().hex[:6]}@example.com"
    uid = f"uid_suspended_{uuid.uuid4().hex[:6]}"
    name = "Suspended Worker"
    user = DBUser(
        full_name=name,
        email=email,
        phone="+919876543200",
        password_hash="hash",
        role="WORKER",
        status="SUSPENDED",
        firebase_uid=uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.close()

    token = create_test_firebase_jwt(uid=uid, email=email, name=name)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Dimension 5: Elimination of Unauthenticated Worker 1 Mutation & Presentation Bypass
# ---------------------------------------------------------------------------

def test_m2_unauthenticated_put_profile_rejected():
    """Unauthenticated PUT /profile/{user_id} is rejected with 401 Unauthorized (even for user_id == 1)."""
    resp = client.put("/api/v1/worker/profile/1", json={"worker_category": "Hacked"})
    assert resp.status_code == 401

def test_m2_unauthenticated_verify_aadhaar_rejected():
    """Unauthenticated POST /verify-aadhaar/{user_id} is rejected with 401 Unauthorized (even for user_id == 1)."""
    payload = {"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}
    resp = client.post("/api/v1/worker/verify-aadhaar/1", json=payload)
    assert resp.status_code == 401

def test_m2_unauthenticated_generate_qr_card_rejected():
    """Unauthenticated GET /presentation/qr-card/{user_id} is rejected with 401 Unauthorized (even for user_id == 1)."""
    resp = client.get("/api/v1/worker/presentation/qr-card/1")
    assert resp.status_code == 401

def test_m2_unauthenticated_download_qr_rejected():
    """Unauthenticated GET /presentation/download-qr/{user_id} is rejected with 401 Unauthorized (even for user_id == 1)."""
    resp = client.get("/api/v1/worker/presentation/download-qr/1")
    assert resp.status_code == 401

