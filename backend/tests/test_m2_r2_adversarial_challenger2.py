"""
Milestone 2 Round 2 — Adversarial Stress Test Suite (Challenger 2)
==================================================================
File: backend/tests/test_m2_r2_adversarial_challenger2.py
Author: Challenger 2 (m2_r2_challenger_2)

Adversarial Stress Testing Mandate:
1. Malformed and expired JWT Bearer tokens to:
   - GET /api/v1/admin/dashboard
   - PUT /api/v1/worker/profile/1
   - GET /api/v1/worker/profile/1
2. Non-admin roles querying /api/v1/admin/dashboard:
   - EMPLOYER (demo & custom accounts)
   - GOVERNMENT (demo & custom accounts)
   - AADHAAR_ADMIN / AADHAAR (demo & custom accounts)
   - WORKER (demo & custom accounts)
   - Unauthenticated callers
3. Cross-tenant worker profile updates & IDOR mutations:
   - Worker B attempting to update Worker A profile (PUT /profile/{A_id})
   - Worker B attempting to verify Aadhaar for Worker A (POST /verify-aadhaar/{A_id})
   - Worker B attempting to generate QR card for Worker A (GET /presentation/qr-card/{A_id})
   - Worker B attempting to download QR presentation for Worker A (GET /presentation/download-qr/{A_id})
   - Worker B attempting to inspect Worker A profile/wallet
   - Non-worker roles (Employer, Government) attempting to mutate worker profiles
   - Worker B attempting to mutate Worker ID 1
   - Integrity assertion: Worker A profile remains strictly unmodified after failed mutations
4. Boundary IDs and negative user IDs on mutating & parameterized endpoints:
   - Negative user IDs (-1, -999999, -2147483648)
   - Zero ID (0)
   - Extreme boundary IDs (999999, 2147483647)
   - SQL injection / non-integer path parameters
   - Tested under Worker principal, Admin principal, and Unauthenticated access
"""

import json
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployerOrganization
from app.core.auth import create_test_firebase_jwt, base64url_encode

client = TestClient(app)


# ============================================================================
# TEST FIXTURES & HELPERS
# ============================================================================

class TestUserHolder:
    def __init__(self, id: int, firebase_uid: str, email: str, full_name: str, role: str):
        self.id = id
        self.firebase_uid = firebase_uid
        self.email = email
        self.full_name = full_name
        self.role = role


def create_db_user(role: str, name: str, status: str = "ACTIVE") -> TestUserHolder:
    """Helper to provision test users with dedicated credentials."""
    db = SessionLocal()
    email = f"{role.lower()}_{uuid.uuid4().hex[:8]}@adversarial-test.org"
    uid = f"uid_{role.lower()}_{uuid.uuid4().hex[:8]}"
    u = DBUser(
        full_name=name,
        email=email,
        phone="+919876543200",
        password_hash="adversarial_hash",
        role=role,
        status=status,
        firebase_uid=uid,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    user_id = u.id

    if role == "WORKER":
        profile = DBWorkerProfile(
            user_id=user_id,
            full_name=name,
            origin_state="Bihar",
            current_state="Maharashtra",
            worker_category="Mason",
            skills_json='["Mason", "Plumbing"]',
            is_credential_anchored=False
        )
        db.add(profile)
        db.commit()

    db.close()
    return TestUserHolder(user_id, uid, email, name, role)


def generate_raw_jwt(header: dict, payload: dict, signature: bytes = b"mock_sig") -> str:
    """Constructs raw JWT from dictionaries with explicit base64url encoding."""
    h_b64 = base64url_encode(json.dumps(header).encode("utf-8"))
    p_b64 = base64url_encode(json.dumps(payload).encode("utf-8"))
    s_b64 = base64url_encode(signature)
    return f"{h_b64}.{p_b64}.{s_b64}"


# ============================================================================
# 1. ADVERSARIAL SUITE 1: MALFORMED & EXPIRED JWT BEARER TOKENS
# ============================================================================

class TestAdversarialJWTTokens:
    """
    Stress-testing JWT parsing, signature/claims validation, and rejection of
    expired, truncated, or forged Bearer tokens against /admin/dashboard and /worker/profile/1.
    """

    def test_expired_jwt_rejected_on_admin_dashboard(self):
        """Expired JWT to /api/v1/admin/dashboard must return 401 Unauthorized."""
        expired_token = create_test_firebase_jwt(
            uid="admin_expired_uid",
            email="admin@passkhadam.org",
            name="Platform Admin",
            expired=True
        )
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    def test_expired_jwt_rejected_on_put_worker_profile(self):
        """Expired JWT to PUT /api/v1/worker/profile/1 must return 401 Unauthorized."""
        expired_token = create_test_firebase_jwt(
            uid="worker_expired_uid",
            email="worker@passkhadam.org",
            name="Worker 1",
            expired=True
        )
        resp = client.put(
            "/api/v1/worker/profile/1",
            json={"worker_category": "Tampered"},
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    def test_expired_jwt_rejected_on_get_worker_profile(self):
        """Expired JWT supplied in Authorization header to GET /api/v1/worker/profile/1 must return 401."""
        expired_token = create_test_firebase_jwt(
            uid="worker_expired_uid",
            email="worker@passkhadam.org",
            name="Worker 1",
            expired=True
        )
        resp = client.get(
            "/api/v1/worker/profile/1",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize("malformed_token", [
        "not_a_jwt_at_all",
        "header_only_no_dots",
        "header.payload_only_two_dots_missing_one",
        "a.b.c.d.extra_segment",
        "",
        "   ",
        "pk_token_invalid_format",
        "mock_firebase_token_",
    ])
    def test_malformed_token_structure_rejected(self, malformed_token):
        """Malformed token structures must return 401 Unauthorized across protected endpoints."""
        for endpoint, method in [
            ("/api/v1/admin/dashboard", "GET"),
            ("/api/v1/worker/profile/1", "PUT")
        ]:
            headers = {"Authorization": f"Bearer {malformed_token}"} if malformed_token.strip() else {}
            if method == "GET":
                resp = client.get(endpoint, headers=headers)
            else:
                resp = client.put(endpoint, json={"worker_category": "Tampered"}, headers=headers)
            assert resp.status_code in [401, 403], f"Failed on {method} {endpoint} with token '{malformed_token}': got {resp.status_code}"

    def test_invalid_audience_jwt_rejected(self):
        """JWT with invalid 'aud' claim must return 401 Unauthorized."""
        wrong_aud_token = create_test_firebase_jwt(
            uid="admin_uid",
            email="admin@passkhadam.org",
            aud="malicious-project-id"
        )
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {wrong_aud_token}"}
        )
        assert resp.status_code == 401
        assert "audience" in resp.json()["detail"].lower()

    def test_invalid_issuer_jwt_rejected(self):
        """JWT with invalid 'iss' claim must return 401 Unauthorized."""
        wrong_iss_token = create_test_firebase_jwt(
            uid="admin_uid",
            email="admin@passkhadam.org",
            iss="https://accounts.google.com/malicious"
        )
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {wrong_iss_token}"}
        )
        assert resp.status_code == 401
        assert "issuer" in resp.json()["detail"].lower()

    def test_missing_subject_claim_jwt_rejected(self):
        """JWT missing subject ('sub' or 'user_id') claim must return 401 Unauthorized."""
        now = int(time.time())
        token = generate_raw_jwt(
            header={"alg": "RS256", "typ": "JWT"},
            payload={
                "iss": "https://securetoken.google.com/passkhadam-live",
                "aud": "passkhadam-live",
                "exp": now + 3600,
                "email": "orphan@passkhadam.org"
                # Missing 'sub' and 'user_id'
            }
        )
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert "subject" in resp.json()["detail"].lower()

    def test_garbage_base64_payload_jwt_rejected(self):
        """JWT with non-JSON garbage payload must return 401 Unauthorized without 500 crash."""
        token = "eyJhbGciOiJSUzI1NiJ9.bm9uLWpzb24tZ2FyYmFnZQ.mock_sig"
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert "unable to parse" in resp.json()["detail"].lower()


# ============================================================================
# 2. ADVERSARIAL SUITE 2: NON-ADMIN ROLES QUERYING /admin/dashboard
# ============================================================================

class TestAdversarialAdminRBAC:
    """
    Stress-testing RBAC enforcement on /api/v1/admin/dashboard.
    Assures strictly ADMIN role is permitted; all other roles receive 403 Forbidden.
    """

    def test_unauthenticated_admin_dashboard_rejected(self):
        """Unauthenticated request to /admin/dashboard returns 401."""
        resp = client.get("/api/v1/admin/dashboard")
        assert resp.status_code == 401

    def test_demo_employer_cannot_access_admin_dashboard(self):
        """Demo EMPLOYER token cannot access /admin/dashboard (403 Forbidden)."""
        token = client.post("/api/v1/auth/demo-login/EMPLOYER").json()["access_token"]
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "only administrators" in resp.json()["detail"].lower()

    def test_demo_government_cannot_access_admin_dashboard(self):
        """Demo GOVERNMENT token cannot access /admin/dashboard (403 Forbidden)."""
        token = client.post("/api/v1/auth/demo-login/GOVERNMENT").json()["access_token"]
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "only administrators" in resp.json()["detail"].lower()

    def test_demo_worker_cannot_access_admin_dashboard(self):
        """Demo WORKER token cannot access /admin/dashboard (403 Forbidden)."""
        token = client.post("/api/v1/auth/demo-login/WORKER").json()["access_token"]
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "only administrators" in resp.json()["detail"].lower()

    def test_demo_aadhaar_authority_cannot_access_admin_dashboard(self):
        """Demo AADHAAR token cannot access /admin/dashboard (403 Forbidden)."""
        token = client.post("/api/v1/auth/demo-login/AADHAAR").json()["access_token"]
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "only administrators" in resp.json()["detail"].lower()

    def test_custom_aadhaar_admin_cannot_access_admin_dashboard(self):
        """Custom user with role AADHAAR_ADMIN cannot access /admin/dashboard (403 Forbidden)."""
        user = create_db_user(role="AADHAAR_ADMIN", name="Aadhaar Admin Operator")
        token = create_test_firebase_jwt(uid=user.firebase_uid, email=user.email, name=user.full_name)
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "only administrators" in resp.json()["detail"].lower()

    def test_custom_employer_cannot_access_admin_dashboard(self):
        """Custom non-demo EMPLOYER user cannot access /admin/dashboard (403 Forbidden)."""
        user = create_db_user(role="EMPLOYER", name="Independent Contractor LLC")
        token = create_test_firebase_jwt(uid=user.firebase_uid, email=user.email, name=user.full_name)
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "only administrators" in resp.json()["detail"].lower()

    def test_custom_government_officer_cannot_access_admin_dashboard(self):
        """Custom non-demo GOVERNMENT officer cannot access /admin/dashboard (403 Forbidden)."""
        user = create_db_user(role="GOVERNMENT", name="District Welfare Officer")
        token = create_test_firebase_jwt(uid=user.firebase_uid, email=user.email, name=user.full_name)
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "only administrators" in resp.json()["detail"].lower()

    def test_admin_access_admin_dashboard_succeeds(self):
        """Legitimate ADMIN token successfully retrieves /admin/dashboard (200 OK)."""
        token = client.post("/api/v1/auth/demo-login/ADMIN").json()["access_token"]
        resp = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "organizations" in data
        assert "total_workers_anchored" in data
        assert "total_employments" in data
        assert "total_welfare_claims" in data


# ============================================================================
# 3. ADVERSARIAL SUITE 3: CROSS-TENANT WORKER PROFILE MUTATIONS (IDOR)
# ============================================================================

class TestAdversarialCrossTenantWorkerMutations:
    """
    Stress-testing horizontal privilege escalation (IDOR) on worker endpoints:
    Worker B attempting to mutate or inspect Worker A records.
    """

    @pytest.fixture(autouse=True)
    def setup_workers(self):
        self.worker_a = create_db_user(role="WORKER", name="Worker Alice")
        self.worker_b = create_db_user(role="WORKER", name="Worker Bob")
        self.token_a = create_test_firebase_jwt(
            uid=self.worker_a.firebase_uid, email=self.worker_a.email, name=self.worker_a.full_name
        )
        self.token_b = create_test_firebase_jwt(
            uid=self.worker_b.firebase_uid, email=self.worker_b.email, name=self.worker_b.full_name
        )

    def test_cross_tenant_profile_update_rejected(self):
        """Worker B attempting PUT /profile/{Worker_A_id} returns 403 Forbidden."""
        resp = client.put(
            f"/api/v1/worker/profile/{self.worker_a.id}",
            json={"worker_category": "Adversarial Takeover", "address": "Hostile Territory"},
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        assert resp.status_code == 403
        assert "only update their own profile" in resp.json()["detail"].lower()

        # Database Integrity Invariant: Alice's record remains Mason, Bihar
        db = SessionLocal()
        profile_a = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == self.worker_a.id).first()
        assert profile_a.worker_category == "Mason"
        assert profile_a.address != "Hostile Territory"
        db.close()

    def test_cross_tenant_verify_aadhaar_rejected(self):
        """Worker B attempting POST /verify-aadhaar/{Worker_A_id} returns 403 Forbidden."""
        resp = client.post(
            f"/api/v1/worker/verify-aadhaar/{self.worker_a.id}",
            json={"aadhaar_number": "123456784821", "full_name": "Worker Alice"},
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        assert resp.status_code == 403
        assert "only verify their own aadhaar" in resp.json()["detail"].lower()

    def test_cross_tenant_qr_card_generation_rejected(self):
        """Worker B attempting GET /presentation/qr-card/{Worker_A_id} returns 403 Forbidden."""
        resp = client.get(
            f"/api/v1/worker/presentation/qr-card/{self.worker_a.id}",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        assert resp.status_code == 403
        assert "only generate their own qr" in resp.json()["detail"].lower()

    def test_cross_tenant_download_qr_rejected(self):
        """Worker B attempting GET /presentation/download-qr/{Worker_A_id} returns 403 Forbidden."""
        resp = client.get(
            f"/api/v1/worker/presentation/download-qr/{self.worker_a.id}",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        assert resp.status_code == 403
        assert "only download their own qr" in resp.json()["detail"].lower()

    def test_cross_tenant_profile_read_rejected(self):
        """Worker B attempting GET /profile/{Worker_A_id} returns 403 Forbidden."""
        resp = client.get(
            f"/api/v1/worker/profile/{self.worker_a.id}",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        assert resp.status_code == 403
        assert "only view their own profile" in resp.json()["detail"].lower()

    def test_cross_tenant_wallet_read_rejected(self):
        """Worker B attempting GET /wallet/{Worker_A_id} returns 403 Forbidden."""
        resp = client.get(
            f"/api/v1/worker/wallet/{self.worker_a.id}",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        assert resp.status_code == 403
        assert "only view their own wallet" in resp.json()["detail"].lower()

    def test_employer_cannot_mutate_worker_profile(self):
        """Employer token attempting PUT /profile/{Worker_A_id} returns 403 Forbidden."""
        emp_token = client.post("/api/v1/auth/demo-login/EMPLOYER").json()["access_token"]
        resp = client.put(
            f"/api/v1/worker/profile/{self.worker_a.id}",
            json={"worker_category": "Unauthorized"},
            headers={"Authorization": f"Bearer {emp_token}"}
        )
        assert resp.status_code == 403

    def test_government_cannot_mutate_worker_profile(self):
        """Government token attempting PUT /profile/{Worker_A_id} returns 403 Forbidden."""
        gov_token = client.post("/api/v1/auth/demo-login/GOVERNMENT").json()["access_token"]
        resp = client.put(
            f"/api/v1/worker/profile/{self.worker_a.id}",
            json={"worker_category": "Unauthorized"},
            headers={"Authorization": f"Bearer {gov_token}"}
        )
        assert resp.status_code == 403

    def test_worker_b_cannot_mutate_worker_id_1(self):
        """Worker B attempting PUT /profile/1 returns 403 Forbidden."""
        resp = client.put(
            "/api/v1/worker/profile/1",
            json={"worker_category": "Tampered"},
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        assert resp.status_code == 403

    def test_worker_a_mutating_own_profile_succeeds(self):
        """Worker A mutating own profile succeeds with 200 OK."""
        resp = client.put(
            f"/api/v1/worker/profile/{self.worker_a.id}",
            json={"worker_category": "Master Carpenter"},
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Profile updated successfully"

        # Verify update in DB
        db = SessionLocal()
        p = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == self.worker_a.id).first()
        assert p.worker_category == "Master Carpenter"
        db.close()


# ============================================================================
# 4. ADVERSARIAL SUITE 4: BOUNDARY IDS AND NEGATIVE USER IDS ON MUTATING APIS
# ============================================================================

class TestAdversarialBoundaryIDs:
    """
    Stress-testing boundary values, negative numbers, overflow integers,
    and non-existent entities on mutating and parameterized endpoints.
    """

    @pytest.fixture(autouse=True)
    def setup_actor(self):
        self.worker = create_db_user(role="WORKER", name="Boundary Worker")
        self.worker_token = create_test_firebase_jwt(
            uid=self.worker.firebase_uid, email=self.worker.email, name=self.worker.full_name
        )
        self.admin_token = client.post("/api/v1/auth/demo-login/ADMIN").json()["access_token"]

    @pytest.mark.parametrize("boundary_id", [-1, -999999, 0, 999999, 2147483647])
    def test_worker_token_on_boundary_id_mutations_blocked_by_rbac(self, boundary_id):
        """
        Worker token sent with boundary ID (which does not match worker.id)
        must return 403 Forbidden across all mutating endpoints.
        """
        # PUT /profile/{boundary_id}
        r_put = client.put(
            f"/api/v1/worker/profile/{boundary_id}",
            json={"worker_category": "Boundary Hack"},
            headers={"Authorization": f"Bearer {self.worker_token}"}
        )
        assert r_put.status_code == 403

        # POST /verify-aadhaar/{boundary_id}
        r_post = client.post(
            f"/api/v1/worker/verify-aadhaar/{boundary_id}",
            json={"aadhaar_number": "123456784821", "full_name": "Boundary Worker"},
            headers={"Authorization": f"Bearer {self.worker_token}"}
        )
        assert r_post.status_code == 403

        # GET /presentation/qr-card/{boundary_id}
        r_qr = client.get(
            f"/api/v1/worker/presentation/qr-card/{boundary_id}",
            headers={"Authorization": f"Bearer {self.worker_token}"}
        )
        assert r_qr.status_code == 403

        # GET /presentation/download-qr/{boundary_id}
        r_dl = client.get(
            f"/api/v1/worker/presentation/download-qr/{boundary_id}",
            headers={"Authorization": f"Bearer {self.worker_token}"}
        )
        assert r_dl.status_code == 403

    @pytest.mark.parametrize("boundary_id", [-1, -999999, 0, 999999])
    def test_admin_token_on_nonexistent_boundary_id_returns_404(self, boundary_id):
        """
        Admin token passes RBAC check, but non-existent boundary ID returns clean 404 Not Found,
        without crashing or producing an unhandled 500 error.
        """
        r_put = client.put(
            f"/api/v1/worker/profile/{boundary_id}",
            json={"worker_category": "Admin Update"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert r_put.status_code == 404
        assert "not found" in r_put.json()["detail"].lower()

        r_verify = client.post(
            f"/api/v1/worker/verify-aadhaar/{boundary_id}",
            json={"aadhaar_number": "123456784821", "full_name": "Test"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert r_verify.status_code == 404
        assert "not found" in r_verify.json()["detail"].lower()

    @pytest.mark.parametrize("boundary_id", [-1, 0, 999999])
    def test_unauthenticated_mutating_endpoints_with_boundary_id_rejected(self, boundary_id):
        """Unauthenticated mutation requests with boundary IDs return 401 Unauthorized."""
        r_put = client.put(f"/api/v1/worker/profile/{boundary_id}", json={"worker_category": "Hack"})
        assert r_put.status_code == 401

        r_verify = client.post(
            f"/api/v1/worker/verify-aadhaar/{boundary_id}",
            json={"aadhaar_number": "123456784821", "full_name": "Test"}
        )
        assert r_verify.status_code == 401

        r_qr = client.get(f"/api/v1/worker/presentation/qr-card/{boundary_id}")
        assert r_qr.status_code == 401

        r_dl = client.get(f"/api/v1/worker/presentation/download-qr/{boundary_id}")
        assert r_dl.status_code == 401

    @pytest.mark.parametrize("invalid_path_val", [
        "notanumber",
        "0.5",
        "true",
        "%27%20OR%201=1%20--",
        "null",
        "NaN"
    ])
    def test_non_integer_path_parameters_rejected_with_422(self, invalid_path_val):
        """Non-integer path parameters rejected with 422 Unprocessable Entity by FastAPI validation."""
        r_put = client.put(
            f"/api/v1/worker/profile/{invalid_path_val}",
            json={"worker_category": "Hack"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert r_put.status_code == 422

        r_get = client.get(
            f"/api/v1/worker/profile/{invalid_path_val}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert r_get.status_code == 422
