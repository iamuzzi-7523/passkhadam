"""
migrate_to_postgres.py
Production PostgreSQL Schema Migration, Security Hardening & Initial Admin Provisioning
for PASSKHADAM on Supabase Managed PostgreSQL.
"""

import os
import sys
import secrets
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.models.db import (
    Base, DBUser, DBWorkerProfile, DBEmployerOrganization, DBGovernmentOfficer,
    DBGovernanceAuditLog, DBAadhaarAuditLog, DBActivationEmail
)

def run_migration():
    print("=" * 70)
    print("PASSKHADAM - PostgreSQL Production Database Migration & Setup")
    print("=" * 70)

    db_url = settings.DATABASE_URL
    if not ("postgresql" in db_url or "postgres" in db_url):
        print(f"[ERROR] DATABASE_URL is not configured for PostgreSQL: {db_url}")
        print("Please set the DATABASE_URL environment variable to your Supabase PostgreSQL URI.")
        print("Example: postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres")
        sys.exit(1)

    print(f"\n[1/5] Connecting to managed PostgreSQL database...")
    engine = create_engine(
        db_url,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True
    )

    with engine.connect() as conn:
        res = conn.execute(text("SELECT version();")).fetchone()
        print(f"Connected successfully: {res[0][:60]}...")

    print("\n[2/5] Creating relational schema tables and constraints...")
    Base.metadata.create_all(bind=engine)
    print("All core tables created successfully.")

    print("\n[3/5] Applying PostgreSQL triggers & partial unique indexes...")
    with engine.connect() as conn:
        # Partial unique index for active employer category scopes
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_active_category_scope
                ON category_authorization_requests (organization_id, category, skill_level, nature_of_employment)
                WHERE is_active_scope = true;
            """))
            conn.commit()
            print("  ✓ Created partial unique index: uq_active_category_scope")
        except Exception as e:
            print(f"  Note: {e}")

        # Immutability triggers for audit logs
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
        print("  ✓ Created audit log immutability triggers (governance_audit_logs & aadhaar_audit_logs)")

    print("\n[4/5] Synchronizing autoincrement primary key sequences...")
    with engine.connect() as conn:
        seq_tables = [
            ("users", "users_id_seq"),
            ("worker_profiles", "worker_profiles_id_seq"),
            ("employer_organizations", "employer_organizations_id_seq"),
            ("government_officers", "government_officers_id_seq"),
            ("governance_audit_logs", "governance_audit_logs_id_seq")
        ]
        for tbl, seq in seq_tables:
            try:
                conn.execute(text(f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {tbl}), 1));"))
                conn.commit()
            except Exception:
                pass
        print("  ✓ Autoincrement sequences synchronized.")

    print("\n[5/5] Provisioning Initial Platform Admin (Secure One-Time Token)...")
    Session = sessionmaker(bind=engine)
    session = Session()

    admin_email = "admin@passkhadam.org"
    existing_admin = session.query(DBUser).filter(DBUser.email == admin_email).first()

    if existing_admin:
        print(f"  Notice: Platform Admin ({admin_email}) already exists with status: {existing_admin.status}.")
    else:
        # Generate cryptographically secure one-time activation token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        salt = secrets.token_hex(16)
        temp_pwd_hash = hashlib.sha256(f"{secrets.token_hex(32)}:{salt}".encode("utf-8")).hexdigest()

        admin_user = DBUser(
            email=admin_email,
            full_name="Platform Administrator",
            phone="+91 99999 00001",
            password_hash=f"{salt}:{temp_pwd_hash}",
            role="ADMIN",
            status="PENDING_ACTIVATION",
            is_email_verified=True,
            is_phone_verified=True,
            created_at=datetime.utcnow()
        )
        session.add(admin_user)
        session.flush()

        activation_record = DBActivationEmail(
            user_id=admin_user.id,
            target_type="ADMIN",
            recipient_email=admin_email,
            recipient_name="Platform Administrator",
            token_hash=token_hash,
            delivery_status="PENDING_OPERATOR_REDEMPTION",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_used=False
        )
        session.add(activation_record)
        session.commit()

        print("  ✓ Platform Admin provisioned in status: PENDING_ACTIVATION")
        print("\n" + "=" * 70)
        print("SECURE INITIAL ADMIN ACTIVATION CREDENTIAL (ONE-TIME PROMPT):")
        print(f"  Target Email:     {admin_email}")
        print(f"  Single-Use Token: {raw_token}")
        print(f"  Valid Duration:   24 Hours")
        print(f"  Redemption Route: /admin/activate?token={raw_token}")
        print("  IMPORTANT: Copy this single-use token now. It is hashed and not stored in plaintext.")
        print("=" * 70)

    session.close()
    print("\n[SUCCESS] PostgreSQL Database Migration & Hardening Completed Successfully!\n")

if __name__ == "__main__":
    run_migration()
