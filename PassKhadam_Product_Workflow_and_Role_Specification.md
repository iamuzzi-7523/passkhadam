# PASSKHADAM

## Decentralized Identity Verification Platform for Migrant Workers

### 1. Product Vision

PASSKHADAM is a web-based decentralized identity platform designed to provide migrant workers with a **portable, verifiable and user-controlled digital identity** that remains useful when they move between states, employers and government departments.

The platform allows a worker to establish a verified identity, receive digitally signed credentials, securely maintain those credentials, and present proof of identity or eligibility to authorized employers and government authorities without depending on a single centralized identity database for every verification.

The platform consists of five primary roles:

1. **User / Worker**
2. **Platform Admin**
3. **Government Authority**
4. **Employer**
5. **Aadhaar API Management / Identity Authority**

The system uses:

- **React** — Web frontend
- **FastAPI** — Backend and business logic
- **Firebase Authentication** — Email and phone authentication/verification
- **Solidity** — Smart contracts
- **Web3.js** — Blockchain interaction
- **IPFS** — Decentralized storage for encrypted credential payloads
- **EVM-compatible blockchain** — Identity, credential, employment and benefit records
- **Aadhaar API / Mock Aadhaar Authority** — Government identity verification
- **SQLite/PostgreSQL** — Application-level off-chain data storage

---

# 2. Core Product Principle

The entire product should revolve around one central concept:

> **A worker creates one trusted digital identity and carries that identity across employers, states and government services.**

The product should therefore be structured around three major capabilities:

### Identity

- Account verification
- Aadhaar verification
- Decentralized Identifier (DID)
- Verifiable Credentials
- Credential wallet
- QR-based identity presentation

### Employment

- Employer verification
- Worker verification
- Employment issuance
- Employment history
- Skill and employment category restrictions
- Employment completion / termination

### Welfare

- Government verification
- Benefit eligibility
- Cross-state verification
- Claim management
- Duplicate-claim prevention
- Benefit disbursement records

---

# 3. Overall Product Lifecycle

The primary product lifecycle is:

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
Identity Approval
        ↓
DID Generation
        ↓
Verifiable Credential Generation
        ↓
Credential Signing
        ↓
Credential Encryption
        ↓
Credential Storage on IPFS
        ↓
Credential Hash / DID Anchored on Blockchain
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
Credential Validation
        ↓
Signature / Integrity Verification
        ↓
Authorization / Eligibility Verification
        ↓
Employment or Welfare Action
        ↓
Immutable Record Created
```

**Important:** The above sequence is the initial product baseline. **Any changes to these steps are entertained** when improving security, usability, privacy, performance, regulatory compatibility or overall product architecture.

---

# 4. USER / WORKER PORTAL

## 4.1 User Registration

The worker begins by creating an account through the PASSKHADAM web application.

### Registration Information

The initial registration form contains:

- Full Name
- Email Address
- Phone Number
- Password
- Confirm Password

The worker submits the registration form.

### Verification Sequence

```text
Create Account
      ↓
Verify Email
      ↓
Verify Phone Number using OTP
      ↓
Account Activated
```

Firebase Authentication is responsible for:

- User authentication
- Email verification
- Phone OTP verification
- Session management
- Authentication tokens

The PASSKHADAM backend verifies the authenticated user's Firebase token before allowing protected operations.

---

# 5. USER PROFILE CREATION

After successful authentication, the worker completes the basic profile.

Possible fields:

- Full Name
- Date of Birth
- Gender
- Phone Number
- Email
- Current State
- Origin State
- Address
- Worker Category
- Optional skill information

At this point:

```text
Account Status:
EMAIL VERIFIED ✓
PHONE VERIFIED ✓
PROFILE COMPLETED ✓
IDENTITY VERIFIED ✕
```

The worker can proceed to government identity verification.

---

# 6. AADHAAR VERIFICATION

The worker selects:

> **Verify Government Identity**

The system displays:

### Aadhaar Verification Form

- Aadhaar Number
- Name as registered with Aadhaar

The worker submits the verification request.

### Verification Logic

The PASSKHADAM backend sends the request to the Aadhaar verification service.

```text
Worker
  ↓
PASSKHADAM Backend
  ↓
Aadhaar Verification API
  ↓
Aadhaar Record Lookup
  ↓
Name Match?
  ↓
Aadhaar Number Match?
  ↓
Aadhaar Active / Valid?
  ↓
Verification Result
```

The worker must already have:

```text
Email Verified ✓
Phone Verified ✓
```

The Aadhaar verification must then successfully validate the supplied government identity details.

Where supported by the identity authority, additional demographic fields may also be cross-checked.

### Important Privacy Rule

The Aadhaar number and other sensitive personal information should **not be stored directly on the blockchain**.

The blockchain should instead contain cryptographic references, hashes, identifiers, issuer information and status information.

---

# 7. AADHAAR VERIFICATION RESULT

### Successful Verification

The user sees:

```text
Government Identity

✓ Aadhaar Verified
✓ Name Matched
✓ Aadhaar Number Matched
✓ Identity Record Valid

Identity verification completed successfully.
```

The portal may display a **masked Aadhaar representation** rather than exposing the complete number.

Example:

```text
XXXX XXXX 4821
```

The worker can now proceed to decentralized identity creation.

### Failed Verification

Possible reasons:

```text
Aadhaar number not found
Name mismatch
Aadhaar inactive
Verification service unavailable
Identity details could not be validated
```

The worker is allowed to correct the details and retry according to configured retry/security rules.

---

# 8. DECENTRALIZED IDENTITY CREATION

After successful identity verification, PASSKHADAM creates the worker's decentralized identity.

Example:

```text
did:PASSKHADAM:worker:{unique-hash}
```

A DID Document is generated containing the information necessary to establish the worker's decentralized identity and verification methods.

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

The DID should not expose the worker's Aadhaar number or unnecessary personal information.

---

# 9. VERIFIABLE CREDENTIAL CREATION

After DID generation, the system creates a digitally signed Verifiable Credential representing the verified identity.

Example credential concept:

```text
Credential Type:
Worker Identity Credential

Subject:
Worker DID

Issuer:
Authorized Identity Authority

Status:
Active

Issued At:
Timestamp
```

The credential represents the result of identity verification rather than becoming a duplicate Aadhaar database.

---

# 10. USER IDENTITY ISSUANCE PROCESS

The system can display a live processing interface while the credential is being created.

Suggested processing sequence:

```text
🔐 Establishing secure identity verification channel...
📋 Validating Aadhaar demographic credentials...
🆔 Generating decentralized identifier...
📄 Creating W3C Verifiable Credential...
🔑 Signing credential with issuer key...
🔍 Computing credential integrity hash...
📦 Encrypting credential payload...
🌐 Pinning encrypted credential to IPFS...
📌 IPFS CID generated...
⛓️ Anchoring credential hash on blockchain...
✅ Identity credential successfully issued
```

After successful completion:

```text
IDENTITY VERIFIED ✓

DID:
did:PASSKHADAM:worker:8f29...

Credential Status:
VALID

Blockchain Status:
ANCHORED

IPFS Status:
PINNED
```

---

# 11. CREDENTIAL STORAGE

The credential architecture should separate data storage from blockchain integrity.

### Off-chain / decentralized storage

The encrypted credential payload is stored on IPFS.

```text
Encrypted Credential
        ↓
       IPFS
        ↓
     IPFS CID
```

### Blockchain

The blockchain stores references such as:

```text
Worker DID
Credential Hash
Credential Type
Issuer
Issue Timestamp
CID / Reference
Credential Status
Revocation Information
```

### Blockchain should NOT contain

```text
Full Aadhaar Number
Full Address
Email
Phone Number
Other unnecessary PII
```

This separation provides:

```text
Database → application data
IPFS → encrypted credential payload
Blockchain → trust, integrity, status and auditability
```

---

# 12. USER CREDENTIAL WALLET

The worker receives a personal credential dashboard.

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

---

# 13. USER QR IDENTITY PRESENTATION

The worker selects:

> **Share Identity**

The platform generates a cryptographic presentation containing the information necessary for an authorized verifier to validate the worker.

The platform displays:

```text
IDENTITY PRESENTATION

[ QR CODE ]

Presentation Status:
Active

Expires:
05:00

[Download QR]
[Download Presentation]
```

The worker can download the QR as an image.

### Important Change

**No camera scanning is required.**

The product is fully web-based.

The receiving organization verifies the worker by:

> **Upload QR**

rather than:

> **Scan QR with camera**

---

# 14. EMPLOYER PORTAL

The employer lifecycle begins with employer registration.

## Employer Registration

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
- Number of workers / expected workforce
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

---

# 15. EMPLOYER ADMIN APPROVAL

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

# 16. EMPLOYER CREDENTIALS AND PERMISSIONS

The admin assigns:

```text
Employer ID
Login credentials
Organization identity
Authorized categories
Permission scope
Account status
```

For example:

```text
ABC Construction Pvt Ltd

Approved Categories:

✓ Mason
✓ Electrician
✓ Plumber
```

The employer is permitted to create employment records only within its approved categories.

---

# 17. EMPLOYER REQUEST FOR NEW EMPLOYMENT CATEGORY

Suppose the employer later wants to hire:

```text
Heavy Machinery Operator
```

but does not currently have permission.

The employer submits:

> **Request Additional Employment Category**

The request goes to the admin.

```text
Employer
   ↓
Additional Category Request
   ↓
Admin Review
   ↓
Approved / Rejected
   ↓
Employer Permission Updated
```

Until approval:

```text
Heavy Machinery Operator → NOT AUTHORIZED
```

---

# 18. EMPLOYER DASHBOARD

The employer portal contains:

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

Dashboard information may include:

```text
Active Workers
Completed Employments
Pending Verifications
Employment Categories
Pending Admin Requests
```

---

# 19. EMPLOYER WORKER VERIFICATION

The employer selects:

> **Verify Worker**

Instead of using a camera, the employer sees:

```text
UPLOAD WORKER QR

[ Drag & Drop QR Image Here ]

or

[ Choose QR Image ]

[ Verify Identity ]
```

The uploaded image contains the worker's cryptographic presentation.

The backend processes the QR image.

---

# 20. EMPLOYER VERIFICATION PROCESS

Suggested processing sequence:

```text
🔍 Decoding uploaded QR cryptographic presentation...
📂 Resolving worker DID...
⛓️ Querying WorkerIdentityRegistry...
📌 Resolving encrypted credential reference...
🔓 Processing encrypted credential payload...
🔐 Verifying credential issuer signature...
🛡️ Checking credential validity and revocation status...
🏗️ Checking required skill / employment credential...
✅ Worker identity cryptographically verified
```

The system then displays only the information the employer is authorized to see.

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

Required Certification:
✓ VALID

Employment Eligibility:
✓ ELIGIBLE
```

Sensitive information should not be unnecessarily exposed.

---

# 21. EMPLOYER WORKER PROFILE

After successful verification, the employer can access the worker information permitted by the employer's role.

Possible information:

```text
Verified Identity
Worker DID
Relevant Skills
Relevant Certifications
Employment History
Current Employment Status
Previous Employment Records
Credential Status
```

The employer does not automatically receive unrestricted access to every worker attribute.

---

# 22. EMPLOYMENT CREATION

After verification, the employer selects:

> **Offer Employment**

Employment details may include:

```text
Worker
Employment Category
Job Role
Employment Type
Work Location
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

# 23. EMPLOYMENT LOGGING PROCESS

Suggested processing sequence:

```text
📝 Preparing verifiable employment record...
🏢 Attaching employer identity...
👷 Assigning authorized employment category...
📋 Validating employer permissions...
🔐 Signing employment record...
⛓️ Anchoring employment record on blockchain...
📦 Updating worker employment history...
✅ Employment successfully recorded
```

The employment record becomes part of the worker's portable employment history.

---

# 24. EMPLOYMENT STATUS MANAGEMENT

An employer should be able to change an employment record to one of the defined states:

```text
ACTIVE
COMPLETED
TERMINATED
RESIGNED
SUSPENDED
```

Every status change should create an auditable event.

Example:

```text
ABC Construction
Position: Mason

05 Oct 2026
Employment Started

12 Dec 2026
Employment Completed
```

or:

```text
Employment Status:
TERMINATED

Reason:
Contract Terminated
```

The exact visibility of termination reasons can be controlled by the platform's permission model.

---

# 25. WORKER EMPLOYMENT HISTORY

The worker can view all authorized employment records.

Example:

```text
EMPLOYMENT HISTORY

ABC Construction
Mason
Bengaluru
05 Oct 2026 – Present
Status: ACTIVE

XYZ Infrastructure
General Labour
Hyderabad
10 Jan 2026 – 30 Sep 2026
Status: COMPLETED
```

This creates a portable employment record that follows the worker instead of remaining trapped inside one employer's system.

---

# 26. GOVERNMENT PORTAL

The government portal is designed for:

```text
Identity Verification
Worker Verification
Benefit Eligibility
Benefit Claims
Cross-State Verification
Employment Verification
Claim History
Audit Records
```

---

# 27. GOVERNMENT WORKER VERIFICATION

Government officers also use:

> **Upload QR**

rather than camera scanning.

Interface:

```text
UPLOAD WORKER QR

[ Upload QR Image ]

[ Verify Worker ]
```

The system extracts the worker's cryptographic presentation.

---

# 28. GOVERNMENT VERIFICATION PROCESS

Suggested sequence:

```text
🔍 Decoding uploaded QR cryptographic presentation...
📂 Resolving worker DID from decentralized registry...
⛓️ Querying WorkerIdentityRegistry...
📌 Resolving encrypted credential reference...
🔓 Processing encrypted Verifiable Credential...
🔐 Verifying issuer signature...
📋 Checking credential validity and revocation status...
🌐 Checking authorized origin-state information...
✅ Identity cryptographically verified
```

The result may show:

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

---

# 29. GOVERNMENT BENEFIT ELIGIBILITY

Once the worker is verified, the government portal evaluates applicable schemes.

Example:

```text
BENEFIT ELIGIBILITY

✓ Construction Worker Welfare
✓ Migrant Worker Assistance
✓ Accident Protection Scheme
✕ State Resident-Only Scheme
```

The eligibility engine can evaluate:

```text
Identity validity
Worker category
Skill / certification
Employment status
State
Scheme rules
Previous claims
Claim cooldown
Other configured conditions
```

---

# 30. BENEFIT CLAIM

The government officer can initiate a claim for an eligible worker.

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

The system performs validation before recording the claim.

---

# 31. BENEFIT DISBURSEMENT PROCESS

Suggested sequence:

```text
🔍 Checking WelfareSchemeRegistry cooldown status...
⏱️ Validating cross-state claim rules...
🛡️ Checking for duplicate or conflicting claims...
📋 Validating worker eligibility...
📝 Generating unique claim identifier...
⛓️ Writing benefit claim record to blockchain...
🔒 Signing transaction with authorized government wallet...
✅ Benefit disbursement record successfully anchored
```

The exact eligibility and cooldown rules remain configurable by the platform.

---

# 32. CROSS-STATE BENEFIT VALIDATION

A core capability of PASSKHADAM is preventing fragmented identity records when workers move across states.

Example:

```text
Worker Origin:
Karnataka

Current Location:
Maharashtra
```

The Maharashtra government does not need the worker to create a completely new identity.

Instead:

```text
Worker DID
   ↓
Existing Credentials
   ↓
Verification
   ↓
Eligibility Check
   ↓
Benefit / Service
```

Where applicable, the system can check whether a previously recorded claim conflicts with the current claim.

---

# 33. GOVERNMENT EMPLOYMENT VERIFICATION

Government authorities may also access authorized employment information.

Example:

```text
Current Employment:
ABC Construction

Role:
Mason

Status:
ACTIVE

Start Date:
05 Oct 2026
```

Historical information can be shown according to the government's authorization scope.

---

# 34. ADMIN PORTAL

The admin is the platform governance and authorization layer.

The admin does not manually become the worker's identity.

Instead, the admin controls which organizations and users are allowed to participate in the ecosystem.

---

# 35. ADMIN RESPONSIBILITIES

The admin manages:

### Organization Management

```text
Employers
Government Authorities
Credential Issuers
```

### User / Organization Approval

```text
Approve
Reject
Suspend
Reactivate
Request Additional Information
```

### Permissions

The admin determines:

```text
What an organization can verify
What credentials an organization can access
What employment categories an employer can create
What services a government authority can access
```

### Employment Category Management

```text
Create Category
Approve Category
Disable Category
Modify Category Rules
```

### Credential Authority Management

The admin controls which authorized organization can:

```text
Issue credentials
Verify credentials
Revoke credentials
```

depending on the product governance model.

---

# 36. EMPLOYER ADMIN WORKFLOW

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
Approval
        ↓
Employer Account Activated
        ↓
Credentials / Permissions Assigned
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

# 37. GOVERNMENT ADMIN WORKFLOW

Government organizations follow a similar onboarding process.

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

Different government departments can receive different permission levels.

---

# 38. AADHAAR API MANAGEMENT / IDENTITY AUTHORITY

The Aadhaar API Management role represents the identity verification authority responsible for the Aadhaar verification service used by PASSKHADAM.

For development and controlled demonstration, this can be represented through a **Mock Aadhaar Authority / Mock Aadhaar API**.

The mock system should behave like an external government identity service rather than allowing the main application to directly read its database.

---

# 39. MOCK AADHAAR AUTHORITY

The mock Aadhaar system contains:

```text
Aadhaar Records
Identity Verification API
Verification Engine
API Credentials
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

The actual implementation can use a separate database.

---

# 40. AADHAAR API VERIFICATION FLOW

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
Status Validation
    ↓
Verification Response
    ↓
PASSKHADAM Identity Service
```

The main application should receive the verification result and necessary reference information instead of unnecessarily copying the full Aadhaar record.

---

# 41. AADHAAR MANAGEMENT DASHBOARD

The identity authority dashboard can contain:

```text
Total Aadhaar Records
Active Records
Verification Requests
Successful Verifications
Failed Verifications
API Health
API Requests
Verification Logs
```

Example:

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

# 42. COMMON VERIFICATION ENGINE

The platform should avoid implementing separate verification logic independently inside the employer and government portals.

Instead, use a central verification service.

```text
Employer Portal
       ↓
       │
Government Portal
       ↓
Verification Service
       ↓
DID Resolution
       ↓
Credential Resolution
       ↓
Signature Verification
       ↓
Hash / Integrity Verification
       ↓
Revocation Check
       ↓
Permission Check
       ↓
Result
```

This makes the product architecture cleaner and easier to maintain.

---

# 43. SHARED IDENTITY VERIFICATION PROCESS

Every organization follows the same core process:

```text
UPLOAD QR IMAGE
      ↓
Decode QR
      ↓
Extract Cryptographic Presentation
      ↓
Resolve DID
      ↓
Resolve Credential
      ↓
Retrieve Encrypted Credential Reference
      ↓
Validate Credential
      ↓
Verify Issuer Signature
      ↓
Verify Integrity Hash
      ↓
Check Revocation / Status
      ↓
Check Organization Permissions
      ↓
Return Authorized Verification Result
```

The difference between Employer and Government access comes from the **permission layer**, not from having completely different identity verification systems.

---

# 44. ROLE-BASED ACCESS MODEL

## Worker

Can:

```text
Create Account
Verify Email
Verify Phone
Verify Identity
Create / Receive DID
View Credentials
View Employment History
Generate Identity QR
Download QR
Manage Profile
View Benefit History
Control Identity Sharing
```

## Admin

Can:

```text
Approve Employers
Approve Government Authorities
Manage Permissions
Manage Employment Categories
Manage Credential Issuers
Suspend Organizations
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
Create Employment Records
Update Employment Status
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
Review Employment Information
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

# 45. CORE SMART CONTRACT LAYER

The blockchain layer can be separated into multiple contracts.

## WorkerIdentityRegistry.sol

Responsible for:

```text
DID Registration
DID Resolution References
Credential Status
Credential Hash
Revocation Status
```

## CredentialRegistry.sol

Responsible for:

```text
Credential Issuance
Credential Status
Credential Revocation
Issuer References
Credential Integrity
```

## OrganizationRegistry.sol

Responsible for:

```text
Employer Registration
Government Organization Registration
Organization Status
Organization Permissions
```

## EmploymentRegistry.sol

Responsible for:

```text
Employment Creation
Employment Status
Employment History
Employer Identity
Worker DID Reference
```

## WelfareSchemeRegistry.sol

Responsible for:

```text
Scheme Registration
Eligibility Rules
Claim Records
Claim Status
Cooldown Rules
Duplicate Claim Checks
```

The actual contract structure can be modified as implementation progresses.

---

# 46. DATA ARCHITECTURE

A clean architecture should separate information into three layers.

## Application Database

Used for:

```text
User Accounts
Firebase User References
Profiles
Organization Data
Admin Data
Operational Information
UI Preferences
```

## IPFS

Used for:

```text
Encrypted Credential Payloads
Credential Documents
Other approved decentralized objects
```

## Blockchain

Used for:

```text
DID References
Credential Hashes
Issuer Information
Credential Status
Employment Records / Hashes
Benefit Claim Records / Hashes
Organization Authorization
Audit Events
```

---

# 47. COMPLETE END-TO-END EXAMPLE

### Stage 1 — Worker joins PASSKHADAM

```text
Worker registers
      ↓
Email verified
      ↓
Phone verified
      ↓
Profile completed
```

### Stage 2 — Identity established

```text
Worker enters Aadhaar number + name
      ↓
Aadhaar API verifies identity
      ↓
Identity verified
      ↓
DID generated
      ↓
Verifiable Credential generated
      ↓
Credential signed
      ↓
Credential encrypted
      ↓
Credential stored on IPFS
      ↓
Credential hash anchored on blockchain
```

### Stage 3 — Worker obtains portable identity

```text
Worker opens Identity Wallet
      ↓
Identity Credential = VALID
      ↓
Worker selects Share Identity
      ↓
QR presentation generated
      ↓
Worker downloads / presents QR image
```

### Stage 4 — Employer verifies worker

```text
Employer logs in
      ↓
Employer selects Verify Worker
      ↓
Uploads QR image
      ↓
QR processed
      ↓
DID resolved
      ↓
Credentials validated
      ↓
Worker verified
      ↓
Employer checks authorized information
```

### Stage 5 — Employer creates employment

```text
Employer selects authorized job category
      ↓
Creates employment record
      ↓
System validates employer permission
      ↓
Employment credential / record generated
      ↓
Record signed
      ↓
Employment record anchored
      ↓
Worker employment history updated
```

### Stage 6 — Worker moves to another state

```text
Worker moves
      ↓
Existing PASSKHADAM identity remains valid
      ↓
New government authority uploads worker QR
      ↓
Worker identity verified
      ↓
Existing credentials recognized
      ↓
Eligibility evaluated
      ↓
Applicable welfare benefits identified
```

### Stage 7 — Government benefit claim

```text
Government verifies worker
      ↓
Eligibility checked
      ↓
Previous claim / cooldown checked
      ↓
Claim approved
      ↓
Benefit record created
      ↓
Blockchain transaction signed
      ↓
Claim anchored
      ↓
Worker benefit history updated
```

---

# 48. PRODUCT STATUS MODEL

The platform should use clear statuses.

### Identity

```text
UNVERIFIED
PENDING
VERIFIED
REVOKED
SUSPENDED
```

### Employer

```text
PENDING_REVIEW
APPROVED
REJECTED
SUSPENDED
```

### Employment

```text
ACTIVE
COMPLETED
TERMINATED
RESIGNED
SUSPENDED
```

### Credential

```text
PENDING
ACTIVE
EXPIRED
REVOKED
SUSPENDED
```

### Benefit Claim

```text
PENDING
ELIGIBLE
APPROVED
DISBURSED
REJECTED
CANCELLED
```

---

# 49. MOST IMPORTANT PRODUCT FLOW

The product should communicate one simple story to the user:

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

The complexity of blockchain, cryptography, IPFS, DID resolution and smart contracts should operate behind the interface.

The user should experience a simple product even though the underlying system is technically sophisticated.

---

# 50. PROPOSED PROCESSING / ANIMATION PRINCIPLE

Whenever the system performs a blockchain, credential or verification operation, the interface can expose a technical processing sequence.

For example:

```text
User Action
    ↓
System Processing Animation
    ↓
Verification
    ↓
Result
```

This can be used for:

```text
Aadhaar verification
DID generation
Credential issuance
QR verification
Employment creation
Benefit disbursement
```

The processing animations should communicate real operations performed by the backend and blockchain rather than displaying fictional technical steps.

---

# 51. DESIGN PRINCIPLE FOR THE COMPLETE PRODUCT

The five portals should not feel like five unrelated websites.

They should share:

```text
Common branding
Common design system
Common authentication philosophy
Common notification system
Common audit model
Common verification engine
Common identity model
Common status system
```

But each role should see only the functions relevant to its responsibilities.

---

# 52. FINAL PRODUCT STRUCTURE

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

# 53. PRODUCT WORKFLOW STATUS

This document represents the **baseline product workflow and architecture**.

**Any changes in steps are entertained.**

The following can be changed during product development without treating this workflow as fixed:

```text
Authentication sequence
Identity verification sequence
Aadhaar verification logic
DID architecture
Credential structure
IPFS storage strategy
Blockchain contract structure
Employer permissions
Government permissions
Employment lifecycle
Benefit eligibility rules
QR presentation structure
Verification sequence
Admin approval process
Data storage architecture
```

The guiding requirement for every future modification should remain:

> **The worker must have a portable, trustworthy and privacy-conscious identity that can be independently verified across authorized employers and government services.**
