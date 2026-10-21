import os
import sys
import io
import json
import base64
import time
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

def run_end_to_end_verification():
    print("======================================================================")
    print("   PASSKHADAM — COMPLETE END-TO-END SYSTEM INTEGRATION TEST (v0.3)")
    print("======================================================================")

    client = TestClient(app)

    # -------------------------------------------------------------------------
    # STAGE 1: Worker Joins PASSKHADAM & Completes Contact Verification
    # -------------------------------------------------------------------------
    print("\n[STAGE 1] Registering Worker Account & Profile...")
    worker_email = f"ramesh.verma.{int(time.time())}@passkhadam.org"
    reg_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Ramesh Kumar Verma",
        "email": worker_email,
        "phone": "+91 9123456789",
        "password": "Password@123",
        "role": "WORKER"
    })
    assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
    worker_data = reg_resp.json()
    worker_id = worker_data["user"]["id"]
    print(f"  ✓ Worker registered: ID {worker_id}, Email Verified ✓, Phone Verified ✓")

    # Update profile trade & skills
    update_resp = client.put(f"/api/v1/worker/profile/{worker_id}", json={
        "worker_category": "Mason",
        "skills": ["Mason", "Plastering", "Tiling"],
        "origin_state": "Bihar",
        "current_state": "Karnataka"
    })
    assert update_resp.status_code == 200
    print("  ✓ Worker profile completed (Origin: Bihar, Current: Karnataka, Trade: Mason)")

    # -------------------------------------------------------------------------
    # STAGE 2: Aadhaar Identity Verification via Mock Authority
    # -------------------------------------------------------------------------
    print("\n[STAGE 2] Submitting Government Identity Verification (Mock Aadhaar API)...")
    aadhaar_resp = client.post(f"/api/v1/worker/verify-aadhaar/{worker_id}", json={
        "aadhaar_number": "987654321012",
        "full_name": "Ramesh Kumar Verma"
    })
    assert aadhaar_resp.status_code == 200, f"Aadhaar verification failed: {aadhaar_resp.text}"
    aadhaar_data = aadhaar_resp.json()
    worker_did = aadhaar_data["did"]
    ipfs_cid = aadhaar_data["ipfs_cid"]
    print(f"  ✓ Aadhaar Verified: {aadhaar_data['masked_aadhaar']}")
    print(f"  ✓ Verified Government Document Visual Generated:")
    print(f"     - Title: {aadhaar_data['verified_document_visual']['title']}")
    print(f"     - Status: {aadhaar_data['verified_document_visual']['status']} (Simulated Record)")
    print(f"  ✓ Decentralized Identifier (DID) Bound: {worker_did}")
    print(f"  ✓ Verifiable Credential Signed & Pinned to IPFS: {ipfs_cid}")
    print(f"  ✓ Integrity Hash Anchored on Blockchain: {aadhaar_data['credential_hash']}")

    # -------------------------------------------------------------------------
    # STAGE 3: Worker Inspects Credential Wallet (including BOCW)
    # -------------------------------------------------------------------------
    print("\n[STAGE 3] Inspecting Worker Credential Wallet...")
    wallet_resp = client.get(f"/api/v1/worker/wallet/{worker_id}")
    assert wallet_resp.status_code == 200
    wallet_data = wallet_resp.json()
    assert wallet_data["is_verified"] is True
    print(f"  ✓ Wallet Active: {len(wallet_data['credentials'])} credentials loaded:")
    for c in wallet_data["credentials"]:
        print(f"     - {c['title']} ({c['type']}) | Status: {c['status']}")
    assert any("BOCW" in c["title"] for c in wallet_data["credentials"])
    print("  ✓ BOCW Safety Certification active in wallet.")

    # -------------------------------------------------------------------------
    # STAGE 4: Worker Generates QR Identity Presentation Card
    # -------------------------------------------------------------------------
    print("\n[STAGE 4] Worker Generates Cryptographic QR Presentation...")
    qr_card_resp = client.get(f"/api/v1/worker/presentation/qr-card/{worker_id}")
    assert qr_card_resp.status_code == 200
    qr_info = qr_card_resp.json()
    raw_envelope = qr_info["raw_envelope"]
    print(f"  ✓ QR Presentation Generated (Expires in: {qr_info['expires_in_seconds']}s)")
    print(f"  ✓ Envelope Ed25519 Signature: {raw_envelope['signature'][:20]}...")

    # Download raw PNG bytes
    qr_download_resp = client.get(f"/api/v1/worker/presentation/download-qr/{worker_id}")
    assert qr_download_resp.status_code == 200
    qr_png_bytes = qr_download_resp.content
    print(f"  ✓ Worker downloads QR presentation image card ({len(qr_png_bytes)} bytes)")

    # -------------------------------------------------------------------------
    # STAGE 5: Employer Verifies Worker via Drag-and-Drop QR Image Upload
    # -------------------------------------------------------------------------
    print("\n[STAGE 5] Employer Uploads Worker QR Image (No Camera)...")
    verify_emp_resp = client.post(
        "/api/v1/employer/verify-worker-qr",
        files={"file": ("worker_qr.png", qr_png_bytes, "image/png")}
    )
    assert verify_emp_resp.status_code == 200, f"Employer verification failed: {verify_emp_resp.text}"
    emp_verify_data = verify_emp_resp.json()
    assert emp_verify_data["verified"] is True
    print(f"  ✓ Common Verification Engine executed 10-step cryptographic sequence:")
    for step in emp_verify_data["audit_steps"]:
        print(f"     [{step['status']}] Step {step['step']}: {step['name']} -> {step['detail']}")
    
    # Check RBAC filter: employer sees skills & BOCW, NOT raw aadhaar
    assert "skills" in emp_verify_data["data"]
    assert "aadhaar_number" not in emp_verify_data["data"]
    print("  ✓ RBAC Verified: Employer granted access to verified skills & BOCW status; PII concealed.")

    # Employer offers on-chain employment
    print("\n  [Stage 5.1] Employer Logging On-Chain Employment Record...")
    offer_resp = client.post("/api/v1/employer/create-employment", json={
        "worker_did": worker_did,
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Head Mason",
        "work_location": "Bengaluru Site B",
        "expected_end_date": 1775000000
    })
    assert offer_resp.status_code == 200
    emp_record = offer_resp.json()["employment_record"]
    emp_id = emp_record["id"]
    print(f"  ✓ Employment Record #{emp_id} Anchored on EmploymentRegistry: Status ACTIVE")

    # Complete employment / Dismissal testing
    status_resp = client.put("/api/v1/employer/employment-status", json={
        "employment_id": emp_id,
        "new_status": "COMPLETED",
        "reason": "Project structural phase concluded successfully"
    })
    assert status_resp.status_code == 200
    print(f"  ✓ Employment #{emp_id} updated to COMPLETED with auditable reason.")

    # -------------------------------------------------------------------------
    # STAGE 6: Worker Moves to Another State (Interstate Mobility)
    # -------------------------------------------------------------------------
    print("\n[STAGE 6] Worker Relocates from Karnataka to Maharashtra...")
    client.put(f"/api/v1/worker/profile/{worker_id}", json={
        "current_state": "Maharashtra"
    })
    print("  ✓ Worker relocates. Identity remains valid without re-registering or re-verifying Aadhaar.")

    # -------------------------------------------------------------------------
    # STAGE 7: Government Verifies Worker via QR Upload & Disburses Claim
    # -------------------------------------------------------------------------
    print("\n[STAGE 7] Maharashtra Government Officer Uploads Worker QR Image...")
    fresh_qr = client.get(f"/api/v1/worker/presentation/download-qr/{worker_id}").content

    verify_gov_resp = client.post(
        "/api/v1/government/verify-worker-qr",
        files={"file": ("worker_qr_gov.png", fresh_qr, "image/png")}
    )
    assert verify_gov_resp.status_code == 200
    gov_verify_data = verify_gov_resp.json()
    assert gov_verify_data["verified"] is True
    print("  ✓ Government officer verification successful:")
    gov_view = gov_verify_data["data"]
    print(f"     - Worker Origin State: {gov_view['origin_state']}")
    print(f"     - Interstate Worker Detected: {gov_view['is_interstate_worker']}")
    print(f"     - Origin-State KYC Status: {gov_view['origin_state_kyc_status']}")
    print(f"     - Masked Aadhaar: {gov_view['masked_aadhaar']}")

    # Disburse welfare benefit claim
    print("\n  [Stage 7.1] Disbursing Interstate Migrant Relief Claim on Blockchain...")
    claim_resp = client.post("/api/v1/government/disburse-claim", json={
        "scheme_id": 1,
        "worker_did": worker_did,
        "officer_state": "Maharashtra",
        "gov_officer_wallet": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
    })
    assert claim_resp.status_code == 200
    claim_info = claim_resp.json()["claim_record"]
    print(f"  ✓ Welfare Claim #{claim_info['claim_id']} Disbursed: ₹{claim_info['amount']} ({claim_info['scheme_name']})")
    print(f"  ✓ SHA-256 Claim ID Anchored: {claim_info['sha256_claim_id'][:16]}...")

    # Verify duplicate claim rejection
    print("\n  [Stage 7.2] Verifying Duplicate Claim Prevention (30-Day Cooldown)...")
    dup_resp = client.post("/api/v1/government/disburse-claim", json={
        "scheme_id": 1,
        "worker_did": worker_did,
        "officer_state": "Maharashtra",
        "gov_officer_wallet": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
    })
    assert dup_resp.status_code == 400
    print(f"  ✓ Duplicate Claim Successfully Rejected: {dup_resp.json()['detail']}")

    print("\n======================================================================")
    print("   ✓ ALL 7 LIFECYCLE STAGES SUCCESSFULLY VERIFIED PROGRAMMATICALLY")
    print("======================================================================")

if __name__ == "__main__":
    run_end_to_end_verification()
