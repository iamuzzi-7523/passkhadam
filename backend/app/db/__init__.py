"""
backend/app/db/__init__.py
Database package initialization for PassKhadam backend.
"""

from app.db.migrate import migrate_database, run_migrations

__all__ = ["migrate_database", "run_migrations"]
