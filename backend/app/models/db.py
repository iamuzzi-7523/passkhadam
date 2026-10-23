"""
backend/app/models/db.py
Authoritative SQLAlchemy Database Models for PASSKHADAM v0.4
"""

import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, DateTime, Text, Float,
    ForeignKey, UniqueConstraint, Index, CheckConstraint, text, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, validates, synonym
from sqlalchemy.engine import Engine

import logging
from app.core.config import settings

logger = logging.getLogger("passkhadam.db")

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enforce SQLite foreign key constraints per connection (only when running on SQLite)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # Strictly inspect the underlying DBAPI driver module
    if "sqlite" in type(dbapi_connection).__module__:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


# ============================================================================
# 1. CANONICAL USER MODEL (PassKhadamUser / DBUser)
# ============================================================================

class DBUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    firebase_uid = Column(String(128), unique=True, index=True, nullable=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="WORKER", nullable=False)  # WORKER, EMPLOYER, GOVERNMENT, ADMIN, AADHAAR_ADMIN
    status = Column(String(50), default="ACTIVE", nullable=False)  # ACTIVE, PENDING_REVIEW, SUSPENDED, REJECTED, DISABLED
    organization_address = Column(String(100), nullable=True)
    organization_name = Column(String(150), nullable=True)
    organization_status = Column(String(50), nullable=True)  # APPROVED, PENDING, REJECTED
    is_email_verified = Column(Boolean, default=True, nullable=False)
    is_phone_verified = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships to role-specific entities
    worker_profile = relationship("DBWorkerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    employer_organization = relationship("DBEmployerOrganization", back_populates="user", uselist=False, cascade="all, delete-orphan", foreign_keys="DBEmployerOrganization.user_id")
    government_officer = relationship("DBGovernmentOfficer", back_populates="user", uselist=False, cascade="all, delete-orphan", foreign_keys="DBGovernmentOfficer.user_id")

# Canonical Alias as mandated by PassKhadam v0.4 Architecture Specification
PassKhadamUser = DBUser


# ============================================================================
# 2. WORKER PROFILE MODEL (DBWorkerProfile)
# ============================================================================

class DBWorkerProfile(Base):
    __tablename__ = "worker_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    full_name = Column(String(150), nullable=False)
    dob = Column(String(50), nullable=True)
    gender = Column(String(20), nullable=True)
    origin_state = Column(String(100), default="Karnataka", nullable=False)
    current_state = Column(String(100), default="Karnataka", nullable=False)
    address = Column(Text, nullable=True)
    worker_category = Column(String(100), default="Mason", nullable=False)
    skills_json = Column(Text, default="[\"Mason\", \"Plumbing Assistance\"]", nullable=False)

    # Aadhaar verification status
    is_aadhaar_verified = Column(Boolean, default=False, nullable=False)
    masked_aadhaar = Column(String(50), nullable=True)
    aadhaar_request_id = Column(String(100), nullable=True, index=True)
    aadhaar_record_id = Column(String(36), nullable=True, index=True)

    # Decentralized Identity (DID) & W3C Credential
    did = Column(String(100), nullable=True, index=True)
    ipfs_cid = Column(String(100), nullable=True)
    credential_hash = Column(String(100), nullable=True)
    is_credential_anchored = Column(Boolean, default=False, nullable=False)

    # 6-Stage Worker Registration Lifecycle State Machine
    # NOT_STARTED -> AADHAAR_SUBMITTED -> DID_GENERATED -> VC_ISSUED -> EVM_ANCHORED -> ACTIVE (or FAILED)
    did_state = Column(String(50), default="NOT_STARTED", nullable=False, index=True)
    failure_reason = Column(Text, nullable=True)

    # Blockchain Anchor Provenance
    tx_hash = Column(String(128), nullable=True, index=True)
    block_number = Column(Integer, nullable=True, index=True)
    chain_id = Column(Integer, nullable=True)
    contract_address = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Back-reference
    user = relationship("DBUser", back_populates="worker_profile")


# ============================================================================
# 3. EMPLOYER ORGANIZATION MODEL (DBEmployerOrganization)
# ============================================================================

class DBEmployerOrganization(Base):
    __tablename__ = "employer_organizations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    name = Column(String(150), nullable=False, index=True)
    org_address = Column(String(100), nullable=True, index=True)

    # Legal Entity Identifiers
    registration_ref_number = Column(String(100), nullable=False, index=True)
    registration_number = Column(String(100), nullable=True, index=True)
    registration_type = Column(String(50), default="CIN", nullable=True)
    registration_authority = Column(String(100), default="MCA", nullable=True)
    registration_date = Column(String(50), nullable=True)

    # Business Profile
    business_type = Column(String(100), default="Construction & Infrastructure", nullable=True)
    nature_of_business = Column(String(150), default="Civil Engineering & Contracting", nullable=True)
    business_address = Column(Text, nullable=True)
    state_code = Column(String(10), default="KA", nullable=True)
    website = Column(String(150), nullable=True)
    expected_workforce = Column(Integer, default=50, nullable=True)

    # Official Contact Details
    official_email = Column(String(150), nullable=True, index=True)
    official_phone = Column(String(50), nullable=True)
    phone = synonym("official_phone")
    contact_person = Column(String(150), nullable=True)
    contact_phone = Column(String(50), nullable=True)

    # Organization Lifecycle Status:
    # PENDING_REVIEW -> APPROVED -> ACTIVE -> REJECTED -> SUSPENDED -> DISABLED
    status = Column(String(50), default="PENDING_REVIEW", nullable=False, index=True)
    verification_status = synonym("status")

    # Administrative Decisions
    rejection_reason = Column(Text, nullable=True)
    suspension_reason = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", back_populates="employer_organization", foreign_keys=[user_id])
    category_requests = relationship("DBCategoryAuthorizationRequest", back_populates="organization", cascade="all, delete-orphan")


# ============================================================================
# 4. CATEGORY AUTHORIZATION REQUEST MODEL (DBCategoryAuthorizationRequest)
# ============================================================================

class DBCategoryAuthorizationRequest(Base):
    __tablename__ = "category_authorization_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Employment Scope Parameters
    category = Column(String(100), nullable=False, index=True)
    skill_level = Column(String(50), default="Skilled", nullable=False)
    nature_of_employment = Column(String(50), default="Contract", nullable=False)
    work_context = Column(String(150), default="Construction", nullable=True)

    # Status: PENDING, APPROVED, REJECTED, MORE_INFO_REQUIRED, DISCONTINUED, SUSPENDED, SUPERSEDED
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    verification_status = synonym("status")

    # Active Scope State Flag (Default False; True ONLY when status == APPROVED)
    is_active_scope = Column(Boolean, default=False, nullable=False, index=True)

    # Request Version (increments when re-requesting a scope)
    request_version = Column(Integer, default=1, nullable=False)

    # Justification & Administrative Decision
    reason = Column(Text, nullable=True)
    review_reason = Column(Text, nullable=True)
    requested_information = Column(Text, nullable=True)
    supporting_documents_json = Column(Text, nullable=True)
    reviewed_by = Column(String(128), nullable=True)

    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    organization = relationship("DBEmployerOrganization", back_populates="category_requests")

    # Composite Unique Index for Active Category Scope (Partial Index in SQLite)
    __table_args__ = (
        Index(
            "uq_active_category_scope",
            "organization_id",
            "category",
            "skill_level",
            "nature_of_employment",
            unique=True,
            sqlite_where=text("is_active_scope = 1"),
            postgresql_where=text("is_active_scope = true"),
        ),
    )


# Legacy Model preserved for backward compatibility
class DBCategoryRequest(Base):
    __tablename__ = "category_requests"
    id = Column(Integer, primary_key=True, index=True)
    employer_address = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(50), default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# 5. GOVERNMENT OFFICER MODEL (DBGovernmentOfficer)
# ============================================================================

class DBGovernmentOfficer(Base):
    __tablename__ = "government_officers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=True)
    officer_name = Column(String(150), nullable=True)
    full_name = Column(String(150), nullable=True)
    officer_reference_id = Column(String(100), unique=True, index=True, nullable=True)

    department = Column(String(150), default="Migrant Labour Welfare Department", nullable=False)
    designation = Column(String(100), default="Labour Welfare Commissioner", nullable=True)
    official_email = Column(String(150), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    wallet_address = Column(String(100), nullable=True)

    # Geographic Hierarchy: NATIONAL, STATE, DISTRICT, BLOCK
    authority_level = Column(String(50), nullable=False, index=True)
    state = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=True, index=True)
    block = Column(String(100), nullable=True, index=True)

    # Granular Permissions (JSON encoded strings)
    permissions_json = Column(Text, default="[]", nullable=False)
    benefit_permissions_json = Column(Text, default="[]", nullable=False)

    # Status: PROVISIONED, PENDING_ACTIVATION, ACTIVE, SUSPENDED, DISABLED
    status = Column(String(50), default="PROVISIONED", nullable=False, index=True)

    suspension_reason = Column(Text, nullable=True)
    provisioned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", back_populates="government_officer", foreign_keys=[user_id])

    # Check Constraint for Geographic Hierarchy Invariants
    __table_args__ = (
        CheckConstraint(
            """(
                (authority_level = 'NATIONAL') OR
                (authority_level = 'STATE' AND state IS NOT NULL AND length(trim(state)) > 0) OR
                (authority_level = 'DISTRICT' AND state IS NOT NULL AND length(trim(state)) > 0 AND district IS NOT NULL AND length(trim(district)) > 0) OR
                (authority_level IN ('BLOCK', 'LOCAL') AND state IS NOT NULL AND length(trim(state)) > 0 AND district IS NOT NULL AND length(trim(district)) > 0 AND block IS NOT NULL AND length(trim(block)) > 0)
            )""",
            name="ck_officer_geographic_hierarchy"
        ),
    )

    @validates("authority_level", "state", "district", "block")
    def validate_geographic_hierarchy(self, key, value):
        if key == "authority_level" and value:
            norm_val = str(value).strip().upper()
            if norm_val == "LOCAL":
                value = "BLOCK"
        level = self.authority_level if key != "authority_level" else value
        if level:
            level = str(level).strip().upper()
            if level == "LOCAL":
                level = "BLOCK"
        st = self.state if key != "state" else value
        dist = self.district if key != "district" else value
        blk = self.block if key != "block" else value

        if level == "STATE":
            if key == "state" and (not value or not str(value).strip()):
                raise ValueError("State is mandatory for STATE authority level")
        elif level == "DISTRICT":
            if key == "state" and (not value or not str(value).strip()):
                raise ValueError("State is mandatory for DISTRICT authority level")
            if key == "district" and (not value or not str(value).strip()):
                raise ValueError("District is mandatory for DISTRICT authority level")
        elif level in ("BLOCK", "LOCAL"):
            if key == "state" and (not value or not str(value).strip()):
                raise ValueError("State is mandatory for BLOCK authority level")
            if key == "district" and (not value or not str(value).strip()):
                raise ValueError("District is mandatory for BLOCK authority level")
            if key == "block" and (not value or not str(value).strip()):
                raise ValueError("Block is mandatory for BLOCK authority level")
        return value


# ============================================================================
# 6. ACTIVATION EMAIL TRACKING (DBActivationEmail)
# ============================================================================

class DBActivationEmail(Base):
    __tablename__ = "activation_emails"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipient_email = Column(String(150), nullable=False, index=True)
    token_hash = Column(String(128), unique=True, index=True, nullable=False)  # SHA-256 hex string

    # Target binding
    entity_type = Column(String(50), nullable=False, index=True)  # EMPLOYER or GOVERNMENT
    entity_id = Column(Integer, nullable=False, index=True)
    subject = Column(String(255), nullable=True)
    template_name = Column(String(100), nullable=True)
    custom_message = Column(Text, nullable=True)

    # Status: PENDING, SENT, FAILED, EXPIRED, USED
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=True)
    last_error = Column(Text, nullable=True)

    expires_at = Column(DateTime, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ============================================================================
# 7. GOVERNANCE AUDIT LOG (DBGovernanceAuditLog) - IMMUTABLE
# ============================================================================

class DBGovernanceAuditLog(Base):
    __tablename__ = "governance_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_firebase_uid = Column(String(128), nullable=False, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_role = Column(String(50), nullable=False, index=True)  # ADMIN, GOVERNMENT, SYSTEM

    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(String(100), nullable=False, index=True)

    previous_state = Column(Text, nullable=True)
    new_state = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)

    request_id = Column(String(100), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# Immutability Protection for DBGovernanceAuditLog
@event.listens_for(DBGovernanceAuditLog, "before_update")
def _prevent_governance_audit_update(mapper, connection, target):
    raise RuntimeError("DBGovernanceAuditLog is immutable; update operations are strictly prohibited.")

@event.listens_for(DBGovernanceAuditLog, "before_delete")
def _prevent_governance_audit_delete(mapper, connection, target):
    raise RuntimeError("DBGovernanceAuditLog is immutable; delete operations are strictly prohibited.")

# Canonical Alias for DBGovernanceAuditLog as requested by Milestone 5
DBAdminAuditLog = DBGovernanceAuditLog


# ============================================================================
# 8. MOCK AADHAAR RECORD & AUDIT LOG (DBAadhaarRecord, DBAadhaarAuditLog)
# ============================================================================

class DBAadhaarRecord(Base):
    __tablename__ = "aadhaar_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_id = Column(String(64), unique=True, index=True, nullable=False)  # Surrogate UUID
    aadhaar_hash = Column(String(128), unique=True, index=True, nullable=False)  # SHA-256 hash
    masked_aadhaar = Column(String(50), nullable=False)
    full_name = Column(String(150), nullable=False, index=True)
    dob = Column(String(50), nullable=False)
    gender = Column(String(20), nullable=False)
    origin_state = Column(String(100), nullable=False, index=True)
    address = Column(Text, nullable=True)

    # Status: ACTIVE, INACTIVE, SUSPENDED
    status = Column(String(50), default="ACTIVE", nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DBAadhaarAuditLog(Base):
    __tablename__ = "aadhaar_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(String(100), unique=True, index=True, nullable=False)
    record_id = Column(String(64), nullable=True, index=True)

    masked_aadhaar = Column(String(50), nullable=False, index=True)
    supplied_name = Column(String(150), nullable=True)
    submitted_name = synonym("supplied_name")
    name_matched = Column(Boolean, default=False, nullable=False)
    aadhaar_matched = Column(Boolean, default=False, nullable=False)
    record_status = Column(String(50), nullable=True)

    result_code = Column(String(50), nullable=False, index=True)
    response_time_ms = Column(Float, nullable=True)
    requester_role = Column(String(50), nullable=True)
    originating_service = Column(String(100), default="PassKhadam-Backend", nullable=False)
    failure_reason = Column(Text, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# Immutability Protection for DBAadhaarAuditLog
@event.listens_for(DBAadhaarAuditLog, "before_update")
def _prevent_aadhaar_audit_update(mapper, connection, target):
    raise RuntimeError("DBAadhaarAuditLog is immutable; update operations are strictly prohibited.")

@event.listens_for(DBAadhaarAuditLog, "before_delete")
def _prevent_aadhaar_audit_delete(mapper, connection, target):
    raise RuntimeError("DBAadhaarAuditLog is immutable; delete operations are strictly prohibited.")


# ============================================================================
# 9. CONSUMED PRESENTATION NONCE (DBConsumedPresentationNonce) - REPLAY DEFENSE
# ============================================================================

class DBConsumedPresentationNonce(Base):
    __tablename__ = "consumed_presentation_nonces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    presentation_id = Column(String(128), nullable=False, index=True)
    verifier_role = Column(String(50), nullable=False, index=True)
    verifier_id = Column(String(128), nullable=False, index=True)
    worker_did = Column(String(100), nullable=True, index=True)
    consumed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "presentation_id", "verifier_role", "verifier_id",
            name="uq_presentation_verifier_context"
        ),
    )


# ============================================================================
# 10. DYNAMIC WORKER CREDENTIALS (DBWorkerCredential)
# ============================================================================

class DBWorkerCredential(Base):
    __tablename__ = "worker_credentials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    credential_id = Column(String(100), unique=True, index=True, nullable=False)
    worker_did = Column(String(100), index=True, nullable=False)
    worker_id = Column(Integer, ForeignKey("worker_profiles.id"), nullable=True, index=True)
    title = Column(String(150), nullable=False)
    credential_type = Column(String(100), nullable=False) # Identity, Safety, Skill, Experience, Welfare, Induction
    issuer_name = Column(String(150), nullable=False)
    issuer_address = Column(String(100), nullable=True, index=True)
    issuer_role = Column(String(50), nullable=False) # GOVERNMENT | EMPLOYER | AADHAAR | ADMIN
    status = Column(String(50), default="VALID", nullable=False, index=True) # VALID | REVOKED | EXPIRED
    revocation_reason = Column(Text, nullable=True)
    skills_json = Column(Text, nullable=True) # JSON array of skills e.g. ["Electrician", "Solar Wiring"]
    metadata_json = Column(Text, nullable=True) # JSON key-value custom attributes
    ipfs_cid = Column(String(100), nullable=True)
    tx_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)


# ============================================================================
# 11. IMMUTABLE PORTABLE EMPLOYMENTS (DBEmployment)
# ============================================================================

class DBEmployment(Base):
    __tablename__ = "employments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    worker_did = Column(String(100), index=True, nullable=False)
    employer_address = Column(String(100), index=True, nullable=False)
    employer_name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    level = Column(String(50), default="Skilled", nullable=False)
    nature_of_employment = Column(String(50), default="Contract", nullable=False)
    job_role = Column(String(150), nullable=False)
    location = Column(String(150), nullable=False)
    start_date = Column(Integer, nullable=False) # Unix timestamp
    end_date = Column(Integer, default=0, nullable=False) # Unix timestamp
    status = Column(String(50), default="ACTIVE", nullable=False, index=True) # ACTIVE | COMPLETED | TERMINATED | RESIGNED | DISMISSED
    status_reason = Column(String(255), default="Stint Initiated", nullable=True)
    tx_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ============================================================================
# 12. WELFARE SCHEME CLAIMS (DBWelfareClaim)
# ============================================================================

class DBWelfareClaim(Base):
    __tablename__ = "welfare_claims"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scheme_id = Column(Integer, nullable=False, index=True)
    scheme_name = Column(String(150), nullable=True)
    worker_did = Column(String(100), index=True, nullable=False)
    gov_address = Column(String(100), index=True, nullable=False)
    officer_state = Column(String(100), nullable=False)
    claim_id_hex = Column(String(128), nullable=True, index=True)
    claim_hash = Column(String(128), nullable=True)
    tx_hash = Column(String(128), nullable=True)
    disbursed_at = Column(Integer, nullable=False) # Unix timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ============================================================================
# DATABASE INITIALIZATION & PARTIAL INDEX MIGRATION
# ============================================================================

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            try:
                # 1. Ensure partial unique index exists in SQLite
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_category_scope "
                    "ON category_authorization_requests (organization_id, category, skill_level, nature_of_employment) "
                    "WHERE is_active_scope = 1;"
                ))
                conn.commit()
            except Exception:
                pass

            # 1.1 Ensure SQLite DDL triggers for audit log immutability exist
            try:
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS prevent_governance_audit_update
                    BEFORE UPDATE ON governance_audit_logs
                    BEGIN
                        SELECT RAISE(ABORT, 'DBGovernanceAuditLog is immutable; update operations are strictly prohibited.');
                    END;
                """))
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS prevent_governance_audit_delete
                    BEFORE DELETE ON governance_audit_logs
                    BEGIN
                        SELECT RAISE(ABORT, 'DBGovernanceAuditLog is immutable; delete operations are strictly prohibited.');
                    END;
                """))
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS prevent_aadhaar_audit_update
                    BEFORE UPDATE ON aadhaar_audit_logs
                    BEGIN
                        SELECT RAISE(ABORT, 'DBAadhaarAuditLog is immutable; update operations are strictly prohibited.');
                    END;
                """))
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS prevent_aadhaar_audit_delete
                    BEFORE DELETE ON aadhaar_audit_logs
                    BEGIN
                        SELECT RAISE(ABORT, 'DBAadhaarAuditLog is immutable; delete operations are strictly prohibited.');
                    END;
                """))
                conn.commit()
            except Exception:
                pass

            # 2. Schema evolution column additions for existing tables in SQLite
            try:
                cursor = conn.connection.cursor()
                existing_user_cols = {col[1] for col in cursor.execute("PRAGMA table_info(users)").fetchall()}
                user_cols = [
                    ("firebase_uid", "VARCHAR(128)"),
                    ("status", "VARCHAR(50) DEFAULT 'ACTIVE'"),
                    ("organization_address", "VARCHAR(100)"),
                    ("organization_name", "VARCHAR(150)"),
                    ("organization_status", "VARCHAR(50)"),
                    ("is_email_verified", "BOOLEAN DEFAULT 1"),
                    ("is_phone_verified", "BOOLEAN DEFAULT 1")
                ]
                for col_name, col_type in user_cols:
                    if col_name not in existing_user_cols:
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

                existing_worker_cols = {col[1] for col in cursor.execute("PRAGMA table_info(worker_profiles)").fetchall()}
                worker_cols = [
                    ("did_state", "VARCHAR(50) DEFAULT 'NOT_STARTED'"),
                    ("tx_hash", "VARCHAR(128)"),
                    ("block_number", "INTEGER"),
                    ("chain_id", "INTEGER"),
                    ("contract_address", "VARCHAR(100)"),
                    ("aadhaar_request_id", "VARCHAR(100)"),
                    ("aadhaar_record_id", "VARCHAR(36)")
                ]
                for col_name, col_type in worker_cols:
                    if col_name not in existing_worker_cols:
                        cursor.execute(f"ALTER TABLE worker_profiles ADD COLUMN {col_name} {col_type}")

                conn.connection.commit()
            except Exception:
                pass

            # 3. Ensure government_officers table contains ck_officer_geographic_hierarchy in SQLite DDL
            try:
                cursor = conn.connection.cursor()
                table_info = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='government_officers'").fetchone()
                if table_info and table_info[0] and "ck_officer_geographic_hierarchy" not in table_info[0]:
                    cursor.execute("PRAGMA foreign_keys=OFF")
                    cursor.execute("ALTER TABLE government_officers RENAME TO _government_officers_old")
                    cursor.execute("""
                        CREATE TABLE government_officers (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER REFERENCES users(id),
                            officer_name VARCHAR(150) NOT NULL,
                            full_name VARCHAR(150),
                            department VARCHAR(150) NOT NULL,
                            designation VARCHAR(100),
                            authority_level VARCHAR(50) NOT NULL,
                            state VARCHAR(100),
                            district VARCHAR(100),
                            block VARCHAR(100),
                            officer_reference_id VARCHAR(100),
                            official_email VARCHAR(150),
                            phone VARCHAR(50),
                            wallet_address VARCHAR(100),
                            permissions_json TEXT DEFAULT '[]',
                            benefit_permissions_json TEXT DEFAULT '[]',
                            status VARCHAR(50) DEFAULT 'PROVISIONED',
                            suspension_reason TEXT,
                            provisioned_by INTEGER,
                            expires_at TIMESTAMP,
                            last_login_at TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT ck_officer_geographic_hierarchy CHECK (
                                (authority_level = 'NATIONAL') OR
                                (authority_level = 'STATE' AND state IS NOT NULL AND length(trim(state)) > 0) OR
                                (authority_level = 'DISTRICT' AND state IS NOT NULL AND length(trim(state)) > 0 AND district IS NOT NULL AND length(trim(district)) > 0) OR
                                (authority_level IN ('BLOCK', 'LOCAL') AND state IS NOT NULL AND length(trim(state)) > 0 AND district IS NOT NULL AND length(trim(district)) > 0 AND block IS NOT NULL AND length(trim(block)) > 0)
                            )
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO government_officers (
                            id, user_id, officer_name, full_name, department, designation, authority_level,
                            state, district, block, officer_reference_id, official_email, phone, wallet_address,
                            permissions_json, benefit_permissions_json, status, suspension_reason, provisioned_by,
                            expires_at, last_login_at, created_at, updated_at
                        )
                        SELECT
                            id, user_id, officer_name, full_name, department, designation, authority_level,
                            state, district, block, officer_reference_id, official_email, phone, wallet_address,
                            permissions_json, benefit_permissions_json, status, suspension_reason, provisioned_by,
                            expires_at, last_login_at, created_at, updated_at
                        FROM _government_officers_old
                    """)
                    cursor.execute("DROP TABLE _government_officers_old")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_government_officers_user_id ON government_officers (user_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_government_officers_official_email ON government_officers (official_email)")
                    cursor.execute("PRAGMA foreign_keys=ON")
                    conn.connection.commit()
            except Exception:
                pass
        else:
            # PostgreSQL Dialect (Supabase Managed PostgreSQL)
            try:
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        RAISE EXCEPTION 'Audit logs are immutable; UPDATE and DELETE operations are strictly prohibited.';
                    END;
                    $$ LANGUAGE plpgsql;
                """))
                conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_prevent_governance_audit_update') THEN
                            CREATE TRIGGER trg_prevent_governance_audit_update
                            BEFORE UPDATE OR DELETE ON governance_audit_logs
                            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_prevent_aadhaar_audit_update') THEN
                            CREATE TRIGGER trg_prevent_aadhaar_audit_update
                            BEFORE UPDATE OR DELETE ON aadhaar_audit_logs
                            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
                        END IF;
                    END $$;
                """))
                conn.commit()
            except Exception as pg_err:
                logger.warning(f"PostgreSQL trigger initialization warning: {pg_err}")

try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
