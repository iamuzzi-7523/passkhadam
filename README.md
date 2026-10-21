# PASSKHADAM — Portable Standalone Distribution

> **Decentralized Identity Verification Platform for Migrant Workers**  
> *Production-Oriented Architecture (v0.3 / v0.4 / v0.5 Baseline)*

This folder is the **lightweight, exportable distribution** of the PASSKHADAM platform (~6 MB instead of the full 700 MB development tree). It contains all source code, pre-compiled smart contract artifacts, test suites, and a clean seed database ready to be transferred to and run independently on any computer.

---

## 📦 What's Inside This Portable Package?

- **`backend/`**: Complete FastAPI verification engine, REST API endpoints, cryptographic services (AES-256-GCM, Ed25519, Keccak-256), IPFS multihash abstraction, and SQLite database models.
- **`frontend/`**: Complete React 18 + Vite + Tailwind CSS portals for all 5 roles (Worker, Employer, Government, Platform Admin, and Mock Aadhaar Authority) + pre-built `dist/` bundle.
- **`contracts/`**: Complete EVM Solidity 0.8.20 smart contracts (`WorkerIdentityRegistry`, `CredentialRegistry`, `OrganizationRegistry`, `EmploymentRegistry`, `WelfareSchemeRegistry`), Hardhat test suites, and deployment scripts.
- **`passkhadam.db`**: Pre-seeded SQLite database containing clean demo accounts for all 5 roles.
- **Launchers & Setup**: 1-click batch and shell scripts for Windows, Linux, and macOS.

*(The 650+ MB `node_modules` folders, bytecode caches, and temporary stress-test databases have been excluded for clean, fast portability across machines).*

---

## ⚡ Quick Start

### 1. Prerequisites
Before running, make sure your target system has:
- **Python 3.10+** (check with `python --version`)
- **Node.js 18+** & **npm** (check with `node --version` and `npm --version`)

---

### 2. One-Click Setup (First Time Only)

Run the setup script to install dependencies for both Python and Node.js:

- **Windows**:
  Double-click **`setup.bat`** (or open terminal and run `.\setup.bat`)

- **Linux / macOS**:
  ```bash
  chmod +x setup.sh start_dev.sh
  ./setup.sh
  ```

---

### 3. Launching PASSKHADAM

Start both the FastAPI backend and Vite frontend with a single command:

- **Windows**:
  Double-click **`start_dev.bat`** (or run `.\start_dev.ps1` in PowerShell)

- **Linux / macOS**:
  ```bash
  ./start_dev.sh
  ```

Once started:
- 🌐 **Web Application**: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- 📖 **Interactive API Docs (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🔑 Pre-Seeded Demonstration Accounts

All 5 core roles are pre-seeded in the database and ready for immediate login:

| Role | Email | Password | Description |
| :--- | :--- | :--- | :--- |
| **Worker** | `worker@passkhadam.org` | `passkhadam123` | View digital card, QR presentation, trade profile & stints |
| **Employer** | `employer@apexinfra.com` | `passkhadam123` | Apex Infrastructure Admin: QR upload, contracts & stints |
| **Government** | `gov@maharashtra.gov.in` | `passkhadam123` | Maharashtra Labour Welfare Officer: Cross-state KYC & claims |
| **Admin** | `admin@passkhadam.org` | `passkhadam123` | Platform Governance: Approve employers & category scopes |
| **Aadhaar** | `authority@uidai.gov.in` | `passkhadam123` | Mock UIDAI Gateway & sandbox audit logs |

---

## 🧪 Running Verification & Tests

To verify that all cryptographic invariants and platform logic are functioning properly:

### Backend Cryptographic & Invariant Tests
```bash
python -m pytest backend/tests/test_backend.py -v
```
*(Tests Aadhaar verification, AES-256-GCM vault encryption, Ed25519 signatures, QR tampering detection, credential replay prevention, and welfare claim cooldowns).*

### Smart Contract Hardhat Tests (Optional)
```bash
cd contracts
npx hardhat test
```
*(Runs unit tests against all 5 smart contracts in the local EVM environment).*

---

## 🛠 Manual Setup Commands (Alternative)

If you prefer installing dependencies manually step-by-step:

### 1. Backend
```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Smart Contracts (Optional)
```bash
cd contracts
npm install
```

---

## 📂 Exported Directory Structure

```
PassKhadam_Exportable/
├── backend/
│   ├── app/
│   │   ├── api/endpoints/         # 5 Role API routers (Worker, Employer, Gov, Admin, Aadhaar)
│   │   ├── blockchain/            # deployed_contracts.json (Contract ABIs & deterministic addresses)
│   │   ├── core/                  # AES-256-GCM, Ed25519, Keccak-256 crypto & settings
│   │   ├── db/                    # SQLite database migration tools
│   │   ├── models/                # SQLAlchemy models & Pydantic schemas
│   │   ├── services/              # 10-Step Verification Engine, QR, IPFS, Blockchain services
│   │   ├── storage/               # Seeded passkhadam.db & ipfs_blobs directory
│   │   └── main.py                # FastAPI application entrypoint & auto-seeder
│   ├── scripts/                   # Integration & seed scripts
│   ├── tests/                     # 100% passing Pytest regression test suite
│   ├── requirements.txt           # Python backend dependencies
│   └── .env                       # Backend configuration (SMTP, secret keys, IPFS)
│
├── frontend/
│   ├── src/                       # React 18 source (portals, components, contexts, hooks)
│   ├── dist/                      # Pre-built production bundle
│   ├── package.json               # Frontend dependencies (React, Vite, Lucide, Tailwind)
│   ├── vite.config.js             # Vite development server configuration
│   └── .env                       # Frontend environment configuration (Firebase, API URL)
│
├── contracts/
│   ├── contracts/                 # Solidity 0.8.20 smart contracts
│   ├── artifacts/                 # Precompiled Hardhat contract artifacts & ABIs
│   ├── scripts/                   # Deploy and artifact export scripts
│   ├── test/                      # Hardhat contract test suites
│   ├── hardhat.config.js          # Hardhat configuration (ChainID 1337)
│   └── package.json               # Hardhat dependencies
│
├── passkhadam.db                  # Clean standalone 155KB SQLite seed database
├── start_dev.bat                  # 1-Click Windows Dev Launcher
├── start_dev.ps1                  # PowerShell Dev Launcher
├── start_dev.sh                   # 1-Click Linux / macOS Dev Launcher
├── setup.bat                      # 1-Click Windows Dependency Installer
├── setup.sh                       # 1-Click Linux / macOS Dependency Installer
└── README.md                      # This Quickstart Guide
```
