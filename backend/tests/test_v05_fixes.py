"""
PassKhadam v0.5.0 Fix Verification & Regression Tests:
1. Government credential issuance HTTP endpoint (no AttributeError, valid credential return)
2. Employer credential issuance HTTP endpoint (valid credential return)
3. Admin active category scope suspension via PATCH and POST
4. Admin government officer suspension and reactivation via status endpoint
5. CORS preflight OPTIONS returns PATCH in Access-Control-Allow-Methods
"""

import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import (
    SessionLocal,
    DBUser,
    DBWorkerProfile,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBGovernmentOfficer,
    DBWorkerCredential
)

client = TestClient(app)

@pytest.fixture
def test_setup():
    db = SessionLocal()
    ts = int(time.time() * 1000)

    # 1. Worker
    worker_user = DBUser(
        email=f"worker_{ts}@test.org",
        full_name="Ramesh Worker",
        phone=f"+91 98{ts % 100000000:08d}",
        password_hash="hash",
        role="WORKER",
        status="ACTIVE"
    )
    db.add(worker_user)
    db.commit()
    db.refresh(worker_user)

    worker_profile = DBWorkerProfile(
        user_id=worker_user.id,
        full_name="Ramesh Worker",
        did=f"did:passkhadam:worker:{ts}",
        is_credential_anchored=True,
        did_state="ACTIVE",
        worker_category="Carpenter"
    )
    db.add(worker_profile)

    # 2. Government Officer User & Profile
    gov_user = DBUser(
        email=f"gov_{ts}@kerala.gov.in",
        full_name="Kerala Welfare Officer",
        phone=f"+91 97{ts % 100000000:08d}",
        password_hash="hash",
        role="GOVERNMENT",
        status="ACTIVE"
    )
    db.add(gov_user)
    db.commit()
    db.refresh(gov_user)

    gov_officer = DBGovernmentOfficer(
        user_id=gov_user.id,
        officer_name="Kerala Welfare Officer",
        full_name="Kerala Welfare Officer",
        officer_reference_id=f"GOV-KL-{ts}",
        department="Labour Welfare Board",
        designation="Welfare Commissioner",
        official_email=gov_user.email,
        authority_level="STATE",
        state="Kerala",
        status="ACTIVE"
    )
    db.add(gov_officer)

    # 3. Employer User & Org
    emp_user = DBUser(
        email=f"emp_{ts}@buildcorp.com",
        full_name="BuildCorp HR",
        phone=f"+91 96{ts % 100000000:08d}",
        password_hash="hash",
        role="EMPLOYER",
        status="ACTIVE",
        organization_name="BuildCorp Ltd",
        organization_address=f"0x{ts:040x}"
    )
    db.add(emp_user)
    db.commit()
    db.refresh(emp_user)

    emp_org = DBEmployerOrganization(
        user_id=emp_user.id,
        name="BuildCorp Ltd",
        registration_ref_number=f"REG-{ts}",
        org_address=emp_user.organization_address,
        status="APPROVED"
    )
    db.add(emp_org)
    db.commit()
    db.refresh(emp_org)

    # 4. Admin User
    admin_user = DBUser(
        email=f"admin_{ts}@passkhadam.gov.in",
        full_name="Super Admin",
        phone=f"+91 95{ts % 100000000:08d}",
        password_hash="hash",
        role="ADMIN",
        status="ACTIVE"
    )
    worker_did = worker_profile.did
    gov_user_id = gov_user.id
    gov_email = gov_user.email
    gov_officer_id = gov_officer.id
    emp_user_id = emp_user.id
    emp_email = emp_user.email
    emp_org_id = emp_org.id
    admin_user_id = admin_user.id
    admin_email = admin_user.email

    db.commit()
    db.close()

    return {
        "worker_did": worker_did,
        "gov_user_id": gov_user_id,
        "gov_email": gov_email,
        "gov_officer_id": gov_officer_id,
        "emp_user_id": emp_user_id,
        "emp_email": emp_email,
        "emp_org_id": emp_org_id,
        "admin_user_id": admin_user_id,
        "admin_email": admin_email,
    }


def test_v05_government_credential_endpoint_http(test_setup):
    """Test 2: Fix for Government Portal 'Failed to fetch' on credential issuance."""
    token = f"pk_token_{test_setup['gov_user_id']}_GOVERNMENT"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "worker_did": test_setup["worker_did"],
        "title": "BOCW Social Security Card",
        "credential_type": "Welfare",
        "skills": ["Formwork", "Carpentry"],
        "valid_days": 365
    }

    res = client.post("/api/v1/government/credentials/issue", json=payload, headers=headers)
    assert res.status_code == 200, f"Government credential issue failed: {res.text}"
    data = res.json()
    assert data["title"] == "BOCW Social Security Card"
    assert data["type"] == "Welfare"
    assert data["issuer_role"] == "GOVERNMENT"
    assert data["status"] == "VALID"
    assert "Formwork" in data["skills"]


def test_v05_employer_credential_endpoint_http(test_setup):
    """Test 1: Fix for Employer Portal Issue Trade / Experience Credential."""
    token = f"pk_token_{test_setup['emp_user_id']}_EMPLOYER"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "worker_did": test_setup["worker_did"],
        "title": "Senior Carpenter Experience Certificate",
        "credential_type": "Experience",
        "skills": ["Carpenter", "Wood Joinery"],
        "valid_days": 365
    }

    res = client.post("/api/v1/employer/credentials/issue", json=payload, headers=headers)
    assert res.status_code == 200, f"Employer credential issue failed: {res.text}"
    data = res.json()
    assert data["title"] == "Senior Carpenter Experience Certificate"
    assert data["type"] == "Experience"
    assert data["issuer_role"] == "EMPLOYER"
    assert data["status"] == "VALID"
    assert "Carpenter" in data["skills"]


def test_v05_admin_suspend_category_scope_patch_and_post(test_setup):
    """Test 3: Fix for Admin Portal 'Failed to fetch' on Active Scope Suspension."""
    db = SessionLocal()
    # Create an active category authorization request
    cat_req = DBCategoryAuthorizationRequest(
        organization_id=test_setup["emp_org_id"],
        category="Carpentry",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True
    )
    db.add(cat_req)
    db.commit()
    db.refresh(cat_req)
    cat_id = cat_req.id
    db.close()

    admin_token = f"pk_token_{test_setup['admin_user_id']}_ADMIN"
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Test PATCH method
    suspend_payload = {
        "action": "SUSPEND",
        "reason": "Safety protocol review"
    }
    patch_res = client.patch(f"/api/v1/admin/category-requests/{cat_id}", json=suspend_payload, headers=headers)
    assert patch_res.status_code == 200, f"PATCH suspend failed: {patch_res.text}"
    data = patch_res.json()
    assert data["status"] == "SUSPENDED"
    assert data["is_active_scope"] is False

    # 2. Test POST fallback alias
    post_res = client.post(f"/api/v1/admin/category-requests/{cat_id}", json=suspend_payload, headers=headers)
    assert post_res.status_code == 200, f"POST suspend alias failed: {post_res.text}"


def test_v05_admin_suspend_and_reactivate_government_officer(test_setup):
    """Test 4: Fix for Government Officer suspension and reactivation."""
    admin_token = f"pk_token_{test_setup['admin_user_id']}_ADMIN"
    headers = {"Authorization": f"Bearer {admin_token}"}
    officer_id = test_setup["gov_officer_id"]

    # 1. Suspend officer with mandatory reason
    suspend_res = client.post(
        f"/api/v1/admin/government-officers/{officer_id}/status",
        json={"status": "SUSPENDED", "reason": "Administrative suspension pending audit"},
        headers=headers
    )
    assert suspend_res.status_code == 200, f"Suspend officer failed: {suspend_res.text}"
    data = suspend_res.json()
    assert data["status"] == "SUSPENDED"
    assert data["suspension_reason"] == "Administrative suspension pending audit"

    # 2. Reactivate officer
    reactivate_res = client.post(
        f"/api/v1/admin/government-officers/{officer_id}/status",
        json={"status": "ACTIVE"},
        headers=headers
    )
    assert reactivate_res.status_code == 200, f"Reactivate officer failed: {reactivate_res.text}"
    data2 = reactivate_res.json()
    assert data2["status"] == "ACTIVE"


def test_v05_cors_allows_patch():
    """Verify that CORS preflight permits PATCH method."""
    headers = {
        "Origin": "app://passkhadam.app",
        "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "Authorization, Content-Type"
    }
    res = client.options("/api/v1/admin/category-requests/1", headers=headers)
    assert res.status_code == 200
    allow_methods = res.headers.get("access-control-allow-methods", "")
    assert "PATCH" in allow_methods, f"PATCH missing from allowed CORS methods: {allow_methods}"
