"""
backend/tests/test_m4_aadhaar_crud_audit.py
Comprehensive Milestone 4 Test Suite:
- Mock Aadhaar CRUD operations with surrogate UUID record_id
- URL Privacy Boundary enforcement (rejection of raw 12-digit numbers in path parameters)
- Machine-to-Machine service authentication via X-PassKhadam-Service-Key
- Append-only audit logging in DBAadhaarAuditLog and immutability validation
- Directory search, filtering, and live dashboard metrics
"""

import os
import sys
import uuid
import hashlib
import random
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.core.config import settings
from app.models.db import SessionLocal, DBAadhaarRecord, DBAadhaarAuditLog
from app.services.aadhaar_service import aadhaar_authority

client = TestClient(app)


def generate_unique_aadhaar() -> str:
    """Generates a pseudo-random unique 12-digit Aadhaar number for testing."""
    # Start with 7, 8, or 9 to avoid collision with standard test constants
    prefix = random.choice(["7", "8"])
    suffix = "".join([str(random.randint(0, 9)) for _ in range(11)])
    return f"{prefix}{suffix}"


# ============================================================================
# 1. CRUD RECORD CREATION TESTS
# ============================================================================

def test_aadhaar_crud_create_success():
    """POST /records creates a record with surrogate UUID, masked number, and SHA-256 hash."""
    aadhaar_num = generate_unique_aadhaar()
    payload = {
        "aadhaar_number": aadhaar_num,
        "full_name": "Vikram Aditya Sharma",
        "dob": "1991-07-15",
        "gender": "MALE",
        "origin_state": "Rajasthan",
        "address": "45 Rajputana Road, Jaipur",
        "status": "ACTIVE"
    }

    res = client.post("/api/v1/aadhaar/records", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()

    assert "record_id" in data
    # record_id must be a valid UUID
    uuid_obj = uuid.UUID(data["record_id"])
    assert str(uuid_obj) == data["record_id"]

    # Verify zero raw Aadhaar exposed in response
    assert data["masked_aadhaar"] == f"XXXX XXXX {aadhaar_num[-4:]}"
    assert "aadhaar_number" not in data
    assert data["full_name"] == "Vikram Aditya Sharma"
    assert data["status"] == "ACTIVE"
    assert data["is_active"] is True
    assert data["origin_state"] == "Rajasthan"

    # Verify database state
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == data["record_id"]).first()
    assert rec is not None
    expected_hash = hashlib.sha256(aadhaar_num.encode("utf-8")).hexdigest()
    assert rec.aadhaar_hash == expected_hash
    assert rec.masked_aadhaar == f"XXXX XXXX {aadhaar_num[-4:]}"
    db.close()


def test_aadhaar_crud_create_duplicate_rejection():
    """POST /records rejects duplicate Aadhaar number with HTTP 409 Conflict."""
    aadhaar_num = generate_unique_aadhaar()
    payload = {
        "aadhaar_number": aadhaar_num,
        "full_name": "Pooja Hegde",
        "dob": "1995-03-22",
        "gender": "FEMALE",
        "origin_state": "Karnataka",
        "address": "12 Residency Road, Bengaluru"
    }

    # First creation succeeds
    r1 = client.post("/api/v1/aadhaar/records", json=payload)
    assert r1.status_code == 201

    # Second creation with same Aadhaar must fail with 409
    r2 = client.post("/api/v1/aadhaar/records", json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"].lower()


def test_aadhaar_crud_create_invalid_format_rejected():
    """POST /records rejects non-12-digit or non-numeric Aadhaar numbers with 422."""
    # 11 digits
    r1 = client.post("/api/v1/aadhaar/records", json={"aadhaar_number": "12345678901", "full_name": "Invalid Short"})
    assert r1.status_code == 422

    # 13 digits
    r2 = client.post("/api/v1/aadhaar/records", json={"aadhaar_number": "1234567890123", "full_name": "Invalid Long"})
    assert r2.status_code == 422

    # Contains alphabets
    r3 = client.post("/api/v1/aadhaar/records", json={"aadhaar_number": "1234ABCD5678", "full_name": "Invalid Chars"})
    assert r3.status_code == 422


# ============================================================================
# 2. URL PRIVACY BOUNDARY & RETRIEVAL TESTS
# ============================================================================

def test_aadhaar_crud_get_by_uuid_success():
    """GET /records/{record_id} successfully retrieves demographic record by UUID."""
    aadhaar_num = generate_unique_aadhaar()
    create_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": "Kavitha Ranganathan",
        "dob": "1988-11-04",
        "gender": "FEMALE",
        "origin_state": "Tamil Nadu",
        "address": "88 Marina Beach Road, Chennai"
    })
    rec_id = create_res.json()["record_id"]

    res = client.get(f"/api/v1/aadhaar/records/{rec_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["record_id"] == rec_id
    assert data["full_name"] == "Kavitha Ranganathan"
    assert data["masked_aadhaar"] == f"XXXX XXXX {aadhaar_num[-4:]}"
    assert "aadhaar_number" not in data


def test_aadhaar_crud_url_privacy_boundary_rejects_12_digit_path_param():
    """
    URL PRIVACY BOUNDARY SECURITY INVARIANT:
    Passing a raw 12-digit Aadhaar number in the URL path is strictly rejected with HTTP 400 Bad Request.
    """
    raw_number = "123456789012"

    # GET /records/{12-digit}
    r_get = client.get(f"/api/v1/aadhaar/records/{raw_number}")
    assert r_get.status_code in [400, 404]
    assert "raw 12-digit aadhaar numbers in url path parameters are strictly prohibited" in r_get.json()["detail"].lower()

    # PUT /records/{12-digit}
    r_put = client.put(f"/api/v1/aadhaar/records/{raw_number}", json={"full_name": "Attacker Name"})
    assert r_put.status_code == 400
    assert "raw 12-digit aadhaar numbers in url path parameters are strictly prohibited" in r_put.json()["detail"].lower()

    # PUT /records/{12-digit}/status
    r_status = client.put(f"/api/v1/aadhaar/records/{raw_number}/status", json={"status": "INACTIVE"})
    assert r_status.status_code == 400
    assert "raw 12-digit aadhaar numbers in url path parameters are strictly prohibited" in r_status.json()["detail"].lower()


def test_aadhaar_crud_get_nonexistent_uuid_returns_404():
    """GET /records/{record_id} with non-existent UUID returns HTTP 404 Not Found."""
    nonexistent = str(uuid.uuid4())
    res = client.get(f"/api/v1/aadhaar/records/{nonexistent}")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# ============================================================================
# 3. RECORD UPDATE & STATUS TRANSITION TESTS
# ============================================================================

def test_aadhaar_crud_update_demographics():
    """PUT /records/{record_id} updates demographic attributes while maintaining immutable UUID."""
    aadhaar_num = generate_unique_aadhaar()
    create_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": "Arjun Singhania",
        "dob": "1990-01-01",
        "gender": "MALE",
        "origin_state": "Delhi",
        "address": "10 Connaught Place, New Delhi",
        "status": "ACTIVE"
    })
    assert create_res.status_code == 201, create_res.text
    rec_id = create_res.json()["record_id"]

    update_payload = {
        "full_name": "Arjun Kumar Singhania",
        "address": "25 Barakhamba Road, New Delhi",
        "origin_state": "Delhi"
    }
    update_res = client.put(f"/api/v1/aadhaar/records/{rec_id}", json=update_payload)
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["record_id"] == rec_id
    assert data["full_name"] == "Arjun Kumar Singhania"
    assert data["address"] == "25 Barakhamba Road, New Delhi"


def test_aadhaar_crud_status_lifecycle():
    """PUT /records/{record_id}/status transitions between ACTIVE, INACTIVE, and SUSPENDED."""
    aadhaar_num = generate_unique_aadhaar()
    create_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": "Meera Patel",
        "dob": "1992-05-10",
        "gender": "FEMALE",
        "origin_state": "Gujarat",
        "address": "15 Ashram Road, Ahmedabad",
        "status": "ACTIVE"
    })
    assert create_res.status_code == 201, create_res.text
    rec_id = create_res.json()["record_id"]

    # 1. Transition to INACTIVE
    r_inact = client.put(f"/api/v1/aadhaar/records/{rec_id}/status", json={"status": "INACTIVE"})
    assert r_inact.status_code == 200
    assert r_inact.json()["status"] == "INACTIVE"
    assert r_inact.json()["is_active"] is False

    # 2. Transition to SUSPENDED
    r_susp = client.put(f"/api/v1/aadhaar/records/{rec_id}/status", json={"status": "SUSPENDED"})
    assert r_susp.status_code == 200
    assert r_susp.json()["status"] == "SUSPENDED"
    assert r_susp.json()["is_active"] is False

    # 3. Transition back to ACTIVE
    r_act = client.put(f"/api/v1/aadhaar/records/{rec_id}/status", json={"status": "ACTIVE"})
    assert r_act.status_code == 200
    assert r_act.json()["status"] == "ACTIVE"
    assert r_act.json()["is_active"] is True

    # 4. Invalid status transition rejected
    r_inv = client.put(f"/api/v1/aadhaar/records/{rec_id}/status", json={"status": "DISCARDED"})
    assert r_inv.status_code == 400


# ============================================================================
# 4. DIRECTORY SEARCH, FILTERING & PRIVACY
# ============================================================================

def test_aadhaar_crud_directory_listing_and_filtering():
    """GET /records supports search, filtering by status and state, and strictly returns masked numbers."""
    aadhaar_num1 = generate_unique_aadhaar()
    aadhaar_num2 = generate_unique_aadhaar()

    client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num1,
        "full_name": "Devendra Fadnavis SearchTest",
        "dob": "1970-07-22",
        "gender": "MALE",
        "origin_state": "Maharashtra",
        "address": "Mumbai",
        "status": "ACTIVE"
    })
    client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num2,
        "full_name": "Eknath Shinde SearchTest",
        "dob": "1964-02-09",
        "gender": "MALE",
        "origin_state": "Maharashtra",
        "address": "Thane",
        "status": "SUSPENDED"
    })

    # Search by full name
    r_search = client.get("/api/v1/aadhaar/records?query=SearchTest")
    assert r_search.status_code == 200
    items = r_search.json()
    assert len(items) >= 2

    # Filter by status = SUSPENDED
    r_susp = client.get("/api/v1/aadhaar/records?query=SearchTest&status=SUSPENDED")
    assert r_susp.status_code == 200
    susp_items = r_susp.json()
    assert all(item["status"] == "SUSPENDED" for item in susp_items)

    # Privacy verification: NO raw 12-digit number exists in listing
    for item in items:
        assert "aadhaar_number" not in item
        assert item["masked_aadhaar"].startswith("XXXX XXXX ")


# ============================================================================
# 5. MACHINE-TO-MACHINE (M2M) SERVICE AUTHENTICATION (/verify)
# ============================================================================

def test_aadhaar_m2m_verify_service_auth_missing_header():
    """POST /verify without X-PassKhadam-Service-Key returns HTTP 401 Unauthorized."""
    payload = {"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}
    res = client.post("/api/v1/aadhaar/verify", json=payload)
    assert res.status_code == 401
    assert "missing" in res.json()["detail"].lower()


def test_aadhaar_m2m_verify_service_auth_invalid_header():
    """POST /verify with invalid X-PassKhadam-Service-Key returns HTTP 401 Unauthorized."""
    payload = {"aadhaar_number": "123456784821", "full_name": "Mohammed Uzair"}
    headers = {"X-PassKhadam-Service-Key": "completely-invalid-attacker-key-999"}
    res = client.post("/api/v1/aadhaar/verify", json=payload, headers=headers)
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


def test_aadhaar_m2m_verify_success_with_service_key():
    """POST /verify with valid X-PassKhadam-Service-Key verifies identity and returns metadata."""
    aadhaar_num = generate_unique_aadhaar()
    client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": "Shubham Gill",
        "dob": "1999-09-08",
        "gender": "MALE",
        "origin_state": "Punjab",
        "status": "ACTIVE"
    })

    service_key = getattr(settings, "AADHAAR_SERVICE_KEY", "pk-mock-aadhaar-service-key-internal-2026")
    headers = {"X-PassKhadam-Service-Key": service_key}
    payload = {"aadhaar_number": aadhaar_num, "full_name": "Shubham Gill"}

    res = client.post("/api/v1/aadhaar/verify", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is True
    assert data["status"] == "VERIFIED"
    assert data["masked_aadhaar"] == f"XXXX XXXX {aadhaar_num[-4:]}"
    assert data["origin_state"] == "Punjab"
    assert "request_id" in data


def test_aadhaar_m2m_verify_rejected_on_suspended_or_inactive_record():
    """POST /verify rejects suspended and inactive records with appropriate reason."""
    aadhaar_num = generate_unique_aadhaar()
    create_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": "Suspended Citizen",
        "dob": "1985-04-12",
        "gender": "MALE",
        "origin_state": "Uttar Pradesh",
        "address": "Varanasi",
        "status": "SUSPENDED"
    })
    assert create_res.status_code == 201, create_res.text

    service_key = getattr(settings, "AADHAAR_SERVICE_KEY", "pk-mock-aadhaar-service-key-internal-2026")
    headers = {"X-PassKhadam-Service-Key": service_key}
    payload = {"aadhaar_number": aadhaar_num, "full_name": "Suspended Citizen"}

    res = client.post("/api/v1/aadhaar/verify", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is False
    assert data["status"] == "REJECTED"
    assert "suspended" in data["reason"].lower()


# ============================================================================
# 6. AUDIT LOGGING & DATABASE IMMUTABILITY TESTS
# ============================================================================

def test_aadhaar_audit_log_persistence_and_query():
    """Verification attempts persist in DBAadhaarAuditLog and are queryable via GET /logs."""
    aadhaar_num = generate_unique_aadhaar()
    create_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": "Audit Tracked Worker",
        "dob": "1993-08-19",
        "gender": "MALE",
        "origin_state": "Bihar",
        "address": "Patna",
        "status": "ACTIVE"
    })
    assert create_res.status_code == 201, create_res.text

    service_key = getattr(settings, "AADHAAR_SERVICE_KEY", "pk-mock-aadhaar-service-key-internal-2026")
    headers = {"X-PassKhadam-Service-Key": service_key}

    # Execute verification via /verify
    v_res = client.post("/api/v1/aadhaar/verify", json={"aadhaar_number": aadhaar_num, "full_name": "Audit Tracked Worker"}, headers=headers)
    assert v_res.status_code == 200
    req_id = v_res.json()["request_id"]

    # Query audit logs via GET /logs
    log_res = client.get(f"/api/v1/aadhaar/logs?masked_aadhaar=XXXX XXXX {aadhaar_num[-4:]}")
    assert log_res.status_code == 200
    logs = log_res.json()
    assert len(logs) >= 1

    matched_log = next((l for l in logs if l["request_id"] == req_id), None)
    assert matched_log is not None
    assert matched_log["name_matched"] is True
    assert matched_log["aadhaar_matched"] is True
    assert matched_log["result_code"] == "SUCCESS"
    assert matched_log["originating_service"] == "PassKhadam-Backend"
    assert matched_log["requester_role"] == "BACKEND_SERVICE"
    assert matched_log["response_time_ms"] > 0


def test_aadhaar_audit_log_db_immutability():
    """DBAadhaarAuditLog event listeners strictly prohibit UPDATE and DELETE operations."""
    db = SessionLocal()
    # Query latest audit log
    latest_log = db.query(DBAadhaarAuditLog).order_by(DBAadhaarAuditLog.id.desc()).first()
    assert latest_log is not None

    # Attempting to delete must raise ValueError / RuntimeError from event listener
    with pytest.raises(Exception) as exc_info:
        db.delete(latest_log)
        db.commit()
    err_str = str(exc_info.value).lower()
    assert "immutable" in err_str or "append-only" in err_str or "prohibited" in err_str
    db.rollback()

    # Attempting to update must raise ValueError / RuntimeError from event listener
    with pytest.raises(Exception) as exc_update:
        latest_log.result_code = "TAMPERED_RESULT"
        db.commit()
    upd_err = str(exc_update.value).lower()
    assert "immutable" in upd_err or "append-only" in upd_err or "prohibited" in upd_err
    db.rollback()
    db.close()


def test_aadhaar_dashboard_metrics():
    """GET /dashboard computes and returns live metrics from database records."""
    res = client.get("/api/v1/aadhaar/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "total_records" in data
    assert "active_records" in data
    assert "suspended_records" in data
    assert "inactive_records" in data
    assert "total_verifications" in data
    assert data["total_records"] >= data["active_records"]
