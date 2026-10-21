"""
backend/tests/verify_m3_challenger.py
Empirical Challenger Script for Milestone 3 Worker Onboarding Lifecycle.

Executes standalone adversarial stress tests verifying:
1. Sequential 6-State Transitions:
   NOT_STARTED -> AADHAAR_SUBMITTED -> DID_GENERATED -> VC_ISSUED -> EVM_ANCHORED -> ACTIVE
2. Strict Idempotency:
   - Repeated POST /api/v1/worker/register (assert 0 duplicate records, 0 ValueError)
   - Repeated POST /api/v1/worker/verify-aadhaar/me (assert 0 duplicate records, 0 ValueError)
3. Partial Failure Handling & Resumption:
   - EVM RPC timeout / network error sets state to FAILED with failure_reason recorded
   - Retry resumes successfully to ACTIVE
4. Security Invariants:
   - Client-supplied DID rejection
   - Cross-account collision defense
"""

import os
import sys
import uuid
import json
import hashlib
from unittest.mock import patch

sys.path.insert(0, os.path.abspath("backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service

client = TestClient(app)

def create_isolated_worker(name="Challenger Worker", initial_state="NOT_STARTED"):
    db = SessionLocal()
    uid = f"uid_c_{uuid.uuid4().hex[:12]}"
    email = f"challenger_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    user = DBUser(
        firebase_uid=uid,
        full_name=name,
        email=email,
        phone="+91 9876543210",
        password_hash=pw_hash,
        role="WORKER",
        status="ACTIVE",
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = DBWorkerProfile(
        user_id=user.id,
        full_name=name,
        origin_state="Maharashtra",
        current_state="Maharashtra",
        worker_category="Electrician",
        skills_json=json.dumps(["Electrician"]),
        did_state=initial_state
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=name)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = user.id
    db.close()
    return user_id, email, token, headers


def run_all_challenger_tests():
    report = {}

    print("=== CHALLENGE 1: Sequential 6-State Transitions ===")
    user_id, _, _, headers = create_isolated_worker("Mohammed Uzair", "NOT_STARTED")

    # Step: Execute verification
    payload = {"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}
    res = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
    data = res.json()
    status_res = client.get("/api/v1/worker/lifecycle-status/me", headers=headers)
    status_data = status_res.json()

    c1_pass = (
        res.status_code == 200 and
        data.get("did_state") == "ACTIVE" and
        data.get("status") == "ANCHORED_ON_BLOCKCHAIN" and
        status_data.get("current_state") == "ACTIVE" and
        status_data.get("steps_completed") == ["NOT_STARTED", "AADHAAR_SUBMITTED", "DID_GENERATED", "VC_ISSUED", "EVM_ANCHORED", "ACTIVE"]
    )
    print(f"1.1 Sequential 6-state progression: {'PASS' if c1_pass else 'FAIL'}")
    report["1.1_sequential_6_state_progression"] = {
        "pass": c1_pass,
        "current_state": status_data.get("current_state"),
        "steps_completed": status_data.get("steps_completed")
    }

    print("\n=== CHALLENGE 2: Strict Idempotency on Repeated Registration ===")
    reg_email = f"idem_reg_{uuid.uuid4().hex[:8]}@example.com"
    reg_payload = {
        "full_name": "Idempotent Worker",
        "email": reg_email,
        "phone": "+91 9876543210",
        "password": "passkhadam123"
    }

    # Call 1
    r_init = client.post("/api/v1/worker/register", json=reg_payload)
    init_uid = r_init.json()["user"]["id"]

    # Repeat 10 times
    all_replays_ok = True
    for i in range(10):
        r_rep = client.post("/api/v1/worker/register", json=reg_payload)
        if r_rep.status_code != 200 or r_rep.json()["user"]["id"] != init_uid:
            all_replays_ok = False
            break

    db = SessionLocal()
    db_u_count = db.query(DBUser).filter(DBUser.email == reg_email.lower()).count()
    db_p_count = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == init_uid).count()
    db.close()

    c2_pass = all_replays_ok and db_u_count == 1 and db_p_count == 1
    print(f"2.1 Repeated registration (10x calls): {'PASS' if c2_pass else 'FAIL'} (Users={db_u_count}, Profiles={db_p_count})")
    report["2.1_registration_strict_idempotency"] = {
        "pass": c2_pass,
        "user_count": db_u_count,
        "profile_count": db_p_count
    }

    print("\n=== CHALLENGE 3: Strict Idempotency on Repeated Aadhaar Verification ===")
    # Repeat verification 10 times on active worker
    v_all_ok = True
    for i in range(10):
        r_v = client.post("/api/v1/worker/verify-aadhaar/me", json=payload, headers=headers)
        if r_v.status_code != 200 or not r_v.json().get("is_idempotent_replay"):
            v_all_ok = False
            break

    c3_pass = v_all_ok
    print(f"3.1 Repeated verify-aadhaar/me (10x calls): {'PASS' if c3_pass else 'FAIL'}")
    report["3.1_verify_aadhaar_strict_idempotency"] = {
        "pass": c3_pass
    }

    print("\n=== CHALLENGE 4: Partial Failure & Resumption ===")
    fail_uid, _, _, fail_headers = create_isolated_worker("Sunita Devi", "NOT_STARTED")
    sunita_payload = {"aadhaar_number": "554433221100", "full_name": "Sunita Devi"}

    # 4.1 EVM failure -> FAILED with failure_reason
    with patch.object(blockchain_service, "register_worker", side_effect=ConnectionError("RPC node unreachable")):
        r_fail = client.post("/api/v1/worker/verify-aadhaar/me", json=sunita_payload, headers=fail_headers)

    db = SessionLocal()
    p_fail = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == fail_uid).first()
    c4_1_pass = (
        r_fail.status_code == 503 and
        p_fail.did_state == "FAILED" and
        "RPC node unreachable" in (p_fail.failure_reason or "")
    )
    db.close()
    print(f"4.1 RPC ConnectionError triggers FAILED state & failure_reason: {'PASS' if c4_1_pass else 'FAIL'}")
    report["4.1_rpc_failure_state_handling"] = {
        "pass": c4_1_pass,
        "status_code": r_fail.status_code,
        "recorded_reason": p_fail.failure_reason
    }

    # 4.2 Retry resumes cleanly to ACTIVE
    r_retry = client.post("/api/v1/worker/verify-aadhaar/me", json=sunita_payload, headers=fail_headers)
    db = SessionLocal()
    p_active = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == fail_uid).first()
    c4_2_pass = (
        r_retry.status_code == 200 and
        r_retry.json().get("did_state") == "ACTIVE" and
        p_active.did_state == "ACTIVE" and
        p_active.is_credential_anchored is True and
        p_active.failure_reason is None
    )
    db.close()
    print(f"4.2 Retry resumes successfully to ACTIVE: {'PASS' if c4_2_pass else 'FAIL'}")
    report["4.2_retry_resumption_to_active"] = {
        "pass": c4_2_pass,
        "final_state": p_active.did_state
    }

    print("\n=== CHALLENGE 5: Security Invariants ===")
    # 5.1 Client-supplied DID rejection
    r_did_inj = client.post("/api/v1/worker/register", json={
        "full_name": "Attacker", "email": f"att_{uuid.uuid4().hex[:6]}@test.com", "phone": "+919876543210",
        "did": "did:passkhadam:worker:injected_did"
    })
    c5_1_pass = r_did_inj.status_code in [400, 422] and "strictly forbidden" in r_did_inj.text
    print(f"5.1 Client-supplied DID injection rejected: {'PASS' if c5_1_pass else 'FAIL'}")
    report["5.1_client_did_rejection"] = {"pass": c5_1_pass}

    # 5.2 Cross-account collision defense
    w2_id, _, _, w2_headers = create_isolated_worker("Attacker 2", "NOT_STARTED")
    r_theft = client.post("/api/v1/worker/verify-aadhaar/me", json={"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}, headers=w2_headers)
    c5_2_pass = r_theft.status_code == 409 and "already registered and anchored" in r_theft.json()["detail"]
    print(f"5.2 Cross-account Aadhaar theft rejected (409): {'PASS' if c5_2_pass else 'FAIL'}")
    report["5.2_cross_account_collision"] = {"pass": c5_2_pass}

    return report


if __name__ == "__main__":
    report = run_all_challenger_tests()
    print("\n=== SUMMARY REPORT ===")
    all_passed = True
    for k, v in report.items():
        res_str = "PASS" if v.get("pass") else "FAIL"
        if not v.get("pass"):
            all_passed = False
        print(f"[{res_str}] {k}")

    verdict = "CONFIRMED" if all_passed else "FAILED"
    print(f"\nFinal Verdict: {verdict}")
    sys.exit(0 if all_passed else 1)
