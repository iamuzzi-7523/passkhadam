import time
import difflib
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.db import DBAadhaarRecord, DBAadhaarAuditLog, SessionLocal
from app.core.config import settings

class MockAadhaarAuthority:
    """
    Simulated Government Identity Authority (Mock Aadhaar API).
    Maintains an isolated demographic registry. Never allows main app to directly read its raw store;
    only responds to verification requests with match results and masked Aadhaar representations.
    """
    def __init__(self):
        # Pre-seeded official Aadhaar directory for demonstration
        self._records: Dict[str, Dict[str, Any]] = {
            "123456784821": {
                "aadhaar_number": "123456784821",
                "full_name": "Mohammed Uzair",
                "dob": "1995-04-12",
                "gender": "Male",
                "origin_state": "Karnataka",
                "address": "45/2 BTM Layout, Bengaluru, Karnataka",
                "is_active": True
            },
            "987654321012": {
                "aadhaar_number": "987654321012",
                "full_name": "Ramesh Kumar Verma",
                "dob": "1992-08-20",
                "gender": "Male",
                "origin_state": "Bihar",
                "address": "Village Chhatarpur, Dist Patna, Bihar",
                "is_active": True
            },
            "554433221100": {
                "aadhaar_number": "554433221100",
                "full_name": "Sunita Devi",
                "dob": "1998-11-05",
                "gender": "Female",
                "origin_state": "Uttar Pradesh",
                "address": "Sector 14, Gorakhpur, UP",
                "is_active": True
            },
            "112233445566": {
                "aadhaar_number": "112233445566",
                "full_name": "Anil Sahu",
                "dob": "1989-02-14",
                "gender": "Male",
                "origin_state": "Odisha",
                "address": "Ward 3, Ganjam, Odisha",
                "is_active": True
            },
            "998877665544": {
                "aadhaar_number": "998877665544",
                "full_name": "Lakshmi Narayana",
                "dob": "1994-06-30",
                "gender": "Female",
                "origin_state": "Andhra Pradesh",
                "address": "Main Road, Guntur, AP",
                "is_active": False # Inactive test record
            }
        }
        
        self.verification_logs: List[Dict[str, Any]] = []
        self.stats = {
            "total_requests": 0,
            "successful_verifications": 0,
            "failed_verifications": 0,
            "service_status": "ONLINE"
        }

    @staticmethod
    def mask_aadhaar(aadhaar: str) -> str:
        clean = "".join(filter(str.isdigit, aadhaar))
        if len(clean) >= 4:
            return f"XXXX XXXX {clean[-4:]}"
        return "XXXX XXXX 0000"

    @staticmethod
    def _match_names(submitted: str, official: str) -> bool:
        """
        Precise token and similarity demographic name comparison.
        Prevents loose substring bypasses (e.g., single characters or sub-words).
        """
        sub_clean = " ".join(submitted.strip().lower().split())
        rec_clean = " ".join(official.strip().lower().split())

        if not sub_clean or len(sub_clean) < 2:
            return False

        # 1. Exact normalized string equality
        if sub_clean == rec_clean:
            return True

        sub_tokens = sub_clean.split()
        rec_tokens = rec_clean.split()

        # 2. Token multiset equality (handles transposed name order)
        if sorted(sub_tokens) == sorted(rec_tokens):
            return True

        # 3. High-confidence string similarity for minor typographical errors (>= 85%)
        sim = difflib.SequenceMatcher(None, sub_clean, rec_clean).ratio()
        if sim >= 0.85:
            return True

        # 4. Multi-token subset matching (e.g., middle name omitted in 3+ token names)
        # Requires at least 2 matching tokens and covering >= 60% of official tokens
        if len(sub_tokens) >= 2 and set(sub_tokens).issubset(set(rec_tokens)):
            if len(sub_tokens) / len(rec_tokens) >= 0.6:
                return True

        return False

    def verify_identity(
        self,
        aadhaar_number: str,
        submitted_name: str,
        db: Optional[Session] = None,
        service_key: Optional[str] = None,
        requester_role: Optional[str] = "WORKER",
        originating_service: Optional[str] = "PassKhadam-Backend"
    ) -> Dict[str, Any]:
        """
        Processes a verification request against the Mock Aadhaar authority.
        Supports both database-backed (DBAadhaarRecord + DBAadhaarAuditLog)
        and backward-compatible in-memory mock modes.
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        clean_num = "".join(filter(str.isdigit, str(aadhaar_number or "")))
        masked = self.mask_aadhaar(clean_num)
        a_hash = hashlib.sha256(clean_num.encode("utf-8")).hexdigest()
        request_id = f"req_aadhaar_{uuid.uuid4().hex[:16]}"

        record_id = None
        official_name = None
        is_active = True
        status_str = "ACTIVE"
        origin_state = None
        gender = None
        dob = None

        # 1. Lookup Record in Database or In-Memory Store
        if db is not None:
            db_rec = db.query(DBAadhaarRecord).filter(DBAadhaarRecord.aadhaar_hash == a_hash).first()
            if db_rec:
                record_id = db_rec.record_id
                official_name = db_rec.full_name
                status_str = (db_rec.status or "ACTIVE").upper()
                is_active = (status_str == "ACTIVE") and (db_rec.is_active is True or db_rec.is_active is None or db_rec.is_active == 1)
                origin_state = db_rec.origin_state
                gender = db_rec.gender
                dob = db_rec.dob
            else:
                # Fallback to in-memory dictionary if DB table is unseeded or during tests
                in_mem = self._records.get(clean_num)
                if in_mem:
                    record_id = in_mem.get("record_id") or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"passkhadam:aadhaar:{clean_num}"))
                    official_name = in_mem["full_name"]
                    is_active = in_mem.get("is_active", True)
                    status_str = "ACTIVE" if is_active else "INACTIVE"
                    origin_state = in_mem.get("origin_state")
                    gender = in_mem.get("gender")
                    dob = in_mem.get("dob")
        else:
            in_mem = self._records.get(clean_num)
            if in_mem:
                record_id = in_mem.get("record_id") or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"passkhadam:aadhaar:{clean_num}"))
                official_name = in_mem["full_name"]
                is_active = in_mem.get("is_active", True)
                status_str = "ACTIVE" if is_active else "INACTIVE"
                origin_state = in_mem.get("origin_state")
                gender = in_mem.get("gender")
                dob = in_mem.get("dob")

        # 2. Evaluate Demographic Status and Match Rules
        if official_name is None:
            result_code = "RECORD_NOT_FOUND"
            reason = "Aadhaar number not found in authority database"
            aadhaar_matched = False
            name_matched = False
            verified = False
            res_status = "REJECTED"
        elif status_str == "SUSPENDED":
            result_code = "SUSPENDED_RECORD"
            reason = "Aadhaar record is suspended"
            aadhaar_matched = True
            name_matched = False
            verified = False
            res_status = "REJECTED"
        elif status_str == "INACTIVE" or not is_active:
            result_code = "INACTIVE_RECORD"
            reason = "Aadhaar record is currently inactive"
            aadhaar_matched = True
            name_matched = False
            verified = False
            res_status = "REJECTED"
        else:
            aadhaar_matched = True
            clean_sub = submitted_name.strip() if isinstance(submitted_name, str) else ""
            if len(clean_sub) < 2:
                result_code = "INVALID_NAME"
                reason = "Invalid or empty name submitted"
                name_matched = False
                verified = False
                res_status = "REJECTED"
            elif not self._match_names(clean_sub.lower(), official_name.strip().lower()):
                result_code = "NAME_MISMATCH"
                reason = f"Name mismatch: Provided '{submitted_name}' does not match official record"
                name_matched = False
                verified = False
                res_status = "REJECTED"
            else:
                result_code = "SUCCESS"
                reason = "Demographics matched and identity record valid"
                name_matched = True
                verified = True
                res_status = "VERIFIED"

        latency_ms = round((time.time() - start_time) * 1000 + 45, 1)

        if verified:
            self.stats["successful_verifications"] += 1
        else:
            self.stats["failed_verifications"] += 1

        # 3. Maintain In-Memory Verification Log for Test Suite Compatibility
        log_entry = {
            "id": len(self.verification_logs) + 1,
            "request_id": request_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "masked_aadhaar": masked,
            "submitted_name": submitted_name if isinstance(submitted_name, str) else "",
            "result": res_status,
            "reason": reason,
            "latency_ms": latency_ms
        }
        self.verification_logs.append(log_entry)

        # 4. Insert Append-Only Row into DBAadhaarAuditLog
        if db is not None:
            try:
                with db.begin_nested():
                    audit_row = DBAadhaarAuditLog(
                        request_id=request_id,
                        record_id=record_id,
                        masked_aadhaar=masked,
                        supplied_name=submitted_name if isinstance(submitted_name, str) else "",
                        name_matched=name_matched,
                        aadhaar_matched=aadhaar_matched,
                        record_status=status_str if official_name else "NONEXISTENT",
                        result_code=result_code,
                        response_time_ms=latency_ms,
                        requester_role=requester_role or "WORKER",
                        originating_service=originating_service or "PassKhadam-Backend",
                        failure_reason=reason if not verified else None,
                        timestamp=datetime.utcnow(),
                        created_at=datetime.utcnow()
                    )
                    db.add(audit_row)
                db.commit()
            except Exception:
                pass

        out: Dict[str, Any] = {
            "verified": verified,
            "status": res_status,
            "masked_aadhaar": masked,
            "request_id": request_id,
            "latency_ms": latency_ms,
            "record_id": record_id
        }
        if verified:
            out["origin_state"] = origin_state
            out["gender"] = gender
            out["dob"] = dob
            out["record_id"] = record_id
        else:
            out["reason"] = reason

        return out

    def get_dashboard_metrics(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Returns live dashboard metrics, preferring DB aggregation when session is provided.
        """
        if db is not None:
            total_records = db.query(DBAadhaarRecord).count()
            active_records = db.query(DBAadhaarRecord).filter(
                (DBAadhaarRecord.status == "ACTIVE") & (DBAadhaarRecord.is_active == True)
            ).count()
            suspended_records = db.query(DBAadhaarRecord).filter(
                DBAadhaarRecord.status == "SUSPENDED"
            ).count()
            inactive_records = db.query(DBAadhaarRecord).filter(
                (DBAadhaarRecord.status == "INACTIVE") | (DBAadhaarRecord.is_active == False)
            ).count()
            total_requests = db.query(DBAadhaarAuditLog).count()
            successful_verifications = db.query(DBAadhaarAuditLog).filter(
                DBAadhaarAuditLog.result_code == "SUCCESS"
            ).count()
            failed_verifications = total_requests - successful_verifications
            recent_logs_db = db.query(DBAadhaarAuditLog).order_by(DBAadhaarAuditLog.id.desc()).limit(15).all()
            recent_logs = [
                {
                    "id": l.id,
                    "request_id": l.request_id,
                    "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "",
                    "masked_aadhaar": l.masked_aadhaar,
                    "submitted_name": l.supplied_name,
                    "result": "VERIFIED" if l.result_code == "SUCCESS" else "REJECTED",
                    "reason": l.failure_reason or l.result_code,
                    "latency_ms": l.response_time_ms or 45.0
                }
                for l in recent_logs_db
            ]
            return {
                "total_records": total_records,
                "active_records": active_records,
                "suspended_records": suspended_records,
                "inactive_records": inactive_records,
                "total_requests": total_requests,
                "total_verifications": total_requests,
                "successful_verifications": successful_verifications,
                "failed_verifications": failed_verifications,
                "service_status": "ONLINE",
                "recent_logs": recent_logs
            }

        return {
            "total_records": len(self._records),
            "active_records": sum(1 for r in self._records.values() if r.get("is_active")),
            "suspended_records": sum(1 for r in self._records.values() if r.get("status") == "SUSPENDED"),
            "inactive_records": sum(1 for r in self._records.values() if not r.get("is_active")),
            "total_requests": self.stats["total_requests"],
            "total_verifications": self.stats["total_requests"],
            "successful_verifications": self.stats["successful_verifications"],
            "failed_verifications": self.stats["failed_verifications"],
            "service_status": self.stats["service_status"],
            "recent_logs": self.verification_logs[-15:][::-1]
        }

aadhaar_authority = MockAadhaarAuthority()

