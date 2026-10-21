# Project: PassKhadam v0.5 — Runtime Defect Remediation & Full Functional Audit

## Architecture
- **Presentation Tier**: Vite React frontend with role-aware portals (Worker, Employer, Government, Admin, Mock Aadhaar). All client state is derived strictly from authenticated server-side context; zero static demo fallbacks or client-side authorization decisions. In-memory token sanitization (`history.replaceState`), dedicated Government activation tab, and accessible debounced search.
- **Application & API Tier**: FastAPI backend running Python 3.11 with SQLAlchemy ORM, Web3.py, PyCryptodome (AES-256-GCM), PyNaCl / cryptography (Ed25519). Authenticated principal resolution via Firebase JWT and `PassKhadamUser` canonical model. Shared verification engine resolves `DBGovernmentOfficer.id` without EVM address checking.
- **Relational Store**: SQLite database (`backend/app/storage/passkhadam.db`) enforcing foreign key integrity, partial unique indices (`uq_active_category_scope`), composite replay constraints (`uq_presentation_verifier_context`), stable `worker_profiles.aadhaar_record_id` foreign reference, and append-only governance and Aadhaar audit logs.
- **Decentralized Identity & Smart Contracts**: Hardhat EVM contracts on local node (Chain ID 1337):
  - `WorkerIdentityRegistry.sol`: Canonical decentralized registry of worker DIDs, credential hashes, and revocation states.
  - `OrganizationRegistry.sol`: Employer organization approvals and category scope authorizations (including `revokeCategory`).
  - `CredentialRegistry.sol`: W3C credential schema and issuer status.
  - `EmploymentRegistry.sol`: On-chain active employment records and event transitions.
  - `WelfareSchemeRegistry.sol`: Scheme registration and welfare claim disbursement with dynamic cooldowns.
- **Decentralized Storage & Off-Chain Artifacts**: IPFS content-addressed storage for AES-256-GCM encrypted verifiable credentials, with SHA-256 integrity hash verification against on-chain records.
- **External Identity Boundary**: Mock Aadhaar service simulating UIDAI demographic verification, accessed exclusively by backend services via `X-PassKhadam-Service-Key`, keyed by internal UUID `record_id`. Live dynamic status revalidation queried on all worker read paths.
- **Mail Transport & Delivery**: Standard `smtplib` mailer reporting truthful states: `PENDING` (unconfigured), `SENT` (transport acceptance), `FAILED` (dispatch error).

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---|---|---|---|
| 1 | Stable `aadhaar_record_id` & Migration Backfill | Schema column addition and strict authoritative reconciliation backfill from audit logs. | M1 | Survey (R1) |
| 2 | Dynamic Live Aadhaar Status Revalidation | Revalidates citizen record status on session/login/profile/wallet/protected ops. | M1 | Survey (R1) |
| 3 | Comprehensive QR Generation Security Gating | Rejects QR generation with HTTP 403 Forbidden when Aadhaar status is not ACTIVE. | M1 | Survey (R1) |
| 4 | Idempotent Worker Identity Recovery | Re-activation recovers status cleanly without creating duplicate DIDs or credentials. | M1 | Survey (R1) |
| 5 | Worker Portal Dynamic Status Presentation | Renders distinct status badges and error handling in WorkerPortal.jsx. | M1 | Survey (R1) |
| 6 | Atomic Employer Registration Persistence | Durably persists DBEmployerOrganization and DBCategoryAuthorizationRequest in atomic transaction. | M2 | Survey (R2) |
| 7 | Employer Registration Route Aliasing & Payload Alignment | Aligns AuthModal payload and adds `/api/v1/employer/register` route alias. | M2 | Survey (R2) |
| 8 | Route-Specific Admin Organization Query | Separates `/organizations` from `/pending-organizations` (strictly PENDING_REVIEW). | M2 | Survey (R2) |
| 9 | Admin Category Scopes 6 Dedicated Views | Reorganizes Category Scopes in AdminPortal.jsx into 6 dedicated workflow views. | M2 | Survey (R3) |
| 10 | Category Discontinuation Decoupling Invariant | Discontinuing a category revokes scope on-chain without suspending employer org. | M2 | Survey (R3) |
| 11 | Server-Side Admin Directory Search & Filtering | Adds search, date ranges, status filters across orgs, categories, and officers. | M3 | Survey (R4) |
| 12 | Pagination Envelopes & Debounced UI Controls | Returns total_count envelopes and adds 300ms debouncing and pagination controls in UI. | M3 | Survey (R4) |
| 13 | Truthful Error Handling in Admin UI | Displays visible backend error alerts instead of false empty state cards. | M3 | Survey (R2, R4) |
| 14 | Canonical Government Officer Caller ID Resolution | Resolves verification caller strictly from PassKhadamUser -> DBGovernmentOfficer.id. | M4 | Survey (R5) |
| 15 | Elimination of EVM Address Expectation for Officers | Removes wallet address checks in verification_engine.py for government officers. | M4 | Survey (R5) |
| 16 | Officer Standing, Permission & Jurisdiction Verification | Verifies active status, WORKER_VERIFICATION permission, and jurisdiction with structured error codes. | M4 | Survey (R5) |
| 17 | Truthful Activation Email Delivery States | Records PENDING (unconfigured), SENT (transport accepted), FAILED (error) in DBActivationEmail. | M5 | Survey (R6) |
| 18 | Target-Type Token Isolation Enforcement | Enforces strict target-type matching (rejects Gov tokens on Employer routes and vice versa). | M5 | Survey (R6) |
| 19 | Dedicated Government Officer Activation Tab | Adds Gov activation tab in AuthModal.jsx submitting to `/api/v1/government/activate`. | M5 | Survey (R6) |
| 20 | Configurable Base URL & In-Memory Token Sanitization | Uses PUBLIC_APP_BASE_URL, sanitizes token from URL into memory before requests. | M5 | Survey (R6) |
| 21 | Referrer-Policy no-referrer & Log Token Redaction | Configures Referrer-Policy and redacts sensitive token parameters from server logs. | M5 | Survey (R6) |
| 22 | Automated Regression Test Suites | Comprehensive test suites for R1-R6 defects with 100% pass rate. | E2E | Survey (R7) |
| 23 | Full 5-Role Functional Audit & Baseline Verification | Complete 5-role audit checklist across all portals, smart contracts, and invariants. | M6 | Survey (R7) |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1 | Live Aadhaar Source-Record Status Revalidation & Migration Integrity | Add `aadhaar_record_id` to `DBWorkerProfile`, migration script backfill, dynamic status query in `worker.py`, distinct statuses (`ACTIVE`, `INACTIVE`, `SUSPENDED`, `UNAVAILABLE`, `UNVERIFIED`), HTTP 403 on non-ACTIVE QR generation, dynamic status UI in `WorkerPortal.jsx`. | none | DONE |
| M2 | Durable Employer Submission & Admin Category Scopes Reorganization | Atomic DB transaction for employer registration, route alias `/register`, payload alignment in `AuthModal.jsx`, shared `query_organizations_base`, strict `/pending-organizations` filter, 6 dedicated views in `AdminPortal.jsx`, category `SUSPEND` action, decoupling invariant. | none | DONE |
| M3 | Search, Filtering & Pagination Across Admin Directories | Server-side `search`, date filters, pagination envelope (`total_count`, `items`) on `/organizations`, `/category-requests`, `/government-officers`, debounced inputs, pagination controls, visible error alerts in `AdminPortal.jsx`. | M2 | DONE |
| M4 | Canonical Government Officer Authorization Alignment | Resolve verification caller strictly from `PassKhadamUser` -> `DBGovernmentOfficer.id`, eliminate EVM address checking in `verification_engine.py`, verify standing, `WORKER_VERIFICATION` permission, jurisdiction, return structured error codes. | none | DONE |
| M5 | Activation Security, Token Isolation & Unambiguous Delivery Policy | Dedicated Gov activation tab in `AuthModal.jsx`, truthful delivery states (`PENDING`, `SENT`, `FAILED`), mailer integration, `PUBLIC_APP_BASE_URL`, token target isolation, in-memory URL token sanitization, `Referrer-Policy: no-referrer`, log token redaction. | none | DONE |
| E2E | Dual Track E2E Test Suite Creation | Design and publish comprehensive opaque-box test suites for R1-R6 requirements (Tiers 1-4, ≥250 tests), creating `TEST_INFRA.md` and publishing `TEST_READY.md`. | none (parallel) | DONE |
| M6 | Full Functional Audit & Final Adversarial Verification | Execute full 5-role audit checklist across Worker, Employer, Government, Admin, Mock Aadhaar. Verify 100% baseline pass (394 Pytest, 48 Hardhat, 27 frontend invariants) + all new v0.5 test suites. Phase 2: Tier 5 adversarial challenge hardening. | M1, M2, M3, M4, M5, E2E | IN_PROGRESS (Iteration 4: Remediation) |

---

## Interface Contracts

### Worker ↔ Mock Aadhaar Status Revalidation
- `resolve_worker_aadhaar_status(db: Session, worker: DBWorkerProfile) -> Tuple[str, Optional[DBAadhaarRecord]]`:
  - If `worker.aadhaar_record_id` is None -> return `("UNVERIFIED", None)`
  - Query `db.query(DBAadhaarRecord).filter(DBAadhaarRecord.record_id == worker.aadhaar_record_id).first()`
  - If database / service is unavailable -> return `("UNAVAILABLE", None)`
  - If record status is `ACTIVE` -> return `("ACTIVE", record)`
  - If record status is `INACTIVE` -> return `("INACTIVE", record)`
  - If record status is `SUSPENDED` -> return `("SUSPENDED", record)`

### QR Verification Engine ↔ Government Officer Context
- In `verification_engine.py`:
  - When `verifier_role == "GOVERNMENT"`:
    - `caller_id` MUST be the UUID string of `DBGovernmentOfficer.id` (not EVM wallet address).
    - Query `db.query(DBGovernmentOfficer).filter(DBGovernmentOfficer.id == UUID(caller_id)).first()`.
    - If not found -> raise `VerificationError(code="OFFICER_NOT_FOUND")`.
    - If status not in `["ACTIVE", "APPROVED"]` -> raise `VerificationError(code="OFFICER_INACTIVE" | "OFFICER_SUSPENDED")`.
    - If officer lacks `WORKER_VERIFICATION` in permissions -> raise `VerificationError(code="FORBIDDEN_PERMISSION")`.
    - Replay context key: `(presentation_id, "GOVERNMENT", str(officer.id))`.

### Admin API ↔ Pagination & Directory Search
- Shared envelope for all directory queries:
  ```json
  {
    "total_count": 128,
    "page": 1,
    "page_size": 20,
    "total_pages": 7,
    "items": [...]
  }
  ```
- Standard query parameters:
  - `search: Optional[str] = None` (normalized case-insensitive partial match)
  - `status: Optional[str] = None`
  - `date_from: Optional[datetime] = None`
  - `date_to: Optional[datetime] = None`
  - `page: int = 1`
  - `page_size: int = 20`

### Activation Pipeline ↔ Token Delivery
- Hashed token generation: `token_hash = hashlib.sha256(raw_token.encode()).hexdigest()`
- Delivery status policy:
  - If SMTP unconfigured -> `status = "PENDING"`, `last_error = "SMTP transport unconfigured; simulated mode"`
  - If SMTP configured and transport accepts -> `status = "SENT"`
  - If SMTP raises exception -> `status = "FAILED"`, `last_error = str(exception)`
- Target Isolation:
  - `POST /api/v1/auth/activate-employer` and `/api/v1/employer/activate` require `entity_type == "EMPLOYER"`. Reject with HTTP 400 `WRONG_TARGET_TYPE`.
  - `POST /api/v1/government/activate` requires `entity_type == "GOVERNMENT"`. Reject with HTTP 400 `WRONG_TARGET_TYPE`.

---

## Code Layout
- `backend/app/models/db.py`: SQLAlchemy models (`DBWorkerProfile.aadhaar_record_id`, `DBActivationEmail`, etc.).
- `backend/app/db/migrate.py`: Database schema migrations and authoritative backfill reconciliation.
- `backend/app/core/config.py`: Environment configuration including `PUBLIC_APP_BASE_URL`.
- `backend/app/core/mailer.py`: SMTP mailer with truthful delivery reporting.
- `backend/app/services/verification_engine.py`: 11-step Common QR Verification Engine.
- `backend/app/api/endpoints/`:
  - `worker.py`: Live Aadhaar status revalidation, QR security checks.
  - `employer.py`: Employer registration, category requests, employment contracts.
  - `admin.py`: Organization review, category decisions, officer provisioning, directory search & pagination.
  - `government.py`: Government officer QR verification, benefit claims, activation redemption.
  - `auth.py`: Registration, login, `/me`, activation routing.
- `frontend/src/`:
  - `components/common/AuthModal.jsx`: Registration alignment, dedicated Gov activation tab.
  - `components/worker/WorkerPortal.jsx`: Dynamic Aadhaar status badges and QR gating.
  - `components/employer/EmployerPortal.jsx`: Employer registration and portal views.
  - `components/admin/AdminPortal.jsx`: 6 dedicated category views, search/filter controls, pagination, error alerts.
  - `components/government/GovernmentPortal.jsx`: Government QR verification and status handling.
