"""
PassKhadam v0.4 — Milestone 1 Adversarial Challenge & Stress Test Suite
=======================================================================
Empirical challenger test harness stress-testing:
1. Partial unique index `uq_active_category_scope`
2. Composite replay constraint `uq_presentation_verifier_context`
3. Immutability of `DBGovernanceAuditLog` and `DBAadhaarAuditLog`
4. Migration idempotency across 5 consecutive runs
"""

import os
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
import pytest
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.models.db import (
    Base,
    DBUser,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBGovernmentOfficer,
    DBActivationEmail,
    DBGovernanceAuditLog,
    DBAadhaarRecord,
    DBAadhaarAuditLog,
    DBConsumedPresentationNonce,
)
from app.db.migrate import migrate_database, CANONICAL_DEMO_ACCOUNTS, BASELINE_AADHAAR_RECORDS


@pytest.fixture
def stress_db(tmp_path):
    """
    Creates an isolated SQLite test database with full schema,
    partial unique index, and foreign keys enabled.
    """
    db_file = str(tmp_path / "stress_challenge.db")
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create tables via metadata
    Base.metadata.create_all(bind=engine)

    # Ensure partial unique index exists explicitly
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_category_scope "
            "ON category_authorization_requests (organization_id, category, skill_level, nature_of_employment) "
            "WHERE is_active_scope = 1;"
        ))
        conn.commit()

    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    yield {
        "engine": engine,
        "session": session,
        "db_file": db_file,
        "Session": Session,
    }

    session.close()
    engine.dispose()


# ============================================================================
# 1. STRESS TEST: PARTIAL UNIQUE INDEX uq_active_category_scope
# ============================================================================

def test_stress_concurrent_active_scopes_fail_integrity(stress_db):
    """
    Stress test 1a: Attempt concurrent active scopes for same
    (organization_id, category, skill_level, nature_of_employment).
    Must fail with IntegrityError.
    """
    session = stress_db["session"]
    Session = stress_db["Session"]

    # Create test employer org
    org = DBEmployerOrganization(
        name="Apex Construction Corp",
        registration_ref_number="CIN-STRESS-001",
        status="APPROVED"
    )
    session.add(org)
    session.commit()
    org_id = org.id

    # 1. Insert first active scope -> must succeed
    scope1 = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Mason",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        request_version=1
    )
    session.add(scope1)
    session.commit()

    # 2. Attempt second active scope for identical tuple via ORM -> must fail
    scope2 = DBCategoryAuthorizationRequest(
        organization_id=org_id,
        category="Mason",
        skill_level="Skilled",
        nature_of_employment="Contract",
        status="APPROVED",
        is_active_scope=True,
        request_version=2
    )
    session.add(scope2)
    with pytest.raises(IntegrityError) as exc_info:
        session.commit()
    session.rollback()

    assert "UNIQUE constraint failed" in str(exc_info.value) or "uq_active_category_scope" in str(exc_info.value)

    # 3. Concurrent multi-threaded assault: 10 threads attempt to insert active scopes
    errors = []
    successes = []

    def insert_active_worker(thread_idx):
        t_session = Session()
        try:
            scope = DBCategoryAuthorizationRequest(
                organization_id=org_id,
                category="Mason",
                skill_level="Skilled",
                nature_of_employment="Contract",
                status="APPROVED",
                is_active_scope=True,
                request_version=100 + thread_idx
            )
            t_session.add(scope)
            t_session.commit()
            successes.append(thread_idx)
        except IntegrityError as e:
            t_session.rollback()
            errors.append(str(e))
        except Exception as e:
            t_session.rollback()
            errors.append(f"Unexpected: {str(e)}")
        finally:
            t_session.close()

    threads = [threading.Thread(target=insert_active_worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Because an active scope already existed, ALL 10 concurrent inserts must fail with IntegrityError
    assert len(successes) == 0, f"Expected 0 successful concurrent active inserts, but {len(successes)} succeeded!"
    assert len(errors) == 10, f"Expected 10 IntegrityErrors, got {len(errors)}"
    for err in errors:
        assert "UNIQUE constraint failed" in err or "uq_active_category_scope" in err


def test_stress_deactivate_active_scope_allows_new_active_scope(stress_db):
    """
    Stress test 1b: Deactivate active scope -> insert new active scope.
    Must succeed cleanly. Verifies 5 successive version transitions.
    """
    session = stress_db["session"]

    org = DBEmployerOrganization(
        name="BuildTech Infrastructure",
        registration_ref_number="CIN-STRESS-002",
        status="APPROVED"
    )
    session.add(org)
    session.commit()
    org_id = org.id

    # Simulate 5 sequential lifecycle upgrades (v1 to v5)
    for version in range(1, 6):
        # Insert active scope for this version
        scope = DBCategoryAuthorizationRequest(
            organization_id=org_id,
            category="Plumber",
            skill_level="Semi-Skilled",
            nature_of_employment="Contract",
            status="APPROVED",
            is_active_scope=True,
            request_version=version
        )
        session.add(scope)
        session.commit()

        # Verify exactly 1 active scope exists
        active_count = session.query(DBCategoryAuthorizationRequest).filter_by(
            organization_id=org_id,
            category="Plumber",
            is_active_scope=True
        ).count()
        assert active_count == 1, f"Expected 1 active scope at version {version}, found {active_count}"

        # If not the final version, deactivate this scope
        if version < 5:
            scope.is_active_scope = False
            scope.status = "SUPERSEDED"
            session.commit()

    # After 5 cycles: exactly 1 active scope (v5) and 4 inactive scopes (v1-v4)
    all_scopes = session.query(DBCategoryAuthorizationRequest).filter_by(
        organization_id=org_id,
        category="Plumber"
    ).order_by(DBCategoryAuthorizationRequest.request_version.asc()).all()

    assert len(all_scopes) == 5
    for s in all_scopes[:-1]:
        assert s.is_active_scope is False
        assert s.status == "SUPERSEDED"
    assert all_scopes[-1].is_active_scope is True
    assert all_scopes[-1].status == "APPROVED"
    assert all_scopes[-1].request_version == 5


def test_stress_multiple_inactive_scopes_coexist(stress_db):
    """
    Stress test 1c: Insert multiple inactive scopes (e.g. 20 PENDING, REJECTED, DISCONTINUED).
    Must succeed with zero IntegrityErrors.
    """
    session = stress_db["session"]

    org = DBEmployerOrganization(
        name="Global Steel Works",
        registration_ref_number="CIN-STRESS-003",
        status="APPROVED"
    )
    session.add(org)
    session.commit()
    org_id = org.id

    statuses = ["PENDING", "REJECTED", "MORE_INFO_REQUIRED", "DISCONTINUED"]
    total_inactive = 20

    for i in range(total_inactive):
        status_val = statuses[i % len(statuses)]
        inactive_scope = DBCategoryAuthorizationRequest(
            organization_id=org_id,
            category="Electrician",
            skill_level="Skilled",
            nature_of_employment="Permanent",
            status=status_val,
            is_active_scope=False,
            request_version=i + 1,
            reason=f"Batch test inactive request #{i+1}"
        )
        session.add(inactive_scope)

    # Commit all 20 inactive requests at once
    session.commit()

    count = session.query(DBCategoryAuthorizationRequest).filter_by(
        organization_id=org_id,
        category="Electrician",
        is_active_scope=False
    ).count()

    assert count == total_inactive, f"Expected {total_inactive} inactive scopes, got {count}"


def test_stress_partial_index_parameter_orthogonality(stress_db):
    """
    Stress test 1d: Active scopes with different organization, skill level,
    or nature of employment must not collide.
    """
    session = stress_db["session"]

    org1 = DBEmployerOrganization(name="Org 1", registration_ref_number="REF-O1")
    org2 = DBEmployerOrganization(name="Org 2", registration_ref_number="REF-O2")
    session.add_all([org1, org2])
    session.commit()

    # 1. Org 1: Mason / Skilled / Contract (Active)
    s1 = DBCategoryAuthorizationRequest(
        organization_id=org1.id, category="Mason", skill_level="Skilled",
        nature_of_employment="Contract", is_active_scope=True, status="APPROVED"
    )
    # 2. Org 2: Mason / Skilled / Contract (Active) -> different org, must succeed
    s2 = DBCategoryAuthorizationRequest(
        organization_id=org2.id, category="Mason", skill_level="Skilled",
        nature_of_employment="Contract", is_active_scope=True, status="APPROVED"
    )
    # 3. Org 1: Mason / Semi-Skilled / Contract (Active) -> different skill_level, must succeed
    s3 = DBCategoryAuthorizationRequest(
        organization_id=org1.id, category="Mason", skill_level="Semi-Skilled",
        nature_of_employment="Contract", is_active_scope=True, status="APPROVED"
    )
    # 4. Org 1: Mason / Skilled / Permanent (Active) -> different nature_of_employment, must succeed
    s4 = DBCategoryAuthorizationRequest(
        organization_id=org1.id, category="Mason", skill_level="Skilled",
        nature_of_employment="Permanent", is_active_scope=True, status="APPROVED"
    )

    session.add_all([s1, s2, s3, s4])
    session.commit()

    active_total = session.query(DBCategoryAuthorizationRequest).filter_by(is_active_scope=True).count()
    assert active_total == 4


# ============================================================================
# 2. STRESS TEST: COMPOSITE REPLAY CONSTRAINT uq_presentation_verifier_context
# ============================================================================

def test_stress_presentation_replay_same_context_fails(stress_db):
    """
    Stress test 2a: Replay same presentation to same verifier role and ID.
    Must fail with IntegrityError across single and concurrent attempts.
    """
    session = stress_db["session"]
    Session = stress_db["Session"]

    presentation_id = "pres_stress_attack_001"
    role = "EMPLOYER"
    verifier_id = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"

    # Initial valid consumption
    nonce1 = DBConsumedPresentationNonce(
        presentation_id=presentation_id,
        verifier_role=role,
        verifier_id=verifier_id,
        worker_did="did:passkhadam:worker:001"
    )
    session.add(nonce1)
    session.commit()

    # Replay attempt 1: Sequential duplicate -> must raise IntegrityError
    nonce_replay = DBConsumedPresentationNonce(
        presentation_id=presentation_id,
        verifier_role=role,
        verifier_id=verifier_id,
        worker_did="did:passkhadam:worker:001"
    )
    session.add(nonce_replay)
    with pytest.raises(IntegrityError) as exc_info:
        session.commit()
    session.rollback()

    assert "UNIQUE constraint failed" in str(exc_info.value) or "uq_presentation_verifier_context" in str(exc_info.value)

    # Replay attempt 2: 10 concurrent replay threads
    replay_errors = []
    replay_success = []

    def replay_worker(idx):
        t_session = Session()
        try:
            n = DBConsumedPresentationNonce(
                presentation_id=presentation_id,
                verifier_role=role,
                verifier_id=verifier_id,
                worker_did=f"did:passkhadam:worker:replay_{idx}"
            )
            t_session.add(n)
            t_session.commit()
            replay_success.append(idx)
        except IntegrityError:
            t_session.rollback()
            replay_errors.append(idx)
        finally:
            t_session.close()

    threads = [threading.Thread(target=replay_worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(replay_success) == 0, f"Replay attack breached constraint! {len(replay_success)} succeeded"
    assert len(replay_errors) == 10


def test_stress_presentation_cross_role_and_verifier_succeeds(stress_db):
    """
    Stress test 2b: Present same presentation to different verifier role or ID.
    Must succeed cleanly.
    """
    session = stress_db["session"]
    pres_id = "pres_stress_cross_context_002"

    contexts = [
        ("EMPLOYER", "org_employer_alpha"),
        ("EMPLOYER", "org_employer_beta"),
        ("GOVERNMENT", "gov_officer_mumbai"),
        ("GOVERNMENT", "gov_officer_pune"),
        ("ADMIN", "admin_compliance_audit"),
    ]

    for role, v_id in contexts:
        nonce = DBConsumedPresentationNonce(
            presentation_id=pres_id,
            verifier_role=role,
            verifier_id=v_id,
            worker_did="did:passkhadam:worker:002"
        )
        session.add(nonce)

    session.commit()

    count = session.query(DBConsumedPresentationNonce).filter_by(presentation_id=pres_id).count()
    assert count == len(contexts), f"Expected {len(contexts)} cross-context nonces, found {count}"


# ============================================================================
# 3. STRESS TEST: IMMUTABILITY OF AUDIT LOGS
# ============================================================================

def test_stress_governance_audit_log_immutability(stress_db):
    """
    Stress test 3a: Attempt UPDATE and DELETE operations on DBGovernanceAuditLog.
    Must raise RuntimeError via event listeners.
    """
    session = stress_db["session"]

    # 1. Insert audit log entry
    audit_log = DBGovernanceAuditLog(
        actor_firebase_uid="ZOGbgd8LfYPgu7VhcUESBEIzZp03",
        actor_user_id=1,
        actor_role="ADMIN",
        action="DECIDE_ORGANIZATION",
        target_type="EMPLOYER_ORGANIZATION",
        target_id="101",
        previous_state="PENDING_REVIEW",
        new_state="APPROVED",
        reason="Verified business registration CIN",
        request_id="req_gov_audit_stress_001"
    )
    session.add(audit_log)
    session.commit()
    log_id = audit_log.id

    # 2. Stress test UPDATE: Attempt to modify fields -> MUST RAISE RuntimeError
    audit_log.action = "TAMPERED_ACTION"
    audit_log.new_state = "REJECTED"
    with pytest.raises(RuntimeError) as exc_update:
        session.commit()
    session.rollback()

    assert "DBGovernanceAuditLog is immutable; update operations are strictly prohibited." in str(exc_update.value)

    # Verify data in DB was not altered
    fresh_entry = session.query(DBGovernanceAuditLog).filter_by(id=log_id).first()
    assert fresh_entry.action == "DECIDE_ORGANIZATION"
    assert fresh_entry.new_state == "APPROVED"

    # 3. Stress test DELETE: Attempt to delete record -> MUST RAISE RuntimeError
    with pytest.raises(RuntimeError) as exc_delete:
        session.delete(fresh_entry)
        session.commit()
    session.rollback()

    assert "DBGovernanceAuditLog is immutable; delete operations are strictly prohibited." in str(exc_delete.value)

def test_stress_partial_index_update_from_inactive_to_active_fails(stress_db):
    """
    Stress test 1e: Attempting to UPDATE an inactive scope to active scope
    when an active scope already exists must fail with IntegrityError.
    """
    session = stress_db["session"]

    org = DBEmployerOrganization(
        name="Update Stress Corp",
        registration_ref_number="CIN-STRESS-UPDATE",
        status="APPROVED"
    )
    session.add(org)
    session.commit()

    # Active scope
    s1 = DBCategoryAuthorizationRequest(
        organization_id=org.id, category="Welder", skill_level="Skilled",
        nature_of_employment="Contract", is_active_scope=True, status="APPROVED", request_version=1
    )
    # Inactive scope
    s2 = DBCategoryAuthorizationRequest(
        organization_id=org.id, category="Welder", skill_level="Skilled",
        nature_of_employment="Contract", is_active_scope=False, status="PENDING", request_version=2
    )
    session.add_all([s1, s2])
    session.commit()

    # Attempt to update s2 to is_active_scope = True without deactivating s1
    s2.is_active_scope = True
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_stress_presentation_replay_via_update_fails(stress_db):
    """
    Stress test 2c: Attempting to update an existing nonce's verifier context
    to collide with another nonce must fail with IntegrityError.
    """
    session = stress_db["session"]

    n1 = DBConsumedPresentationNonce(
        presentation_id="pres_upd_001",
        verifier_role="EMPLOYER",
        verifier_id="org_1"
    )
    n2 = DBConsumedPresentationNonce(
        presentation_id="pres_upd_001",
        verifier_role="EMPLOYER",
        verifier_id="org_2"
    )
    session.add_all([n1, n2])
    session.commit()

    # Attempt to change n2's verifier_id to collide with n1
    n2.verifier_id = "org_1"
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_adversarial_investigation_query_bulk_audit_log_operations(stress_db):
    """
    Adversarial Investigation: Test whether SQLAlchemy mapper events
    intercept Query.update() and Query.delete().
    In standard SQLAlchemy, Query.update/delete execute DML directly
    unless event listeners hook into Query or Session events.
    """
    session = stress_db["session"]
    engine = stress_db["engine"]

    audit_log = DBGovernanceAuditLog(
        actor_firebase_uid="ZOGbgd8LfYPgu7VhcUESBEIzZp03",
        actor_user_id=1,
        actor_role="ADMIN",
        action="ORIGINAL_ACTION",
        target_type="EMPLOYER_ORGANIZATION",
        target_id="999",
        reason="Initial test",
        request_id="req_adv_query_001"
    )
    session.add(audit_log)
    session.commit()
    log_id = audit_log.id

    # Test Query.update() behavior:
    # Does Query.update() trigger mapper before_update event?
    query_update_raised = False
    try:
        session.query(DBGovernanceAuditLog).filter_by(id=log_id).update({"action": "BULK_MUTATED"})
        session.commit()
    except RuntimeError:
        query_update_raised = True
        session.rollback()
    except Exception:
        session.rollback()

    # Record whether ORM mapper event protects Query.update
    # (Document this as a caveat / security finding if it bypasses mapper events)
    print(f"\n[Adversarial Probe] Query.update() raised RuntimeError: {query_update_raised}")


def test_stress_aadhaar_audit_log_immutability(stress_db):
    """
    Stress test 3b: Attempt UPDATE and DELETE operations on DBAadhaarAuditLog.
    Must raise RuntimeError via event listeners.

    """
    session = stress_db["session"]

    # 1. Insert Aadhaar audit log entry
    aadhaar_log = DBAadhaarAuditLog(
        request_id="aadhaar_stress_req_999",
        record_id=str(uuid.uuid4()),
        masked_aadhaar="XXXX XXXX 4821",
        supplied_name="Mohammed Uzair",
        name_matched=True,
        aadhaar_matched=True,
        record_status="ACTIVE",
        result_code="VERIFIED_SUCCESS",
        response_time_ms=52.4,
        requester_role="WORKER",
        originating_service="PassKhadam-Backend"
    )
    session.add(aadhaar_log)
    session.commit()
    log_id = aadhaar_log.id

    # 2. Stress test UPDATE: Attempt to alter result_code / name_matched -> MUST RAISE RuntimeError
    aadhaar_log.result_code = "FAILED_TAMPERED"
    aadhaar_log.name_matched = False
    with pytest.raises(RuntimeError) as exc_update:
        session.commit()
    session.rollback()

    assert "DBAadhaarAuditLog is immutable; update operations are strictly prohibited." in str(exc_update.value)

    # Verify record remains untampered
    fresh_entry = session.query(DBAadhaarAuditLog).filter_by(id=log_id).first()
    assert fresh_entry.result_code == "VERIFIED_SUCCESS"
    assert fresh_entry.name_matched is True

    # 3. Stress test DELETE: Attempt to purge audit trail -> MUST RAISE RuntimeError
    with pytest.raises(RuntimeError) as exc_delete:
        session.delete(fresh_entry)
        session.commit()
    session.rollback()

    assert "DBAadhaarAuditLog is immutable; delete operations are strictly prohibited." in str(exc_delete.value)

    # Verify record still persists
    persisted = session.query(DBAadhaarAuditLog).filter_by(id=log_id).first()
    assert persisted is not None
    assert persisted.id == log_id


# ============================================================================
# 4. STRESS TEST: MIGRATION IDEMPOTENCY ACROSS 5 CONSECUTIVE RUNS
# ============================================================================

def test_stress_migration_idempotency_5_consecutive_runs(tmp_path):
    """
    Stress test 4: Run migrate_database() 5 times consecutively on a fresh DB.
    Assert 0 errors and 0 duplicates across all 5 runs.
    """
    db_file = str(tmp_path / "migration_5_runs_stress.db")

    # Run 1 through 5
    for run_idx in range(1, 6):
        success = migrate_database(db_path=db_file)
        assert success is True, f"Run {run_idx} failed!"

    # Connect and assert zero duplicates
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 1. Exactly 5 canonical demo users
    cursor.execute("SELECT email, firebase_uid, role FROM users;")
    all_users = cursor.fetchall()
    assert len(all_users) == 5, f"Expected exactly 5 demo accounts, found {len(all_users)}"

    # Check each demo account
    emails = {u[0].lower() for u in all_users}
    for acc in CANONICAL_DEMO_ACCOUNTS:
        assert acc["email"].lower() in emails, f"Demo account {acc['email']} missing"

    # 2. Exactly 1 employer organization for Apex
    cursor.execute("SELECT COUNT(*) FROM employer_organizations;")
    emp_count = cursor.fetchone()[0]
    assert emp_count == 1, f"Expected 1 employer org, found {emp_count}"

    # 3. Exactly 3 pre-approved category authorizations for Apex
    cursor.execute("SELECT COUNT(*) FROM category_authorization_requests WHERE is_active_scope = 1;")
    active_cats = cursor.fetchone()[0]
    assert active_cats == 3, f"Expected 3 active categories, found {active_cats}"

    # 4. Exactly 1 government officer
    cursor.execute("SELECT COUNT(*) FROM government_officers;")
    gov_count = cursor.fetchone()[0]
    assert gov_count == 1, f"Expected 1 government officer, found {gov_count}"

    # 5. Exactly 5 baseline Aadhaar records
    cursor.execute("SELECT COUNT(*) FROM aadhaar_records;")
    aadhaar_count = cursor.fetchone()[0]
    assert aadhaar_count == 5, f"Expected 5 baseline Aadhaar records, found {aadhaar_count}"

    # 6. Check partial index and composite constraint
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='uq_active_category_scope';")
    assert cursor.fetchone() is not None, "Partial unique index uq_active_category_scope missing"

    conn.close()


def test_stress_migration_idempotency_on_production_db_copy(tmp_path):
    """
    Stress test 4b: Copy live database (passkhadam.db) to temporary file,
    run migrate_database() 5 times consecutively, and assert zero row drift.
    """
    live_db_path = os.path.join(
        os.path.dirname(__file__), "..", "app", "storage", "passkhadam.db"
    )
    if not os.path.exists(live_db_path):
        pytest.skip(f"Live database not found at {live_db_path}")

    test_copy_path = str(tmp_path / "live_copy_5_runs.db")
    shutil.copyfile(live_db_path, test_copy_path)

    # Apply initial migration to bring database into fully migrated baseline state
    migrate_database(db_path=test_copy_path)

    # Capture baseline table row counts after migration is applied
    conn = sqlite3.connect(test_copy_path)
    cursor = conn.cursor()

    tables = [
        "users",
        "worker_profiles",
        "employer_organizations",
        "category_authorization_requests",
        "government_officers",
        "aadhaar_records",
    ]

    baseline_counts = {}
    for tbl in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
        baseline_counts[tbl] = cursor.fetchone()[0]
    conn.close()

    # Execute 5 consecutive migrations on the migrated database to assert strict idempotency
    for run_num in range(1, 6):
        res = migrate_database(db_path=test_copy_path)
        assert res is True, f"Migration run #{run_num} on live copy returned False"

        # Check row counts after each run
        conn = sqlite3.connect(test_copy_path)
        cursor = conn.cursor()
        current_counts = {}
        for tbl in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
            current_counts[tbl] = cursor.fetchone()[0]
        conn.close()

        for tbl in tables:
            assert current_counts[tbl] == baseline_counts[tbl], (
                f"Table {tbl} row count drifted on migration run #{run_num}! "
                f"Baseline: {baseline_counts[tbl]}, Run {run_num}: {current_counts[tbl]}"
            )

