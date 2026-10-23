import json
import time
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Header, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.db import (
    get_db,
    DBUser,
    DBGovernmentOfficer,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBAdminAuditLog,
    DBWorkerCredential,
    DBWorkerProfile
)
from app.models.schemas import (
    WelfareClaimRequest,
    GovernmentActivationRequest,
    GovernmentActivationStatusResponse,
    DisputeCreateRequest,
    DisputeResolutionRequest,
    DisputeResolutionResponse,
    CredentialIssueRequest,
    CredentialResponse
)
from app.core.auth import get_current_user, get_current_government_officer
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

def log_gov_audit(
    db: Session,
    actor: DBUser,
    action: str,
    target_type: str,
    target_id: str,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    reason: Optional[str] = None
):
    audit = DBGovernanceAuditLog(
        actor_firebase_uid=actor.firebase_uid or f"uid_user_{actor.id}",
        actor_user_id=actor.id if actor.id else None,
        actor_role=actor.role,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        previous_state=str(previous_state) if previous_state is not None else None,
        new_state=str(new_state) if new_state is not None else None,
        reason=reason,
        request_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.flush()
    return audit

router = APIRouter()

DEFAULT_GOV_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
DEFAULT_OFFICER_STATE = "Maharashtra"


# ============================================================================
# 1. OFFICER ACTIVATION LIFECYCLE
# ============================================================================

@router.post("/activate")
def activate_government_officer(
    req: GovernmentActivationRequest,
    db: Session = Depends(get_db)
):
    raw_token = req.activation_token.strip()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.token_hash == token_hash
    ).first()

    if not act_email:
        raise HTTPException(status_code=404, detail="Invalid activation token")

    if act_email.entity_type != "GOVERNMENT":
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

    officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == act_email.entity_id).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Government officer record not found")

    # Transition to ACTIVE
    previous_state = officer.status
    act_email.status = "USED"
    act_email.used_at = datetime.utcnow()
    officer.status = "ACTIVE"

    user = None
    if officer.user_id:
        user = db.query(DBUser).filter(DBUser.id == officer.user_id).first()
        if user:
            user.status = "ACTIVE"
            if req.password:
                user.password_hash = hash_pw(req.password)

    if officer.wallet_address:
        blockchain_service.organizations[officer.wallet_address] = {
            "id": officer.id,
            "name": officer.department or officer.officer_name or officer.full_name,
            "reg_number": officer.officer_reference_id,
            "state_code": officer.state or "ALL",
            "org_type": "GOVERNMENT",
            "status": "APPROVED",
            "categories": [],
            "levels": [],
            "natures": [],
            "registered_at": int(time.time())
        }

    log_gov_audit(
        db=db,
        actor=user or DBUser(id=0, role="GOVERNMENT", firebase_uid="sys"),
        action="GOVERNMENT_OFFICER_ACTIVATED",
        target_type="GOVERNMENT_OFFICER",
        target_id=str(officer.id),
        previous_state=previous_state,
        new_state="ACTIVE",
        reason="Officer redeemed single-use activation token"
    )

    db.commit()

    return {
        "status": "ACTIVE",
        "message": f"Government officer account for {act_email.recipient_email} successfully activated!",
        "officer_reference_id": officer.officer_reference_id,
        "full_name": officer.full_name
    }


@router.get("/activation-status", response_model=GovernmentActivationStatusResponse)
def get_officer_activation_status(
    token: str = Query(..., description="Activation token to inspect"),
    db: Session = Depends(get_db)
):
    raw_token = token.strip()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    act_email = db.query(DBActivationEmail).filter(
        DBActivationEmail.token_hash == token_hash
    ).first()

    if not act_email or act_email.entity_type != "GOVERNMENT":
        return GovernmentActivationStatusResponse(status="INVALID")

    if act_email.status == "USED":
        return GovernmentActivationStatusResponse(status="USED", official_email=act_email.recipient_email)

    if act_email.status in ["EXPIRED", "SUPERSEDED"] or (act_email.expires_at and act_email.expires_at < datetime.utcnow()):
        return GovernmentActivationStatusResponse(status="EXPIRED", official_email=act_email.recipient_email)

    officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == act_email.entity_id).first()
    return GovernmentActivationStatusResponse(
        status="VALID",
        officer_name=officer.officer_name if officer else None,
        official_email=act_email.recipient_email,
        department=officer.department if officer else None,
        designation=officer.designation if officer else None,
        authority_level=officer.authority_level if officer else None,
        state=officer.state if officer else None,
        district=officer.district if officer else None
    )


# ============================================================================
# 2. OFFICER SELF-SERVICE & PORTAL CONTEXT
# ============================================================================

@router.get("/profile/me")
def get_officer_profile_me(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["GOVERNMENT", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only government officers can access this portal"
        )

    officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.user_id == current_user.id).first()
    if not officer and current_user.email:
        officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.official_email == current_user.email).first()

    if not officer:
        # Fallback to current user context
        return {
            "user_id": current_user.id,
            "full_name": current_user.full_name,
            "official_email": current_user.email,
            "authority_level": "STATE",
            "state": "Maharashtra",
            "district": None,
            "block": None,
            "permissions": ["WORKER_VERIFICATION", "DISBURSE_BENEFIT"],
            "benefit_permissions": ["1", "2"],
            "status": current_user.status or "ACTIVE"
        }

    try:
        perms = json.loads(officer.permissions_json) if officer.permissions_json else []
    except Exception:
        perms = []
    try:
        b_perms = json.loads(officer.benefit_permissions_json) if officer.benefit_permissions_json else []
    except Exception:
        b_perms = []

    return {
        "id": officer.id,
        "user_id": officer.user_id,
        "officer_reference_id": officer.officer_reference_id,
        "officer_name": officer.officer_name,
        "full_name": officer.full_name,
        "official_email": officer.official_email,
        "phone": officer.phone,
        "department": officer.department,
        "designation": officer.designation,
        "authority_level": officer.authority_level,
        "state": officer.state,
        "district": officer.district,
        "block": officer.block,
        "wallet_address": officer.wallet_address,
        "permissions": perms,
        "benefit_permissions": b_perms,
        "status": officer.status,
        "created_at": officer.created_at,
        "last_login_at": officer.last_login_at
    }


@router.get("/info")
def get_gov_info(
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    # Dynamic derivation from authenticated officer
    if current_user and current_user.role == "GOVERNMENT":
        officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.user_id == current_user.id).first()
        if not officer and current_user.email:
            officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.official_email == current_user.email).first()

        if officer:
            officer_state = officer.state or "National"
            officer_wallet = officer.wallet_address or current_user.organization_address or DEFAULT_GOV_ADDR
            department_name = officer.department or current_user.organization_name or "Government Welfare Dept"

            # Filter claims by officer state if state is defined
            all_claims = list(blockchain_service.claims.values())
            if officer.state:
                state_claims = [c for c in all_claims if c.get("officer_state") == officer.state]
            else:
                state_claims = all_claims

            total_claims = len(state_claims)
            total_disbursed = sum(c.get("amount", 0) for c in state_claims)

            return {
                "address": officer_wallet,
                "department_name": department_name,
                "state": officer_state,
                "district": officer.district,
                "authority_level": officer.authority_level,
                "schemes": list(blockchain_service.schemes.values()),
                "total_claims_recorded": total_claims,
                "total_disbursed_inr": total_disbursed,
                "all_claims": state_claims[::-1]
            }

    # Demo fallback for unauthenticated requests
    org = blockchain_service.organizations.get(DEFAULT_GOV_ADDR)
    schemes = list(blockchain_service.schemes.values())
    total_claims = len(blockchain_service.claims)
    total_disbursed = sum(c["amount"] for c in blockchain_service.claims.values())

    return {
        "address": DEFAULT_GOV_ADDR,
        "department_name": org["name"] if org else "Government Welfare Dept",
        "state": DEFAULT_OFFICER_STATE,
        "schemes": schemes,
        "total_claims_recorded": total_claims,
        "total_disbursed_inr": total_disbursed,
        "all_claims": list(blockchain_service.claims.values())[::-1]
    }


# ============================================================================
# 3. VERIFICATION & BENEFIT DISBURSEMENT GATING
# ============================================================================

@router.post("/verify-worker-qr")
@router.post("/verify-worker")
async def verify_worker_by_qr_image(
    file: UploadFile = File(...),
    officer: DBGovernmentOfficer = Depends(get_current_government_officer),
    db: Session = Depends(get_db)
):
    """
    Government worker verification via drag-and-drop QR image upload.
    Identifies interstate migration status and cross-references origin-state KYC records.
    Executes the canonical 11-step Common Verification sequence.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    caller_role = "GOVERNMENT"
    caller_id = str(officer.id)

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
        elif vee.error_code in [
            VerificationErrorCode.VERIFIER_UNAUTHORIZED,
            getattr(VerificationErrorCode, "OFFICER_INACTIVE", None),
            getattr(VerificationErrorCode, "OFFICER_SUSPENDED", None),
            getattr(VerificationErrorCode, "PERMISSION_DENIED", None),
            getattr(VerificationErrorCode, "FORBIDDEN_PERMISSION", None),
            getattr(VerificationErrorCode, "ACCOUNT_INACTIVE", None),
            getattr(VerificationErrorCode, "JURISDICTION_MISMATCH", None)
        ] or vee.detail in [
            "OFFICER_INACTIVE",
            "OFFICER_SUSPENDED",
            "PERMISSION_DENIED",
            "FORBIDDEN_PERMISSION",
            "ACCOUNT_INACTIVE",
            "JURISDICTION_MISMATCH"
        ]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=vee.message)
        elif vee.error_code == getattr(VerificationErrorCode, "OFFICER_NOT_FOUND", None) or vee.detail == "OFFICER_NOT_FOUND":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=vee.message)
        elif vee.error_code in [VerificationErrorCode.RPC_UNAVAILABLE, VerificationErrorCode.IPFS_UNAVAILABLE]:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=vee.message)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=vee.message)
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failure: {str(e)}")


@router.get("/schemes")
def list_welfare_schemes():
    return list(blockchain_service.schemes.values())


@router.post("/disburse-claim")
def disburse_welfare_claim(
    req: WelfareClaimRequest,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if req.scheme_id not in blockchain_service.schemes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scheme ID {req.scheme_id} or Scheme not active"
        )

    officer = None
    if not current_user:
        if not req.gov_officer_wallet:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided"
            )
        gov_wallet = req.gov_officer_wallet
        officer_state = req.officer_state or DEFAULT_OFFICER_STATE
    else:
        if current_user.role not in ["GOVERNMENT", "ADMIN"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only government officers or admins can disburse welfare claims"
            )
        if current_user.status not in ["ACTIVE", "APPROVED"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is {current_user.status}. Access denied."
            )

        officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.user_id == current_user.id).first()
        if not officer and current_user.email:
            officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.official_email == current_user.email).first()

        gov_wallet = None
        officer_state = req.officer_state or DEFAULT_OFFICER_STATE

        if officer:
            if officer.status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Officer account is {officer.status}. Disbursement denied."
                )

            # Check permissions
            try:
                perms = json.loads(officer.permissions_json) if officer.permissions_json else []
            except Exception:
                perms = []
            if perms and "DISBURSE_BENEFIT" not in perms:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Officer lacks 'DISBURSE_BENEFIT' permission"
                )

            # Check benefit_permissions_json
            try:
                b_perms = json.loads(officer.benefit_permissions_json) if officer.benefit_permissions_json else []
            except Exception:
                b_perms = []

            scheme_id_str = str(req.scheme_id).strip()
            scheme_obj = blockchain_service.schemes.get(req.scheme_id, {})
            scheme_name = scheme_obj.get("name", "")
            scheme_name_lower = scheme_name.strip().lower()

            norm_b_perms = set(str(p).strip().lower() for p in b_perms if p)
            has_wildcard = not norm_b_perms or "all" in norm_b_perms or "*" in norm_b_perms

            if not has_wildcard:
                # Semantic mapping between admin permission vocabulary and on-chain schemes
                scheme_1_aliases = {
                    "1", "scheme_1", "interstate migrant worker relief scheme",
                    "emergency_relief", "ration_benefit", "housing_subsidy"
                }
                scheme_2_aliases = {
                    "2", "scheme_2", "bocw safety & skill empowerment grant",
                    "bocw_grant", "healthcare_assistance", "education_grant"
                }

                is_authorized = False
                if scheme_id_str.lower() in norm_b_perms or scheme_name_lower in norm_b_perms:
                    is_authorized = True
                elif req.scheme_id == 1 and norm_b_perms.intersection(scheme_1_aliases):
                    is_authorized = True
                elif req.scheme_id == 2 and norm_b_perms.intersection(scheme_2_aliases):
                    is_authorized = True

                if not is_authorized:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Officer is not authorized to disburse benefit scheme #{req.scheme_id} ('{scheme_name}')"
                    )

            # Enforce geographic jurisdiction
            off_lvl = (officer.authority_level or "NATIONAL").upper()
            if off_lvl == "NATIONAL":
                pass
            elif off_lvl in ["STATE", "DISTRICT", "BLOCK"]:
                if req.officer_state and req.officer_state != officer.state:
                    if "CROSS_STATE_VERIFICATION" not in perms:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Officer in state '{officer.state}' cannot disburse under '{req.officer_state}'. Cross-state verification permission required."
                        )

            gov_wallet = officer.wallet_address or current_user.organization_address or getattr(req, "officer_wallet", None) or req.gov_officer_wallet or DEFAULT_GOV_ADDR
            officer_state = officer.state or req.officer_state or DEFAULT_OFFICER_STATE

            # Automatically ensure active government officer is registered and approved in blockchain_service
            if gov_wallet not in blockchain_service.organizations:
                blockchain_service.organizations[gov_wallet] = {
                    "id": officer.id,
                    "name": officer.department or officer.officer_name or officer.full_name,
                    "reg_number": officer.officer_reference_id,
                    "state_code": officer.state or "ALL",
                    "org_type": "GOVERNMENT",
                    "status": "APPROVED",
                    "categories": [],
                    "levels": [],
                    "natures": [],
                    "registered_at": int(time.time())
                }
        else:
            gov_wallet = current_user.organization_address or getattr(req, "officer_wallet", None) or req.gov_officer_wallet or (DEFAULT_GOV_ADDR if current_user.role == "GOVERNMENT" else "0x90F79bf6EB2c4f870365E785982E1f101E93b906")
            officer_state = req.officer_state or DEFAULT_OFFICER_STATE

    # On-chain / in-memory wallet registration check
    if not blockchain_service.is_org_approved(gov_wallet):
        if officer and officer.status == "ACTIVE":
            blockchain_service.organizations[gov_wallet] = {
                "id": officer.id,
                "name": officer.department or officer.officer_name or officer.full_name,
                "reg_number": officer.officer_reference_id,
                "state_code": officer.state or "ALL",
                "org_type": "GOVERNMENT",
                "status": "APPROVED",
                "categories": [],
                "levels": [],
                "natures": [],
                "registered_at": int(time.time())
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Government officer wallet is not registered or approved on-chain"
            )

    try:
        claim = blockchain_service.record_welfare_claim(
            scheme_id=req.scheme_id,
            worker_did=req.worker_did,
            gov_address=gov_wallet,
            officer_state=officer_state
        )

        log_gov_audit(
            db=db,
            actor=current_user or DBUser(id=0, role="GOVERNMENT", firebase_uid="sys"),
            action="DISBURSE_WELFARE_CLAIM",
            target_type="WELFARE_CLAIM",
            target_id=str(claim.get("claim_id") or claim.get("id", "0")),
            previous_state="PENDING",
            new_state="DISBURSED",
            reason=f"Claim disbursed under scheme #{req.scheme_id} ({officer_state})"
        )
        db.commit()

        return {
            "message": "Benefit disbursement record successfully anchored on blockchain",
            "claim_record": claim
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# 4. DISPUTE MEDIATION & ADJUDICATION
# ============================================================================

@router.post("/disputes", response_model=DisputeResolutionResponse)
@router.post("/resolve-dispute", response_model=DisputeResolutionResponse)
def resolve_employment_dispute(
    req: DisputeResolutionRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["GOVERNMENT", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only government officers or admins can adjudicate disputes"
        )

    emp_id = req.employment_id or 1
    if emp_id not in blockchain_service.employments:
        raise HTTPException(status_code=404, detail=f"Employment contract #{emp_id} not found")

    emp = blockchain_service.employments[emp_id]
    prev_status = emp["status"]

    # Update employment status in blockchain_service
    emp["status"] = req.resolution_status.upper()
    emp["status_reason"] = req.resolution_notes

    # Append event to employmentEvents
    if emp_id not in blockchain_service.employment_events:
        blockchain_service.employment_events[emp_id] = []
    blockchain_service.employment_events[emp_id].append({
        "status": req.resolution_status.upper(),
        "reason": req.resolution_notes,
        "adjudicated_by": current_user.full_name or current_user.email,
        "settlement_amount_inr": req.settlement_amount_inr,
        "timestamp": int(datetime.utcnow().timestamp())
    })

    log_gov_audit(
        db=db,
        actor=current_user,
        action="RESOLVE_EMPLOYMENT_DISPUTE",
        target_type="EMPLOYMENT_CONTRACT",
        target_id=str(emp_id),
        previous_state=prev_status,
        new_state=req.resolution_status.upper(),
        reason=f"Dispute resolved with determination: {req.resolution_notes}"
    )
    db.commit()

    return DisputeResolutionResponse(
        success=True,
        employment_id=emp_id,
        new_status=req.resolution_status.upper(),
        resolution_notes=req.resolution_notes,
        settlement_amount_inr=req.settlement_amount_inr or 0.0,
        adjudicated_by=current_user.full_name or current_user.email,
        adjudicated_at=datetime.utcnow()
    )


@router.post("/credentials/issue", response_model=CredentialResponse)
def issue_government_credential(
    req: CredentialIssueRequest,
    current_user: DBUser = Depends(get_current_government_officer),
    db: Session = Depends(get_db)
):
    """
    Allows authorized Government Officers to issue official W3C Verifiable Credentials
    (e.g., BOCW Social Security, Trade Skill Certification, Health/Safety Clearance, Inter-State Migrant Permit)
    directly to a worker's DID wallet.
    """
    officer = db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.user_id == current_user.id).first()
    issuer_name = req.issuer_name or (officer.department if officer else None) or current_user.full_name or "Government Authority"
    issuer_addr = (officer.wallet_address if officer else None) or current_user.organization_address or "0xgov_official"

    # Verify worker exists and is valid
    worker = db.query(DBWorkerProfile).filter(DBWorkerProfile.did == req.worker_did).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker with specified DID not found")

    cred_uuid = f"cred-gov-{uuid.uuid4().hex[:10]}"
    expires_at = datetime.utcnow() + timedelta(days=req.valid_days or 365)

    new_cred = DBWorkerCredential(
        credential_id=cred_uuid,
        worker_did=req.worker_did,
        worker_id=worker.id,
        title=req.title,
        credential_type=req.credential_type or "Welfare",
        issuer_name=issuer_name,
        issuer_address=issuer_addr,
        issuer_role="GOVERNMENT",
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
        issuer_role="GOVERNMENT",
        status="VALID",
        worker_did=new_cred.worker_did,
        skills=req.skills or [],
        metadata=req.metadata or {},
        anchored=True,
        created_at=new_cred.created_at.strftime("%Y-%m-%d"),
        expires_at=new_cred.expires_at.strftime("%Y-%m-%d") if new_cred.expires_at else None
    )

