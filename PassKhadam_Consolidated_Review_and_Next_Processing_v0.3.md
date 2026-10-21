# PASSKHADAM — Consolidated Review Findings & Next-Processing Instructions
## Version 0.3 — Documentation and Architecture Reconciliation

---

## 0. Purpose

This document consolidates the review of the current PassKhadam product specification and the following uploaded artifacts:

1. `prompt_draft.md` — Teamwork Project Prompt
2. `implementation_plan.md` — Implementation Plan
3. `walkthrough.md` — Implementation / Verification Walkthrough
4. `README.pdf` — Product / Setup README

The purpose of this document is to provide the **next processing step with one clear set of corrections, reconciliations, missing requirements, technical clarifications, and implementation priorities**.

This is a product architecture and documentation reconciliation document.

It is **not** a new feature wishlist. It exists to ensure that the existing product objective, implementation plan, execution prompt, walkthrough, and README all describe the same system.

---

# 1. Product Objective — Canonical Interpretation

PassKhadam is a **fully web-based decentralized identity platform for migrant workers**.

The core objective is:

> A worker should be able to establish one trusted, portable and privacy-conscious digital identity and use that identity across authorized employers, states and government services without having to recreate the identity whenever the worker moves.

The product combines:

- Government-backed identity verification through an Aadhaar API / Mock Aadhaar Authority
- Decentralized Identifiers (DIDs)
- W3C Verifiable Credentials
- Cryptographic signatures
- Encrypted credential storage
- IPFS / IPFS-compatible storage
- EVM blockchain anchoring
- Role-based access control
- Employer verification and employment lifecycle
- Cross-state government verification
- Welfare eligibility and benefit disbursement
- Auditability

The product has five roles:

1. User / Worker
2. Platform Admin
3. Government Authority
4. Employer
5. Aadhaar API Management / Identity Authority

---

# 2. Core Product Principle

The product should revolve around:

```text
VERIFY YOUR IDENTITY
        ↓
OWN / RECEIVE YOUR CREDENTIALS
        ↓
SHARE WHEN NEEDED
        ↓
GET VERIFIED ANYWHERE
        ↓
GET EMPLOYED
        ↓
BUILD PORTABLE EMPLOYMENT HISTORY
        ↓
ACCESS ELIGIBLE BENEFITS
```

Blockchain, IPFS, DID, cryptographic signatures and backend processing are implementation mechanisms supporting this experience.

They are not the product's primary user-facing purpose.

---

# 3. Critical Reconciliation Findings

The current documents are substantially aligned, but the following areas require correction before the architecture is treated as implementation-ready.

## Priority 1 — Normalize Blockchain Client Architecture

Current documentation contains references to:

- Web3.js
- ethers.js
- Web3.py

The product's minimum technology requirement explicitly includes **Web3.js**.

The implementation plan currently states:

> Hardhat with ethers.js/web3 integration.

It also defines `blockchain_service.py` as a **Web3.py** wrapper.

### Required clarification

Use a clear client responsibility model.

Recommended:

```text
React Frontend
        ↓
Web3.js
        ↓
EVM / Hardhat
```

and, where backend blockchain access is actually required:

```text
FastAPI
        ↓
Web3.py
        ↓
EVM / Hardhat
```

In this model:

- **Web3.js** = frontend EVM interaction
- **Web3.py** = backend blockchain interaction
- **Hardhat** = local EVM runtime and smart-contract test environment

`ethers.js` should not remain in the architecture merely as an unexplained third blockchain client.

If ethers.js is genuinely selected instead, explicitly replace Web3.js as the frontend blockchain client and update the product's technology baseline. Do not leave the three libraries ambiguously mixed.

---

# 4. Critical Reconciliation — Production vs Development Language

The current implementation plan says:

> “Build the complete, production-ready PASSKHADAM web platform.”

The walkthrough says:

> “We have built and fully verified PASSKHADAM.”

At the same time, the actual architecture is based on:

- Local Hardhat
- Mock Aadhaar Authority
- Embedded / local IPFS-compatible storage
- Development-oriented authentication flexibility
- Pre-seeded demo data

### Required wording change

Do not claim the current system is literally production-deployed.

Use:

> **Feature-complete product implementation for controlled development and demonstration, with production-oriented architecture and configurable external infrastructure.**

or:

> **Production-oriented architecture with a local development runtime and replaceable external service providers.**

This is more accurate without weakening the product.

---

# 5. Critical Reconciliation — Centralized Database Claim

Current wording says the platform:

> eliminates centralized database dependency.

That does not match the architecture because the product explicitly contains:

```text
SQLite / PostgreSQL
Mock Aadhaar Database
FastAPI operational services
```

### Required wording

Replace:

> “eliminates centralized database dependency”

with:

> **“reduces dependence on a single centralized identity database by combining DIDs, Verifiable Credentials, decentralized/IPFS storage, and blockchain-anchored integrity and status records.”**

Important distinction:

```text
Application DB
→ application / operational data

IPFS / IPFS-compatible storage
→ encrypted credential objects

Blockchain
→ trust, integrity, status, authorization and audit references
```

---

# 6. Critical Reconciliation — Authentication

The intended product workflow requires:

```text
Email verification
+
Phone OTP verification
```

Firebase Authentication is the preferred baseline.

The current implementation plan introduces a mock/dev authentication mode.

### Required architecture

```text
Production / normal product path:
Firebase Authentication

Development-only convenience:
Mock authentication adapter
```

The mock mode must never silently replace the actual product authentication path.

The product specification should clearly say:

> Firebase Authentication is the baseline authentication system; mock authentication is a development-only adapter.

---

# 7. Critical Reconciliation — Role Switcher vs Real RBAC

The implementation plan includes a:

> Universal Role Switcher Bar allowing instant switching between all 5 roles.

That is acceptable for developer/demo tooling but **must not be the actual security model**.

### Required security model

```text
Authenticated Identity
        ↓
Assigned Role(s)
        ↓
Role-Based Access Control
        ↓
Authorized Portal / Actions
```

A user must not be able to escalate:

```text
Employer → Government
Employer → Admin
Worker → Employer
Worker → Government
```

merely through a frontend role switcher.

### Required distinction

```text
DEV / DEMO ROLE SIMULATOR
≠
Production authorization mechanism
```

If a role switcher exists for testing, it must still respect simulated server-side authorization rules.

---

# 8. Worker Identity Flow — Remove Incorrect “Identity Approval” Step

The original product concept does not require an admin to manually approve each worker's identity.

The current lifecycle contains:

```text
Aadhaar Verification
        ↓
Identity Approval
        ↓
DID Generation
```

### Correct baseline

```text
Aadhaar Verification
        ↓
Identity Verification Result
        ↓
Worker Identity Binding
        ↓
DID Generation
```

The term **Identity Approval** should be removed unless a genuine future governance rule introduces such a step.

---

# 9. Worker Authentication and Identity Binding

The product should keep two verification domains distinct:

```text
Firebase
 ├── Email verified
 └── Phone verified

Mock Aadhaar API / Identity Authority
 ├── Aadhaar number verified
 └── Name verified
```

PassKhadam then binds the results to the authenticated account:

```text
Verified PassKhadam Account
        +
Successful Government Identity Verification
        ↓
Worker Identity Binding
        ↓
DID
        ↓
Identity Credential
```

The Aadhaar authority does not need to verify the worker's email or phone unless that authority explicitly provides such a capability.

---

# 10. Missing Requirement — Verified Aadhaar Card Visual

The intended worker experience includes a **verified Aadhaar / government-document visual** in the user portal after successful verification.

The current walkthrough and implementation documentation primarily demonstrate verification status, not the actual visual document representation.

### Required worker UI

```text
VERIFIED GOVERNMENT DOCUMENT

┌──────────────────────────────────────┐
│             Aadhaar                  │
│                                      │
│ Name: [verified display name]        │
│                                      │
│ Aadhaar: XXXX XXXX 4821              │
│                                      │
│ Status: ✓ VERIFIED                   │
│ Status: ✓ VALID                      │
└──────────────────────────────────────┘
```

The UI must clearly label a simulated/mock representation as such if it is not an official government-issued visual document.

Do not expose the full Aadhaar number unnecessarily.

---

# 11. Missing Requirement — Employer Onboarding Email Activation

The original product workflow includes:

```text
Employer Registration
        ↓
Admin Review
        ↓
Approval
        ↓
Credentials / activation information sent by email
        ↓
Employer activates account
```

The current implementation documentation does not make this sufficiently explicit.

### Required implementation behavior

Use:

```text
Admin Approval
        ↓
Organization Identity Created
        ↓
Permissions Assigned
        ↓
Secure Activation Link Sent to Registered Email
        ↓
Employer Sets / Activates Authentication
        ↓
Employer Account Activated
```

Do not send plaintext passwords by email if a secure activation link is available.

The same governance concept should apply to government organization/officer onboarding where appropriate.

---

# 12. Missing Employer Registration Fields

Employer registration must capture more than organization name and job category.

Required conceptual information includes:

```text
Company / Organization Name
Registration Number
Business Address
Contact Person
Official Email
Phone
Business Type
Nature of Business
Requested Employment Categories
Requested Employment Levels
Nature of Requested Employment
Expected Workforce
Supporting Organization Documents
```

---

# 13. Missing Employment-Level and Nature-of-Employment Controls

The product originally requires the employer to specify:

- What kind of employment
- Employment levels
- Nature of employment

These concepts should be first-class fields, not informal notes.

Example:

```text
Employment Category:
Mason

Employment Level:
Skilled

Nature of Employment:
Construction / Contract

Work Context:
Construction Site
```

Possible configurable employment levels:

```text
Skilled
Semi-Skilled
Unskilled
Supervisory
Other
```

Possible configurable nature-of-employment values:

```text
Permanent
Contract
Temporary
Seasonal
Project-Based
Other
```

These are configurable taxonomies, not immutable global values.

---

# 14. Employer Authorization Must Cover More Than Category

Current implementation primarily enforces authorized employment categories.

The broader product requirement should support authorization of:

```text
Employment Category
Employment Level
Nature of Employment
```

Baseline authorization flow:

```text
Employer Authorized?
        ↓
Category Authorized?
        ↓
Level Authorized?
        ↓
Nature Authorized?
        ↓
Worker Credential Valid?
        ↓
Create Employment Record
```

This must be enforced server-side.

---

# 15. Employer Additional Category Request

Required workflow:

```text
Employer
   ↓
Request Additional Employment Category
   ↓
Admin Review
   ↓
Approve / Reject / Request More Information
   ↓
Employer Permissions Updated
```

Until approval:

```text
Requested Category
        ↓
NOT AUTHORIZED
```

The employer must not bypass this restriction through frontend manipulation or direct API calls.

---

# 16. Missing BOCW Requirement

The original employer verification concept explicitly includes:

> BOCW safety certification & skill category.

The current implementation uses more generic wording such as skills and safety induction.

If BOCW is part of the PassKhadam credential model, it must explicitly appear in:

- Worker credential wallet
- Employer verification flow
- Government verification flow where relevant
- Seed data
- Verification tests
- Role-based display rules
- Credential status model

Example:

```text
BOCW Safety Certification
Status: VALID
```

---

# 17. Employer Verification — Canonical 9-Step Model

The walkthrough currently demonstrates this sequence:

```text
1. QR image decoded
2. Presentation expiration checked
3. Presentation Ed25519 signature verified
4. DID resolved on-chain
5. Revocation / good standing checked
6. Encrypted credential retrieved from IPFS
7. Credential decrypted
8. Credential signature verified
9. RBAC filtering applied
```

This is a useful concrete baseline.

However, because the product anchors a credential integrity hash on-chain, an explicit **integrity-hash verification** operation must also exist.

### Recommended logical verification sequence

```text
1. Decode uploaded QR presentation
2. Validate presentation expiration
3. Verify presentation envelope signature
4. Resolve worker DID
5. Check DID / credential status and revocation
6. Resolve IPFS credential CID
7. Retrieve encrypted credential
8. Decrypt credential
9. Verify issuer credential signature / proof
10. Recompute credential integrity hash
11. Compare against on-chain integrity hash
12. Apply organization and role permissions
13. Return authorized verification result
```

The exact number of UI steps can be 9, 10, 12, etc.; the critical requirement is that integrity verification genuinely occurs.

---

# 18. Critical Security Test — Credential Tampering

The system should explicitly test:

```text
Original Credential
        ↓
Hash stored on blockchain
```

Then simulate:

```text
Credential altered
        ↓
Credential retrieved
        ↓
Hash recomputed
        ↓
Blockchain hash comparison
        ↓
MISMATCH
        ↓
VERIFICATION FAILED
```

This should become a dedicated automated test.

---

# 19. Cryptographic Model Must Be Explicitly Unified

Current artifacts contain:

- Ed25519
- ECDSA
- secp256k1
- EIP-712
- AES-256-GCM
- SHA-256
- Keccak-256

These can coexist, but the documentation must state what each is responsible for.

### Recommended responsibility map

```text
QR / Presentation Envelope
→ Ed25519 signature

Verifiable Credential proof / issuer signing
→ ECDSA secp256k1 or the selected interoperable VC proof mechanism

Typed structured application / blockchain signing
→ EIP-712 where applicable

Credential encryption
→ AES-256-GCM

Credential integrity hash
→ SHA-256

Ethereum / EVM-specific hashing
→ Keccak-256 where required by the implementation
```

Do not use these algorithms interchangeably.

---

# 20. EIP-712 Clarification

EIP-712 is a typed structured-data hashing/signing mechanism.

It should not be described as though it is the entire Verifiable Credential format.

Recommended conceptual flow:

```text
Create VC
        ↓
Create implementation-defined signing representation
        ↓
Create typed signing payload
        ↓
EIP-712 / secp256k1 signature where applicable
        ↓
Attach proof / signature information
```

The final VC proof format remains an implementation choice.

---

# 21. Encryption Clarification

Do not use the phrase:

```text
AES-256 Fernet
```

These are different constructions.

Current implementation evidence uses **AES-256-GCM**, which is internally consistent.

Therefore keep:

```text
AES-256-GCM
```

for the current implementation, or explicitly switch to standard Fernet if Fernet is desired.

Do not combine the labels.

---

# 22. IPFS Architecture Clarification

The current implementation describes a local IPFS-compatible service with real content-addressed CIDs.

Important distinction:

```text
Actual IPFS network/node
        ≠
Local filesystem + CID generator
```

The current development system should therefore be described as:

> **Local IPFS-compatible development provider with real cryptographic CID generation, switchable to Kubo / Pinata / another IPFS provider through configuration.**

When an actual Kubo node or Pinata provider is enabled:

```text
Encrypted Credential
        ↓
Actual IPFS Provider
        ↓
CID
```

For local development:

```text
Encrypted Credential
        ↓
Local IPFS-compatible provider
        ↓
Real CID
```

The application should expose a provider abstraction.

Example:

```env
IPFS_PROVIDER=local
```

Later:

```env
IPFS_PROVIDER=pinata
```

or:

```env
IPFS_PROVIDER=kubo
```

---

# 23. QR Presentation Architecture

The product is fully web-based.

There is **no camera scanning requirement**.

Worker:

```text
Generate Identity Presentation
        ↓
Generate QR
        ↓
Download QR PNG
```

Employer / Government:

```text
Upload QR Image
        ↓
Decode QR
        ↓
Verify Presentation
```

Recommended upload UX:

```text
[ Drag & Drop QR Image Here ]

or

[ Choose QR Image ]

[ Verify Identity ]
```

Potentially supported image types can include:

```text
PNG
JPG / JPEG
WEBP
```

if supported by the selected QR decoder.

---

# 24. QR Presentation Expiration

Current implementation uses:

```text
300 seconds = 5 minutes
```

This is a reasonable baseline.

The system should:

- include an expiry timestamp
- reject expired presentations
- avoid relying on stale screenshots
- eventually support nonce/challenge binding if stronger anti-replay protection is needed

A future implementation can use:

```text
Presentation
+
Nonce / Challenge
+
Audience / verifier binding
+
Expiry
```

---

# 25. Zero-PII Verification

The employer verification flow should support minimum necessary disclosure.

Example:

Employer asks:

> Is the worker a certified Mason?

Preferred response:

```text
Skill:
Mason ✓

Certification:
VALID ✓
```

rather than exposing:

```text
Full Aadhaar
Full address
Personal phone
Personal email
```

The phrase **Zero-PII verification** should be used only when the implemented presentation truly avoids unnecessary PII disclosure.

---

# 26. Employer Removal / Dismissal Workflow

The product requires the employer to be able to remove a worker from its active workforce and record an outcome.

Required workflow:

```text
Employer
   ↓
Select Active Worker
   ↓
End Employment / Remove From Active Workers
   ↓
Select Outcome
   ├── Completed
   ├── Terminated
   ├── Dismissed
   ├── Resigned
   └── Suspended
   ↓
Record Employment Event
   ↓
Remove From Active Worker List
   ↓
Preserve Historical Employment Record
```

Important rule:

> Removing a worker from the employer's active roster must never delete the worker's historical employment record.

---

# 27. Employment Lifecycle Should Be Event-Based

The term "immutable lifecycle" is good, but the implementation should preferably maintain an append-only history.

Example:

```text
Employment Created
        ↓
Employment Started
        ↓
Employment Suspended
        ↓
Employment Resumed
        ↓
Employment Completed / Terminated / Dismissed
```

The current status can be derived from the latest valid event.

This is stronger than merely mutating:

```text
employment.status
```

without preserving the event history.

---

# 28. Employment Logging — Required Information

Employment records should conceptually preserve:

```text
Worker DID
Employer DID / Organization Identity
Employment Category
Employment Level
Nature of Employment
Employment Type
Work Location
Construction / Work Site
Start Date
End Date
Status
Issue Timestamp
Issuer / Signer
Record Hash / Reference
```

Not all fields must be stored directly on-chain.

A privacy-preserving architecture can use:

```text
Detailed employment record
→ encrypted / controlled storage

Employment hash + reference + status
→ blockchain
```

---

# 29. Employment Logging — Corrected Processing Sequence

Recommended baseline:

```text
📝 Preparing verifiable employment stint record...
🏢 Attaching employer DID / organization identity...
🏗️ Attaching construction site and work-site metadata...
👷 Assigning authorized employment category and level...
📋 Validating employer permissions...
🔐 Signing employment record using authorized employer blockchain identity / wallet...
⛓️ Anchoring employment record / hash...
📦 Updating worker's portable employment history...
✅ Employment stint anchored successfully.
```

If EIP-712 is actually used for the signing payload, display that accurately.

---

# 30. Government Verification — Origin-State KYC

The original concept includes cross-referencing an **origin-state KYC registry**.

The current documents should explicitly define this.

Baseline:

```text
Origin-State KYC Registry
        ↓
SQLite-backed operational registry
```

This registry should provide only the authorized information needed for cross-state verification.

It can later be migrated to another database technology.

---

# 31. Government Verification — Canonical Flow

Recommended current flow:

```text
🔍 Decoding uploaded QR cryptographic presentation payload...
📂 Resolving DID Document from did:passkadam registry...
⛓️ Querying WorkerIdentityRegistry.sol on EVM ledger...
📌 Resolving encrypted IPFS CID...
🔓 Processing encrypted Verifiable Credential payload...
🔐 Verifying issuer signature / configured proof...
📋 Checking credential validity and revocation status...
🧾 Recomputing and validating credential integrity hash...
🌐 Cross-referencing authorized origin-state KYC registry...
✅ Identity cryptographically verified.
✅ Signature valid.
✅ DID / identity reference confirmed on-chain.
```

The exact UI number of displayed steps can differ from the logical backend sequence.

---

# 32. Government Verification Output

Example:

```text
WORKER IDENTITY

Identity:
✓ VERIFIED

DID:
did:passkhadam:worker:8f29...

Origin State:
Karnataka

Current State:
Maharashtra

Identity Credential:
VALID ✓

Relevant Worker Credentials:
VALID ✓
```

Only authorized information should be shown.

---

# 33. Government Benefit Eligibility

The eligibility engine should evaluate configurable rules such as:

```text
Identity validity
Worker category
Relevant skill / certification
Employment status
Origin state
Current state
Scheme rules
Previous claims
Cross-state claim history
Claim cooldown
Other configured conditions
```

The product should not assume that every eligibility rule must be hardcoded into Solidity.

---

# 34. Welfare Architecture — Recommended Responsibility Split

A better long-term architecture is:

```text
Government Eligibility Engine
        ↓
Evaluate configurable / private attributes
        ↓
Generate eligibility result + rule / scheme version reference
        ↓
Blockchain
        ↓
Record claim + integrity reference
        ↓
Enforce critical anti-duplicate / cooldown invariants
```

Complex eligibility calculations can remain off-chain where necessary.

Blockchain should be responsible for the trust-critical state and invariants rather than becoming a giant rules engine.

---

# 35. Cross-State Benefit Claim Rules

The intended baseline includes a:

```text
30-day cooldown
```

for applicable cross-state claims.

The current walkthrough contains:

```text
Cooldown active for 31 more days
```

which is inconsistent with a 30-day policy.

### Required correction

Use:

```text
Default cooldown:
30 days
```

and calculate remaining time dynamically from timestamps.

Example:

```text
remaining = cooldown_expiry_timestamp - current_timestamp
```

Do not hardcode a displayed remaining duration.

The 30-day period should be configurable per scheme.

---

# 36. Cross-State Duplicate Claim Prevention

The product should check equivalent/conflicting claims across authorized state registries.

Conceptual flow:

```text
Current-State Claim
        ↓
Worker Identity
        ↓
Current Claim
        ↓
Existing Claim Search
        ├── Origin State
        ├── Current State
        └── Other Authorized State Registries
        ↓
Duplicate / Conflict Check
```

A duplicate or conflicting claim should be rejected or routed for review according to scheme rules.

---

# 37. Claim Identifier

The original design includes a unique **SHA-256-based Claim ID**.

The implementation should preserve that explicitly where SHA-256 is the selected mechanism.

Example:

```text
Claim Data
        ↓
Canonical representation
        ↓
SHA-256
        ↓
Claim ID
```

Do not replace this with a completely opaque random identifier if the product still intends the Claim ID to be cryptographically derived.

---

# 38. Government Wallet Authorization

The system should not treat government portal login as sufficient blockchain authority.

Recommended model:

```text
Government Organization
        ↓
Authorized Officer
        ↓
Officer Permission
        ↓
Registered Blockchain Identity / Wallet
        ↓
Signed Blockchain Transaction
```

The transaction must be associated with the authorized organization/officer identity.

The exact wallet custody model can be improved later.

---

# 39. Government Benefit Disbursement Processing Sequence

Recommended:

```text
🔍 Checking WelfareSchemeRegistry.sol cooldown status...
⏱️ Validating cross-state claim cooldown period (30-day policy)...
🛡️ Confirming no duplicate or conflicting claim in any other authorized state registry...
📋 Validating worker eligibility and scheme conditions...
📝 Generating unique SHA-256-based Claim ID...
⛓️ Writing benefit disbursement record to blockchain ledger...
🔒 Signing transaction with authorized government officer / authority wallet...
✅ Benefit disbursed! Claim record immutably anchored on-chain.
```

The word “disbursed” should only be used when the product really records the relevant disbursement action. Otherwise use “claim recorded”.

---

# 40. Credential Revocation Authority

Revocation must be scoped by credential ownership.

Example:

```text
Identity Credential
→ Authorized identity issuer

Skill Credential
→ Authorized skill / certification issuer

Employment Record
→ Issuing employer for its own employment record

Government Benefit Record
→ Authorized government authority
```

Do not allow arbitrary role holders to revoke every type of credential.

Examples:

```text
Employer cannot revoke a government identity credential.

Employer A cannot rewrite Employer B's employment record.

Worker cannot fabricate a government credential.

Government cannot arbitrarily rewrite another authority's credential.
```

---

# 41. Smart Contract Responsibilities

## WorkerIdentityRegistry.sol

Responsible for:

```text
DID Registration
DID References
Credential Hash References
IPFS CID References
Credential Status
Revocation State / References
```

Potential operations:

```text
registerDID()
registerCredentialHash()
setCredentialStatus()
revokeCredential()
isCredentialValid()
```

## CredentialRegistry.sol

Responsible for:

```text
Credential Issuance References
Issuer References
Validity
Credential Status
Revocation
Integrity
```

## OrganizationRegistry.sol

Responsible for:

```text
Employer Registration
Government Registration
Organization Approval State
Permissions
Authorized Employment Categories
Authorized Employment Levels / Scope
Authorized Blockchain Identity / Wallet Reference
```

## EmploymentRegistry.sol

Responsible for:

```text
Employment Creation
Employment Lifecycle
Employment Status
Employment History References
Worker DID
Employer Identity
```

## WelfareSchemeRegistry.sol

Responsible for:

```text
Scheme Registration
Claim References
Claim Status
Cooldown State
Duplicate Claim Prevention
```

Complex eligibility calculations can remain off-chain when appropriate.

---

# 42. Blockchain Data Boundary

Do not place the following raw information directly on-chain:

```text
Full Aadhaar Number
Full Address
Phone Number
Email Address
Unnecessary PII
Large Credential Documents
```

Blockchain should primarily hold:

```text
DID references
Credential hashes
IPFS CIDs / references
Issuer references
Status / revocation state
Employment references / hashes
Benefit claim references / hashes
Organization authorization
Audit events
```

---

# 43. Credential Wallet

The worker credential wallet should support at minimum:

```text
Identity Credential
Skill / Trade Credentials
Safety / BOCW Certification
```

Each credential can display:

```text
Credential Type
Issuer
Status
Issue Date
Expiration if applicable
Verification State
```

The final taxonomy is configurable.

---

# 44. Role-Based Information Filtering

## Employer

Should primarily receive:

```text
Verified Identity Result
Worker DID where appropriate
Relevant Skills
Relevant Certifications
BOCW status where required
Employment Eligibility
Availability / Work Status where authorized
Relevant Employment History
```

It should not automatically receive:

```text
Full Aadhaar
Full home address
Private phone
Private email
```

## Government

May receive:

```text
Identity verification result
Origin state
Current state
Authorized masked Aadhaar representation
Relevant credentials
Employment information
Welfare history
Eligibility information
```

Access depends on government authorization.

---

# 45. Seed Data

The platform should boot with rich pre-seeded demonstration data.

Seed categories should include:

```text
MOCK AADHAAR
├── Multiple worker records
├── Valid records
├── Invalid / mismatch cases
└── Different worker profiles

EMPLOYERS
├── Approved employers
├── Pending employers
├── Different business types
├── Different employment categories
└── Different permission scopes

EMPLOYMENT CATEGORIES
├── Mason
├── Electrician
├── Plumber
├── Carpenter
├── Welder
├── Machine Operator
└── General Labour

WORKER CREDENTIALS
├── Identity credentials
├── Skill credentials
├── BOCW / Safety credentials
└── Different credential statuses

EMPLOYMENT HISTORY
├── Active
├── Completed
├── Terminated
├── Dismissed
├── Resigned
└── Multiple employers

GOVERNMENT
├── Multiple authorities / departments
├── Welfare schemes
├── Eligible workers
├── Existing claims
└── Cross-state examples

ADMIN
├── Approved organizations
├── Pending organizations
├── Category requests
└── Permission configurations
```

---

# 46. Seeded Mode + Fresh Mode

The recommended seeded demo mode should **not** replace fresh onboarding.

Support both:

```text
DEMO / SEEDED MODE
        +
FRESH / EMPTY MODE
```

Recommended capabilities:

```text
Load Seed Data
Reset Demo Data
Clear Environment
Start Fresh
```

The seeded environment should demonstrate the full product immediately.

Fresh mode should validate that the onboarding workflows actually work from scratch.

---

# 47. Current Test Coverage

Current evidence in the walkthrough reports:

```text
Smart Contracts:
10 passing tests

Backend:
6 passing tests

End-to-End:
7-stage flow passing
```

The existing test evidence includes:

- DID registration
- Duplicate DID prevention
- Worker identity revocation
- Organization approval
- Additional category authorization
- Employment category enforcement
- Employment status updates
- Welfare claim cooldown / duplicate prevention
- Aadhaar verification logic
- Encryption / IPFS flow
- Ed25519 signatures
- QR generation / verification
- Role filtering
- End-to-end worker-to-welfare lifecycle

These tests are a strong foundation.

---

# 48. Required Additional Automated Tests

Add tests for:

```text
Email verification requirement
Phone OTP verification requirement
Aadhaar-to-account binding
Aadhaar name mismatch
Aadhaar number mismatch
Aadhaar unavailable / service failure
Employer approval
Employer rejection
Employer activation email workflow
Unauthorized employment level
Unauthorized employment nature
Dismissed worker
Worker removed from active roster but history preserved
Credential expiration
Credential revocation
Expired QR presentation
Tampered QR presentation
Invalid presentation signature
Credential integrity hash mismatch
Unauthorized role access
Employer role attempting government action
Government role attempting admin action
Cross-state duplicate claim
30-day cooldown boundary
Invalid claim state transition
Unauthorized blockchain wallet transaction
```

---

# 49. Security Testing Priorities

The highest-value security tests are:

## Credential Tampering

```text
Modify IPFS credential
        ↓
Recompute hash
        ↓
Compare with on-chain hash
        ↓
FAIL
```

## QR Tampering

```text
Modify QR payload
        ↓
Presentation signature verification
        ↓
FAIL
```

## QR Expiration

```text
Expired presentation
        ↓
Verification
        ↓
REJECT
```

## Role Escalation

```text
Employer token
        ↓
Admin endpoint
        ↓
REJECT
```

## Organization Permission Bypass

```text
Employer requests unauthorized job category
        ↓
Direct API manipulation
        ↓
Backend authorization
        ↓
REJECT
```

---

# 50. README Reconciliation

The current README is useful as a concise overview, setup guide and architecture reference.

However, it should remain a summary document.

It should not replace the product specification.

After the architecture is reconciled, update the README to reflect:

```text
Correct IPFS terminology
Correct crypto terminology
Web3.js / Web3.py client responsibilities
Real RBAC vs demo role switching
Current product status
Seeded vs fresh mode
Five-role architecture
QR upload-only verification
Cross-state workflow
```

---

# 51. Source-of-Truth Document Hierarchy

The documentation should be organized as:

```text
01_Product_Specification.md
        ↓
Defines WHAT the product does

02_Implementation_Plan.md
        ↓
Defines HOW it should be built

03_Teamwork_Project_Prompt.md
        ↓
Defines WHAT the implementation team/agent must execute

04_Walkthrough.md
        ↓
Describes WHAT is actually implemented and tested

05_README.md
        ↓
Provides concise overview, setup and operational guidance
```

Do not allow lower-level documents to silently change product requirements.

When there is a conflict:

```text
Product Specification
        ↓
Implementation Plan
        ↓
Teamwork Prompt
        ↓
Walkthrough
        ↓
README summary
```

The walkthrough should never claim a feature is implemented unless it is actually implemented.

---

# 52. Required Document Synchronization

Once architecture corrections are implemented:

### Product Specification

Must contain:

```text
All business requirements
All role workflows
All permissions
All privacy rules
All credential lifecycle rules
All configurable areas
```

### Implementation Plan

Must translate those requirements into:

```text
Components
Services
Contracts
APIs
Database models
Frontend modules
Tests
```

### Teamwork Prompt

Must contain:

```text
Execution-ready requirements
Acceptance criteria
No contradictory options
No ambiguity around security or roles
```

### Walkthrough

Must contain:

```text
Only actually implemented behavior
Actual test evidence
Actual runtime behavior
Known limitations
```

### README

Must contain:

```text
Quick overview
Architecture summary
Setup
Run commands
Verification summary
Development notes
```

---

# 53. Current Product Architecture — Canonical Target

```text
                           PASSKHADAM
                Decentralized Worker Identity
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
     IDENTITY              EMPLOYMENT             WELFARE
        │                     │                     │
        ▼                     ▼                     ▼
    Aadhaar                Employers             Government
    Verification           Worker Verify         Verification
    DID                    Employment            Eligibility
    Credentials            History               Claims
    IPFS                    Status                Disbursement
    Blockchain                                     Ledger
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                       TRUST & GOVERNANCE
                              │
                 ┌────────────┴────────────┐
                 │                         │
               ADMIN                AADHAAR AUTHORITY
                 │                         │
          Permissions                 Identity API
          Organizations               Verification
          Categories                 Records / Logs
          Governance
```

---

# 54. Canonical Runtime Architecture

```text
React
  │
  ├── Worker Portal
  ├── Employer Portal
  ├── Government Portal
  ├── Admin Portal
  └── Aadhaar Authority Portal
          │
          ▼
       FastAPI
          │
     ┌────┼─────────────┐
     │    │             │
     ▼    ▼             ▼
 Auth   Identity     Verification
        + VC         Engine
     │    │             │
     │    ├─────────────┤
     │    │             │
     ▼    ▼             ▼
 Firebase DB          IPFS Provider
                       │
                       ▼
                  Web3 / Web3.py
                       │
                       ▼
                  EVM / Hardhat
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
       Identity    Employment    Welfare
       Registry    Registry      Registry
```

Frontend blockchain operations may use Web3.js where appropriate.

---

# 55. Canonical Worker Lifecycle

```text
1. Register
2. Verify email
3. Verify phone
4. Complete profile
5. Verify Aadhaar
6. Bind verified identity to account
7. Generate DID
8. Generate DID Document
9. Create Verifiable Credential
10. Sign credential
11. Generate integrity hash
12. Encrypt credential
13. Store encrypted credential through IPFS provider
14. Store DID / credential hash / reference on blockchain
15. Activate credential wallet
16. Generate expiring QR presentation
17. Download QR image
18. Employer / Government uploads QR image
19. Central Verification Engine validates presentation
20. Authorized action is performed
21. Result is recorded / audited
```

---

# 56. Canonical Employer Lifecycle

```text
Employer Registration
        ↓
Submit organization information
        ↓
Submit employment categories / levels / nature
        ↓
Submit supporting documents
        ↓
Admin Review
        ↓
Approve / Reject / More Information
        ↓
Approved
        ↓
Secure Email Activation
        ↓
Permissions Applied
        ↓
Employer Login
        ↓
Upload Worker QR
        ↓
Worker Verification
        ↓
View Authorized Information
        ↓
Offer Employment
        ↓
Validate Category / Level / Nature
        ↓
Create Employment Record
        ↓
Employment Becomes Active
        ↓
Later:
Complete / Terminate / Dismiss / Resign / Suspend
        ↓
Remove from active roster
        ↓
Preserve history
```

---

# 57. Canonical Government Lifecycle

```text
Government Authority Registration
        ↓
Admin Authorization
        ↓
Officer Authorization
        ↓
Government Login
        ↓
Upload Worker QR
        ↓
Verify DID / Credentials
        ↓
Check Origin-State KYC
        ↓
Determine Interstate Context
        ↓
Evaluate Benefit Eligibility
        ↓
Check Cooldown
        ↓
Check Cross-State Duplicate Claims
        ↓
Generate Claim ID
        ↓
Authorized Officer / Authority Wallet Signs
        ↓
Record Claim / Disbursement
        ↓
Audit / Blockchain Reference
```

---

# 58. Canonical Aadhaar Authority Lifecycle

```text
Mock Aadhaar Authority
        ↓
Maintain simulated demographic records
        ↓
Receive verification request
        ↓
Validate Aadhaar number
        ↓
Validate name
        ↓
Validate active / valid status where configured
        ↓
Return verification result
        ↓
Log request
        ↓
Expose service health / metrics
```

The PassKhadam backend should interact through the API rather than directly querying the authority's database.

---

# 59. Canonical Data Flow

```text
Aadhaar Verification
        ↓
Verified Result
        ↓
Identity Binding
        ↓
DID
        ↓
Verifiable Credential
        ↓
Credential Signing
        ↓
Integrity Hash
        ↓
Encryption
        ↓
IPFS
        ↓
CID
        ↓
Blockchain Reference
```

Verification:

```text
Uploaded QR
        ↓
Presentation
        ↓
DID
        ↓
Blockchain Registry
        ↓
CID
        ↓
IPFS
        ↓
Encrypted Credential
        ↓
Decryption
        ↓
Signature Validation
        ↓
Integrity Hash Validation
        ↓
Revocation / Status
        ↓
Role Authorization
        ↓
Authorized Result
```

---

# 60. Final Review — What Is Already Strong

The existing artifacts already have several strong foundations:

```text
✓ Five-role architecture
✓ Fully web-based QR upload model
✓ Local Hardhat development environment
✓ Modular Solidity contracts
✓ Mock Aadhaar Authority
✓ Shared verification engine
✓ Privacy-aware blockchain data model
✓ Credential wallet
✓ QR presentation expiry
✓ Employer category authorization
✓ Employment lifecycle concept
✓ Cross-state portability
✓ Welfare duplicate prevention
✓ Automated smart-contract tests
✓ Backend tests
✓ End-to-end integration test
✓ Seeded demonstration data
✓ Unified React application
```

The current Walkthrough provides concrete evidence of 10 smart-contract tests, 6 backend tests and a 7-stage end-to-end lifecycle. These results should be preserved as implementation evidence, but future walkthrough claims must remain limited to what the current build actually demonstrates.

---

# 61. Final Review — What Must Be Fixed Before Next Processing

The next implementation/documentation pass should prioritize:

```text
1. Normalize Web3.js / Web3.py / ethers architecture.
2. Remove “Identity Approval” unless intentionally introduced.
3. Make Firebase the normal authentication path; mock auth development-only.
4. Separate real RBAC from the demo Role Switcher.
5. Correct “eliminates centralized database” wording.
6. Stop calling the current local/mock environment literally production-ready.
7. Add the verified Aadhaar card visual.
8. Add employer email activation flow.
9. Add employment level and nature-of-employment permissions.
10. Add BOCW certification explicitly.
11. Add employment dismissal/removal while preserving history.
12. Add credential integrity-hash verification to the verification engine.
13. Unify the cryptographic responsibility model.
14. Keep AES-256-GCM terminology separate from Fernet.
15. Clarify IPFS-compatible local provider vs real IPFS network.
16. Add origin-state KYC registry explicitly.
17. Normalize the 30-day cooldown rule.
18. Restore cross-state duplicate-claim logic explicitly.
19. Restore SHA-256 Claim ID.
20. Require authorized government wallet signing.
21. Add revocation authority boundaries.
22. Expand automated security / authorization tests.
23. Synchronize all five documentation layers after implementation changes.
```

---

# 62. Implementation Priority Matrix

## P0 — Must Fix

These are architecture/security/documentation blockers:

```text
Web3.js / Web3.py ambiguity
RBAC vs Role Switcher
Cryptographic model ambiguity
Credential integrity-hash verification
Aadhaar account-binding logic
30-day cooldown inconsistency
Centralized database wording
Production-ready wording
IPFS provider terminology
```

## P1 — Must Implement / Reconcile

```text
Verified Aadhaar card visual
Employer activation email
Employment levels
Nature of employment
BOCW certification
Dismissed status
Worker removal + history preservation
Origin-state KYC registry
Cross-state duplicate claim logic
SHA-256 Claim ID
Authorized government wallet
Credential revocation authority
```

## P2 — Strengthening

```text
Nonce / challenge-based QR anti-replay
Additional security tests
More complete seeded data
Fresh-mode reset tooling
README synchronization
Expanded audit model
```

---

# 63. Product Change Policy

This consolidated document does not freeze the product.

The product remains intentionally adaptable.

> **Any changes in steps are entertained.**

A change is acceptable when it improves:

- Security
- Privacy
- Usability
- Reliability
- Scalability
- Interoperability
- Maintainability
- Performance
- Cost
- Regulatory compatibility
- Decentralization value

Do not retain a feature merely because it already appears in a document.

---

# 64. Final Instruction for the Next Processing Step

The next processing agent/team should use this document together with the existing product specification and implementation artifacts to:

1. Reconcile all contradictory terminology.
2. Preserve the original product objective.
3. Implement the missing product requirements identified above.
4. Avoid silently removing original requirements.
5. Separate development/demo infrastructure from production architecture.
6. Enforce role permissions server-side.
7. Ensure all cryptographic claims in the UI correspond to real backend operations.
8. Add automated tests for the missing security and lifecycle cases.
9. Synchronize the Product Specification, Implementation Plan, Teamwork Prompt, Walkthrough and README.
10. Record actual implementation status honestly rather than claiming functionality that has not been implemented.

The next version should emerge as a **single coherent PassKhadam product architecture**, not as five independently evolving documents.

---

# 65. Final Product Definition

> **PassKhadam is a web-based decentralized identity platform that enables migrant workers to establish a verified digital identity, receive and control verifiable credentials, present cryptographic proof through downloadable QR images, be verified by authorized employers and government authorities without camera scanning, build portable employment history, and access eligible welfare services across states through privacy-conscious, auditable verification.**
