/**
 * frontend/tests/test_m6_frontend_invariants.mjs
 *
 * Empirical Challenger Test Suite for Milestone 6:
 * Frontend Authentication, Session Invariants, Demo Fallback Elimination,
 * RoleGuard Dual Verification & IDOR Elimination.
 *
 * Author: m6_challenger_1
 */

import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_DIR = path.resolve(__dirname, '..');

console.log('================================================================');
console.log('  RUNNING M6 FRONTEND ADVERSARIAL CHALLENGE SUITE (Node.js)    ');
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
// 1. Centralized apiFetch & formatMaskedAadhaar Unit Tests
// ----------------------------------------------------------------------------
import { formatMaskedAadhaar, apiFetch } from '../src/utils/api.js';

// Setup mock localStorage and global fetch for apiFetch test
const mockStorage = new Map();
global.localStorage = {
  getItem: (k) => mockStorage.get(k) || null,
  setItem: (k, v) => mockStorage.set(k, String(v)),
  removeItem: (k) => mockStorage.delete(k),
  clear: () => mockStorage.clear()
};

let lastFetchCall = null;
global.fetch = async (url, options) => {
  lastFetchCall = { url, options };
  return {
    ok: true,
    status: 200,
    json: async () => ({ success: true })
  };
};

async function main() {
  await runTest('R6.1.1 formatMaskedAadhaar formats 12 raw digits to XXXX-XXXX-XXXX', () => {
    assert.equal(formatMaskedAadhaar('123456789012'), 'XXXX-XXXX-9012');
    assert.equal(formatMaskedAadhaar(123456789012), 'XXXX-XXXX-9012');
  });

  await runTest('R6.1.2 formatMaskedAadhaar formats spaced or hyphenated 12 digits', () => {
    assert.equal(formatMaskedAadhaar('1234 5678 9012'), 'XXXX-XXXX-9012');
    assert.equal(formatMaskedAadhaar('1234-5678-9012'), 'XXXX-XXXX-9012');
    assert.equal(formatMaskedAadhaar('  1234  5678  9012  '), 'XXXX-XXXX-9012');
  });

  await runTest('R6.1.3 formatMaskedAadhaar preserves already masked Aadhaar ending in 4 digits', () => {
    assert.equal(formatMaskedAadhaar('XXXX-XXXX-9012'), 'XXXX-XXXX-9012');
    assert.equal(formatMaskedAadhaar('XXXX XXXX 9012'), 'XXXX-XXXX-9012');
    assert.equal(formatMaskedAadhaar(''), '');
    assert.equal(formatMaskedAadhaar(null), '');
    assert.equal(formatMaskedAadhaar(undefined), '');
  });

  await runTest('R6.1.4 apiFetch automatically injects Bearer token from localStorage', async () => {
    mockStorage.set('pk_token', 'jwt_test_token_abc123');
    await apiFetch('/api/v1/worker/profile/me');

    assert.ok(lastFetchCall);
    assert.equal(lastFetchCall.url, '/api/v1/worker/profile/me');
    assert.equal(lastFetchCall.options.headers['Authorization'], 'Bearer jwt_test_token_abc123');
  });

  await runTest('R6.1.5 apiFetch omits Authorization header when localStorage is empty', async () => {
    mockStorage.clear();
    await apiFetch('/api/v1/auth/me');

    assert.ok(lastFetchCall);
    assert.equal(lastFetchCall.options.headers['Authorization'], undefined);
  });

  await runTest('R6.1.6 apiFetch automatically serializes object body and sets application/json', async () => {
    mockStorage.clear();
    await apiFetch('/api/v1/auth/login', {
      method: 'POST',
      body: { email: 'worker@passkhadam.org', password: 'password123' }
    });

    assert.ok(lastFetchCall);
    assert.equal(lastFetchCall.options.headers['Content-Type'], 'application/json');
    assert.equal(lastFetchCall.options.body, JSON.stringify({ email: 'worker@passkhadam.org', password: 'password123' }));
  });

  // ----------------------------------------------------------------------------
  // 2. AuthContext Source Inspection & Invariants
  // ----------------------------------------------------------------------------
  const authContextPath = path.join(FRONTEND_DIR, 'src', 'context', 'AuthContext.jsx');
  const authContextSrc = fs.readFileSync(authContextPath, 'utf-8');

  await runTest('R6.2.1 AuthContext starts with null user when localStorage is empty (no default Worker #1)', () => {
    const userInitMatch = authContextSrc.match(/const\s*\[currentUser,\s*setCurrentUser\]\s*=\s*useState\(\(\)\s*=>\s*\{([\s\S]*?)\}\);/);
    assert.ok(userInitMatch, 'currentUser useState hook found in AuthContext.jsx');
    const body = userInitMatch[1];
    assert.ok(body.includes("localStorage.getItem('pk_user')"), 'Checks localStorage for pk_user');
    assert.ok(body.includes('return null;'), 'Defaults strictly to return null when empty');
    assert.ok(!body.includes('DEFAULT_USERS.WORKER'), 'Must NOT initialize with DEFAULT_USERS.WORKER');
  });

  await runTest('R6.2.2 AuthContext starts with null token when localStorage is empty', () => {
    const tokenInitMatch = authContextSrc.match(/const\s*\[token,\s*setToken\]\s*=\s*useState\(\(\)\s*=>\s*([\s\S]*?)\);/);
    assert.ok(tokenInitMatch, 'token useState hook found');
    const body = tokenInitMatch[1];
    assert.ok(body.includes("localStorage.getItem('pk_token') || null"), 'Defaults strictly to null if no token');
    assert.ok(!body.includes('pk_token_1_worker'), 'Must NOT initialize with pk_token_1_worker');
  });

  await runTest('R6.2.3 fetchAuthoritativeContext purges session on HTTP 401/403 and never falls back to mock user', () => {
    const fetchAuthMatch = authContextSrc.match(/const\s+fetchAuthoritativeContext\s*=\s*async\s*\([\s\S]*?\{([\s\S]*?)\n\s*\};/);
    assert.ok(fetchAuthMatch, 'fetchAuthoritativeContext function defined');
    const code = fetchAuthMatch[1];

    assert.ok(code.includes('res.status === 401 || res.status === 403'), 'Handles 401 and 403 explicitly');
    assert.ok(code.includes('setCurrentUser(null)'), 'Clears currentUser state on rejection');
    assert.ok(code.includes('setToken(null)'), 'Clears token state on rejection');
    assert.ok(code.includes("localStorage.removeItem('pk_user')"), 'Purges pk_user from localStorage');
    assert.ok(code.includes("localStorage.removeItem('pk_token')"), 'Purges pk_token from localStorage');
    assert.ok(!code.includes('DEFAULT_USERS'), 'Does not fall back to DEFAULT_USERS on rejection');
  });

  await runTest('R6.2.4 demoLogin rejects on network/server error without static mock fallback', () => {
    const demoLoginMatch = authContextSrc.match(/const\s+demoLogin\s*=\s*async\s*\([\s\S]*?\{([\s\S]*?)\n\s*\};/);
    assert.ok(demoLoginMatch, 'demoLogin function defined');
    const code = demoLoginMatch[1];

    assert.ok(code.includes('/api/v1/auth/demo-login/'), 'Calls server-side demo-login endpoint');
    assert.ok(code.includes('fetchAuthoritativeContext(data.access_token, true)'), 'Explicitly passes isDemo=true to context resolution');
    assert.ok(!code.includes('setCurrentUser(DEFAULT_USERS[role])'), 'Does NOT set DEFAULT_USERS[role] on error');
    assert.ok(code.includes('return { success: false'), 'Returns explicit error payload on failure');
  });

  // ----------------------------------------------------------------------------
  // 3. Header Tab Click Navigation & Demo Badge Invariants
  // ----------------------------------------------------------------------------
  const headerPath = path.join(FRONTEND_DIR, 'src', 'components', 'common', 'Header.jsx');
  const headerSrc = fs.readFileSync(headerPath, 'utf-8');

  await runTest('R6.3.1 Header handleRoleClick does NOT call demoLogin (prevents session mutation on tab click)', () => {
    const handleRoleMatch = headerSrc.match(/const\s+handleRoleClick\s*=\s*\(([\s\S]*?)\)\s*=>\s*\{([\s\S]*?)\};/);
    assert.ok(handleRoleMatch, 'handleRoleClick defined in Header.jsx');
    const body = handleRoleMatch[2];

    assert.ok(body.includes('onRoleChange(roleId)'), 'Calls onRoleChange');
    assert.ok(!body.includes('demoLogin'), 'MUST NOT invoke demoLogin on tab click');
  });

  await runTest('R6.3.2 Header renders DEMO MODE badge exclusively when currentUser.is_demo is true', () => {
    assert.ok(headerSrc.includes('currentUser.is_demo'), 'Checks currentUser.is_demo flag');
    assert.ok(headerSrc.includes('DEMO MODE'), 'Displays DEMO MODE label');
    assert.ok(headerSrc.includes('ShieldAlert'), 'Renders ShieldAlert icon next to demo badge');
  });

  // ----------------------------------------------------------------------------
  // 4. RoleGuard Dual Verification & Access Control Invariants
  // ----------------------------------------------------------------------------
  const roleGuardPath = path.join(FRONTEND_DIR, 'src', 'components', 'common', 'RoleGuard.jsx');
  const roleGuardSrc = fs.readFileSync(roleGuardPath, 'utf-8');

  await runTest('R6.4.1 RoleGuard enforces Dual Verification for non-demo users', () => {
    assert.ok(roleGuardSrc.includes('currentUser && !currentUser.is_demo'), 'Guards non-demo users strictly');
    assert.ok(roleGuardSrc.includes('const isEmailVerified = Boolean(currentUser.is_email_verified)'), 'Validates is_email_verified');
    assert.ok(roleGuardSrc.includes('const isPhoneVerified = Boolean(currentUser.is_phone_verified)'), 'Validates is_phone_verified');
    assert.ok(roleGuardSrc.includes('!isEmailVerified || !isPhoneVerified'), 'Blocks user if either verification is incomplete');
    assert.ok(roleGuardSrc.includes('Dual Verification Required'), 'Renders Dual Verification Required block');
  });

  await runTest('R6.4.2 RoleGuard employer fallback renders "Organization Under Review" instead of Apex', () => {
    assert.ok(!roleGuardSrc.includes("'Apex Infrastructure'"), 'Eliminated hardcoded Apex Infrastructure fallback');
    assert.ok(roleGuardSrc.includes('Organization Under Review'), 'Uses generic Organization Under Review placeholder');
  });

  await runTest('R6.4.3 RoleGuard blocks suspended or disabled accounts', () => {
    assert.ok(roleGuardSrc.includes("currentUser.status === 'SUSPENDED' || currentUser.status === 'DISABLED'"), 'Enforces suspension status');
    assert.ok(roleGuardSrc.includes('Account Access Suspended'), 'Displays suspension block');
  });

  // Functional simulation of RoleGuard logic
  function simulateRoleGuard(currentUser, requiredRole) {
    if (!currentUser) return 'AUTHENTICATION_REQUIRED';
    if (currentUser.status === 'SUSPENDED' || currentUser.status === 'DISABLED') return 'ACCOUNT_SUSPENDED';
    if (!currentUser.is_demo) {
      if (!currentUser.is_email_verified || !currentUser.is_phone_verified) {
        return 'DUAL_VERIFICATION_REQUIRED';
      }
    }
    if (requiredRole === 'EMPLOYER' && (currentUser.organization_status === 'PENDING_REVIEW' || currentUser.status === 'PENDING_REVIEW')) {
      return 'ONBOARDING_PENDING_REVIEW';
    }
    const userRole = (currentUser.role || '').toUpperCase();
    const reqRole = requiredRole.toUpperCase();
    if (userRole !== reqRole && userRole !== 'ADMIN') {
      return 'ROLE_MISMATCH';
    }
    return 'AUTHORIZED';
  }

  await runTest('R6.4.4 RoleGuard functional simulation: Unauthenticated -> AUTHENTICATION_REQUIRED', () => {
    assert.equal(simulateRoleGuard(null, 'WORKER'), 'AUTHENTICATION_REQUIRED');
  });

  await runTest('R6.4.5 RoleGuard functional simulation: Non-demo unverified email -> DUAL_VERIFICATION_REQUIRED', () => {
    const user = { role: 'WORKER', is_demo: false, is_email_verified: false, is_phone_verified: true, status: 'ACTIVE' };
    assert.equal(simulateRoleGuard(user, 'WORKER'), 'DUAL_VERIFICATION_REQUIRED');
  });

  await runTest('R6.4.6 RoleGuard functional simulation: Non-demo unverified phone -> DUAL_VERIFICATION_REQUIRED', () => {
    const user = { role: 'WORKER', is_demo: false, is_email_verified: true, is_phone_verified: false, status: 'ACTIVE' };
    assert.equal(simulateRoleGuard(user, 'WORKER'), 'DUAL_VERIFICATION_REQUIRED');
  });

  await runTest('R6.4.7 RoleGuard functional simulation: Non-demo dual verified -> AUTHORIZED', () => {
    const user = { role: 'WORKER', is_demo: false, is_email_verified: true, is_phone_verified: true, status: 'ACTIVE' };
    assert.equal(simulateRoleGuard(user, 'WORKER'), 'AUTHORIZED');
  });

  await runTest('R6.4.8 RoleGuard functional simulation: Demo user bypasses dual verification check', () => {
    const user = { role: 'WORKER', is_demo: true, is_email_verified: false, is_phone_verified: false, status: 'ACTIVE' };
    assert.equal(simulateRoleGuard(user, 'WORKER'), 'AUTHORIZED');
  });

  await runTest('R6.4.9 RoleGuard functional simulation: Role mismatch blocks non-admin user', () => {
    const user = { role: 'EMPLOYER', is_demo: true, is_email_verified: true, is_phone_verified: true, status: 'ACTIVE' };
    assert.equal(simulateRoleGuard(user, 'WORKER'), 'ROLE_MISMATCH');
  });

  await runTest('R6.4.10 RoleGuard functional simulation: ADMIN role passes any portal', () => {
    const user = { role: 'ADMIN', is_demo: true, is_email_verified: true, is_phone_verified: true, status: 'ACTIVE' };
    assert.equal(simulateRoleGuard(user, 'WORKER'), 'AUTHORIZED');
    assert.equal(simulateRoleGuard(user, 'EMPLOYER'), 'AUTHORIZED');
    assert.equal(simulateRoleGuard(user, 'GOVERNMENT'), 'AUTHORIZED');
  });

  await runTest('R6.4.11 RoleGuard functional simulation: Suspended account blocked regardless of verification or role', () => {
    const user = { role: 'ADMIN', is_demo: true, is_email_verified: true, is_phone_verified: true, status: 'SUSPENDED' };
    assert.equal(simulateRoleGuard(user, 'ADMIN'), 'ACCOUNT_SUSPENDED');
  });

  // ----------------------------------------------------------------------------
  // 5. WorkerPortal & App.jsx IDOR Resistance Invariants
  // ----------------------------------------------------------------------------
  const workerPortalPath = path.join(FRONTEND_DIR, 'src', 'components', 'worker', 'WorkerPortal.jsx');
  const workerPortalSrc = fs.readFileSync(workerPortalPath, 'utf-8');

  const appPath = path.join(FRONTEND_DIR, 'src', 'App.jsx');
  const appSrc = fs.readFileSync(appPath, 'utf-8');

  await runTest('R6.5.1 App.jsx renders WorkerPortal without hardcoded workerId prop', () => {
    assert.ok(!appSrc.includes('workerId={1}'), 'Must not pass workerId={1}');
    assert.ok(!appSrc.includes('workerId='), 'Must not pass any workerId prop to WorkerPortal');
    assert.ok(appSrc.includes('<WorkerPortal currentLang={currentLang} />'), 'Renders WorkerPortal with language prop only');
  });

  await runTest('R6.5.2 WorkerPortal.jsx does not accept workerId default prop or parameter', () => {
    const funcDecl = workerPortalSrc.match(/export\s+default\s+function\s+WorkerPortal\s*\(([\s\S]*?)\)\s*\{/);
    assert.ok(funcDecl, 'WorkerPortal function declaration found');
    const params = funcDecl[1];
    assert.ok(!params.includes('workerId'), 'WorkerPortal signature does not accept workerId');
  });

  await runTest('R6.5.3 WorkerPortal.jsx uses strictly self-service /me endpoints', () => {
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/profile/me')"), 'Uses /api/v1/worker/profile/me');
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/wallet/me')"), 'Uses /api/v1/worker/wallet/me');
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/presentation/qr-card/me')"), 'Uses /api/v1/worker/presentation/qr-card/me');
    assert.ok(workerPortalSrc.includes("apiFetch('/api/v1/worker/verify-aadhaar/me'"), 'Uses /api/v1/worker/verify-aadhaar/me');
    assert.ok(!workerPortalSrc.includes('/profile/${workerId}'), 'No parameterized profile endpoint');
    assert.ok(!workerPortalSrc.includes('/wallet/${workerId}'), 'No parameterized wallet endpoint');
    assert.ok(!workerPortalSrc.includes('/verify-aadhaar/${workerId}'), 'No parameterized verify-aadhaar endpoint');
  });

  // ----------------------------------------------------------------------------
  // 6. VerificationStepper 11-Stage Alignment
  // ----------------------------------------------------------------------------
  const stepperPath = path.join(FRONTEND_DIR, 'src', 'components', 'common', 'VerificationStepper.jsx');
  const stepperSrc = fs.readFileSync(stepperPath, 'utf-8');

  await runTest('R6.6.1 VerificationStepper contains all 11 stages from backend verification_engine', () => {
    assert.ok(stepperSrc.includes('Verifier Authorization & Scope Check'), 'Step 10 present');
    assert.ok(stepperSrc.includes('Deferred Atomic Nonce Consumption'), 'Step 11 present');
    assert.ok(stepperSrc.includes('/11 Stages Verified'), 'Shows 11 stages verified in header');
  });

  console.log('\n================================================================');
  console.log(`  ALL ${passedTests}/${totalTests} FRONTEND CHALLENGE TESTS PASSED SUCCESSFULLY! `);
  console.log('================================================================\n');
}

main().catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
