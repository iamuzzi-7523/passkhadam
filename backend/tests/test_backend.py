import io
import json
import time
import pytest
from app.core.crypto import (
    encrypt_payload, decrypt_payload, sign_credential,
    verify_credential_signature, generate_worker_did, keccak_hash
)
from app.services.ipfs_service import ipfs_service
from app.services.aadhaar_service import aadhaar_authority
from app.services.blockchain_service import blockchain_service
from app.services.verification_engine import verification_engine

def test_aadhaar_verification_logic():
    # Valid record
    res = aadhaar_authority.verify_identity("123456784821", "Mohammed Uzair")
    assert res["verified"] is True
    assert res["status"] == "VERIFIED"
    assert res["masked_aadhaar"] == "XXXX XXXX 4821"
    assert res["origin_state"] == "Karnataka"

    # Valid name with transposed tokens
    res_transposed = aadhaar_authority.verify_identity("123456784821", "Uzair Mohammed")
    assert res_transposed["verified"] is True
    assert res_transposed["status"] == "VERIFIED"

    # Name mismatch
    res_mismatch = aadhaar_authority.verify_identity("123456784821", "Wrong Person Name")
    assert res_mismatch["verified"] is False
    assert res_mismatch["status"] == "REJECTED"

    # Empty name rejection
    res_empty = aadhaar_authority.verify_identity("123456784821", "")
    assert res_empty["verified"] is False
    assert res_empty["status"] == "REJECTED"
    assert "Invalid or empty name" in res_empty["reason"]

    # Whitespace name rejection
    res_ws = aadhaar_authority.verify_identity("123456784821", "   ")
    assert res_ws["verified"] is False
    assert res_ws["status"] == "REJECTED"
    assert "Invalid or empty name" in res_ws["reason"]

    # Single-character name rejection
    res_single = aadhaar_authority.verify_identity("123456784821", "a")
    assert res_single["verified"] is False
    assert res_single["status"] == "REJECTED"
    assert "Invalid or empty name" in res_single["reason"]

    # Inactive record
    res_inactive = aadhaar_authority.verify_identity("998877665544", "Lakshmi Narayana")
    assert res_inactive["verified"] is False
    assert "inactive" in res_inactive["reason"].lower()

def test_aes_encryption_and_ipfs():
    sample_data = {
        "did": "did:passkhadam:worker:12345678",
        "name": "Ramesh Verma",
        "trade": "Electrician"
    }
    encrypted = encrypt_payload(sample_data)
    assert encrypted != json.dumps(sample_data)

    decrypted = decrypt_payload(encrypted)
    assert decrypted == sample_data

    # IPFS Pinning & Resolution
    cid = ipfs_service.pin_payload(encrypted)
    assert cid.startswith("Qm")
    resolved = ipfs_service.resolve_payload(cid)
    assert resolved == encrypted

def test_ed25519_signatures():
    payload = {"worker": "did:passkhadam:worker:test", "issued": 123456}
    signature = sign_credential(payload)
    assert verify_credential_signature(payload, signature) is True
    # Tampered payload fails
    tampered = {"worker": "did:passkhadam:worker:test", "issued": 999999}
    assert verify_credential_signature(tampered, signature) is False

def test_qr_presentation_generation_and_verification():
    worker_did = "did:passkhadam:worker:test-qr-flow-v3"
    cred_payload = {
        "full_name": "Anil Sahu",
        "worker_category": "Mason",
        "employment_level": "Skilled",
        "nature_of_employment": "Contract",
        "skills": ["Mason", "Tiling"]
    }
    enc_blob = encrypt_payload({"credentialSubject": cred_payload, "proof": {"signatureValue": sign_credential(cred_payload)}})
    cid = ipfs_service.pin_payload(enc_blob)
    cred_hash = keccak_hash(enc_blob)

    # Register worker on-chain
    blockchain_service.register_worker(worker_did, cred_hash, cid)

    # Generate QR image
    png_bytes, envelope_json = verification_engine.generate_qr_presentation(worker_did, cred_payload)
    assert len(png_bytes) > 100

    # Test Employer Verification via uploaded QR image
    employer_res = verification_engine.verify_uploaded_presentation(
        png_bytes,
        caller_role="EMPLOYER",
        caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
    )
    assert employer_res["verified"] is True
    assert employer_res["worker_did"] == worker_did
    assert employer_res["data"]["full_name"] == "Anil Sahu"
    assert "Mason" in employer_res["data"]["skills"]
    assert any("BOCW" in cert["type"] for cert in employer_res["data"]["verified_certifications"])
    # Verify raw Aadhaar is NOT present
    assert "aadhaar_number" not in employer_res["data"]

    # Test Government Verification via uploaded QR image
    gov_res = verification_engine.verify_uploaded_presentation(
        png_bytes,
        caller_role="GOVERNMENT",
        caller_id="0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
    )
    assert gov_res["verified"] is True
    assert gov_res["data"]["full_name"] == "Anil Sahu"
    assert gov_res["data"]["origin_state_kyc_status"] == "CONFIRMED_VALID"
    assert "previous_claims" in gov_res["data"]

# --- CRITICAL SECURITY & INTEGRITY TESTS (P0 & P1) ---

def test_credential_tampering_integrity_hash_mismatch():
    """
    SECURITY TEST: Simulates a malicious actor modifying the credential payload on IPFS.
    The verification engine must recompute the hash, detect the mismatch against the
    on-chain anchor, and reject with an integrity failure!
    """
    worker_did = "did:passkhadam:worker:tamper-test"
    original_payload = {"full_name": "Authentic Worker", "worker_category": "Mason"}
    enc_original = encrypt_payload({"credentialSubject": original_payload, "proof": {"signatureValue": sign_credential(original_payload)}})
    original_cid = ipfs_service.pin_payload(enc_original)
    original_hash = keccak_hash(enc_original)

    # Blockchain anchors the original hash
    blockchain_service.register_worker(worker_did, original_hash, original_cid)

    # Attacker alters the payload and overwrites IPFS cache for that CID
    tampered_payload = {"full_name": "Imposter Attacker", "worker_category": "Master Engineer"}
    enc_tampered = encrypt_payload({"credentialSubject": tampered_payload, "proof": {"signatureValue": sign_credential(tampered_payload)}})
    ipfs_service._in_memory_cache[original_cid] = enc_tampered

    # Generate QR referencing this CID
    png_bytes, _ = verification_engine.generate_qr_presentation(worker_did, original_payload)

    # Verification MUST fail with On-chain integrity hash mismatch
    with pytest.raises(ValueError, match="Tampered credential detected"):
        verification_engine.verify_uploaded_presentation(
            png_bytes,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        )

def test_qr_tampering_envelope_signature_rejection():
    """
    SECURITY TEST: Altering the QR payload envelope invalidates the Ed25519 signature.
    """
    worker_did = "did:passkhadam:worker:qr-tamper"
    payload = {"full_name": "Valid Worker"}
    enc = encrypt_payload({"credentialSubject": payload, "proof": {"signatureValue": sign_credential(payload)}})
    cid = ipfs_service.pin_payload(enc)
    blockchain_service.register_worker(worker_did, keccak_hash(enc), cid)

    # Valid presentation
    png_bytes, env_json = verification_engine.generate_qr_presentation(worker_did, payload)
    env = json.loads(env_json)

    # Tamper with the envelope payload
    env["payload"]["worker_did"] = "did:passkhadam:worker:fraudulent-identity"
    tampered_json = json.dumps(env)

    # Encode tampered JSON into QR
    import qrcode
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(tampered_json)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    with pytest.raises(ValueError, match="Tampered or invalid presentation envelope signature"):
        verification_engine.verify_uploaded_presentation(
            buf.getvalue(),
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        )

def test_qr_expiration_rejection():
    """
    SECURITY TEST: Presentations older than expiration window must be rejected.
    """
    worker_did = "did:passkhadam:worker:expired-test"
    payload = {"full_name": "Valid Worker"}
    enc = encrypt_payload({"credentialSubject": payload, "proof": {"signatureValue": sign_credential(payload)}})
    cid = ipfs_service.pin_payload(enc)
    blockchain_service.register_worker(worker_did, keccak_hash(enc), cid)

    # Generate QR with negative validity (already expired)
    png_bytes, _ = verification_engine.generate_qr_presentation(worker_did, payload, validity_seconds=-10)

    with pytest.raises(ValueError, match="QR Presentation has expired"):
        verification_engine.verify_uploaded_presentation(
            png_bytes,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        )

def test_employment_lifecycle_and_dismissed_history_preservation():
    """
    LIFECYCLE TEST: Verifies that dismissing a worker updates the status
    while preserving append-only historical audit records.
    """
    worker_did = "did:passkhadam:worker:dismissal-test"
    employer_addr = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"

    emp = blockchain_service.create_employment(
        worker_did=worker_did,
        employer_address=employer_addr,
        category="Mason",
        job_role="Mason",
        location="Bengaluru",
        level="Skilled",
        nature_of_employment="Contract"
    )
    assert emp["status"] == "ACTIVE"

    # Dismiss worker
    blockchain_service.update_employment_status(
        emp_id=emp["id"],
        caller_address=employer_addr,
        new_status="DISMISSED",
        reason="Repeated workplace absence"
    )

    # Verify updated record
    updated = blockchain_service.employments[emp["id"]]
    assert updated["status"] == "DISMISSED"
    assert updated["status_reason"] == "Repeated workplace absence"

    # Verify historical events preserved (2 events: Created + Dismissed)
    events = blockchain_service.employment_events[emp["id"]]
    assert len(events) == 2
    assert events[0]["status"] == "ACTIVE"
    assert events[1]["status"] == "DISMISSED"

    # Verify active workforce does not list the dismissed worker
    active = blockchain_service.get_active_workforce(employer_addr)
    assert not any(a["id"] == emp["id"] for a in active)

def test_welfare_duplicate_prevention_dynamic_cooldown_and_sha256_id():
    """
    WELFARE TEST: Verifies dynamic cooldown message and deterministic SHA-256 Claim ID.
    """
    worker_did = "did:passkhadam:worker:welfare-v3-test"
    gov_addr = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"

    claim1 = blockchain_service.record_welfare_claim(1, worker_did, gov_addr, "MH")
    assert claim1["is_disbursed"] is True
    assert len(claim1["sha256_claim_id"]) == 64 # Valid SHA-256 hex string

    # Second claim attempt within 30-day cooldown raises dynamic error
    with pytest.raises(ValueError, match="Duplicate claim prevented. Cooldown active for"):
        blockchain_service.record_welfare_claim(1, worker_did, gov_addr, "MH")

def test_malformed_qr_payload_and_invalid_expiration():
    """
    SECURITY TEST: Validates rejection of malformed envelopes, non-dict payloads,
    and missing/non-numeric expires_at fields.
    """
    import qrcode

    def make_qr_bytes(content):
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(json.dumps(content) if isinstance(content, (dict, list)) else str(content))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # Non-dict payload
    bad_payload_qr = make_qr_bytes({"payload": "string_not_dict", "signature": "1234abcd"})
    with pytest.raises(ValueError, match="Invalid presentation token structure"):
        verification_engine.verify_uploaded_presentation(
            bad_payload_qr,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        )

    # Missing expires_at
    no_exp_qr = make_qr_bytes({"payload": {"worker_did": "did:test"}, "signature": "1234abcd"})
    with pytest.raises(ValueError, match="Invalid or missing presentation expiration timestamp"):
        verification_engine.verify_uploaded_presentation(
            no_exp_qr,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        )

    # String expires_at
    str_exp_qr = make_qr_bytes({"payload": {"expires_at": "not_a_number"}, "signature": "1234abcd"})
    with pytest.raises(ValueError, match="Invalid or missing presentation expiration timestamp"):
        verification_engine.verify_uploaded_presentation(
            str_exp_qr,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        )

    # Boolean expires_at
    bool_exp_qr = make_qr_bytes({"payload": {"expires_at": True}, "signature": "1234abcd"})
    with pytest.raises(ValueError, match="Invalid or missing presentation expiration timestamp"):
        verification_engine.verify_uploaded_presentation(
            bool_exp_qr,
            caller_role="EMPLOYER",
            caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906"
        )

