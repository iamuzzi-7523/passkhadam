# PASSKHADAM

## Decentralized Identity Verification Platform for Migrant Workers

### Product Specification — Version 0.2

---

## 0. Document Purpose

This document defines the current baseline product specification for **PASSKHADAM**, a fully web-based decentralized identity platform for migrant workers.

It describes:

- Product objective and value proposition
- Core product principles
- Roles and responsibilities
- End-to-end user lifecycle
- Aadhaar verification
- DID and Verifiable Credential issuance
- Credential storage and blockchain anchoring
- QR identity presentation and **QR image upload verification**
- Employer onboarding and authorization
- Worker verification by employers
- Employment creation and lifecycle management
- Government worker verification
- Welfare eligibility and benefit disbursement
- Cross-state identity and claim verification
- Platform administration and governance
- Mock Aadhaar Authority / Aadhaar API Management
- Role-based access control
- Smart-contract responsibilities
- Data architecture
- Security and privacy boundaries
- Product statuses
- Technical processing/animation sequences
- Configurable aspects of the product

This specification is the **current proposed baseline** and is not a rigid implementation contract.

> **Any changes to steps, fields, permissions, architecture, technologies, business rules, verification methods, credential structures, storage strategy, or workflows are entertained whenever a change improves security, privacy, usability, scalability, interoperability, regulatory compatibility, maintainability, or overall product quality.**

---

# 1. Product Objective

Migrant workers moving between states can lose practical access to employment opportunities, identity-dependent services and welfare benefits because identity, employment history and entitlement information may remain fragmented across organizations and state systems.

PASSKHADAM is intended to address this fragmentation by creating a **portable, verifiable and privacy-conscious digital identity** for a worker.

The worker should be able to:

1. Create and verify a PASSKHADAM account.
2. Establish a government-verified identity.
3. Receive a decentralized identity (DID).
4. Receive digitally signed Verifiable Credentials.
5. Maintain those credentials in a personal credential wallet.
6. Generate a portable identity presentation.
7. Share the presentation with authorized employers and government authorities.
8. Have the presentation verified through a **web upload workflow rather than camera scanning**.
9. Build portable employment history.
10. Access applicable government benefits across participating states.
11. Maintain a trusted identity even after moving from one state or employer to another.

The central product proposition is:

> **One trusted worker identity that can travel across employers, states and government services.**

---

# 2. Product Scope

PASSKHADAM consists of five primary roles:

1. **User / Worker**
2. **Platform Admin**
3. **Government Authority**
4. **Employer**
5. **Aadhaar API Management / Identity Authority**

The platform uses a shared identity and verification layer rather than treating these portals as unrelated applications.

---

# 3. Technology Baseline

The minimum intended technology stack is:

| Technology                           | Primary Responsibility                                             |
| ------------------------------------ | ------------------------------------------------------------------ |
| React                                | Web frontend                                                       |
| FastAPI                              | Backend, APIs and business logic                                   |
| Firebase Authentication              | Account authentication, email verification and phone OTP           |
| Solidity                             | Smart contracts                                                    |
| Web3.js                              | Blockchain interaction                                             |
| IPFS                                 | Decentralized storage for encrypted credential payloads            |
| EVM-compatible blockchain            | Identity, credential, employment, organization and welfare records |
| Aadhaar API / Mock Aadhaar Authority | Government identity verification                                   |
| SQLite / PostgreSQL                  | Off-chain application and operational data                         |

### Technology Flexibility

The above technologies are the minimum baseline. A technology may be replaced, supplemented or restructured when a demonstrably better implementation is required.

For example:

- Web3.js may be supplemented or replaced by another EVM client library if architecture requires it.
- SQLite may be used initially and PostgreSQL introduced when stronger operational persistence is required.
- A mock Aadhaar service may be replaced by a compliant external identity verification provider in a real deployment.
- Additional cryptographic or identity standards may be introduced to improve interoperability.

Any such change must preserve the product objective.

---

# 4. Core Product Principles

## 4.1 Worker-Centric Identity

The worker is the primary subject of the identity.

The identity should not depend on one employer remaining the worker's permanent authority.

## 4.2 Portability

A worker's identity should remain usable when the worker:

- Moves to another state
- Changes employer
- Ends employment
- Starts a new employment
- Applies for services through another authorized government authority

## 4.3 Verifiability

Authorized verifiers should be able to cryptographically determine whether a credential or identity presentation is valid.

## 4.4 Privacy

Sensitive personal information should not be unnecessarily stored on-chain or exposed to verifiers.

## 4.5 Least-Privilege Access

Employers and government authorities should see only the information necessary and authorized for their use case.

## 4.6 Auditability

Important organizational, employment and welfare actions should produce an auditable record.

## 4.7 Decentralization Where It Adds Value

Blockchain and IPFS should be used for trust, integrity, portability and verification rather than as a reason to place every piece of application data on-chain.

---

# 5. High-Level Product Architecture

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

# 6. Logical System Architecture

```text
                           React Web Application
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            ▼                     ▼                     ▼
       Worker Portal         Employer Portal       Government Portal
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  │
                           Platform API Layer
                                FastAPI
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             ▼                    ▼                    ▼
       Identity Service     Credential Service   Authorization Service
             │                    │                    │
             ├───────────────┐    │                    │
             │               │    │                    │
             ▼               ▼    ▼                    ▼
       Mock Aadhaar API    Database IPFS           Organization DB
                                  │
                                  ▼
                           Blockchain Service
                                Web3.js
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                     ▼
     WorkerIdentity         CredentialRegistry    OrganizationRegistry
        Registry
            │
            ├──────────────┐
            ▼              ▼
     EmploymentRegistry  WelfareSchemeRegistry
```

---

# 7. Separation of Data Responsibilities

The product should separate information into three major storage layers.

## 7.1 Application Database

Used for application and operational data such as:

- User account references
- Firebase user identifiers
- Worker profile data
- Organization records
- Admin information
- Operational workflow state
- Requests
- UI preferences
- Non-blockchain application metadata
- Mock Aadhaar authority operational data where applicable

## 7.2 IPFS

Used for decentralized content-addressed storage of approved encrypted objects such as:

- Encrypted Verifiable Credential payloads
- Credential documents
- Other approved decentralized documents

The IPFS content should be encrypted before pinning when it contains sensitive information.

## 7.3 Blockchain

Used for tamper-evident references and shared trust state such as:

- DID references
- Credential hashes
- Credential issuer references
- Credential status
- Credential revocation state
- Employment record references / hashes
- Benefit claim references / hashes
- Organization authorization state
- Relevant audit events
- Blockchain transaction references

### Data that should not be placed directly on the blockchain

Unless a future architecture explicitly and safely determines otherwise, do not put the following as raw data on-chain:

- Full Aadhaar number
- Full address
- Phone number
- Email address
- Unnecessary personally identifiable information (PII)
- Large credential documents

---

# 8. Role Definitions

## 8.1 User / Worker

The worker owns and uses the portable identity.

Primary responsibilities and capabilities:

- Register
- Verify email
- Verify phone
- Complete profile
- Verify government identity
- Receive DID
- Receive credentials
- View credential wallet
- View identity status
- Generate QR identity presentation
- Download QR presentation
- Share authorized identity information
- View employment history
- View benefit history
- Manage account and security settings

## 8.2 Platform Admin

The admin is the governance and authorization authority for participating organizations and platform configuration.

Primary capabilities:

- Approve employers
- Approve government authorities
- Review organization documents
- Grant permissions
- Manage employment categories
- Review requests
- Suspend organizations
- Reactivate organizations
- Manage credential issuer authorization
- View audit logs
- Manage governance configuration

The admin does **not** manually become the worker's identity issuer simply by being a platform administrator unless explicitly configured as an authorized issuer.

## 8.3 Government Authority

Government users can:

- Upload worker QR presentations
- Verify worker identities
- Verify authorized credentials
- View authorized employment information
- Check welfare eligibility
- Initiate benefit claims
- Record benefit disbursements
- Review authorized claim history
- Perform cross-state verification

Access is controlled by government organization and officer permissions.

## 8.4 Employer

Employers can:

- Register an organization
- Submit documents for approval
- Request employment categories
- Upload worker QR images
- Verify worker credentials
- View authorized worker information
- Create employment records
- Update employment status
- End / remove workers from active employment
- Maintain employment history
- Request additional employment categories

Employers can only create or manage employment categories and functions authorized by the platform.

## 8.5 Aadhaar API Management / Identity Authority

This role represents the identity verification service and its management layer.

Primary capabilities:

- Manage mock Aadhaar records
- Handle verification requests
- Manage API credentials / access
- View verification logs
- Monitor service status
- Maintain the identity verification service
- Manage mock authority configuration

For the current architecture, this role is represented by a **Mock Aadhaar Authority / Mock Aadhaar API**.

---

# 9. Overall Product Lifecycle

The complete initial lifecycle is:

```text
Worker Registration
        ↓
Email Verification
        ↓
Phone Verification
        ↓
Worker Profile Creation
        ↓
Aadhaar Verification
        ↓
Identity Verified
        ↓
DID Generation
        ↓
DID Document Generation
        ↓
Verifiable Credential Generation
        ↓
Credential Signing
        ↓
Credential Integrity Hash
        ↓
Credential Encryption
        ↓
Encrypted Credential Stored on IPFS
        ↓
DID / Credential Reference Anchored on Blockchain
        ↓
Worker Identity Wallet Activated
        ↓
Worker Generates QR Identity Presentation
        ↓
Employer / Government Uploads QR Image
        ↓
Verification Engine Processes QR
        ↓
DID Resolution
        ↓
Credential Resolution
        ↓
Signature Verification
        ↓
Integrity Verification
        ↓
Credential Status / Revocation Check
        ↓
Organization Authorization Check
        ↓
Employment or Welfare Action
        ↓
Immutable / Auditable Record Created
```

**This is the current baseline only. Any changes in steps are entertained.**

---

# 10. USER / WORKER PORTAL

## 10.1 Registration

The worker begins by creating a PASSKHADAM account through the web application.

### Registration Fields

- Full Name
- Email Address
- Phone Number
- Password
- Confirm Password

The worker submits the registration form.

---

# 11. Authentication and Contact Verification

Firebase Authentication is the proposed service for:

- Account authentication
- Email verification
- Phone OTP verification
- Session management
- Authentication tokens

### Flow

```text
Create Account
      ↓
Send Email Verification
      ↓
Email Verified
      ↓
Send Phone OTP
      ↓
Phone Verified
      ↓
Account Activated
```

PASSKHADAM should not treat a user as fully identity-verified merely because authentication succeeded.

At this stage:

```text
Email Verified ✓
Phone Verified ✓
Identity Verified ✕
```

The backend should verify the Firebase authentication token before allowing protected account operations.

---

# 12. Worker Profile Creation

After successful account verification, the worker completes the profile.

### Potential fields

- Full Name
- Date of Birth
- Gender
- Phone Number
- Email
- Current State
- Origin State
- Address
- Worker Category
- Optional Skill Information

These profile fields are **configurable** and should not automatically be interpreted as mandatory unless the product rules explicitly require them.

### Initial Account State

```text
EMAIL VERIFIED ✓
PHONE VERIFIED ✓
PROFILE COMPLETED ✓
IDENTITY VERIFIED ✕
```

---

# 13. Government Identity Verification

The worker selects:

> **Verify Government Identity**

The worker is presented with an Aadhaar verification form.

### Input

- Aadhaar Number
- Name exactly as registered with Aadhaar

The user submits the verification request.

---

# 14. Aadhaar Verification Architecture

The main PASSKHADAM application should interact with the Aadhaar identity service through an API.

The intended architecture is:

```text
                       PASSKHADAM
                           │
                           │ Secure Verification Request
                           ▼
                  Mock Aadhaar API
                           │
                           ▼
                  Validation Engine
                           │
               ┌───────────┴───────────┐
               │                       │
               ▼                       ▼
         Mock Aadhaar DB        Verification Rules
               │                       │
               └───────────┬───────────┘
                           ▼
                   Verification Result
                           │
                           ▼
                    PASSKHADAM Backend
```

The PASSKHADAM backend should not directly access the mock Aadhaar database as though it were an internal table.

The mock authority should behave as an external identity-verification authority.

---

# 15. Aadhaar Verification Logic

Before Aadhaar verification proceeds, the PASSKHADAM account should have:

```text
Email Verified ✓
Phone Verified ✓
```

The verification service evaluates the submitted identity details.

Baseline matching:

```text
Aadhaar Number Match?
        +
Name Match?
        ↓
Identity Record Valid?
        ↓
Verification Result
```

If the identity authority supports additional approved checks, additional demographic validation may be introduced.

The result is returned to PASSKHADAM without unnecessarily copying the complete government identity record into the application.

---

# 16. Aadhaar Verification Outcome

## Successful Verification

The user sees:

```text
Government Identity

✓ Aadhaar Verified
✓ Name Matched
✓ Aadhaar Number Matched
✓ Identity Record Valid

Identity verification completed successfully.
```

A masked Aadhaar number may be shown:

```text
XXXX XXXX 4821
```

## Verified Aadhaar Document Visual

After successful verification, the worker should also receive a **verified government-document visual / mock Aadhaar card representation** in the user portal.

Example:

```text
VERIFIED GOVERNMENT DOCUMENT

┌──────────────────────────────────────┐
│             Aadhaar                  │
│                                      │
│ Name: Mohammed Uzair                 │
│                                      │
│ Aadhaar: XXXX XXXX 4821              │
│                                      │
│ Status: ✓ VERIFIED                   │
│ Status: ✓ VALID                      │
└──────────────────────────────────────┘
```

The visual is a product representation for the verified identity record and should not be presented as an official document if it is a mock representation.

## Failed Verification

Possible failure states include:

```text
Aadhaar number not found
Name mismatch
Aadhaar record invalid / inactive
Verification service unavailable
Identity details could not be validated
```

The user may correct the submitted information and retry according to configured security and retry rules.

---

# 17. Identity Binding

Successful contact verification and successful Aadhaar verification are combined within the PASSKHADAM identity service.

Conceptually:

```text
Verified PASSKHADAM Account
        +
Successful Government Identity Verification
        ↓
Worker Identity Binding
        ↓
Decentralized Identity Creation
```

The Aadhaar service does not need to verify the user's email and phone itself unless the identity authority implementation explicitly supports and requires that behavior.

Instead:

```text
Firebase
 ├── Email verified
 └── Phone verified

Mock Aadhaar API
 ├── Aadhaar number verified
 └── Name verified

PASSKHADAM Identity Service
 └── Binds the verification results to one account
```

---

# 18. Decentralized Identity Creation

After successful government identity verification, PASSKHADAM creates the worker's decentralized identity.

Example:

```text
did:PASSKHADAM:worker:{unique-hash}
```

A DID Document is created containing information necessary to establish the decentralized identity and associated verification methods.

Example concept:

```json
{
  "id": "did:PASSKHADAM:worker:8f29...",
  "verificationMethod": [
    {
      "id": "did:PASSKHADAM:worker:8f29...#key-1",
      "type": "EcdsaSecp256k1RecoveryMethod2020"
    }
  ]
}
```

The DID should not expose the worker's Aadhaar number or other unnecessary personal information.

---

# 19. Verifiable Credential Creation

After DID creation, PASSKHADAM generates a digitally signed **Worker Identity Verifiable Credential**.

Conceptual fields:

```text
Credential Type:
Worker Identity Credential

Credential Subject:
Worker DID

Issuer:
Authorized Identity Authority

Status:
Active

Issued At:
Timestamp
```

The credential represents the result of identity verification.

It should not become a second full Aadhaar database.

---

# 20. Current Proposed Identity Issuance Processing Sequence

The identity issuance interface may display the following live processing sequence:

```text
🔐 Establishing secure identity verification channel...
📋 Validating Aadhaar demographic credentials...
🆔 Generating W3C DID Document: did:PASSKHADAM:worker:{hash}...
📄 Formatting W3C Verifiable Credential representation...
🔑 Preparing typed credential signing payload...
✍️ Signing credential using authorized issuer key with secp256k1 / EIP-712 where implemented...
🔍 Computing SHA-256 integrity hash of credential payload...
📦 Encrypting credential payload using authenticated encryption...
🌐 Pinning encrypted Verifiable Credential to IPFS...
📌 IPFS CID generated & pinned: QmPK{hash}...
⛓️ Anchoring DID / credential reference on WorkerIdentityRegistry.sol...
✅ Block confirmed! Identity record anchored on EVM network.
```

### Current Cryptographic Wording

The original concept referenced:

> AES-256 Fernet

That terminology should be corrected.

**Fernet is not AES-256.** The standard Fernet construction uses AES-128-CBC with HMAC-SHA256.

Therefore the current specification should use either:

```text
Fernet authenticated encryption
```

or, if an explicit AES-256 construction is selected:

```text
AES-256-GCM
```

The final implementation should use one clearly defined construction rather than mixing the two names.

---

# 21. EIP-712 / Signature Model

EIP-712 should be treated as a typed structured-data signing mechanism rather than as the entire Verifiable Credential format.

Proposed flow:

```text
Create Verifiable Credential
        ↓
Create canonical / implementation-defined signing representation
        ↓
Create typed signing payload
        ↓
Sign typed payload using secp256k1 / EIP-712
        ↓
Attach signature / proof information
        ↓
Generate integrity hash
```

The exact VC proof format and signing representation remain configurable during implementation.

---

# 22. Credential Storage

The credential architecture separates credential content from blockchain trust state.

## Credential Content

```text
Verifiable Credential
        ↓
Encryption
        ↓
IPFS
        ↓
CID
```

## Blockchain

```text
Worker DID
Credential Hash
Credential Type
Issuer
Issue Timestamp
IPFS CID / Reference
Credential Status
Revocation Information
```

The blockchain acts primarily as a tamper-evident trust and integrity layer.

---

# 23. Identity Issuance Success State

After successful issuance, the user sees:

```text
IDENTITY VERIFIED ✓

DID:
did:PASSKHADAM:worker:8f29...

Identity Credential:
VALID

Blockchain Status:
ANCHORED

IPFS Status:
PINNED
```

---

# 24. Worker Credential Wallet

The worker receives a credential wallet.

Example:

```text
MY CREDENTIALS

┌─────────────────────────────────┐
│ Identity Credential             │
│ ✓ VERIFIED                      │
│ Issuer: Identity Authority      │
│ Status: Active                  │
│                                 │
│ [View] [Share]                  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Skill Credential                │
│ ✓ VERIFIED                      │
│ Skill: Mason                    │
│ Status: Active                  │
│                                 │
│ [View] [Share]                  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Safety Certification            │
│ ✓ VERIFIED                      │
│ Status: Active                  │
│                                 │
│ [View] [Share]                  │
└─────────────────────────────────┘
```

The exact credential categories are configurable.

---

# 25. Identity Presentation

The worker selects:

> **Share Identity**

The platform generates a cryptographic identity presentation containing the information necessary for an authorized verifier.

The worker sees:

```text
IDENTITY PRESENTATION

[ QR CODE ]

Presentation Status:
ACTIVE

Expires:
05:00

[Download QR]
[Download Presentation]
```

The worker can download the QR image.

---

# 26. QR Verification Model

PASSKHADAM is a **web-based product**.

Camera-based QR scanning is **not required** for the core verification flow.

Instead, Employer and Government portals use:

> **Upload Worker QR**

### Verification entry point

```text
UPLOAD WORKER QR

[ Drag & Drop QR Image Here ]

or

[ Choose QR Image ]

[ Verify Identity ]
```

The uploaded QR image is decoded by the platform.

The system then verifies the cryptographic presentation contained in the QR payload.

---

# 27. Employer Portal

The employer lifecycle begins with registration.

## 27.1 Employer Registration Information

The employer submits:

- Company / Organization Name
- Registration Number
- Business Address
- Contact Person
- Official Email
- Phone Number
- Business Type
- Nature of Business
- Employment Categories Requested
- Employment Levels Requested
- Nature of Requested Employment
- Expected Workforce / Number of Workers
- Supporting organization documents

Example employment categories:

```text
Mason
Electrician
Plumber
Carpenter
Welder
Machine Operator
General Labour
```

The exact category taxonomy is configurable.

---

# 28. Employment Categories, Levels and Nature

Employer registration should capture more than just a job title.

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

Potential employment levels:

```text
Skilled
Semi-Skilled
Unskilled
Supervisory
Other Configurable Levels
```

Potential nature-of-employment values:

```text
Permanent
Contract
Temporary
Seasonal
Project-Based
Other Configurable Types
```

These classifications are configurable.

---

# 29. Employer Admin Approval

A newly registered employer remains:

```text
PENDING ADMIN REVIEW
```

The admin reviews:

```text
Company legitimacy
Business details
Registration information
Requested employment categories
Requested employment levels
Nature of employment
Supporting documents
Organization contact details
```

The admin can:

```text
Approve
Reject
Request More Information
Suspend
```

Only an approved employer receives an active employer account.

---

# 30. Employer Credential Delivery

After approval:

```text
Admin Approval
      ↓
Employer Organization Created
      ↓
Employer Permissions Assigned
      ↓
Login / Account Activation Information Generated
      ↓
Credentials / Activation Information Sent
to the Employer's Registered Email
      ↓
Employer Account Activated
```

The exact credential-delivery mechanism may be changed later for stronger security, such as password setup links or identity-bound activation.

Credentials should not be sent as insecure plaintext passwords if a safer activation mechanism is available.

---

# 31. Employer Identity and Permissions

The admin assigns or authorizes:

```text
Employer ID
Organization Identity
Authorized Employment Categories
Authorized Employment Levels
Permission Scope
Account Status
Blockchain Organization Identity / Wallet Reference
```

Example:

```text
ABC Construction Pvt Ltd

Approved Categories:

✓ Mason
✓ Electrician
✓ Plumber
```

The employer can only create employment records within its authorized scope.

---

# 32. Employer Request for Additional Employment Category

Suppose the employer wants to hire:

```text
Heavy Machinery Operator
```

but this category is not currently authorized.

The employer selects:

> **Request Additional Employment Category**

Workflow:

```text
Employer
   ↓
Additional Category Request
   ↓
Admin Review
   ↓
Approve / Reject / Request More Information
   ↓
Employer Permission Updated
```

Until approval:

```text
Heavy Machinery Operator → NOT AUTHORIZED
```

The employer must not bypass this restriction through its frontend or API.

Authorization must be enforced in the backend and, where relevant, blockchain governance layer.

---

# 33. Employer Dashboard

Suggested employer navigation:

```text
Dashboard
Workers
Verify Worker
Employment
Employment History
Requests
Company Profile
Audit / Activity
```

Dashboard may show:

```text
Active Workers
Completed Employments
Pending Worker Verifications
Authorized Employment Categories
Pending Admin Requests
```

---

# 34. Employer Worker Verification

The employer selects:

> **Verify Worker**

The employer uploads the worker's QR image.

```text
UPLOAD WORKER QR

[ Drag & Drop QR Image Here ]

or

[ Choose QR Image ]

[ Verify Identity ]
```

No camera is required.

---

# 35. Employer Verification Processing Sequence

Current proposed sequence:

```text
🔍 Decoding uploaded QR cryptographic presentation...
📂 Resolving DID Document from did:PASSKHADAM decentralized registry...
⛓️ Querying WorkerIdentityRegistry.sol on the EVM ledger...
📌 Resolving encrypted credential IPFS CID: QmPK{hash}...
🔓 Decrypting / processing encrypted Verifiable Credential payload...
🔐 Verifying ECDSA secp256k1 issuer signature / configured proof...
🛡️ Checking credential validity and revocation status...
🏗️ Checking BOCW safety certification & skill category...
📋 Checking employer authorization for the requested employment category...
✅ Worker identity cryptographically verified.
✅ Authorized zero-PII verification result generated.
```

The exact cryptographic implementation can change if a better interoperable standard is adopted.

---

# 36. Employer Verification Result

The employer should receive the minimum information required for its purpose.

Example:

```text
WORKER VERIFICATION

Identity:
✓ VERIFIED

Worker DID:
did:PASSKHADAM:worker:8f29...

Identity Credential:
✓ VALID

Skill:
Mason ✓

BOCW Safety Certification:
✓ VALID

Employment Eligibility:
✓ ELIGIBLE
```

Sensitive information should not automatically be exposed.

Potentially restricted information includes:

- Full Aadhaar number
- Full address
- Personal contact details
- Unnecessary personal information

---

# 37. Zero-PII Verification Principle

The platform should support a presentation model where an employer can verify required facts without receiving unnecessary PII.

Conceptually:

```text
Worker possesses identity
        ↓
Worker presents proof
        ↓
Employer verifies required claims
        ↓
Employer receives authorized result
        ↓
Unnecessary PII remains undisclosed
```

The phrase **zero-PII verification** should only be used where the actual implementation truly prevents disclosure of personally identifying information beyond what is intentionally authorized.

---

# 38. Employer Worker Profile

After successful verification, the employer can access information permitted by its role.

Possible information:

```text
Verified Identity
Worker DID
Relevant Skills
Relevant Certifications
BOCW Certification
Authorized Employment History
Current Employment Status
Credential Status
```

The employer should not receive unrestricted access to every worker attribute merely because identity verification succeeded.

---

# 39. Employment Creation

After successful verification, the employer selects:

> **Offer Employment**

Employment information can include:

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

Example:

```text
Worker:
did:PASSKHADAM:worker:8f29...

Position:
Mason

Employment Level:
Skilled

Nature:
Construction

Employment Type:
Contract

Location:
Bengaluru

Start Date:
05 Oct 2026

Expected End Date:
05 Apr 2027
```

The employer submits the employment record.

---

# 40. Employment Authorization Check

Before creating an employment record:

```text
Employer Authorized?
        ↓
Employment Category Authorized?
        ↓
Employment Level Authorized?
        ↓
Nature of Employment Permitted?
        ↓
Worker Credential Valid?
        ↓
Create Employment Record
```

This validation must occur on the backend.

---

# 41. Employment Logging Processing Sequence

Current proposed sequence:

```text
📝 Preparing verifiable employment stint record...
🏢 Attaching employer DID / organization identity...
🏗️ Attaching construction site and work-site metadata...
👷 Assigning authorized employment category and level...
📋 Validating employer permissions...
🔐 Signing employment record with the authorized employer blockchain identity / wallet using EIP-712 where implemented...
⛓️ Writing employment engagement to the employment ledger...
✅ Employment stint anchored.
📦 Worker's portable employment history updated.
```

The exact storage model may use a complete record off-chain plus an on-chain hash/reference rather than placing all employment data directly on-chain.

---

# 42. Employment History

The worker should retain the historical employment record even after employment ends.

Example:

```text
EMPLOYMENT HISTORY

ABC Construction
Mason
Skilled
Bengaluru
05 Oct 2026 – Present
Status: ACTIVE

XYZ Infrastructure
General Labour
Hyderabad
10 Jan 2026 – 30 Sep 2026
Status: COMPLETED
```

The employer's current active worker list and the worker's historical employment record are separate concepts.

---

# 43. Ending / Removing Worker Employment

An employer should be able to end a worker's active employment.

Workflow:

```text
Employer
   ↓
Select Active Worker
   ↓
End Employment / Remove From Active Workers
   ↓
Select Employment Outcome
   ├── Completed
   ├── Terminated
   ├── Dismissed
   ├── Resigned
   └── Suspended
   ↓
Record Employment Event
   ↓
Remove Worker From Active Worker List
   ↓
Preserve Historical Employment Record
```

Removing a worker from the employer's active workforce **must not delete the worker's historical employment record**.

---

# 44. Employment Statuses

Baseline statuses:

```text
ACTIVE
COMPLETED
TERMINATED
DISMISSED
RESIGNED
SUSPENDED
```

The exact status taxonomy is configurable.

Every meaningful status transition should generate an auditable event.

Example:

```text
ABC Construction
Position: Mason

05 Oct 2026
Employment Started

12 Dec 2026
Employment Status:
TERMINATED
```

---

# 45. Government Portal

The Government portal is designed for authorized government authorities and officers.

Suggested navigation:

```text
Dashboard
Worker Verification
Benefits
Eligibility
Claims
Employment Verification
Cross-State Verification
Claim History
Audit Records
```

---

# 46. Government Onboarding

Government authorities should be registered or provisioned through a governance workflow.

Baseline workflow:

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

Different government departments or authorities may receive different permission levels.

---

# 47. Government Worker Verification

Government officers use:

> **Upload QR**

not camera scanning.

Interface:

```text
UPLOAD WORKER QR

[ Upload QR Image ]

[ Verify Worker ]
```

The uploaded QR contains the worker's cryptographic identity presentation.

---

# 48. Government Verification Processing Sequence

Current proposed sequence:

```text
🔍 Decoding uploaded QR cryptographic presentation payload...
📂 Resolving DID Document from did:PASSKHADAM registry...
⛓️ Querying WorkerIdentityRegistry.sol on the EVM ledger...
📌 Resolving encrypted IPFS CID: QmPK{hash}...
🔓 Decrypting / processing encrypted Verifiable Credential payload...
🔐 Verifying ECDSA secp256k1 issuer signature / configured proof...
📋 Checking credential validity and revocation status...
🌐 Cross-referencing authorized origin-state KYC registry (SQLite-backed)...
✅ Identity cryptographically verified.
✅ Signature valid.
✅ DID / identity reference confirmed on-chain.
```

The exact implementation may be modified for interoperability, privacy or standards compliance.

---

# 49. Government Verification Result

Example:

```text
WORKER IDENTITY

Identity:
✓ VERIFIED

DID:
did:PASSKHADAM:worker:8f29...

Origin State:
Karnataka

Current State:
Maharashtra

Identity Credential:
VALID ✓

Relevant Worker Credentials:
VALID ✓
```

The current state may come from the worker's authorized profile or a relevant government record depending on the final data architecture.

---

# 50. Government Employment Verification

Government authorities may access authorized employment information.

Example:

```text
Current Employment:
ABC Construction

Role:
Mason

Level:
Skilled

Status:
ACTIVE

Start Date:
05 Oct 2026

Location:
Bengaluru
```

Historical employment information is visible only according to the government's authorization scope.

---

# 51. Welfare / Benefit Eligibility

Once the worker is verified, the government portal evaluates applicable benefit schemes.

Example:

```text
BENEFIT ELIGIBILITY

✓ Construction Worker Welfare
✓ Migrant Worker Assistance
✓ Accident Protection Scheme
✕ State Resident-Only Scheme
```

Eligibility can evaluate:

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

The exact eligibility rules are configurable.

---

# 52. Cross-State Identity

A key PASSKHADAM capability is allowing one verified worker identity to remain usable across participating states.

Example:

```text
Worker Origin:
Karnataka

Current State:
Maharashtra
```

The Maharashtra government should not need the worker to create a completely new PASSKHADAM identity.

Instead:

```text
Worker DID
   ↓
Existing Credentials
   ↓
Cryptographic Verification
   ↓
Authorized Cross-State Information
   ↓
Eligibility Check
   ↓
Benefit / Service
```

---

# 53. Origin-State KYC Registry

The current proposed government verification architecture may use an origin-state KYC registry.

For the baseline implementation this may be:

```text
Origin-State KYC Registry
        ↓
SQLite-backed operational registry
```

This registry can hold authorized information needed for cross-state verification.

Its exact schema and future storage engine are configurable.

---

# 54. Benefit Claim

After eligibility is established, an authorized government officer may initiate a benefit claim.

Example:

```text
Worker:
did:PASSKHADAM:worker:8f29...

Scheme:
Migrant Worker Assistance

Amount:
₹XXXX

State:
Maharashtra

Claim Type:
Welfare Disbursement
```

Before final submission, the system performs all configured eligibility and duplication checks.

---

# 55. Benefit Disbursement Processing Sequence

Current proposed sequence:

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

The **30-day policy is a baseline rule** and should be configurable by scheme.

A future implementation may use different cooldown periods depending on the benefit.

---

# 56. Cross-State Duplicate Claim Prevention

The system should check whether an equivalent or conflicting benefit claim already exists across authorized state registries.

Conceptual flow:

```text
Current-State Claim
        ↓
Worker Identity
        ↓
Existing Claim Search
        ↓
Origin State
        ↓
Current State
        ↓
Other Authorized State Registries
        ↓
Duplicate / Conflict Detection
```

A claim should be blocked or routed for review when configured rules determine that an equivalent claim already exists.

---

# 57. Government Wallet Authorization

A government officer must not be able to create blockchain records simply because they can log into the web portal.

The proposed authorization model is:

```text
Government Organization
        ↓
Authorized Officer
        ↓
Officer Permission
        ↓
Registered Blockchain Wallet / Identity
        ↓
Blockchain Transaction
```

Transactions should be signed by the authorized blockchain identity / wallet.

The exact wallet custody model can be changed to improve security.

---

# 58. Admin Portal

The admin is the platform governance and authorization layer.

Admin navigation may include:

```text
Dashboard
Organizations
Employers
Government Authorities
Credential Issuers
Employment Categories
Requests
Permissions
Audit Logs
Platform Configuration
```

---

# 59. Admin Responsibilities

## 59.1 Organization Management

Manage:

```text
Employers
Government Authorities
Credential Issuers
```

## 59.2 Organization Approval

Admin can:

```text
Approve
Reject
Suspend
Reactivate
Request More Information
```

## 59.3 Permissions

Admin determines:

```text
What an organization can verify
What credential categories an organization can access
What employment categories an employer can create
What employment levels an employer can create
What government services an authority can access
What actions an officer can perform
```

## 59.4 Employment Category Management

Admin may:

```text
Create Category
Approve Category
Disable Category
Modify Category Rules
```

## 59.5 Credential Authority Management

Admin can control which authorized organizations are permitted to:

```text
Issue credentials
Verify credentials
Revoke credentials
```

depending on the credential governance model.

---

# 60. Credential Issuer Governance

Credential powers should be scoped.

Example:

```text
Identity Authority
    → Identity Credentials

Skill / Certification Authority
    → Skill / Safety Credentials

Employer
    → Its own employment records / employment credentials

Government Authority
    → Its own authorized benefit / welfare records
```

An organization should not be able to revoke or modify credentials it does not own or govern.

Examples:

```text
Employer cannot revoke a worker's government identity credential.

Employer cannot rewrite another employer's employment record.

Worker cannot fabricate a government-issued credential.

Government authority cannot arbitrarily rewrite a credential issued by another authority.
```

The exact governance model can change as the product matures.

---

# 61. Employer Admin Workflow

```text
Employer Registration
        ↓
Documents Submitted
        ↓
Admin Review
        ↓
Business Verification
        ↓
Requested Employment Categories Reviewed
        ↓
Employment Levels Reviewed
        ↓
Nature of Employment Reviewed
        ↓
Approval / Rejection
        ↓
Employer Account Activated
        ↓
Credentials / Activation Information Sent
        ↓
Permissions Applied
```

If rejected:

```text
Rejected
   ↓
Reason Provided
   ↓
Employer May Resubmit
```

---

# 62. Government Admin Workflow

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

---

# 63. Aadhaar API Management / Identity Authority

The Aadhaar API Management role is a service-level identity authority rather than a normal business user role.

For the present architecture, this is represented by a Mock Aadhaar Authority.

The mock service should simulate the behavior of an external identity verification provider.

---

# 64. Mock Aadhaar Authority

The mock Aadhaar system can contain:

```text
Mock Aadhaar Records
Identity Verification API
Verification Engine
API Access Management
Verification Logs
Service Status
```

Example internal record:

```text
Aadhaar Number:
XXXX XXXX 4821

Name:
Mohammed Uzair

Status:
ACTIVE

Verification:
AVAILABLE
```

The mock system can use a separate database.

---

# 65. Mock Aadhaar Website

A separate web interface may be created for the simulated authority.

Example:

```text
MOCK AADHAAR AUTHORITY

Overview
Aadhaar Records
Verification Requests
API Access
Logs
Service Status
```

The interface may show:

```text
Total Records
Active Records
Verification Requests
Successful Verifications
Failed Verifications
API Health
```

Example dashboard:

```text
AADHAAR AUTHORITY

Total Records          10,000
Active Records          9,842
Verification Requests   1,293
Successful               1,241
Failed                      52
API Status               ONLINE
```

---

# 66. Aadhaar API Verification Flow

```text
PASSKHADAM
    ↓
Secure Verification Request
    ↓
Mock Aadhaar API
    ↓
Record Lookup
    ↓
Name Match
    ↓
Aadhaar Number Match
    ↓
Record Status Validation
    ↓
Verification Response
    ↓
PASSKHADAM Identity Service
```

The API should return the minimum necessary verification result.

Example conceptual response:

```json
{
  "verified": true,
  "reference_id": "AAD-VRF-83921",
  "name_match": true,
  "identity_record_valid": true
}
```

The exact response schema is configurable.

---

# 67. Central Verification Engine

Employer and Government should not implement completely separate credential verification engines.

Instead:

```text
Employer Portal
       │
       ├──────────────┐
       │              │
Government Portal     │
       │              │
       └──────┬───────┘
              ▼
      Central Verification Service
              │
              ▼
       DID Resolution
              ↓
       Credential Resolution
              ↓
       Signature Verification
              ↓
       Integrity Verification
              ↓
       Revocation / Status Check
              ↓
       Organization Authorization
              ↓
       Role-Specific Result
```

This improves maintainability and consistency.

---

# 68. Shared Identity Verification Process

Baseline common verification flow:

```text
UPLOAD QR IMAGE
      ↓
Validate Uploaded File
      ↓
Decode QR
      ↓
Extract Cryptographic Presentation
      ↓
Resolve DID
      ↓
Resolve Credential / Credential Reference
      ↓
Resolve IPFS CID where applicable
      ↓
Retrieve Encrypted Credential
      ↓
Decrypt using configured secure mechanism
      ↓
Verify Credential Issuer Signature / Proof
      ↓
Verify Integrity Hash
      ↓
Check Revocation / Credential Status
      ↓
Check Verifier Authorization
      ↓
Return Authorized Verification Result
```

---

# 69. Worker QR Presentation — Functional Model

The QR should carry only the information required to locate or validate the presentation.

A conceptual presentation may include:

```text
Presentation ID
Worker DID
Credential Reference
Presentation Timestamp
Expiration Timestamp
Cryptographic Proof
Optional Nonce / Challenge
```

The QR should not be treated as a plain container for all worker data.

The exact presentation structure is configurable and may be changed to comply with a selected identity standard.

---

# 70. Presentation Expiration

Generated presentations should be capable of having an expiry period.

Example:

```text
Presentation Status:
ACTIVE

Expires:
05:00
```

This reduces the usefulness of an old screenshot or stale presentation.

Additional anti-replay measures such as nonce/challenge binding may be added during implementation.

---

# 71. Role-Based Access Control

## Worker

Can:

```text
Create Account
Verify Email
Verify Phone
Complete Profile
Verify Identity
Receive DID
Receive Credentials
View Credentials
View Employment History
Generate Identity QR
Download QR
View Benefit History
Manage Profile
Manage Sharing / Presentation
Manage Security Settings
```

## Admin

Can:

```text
Approve Employers
Approve Government Authorities
Manage Permissions
Manage Employment Categories
Manage Employment Levels / Rules
Manage Credential Issuers
Suspend Organizations
Reactivate Organizations
Review Requests
View Platform Audit Logs
```

## Employer

Can:

```text
Manage Company Profile
Upload Worker QR
Verify Workers
View Authorized Worker Information
View Authorized Credentials
Create Employment Records
Update Employment Status
End Employment
Remove Worker From Active Workers
View Authorized Employment History
Request Additional Employment Categories
```

## Government

Can:

```text
Upload Worker QR
Verify Worker Identity
View Authorized Credentials
Check Benefit Eligibility
Initiate Benefit Claims
Record Disbursements
Review Authorized Employment Information
Perform Cross-State Verification
View Authorized Claim History
```

## Aadhaar API Management

Can:

```text
Manage Mock Aadhaar Records
Handle Verification Requests
Manage API Access
View Verification Logs
Manage API Availability
Maintain Identity Verification Service
```

---

# 72. Worker Permissions vs Organization Permissions

The product should distinguish between:

```text
Identity ownership
```

and:

```text
Verification authority
```

The worker owns or controls the use of their presentation, while authorized issuers and registries determine whether their credentials are valid.

An employer's ability to verify does not make the employer the owner of the worker's identity.

---

# 73. Core Smart Contract Layer

The blockchain layer can be separated into multiple Solidity contracts.

## 73.1 WorkerIdentityRegistry.sol

Responsible for:

```text
DID Registration
DID Resolution References
Credential Hash References
Credential Status
Revocation State / References
```

Potential functions:

```text
registerDID()
updateDIDReference()
registerCredentialHash()
setCredentialStatus()
revokeCredential()
isCredentialValid()
```

Exact functions may change.

---

# 74. CredentialRegistry.sol

Responsible for:

```text
Credential Issuance References
Credential Status
Credential Revocation
Issuer References
Credential Integrity
```

Potential functions:

```text
registerCredential()
revokeCredential()
getCredentialStatus()
isCredentialValid()
```

---

# 75. OrganizationRegistry.sol

Responsible for:

```text
Employer Registration
Government Organization Registration
Organization Status
Organization Permissions
Authorized Categories
Authorized Blockchain Identity / Wallet Reference
```

Potential functions:

```text
registerOrganization()
approveOrganization()
suspendOrganization()
setPermission()
setAuthorizedCategory()
isOrganizationAuthorized()
```

---

# 76. EmploymentRegistry.sol

Responsible for:

```text
Employment Creation
Employment Status
Employment History
Employer Identity
Worker DID Reference
Employment Hash / Reference
```

Potential functions:

```text
createEmployment()
updateEmploymentStatus()
getEmploymentRecord()
getWorkerEmploymentHistory()
```

The full employment payload may remain off-chain while its cryptographic hash/reference is anchored on-chain.

---

# 77. WelfareSchemeRegistry.sol

Responsible for:

```text
Scheme Registration
Eligibility Rules / References
Claim Records
Claim Status
Cooldown Rules
Duplicate Claim Checks
```

Potential functions:

```text
registerScheme()
checkEligibility()
recordClaim()
checkCooldown()
checkDuplicateClaim()
```

Exact business logic may remain partly off-chain for flexibility while critical claim references are anchored on-chain.

---

# 78. Optional Access-Control Contract

An additional contract may be introduced:

```text
AccessControl.sol
```

or access control may be implemented through standard Solidity authorization mechanisms.

Potential responsibilities:

```text
Platform Admin Roles
Issuer Roles
Government Roles
Employer Roles
Authorized Wallets
Contract-Level Permissions
```

The final implementation can use OpenZeppelin access-control patterns or another secure mechanism.

---

# 79. Credential Revocation Model

Credential validity should be independently checkable.

Baseline states:

```text
PENDING
ACTIVE
EXPIRED
REVOKED
SUSPENDED
```

Revocation authority must depend on the credential type.

Example:

```text
Identity Credential
→ Authorized identity issuer

Skill Credential
→ Authorized skill / certification issuer

Employment Record
→ Issuing employer for its own record

Government Benefit Record
→ Authorized government authority
```

---

# 80. Preventing Unauthorized Modification

The system should ensure:

```text
Worker
    ≠
Credential Issuer

Employer
    ≠
Government Authority

Employer A
    ≠
Employer B

Platform Admin
    ≠
Automatic authority to rewrite every credential
```

Each actor should have explicitly scoped privileges.

---

# 81. Employment Record Integrity

When an employment record is created, the system should preserve:

```text
Worker DID
Employer DID / organization identity
Employment Category
Employment Level
Nature of Employment
Work Site
Start Date
End Date
Status
Issue Timestamp
Record Hash / Reference
Issuer / Signer
```

Not all these fields must be placed directly on-chain.

A privacy-preserving design may store:

```text
Detailed Employment Record → encrypted / controlled storage
Record Hash + reference + status → blockchain
```

---

# 82. Benefit Record Integrity

A benefit record may contain:

```text
Claim ID
Worker DID / privacy-preserving reference
Scheme ID
Issuing Government Authority
State
Claim Timestamp
Eligibility Result / reference
Amount / approved value
Claim Status
Transaction Reference
```

The exact handling of monetary amounts and personal information should be determined by privacy and regulatory requirements.

---

# 83. Audit Model

Important events should be auditable.

Examples:

```text
Worker Identity Issued
Credential Issued
Credential Revoked
Employer Approved
Employer Suspended
Employment Created
Employment Status Changed
Worker Removed From Active Workforce
Benefit Claimed
Benefit Disbursed
Organization Permission Changed
Additional Employment Category Approved
```

An audit record may contain:

```text
Actor
Role
Action
Timestamp
Target Entity
Transaction Hash / Reference
Result
```

---

# 84. Product Status Model

## Identity

```text
UNVERIFIED
PENDING
VERIFIED
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

## Credential

```text
PENDING
ACTIVE
EXPIRED
REVOKED
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

# 85. Worker Account State Example

```text
ACCOUNT

Email:
VERIFIED ✓

Phone:
VERIFIED ✓

Profile:
COMPLETED ✓

Government Identity:
VERIFIED ✓

DID:
ACTIVE ✓

Identity Credential:
VALID ✓

Blockchain:
ANCHORED ✓

IPFS:
PINNED ✓
```

---

# 86. Complete End-to-End Worker Journey

## Stage 1 — Registration

```text
Worker registers
      ↓
Email verification
      ↓
Phone OTP verification
      ↓
Profile completion
```

## Stage 2 — Identity Establishment

```text
Enter Aadhaar number + name
      ↓
PASSKHADAM sends request to Aadhaar API
      ↓
Aadhaar record lookup
      ↓
Name match
      ↓
Aadhaar number match
      ↓
Identity record valid
      ↓
Identity verified
```

## Stage 3 — Decentralized Credential Issuance

```text
Generate DID
      ↓
Generate DID Document
      ↓
Create Verifiable Credential
      ↓
Create signing payload
      ↓
Sign credential
      ↓
Compute SHA-256 integrity hash
      ↓
Encrypt credential
      ↓
Pin encrypted credential to IPFS
      ↓
Obtain CID
      ↓
Anchor DID / credential reference and hash
on blockchain
```

## Stage 4 — Portable Identity

```text
Identity Wallet activated
      ↓
Worker views credentials
      ↓
Worker selects Share Identity
      ↓
Identity Presentation generated
      ↓
QR generated
      ↓
Worker downloads QR image
```

## Stage 5 — Employer Verification

```text
Employer logs in
      ↓
Employer selects Verify Worker
      ↓
Uploads QR image
      ↓
QR decoded
      ↓
DID resolved
      ↓
Credential reference resolved
      ↓
IPFS credential retrieved
      ↓
Credential decrypted
      ↓
Signature verified
      ↓
Integrity verified
      ↓
Revocation status checked
      ↓
BOCW / skill credential checked
      ↓
Employer permissions checked
      ↓
Worker verified
```

## Stage 6 — Employment

```text
Employer selects Offer Employment
      ↓
Select authorized category
      ↓
Select authorized level
      ↓
Enter nature of employment
      ↓
Enter location / site
      ↓
Enter employment dates
      ↓
Validate permissions
      ↓
Sign employment record
      ↓
Anchor record / hash
      ↓
Worker employment history updated
```

## Stage 7 — Employment Completion / Termination

```text
Employer selects active worker
      ↓
End Employment
      ↓
Select:
Completed / Terminated / Dismissed / Resigned / Suspended
      ↓
Record event
      ↓
Remove from active workers
      ↓
Preserve history
```

## Stage 8 — Worker Moves State

```text
Worker moves from Karnataka to Maharashtra
      ↓
Existing PASSKHADAM identity remains valid
      ↓
Maharashtra government requests verification
      ↓
Government uploads worker QR
      ↓
Worker identity verified
      ↓
Existing credentials recognized
      ↓
Cross-state information checked
      ↓
Benefit eligibility evaluated
```

## Stage 9 — Benefit Claim

```text
Government verifies worker
      ↓
Scheme eligibility checked
      ↓
30-day cooldown checked where applicable
      ↓
Duplicate claim check across authorized states
      ↓
Claim ID generated
      ↓
Authorized officer signs transaction
      ↓
Claim anchored on blockchain
      ↓
Benefit record updated
```

---

# 87. Product Processing Animation Principle

Whenever a high-value system operation occurs, the interface may display an explicit processing sequence.

Examples:

- Aadhaar verification
- DID generation
- Credential issuance
- QR verification
- Employment creation
- Employment completion
- Benefit disbursement
- Organization approval

The animations should describe operations that actually occur in the system.

The animation layer should not claim biometric verification, blockchain writes, cryptographic signatures, IPFS pinning, or other technical actions unless the backend really performs them.

---

# 88. Identity Processing Animation

Baseline:

```text
🔐 Establishing secure identity verification channel...
📋 Validating Aadhaar demographic credentials...
🆔 Generating W3C DID Document...
📄 Creating W3C Verifiable Credential...
🔑 Preparing credential signing payload...
✍️ Signing credential using authorized issuer key...
🔍 Computing SHA-256 integrity hash...
📦 Encrypting credential payload...
🌐 Pinning encrypted credential to IPFS...
📌 IPFS CID generated & pinned...
⛓️ Anchoring identity reference on WorkerIdentityRegistry.sol...
✅ Identity credential issued and anchored.
```

---

# 89. Employer Verification Animation

Baseline:

```text
🔍 Decoding uploaded QR cryptographic presentation...
📂 Resolving DID Document from did:PASSKHADAM decentralized registry...
⛓️ Querying WorkerIdentityRegistry.sol...
📌 Resolving encrypted IPFS CID...
🔓 Processing encrypted credential payload...
🔐 Verifying issuer signature / configured credential proof...
🛡️ Checking credential validity and revocation status...
🏗️ Checking BOCW safety certification & skill category...
📋 Checking employer authorization...
✅ Worker identity cryptographically verified.
```

---

# 90. Employment Logging Animation

Baseline:

```text
📝 Preparing verifiable employment stint record...
🏢 Attaching employer DID / organization identity...
🏗️ Attaching construction site metadata...
👷 Assigning employment category and level...
📋 Validating employer permissions...
🔐 Signing employment record using authorized employer identity...
⛓️ Anchoring employment record / hash...
📦 Updating worker's portable employment history...
✅ Employment stint anchored successfully.
```

---

# 91. Government Verification Animation

Baseline:

```text
🔍 Decoding uploaded QR cryptographic presentation payload...
📂 Resolving DID Document from did:PASSKHADAM registry...
⛓️ Querying WorkerIdentityRegistry.sol on EVM ledger...
📌 Resolving encrypted IPFS CID...
🔓 Processing encrypted Verifiable Credential payload...
🔐 Verifying issuer signature / configured proof...
📋 Checking credential validity and revocation status...
🌐 Cross-referencing authorized origin-state KYC registry...
✅ Identity cryptographically verified.
✅ Signature valid.
✅ DID / identity reference confirmed on-chain.
```

---

# 92. Government Benefit Disbursement Animation

Baseline:

```text
🔍 Checking WelfareSchemeRegistry.sol cooldown status...
⏱️ Validating cross-state claim cooldown period (30-day policy)...
🛡️ Confirming no duplicate or conflicting claim in any other authorized state registry...
📋 Validating worker eligibility...
📝 Generating unique SHA-256-based Claim ID...
⛓️ Writing benefit disbursement record to blockchain ledger...
🔒 Signing transaction with authorized government officer / authority wallet...
✅ Benefit disbursed! Claim record immutably anchored on-chain.
```

---

# 93. UX Principle

The underlying technical complexity should be hidden behind a simple user experience.

Users should primarily experience:

```text
Verify Identity
        ↓
Receive Credentials
        ↓
Share Identity
        ↓
Get Verified
        ↓
Get Employed
        ↓
Build Employment History
        ↓
Access Benefits
```

The blockchain, IPFS, DID, cryptographic signing and verification systems should operate behind the interface.

---

# 94. Recommended User Portal Navigation

```text
Overview
Identity
Credentials
Employment
Benefits
Share / Verify
Activity
Security
Profile
```

---

# 95. Recommended Employer Portal Navigation

```text
Dashboard
Workers
Verify Worker
Employment
Employment History
Requests
Company Profile
Audit / Activity
```

---

# 96. Recommended Government Portal Navigation

```text
Dashboard
Worker Verification
Benefits
Eligibility
Claims
Cross-State Verification
Employment Verification
Claim History
Audit Records
```

---

# 97. Recommended Admin Portal Navigation

```text
Dashboard
Organizations
Employers
Government Authorities
Credential Issuers
Employment Categories
Requests
Permissions
Audit Logs
Platform Configuration
```

---

# 98. Recommended Aadhaar Authority Navigation

```text
Dashboard
Aadhaar Records
Verification Requests
API Access
Verification Logs
Service Status
Configuration
```

---

# 99. Security Baseline

The final implementation should address at least:

- Firebase token validation
- Secure backend authorization
- Role-based access control
- Server-side permission checks
- Input validation
- Rate limiting
- Retry controls for identity verification
- Secure storage of private keys
- Blockchain wallet authorization
- Credential signature verification
- Credential revocation
- Presentation expiration
- Replay resistance where implemented
- Encryption of sensitive credential payloads
- Do not store sensitive PII unnecessarily on-chain
- Audit logging of privileged actions
- Secure API access to the Mock Aadhaar Authority

Security requirements can be expanded as the implementation matures.

---

# 100. Privacy Baseline

The product should apply the following privacy principles:

```text
Collect only necessary information
        ↓
Use verified claims rather than unnecessary raw PII
        ↓
Encrypt sensitive credential payloads
        ↓
Do not place raw Aadhaar data on blockchain
        ↓
Share minimum required information
        ↓
Use role-based access
        ↓
Preserve cryptographic integrity
```

The worker should not be forced to expose unrelated personal information simply to prove one eligibility condition.

---

# 101. Data Visibility Philosophy

Example:

### Employer asks:

> Is this worker a certified Mason?

The ideal result is:

```text
Skill:
Mason ✓

Certification:
VALID ✓
```

not necessarily:

```text
Full Aadhaar
Full address
Private phone
Private email
```

### Government asks:

> Is this worker eligible for a migrant welfare scheme?

The ideal result is:

```text
Identity:
VALID ✓

Eligibility:
YES ✓
```

plus whatever additional authorized attributes are actually required.

---

# 102. Product Governance Principle

No single participating organization should automatically control everything.

Conceptually:

```text
Worker
    ↓
Controls presentation / sharing

Identity Issuer
    ↓
Issues / governs identity credential

Skill Authority
    ↓
Issues skill credentials

Employer
    ↓
Creates its employment records

Government Authority
    ↓
Creates its authorized benefit records

Platform Admin
    ↓
Governs participation and permissions
```

This preserves separation of authority.

---

# 103. Product Outcome

A successful PASSKHADAM workflow should result in:

```text
A verified worker identity
        +
Portable credentials
        +
Cryptographic verification
        +
Controlled information sharing
        +
Portable employment history
        +
Cross-state verification
        +
Eligibility-aware welfare access
        +
Auditable organizational actions
```

---

# 104. Final Product Structure

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

# 105. Most Important Product Flow

The product should communicate one simple story:

```text
VERIFY YOUR IDENTITY
        ↓
OWN YOUR CREDENTIALS
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

---

# 106. Current Baseline Business Rules

The current proposed baseline includes:

```text
1. Worker email must be verified.
2. Worker phone must be verified.
3. Government identity must be successfully verified.
4. Worker identity is not considered fully verified before government identity verification.
5. Aadhaar details are verified through the Aadhaar API / Mock Aadhaar Authority.
6. Raw Aadhaar information should not be stored directly on-chain.
7. Worker receives a DID after successful identity verification.
8. Worker receives a Verifiable Credential representing the verified identity.
9. Credential integrity is represented using a cryptographic hash.
10. Credential content may be encrypted before IPFS storage.
11. Blockchain stores references / hashes / status rather than large sensitive payloads.
12. Worker can generate a QR-based identity presentation.
13. Employer and Government verify through QR image upload, not camera scanning.
14. Employer access is permission-controlled.
15. Employer employment categories are permission-controlled.
16. New employment categories require another admin approval.
17. Ending employment removes the worker from active employment but preserves historical records.
18. Government access is permission-controlled.
19. Benefit eligibility is rule-based.
20. Cross-state duplicate claim checks are supported.
21. A 30-day cooldown is the current baseline for applicable cross-state claims.
22. Government transactions require an authorized blockchain identity / wallet.
23. Identity and credential revocation are supported.
24. Important actions are auditable.
25. The architecture remains changeable when a better approach is identified.
```

---

# 107. Configurable / Changeable Areas

The following should be treated as changeable rather than immutable requirements:

```text
Authentication sequence
Profile fields
Identity verification checks
Aadhaar API response schema
DID method
DID document structure
Verifiable Credential version
Credential proof format
Signature mechanism
Encryption mechanism
IPFS pinning strategy
Blockchain network
Smart-contract organization
Credential status model
Employment categories
Employment levels
Nature-of-employment taxonomy
Employer permissions
Government permissions
Cross-state policies
Benefit eligibility rules
Benefit cooldown duration
Claim duplication rules
QR presentation structure
QR expiration period
Presentation anti-replay mechanism
Data storage engine
Wallet custody model
Admin governance model
Audit schema
Portal navigation
UX processing animations
```

---

# 108. Explicit Change Policy

This document is **not a locked architecture**.

The following statement applies throughout the product lifecycle:

> **Any changes in steps are entertained.**

A workflow may be reordered, simplified, expanded or replaced if the change improves the product.

A component may be replaced if the replacement provides a better balance of:

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

No feature should be retained merely because it appears in this baseline document.

---

# 109. Design Standard for Future Product Decisions

When evaluating a future feature or architecture change, use the following test:

```text
Does it improve the worker's ability to carry a trusted identity?
        ↓
Does it reduce unnecessary friction?
        ↓
Does it preserve privacy?
        ↓
Does it preserve verifiability?
        ↓
Does it maintain proper separation of authority?
        ↓
Does it make the product easier to operate and scale?
        ↓
Does it have a real technical purpose?
```

If not, the feature should be questioned rather than added for complexity alone.

---

# 110. Final Product Statement

PASSKHADAM is intended to function as a **portable trust layer for migrant-worker identity, employment and welfare interactions**.

The worker establishes a verified identity once, receives cryptographically verifiable credentials, controls how those credentials are presented, and can use the same identity across authorized employers and government authorities.

Employers can verify authorized worker credentials and create portable employment records without owning the worker's identity.

Government authorities can verify workers, evaluate cross-state benefit eligibility and record authorized welfare transactions without requiring the worker to recreate an entirely separate identity after migration.

The platform admin provides governance over participating organizations, permissions and credential authorities.

The Aadhaar Authority provides the identity verification interface used to establish the initial government-backed identity link.

The overall system is therefore:

```text
Government-backed identity verification
                +
Decentralized identity
                +
Verifiable credentials
                +
Encrypted decentralized storage
                +
Blockchain integrity / auditability
                +
Role-based verification
                +
Portable employment history
                +
Cross-state welfare verification
                =
             PASSKHADAM
```

---

## 111. Current Specification Status

**Version:** 0.2

**Status:** Proposed Baseline Product Specification

**Primary Product Model:** Web-based decentralized identity platform

**QR Interaction Model:** Upload QR image for verification; camera scanning is not part of the core web workflow.

**Identity Model:** Government-verified identity + DID + Verifiable Credentials

**Trust Layer:** EVM-compatible blockchain

**Decentralized Storage:** IPFS for encrypted credential objects

**Backend:** FastAPI

**Frontend:** React

**Authentication:** Firebase Authentication

**Smart Contracts:** Solidity

**Blockchain Interaction:** Web3.js

**Identity Verification Authority:** Aadhaar API / Mock Aadhaar Authority

**Primary Roles:**

```text
1. User / Worker
2. Admin
3. Government
4. Employer
5. Aadhaar API Management / Identity Authority
```

**Change Policy:** Open to architectural, workflow, technical and product changes whenever justified.

---

# 112. One-Sentence Product Definition

> **PASSKHADAM is a web-based decentralized identity platform that enables migrant workers to establish a verified digital identity, carry verifiable credentials across states and employers, build portable employment history, and access authorized welfare services through privacy-conscious cryptographic verification.**
