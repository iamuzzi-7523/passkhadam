"""
PassKhadam v0.4 Invariant Regression Tests:
1. Dynamic worker trade registration (e.g. Electrician)
2. Decoupled employment persistence: Category revocation preserves existing historical stints
3. Government credential issuance workflow
4. Employer credential issuance workflow
"""

import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import SessionLocal, DBUser, DBWorkerProfile, DBEmployerOrganization, DBCategoryAuthorizationRequest, DBGovernmentOfficer, DBWorkerCredential, DBEmployment
from app.services.blockchain_service import blockchain_service

client = TestClient(app)

def test_dynamic_worker_trade_registration():
    """Verify that worker registering with non-Mason profession (e.g., Electrician) is respected."""
    db = SessionLocal()
    try:
        user_email = f"electrician_{int(pytest.importorskip('time').time())}@worker.org"
        reg_payload = {
            "email": user_email,
            "full_name": "Suresh Electrician",
            "password": "Password123!",
            "phone": "+91 98765 43210",
            "role": "WORKER",
            "worker_category": "Electrician",
            "skills": ["Electrical Wiring", "Solar Inverter Maintenance"],
            "origin_state": "Karnataka",
            "current_state": "Karnataka",
            "is_email_verified": True,
            "is_phone_verified": True
        }
        res = client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["user"]["role"] == "WORKER"

        # Check DB profile
        prof = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == data["user"]["id"]).first()
        assert prof is not None
        assert prof.worker_category == "Electrician"
        skills = json.loads(prof.skills_json)
        assert "Electrical Wiring" in skills
    finally:
        db.close()


def test_category_discontinuation_preserves_worker_employment_history():
    """
    CRITICAL INVARIANT TEST:
    1. Employer creates employment for worker under 'Plumber' category.
    2. Admin discontinues 'Plumber' category for employer.
    3. Worker's employment history STILL retains the 'Plumber' employment record.
    """
    db = SessionLocal()
    try:
        worker_did = "did:passkhadam:worker:invariant_plumber_test"
        emp_addr = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"

        # Ensure org has approved Plumber category
        blockchain_service.authorize_category(emp_addr, "Plumber")
        assert blockchain_service.is_category_authorized(emp_addr, "Plumber")

        # Create employment record
        emp_rec = blockchain_service.create_employment(
            worker_did=worker_did,
            employer_address=emp_addr,
            category="Plumber",
            job_role="Master Pipefitter",
            location="Site 7, Bengaluru",
            level="Skilled",
            nature_of_employment="Contract"
        )
        assert emp_rec["category"] == "Plumber"
        emp_id = emp_rec["id"]

        # Verify employment is in get_worker_employments
        initial_stints = blockchain_service.get_worker_employments(worker_did)
        assert any(e["id"] == emp_id and e["category"] == "Plumber" for e in initial_stints)

        # Admin discontinues 'Plumber' category
        blockchain_service.revoke_category(emp_addr, "Plumber")
        assert not blockchain_service.is_category_authorized(emp_addr, "Plumber")

        # INVARIANT: Worker's historical stint MUST STILL BE VISIBLE!
        post_revocation_stints = blockchain_service.get_worker_employments(worker_did)
        plumber_stints = [e for e in post_revocation_stints if e["category"] == "Plumber" and e["id"] == emp_id]
        assert len(plumber_stints) == 1, "Historical employment disappeared after category revocation!"
        assert plumber_stints[0]["job_role"] == "Master Pipefitter"
    finally:
        db.close()


def test_government_and_employer_credential_issuance():
    """Verify that Government and Employer can issue custom credentials to worker DID."""
    db = SessionLocal()
    try:
        worker_did = "did:passkhadam:worker:custom_cred_test_did"
        # Seed test worker profile
        worker_user = DBUser(
            email=f"w_{int(pytest.importorskip('time').time())}@test.com",
            full_name="Arjun Worker",
            phone="+919111122223",
            password_hash="hash",
            role="WORKER",
            status="ACTIVE"
        )
        db.add(worker_user)
        db.commit()
        db.refresh(worker_user)

        prof = DBWorkerProfile(
            user_id=worker_user.id,
            full_name="Arjun Worker",
            did=worker_did,
            is_credential_anchored=True,
            did_state="ACTIVE",
            worker_category="Carpenter"
        )
        db.add(prof)
        db.commit()

        # 1. Government issues BOCW Welfare Certification
        gov_cred = DBWorkerCredential(
            credential_id=f"cred-gov-{int(pytest.importorskip('time').time())}",
            worker_did=worker_did,
            worker_id=prof.id,
            title="BOCW Welfare Social Security Card",
            credential_type="Welfare",
            issuer_name="Karnataka BOCW Welfare Board",
            issuer_address="0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
            issuer_role="GOVERNMENT",
            status="VALID",
            skills_json=json.dumps(["Carpentry", "Formwork Installation"])
        )
        db.add(gov_cred)

        # 2. Employer issues Trade Experience Credential
        emp_cred = DBWorkerCredential(
            credential_id=f"cred-emp-{int(pytest.importorskip('time').time())}",
            worker_did=worker_did,
            worker_id=prof.id,
            title="Senior Carpenter Experience Certificate",
            credential_type="Experience",
            issuer_name="Apex Infrastructure Ltd",
            issuer_address="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            issuer_role="EMPLOYER",
            status="VALID",
            skills_json=json.dumps(["Timber Framing", "Interior Woodwork"])
        )
        db.add(emp_cred)
        db.commit()

        # Query worker wallet
        from app.api.endpoints.worker import serialize_worker_wallet
        wallet = serialize_worker_wallet(prof, db=db)
        creds = wallet["credentials"]

        # Assert Government Identity Credential exists
        assert any(c["id"] == "cred-id-01" for c in creds)

        # Assert Government issued BOCW credential is in wallet
        bocw = next((c for c in creds if "BOCW Welfare" in c["title"]), None)
        assert bocw is not None
        assert bocw["issuer_role"] == "GOVERNMENT"

        # Assert Employer issued Experience credential is in wallet
        exp = next((c for c in creds if "Senior Carpenter" in c["title"]), None)
        assert exp is not None
        assert exp["issuer_role"] == "EMPLOYER"
    finally:
        db.close()
