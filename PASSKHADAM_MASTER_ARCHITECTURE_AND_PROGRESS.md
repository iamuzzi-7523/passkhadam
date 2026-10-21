# PASSKHADAM: Master System Architecture & Project Progress Documentation

> **Platform Version:** v1.3 (Production-Oriented Decentralized Identity Platform)  
> **Last Updated:** October 2026  
> **Repository Root:** `e:\AI\projects\PassKhadam`  
> **Target Audience:** Developers, System Architects, Auditors, and Product Evaluators  

---

## 1. Executive Summary & Problem Space

### 1.1 The Problem
India's migrant workforce exceeds 100 million individuals who move across state borders for construction, infrastructure, manufacturing, and domestic labor. These workers face severe systemic barriers:
- **Centralized Database Vulnerabilities**: Dependence on centralized systems creates single-points-of-failure, data leakage risks, and surveillance vulnerabilities.
- **Lost Employment Records**: Workers lack portable, verifiable proof of their past employment, trade skills, and safety certifications when migrating between contractors and states.
- **Interstate Welfare Lockout**: State welfare schemes (e.g., BOCW – Building and Other Construction Workers Welfare Boards) are fragmented. Workers frequently lose access to benefits or face fraudulent claims across borders.
- **Privacy Invasion**: Sharing identity credentials often exposes raw Aadhaar numbers, leading to identity theft and biometric compromise.

### 1.2 The PassKhadam Solution
**PASSKHADAM** (*"Pass of the Worker"*) is a decentralized, privacy-preserving digital identity and credential verification ecosystem designed specifically for migrant workers.
- **Decentralized Identifiers (DIDs)**: Workers own sovereign identities formatted as `did:passkhadam:worker:{hash}`, completely independent of centralized state authorities.
- **W3C Verifiable Credentials (VCs)**: Skills, employment records, and safety certifications are cryptographically issued, Ed25519-signed, and AES-256-GCM encrypted.
- **Zero Raw PII On-Chain**: No name, date of birth, biometric, or 12-digit Aadhaar number is ever written to the blockchain. The blockchain stores only cryptographically salted hashes, IPFS Content Identifiers (CIDs), and revocation flags.
- **Web QR Upload (Zero Camera Scanning Required)**: Verifications work in browser environments via image upload, drag-and-drop, and automated OpenCV decoding.
- **Dual-Factor Verification Architecture (v1.3)**: Real email verification (Google Firebase official email links + FastAPI SMTP mailer) paired with phone verification (carrier SMS + gateway fallback).

---

## 2. High-Level Architecture & Component Stack

PassKhadam consists of 5 modular, tightly integrated layers:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LAYER 1: CLIENT FRONTEND                              │
│  React 18 + Vite • Tailwind CSS • Web3.js / MetaMask • Web Speech API           │
│  Portals: Worker • Employer • Government • Admin • UIDAI Mock Authority         │
└──────────────┬──────────────────────────┬─────────────────────────┬─────────────┘
               │                          │                         │
               ▼                          ▼                         ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌─────────────────────┐
│ LAYER 2: AUTHENTICATION   │ │  LAYER 3: BACKEND ENGINE  │ │  LAYER 4: STORAGE   │
│ • Google Firebase Web SDK │ │ • FastAPI (Python 3.11+)  │ │ • IPFS Provider     │
│ • Official Email Links    │ │ • Ed25519 Signature Envs  │ │   (Local CIDv0 /    │
│ • Phone reCAPTCHA & SMS   │ │ • AES-256-GCM Encryption  │ │   Pinata / Kubo)    │
│ • Authoritative RBAC /me  │ │ • 10-Step Verification    │ │ • SQLite Database   │
│ • SMTP Gateway Transport  │ │ • Mock Aadhaar Directory  │ │   (Relational Cache)│
└──────────────┬────────────┘ └─────────────┬─────────────┘ └─────────────────────┘
               │                            │
               └────────────────────────────┼─────────────────────────┐
                                            ▼                         ▼
                              ┌───────────────────────────────────────────────┐
                              │     LAYER 5: EVM SMART CONTRACTS (SOLIDITY)   │
                              │  Compiled with viaIR: true under Hardhat      │
                              │  • WorkerIdentityRegistry.sol                 │
                              │  • OrganizationRegistry.sol                   │
                              │  • EmploymentRegistry.sol                     │
                              │  • WelfareSchemeRegistry.sol                  │
                              │  • CredentialRegistry.sol                     │
                              └───────────────────────────────────────────────┘
```

### Technology Breakdown

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend Framework** | React + Vite | React 18.3, Vite 6.0 | Fast, modular Single Page Application |
| **Styling & Icons** | Tailwind CSS + Lucide React | v3.4, v1.16 | Responsive slate-dark theme with micro-interactions |
| **Client Auth** | Google Firebase SDK | v12.19 | Email/Password, Email Verification, Phone Auth |
| **Blockchain Client** | Web3.js / Ethers | Standard Web3 | MetaMask wallet connection & chain switching |
| **Backend Framework**| FastAPI + Uvicorn | FastAPI 0.110+ | High-performance asynchronous REST API |
| **Cryptography** | Cryptography (Python) | Standard | Ed25519 signing, AES-256-GCM authenticated cipher |
| **QR Processing** | OpenCV (`cv2`) + pyzbar | OpenCV Headless | Multi-engine QR detection from uploaded images |
| **Smart Contracts** | Solidity | 0.8.20 | EVM smart contracts deployed via Hardhat |
| **Blockchain Runtime**| Hardhat Local Node | EVM Chain ID 1337 | Local zero-gas deterministic test blockchain |
| **Storage Abstraction**| Custom IPFS Provider | CIDv0 Multihash | Encrypted credential payload storage & resolution |
| **Relational DB** | SQLite + SQLAlchemy | SQLAlchemy 2.0 | User profiles, audit logs, cached metadata |

---

## 3. How the System Components Are Linked

### 3.1 Frontend $\longleftrightarrow$ Authentication (Firebase + FastAPI)
1. **User Sign-In / Registration**: The user enters credentials in `AuthModal.jsx`.
2. **Firebase Credential Issuance**: The client invokes `signInWithEmailAndPassword` or `createUserWithEmailAndPassword`. Firebase returns an authenticated user object and an ID Token.
3. **Backend Authoritative Context**: The client sends the Bearer token to FastAPI (`GET /api/v1/auth/me`). The backend authoritatively resolves the user's role (`WORKER`, `EMPLOYER`, `GOVERNMENT`, `ADMIN`, `AADHAAR`), account status (`ACTIVE`, `PENDING_REVIEW`, `SUSPENDED`), and organization status before granting portal access.
4. **RoleGuard Enforcement**: `RoleGuard.jsx` protects every portal. If a user modifies their role in the browser's local state, `RoleGuard` checks the backend-verified context and denies unauthorized access.

### 3.2 Frontend $\longleftrightarrow$ Blockchain (Web3.js + MetaMask)
1. **Wallet Connection**: `Web3Context.jsx` detects `window.ethereum` (MetaMask) or provides a 1-click **Simulated Hardhat Wallet** (`0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65`) with pre-funded 100.00 ETH.
2. **Network Auto-Switching**: Supports switching between:
   - Hardhat Local EVM (Chain ID `1337` / `0x539`)
   - Polygon Amoy Testnet (Chain ID `80002` / `0x13882`)
   - Ethereum Sepolia Testnet (Chain ID `11155111` / `0xaa36a7`)

### 3.3 Backend $\longleftrightarrow$ Decentralized Storage (IPFS)
1. When a Verifiable Credential is created, FastAPI serializes the W3C credential JSON.
2. The credential is encrypted with **AES-256-GCM** using an ephemeral symmetric key.
3. The encrypted ciphertext is handed to the `IPFSProvider` (`backend/app/services/ipfs_service.py`), which generates a deterministic Base58 CIDv0 multihash (`Qm...`).
4. The CID is anchored on the blockchain inside `WorkerIdentityRegistry.sol`.

### 3.4 Backend $\longleftrightarrow$ Smart Contracts (`web3.py`)
1. FastAPI acts as the authorized relayer using `web3.py` connected to `http://127.0.0.1:8545`.
2. Calls the deployed contracts using compiled JSON ABIs in `contracts/artifacts/`.
3. Ensures strict atomicity: if an on-chain registration or claim fails, the backend transaction is rolled back.

---

## 4. The 5 User Portals & Interactive Workflows

### 4.1 Worker Portal (`WORKER`)
Designed for simplicity, accessibility, and migrant worker empowerment:
- **Masked Identity Visual**: Displays a simulated government identity card showing photo, name, date of birth, gender, and masked Aadhaar (`XXXX XXXX 4821`).
- **DID & Blockchain Badge**: Displays the worker's unique decentralized identifier (`did:passkhadam:worker:1f15aa...`) and IPFS CID.
- **Personal Credential Wallet**: Visual cards for:
  1. *Government Verified Identity Credential*
  2. *BOCW Safety & Hazardous Environment Certification*
  3. *Trade Skills Credential* (e.g. Mason, Welder, Electrician)
- **Live QR Presentation Generator**: Generates an encrypted Ed25519 presentation payload encoded into a QR code with an interactive 300-second expiration countdown and 1-click PNG download.
- **Multilingual Voice Narrator**: Reads out worker profile and credential status in 6 Indian languages (**English, Hindi, Kannada, Bengali, Marathi, Telugu**) using the Web Speech API.

### 4.2 Employer Portal (`EMPLOYER`)
Designed for construction contractors and corporate infrastructure employers:
- **Web QR Upload (Zero Camera Required)**: Employers upload or drag-and-drop the worker's presentation QR image file.
- **10-Step Verification Stepper**: Real-time progress bar rendering each of the 10 cryptographic verification stages.
- **Employment Offer Form**: Upon verification, allows dispatching verified employment offers specifying:
  - *Trade Category*: Mason, Carpenter, Electrician, Plumber, Welder, Scaffolder, etc.
  - *Skill Level*: `Skilled`, `Semi-Skilled`, `Unskilled`
  - *Nature of Employment*: `Contract`, `Permanent`, `Project-Based`
- **Workforce Management Table**: Tracks all hired workers, active contracts, and records dismissal/completion events directly to the append-only smart contract.

### 4.3 Government Portal (`GOVERNMENT`)
Designed for state welfare boards and labor welfare officers:
- **Interstate Migrant Detector**: Automatically compares the worker's origin state (e.g. Bihar, Karnataka) with the current employment state (e.g. Maharashtra). If different, activates the **"Interstate Migrant Worker"** classification.
- **Origin-State KYC Badge**: Verifies whether the worker's identity and BOCW registration were verified in their home state.
- **Welfare Scheme Eligibility Evaluator**: Evaluates eligibility for government schemes:
  - *BOCW Maternity Benefit Scheme*
  - *Interstate Travel & Housing Allowance*
  - *Accident Relief & Disability Assistance*
- **Dynamic 30-Day Cooldown Enforcement**: Prevents repeat claims within 30 days while generating deterministic SHA-256 Claim IDs (`0x...`) anchored on-chain.

### 4.4 Admin Governance Portal (`ADMIN`)
Designed for platform governance and compliance:
- **Employer Organization Review**: Inspects newly registered employers in `PENDING_REVIEW` status and allows approval.
- **Category Governance**: Restricts which job categories an employer is legally authorized to hire.
- **Secure Activation Token Generation**: Generates 256-bit secure activation links for approved employers.
- **Smart Contract Auditing**: Monitors live EVM contract addresses, DID registry volume, and transaction history.

### 4.5 Mock Aadhaar Authority Portal (`AADHAAR`)
Simulates the Unique Identification Authority of India (UIDAI) in a sandbox environment:
- **Demographic Directory**: Directory of pre-seeded demographic records with masked identifiers.
- **Live API Audit Log**: Shows real-time verification requests and response latency.
- **Interactive Sandbox**: Allows testing demographic verification without exposing cleartext PII to the blockchain or frontend.

---

## 5. The Canonical 10-Step Verification Engine

Every time an Employer or Government Officer verifies a worker's QR code, the system executes an immutable 10-step cryptographic pipeline:

```
[Uploaded QR Image]
        │
        ▼
1. Decode QR Image ───────────► OpenCV Multi-Detector (WeChat/Standard)
        │
        ▼
2. Check Expiration ──────────► Reject if timestamp > 300s
        │
        ▼
3. Verify Envelope Sig ───────► Ed25519 signature on presentation envelope
        │
        ▼
4. Resolve Worker DID ────────► Query WorkerIdentityRegistry.sol
        │
        ▼
5. Check Revocation Status ───► Verify DID status == ACTIVE (not REVOKED)
        │
        ▼
6. Retrieve IPFS Payload ─────► Fetch AES-256 encrypted VC by CID
        │
        ▼
7. Verify Integrity Hash ─────► Recompute SHA-256(payload) == on-chain hash
        │
        ▼
8. Decrypt Payload ───────────► AES-256-GCM symmetric decryption
        │
        ▼
9. Verify Issuer Signature ───► Validate Ed25519 signature of the issuing authority
        │
        ▼
10. Apply Role Filters & KYC ─► Check Interstate KYC & Scoped Category Permissions
        │
        ▼
[VERIFICATION SUCCESS: Authentic & Untampered]
```

### Detailed Step Description

1. **Decode QR Image**: Reads the image file using OpenCV's `QRCodeDetector` (with automated grayscale and contrast pre-processing fallbacks).
2. **Validate Expiration**: Checks if the presentation timestamp has exceeded its time-to-live (300 seconds), preventing presentation replay attacks.
3. **Verify Envelope Signature**: Verifies that the presentation was signed with the worker's private key using Ed25519.
4. **Resolve Worker DID On-Chain**: Queries `WorkerIdentityRegistry.sol` using the DID string (`did:passkhadam:worker:{hash}`).
5. **Check On-Chain Revocation**: Confirms that the worker identity has not been revoked or blacklisted.
6. **Fetch Encrypted Credential from IPFS**: Retrieves the encrypted JSON ciphertext associated with the on-chain CID.
7. **Verify Credential Integrity Hash**: Computes `SHA-256(ciphertext)` and asserts equality against the on-chain credential hash. If an attacker modifies even 1 bit on IPFS, this step immediately aborts verification.
8. **Decrypt AES-256-GCM Payload**: Decrypts the Verifiable Credential using the session key.
9. **Verify Issuer Signature**: Verifies the signature of the issuing authority (e.g. BOCW Board, State Skill Development Agency).
10. **Apply Scoped RBAC & Interstate KYC**: Applies role-based visibility filters (e.g., hiding biometric tokens from employers) and validates interstate KYC status.

---

## 6. Authentication Architecture (v1.0 $\rightarrow$ v1.3 Evolution)

### 6.1 Authentication Evolution History
- **v1.0 (Baseline)**: Local mock authentication with client-side role toggling.
- **v1.1 (Official Firebase Integration)**: Integrated Google Firebase project (`passkhadam-live`) across all 5 roles, combined with invisible reCAPTCHA and Firebase phone authentication.
- **v1.2 (Dual Verification Architecture)**: Mandated dual-factor verification (Email + Phone) with FastAPI RBAC synchronization before registration completion.
- **v1.3 (Real Email Delivery & SMTP Mailer)**:
  - **Live Firebase Verification Email**: Initiates Firebase user authentication and triggers Google's mail servers (`noreply@passkhadam-live.firebaseapp.com`) to deliver official verification email links to real inboxes.
  - **FastAPI SMTP Mailer**: Implemented `backend/app/core/mailer.py` supporting standard TLS (587) and SSL (465) transports to send real 6-digit OTP codes via email.
  - **Adversarial Hardening**: Added MIME injection protection, rate limiting (5 attempts / 60s cooldown), and React Error Boundary guards.
- **v1.4 (Firebase-FastAPI Auth Synchronization & Account Claiming)**:
  - **Direct Firebase ID Token Login**: When Firebase accepts user credentials, `AuthContext.jsx` immediately resolves authoritative context via `GET /api/v1/auth/me` with `Bearer ${idToken}`, eliminating false "Invalid email or password" rejections.
  - **Seamless Existing Account Registration**: If an account was previously created in Firebase Console, `register` automatically handles `auth/email-already-in-use` by signing in to capture verified `firebase_uid` and updating the database cleanly without "User with this email already exists" errors.
  - **Stale Record Cleanup & UID Decoupling**: Released stale cross-account UID mappings in `passkhadam.db` and decoupled token synchronization in `login_user`.

### 6.2 Pre-Configured Demo Accounts (All 5 Roles)

| Role | Email | Password | Pre-Seeded Status |
|---|---|---|---|
| **Worker** | `worker@passkhadam.org` | `passkhadam123` | Active, Dual Verified, BOCW Registered |
| **Employer** | `employer@apexinfra.com` | `passkhadam123` | Active, Approved Org, All Categories |
| **Government Officer** | `gov@maharashtra.gov.in`| `passkhadam123` | Active, Authorized Welfare Disburser |
| **Platform Admin** | `admin@passkhadam.org` | `passkhadam123` | Active, Full Governance Rights |
| **UIDAI Mock Authority** | `authority@uidai.gov.in`| `passkhadam123` | Active, Sandbox & Demographic Access |

---

## 7. Smart Contracts Architecture (Solidity `0.8.20`)

The contracts are compiled under Hardhat using `viaIR: true` for optimization:

### 7.1 Contract Inventory

```
contracts/contracts/
├── WorkerIdentityRegistry.sol   # Anchors worker DIDs, credential hashes, and CIDs
├── CredentialRegistry.sol       # Tracks Verifiable Credential issuance & revocation
├── OrganizationRegistry.sol     # Manages employer registration, approvals, and scopes
├── EmploymentRegistry.sol       # Records portable, append-only employment history
└── WelfareSchemeRegistry.sol    # Enforces 30-day cooldowns & deterministic claim IDs
```

### 7.2 Smart Contract Invariants
- **Sybil Resistance**: A worker identity cannot be registered twice by the same or different authorized issuers.
- **Tamper Prevention**: Once an identity is revoked, it cannot be overwritten or reactivated by unauthorized parties.
- **Scope Restriction**: Employers cannot hire workers in trade categories or skill levels they are not approved for.
- **Append-Only Employment History**: When a worker is marked `DISMISSED` or `COMPLETED`, the historical audit trail is preserved permanently in event logs.
- **Adversarial Cooldown Boundary**: Welfare claims enforce a strict 30-day cooldown period. A claim submitted at 29 days 23 hours 59 minutes 59 seconds is rejected.

---

## 8. Directory & File Structure Map

```
e:\AI\projects\PassKhadam\
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints/
│   │   │       ├── auth.py             # Auth endpoints (login, register, email/phone OTP)
│   │   │       ├── worker.py           # Worker profile, wallet, QR presentation
│   │   │       ├── employer.py         # Verification, offers, workforce management
│   │   │       ├── government.py       # Scheme evaluator, interstate migration
│   │   │       ├── admin.py            # Org approvals, category governance
│   │   │       └── aadhaar.py          # Mock UIDAI verification sandbox
│   │   ├── core/
│   │   │   ├── auth.py                 # RBAC, password hashing, user context builder
│   │   │   ├── config.py               # Settings, environment variables
│   │   │   ├── crypto.py               # Ed25519 signing & AES-256-GCM cipher
│   │   │   └── mailer.py               # SMTP transport (TLS/SSL) for real email OTPs
│   │   ├── models/
│   │   │   ├── db.py                   # SQLAlchemy database models (Users, Profiles, Claims)
│   │   │   └── schemas.py              # Pydantic request/response validation schemas
│   │   ├── services/
│   │   │   ├── verification_engine.py  # 10-step cryptographic verification pipeline
│   │   │   ├── ipfs_service.py         # IPFS multihash CID generation & storage
│   │   │   └── blockchain_service.py   # web3.py contract client interface
│   │   └── main.py                     # FastAPI application factory & CORS setup
│   ├── tests/
│   │   ├── test_auth_e2e_all_roles.py  # All-roles authentication & RBAC tests
│   │   ├── test_mailer.py              # Real SMTP mailer & fallback unit tests
│   │   ├── test_email_otp.py           # Email OTP generation & verification tests
│   │   ├── test_verification_engine.py # 10-step engine adversarial test suite
│   │   └── test_welfare_cooldown.py    # 30-day cooldown boundary tests
│   └── requirements.txt                # Python backend dependencies
│
├── contracts/
│   ├── contracts/                      # 5 Solidity smart contracts
│   ├── test/
│   │   └── passkhadam.test.js          # 33 Hardhat adversarial invariant unit tests
│   ├── hardhat.config.js               # Hardhat configuration (Solidity 0.8.20, viaIR)
│   └── package.json                    # Hardhat dependencies
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── aadhaar/                # Mock UIDAI authority dashboard
│   │   │   ├── admin/                  # Governance, employer approvals
│   │   │   ├── common/
│   │   │   │   ├── AuthModal.jsx       # Dual email & phone verification dialog
│   │   │   │   ├── ErrorBoundary.jsx   # React runtime error boundary guard
│   │   │   │   ├── Header.jsx          # Role switcher, MetaMask pill, lang selector
│   │   │   │   ├── RoleGuard.jsx       # Authoritative RBAC route protector
│   │   │   │   └── Web3WalletModal.jsx # MetaMask & simulated wallet connection
│   │   │   ├── employer/               # QR upload, 10-step stepper, offer dispatch
│   │   │   ├── government/             # Interstate migration detector, claims
│   │   │   └── worker/                 # Visual card, wallet, QR generator
│   │   ├── config/
│   │   │   └── firebase.js             # Singleton Firebase Auth client configuration
│   │   ├── context/
│   │   │   ├── AuthContext.jsx         # Global user state, login, OTP dispatch
│   │   │   └── Web3Context.jsx         # Web3 wallet connection, chain switching
│   │   ├── i18n/
│   │   │   └── translations.js         # Multilingual translations (6 Indian languages)
│   │   ├── utils/
│   │   │   └── speech.js               # Web Speech API narration integration
│   │   ├── App.jsx                     # Top-level portal routing & layout
│   │   └── main.jsx                    # React entry point with ErrorBoundary
│   ├── index.html                      # HTML entry with fallback script listener
│   ├── vite.config.js                  # Vite dev server with /api proxy to FastAPI
│   └── package.json                    # Frontend dependencies
│
├── start_dev.bat                       # 1-Click Windows batch launcher
├── start_dev.ps1                       # 1-Click PowerShell launcher
└── README.md                           # Quickstart guide
```

---

## 9. Current Verification & Test Metrics

Every requirement and invariant is validated through automated test suites:

### 9.1 Backend Pytest Suite: 150 / 150 Tests Passed (100%)
```bash
pytest backend/tests/ -q
======================= 150 passed, 25 warnings in 17.10s =======================
```
- **Coverage**:
  - Full authentication lifecycle for all 5 roles.
  - SMTP configuration parsing, TLS/SSL dispatch, and graceful fallback.
  - Rate-limiting (5-attempt thresholds and 60s cooldowns).
  - Firebase ID token authentication, auto-sync, and cross-account collision prevention (`test_firebase_sync.py`).
  - 10-step verification engine under adversarial attacks (tampered payloads, expired presentations, invalid signatures).
  - Dynamic 30-day welfare cooldown boundaries.

### 9.2 Smart Contracts Hardhat Suite: 33 / 33 Tests Passed (100%)
```bash
npx hardhat test
  33 passing (6s)
```
- **Coverage**:
  - Sybil identity registration prevention.
  - Revocation immutability.
  - Scoped category and employment level constraints.
  - Historical append-only log preservation upon worker dismissal.
  - Deterministic SHA-256 Claim ID tracking across states.

### 9.3 Frontend Production Compilation: Clean (0 Errors)
```bash
npm run build
✓ 1937 modules transformed.
dist/index.html                   1.68 kB │ gzip:   0.98 kB
dist/assets/index-hMfpc1jr.css   34.11 kB │ gzip:   6.36 kB
dist/assets/index-Uacd-YbQ.js   526.38 kB │ gzip: 126.40 kB
✓ built in 36.92s
```

---

## 10. How to Launch & Explore the Project

### 10.1 Automated Launchers (Windows)
To start both servers with a single command:
```powershell
# Double click or run in terminal:
.\start_dev.bat
# Or using PowerShell:
.\start_dev.ps1
```

### 10.2 Manual Commands
If you prefer running services in separate terminal windows:

**Terminal 1 — FastAPI Backend**:
```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*API Documentation will be live at `http://127.0.0.1:8000/docs`.*

**Terminal 2 — React Frontend (Vite)**:
```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
*Application interface will be live at `http://localhost:5173`.*

**Terminal 3 (Optional) — Hardhat Local Node**:
```powershell
cd contracts
npx hardhat node
```

---

## 11. Security & Privacy Guarantees

1. **Zero Cleartext PII on Public Ledgers**: Names, mobile numbers, and Aadhaar numbers are never passed to smart contracts. Only cryptographic hashes and multihash CIDs are anchored.
2. **Deterministic Cryptographic Binding**: A credential cannot be forged because the on-chain registry enforces `hash(credential) == anchored_hash`.
3. **Replay Protection**: Presentation QR codes expire strictly after 300 seconds and are signed with single-use presentation nonces.
4. **MIME & Injection Defenses**: The backend mailer incorporates `html.escape` sanitization and regex validation on all email headers.
5. **Brute-Force Rate Limiting**: OTP verification endpoints enforce a maximum of 5 attempts and a 60-second cooldown period per session.
6. **Graceful Error Recovery**: A global React `ErrorBoundary` and HTML fallback listener ensure unhandled runtime exceptions provide recovery buttons instead of unmounting into a blank screen.

---

*PassKhadam — Empowering India's Migrant Workforce through Privacy-First Decentralized Identity.*
