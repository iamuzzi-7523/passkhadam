import uuid
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.db import get_db, DBAadhaarRecord, DBAadhaarAuditLog
from app.core.config import settings
from app.services.aadhaar_service import aadhaar_authority
from app.models.schemas import (
    AadhaarVerifyRequest,
    AadhaarRecordCreate,
    AadhaarRecordUpdate,
    AadhaarRecordStatusUpdate,
    AadhaarRecordResponse,
    AadhaarVerifyServiceResponse,
    AadhaarAuditLogResponse
)

router = APIRouter()


# ============================================================================
# LIVE DASHBOARD & AUDIT LOGS
# ============================================================================

@router.get("/dashboard")
def get_aadhaar_dashboard(db: Session = Depends(get_db)):
    """Returns aggregated dashboard metrics computed directly from database."""
    return aadhaar_authority.get_dashboard_metrics(db=db)


@router.get("/logs", response_model=List[AadhaarAuditLogResponse])
def get_aadhaar_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    result_code: Optional[str] = Query(None),
    record_id: Optional[str] = Query(None),
    masked_aadhaar: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Inspects immutable append-only audit trail from DBAadhaarAuditLog.
    Supports filtering by result_code, record_id, and masked_aadhaar.
    """
    query = db.query(DBAadhaarAuditLog)
    if result_code:
        query = query.filter(DBAadhaarAuditLog.result_code == result_code)
    if record_id:
        query = query.filter(DBAadhaarAuditLog.record_id == record_id)
    if masked_aadhaar:
        query = query.filter(DBAadhaarAuditLog.masked_aadhaar == masked_aadhaar)

    logs = query.order_by(DBAadhaarAuditLog.id.desc()).offset(offset).limit(limit).all()
    return logs


# ============================================================================
# MOCK AADHAAR RECORD CRUD (SURROGATE UUID & URL PRIVACY BOUNDARY)
# ============================================================================

@router.post("/records", response_model=AadhaarRecordResponse, status_code=status.HTTP_201_CREATED)
def create_aadhaar_record(
    req: AadhaarRecordCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new demographic identity record in Mock Aadhaar Authority.
    Raw 12-digit Aadhaar is hashed with SHA-256 and never stored plaintext.
    Returns 201 Created with surrogate UUID record_id and masked representation.
    """
    clean_num = req.aadhaar_number
    a_hash = hashlib.sha256(clean_num.encode("utf-8")).hexdigest()

    # Reject duplicate Aadhaar hash
    existing = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.aadhaar_hash == a_hash).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aadhaar record with this number already exists"
        )

    rec_id = str(uuid.uuid4())
    masked = aadhaar_authority.mask_aadhaar(clean_num)
    rec_status = (req.status or "ACTIVE").upper()
    is_act = (rec_status == "ACTIVE")

    record = DBAadhaarRecord(
        record_id=rec_id,
        aadhaar_hash=a_hash,
        masked_aadhaar=masked,
        full_name=req.full_name,
        dob=req.dob,
        gender=req.gender,
        origin_state=req.origin_state,
        address=req.address,
        status=rec_status,
        is_active=is_act
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Sync to in-memory store for unit test backward compatibility
    aadhaar_authority._records[clean_num] = {
        "aadhaar_number": clean_num,
        "full_name": req.full_name,
        "dob": req.dob,
        "gender": req.gender,
        "origin_state": req.origin_state,
        "address": req.address,
        "is_active": is_act
    }

    return record


@router.get("/records", response_model=List[AadhaarRecordResponse])
def list_aadhaar_records(
    query: Optional[str] = Query(None, description="Search query by name, masked number, or record_id"),
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, INACTIVE, SUSPENDED"),
    origin_state: Optional[str] = Query(None, description="Filter by state of origin"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Lists and searches Mock Aadhaar records with pagination and filtering.
    Zero raw Aadhaar numbers exposed — strictly masked numbers returned.
    """
    q = db.query(DBAadhaarRecord)
    if query:
        pattern = f"%{query}%"
        q = q.filter(
            or_(
                DBAadhaarRecord.full_name.ilike(pattern),
                DBAadhaarRecord.masked_aadhaar.ilike(pattern),
                DBAadhaarRecord.record_id == query
            )
        )
    if status:
        q = q.filter(DBAadhaarRecord.status.ilike(status))
    if origin_state:
        q = q.filter(DBAadhaarRecord.origin_state.ilike(origin_state))

    records = q.order_by(DBAadhaarRecord.id.asc()).offset(offset).limit(limit).all()
    return records


@router.get("/records/{record_id}", response_model=AadhaarRecordResponse)
def get_aadhaar_record_by_id(
    record_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves demographic record by surrogate UUID.
    URL PRIVACY BOUNDARY: Strictly rejects raw 12-digit numbers in the URL path.
    """
    # URL Privacy Boundary: reject 12-digit Aadhaar in path parameter
    clean_id = "".join(filter(str.isdigit, record_id))
    if len(record_id.strip()) == 12 and record_id.strip().isdigit():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Raw 12-digit Aadhaar numbers in URL path parameters are strictly prohibited. Record not found."
        )

    record = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aadhaar record not found"
        )
    return record


@router.put("/records/{record_id}", response_model=AadhaarRecordResponse)
def update_aadhaar_record(
    record_id: str,
    req: AadhaarRecordUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates demographic fields of an existing Aadhaar record by surrogate UUID.
    Modifying aadhaar_number or record_id is strictly prohibited.
    """
    if len(record_id.strip()) == 12 and record_id.strip().isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Raw 12-digit Aadhaar numbers in URL path parameters are strictly prohibited. Use surrogate UUID record_id."
        )

    record = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aadhaar record not found"
        )

    if req.full_name is not None:
        record.full_name = req.full_name
    if req.dob is not None:
        record.dob = req.dob
    if req.gender is not None:
        record.gender = req.gender
    if req.origin_state is not None:
        record.origin_state = req.origin_state
    if req.address is not None:
        record.address = req.address
    if req.status is not None:
        record.status = req.status.upper()
        record.is_active = (record.status == "ACTIVE")

    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


@router.put("/records/{record_id}/status", response_model=AadhaarRecordResponse)
def update_aadhaar_record_status(
    record_id: str,
    req: AadhaarRecordStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Transitions record status between ACTIVE, INACTIVE, and SUSPENDED.
    """
    if len(record_id.strip()) == 12 and record_id.strip().isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Raw 12-digit Aadhaar numbers in URL path parameters are strictly prohibited. Use surrogate UUID record_id."
        )

    valid_statuses = {"ACTIVE", "INACTIVE", "SUSPENDED"}
    new_status = req.status.strip().upper()
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{req.status}'. Must be one of: ACTIVE, INACTIVE, SUSPENDED"
        )

    record = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aadhaar record not found"
        )

    record.status = new_status
    record.is_active = (new_status == "ACTIVE")
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


# ============================================================================
# VERIFICATION ENDPOINTS (M2M SERVICE AUTH & UI SANDBOX)
# ============================================================================

@router.post("/verify", response_model=AadhaarVerifyServiceResponse)
def verify_identity_service(
    req: AadhaarVerifyRequest,
    x_passkhadam_service_key: Optional[str] = Header(None, alias="X-PassKhadam-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    Machine-to-Machine identity verification endpoint.
    MANDATORY SERVICE AUTH: Requires valid 'X-PassKhadam-Service-Key' header.
    Writes immutable audit log entry into DBAadhaarAuditLog.
    """
    if not x_passkhadam_service_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required service authentication key header 'X-PassKhadam-Service-Key'"
        )

    valid_keys = {
        getattr(settings, "AADHAAR_SERVICE_KEY", "pk-mock-aadhaar-service-key-internal-2026"),
        getattr(settings, "PASSKHADAM_SERVICE_KEY", "pk-mock-aadhaar-service-key-internal-2026")
    }
    if x_passkhadam_service_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service authentication key"
        )

    result = aadhaar_authority.verify_identity(
        aadhaar_number=req.aadhaar_number,
        submitted_name=req.full_name,
        db=db,
        service_key=x_passkhadam_service_key,
        requester_role="BACKEND_SERVICE",
        originating_service="PassKhadam-Backend"
    )
    return result


@router.post("/test-verify")
def test_verify_identity(
    req: AadhaarVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Interactive test verification sandbox for Mock Aadhaar UI portal.
    Also records verification attempt in DBAadhaarAuditLog.
    """
    return aadhaar_authority.verify_identity(
        aadhaar_number=req.aadhaar_number,
        submitted_name=req.full_name,
        db=db,
        service_key=getattr(settings, "AADHAAR_SERVICE_KEY", None),
        requester_role="UI_SANDBOX",
        originating_service="PassKhadam-UISandbox"
    )
