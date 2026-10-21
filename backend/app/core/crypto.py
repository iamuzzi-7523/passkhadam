import os
import json
import base64
import hashlib
from datetime import datetime, timezone
from typing import Union, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Multi-tier EVM Keccak-256 Engine (Web3.py -> PyCryptodome -> eth_hash)
try:
    from web3 import Web3
    def _evm_keccak_bytes(data: bytes) -> bytes:
        return bytes(Web3.keccak(primitive=data))
except ImportError:
    try:
        from Crypto.Hash import keccak as _pycrypto_keccak
        def _evm_keccak_bytes(data: bytes) -> bytes:
            k = _pycrypto_keccak.new(digest_bits=256)
            k.update(data)
            return k.digest()
    except ImportError:
        from eth_hash.auto import keccak as _eth_keccak
        def _evm_keccak_bytes(data: bytes) -> bytes:
            return _eth_keccak(data)

# Master encryption key for decentralized IPFS payloads (AES-256)
def get_payload_secret_key() -> bytes:
    try:
        from app.core.config import settings
        seed = getattr(settings, "PAYLOAD_SECRET_KEY_SEED", None) or getattr(settings, "PAYLOAD_SECRET_KEY", "passkhadam-decentralized-worker-vault-key-2026")
    except Exception:
        seed = os.getenv("PAYLOAD_SECRET_KEY_SEED") or os.getenv("PAYLOAD_SECRET_KEY", "passkhadam-decentralized-worker-vault-key-2026")
    return hashlib.sha256(str(seed).encode("utf-8")).digest()

PAYLOAD_SECRET_KEY = get_payload_secret_key()

# Master Identity Authority Ed25519 Signing Keypair
# Deterministically derived from AUTHORITY_SEED so signing keys persist across uvicorn reloads
try:
    from app.core.config import settings
    _seed_source = getattr(settings, "AUTHORITY_SEED", "passkhadam-master-authority-seed-2026")
except Exception:
    _seed_source = os.getenv("AUTHORITY_SEED", "passkhadam-master-authority-seed-2026")

_seed_bytes = hashlib.sha256(str(_seed_source).encode("utf-8")).digest()
AUTHORITY_PRIVATE_KEY = ed25519.Ed25519PrivateKey.from_private_bytes(_seed_bytes)
AUTHORITY_PUBLIC_KEY = AUTHORITY_PRIVATE_KEY.public_key()

def get_authority_public_bytes() -> str:
    pub_bytes = AUTHORITY_PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return pub_bytes.hex()

def generate_worker_did(aadhaar_number: str, name: str = "") -> str:
    """
    Deterministically/uniquely derives a worker DID without storing or leaking raw Aadhaar.
    Uses SHA-256 of salt + Aadhaar (+ Name).
    """
    try:
        from app.core.config import settings
        salt_source = getattr(settings, "DID_SALT", "passkhadam-did-seed-v1")
    except Exception:
        salt_source = os.getenv("DID_SALT", "passkhadam-did-seed-v1")
    salt = str(salt_source).encode("utf-8")
    payload = salt + aadhaar_number.encode("utf-8")
    if name:
        payload += name.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"did:passkhadam:worker:{digest[:16]}"

def hash_data(data_bytes: bytes) -> str:
    """Computes SHA-256 hex string."""
    return hashlib.sha256(data_bytes).hexdigest()

def canonical_json_bytes(obj: dict) -> bytes:
    """
    Returns RFC 8785 compliant canonical JSON bytes (sorted keys, compact separators, UTF-8)
    for deterministic cross-platform signing and verification between Python and JavaScript.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False
    ).encode("utf-8")

def keccak_hash(data: Union[str, bytes]) -> str:
    """
    Computes genuine Ethereum Keccak-256 (padding 0x01) for EVM compatibility.
    Accepts str or bytes; returns 0x-prefixed 64-character lowercase hex string (66 chars).
    """
    if isinstance(data, str):
        data_bytes = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray)):
        data_bytes = bytes(data)
    else:
        data_bytes = str(data).encode("utf-8")
    return "0x" + _evm_keccak_bytes(data_bytes).hex().lower()

def encrypt_payload(data_dict: dict) -> str:
    """
    Encrypts a JSON dictionary using AES-256-GCM.
    Returns base64 encoded nonce + ciphertext + tag.
    """
    aesgcm = AESGCM(get_payload_secret_key())
    nonce = os.urandom(12)
    data_bytes = canonical_json_bytes(data_dict)
    ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")

def decrypt_payload(encrypted_b64: str) -> dict:
    """
    Decrypts an AES-256-GCM payload.
    """
    encrypted_bytes = base64.b64decode(encrypted_b64.encode("utf-8"))
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    aesgcm = AESGCM(get_payload_secret_key())
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(decrypted_bytes.decode("utf-8"))

def sign_credential(credential_payload: dict) -> str:
    """
    Signs the canonical JSON representation of a credential using Authority Ed25519 key.
    Returns hex signature.
    """
    canonical_bytes = canonical_json_bytes(credential_payload)
    sig = AUTHORITY_PRIVATE_KEY.sign(canonical_bytes)
    return sig.hex()

def verify_credential_signature(credential_payload: dict, signature_hex: str) -> bool:
    """
    Verifies that a credential was signed by the Authority Ed25519 key.
    """
    try:
        canonical_bytes = canonical_json_bytes(credential_payload)
        sig_bytes = bytes.fromhex(signature_hex)
        AUTHORITY_PUBLIC_KEY.verify(sig_bytes, canonical_bytes)
        return True
    except Exception:
        return False

def build_w3c_verifiable_credential(
    vc_subject: dict,
    issuer_did: str = "did:passkhadam:authority:identity-gateway"
) -> dict:
    """
    Builds a W3C Verifiable Credentials Data Model v1.1 compliant credential.
    Canonicalizes vc_subject using RFC 8785 before signing with Ed25519 Authority key.
    Includes @context, id, type, issuer, issuanceDate, credentialSubject, and proof.
    """
    subject_id = str(vc_subject.get("id") or "")
    issuance_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature = sign_credential(vc_subject)

    suffix = subject_id[-8:] if len(subject_id) >= 8 else hashlib.sha256(issuance_date.encode()).hexdigest()[:8]
    return {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "id": f"urn:uuid:vc-{suffix}",
        "type": ["VerifiableCredential", "WorkerIdentityCredential"],
        "issuer": issuer_did,
        "issuanceDate": issuance_date,
        "credentialSubject": vc_subject,
        "proof": {
            "type": "Ed25519Signature2020",
            "proofPurpose": "assertionMethod",
            "verificationMethod": f"{issuer_did}#key-1",
            "created": issuance_date,
            "signatureValue": signature
        }
    }
