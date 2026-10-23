# PassKadam: Decentralized Identity Verification & Benefit Portability for Migrant Workers

[![UN SDG 8](https://img.shields.io/badge/SDG%208-Decent%20Work%20%26%20Economic%20Growth-darkorange?style=flat-square)](https://sdgs.un.org/goals/goal8)
[![UN SDG 10](https://img.shields.io/badge/SDG%2010-Reduced%20Inequalities-crimson?style=flat-square)](https://sdgs.un.org/goals/goal10)
[![Release](https://img.shields.io/badge/Release-v0.5.0-blue?logo=github&style=flat-square)](https://github.com/iamuzzi-7523/passkhadam/releases)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.24-lightgrey?logo=solidity&style=flat-square)](https://soliditylang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688?logo=fastapi&style=flat-square)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&style=flat-square)](https://react.dev/)
[![IPFS](https://img.shields.io/badge/IPFS-Decentralized%20Storage-65C2CB?logo=ipfs&style=flat-square)](https://ipfs.tech/)

> **Final Year B.Tech Capstone Project**  
> A Self-Sovereign Identity (SSI) and Cross-State Welfare Portability Platform ensuring interstate migrant workers never lose access to their fundamental social security entitlements.

---

## 📌 1. Problem Statement & Motivation

In India, over **100+ million interstate migrant workers** move between states (e.g., from Bihar, Uttar Pradesh, Odisha, or West Bengal to destination states like Kerala, Maharashtra, Delhi, or Karnataka). Upon crossing state borders, they encounter severe administrative exclusion:

- **Siloed State Databases**: Welfare benefits (such as **PDS Ration Quotas**, **State BOCW Construction Funds**, and **Ayushman Emergency Health Services**) are bound to home state servers.
- **Verification Bottlenecks**: Destination state officers cannot verify cross-state entitlement cards without slow inter-state bureaucratic clearances.
- **Document Confiscation & Vulnerability**: Rogue contractors and intermediaries frequently confiscate physical identity documents, exposing workers to wage theft, unsafe working conditions, and exploitation.

### The PassKadam Solution
**PassKadam** decouples identity verification from centralized databases by implementing a **Decentralized Self-Sovereign Identity (SSI)** architecture:
1. Origin states and national authorities issue cryptographically signed **W3C Verifiable Credentials (VC)**.
2. Demographic details are encrypted using **AES-256** and pinned to **IPFS**—ensuring **0 bytes of cleartext PII touch the public blockchain**.
3. Cryptographic integrity hashes and revocation statuses are anchored on **Ethereum / Solidity Smart Contracts**.
4. Any destination state officer or employer can verify identity and disburse portable entitlements in **under 2 seconds** via a QR code presentation, with the smart contract automatically preventing double-spending and duplicate cross-state claims.

---

## 🎯 2. UN Sustainable Development Goals (SDG) Mapping

| SDG Target | United Nations Goal Description | PassKadam Technological Impact |
| :--- | :--- | :--- |
| **SDG 8 (Target 8.8)** | *Protect labour rights and promote safe and secure working environments for all workers, including migrant workers.* | **Zero-Document Exploitation**: Eliminates the practice of contractors withholding physical papers. Employers verify verified trade skills and safety ratings without holding physical Aadhaar/voter IDs. |
| **SDG 10 (Target 10.7)** | *Facilitate orderly, safe, regular and responsible migration and mobility of people.* | **One Nation Welfare Portability**: Guarantees equal and non-discriminatory access to food security, transit housing allowances, and emergency healthcare anywhere in India. |

---

## 🏗️ 3. System Architecture

```
                                 [ MIGRANT WORKER ]
                                         │
                   1. Enrolls via Mock Aadhaar KYC & OTP Verification
                                         ▼
                                 [ FASTAPI BACKEND ]
                    (EIP-712 Credential Signer & Cryptographic Engine)
                         │                                 │
   2. AES-256 Encrypt & Pin                   3. Anchor DID Hash & Integrity Hash
                         ▼                                 ▼
                 [ IPFS NETWORK ]                [ SOLIDITY SMART CONTRACTS ]
            (Encrypted Credential JSON)             (Identity & Welfare Registry)
                         │                                 │
                         └─────────────────┬───────────────┘
                                           │
                   4. Generates Portable QR Presentation (PassKadam)
                                           │
                  ┌────────────────────────┴────────────────────────┐
                  ▼                                                 ▼
     [ DESTINATION WELFARE OFFICER ]                      [ REGISTERED EMPLOYER ]
       - Scans QR Code                                      - Scans QR Code
       - Decrypts Off-Chain IPFS VC                         - Verifies Certified Trade Skills
       - On-Chain Eligibility Check                         - Confirms Safety Certifications
       - Disburses Portable Rations / Benefits              - Logs Verified Employment Stint
       - Prevents Duplicate Cross-State Claims              - Zero PII Document Confiscation
```

---

## 👥 4. Team Contribution Matrix (40% - 30% - 30%)

| Team Member | Role & Focus Area | Target Contribution | Module Responsibility |
| :--- | :--- | :---: | :--- |
| **Mohammed Uzair**<br>([@iamuzzi-7523](https://github.com/iamuzzi-7523)) | **Lead & Blockchain Architect** | **~40%** | Solidity smart contracts (`AccessManager.sol`, `WorkerIdentityRegistry.sol`, `WelfareSchemeRegistry.sol`), Hardhat test suites, EVM deployment scripts, anti-duplicate claim logic. |
| **Mohammed Adnan**<br>([@Mohammed-Adnan7](https://github.com/Mohammed-Adnan7)) | **Backend & Cryptography Engineer** | **~30%** | FastAPI backend, Mock Aadhaar KYC verification & OTP engine, AES-256 IPFS encryption pipeline, W3C Verifiable Credential ECDSA signing. |
| **Muhammed Muthahar K M**<br>([@MUTHAHAR2003](https://github.com/MUTHAHAR2003)) | **Frontend & UI/UX Developer** | **~30%** | React 19 + Vite frontend, Worker DID Digital Card, QR generator/scanner, State Welfare Officer portal, Employer zero-PII dashboard, SDG analytics. |

---

## 💻 5. Technology Stack Breakdown

- **Blockchain Layer**: Solidity `0.8.24`, Hardhat, OpenZeppelin Contracts v5.
- **Decentralized Storage**: IPFS (Content Addressing CID with AES-256-Fernet encryption).
- **Backend & Middleware**: Python 3.13, FastAPI, Web3.py, `eth-account` (EIP-712 / ECDSA), Pytest.
- **Frontend Application**: React 19, Vite, Tailwind CSS, Lucide React, `qrcode.react`, Ethers.js.
- **Mock KYC**: UIDAI Aadhaar verification & OTP simulation with pre-seeded migrant demographics.

---

## 🚀 6. Quick Start & Execution Guide

### Prerequisites
- **Node.js**: v18+ (tested on v22.19.0)
- **Python**: 3.10+ (tested on 3.13.11)
- **Git**

### Step 1: Clone Repository
```bash
git clone https://github.com/iamuzzi-7523/passkhadam.git
cd passkhadam
```

### Step 2: Compile & Test Smart Contracts
```bash
cd contracts
npm install
npx hardhat compile
npx hardhat test
```
*All 48 unit tests verify access control, worker anchoring, revocation, and anti-duplicate cooldowns.*

### Step 3: Start FastAPI Backend
Open a new terminal:
```bash
cd backend
pip install -r requirements.txt
# Run automated backend tests
python -m pytest tests/test_backend.py -v
# Launch FastAPI server (port 8000)
python -m uvicorn app.main:app --reload --port 8000
```
*API interactive documentation available at `http://localhost:8000/docs`.*

### Step 4: Start React Frontend
Open a new terminal:
```bash
cd frontend
npm install
npm run dev
```
*Open `http://localhost:5173` in your browser.*

---

## 🧪 7. Demonstration Walkthrough (Viva Voce Flow)

1. **Worker Onboarding**:
   - Open the **Worker Wallet** tab.
   - Select demo worker *Rameshwar Kumar* (Bihar) or enter custom 12-digit Aadhaar.
   - Click **Request Mock Aadhaar OTP** (test OTP `752310` auto-fills).
   - Click **Verify & Anchor Credential**.
   - The system generates an **ECDSA-signed W3C Verifiable Credential**, encrypts it on **IPFS**, and anchors the DID hash on the **Ethereum blockchain**.
   - The **PassKadam Digital Worker Card** appears with photo, QR code, and portable entitlements.

2. **Cross-State Inspection & Disbursement**:
   - Click **Simulate Inspection in Destination State (Officer View)**.
   - Switch destination state to **Kerala**.
   - Click **Verify Worker Credential**.
   - Verification confirms: *Cryptographic Proof Verified & Active on Blockchain*.
   - In the **Benefit Portability** panel, select *One Nation One Ration Card (PDS)* and click **Disburse Benefit in Kerala**.
   - Transaction is confirmed with on-chain Claim ID!
   - *Duplicate Claim Test*: Click **Disburse Benefit** again. The smart contract immediately blocks the claim with an alert: *"Duplicate claim prevented! Cooldown active"*.

3. **Employer Zero-Document Verification**:
   - Switch to the **Employer Portal** tab.
   - Paste the worker's QR payload and click **Verify Worker Credentials**.
   - View verified trade skills and safety ratings with **zero raw Aadhaar or physical documents retained**.
   - Log an active employment engagement.

4. **SDG Impact Dashboard**:
   - Switch to **SDG 8 & 10 Impact** to present live metrics and answer external viva examination questions.

---

## ⚖️ 8. Security & Privacy Guarantees

- **No Cleartext PII on Blockchain**: Complies with the Indian **Digital Personal Data Protection (DPDP) Act 2023** and **GDPR**.
- **Cryptographic Non-Repudiation**: Credential subjects are signed using `secp256k1` ECDSA keys belonging to authorized state labour departments.
- **Anti-Double Dipping**: Smart contract cooldown algorithms prevent dishonest multi-state benefit redemption without centralized cross-state sync.

---

## 📦 9. Releases & Desktop Distribution

PassKadam provides both cloud-deployed web portals and zero-dependency portable desktop executables built with Electron:

| Release Version | Status | Primary Focus & Highlights | Download / Notes |
| :--- | :---: | :--- | :--- |
| **v0.5.0** | **Latest** | **Credential Issuance & Governance Reliability Patch**: Fixes employer trade credential issue loading loop, resolves government credential issuance "Failed to fetch" (eliminates route typing AttributeError and preserves CORS headers), enables active category scope suspension via CORS PATCH/POST, and upgrades government officer suspension to an Electron-compatible modal dialog. | [v0.5.0 Notes](releases/v0.5.0.md) |
| **v0.4.0** | **Preserved** | **Cloud Staging & Verifiable Credential Architecture**: Deployed live FastAPI backend on Render (`https://passkhadam-api.onrender.com`), persistent Supabase PostgreSQL database, Sepolia testnet contracts, multi-trade worker onboarding, and standalone desktop executable. | [v0.4.0 Release](https://github.com/iamuzzi-7523/passkhadam/releases/tag/v0.4.0) • [v0.4.0 Notes](releases/v0.4.0.md) |
| **v0.3.0** | Archived | **Portable Desktop Distribution**: Standalone Windows x64 portable executable with custom protocol handler (`app://passkhadam.app`). | [v0.3.0 Release](https://github.com/iamuzzi-7523/passkhadam/releases/tag/v0.3.0) |

---

## 📜 10. License

This project is licensed under the MIT License.
