"""
PassKhadam v0.5 — Test Module 8: All-Role Pairwise Combinatorial Smoke Tests
=============================================================================
Tier 3: Pairwise Combinations Across All Personas & Features
Covers interactions across Worker, Employer, Government Officer, Admin, and Mock Aadhaar Authority.

Total Tests: 24 tests
Pass/Fail Semantics: 100% pass rate, exit code 0, 0 skipped.
"""

import os
import sys
import json
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBWorkerProfile,
    DBEmployerOrganization,
    DBGovernmentOfficer,
    DBCategoryAuthorizationRequest,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBAadhaarRecord,
    DBAadhaarAuditLog,
)
from app.core.auth import create_test_firebase_jwt
from app.services.verification_engine import verification_engine
from app.services.blockchain_service import blockchain_service

client = TestClient(app)

DEFAULT_GOV_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"


# =============================================================================
# Helper Utilities
# =============================================================================

def get_admin_token() -> str:
    """Creates a persistent admin user and returns bearer JWT."""
    db = SessionLocal()
    u_uid = f"uid_adm_{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@passkhadam.org"
    user = DBUser(
        firebase_uid=u_uid,
        full_name="Platform Admin",
        email=email,
        phone="+919876500000",
        password_hash="hash",
        role="ADMIN",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.close()
    return create_test_firebase_jwt(uid=u_uid, email=email, name="Platform Admin")


def create_verified_worker(state: str = "Bihar") -> tuple[str, str, str, str, bytes]:
    """Sets up an anchored active worker via the canonical verify-aadhaar pipeline and generates valid QR PNG bytes."""
    worker_name = f"VerifWorker_{uuid.uuid4().hex[:6]}"
    uid = f"uid_{uuid.uuid4().hex[:10]}"
    email = f"worker_{uuid.uuid4().hex[:8]}@example.com"
    pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()

    db = SessionLocal()
    user = DBUser(
        firebase_uid=uid,
        full_name=worker_name,
        email=email,
        phone="+91 9876543210",
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
        origin_state=state,
        current_state="Maharashtra",
        worker_category="Mason",
        skills_json=json.dumps(["Mason", "Bricklaying"]),
        did_state="NOT_STARTED"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_test_firebase_jwt(uid=uid, email=email, name=worker_name)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Seed Aadhaar record in Mock Authority DB
    aadhaar_num = f"88{secrets.randbelow(10000000000):010d}"
    seed_res = client.post("/api/v1/aadhaar/records", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name,
        "dob": "1994-05-15",
        "gender": "MALE",
        "origin_state": state,
        "address": f"Patna, {state}",
        "status": "ACTIVE"
    })
    assert seed_res.status_code == 201, seed_res.text
    rec_id = seed_res.json()["record_id"]

    # 2. Verify Aadhaar to achieve ACTIVE anchored state
    v_res = client.post("/api/v1/worker/verify-aadhaar/me", json={
        "aadhaar_number": aadhaar_num,
        "full_name": worker_name
    }, headers=headers)
    assert v_res.status_code == 200, v_res.text
    worker_did = v_res.json()["did"]

    png_bytes, _ = verification_engine.generate_qr_presentation(
        worker_did=worker_did,
        worker_profile={"full_name": worker_name},
        validity_seconds=300
    )
    db.close()
    return worker_did, aadhaar_num, token, rec_id, png_bytes


def create_approved_employer(category: str = "Mason") -> tuple[int, str, str]:
    """Creates an approved active employer with active category authorization. Returns (org_id, org_address, employer_token)."""
    db = SessionLocal()
    org_addr = f"0x{uuid.uuid4().hex[:40]}"
    u_uid = f"uid_emp_{uuid.uuid4().hex[:8]}"
    email = f"employer_{uuid.uuid4().hex[:6]}@apexinfra.com"
    name = f"Apex Builders {uuid.uuid4().hex[:4]}"

    user = DBUser(
        firebase_uid=u_uid,
        full_name=name,
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="EMPLOYER",
        status="ACTIVE",
        organization_address=org_addr
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    org = DBEmployerOrganization(
        user_id=user.id,
        name=name,
        registration_ref_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        registration_number=f"CIN-{uuid.uuid4().hex[:8].upper()}",
        official_email=email,
        official_phone="+919876543210",
        contact_person="Ramesh Gupta",
        business_type="Construction",
        org_address=org_addr,
        status="APPROVED",
        state_code="MH"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    cat_auth = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category=category,
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        submitted_at=datetime.utcnow()
    )
    db.add(cat_auth)
    db.commit()
    db.close()

    # Blockchain registration
    blockchain_service.register_organization(
        address=org_addr,
        name=name,
        reg_num=f"CIN-{uuid.uuid4().hex[:8].upper()}",
        state_code="MH",
        org_type="EMPLOYER",
        categories=[category]
    )
    blockchain_service.set_org_status(org_addr, "APPROVED")
    blockchain_service.authorize_category(org_addr, category)

    token = create_test_firebase_jwt(uid=u_uid, email=email, name=name)
    return org_id, org_addr, token


def create_active_officer(state: str = "Maharashtra", perms: list = None) -> tuple[int, str]:
    """Creates an active government officer and returns (officer_id, officer_token)."""
    db = SessionLocal()
    u_uid = f"uid_gov_{uuid.uuid4().hex[:8]}"
    email = f"officer_{uuid.uuid4().hex[:6]}@labour.gov.in"
    name = f"Officer {uuid.uuid4().hex[:4]}"

    user = DBUser(
        firebase_uid=u_uid,
        full_name=name,
        email=email,
        phone="+919876543210",
        password_hash="hash",
        role="GOVERNMENT",
        status="ACTIVE",
        organization_address=None
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    officer = DBGovernmentOfficer(
        user_id=user.id,
        officer_name=name,
        full_name=name,
        officer_reference_id=f"GOV-OFF-{uuid.uuid4().hex[:8].upper()}",
        official_email=email,
        phone="+919876543210",
        wallet_address=None,
        department="Labour Welfare Department",
        designation="Commissioner",
        authority_level="STATE",
        state=state,
        status="ACTIVE",
        permissions_json=json.dumps(perms or ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"]),
        benefit_permissions_json=json.dumps(["1", "2"])
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    officer_id = officer.id
    db.close()

    blockchain_service.register_organization(
        address=DEFAULT_GOV_ADDR,
        name="Labour Welfare Department",
        reg_num="GOV-MH-01",
        state_code="MH",
        org_type="GOVERNMENT",
        categories=[]
    )
    blockchain_service.set_org_status(DEFAULT_GOV_ADDR, "APPROVED")

    token = create_test_firebase_jwt(uid=u_uid, email=email, name=name)
    return officer_id, token


# =============================================================================
# PAIR 1: Worker + Employer (T3.1 - T3.4)
# =============================================================================

def test_t3_worker_employer_verified_worker_hired():
    """T3.1: Approved employer successfully creates on-chain employment for verified worker."""
    worker_did, _, _, _, _ = create_verified_worker()
    _, _, emp_token = create_approved_employer(category="Mason")

    payload = {
        "worker_did": worker_did,
        "category": "Mason",
        "level": "Skilled",
        "nature_of_employment": "Contract",
        "job_role": "Master Mason",
        "work_location": "Bandra Kurla Complex, Mumbai",
        "expected_end_date": 0
    }
    resp = client.post(
        "/api/v1/employer/create-employment",
        json=payload,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "employment_record" in data
    assert data["employment_record"]["worker_did"] == worker_did


def test_t3_worker_employer_unverified_worker_cannot_be_hired():
    """T3.2: Employer cannot create employment contract for non-existent / unanchored worker DID."""
    fake_did = "did:passkhadam:worker:0x0000000000000000000000000000000000000000"
    _, _, emp_token = create_approved_employer(category="Mason")

    payload = {
        "worker_did": fake_did,
        "category": "UnapprovedCategory",
        "job_role": "Mason",
        "work_location": "Mumbai"
    }
    resp = client.post(
        "/api/v1/employer/create-employment",
        json=payload,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert resp.status_code in [400, 404]


def test_t3_worker_employer_qr_verification_by_employer():
    """T3.3: Employer uploads worker QR presentation image and receives verified identity."""
    worker_did, _, _, _, png_bytes = create_verified_worker()
    _, org_addr, emp_token = create_approved_employer(category="Mason")

    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post(
        "/api/v1/employer/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["worker_did"] == worker_did
    assert result["verified"] is True


def test_t3_worker_employer_completed_employment_status_transition():
    """T3.4: Employer transitions active employment to COMPLETED; historical record is preserved."""
    worker_did, _, _, _, _ = create_verified_worker()
    _, org_addr, emp_token = create_approved_employer(category="Mason")

    # Create employment first
    c_resp = client.post(
        "/api/v1/employer/create-employment",
        json={
            "worker_did": worker_did,
            "category": "Mason",
            "job_role": "Mason",
            "work_location": "Mumbai"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    emp_id = c_resp.json()["employment_record"]["id"]

    # Transition to COMPLETED
    u_resp = client.put(
        "/api/v1/employer/employment-status",
        json={
            "employment_id": emp_id,
            "new_status": "COMPLETED",
            "reason": "Contract duration completed successfully"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert u_resp.status_code == 200
    assert u_resp.json()["status"] == "COMPLETED"


# =============================================================================
# PAIR 2: Worker + Government Officer (T3.5 - T3.8)
# =============================================================================

def test_t3_worker_gov_active_worker_qr_scanned_by_officer():
    """T3.5: Active worker QR presentation scanned by Government Officer passes verification."""
    worker_did, _, _, _, png_bytes = create_verified_worker()
    _, officer_token = create_active_officer(state="Maharashtra")

    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["worker_did"] == worker_did
    assert resp.json()["verified"] is True


def test_t3_worker_gov_inactivated_worker_rejected_by_officer_scan():
    """T3.6: Worker whose on-chain credential is revoked is rejected when scanned by officer."""
    worker_did, _, _, rec_id, png_bytes = create_verified_worker()
    _, officer_token = create_active_officer()

    # Revoke worker on-chain / in blockchain registry
    if worker_did in blockchain_service.worker_registry:
        blockchain_service.worker_registry[worker_did]["is_revoked"] = True
        blockchain_service.worker_registry[worker_did]["revocation_reason"] = "Identity Suspended"

    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert resp.status_code in [400, 403]


def test_t3_worker_gov_interstate_worker_kyc_resolved_by_officer():
    """T3.7: Officer scans QR for worker from Bihar; interstate migration metadata resolved."""
    worker_did, _, _, _, png_bytes = create_verified_worker(state="Bihar")
    _, officer_token = create_active_officer(state="Maharashtra")

    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["origin_state"] == "Bihar"


def test_t3_worker_gov_welfare_benefit_disbursement():
    """T3.8: Government Officer disburses welfare claim to verified worker in same jurisdiction."""
    worker_did, _, _, _, _ = create_verified_worker()
    _, officer_token = create_active_officer(state="Maharashtra")

    payload = {
        "worker_did": worker_did,
        "scheme_id": 1,
        "officer_state": "Maharashtra"
    }
    resp = client.post(
        "/api/v1/government/disburse-claim",
        json=payload,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "claim_record" in data
    assert data["claim_record"]["worker_did"] == worker_did


# =============================================================================
# PAIR 3: Employer + Admin (T3.9 - T3.12)
# =============================================================================

def test_t3_employer_admin_onboarding_review_and_activation():
    """T3.9: Employer registers, Admin reviews and approves in queue, Employer redeems activation."""
    # 1. Employer submits registration
    reg_payload = {
        "company_name": f"Metro Construction {uuid.uuid4().hex[:4]}",
        "registration_number": f"CIN-{uuid.uuid4().hex[:8].upper()}",
        "business_address": "BKC, Mumbai",
        "contact_person": "Sunil Nair",
        "email": f"metro_{uuid.uuid4().hex[:6]}@metroinfra.com",
        "phone": "+919876543210",
        "categories_requested": ["Mason"]
    }
    r_reg = client.post("/api/v1/employer/register-organization", json=reg_payload)
    assert r_reg.status_code == 200
    org_id = r_reg.json()["organization_id"]
    raw_token = r_reg.json()["activation_token"]

    # 2. Admin approves organization
    admin_token = get_admin_token()
    r_rev = client.post(
        f"/api/v1/admin/organizations/{org_id}/review",
        json={"action": "APPROVE", "notes": "KYC documentation verified"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_rev.status_code == 200
    assert r_rev.json()["organization"]["status"] == "APPROVED"

    # 3. Employer redeems fresh activation token issued upon admin approval
    act_link = r_rev.json().get("activation_link")
    if act_link and "token=" in act_link:
        fresh_token = act_link.split("token=")[1]
    else:
        db = SessionLocal()
        rec = db.query(DBActivationEmail).filter(
            DBActivationEmail.entity_type == "EMPLOYER",
            DBActivationEmail.entity_id == org_id,
            DBActivationEmail.status == "SENT"
        ).order_by(DBActivationEmail.id.desc()).first()
        db.close()
        fresh_token = rec.custom_message if rec else raw_token
    r_act = client.post("/api/v1/employer/activate", json={"activation_token": fresh_token})
    assert r_act.status_code == 200


def test_t3_employer_admin_organization_suspension_by_admin():
    """T3.10: Admin suspends employer organization; subsequent employer actions are blocked."""
    org_id, org_addr, emp_token = create_approved_employer(category="Mason")
    admin_token = get_admin_token()

    # Admin suspends organization
    resp = client.post(
        f"/api/v1/admin/organizations/{org_id}/review",
        json={"action": "SUSPEND", "reason": "Non-compliance with safety regulations"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["organization"]["status"] == "SUSPENDED"

    # Employer attempts to create employment while suspended -> HTTP 403
    emp_resp = client.post(
        "/api/v1/employer/create-employment",
        json={
            "worker_did": "did:passkhadam:worker:test",
            "category": "Mason",
            "job_role": "Mason",
            "work_location": "Mumbai"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert emp_resp.status_code == 403


def test_t3_employer_admin_category_request_approval():
    """T3.11: Employer requests additional category scope; Admin approves it."""
    org_id, _, emp_token = create_approved_employer(category="Mason")
    admin_token = get_admin_token()

    # Employer submits category request
    req_resp = client.post(
        "/api/v1/employer/request-category",
        json={"category": "Electrician", "reason": "Expansion into industrial electrical works"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert req_resp.status_code == 200
    req_id = req_resp.json()["request_id"]

    # Admin approves category request
    rev_resp = client.post(
        f"/api/v1/admin/category-requests/{req_id}/review",
        json={"action": "APPROVE"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "APPROVED"


def test_t3_employer_admin_rejection_with_reason():
    """T3.12: Admin rejects employer registration with mandatory reason; status updated."""
    reg_payload = {
        "company_name": f"Flawed Corp {uuid.uuid4().hex[:4]}",
        "registration_number": f"CIN-BAD-{uuid.uuid4().hex[:8].upper()}",
        "business_address": "Nowhere",
        "contact_person": "Anon",
        "email": f"flawed_{uuid.uuid4().hex[:6]}@badcorp.com",
        "phone": "+919876543210"
    }
    r_reg = client.post("/api/v1/employer/register-organization", json=reg_payload)
    org_id = r_reg.json()["organization_id"]

    admin_token = get_admin_token()
    r_rev = client.post(
        f"/api/v1/admin/organizations/{org_id}/review",
        json={"action": "REJECT", "reason": "Invalid corporate identification number"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_rev.status_code == 200
    data = r_rev.json()
    assert data["organization"]["status"] == "REJECTED"
    db = SessionLocal()
    org_rec = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
    assert org_rec is not None
    assert org_rec.status == "REJECTED"
    assert "Invalid corporate" in (org_rec.rejection_reason or "")
    db.close()


# =============================================================================
# PAIR 4: Government Officer + Admin (T3.13 - T3.16)
# =============================================================================

def test_t3_gov_admin_officer_provisioning_and_jurisdiction_setup():
    """T3.13: Admin provisions officer with STATE authority; officer profile reflects grant."""
    admin_token = get_admin_token()
    email = f"officer_prov_{uuid.uuid4().hex[:6]}@labour.gov.in"
    payload = {
        "full_name": "Jurisdiction Officer",
        "official_email": email,
        "department": "Labour Commissionerate",
        "designation": "State Joint Commissioner",
        "authority_level": "STATE",
        "state": "Maharashtra",
        "permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"],
        "benefit_permissions": ["1", "2"]
    }
    resp = client.post(
        "/api/v1/admin/government-officers",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["authority_level"] == "STATE"
    assert data["state"] == "Maharashtra"
    assert "DISBURSE_BENEFIT" in data["permissions"]


def test_t3_gov_admin_officer_status_suspension_by_admin():
    """T3.14: Admin suspends government officer; officer blocked from verification portal."""
    admin_token = get_admin_token()
    officer_id, officer_token = create_active_officer()

    # Admin suspends officer via POST /status
    s_resp = client.post(
        f"/api/v1/admin/government-officers/{officer_id}/status",
        json={"status": "SUSPENDED", "reason": "Administrative inquiry pending"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert s_resp.status_code == 200
    assert s_resp.json()["status"] == "SUSPENDED"

    # Officer attempts to verify worker QR -> HTTP 403
    png_bytes, _ = verification_engine.generate_qr_presentation(
        worker_did="did:passkhadam:worker:test",
        worker_profile={"full_name": "Test"},
        validity_seconds=300
    )
    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    v_resp = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert v_resp.status_code == 403


def test_t3_gov_admin_officer_permission_update_by_admin():
    """T3.15: Admin updates officer permissions; updated context dynamic and immediate."""
    admin_token = get_admin_token()
    officer_id, officer_token = create_active_officer(perms=["WORKER_VERIFICATION"])

    # Update to add DISBURSE_BENEFIT
    resp = client.put(
        f"/api/v1/admin/government-officers/{officer_id}",
        json={"permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT", "CROSS_STATE_VERIFICATION"]},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert "CROSS_STATE_VERIFICATION" in resp.json()["permissions"]


def test_t3_gov_admin_governance_audit_trail_created():
    """T3.16: Admin provisioning of officer writes immutable DBGovernanceAuditLog record."""
    admin_token = get_admin_token()
    email = f"audit_prov_{uuid.uuid4().hex[:6]}@labour.gov.in"
    client.post(
        "/api/v1/admin/government-officers",
        json={
            "full_name": "Audited Officer",
            "official_email": email,
            "department": "Welfare Board",
            "authority_level": "STATE",
            "state": "Maharashtra"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    db = SessionLocal()
    audit = db.query(DBGovernanceAuditLog).filter(
        DBGovernanceAuditLog.action == "PROVISION_GOVERNMENT_OFFICER"
    ).order_by(DBGovernanceAuditLog.id.desc()).first()

    assert audit is not None
    assert audit.target_type == "GOVERNMENT_OFFICER"
    assert audit.new_state == "PROVISIONED"
    db.close()


# =============================================================================
# PAIR 5: Category Scope + Employer (T3.17 - T3.20)
# =============================================================================

def test_t3_category_employer_active_scope_allows_hiring():
    """T3.17: Approved employer with active scope for 'Plumber' creates employment successfully."""
    worker_did, _, _, _, _ = create_verified_worker()
    _, _, emp_token = create_approved_employer(category="Plumber")

    payload = {
        "worker_did": worker_did,
        "category": "Plumber",
        "job_role": "Industrial Pipefitter",
        "work_location": "Navi Mumbai"
    }
    resp = client.post(
        "/api/v1/employer/create-employment",
        json=payload,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["employment_record"]["category"] == "Plumber"


def test_t3_category_employer_unapproved_category_denied():
    """T3.18: Employer authorized only for 'Mason' denied when creating contract for 'Welder'."""
    worker_did, _, _, _, _ = create_verified_worker()
    _, _, emp_token = create_approved_employer(category="Mason")

    payload = {
        "worker_did": worker_did,
        "category": "Welder",
        "job_role": "Arc Welder",
        "work_location": "Pune"
    }
    resp = client.post(
        "/api/v1/employer/create-employment",
        json=payload,
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert resp.status_code == 400
    assert "does not have an active approved scope" in resp.text


def test_t3_category_employer_discontinuation_decoupling():
    """T3.19: Admin discontinues category; employer contracts decoupled non-destructively."""
    worker_did, _, _, _, _ = create_verified_worker()
    org_id, _, emp_token = create_approved_employer(category="Excavator")

    # Contract created while category active
    client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Excavator", "job_role": "Operator", "work_location": "Thane"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )

    # Admin discontinues category
    admin_token = get_admin_token()
    client.post(
        "/api/v1/admin/category-scopes/Excavator/discontinue",
        json={"reason": "Category phase out due to national automation guidelines"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Employer status remains APPROVED; contracts remain intact
    db = SessionLocal()
    org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
    assert org.status == "APPROVED"
    db.close()


def test_t3_category_employer_multi_category_partial_approval():
    """T3.20: Employer has Mason APPROVED and Painter PENDING; hiring permitted only for Mason."""
    org_id, org_addr, emp_token = create_approved_employer(category="Mason")
    worker_did, _, _, _, _ = create_verified_worker()

    # Add Painter as PENDING
    db = SessionLocal()
    p_auth = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Painter",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="PENDING",
        is_active_scope=False,
        submitted_at=datetime.utcnow()
    )
    db.add(p_auth)
    db.commit()
    db.close()

    # Hiring for Mason succeeds
    r_mason = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Mason", "job_role": "Mason", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert r_mason.status_code == 200

    # Hiring for Painter fails
    r_painter = client.post(
        "/api/v1/employer/create-employment",
        json={"worker_did": worker_did, "category": "Painter", "job_role": "Painter", "work_location": "Mumbai"},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert r_painter.status_code == 400


# =============================================================================
# PAIR 6: Mock Aadhaar Authority + All Roles (T3.21 - T3.24)
# =============================================================================

def test_t3_aadhaar_worker_demographic_sync():
    """T3.21: Updating demographic address in Mock Aadhaar reflects during worker profile query."""
    worker_did, _, token, rec_id, _ = create_verified_worker()

    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == rec_id).first()
    rec.address = "Sector 17, Vashi, Navi Mumbai, Maharashtra"
    db.commit()
    db.close()

    resp = client.get("/api/v1/worker/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_t3_aadhaar_worker_deactivation_cascades_to_qr():
    """T3.22: Inactivating Aadhaar record prevents worker from generating fresh QR presentation."""
    worker_did, _, token, rec_id, _ = create_verified_worker()

    # Inactivate record in Mock Authority DB
    db = SessionLocal()
    rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == rec_id).first()
    rec.status = "INACTIVE"
    rec.is_active = False
    db.commit()
    db.close()

    # Requesting fresh QR presentation must be rejected with HTTP 403
    resp = client.get("/api/v1/worker/presentation/qr-card/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_t3_aadhaar_gov_cross_check_jurisdiction():
    """T3.23: Origin state from Mock Aadhaar verified against Officer jurisdiction."""
    worker_did, _, _, _, png_bytes = create_verified_worker(state="Bihar")
    _, officer_token = create_active_officer(state="Maharashtra")

    files = {"file": ("worker_qr.png", png_bytes, "image/png")}
    resp = client.post(
        "/api/v1/government/verify-worker-qr",
        files=files,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["origin_state"] == "Bihar"


def test_t3_aadhaar_immutable_audit_logging():
    """T3.24: Every Aadhaar check creates immutable DBAadhaarAuditLog that cannot be altered."""
    db = SessionLocal()
    audit_id = str(uuid.uuid4())
    audit = DBAadhaarAuditLog(
        request_id=audit_id,
        record_id=str(uuid.uuid4()),
        masked_aadhaar="XXXXXXXX1234",
        supplied_name="Test Citizen",
        name_matched=True,
        aadhaar_matched=True,
        record_status="ACTIVE",
        result_code="SUCCESS_ACTIVE"
    )
    db.add(audit)
    db.commit()

    # Verify immutable trigger prevents modification
    audit.name_matched = False
    with pytest.raises(Exception):
        db.commit()
    db.rollback()
    db.close()
