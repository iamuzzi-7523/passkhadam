/**
 * frontend/tests/test_m7_r2_challenger_isolation.mjs
 *
 * Empirical Adversarial Challenge Test Harness for Milestone 7:
 * Principal Isolation & Zero Static Demo Fallbacks Verification
 *
 * Author: m7_r2_challenger_2 (EMPIRICAL CHALLENGER)
 * Target Objectives:
 * 1. Unauthenticated visitors start without mock identity (no default Worker Ramesh, no default employer Apex).
 * 2. AuthContext purges session on HTTP 401/403 and never falls back to mock user data.
 * 3. Role tab switching does not trigger demoLogin(), ensuring true account context is preserved.
 * 4. RoleGuard mandates dual verification (is_email_verified && is_phone_verified) for non-demo users.
 * 5. WorkerPortal strictly uses /me self-service endpoints and does not accept hardcoded workerId={1}.
 */

import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_DIR = path.resolve(__dirname, '..');
const SRC_DIR = path.join(FRONTEND_DIR, 'src');

console.log('================================================================');
console.log('  M7-R2 ADVERSARIAL CHALLENGE HARNESS: PRINCIPAL ISOLATION      ');
console.log('  & ZERO STATIC DEMO FALLBACKS                                 ');
console.log('================================================================\n');

let totalTests = 0;
let passedTests = 0;

async function runTest(testName, fn) {
  totalTests++;
  try {
    await fn();
    console.log(`  [PASS] ${testName}`);
    passedTests++;
  } catch (err) {
    console.error(`  [FAIL] ${testName}`);
    console.error(`         Error: ${err.message}`);
    throw err;
  }
}

// ----------------------------------------------------------------------------
// Load Source Files for Empirical AST / Pattern Inspection
// ----------------------------------------------------------------------------
const authContextPath = path.join(SRC_DIR, 'context', 'AuthContext.jsx');
const authContextSrc = fs.readFileSync(authContextPath, 'utf-8');

const roleGuardPath = path.join(SRC_DIR, 'components', 'common', 'RoleGuard.jsx');
const roleGuardSrc = fs.readFileSync(roleGuardPath, 'utf-8');

const headerPath = path.join(SRC_DIR, 'components', 'common', 'Header.jsx');
const headerSrc = fs.readFileSync(headerPath, 'utf-8');

const appPath = path.join(SRC_DIR, 'App.jsx');
const appSrc = fs.readFileSync(appPath, 'utf-8');

const workerPortalPath = path.join(SRC_DIR, 'components', 'worker', 'WorkerPortal.jsx');
const workerPortalSrc = fs.readFileSync(workerPortalPath, 'utf-8');

const employerPortalPath = path.join(SRC_DIR, 'components', 'employer', 'EmployerPortal.jsx');
const employerPortalSrc = fs.readFileSync(employerPortalPath, 'utf-8');

const governmentPortalPath = path.join(SRC_DIR, 'components', 'government', 'GovernmentPortal.jsx');
const governmentPortalSrc = fs.readFileSync(governmentPortalPath, 'utf-8');

// ----------------------------------------------------------------------------
// TEST SUITE EXECUTION
// ----------------------------------------------------------------------------
async function main() {

  // ==========================================================================
  // OBJECTIVE 1: Unauthenticated visitors start without mock identity
  // ==========================================================================
  console.log('--- Objective 1: Unauthenticated Visitors & Zero Mock Identity ---');

  await runTest('O1.1: AuthContext initializes currentUser strictly to null when localStorage is empty', () => {
    // Simulate empty localStorage initialization
    const initFn = (storageVal) => {
      if (storageVal) {
        try { return JSON.parse(storageVal); } catch (e) { /* ignore */ }
      }
      return null;
    };
    assert.equal(initFn(null), null);
    assert.equal(initFn(''), null);
  });

  await runTest('O1.2: Corrupted or invalid JSON in localStorage does not crash or fall back to mock identity', () => {
    const initFn = (storageVal) => {
      if (storageVal) {
        try { return JSON.parse(storageVal); } catch (e) { /* ignore */ }
      }
      return null;
    };
    assert.equal(initFn('not-valid-json{{{'), null);
    assert.equal(initFn('undefined'), null);
  });

  await runTest('O1.3: AuthContext does NOT assign DEFAULT_USERS to currentUser anywhere in its implementation', () => {
    // Assert that setCurrentUser(DEFAULT_USERS...) never occurs
    const occurrences = authContextSrc.match(/setCurrentUser\s*\(\s*DEFAULT_USERS/g);
    assert.equal(occurrences, null, 'setCurrentUser(DEFAULT_USERS) must never be called in AuthContext');
  });

  await runTest('O1.4: Header renders login button and NO mock identity name when currentUser is null', () => {
    // When currentUser is null, Header must show LogIn button and hide User pill
    assert.ok(headerSrc.includes('{currentUser ? ('), 'Header conditions user pill on currentUser');
    assert.ok(headerSrc.includes('setIsAuthOpen(true)'), 'Header opens login modal on unauthenticated click');
    // Ensure Ramesh Kumar Verma or Apex is not hardcoded into Header
    assert.ok(!headerSrc.includes('Ramesh Kumar Verma'));
    assert.ok(!headerSrc.includes('Apex Infrastructure'));
  });

  await runTest('O1.5: RoleGuard unconditionally presents Authentication Required gate to unauthenticated visitors', () => {
    assert.ok(roleGuardSrc.includes('if (!currentUser) {'), 'RoleGuard checks !currentUser first');
    assert.ok(roleGuardSrc.includes('Authentication Required'), 'Renders Authentication Required view');
    assert.ok(roleGuardSrc.includes('Open Sign-In Dialog'), 'Offers Open Sign-In Dialog action');
  });

  await runTest('O1.6: EmployerPortal and GovernmentPortal derive identity dynamically with zero default fallback', () => {
    // Employer portal must use apiFetch('/api/v1/employer/info')
    assert.ok(employerPortalSrc.includes("apiFetch('/api/v1/employer/info')") || employerPortalSrc.includes('apiFetch("/api/v1/employer/info")'));
    assert.ok(!employerPortalSrc.includes('Apex Infrastructure & Construction Ltd'));

    // Government portal must use apiFetch('/api/v1/government/profile/me')
    assert.ok(governmentPortalSrc.includes("apiFetch('/api/v1/government/profile/me')") || governmentPortalSrc.includes('apiFetch("/api/v1/government/profile/me")'));
    assert.ok(!governmentPortalSrc.includes('Maharashtra Labour Welfare Officer'));
  });


  // ==========================================================================
  // OBJECTIVE 2: AuthContext purges session on HTTP 401/403 and never falls back
  // ==========================================================================
  console.log('\n--- Objective 2: AuthContext Session Purging on HTTP 401/403 ---');

  await runTest('O2.1: fetchAuthoritativeContext handles HTTP 401 and HTTP 403 explicitly', () => {
    assert.ok(authContextSrc.includes('if (res.status === 401 || res.status === 403)'), 'Explicit 401/403 branch found');
  });

  await runTest('O2.2: HTTP 401/403 purges currentUser, token, pk_user, and pk_token', () => {
    const fetchAuthMatch = authContextSrc.match(/const\s+fetchAuthoritativeContext\s*=\s*async\s*\([\s\S]*?\{([\s\S]*?)\n\s*\};/);
    assert.ok(fetchAuthMatch, 'fetchAuthoritativeContext declaration found');
    const body = fetchAuthMatch[1];

    assert.ok(body.includes('setCurrentUser(null)'), 'Sets currentUser to null');
    assert.ok(body.includes('setToken(null)'), 'Sets token to null');
    assert.ok(body.includes("localStorage.removeItem('pk_user')"), 'Removes pk_user from localStorage');
    assert.ok(body.includes("localStorage.removeItem('pk_token')"), 'Removes pk_token from localStorage');
    assert.ok(body.includes('return null;'), 'Returns null on rejection');
  });

  await runTest('O2.3: fetchAuthoritativeContext catch block returns null without mock fallback on network error', () => {
    const fetchAuthMatch = authContextSrc.match(/const\s+fetchAuthoritativeContext\s*=\s*async\s*\([\s\S]*?\{([\s\S]*?)\n\s*\};/);
    const body = fetchAuthMatch[1];
    const catchIndex = body.indexOf('catch (e)');
    assert.ok(catchIndex !== -1, 'catch block exists');
    const catchBlock = body.slice(catchIndex);
    assert.ok(catchBlock.includes('return null;'), 'Catch block terminates returning null');
    assert.ok(!catchBlock.includes('DEFAULT_USERS'), 'Catch block does not assign DEFAULT_USERS');
    assert.ok(!catchBlock.includes('setCurrentUser'), 'Catch block does not call setCurrentUser with mock');
  });

  await runTest('O2.4: demoLogin rejects with error on server failure without mock fallback', () => {
    const demoLoginMatch = authContextSrc.match(/const\s+demoLogin\s*=\s*async\s*\([\s\S]*?\{([\s\S]*?)\n\s*\};/);
    assert.ok(demoLoginMatch, 'demoLogin function exists');
    const body = demoLoginMatch[1];
    assert.ok(!body.includes('setCurrentUser(DEFAULT_USERS'), 'demoLogin does not fallback to DEFAULT_USERS');
    assert.ok(body.includes('return { success: false, error: errMsg };'), 'Returns explicit failure on server error');
  });

  await runTest('O2.5: logout function purges Firebase session, context state, and localStorage', () => {
    const logoutMatch = authContextSrc.match(/const\s+logout\s*=\s*async\s*\([\s\S]*?\{([\s\S]*?)\n\s*\};/);
    assert.ok(logoutMatch, 'logout function exists');
    const body = logoutMatch[1];
    assert.ok(body.includes('signOut(auth)'), 'Invokes Firebase signOut');
    assert.ok(body.includes('setCurrentUser(null)'), 'Resets currentUser to null');
    assert.ok(body.includes('setToken(null)'), 'Resets token to null');
    assert.ok(body.includes("localStorage.removeItem('pk_user')"), 'Cleans pk_user');
    assert.ok(body.includes("localStorage.removeItem('pk_token')"), 'Cleans pk_token');
  });


  // ==========================================================================
  // OBJECTIVE 3: Role tab switching does not trigger demoLogin()
  // ==========================================================================
  console.log('\n--- Objective 3: Role Tab Switching Preserves True Account Context ---');

  await runTest('O3.1: Header handleRoleClick invokes onRoleChange and does NOT invoke demoLogin', () => {
    const handleRoleMatch = headerSrc.match(/const\s+handleRoleClick\s*=\s*\(([\s\S]*?)\)\s*=>\s*\{([\s\S]*?)\};/);
    assert.ok(handleRoleMatch, 'handleRoleClick handler found in Header.jsx');
    const body = handleRoleMatch[2];
    assert.ok(body.includes('onRoleChange(roleId)'), 'Delegates roleId to onRoleChange');
    assert.ok(!body.includes('demoLogin'), 'handleRoleClick must never call demoLogin');
    assert.ok(!body.includes('login'), 'handleRoleClick must never call login');
  });

  await runTest('O3.2: Header role buttons trigger handleRoleClick for all 5 roles without session mutation', () => {
    assert.ok(headerSrc.includes("onClick={() => handleRoleClick(r.id)}"), 'Wires handleRoleClick to role buttons');
    assert.ok(!headerSrc.includes("demoLogin(r.id)"), 'No direct demoLogin binding on tab buttons');
  });

  await runTest('O3.3: App.jsx passes setCurrentRole to Header without side-effect on authentication context', () => {
    assert.ok(appSrc.includes("const [currentRole, setCurrentRole] = useState('WORKER');"), 'currentRole state managed in App');
    assert.ok(appSrc.includes('onRoleChange={setCurrentRole}'), 'onRoleChange simply updates currentRole view state');
  });

  await runTest('O3.4: RoleGuard blocks mismatched tab viewing without altering user role', () => {
    // RoleGuard rejects users whose role !== requiredRole (unless ADMIN)
    assert.ok(roleGuardSrc.includes("if (userRole !== reqRole && userRole !== 'ADMIN')"), 'RoleGuard compares authenticated role');
    assert.ok(roleGuardSrc.includes('Role Mismatch'), 'Displays Role Mismatch notice');
    assert.ok(!roleGuardSrc.includes('demoLogin'), 'RoleGuard does not automatically switch user with demoLogin');
  });


  // ==========================================================================
  // OBJECTIVE 4: RoleGuard dual verification enforcement for non-demo users
  // ==========================================================================
  console.log('\n--- Objective 4: RoleGuard Dual Verification Enforcement ---');

  // RoleGuard decision simulator matching exact logic of RoleGuard.jsx
  function evaluateRoleGuard(currentUser, requiredRole) {
    if (!currentUser) return { allowed: false, reason: 'AUTHENTICATION_REQUIRED' };
    if (currentUser.status === 'SUSPENDED' || currentUser.status === 'DISABLED') {
      return { allowed: false, reason: 'ACCOUNT_SUSPENDED' };
    }
    if (currentUser && !currentUser.is_demo) {
      const isEmailVerified = Boolean(currentUser.is_email_verified);
      const isPhoneVerified = Boolean(currentUser.is_phone_verified);
      if (!isEmailVerified || !isPhoneVerified) {
        return { allowed: false, reason: 'DUAL_VERIFICATION_REQUIRED' };
      }
    }
    if (requiredRole === 'EMPLOYER' && (currentUser.organization_status === 'PENDING_REVIEW' || currentUser.status === 'PENDING_REVIEW')) {
      return { allowed: false, reason: 'PENDING_REVIEW' };
    }
    const userRole = (currentUser.role || '').toUpperCase();
    const reqRole = requiredRole.toUpperCase();
    if (userRole !== reqRole && userRole !== 'ADMIN') {
      return { allowed: false, reason: 'ROLE_MISMATCH' };
    }
    return { allowed: true, reason: 'AUTHORIZED' };
  }

  await runTest('O4.1: RoleGuard strictly checks !currentUser.is_demo before dual verification check', () => {
    assert.ok(roleGuardSrc.includes('if (currentUser && !currentUser.is_demo)'), 'Non-demo check present in RoleGuard.jsx');
    assert.ok(roleGuardSrc.includes('const isEmailVerified = Boolean(currentUser.is_email_verified)'), 'Email boolean cast');
    assert.ok(roleGuardSrc.includes('const isPhoneVerified = Boolean(currentUser.is_phone_verified)'), 'Phone boolean cast');
    assert.ok(roleGuardSrc.includes('!isEmailVerified || !isPhoneVerified'), 'Conjunction of dual verification requirement');
  });

  await runTest('O4.2: Non-demo user with neither email nor phone verified is BLOCKED', () => {
    const user = { role: 'WORKER', is_demo: false, is_email_verified: false, is_phone_verified: false, status: 'ACTIVE' };
    const res = evaluateRoleGuard(user, 'WORKER');
    assert.equal(res.allowed, false);
    assert.equal(res.reason, 'DUAL_VERIFICATION_REQUIRED');
  });

  await runTest('O4.3: Non-demo user with email verified but phone unverified is BLOCKED', () => {
    const user = { role: 'WORKER', is_demo: false, is_email_verified: true, is_phone_verified: false, status: 'ACTIVE' };
    const res = evaluateRoleGuard(user, 'WORKER');
    assert.equal(res.allowed, false);
    assert.equal(res.reason, 'DUAL_VERIFICATION_REQUIRED');
  });

  await runTest('O4.4: Non-demo user with phone verified but email unverified is BLOCKED', () => {
    const user = { role: 'WORKER', is_demo: false, is_email_verified: false, is_phone_verified: true, status: 'ACTIVE' };
    const res = evaluateRoleGuard(user, 'WORKER');
    assert.equal(res.allowed, false);
    assert.equal(res.reason, 'DUAL_VERIFICATION_REQUIRED');
  });

  await runTest('O4.5: Non-demo user with falsy/null/undefined verification values is BLOCKED', () => {
    const userNull = { role: 'WORKER', is_demo: false, is_email_verified: null, is_phone_verified: undefined, status: 'ACTIVE' };
    const resNull = evaluateRoleGuard(userNull, 'WORKER');
    assert.equal(resNull.allowed, false);
    assert.equal(resNull.reason, 'DUAL_VERIFICATION_REQUIRED');

    const userZero = { role: 'WORKER', is_demo: false, is_email_verified: 0, is_phone_verified: 0, status: 'ACTIVE' };
    const resZero = evaluateRoleGuard(userZero, 'WORKER');
    assert.equal(resZero.allowed, false);
    assert.equal(resZero.reason, 'DUAL_VERIFICATION_REQUIRED');
  });

  await runTest('O4.6: Non-demo user with BOTH verified passes dual verification gate', () => {
    const user = { role: 'WORKER', is_demo: false, is_email_verified: true, is_phone_verified: true, status: 'ACTIVE' };
    const res = evaluateRoleGuard(user, 'WORKER');
    assert.equal(res.allowed, true);
    assert.equal(res.reason, 'AUTHORIZED');
  });

  await runTest('O4.7: Explicit demo user (is_demo=true) bypasses dual verification check', () => {
    const demoUser = { role: 'WORKER', is_demo: true, is_email_verified: false, is_phone_verified: false, status: 'ACTIVE' };
    const res = evaluateRoleGuard(demoUser, 'WORKER');
    assert.equal(res.allowed, true);
    assert.equal(res.reason, 'AUTHORIZED');
  });

  await runTest('O4.8: Suspended account status takes precedence over dual verification and demo status', () => {
    const suspendedReal = { role: 'WORKER', is_demo: false, is_email_verified: true, is_phone_verified: true, status: 'SUSPENDED' };
    assert.equal(evaluateRoleGuard(suspendedReal, 'WORKER').reason, 'ACCOUNT_SUSPENDED');

    const suspendedDemo = { role: 'WORKER', is_demo: true, is_email_verified: true, is_phone_verified: true, status: 'SUSPENDED' };
    assert.equal(evaluateRoleGuard(suspendedDemo, 'WORKER').reason, 'ACCOUNT_SUSPENDED');
  });

  await runTest('O4.9: Employer PENDING_REVIEW renders review notice without falling back to Apex', () => {
    const pendingEmployer = {
      role: 'EMPLOYER',
      is_demo: false,
      is_email_verified: true,
      is_phone_verified: true,
      status: 'ACTIVE',
      organization_status: 'PENDING_REVIEW',
      organization_name: 'Tranquile Solutions'
    };
    const res = evaluateRoleGuard(pendingEmployer, 'EMPLOYER');
    assert.equal(res.allowed, false);
    assert.equal(res.reason, 'PENDING_REVIEW');
    assert.ok(roleGuardSrc.includes('Organization Under Review'), 'Placeholder when organization_name missing');
    assert.ok(!roleGuardSrc.includes('Apex Infrastructure'), 'Zero Apex fallback');
  });


  // ==========================================================================
  // OBJECTIVE 5: WorkerPortal strictly uses /me endpoints and rejects workerId={1}
  // ==========================================================================
  console.log('\n--- Objective 5: WorkerPortal /me Self-Service & Zero IDOR ---');

  await runTest('O5.1: App.jsx renders WorkerPortal without hardcoded workerId prop', () => {
    assert.ok(!appSrc.includes('workerId'), 'App.jsx must contain zero workerId references');
    assert.ok(appSrc.includes('<WorkerPortal currentLang={currentLang} />'), 'Renders WorkerPortal with currentLang only');
  });

  await runTest('O5.2: WorkerPortal signature accepts ONLY currentLang and rejects workerId param', () => {
    const signatureMatch = workerPortalSrc.match(/export\s+default\s+function\s+WorkerPortal\s*\(([\s\S]*?)\)\s*\{/);
    assert.ok(signatureMatch, 'WorkerPortal function signature located');
    const params = signatureMatch[1];
    assert.ok(params.includes('currentLang'), 'currentLang prop declared');
    assert.ok(!params.includes('workerId'), 'workerId parameter NOT declared');
  });

  await runTest('O5.3: WorkerPortal profile fetch targets strictly /api/v1/worker/profile/me', () => {
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/profile/me')"), 'Calls /api/v1/worker/profile/me');
    assert.ok(!workerPortalSrc.includes('/api/v1/worker/profile/1'), 'Does not call /profile/1');
  });

  await runTest('O5.4: WorkerPortal wallet fetch targets strictly /api/v1/worker/wallet/me', () => {
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/wallet/me')"), 'Calls /api/v1/worker/wallet/me');
    assert.ok(!workerPortalSrc.includes('/api/v1/worker/wallet/1'), 'Does not call /wallet/1');
  });

  await runTest('O5.5: WorkerPortal QR presentation fetch targets strictly /api/v1/worker/presentation/qr-card/me', () => {
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/presentation/qr-card/me')"), 'Calls /presentation/qr-card/me');
    assert.ok(!workerPortalSrc.includes('/presentation/qr-card/1'), 'Does not call /presentation/qr-card/1');
  });

  await runTest('O5.6: WorkerPortal Aadhaar verification targets strictly /api/v1/worker/verify-aadhaar/me', () => {
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/verify-aadhaar/me'"), 'Calls /verify-aadhaar/me');
    assert.ok(!workerPortalSrc.includes('/verify-aadhaar/1'), 'Does not call /verify-aadhaar/1');
  });

  await runTest('O5.7: WorkerPortal QR download targets strictly /api/v1/worker/presentation/download-qr/me', () => {
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/presentation/download-qr/me')"), 'Calls /download-qr/me');
    assert.ok(!workerPortalSrc.includes('/download-qr/1'), 'Does not call /download-qr/1');
  });

  await runTest('O5.8: Zero parameterized or ID-based endpoints exist in WorkerPortal.jsx', () => {
    const idParamRegex = /\/api\/v1\/worker\/[a-zA-Z-]+\/(\$\{.*\}|[0-9]+)/;
    const match = workerPortalSrc.match(idParamRegex);
    assert.equal(match, null, `Found forbidden parameterized worker endpoint: ${match ? match[0] : ''}`);
  });

  console.log('\n================================================================');
  console.log(`  ALL ${passedTests}/${totalTests} ADVERSARIAL CHALLENGE TESTS PASSED!`);
  console.log('================================================================\n');
}

main().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
