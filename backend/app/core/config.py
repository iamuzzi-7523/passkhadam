import os
from typing import Optional
from pydantic_settings import BaseSettings

def _load_env_file():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        os.path.join(os.getcwd(), "backend", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass
            break

_load_env_file()

def _resolve_database_url() -> str:
    raw = os.getenv("DATABASE_URL")
    if raw and raw.strip():
        cleaned = raw.strip()
        if cleaned.startswith("postgres://"):
            return cleaned.replace("postgres://", "postgresql+psycopg2://", 1)
        elif cleaned.startswith("postgresql://") and not cleaned.startswith("postgresql+"):
            return cleaned.replace("postgresql://", "postgresql+psycopg2://", 1)
        return cleaned
    default_sqlite = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "passkhadam.db")
    return f"sqlite:///{default_sqlite}"

def _parse_port(val: Optional[str], default: int = 587) -> int:
    if not val:
        return default
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default

class Settings(BaseSettings):
    PROJECT_NAME: str = "PASSKHADAM"
    VERSION: str = "0.5.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "passkhadam-super-secure-production-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    PUBLIC_APP_BASE_URL: str = os.getenv("PUBLIC_APP_BASE_URL", "http://127.0.0.1:5173")

    # Blockchain
    WEB3_RPC_URL: str = os.getenv("WEB3_RPC_URL") or os.getenv("RPC_URL", "http://127.0.0.1:8545")
    RPC_URL: str = os.getenv("WEB3_RPC_URL") or os.getenv("RPC_URL", "http://127.0.0.1:8545")
    CHAIN_ID: int = 1337

    # Authority Keys
    AUTHORITY_SEED: str = os.getenv("AUTHORITY_SEED", "passkhadam-master-authority-seed-2026")
    DID_SALT: str = os.getenv("DID_SALT", "passkhadam-did-seed-v1")
    PAYLOAD_SECRET_KEY_SEED: str = os.getenv("PAYLOAD_SECRET_KEY_SEED", "passkhadam-decentralized-worker-vault-key-2026")
    PAYLOAD_SECRET_KEY: str = os.getenv("PAYLOAD_SECRET_KEY", "passkhadam-decentralized-worker-vault-key-2026")
    PRESENTATION_SIGNING_SEED: str = os.getenv("PRESENTATION_SIGNING_SEED", "passkhadam-presentation-seed-2026")
    AADHAAR_SERVICE_KEY: str = os.getenv("AADHAAR_SERVICE_KEY", "pk-mock-aadhaar-service-key-internal-2026")
    PASSKHADAM_SERVICE_KEY: str = os.getenv("PASSKHADAM_SERVICE_KEY", "pk-mock-aadhaar-service-key-internal-2026")

    # IPFS Provider ('local', 'pinata', 'kubo')
    IPFS_PROVIDER: str = os.getenv("IPFS_PROVIDER", "local")
    PINATA_JWT: Optional[str] = os.getenv("PINATA_JWT", None)
    PINATA_API_KEY: Optional[str] = os.getenv("PINATA_API_KEY", None)
    PINATA_SECRET_KEY: Optional[str] = os.getenv("PINATA_SECRET_KEY", None)
    KUBO_API_URL: str = os.getenv("KUBO_API_URL", "http://127.0.0.1:5001")

    # Environment & Cloud Integration
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    RESEND_API_KEY: Optional[str] = os.getenv("RESEND_API_KEY", None)
    BREVO_API_KEY: Optional[str] = os.getenv("BREVO_API_KEY", None)
    ALLOWED_ORIGINS: Optional[str] = os.getenv("ALLOWED_ORIGINS", None)

    # Storage & Authoritative Database URL
    STORAGE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
    DATABASE_URL: str = _resolve_database_url()

    # SMTP Configuration for Real Email / OTP Delivery
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST") or None
    SMTP_PORT: int = _parse_port(os.getenv("SMTP_PORT"), 587)
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER") or None
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD") or None
    EMAILS_FROM_EMAIL: Optional[str] = os.getenv("EMAILS_FROM_EMAIL") or None

    class Config:
        case_sensitive = True
        extra = "ignore"

settings = Settings()
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
