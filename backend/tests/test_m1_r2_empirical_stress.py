"""
Milestone 1 Round 2 — Empirical Challenger Stress Test Suite
=============================================================
Adversarial stress testing of:
1. DBAadhaarAuditLog with synonym("supplied_name")
2. Partial unique index uq_active_category_scope
3. Replay nonce constraint uq_presentation_verifier_context
4. Immutability listeners on DBGovernanceAuditLog and DBAadhaarAuditLog
"""

import os
import uuid
import tempfile
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models.db import (
    Base,
    SessionLocal,
    DBUser,
    DBEmployerOrganization,
    DBCategoryAuthorizationRequest,
    DBGovernanceAuditLog,
    DBAadhaarRecord,
    DBAadhaarAuditLog,
    DBConsumedPresentationNonce,
)
from app.db.migrate import migrate_database


@pytest.fixture
def test_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Apply full v0.4 migration
    migrate_database(db_path)
    
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    # Ensure foreign keys are enabled in SQLite
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))
    
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSession()
    
    yield {"session": session, "engine": engine, "path": db_path}
    
    session.close()
    engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)


# ============================================================================
# 1. CHALLENGE 1: DBAadhaarAuditLog synonym("supplied_name")
# ============================================================================

def test_aadhaar_audit_log_synonym_full_lifecycle(test_db):
    """
    Empirical challenge:
    - Query via .supplied_name and .submitted_name.
    - Filter queries by .submitted_name == '...' and .supplied_name == '...'.
    - Insert record specifying submitted_name, verify it writes cleanly to supplied_name.
    - Assert 0 SQLite OperationalError exceptions.
    - Check underlying SQLite table schema has NO submitted_name column.
    """
    session = test_db["session"]
    engine = test_db["engine"]

    # 1. Inspect table columns via PRAGMA table_info to verify physical schema
    with engine.connect() as conn:
        columns = [row[1] for row in conn.execute(text("PRAGMA table_info(aadhaar_audit_logs);")).fetchall()]
        assert "supplied_name" in columns, "Physical column supplied_name must exist in SQLite"
        assert "submitted_name" not in columns, "Physical column submitted_name must NOT exist in SQLite table"

    # 2. Insert record specifying submitted_name (synonym) in constructor
    req_id_1 = f"req_{uuid.uuid4()}"
    log_1 = DBAadhaarAuditLog(
        request_id=req_id_1,
        masked_aadhaar="XXXX XXXX 1122",
        submitted_name="Aarav Sharma",  # specifying submitted_name
        name_matched=True,
        aadhaar_matched=True,
        record_status="ACTIVE",
        result_code="VERIFIED_SUCCESS",
        response_time_ms=35.5,
        requester_role="WORKER",
        originating_service="PassKhadam-Backend",
    )
    session.add(log_1)
    session.commit()

    # Verify attributes on persisted instance
    assert log_1.supplied_name == "Aarav Sharma"
    assert log_1.submitted_name == "Aarav Sharma"

    # 3. Query via SessionLocal and filter by .submitted_name == '...'
    query_submitted = session.query(DBAadhaarAuditLog).filter(
        DBAadhaarAuditLog.submitted_name == "Aarav Sharma"
    ).all()
    assert len(query_submitted) == 1
    assert query_submitted[0].request_id == req_id_1
    assert query_submitted[0].supplied_name == "Aarav Sharma"
    assert query_submitted[0].submitted_name == "Aarav Sharma"

    # 4. Query via SessionLocal and filter by .supplied_name == '...'
    query_supplied = session.query(DBAadhaarAuditLog).filter(
        DBAadhaarAuditLog.supplied_name == "Aarav Sharma"
    ).all()
    assert len(query_supplied) == 1
    assert query_supplied[0].request_id == req_id_1

    # 5. Insert record specifying supplied_name in constructor
    req_id_2 = f"req_{uuid.uuid4()}"
    log_2 = DBAadhaarAuditLog(
        request_id=req_id_2,
        masked_aadhaar="XXXX XXXX 3344",
        supplied_name="Sunita Patel",  # specifying supplied_name
        name_matched=True,
        aadhaar_matched=True,
        record_status="ACTIVE",
        result_code="VERIFIED_SUCCESS",
        response_time_ms=42.1,
        requester_role="WORKER",
        originating_service="PassKhadam-Backend",
    )
    session.add(log_2)
    session.commit()

    assert log_2.supplied_name == "Sunita Patel"
    assert log_2.submitted_name == "Sunita Patel"

    # Filter with submitted_name on second record
    res2 = session.query(DBAadhaarAuditLog).filter(
        DBAadhaarAuditLog.submitted_name == "Sunita Patel"
    ).one()
    assert res2.request_id == req_id_2

    # 6. Test expression operators on synonym (.like, !=, .in_)
    like_res = session.query(DBAadhaarAuditLog).filter(
        DBAadhaarAuditLog.submitted_name.like("%Patel%")
    ).all()
    assert len(like_res) == 1
    assert like_res[0].supplied_name == "Sunita Patel"

    in_res = session.query(DBAadhaarAuditLog).filter(
        DBAadhaarAuditLog.submitted_name.in_(["Aarav Sharma", "Sunita Patel"])
    ).all()
    assert len(in_res) == 2

    # 7. Direct raw SQL execution to verify physical storage
    with engine.connect() as conn:
        raw_row = conn.execute(
            text("SELECT supplied_name FROM aadhaar_audit_logs WHERE request_id = :rid"),
            {"rid": req_id_1}
        ).fetchone()
        assert raw_row[0] == "Aarav Sharma"

    # 8. Adversarial edge cases: Unicode, SQL special chars, and bidirectional mutation in memory
    unicode_name = "मोहम्मद उज़ैर / O'Connor & Sons <Test>"
    log_unicode = DBAadhaarAuditLog(
        request_id=f"req_{uuid.uuid4()}",
        masked_aadhaar="XXXX XXXX 5566",
        submitted_name=unicode_name,
        name_matched=True,
        aadhaar_matched=True,
        result_code="VERIFIED_SUCCESS",
    )
    assert log_unicode.supplied_name == unicode_name
    assert log_unicode.submitted_name == unicode_name
    session.add(log_unicode)
    session.commit()

    reloaded_unicode = session.query(DBAadhaarAuditLog).filter(
        DBAadhaarAuditLog.submitted_name == unicode_name
    ).one()
    assert reloaded_unicode.supplied_name == unicode_name


# ============================================================================
# 2. CHALLENGE 2: Partial Unique Index uq_active_category_scope
# ============================================================================

def test_partial_unique_index_active_category_scope(test_db):
    """
    Empirical challenge:
    - Insert concurrent active scopes for same org + category + skill + nature -> must fail with IntegrityError.
    - Multiple inactive scopes for same org + category + skill + nature -> must succeed.
    - Deactivate active scope -> insert new active scope -> must succeed.
    - Reactivate old scope while another is active -> must fail with IntegrityError.
    """
    session = test_db["session"]

    # Setup base user and organization
    user = DBUser(
        firebase_uid="uid_org_owner_challenge",
        full_name="Challenge Employer",
        email="challenge_emp@apexinfra.com",
        phone="+91 9876500001",
        password_hash="pwdhash123",
        role="EMPLOYER",
        status="ACTIVE",
    )
    session.add(user)
    session.commit()

    org = DBEmployerOrganization(
        user_id=user.id,
        name="Challenger Infra Ltd",
        registration_ref_number="CIN-CHALLENGE-001",
        status="APPROVED",
    )
    session.add(org)
    session.commit()

    # 1. Insert first active scope
    scope_active_1 = DBCategoryAuthorizationRequest(
        organization_id=org.id,
        category="Masonry",
        skill_level="Skilled",
        nature_of_employment="Permanent",
        status="APPROVED",
        is_active_scope=True,
        request_version=1,
    )
    session.add(scope_active_1)
    session.commit()
    assert scope_active_1.id is not None

    # 2. Insert concurrent second active scope with identical tuple -> MUST FAIL
    scope_active_duplicate = DBCategoryAuthorizationRequest(
        organization_id=org.id,
        category="Masonry",
        skill_level="Skilled",
        nature_of_employment="Permanent",
        status="APPROVED",
        is_active_scope=True,
        request_version=2,
    )
    session.add(scope_active_duplicate)
    with pytest.raises(IntegrityError) as exc_info:
        session.commit()
    assert "UNIQUE constraint failed" in str(exc_info.value) or "uq_active_category_scope" in str(exc_info.value)
    session.rollback()

    # 3. Insert multiple INACTIVE scopes for the same tuple -> MUST SUCCEED
    scope_inactive_v2 = DBCategoryAuthorizationRequest(
        organization_id=org.id,
        category="Masonry",
        skill_level="Skilled",
        nature_of_employment="Permanent",
        status="PENDING",
        is_active_scope=False,
        request_version=2,
    )
    scope_inactive_v3 = DBCategoryAuthorizationRequest(
        organization_id=org.id,
        category="Masonry",
        skill_level="Skilled",
        nature_of_employment="Permanent",
        status="REJECTED",
        is_active_scope=False,
        request_version=3,
    )
    session.add_all([scope_inactive_v2, scope_inactive_v3])
    session.commit()
    assert scope_inactive_v2.id is not None
    assert scope_inactive_v3.id is not None

    # 4. Deactivate the active scope 1 -> insert new active scope -> MUST SUCCEED
    scope_active_1_reload = session.query(DBCategoryAuthorizationRequest).filter_by(id=scope_active_1.id).one()
    scope_active_1_reload.is_active_scope = False
    scope_active_1_reload.status = "SUPERSEDED"
    session.commit()

    scope_active_new = DBCategoryAuthorizationRequest(
        organization_id=org.id,
        category="Masonry",
        skill_level="Skilled",
        nature_of_employment="Permanent",
        status="APPROVED",
        is_active_scope=True,
        request_version=4,
    )
    session.add(scope_active_new)
    session.commit()
    assert scope_active_new.id is not None

    # 5. Try to reactivate scope 1 while scope 4 is active -> MUST FAIL
    scope_active_1_reload.is_active_scope = True
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 6. Verify DIFFERENT organization CAN have concurrent active scope for same (category, skill, nature)
    user2 = DBUser(
        firebase_uid="uid_org_owner_challenge_2",
        full_name="Second Employer",
        email="challenge_emp_2@company.com",
        phone="+91 9876500002",
        password_hash="pwdhash456",
        role="EMPLOYER",
        status="ACTIVE",
    )
    session.add(user2)
    session.commit()
    org2 = DBEmployerOrganization(
        user_id=user2.id,
        name="Second Builders Ltd",
        registration_ref_number="CIN-CHALLENGE-002",
        status="APPROVED",
    )
    session.add(org2)
    session.commit()

    scope_org2_active = DBCategoryAuthorizationRequest(
        organization_id=org2.id,
        category="Masonry",
        skill_level="Skilled",
        nature_of_employment="Permanent",
        status="APPROVED",
        is_active_scope=True,
        request_version=1,
    )
    session.add(scope_org2_active)
    session.commit()
    assert scope_org2_active.id is not None



# ============================================================================
# 3. CHALLENGE 3: Replay Nonce Constraint uq_presentation_verifier_context
# ============================================================================

def test_replay_nonce_constraint_verifier_context(test_db):
    """
    Empirical challenge:
    - Same presentation_id to same verifier_role and verifier_id -> must fail with IntegrityError.
    - Same presentation_id to DIFFERENT verifier_role or verifier_id -> must succeed (legitimate verification by multiple parties).
    """
    session = test_db["session"]

    pres_id = f"urn:uuid:{uuid.uuid4()}"

    # 1. Employer 1 verifies presentation
    nonce_emp1 = DBConsumedPresentationNonce(
        presentation_id=pres_id,
        verifier_role="EMPLOYER",
        verifier_id="ORG_ALPHA_001",
        worker_did="did:passkhadam:worker:123",
    )
    session.add(nonce_emp1)
    session.commit()

    # 2. Government Officer verifies the SAME presentation -> MUST SUCCEED
    nonce_gov = DBConsumedPresentationNonce(
        presentation_id=pres_id,
        verifier_role="GOVERNMENT",
        verifier_id="OFFICER_MH_042",
        worker_did="did:passkhadam:worker:123",
    )
    session.add(nonce_gov)
    session.commit()

    # 3. Employer 2 verifies the SAME presentation -> MUST SUCCEED
    nonce_emp2 = DBConsumedPresentationNonce(
        presentation_id=pres_id,
        verifier_role="EMPLOYER",
        verifier_id="ORG_BETA_002",
        worker_did="did:passkhadam:worker:123",
    )
    session.add(nonce_emp2)
    session.commit()

    # 4. Employer 1 attempts to replay the SAME presentation -> MUST FAIL WITH IntegrityError
    replay_emp1 = DBConsumedPresentationNonce(
        presentation_id=pres_id,
        verifier_role="EMPLOYER",
        verifier_id="ORG_ALPHA_001",
        worker_did="did:passkhadam:worker:123",
    )
    session.add(replay_emp1)
    with pytest.raises(IntegrityError) as exc_info:
        session.commit()
    assert "UNIQUE constraint failed" in str(exc_info.value) or "uq_presentation_verifier_context" in str(exc_info.value)
    session.rollback()

    # 5. Government Officer attempts to replay the SAME presentation -> MUST FAIL WITH IntegrityError
    replay_gov = DBConsumedPresentationNonce(
        presentation_id=pres_id,
        verifier_role="GOVERNMENT",
        verifier_id="OFFICER_MH_042",
        worker_did="did:passkhadam:worker:123",
    )
    session.add(replay_gov)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ============================================================================
# 4. CHALLENGE 4: Immutability Stress-Test on Audit Logs
# ============================================================================

def test_governance_audit_log_immutability(test_db):
    """
    Empirical challenge:
    - Attempt UPDATE operation on DBGovernanceAuditLog -> must raise RuntimeError.
    - Attempt DELETE operation on DBGovernanceAuditLog -> must raise RuntimeError.
    """
    session = test_db["session"]

    # Insert initial governance audit log
    gov_log = DBGovernanceAuditLog(
        actor_firebase_uid="uid_admin_immutability",
        actor_role="ADMIN",
        action="SUSPEND_OFFICER",
        target_type="GOVERNMENT_OFFICER",
        target_id="GOV-OFFICER-009",
        reason="Compliance review pending",
    )
    session.add(gov_log)
    session.commit()
    log_id = gov_log.id

    # 1. Attempt UPDATE
    gov_log.reason = "Tampered / Altered Reason"
    with pytest.raises(RuntimeError) as exc_info:
        session.commit()
    assert "DBGovernanceAuditLog is immutable; update operations are strictly prohibited" in str(exc_info.value)
    session.rollback()

    # Verify state was not modified
    reloaded = session.query(DBGovernanceAuditLog).filter_by(id=log_id).one()
    assert reloaded.reason == "Compliance review pending"

    # 2. Attempt DELETE
    session.delete(reloaded)
    with pytest.raises(RuntimeError) as exc_info:
        session.commit()
    assert "DBGovernanceAuditLog is immutable; delete operations are strictly prohibited" in str(exc_info.value)
    session.rollback()

    # Verify record still exists
    reloaded_after_del = session.query(DBGovernanceAuditLog).filter_by(id=log_id).one()
    assert reloaded_after_del is not None


def test_aadhaar_audit_log_immutability(test_db):
    """
    Empirical challenge:
    - Attempt UPDATE operation on DBAadhaarAuditLog -> must raise RuntimeError.
    - Attempt DELETE operation on DBAadhaarAuditLog -> must raise RuntimeError.
    """
    session = test_db["session"]

    aadhaar_log = DBAadhaarAuditLog(
        request_id=f"req_immutability_{uuid.uuid4()}",
        masked_aadhaar="XXXX XXXX 9988",
        supplied_name="Vikram Singh",
        name_matched=True,
        aadhaar_matched=True,
        result_code="VERIFIED_SUCCESS",
    )
    session.add(aadhaar_log)
    session.commit()
    log_id = aadhaar_log.id

    # 1. Attempt UPDATE
    aadhaar_log.supplied_name = "Tampered Singh"
    with pytest.raises(RuntimeError) as exc_info:
        session.commit()
    assert "DBAadhaarAuditLog is immutable; update operations are strictly prohibited" in str(exc_info.value)
    session.rollback()

    reloaded = session.query(DBAadhaarAuditLog).filter_by(id=log_id).one()
    assert reloaded.supplied_name == "Vikram Singh"

    # 2. Attempt DELETE
    session.delete(reloaded)
    with pytest.raises(RuntimeError) as exc_info:
        session.commit()
    assert "DBAadhaarAuditLog is immutable; delete operations are strictly prohibited" in str(exc_info.value)
    session.rollback()

    reloaded_after_del = session.query(DBAadhaarAuditLog).filter_by(id=log_id).one()
    assert reloaded_after_del is not None
