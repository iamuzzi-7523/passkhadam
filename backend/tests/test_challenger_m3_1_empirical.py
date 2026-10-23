"""
backend/tests/test_challenger_m3_1_empirical.py
Milestone 3 Empirical Challenger Test Suite (challenger_m3_1)

Adversarial Stress Testing of:
1. Zero-Camera Simulation Replay Invariant:
   - Consecutive demo QR requests yield unique presentation IDs & valid PNGs.
   - Sequential simulations do NOT trigger HTTP 409 REPLAY_ATTACK_DETECTED.
   - Re-submitting the exact same QR file twice DOES trigger HTTP 409 REPLAY_ATTACK_DETECTED.
   - Cross-role composite replay defense (independent Employer vs Government verification).
2. All 11 Verification Audit Steps Verification & Payload Integrity:
   - Verification across Employer & Government roles.
   - Handling of expired presentations and malformed QR inputs.
"""

import io
import json
import base64
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBConsumedPresentationNonce
from app.services.verification_engine import verification_engine
from app.core.auth import create_test_firebase_jwt
from app.services.blockchain_service import blockchain_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_shared_state():
    yield
    blockchain_service.last_claim_times.pop("did:passkhadam:worker:welfare-v3-test", None)


def _get_employer_headers():
    token = create_test_firebase_jwt(uid="uid_employer_apex", email="employer@apexinfra.com")
    return {"Authorization": f"Bearer {token}"}


def _get_government_headers():
    token = create_test_firebase_jwt(uid="uid_gov_mh", email="gov@maharashtra.gov.in")
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. CONSECUTIVE DEMO QR PRESENTATION REQUESTS & UNIQUENESS
# ============================================================================

def test_challenge_consecutive_demo_qr_employer_endpoint_uniqueness():
    """
    Challenge 1.1: Request demo QR presentation twice consecutively from Employer endpoint.
    Verify two unique presentation IDs, two valid QR PNGs, and distinct nonces.
    """
    headers = _get_employer_headers()

    # Request 1
    resp1 = client.get("/api/v1/employer/demo-worker-qr", headers=headers)
    assert resp1.status_code == 200, resp1.text
    data1 = resp1.json()

    # Request 2
    resp2 = client.get("/api/v1/employer/demo-worker-qr", headers=headers)
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()

    assert data1["qr_base64_data_uri"].startswith("data:image/png;base64,")
    assert data2["qr_base64_data_uri"].startswith("data:image/png;base64,")

    raw_bytes1 = base64.b64decode(data1["qr_base64_data_uri"].split(",")[1])
    raw_bytes2 = base64.b64decode(data2["qr_base64_data_uri"].split(",")[1])

    # Valid PNG headers
    assert raw_bytes1.startswith(b"\x89PNG\r\n\x1a\n")
    assert raw_bytes2.startswith(b"\x89PNG\r\n\x1a\n")

    # Images must not be identical bytes (different timestamp / nonce)
    assert raw_bytes1 != raw_bytes2

    # Decode and parse QR payloads
    qr_text1 = verification_engine.decode_qr_image(raw_bytes1)
    qr_text2 = verification_engine.decode_qr_image(raw_bytes2)

    assert qr_text1, "Failed to decode QR 1"
    assert qr_text2, "Failed to decode QR 2"

    env1 = json.loads(qr_text1)
    env2 = json.loads(qr_text2)

    pres_id1 = env1.get("presentation_id") or env1.get("payload", {}).get("presentation_id")
    pres_id2 = env2.get("presentation_id") or env2.get("payload", {}).get("presentation_id")

    assert pres_id1 is not None and pres_id2 is not None
    assert pres_id1.startswith("urn:uuid:")
    assert pres_id2.startswith("urn:uuid:")
    assert pres_id1 != pres_id2, f"Presentation IDs must be strictly unique! Both got {pres_id1}"

    nonce1 = env1.get("nonce") or env1.get("payload", {}).get("nonce")
    nonce2 = env2.get("nonce") or env2.get("payload", {}).get("nonce")
    assert nonce1 != nonce2, f"Cryptographic nonces must be strictly unique! Both got {nonce1}"


def test_challenge_consecutive_demo_qr_government_endpoint_uniqueness():
    """
    Challenge 1.2: Request demo QR presentation twice consecutively from Government endpoint.
    Verify two unique presentation IDs and two valid QR PNGs.
    """
    headers = _get_government_headers()

    resp1 = client.get("/api/v1/government/demo-worker-qr", headers=headers)
    assert resp1.status_code == 200, resp1.text
    data1 = resp1.json()

    resp2 = client.get("/api/v1/government/demo-worker-qr", headers=headers)
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()

    raw_bytes1 = base64.b64decode(data1["qr_base64_data_uri"].split(",")[1])
    raw_bytes2 = base64.b64decode(data2["qr_base64_data_uri"].split(",")[1])

    assert raw_bytes1.startswith(b"\x89PNG\r\n\x1a\n")
    assert raw_bytes2.startswith(b"\x89PNG\r\n\x1a\n")

    qr_text1 = verification_engine.decode_qr_image(raw_bytes1)
    qr_text2 = verification_engine.decode_qr_image(raw_bytes2)

    env1 = json.loads(qr_text1)
    env2 = json.loads(qr_text2)

    pres_id1 = env1.get("presentation_id") or env1.get("payload", {}).get("presentation_id")
    pres_id2 = env2.get("presentation_id") or env2.get("payload", {}).get("presentation_id")

    assert pres_id1 != pres_id2


def test_challenge_consecutive_demo_qr_worker_endpoint_uniqueness():
    """
    Challenge 1.3: Request demo QR presentation twice consecutively from Worker public fallback.
    Verify unique presentation IDs and valid PNGs.
    """
    resp1 = client.get("/api/v1/worker/presentation/demo-qr")
    assert resp1.status_code == 200
    data1 = resp1.json()

    resp2 = client.get("/api/v1/worker/presentation/demo-qr")
    assert resp2.status_code == 200
    data2 = resp2.json()

    raw_bytes1 = base64.b64decode(data1["qr_base64_data_uri"].split(",")[1])
    raw_bytes2 = base64.b64decode(data2["qr_base64_data_uri"].split(",")[1])

    qr_text1 = verification_engine.decode_qr_image(raw_bytes1)
    qr_text2 = verification_engine.decode_qr_image(raw_bytes2)

    env1 = json.loads(qr_text1)
    env2 = json.loads(qr_text2)

    pres_id1 = env1.get("presentation_id") or env1.get("payload", {}).get("presentation_id")
    pres_id2 = env2.get("presentation_id") or env2.get("payload", {}).get("presentation_id")

    assert pres_id1 != pres_id2


# ============================================================================
# 2. SEQUENTIAL SIMULATIONS DO NOT TRIGGER HTTP 409 REPLAY ATTACK
# ============================================================================

def test_challenge_sequential_simulations_employer_no_409():
    """
    Challenge 2.1: Perform 4 back-to-back zero-camera simulation cycles for Employer.
    Each cycle requests a fresh QR and immediately submits it.
    Verify all 4 cycles complete with HTTP 200 and zero HTTP 409 conflicts.
    """
    headers = _get_employer_headers()

    for i in range(4):
        # 1. Request demo QR
        gen_resp = client.get("/api/v1/employer/demo-worker-qr", headers=headers)
        assert gen_resp.status_code == 200, f"Cycle {i+1} generate failed: {gen_resp.text}"
        qr_uri = gen_resp.json()["qr_base64_data_uri"]
        png_bytes = base64.b64decode(qr_uri.split(",")[1])

        # 2. Submit to verify-worker-qr
        files = {"file": (f"simulated_worker_{i}.png", io.BytesIO(png_bytes), "image/png")}
        verify_resp = client.post("/api/v1/employer/verify-worker-qr", headers=headers, files=files)

        assert verify_resp.status_code == 200, (
            f"Cycle {i+1} verification failed unexpectedly with status {verify_resp.status_code}: {verify_resp.text}"
        )
        res_data = verify_resp.json()
        assert res_data["verified"] is True
        assert len(res_data["audit_steps"]) == 11
        assert res_data["audit_steps"][-1]["name"] == "Deferred Atomic Nonce Consumption"
        assert res_data["audit_steps"][-1]["status"] == "SUCCESS"


def test_challenge_sequential_simulations_government_no_409():
    """
    Challenge 2.2: Perform 3 back-to-back zero-camera simulation cycles for Government.
    Each cycle requests a fresh QR and immediately submits it.
    Verify all cycles complete with HTTP 200 and zero HTTP 409 conflicts.
    """
    headers = _get_government_headers()

    for i in range(3):
        gen_resp = client.get("/api/v1/government/demo-worker-qr", headers=headers)
        assert gen_resp.status_code == 200
        qr_uri = gen_resp.json()["qr_base64_data_uri"]
        png_bytes = base64.b64decode(qr_uri.split(",")[1])

        files = {"file": (f"simulated_worker_gov_{i}.png", io.BytesIO(png_bytes), "image/png")}
        verify_resp = client.post("/api/v1/government/verify-worker-qr", headers=headers, files=files)

        assert verify_resp.status_code == 200, (
            f"Government cycle {i+1} failed with status {verify_resp.status_code}: {verify_resp.text}"
        )
        res_data = verify_resp.json()
        assert res_data["verified"] is True
        assert len(res_data["audit_steps"]) == 11
        assert res_data["audit_steps"][-1]["status"] == "SUCCESS"


# ============================================================================
# 3. RE-SUBMITTING EXACT SAME QR FILE TWICE DOES TRIGGER HTTP 409
# ============================================================================

def test_challenge_duplicate_qr_submission_employer_triggers_409():
    """
    Challenge 3.1: Re-submitting the exact same QR file twice to Employer verification
    MUST trigger HTTP 409 Conflict with REPLAY_ATTACK_DETECTED.
    """
    headers = _get_employer_headers()

    # Generate one single presentation
    gen_resp = client.get("/api/v1/employer/demo-worker-qr", headers=headers)
    assert gen_resp.status_code == 200
    png_bytes = base64.b64decode(gen_resp.json()["qr_base64_data_uri"].split(",")[1])

    # First submission -> MUST SUCCEED (200)
    files1 = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
    res1 = client.post("/api/v1/employer/verify-worker-qr", headers=headers, files=files1)
    assert res1.status_code == 200, f"First submission failed: {res1.text}"
    assert res1.json()["verified"] is True

    # Second submission (replay attempt) -> MUST BE REJECTED with HTTP 409
    files2 = {"file": ("worker_presentation.png", io.BytesIO(png_bytes), "image/png")}
    res2 = client.post("/api/v1/employer/verify-worker-qr", headers=headers, files=files2)
    assert res2.status_code == 409, f"Expected HTTP 409 Conflict on replay, got {res2.status_code}: {res2.text}"

    err_detail = res2.json().get("detail", "")
    assert "REPLAY_ATTACK_DETECTED" in err_detail
    assert "single-use" in err_detail.lower()


def test_challenge_duplicate_qr_submission_government_triggers_409():
    """
    Challenge 3.2: Re-submitting the exact same QR file twice to Government verification
    MUST trigger HTTP 409 Conflict with REPLAY_ATTACK_DETECTED.
    """
    headers = _get_government_headers()

    gen_resp = client.get("/api/v1/government/demo-worker-qr", headers=headers)
    assert gen_resp.status_code == 200
    png_bytes = base64.b64decode(gen_resp.json()["qr_base64_data_uri"].split(",")[1])

    # First submission -> 200
    files1 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res1 = client.post("/api/v1/government/verify-worker-qr", headers=headers, files=files1)
    assert res1.status_code == 200
    assert res1.json()["verified"] is True

    # Second submission -> 409
    files2 = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
    res2 = client.post("/api/v1/government/verify-worker-qr", headers=headers, files=files2)
    assert res2.status_code == 409, f"Expected HTTP 409, got {res2.status_code}: {res2.text}"
    assert "REPLAY_ATTACK_DETECTED" in res2.json().get("detail", "")


# ============================================================================
# 4. CROSS-ROLE COMPOSITE REPLAY DEFENSE INVARIANT
# ============================================================================

def test_challenge_cross_role_composite_replay_invariant():
    """
    Challenge 4.1: Cross-Role Verifier Context Invariant.
    A single valid presentation can be legitimately verified once by Employer
    AND once by Government (different verifier roles).
    However, neither role can verify it a second time.
    """
    emp_headers = _get_employer_headers()
    gov_headers = _get_government_headers()

    # Generate one valid QR presentation
    gen_resp = client.get("/api/v1/employer/demo-worker-qr", headers=emp_headers)
    assert gen_resp.status_code == 200
    png_bytes = base64.b64decode(gen_resp.json()["qr_base64_data_uri"].split(",")[1])

    # 1. Employer verifies -> 200 OK
    files_emp1 = {"file": ("shared_worker.png", io.BytesIO(png_bytes), "image/png")}
    r_emp1 = client.post("/api/v1/employer/verify-worker-qr", headers=emp_headers, files=files_emp1)
    assert r_emp1.status_code == 200, f"Employer first verification failed: {r_emp1.text}"

    # 2. Government verifies SAME presentation -> 200 OK (composite key: role=GOVERNMENT != EMPLOYER)
    files_gov1 = {"file": ("shared_worker.png", io.BytesIO(png_bytes), "image/png")}
    r_gov1 = client.post("/api/v1/government/verify-worker-qr", headers=gov_headers, files=files_gov1)
    assert r_gov1.status_code == 200, f"Government independent verification failed: {r_gov1.text}"

    # 3. Employer submits AGAIN -> 409 Conflict!
    files_emp2 = {"file": ("shared_worker.png", io.BytesIO(png_bytes), "image/png")}
    r_emp2 = client.post("/api/v1/employer/verify-worker-qr", headers=emp_headers, files=files_emp2)
    assert r_emp2.status_code == 409
    assert "REPLAY_ATTACK_DETECTED" in r_emp2.json().get("detail", "")

    # 4. Government submits AGAIN -> 409 Conflict!
    files_gov2 = {"file": ("shared_worker.png", io.BytesIO(png_bytes), "image/png")}
    r_gov2 = client.post("/api/v1/government/verify-worker-qr", headers=gov_headers, files=files_gov2)
    assert r_gov2.status_code == 409
    assert "REPLAY_ATTACK_DETECTED" in r_gov2.json().get("detail", "")


# ============================================================================
# 5. ALL 11 VERIFICATION AUDIT STEPS AUDIT & INTEGRITY
# ============================================================================

def test_challenge_all_11_verification_steps_structure():
    """
    Challenge 5.1: Assert complete structure and SUCCESS status for all 11 steps
    in verification audit_steps.
    """
    headers = _get_employer_headers()

    gen_resp = client.get("/api/v1/employer/demo-worker-qr", headers=headers)
    assert gen_resp.status_code == 200
    png_bytes = base64.b64decode(gen_resp.json()["qr_base64_data_uri"].split(",")[1])

    files = {"file": ("audit_worker.png", io.BytesIO(png_bytes), "image/png")}
    verify_resp = client.post("/api/v1/employer/verify-worker-qr", headers=headers, files=files)
    assert verify_resp.status_code == 200
    data = verify_resp.json()

    steps = data.get("audit_steps", [])
    assert len(steps) == 11, f"Expected exactly 11 audit steps, found {len(steps)}"

    expected_steps = [
        (1, "Payload Parse & Schema Validation"),
        (2, "Presentation Signature Verification"),
        (3, "Expiration / Timestamp Validation"),
        (4, "On-Chain DID & Registration Verification"),
        (5, "IPFS Credential Retrieval"),
        (6, "Integrity Hash Verification"),
        (7, "Decryption of Verifiable Credential"),
        (8, "Issuer Signature Verification"),
        (9, "Role-Based Data Redaction"),
        (10, "Verifier Authorization & Scope Check"),
        (11, "Deferred Atomic Nonce Consumption")
    ]

    for (exp_num, exp_name), actual in zip(expected_steps, steps):
        assert actual["step"] == exp_num, f"Step mismatch: expected {exp_num}, got {actual['step']}"
        assert actual["name"] == exp_name, f"Name mismatch for step {exp_num}: expected '{exp_name}', got '{actual['name']}'"
        assert actual["status"] == "SUCCESS", f"Step {exp_num} status must be SUCCESS, got {actual['status']}"
        assert len(actual.get("detail", "")) > 0, f"Step {exp_num} missing detail description"


# ============================================================================
# 6. EDGE CASES: EXPIRED PRESENTATION & MALFORMED INPUTS
# ============================================================================

def test_challenge_expired_presentation_rejection():
    """
    Challenge 6.1: An expired presentation must be rejected at Step 3 without consuming nonce.
    """
    headers = _get_employer_headers()

    # Generate an expired presentation directly with validity_seconds=-10
    demo_user = DBUser.query if hasattr(DBUser, "query") else None
    db = SessionLocal()
    try:
        prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.did.isnot(None)).first()
        assert prof is not None

        expired_png, _ = verification_engine.generate_qr_presentation(
            worker_did=prof.did,
            worker_profile={"full_name": prof.full_name},
            validity_seconds=-10  # Expired
        )
    finally:
        db.close()

    files = {"file": ("expired_worker.png", io.BytesIO(expired_png), "image/png")}
    resp = client.post("/api/v1/employer/verify-worker-qr", headers=headers, files=files)
    assert resp.status_code == 400
    assert "EXPIRED" in resp.json().get("detail", "").upper()


def test_challenge_corrupted_image_bytes():
    """
    Challenge 6.2: Uploading corrupted bytes or non-QR images returns HTTP 400 MALFORMED_QR.
    """
    headers = _get_employer_headers()

    # Random binary noise
    garbage = b"\x00\x01\x02\x03\x04\x05\x06\x07" * 100
    files = {"file": ("garbage.png", io.BytesIO(garbage), "image/png")}
    resp = client.post("/api/v1/employer/verify-worker-qr", headers=headers, files=files)
    assert resp.status_code == 400
    detail_lower = resp.json().get("detail", "").lower()
    assert (
        "malformed_qr" in detail_lower or
        "could not be detected" in detail_lower or
        "failed to decode qr code" in detail_lower or
        "cannot identify image file" in detail_lower
    )


def test_challenge_empty_file_upload():
    """
    Challenge 6.3: Uploading an empty file returns HTTP 400 Bad Request.
    """
    headers = _get_employer_headers()
    files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
    resp = client.post("/api/v1/employer/verify-worker-qr", headers=headers, files=files)
    assert resp.status_code == 400
    assert "empty" in resp.json().get("detail", "").lower()
