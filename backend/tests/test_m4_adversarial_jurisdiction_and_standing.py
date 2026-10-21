"""
backend/tests/test_m4_adversarial_jurisdiction_and_standing.py
Milestone 4 (R5) Adversarial Challenge Test Suite:
4-Tier Jurisdiction Hierarchy & Strict Standing Enforcement
=============================================================
Stress-tests:
1. 4-Tier Jurisdiction Hierarchy:
   - NATIONAL officer verifies across all states (Maharashtra, Karnataka, Delhi, Bihar).
   - STATE officer verifies same state; out-of-state worker rejected with HTTP 403 JURISDICTION_MISMATCH
     (unless officer has CROSS_STATE_VERIFICATION).
   - DISTRICT officer verifies same district; out-of-district worker rejected with HTTP 403.
   - BLOCK officer verifies same block; out-of-block worker rejected with HTTP 403.
2. Strict Permission & Standing Enforcement:
   - Officer with permissions ["BENEFIT_DISBURSEMENT"] (missing "WORKER_VERIFICATION"): assert HTTP 403 PERMISSION_DENIED.
   - Officer with status="SUSPENDED": assert HTTP 403 OFFICER_SUSPENDED.
   - Officer with inactive linked DBUser: assert HTTP 403 ACCOUNT_INACTIVE.
   - Unlinked government user: assert HTTP 404 OFFICER_NOT_FOUND.
"""

import io
import os
import sys
import json
import uuid
import hashlib
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBGovernmentOfficer,
    DBWorkerProfile,
    DBConsumedPresentationNonce
)
from app.core.auth import create_test_firebase_jwt
from app.services.verification_engine import (
    verification_engine,
    VerificationEngineError,
    VerificationErrorCode
)

client = TestClient(app)


# =============================================================================
# Helpers
# =============================================================================

def create_challenger_officer(
    status: str = "ACTIVE",
    authority_level: str = "STATE",
    state: str = "Maharashtra",
    district: str = None,
    block: str = None,
    permissions: list = None,
    user_status: str = "ACTIVE",
    user_is_active: bool = True
) -> tuple[int, int, str]:
    """Creates an isolated government officer and user in SQLite."""
    db = SessionLocal()
    u_uid = f"uid_gov_adv_{uuid.uuid4().hex[:8]}"
    email = f"officer_adv_{uuid.uuid4().hex[:6]}@gov.in"
    name = f"Adv Officer {uuid.uuid4().hex[:4]}"

    user = DBUser(
        firebase_uid=u_uid,
        full_name=name,
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="GOVERNMENT",
        status=user_status,
        is_active=user_is_active
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    officer = DBGovernmentOfficer(
        user_id=user.id,
        full_name=name,
        officer_name=name,
        officer_reference_id=f"GOV-ADV-{uuid.uuid4().hex[:8].upper()}",
        official_email=email,
        phone="+919876543210",
        authority_level=authority_level,
        state=state,
        district=district,
        block=block,
        department="Labour Welfare Department",
        designation="Welfare Commissioner",
        status=status,
        permissions_json=json.dumps(permissions if permissions is not None else ["WORKER_VERIFICATION"]),
        benefit_permissions_json=json.dumps(["SCHEME_001"])
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)

    user_id = user.id
    officer_id = officer.id
    db.close()

    token = create_test_firebase_jwt(uid=u_uid, email=email, name=name)
    return user_id, officer_id, token


def create_worker_qr_for_location(
    worker_state: str = "Maharashtra",
    district: str = "Pune",
    block: str = "Haveli"
) -> tuple[str, str, bytes]:
    """Sets up an anchored active worker at a specific location and generates valid presentation QR."""
    db = SessionLocal()
    worker_name = f"Worker_{uuid.uuid4().hex[:6]}"
    uid = f"uid_worker_{uuid.uuid4().hex[:8]}"
    email = f"worker_{uuid.uuid4().hex[:6]}@domain.org"
    pw_hash = hashlib.sha256("password123".encode("utf-8")).hexdigest()
    full_address = f"Locality 1, Block {block}, District {district}, {worker_state}"

    user = DBUser(
        firebase_uid=uid,
        full_name=worker_name,
        email=email,
        phone="+919876543210",
        password_hash=pw_hash,
        role="WORKER",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = DBWorkerProfile(
        user_id=user.id,
        full_name=worker_name,
        origin_state=worker_state,
        current_state=worker_state,
        address=full_address,
        worker_category="Construction",
        skills_json=json.dumps(["Mason", "Electrical"]),
        did_state="NOT_STARTED"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=worker_name)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed Mock Aadhaar
    aadhaar_num = f"99{uuid.uuid4().int % 10000000000:010d}"
    seed_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name,
        "dob": "1992-07-20",
        "gender": "FEMALE",
        "origin_state": worker_state,
        "address": full_address,
        "status": "ACTIVE"
    })
    assert seed_res.status_code == 201, seed_res.text

    # Verify Aadhaar
    v_res = client.post("/api/v1/worker/verify-aadhaar/me", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name
    }, headers=headers)
    assert v_res.status_code == 200, v_res.text
    worker_did = v_res.json()["did"]

    # Generate QR presentation
    png_bytes, _ = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={
            "full_name": worker_name,
            "origin_state": worker_state,
            "current_state": worker_state,
            "district": district,
            "block": block,
            "address": full_address
        },
        validity_seconds=300
    )
    db.close()
    return worker_did, worker_name, png_bytes


# =============================================================================
# PART 1: 4-Tier Jurisdiction Hierarchy Tests
# =============================================================================

class TestJurisdictionHierarchy:

    def test_national_officer_verifies_across_all_states(self):
        """
        1.1 NATIONAL officer verifies across all states:
        - Maharashtra
        - Karnataka
        - Delhi
        - Bihar
        All succeed with HTTP 200 OK.
        """
        _, officer_id, token = create_challenger_officer(
            status="ACTIVE",
            authority_level="NATIONAL",
            state=None,
            district=None,
            block=None,
            permissions=["WORKER_VERIFICATION"]
        )
        headers = {"Authorization": f"Bearer {token}"}

        states_to_test = ["Maharashtra", "Karnataka", "Delhi", "Bihar"]
        for test_state in states_to_test:
            worker_did, _, png_bytes = create_worker_qr_for_location(
                worker_state=test_state,
                district="Capital",
                block="Sector-1"
            )
            files = {"file": ("worker_qr.png", io.BytesIO(png_bytes), "image/png")}
            res = client.post("/api/v1/government/verify-worker", files=files, headers=headers)
            assert res.status_code == 200, f"NATIONAL officer failed on state {test_state}: {res.text}"
            assert res.json()["verified"] is True
            assert res.json()["worker_did"] == worker_did

    def test_state_officer_same_state_vs_out_of_state(self):
        """
        1.2 STATE officer in Maharashtra:
        - Same state (Maharashtra): succeeds (HTTP 200).
        - Out-of-state (Karnataka) without CROSS_STATE_VERIFICATION: HTTP 403 JURISDICTION_MISMATCH.
        - Out-of-state (Karnataka) WITH CROSS_STATE_VERIFICATION: HTTP 200.
        """
        # Officer without CROSS_STATE_VERIFICATION
        _, _, token_strict = create_challenger_officer(
            status="ACTIVE",
            authority_level="STATE",
            state="Maharashtra",
            permissions=["WORKER_VERIFICATION"]
        )
        headers_strict = {"Authorization": f"Bearer {token_strict}"}

        # Same state: Maharashtra -> succeeds
        _, _, mh_qr = create_worker_qr_for_location(worker_state="Maharashtra")
        res_same = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(mh_qr), "image/png")},
            headers=headers_strict
        )
        assert res_same.status_code == 200, res_same.text
        assert res_same.json()["verified"] is True

        # Out-of-state: Karnataka -> 403
        _, _, ka_qr = create_worker_qr_for_location(worker_state="Karnataka")
        res_out = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(ka_qr), "image/png")},
            headers=headers_strict
        )
        assert res_out.status_code == 403, res_out.text
        assert "jurisdiction" in res_out.text.lower() or "cover" in res_out.text.lower()

        # Officer WITH CROSS_STATE_VERIFICATION -> succeeds on Karnataka
        _, _, token_cross = create_challenger_officer(
            status="ACTIVE",
            authority_level="STATE",
            state="Maharashtra",
            permissions=["WORKER_VERIFICATION", "CROSS_STATE_VERIFICATION"]
        )
        headers_cross = {"Authorization": f"Bearer {token_cross}"}
        _, _, ka_qr_2 = create_worker_qr_for_location(worker_state="Karnataka")
        res_cross = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(ka_qr_2), "image/png")},
            headers=headers_cross
        )
        assert res_cross.status_code == 200, res_cross.text
        assert res_cross.json()["verified"] is True

    def test_district_officer_same_district_vs_out_of_district(self):
        """
        1.3 DISTRICT officer in (Maharashtra, Pune):
        - Same district (Maharashtra, Pune): succeeds (HTTP 200).
        - Out-of-district (Maharashtra, Nagpur): rejected with HTTP 403.
        - Out-of-state (Karnataka, Bangalore): rejected with HTTP 403.
        """
        _, _, token_dist = create_challenger_officer(
            status="ACTIVE",
            authority_level="DISTRICT",
            state="Maharashtra",
            district="Pune",
            permissions=["WORKER_VERIFICATION"]
        )
        headers_dist = {"Authorization": f"Bearer {token_dist}"}

        # Same district: Maharashtra, Pune -> 200
        _, _, pune_qr = create_worker_qr_for_location(
            worker_state="Maharashtra",
            district="Pune",
            block="Haveli"
        )
        res_pune = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(pune_qr), "image/png")},
            headers=headers_dist
        )
        assert res_pune.status_code == 200, res_pune.text

        # Different district: Maharashtra, Nagpur -> 403
        _, _, nagpur_qr = create_worker_qr_for_location(
            worker_state="Maharashtra",
            district="Nagpur",
            block="Nagpur-Urban"
        )
        res_nagpur = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(nagpur_qr), "image/png")},
            headers=headers_dist
        )
        assert res_nagpur.status_code == 403, res_nagpur.text
        assert "jurisdiction" in res_nagpur.text.lower() or "cover" in res_nagpur.text.lower()

        # Different state: Karnataka -> 403
        _, _, blr_qr = create_worker_qr_for_location(
            worker_state="Karnataka",
            district="Bangalore",
            block="East"
        )
        res_blr = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(blr_qr), "image/png")},
            headers=headers_dist
        )
        assert res_blr.status_code == 403, res_blr.text

    def test_block_officer_same_block_vs_out_of_block(self):
        """
        1.4 BLOCK officer in (Maharashtra, Pune, Haveli):
        - Same block (Maharashtra, Pune, Haveli): succeeds (HTTP 200).
        - Out-of-block (Maharashtra, Pune, Baramati): rejected with HTTP 403.
        - Out-of-district (Maharashtra, Thane, Kalyan): rejected with HTTP 403.
        """
        _, _, token_block = create_challenger_officer(
            status="ACTIVE",
            authority_level="BLOCK",
            state="Maharashtra",
            district="Pune",
            block="Haveli",
            permissions=["WORKER_VERIFICATION"]
        )
        headers_block = {"Authorization": f"Bearer {token_block}"}

        # Same block: Haveli -> 200
        _, _, haveli_qr = create_worker_qr_for_location(
            worker_state="Maharashtra",
            district="Pune",
            block="Haveli"
        )
        res_haveli = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(haveli_qr), "image/png")},
            headers=headers_block
        )
        assert res_haveli.status_code == 200, res_haveli.text

        # Different block: Baramati -> 403
        _, _, baramati_qr = create_worker_qr_for_location(
            worker_state="Maharashtra",
            district="Pune",
            block="Baramati"
        )
        res_baramati = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(baramati_qr), "image/png")},
            headers=headers_block
        )
        assert res_baramati.status_code == 403, res_baramati.text
        assert "jurisdiction" in res_baramati.text.lower() or "cover" in res_baramati.text.lower()


# =============================================================================
# PART 2: Strict Permission & Standing Enforcement Tests
# =============================================================================

class TestPermissionAndStandingEnforcement:

    def test_officer_missing_worker_verification_permission_returns_403(self):
        """
        2.1 Officer with permissions=["BENEFIT_DISBURSEMENT"] (missing "WORKER_VERIFICATION"):
        Assert HTTP 403 PERMISSION_DENIED.
        """
        _, _, token_no_perm = create_challenger_officer(
            status="ACTIVE",
            authority_level="STATE",
            state="Maharashtra",
            permissions=["BENEFIT_DISBURSEMENT"]
        )
        _, _, png_bytes = create_worker_qr_for_location(worker_state="Maharashtra")
        res = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(png_bytes), "image/png")},
            headers={"Authorization": f"Bearer {token_no_perm}"}
        )
        assert res.status_code == 403, res.text
        assert "permission" in res.text.lower() or "WORKER_VERIFICATION" in res.text

    def test_suspended_officer_returns_403_officer_suspended(self):
        """
        2.2 Officer with status="SUSPENDED":
        Assert HTTP 403 OFFICER_SUSPENDED.
        """
        _, _, token_susp = create_challenger_officer(
            status="SUSPENDED",
            authority_level="STATE",
            state="Maharashtra",
            permissions=["WORKER_VERIFICATION"]
        )
        _, _, png_bytes = create_worker_qr_for_location(worker_state="Maharashtra")
        res = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(png_bytes), "image/png")},
            headers={"Authorization": f"Bearer {token_susp}"}
        )
        assert res.status_code == 403, res.text
        assert "suspended" in res.text.lower() or "inactive" in res.text.lower()

    def test_inactive_linked_user_returns_403_account_inactive(self):
        """
        2.3 Officer with ACTIVE standing, but inactive linked DBUser:
        Assert HTTP 403 ACCOUNT_INACTIVE.
        """
        # Test A: user_status="INACTIVE"
        _, _, token_inactive_user = create_challenger_officer(
            status="ACTIVE",
            authority_level="STATE",
            state="Maharashtra",
            permissions=["WORKER_VERIFICATION"],
            user_status="INACTIVE",
            user_is_active=True
        )
        _, _, png_bytes_a = create_worker_qr_for_location(worker_state="Maharashtra")
        res_a = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(png_bytes_a), "image/png")},
            headers={"Authorization": f"Bearer {token_inactive_user}"}
        )
        assert res_a.status_code == 403, res_a.text
        assert "inactive" in res_a.text.lower() or "suspended" in res_a.text.lower()

        # Test B: user_is_active=False
        _, _, token_deactivated = create_challenger_officer(
            status="ACTIVE",
            authority_level="STATE",
            state="Maharashtra",
            permissions=["WORKER_VERIFICATION"],
            user_status="ACTIVE",
            user_is_active=False
        )
        _, _, png_bytes_b = create_worker_qr_for_location(worker_state="Maharashtra")
        res_b = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(png_bytes_b), "image/png")},
            headers={"Authorization": f"Bearer {token_deactivated}"}
        )
        assert res_b.status_code == 403, res_b.text
        assert "inactive" in res_b.text.lower() or "suspended" in res_b.text.lower()

    def test_unlinked_government_user_returns_404_officer_not_found(self):
        """
        2.4 Unlinked government user with no DBGovernmentOfficer:
        Assert HTTP 404 OFFICER_NOT_FOUND.
        """
        db = SessionLocal()
        u_uid = f"uid_gov_orphan_{uuid.uuid4().hex[:6]}"
        email = f"orphan_{uuid.uuid4().hex[:6]}@gov.in"
        orphan_user = DBUser(
            firebase_uid=u_uid,
            full_name="Orphan Gov User",
            email=email,
            phone="+919876543210",
            password_hash="hash",
            role="GOVERNMENT",
            status="ACTIVE"
        )
        db.add(orphan_user)
        db.commit()
        db.close()

        token_orphan = create_test_firebase_jwt(uid=u_uid, email=email, name="Orphan Gov User")
        _, _, png_bytes = create_worker_qr_for_location(worker_state="Maharashtra")
        res = client.post(
            "/api/v1/government/verify-worker",
            files={"file": ("qr.png", io.BytesIO(png_bytes), "image/png")},
            headers={"Authorization": f"Bearer {token_orphan}"}
        )
        assert res.status_code == 404, res.text
        assert "not found" in res.text.lower()
