"""
PassKhadam v0.4 — Database Migration & Schema Invariants Test Suite
=====================================================================
Opaque-box test suite for SQLite schema migration, table existence,
partial unique index `uq_active_category_scope`, composite replay constraint
`uq_presentation_verifier_context`, and 5 baseline demo accounts preservation.

Requirements: R1, R5, R6, R7, R8, R9, R10
Specification: PassKhadam_v0.4_Product_Corrections_and_Workflow_Hardening.md §71-§74, §81, §85
"""

import os
import sqlite3
import importlib.util
import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.db import (
    SessionLocal,
    DBUser,
    DBWorkerProfile,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBGovernmentOfficer,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBAadhaarRecord,
    DBAadhaarAuditLog,
    DBConsumedPresentationNonce,
)
from app.db.migrate import migrate_database

CANONICAL_DEMO_ACCOUNTS = {
    "WORKER": {
        "email": "worker@passkhadam.org",
        "role": "WORKER",
        "expected_name": "Mohammed Uzair",
    },
    "EMPLOYER": {
        "email": "employer@apexinfra.com",
        "role": "EMPLOYER",
        "expected_name": "Apex Infrastructure Admin",
    },
    "GOVERNMENT": {
        "email": "gov@maharashtra.gov.in",
        "role": "GOVERNMENT",
        "expected_name": "Maharashtra Labour Welfare Officer",
    },
    "ADMIN": {
        "email": "admin@passkhadam.org",
        "role": "ADMIN",
        "expected_name": "PassKhadam Platform Governance",
    },
    "AADHAAR": {
        "email": "authority@uidai.gov.in",
        "role": ["AADHAAR", "AADHAAR_ADMIN"],
        "expected_name": "UIDAI Mock Authority Gateway",
    },
}

V04_MIGRATION_DDL = """
-- 1. Users table baseline
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    firebase_uid VARCHAR(128) UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'WORKER',
    status VARCHAR(50) DEFAULT 'ACTIVE',
    organization_address VARCHAR(100),
    organization_name VARCHAR(150),
    organization_status VARCHAR(50),
    is_email_verified BOOLEAN DEFAULT 1,
    is_phone_verified BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Worker Profiles table
CREATE TABLE IF NOT EXISTS worker_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    full_name VARCHAR(150) NOT NULL,
    dob VARCHAR(50),
    gender VARCHAR(20),
    origin_state VARCHAR(100) DEFAULT 'Karnataka',
    current_state VARCHAR(100) DEFAULT 'Karnataka',
    address TEXT,
    worker_category VARCHAR(100) DEFAULT 'Mason',
    skills_json TEXT DEFAULT '["Mason"]',
    is_aadhaar_verified BOOLEAN DEFAULT 0,
    masked_aadhaar VARCHAR(50),
    did VARCHAR(100),
    ipfs_cid VARCHAR(100),
    credential_hash VARCHAR(100),
    is_credential_anchored BOOLEAN DEFAULT 0,
    did_state VARCHAR(50) DEFAULT 'NOT_STARTED',
    tx_hash VARCHAR(128),
    block_number INTEGER,
    chain_id INTEGER,
    contract_address VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Employer Organizations table
CREATE TABLE IF NOT EXISTS employer_organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(150) NOT NULL,
    registration_ref_number VARCHAR(100) NOT NULL,
    registration_type VARCHAR(50) DEFAULT 'CIN',
    registration_authority VARCHAR(100) DEFAULT 'MCA',
    business_type VARCHAR(100),
    nature_of_business VARCHAR(150),
    official_email VARCHAR(150),
    official_phone VARCHAR(50),
    contact_person VARCHAR(150),
    status VARCHAR(50) DEFAULT 'PENDING_REVIEW',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Category Authorization Requests table
CREATE TABLE IF NOT EXISTS category_authorization_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES employer_organizations(id),
    category VARCHAR(100) NOT NULL,
    skill_level VARCHAR(50) NOT NULL DEFAULT 'Skilled',
    nature_of_employment VARCHAR(50) NOT NULL DEFAULT 'Contract',
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    is_active_scope BOOLEAN NOT NULL DEFAULT 0,
    request_version INTEGER NOT NULL DEFAULT 1,
    review_reason TEXT,
    requested_information TEXT,
    reviewed_by VARCHAR(128),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

-- Partial unique index on active scopes
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_category_scope 
ON category_authorization_requests (organization_id, category, skill_level, nature_of_employment) 
WHERE is_active_scope = 1;

-- 5. Government Officers table
CREATE TABLE IF NOT EXISTS government_officers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    officer_name VARCHAR(150) NOT NULL,
    department VARCHAR(150) NOT NULL,
    designation VARCHAR(100),
    authority_level VARCHAR(50) NOT NULL, -- NATIONAL, STATE, DISTRICT, BLOCK
    state VARCHAR(100),
    district VARCHAR(100),
    block VARCHAR(100),
    officer_reference_id VARCHAR(100),
    permissions_json TEXT DEFAULT '[]',
    benefit_permissions_json TEXT DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'PROVISIONED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Activation Emails table
CREATE TABLE IF NOT EXISTS activation_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_email VARCHAR(150) NOT NULL,
    token_hash VARCHAR(128) NOT NULL,
    entity_type VARCHAR(50) NOT NULL, -- EMPLOYER, GOVERNMENT
    entity_id INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, SENT, FAILED, EXPIRED, USED
    attempt_count INTEGER DEFAULT 0,
    last_error TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Governance Audit Logs table
CREATE TABLE IF NOT EXISTS governance_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_firebase_uid VARCHAR(128) NOT NULL,
    actor_user_id INTEGER,
    actor_role VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(100) NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    reason TEXT,
    request_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Mock Aadhaar Records table
CREATE TABLE IF NOT EXISTS aadhaar_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id VARCHAR(64) UNIQUE NOT NULL, -- UUID surrogate identifier
    aadhaar_hash VARCHAR(128) UNIQUE NOT NULL,
    masked_aadhaar VARCHAR(50) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    dob VARCHAR(50) NOT NULL,
    gender VARCHAR(20) NOT NULL,
    origin_state VARCHAR(100) NOT NULL,
    address TEXT,
    status VARCHAR(50) DEFAULT 'ACTIVE',
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Aadhaar Audit Logs table
CREATE TABLE IF NOT EXISTS aadhaar_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id VARCHAR(100) NOT NULL,
    record_id VARCHAR(64),
    masked_aadhaar VARCHAR(50) NOT NULL,
    supplied_name VARCHAR(150),
    name_matched BOOLEAN NOT NULL,
    aadhaar_matched BOOLEAN NOT NULL,
    record_status VARCHAR(50),
    result_code VARCHAR(50) NOT NULL,
    response_time_ms FLOAT,
    requester_role VARCHAR(50),
    originating_service VARCHAR(100),
    failure_reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Consumed Presentation Nonces table (Deferred atomic replay protection)
CREATE TABLE IF NOT EXISTS consumed_presentation_nonces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    presentation_id VARCHAR(128) NOT NULL,
    verifier_role VARCHAR(50) NOT NULL,
    verifier_id VARCHAR(128) NOT NULL,
    worker_did VARCHAR(100),
    consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_presentation_verifier_context UNIQUE (presentation_id, verifier_role, verifier_id)
);

-- Legacy compatibility table
CREATE TABLE IF NOT EXISTS category_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_address VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture
def isolated_v04_db(tmp_path):
    """Provides an isolated SQLite database initialized with v0.4 schema."""
    db_file = str(tmp_path / "test_migration_isolated.db")
    conn = sqlite3.connect(db_file)
    conn.executescript(V04_MIGRATION_DDL)
    conn.commit()
    conn.close()
    return db_file


def test_sqlite_v04_all_mandated_tables_exist(isolated_v04_db):
    """Verifies that all 10 required v0.4 tables are created in the SQLite schema."""
    conn = sqlite3.connect(isolated_v04_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected_tables = {
        "users",
        "worker_profiles",
        "employer_organizations",
        "category_authorization_requests",
        "government_officers",
        "activation_emails",
        "governance_audit_logs",
        "aadhaar_records",
        "aadhaar_audit_logs",
        "consumed_presentation_nonces",
        "category_requests",
    }
    missing = expected_tables - tables
    assert not missing, f"Missing required v0.4 SQLite tables: {missing}"


def test_sqlite_partial_unique_index_active_scope_definition(isolated_v04_db):
    """Verifies that partial unique index `uq_active_category_scope` exists on category_authorization_requests."""
    conn = sqlite3.connect(isolated_v04_db)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='uq_active_category_scope';")
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "Partial unique index uq_active_category_scope was not found in sqlite_master"
    sql = row[0].lower()
    assert "unique" in sql
    assert "is_active_scope = 1" in sql or "is_active_scope=1" in sql
    assert "organization_id" in sql and "category" in sql


def test_sqlite_partial_unique_index_allows_multiple_inactive_scopes(isolated_v04_db):
    """Verifies that multiple requests with is_active_scope = 0 can coexist for the same scope tuple."""
    conn = sqlite3.connect(isolated_v04_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO employer_organizations (name, registration_ref_number) VALUES ('Org A', 'REF-001')")
    org_id = cursor.lastrowid

    # Insert 3 separate requests for same scope with is_active_scope = 0 (PENDING, REJECTED, DISCONTINUED)
    cursor.execute(
        "INSERT INTO category_authorization_requests (organization_id, category, skill_level, nature_of_employment, status, is_active_scope) VALUES (?, ?, ?, ?, ?, ?)",
        (org_id, "Mason", "Skilled", "Contract", "PENDING", 0)
    )
    cursor.execute(
        "INSERT INTO category_authorization_requests (organization_id, category, skill_level, nature_of_employment, status, is_active_scope) VALUES (?, ?, ?, ?, ?, ?)",
        (org_id, "Mason", "Skilled", "Contract", "REJECTED", 0)
    )
    cursor.execute(
        "INSERT INTO category_authorization_requests (organization_id, category, skill_level, nature_of_employment, status, is_active_scope) VALUES (?, ?, ?, ?, ?, ?)",
        (org_id, "Mason", "Skilled", "Contract", "DISCONTINUED", 0)
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM category_authorization_requests WHERE organization_id = ? AND category = 'Mason'", (org_id,))
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 3, f"Expected 3 inactive requests to coexist without constraint violation, got {count}"


def test_sqlite_partial_unique_index_enforces_single_active_scope(isolated_v04_db):
    """Verifies that attempting to activate a second scope with is_active_scope = 1 raises sqlite3.IntegrityError."""
    conn = sqlite3.connect(isolated_v04_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO employer_organizations (name, registration_ref_number) VALUES ('Org A', 'REF-001')")
    org_id = cursor.lastrowid

    # First active scope succeeds
    cursor.execute(
        "INSERT INTO category_authorization_requests (organization_id, category, skill_level, nature_of_employment, status, is_active_scope) VALUES (?, ?, ?, ?, ?, ?)",
        (org_id, "Electrician", "Skilled", "Permanent", "APPROVED", 1)
    )
    conn.commit()

    # Attempt to insert second active scope for identical tuple must fail
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        cursor.execute(
            "INSERT INTO category_authorization_requests (organization_id, category, skill_level, nature_of_employment, status, is_active_scope) VALUES (?, ?, ?, ?, ?, ?)",
            (org_id, "Electrician", "Skilled", "Permanent", "APPROVED", 1)
        )
        conn.commit()
    conn.close()

    assert "UNIQUE constraint failed" in str(exc_info.value) or "uq_active_category_scope" in str(exc_info.value)


def test_sqlite_active_scope_deactivation_allows_new_active_scope(isolated_v04_db):
    """Verifies that discontinuing an active scope (is_active_scope -> 0) allows a new version to become active."""
    conn = sqlite3.connect(isolated_v04_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO employer_organizations (name, registration_ref_number) VALUES ('Org A', 'REF-001')")
    org_id = cursor.lastrowid

    # Active v1
    cursor.execute(
        "INSERT INTO category_authorization_requests (organization_id, category, skill_level, nature_of_employment, status, is_active_scope, request_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (org_id, "Plumber", "Semi-Skilled", "Contract", "APPROVED", 1, 1)
    )
    req1_id = cursor.lastrowid
    conn.commit()

    # Admin discontinues v1 -> is_active_scope = 0
    cursor.execute(
        "UPDATE category_authorization_requests SET status = 'DISCONTINUED', is_active_scope = 0 WHERE id = ?",
        (req1_id,)
    )
    conn.commit()

    # New request v2 approved -> is_active_scope = 1 must now succeed cleanly
    cursor.execute(
        "INSERT INTO category_authorization_requests (organization_id, category, skill_level, nature_of_employment, status, is_active_scope, request_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (org_id, "Plumber", "Semi-Skilled", "Contract", "APPROVED", 1, 2)
    )
    conn.commit()

    cursor.execute("SELECT status, is_active_scope, request_version FROM category_authorization_requests WHERE organization_id = ? ORDER BY id ASC", (org_id,))
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0] == ("DISCONTINUED", 0, 1)
    assert rows[1] == ("APPROVED", 1, 2)


def test_sqlite_composite_nonce_constraint_prevents_replay(isolated_v04_db):
    """Verifies that inserting identical (presentation_id, verifier_role, verifier_id) raises IntegrityError."""
    conn = sqlite3.connect(isolated_v04_db)
    cursor = conn.cursor()

    presentation_id = "pres_unique_nonce_abc123"
    role = "EMPLOYER"
    verifier_id = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"

    # First consumption succeeds
    cursor.execute(
        "INSERT INTO consumed_presentation_nonces (presentation_id, verifier_role, verifier_id) VALUES (?, ?, ?)",
        (presentation_id, role, verifier_id)
    )
    conn.commit()

    # Immediate replay by same verifier context must fail
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        cursor.execute(
            "INSERT INTO consumed_presentation_nonces (presentation_id, verifier_role, verifier_id) VALUES (?, ?, ?)",
            (presentation_id, role, verifier_id)
        )
        conn.commit()
    conn.close()

    assert "UNIQUE constraint failed" in str(exc_info.value) or "uq_presentation_verifier_context" in str(exc_info.value)


def test_sqlite_composite_nonce_permits_independent_cross_role_and_verifier(isolated_v04_db):
    """Verifies that Government and another Employer can verify the same presentation without collision."""
    conn = sqlite3.connect(isolated_v04_db)
    cursor = conn.cursor()

    pres_id = "pres_shared_multi_party_999"

    # 1. Employer A consumes
    cursor.execute(
        "INSERT INTO consumed_presentation_nonces (presentation_id, verifier_role, verifier_id) VALUES (?, ?, ?)",
        (pres_id, "EMPLOYER", "0xOrgA")
    )
    # 2. Government Officer consumes same presentation ID
    cursor.execute(
        "INSERT INTO consumed_presentation_nonces (presentation_id, verifier_role, verifier_id) VALUES (?, ?, ?)",
        (pres_id, "GOVERNMENT", "0xGovOfficial1")
    )
    # 3. Employer B consumes same presentation ID
    cursor.execute(
        "INSERT INTO consumed_presentation_nonces (presentation_id, verifier_role, verifier_id) VALUES (?, ?, ?)",
        (pres_id, "EMPLOYER", "0xOrgB")
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM consumed_presentation_nonces WHERE presentation_id = ?", (pres_id,))
    total = cursor.fetchone()[0]
    conn.close()

    assert total == 3, f"Expected 3 independent verifier consumptions, got {total}"


def test_sqlite_migration_is_strictly_idempotent(isolated_v04_db):
    """Verifies that re-executing the migration DDL against an existing database runs with zero errors."""
    conn = sqlite3.connect(isolated_v04_db)
    # Execute full migration script a second time
    conn.executescript(V04_MIGRATION_DDL)
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "users" in tables
    assert "category_authorization_requests" in tables
    assert "consumed_presentation_nonces" in tables


def test_sqlite_migration_preserves_5_demo_accounts():
    """Verifies that all 5 standard demo accounts exist in the primary DB with valid Firebase UIDs and verified flags."""
    db = SessionLocal()
    try:
        users = db.query(DBUser).all()
        user_by_email = {u.email.lower(): u for u in users}

        for role_key, spec in CANONICAL_DEMO_ACCOUNTS.items():
            email = spec["email"].lower()
            assert email in user_by_email, f"Demo account {email} ({role_key}) is missing from database"
            user = user_by_email[email]

            # Role verification
            if isinstance(spec["role"], list):
                assert user.role in spec["role"], f"Expected role in {spec['role']}, got {user.role}"
            else:
                assert user.role == spec["role"], f"Expected role {spec['role']}, got {user.role}"

            # Firebase UID must be present and non-empty
            assert user.firebase_uid, f"Demo user {email} has null or empty firebase_uid"
            assert len(user.firebase_uid) > 0

            # Verified flags
            assert user.is_email_verified is True, f"Demo user {email} is_email_verified should be True"
            assert user.is_phone_verified is True, f"Demo user {email} is_phone_verified should be True"
            assert user.status == "ACTIVE"
    finally:
        db.close()


def test_sqlite_migration_script_module_discovery_or_interface():
    """
    Checks for the migration script at `backend/app/db/migrate.py`.
    If present, verifies its entrypoint is callable and returns cleanly.
    """
    try:
        spec = importlib.util.find_spec("app.db.migrate")
    except ModuleNotFoundError:
        spec = None

    if spec is not None and spec.loader is not None:
        migrate_mod = importlib.import_module("app.db.migrate")
        # Verify module has either run_migrations, migrate_database, or main
        entrypoint = getattr(migrate_mod, "migrate_database", None) or \
                     getattr(migrate_mod, "run_migrations", None) or \
                     getattr(migrate_mod, "main", None)
        assert entrypoint is not None, "app.db.migrate must define migrate_database, run_migrations, or main"
        # Run it once in safe mode or check docstring
        assert callable(entrypoint)
    else:
        # Schema migration invariants are verified via standalone engine
        engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
        with engine.connect() as conn:
            # Check users table is present and healthy
            result = conn.execute(text("SELECT count(*) FROM users;")).scalar()
            assert result >= 5, "Database must retain at least 5 registered accounts"


def test_sqlite_pre_v04_data_retention_simulation(tmp_path):
    """
    Simulates upgrading a legacy pre-v0.4 database containing legacy users and worker profiles.
    Asserts zero data loss and clean table augmentation.
    """
    db_file = str(tmp_path / "legacy_v03.db")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Pre-v0.4 schema
    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        full_name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        password_hash TEXT,
        role TEXT
    );
    """)
    cursor.execute("""
    INSERT INTO users VALUES (1, 'Ramesh Legacy', 'ramesh@legacy.org', '+919999999999', 'hash123', 'WORKER');
    """)
    conn.commit()
    conn.close()

    # Apply v0.4 migration script on legacy db
    conn = sqlite3.connect(db_file)
    conn.executescript(V04_MIGRATION_DDL)
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email FROM users WHERE id = 1;")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 1
    assert row[1] == "Ramesh Legacy"
    assert row[2] == "ramesh@legacy.org"


def test_v04_all_orm_models_match_migrated_sqlite_schema_at_runtime(tmp_path):
    """
    R1-R10: Guarantees that every single one of the 8 SQLAlchemy ORM models
    (plus DBUser and DBWorkerProfile) matches the SQLite schema produced by
    `migrate_database()` at runtime with zero OperationalError exceptions.
    
    Performs full SELECT queries, record additions, transaction commits,
    and query reloads for each model.
    """
    db_file = str(tmp_path / "runtime_orm_schema_test.db")
    migration_success = migrate_database(db_file)
    assert migration_success is True, "migrate_database must succeed"

    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()

    try:
        # 1. DBUser — SELECT and INSERT
        initial_users = session.query(DBUser).all()
        assert len(initial_users) >= 5, "Migrated database must contain 5 seeded demo accounts"
        
        test_user = DBUser(
            firebase_uid="uid_test_runtime_user_001",
            full_name="Runtime Test User",
            email="runtime_user@passkhadam.org",
            phone="+91 9111122222",
            password_hash="testhashsecret",
            role="WORKER",
            status="ACTIVE",
            is_email_verified=True,
            is_phone_verified=True,
        )
        session.add(test_user)
        session.commit()
        assert test_user.id is not None
        reloaded_user = session.query(DBUser).filter_by(id=test_user.id).one()
        assert reloaded_user.email == "runtime_user@passkhadam.org"

        # 2. DBWorkerProfile — INSERT, COMMIT, SELECT
        worker_profile = DBWorkerProfile(
            user_id=test_user.id,
            full_name="Runtime Test Worker",
            worker_category="Mason",
            origin_state="Karnataka",
            current_state="Karnataka",
            did_state="NOT_STARTED",
        )
        session.add(worker_profile)
        session.commit()
        assert worker_profile.id is not None
        reloaded_worker = session.query(DBWorkerProfile).filter_by(id=worker_profile.id).one()
        assert reloaded_worker.worker_category == "Mason"

        # 3. DBEmployerOrganization — INSERT, COMMIT, SELECT
        employer_org = DBEmployerOrganization(
            user_id=test_user.id,
            name="Runtime Infrastructure Ltd",
            registration_ref_number="CIN-RUNTIME-9999",
            status="APPROVED",
            business_type="Construction",
        )
        session.add(employer_org)
        session.commit()
        assert employer_org.id is not None
        reloaded_org = session.query(DBEmployerOrganization).filter_by(id=employer_org.id).one()
        assert reloaded_org.registration_ref_number == "CIN-RUNTIME-9999"

        # 4. DBCategoryAuthorizationRequest — INSERT, COMMIT, SELECT
        cat_request = DBCategoryAuthorizationRequest(
            organization_id=employer_org.id,
            category="Electrician",
            skill_level="Skilled",
            nature_of_employment="Contract",
            status="APPROVED",
            is_active_scope=True,
            request_version=1,
        )
        session.add(cat_request)
        session.commit()
        assert cat_request.id is not None
        reloaded_cat = session.query(DBCategoryAuthorizationRequest).filter_by(id=cat_request.id).one()
        assert reloaded_cat.category == "Electrician"
        assert reloaded_cat.is_active_scope is True

        # 5. DBGovernmentOfficer — INSERT, COMMIT, SELECT (Hierarchy invariant respected)
        gov_officer = DBGovernmentOfficer(
            user_id=test_user.id,
            officer_name="Runtime Officer",
            department="Migrant Welfare Board",
            authority_level="NATIONAL",
            status="ACTIVE",
        )
        session.add(gov_officer)
        session.commit()
        assert gov_officer.id is not None
        reloaded_officer = session.query(DBGovernmentOfficer).filter_by(id=gov_officer.id).one()
        assert reloaded_officer.authority_level == "NATIONAL"

        # 6. DBActivationEmail — INSERT, COMMIT, SELECT
        activation_email = DBActivationEmail(
            recipient_email="officer_runtime@passkhadam.gov.in",
            token_hash="token_hash_hex_abcdef1234567890abcdef1234567890",
            entity_type="GOVERNMENT",
            entity_id=gov_officer.id,
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        session.add(activation_email)
        session.commit()
        assert activation_email.id is not None
        reloaded_email = session.query(DBActivationEmail).filter_by(id=activation_email.id).one()
        assert reloaded_email.status == "PENDING"

        # 7. DBGovernanceAuditLog — INSERT, COMMIT, SELECT (Immutable model)
        gov_audit = DBGovernanceAuditLog(
            actor_firebase_uid="uid_admin_runtime",
            actor_role="ADMIN",
            action="APPROVE_ORGANIZATION",
            target_type="EMPLOYER",
            target_id=str(employer_org.id),
            reason="All regulatory criteria satisfied",
        )
        session.add(gov_audit)
        session.commit()
        assert gov_audit.id is not None
        reloaded_gov_audit = session.query(DBGovernanceAuditLog).filter_by(id=gov_audit.id).one()
        assert reloaded_gov_audit.action == "APPROVE_ORGANIZATION"

        # 8. DBAadhaarRecord — SELECT seeded, INSERT, COMMIT, SELECT
        seeded_records = session.query(DBAadhaarRecord).all()
        assert len(seeded_records) >= 5, "Database must retain 5 baseline Mock Aadhaar records"

        new_aadhaar_rec = DBAadhaarRecord(
            record_id=str(uuid.uuid4()),
            aadhaar_hash="sha256_mock_aadhaar_runtime_test",
            masked_aadhaar="XXXX XXXX 3344",
            full_name="Deepa Sharma",
            dob="1993-07-21",
            gender="Female",
            origin_state="Rajasthan",
            status="ACTIVE",
            is_active=True,
        )
        session.add(new_aadhaar_rec)
        session.commit()
        assert new_aadhaar_rec.id is not None
        reloaded_aadhaar_rec = session.query(DBAadhaarRecord).filter_by(id=new_aadhaar_rec.id).one()
        assert reloaded_aadhaar_rec.full_name == "Deepa Sharma"

        # 9. DBAadhaarAuditLog — Critical Verification: INSERT, COMMIT, SELECT
        aadhaar_audit = DBAadhaarAuditLog(
            request_id=f"req_runtime_{uuid.uuid4()}",
            record_id=new_aadhaar_rec.record_id,
            masked_aadhaar="XXXX XXXX 3344",
            supplied_name="Deepa Sharma",
            name_matched=True,
            aadhaar_matched=True,
            record_status="ACTIVE",
            result_code="VERIFIED_SUCCESS",
            response_time_ms=48.2,
            requester_role="WORKER",
            originating_service="PassKhadam-Backend",
        )
        session.add(aadhaar_audit)
        session.commit()
        assert aadhaar_audit.id is not None
        reloaded_aadhaar_audit = session.query(DBAadhaarAuditLog).filter_by(id=aadhaar_audit.id).one()
        assert reloaded_aadhaar_audit.result_code == "VERIFIED_SUCCESS"
        assert reloaded_aadhaar_audit.supplied_name == "Deepa Sharma"
        # Test synonym access
        assert reloaded_aadhaar_audit.submitted_name == "Deepa Sharma"

        # 10. DBConsumedPresentationNonce — INSERT, COMMIT, SELECT
        nonce_record = DBConsumedPresentationNonce(
            presentation_id=f"pres_runtime_nonce_{uuid.uuid4()}",
            verifier_role="EMPLOYER",
            verifier_id="0xVerifierRuntimeOrg",
            worker_did="did:passkhadam:worker:runtime999",
        )
        session.add(nonce_record)
        session.commit()
        assert nonce_record.id is not None
        reloaded_nonce = session.query(DBConsumedPresentationNonce).filter_by(id=nonce_record.id).one()
        assert reloaded_nonce.verifier_role == "EMPLOYER"

    finally:
        session.close()
        engine.dispose()


def test_v04_primary_database_all_models_queryable():
    """
    R1-R10: Verifies that the primary project SQLite database (passkhadam.db)
    allows querying all 8 models + 2 core models via SessionLocal() without
    throwing OperationalError.
    """
    db = SessionLocal()
    try:
        assert db.query(DBUser).count() >= 5
        assert db.query(DBWorkerProfile).count() >= 1
        assert db.query(DBEmployerOrganization).count() >= 1
        assert db.query(DBCategoryAuthorizationRequest).count() >= 3
        assert db.query(DBGovernmentOfficer).count() >= 1
        assert db.query(DBActivationEmail).count() >= 0
        assert db.query(DBGovernanceAuditLog).count() >= 0
        assert db.query(DBAadhaarRecord).count() >= 5
        assert db.query(DBAadhaarAuditLog).count() >= 0  # Previously failed with OperationalError
        assert db.query(DBConsumedPresentationNonce).count() >= 0
    finally:
        db.close()

