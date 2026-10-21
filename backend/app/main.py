import os
import re
import json
import hashlib
import logging
from typing import Optional, List
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware

from urllib.parse import urlparse

from app.core.config import settings
from app.models.db import init_db, SessionLocal, DBUser, DBWorkerProfile, DBGovernmentOfficer
from app.api.endpoints import auth, worker, employer, government, admin, aadhaar
from app.services.blockchain_service import blockchain_service

logger = logging.getLogger("passkhadam.access")

def _validate_and_sanitize_origins(origins_input: Optional[str], is_prod: bool) -> list[str]:
    valid: list[str] = []
    if not origins_input:
        return valid
    for raw in origins_input.split(","):
        candidate = raw.strip()
        if not candidate:
            continue
        if candidate == "app://passkhadam.app":
            if candidate not in valid:
                valid.append(candidate)
            continue
        try:
            parsed = urlparse(candidate)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"CORS Origin dropped (missing scheme/netloc): '{candidate}'")
                continue
            if parsed.path not in ("", "/"):
                logger.warning(f"CORS Origin dropped (contains path component): '{candidate}'")
                continue
            if parsed.params or parsed.query or parsed.fragment:
                logger.warning(f"CORS Origin dropped (contains query/fragment): '{candidate}'")
                continue
            if parsed.username or parsed.password:
                logger.warning(f"CORS Origin dropped (contains credentials): '{candidate}'")
                continue
            if "*" in candidate:
                logger.warning(f"CORS Origin dropped (wildcards prohibited): '{candidate}'")
                continue

            if is_prod:
                if parsed.scheme.lower() != "https":
                    logger.warning(f"CORS Origin dropped in production (non-HTTPS): '{candidate}'")
                    continue
                host = parsed.hostname or ""
                if host.lower() in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
                    logger.warning(f"CORS Origin dropped in production (loopback host): '{candidate}'")
                    continue
            else:
                if parsed.scheme.lower() not in ["http", "https"]:
                    logger.warning(f"CORS Origin dropped (invalid scheme): '{candidate}'")
                    continue

            normalized = f"{parsed.scheme.lower()}://{parsed.netloc}"
            if normalized not in valid:
                valid.append(normalized)
        except Exception as e:
            logger.warning(f"CORS Origin dropped (parse error): '{candidate}': {e}")
    return valid

class SensitiveQueryRedactionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        query_string = request.url.query
        if query_string:
            sanitized_query = re.sub(
                r'(?i)(^|[?&])(token|activation_token|otp)=([^&]*)',
                r'\g<1>\g<2>=[REDACTED]',
                query_string
            )
            request.state.sanitized_query = sanitized_query
            logger.info(f"{request.method} {request.url.path}?{sanitized_query}")
        else:
            request.state.sanitized_query = ""
            logger.info(f"{request.method} {request.url.path}")

        response = await call_next(request)
        return response

app = FastAPI(
    title="PASSKHADAM Decentralized Identity Platform API",
    description="Backend services, Common Cryptographic Verification Engine, and Mock Aadhaar Authority for Migrant Workers",
    version=settings.VERSION
)

# Request logging & token redaction middleware
app.add_middleware(SensitiveQueryRedactionMiddleware)

# CORS middleware configuration with strict environment separation
is_production = settings.ENVIRONMENT.lower() in ["production", "staging"] or os.getenv("RENDER") == "true"

if is_production:
    # Production Allowlist: Strictly immutable allowlist of approved production web & desktop origins
    ALLOWED_ORIGINS = [
        "https://passkhadam.vercel.app",  # Production Web Portal
        "app://passkhadam.app",            # Packaged Electron Desktop Application
    ]
    if getattr(settings, "ALLOWED_ORIGINS", None):
        sanitized_env_origins = _validate_and_sanitize_origins(settings.ALLOWED_ORIGINS, is_prod=True)
        for o in sanitized_env_origins:
            if o not in ALLOWED_ORIGINS:
                ALLOWED_ORIGINS.append(o)
    if os.getenv("ADDITIONAL_CORS_ORIGINS"):
        logger.warning("Security Warning: ADDITIONAL_CORS_ORIGINS is ignored in production mode to prevent configuration-based origin injection.")
else:
    # Development Allowlist: Localhost dev servers and testing clients
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "app://passkhadam.app"
    ]
    if getattr(settings, "ALLOWED_ORIGINS", None):
        sanitized_env_origins = _validate_and_sanitize_origins(settings.ALLOWED_ORIGINS, is_prod=False)
        for o in sanitized_env_origins:
            if o not in ALLOWED_ORIGINS:
                ALLOWED_ORIGINS.append(o)
    if os.getenv("ADDITIONAL_CORS_ORIGINS"):
        for origin in _validate_and_sanitize_origins(os.getenv("ADDITIONAL_CORS_ORIGINS"), is_prod=False):
            if origin not in ALLOWED_ORIGINS:
                ALLOWED_ORIGINS.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Service-Key", "X-Device-ID"],
)

# Ensure database tables exist
init_db()

# Register routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(worker.router, prefix="/api/v1/worker", tags=["Worker Portal"])
app.include_router(employer.router, prefix="/api/v1/employer", tags=["Employer Portal"])
app.include_router(government.router, prefix="/api/v1/government", tags=["Government Portal"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Platform Admin"])
app.include_router(aadhaar.router, prefix="/api/v1/aadhaar", tags=["Mock Aadhaar Authority"])

@app.on_event("startup")
def on_startup():
    init_db()
    # Seed default demonstration users for all 5 roles if not present
    db = SessionLocal()
    try:
        def get_or_create_user(email, full_name, phone, role, firebase_uid=None, org_addr=None, org_name=None, org_status=None):
            u = db.query(DBUser).filter(DBUser.email == email).first()
            pw_hash = hashlib.sha256("passkhadam123".encode("utf-8")).hexdigest()
            if not u:
                u = DBUser(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    password_hash=pw_hash,
                    role=role,
                    status="ACTIVE",
                    firebase_uid=firebase_uid or f"uid_{role.lower()}_live",
                    organization_address=org_addr,
                    organization_name=org_name,
                    organization_status=org_status,
                    is_email_verified=True,
                    is_phone_verified=True
                )
                db.add(u)
                db.commit()
                db.refresh(u)
            else:
                updated = False
                if not u.status:
                    u.status = "ACTIVE"
                    updated = True
                if not u.firebase_uid:
                    u.firebase_uid = firebase_uid or f"uid_{role.lower()}_live"
                    updated = True
                if org_addr and not u.organization_address:
                    u.organization_address = org_addr
                    u.organization_name = org_name
                    u.organization_status = org_status or "APPROVED"
                    updated = True
                if updated:
                    db.commit()
                    db.refresh(u)
            return u

        # 1. Worker
        worker_user = get_or_create_user(
            "worker@passkhadam.org",
            "Mohammed Uzair",
            "+91 9876543210",
            "WORKER",
            firebase_uid="uid_worker_live"
        )
        profile = db.query(DBWorkerProfile).filter(DBWorkerProfile.user_id == worker_user.id).first()
        if not profile:
            profile = DBWorkerProfile(
                user_id=worker_user.id,
                full_name="Mohammed Uzair",
                dob="1995-04-12",
                gender="Male",
                origin_state="Karnataka",
                current_state="Karnataka",
                address="45/2 BTM Layout, Bengaluru, Karnataka",
                worker_category="Mason",
                skills_json=json.dumps(["Mason", "Bricklaying", "Concrete Work", "Plumbing Assistance"]),
                is_aadhaar_verified=False
            )
            db.add(profile)
            db.commit()

        # 2. Employer
        get_or_create_user(
            "employer@apexinfra.com",
            "Apex Infrastructure Admin",
            "+91 9876543211",
            "EMPLOYER",
            firebase_uid="uid_employer_live",
            org_addr="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            org_name="Apex Infrastructure & Construction Ltd",
            org_status="APPROVED"
        )

        # 3. Government Authority
        gov_user = get_or_create_user(
            "gov@maharashtra.gov.in",
            "Maharashtra Labour Welfare Officer",
            "+91 9876543212",
            "GOVERNMENT",
            firebase_uid="uid_gov_live",
            org_addr=None,
            org_name="Labour Welfare",
            org_status="APPROVED"
        )
        if gov_user.organization_address == "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65":
            gov_user.organization_address = None
            db.commit()

        gov_off = db.query(DBGovernmentOfficer).filter(
            (DBGovernmentOfficer.user_id == gov_user.id) |
            (DBGovernmentOfficer.official_email == "gov@maharashtra.gov.in") |
            (DBGovernmentOfficer.officer_reference_id == "GOV-OFF-0028")
        ).first()
        if not gov_off:
            gov_off = DBGovernmentOfficer(
                user_id=gov_user.id,
                officer_name="Maharashtra Labour Welfare Officer",
                full_name="Maharashtra Labour Welfare Officer",
                officer_reference_id="GOV-OFF-0028",
                department="Labour Welfare",
                designation="Welfare Commissioner",
                authority_level="STATE",
                state="Maharashtra",
                district=None,
                block=None,
                official_email="gov@maharashtra.gov.in",
                phone="+91-22-22020000",
                status="ACTIVE",
                permissions_json=json.dumps(["WORKER_VERIFICATION", "BENEFIT_DISBURSEMENT"]),
                benefit_permissions_json=json.dumps(["1", "2", "Interstate Migrant Worker Relief", "Accident Relief"])
            )
            db.add(gov_off)
            db.commit()
            db.refresh(gov_off)
        else:
            gov_off.user_id = gov_user.id
            gov_off.officer_reference_id = "GOV-OFF-0028"
            gov_off.full_name = "Maharashtra Labour Welfare Officer"
            gov_off.officer_name = "Maharashtra Labour Welfare Officer"
            gov_off.department = "Labour Welfare"
            gov_off.designation = "Welfare Commissioner"
            gov_off.authority_level = "STATE"
            gov_off.state = "Maharashtra"
            gov_off.official_email = "gov@maharashtra.gov.in"
            gov_off.phone = "+91-22-22020000"
            gov_off.status = "ACTIVE"
            try:
                existing_perms = json.loads(gov_off.permissions_json) if gov_off.permissions_json else []
            except Exception:
                existing_perms = []
            for p in ["WORKER_VERIFICATION", "BENEFIT_DISBURSEMENT"]:
                if p not in existing_perms:
                    existing_perms.append(p)
            gov_off.permissions_json = json.dumps(existing_perms)
            db.commit()

        # 4. Platform Admin
        get_or_create_user(
            "admin@passkhadam.org",
            "PassKhadam Platform Governance",
            "+91 9876543213",
            "ADMIN",
            firebase_uid="uid_admin_live"
        )

        # 5. Mock Aadhaar Authority
        get_or_create_user(
            "authority@uidai.gov.in",
            "UIDAI Mock Authority Gateway",
            "+91 9876543214",
            "AADHAAR",
            firebase_uid="uid_aadhaar_live"
        )

        # Synchronize anchored worker profiles from database into active blockchain service
        blockchain_service.sync_from_database(db)

    finally:
        db.close()

@app.get("/")
def root():
    return {
        "platform": "PASSKHADAM",
        "description": "Decentralized Identity Verification Platform for Migrant Workers",
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "health": "/health",
        "docs": "/docs"
    }

@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    """
    HTTP Health Check Endpoint for Cloud Platforms (Render, Kubernetes).
    Returns 200 OK with operational diagnostics and database connectivity status.
    """
    db_status = "UNKNOWN"
    try:
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_status = "CONNECTED"
        finally:
            db.close()
    except Exception as e:
        db_status = f"ERROR: {str(e)}"

    is_healthy = db_status == "CONNECTED"
    return {
        "status": "HEALTHY" if is_healthy else "DEGRADED",
        "service": "PASSKHADAM Backend API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status
    }
