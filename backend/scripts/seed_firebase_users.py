#!/usr/bin/env python3
"""
PASSKHADAM — Multi-Role Firebase Authentication & Database Provisioning Script.
Provisions and synchronizes the 5 baseline canonical demonstration accounts
across Firebase Authentication and PassKhadam's SQLite state store.

Baseline Accounts:
1. Worker: worker@passkhadam.org
2. Employer: employer@apexinfra.com
3. Government Officer: gov@maharashtra.gov.in
4. Platform Admin: admin@passkhadam.org
5. Mock Aadhaar Authority: authority@uidai.gov.in

Demo Password: passkhadam123
"""

import sys
import os
import json
import hashlib
import urllib.request
import urllib.error

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.db import init_db, SessionLocal, DBUser, DBWorkerProfile

BASELINE_ACCOUNTS = [
    {
        "role": "WORKER",
        "email": "worker@passkhadam.org",
        "name": "Mohammed Uzair",
        "phone": "+91 9876543210",
        "password": "passkhadam123",
        "firebase_uid": "uid_worker_live",
        "status": "ACTIVE",
        "org_address": None,
        "org_name": None,
        "org_status": None,
        "worker_profile": {
            "dob": "1995-04-12",
            "gender": "Male",
            "origin_state": "Karnataka",
            "current_state": "Karnataka",
            "address": "45/2 BTM Layout, Bengaluru, Karnataka",
            "worker_category": "Mason",
            "skills": ["Mason", "Bricklaying", "Concrete Work", "Plumbing Assistance"]
        }
    },
    {
        "role": "EMPLOYER",
        "email": "employer@apexinfra.com",
        "name": "Apex Infrastructure Admin",
        "phone": "+91 9876543211",
        "password": "passkhadam123",
        "firebase_uid": "uid_employer_live",
        "status": "ACTIVE",
        "org_address": "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
        "org_name": "Apex Infrastructure & Construction Ltd",
        "org_status": "APPROVED",
        "worker_profile": None
    },
    {
        "role": "GOVERNMENT",
        "email": "gov@maharashtra.gov.in",
        "name": "Maharashtra Labour Welfare Officer",
        "phone": "+91 9876543212",
        "password": "passkhadam123",
        "firebase_uid": "uid_gov_live",
        "status": "ACTIVE",
        "org_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
        "org_name": "Maharashtra State Migrant Welfare Board",
        "org_status": "APPROVED",
        "worker_profile": None
    },
    {
        "role": "ADMIN",
        "email": "admin@passkhadam.org",
        "name": "PassKhadam Platform Governance",
        "phone": "+91 9876543213",
        "password": "passkhadam123",
        "firebase_uid": "uid_admin_live",
        "status": "ACTIVE",
        "org_address": None,
        "org_name": None,
        "org_status": None,
        "worker_profile": None
    },
    {
        "role": "AADHAAR",
        "email": "authority@uidai.gov.in",
        "name": "UIDAI Mock Authority Gateway",
        "phone": "+91 9876543214",
        "password": "passkhadam123",
        "firebase_uid": "uid_aadhaar_live",
        "status": "ACTIVE",
        "org_address": None,
        "org_name": None,
        "org_status": None,
        "worker_profile": None
    }
]

def try_provision_firebase_cloud(email: str, password: str, api_key: str = None) -> str:
    """
    Attempts to create or sign in user on Firebase Authentication REST API if API key provided.
    Returns Firebase UID if successful, else None.
    """
    key = api_key or os.getenv("FIREBASE_WEB_API_KEY") or os.getenv("VITE_FIREBASE_API_KEY")
    if not key:
        return None
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={key}"
    payload = json.dumps({
        "email": email,
        "password": password,
        "returnSecureToken": True
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("localId")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        if "EMAIL_EXISTS" in err_body:
            # Attempt signInWithPassword to get UID
            signin_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={key}"
            req_in = urllib.request.Request(signin_url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req_in, timeout=5) as in_resp:
                    in_data = json.loads(in_resp.read().decode("utf-8"))
                    return in_data.get("localId")
            except Exception:
                pass
    except Exception:
        pass
    return None

def seed_database():
    """Initializes tables and provisions all 5 baseline accounts."""
    print("=" * 65)
    print("PASSKHADAM — Baseline Accounts Provisioning Engine (v1.1)")
    print("=" * 65)

    init_db()
    db = SessionLocal()

    api_key = os.getenv("VITE_FIREBASE_API_KEY", "AIzaSyAm2y_rprQk5C51aD_1UTcw4pyfI-vsrHQ")

    try:
        for acc in BASELINE_ACCOUNTS:
            email = acc["email"]
            name = acc["name"]
            phone = acc["phone"]
            role = acc["role"]
            pw = acc["password"]
            pw_hash = hashlib.sha256(pw.encode("utf-8")).hexdigest()

            # Optional remote provisioning
            remote_uid = try_provision_firebase_cloud(email, pw, api_key)
            final_uid = remote_uid or acc["firebase_uid"]

            user = db.query(DBUser).filter(DBUser.email == email).first()
            if not user:
                user = DBUser(
                    full_name=name,
                    email=email,
                    phone=phone,
                    password_hash=pw_hash,
                    role=role,
                    status=acc["status"],
                    firebase_uid=final_uid,
                    organization_address=acc["org_address"],
                    organization_name=acc["org_name"],
                    organization_status=acc["org_status"],
                    is_email_verified=True,
                    is_phone_verified=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                action = "CREATED"
            else:
                user.full_name = name
                user.phone = phone
                user.password_hash = pw_hash
                user.role = role
                user.status = acc["status"]
                user.firebase_uid = final_uid
                if acc["org_address"]:
                    user.organization_address = acc["org_address"]
                    user.organization_name = acc["org_name"]
                    user.organization_status = acc["org_status"]
                db.commit()
                db.refresh(user)
                action = "SYNCHRONIZED"

            # Create or update worker profile if applicable
            if acc["worker_profile"]:
                wp = acc["worker_profile"]
                profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).first()
                if not profile:
                    profile = DBWorkerProfile(
                        user_id=user.id,
                        full_name=user.full_name,
                        dob=wp["dob"],
                        gender=wp["gender"],
                        origin_state=wp["origin_state"],
                        current_state=wp["current_state"],
                        address=wp["address"],
                        worker_category=wp["worker_category"],
                        skills_json=json.dumps(wp["skills"]),
                        is_aadhaar_verified=False
                    )
                    db.add(profile)
                    db.commit()
                else:
                    profile.full_name = user.full_name
                    profile.origin_state = wp["origin_state"]
                    profile.current_state = wp["current_state"]
                    db.commit()

            cloud_status = f"Cloud UID ({final_uid})" if remote_uid else f"Local UID ({final_uid})"
            print(f"[{action}] Role: {role:<12} | Email: {email:<28} | Status: {user.status:<7} | {cloud_status}")

        print("=" * 65)
        print("Provisioning successfully completed. All 5 baseline accounts active.")
        print("=" * 65)

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
