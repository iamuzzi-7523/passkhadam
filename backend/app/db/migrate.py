"""
backend/app/db/migrate.py
Authoritative Database Migration & Schema Invariants Pipeline for PASSKHADAM v0.4

Preserves existing users and Firebase UIDs.
Creates all v0.4 mandated tables, partial unique index `uq_active_category_scope`,
migrates existing Employer and Government users, and populates initial baseline Mock Aadhaar records.
Fully idempotent.
"""

import os
import sys
import json
import uuid
import hashlib
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("passkhadam.migration")

# Add backend directory to path if running standalone
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    from app.core.config import settings
    DEFAULT_DB_PATH = settings.DATABASE_URL.replace("sqlite:///", "")
except Exception:
    DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "app", "storage", "passkhadam.db")

CANONICAL_DEMO_ACCOUNTS = [
    {
        "email": "worker@passkhadam.org",
        "full_name": "Mohammed Uzair",
        "phone": "+91 9876543210",
        "role": "WORKER",
        "firebase_uid": "gz64njiIhYcxQs8C9aneVA5xuIM2",
        "status": "ACTIVE",
    },
    {
        "email": "employer@apexinfra.com",
        "full_name": "Apex Infrastructure Admin",
        "phone": "+91 9876543211",
        "role": "EMPLOYER",
        "firebase_uid": "ap5EyBFdR8OjNqHc1soS61E088s2",
        "status": "ACTIVE",
        "org_name": "Apex Infrastructure & Construction Ltd",
        "org_addr": "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
        "org_status": "APPROVED",
        "reg_ref": "CIN-U72200MH2020PTC123456",
    },
    {
        "email": "gov@maharashtra.gov.in",
        "full_name": "Maharashtra Labour Welfare Officer",
        "phone": "+91 9876543212",
        "role": "GOVERNMENT",
        "firebase_uid": "tMfQ1nQGDIWBlw6VFsNqZa7TtY33",
        "status": "ACTIVE",
        "org_name": "Maharashtra State Migrant Welfare Board",
        "org_addr": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
        "org_status": "APPROVED",
    },
    {
        "email": "admin@passkhadam.org",
        "full_name": "PassKhadam Platform Governance",
        "phone": "+91 9876543213",
        "role": "ADMIN",
        "firebase_uid": "ZOGbgd8LfYPgu7VhcUESBEIzZp03",
        "status": "ACTIVE",
    },
    {
        "email": "authority@uidai.gov.in",
        "full_name": "UIDAI Mock Authority Gateway",
        "phone": "+91 9876543214",
        "role": "AADHAAR",
        "firebase_uid": "brrBrUNoznVmENZPQUrRCPiBchF2",
        "status": "ACTIVE",
    },
]

BASELINE_AADHAAR_RECORDS = [
    {
        "aadhaar_number": "123456784821",
        "full_name": "Mohammed Uzair",
        "dob": "1995-04-12",
        "gender": "Male",
        "origin_state": "Karnataka",
        "address": "45/2 BTM Layout, Bengaluru, Karnataka",
        "is_active": True,
    },
    {
        "aadhaar_number": "987654321012",
        "full_name": "Ramesh Kumar Verma",
        "dob": "1992-08-20",
        "gender": "Male",
        "origin_state": "Bihar",
        "address": "Village Chhatarpur, Dist Patna, Bihar",
        "is_active": True,
    },
    {
        "aadhaar_number": "554433221100",
        "full_name": "Sunita Devi",
        "dob": "1998-11-05",
        "gender": "Female",
        "origin_state": "Uttar Pradesh",
        "address": "Sector 14, Gorakhpur, UP",
        "is_active": True,
    },
    {
        "aadhaar_number": "112233445566",
        "full_name": "Anil Sahu",
        "dob": "1989-02-14",
        "gender": "Male",
        "origin_state": "Odisha",
        "address": "Ward 3, Ganjam, Odisha",
        "is_active": True,
    },
    {
        "aadhaar_number": "998877665544",
        "full_name": "Lakshmi Narayana",
        "dob": "1994-06-30",
        "gender": "Female",
        "origin_state": "Andhra Pradesh",
        "address": "Main Road, Guntur, AP",
        "is_active": False,
    },
]


def ensure_column_exists(cursor: sqlite3.Cursor, table_name: str, col_name: str, col_def: str):
    """Safely adds a column to an existing SQLite table if not already present."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if col_name not in existing_cols:
        logger.info(f"Adding column '{col_name}' to table '{table_name}'...")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def};")


def migrate_database(db_path: Optional[str] = None) -> bool:
    """
    Executes the complete idempotent migration pipeline.
    """
    target_path = db_path or DEFAULT_DB_PATH
    logger.info(f"Starting PassKhadam v0.4 database migration on: {target_path}")

    # Ensure parent directory exists
    parent_dir = os.path.dirname(os.path.abspath(target_path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(target_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = ON;")

        # ====================================================================
        # 1. TABLE CREATION / AUGMENTATION
        # ====================================================================

        # 1.1 Users table
        cursor.execute("""
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
        """)
        # Schema evolution for users
        ensure_column_exists(cursor, "users", "firebase_uid", "VARCHAR(128)")
        ensure_column_exists(cursor, "users", "status", "VARCHAR(50) DEFAULT 'ACTIVE'")
        ensure_column_exists(cursor, "users", "organization_address", "VARCHAR(100)")
        ensure_column_exists(cursor, "users", "organization_name", "VARCHAR(150)")
        ensure_column_exists(cursor, "users", "organization_status", "VARCHAR(50)")
        ensure_column_exists(cursor, "users", "is_email_verified", "BOOLEAN DEFAULT 1")
        ensure_column_exists(cursor, "users", "is_phone_verified", "BOOLEAN DEFAULT 1")
        ensure_column_exists(cursor, "users", "created_at", "TIMESTAMP")

        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);")

        # 1.2 Worker Profiles table
        cursor.execute("""
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
            failure_reason TEXT,
            tx_hash VARCHAR(128),
            block_number INTEGER,
            chain_id INTEGER,
            contract_address VARCHAR(100),
            aadhaar_request_id VARCHAR(100),
            aadhaar_record_id VARCHAR(36),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # Schema evolution for worker_profiles
        ensure_column_exists(cursor, "worker_profiles", "did_state", "VARCHAR(50) DEFAULT 'NOT_STARTED'")
        ensure_column_exists(cursor, "worker_profiles", "failure_reason", "TEXT")
        ensure_column_exists(cursor, "worker_profiles", "tx_hash", "VARCHAR(128)")
        ensure_column_exists(cursor, "worker_profiles", "block_number", "INTEGER")
        ensure_column_exists(cursor, "worker_profiles", "chain_id", "INTEGER")
        ensure_column_exists(cursor, "worker_profiles", "contract_address", "VARCHAR(100)")
        ensure_column_exists(cursor, "worker_profiles", "aadhaar_request_id", "VARCHAR(100)")
        ensure_column_exists(cursor, "worker_profiles", "aadhaar_record_id", "VARCHAR(36)")
        ensure_column_exists(cursor, "worker_profiles", "created_at", "TIMESTAMP")
        ensure_column_exists(cursor, "worker_profiles", "updated_at", "TIMESTAMP")

        cursor.execute("CREATE INDEX IF NOT EXISTS ix_worker_profiles_id ON worker_profiles (id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_worker_profiles_user_id ON worker_profiles (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_worker_profiles_did ON worker_profiles (did);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_worker_profiles_aadhaar_record_id ON worker_profiles (aadhaar_record_id);")

        # 1.3 Employer Organizations table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS employer_organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            name VARCHAR(150) NOT NULL,
            registration_ref_number VARCHAR(100) NOT NULL,
            registration_number VARCHAR(100),
            registration_type VARCHAR(50) DEFAULT 'CIN',
            registration_authority VARCHAR(100) DEFAULT 'MCA',
            registration_date VARCHAR(50),
            business_type VARCHAR(100),
            nature_of_business VARCHAR(150),
            business_address TEXT,
            state_code VARCHAR(10) DEFAULT 'KA',
            website VARCHAR(150),
            expected_workforce INTEGER DEFAULT 50,
            official_email VARCHAR(150),
            official_phone VARCHAR(50),
            contact_person VARCHAR(150),
            contact_phone VARCHAR(50),
            org_address VARCHAR(100),
            status VARCHAR(50) DEFAULT 'PENDING_REVIEW',
            rejection_reason TEXT,
            suspension_reason TEXT,
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        ensure_column_exists(cursor, "employer_organizations", "registration_ref_number", "VARCHAR(100)")
        ensure_column_exists(cursor, "employer_organizations", "registration_number", "VARCHAR(100)")
        ensure_column_exists(cursor, "employer_organizations", "org_address", "VARCHAR(100)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_employer_organizations_user_id ON employer_organizations (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_employer_organizations_ref ON employer_organizations (registration_ref_number);")

        # 1.4 Category Authorization Requests table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_authorization_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES employer_organizations(id),
            category VARCHAR(100) NOT NULL,
            skill_level VARCHAR(50) NOT NULL DEFAULT 'Skilled',
            nature_of_employment VARCHAR(50) NOT NULL DEFAULT 'Contract',
            work_context VARCHAR(150) DEFAULT 'Construction',
            status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
            is_active_scope BOOLEAN NOT NULL DEFAULT 0,
            request_version INTEGER NOT NULL DEFAULT 1,
            reason TEXT,
            review_reason TEXT,
            requested_information TEXT,
            supporting_documents_json TEXT,
            reviewed_by VARCHAR(128),
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_cat_auth_req_org_id ON category_authorization_requests (organization_id);")

        # 1.5 Partial Unique Index on Active Scopes
        cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_category_scope 
        ON category_authorization_requests (organization_id, category, skill_level, nature_of_employment) 
        WHERE is_active_scope = 1;
        """)

        # 1.6 Government Officers table
        table_info = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='government_officers'").fetchone()
        if table_info and table_info[0] and "ck_officer_geographic_hierarchy" not in table_info[0]:
            cursor.execute("PRAGMA foreign_keys=OFF;")
            cursor.execute("ALTER TABLE government_officers RENAME TO _government_officers_old;")
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
            );
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
            FROM _government_officers_old;
            """)
            cursor.execute("DROP TABLE _government_officers_old;")
            cursor.execute("PRAGMA foreign_keys=ON;")
        else:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS government_officers (
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
            );
            """)
        ensure_column_exists(cursor, "government_officers", "officer_name", "VARCHAR(150)")
        ensure_column_exists(cursor, "government_officers", "full_name", "VARCHAR(150)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_government_officers_user_id ON government_officers (user_id);")

        # 1.7 Activation Emails table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS activation_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email VARCHAR(150) NOT NULL,
            token_hash VARCHAR(128) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER NOT NULL,
            subject VARCHAR(255),
            template_name VARCHAR(100),
            custom_message TEXT,
            status VARCHAR(50) DEFAULT 'PENDING',
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            last_error TEXT,
            expires_at TIMESTAMP NOT NULL,
            sent_at TIMESTAMP,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_activation_emails_token_hash ON activation_emails (token_hash);")

        # 1.8 Governance Audit Logs table
        cursor.execute("""
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_gov_audit_actor ON governance_audit_logs (actor_firebase_uid);")

        # 1.8.1 SQLite Immutability Triggers for Governance Audit Logs
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_governance_audit_update
        BEFORE UPDATE ON governance_audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'DBGovernanceAuditLog is immutable; update operations are strictly prohibited.');
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_governance_audit_delete
        BEFORE DELETE ON governance_audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'DBGovernanceAuditLog is immutable; delete operations are strictly prohibited.');
        END;
        """)

        # 1.9 Mock Aadhaar Records table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS aadhaar_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id VARCHAR(64) UNIQUE NOT NULL,
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
        """)
        ensure_column_exists(cursor, "aadhaar_records", "is_active", "BOOLEAN DEFAULT 1")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_aadhaar_records_record_id ON aadhaar_records (record_id);")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_aadhaar_records_aadhaar_hash ON aadhaar_records (aadhaar_hash);")

        # 1.10 Aadhaar Audit Logs table
        cursor.execute("""
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
        """)
        ensure_column_exists(cursor, "aadhaar_audit_logs", "supplied_name", "VARCHAR(150)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_aadhaar_audit_req ON aadhaar_audit_logs (request_id);")

        # 1.10.1 SQLite Immutability Triggers for Aadhaar Audit Logs
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_aadhaar_audit_update
        BEFORE UPDATE ON aadhaar_audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'DBAadhaarAuditLog is immutable; update operations are strictly prohibited.');
        END;
        """)
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_aadhaar_audit_delete
        BEFORE DELETE ON aadhaar_audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'DBAadhaarAuditLog is immutable; delete operations are strictly prohibited.');
        END;
        """)

        # 1.11 Consumed Presentation Nonces table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS consumed_presentation_nonces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            presentation_id VARCHAR(128) NOT NULL,
            verifier_role VARCHAR(50) NOT NULL,
            verifier_id VARCHAR(128) NOT NULL,
            worker_did VARCHAR(100),
            consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_presentation_verifier_context UNIQUE (presentation_id, verifier_role, verifier_id)
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_consumed_pres_id ON consumed_presentation_nonces (presentation_id);")

        # 1.12 Legacy Category Requests table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_address VARCHAR(100) NOT NULL,
            category VARCHAR(100) NOT NULL,
            reason TEXT,
            status VARCHAR(50) DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # ====================================================================
        # 2. DATA PRESERVATION & BASELINE SEEDING
        # ====================================================================

        # 2.1 Preserve / Seed 5 Canonical Demo Accounts
        default_pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()
        worker_user_id = None

        for acc in CANONICAL_DEMO_ACCOUNTS:
            cursor.execute("SELECT id, firebase_uid, email, full_name, phone, role, status FROM users WHERE lower(email) = lower(?)", (acc["email"],))
            row = cursor.fetchone()
            if row:
                u_id, existing_uid, _, _, _, existing_role, _ = row
                # Preserve existing non-empty authentic firebase_uid
                final_uid = existing_uid if (existing_uid and len(existing_uid.strip()) > 0) else acc["firebase_uid"]
                # Keep existing role if it's already an accepted variant (e.g. AADHAAR or AADHAAR_ADMIN)
                final_role = existing_role if (acc["role"] == "AADHAAR" and existing_role in ("AADHAAR", "AADHAAR_ADMIN")) else acc["role"]
                cursor.execute("""
                    UPDATE users
                    SET firebase_uid = ?,
                        full_name = ?,
                        phone = ?,
                        role = ?,
                        status = 'ACTIVE',
                        is_email_verified = 1,
                        is_phone_verified = 1
                    WHERE id = ?;
                """, (final_uid, acc["full_name"], acc["phone"], final_role, u_id))
                if acc["role"] == "WORKER":
                    worker_user_id = u_id
            else:
                cursor.execute("""
                    INSERT INTO users (
                        firebase_uid, full_name, email, phone, password_hash,
                        role, status, is_email_verified, is_phone_verified
                    ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', 1, 1);
                """, (acc["firebase_uid"], acc["full_name"], acc["email"], acc["phone"], default_pw_hash, acc["role"]))
                if acc["role"] == "WORKER":
                    worker_user_id = cursor.lastrowid

        # Ensure demo worker profile exists
        if worker_user_id:
            cursor.execute("SELECT id FROM worker_profiles WHERE user_id = ?", (worker_user_id,))
            if not cursor.fetchone():
                skills = json.dumps(["Mason", "Bricklaying", "Concrete Work", "Plumbing Assistance"])
                cursor.execute("""
                    INSERT INTO worker_profiles (
                        user_id, full_name, dob, gender, origin_state, current_state,
                        address, worker_category, skills_json, is_aadhaar_verified
                    ) VALUES (?, 'Mohammed Uzair', '1995-04-12', 'Male', 'Karnataka', 'Karnataka',
                              '45/2 BTM Layout, Bengaluru, Karnataka', 'Mason', ?, 0);
                """, (worker_user_id, skills))

        # 2.2 Migrate Employer Users into DBEmployerOrganization
        cursor.execute("SELECT id, email, full_name, phone, status, organization_name, organization_address, organization_status FROM users WHERE role = 'EMPLOYER';")
        employers = cursor.fetchall()
        for emp in employers:
            u_id, u_email, u_name, u_phone, u_status, u_org_name, u_org_addr, u_org_status = emp
            cursor.execute("SELECT id FROM employer_organizations WHERE user_id = ?", (u_id,))
            existing_org = cursor.fetchone()
            if not existing_org:
                org_name = u_org_name if u_org_name else (u_name or "Employer Organization")
                if u_email.lower() == "employer@apexinfra.com":
                    reg_ref = "CIN-U72200MH2020PTC123456"
                    final_status = "APPROVED"
                elif u_email.lower() == "howrubrother9@gmail.com":
                    reg_ref = "CIN-U45200KA2021PTC987654"
                    final_status = "PENDING_REVIEW"
                else:
                    reg_ref = f"REF-ORG-{u_id:04d}"
                    final_status = "DISABLED" if u_status == "DISABLED" else (u_org_status or "PENDING_REVIEW")

                cursor.execute("""
                    INSERT INTO employer_organizations (
                        user_id, name, registration_ref_number, registration_number,
                        registration_type, registration_authority, business_type, nature_of_business,
                        official_email, official_phone, contact_person, status, org_address
                    ) VALUES (?, ?, ?, ?, 'CIN', 'MCA', 'Construction & Infrastructure', 'Civil Engineering & Contracting', ?, ?, ?, ?, ?);
                """, (u_id, org_name, reg_ref, reg_ref, u_email, u_phone, u_name, final_status, u_org_addr))
                org_id = cursor.lastrowid
            else:
                org_id = existing_org[0]

            # For Apex, seed baseline approved active categories if none exist
            if u_email.lower() == "employer@apexinfra.com":
                cursor.execute("SELECT COUNT(*) FROM category_authorization_requests WHERE organization_id = ?;", (org_id,))
                if cursor.fetchone()[0] == 0:
                    baseline_scopes = [
                        ("Mason", "Skilled", "Contract", "APPROVED", 1, 1, "Platform pre-approved category"),
                        ("Electrician", "Skilled", "Permanent", "APPROVED", 1, 1, "Platform pre-approved category"),
                        ("Plumber", "Semi-Skilled", "Contract", "APPROVED", 1, 1, "Platform pre-approved category"),
                    ]
                    for cat, skl, nat, st, act, ver, rsn in baseline_scopes:
                        cursor.execute("""
                            INSERT INTO category_authorization_requests (
                                organization_id, category, skill_level, nature_of_employment,
                                status, is_active_scope, request_version, review_reason
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """, (org_id, cat, skl, nat, st, act, ver, rsn))

                    # Migrate legacy category requests to new table with is_active_scope = 0
                    cursor.execute("SELECT category, reason, status, created_at FROM category_requests WHERE employer_address = ?;", ("0x90F79bf6EB2c4f870365E785982E1f101E93b906",))
                    legacy_reqs = cursor.fetchall()
                    for l_cat, l_rsn, l_st, l_ts in legacy_reqs:
                        # Avoid duplicates if category already active
                        cursor.execute("SELECT id FROM category_authorization_requests WHERE organization_id = ? AND category = ? AND is_active_scope = 1;", (org_id, l_cat))
                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO category_authorization_requests (
                                    organization_id, category, skill_level, nature_of_employment,
                                    status, is_active_scope, request_version, review_reason, submitted_at
                                ) VALUES (?, ?, 'Skilled', 'Contract', ?, 0, 1, ?, ?);
                            """, (org_id, l_cat, l_st, l_rsn, l_ts))

            # 2.2.1 Seed canonical activation token for Apex Infrastructure (act_b906_secure)
            if u_email.lower() == "employer@apexinfra.com":
                apex_token = "act_b906_secure"
                apex_token_hash = hashlib.sha256(apex_token.encode("utf-8")).hexdigest()
                cursor.execute("SELECT id FROM activation_emails WHERE token_hash = ?;", (apex_token_hash,))
                existing_act = cursor.fetchone()
                expires_at_str = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
                if not existing_act:
                    cursor.execute("""
                        INSERT INTO activation_emails (
                            recipient_email, token_hash, entity_type, entity_id, subject,
                            template_name, status, attempt_count, max_attempts, expires_at
                        ) VALUES (
                            'employer@apexinfra.com', ?, 'EMPLOYER', ?, 'Apex Infrastructure Account Activation',
                            'employer_activation', 'PENDING', 0, 3, ?
                        );
                    """, (apex_token_hash, org_id, expires_at_str))

        # 2.3 Migrate Government Users into DBGovernmentOfficer
        cursor.execute("SELECT id, email, full_name, phone, status, organization_name, organization_address, organization_status FROM users WHERE role = 'GOVERNMENT';")
        gov_users = cursor.fetchall()
        for gu in gov_users:
            u_id, u_email, u_name, u_phone, u_status, u_org_name, u_org_addr, u_org_status = gu
            cursor.execute("SELECT id FROM government_officers WHERE user_id = ?;", (u_id,))
            if not cursor.fetchone():
                dept = u_org_name if u_org_name else "Maharashtra State Migrant Welfare Board"
                perms = json.dumps([
                    "WORKER_VERIFICATION",
                    "CROSS_STATE_VERIFICATION",
                    "VIEW_EMPLOYMENT",
                    "VIEW_WELFARE_ELIGIBILITY",
                    "CREATE_BENEFIT_CLAIM",
                    "DISBURSE_BENEFIT",
                    "VIEW_CLAIM_HISTORY",
                    "AUDIT_VIEW"
                ])
                benefit_perms = json.dumps([
                    "Interstate Migrant Worker Relief",
                    "Accident Relief",
                    "Housing Allowance"
                ])
                ref_id = f"GOV-OFF-{u_id:04d}"
                gov_status = "ACTIVE" if u_status == "ACTIVE" else "PROVISIONED"
                cursor.execute("""
                    INSERT INTO government_officers (
                        user_id, officer_name, full_name, department, designation,
                        authority_level, state, district, block, officer_reference_id,
                        permissions_json, benefit_permissions_json, status, official_email, phone, wallet_address
                    ) VALUES (?, ?, ?, ?, 'State Welfare Commissioner', 'STATE', 'Maharashtra', NULL, NULL, ?, ?, ?, ?, ?, ?, ?);
                """, (u_id, u_name, u_name, dept, ref_id, perms, benefit_perms, gov_status, u_email, u_phone, u_org_addr))

        # 2.4 Populate Initial Baseline Mock Aadhaar Records
        for rec in BASELINE_AADHAAR_RECORDS:
            raw_num = rec["aadhaar_number"]
            a_hash = hashlib.sha256(raw_num.encode("utf-8")).hexdigest()
            rec_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"passkhadam:aadhaar:{raw_num}"))
            masked = f"XXXX XXXX {raw_num[-4:]}"
            status_str = "ACTIVE" if rec["is_active"] else "INACTIVE"
            is_act = 1 if rec["is_active"] else 0

            cursor.execute("SELECT id FROM aadhaar_records WHERE aadhaar_hash = ? OR record_id = ?;", (a_hash, rec_id))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO aadhaar_records (
                        record_id, aadhaar_hash, masked_aadhaar, full_name,
                        dob, gender, origin_state, address, status, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (rec_id, a_hash, masked, rec["full_name"], rec["dob"], rec["gender"], rec["origin_state"], rec["address"], status_str, is_act))

        # 2.5 Authoritative Backfill Reconciliation for worker_profiles.aadhaar_record_id
        logger.info("Executing authoritative backfill reconciliation for worker_profiles...")

        # A. Sanitize dangling references where aadhaar_record_id does not exist in aadhaar_records
        cursor.execute("""
            SELECT wp.id, wp.aadhaar_record_id, wp.aadhaar_request_id
            FROM worker_profiles wp
            LEFT JOIN aadhaar_records ar ON wp.aadhaar_record_id = ar.record_id
            WHERE wp.aadhaar_record_id IS NOT NULL 
              AND length(trim(wp.aadhaar_record_id)) > 0
              AND ar.id IS NULL;
        """)
        dangling_profiles = cursor.fetchall()
        for wp_id, bad_rec_id, req_id in dangling_profiles:
            reconciled = False
            if req_id and len(req_id.strip()) > 0:
                cursor.execute("""
                    SELECT record_id FROM aadhaar_audit_logs
                    WHERE request_id = ? AND result_code = 'SUCCESS' AND record_id IS NOT NULL;
                """, (req_id.strip(),))
                audit_rows = cursor.fetchall()
                if len(audit_rows) == 1:
                    matched_rec = audit_rows[0][0]
                    cursor.execute("SELECT id FROM aadhaar_records WHERE record_id = ?;", (matched_rec,))
                    if cursor.fetchone():
                        cursor.execute("UPDATE worker_profiles SET aadhaar_record_id = ? WHERE id = ?;", (matched_rec, wp_id))
                        reconciled = True
                        logger.info(f"Corrected dangling link for worker_profile id={wp_id} -> {matched_rec}")
            if not reconciled:
                cursor.execute("UPDATE worker_profiles SET aadhaar_record_id = NULL WHERE id = ?;", (wp_id,))
                logger.warning(f"Sanitized dangling aadhaar_record_id to NULL for worker_profile id={wp_id}")

        # B. Authoritative reconciliation backfill: match aadhaar_request_id to SUCCESS audit logs
        cursor.execute("""
            SELECT id, aadhaar_request_id
            FROM worker_profiles
            WHERE (aadhaar_record_id IS NULL OR length(trim(aadhaar_record_id)) = 0)
              AND aadhaar_request_id IS NOT NULL
              AND length(trim(aadhaar_request_id)) > 0;
        """)
        unlinked_profiles = cursor.fetchall()
        reconciled_count = 0
        unresolved_count = 0

        for wp_id, req_id in unlinked_profiles:
            cursor.execute("""
                SELECT record_id
                FROM aadhaar_audit_logs
                WHERE request_id = ?
                  AND result_code = 'SUCCESS'
                  AND record_id IS NOT NULL
                  AND length(trim(record_id)) > 0;
            """, (req_id.strip(),))
            audit_rows = cursor.fetchall()

            # Strict Unambiguous Rule: exactly one SUCCESS audit log with matching request_id
            if len(audit_rows) == 1:
                matched_rec_id = audit_rows[0][0]
                cursor.execute("SELECT id FROM aadhaar_records WHERE record_id = ?;", (matched_rec_id,))
                if cursor.fetchone():
                    cursor.execute("UPDATE worker_profiles SET aadhaar_record_id = ? WHERE id = ?;", (matched_rec_id, wp_id))
                    reconciled_count += 1
                    logger.info(f"Reconciled worker_profile id={wp_id} with aadhaar_record_id={matched_rec_id}")
                else:
                    unresolved_count += 1
                    logger.warning(f"Audit record_id={matched_rec_id} not found in aadhaar_records for profile id={wp_id}. Kept unset.")
            else:
                unresolved_count += 1
                if len(audit_rows) > 1:
                    logger.warning(f"Ambiguous audit logs ({len(audit_rows)}) for worker_profile id={wp_id}, request_id={req_id}. Kept unset.")
                else:
                    logger.info(f"No successful audit log for worker_profile id={wp_id}, request_id={req_id}. Kept unset.")

        logger.info(f"Authoritative reconciliation complete: {reconciled_count} reconciled, {unresolved_count} unresolved.")

        conn.commit()
        logger.info("PassKhadam v0.4 database migration completed successfully.")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed with error: {str(e)}", exc_info=True)
        raise e
    finally:
        conn.close()


def run_migrations(db_path: Optional[str] = None) -> bool:
    """Convenience alias for migrate_database."""
    return migrate_database(db_path=db_path)


def main():
    """CLI entrypoint for standalone execution."""
    import argparse
    parser = argparse.ArgumentParser(description="PassKhadam v0.4 Database Migration Tool")
    parser.add_argument("--db-path", type=str, default=None, help="Target SQLite database file path")
    args = parser.parse_args()

    success = migrate_database(db_path=args.db_path)
    if success:
        print("Migration succeeded.")
        sys.exit(0)
    else:
        print("Migration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
