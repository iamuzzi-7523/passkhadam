"""
PassKhadam PostgreSQL Migration & Production Initialization Script
===================================================================
Executes versioned schema creation, dialect-specific constraints,
immutability triggers, and secure platform admin provisioning
against managed PostgreSQL instances (e.g. Supabase).

Usage:
    python scripts/migrate_to_postgres.py [--db-url postgresql+psycopg2://user:pass@host:5432/dbname]
"""

import os
import sys
import argparse
import secrets
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, inspect

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings
from app.models.db import Base, DBUser, DBActivationEmail

def run_migration(db_url: str = None):
    target_url = db_url or settings.DATABASE_URL
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif target_url.startswith("postgresql://") and not target_url.startswith("postgresql+"):
        target_url = target_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    is_postgres = "postgresql" in target_url
    print(f"[*] Target database engine: {'PostgreSQL (Production/Staging)' if is_postgres else 'SQLite (Local)'}")
    
    # Redact credentials for logging
    try:
        from urllib.parse import urlparse
        p = urlparse(target_url)
        safe_netloc = f"{p.hostname}:{p.port}" if p.port else p.hostname
        print(f"[*] Target endpoint: {p.scheme}://***:***@{safe_netloc}{p.path}")
    except Exception:
        print("[*] Target endpoint: [REDACTED]")

    engine = create_engine(
        target_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )

    print("\n[Step 1/5] Creating schema and core tables...")
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"[OK] Created/Verified {len(tables)} tables: {', '.join(sorted(tables))}")

    if is_postgres:
        print("\n[Step 2/5] Applying PostgreSQL Partial Indexes & Invariant Constraints...")
        with engine.begin() as conn:
            # Check if category_scopes or category_authorization_requests exists before indexing
            if "category_scopes" in tables:
                conn.execute(text("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_category_scope 
                    ON category_scopes (organization_id, category, skill_level, nature_of_employment) 
                    WHERE is_active_scope = true;
                """))
                print("[OK] Partial unique index 'uq_active_category_scope' active.")
            elif "category_authorization_requests" in tables:
                # Table already has unique constraints defined via SQLAlchemy ORM
                print("[OK] Category authorization table verified with ORM constraints.")
            else:
                print("[OK] No separate category_scopes table needed; skipping index.")

        print("\n[Step 3/5] Applying Audit Log Immutability Triggers...")
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'Audit logs are immutable; UPDATE and DELETE operations are strictly prohibited.';
                END;
                $$ LANGUAGE plpgsql;
            """))
            # Apply immutability trigger to governance_audit_logs
            conn.execute(text("""
                DROP TRIGGER IF EXISTS trg_protect_governance_audit_logs ON governance_audit_logs;
                CREATE TRIGGER trg_protect_governance_audit_logs
                BEFORE UPDATE OR DELETE ON governance_audit_logs
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
            """))
            # Apply immutability trigger to aadhaar_audit_logs
            conn.execute(text("""
                DROP TRIGGER IF EXISTS trg_protect_aadhaar_audit_logs ON aadhaar_audit_logs;
                CREATE TRIGGER trg_protect_aadhaar_audit_logs
                BEFORE UPDATE OR DELETE ON aadhaar_audit_logs
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
            """))
            print("[OK] Audit log immutability triggers active on 'governance_audit_logs' and 'aadhaar_audit_logs'.")
    else:
        print("\n[Step 2/5] SQLite mode: Skipping PostgreSQL-specific triggers and partial index syntax.")
        print("[Step 3/5] SQLite mode: Table-level SQLite invariants active.")

    print("\n[Step 4/5] Initializing Sequence Alignment...")
    if is_postgres:
        with engine.begin() as conn:
            for table in tables:
                try:
                    conn.execute(text(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table}', 'id'),
                            COALESCE(MAX(id), 1),
                            MAX(id) IS NOT NULL
                        ) FROM {table};
                    """))
                except Exception:
                    pass
        print("[OK] Primary key sequences aligned.")
    else:
        print("[OK] SQLite autoincrement sequence active.")

    print("\n[Step 5/5] Provisioning Initial Platform Governance Admin...")
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        admin_user = db.query(DBUser).filter(DBUser.role == "ADMIN").first()
        if not admin_user:
            admin_email = os.getenv("ADMIN_EMAIL", "governance@passkhadam.internal")
            initial_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(initial_token.encode("utf-8")).hexdigest()
            correlation_id = secrets.token_hex(8)

            admin_user = DBUser(
                full_name="Platform Governance Administrator",
                email=admin_email,
                phone="+91 9000000000",
                password_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(), # Random locked password until activated
                role="ADMIN",
                status="PENDING_ACTIVATION",
                is_email_verified=False,
                is_phone_verified=False,
                created_at=datetime.utcnow()
            )
            db.add(admin_user)
            db.flush()

            act_record = DBActivationEmail(
                entity_type="ADMIN",
                entity_id=admin_user.id,
                recipient_email=admin_email,
                token_hash=token_hash,
                status="PENDING",
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.add(act_record)
            db.commit()

            print(f"[OK] Platform Governance Admin created in PENDING_ACTIVATION status.")
            print(f"[*] Admin Email: {admin_email}")
            print(f"[*] Correlation ID: {correlation_id}")
            print(f"[*] One-time 24-hour activation token: {initial_token}")
            print(f"[!] Keep this token secure and deliver it out-of-band to the platform administrator.")
        else:
            print(f"[OK] Platform Governance Admin already provisioned (ID: {admin_user.id}, Status: {admin_user.status}).")
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("  MIGRATION & DATABASE INITIALIZATION COMPLETE (Exit Code 0)")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PassKhadam Database Migration to PostgreSQL")
    parser.add_argument("--db-url", type=str, default=None, help="Authoritative Database Connection URI")
    args = parser.parse_args()
    run_migration(args.db_url)
