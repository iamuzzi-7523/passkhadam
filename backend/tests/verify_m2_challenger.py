import sys
import os
import uuid
import json

sys.path.insert(0, os.path.abspath("backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployerOrganization
from app.core.auth import create_test_firebase_jwt

client = TestClient(app)

def run_all_stress_tests():
    report = {}

    # Helper to create test worker
    def create_worker(name, is_anchored=False):
        db = SessionLocal()
        email = f"worker_{uuid.uuid4().hex[:8]}@example.com"
        uid = f"uid_{uuid.uuid4().hex[:8]}"
        u = DBUser(
            full_name=name, email=email, phone="+919876543299",
            password_hash="hash", role="WORKER", status="ACTIVE",
            firebase_uid=uid, is_email_verified=True, is_phone_verified=True
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        user_id = u.id
        p = DBWorkerProfile(
            user_id=user_id, full_name=name, origin_state="Bihar", current_state="Maharashtra",
            worker_category="Carpenter", skills_json='["Carpenter"]',
            is_credential_anchored=is_anchored,
            did=f"did:passkhadam:worker:{user_id}" if is_anchored else None
        )
        db.add(p)
        db.commit()
        db.close()
        token = create_test_firebase_jwt(uid=uid, email=email, name=name)
        return user_id, token

    print("=== STRESS TEST 1: IDOR Protection ===")
    w_a_id, token_a = create_worker("Worker A", is_anchored=False)
    w_b_id, token_b = create_worker("Worker B", is_anchored=True)

    # 1.1 Worker A accesses Worker B profile
    r1_1 = client.get(f"/api/v1/worker/profile/{w_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    print(f"1.1 GET /profile/{{worker_b_id}} with Worker A token: {r1_1.status_code}")
    report["1.1_worker_a_access_worker_b_profile"] = {
        "expected": 403,
        "actual": r1_1.status_code,
        "pass": r1_1.status_code == 403,
        "response": r1_1.json()
    }

    # 1.2 Worker A updates Worker B profile
    r1_2 = client.put(f"/api/v1/worker/profile/{w_b_id}", json={"worker_category": "Hacked"}, headers={"Authorization": f"Bearer {token_a}"})
    print(f"1.2 PUT /profile/{{worker_b_id}} with Worker A token: {r1_2.status_code}")
    report["1.2_worker_a_update_worker_b_profile"] = {
        "expected": 403,
        "actual": r1_2.status_code,
        "pass": r1_2.status_code == 403,
        "response": r1_2.json()
    }

    # 1.3 Worker A generates Worker B QR card
    r1_3 = client.get(f"/api/v1/worker/presentation/qr-card/{w_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    print(f"1.3 GET /presentation/qr-card/{{worker_b_id}} with Worker A token: {r1_3.status_code}")
    report["1.3_worker_a_gen_worker_b_qr"] = {
        "expected": 403,
        "actual": r1_3.status_code,
        "pass": r1_3.status_code == 403,
        "response": r1_3.json()
    }

    print("\n=== STRESS TEST 2: Cross-Role RBAC ===")
    emp_token = client.post("/api/v1/auth/demo-login/EMPLOYER").json()["access_token"]
    gov_token = client.post("/api/v1/auth/demo-login/GOVERNMENT").json()["access_token"]

    r2_1 = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {emp_token}"})
    print(f"2.1 GET /worker/profile/me with Employer token: {r2_1.status_code}")
    report["2.1_employer_access_worker_profile_me"] = {
        "expected": 403,
        "actual": r2_1.status_code,
        "pass": r2_1.status_code == 403,
        "response": r2_1.json()
    }

    r2_2 = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {gov_token}"})
    print(f"2.2 GET /worker/profile/me with Government token: {r2_2.status_code}")
    report["2.2_government_access_worker_profile_me"] = {
        "expected": 403,
        "actual": r2_2.status_code,
        "pass": r2_2.status_code == 403,
        "response": r2_2.json()
    }

    r2_3 = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {emp_token}"})
    print(f"2.3 GET /worker/wallet/me with Employer token: {r2_3.status_code}")
    report["2.3_employer_access_worker_wallet_me"] = {
        "expected": 403,
        "actual": r2_3.status_code,
        "pass": r2_3.status_code == 403,
        "response": r2_3.json()
    }

    r2_4 = client.get("/api/v1/worker/wallet/me", headers={"Authorization": f"Bearer {gov_token}"})
    print(f"2.4 GET /worker/wallet/me with Government token: {r2_4.status_code}")
    report["2.4_government_access_worker_wallet_me"] = {
        "expected": 403,
        "actual": r2_4.status_code,
        "pass": r2_4.status_code == 403,
        "response": r2_4.json()
    }

    r2_5 = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token_a}"})
    print(f"2.5 GET /admin/dashboard with Worker token: {r2_5.status_code}")
    report["2.5_worker_access_admin_dashboard"] = {
        "expected": 403,
        "actual": r2_5.status_code,
        "pass": r2_5.status_code == 403,
        "response": r2_5.json()
    }

    print("\n=== STRESS TEST 3: Demo Principal Isolation ===")
    real_user_token = create_test_firebase_jwt(uid=f"real_{uuid.uuid4().hex[:6]}", email="real_worker@somedomain.com", name="Real Worker")
    r3_1 = client.get("/api/v1/auth/me?is_demo=true", headers={"Authorization": f"Bearer {real_user_token}"})
    r3_1_data = r3_1.json()
    print(f"3.1 GET /auth/me?is_demo=true with real user: status={r3_1.status_code}, is_demo={r3_1_data.get('is_demo')}")
    report["3.1_non_canonical_is_demo_false"] = {
        "expected": {"status": 200, "is_demo": False, "organization": None},
        "actual": {"status": r3_1.status_code, "is_demo": r3_1_data.get("is_demo"), "organization": r3_1_data.get("organization")},
        "pass": r3_1.status_code == 200 and r3_1_data.get("is_demo") is False and r3_1_data.get("organization") is None
    }

    # Real employer newly registered
    db = SessionLocal()
    emp_email = f"corp_{uuid.uuid4().hex[:6]}@realcompany.com"
    emp_uid = f"uid_{uuid.uuid4().hex[:6]}"
    eu = DBUser(
        full_name="Real Employer Admin", email=emp_email, phone="+919876543200",
        password_hash="hash", role="EMPLOYER", status="PENDING_REVIEW",
        firebase_uid=emp_uid, is_email_verified=True, is_phone_verified=True
    )
    db.add(eu)
    db.commit()
    db.refresh(eu)
    eorg = DBEmployerOrganization(
        user_id=eu.id, name="Real Construction Pvt Ltd", registration_ref_number="CIN-REAL-12345", status="PENDING_REVIEW"
    )
    db.add(eorg)
    db.commit()
    db.close()
    real_emp_token = create_test_firebase_jwt(uid=emp_uid, email=emp_email, name="Real Employer Admin")
    r3_2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {real_emp_token}"})
    r3_2_data = r3_2.json()
    has_apex_data = False
    org_data = r3_2_data.get("organization")
    if org_data:
        if "apex" in org_data.get("name", "").lower() or org_data.get("address") == "0x90F79bf6EB2c4f870365E785982E1f101E93b906":
            has_apex_data = True
    print(f"3.2 Real employer: is_demo={r3_2_data.get('is_demo')}, org_name={org_data.get('name') if org_data else None}, has_apex={has_apex_data}")
    report["3.2_real_employer_zero_apex"] = {
        "expected": {"is_demo": False, "has_apex_data": False},
        "actual": {"is_demo": r3_2_data.get("is_demo"), "has_apex_data": has_apex_data, "org_name": org_data.get("name") if org_data else None},
        "pass": r3_2_data.get("is_demo") is False and not has_apex_data
    }

    print("\n=== STRESS TEST 4: Suspended Account Enforcement ===")
    db = SessionLocal()
    susp_email = f"susp_{uuid.uuid4().hex[:6]}@example.com"
    susp_uid = f"uid_{uuid.uuid4().hex[:6]}"
    su = DBUser(
        full_name="Suspended Worker", email=susp_email, phone="+919876543200",
        password_hash="hash", role="WORKER", status="SUSPENDED",
        firebase_uid=susp_uid, is_email_verified=True, is_phone_verified=True
    )
    db.add(su)
    db.commit()
    db.refresh(su)
    sp = DBWorkerProfile(
        user_id=su.id, full_name="Suspended Worker", origin_state="Bihar", current_state="Maharashtra",
        worker_category="Mason", skills_json='["Mason"]', is_credential_anchored=False
    )
    db.add(sp)
    db.commit()
    db.close()
    susp_token = create_test_firebase_jwt(uid=susp_uid, email=susp_email, name="Suspended Worker")

    r4_1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {susp_token}"})
    print(f"4.1 GET /auth/me with suspended token: {r4_1.status_code}")
    report["4.1_suspended_auth_me"] = {
        "expected": 403,
        "actual": r4_1.status_code,
        "pass": r4_1.status_code == 403,
        "response": r4_1.json()
    }

    r4_2 = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {susp_token}"})
    print(f"4.2 GET /worker/profile/me with suspended token: {r4_2.status_code}")
    report["4.2_suspended_worker_profile_me"] = {
        "expected": 403,
        "actual": r4_2.status_code,
        "pass": r4_2.status_code == 403,
        "response": r4_2.json()
    }

    print("\n=== STRESS TEST 5: Worker Mutation & QR Authentication Enforcement ===")
    # 5.1 Unauthenticated PUT /profile/1
    r5_1 = client.put("/api/v1/worker/profile/1", json={"worker_category": "Tampered"})
    print(f"5.1 Unauthenticated PUT /profile/1: {r5_1.status_code}")
    report["5.1_unauthenticated_put_profile_1"] = {
        "expected": 401,
        "actual": r5_1.status_code,
        "pass": r5_1.status_code in [401, 403]
    }

    # 5.2 Unauthenticated GET /presentation/qr-card/1
    r5_2 = client.get("/api/v1/worker/presentation/qr-card/1")
    print(f"5.2 Unauthenticated GET /presentation/qr-card/1: {r5_2.status_code}")
    report["5.2_unauthenticated_gen_qr_1"] = {
        "expected": 401,
        "actual": r5_2.status_code,
        "pass": r5_2.status_code in [401, 403]
    }

    # 5.3 Unauthenticated POST /verify-aadhaar/1
    r5_3 = client.post("/api/v1/worker/verify-aadhaar/1", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"})
    print(f"5.3 Unauthenticated POST /verify-aadhaar/1: {r5_3.status_code}")
    report["5.3_unauthenticated_verify_aadhaar_1"] = {
        "expected": 401,
        "actual": r5_3.status_code,
        "pass": r5_3.status_code in [401, 403]
    }

    # 5.4 Authenticated Worker A updating Worker 1 -> 403 Forbidden
    r5_4 = client.put("/api/v1/worker/profile/1", json={"worker_category": "Tampered"}, headers={"Authorization": f"Bearer {token_a}"})
    print(f"5.4 Worker A updating Worker 1: {r5_4.status_code}")
    report["5.4_worker_a_tampering_worker_1"] = {
        "expected": 403,
        "actual": r5_4.status_code,
        "pass": r5_4.status_code == 403
    }

    return report

if __name__ == "__main__":
    report = run_all_stress_tests()
    print("\n=== SUMMARY REPORT ===")
    all_passed = True
    for test_name, res in report.items():
        status_str = "PASS" if res.get("pass") else "FAIL"
        if not res.get("pass"):
            all_passed = False
        print(f"[{status_str}] {test_name}: expected {res.get('expected')}, got {res.get('actual')}")

    print(f"\nFinal Verdict: {'CONFIRMED' if all_passed else 'FAILED'}")
    sys.exit(0 if all_passed else 1)
