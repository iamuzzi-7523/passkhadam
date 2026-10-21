"""
PassKhadam v0.5 — Test Suite: R1 Aadhaar Source-Record Migration & Authoritative Backfill
========================================================================================
Covers Milestone 1 (M1) Requirement R1:
- Column addition of aadhaar_record_id VARCHAR(36) to worker_profiles
- Authoritative reconciliation backfill matching aadhaar_request_id to SUCCESS audit logs
- Idempotency across repeat migration runs
- Handling of missing audit logs (profile left unlinked)
- Handling of ambiguous audit logs (profile left unlinked)
- Handling of failed verification audit logs (profile left unlinked)
- Handling of dangling audit record IDs (profile left unlinked)
- Strict no-fuzzy demographic matching (profiles without unambiguous link remain NULL)
- Sanitization of dangling links where aadhaar_record_id does not exist in aadhaar_records
- Correction of dangling links when valid audit log exists
"""

import os
import sys
import sqlite3
import tempfile
import uuid
import hashlib
from datetime import datetime
import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.migrate import migrate_database


def create_pre_v05_database(db_path: str) -> None:
    """Creates a pre-v0.5 SQLite database schema without aadhaar_record_id in worker_profiles."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        firebase_uid VARCHAR(128) UNIQUE NOT NULL,
        full_name VARCHAR(150) NOT NULL,
        email VARCHAR(150) UNIQUE NOT NULL,
        phone VARCHAR(50) NOT NULL,
        password_hash VARCHAR(256) NOT NULL,
        role VARCHAR(50) NOT NULL,
        status VARCHAR(50) DEFAULT 'ACTIVE',
        organization_address VARCHAR(100),
        organization_name VARCHAR(150),
        organization_status VARCHAR(50),
        is_email_verified BOOLEAN DEFAULT 1,
        is_phone_verified BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE worker_profiles (
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE aadhaar_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id VARCHAR(64) UNIQUE NOT NULL,
        aadhaar_hash VARCHAR(128) UNIQUE NOT NULL,
        masked_aadhaar VARCHAR(50) NOT NULL,
        full_name VARCHAR(150) NOT NULL,
        dob VARCHAR(50),
        gender VARCHAR(20),
        origin_state VARCHAR(100),
        address TEXT,
        status VARCHAR(50) DEFAULT 'ACTIVE',
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE aadhaar_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id VARCHAR(100) NOT NULL,
        record_id VARCHAR(64),
        masked_aadhaar VARCHAR(50) NOT NULL,
        supplied_name VARCHAR(150),
        name_matched BOOLEAN NOT NULL,
        aadhaar_matched BOOLEAN NOT NULL,
        record_status VARCHAR(50) NOT NULL,
        result_code VARCHAR(50) NOT NULL,
        response_time_ms FLOAT,
        requester_role VARCHAR(50) NOT NULL,
        originating_service VARCHAR(100) NOT NULL,
        failure_reason TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


def test_migration_adds_aadhaar_record_id_column():
    """Verify that running migration adds aadhaar_record_id column and index to worker_profiles."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        # Check column does not exist initially
        conn = sqlite3.connect(db_path)
        cols_before = [col[1] for col in conn.cursor().execute("PRAGMA table_info(worker_profiles);").fetchall()]
        conn.close()
        assert "aadhaar_record_id" not in cols_before

        # Run migration
        success = migrate_database(db_path)
        assert success is True

        # Check column exists now
        conn = sqlite3.connect(db_path)
        cols_after = [col[1] for col in conn.cursor().execute("PRAGMA table_info(worker_profiles);").fetchall()]
        indices = [idx[1] for idx in conn.cursor().execute("PRAGMA index_list(worker_profiles);").fetchall()]
        conn.close()

        assert "aadhaar_record_id" in cols_after
        assert "ix_worker_profiles_aadhaar_record_id" in indices
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_authoritative_backfill_unambiguous_link():
    """Verify authoritative reconciliation links worker_profile.aadhaar_record_id via SUCCESS audit log."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        rec_id = str(uuid.uuid4())
        raw_num = "987654321012"
        a_hash = hashlib.sha256(raw_num.encode()).hexdigest()

        # Seed citizen in aadhaar_records
        cur.execute("""
            INSERT INTO aadhaar_records (record_id, aadhaar_hash, masked_aadhaar, full_name, dob, gender, origin_state, address, status, is_active)
            VALUES (?, ?, 'XXXX XXXX 1012', 'Ramesh Kumar Verma', '1992-08-20', 'Male', 'Bihar', 'Patna, Bihar', 'ACTIVE', 1);
        """, (rec_id, a_hash))

        # Seed audit log with SUCCESS
        req_id = f"req_{uuid.uuid4().hex[:10]}"
        cur.execute("""
            INSERT INTO aadhaar_audit_logs (request_id, record_id, masked_aadhaar, supplied_name, name_matched, aadhaar_matched, record_status, result_code, requester_role, originating_service)
            VALUES (?, ?, 'XXXX XXXX 1012', 'Ramesh Kumar Verma', 1, 1, 'ACTIVE', 'SUCCESS', 'WORKER', 'PassKhadam-WorkerOnboarding');
        """, (req_id, rec_id))

        # Seed user and worker profile with aadhaar_request_id
        cur.execute("""
            INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role)
            VALUES ('uid_ramesh', 'Ramesh Kumar Verma', 'ramesh@test.com', '+919876543210', 'hash', 'WORKER');
        """)
        u_id = cur.lastrowid

        cur.execute("""
            INSERT INTO worker_profiles (user_id, full_name, is_aadhaar_verified, masked_aadhaar, aadhaar_request_id, is_credential_anchored, did_state)
            VALUES (?, 'Ramesh Kumar Verma', 1, 'XXXX XXXX 1012', ?, 1, 'ACTIVE');
        """, (u_id, req_id))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Run migration
        migrate_database(db_path)

        # Assert worker_profile.aadhaar_record_id is populated
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        linked_rec_id = cur.fetchone()[0]
        conn.close()

        assert linked_rec_id == rec_id
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_authoritative_backfill_idempotent():
    """Verify that repeat migration executions are idempotent and do not corrupt existing links."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        rec_id = str(uuid.uuid4())
        req_id = f"req_{uuid.uuid4().hex[:10]}"

        cur.execute("""
            INSERT INTO aadhaar_records (record_id, aadhaar_hash, masked_aadhaar, full_name, status, is_active)
            VALUES (?, 'hash123', 'XXXX XXXX 9999', 'Anil Sahu', 'ACTIVE', 1);
        """, (rec_id,))

        cur.execute("""
            INSERT INTO aadhaar_audit_logs (request_id, record_id, masked_aadhaar, supplied_name, name_matched, aadhaar_matched, record_status, result_code, requester_role, originating_service)
            VALUES (?, ?, 'XXXX XXXX 9999', 'Anil Sahu', 1, 1, 'ACTIVE', 'SUCCESS', 'WORKER', 'PassKhadam-WorkerOnboarding');
        """, (req_id, rec_id))

        cur.execute("""
            INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role)
            VALUES ('uid_anil', 'Anil Sahu', 'anil@test.com', '+919876543211', 'hash', 'WORKER');
        """)
        u_id = cur.lastrowid

        cur.execute("""
            INSERT INTO worker_profiles (user_id, full_name, is_aadhaar_verified, masked_aadhaar, aadhaar_request_id, is_credential_anchored, did_state)
            VALUES (?, 'Anil Sahu', 1, 'XXXX XXXX 9999', ?, 1, 'ACTIVE');
        """, (u_id, req_id))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Run migration 1
        migrate_database(db_path)

        # Run migration 2
        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        final_rec_id = cur.fetchone()[0]
        conn.close()

        assert final_rec_id == rec_id
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_authoritative_backfill_missing_audit_log():
    """Verify that worker profiles with aadhaar_request_id lacking an audit log remain unlinked (NULL)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        req_id = f"orphan_req_{uuid.uuid4().hex[:10]}"

        cur.execute("""
            INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role)
            VALUES ('uid_orphan', 'Orphan Worker', 'orphan@test.com', '+919876543212', 'hash', 'WORKER');
        """)
        u_id = cur.lastrowid

        cur.execute("""
            INSERT INTO worker_profiles (user_id, full_name, is_aadhaar_verified, masked_aadhaar, aadhaar_request_id)
            VALUES (?, 'Orphan Worker', 1, 'XXXX XXXX 0000', ?);
        """, (u_id, req_id))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Run migration
        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        rec_id_val = cur.fetchone()[0]
        conn.close()

        assert rec_id_val is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_authoritative_backfill_ambiguous_audit_logs():
    """Verify that multiple conflicting SUCCESS audit logs for the same request ID are preserved as unlinked."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        rec1 = str(uuid.uuid4())
        rec2 = str(uuid.uuid4())
        req_id = "ambiguous_req_123"

        cur.execute("INSERT INTO aadhaar_records (record_id, aadhaar_hash, masked_aadhaar, full_name) VALUES (?, 'h1', 'XXXX 1', 'Worker 1');", (rec1,))
        cur.execute("INSERT INTO aadhaar_records (record_id, aadhaar_hash, masked_aadhaar, full_name) VALUES (?, 'h2', 'XXXX 2', 'Worker 2');", (rec2,))

        # Two audit logs with same request_id
        cur.execute("""
            INSERT INTO aadhaar_audit_logs (request_id, record_id, masked_aadhaar, supplied_name, name_matched, aadhaar_matched, record_status, result_code, requester_role, originating_service)
            VALUES (?, ?, 'XXXX 1', 'Worker 1', 1, 1, 'ACTIVE', 'SUCCESS', 'WORKER', 'Service');
        """, (req_id, rec1))
        cur.execute("""
            INSERT INTO aadhaar_audit_logs (request_id, record_id, masked_aadhaar, supplied_name, name_matched, aadhaar_matched, record_status, result_code, requester_role, originating_service)
            VALUES (?, ?, 'XXXX 2', 'Worker 2', 1, 1, 'ACTIVE', 'SUCCESS', 'WORKER', 'Service');
        """, (req_id, rec2))

        cur.execute("INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role) VALUES ('uid_amb', 'Amb Worker', 'amb@test.com', '123', 'pw', 'WORKER');")
        u_id = cur.lastrowid

        cur.execute("INSERT INTO worker_profiles (user_id, full_name, is_aadhaar_verified, aadhaar_request_id) VALUES (?, 'Amb Worker', 1, ?);", (u_id, req_id))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        rec_id_val = cur.fetchone()[0]
        conn.close()

        # Strict unambiguous rule: ambiguous remains unset
        assert rec_id_val is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_authoritative_backfill_failed_verification_log():
    """Verify that audit logs with failure result codes (e.g. NAME_MISMATCH) do not backfill record_id."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        rec_id = str(uuid.uuid4())
        req_id = "failed_req_456"

        cur.execute("INSERT INTO aadhaar_records (record_id, aadhaar_hash, masked_aadhaar, full_name) VALUES (?, 'h3', 'XXXX 3', 'Sunita Devi');", (rec_id,))

        cur.execute("""
            INSERT INTO aadhaar_audit_logs (request_id, record_id, masked_aadhaar, supplied_name, name_matched, aadhaar_matched, record_status, result_code, requester_role, originating_service)
            VALUES (?, ?, 'XXXX 3', 'Sunita Devi', 0, 1, 'ACTIVE', 'NAME_MISMATCH', 'WORKER', 'Service');
        """, (req_id, rec_id))

        cur.execute("INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role) VALUES ('uid_fail', 'Sunita Devi', 'sunita@test.com', '123', 'pw', 'WORKER');")
        u_id = cur.lastrowid

        cur.execute("INSERT INTO worker_profiles (user_id, full_name, is_aadhaar_verified, aadhaar_request_id) VALUES (?, 'Sunita Devi', 0, ?);", (u_id, req_id))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        rec_id_val = cur.fetchone()[0]
        conn.close()

        assert rec_id_val is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_authoritative_backfill_dangling_audit_record():
    """Verify that an audit log referencing a nonexistent record_id is not bound."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        ghost_rec_id = str(uuid.uuid4())
        req_id = "ghost_req_789"

        # Note: ghost_rec_id is NOT in aadhaar_records

        cur.execute("""
            INSERT INTO aadhaar_audit_logs (request_id, record_id, masked_aadhaar, supplied_name, name_matched, aadhaar_matched, record_status, result_code, requester_role, originating_service)
            VALUES (?, ?, 'XXXX 7', 'Ghost Record', 1, 1, 'ACTIVE', 'SUCCESS', 'WORKER', 'Service');
        """, (req_id, ghost_rec_id))

        cur.execute("INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role) VALUES ('uid_ghost', 'Ghost Worker', 'ghost@test.com', '123', 'pw', 'WORKER');")
        u_id = cur.lastrowid

        cur.execute("INSERT INTO worker_profiles (user_id, full_name, is_aadhaar_verified, aadhaar_request_id) VALUES (?, 'Ghost Worker', 1, ?);", (u_id, req_id))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        rec_id_val = cur.fetchone()[0]
        conn.close()

        assert rec_id_val is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_strict_no_fuzzy_matching():
    """Verify that demographic matching alone (name, state, masked Aadhaar) NEVER binds aadhaar_record_id."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        rec_id = str(uuid.uuid4())
        # Seed citizen in aadhaar_records
        cur.execute("""
            INSERT INTO aadhaar_records (record_id, aadhaar_hash, masked_aadhaar, full_name, dob, gender, origin_state, status, is_active)
            VALUES (?, 'hash_fuzzy', 'XXXX XXXX 4821', 'Mohammed Uzair', '1995-04-12', 'Male', 'Karnataka', 'ACTIVE', 1);
        """, (rec_id,))

        # Seed worker profile with identical demographics but NO aadhaar_request_id
        cur.execute("INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role) VALUES ('uid_fuzzy', 'Mohammed Uzair', 'uzair@test.com', '123', 'pw', 'WORKER');")
        u_id = cur.lastrowid

        cur.execute("""
            INSERT INTO worker_profiles (user_id, full_name, dob, gender, origin_state, masked_aadhaar, aadhaar_request_id, is_aadhaar_verified)
            VALUES (?, 'Mohammed Uzair', '1995-04-12', 'Male', 'Karnataka', 'XXXX XXXX 4821', NULL, 0);
        """, (u_id,))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        rec_id_val = cur.fetchone()[0]
        conn.close()

        # Strict prohibition: must remain NULL, no fuzzy guessing!
        assert rec_id_val is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_sanitize_dangling_linked_profile():
    """Verify that profiles with dangling aadhaar_record_id pointing to nonexistent records are sanitized to NULL."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Add column manually to simulate pre-existing dangling pointer
        cur.execute("ALTER TABLE worker_profiles ADD COLUMN aadhaar_record_id VARCHAR(36);")

        cur.execute("INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role) VALUES ('uid_dang', 'Dang Worker', 'dang@test.com', '123', 'pw', 'WORKER');")
        u_id = cur.lastrowid

        cur.execute("""
            INSERT INTO worker_profiles (user_id, full_name, aadhaar_record_id, aadhaar_request_id, is_aadhaar_verified)
            VALUES (?, 'Dang Worker', 'nonexistent_dangling_uuid_999', NULL, 1);
        """, (u_id,))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        rec_id_val = cur.fetchone()[0]
        conn.close()

        # Dangling pointer must be sanitized to NULL
        assert rec_id_val is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_sanitize_dangling_reconciles_via_valid_audit_log():
    """Verify that a dangling reference is corrected if a valid request_id points to an authoritative record."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        create_pre_v05_database(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        real_rec_id = str(uuid.uuid4())
        req_id = "recon_req_111"

        cur.execute("ALTER TABLE worker_profiles ADD COLUMN aadhaar_record_id VARCHAR(36);")

        cur.execute("INSERT INTO aadhaar_records (record_id, aadhaar_hash, masked_aadhaar, full_name) VALUES (?, 'h_real', 'XXXX 1111', 'Real Worker');", (real_rec_id,))

        cur.execute("""
            INSERT INTO aadhaar_audit_logs (request_id, record_id, masked_aadhaar, supplied_name, name_matched, aadhaar_matched, record_status, result_code, requester_role, originating_service)
            VALUES (?, ?, 'XXXX 1111', 'Real Worker', 1, 1, 'ACTIVE', 'SUCCESS', 'WORKER', 'Service');
        """, (req_id, real_rec_id))

        cur.execute("INSERT INTO users (firebase_uid, full_name, email, phone, password_hash, role) VALUES ('uid_recon', 'Real Worker', 'real@test.com', '123', 'pw', 'WORKER');")
        u_id = cur.lastrowid

        cur.execute("""
            INSERT INTO worker_profiles (user_id, full_name, aadhaar_record_id, aadhaar_request_id, is_aadhaar_verified)
            VALUES (?, 'Real Worker', 'bad_old_dangling_id', ?, 1);
        """, (u_id, req_id))
        wp_id = cur.lastrowid
        conn.commit()
        conn.close()

        migrate_database(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT aadhaar_record_id FROM worker_profiles WHERE id = ?;", (wp_id,))
        corrected_rec_id = cur.fetchone()[0]
        conn.close()

        assert corrected_rec_id == real_rec_id
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
