"""
Milestone 1 Adversarial Challenge: DBGovernmentOfficer Geographic Hierarchy Invariants (Challenger_2)
===================================================================================================
Adversarially tests DBGovernmentOfficer geographic invariants:
1. STATE officer with empty or None state -> MUST revert / raise exception.
2. DISTRICT officer with state but None or empty district -> MUST revert / raise exception.
3. BLOCK officer with state and district but None or empty block -> MUST revert / raise exception.
4. Validation at both ORM level (@validates) and SQLite CheckConstraint level (ck_officer_geographic_hierarchy).
5. Valid configurations (NATIONAL, STATE, DISTRICT, BLOCK) succeed and persist cleanly.
"""

import pytest
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.models.db import Base, DBGovernmentOfficer, DBUser


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database enforcing foreign keys and constraints."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    # Enable foreign keys for SQLite
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


class TestOfficerGeographicHierarchyInvariants:
    """Adversarial stress testing of geographic hierarchy invariants."""

    # --------------------------------------------------------------------------
    # 1. STATE Invariants
    # --------------------------------------------------------------------------
    def test_state_officer_with_none_state_raises_at_orm_level(self):
        """STATE officer with None state must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="State is mandatory for STATE authority level"):
            DBGovernmentOfficer(
                authority_level="STATE",
                state=None,
                officer_name="Officer State Invalid",
                official_email="officer_state_invalid@gov.in"
            )

    def test_state_officer_with_empty_state_raises_at_orm_level(self):
        """STATE officer with empty string state must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="State is mandatory for STATE authority level"):
            DBGovernmentOfficer(
                authority_level="STATE",
                state="",
                officer_name="Officer State Empty",
                official_email="officer_state_empty@gov.in"
            )

    def test_state_officer_with_whitespace_state_raises_at_orm_level(self):
        """STATE officer with whitespace-only state must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="State is mandatory for STATE authority level"):
            DBGovernmentOfficer(
                authority_level="STATE",
                state="   ",
                officer_name="Officer State Whitespace",
                official_email="officer_state_ws@gov.in"
            )

    def test_state_officer_omitted_state_violates_db_check_constraint(self, test_db):
        """Bypassing ORM validation (e.g. state omitted or raw DB) violates ck_officer_geographic_hierarchy."""
        # When state is omitted from kwargs, ORM validator for state isn't triggered on init,
        # but DB CheckConstraint MUST reject on flush/commit.
        officer = DBGovernmentOfficer(
            authority_level="STATE",
            officer_name="Bypass State Officer",
            official_email="bypass_state@gov.in"
        )
        test_db.add(officer)
        with pytest.raises(IntegrityError):
            test_db.flush()
        test_db.rollback()

    # --------------------------------------------------------------------------
    # 2. DISTRICT Invariants
    # --------------------------------------------------------------------------
    def test_district_officer_with_state_but_none_district_raises_at_orm_level(self):
        """DISTRICT officer with state but None district must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="District is mandatory for DISTRICT authority level"):
            DBGovernmentOfficer(
                authority_level="DISTRICT",
                state="Maharashtra",
                district=None,
                officer_name="Officer District None",
                official_email="officer_dist_none@gov.in"
            )

    def test_district_officer_with_state_but_empty_district_raises_at_orm_level(self):
        """DISTRICT officer with state but empty district must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="District is mandatory for DISTRICT authority level"):
            DBGovernmentOfficer(
                authority_level="DISTRICT",
                state="Maharashtra",
                district="",
                officer_name="Officer District Empty",
                official_email="officer_dist_empty@gov.in"
            )

    def test_district_officer_with_state_but_whitespace_district_raises_at_orm_level(self):
        """DISTRICT officer with state but whitespace district must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="District is mandatory for DISTRICT authority level"):
            DBGovernmentOfficer(
                authority_level="DISTRICT",
                state="Maharashtra",
                district="   ",
                officer_name="Officer District Whitespace",
                official_email="officer_dist_ws@gov.in"
            )

    def test_district_officer_with_none_state_raises_at_orm_level(self):
        """DISTRICT officer with None state must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="State is mandatory for DISTRICT authority level"):
            DBGovernmentOfficer(
                authority_level="DISTRICT",
                state=None,
                district="Pune",
                officer_name="Officer District No State",
                official_email="officer_dist_nostate@gov.in"
            )

    def test_district_officer_omitted_district_violates_db_check_constraint(self, test_db):
        """DISTRICT officer with omitted district violates ck_officer_geographic_hierarchy on commit."""
        officer = DBGovernmentOfficer(
            authority_level="DISTRICT",
            state="Maharashtra",
            officer_name="Bypass District Officer",
            official_email="bypass_district@gov.in"
        )
        test_db.add(officer)
        with pytest.raises(IntegrityError):
            test_db.flush()
        test_db.rollback()

    # --------------------------------------------------------------------------
    # 3. BLOCK Invariants
    # --------------------------------------------------------------------------
    def test_block_officer_with_state_and_district_but_none_block_raises_at_orm_level(self):
        """BLOCK officer with state and district but None block must raise ValueError at ORM level."""
        with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                authority_level="BLOCK",
                state="Maharashtra",
                district="Pune",
                block=None,
                officer_name="Officer Block None",
                official_email="officer_block_none@gov.in"
            )

    def test_block_officer_with_state_and_district_but_empty_block_raises_at_orm_level(self):
        """BLOCK officer with state and district but empty block must raise ValueError at ORM level."""
        with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                authority_level="BLOCK",
                state="Maharashtra",
                district="Pune",
                block="",
                officer_name="Officer Block Empty",
                official_email="officer_block_empty@gov.in"
            )

    def test_block_officer_with_state_and_district_but_whitespace_block_raises_at_orm_level(self):
        """BLOCK officer with state and district but whitespace block must raise ValueError at ORM level."""
        with pytest.raises(ValueError, match="Block is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                authority_level="BLOCK",
                state="Maharashtra",
                district="Pune",
                block="   ",
                officer_name="Officer Block Whitespace",
                official_email="officer_block_ws@gov.in"
            )

    def test_block_officer_with_none_district_raises_at_orm_level(self):
        """BLOCK officer with None district must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="District is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                authority_level="BLOCK",
                state="Maharashtra",
                district=None,
                block="Haveli",
                officer_name="Officer Block No District",
                official_email="officer_block_nodist@gov.in"
            )

    def test_block_officer_with_none_state_raises_at_orm_level(self):
        """BLOCK officer with None state must raise ValueError at ORM validation level."""
        with pytest.raises(ValueError, match="State is mandatory for BLOCK authority level"):
            DBGovernmentOfficer(
                authority_level="BLOCK",
                state=None,
                district="Pune",
                block="Haveli",
                officer_name="Officer Block No State",
                official_email="officer_block_nostate@gov.in"
            )

    def test_block_officer_omitted_block_violates_db_check_constraint(self, test_db):
        """BLOCK officer with omitted block violates ck_officer_geographic_hierarchy on commit."""
        officer = DBGovernmentOfficer(
            authority_level="BLOCK",
            state="Maharashtra",
            district="Pune",
            officer_name="Bypass Block Officer",
            official_email="bypass_block@gov.in"
        )
        test_db.add(officer)
        with pytest.raises(IntegrityError):
            test_db.flush()
        test_db.rollback()

    # --------------------------------------------------------------------------
    # 4. Valid Geographic Hierarchies
    # --------------------------------------------------------------------------
    def test_valid_national_officer_succeeds(self, test_db):
        """NATIONAL officer with no state/district/block persists cleanly."""
        officer = DBGovernmentOfficer(
            authority_level="NATIONAL",
            state=None,
            district=None,
            block=None,
            officer_name="National Officer",
            official_email="national@gov.in"
        )
        test_db.add(officer)
        test_db.commit()

        retrieved = test_db.query(DBGovernmentOfficer).filter_by(official_email="national@gov.in").first()
        assert retrieved is not None
        assert retrieved.authority_level == "NATIONAL"
        assert retrieved.state is None
        assert retrieved.district is None
        assert retrieved.block is None

    def test_valid_state_officer_succeeds(self, test_db):
        """STATE officer with state and no district/block persists cleanly."""
        officer = DBGovernmentOfficer(
            authority_level="STATE",
            state="Karnataka",
            district=None,
            block=None,
            officer_name="State Officer KA",
            official_email="state_ka@gov.in"
        )
        test_db.add(officer)
        test_db.commit()

        retrieved = test_db.query(DBGovernmentOfficer).filter_by(official_email="state_ka@gov.in").first()
        assert retrieved is not None
        assert retrieved.authority_level == "STATE"
        assert retrieved.state == "Karnataka"
        assert retrieved.district is None
        assert retrieved.block is None

    def test_valid_district_officer_succeeds(self, test_db):
        """DISTRICT officer with state and district persists cleanly."""
        officer = DBGovernmentOfficer(
            authority_level="DISTRICT",
            state="Karnataka",
            district="Bengaluru Urban",
            block=None,
            officer_name="District Officer",
            official_email="district_ka@gov.in"
        )
        test_db.add(officer)
        test_db.commit()

        retrieved = test_db.query(DBGovernmentOfficer).filter_by(official_email="district_ka@gov.in").first()
        assert retrieved is not None
        assert retrieved.authority_level == "DISTRICT"
        assert retrieved.state == "Karnataka"
        assert retrieved.district == "Bengaluru Urban"
        assert retrieved.block is None

    def test_valid_block_officer_succeeds(self, test_db):
        """BLOCK officer with state, district, and block persists cleanly."""
        officer = DBGovernmentOfficer(
            authority_level="BLOCK",
            state="Karnataka",
            district="Bengaluru Urban",
            block="Bangalore South",
            officer_name="Block Officer",
            official_email="block_ka@gov.in"
        )
        test_db.add(officer)
        test_db.commit()

        retrieved = test_db.query(DBGovernmentOfficer).filter_by(official_email="block_ka@gov.in").first()
        assert retrieved is not None
        assert retrieved.authority_level == "BLOCK"
        assert retrieved.state == "Karnataka"
        assert retrieved.district == "Bengaluru Urban"
        assert retrieved.block == "Bangalore South"
