# PASSKHADAM — Sign-In, Login & Firebase Authentication Architecture
## Version 1.1 — Firebase Project Integrated

---

# 1. Purpose

This document defines the **authentication, sign-in, login, account activation, Firebase Authentication, session, token, logout, role assignment, organization authorization, and access-control flows** for PassKhadam.

It focuses only on authentication and authorization.

It does **not** define:

- Aadhaar identity verification logic
- DID issuance
- Verifiable Credential issuance
- IPFS storage
- Blockchain workflows
- Employment workflows
- Welfare workflows

Those systems begin after authentication and authorization have succeeded.

The five PassKhadam roles are:

1. **Worker / User**
2. **Employer**
3. **Government Authority / Officer**
4. **Platform Admin**
5. **Aadhaar API Management / Identity Authority**

---

# 2. Authentication Principle

PassKhadam uses a common authentication foundation rather than five unrelated login systems.

```text
                         FIREBASE AUTHENTICATION
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             ▼                    ▼                    ▼
          WORKER              EMPLOYER            GOVERNMENT
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                         ┌────────┴─────────┐
                         ▼                  ▼
                       ADMIN         AADHAAR AUTHORITY
                         │                  │
                         └────────┬─────────┘
                                  ▼
                         FastAPI Authorization
                                  │
                                  ▼
                     Role / Organization / Scope
                                  │
                                  ▼
                         Permission Evaluation
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                ▼                ▼
              Worker          Employer         Government
              Portal           Portal             Portal
```

Authentication answers:

> **Who are you?**

Authorization answers:

> **What are you allowed to do?**

Firebase provides the authentication foundation. PassKadam's backend is the authority for application roles, organization membership, account status, and fine-grained permissions.

---

# 3. Current Firebase Project

The currently configured Firebase Web project is:

```text
Project Name / Project ID:
passkhadam-live

Firebase Auth Domain:
passkhadam-live.firebaseapp.com

Storage Bucket:
passkhadam-live.firebasestorage.app

Messaging Sender ID:
854979434504

Web App ID:
1:854979434504:web:f7378b2c22039d3b1159bd
```

### Current Firebase Web Configuration

The manually generated web configuration is:

```javascript
import { initializeApp } from "firebase/app";

const firebaseConfig = {
  apiKey: "AIzaSyAm2y_rprQk5C51aD_1UTcw4pyfI-vsrHQ",
  authDomain: "passkhadam-live.firebaseapp.com",
  projectId: "passkhadam-live",
  storageBucket: "passkhadam-live.firebasestorage.app",
  messagingSenderId: "854979434504",
  appId: "1:854979434504:web:f7378b2c22039d3b1159bd"
};

const app = initializeApp(firebaseConfig);
```

This configuration is for the **Firebase Web SDK**.

---

# 4. Firebase Configuration Handling

The Firebase Web configuration is intended for the client application, but it should not be committed carelessly throughout source code.

Recommended implementation:

```text
frontend/.env
```

with values such as:

```env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=passkhadam-live.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=passkhadam-live
VITE_FIREBASE_STORAGE_BUCKET=passkhadam-live.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=854979434504
VITE_FIREBASE_APP_ID=1:854979434504:web:f7378b2c22039d3b1159bd
```

Then:

```javascript
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};
```

### Important

A Firebase Web `apiKey` is not treated like a backend private key or service-account secret. However:

- Firebase Security Rules must be configured correctly.
- API restrictions should be applied where appropriate.
- Authentication providers must be configured in Firebase Console.
- Backend service-account credentials must **never** be exposed to the frontend.
- Do not place Firebase Admin SDK private credentials in React source code.

---

# 5. Firebase Initialization

Create a single Firebase initialization module.

Recommended:

```text
frontend/src/lib/firebase.js
```

Conceptually:

```javascript
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export default app;
```

The exact file structure may change.

The important rule is:

> Initialize Firebase once and share the Auth instance throughout the React application.

---

# 6. Firebase Products Required

For the current authentication model, the primary Firebase product is:

```text
Firebase Authentication
```

Required authentication capabilities:

```text
Email/password authentication
Email verification
Phone OTP verification
Password reset
Authentication state tracking
ID token issuance
Token refresh handling
Logout
```

Firebase Storage, Firestore, Analytics, Cloud Messaging, or other Firebase products are **not automatically required** merely because this project uses Firebase Authentication.

---

# 7. Firebase Authentication Providers

Enable only the providers required by PassKadam.

Baseline:

```text
Email / Password
Phone Number
```

Additional providers may be introduced later if justified.

---

# 8. Human Authentication vs Machine Authentication

This distinction is mandatory.

## Human users

The following roles authenticate through Firebase Authentication:

```text
Worker
Employer user
Government officer
Platform admin
Aadhaar Authority operator
```

## Machine-to-machine communication

The following does **not** use Firebase human authentication:

```text
PassKadam Backend
        ↔
Mock Aadhaar API
```

Service authentication should use an appropriate service credential mechanism.

Do not use a human Firebase ID token as a permanent backend-to-backend API credential.

---

# 9. Firebase Identity vs PassKadam Identity

Firebase identifies the authenticated account.

PassKadam maintains the business identity.

```text
Firebase UID
      ↓
PassKadam UserAccount
      ↓
Role
      ↓
Organization
      ↓
Permissions
```

Example Worker:

```text
Firebase UID:
firebase_uid_abc123

PassKadam User ID:
USR-000123

Role:
WORKER

Status:
ACTIVE
```

Example Employer:

```text
Firebase UID:
firebase_uid_xyz789

PassKadam User ID:
USR-000456

Role:
EMPLOYER

Organization:
ABC Construction Pvt Ltd

Organization Status:
APPROVED

User Status:
ACTIVE
```

---

# 10. Canonical Application Identity Model

Conceptual `UserAccount`:

```text
UserAccount
────────────────────────────
id
firebase_uid
role
status
email
organization_id
created_at
updated_at
last_login_at
```

Conceptual `Organization`:

```text
Organization
────────────────────────────
id
name
organization_type
status
official_email
registration_reference
created_at
updated_at
```

Relationship:

```text
Firebase UID
      ↓
UserAccount
      ↓
Role
      ↓
Organization (if applicable)
      ↓
Permissions
```

The exact database schema is implementation-configurable.

---

# 11. Canonical Roles

```text
WORKER
EMPLOYER
GOVERNMENT
ADMIN
AADHAAR_AUTHORITY
```

Do not trust a role value sent by the browser.

The backend must resolve the actual role from authoritative application data.

---

# 12. Account Status

Common application-level statuses:

```text
PENDING
ACTIVE
SUSPENDED
DISABLED
REJECTED
```

Role-specific statuses may also exist.

### Worker

```text
REGISTERED
EMAIL_PENDING
PHONE_PENDING
ACTIVE
SUSPENDED
DISABLED
```

### Employer

```text
PENDING_REVIEW
APPROVED
REJECTED
SUSPENDED
```

### Government

```text
PENDING_REVIEW
APPROVED
SUSPENDED
DISABLED
```

### Admin

```text
ACTIVE
SUSPENDED
DISABLED
```

### Aadhaar Authority

```text
ACTIVE
SUSPENDED
DISABLED
```

---

# 13. Worker Registration

Worker registration begins in the React web application.

Inputs:

```text
Full Name
Email
Phone Number
Password
Confirm Password
```

Flow:

```text
Worker
   ↓
React Registration Form
   ↓
Firebase createUserWithEmailAndPassword()
   ↓
Firebase UID created
   ↓
PassKhadam UserAccount created / synchronized
   ↓
Worker onboarding continues
```

---

# 14. Worker Email Verification

```text
Worker Registration
        ↓
Firebase Account Created
        ↓
Verification Email Sent
        ↓
Worker Opens Verification Link
        ↓
Firebase emailVerified = true
        ↓
Worker returns to PassKhadam
        ↓
Firebase user state refreshed
        ↓
PassKhadam backend verifies Firebase ID Token
        ↓
Backend confirms email verification
```

Before verification:

```text
EMAIL VERIFIED = FALSE
```

After verification:

```text
EMAIL VERIFIED = TRUE
```

---

# 15. Worker Phone Verification

After email verification:

```text
Worker
   ↓
Enter / confirm phone number
   ↓
Firebase Phone Authentication
   ↓
OTP Sent
   ↓
Worker enters OTP
   ↓
Firebase verifies OTP
   ↓
Phone Number Verified
   ↓
PassKhadam profile updated
```

Result:

```text
EMAIL VERIFIED ✓
PHONE VERIFIED ✓
```

---

# 16. Worker Account Activation

The worker account becomes fully active after the required contact-verification conditions are satisfied.

Conceptually:

```text
Firebase Account Created
        ↓
Email Verified
        ↓
Phone Verified
        ↓
PassKhadam Account ACTIVE
```

Government identity verification remains a separate later process.

Therefore:

```text
Firebase Account
        ≠
Government Identity
```

---

# 17. Worker Sign-In

Existing worker:

```text
Worker opens Login
        ↓
Email
+
Password
        ↓
Firebase Authentication
        ↓
Authentication success
        ↓
Firebase ID Token
        ↓
React obtains authenticated Firebase user
        ↓
React calls PassKhadam /me or session endpoint
        ↓
FastAPI verifies Firebase ID Token
        ↓
Firebase UID resolved
        ↓
Worker UserAccount loaded
        ↓
Account status checked
        ↓
WORKER role checked
        ↓
Worker Portal
```

---

# 18. Employer Registration

Employer registration is an organization onboarding process.

The employer provides:

```text
Company / Organization Name
Registration Number
Business Address
Contact Person
Official Email
Phone Number
Business Type
Nature of Business
Requested Employment Categories
Requested Employment Levels
Nature of Requested Employment
Expected Workforce
Supporting Documents
```

Firebase can be used to establish the employer user's authentication identity while the organization itself remains:

```text
PENDING_REVIEW
```

until approved.

---

# 19. Employer Firebase Account Flow

```text
Employer Registration
        ↓
Firebase Account Created
        ↓
Email Verification
        ↓
PassKhadam Organization Created
        ↓
Organization Status = PENDING_REVIEW
        ↓
Admin Review
        ↓
Approved
        ↓
Secure Activation
        ↓
Employer User / Organization = ACTIVE
```

---

# 20. Employer Admin Approval

The admin reviews:

```text
Company legitimacy
Business details
Registration information
Requested employment categories
Requested employment levels
Nature of employment
Supporting documents
Organization contact information
```

Possible outcomes:

```text
APPROVE
REJECT
REQUEST MORE INFORMATION
SUSPEND
```

The employer must not gain operational employer access simply because its Firebase account exists.

---

# 21. Employer Secure Activation

After approval:

```text
Admin Approves Organization
        ↓
Secure Activation Token / Link Generated
        ↓
Activation Link Sent to Registered Employer Email
        ↓
Employer Opens Link
        ↓
Employer Completes Account Activation / Password Setup
        ↓
Firebase Authentication Account Ready
        ↓
PassKhadam Organization = ACTIVE
        ↓
Employer Can Sign In
```

Do not email plaintext passwords when a secure activation mechanism is available.

---

# 22. Employer Login

```text
Employer
   ↓
Email + Password
   ↓
Firebase Authentication
   ↓
Firebase ID Token
   ↓
FastAPI verifies ID token
   ↓
Firebase UID
   ↓
Employer UserAccount lookup
   ↓
Organization lookup
   ↓
Organization status check
   ↓
Employer role check
   ↓
Employer permissions check
   ↓
Employer Portal
```

---

# 23. Employer Access Denial Conditions

The employer should be denied normal employer access if:

```text
Firebase authentication failed
Firebase account disabled
PassKhadam account suspended
Organization pending review
Organization rejected
Organization suspended
Employer role missing
Required permission missing
```

---

# 24. Government Authority Onboarding

Government access should not be granted by simply selecting a “Government” role on a public form.

Recommended:

```text
Government Authority / Department
        ↓
Authority / Department Registration or Provisioning
        ↓
Officer Account
        ↓
Firebase Identity
        ↓
Email Verification / Secure Activation
        ↓
Admin Review
        ↓
Approval
        ↓
Permission Assignment
        ↓
Account ACTIVE
```

---

# 25. Government Officer Login

```text
Government Officer
        ↓
Login
        ↓
Firebase Authentication
        ↓
Firebase ID Token
        ↓
FastAPI Token Verification
        ↓
Firebase UID
        ↓
Government Officer Lookup
        ↓
Government Organization Lookup
        ↓
Organization Status
        ↓
Officer Status
        ↓
Department / Scope
        ↓
Permission Check
        ↓
Government Portal
```

---

# 26. Government Permissions

Government authorization should resolve:

```text
Government Organization
+
Officer
+
Department / Scope
+
Permissions
```

Example:

```text
Role:
GOVERNMENT

Allowed:
VERIFY_WORKER ✓
WELFARE_ELIGIBILITY ✓
BENEFIT_CLAIMS ✓
CROSS_STATE_VERIFY ✓

Not Allowed:
ADMIN_ORGANIZATION_APPROVAL ✕
EMPLOYER_CATEGORY_GOVERNANCE ✕
```

---

# 27. Platform Admin Provisioning

Admin accounts must not be openly self-registered.

Preferred:

```text
Existing Authorized Admin
        ↓
Creates / Provisions Admin User
        ↓
Firebase Authentication Identity
        ↓
ADMIN role assigned server-side
        ↓
Admin Account ACTIVE
```

Alternative secure provisioning mechanisms may be introduced.

---

# 28. Admin Login

```text
Admin
   ↓
Email + Password
   ↓
Firebase Authentication
   ↓
Firebase ID Token
   ↓
FastAPI verifies token
   ↓
Firebase UID
   ↓
Admin UserAccount
   ↓
ADMIN role verification
   ↓
Admin status verification
   ↓
Admin permissions
   ↓
Admin Portal
```

---

# 29. Admin Security Rule

Never implement:

```text
User selects:
[ADMIN]
```

and treat the selection as authorization.

Correct:

```text
Firebase UID
        ↓
Backend UserAccount
        ↓
Stored ADMIN role
        ↓
Stored permissions
        ↓
Admin endpoint access
```

---

# 30. Aadhaar Authority Human User

The Aadhaar Authority Portal can use Firebase for human operators.

Flow:

```text
Authorized Aadhaar Authority Operator
        ↓
Firebase Account
        ↓
Email Verification / Secure Activation
        ↓
AADHAAR_AUTHORITY role assigned server-side
        ↓
Login
        ↓
FastAPI authorization
        ↓
Aadhaar Authority Portal
```

---

# 31. Aadhaar API Machine Authentication

The actual PassKhadam backend-to-Aadhaar API communication is separate.

```text
PassKhadam Backend
        ↓
Service-to-Service Authentication
        ↓
Mock Aadhaar API
        ↓
Verification Response
```

Do not use a Firebase human-user token as a permanent service credential.

---

# 32. Shared Login Pipeline

All human roles should follow:

```text
                         LOGIN
                           │
                           ▼
                Firebase Authentication
                           │
                  Success / Failure
                    │            │
                   FAIL        SUCCESS
                    │            │
                    ▼            ▼
                  Reject      Firebase ID Token
                                  │
                                  ▼
                              React App
                                  │
                                  ▼
                              FastAPI
                                  │
                                  ▼
                      Verify Firebase ID Token
                                  │
                                  ▼
                            Firebase UID
                                  │
                                  ▼
                      PassKhadam User Lookup
                                  │
                                  ▼
                           Account Status
                                  │
                                  ▼
                               Role
                                  │
                                  ▼
                           Organization
                             where needed
                                  │
                                  ▼
                           Permissions
                                  │
                                  ▼
                         Authorized Portal
```

---

# 33. Firebase ID Token Flow

After Firebase authentication:

```text
Firebase
   ↓
ID Token
   ↓
React
   ↓
Authorization: Bearer <ID_TOKEN>
   ↓
FastAPI
   ↓
Firebase Admin SDK verification
   ↓
Verified Firebase UID
```

Backend must validate token authenticity and validity before processing protected requests.

---

# 34. Backend User Resolution

```text
Firebase UID
        ↓
UserAccount lookup
        ↓
Exists?
   ┌────┴────┐
  NO        YES
   │          │
   ▼          ▼
Reject    Account Status
              │
              ▼
             Role
              │
              ▼
          Organization
              │
              ▼
          Permissions
```

---

# 35. `/me` / Session Context

After authentication the frontend should retrieve its PassKhadam application context from FastAPI.

Conceptually:

```http
GET /api/me
Authorization: Bearer <firebase-id-token>
```

Possible response:

```json
{
  "user_id": "USR-000123",
  "firebase_uid": "firebase_uid_abc123",
  "role": "WORKER",
  "status": "ACTIVE",
  "organization_id": null,
  "permissions": [
    "VIEW_PROFILE",
    "VIEW_CREDENTIALS",
    "GENERATE_PRESENTATION"
  ]
}
```

Employer example:

```json
{
  "user_id": "USR-000456",
  "firebase_uid": "firebase_uid_xyz789",
  "role": "EMPLOYER",
  "status": "ACTIVE",
  "organization_id": "ORG-000045",
  "permissions": [
    "VERIFY_WORKER",
    "CREATE_EMPLOYMENT",
    "UPDATE_EMPLOYMENT",
    "REQUEST_CATEGORY"
  ]
}
```

The response schema is implementation-configurable.

---

# 36. Portal Routing

React should not route based solely on a user-selected role.

Instead:

```text
Firebase Login
      ↓
GET /api/me
      ↓
Backend returns authorized role/context
      ↓
React selects permitted portal
```

Conceptual:

```text
ROLE
 │
 ├── WORKER → Worker Portal
 ├── EMPLOYER → Employer Portal
 ├── GOVERNMENT → Government Portal
 ├── ADMIN → Admin Portal
 └── AADHAAR_AUTHORITY → Aadhaar Authority Portal
```

---

# 37. Role Switching

A role switcher may exist in development/demo mode.

It must not modify real authorization.

Development:

```text
Developer
   ↓
Select simulated role
   ↓
Backend creates controlled test context
```

Production:

```text
Firebase UID
   ↓
Stored application role
   ↓
Stored permissions
```

Never:

```text
Frontend dropdown
   ↓
role = ADMIN
   ↓
Admin access
```

---

# 38. Fine-Grained Employer Permissions

Employer authorization should resolve:

```text
User
 ↓
Employer Organization
 ↓
Organization Status
 ↓
Employment Categories
 ↓
Employment Levels
 ↓
Nature of Employment
 ↓
Functional Permissions
```

Example:

```text
ABC Construction

Mason → Allowed
Electrician → Allowed
Plumber → Allowed

Heavy Machinery Operator → Not Allowed
```

The browser may hide unauthorized options for UX, but the backend must enforce them.

---

# 39. Government Fine-Grained Permissions

Government authorization can depend on:

```text
Authority
Department
Officer
Permission Scope
```

Example:

```text
Officer A
→ Worker Verification

Officer B
→ Worker Verification
→ Benefit Eligibility

Officer C
→ Benefit Claims
→ Disbursement
```

A government officer must not inherit admin powers simply because they are authenticated.

---

# 40. Organization and User Relationship

An organization may contain multiple users.

### Employer example

```text
ABC Construction
       │
       ├── Employer Admin
       ├── Employer HR
       └── Employer Verifier
```

All users can authenticate through Firebase.

Their PassKhadam permissions can differ.

### Government example

```text
Migrant Welfare Authority
       │
       ├── Verification Officer
       ├── Welfare Officer
       └── Audit Officer
```

This is preferable to shared organization passwords.

---

# 41. Password Reset

Firebase handles password reset.

```text
Login
   ↓
Forgot Password
   ↓
Registered Email
   ↓
Firebase Password Reset Email
   ↓
User Opens Link
   ↓
New Password
   ↓
Firebase Updates Password
   ↓
User Logs In
```

PassKhadam should not store application passwords itself.

---

# 42. Email Change

Conceptual:

```text
Authenticated User
        ↓
Request Email Change
        ↓
Re-authenticate if required
        ↓
New Email
        ↓
Firebase Verification
        ↓
Email Updated
        ↓
PassKhadam Profile Synchronized
```

---

# 43. Phone Change

Conceptual:

```text
Authenticated User
        ↓
Request Phone Change
        ↓
OTP to New Number
        ↓
Firebase Verification
        ↓
Phone Updated
        ↓
PassKhadam Profile Synchronized
```

An unverified new phone number must not immediately become the trusted verified number.

---

# 44. Logout

Logout should clear the Firebase authentication state.

```text
User
   ↓
Logout
   ↓
Firebase signOut()
   ↓
Client auth state cleared
   ↓
Cached application session/context cleared
   ↓
Protected route blocked
   ↓
Login page
```

---

# 45. Session Persistence

Use Firebase SDK-supported session persistence.

The frontend should not invent an unsafe long-lived token storage strategy.

Conceptually:

```text
Firebase Auth State
        ↓
React Auth Listener
        ↓
Current Firebase User
        ↓
Current ID Token
        ↓
FastAPI Authorization
```

---

# 46. Token Refresh

Conceptually:

```text
Firebase User
        ↓
Current ID Token
        ↓
Token expiration approaching
        ↓
Firebase SDK refreshes token as supported
        ↓
Frontend retrieves valid current token
        ↓
API request
```

FastAPI must validate protected tokens server-side.

---

# 47. Account Suspension

If:

```text
PassKhadam account = SUSPENDED
```

then:

```text
Firebase Login ✓
        ↓
FastAPI User Lookup
        ↓
Status = SUSPENDED
        ↓
Protected access denied
```

Firebase authentication alone is not sufficient for PassKhadam portal access.

---

# 48. Firebase Account Disabled vs PassKhadam Suspension

These are separate states.

```text
Firebase account disabled
        ↓
Firebase authentication blocked

PassKhadam account suspended
        ↓
Firebase may authenticate
        ↓
Application access blocked
```

Both must be handled.

---

# 49. Login Failure States

Potential outcomes:

```text
Invalid email/password
Email not verified
Phone not verified where required
Firebase account disabled
PassKhadam account suspended
Employer organization pending
Employer organization rejected
Employer organization suspended
Government authority pending
Government authority suspended
Admin not authorized
Role not assigned
Permission denied
Firebase unavailable
FastAPI unavailable
```

User-facing messages should reveal only appropriate information.

---

# 50. Public Authentication Entry Points

Recommended public entry points:

```text
Sign In
Register as Worker
Register as Employer
```

Government, Admin and Aadhaar Authority access should use controlled provisioning / onboarding rather than unrestricted public role selection.

---

# 51. Login UI Design

A shared login interface may display:

```text
PASSKHADAM

Email
Password

[ Sign In ]

Forgot password?

Register as Worker
Register as Employer
```

Do not make the selected portal determine authorization.

After authentication:

```text
Backend determines role
        ↓
Redirect to authorized portal
```

---

# 52. Multi-Role / Multi-Account Model

The baseline implementation can use one primary application role per PassKhadam user account.

For example:

```text
Firebase UID A
→ WORKER

Firebase UID B
→ EMPLOYER

Firebase UID C
→ GOVERNMENT

Firebase UID D
→ ADMIN
```

If future multi-role support is introduced:

```text
Firebase UID
        ↓
Multiple PassKhadam role assignments
        ↓
Explicit permission context
```

A frontend role selector must never be enough to assume a role.

---

# 53. Demo Authentication Adapter

A development-only auth adapter may be provided:

```text
FirebaseAuthProvider
MockAuthProvider
```

Both should conform to a common application-level interface.

Example:

```text
AuthProvider
 ├── Firebase
 └── Mock / Dev
```

Mock mode must be explicitly enabled.

Example:

```env
AUTH_PROVIDER=firebase
```

Development:

```env
AUTH_PROVIDER=mock
```

The default should remain Firebase for the actual product path.

---

# 54. Firebase Admin SDK

FastAPI should verify Firebase ID tokens using the Firebase Admin SDK / trusted server-side verification mechanism.

The backend must have access to the appropriate Firebase project credentials through secure server-side configuration.

Never expose Admin SDK private keys to React.

Example conceptual environment configuration:

```env
FIREBASE_PROJECT_ID=passkhadam-live
FIREBASE_CLIENT_EMAIL=<server-side-service-account-email>
FIREBASE_PRIVATE_KEY=<server-side-secret>
```

The exact credentials depend on the selected Firebase server integration.

---

# 55. Firebase Project Consistency

The frontend and backend must target the same Firebase project:

```text
Firebase Project ID:
passkhadam-live
```

The backend token verifier must trust the same Firebase project that issues the frontend ID tokens.

Do not mix:

```text
Frontend → passkhadam-live
Backend → different Firebase project
```

unless explicitly implementing a multi-project architecture.

---

# 56. Firebase Environment Configuration

Recommended environment separation:

## Frontend

```env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=passkhadam-live.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=passkhadam-live
VITE_FIREBASE_STORAGE_BUCKET=passkhadam-live.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=854979434504
VITE_FIREBASE_APP_ID=1:854979434504:web:f7378b2c22039d3b1159bd
```

## Backend

```env
FIREBASE_PROJECT_ID=passkhadam-live
FIREBASE_CLIENT_EMAIL=<server-side>
FIREBASE_PRIVATE_KEY=<server-side>
```

The backend does not need to expose the Firebase client configuration to callers.

---

# 57. Authentication / Authorization Request Lifecycle

Every protected request follows:

```text
React
  ↓
Firebase currentUser
  ↓
Get current ID token
  ↓
HTTP Request
  ↓
Authorization: Bearer <token>
  ↓
FastAPI
  ↓
Verify Firebase token
  ↓
Resolve Firebase UID
  ↓
Load PassKhadam account
  ↓
Check account status
  ↓
Resolve role
  ↓
Resolve organization / department
  ↓
Resolve permissions
  ↓
Authorize endpoint
  ↓
Execute operation
```

---

# 58. Critical Security Boundaries

Never allow the following:

```text
Frontend role string → privilege
Firebase UID alone → admin access
Firebase authentication → government identity verification
Firebase authentication → employer approval
Employer authentication → unrestricted employment authority
Government authentication → unrestricted benefit authority
Aadhaar portal login → backend service credential
Mock login → production privilege
```

Correct model:

```text
Authentication
+
Application Authorization
+
Organization Authorization
+
Action Permission
```

---

# 59. Authentication Acceptance Criteria

## Worker

```text
[ ] Worker can register using Firebase
[ ] Email verification works
[ ] Phone OTP works
[ ] Worker can log in after verification
[ ] Firebase ID token reaches FastAPI
[ ] FastAPI verifies token
[ ] Worker role resolved server-side
[ ] Worker portal opens
[ ] Suspended worker is blocked
[ ] Logout works
[ ] Password reset works
```

## Employer

```text
[ ] Employer can register
[ ] Firebase account can be created
[ ] Email verification works
[ ] Organization begins as PENDING_REVIEW
[ ] Admin approval is required
[ ] Secure activation link is sent after approval
[ ] Employer can activate account
[ ] Employer can log in
[ ] Organization status is checked server-side
[ ] Employer permissions are resolved server-side
[ ] Suspended employer is blocked
```

## Government

```text
[ ] Government authority/officer account is provisioned
[ ] Firebase identity exists
[ ] Email verification / activation works
[ ] Admin approval / authorization works
[ ] Government officer can log in
[ ] Government role is resolved server-side
[ ] Organization and department permissions are enforced
[ ] Suspended officer is blocked
```

## Admin

```text
[ ] No unrestricted public admin signup
[ ] Admin account is securely provisioned
[ ] Firebase login works
[ ] ADMIN role is stored server-side
[ ] Admin portal is protected
[ ] Non-admin cannot call admin APIs
```

## Aadhaar Authority

```text
[ ] Authority operator can authenticate
[ ] Authority portal is protected
[ ] Human Firebase authentication is separated from machine API authentication
[ ] Non-authority cannot access authority-management APIs
```

---

# 60. Authentication Security Test Cases

The implementation should test:

```text
Valid Firebase login
Invalid password
Unverified email
Unverified phone
Expired Firebase token
Invalid Firebase token
Disabled Firebase user
PassKhadam suspended account
Pending employer
Rejected employer
Suspended employer
Unauthorized employer endpoint
Unauthorized government endpoint
Unauthorized admin endpoint
Unauthorized Aadhaar endpoint
Frontend role manipulation
Role escalation
Organization permission bypass
```

---

# 61. Firebase Console Configuration Checklist

The Firebase project:

```text
passkhadam-live
```

should be configured with:

```text
[ ] Web application registered
[ ] Email/Password provider enabled
[ ] Phone provider enabled
[ ] Authorized domains configured
[ ] Email verification enabled
[ ] Password reset enabled
[ ] Appropriate SMS / phone-auth configuration
[ ] Firebase Admin SDK / server verification configured
[ ] Development and production environments separated appropriately
```

The exact Firebase Console settings depend on the eventual deployment environment.

---

# 62. Recommended Auth File Structure

A possible frontend structure:

```text
frontend/
└── src/
    ├── lib/
    │   └── firebase.js
    │
    ├── auth/
    │   ├── AuthProvider.jsx
    │   ├── useAuth.js
    │   ├── ProtectedRoute.jsx
    │   └── roleRouting.js
    │
    └── pages/
        ├── Login.jsx
        ├── WorkerRegister.jsx
        ├── EmployerRegister.jsx
        └── ...
```

Possible backend:

```text
backend/
└── app/
    ├── core/
    │   ├── firebase.py
    │   └── config.py
    │
    ├── auth/
    │   ├── dependencies.py
    │   ├── roles.py
    │   └── permissions.py
    │
    └── api/
        └── endpoints/
```

Exact file structure may change.

---

# 63. Firebase Authentication Does Not Replace RBAC

Firebase answers:

```text
Who is the user?
```

PassKhadam answers:

```text
What is the user's role?
Which organization do they belong to?
What is the organization's status?
Which actions are permitted?
```

This separation must remain intact.

---

# 64. Complete Role Authentication Map

```text
                           FIREBASE
                              │
       ┌──────────────┬───────┼────────┬──────────────┐
       │              │       │        │              │
       ▼              ▼       ▼        ▼              ▼
    Worker         Employer  Govt     Admin       Aadhaar
       │              │       │        │              │
       │              │       │        │              │
       └──────────────┴───────┴────────┴──────────────┘
                              │
                              ▼
                       Firebase ID Token
                              │
                              ▼
                           FastAPI
                              │
                              ▼
                    Token Verification
                              │
                              ▼
                       Firebase UID
                              │
                              ▼
                    PassKhadam Account
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
         Role             Organization         Status
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                         Permissions
                              │
                              ▼
                        Portal Access
```

---

# 65. Full Authentication Journey by Role

## Worker

```text
Register
 ↓
Firebase Account
 ↓
Email Verify
 ↓
Phone OTP
 ↓
PassKhadam Account ACTIVE
 ↓
Login
 ↓
Firebase ID Token
 ↓
FastAPI Verification
 ↓
WORKER role
 ↓
Worker Portal
```

## Employer

```text
Register Organization
 ↓
Firebase Account
 ↓
Email Verify
 ↓
Organization PENDING_REVIEW
 ↓
Admin Approval
 ↓
Secure Activation Email
 ↓
Organization ACTIVE
 ↓
Login
 ↓
Firebase ID Token
 ↓
FastAPI Verification
 ↓
EMPLOYER + Organization + Permissions
 ↓
Employer Portal
```

## Government

```text
Authority / Officer Provisioning
 ↓
Firebase Account
 ↓
Email Verify / Activation
 ↓
Admin Authorization
 ↓
Organization + Officer Permissions
 ↓
Login
 ↓
Firebase ID Token
 ↓
FastAPI Verification
 ↓
GOVERNMENT + Organization + Scope
 ↓
Government Portal
```

## Admin

```text
Secure Provisioning
 ↓
Firebase Account
 ↓
ADMIN role assigned server-side
 ↓
Login
 ↓
Firebase ID Token
 ↓
FastAPI Verification
 ↓
ADMIN authorization
 ↓
Admin Portal
```

## Aadhaar Authority

```text
Secure Operator Provisioning
 ↓
Firebase Account
 ↓
Activation / Email Verification
 ↓
AADHAAR_AUTHORITY role
 ↓
Login
 ↓
Firebase ID Token
 ↓
FastAPI Verification
 ↓
Authority Permissions
 ↓
Aadhaar Authority Portal
```

---

# 66. Machine-to-Machine Aadhaar Flow

```text
PassKhadam Backend
        ↓
Service Authentication
        ↓
Mock Aadhaar API
        ↓
Request Validation
        ↓
Aadhaar Verification
        ↓
Response
        ↓
PassKhadam Identity Service
```

This is independent of a human operator's Firebase login.

---

# 67. Final Authentication Rules

The following rules are authoritative:

```text
1. Firebase Authentication is the baseline human authentication provider.
2. Firebase UID identifies the authenticated account.
3. Firebase UID is not itself a business role.
4. PassKhadam resolves roles server-side.
5. PassKhadam resolves organization membership server-side.
6. PassKhadam resolves permissions server-side.
7. Frontend role selection never grants privilege.
8. Workers require email and phone verification according to the baseline onboarding policy.
9. Employer organizations require admin approval before operational access.
10. Employer activation uses secure email activation.
11. Government authority access requires controlled provisioning / approval.
12. Admin accounts are not unrestricted public registrations.
13. Aadhaar Authority human users may authenticate through Firebase.
14. PassKhadam-to-Aadhaar API communication uses service authentication.
15. Firebase authentication does not prove Aadhaar identity.
16. Firebase authentication does not prove employer authorization.
17. Firebase authentication does not prove government benefit authority.
18. Suspended / disabled PassKhadam accounts cannot use protected functionality.
19. Backend validates Firebase ID tokens for protected routes.
20. Backend checks organization status for organization users.
21. Backend checks fine-grained permissions.
22. Passwords are managed by Firebase, not stored by PassKhadam.
23. Mock authentication is development-only.
24. Firebase Admin credentials never appear in frontend code.
25. Firebase project configuration must remain consistent across frontend and backend.
```

---

# 68. Final Firebase Project Reference

Current Firebase project:

```text
Project ID:
passkhadam-live

Auth Domain:
passkhadam-live.firebaseapp.com

Storage Bucket:
passkhadam-live.firebasestorage.app

Messaging Sender ID:
854979434504

Web App ID:
1:854979434504:web:f7378b2c22039d3b1159bd
```

Current manually generated Web SDK initialization:

```javascript
import { initializeApp } from "firebase/app";

const firebaseConfig = {
  apiKey: "AIzaSyAm2y_rprQk5C51aD_1UTcw4pyfI-vsrHQ",
  authDomain: "passkhadam-live.firebaseapp.com",
  projectId: "passkhadam-live",
  storageBucket: "passkhadam-live.firebasestorage.app",
  messagingSenderId: "854979434504",
  appId: "1:854979434504:web:f7378b2c22039d3b1159bd"
};

const app = initializeApp(firebaseConfig);
```

> Note: The API key above is a browser-facing Firebase configuration value. It should still be protected by correctly configured Firebase Authentication settings, authorized domains, API restrictions where appropriate, and backend security rules. Never expose Firebase Admin SDK service-account private keys in frontend code.

---

# 69. Change Policy

This document is the current baseline for PassKhadam authentication.

> **Any changes to authentication flow, Firebase configuration, role provisioning, session architecture, authorization structure, organization onboarding, or machine-to-machine authentication are allowed when they improve security, privacy, usability, reliability, maintainability, scalability, or deployment readiness.**

Any significant change should be synchronized across:

```text
Product Specification
Implementation Plan
Teamwork Prompt
Walkthrough
README
Authentication Documentation
```

---

# 70. Final Definition

> **PassKhadam uses the Firebase project `passkhadam-live` as the common human authentication foundation for Worker, Employer, Government, Admin, and Aadhaar Authority portal users. Firebase authenticates the account and issues the Firebase ID token; FastAPI verifies that token and resolves the authoritative PassKhadam role, organization, account status, and permissions before granting portal or API access.**
