"""
PassKhadam v0.4 — Blockchain Privacy & Zero-PII Verification Test Suite
========================================================================
Opaque-box privacy verification suite asserting:
1. Zero raw 12-digit Aadhaar numbers placed on-chain.
2. Zero full demographic names placed on-chain.
3. Zero residential addresses or geographic PII placed on-chain.
4. Zero server-side private keys or data-encryption keys (DEK) placed on-chain.
5. All credentials pinned to IPFS are strictly AES-256-GCM encrypted ciphertext.
6. QR presentation envelopes contain zero raw Aadhaar numbers and zero private keys.
7. Role-Based redaction strictly conceals raw PII across Employer and Government verifier views.

Requirements: R1, R4, R9, R10
Specification: PassKhadam_v0.4_Product_Corrections_and_Workflow_Hardening.md §60-§68, §82, Acceptance Criteria §267
"""

import re
import json
import uuid
import pytest

from app.core.crypto import (
    generate_worker_did,
    encrypt_payload,
    decrypt_payload,
    sign_credential,
    verify_credential_signature,
    keccak_hash,
)
from app.services.ipfs_service import ipfs_service
from app.services.blockchain_service import blockchain_service
from app.services.verification_engine import verification_engine
from app.services.aadhaar_service import aadhaar_authority

RAW_AADHAAR_REGEX = re.compile(r"\b\d{12}\b|\b\d{4}\s\d{4}\s\d{4}\b")


@pytest.fixture
def clean_privacy_state():
    """Provides isolated testing environment for privacy assertions."""
    initial_registry = dict(blockchain_service.worker_registry)
    blockchain_service.worker_registry = {}
    yield
    blockchain_service.worker_registry = initial_registry


def test_blockchain_worker_registration_contains_zero_raw_aadhaar(clean_privacy_state):
    """
    R1, R9: Inspects on-chain worker registration records to assert zero 12-digit raw Aadhaar numbers.
    """
    test_cases = [
        {"aadhaar": "123456784821", "name": "Mohammed Uzair"},
        {"aadhaar": "987654321098", "name": "Ramesh Kumar Verma"},
        {"aadhaar": "554433221100", "name": "Anil Sahu"},
    ]

    for tc in test_cases:
        aadhaar = tc["aadhaar"]
        name = tc["name"]
        did = generate_worker_did(aadhaar, name)
        cred_blob = encrypt_payload({"aadhaar": aadhaar, "name": name})
        cid = ipfs_service.pin_payload(cred_blob)
        cred_hash = keccak_hash(cred_blob)

        blockchain_service.register_worker(did, cred_hash, cid)

        onchain_record = blockchain_service.get_worker(did)
        assert onchain_record is not None
        record_json_str = json.dumps(onchain_record)

        matches = RAW_AADHAAR_REGEX.findall(record_json_str)
        assert len(matches) == 0, f"Privacy violation: raw Aadhaar found in on-chain record: {matches}"
        assert aadhaar not in record_json_str, f"Raw Aadhaar {aadhaar} leaked into on-chain record"


def test_blockchain_worker_registration_contains_zero_demographic_names(clean_privacy_state):
    """
    R1, R4: Asserts that worker demographic full names never appear in any on-chain fields.
    """
    names = [
        "Mohammed Uzair",
        "Ramesh Kumar Verma",
        "Kavita Bai",
        "Sita Devi",
        "Anil Sahu",
    ]

    for name in names:
        dummy_aadhaar = f"11223344{abs(hash(name)) % 10000:04d}"
        did = generate_worker_did(dummy_aadhaar, name)
        cred_blob = encrypt_payload({"full_name": name, "category": "Mason"})
        cid = ipfs_service.pin_payload(cred_blob)
        cred_hash = keccak_hash(cred_blob)

        blockchain_service.register_worker(did, cred_hash, cid)

        onchain_record = blockchain_service.get_worker(did)
        record_str = json.dumps(onchain_record).lower()

        # Check full name and individual tokens
        assert name.lower() not in record_str, f"Full name {name} leaked into on-chain record: {record_str}"
        for token in name.split():
            if len(token) > 3:
                assert token.lower() not in record_str, f"Name token {token} leaked into on-chain record: {record_str}"


def test_blockchain_worker_registration_contains_zero_residential_addresses(clean_privacy_state):
    """
    R1: Asserts that detailed residential addresses or street PII never appear on-chain.
    """
    sensitive_addresses = [
        "Flat 402, Sunshine Residency, Whitefield, Bengaluru, Karnataka 560066",
        "House No 12, Ward 4, Rampur Village, District Gaya, Bihar 823001",
        "Plot 99, Industrial Area Phase 2, Navi Mumbai, Maharashtra 400705",
    ]

    for addr in sensitive_addresses:
        aadhaar = f"998877{abs(hash(addr)) % 1000000:06d}"
        did = generate_worker_did(aadhaar, "Test Worker")
        cred_blob = encrypt_payload({"address": addr, "city": "Bengaluru"})
        cid = ipfs_service.pin_payload(cred_blob)
        cred_hash = keccak_hash(cred_blob)

        blockchain_service.register_worker(did, cred_hash, cid)

        onchain_record = blockchain_service.get_worker(did)
        record_str = json.dumps(onchain_record).lower()

        assert "flat 402" not in record_str
        assert "whitefield" not in record_str
        assert "rampur" not in record_str
        assert "560066" not in record_str
        assert "823001" not in record_str


def test_blockchain_zero_server_private_keys_exposed(clean_privacy_state):
    """
    R4: Asserts that server-side Ed25519 signing private keys and encryption keys are NEVER on-chain.
    """
    from app.core.crypto import AUTHORITY_PRIVATE_KEY, PAYLOAD_SECRET_KEY

    # Check key representations
    priv_seed_hex = AUTHORITY_PRIVATE_KEY.private_bytes_raw().hex()
    enc_key_hex = PAYLOAD_SECRET_KEY.hex()

    did = "did:passkhadam:worker:privkey-leak-test-01"
    cred_blob = encrypt_payload({"test": "data"})
    cid = ipfs_service.pin_payload(cred_blob)
    cred_hash = keccak_hash(cred_blob)

    blockchain_service.register_worker(did, cred_hash, cid)

    # Dump all on-chain states
    all_state = json.dumps({
        "workers": blockchain_service.worker_registry,
        "orgs": blockchain_service.organizations,
        "employments": blockchain_service.employments,
        "claims": blockchain_service.claims,
    })

    assert priv_seed_hex not in all_state, "FATAL: Authority private seed found in on-chain state"
    assert enc_key_hex not in all_state, "FATAL: Symmetric encryption key found in on-chain state"


def test_ipfs_payload_is_strictly_encrypted_ciphertext_with_zero_plaintext_pii():
    """
    R4: Asserts that payloads stored on IPFS are AES-256-GCM ciphertext without plaintext PII.
    """
    secret_profile = {
        "aadhaar_number": "123456784821",
        "full_name": "Mohammed Uzair",
        "dob": "1994-08-15",
        "gender": "Male",
        "residential_address": "Koramangala 4th Block, Bengaluru",
        "worker_category": "Mason",
    }

    encrypted_blob = encrypt_payload(secret_profile)
    cid = ipfs_service.pin_payload(encrypted_blob)

    # Retrieve raw payload directly from IPFS store
    retrieved = ipfs_service.resolve_payload(cid)
    assert retrieved is not None
    assert retrieved != json.dumps(secret_profile)

    # Search for plaintext sensitive fields in raw IPFS string
    assert "123456784821" not in retrieved
    assert "Mohammed Uzair" not in retrieved
    assert "Koramangala" not in retrieved
    assert "1994-08-15" not in retrieved

    # Verification: only decrypt_payload with valid key recovers the plaintext
    decrypted = decrypt_payload(retrieved)
    assert decrypted == secret_profile


def test_qr_presentation_envelope_contains_zero_raw_aadhaar_or_private_keys(clean_privacy_state):
    """
    R4, R5: Asserts that the QR presentation envelope contains zero raw 12-digit Aadhaar and zero private keys.
    """
    raw_aadhaar = "123456784821"
    name = "Mohammed Uzair"
    did = generate_worker_did(raw_aadhaar, name)
    cred_blob = encrypt_payload({"full_name": name, "category": "Mason"})
    cid = ipfs_service.pin_payload(cred_blob)
    cred_hash = keccak_hash(cred_blob)

    blockchain_service.register_worker(did, cred_hash, cid)

    # Generate QR presentation
    png_bytes, envelope_json = verification_engine.generate_qr_presentation(
        worker_did=did,
        worker_profile={"full_name": name},
        validity_seconds=300,
    )

    envelope = json.loads(envelope_json)
    payload = envelope["payload"]

    envelope_dump = json.dumps(envelope)

    # Zero raw 12-digit numbers
    assert raw_aadhaar not in envelope_dump
    matches = RAW_AADHAAR_REGEX.findall(envelope_dump)
    assert len(matches) == 0, f"Raw Aadhaar detected in QR envelope: {matches}"

    # Verifiable presentation must have did, issued_at, expires_at, signature
    assert payload["worker_did"] == did
    assert "expires_at" in payload
    assert "signature" in envelope
    assert "private_key" not in envelope_dump
    assert "secret" not in envelope_dump


def test_employer_verifier_view_conceals_worker_raw_pii(clean_privacy_state):
    """
    R5: Asserts that verification under caller_role='EMPLOYER' conceals demographic PII.
    """
    did = "did:passkhadam:worker:employer-redaction-test"
    vc_body = {
        "full_name": "Sita Devi",
        "aadhaar_number": "998877665544",
        "masked_aadhaar": "XXXX XXXX 5544",
        "dob": "1990-01-01",
        "residential_address": "Gaya, Bihar",
        "worker_category": "Electrician",
        "employment_level": "Skilled",
        "skills": ["Industrial Wiring", "Safety Induction"],
        "origin_state": "Bihar",
        "current_state": "Maharashtra",
    }
    sig = sign_credential(vc_body)
    vc = {
        "credentialSubject": vc_body,
        "proof": {"signatureValue": sig},
    }
    enc_blob = encrypt_payload(vc)
    cid = ipfs_service.pin_payload(enc_blob)
    cred_hash = keccak_hash(enc_blob)

    blockchain_service.register_worker(did, cred_hash, cid)

    png_bytes, _ = verification_engine.generate_qr_presentation(did, {"full_name": "Sita Devi"})

    result = verification_engine.verify_uploaded_presentation(
        image_bytes=png_bytes,
        caller_role="EMPLOYER",
        caller_id="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
    )

    assert result["verified"] is True
    emp_data = result["data"]

    # Permitted fields for Employer
    assert emp_data["worker_did"] == did
    assert emp_data["worker_category"] == "Electrician"
    assert "Industrial Wiring" in emp_data["skills"]

    # Redacted fields: raw Aadhaar, DOB, residential address must NOT be present
    data_dump = json.dumps(emp_data)
    assert "998877665544" not in data_dump
    assert "1990-01-01" not in data_dump
    assert "Gaya, Bihar" not in data_dump


def test_government_verifier_view_exposes_masked_aadhaar_only_never_raw(clean_privacy_state):
    """
    R5: Asserts that Government verification view exposes only masked Aadhaar (XXXX XXXX 1234), never raw.
    """
    did = "did:passkhadam:worker:gov-redaction-test"
    vc_body = {
        "full_name": "Ramesh Kumar Verma",
        "aadhaar_number": "123456784821",
        "masked_aadhaar": "XXXX XXXX 4821",
        "dob": "1995-04-12",
        "origin_state": "Karnataka",
        "current_state": "Maharashtra",
        "worker_category": "Mason",
    }
    sig = sign_credential(vc_body)
    enc_blob = encrypt_payload({"credentialSubject": vc_body, "proof": {"signatureValue": sig}})
    cid = ipfs_service.pin_payload(enc_blob)
    cred_hash = keccak_hash(enc_blob)

    blockchain_service.register_worker(did, cred_hash, cid)

    png_bytes, _ = verification_engine.generate_qr_presentation(did, {"full_name": "Ramesh Kumar Verma"})

    result = verification_engine.verify_uploaded_presentation(
        image_bytes=png_bytes,
        caller_role="GOVERNMENT",
        caller_id="0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
    )

    assert result["verified"] is True
    gov_data = result["data"]

    assert gov_data["masked_aadhaar"] == "XXXX XXXX 4821"
    assert gov_data["is_interstate_worker"] is True
    assert gov_data["origin_state"] == "Karnataka"

    gov_dump = json.dumps(gov_data)
    assert "123456784821" not in gov_dump
    assert len(RAW_AADHAAR_REGEX.findall(gov_dump)) == 0


def test_adversarial_unicode_and_special_character_demographics_zero_leakage(clean_privacy_state):
    """
    Adversarial verification: Demographics with accented letters, hyphens, and apostrophes do not leak.
    """
    adversarial_demographics = [
        {"aadhaar": "991122334455", "name": "François O'Connor-García"},
        {"aadhaar": "882233445566", "name": "Dr. A. P. J. Abdul-Kalam Nagarajan"},
        {"aadhaar": "773344556677", "name": "München Über-Müller"},
    ]

    for adv in adversarial_demographics:
        did = generate_worker_did(adv["aadhaar"], adv["name"])
        enc_blob = encrypt_payload({"name": adv["name"], "aadhaar": adv["aadhaar"]})
        cid = ipfs_service.pin_payload(enc_blob)
        cred_hash = keccak_hash(enc_blob)

        blockchain_service.register_worker(did, cred_hash, cid)

        onchain_record = blockchain_service.get_worker(did)
        rec_dump = json.dumps(onchain_record)

        assert adv["aadhaar"] not in rec_dump
        assert adv["name"] not in rec_dump
        assert len(RAW_AADHAAR_REGEX.findall(rec_dump)) == 0


def test_multi_worker_aggregate_onchain_scan_privacy_guarantee(clean_privacy_state):
    """
    Stress privacy audit: Registers 15 workers and exhaustively verifies the entire blockchain ledger
    has zero instances of raw Aadhaar numbers or human names.
    """
    registered_aadhaars = []
    registered_names = []

    for i in range(15):
        aadhaar = f"90001000{i:04d}"
        name = f"Migrant Worker TestPersona {i}"
        registered_aadhaars.append(aadhaar)
        registered_names.append(name)

        did = generate_worker_did(aadhaar, name)
        enc_blob = encrypt_payload({"full_name": name, "aadhaar": aadhaar})
        cid = ipfs_service.pin_payload(enc_blob)
        cred_hash = keccak_hash(enc_blob)

        blockchain_service.register_worker(did, cred_hash, cid)

    # Exhaustive ledger dump
    full_ledger_dump = json.dumps({
        "worker_registry": blockchain_service.worker_registry,
        "organizations": blockchain_service.organizations,
        "employments": blockchain_service.employments,
        "claims": blockchain_service.claims,
    })

    for aadhaar in registered_aadhaars:
        assert aadhaar not in full_ledger_dump, f"Audit failure: raw Aadhaar {aadhaar} leaked into ledger"

    for name in registered_names:
        assert name not in full_ledger_dump, f"Audit failure: full name {name} leaked into ledger"

    assert len(RAW_AADHAAR_REGEX.findall(full_ledger_dump)) == 0, "Audit failure: 12-digit number found in ledger"
