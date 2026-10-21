# PASSKHADAM — Next Processing Execution Guide
## Version 1.0
### Execution-Control Document for Continued Product Development

---

# 1. Purpose

This document is the **execution-control and handoff guide** for the next processing step of the PassKhadam product.

It exists to prevent architectural drift, requirement loss, contradictory implementation decisions, accidental scope changes, and unsupported claims of completion.

This document should be used together with the current PassKhadam product documentation and implementation artifacts.

It defines:

- Which document is authoritative for which type of decision
- Which architecture decisions are currently locked
- Which areas remain configurable
- Which product requirements must be preserved
- Role and permission boundaries
- Identity, credential, QR, employment and welfare workflows
- Cryptographic responsibilities
- Storage boundaries
- Development vs production distinctions
- Required implementation behavior
- Required verification/testing standards
- Conflict-resolution rules
- Reporting requirements for deviations
- Final implementation checklist

---

# 2. Execution Principle

The next processing step must follow this rule:

> **Do not silently change, remove, reinterpret, weaken, or replace an existing product requirement.**

When a change is necessary:

```text
Identify Requirement
        ↓
Explain Proposed Change
        ↓
Evaluate Security / Privacy / UX / Architecture Impact
        ↓
Record Change
        ↓
Apply Change Consistently Across All Documents
```

Changes are allowed.

Silent drift is not.

---

# 3. Product North Star

PassKhadam is a **web-based decentralized identity platform for migrant workers**.

The central product objective is:

> **A worker establishes one trusted, portable and privacy-conscious digital identity that can be used across authorized employers, states and government services without recreating the identity after migration.**

The product should connect:

```text
IDENTITY
   +
EMPLOYMENT
   +
WELFARE
   +
GOVERNANCE
```

through a common trust and verification layer.

---

# 4. Canonical Product Story

The product story must remain:

```text
Worker Registers
        ↓
Email Verified
        ↓
Phone Verified
        ↓
Profile Completed
        ↓
Aadhaar / Government Identity Verified
        ↓
Identity Bound to Worker Account
        ↓
DID Created
        ↓
Verifiable Credential Created
        ↓
Credential Signed
        ↓
Credential Integrity Hash Created
        ↓
Credential Encrypted
        ↓
Encrypted Credential Stored through IPFS Provider
        ↓
CID / Hash / Identity Reference Anchored on EVM Blockchain
        ↓
Worker Credential Wallet Activated
        ↓
Worker Generates QR Identity Presentation
        ↓
Worker Downloads QR Image
        ↓
Employer / Government Uploads QR Image
        ↓
Central Verification Engine
        ↓
Identity / Credential / Integrity / Status / Authorization Validation
        ↓
Employment or Welfare Action
        ↓
Auditable Record
```

This is the canonical baseline.

---

# 5. Document Authority Hierarchy

Use the documents according to the following hierarchy:

```text
01. Product Specification
        ↓
Defines WHAT the product does

02. Implementation Plan
        ↓
Defines HOW the product is built

03. Teamwork Project Prompt
        ↓
Defines WHAT the implementation agent/team must execute

04. Walkthrough
        ↓
Defines WHAT is actually implemented and tested

05. README
        ↓
Human-facing setup and concise system overview
```

### Rule

A lower-level document must not silently redefine a higher-level product requirement.

Example:

If the Product Specification says:

```text
Employer verifies worker using QR image upload
```

the Implementation Plan must not replace this with:

```text
Camera scanning
```

without an explicitly documented architecture change.

---

# 6. Current Locked Architecture Decisions

The following decisions are currently locked as the baseline.

## 6.1 Product Type

```text
WEB-BASED
```

The product is not dependent on Android/mobile-specific functionality.

---

## 6.2 QR Interaction

```text
NO CAMERA SCANNING
```

Worker:

```text
Generate QR
↓
Download QR image
```

Employer / Government:

```text
Upload QR image
↓
Decode and verify
```

Camera-based verification is not part of the core workflow.

---

## 6.3 Blockchain Runtime

Default development environment:

```text
Hardhat Local EVM
Chain ID:
31337
```

Benefits:

- Reproducible local execution
- Fast transactions
- No external RPC dependency
- No testnet faucet dependency
- Deterministic development
- Automated contract testing

Public EVM testnets remain a future deployment target.

---

## 6.4 Frontend Blockchain Client

```text
Web3.js
```

Primary responsibility:

- Browser wallet interaction
- Frontend contract queries
- Frontend blockchain actions where required

---

## 6.5 Backend Blockchain Client

```text
Web3.py
```

Primary responsibility:

- FastAPI blockchain service
- Backend contract interaction
- Transaction submission where backend signing is required
- Registry queries

---

## 6.6 Smart Contracts

Baseline contracts:

```text
WorkerIdentityRegistry.sol
CredentialRegistry.sol
OrganizationRegistry.sol
EmploymentRegistry.sol
WelfareSchemeRegistry.sol
```

---

## 6.7 Backend

```text
FastAPI
```

Core services:

```text
Authentication
Identity / DID
Credential issuance
Verification
Employment
Welfare
Organization authorization
Aadhaar integration
Blockchain service
IPFS service
```

---

## 6.8 Authentication

Normal product path:

```text
Firebase Authentication
```

Required capabilities:

```text
Email verification
Phone OTP verification
Authentication
Session management
Token-based backend authorization
```

Development convenience:

```text
Mock / Dev Authentication Adapter
```

The mock adapter must not replace the intended Firebase product path in normal usage.

---

## 6.9 Database

Baseline:

```text
SQLAlchemy
+
SQLite / PostgreSQL
```

Use for:

- Application data
- Operational data
- Organization records
- Requests
- Non-blockchain workflow state
- Appropriate off-chain metadata
- Origin-state KYC registry where configured
- Development/demo data

---

## 6.10 IPFS

Development:

```text
IPFS_PROVIDER=local
```

The local provider should support real content-addressed CID generation.

External provider support:

```text
Kubo
Pinata
```

or another compatible provider through configuration.

Do not describe a local filesystem-only simulation as a fully decentralized public IPFS network.

---

# 7. Canonical Cryptographic Responsibility Map

The cryptographic architecture must remain explicit and non-ambiguous.

## 7.1 QR / Presentation Envelope

```text
Ed25519
```

Purpose:

```text
Presentation envelope authenticity
```

---

## 7.2 Credential Encryption

Current implementation baseline:

```text
AES-256-GCM
```

Purpose:

```text
Encryption of credential payload before IPFS storage
```

Do not use the phrase:

```text
AES-256 Fernet
```

These are different constructions.

---

## 7.3 Credential Integrity

```text
SHA-256
```

Purpose:

```text
Credential payload integrity hash
```

Verification:

```text
Retrieve credential
        ↓
Recompute SHA-256
        ↓
Compare with blockchain anchor
        ↓
Match = integrity valid
Mismatch = tampering detected
```

---

## 7.4 EVM Hashing

```text
Keccak-256
```

May be used where required by Ethereum/EVM data structures and hashing.

Do not confuse Keccak-256 with SHA-256.

---

## 7.5 Credential / Typed Signing

The implementation may use:

```text
ECDSA secp256k1
```

and:

```text
EIP-712
```

where appropriate for typed structured-data signing.

EIP-712 is the typed-data signing mechanism, not the complete Verifiable Credential format.

---

# 8. Worker Identity Workflow

## 8.1 Account Creation

Fields:

```text
Full Name
Email
Phone
Password
Confirm Password
```

---

## 8.2 Contact Verification

```text
Create Account
        ↓
Verify Email
        ↓
Verify Phone via OTP
        ↓
Account Activated
```

---

## 8.3 Profile

Potential fields:

```text
Full Name
DOB
Gender
Phone
Email
Current State
Origin State
Address
Worker Category
Optional Skills
```

These fields are configurable and should not all be assumed mandatory.

---

## 8.4 Government Identity Verification

Worker selects:

```text
Verify Government Identity
```

Inputs:

```text
Aadhaar Number
Name as registered with Aadhaar
```

Request:

```text
Worker
   ↓
PassKhadam Backend
   ↓
Mock Aadhaar API
   ↓
Aadhaar Record Lookup
   ↓
Name Match
   ↓
Aadhaar Number Match
   ↓
Status Validation where configured
   ↓
Verification Result
```

---

## 8.5 Identity Binding

Do not introduce an unsupported admin approval step between Aadhaar verification and DID creation.

Baseline:

```text
Aadhaar Verification
        ↓
Successful Identity Verification
        ↓
Bind Result to Authenticated Worker Account
        ↓
Generate DID
```

---

# 9. Aadhaar Authority Rules

The Mock Aadhaar Authority should behave like an external identity authority.

The architecture should be:

```text
PassKhadam
    ↓
Aadhaar Verification API
    ↓
Mock Aadhaar Authority
    ↓
Mock Aadhaar Database
```

PassKhadam should not directly query the Aadhaar database.

The API should return the minimum necessary verification result.

Example:

```json
{
  "verified": true,
  "reference_id": "AAD-VRF-83921",
  "name_match": true,
  "identity_record_valid": true
}
```

---

# 10. Aadhaar Result and Document Visual

On successful verification:

```text
Aadhaar Verified ✓
Name Matched ✓
Aadhaar Number Matched ✓
Identity Record Valid ✓
```

The Worker Portal must support a **verified government identity document visual**.

Example:

```text
VERIFIED GOVERNMENT DOCUMENT

Name:
[Verified Name]

Aadhaar:
XXXX XXXX 4821

Status:
✓ VERIFIED
✓ VALID
```

The visual must be clearly marked as a simulated/mock representation when applicable.

Never unnecessarily display the full Aadhaar number.

---

# 11. DID and Verifiable Credential Workflow

After successful identity verification:

```text
Generate DID
        ↓
Generate DID Document
        ↓
Create Worker Identity Verifiable Credential
        ↓
Create signing representation
        ↓
Sign credential / proof
        ↓
Compute integrity hash
        ↓
Encrypt payload
        ↓
Store encrypted payload through IPFS provider
        ↓
Get CID
        ↓
Anchor DID / credential hash / reference
on blockchain
```

Example DID:

```text
did:passkhadam:worker:{hash}
```

The DID must not expose unnecessary personal information.

---

# 12. Identity Issuance Processing Animation

UI steps may communicate:

```text
🔐 Establishing secure identity verification channel...
📋 Validating Aadhaar demographic credentials...
🆔 Generating W3C DID Document...
📄 Creating W3C Verifiable Credential...
🔑 Preparing credential signing payload...
✍️ Signing credential with authorized issuer key...
🔍 Computing SHA-256 integrity hash...
📦 Encrypting credential payload with AES-256-GCM...
🌐 Pinning encrypted credential to IPFS...
📌 IPFS CID generated and pinned...
⛓️ Anchoring identity / credential reference on WorkerIdentityRegistry.sol...
✅ Identity credential successfully issued.
```

The UI must only show an operation as completed if the backend actually completed it.

---

# 13. Credential Wallet

Baseline credential categories:

```text
Identity Credential
Trade / Skill Credential
BOCW Safety Certification
Safety Induction / other relevant certification
```

Each credential may show:

```text
Type
Issuer
Status
Issue Date
Expiration if applicable
Verification state
```

---

# 14. Worker QR Presentation

Worker selects:

```text
Share Identity
```

The platform generates:

```text
Cryptographic Presentation
+
QR Image
+
Expiration
```

Current baseline:

```text
5 minutes / 300 seconds
```

Worker can:

```text
Download QR
Download Presentation
```

---

# 15. QR Presentation Security

Baseline:

```text
Presentation expiry
+
Ed25519 envelope signature
```

Future strengthening can include:

```text
Nonce
Challenge
Audience binding
Verifier binding
```

Do not claim stronger anti-replay protections unless implemented.

---

# 16. Employer Onboarding Workflow

Employer submits:

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
Supporting Documents
```

---

# 17. Employer Approval

```text
Employer Registration
        ↓
Documents Submitted
        ↓
Admin Review
        ↓
Business Verification
        ↓
Category Review
        ↓
Level Review
        ↓
Nature-of-Employment Review
        ↓
Approve / Reject / Request More Information
```

Employer status:

```text
PENDING_REVIEW
APPROVED
REJECTED
SUSPENDED
```

---

# 18. Employer Secure Activation

After approval:

```text
Admin Approval
        ↓
Employer Organization Created
        ↓
Permissions Assigned
        ↓
Secure Activation Token Generated
        ↓
Activation Link Sent to Registered Email
        ↓
Employer Activates Account
```

Never use insecure plaintext password delivery where a secure activation link is possible.

---

# 19. Employer Permissions

The employer's authority should be scoped by:

```text
Employment Category
Employment Level
Nature of Employment
Other configured permissions
```

Example:

```text
ABC Construction

Mason ✓
Electrician ✓
Plumber ✓

Heavy Machinery Operator ✕
```

The restriction must be enforced by the backend, not merely hidden in the frontend.

---

# 20. Additional Employer Category Request

```text
Employer
        ↓
Request Additional Category
        ↓
Admin Review
        ↓
Approve / Reject / More Information
        ↓
Employer Permission Updated
```

Until approval:

```text
Requested category = NOT AUTHORIZED
```

---

# 21. Employer Worker Verification

Employer selects:

```text
Verify Worker
```

Then:

```text
UPLOAD WORKER QR

[ Drag & Drop QR Image Here ]

or

[ Choose QR Image ]

[ Verify Identity ]
```

No camera requirement.

---

# 22. Canonical Verification Engine

The central verification service must be shared between Employer and Government.

Logical sequence:

```text
1. Decode uploaded QR presentation
2. Validate presentation expiry
3. Verify Ed25519 presentation signature
4. Resolve worker DID
5. Check credential / identity status and revocation
6. Retrieve encrypted credential using IPFS CID
7. Recompute credential integrity hash
8. Compare against on-chain integrity anchor
9. Decrypt credential using AES-256-GCM
10. Verify issuer credential signature / proof
11. Apply role-based authorization filters
12. Apply required origin-state KYC verification for government workflows
```

The UI may display a shortened 10-step sequence if several backend operations are grouped, but all critical validations must actually occur.

---

# 23. Employer Verification Result

Employer should receive only authorized information.

Example:

```text
WORKER VERIFICATION

Identity:
✓ VERIFIED

Worker DID:
did:passkhadam:worker:8f29...

Identity Credential:
✓ VALID

Skill:
Mason ✓

BOCW Safety Certification:
✓ VALID

Employment Eligibility:
✓ ELIGIBLE
```

Employer should not automatically receive:

```text
Full Aadhaar
Full home address
Private phone
Private email
Unnecessary PII
```

---

# 24. Employer Verification Processing Animation

Baseline UI messaging:

```text
🔍 Decoding uploaded QR cryptographic presentation...
📂 Resolving DID Document...
⛓️ Querying WorkerIdentityRegistry.sol...
📌 Resolving encrypted IPFS CID...
🔓 Processing encrypted credential payload...
🔐 Verifying presentation / issuer signatures...
🛡️ Checking credential status and revocation...
🔍 Verifying credential integrity against on-chain hash...
🏗️ Checking BOCW safety certification & skill category...
📋 Applying employer authorization rules...
✅ Worker identity cryptographically verified.
```

---

# 25. Employer Employment Creation

Employer selects:

```text
Offer Employment
```

Baseline information:

```text
Worker
Employment Category
Job Role
Employment Level
Nature of Employment
Employment Type
Work Location
Construction / Work Site
Start Date
Expected End Date
Contract / Reference Information
```

---

# 26. Employment Authorization

Before creating the employment record:

```text
Employer Authorized?
        ↓
Category Authorized?
        ↓
Employment Level Authorized?
        ↓
Nature Authorized?
        ↓
Worker Credentials Valid?
        ↓
Create Employment Record
```

---

# 27. Employment Logging

Baseline processing:

```text
📝 Preparing verifiable employment stint record...
🏢 Attaching employer DID / organization identity...
🏗️ Attaching construction site and work-site metadata...
👷 Assigning authorized employment category and level...
📋 Validating employer permissions...
🔐 Signing employment record with authorized employer identity...
⛓️ Anchoring employment record / hash...
📦 Updating worker's portable employment history...
✅ Employment stint anchored successfully.
```

---

# 28. Event-Driven Employment Lifecycle

Employment history should be append-only / event-driven wherever practical.

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
Employment Completed
```

or:

```text
Employment Created
        ↓
Employment Terminated
```

Current status may be derived from the latest valid event.

---

# 29. Employment Statuses

Baseline:

```text
ACTIVE
COMPLETED
TERMINATED
DISMISSED
RESIGNED
SUSPENDED
```

---

# 30. Employer Worker Removal

Required behavior:

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
Create Employment Event
   ↓
Remove From Active Workforce
   ↓
Preserve Historical Employment Record
```

Critical rule:

> Removing a worker from an employer's active roster must never delete the historical employment record.

---

# 31. Government Onboarding

Government authority onboarding:

```text
Government Authority Registration
        ↓
Authority / Department Information
        ↓
Officer Information
        ↓
Supporting Authorization
        ↓
Admin Verification
        ↓
Permission Assignment
        ↓
Government Portal Activated
```

Different departments may have different permission scopes.

---

# 32. Government Verification

Government officer:

```text
Upload Worker QR
```

Then:

```text
Decode QR
        ↓
Resolve DID
        ↓
Check identity / credential status
        ↓
Retrieve encrypted credential
        ↓
Verify integrity
        ↓
Decrypt
        ↓
Verify issuer proof
        ↓
Cross-reference origin-state KYC
        ↓
Apply government authorization
        ↓
Return result
```

---

# 33. Government Verification Result

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

Origin-State KYC:
CONFIRMED ✓
```

---

# 34. Government Origin-State KYC

The baseline implementation may use:

```text
Origin-State KYC Registry
        ↓
SQLite-backed operational registry
```

The registry should provide only the information necessary for authorized cross-state verification.

It should not become an unrestricted second copy of sensitive identity data.

---

# 35. Cross-State Portability

Example:

```text
Origin:
Karnataka

Current State:
Maharashtra
```

The worker should not need a new PassKhadam identity simply because they moved.

Instead:

```text
Existing DID
        ↓
Existing Credentials
        ↓
Verification
        ↓
Cross-State Context
        ↓
Eligibility
        ↓
Government Service
```

---

# 36. Government Benefit Eligibility

The eligibility engine may evaluate:

```text
Identity validity
Worker category
Skill / certification
Employment status
Origin state
Current state
Scheme rules
Previous claims
Cross-state claim history
Cooldown
Other configured conditions
```

Complex eligibility rules may remain off-chain.

---

# 37. Welfare Scheme Architecture

Recommended split:

```text
Government Eligibility Engine
        ↓
Evaluate private / configurable attributes
        ↓
Generate eligibility result + scheme/rule version
        ↓
Blockchain
        ↓
Record claim / integrity reference
        ↓
Enforce critical cooldown / duplicate invariants
```

Do not turn the blockchain into an unnecessarily large rules engine.

---

# 38. Welfare Claim

Example:

```text
Worker:
did:passkhadam:worker:8f29...

Scheme:
Migrant Worker Assistance

Amount:
₹XXXX

State:
Maharashtra

Claim Type:
Welfare Disbursement
```

---

# 39. Benefit Cooldown

Current baseline:

```text
30 days
```

The cooldown must be calculated dynamically from timestamps.

Do not hardcode text such as:

```text
31 more days
```

Instead:

```text
claim_timestamp
        +
configured_cooldown_seconds
        =
cooldown_expiry
```

Then:

```text
remaining_time =
cooldown_expiry - current_timestamp
```

The 30-day rule should be configurable per welfare scheme.

---

# 40. Cross-State Duplicate Claim Prevention

The system should check equivalent/conflicting claims across authorized registries.

Conceptual flow:

```text
Current Claim
        ↓
Worker Identity
        ↓
Claim History Lookup
        ├── Origin State
        ├── Current State
        └── Other Authorized States
        ↓
Duplicate / Conflict Check
        ↓
ALLOW / REJECT / REVIEW
```

---

# 41. SHA-256 Claim ID

Current baseline:

```text
Claim Data
        ↓
Canonical representation
        ↓
SHA-256
        ↓
Claim ID
```

The exact canonical input may include:

```text
claim identifier
worker DID
scheme ID
timestamp
```

The exact formula can remain implementation-defined, but it must be deterministic if that is the selected design.

---

# 42. Government Disbursement Signing

Required concept:

```text
Government Organization
        ↓
Authorized Officer
        ↓
Officer Permission
        ↓
Registered Blockchain Identity / Wallet
        ↓
Signed Transaction
```

Logging into the web portal alone is not sufficient blockchain authority.

---

# 43. Admin Governance

Admin manages:

```text
Employers
Government Authorities
Credential Issuers
Employment Categories
Employment Levels / Rules
Organization Permissions
Approval queues
Suspensions
Credential governance
Audit logs
Platform configuration
```

Admin actions:

```text
Approve
Reject
Suspend
Reactivate
Request More Information
```

---

# 44. Credential Authority Boundaries

Examples:

```text
Identity Authority
→ Identity credentials

Skill / Certification Authority
→ Skill / safety credentials

Employer
→ Its own employment records / credentials

Government Authority
→ Its own authorized welfare records
```

Do not allow arbitrary role holders to revoke or modify credentials they do not govern.

---

# 45. Aadhaar Authority Portal

Capabilities:

```text
Mock Aadhaar Record Directory
Verification Requests
Verification Logs
API Access
API Health
Traffic Analytics
Service Configuration
```

Possible metrics:

```text
Total Records
Active Records
Verification Requests
Successful Requests
Failed Requests
Latency
API Health
```

---

# 46. Role-Based Access Control

Real authorization must be server-side.

## Worker

```text
Register
Verify Email
Verify Phone
Complete Profile
Verify Government Identity
Receive DID
Receive Credentials
View Credential Wallet
View Employment History
Generate QR
Download QR
View Benefit History
Manage Profile
Manage Sharing
Manage Security
```

## Employer

```text
Manage Company Profile
Upload Worker QR
Verify Worker
View Authorized Worker Information
View Authorized Credentials
Create Employment
Update Employment Status
End Employment
Remove Worker From Active Roster
View Authorized Employment History
Request Additional Categories
```

## Government

```text
Upload Worker QR
Verify Worker
View Authorized Credentials
Check Eligibility
Initiate Claims
Record Disbursement
Review Authorized Employment Data
Perform Cross-State Verification
View Authorized Claim History
```

## Admin

```text
Approve Organizations
Manage Permissions
Manage Employment Categories
Manage Employment Levels / Rules
Manage Credential Issuers
Suspend Organizations
Reactivate Organizations
Review Requests
View Audit Logs
```

## Aadhaar Authority

```text
Manage Mock Aadhaar Records
Handle Verification Requests
Manage API Access
View Verification Logs
Manage API Health
Maintain Identity Verification Service
```

---

# 47. Demo Role Switcher Rule

A role switcher may exist for controlled development/demo use.

It must never become the actual authorization mechanism.

Correct model:

```text
Development:
Role Switcher → simulated test context

Actual authorization:
Authenticated identity
        ↓
Server-side role
        ↓
Server-side permissions
        ↓
Allowed action
```

A frontend role switch must not allow privilege escalation.

---

# 48. Storage Boundaries

## Application Database

Use for:

```text
User account references
Firebase references
Profiles
Organizations
Requests
Operational metadata
Application state
Origin-state KYC where applicable
```

## IPFS

Use for:

```text
Encrypted credential payloads
Encrypted credential documents
Approved decentralized content
```

## Blockchain

Use for:

```text
DID references
Credential integrity hashes
IPFS CIDs / references
Issuer references
Status / revocation references
Employment record references / hashes
Benefit claim references / hashes
Organization authorization
Audit events
```

---

# 49. Never Store Raw PII On-Chain

Do not place these directly on-chain:

```text
Full Aadhaar number
Full home address
Phone number
Email address
Unnecessary demographic PII
Large credential documents
```

---

# 50. Product Privacy Principle

The worker should provide only the information necessary for the verification purpose.

Example:

```text
Employer asks:
“Is this worker a certified Mason?”
```

Preferred result:

```text
Mason ✓
Certification VALID ✓
```

rather than:

```text
Full Aadhaar
Full Address
Phone
Email
```

---

# 51. Identity and Credential Status

## Identity

```text
UNVERIFIED
PENDING
VERIFIED
REVOKED
SUSPENDED
```

## Credential

```text
PENDING
ACTIVE
EXPIRED
REVOKED
SUSPENDED
```

## Employer

```text
PENDING_REVIEW
APPROVED
REJECTED
SUSPENDED
```

## Employment

```text
ACTIVE
COMPLETED
TERMINATED
DISMISSED
RESIGNED
SUSPENDED
```

## Benefit Claim

```text
PENDING
ELIGIBLE
APPROVED
DISBURSED
REJECTED
CANCELLED
```

---

# 52. Audit Requirements

Audit important actions such as:

```text
Identity Issued
Credential Issued
Credential Revoked
Employer Approved
Employer Suspended
Government Authority Approved
Permission Changed
Employment Created
Employment Status Changed
Worker Removed From Active Workforce
Benefit Claimed
Benefit Disbursed
Category Approved
Category Rejected
```

An audit record may include:

```text
Actor
Role
Action
Timestamp
Target Entity
Transaction / Reference
Result
```

---

# 53. Testing Requirements

The next processing step must not rely only on happy-path tests.

## Authentication

Test:

```text
Email verification
Phone OTP
Unauthorized account
Expired / invalid token
```

## Aadhaar

Test:

```text
Valid Aadhaar
Name mismatch
Aadhaar mismatch
Inactive/invalid record
Service unavailable
Account binding
```

## DID / Credentials

Test:

```text
DID creation
Credential creation
Signature validation
Credential expiration
Credential revocation
Invalid credential
```

## Integrity

Test:

```text
Original credential hash
Modified IPFS credential
Hash mismatch
Verification rejection
```

## QR

Test:

```text
Valid QR
Malformed QR
Expired QR
Tampered QR
Invalid envelope signature
Unsupported file
```

## RBAC

Test:

```text
Worker → Worker actions
Employer → Employer actions
Government → Government actions
Admin → Admin actions
Cross-role privilege escalation
```

## Employer

Test:

```text
Employer approval
Employer rejection
Activation email flow
Authorized category
Unauthorized category
Authorized level
Unauthorized level
Authorized nature
Unauthorized nature
Dismissal
Termination
Worker removal
History preservation
```

## Government

Test:

```text
Origin-state KYC
Interstate detection
Eligibility
Cooldown
Duplicate claim
Cross-state duplicate
Claim ID
Wallet authorization
```

---

# 54. Security Priority Tests

Highest priority:

```text
1. Credential tampering
2. QR tampering
3. Expired QR
4. Invalid presentation signature
5. Credential signature failure
6. Integrity hash mismatch
7. RBAC privilege escalation
8. Employer category bypass
9. Employment level bypass
10. Duplicate welfare claim
11. Cooldown bypass
12. Unauthorized blockchain signer
```

---

# 55. Seed Data

The system should support rich pre-seeded demo data.

Seed:

```text
Workers
Aadhaar records
Employers
Government authorities
Employment categories
Employment levels
Nature-of-employment types
Worker credentials
BOCW certifications
Employment histories
Welfare schemes
Existing claims
Pending approval requests
Permission configurations
```

Seeded mode should demonstrate the product immediately.

---

# 56. Fresh Mode

Also support:

```text
Empty / Fresh Environment
```

Provide controlled development tooling such as:

```text
Load Seed Data
Reset Demo Data
Clear Environment
Start Fresh
```

Fresh mode should validate that onboarding works from scratch.

---

# 57. Development vs Production

## Development Baseline

```text
Hardhat Local EVM
Local IPFS Provider
Mock Aadhaar Authority
Firebase or Dev Auth Adapter
Seeded Data
Local Database
```

## Future Production-Oriented Infrastructure

```text
Public / permissioned EVM network
Real IPFS / Kubo / Pinata infrastructure
Real identity verification provider
Production Firebase configuration
Managed PostgreSQL
Production key custody
Production monitoring
Production security controls
```

Do not claim the local development system is already a production deployment.

---

# 58. What Must Not Be Silently Changed

Do not silently replace:

```text
QR Upload
→ Camera Scan

Hardhat
→ Public Testnet by default

Firebase
→ Mock Auth by default

Web3.js / Web3.py architecture
→ unexplained ethers-only architecture

Aadhaar API
→ direct database access

Worker portable identity
→ employer-owned identity

Encrypted credential storage
→ raw credential storage

Role permissions
→ unrestricted role switching

Cross-state claims
→ single-state-only checks

30-day cooldown
→ arbitrary cooldown text

Employment history
→ overwrite/delete model
```

---

# 59. When a Change Is Proposed

Use this format:

```text
CHANGE PROPOSED

Current:
[Existing architecture / workflow]

Proposed:
[New architecture / workflow]

Reason:
[Security / privacy / UX / performance / interoperability / maintainability]

Impact:
[Components affected]

Required Updates:
[Product Spec / Implementation Plan / Prompt / Walkthrough / README]

Approval:
[Required / Not Required]
```

Do not silently apply major architectural changes.

---

# 60. No Fake Technical Claims

The frontend processing animations must correspond to actual operations.

Do not display:

```text
Blockchain confirmed
```

unless a real transaction was confirmed.

Do not display:

```text
IPFS pinned
```

unless the selected IPFS provider successfully stored the object.

Do not display:

```text
Signature verified
```

unless signature verification actually succeeded.

Do not display:

```text
Aadhaar biometric verified
```

unless the identity provider actually performs biometric verification.

Do not claim:

```text
Decentralized storage
```

when only a local filesystem simulator is being used, unless it is clearly labeled as a local development IPFS-compatible provider.

---

# 61. No Biometric Claim Without Biometric Implementation

The Aadhaar workflow currently represents:

```text
Name verification
+
Aadhaar number verification
+
Status verification where configured
```

Do not describe this as:

```text
Biometric authentication
Biometric Aadhaar channel
Fingerprint verification
Face verification
```

unless such functionality genuinely exists.

---

# 62. No Unsupported Government-Authority Claims

When using a Mock Aadhaar Authority, clearly identify it as:

```text
Mock Aadhaar Authority
```

or:

```text
Simulated Identity Verification Authority
```

Do not represent mock records or a mock API as a live government service.

---

# 63. Product UX Expectations

All five portals should feel like one product.

Shared:

```text
Branding
Design system
Typography
Navigation patterns
Status language
Notifications
Verification components
Audit presentation
Interaction patterns
```

But each role sees only its authorized functionality.

---

# 64. User Experience Priority

The user should experience:

```text
Simple UI
        ↓
Clear status
        ↓
Clear next action
        ↓
Technical details available during processing
        ↓
Verifiable final result
```

The underlying system may be complex.

The interface should not force the user to understand blockchain architecture to use the product.

---

# 65. Final End-to-End Acceptance Flow

A complete acceptance run should demonstrate:

```text
1. Worker Registration
2. Email Verification
3. Phone Verification
4. Profile Completion
5. Aadhaar Verification
6. Verified Government Identity Visual
7. DID Creation / Binding
8. VC Creation
9. Credential Encryption
10. IPFS Storage
11. Blockchain Integrity Anchor
12. Credential Wallet
13. QR Presentation Generation
14. QR Image Download
15. Employer QR Upload
16. Employer Verification
17. BOCW / Skill Validation
18. Employment Authorization
19. Employment Creation
20. Employment Status Update
21. Worker Removal / Dismissal while preserving history
22. Cross-State Relocation
23. Government QR Upload
24. Origin-State KYC Verification
25. Eligibility Evaluation
26. 30-Day Cooldown Check
27. Cross-State Duplicate Claim Check
28. SHA-256 Claim ID
29. Authorized Government Wallet Signing
30. Benefit Claim / Disbursement
31. Audit Record
```

---

# 66. Final Implementation Quality Gate

Do not consider the current processing complete until:

```text
[ ] Product workflow matches the canonical product story
[ ] All 5 roles exist
[ ] Real server-side RBAC works
[ ] QR upload replaces camera requirements
[ ] Firebase is the normal authentication path
[ ] Aadhaar interaction occurs through API boundary
[ ] Verified Aadhaar visual exists
[ ] DID creation works
[ ] VC creation works
[ ] Credential encryption works
[ ] IPFS provider abstraction works
[ ] Integrity hash is anchored and verified
[ ] Presentation signature is verified
[ ] Credential signature/proof is verified
[ ] Credential revocation is enforced
[ ] BOCW credential is present and checked
[ ] Employer category permissions work
[ ] Employment level restrictions work
[ ] Nature-of-employment restrictions work
[ ] Employer activation workflow works
[ ] Employment lifecycle is event-driven / auditable
[ ] Dismissal / termination works
[ ] Historical employment is preserved
[ ] Origin-state KYC works
[ ] Cross-state portability works
[ ] 30-day cooldown is dynamically calculated
[ ] Cross-state duplicate claim prevention works
[ ] Claim ID generation works
[ ] Government wallet authorization works
[ ] Seeded data works
[ ] Fresh mode works
[ ] Security tests pass
[ ] End-to-end test passes
[ ] README matches actual implementation
[ ] Walkthrough reports actual evidence only
```

---

# 67. Documentation Synchronization Checklist

After any major implementation change:

```text
Update Product Specification
        ↓
Update Implementation Plan
        ↓
Update Teamwork Prompt
        ↓
Update Walkthrough
        ↓
Update README
```

Check for:

```text
Terminology consistency
Architecture consistency
Workflow consistency
Status consistency
Crypto consistency
Permission consistency
Technology consistency
Test-result consistency
```

---

# 68. Reporting Format for Next Processing

The next processing output should clearly distinguish:

## Implemented

```text
What actually exists and passes tests
```

## Not Yet Implemented

```text
What remains
```

## Changed

```text
What was intentionally changed from the baseline
```

## Recommended Future Improvements

```text
Optional improvements that do not alter the current baseline
```

Do not mix these four categories.

---

# 69. Conflict Resolution Examples

## Example 1

Product Specification:

```text
QR upload
```

Implementation:

```text
Camera scan
```

Resolution:

```text
Implementation is wrong unless an explicit change is approved.
```

## Example 2

Product Specification:

```text
30-day cooldown
```

Walkthrough:

```text
31-day cooldown
```

Resolution:

```text
Normalize to configured 30-day baseline and calculate remaining time dynamically.
```

## Example 3

Product Specification:

```text
Employer sees authorized skill data
```

Frontend:

```text
Employer can see full Aadhaar
```

Resolution:

```text
RBAC/privacy requirement takes priority.
```

---

# 70. Architecture Change Philosophy

A better technical solution may replace the current implementation.

Examples:

```text
Current IPFS provider
→ better IPFS provider

Current VC proof method
→ more interoperable proof method

Local blockchain
→ public testnet

SQLite
→ PostgreSQL

Development wallet model
→ secure custody model
```

Such changes are allowed.

The change must be:

```text
Explicit
Justified
Documented
Tested
Synchronized
```

---

# 71. Do Not Add Complexity for Its Own Sake

Blockchain, cryptography, IPFS and DID technology should serve actual product needs.

Do not add a mechanism merely because it sounds advanced.

For every technical component ask:

```text
What trust problem does it solve?
What privacy problem does it solve?
What portability problem does it solve?
What integrity problem does it solve?
```

If it solves none of these, reconsider it.

---

# 72. Final Execution Directive

The next processing step should produce a **coherent implementation**, not just more documentation.

Primary objective:

```text
Preserve the PassKhadam product objective
        +
Implement the canonical workflows
        +
Enforce real authorization
        +
Make cryptographic claims truthful
        +
Preserve privacy
        +
Test failure conditions
        +
Keep architecture replaceable
        +
Keep documentation synchronized
```

The implementation team/agent must not:

```text
Invent unsupported product features
Remove existing core functionality silently
Bypass role permissions
Store raw sensitive PII on-chain
Fake blockchain/IPFS verification results
Claim production deployment when using development infrastructure
Treat a demo role switcher as security
Treat mock Aadhaar as a live government authority
```

---

# 73. Final Product Definition

> **PassKhadam is a web-based decentralized identity platform that enables migrant workers to establish a verified digital identity, receive and control verifiable credentials, present cryptographic proof through downloadable QR images, be verified by authorized employers and government authorities without camera scanning, build portable employment history, and access eligible welfare services across states through privacy-conscious, auditable verification.**

---

# 74. Execution Status

```text
Document:
PassKhadam_Next_Processing_Execution_Guide_v1.0.md

Purpose:
Execution control / handoff

Product:
PASSKHADAM

Primary Runtime:
Local Hardhat EVM

Frontend Blockchain:
Web3.js

Backend Blockchain:
Web3.py

Backend:
FastAPI

Frontend:
React

Authentication:
Firebase + development adapter

Decentralized Storage:
IPFS Provider Abstraction

Encryption:
AES-256-GCM

Presentation Signature:
Ed25519

Credential Integrity:
SHA-256

EVM Hashing:
Keccak-256 where applicable

Primary Roles:
Worker
Employer
Government
Admin
Aadhaar Authority

QR:
Upload-based web verification
No camera requirement

Current Baseline:
Production-oriented architecture with local development infrastructure

Change Policy:
Changes are allowed when explicitly justified and synchronized.
