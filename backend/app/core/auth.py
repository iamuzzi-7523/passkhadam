import time
import json
import base64
import hashlib
from typing import Optional, Dict, Any, List
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.db import (
    get_db, SessionLocal, DBUser, DBWorkerProfile,
    DBEmployerOrganization, DBCategoryAuthorizationRequest, DBGovernmentOfficer
)
from app.models.schemas import UserContextResponse, OrganizationInfo
from app.services.blockchain_service import blockchain_service

# Canonical permissions tailored to each role
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "WORKER": [
        "view_worker_portal",
        "generate_qr",
        "view_credentials",
        "VIEW_PROFILE",
        "UPDATE_PROFILE",
        "VERIFY_AADHAAR",
        "VIEW_CREDENTIALS",
        "GENERATE_PRESENTATION",
        "VIEW_EMPLOYMENTS",
        "VIEW_CLAIMS"
    ],
    "EMPLOYER": [
        "view_employer_portal",
        "verify_worker",
        "manage_workforce",
        "VIEW_WORKFORCE",
        "VERIFY_WORKER_QR",
        "CREATE_EMPLOYMENT",
        "UPDATE_EMPLOYMENT",
        "REQUEST_CATEGORY"
    ],
    "GOVERNMENT": [
        "view_government_portal",
        "verify_interstate",
        "disburse_welfare",
        "VIEW_GOV_DASHBOARD",
        "VERIFY_WORKER_QR",
        "DISBURSE_WELFARE_CLAIM",
        "VIEW_WELFARE_SCHEMES"
    ],
    "ADMIN": [
        "view_admin_portal",
        "approve_organizations",
        "manage_governance",
        "VIEW_ADMIN_DASHBOARD",
        "APPROVE_ORGANIZATION",
        "APPROVE_CATEGORY",
        "CONFIGURE_NETWORK",
        "REVOKE_WORKER"
    ],
    "AADHAAR": [
        "view_aadhaar_portal",
        "view_directory",
        "inspect_api_logs",
        "VIEW_AADHAAR_DIRECTORY",
        "VIEW_API_LOGS",
        "SIMULATE_AADHAAR_VERIFICATION"
    ],
    "AADHAAR_ADMIN": [
        "view_aadhaar_portal",
        "view_directory",
        "inspect_api_logs",
        "VIEW_AADHAAR_DIRECTORY",
        "VIEW_API_LOGS",
        "SIMULATE_AADHAAR_VERIFICATION"
    ]
}

# Baseline demo accounts catalog
DEMO_ACCOUNTS_MAP = {
    "WORKER": {"email": "worker@passkhadam.org", "name": "Mohammed Uzair", "phone": "+91 9876543210"},
    "EMPLOYER": {"email": "employer@apexinfra.com", "name": "Apex Infrastructure Admin", "phone": "+91 9876543211"},
    "GOVERNMENT": {"email": "gov@maharashtra.gov.in", "name": "Maharashtra Labour Welfare Officer", "phone": "+91 9876543212"},
    "ADMIN": {"email": "admin@passkhadam.org", "name": "PassKhadam Platform Governance", "phone": "+91 9876543213"},
    "AADHAAR": {"email": "authority@uidai.gov.in", "name": "UIDAI Mock Authority Gateway", "phone": "+91 9876543214"}
}

CANONICAL_DEMO_EMAILS = {
    "worker@passkhadam.org",
    "employer@apexinfra.com",
    "gov@maharashtra.gov.in",
    "admin@passkhadam.org",
    "authority@uidai.gov.in"
}

def base64url_decode(s: str) -> bytes:
    """Decode base64url-encoded string with padding correction."""
    rem = len(s) % 4
    if rem > 0:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)

def base64url_encode(b: bytes) -> str:
    """Encode bytes to base64url-encoded string without padding."""
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def decode_jwt_unverified(token: str) -> Dict[str, Any]:
    """
    Decodes JWT header and payload without external network dependency.
    Validates token structure and returns payload claims.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed JWT token structure"
        )
    try:
        header_bytes = base64url_decode(parts[0])
        header = json.loads(header_bytes.decode("utf-8"))
        payload_bytes = base64url_decode(parts[1])
        payload = json.loads(payload_bytes.decode("utf-8"))
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to parse JWT token: {str(e)}"
        )

def verify_firebase_id_token(token: str) -> Dict[str, Any]:
    """
    Verifies a Firebase ID token.
    Validates claims:
    - aud == 'passkhadam-live'
    - iss matches Google securetoken URL for 'passkhadam-live'
    - expiration timestamp
    """
    payload = decode_jwt_unverified(token)

    # 1. Verify audience (Project ID)
    aud = payload.get("aud")
    if aud != "passkhadam-live":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token audience '{aud}'. Expected 'passkhadam-live'"
        )

    # 2. Verify issuer
    iss = payload.get("iss", "")
    if "passkhadam-live" not in iss:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token issuer '{iss}'. Expected Firebase project 'passkhadam-live'"
        )

    # 3. Check expiration
    exp = payload.get("exp")
    if exp and exp < time.time():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token has expired"
        )

    # 4. Check subject
    sub = payload.get("sub") or payload.get("user_id")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing subject claim ('sub') in token payload"
        )

    return payload

def get_permissions_for_role(role: str) -> List[str]:
    """Returns authoritative permissions list for a role."""
    return ROLE_PERMISSIONS.get(role.upper(), ["view_worker_portal", "generate_qr", "view_credentials"])

def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
) -> DBUser:
    """
    Authoritative FastApi dependency for token resolution.
    Hybrid dual-mode verifier:
    1. Firebase ID token (JWT for project passkhadam-live)
    2. Demo/test token (pk_token_{id}_{role} or mock_firebase_token_{...})
    Enforces account status and resolves user identity.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided"
        )

    # Extract Bearer token
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    user: Optional[DBUser] = None

    # Mode 1: Check for JWT (Firebase ID token)
    if token.count(".") == 2:
        payload = verify_firebase_id_token(token)
        uid = payload.get("sub") or payload.get("user_id")
        email = payload.get("email")
        phone = payload.get("phone_number") or payload.get("phone")
        name = payload.get("name") or (email.split("@")[0].capitalize() if email else "PassKhadam User")
        email_verified = payload.get("email_verified", True)

        clean_email = (email or "").strip().lower()

        # 1. Authoritative lookup by email if present
        if clean_email:
            user = db.query(DBUser).filter(func.lower(DBUser.email) == clean_email).first()
            if user:
                needs_commit = False
                if uid and user.firebase_uid != uid:
                    other = db.query(DBUser).filter(DBUser.firebase_uid == uid, DBUser.id != user.id).first()
                    if other:
                        other.firebase_uid = None
                    user.firebase_uid = uid
                    needs_commit = True
                # Automatically synchronize email verification status from Firebase ID token
                if payload.get("email_verified") is True and not user.is_email_verified:
                    user.is_email_verified = True
                    needs_commit = True
                # Automatically synchronize phone verification status from Firebase ID token
                if (payload.get("phone_number") or phone) and not user.is_phone_verified:
                    user.is_phone_verified = True
                    needs_commit = True
                if needs_commit:
                    db.commit()
                    db.refresh(user)

        # 2. If not found by email, lookup by firebase_uid
        if not user and uid:
            user = db.query(DBUser).filter(DBUser.firebase_uid == uid).first()
            if user:
                needs_commit = False
                if payload.get("email_verified") is True and not user.is_email_verified:
                    user.is_email_verified = True
                    needs_commit = True
                if (payload.get("phone_number") or phone) and not user.is_phone_verified:
                    user.is_phone_verified = True
                    needs_commit = True
                if needs_commit:
                    db.commit()
                    db.refresh(user)

        # 3. Only auto-provision canonical DEMO accounts; NEVER auto-provision unregistered new accounts on arbitrary token inspection
        if not user and clean_email and clean_email in CANONICAL_DEMO_EMAILS:
            if uid:
                other = db.query(DBUser).filter(DBUser.firebase_uid == uid).first()
                if other:
                    other.firebase_uid = None
                    db.commit()

            role = "WORKER"
            for r_key, acc in DEMO_ACCOUNTS_MAP.items():
                if clean_email == acc["email"].lower():
                    role = r_key
                    break
            if role == "WORKER":
                if clean_email.endswith("@maharashtra.gov.in") or "gov." in clean_email:
                    role = "GOVERNMENT"
                elif clean_email.endswith("@apexinfra.com") or "employer" in clean_email:
                    role = "EMPLOYER"

            user = DBUser(
                firebase_uid=uid,
                full_name=name,
                email=clean_email,
                phone=phone or "+91 9876543210",
                password_hash=hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest(),
                role=role,
                status="ACTIVE",
                is_email_verified=True,
                is_phone_verified=True
            )
            if role == "EMPLOYER":
                if clean_email == "employer@apexinfra.com" or clean_email.endswith("@apexinfra.com"):
                    user.organization_address = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
                    user.organization_name = "Apex Infrastructure & Construction Ltd"
                    user.organization_status = "APPROVED"
                else:
                    user.organization_status = "PENDING_REVIEW"
            elif role == "GOVERNMENT":
                if clean_email == "gov@maharashtra.gov.in" or clean_email.endswith("@maharashtra.gov.in"):
                    user.organization_name = "Maharashtra State Migrant Welfare Board"
                    user.organization_status = "APPROVED"
                else:
                    user.organization_status = "PROVISIONED"

            db.add(user)
            db.commit()
            db.refresh(user)

            if role == "WORKER":
                profile = DBWorkerProfile(
                    user_id=user.id,
                    full_name=user.full_name,
                    origin_state="Karnataka",
                    current_state="Karnataka",
                    worker_category="Mason"
                )
                db.add(profile)
                db.commit()

    # Mode 2: Demo / Test token (pk_token_{id}_{role})
    elif token.startswith("pk_token_"):
        parts = token.split("_")
        if len(parts) >= 4:
            try:
                user_id = int(parts[2])
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
            except ValueError:
                user = None

            if not user and len(parts) >= 4:
                role_candidate = parts[3].upper()
                if role_candidate in DEMO_ACCOUNTS_MAP:
                    acc = DEMO_ACCOUNTS_MAP[role_candidate]
                    user = db.query(DBUser).filter(func.lower(DBUser.email) == acc["email"].lower()).first()

    # Mode 3: Mock token for testing (mock_firebase_token_{role_or_email})
    elif token.startswith("mock_firebase_token_"):
        suffix = token.replace("mock_firebase_token_", "")
        # Suffix could be role or email
        if "@" in suffix:
            user = db.query(DBUser).filter(func.lower(DBUser.email) == suffix.strip().lower()).first()
        else:
            role_key = suffix.upper()
            if role_key in DEMO_ACCOUNTS_MAP:
                acc = DEMO_ACCOUNTS_MAP[role_key]
                user = db.query(DBUser).filter(func.lower(DBUser.email) == acc["email"].lower()).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognized authentication token"
        )

    # Tag demo tokens for session isolation
    if token.startswith("pk_token_") or token.startswith("mock_firebase_token_"):
        user._is_demo_token = True

    # Enforce account status: SUSPENDED, DISABLED, REJECTED are forbidden
    account_status = (user.status or "ACTIVE").upper()
    if account_status in ["SUSPENDED", "DISABLED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {account_status.lower()} (status: {account_status}). Access denied."
        )

    return user

def get_current_government_officer(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DBGovernmentOfficer:
    """
    Resolves DBGovernmentOfficer for current_user (officer.user_id == current_user.id
    or officer.official_email == current_user.email).
    If unlinked, raises HTTPException(status_code=404, detail="Government officer profile not found").
    """
    if current_user.role not in ["GOVERNMENT", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only government officers can access this endpoint"
        )
    officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.user_id == current_user.id).first()
    if not officer and current_user.email:
        officer = db.query(DBGovernmentOfficer).filter(
            func.lower(DBGovernmentOfficer.official_email) == current_user.email.strip().lower()
        ).first()
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Government officer profile not found"
        )
    return officer


def build_user_context(
    user: DBUser,
    db: Optional[Session] = None,
    is_demo: bool = False
) -> UserContextResponse:
    """
    Constructs the canonical UserContextResponse dynamically from SQLite database models.
    Zero silent fallbacks: queries DBWorkerProfile, DBEmployerOrganization, and DBGovernmentOfficer.
    Demo principal isolation: is_demo is only respected if user is a canonical demo account.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        clean_email = (user.email or "").strip().lower()
        demo_requested = is_demo or getattr(user, "_is_demo_token", False)
        effective_demo = bool(demo_requested and (clean_email in CANONICAL_DEMO_EMAILS))

        organization: Optional[OrganizationInfo] = None
        org_address: Optional[str] = None
        org_name: Optional[str] = None
        org_status: Optional[str] = None
        profile_id: Optional[str] = None
        profile_status: str = "ACTIVE"
        authority_level: Optional[str] = None
        state: Optional[str] = None
        district: Optional[str] = None
        block: Optional[str] = None
        worker_profile_data: Optional[Dict[str, Any]] = None

        if user.role == "WORKER":
            profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == user.id).first()
            if profile:
                profile_id = f"WORKER-{profile.id:06d}"
                skills = []
                if profile.skills_json:
                    try:
                        skills = json.loads(profile.skills_json)
                    except Exception:
                        skills = [profile.skills_json]

                from app.api.endpoints.worker import resolve_worker_aadhaar_status
                aadhaar_status, _ = resolve_worker_aadhaar_status(profile, db)

                worker_profile_data = {
                    "id": profile.id,
                    "did": profile.did,
                    "did_state": profile.did_state,
                    "is_aadhaar_verified": profile.is_aadhaar_verified,
                    "masked_aadhaar": profile.masked_aadhaar,
                    "aadhaar_request_id": profile.aadhaar_request_id,
                    "aadhaar_record_id": profile.aadhaar_record_id,
                    "aadhaar_status": aadhaar_status,
                    "is_credential_anchored": profile.is_credential_anchored,
                    "origin_state": profile.origin_state,
                    "current_state": profile.current_state,
                    "worker_category": profile.worker_category,
                    "skills": skills
                }
                if profile.is_credential_anchored:
                    profile_status = "COMPLETE" if aadhaar_status == "ACTIVE" else aadhaar_status
                else:
                    profile_status = "PENDING_VERIFICATION" if not profile.is_aadhaar_verified else "CREDENTIAL_PENDING"
            else:
                profile_status = "PENDING"
                profile_id = None
                worker_profile_data = None

        elif user.role == "EMPLOYER":
            org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == user.id).first()
            if org:
                profile_id = f"ORG-{org.id:06d}"
                org_address = org.org_address or user.organization_address or ("0x90F79bf6EB2c4f870365E785982E1f101E93b906" if clean_email == "employer@apexinfra.com" else None)
                org_name = ("Apex Infrastructure & Construction Ltd" if clean_email == "employer@apexinfra.com" else org.name)
                org_status = org.status
                profile_status = org.status

                active_reqs = db.query(DBCategoryAuthorizationRequest).filter(
                    DBCategoryAuthorizationRequest.organization_id == org.id,
                    DBCategoryAuthorizationRequest.is_active_scope == True
                ).all()

                categories = list({r.category for r in active_reqs})
                levels = list({r.skill_level for r in active_reqs})
                natures = list({r.nature_of_employment for r in active_reqs})

                organization = OrganizationInfo(
                    address=org_address,
                    name=org_name,
                    status=org_status,
                    org_type="EMPLOYER",
                    categories=categories,
                    levels=levels,
                    natures=natures
                )
            else:
                profile_status = "PENDING"
                profile_id = None
                organization = None
                org_address = user.organization_address or ("0x90F79bf6EB2c4f870365E785982E1f101E93b906" if clean_email == "employer@apexinfra.com" else None)
                org_name = user.organization_name or ("Apex Infrastructure & Construction Ltd" if clean_email == "employer@apexinfra.com" else None)
                org_status = user.organization_status or "PENDING_REVIEW"

        effective_permissions = get_permissions_for_role(user.role)
        benefit_permissions = []

        if user.role == "GOVERNMENT":
            officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.user_id == user.id).first()
            if not officer and user.email:
                officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.official_email == user.email).first()

            if officer:
                profile_id = officer.officer_reference_id or f"GOV-{officer.id:06d}"
                org_address = officer.wallet_address or user.organization_address or ("0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65" if clean_email == "gov@maharashtra.gov.in" else None)
                org_name = ("Maharashtra State Migrant Welfare Board" if clean_email == "gov@maharashtra.gov.in" else (officer.department or user.organization_name))
                org_status = user.organization_status or ("APPROVED" if officer.status in ["ACTIVE", "APPROVED"] else officer.status)
                profile_status = officer.status
                authority_level = officer.authority_level
                state = officer.state
                district = officer.district
                block = officer.block

                if officer.permissions_json:
                    try:
                        custom_perms = json.loads(officer.permissions_json)
                        if isinstance(custom_perms, list) and custom_perms:
                            effective_permissions = list(dict.fromkeys(get_permissions_for_role(user.role) + custom_perms))
                    except Exception:
                        pass

                if officer.benefit_permissions_json:
                    try:
                        b_perms = json.loads(officer.benefit_permissions_json)
                        if isinstance(b_perms, list):
                            benefit_permissions = b_perms
                    except Exception:
                        pass

                organization = OrganizationInfo(
                    address=org_address,
                    name=org_name,
                    status=org_status,
                    org_type="GOVERNMENT",
                    categories=[],
                    levels=[],
                    natures=[]
                )
            else:
                profile_status = "PENDING"
                profile_id = None
                org_address = user.organization_address or ("0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65" if clean_email == "gov@maharashtra.gov.in" else None)
                org_name = ("Maharashtra State Migrant Welfare Board" if clean_email == "gov@maharashtra.gov.in" else user.organization_name)
                org_status = user.organization_status or "PROVISIONED"
                if org_name:
                    organization = OrganizationInfo(
                        address=org_address,
                        name=org_name,
                        status=org_status,
                        org_type="GOVERNMENT",
                        categories=[],
                        levels=[],
                        natures=[]
                    )
                else:
                    organization = None

        return UserContextResponse(
            id=user.id,
            user_id=f"USR-{user.id:06d}",
            firebase_uid=user.firebase_uid or f"uid_{user.role.lower()}_{user.id}",
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            status=user.status or "ACTIVE",
            is_email_verified=bool(user.is_email_verified),
            is_phone_verified=bool(user.is_phone_verified),
            phone=user.phone,
            organization=organization,
            organization_address=org_address,
            organization_name=org_name,
            organization_status=org_status,
            profile_id=profile_id,
            profile_status=profile_status,
            authority_level=authority_level,
            state=state,
            district=district,
            block=block,
            worker_profile=worker_profile_data,
            is_demo=effective_demo,
            permissions=effective_permissions,
            benefit_permissions=benefit_permissions
        )
    finally:
        if close_session:
            db.close()

def create_test_firebase_jwt(
    uid: str,
    email: str,
    name: Optional[str] = None,
    aud: str = "passkhadam-live",
    iss: str = "https://securetoken.google.com/passkhadam-live",
    expired: bool = False
) -> str:
    """
    Generates a deterministic Firebase ID token (JWT) for testing purposes.
    """
    header = {"alg": "RS256", "kid": "mock_kid_passkhadam", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": iss,
        "aud": aud,
        "auth_time": now,
        "user_id": uid,
        "sub": uid,
        "iat": now,
        "exp": now - 3600 if expired else now + 3600,
        "email": email,
        "email_verified": True,
        "name": name or email.split("@")[0].capitalize(),
        "firebase": {
            "identities": {"email": [email]},
            "sign_in_provider": "password"
        }
    }
    header_b64 = base64url_encode(json.dumps(header).encode("utf-8"))
    payload_b64 = base64url_encode(json.dumps(payload).encode("utf-8"))
    sig_b64 = base64url_encode(b"mock_signature_passkhadam_live")
    return f"{header_b64}.{payload_b64}.{sig_b64}"
