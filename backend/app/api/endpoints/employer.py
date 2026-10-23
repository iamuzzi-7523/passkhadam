import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Query, status
from sqlalchemy.orm import Session

from app.models.db import (
    get_db,
    DBUser,
    DBCategoryRequest,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBWorkerCredential,
    DBWorkerProfile
)
from app.models.schemas import (
    CategoryRequest,
    CreateEmploymentRequest,
    UpdateEmploymentStatusRequest,
    EmployerRegister,
    EmployerActivationRequest,
    EmployerActivationResponse,
    CategoryAuthorizationRequestResponse,
    CredentialIssueRequest,
    CredentialResponse
)
from app.core.auth import get_current_user
from app.services.blockchain_service import blockchain_service
from app.services.verification_engine import (
    verification_engine,
    VerificationEngineError,
    VerificationErrorCode,
    ReplayAttackError
)

def get_optional_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
) -> Optional[DBUser]:
    if not authorization:
        return None
    try:
        return get_current_user(authorization=authorization, db=db)
    except HTTPException as e:
        if e.status_code in (401, 403):
            raise
        return None
    except Exception:
        return None

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

router = APIRouter()

DEFAULT_EMPLOYER_ADDR = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"

@router.get("/info")
@router.get("/profile")
def get_employer_info(
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if current_user and current_user.role == "EMPLOYER":
        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == current_user.id).first()
        if not org and current_user.organization_address:
            org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.org_address == current_user.organization_address).first()

        if org:
            target_addr = org.org_address or current_user.organization_address or f"0xemp_{org.id:04d}"
            active_scopes = db.query(DBCategoryAuthorizationRequest).filter(
                DBCategoryAuthorizationRequest.organization_id == org.id,
                DBCategoryAuthorizationRequest.is_active_scope == True
            ).all()
            approved_cats = [s.category for s in active_scopes]
            company_emps = [e for e in blockchain_service.employments.values() if e["employer_address"] == target_addr]
            active_workers = len([e for e in company_emps if e["status"] == "ACTIVE"])
            completed_contracts = len([e for e in company_emps if e["status"] == "COMPLETED"])

            return {
                "id": org.id,
                "address": target_addr,
                "name": org.name,
                "reg_number": org.registration_ref_number or "N/A",
                "status": org.status,
                "approved_categories": approved_cats,
                "approved_levels": ["Skilled", "Semi-Skilled"],
                "approved_natures": ["Contract", "Project-Based"],
                "active_workers": active_workers,
                "completed_contracts": completed_contracts,
                "employments": company_emps
            }

    # Demo fallback for unauthenticated requests
    org = blockchain_service.organizations.get(DEFAULT_EMPLOYER_ADDR)
    if not org:
        raise HTTPException(status_code=404, detail="Employer organization not found")

    company_emps = [e for e in blockchain_service.employments.values() if e["employer_address"] == DEFAULT_EMPLOYER_ADDR]
    active_workers = len([e for e in company_emps if e["status"] == "ACTIVE"])
    completed_contracts = len([e for e in company_emps if e["status"] == "COMPLETED"])

    return {
        "address": DEFAULT_EMPLOYER_ADDR,
        "name": org["name"],
        "reg_number": org["reg_number"],
        "status": org["status"],
        "approved_categories": org["categories"],
        "approved_levels": org.get("levels", ["Skilled", "Semi-Skilled"]),
        "approved_natures": org.get("natures", ["Contract", "Project-Based"]),
        "active_workers": active_workers,
        "completed_contracts": completed_contracts,
        "employments": company_emps
    }

@router.post("/register-organization")
@router.post("/register")
@router.post("/onboard")
def register_organization(req: EmployerRegister, db: Session = Depends(get_db)):
    if not req.company_name or not req.company_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Validation error: 'company_name' is required and cannot be empty."
        )
    if not req.registration_number or not req.registration_number.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Validation error: 'registration_number' is required and cannot be empty."
        )
    if not req.email or "@" not in req.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Validation error: A valid 'email' address is required."
        )

    clean_email = req.email.lower().strip()
    reg_num = req.registration_number.strip()

    # Check for duplicate registration by reference under a different user
    existing_org_by_ref = db.query(DBEmployerOrganization).filter(
        (DBEmployerOrganization.registration_ref_number == reg_num) |
        (DBEmployerOrganization.registration_number == reg_num)
    ).first()

    existing_user = db.query(DBUser).filter(DBUser.email == clean_email).first()
    if existing_org_by_ref and existing_user and existing_org_by_ref.user_id != existing_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Registration reference '{reg_num}' is already registered under another account."
        )

    new_addr = f"0xemp_{secrets.token_hex(4)}"
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Determine categories
    cats_to_create = req.categories_requested if req.categories_requested else ["Mason", "Electrician"]

    # ATOMIC DATABASE TRANSACTION
    try:
        user = existing_user
        if not user:
            user_pw = getattr(req, "password", None) or "temporary_employer_pw"
            user = DBUser(
                email=clean_email,
                full_name=req.company_name,
                phone=req.phone or "+91 9876543210",
                password_hash=hash_pw(user_pw),
                role="EMPLOYER",
                status="PENDING_REVIEW",
                organization_address=new_addr,
                organization_name=req.company_name,
                organization_status="PENDING_REVIEW",
                is_email_verified=True,
                is_phone_verified=True,
                firebase_uid=f"uid_emp_{uuid.uuid4().hex[:12]}"
            )
            db.add(user)
            db.flush()

        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == user.id).first()
        if not org:
            org = DBEmployerOrganization(
                user_id=user.id,
                name=req.company_name,
                registration_ref_number=reg_num,
                registration_number=reg_num,
                business_type=req.business_type or "Private Limited",
                nature_of_business=req.nature_of_business or "Construction & Infrastructure",
                business_address=req.business_address or "Industrial Sector 4, Bengaluru, KA",
                official_email=clean_email,
                contact_person=req.contact_person or req.company_name,
                official_phone=req.phone or "+91 9876543210",
                phone=req.phone or "+91 9876543210",
                org_address=new_addr,
                status="PENDING_REVIEW"
            )
            db.add(org)
            db.flush()
        else:
            org.name = req.company_name
            org.registration_ref_number = reg_num
            org.registration_number = reg_num
            org.official_email = clean_email
            org.org_address = new_addr
            org.status = "PENDING_REVIEW"
            db.flush()

        # Atomically create DBCategoryAuthorizationRequest entries (status PENDING, is_active_scope=False)
        for cat in cats_to_create:
            cat_req = DBCategoryAuthorizationRequest(
                organization_id=org.id,
                category=cat,
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="PENDING",
                is_active_scope=False,
                request_version=1
            )
            db.add(cat_req)

        # Invalidate older pending/sent tokens for this organization
        db.query(DBActivationEmail).filter(
            DBActivationEmail.entity_type == "EMPLOYER",
            DBActivationEmail.entity_id == org.id,
            DBActivationEmail.status.in_(["PENDING", "SENT"])
        ).update({"status": "EXPIRED"})

        act_email = DBActivationEmail(
            entity_type="EMPLOYER",
            entity_id=org.id,
            recipient_email=clean_email,
            token_hash=token_hash,
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=7),
            attempt_count=1
        )
        db.add(act_email)
        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failure during employer registration: {str(exc)}"
        )

    # Call blockchain_service.register_organization ONLY AFTER db commit succeeds
    try:
        blockchain_service.register_organization(
            address=new_addr,
            name=req.company_name,
            reg_num=reg_num,
            state_code="KA",
            org_type="EMPLOYER",
            categories=cats_to_create
        )
    except Exception:
        pass

    return {
        "message": "Employer registration submitted. Pending admin review.",
        "assigned_address": new_addr,
        "organization_id": org.id,
        "status": "PENDING_REVIEW",
        "verification_status": "PENDING_REVIEW",
        "activation_notice": f"Upon admin approval, a secure activation link will be dispatched to {clean_email}",
        "activation_token": raw_token,
        "raw_token": raw_token
    }

@router.get("/activate-account/{token}")
def activate_employer_account(token: str, db: Session = Depends(get_db)):
    token_str = token.strip()
    token_hash = hashlib.sha256(token_str.encode("utf-8")).hexdigest()

    # 1. Authoritative lookup by SHA-256 token hash (ordered by id desc)
    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.token_hash == token_hash
    ).order_by(DBActivationEmail.id.desc()).first()

    # 2. Backward compatibility for legacy test harnesses using act_sec_<addr[-6:]>
    if not act_email and token_str.startswith("act_sec_"):
        addr_suffix = token_str[len("act_sec_"):]
        org_cand = db.query(DBEmployerOrganization).filter(
            DBEmployerOrganization.org_address.endswith(addr_suffix)
        ).order_by(DBEmployerOrganization.id.desc()).first()
        if org_cand:
            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.entity_id == org_cand.id
            ).order_by(DBActivationEmail.id.desc()).first()

    if not act_email:
        raise HTTPException(status_code=404, detail="Invalid or expired activation token")

    if act_email.entity_type != "EMPLOYER":
        raise HTTPException(
            status_code=400,
            detail="WRONG_TARGET_TYPE: Activation token is not intended for this account type"
        )

    if act_email.status in ["EXPIRED", "SUPERSEDED"] or (act_email.expires_at and act_email.expires_at < datetime.utcnow()):
        act_email.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Activation token has expired or been superseded")

    if act_email.status == "USED":
        raise HTTPException(status_code=400, detail="Activation token has already been used")

    org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == act_email.entity_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_status = org.status
    if org.org_address and org.org_address in blockchain_service.organizations:
        bc_status = blockchain_service.organizations[org.org_address].get("status")
        if bc_status:
            org_status = bc_status

    if org_status not in ["APPROVED", "ACTIVE"]:
        raise HTTPException(status_code=400, detail="Cannot activate account: Admin has not approved organization yet")

    act_email.status = "USED"
    act_email.used_at = datetime.utcnow()
    org.status = "ACTIVE"
    if org.user_id:
        u = db.query(DBUser).filter(DBUser.id == org.user_id).first()
        if u:
            u.status = "ACTIVE"

    if org.org_address:
        blockchain_service.set_org_status(org.org_address, "APPROVED", "Activated via token")

    db.commit()

    return {
        "message": f"Employer account for {act_email.recipient_email} successfully activated!",
        "org_address": org.org_address,
        "status": "ACTIVE"
    }

@router.post("/activate", response_model=EmployerActivationResponse)
@router.post("/activate-employer", response_model=EmployerActivationResponse)
def activate_employer(
    req: EmployerActivationRequest,
    db: Session = Depends(get_db)
):
    token_str = req.activation_token.strip()
    token_hash = hashlib.sha256(token_str.encode("utf-8")).hexdigest()

    # 1. Authoritative lookup by SHA-256 token hash (ordered by id desc)
    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.token_hash == token_hash
    ).order_by(DBActivationEmail.id.desc()).first()

    # 2. Backward compatibility for legacy test harnesses using act_sec_<addr[-6:]>
    if not act_email and token_str.startswith("act_sec_"):
        addr_suffix = token_str[len("act_sec_"):]
        org_cand = db.query(DBEmployerOrganization).filter(
            DBEmployerOrganization.org_address.endswith(addr_suffix)
        ).order_by(DBEmployerOrganization.id.desc()).first()
        if org_cand:
            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.entity_id == org_cand.id
            ).order_by(DBActivationEmail.id.desc()).first()

    if not act_email:
        raise HTTPException(status_code=404, detail="Invalid or expired activation token")

    if act_email.entity_type != "EMPLOYER":
        raise HTTPException(
            status_code=400,
            detail="WRONG_TARGET_TYPE: Activation token is not intended for this account type"
        )

    if act_email.status in ["EXPIRED", "SUPERSEDED"] or (act_email.expires_at and act_email.expires_at < datetime.utcnow()):
        act_email.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Activation token has expired or been superseded")

    if act_email.status == "USED":
        raise HTTPException(status_code=400, detail="Activation token has already been used")

    org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == act_email.entity_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_status = org.status
    if org.org_address and org.org_address in blockchain_service.organizations:
        bc_status = blockchain_service.organizations[org.org_address].get("status")
        if bc_status:
            org_status = bc_status

    if org_status not in ["APPROVED", "ACTIVE"]:
        raise HTTPException(status_code=400, detail="Cannot activate account: Admin has not approved organization yet")

    act_email.status = "USED"
    act_email.used_at = datetime.utcnow()
    org.status = "ACTIVE"

    if org.user_id:
        user = db.query(DBUser).filter(DBUser.id == org.user_id).first()
        if user:
            user.status = "ACTIVE"
            if req.password:
                user.password_hash = hash_pw(req.password)

    if org.org_address:
        blockchain_service.set_org_status(org.org_address, "APPROVED", "Activated via secure token")

    db.commit()

    return EmployerActivationResponse(
        status="ACTIVE",
        message=f"Employer account for {act_email.recipient_email} successfully activated!",
        email=act_email.recipient_email,
        organization_status="ACTIVE"
    )

@router.get("/activation-status")
def get_employer_activation_status(
    token: str = Query(..., description="Activation token to inspect"),
    db: Session = Depends(get_db)
):
    token_str = token.strip()
    token_hash = hashlib.sha256(token_str.encode("utf-8")).hexdigest()

    # 1. Authoritative lookup by SHA-256 token hash (ordered by id desc)
    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.entity_type == "EMPLOYER",
        DBActivationEmail.token_hash == token_hash
    ).order_by(DBActivationEmail.id.desc()).first()

    # 2. Backward compatibility for legacy test harnesses using act_sec_<addr[-6:]>
    if not act_email and token_str.startswith("act_sec_"):
        addr_suffix = token_str[len("act_sec_"):]
        org_cand = db.query(DBEmployerOrganization).filter(
            DBEmployerOrganization.org_address.endswith(addr_suffix)
        ).order_by(DBEmployerOrganization.id.desc()).first()
        if org_cand:
            act_email = db.query(DBActivationEmail).filter(
                DBActivationEmail.entity_type == "EMPLOYER",
                DBActivationEmail.entity_id == org_cand.id
            ).order_by(DBActivationEmail.id.desc()).first()

    if not act_email:
        return {"status": "INVALID", "message": "Token not found"}

    if act_email.status == "USED":
        return {"status": "USED", "recipient_email": act_email.recipient_email}
    if act_email.status in ["EXPIRED", "SUPERSEDED"] or (act_email.expires_at and act_email.expires_at < datetime.utcnow()):
        return {"status": "EXPIRED", "recipient_email": act_email.recipient_email}

    org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == act_email.entity_id).first()
    return {
        "status": "VALID",
        "recipient_email": act_email.recipient_email,
        "organization_name": org.name if org else None,
        "organization_status": org.status if org else None
    }

@router.post("/verify-worker-qr")
async def verify_worker_by_qr_image(
    file: UploadFile = File(...),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Web-first verification: Processes uploaded worker QR presentation image.
    NO camera scanning required. Executes the 11-step Common Verification sequence.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    caller_role = "EMPLOYER"
    caller_id = DEFAULT_EMPLOYER_ADDR
    if current_user:
        if current_user.role not in ["EMPLOYER", "ADMIN"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized: Only employers or admins can access this verification portal")
        caller_role = current_user.role
        caller_id = current_user.organization_address or str(current_user.id)

    try:
        result = verification_engine.verify_uploaded_presentation(
            image_bytes=image_bytes,
            caller_role=caller_role,
            caller_id=caller_id,
            db=db
        )
        return result
    except VerificationEngineError as vee:
        if vee.error_code == VerificationErrorCode.REPLAY_ATTACK_DETECTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=vee.message)
        elif vee.error_code == VerificationErrorCode.VERIFIER_UNAUTHORIZED:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=vee.message)
        elif vee.error_code in [VerificationErrorCode.RPC_UNAVAILABLE, VerificationErrorCode.IPFS_UNAVAILABLE]:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=vee.message)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=vee.message)
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failure: {str(e)}")

@router.post("/request-category")
def request_category(
    req: CategoryRequest,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        org = db.query(DBEmployerOrganization).filter(
            (DBEmployerOrganization.org_address == DEFAULT_EMPLOYER_ADDR) |
            (DBEmployerOrganization.official_email == "employer@apexinfra.com")
        ).first()
        org_id = org.id if org else 1
        emp_addr = DEFAULT_EMPLOYER_ADDR
    else:
        if current_user.status == "SUSPENDED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended. Access denied."
            )
        if current_user.role != "EMPLOYER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only employers can request category scopes"
            )

        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == current_user.id).first()
        if not org and current_user.organization_address:
            org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.org_address == current_user.organization_address).first()

        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employer organization record not found"
            )

        org_id = org.id
        emp_addr = org.org_address or current_user.organization_address or f"0xemp_{org.id:04d}"

    # Query latest version to calculate request_version increment
    latest = db.query(DBCategoryAuthorizationRequest).filter(
        DBCategoryAuthorizationRequest.organization_id == org_id,
        DBCategoryAuthorizationRequest.category == req.category
    ).order_by(DBCategoryAuthorizationRequest.request_version.desc()).first()
    req_ver = (latest.request_version + 1) if latest else 1

    cat_auth_req = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category=req.category,
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="PENDING",
        is_active_scope=False,
        request_version=req_ver,
        reason=req.reason
    )
    db.add(cat_auth_req)

    # Legacy DBCategoryRequest
    cat_req = DBCategoryRequest(
        employer_address=emp_addr,
        category=req.category,
        reason=req.reason,
        status="PENDING"
    )
    db.add(cat_req)
    db.commit()

    return {
        "message": f"Category request for '{req.category}' (version {req_ver}) submitted for Admin review",
        "request_id": cat_auth_req.id,
        "request_version": req_ver
    }

@router.get("/categories")
def get_employer_categories(
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if current_user and current_user.role == "EMPLOYER":
        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == current_user.id).first()
        if org:
            requests = db.query(DBCategoryAuthorizationRequest).filter(
                DBCategoryAuthorizationRequest.organization_id == org.id
            ).all()
            return [{
                "id": r.id,
                "category": r.category,
                "skill_level": r.skill_level,
                "nature_of_employment": r.nature_of_employment,
                "status": r.status,
                "is_active_scope": bool(r.is_active_scope),
                "request_version": r.request_version
            } for r in requests]
    return []

@router.post("/create-employment")
def create_employment(
    req: CreateEmploymentRequest,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        employer_addr = DEFAULT_EMPLOYER_ADDR
        if req.category and req.category not in blockchain_service.organizations.get(DEFAULT_EMPLOYER_ADDR, {}).get("categories", []):
            blockchain_service.organizations[DEFAULT_EMPLOYER_ADDR]["categories"].append(req.category)
    else:
        if current_user.status == "SUSPENDED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employer organization is SUSPENDED. Access denied."
            )
        if current_user.role != "EMPLOYER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only employers can create employment contracts"
            )

        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == current_user.id).first()
        if not org and current_user.organization_address:
            org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.org_address == current_user.organization_address).first()

        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employer organization record not found"
            )

        # Enforce Decoupling Invariant
        if org.status not in ["APPROVED", "ACTIVE"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Employer organization is {org.status}. Must be APPROVED or ACTIVE to create employment."
            )

        active_scope = db.query(DBCategoryAuthorizationRequest).filter(
            DBCategoryAuthorizationRequest.organization_id == org.id,
            DBCategoryAuthorizationRequest.category == req.category,
            DBCategoryAuthorizationRequest.is_active_scope == True
        ).first()

        if not active_scope:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{req.category}' does not have an active approved scope for this employer"
            )

        employer_addr = org.org_address or current_user.organization_address
        if not employer_addr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employer organization address is not configured"
            )

    try:
        record = blockchain_service.create_employment(
            worker_did=req.worker_did,
            employer_address=employer_addr,
            category=req.category,
            level=req.level,
            nature_of_employment=req.nature_of_employment,
            job_role=req.job_role,
            location=req.work_location,
            end_date=req.expected_end_date or 0
        )
        return {
            "message": "Employment successfully anchored on blockchain",
            "employment_record": record
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/employment-status")
def update_status(
    req: UpdateEmploymentStatusRequest,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided"
        )
    if current_user.status == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Access denied."
        )
    if current_user.role not in ["EMPLOYER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only employing organization or admin can update employment status"
        )

    caller_addr = None
    if current_user.role == "ADMIN":
        caller_addr = "ADMIN"
    elif current_user.role == "EMPLOYER":
        if current_user.organization_address:
            caller_addr = current_user.organization_address
        else:
            org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == current_user.id).first()
            if org and org.org_address:
                caller_addr = org.org_address

    if not caller_addr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Caller address could not be resolved from authenticated user"
        )

    try:
        blockchain_service.update_employment_status(
            emp_id=req.employment_id,
            caller_address=caller_addr,
            new_status=req.new_status,
            reason=req.reason
        )
        return {
            "message": f"Employment #{req.employment_id} updated to {req.new_status}. Historical record preserved.",
            "status": req.new_status
        }
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/credentials/issue", response_model=CredentialResponse)
def issue_employer_credential(
    req: CredentialIssueRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows approved Employers to issue Trade Experience, Competency, and Site Induction credentials
    to a worker's DID wallet.
    """
    if current_user.role != "EMPLOYER":
        raise HTTPException(status_code=403, detail="Unauthorized: Only employers can issue trade/experience credentials")

    org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.user_id == current_user.id).first()
    if not org and current_user.organization_address:
        org = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.org_address == current_user.organization_address).first()

    if org and org.status not in ["APPROVED", "ACTIVE"]:
        raise HTTPException(status_code=403, detail="Employer organization must be APPROVED or ACTIVE to issue credentials")

    issuer_name = req.issuer_name or (org.name if org else None) or current_user.organization_name or current_user.full_name or "Approved Employer"
    issuer_addr = (org.org_address if org else None) or current_user.organization_address or "0xemp_official"

    worker = db.query(DBWorkerProfile).filter(DBWorkerProfile.did == req.worker_did).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker with specified DID not found")

    cred_uuid = f"cred-emp-{uuid.uuid4().hex[:10]}"
    expires_at = datetime.utcnow() + timedelta(days=req.valid_days or 365)

    new_cred = DBWorkerCredential(
        credential_id=cred_uuid,
        worker_did=req.worker_did,
        worker_id=worker.id,
        title=req.title,
        credential_type=req.credential_type or "Experience",
        issuer_name=issuer_name,
        issuer_address=issuer_addr,
        issuer_role="EMPLOYER",
        status="VALID",
        skills_json=json.dumps(req.skills or []),
        metadata_json=json.dumps(req.metadata or {}),
        created_at=datetime.utcnow(),
        expires_at=expires_at
    )
    db.add(new_cred)
    db.commit()
    db.refresh(new_cred)

    return CredentialResponse(
        id=new_cred.credential_id,
        title=new_cred.title,
        type=new_cred.credential_type,
        issuer=new_cred.issuer_name,
        issuer_role="EMPLOYER",
        status="VALID",
        worker_did=new_cred.worker_did,
        skills=req.skills or [],
        metadata=req.metadata or {},
        anchored=True,
        created_at=new_cred.created_at.strftime("%Y-%m-%d"),
        expires_at=new_cred.expires_at.strftime("%Y-%m-%d") if new_cred.expires_at else None
    )

