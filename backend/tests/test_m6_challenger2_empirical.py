"""
backend/tests/test_m6_challenger2_empirical.py
Empirical Adversarial Challenges & Verification Suite for Milestone 6:
1. P0-3 Single-Category Discontinuation & Employer Isolation
2. Government Officer Geographic Hierarchy Strict Invariants
3. Mock Aadhaar URL Privacy Boundary, Conflict Handling & Unmasked Data Leakage Prevention
4. Masked Aadhaar Formatting Conformance
5. VerificationStepper 11-Stage Contract Alignment
"""

import re
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.db import (
    get_db, DBUser, DBEmployerOrganization, DBCategoryAuthorizationRequest,
    DBGovernmentOfficer, DBGovernanceAuditLog, DBAadhaarRecord
)
from app.services.verification_engine import CommonVerificationEngine


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    """Obtains a valid JWT token for platform administrator."""
    res = client.post("/api/v1/auth/demo-login/admin")
    assert res.status_code == 200, f"Admin demo login failed: {res.text}"
    data = res.json()
    token = data.get("access_token")
    assert token, "No access_token returned"
    return token


# ============================================================================
# CHALLENGE 1: P0-3 SINGLE-CATEGORY DISCONTINUATION & EMPLOYER ISOLATION
# ============================================================================

class TestSingleCategoryDiscontinuationIsolation:
    """
    Stress-tests P0-3: Admin can discontinue one approved employer category
    without suspending the entire employer or affecting other active categories.
    Verifies mandatory reason enforcement and audit trail persistence.
    """

    def test_discontinue_category_mandatory_reason_enforcement(self, client, admin_token):
        """Rejects discontinuation without a valid reason (empty, missing, or < 3 chars)."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Setup test organization and category
        from app.models.db import SessionLocal
        db = SessionLocal()
        try:
            org = DBEmployerOrganization(
                name=f"Org-{uuid.uuid4().hex[:6]}",
                registration_ref_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
                org_address=f"0x{uuid.uuid4().hex[:40]}",
                official_email=f"employer_{uuid.uuid4().hex[:6]}@test.com",
                status="ACTIVE"
            )
            db.add(org)
            db.flush()

            cat = DBCategoryAuthorizationRequest(
                organization_id=org.id,
                category="Masonry & Concrete Works",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="APPROVED",
                is_active_scope=True
            )
            db.add(cat)
            db.commit()
            cat_id = cat.id
        finally:
            db.close()

        # 1. Missing reason field -> 422
        res1 = client.post(f"/api/v1/admin/discontinue-category/{cat_id}", json={}, headers=headers)
        assert res1.status_code == 422, f"Expected 422 for missing reason, got {res1.status_code}: {res1.text}"

        # 2. Too short reason (< 3 chars) -> 422
        res2 = client.post(f"/api/v1/admin/discontinue-category/{cat_id}", json={"reason": "no"}, headers=headers)
        assert res2.status_code == 422, f"Expected 422 for short reason, got {res2.status_code}: {res2.text}"

        # 3. Valid reason -> 200 OK
        res3 = client.post(
            f"/api/v1/admin/discontinue-category/{cat_id}",
            json={"reason": "Regulatory license expired for masonry division"},
            headers=headers
        )
        assert res3.status_code == 200, f"Expected 200 for valid discontinuation, got {res3.status_code}: {res3.text}"
        data3 = res3.json()
        assert data3["status"] == "DISCONTINUED"
        assert data3["is_active_scope"] is False

    def test_discontinuation_leaves_other_categories_and_employer_org_active(self, client, admin_token):
        """
        Critical P0-3 isolation test:
        An employer has Category A and Category B.
        Discontinuing Category A MUST NOT suspend Category B or the Employer Org.
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        from app.models.db import SessionLocal
        db = SessionLocal()
        try:
            org = DBEmployerOrganization(
                name="Mega Builders Ltd",
                registration_ref_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
                org_address=f"0x{uuid.uuid4().hex[:40]}",
                official_email=f"megabuild_{uuid.uuid4().hex[:6]}@test.com",
                status="ACTIVE"
            )
            db.add(org)
            db.flush()

            cat_a = DBCategoryAuthorizationRequest(
                organization_id=org.id,
                category="Electrical Installation",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="APPROVED",
                is_active_scope=True
            )
            cat_b = DBCategoryAuthorizationRequest(
                organization_id=org.id,
                category="Plumbing & Sanitation",
                skill_level="Semi-Skilled",
                nature_of_employment="Permanent",
                status="APPROVED",
                is_active_scope=True
            )
            db.add_all([cat_a, cat_b])
            db.commit()
            org_id = org.id
            cat_a_id = cat_a.id
            cat_b_id = cat_b.id
        finally:
            db.close()

        # Discontinue Category A
        res = client.post(
            f"/api/v1/admin/discontinue-category/{cat_a_id}",
            json={"reason": "Safety audit failure in electrical equipment"},
            headers=headers
        )
        assert res.status_code == 200, f"Failed discontinuation: {res.text}"

        # Re-check database state
        db = SessionLocal()
        try:
            rechecked_org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
            rechecked_a = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat_a_id).first()
            rechecked_b = db.query(DBCategoryAuthorizationRequest).filter(DBCategoryAuthorizationRequest.id == cat_b_id).first()

            # P0-3 Assertions:
            assert rechecked_a.status == "DISCONTINUED"
            assert rechecked_a.is_active_scope is False
            assert rechecked_a.review_reason == "Safety audit failure in electrical equipment"

            # Category B must remain APPROVED and active
            assert rechecked_b.status == "APPROVED"
            assert rechecked_b.is_active_scope is True

            # Employer Org must remain ACTIVE
            assert rechecked_org.status == "ACTIVE"

            # Governance Audit Log must record discontinuation
            audit_log = db.query(DBGovernanceAuditLog).filter(
                DBGovernanceAuditLog.target_type == "CATEGORY_AUTHORIZATION_REQUEST",
                DBGovernanceAuditLog.target_id == str(cat_a_id),
                DBGovernanceAuditLog.action == "DISCONTINUE_CATEGORY"
            ).first()
            assert audit_log is not None, "Missing governance audit log entry for discontinuation"
            assert audit_log.previous_state == "APPROVED"
            assert audit_log.new_state == "DISCONTINUED"
            assert audit_log.reason == "Safety audit failure in electrical equipment"
        finally:
            db.close()

    def test_cannot_discontinue_non_approved_or_already_discontinued_category(self, client, admin_token):
        """Attempting to discontinue pending or discontinued categories must return 400 Bad Request."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        from app.models.db import SessionLocal
        db = SessionLocal()
        try:
            cat = DBCategoryAuthorizationRequest(
                organization_id=1,
                category="Heavy Machinery Operation",
                status="PENDING",
                is_active_scope=False
            )
            db.add(cat)
            db.commit()
            cat_id = cat.id
        finally:
            db.close()

        res = client.post(
            f"/api/v1/admin/discontinue-category/{cat_id}",
            json={"reason": "premature discontinuation"},
            headers=headers
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Only approved categories can be discontinued" in res.json().get("detail", "")


# ============================================================================
# CHALLENGE 2: GOVERNMENT OFFICER GEOGRAPHIC HIERARCHY RULES
# ============================================================================

class TestGovernmentOfficerGeographicHierarchy:
    """
    Stress-tests geographic jurisdiction invariants:
    - NATIONAL: state/district/block must be empty.
    - STATE: state is mandatory; district/block must be empty.
    - DISTRICT: state and district are mandatory; block must be empty.
    - BLOCK: state, district, and block are mandatory.
    """

    def test_national_authority_rejects_state_district_or_block(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. NATIONAL with state -> 400
        payload_with_state = {
            "full_name": "National Officer A",
            "official_email": f"nat_officer_{uuid.uuid4().hex[:6]}@labour.gov.in",
            "department": "Ministry of Labour",
            "designation": "Director General",
            "authority_level": "NATIONAL",
            "state": "Maharashtra"
        }
        res1 = client.post("/api/v1/admin/government-officers", json=payload_with_state, headers=headers)
        assert res1.status_code == 400
        assert "NATIONAL authority level cannot have state, district, or block" in res1.json()["detail"]

        # 2. NATIONAL with no geo -> 200/201 Success
        payload_valid_nat = {
            "full_name": "National Officer Valid",
            "official_email": f"nat_valid_{uuid.uuid4().hex[:6]}@labour.gov.in",
            "department": "Ministry of Labour",
            "designation": "Director General",
            "authority_level": "NATIONAL"
        }
        res2 = client.post("/api/v1/admin/government-officers", json=payload_valid_nat, headers=headers)
        assert res2.status_code == 200 or res2.status_code == 201
        data = res2.json()
        assert data["authority_level"] == "NATIONAL"
        assert data["state"] is None
        assert data["district"] is None
        assert data["block"] is None

    def test_state_authority_enforces_state_only(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. STATE without state -> 400
        payload_no_state = {
            "full_name": "State Officer Missing State",
            "official_email": f"state_no_{uuid.uuid4().hex[:6]}@state.gov.in",
            "department": "State Labour Dept",
            "designation": "Labour Secretary",
            "authority_level": "STATE"
        }
        res1 = client.post("/api/v1/admin/government-officers", json=payload_no_state, headers=headers)
        assert res1.status_code == 400
        assert "State is mandatory for STATE authority level" in res1.json()["detail"]

        # 2. STATE with district -> 400
        payload_with_district = {
            "full_name": "State Officer With District",
            "official_email": f"state_dist_{uuid.uuid4().hex[:6]}@state.gov.in",
            "department": "State Labour Dept",
            "designation": "Labour Secretary",
            "authority_level": "STATE",
            "state": "Bihar",
            "district": "Patna"
        }
        res2 = client.post("/api/v1/admin/government-officers", json=payload_with_district, headers=headers)
        assert res2.status_code == 400
        assert "STATE authority level cannot have district or block" in res2.json()["detail"]

        # 3. Valid STATE -> 200/201
        payload_valid_state = {
            "full_name": "State Officer Valid",
            "official_email": f"state_valid_{uuid.uuid4().hex[:6]}@state.gov.in",
            "department": "State Labour Dept",
            "designation": "Labour Secretary",
            "authority_level": "STATE",
            "state": "Bihar"
        }
        res3 = client.post("/api/v1/admin/government-officers", json=payload_valid_state, headers=headers)
        assert res3.status_code in [200, 201]
        data = res3.json()
        assert data["state"] == "Bihar"
        assert data["district"] is None
        assert data["block"] is None

    def test_district_authority_enforces_state_and_district_only(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. DISTRICT without district -> 400
        payload_no_dist = {
            "full_name": "District Officer Missing District",
            "official_email": f"dist_no_{uuid.uuid4().hex[:6]}@dist.gov.in",
            "department": "District Office",
            "designation": "District Magistrate",
            "authority_level": "DISTRICT",
            "state": "Karnataka"
        }
        res1 = client.post("/api/v1/admin/government-officers", json=payload_no_dist, headers=headers)
        assert res1.status_code == 400
        assert "District is mandatory for DISTRICT authority level" in res1.json()["detail"]

        # 2. DISTRICT with block -> 400
        payload_with_block = {
            "full_name": "District Officer With Block",
            "official_email": f"dist_blk_{uuid.uuid4().hex[:6]}@dist.gov.in",
            "department": "District Office",
            "designation": "District Magistrate",
            "authority_level": "DISTRICT",
            "state": "Karnataka",
            "district": "Bengaluru Urban",
            "block": "Anekal"
        }
        res2 = client.post("/api/v1/admin/government-officers", json=payload_with_block, headers=headers)
        assert res2.status_code == 400
        assert "DISTRICT authority level cannot have block assigned" in res2.json()["detail"]

        # 3. Valid DISTRICT -> 200/201
        payload_valid_dist = {
            "full_name": "District Officer Valid",
            "official_email": f"dist_valid_{uuid.uuid4().hex[:6]}@dist.gov.in",
            "department": "District Office",
            "designation": "District Magistrate",
            "authority_level": "DISTRICT",
            "state": "Karnataka",
            "district": "Bengaluru Urban"
        }
        res3 = client.post("/api/v1/admin/government-officers", json=payload_valid_dist, headers=headers)
        assert res3.status_code in [200, 201]
        data = res3.json()
        assert data["state"] == "Karnataka"
        assert data["district"] == "Bengaluru Urban"
        assert data["block"] is None

    def test_block_authority_requires_state_district_and_block(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. BLOCK without block -> 400
        payload_no_block = {
            "full_name": "Block Officer Missing Block",
            "official_email": f"blk_no_{uuid.uuid4().hex[:6]}@block.gov.in",
            "department": "Panchayat Office",
            "designation": "Block Development Officer",
            "authority_level": "BLOCK",
            "state": "Uttar Pradesh",
            "district": "Varanasi"
        }
        res1 = client.post("/api/v1/admin/government-officers", json=payload_no_block, headers=headers)
        assert res1.status_code == 400
        assert "Block/Local is mandatory for BLOCK authority level" in res1.json()["detail"]

        # 2. Valid BLOCK -> 200/201
        payload_valid_blk = {
            "full_name": "Block Officer Valid",
            "official_email": f"blk_valid_{uuid.uuid4().hex[:6]}@block.gov.in",
            "department": "Panchayat Office",
            "designation": "Block Development Officer",
            "authority_level": "BLOCK",
            "state": "Uttar Pradesh",
            "district": "Varanasi",
            "block": "Kashi Vidya Pith"
        }
        res2 = client.post("/api/v1/admin/government-officers", json=payload_valid_blk, headers=headers)
        assert res2.status_code in [200, 201]
        data = res2.json()
        assert data["state"] == "Uttar Pradesh"
        assert data["district"] == "Varanasi"
        assert data["block"] == "Kashi Vidya Pith"


# ============================================================================
# CHALLENGE 3: MOCK AADHAAR URL PRIVACY BOUNDARY & CONFLICT HANDLING
# ============================================================================

class TestMockAadhaarUrlPrivacyBoundary:
    """
    Stress-tests Mock Aadhaar endpoints:
    - PUT /api/v1/aadhaar/records/{record_id} strictly uses UUID.
    - Raw 12-digit Aadhaar numbers in path parameters MUST be rejected.
    - 409 Conflict handled on duplicate 12-digit Aadhaar.
    - Returned records list and logs must never expose raw 12-digit Aadhaar numbers.
    """

    def test_raw_12_digit_aadhaar_in_path_strictly_rejected(self, client):
        raw_aadhaar = "998877665544"

        # 1. GET /api/v1/aadhaar/records/{raw_aadhaar} -> 404 (Privacy Boundary error)
        res_get = client.get(f"/api/v1/aadhaar/records/{raw_aadhaar}")
        assert res_get.status_code == 404
        assert "Raw 12-digit Aadhaar numbers in URL path parameters are strictly prohibited" in res_get.json()["detail"]

        # 2. PUT /api/v1/aadhaar/records/{raw_aadhaar} -> 400 (Privacy Boundary error)
        res_put = client.put(f"/api/v1/aadhaar/records/{raw_aadhaar}", json={"full_name": "Hacked Name"})
        assert res_put.status_code == 400
        assert "Raw 12-digit Aadhaar numbers in URL path parameters are strictly prohibited" in res_put.json()["detail"]

        # 3. PUT /api/v1/aadhaar/records/{raw_aadhaar}/status -> 400 (Privacy Boundary error)
        res_status = client.put(f"/api/v1/aadhaar/records/{raw_aadhaar}/status", json={"status": "SUSPENDED"})
        assert res_status.status_code == 400
        assert "Raw 12-digit Aadhaar numbers in URL path parameters are strictly prohibited" in res_status.json()["detail"]

    def test_aadhaar_crud_uses_uuid_and_handles_409_conflict(self, client):
        aadhaar_num = f"55{uuid.uuid4().int % 10000000000:010d}"

        # 1. Create Record
        create_payload = {
            "aadhaar_number": aadhaar_num,
            "full_name": "Adversarial Test Citizen",
            "dob": "1992-04-12",
            "gender": "Female",
            "origin_state": "Odisha",
            "address": "Plot 42, Ganjam, Odisha",
            "status": "ACTIVE"
        }
        res_create = client.post("/api/v1/aadhaar/records", json=create_payload)
        assert res_create.status_code == 201, f"Failed creation: {res_create.text}"
        data_create = res_create.json()
        rec_id = data_create["record_id"]

        # Verify UUID structure
        uuid.UUID(rec_id)  # Throws ValueError if not valid UUID
        assert "aadhaar_number" not in data_create or data_create.get("aadhaar_number") is None
        assert data_create["masked_aadhaar"] == f"XXXX XXXX {aadhaar_num[-4:]}"

        # 2. Re-create same 12-digit Aadhaar -> must return 409 Conflict
        res_dup = client.post("/api/v1/aadhaar/records", json=create_payload)
        assert res_dup.status_code == 409
        assert "already exists" in res_dup.json()["detail"].lower()

        # 3. Update Record using surrogate UUID
        res_update = client.put(
            f"/api/v1/aadhaar/records/{rec_id}",
            json={"full_name": "Adversarial Citizen Updated", "origin_state": "Jharkhand"}
        )
        assert res_update.status_code == 200
        data_update = res_update.json()
        assert data_update["full_name"] == "Adversarial Citizen Updated"
        assert data_update["origin_state"] == "Jharkhand"
        assert data_update["record_id"] == rec_id

        # 4. Status Transition using surrogate UUID
        res_status = client.put(f"/api/v1/aadhaar/records/{rec_id}/status", json={"status": "SUSPENDED"})
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "SUSPENDED"

    def test_list_records_and_logs_never_leak_raw_aadhaar(self, client):
        """Verifies GET /api/v1/aadhaar/records and GET /api/v1/aadhaar/logs contain zero 12-digit plaintext numbers."""
        res_records = client.get("/api/v1/aadhaar/records?limit=100")
        assert res_records.status_code == 200
        records = res_records.json()
        for r in records:
            # Must not contain plaintext aadhaar_number field
            assert "aadhaar_number" not in r or r.get("aadhaar_number") is None
            # Masked Aadhaar must contain 'X'
            if "masked_aadhaar" in r and r["masked_aadhaar"]:
                assert "X" in r["masked_aadhaar"]
            # Ensure masked_aadhaar itself is never a raw 12-digit number
            assert not re.match(r"^\d{12}$", str(r.get("masked_aadhaar", "")))
            for field in ["full_name", "origin_state", "address", "masked_aadhaar"]:
                val = str(r.get(field, ""))
                assert not re.search(r"\b[2-9]\d{11}\b", val), f"Plaintext Aadhaar leaked in record field {field}: {val}"

        res_logs = client.get("/api/v1/aadhaar/logs?limit=100")
        assert res_logs.status_code == 200
        logs = res_logs.json()
        for l in logs:
            assert "aadhaar_number" not in l or l.get("aadhaar_number") is None
            if "masked_aadhaar" in l and l["masked_aadhaar"]:
                assert "X" in l["masked_aadhaar"]
            assert not re.match(r"^\d{12}$", str(l.get("masked_aadhaar", "")))
            for field in ["details", "description", "action", "masked_aadhaar"]:
                val = str(l.get(field, ""))
                assert not re.search(r"\b[2-9]\d{11}\b", val), f"Plaintext Aadhaar leaked in log field {field}: {val}"


# ============================================================================
# CHALLENGE 4: MASKED AADHAAR FORMAT CONFORMANCE (XXXX-XXXX-1234)
# ============================================================================

class TestMaskedAadhaarFormatConformance:
    """
    Empirically verifies the masking transformation:
    Any raw 12-digit number, space-separated, dash-separated, or pre-masked string
    converts deterministically to XXXX-XXXX-1234.
    """

    @staticmethod
    def format_masked_aadhaar_py(raw):
        """Python mirror of frontend formatMaskedAadhaar() in api.js."""
        if not raw:
            return ""
        s = str(raw).strip()
        clean = re.sub(r"[\s-]", "", s)
        if len(clean) == 12:
            return f"XXXX-XXXX-{clean[-4:]}"
        m = re.search(r"(\d{4})$", s)
        if m:
            return f"XXXX-XXXX-{m.group(1)}"
        return s

    def test_various_inputs_conform_to_four_dash_four_dash_four(self):
        cases = [
            ("123456784821", "XXXX-XXXX-4821"),
            ("1234 5678 4821", "XXXX-XXXX-4821"),
            ("1234-5678-4821", "XXXX-XXXX-4821"),
            ("XXXX XXXX 4821", "XXXX-XXXX-4821"),
            ("XXXX-XXXX-4821", "XXXX-XXXX-4821"),
            ("XXXX XXXX 9999", "XXXX-XXXX-9999"),
            ("", ""),
            (None, ""),
        ]
        for inp, expected in cases:
            out = self.format_masked_aadhaar_py(inp)
            assert out == expected, f"Input '{inp}' formatted to '{out}', expected '{expected}'"


# ============================================================================
# CHALLENGE 5: VERIFICATION STEPPER 11-STAGE EXACT SEQUENCE MATCH
# ============================================================================

class TestVerificationStepperAlignment:
    """
    Verifies that the 11 stages defined in VerificationStepper.jsx exactly match
    the 11 steps implemented in backend CommonVerificationEngine.
    """

    EXPECTED_STAGES = [
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
        (11, "Deferred Atomic Nonce Consumption"),
    ]

    def test_backend_verification_engine_docstring_and_execution_sequence(self):
        import inspect
        from app.services.verification_engine import CommonVerificationEngine

        engine = CommonVerificationEngine()
        src = inspect.getsource(engine.verify_uploaded_presentation)

        for step_num, step_name in self.EXPECTED_STAGES:
            # Check step header comment or audit_steps name exists in verify_uploaded_presentation
            assert f"STEP {step_num}" in src or f'"step": {step_num}' in src, f"Step {step_num} missing from verification_engine.py"
            assert step_name in src, f"Step {step_num} name '{step_name}' missing from verification_engine.py"

    def test_frontend_verification_stepper_jsx_contains_all_11_stages(self):
        stepper_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "common" / "VerificationStepper.jsx"
        if not stepper_path.exists():
            stepper_path = Path("e:/AI/projects/PassKhadam/PassKhadam_Exportable/frontend/src/components/common/VerificationStepper.jsx")
        with open(stepper_path, "r", encoding="utf-8") as f:
            content = f.read()

        for step_num, step_name in self.EXPECTED_STAGES:
            assert f"step: {step_num}" in content, f"Step {step_num} missing in VerificationStepper.jsx"
            assert f'name: "{step_name}"' in content, f"Stage '{step_name}' missing in VerificationStepper.jsx"
