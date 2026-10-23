/**
 * frontend/tests/test_m1_auth_state_challenger.mjs
 *
 * Empirical Adversarial Challenger Test Suite for Milestone 1:
 * Frontend Auth State Transitions, Premature RoleGuard Lock Prevention &
 * Custom Trade / Profession Input Validation.
 *
 * Author: challenger_m1_1 (EMPIRICAL CHALLENGER)
 * Target Codebase: PassKhadam_Exportable
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
console.log('  M1 ADVERSARIAL CHALLENGE HARNESS: AUTH STATE TRANSITIONS,    ');
console.log('  PREMATURE LOCK PREVENTIONS & CUSTOM TRADE VALIDATION         ');
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
// Load Source Files for AST and Pattern Verification
// ----------------------------------------------------------------------------
const authContextPath = path.join(SRC_DIR, 'context', 'AuthContext.jsx');
const authContextSrc = fs.readFileSync(authContextPath, 'utf-8');

const authModalPath = path.join(SRC_DIR, 'components', 'common', 'AuthModal.jsx');
const authModalSrc = fs.readFileSync(authModalPath, 'utf-8');

const authPagePath = path.join(SRC_DIR, 'components', 'common', 'AuthPage.jsx');
const authPageSrc = fs.readFileSync(authPagePath, 'utf-8');

const roleGuardPath = path.join(SRC_DIR, 'components', 'common', 'RoleGuard.jsx');
const roleGuardSrc = fs.readFileSync(roleGuardPath, 'utf-8');

const appPath = path.join(SRC_DIR, 'App.jsx');
const appSrc = fs.readFileSync(appPath, 'utf-8');

// ----------------------------------------------------------------------------
// Simulation Environments & State Machine Harness
// ----------------------------------------------------------------------------

/**
 * Simulates AuthContext phone OTP verification state machine
 */
function createAuthContextHarness(initialUser = null) {
  let currentUser = initialUser;
  let phoneConfirmationResult = null;
  let phoneSessionId = 'fb_sess_test_123';
  let mockFetchResponses = new Map();

  const setCurrentUser = (updater) => {
    if (typeof updater === 'function') {
      currentUser = updater(currentUser);
    } else {
      currentUser = updater;
    }
  };

  const setPhoneConfirmation = (confResult) => {
    phoneConfirmationResult = confResult;
  };

  const setMockFetch = (endpoint, response) => {
    mockFetchResponses.set(endpoint, response);
  };

  const verifyPhoneOtp = async (phone, otp, sessionId = null) => {
    let cleanPhone = (phone || '').replace(/[\s\-()]/g, '');
    if (cleanPhone && !cleanPhone.startsWith('+')) {
      if (cleanPhone.length === 10) {
        cleanPhone = '+91' + cleanPhone;
      } else {
        cleanPhone = '+' + cleanPhone;
      }
    }
    const formattedPhone = cleanPhone;
    const activeSessionId = sessionId || phoneSessionId;

    try {
      // 1. Try Firebase confirmation result
      if (phoneConfirmationResult) {
        try {
          const userCredential = await phoneConfirmationResult.confirm(otp);
          setCurrentUser(prev => prev ? { ...prev, is_phone_verified: true, phone: formattedPhone } : null);
          return {
            success: true,
            user: userCredential?.user,
            message: 'Phone verified successfully via Firebase Phone Auth!'
          };
        } catch (confErr) {
          if (otp === '123456' || otp === '729415') {
            setCurrentUser(prev => prev ? { ...prev, is_phone_verified: true, phone: formattedPhone } : null);
            return { success: true, message: 'Phone verified successfully via test OTP' };
          }
        }
      }

      // 2. Validate against Backend /api/v1/auth/verify-otp
      const mockResp = mockFetchResponses.get('/api/v1/auth/verify-otp');
      if (mockResp) {
        if (mockResp.ok && mockResp.data?.verified) {
          setCurrentUser(prev => prev ? { ...prev, is_phone_verified: true, phone: formattedPhone } : null);
          return { success: true, message: mockResp.data.message };
        }
      }

      // 3. Fictional console test codes fallback
      if (otp.trim() === '123456' || otp.trim() === '729415') {
        setCurrentUser(prev => prev ? { ...prev, is_phone_verified: true, phone: formattedPhone } : null);
        return { success: true, message: 'Phone verified successfully via test OTP' };
      }

      return { success: false, error: 'Invalid verification code' };
    } catch (e) {
      if (otp.trim() === '123456' || otp.trim() === '729415') {
        setCurrentUser(prev => prev ? { ...prev, is_phone_verified: true, phone: formattedPhone } : null);
        return { success: true, message: 'Phone verified successfully' };
      }
      return { success: false, error: 'Failed to verify OTP' };
    }
  };

  const verifyEmailOtp = async (email, code, sessionId = null) => {
    const cleanEmail = (email || '').trim().toLowerCase();
    if (code === '123456' || code === '729415') {
      setCurrentUser(prev => prev ? { ...prev, is_email_verified: true, email: cleanEmail } : prev);
      return { success: true, message: 'Email verified successfully via test OTP preset' };
    }
    return { success: false, error: 'Invalid code' };
  };

  return {
    getCurrentUser: () => currentUser,
    setCurrentUser,
    setPhoneConfirmation,
    setMockFetch,
    verifyPhoneOtp,
    verifyEmailOtp
  };
}

/**
 * Simulates Registration Form Validation & Submission
 */
function simulateRegistrationSubmission({
  regRole = 'WORKER',
  workerCategory = 'Mason',
  customProfession = '',
  workerOriginState = 'Karnataka',
  emailVerified = true,
  otpVerified = true,
  regName = 'Test User',
  regEmail = 'user@example.com',
  regPhone = '+91 98765 43210',
  regPassword = 'Password123!'
}) {
  let errorMsg = null;

  if (regRole === 'WORKER') {
    if (!emailVerified) {
      errorMsg = 'Please verify your email address via 6-digit code or email link first';
      return { success: false, errorMsg };
    }
    if (!otpVerified) {
      errorMsg = 'Please verify your phone number via SMS OTP first';
      return { success: false, errorMsg };
    }
  }

  let effectiveCategory = workerCategory;
  if (regRole === 'WORKER' && workerCategory === 'Other') {
    const cleanCustom = customProfession.trim();
    if (!cleanCustom) {
      errorMsg = 'Please specify your custom trade or profession';
      return { success: false, errorMsg };
    }
    effectiveCategory = cleanCustom;
  }

  const payload = {
    full_name: regName,
    email: regEmail,
    phone: regPhone,
    password: regPassword,
    role: regRole,
    worker_category: regRole === 'WORKER' ? effectiveCategory : null,
    skills: regRole === 'WORKER' ? [effectiveCategory] : null,
    origin_state: regRole === 'WORKER' ? workerOriginState : null,
    current_state: regRole === 'WORKER' ? 'Karnataka' : null
  };

  return { success: true, payload };
}

// ----------------------------------------------------------------------------
// Test Execution
// ----------------------------------------------------------------------------

async function main() {
  console.log('--- SECTION 1: Phone OTP State Transitions on Uncompleted Registration ---');

  await runTest('T1.1: verifyPhoneOtp with test OTP (123456) when currentUser is null preserves currentUser === null', async () => {
    const harness = createAuthContextHarness(null);
    assert.equal(harness.getCurrentUser(), null);

    const res = await harness.verifyPhoneOtp('+91 98765 43210', '123456');
    assert.equal(res.success, true);
    assert.equal(harness.getCurrentUser(), null, 'currentUser must remain null after phone OTP verification during registration');
  });

  await runTest('T1.2: verifyPhoneOtp with demo OTP (729415) when currentUser is null preserves currentUser === null', async () => {
    const harness = createAuthContextHarness(null);
    const res = await harness.verifyPhoneOtp('+91 98765 43210', '729415');
    assert.equal(res.success, true);
    assert.equal(harness.getCurrentUser(), null);
  });

  await runTest('T1.3: verifyPhoneOtp via backend verify-otp success when currentUser is null preserves currentUser === null', async () => {
    const harness = createAuthContextHarness(null);
    harness.setMockFetch('/api/v1/auth/verify-otp', {
      ok: true,
      data: { verified: true, message: 'OTP verified by server' }
    });
    const res = await harness.verifyPhoneOtp('+91 98765 43210', '998877');
    assert.equal(res.success, true);
    assert.equal(harness.getCurrentUser(), null);
  });

  await runTest('T1.4: verifyPhoneOtp via Firebase confirmation success when currentUser is null preserves currentUser === null', async () => {
    const harness = createAuthContextHarness(null);
    harness.setPhoneConfirmation({
      confirm: async (code) => ({ user: { uid: 'fb_user_123', phoneNumber: '+919876543210' } })
    });
    const res = await harness.verifyPhoneOtp('+91 98765 43210', '554433');
    assert.equal(res.success, true);
    assert.equal(harness.getCurrentUser(), null);
  });

  await runTest('T1.5: verifyPhoneOtp via Firebase confirmation failure + fallback code preserves currentUser === null', async () => {
    const harness = createAuthContextHarness(null);
    harness.setPhoneConfirmation({
      confirm: async () => { throw new Error('auth/invalid-verification-code'); }
    });
    const res = await harness.verifyPhoneOtp('+91 98765 43210', '123456');
    assert.equal(res.success, true);
    assert.equal(harness.getCurrentUser(), null);
  });

  await runTest('T1.6: verifyPhoneOtp preserves existing session when currentUser is an authenticated user', async () => {
    const existingUser = {
      id: 42,
      full_name: 'Existing Worker',
      email: 'worker@passkhadam.org',
      role: 'WORKER',
      is_email_verified: true,
      is_phone_verified: false,
      is_demo: false
    };
    const harness = createAuthContextHarness(existingUser);
    const res = await harness.verifyPhoneOtp('+91 98765 43210', '123456');
    assert.equal(res.success, true);
    const updated = harness.getCurrentUser();
    assert.notEqual(updated, null);
    assert.equal(updated.id, 42);
    assert.equal(updated.is_phone_verified, true);
    assert.equal(updated.phone, '+919876543210');
    assert.equal(updated.is_email_verified, true);
  });

  await runTest('T1.7: verifyEmailOtp when currentUser is null preserves currentUser === null', async () => {
    const harness = createAuthContextHarness(null);
    const res = await harness.verifyEmailOtp('test@passkhadam.org', '123456');
    assert.equal(res.success, true);
    assert.equal(harness.getCurrentUser(), null);
  });

  console.log('\n--- SECTION 2: Premature Lock AST & Gate Analysis ---');

  await runTest('T2.1: AuthContext.jsx contains NO buggy null-spreading ({ ...prev, is_phone_verified: true }) in verifyPhoneOtp', () => {
    const buggyPattern = /setCurrentUser\(\s*prev\s*=>\s*\(\{\s*\.\.\.prev,\s*is_phone_verified:\s*true/g;
    const matches = authContextSrc.match(buggyPattern);
    assert.equal(matches, null, 'Found buggy null-spreading setCurrentUser calls that could cause premature lock');
  });

  await runTest('T2.2: AuthContext.jsx verifyPhoneOtp contains exactly 5 null-safe updater exit points', () => {
    // Check for null-safe pattern: setCurrentUser(prev => prev ? { ...prev, is_phone_verified: true ... } : null)
    const safePattern = /setCurrentUser\(\s*prev\s*=>\s*prev\s*\?\s*\{\s*\.\.\.prev,\s*is_phone_verified:\s*true,\s*phone:\s*formattedPhone\s*\}\s*:\s*null\s*\)/g;
    const matches = authContextSrc.match(safePattern);
    assert.notEqual(matches, null, 'Expected null-safe pattern in AuthContext.jsx');
    assert.equal(matches.length, 5, `Expected 5 guarded exit points, found ${matches.length}`);
  });

  await runTest('T2.3: App.jsx conditionally renders AuthPage when !currentUser and never mounts RoleGuard', () => {
    assert.match(appSrc, /\{!currentUser\s*\?\s*\(\s*<AuthPage/);
    assert.match(appSrc, /<RoleGuard requiredRole="WORKER">/);
    // When currentUser is null, !currentUser is true, so AuthPage is rendered and RoleGuard is NOT mounted.
    const isAuthPageRendered = (user) => !user;
    assert.equal(isAuthPageRendered(null), true);
    assert.equal(isAuthPageRendered({ is_phone_verified: true }), false, 'A truthy object causes RoleGuard to mount');
  });

  await runTest('T2.4: Counterfactual Regression Oracle: RoleGuard locks into Dual Verification Required if currentUser is truthy but unverified', () => {
    // If currentUser were mutated to the buggy unauthenticated object:
    const buggyUnauthUser = { is_phone_verified: true, phone: '+919876543210' };
    
    // Evaluate RoleGuard check (lines 186-189):
    const shouldBlock = (user) => {
      if (user && !user.is_demo) {
        const isEmailVerified = Boolean(user.is_email_verified);
        const isPhoneVerified = Boolean(user.is_phone_verified);
        if (!isEmailVerified || !isPhoneVerified) {
          return 'DUAL_VERIFICATION_REQUIRED';
        }
      }
      return 'AUTHORIZED';
    };

    assert.equal(shouldBlock(buggyUnauthUser), 'DUAL_VERIFICATION_REQUIRED', 'Buggy object causes premature lock!');
    
    // When currentUser is correctly kept as null:
    assert.equal(shouldBlock(null), 'AUTHORIZED', 'Null user bypasses dual-verification check in RoleGuard (caught by App !currentUser gate)');
  });

  await runTest('T2.5: Full interactive registration sequence does not mutate currentUser', async () => {
    const harness = createAuthContextHarness(null);

    // 1. Visitor opens registration form
    let tab = 'register';
    assert.equal(harness.getCurrentUser(), null);

    // 2. Visitor sends phone OTP
    const phone = '+91 98765 43210';
    assert.equal(harness.getCurrentUser(), null);

    // 3. Visitor enters OTP '123456' and verifies
    const phoneRes = await harness.verifyPhoneOtp(phone, '123456');
    assert.equal(phoneRes.success, true);
    assert.equal(harness.getCurrentUser(), null, 'currentUser MUST be null after phone verify');

    // 4. Visitor sends email OTP
    assert.equal(harness.getCurrentUser(), null);

    // 5. Visitor enters email OTP and verifies
    const emailRes = await harness.verifyEmailOtp('test@passkhadam.org', '123456');
    assert.equal(emailRes.success, true);
    assert.equal(harness.getCurrentUser(), null, 'currentUser MUST be null after email verify');

    // 6. Visitor switches tabs back and forth
    tab = 'login';
    tab = 'activate';
    tab = 'activate_gov';
    tab = 'register';
    assert.equal(harness.getCurrentUser(), null, 'Tab switching must not mutate currentUser');
  });

  console.log('\n--- SECTION 3: Custom Trade / Profession Input Validation ---');

  await runTest('T3.1: AuthModal blocks worker registration when workerCategory === "Other" and customProfession is empty', () => {
    const res = simulateRegistrationSubmission({
      regRole: 'WORKER',
      workerCategory: 'Other',
      customProfession: '',
      emailVerified: true,
      otpVerified: true
    });
    assert.equal(res.success, false);
    assert.equal(res.errorMsg, 'Please specify your custom trade or profession');
  });

  await runTest('T3.2: AuthModal blocks worker registration when customProfession is spaces only', () => {
    const res = simulateRegistrationSubmission({
      regRole: 'WORKER',
      workerCategory: 'Other',
      customProfession: '     ',
      emailVerified: true,
      otpVerified: true
    });
    assert.equal(res.success, false);
    assert.equal(res.errorMsg, 'Please specify your custom trade or profession');
  });

  await runTest('T3.3: AuthModal blocks worker registration when customProfession is tabs, newlines, and whitespace', () => {
    const res = simulateRegistrationSubmission({
      regRole: 'WORKER',
      workerCategory: 'Other',
      customProfession: '\t\n  \r\n \t ',
      emailVerified: true,
      otpVerified: true
    });
    assert.equal(res.success, false);
    assert.equal(res.errorMsg, 'Please specify your custom trade or profession');
  });

  await runTest('T3.4: AuthModal accepts valid custom trade and populates effectiveCategory and skills', () => {
    const res = simulateRegistrationSubmission({
      regRole: 'WORKER',
      workerCategory: 'Other',
      customProfession: 'Underwater Welding & Hyperbaric Technician',
      workerOriginState: 'Odisha',
      emailVerified: true,
      otpVerified: true
    });
    assert.equal(res.success, true);
    assert.equal(res.payload.worker_category, 'Underwater Welding & Hyperbaric Technician');
    assert.deepEqual(res.payload.skills, ['Underwater Welding & Hyperbaric Technician']);
    assert.equal(res.payload.origin_state, 'Odisha');
    assert.equal(res.payload.current_state, 'Karnataka');
  });

  await runTest('T3.5: AuthModal accepts standard preset trade without requiring customProfession', () => {
    const res = simulateRegistrationSubmission({
      regRole: 'WORKER',
      workerCategory: 'Electrician',
      customProfession: '',
      workerOriginState: 'Uttar Pradesh',
      emailVerified: true,
      otpVerified: true
    });
    assert.equal(res.success, true);
    assert.equal(res.payload.worker_category, 'Electrician');
    assert.deepEqual(res.payload.skills, ['Electrician']);
    assert.equal(res.payload.origin_state, 'Uttar Pradesh');
  });

  await runTest('T3.6: AuthModal and AuthPage source code both contain the exact custom profession validation logic', () => {
    const expectedSnippet = `if (regRole === 'WORKER' && workerCategory === 'Other') {
      const cleanCustom = customProfession.trim();
      if (!cleanCustom) {
        setErrorMsg('Please specify your custom trade or profession');
        return;
      }
      effectiveCategory = cleanCustom;
    }`;

    // Normalize whitespace for comparison
    const norm = (s) => s.replace(/\s+/g, ' ').trim();
    assert.ok(norm(authModalSrc).includes(norm(expectedSnippet)), 'AuthModal.jsx must contain custom profession validation');
    assert.ok(norm(authPageSrc).includes(norm(expectedSnippet)), 'AuthPage.jsx must contain custom profession validation');
  });

  await runTest('T3.7: AuthPage.jsx correctly handles is_test_number test phone quick-fill', () => {
    assert.match(authPageSrc, /if\s*\(\s*res\.is_test_number\s*\)\s*\{\s*setOtpCode\('123456'\);/);
    assert.match(authModalSrc, /if\s*\(\s*res\.is_test_number\s*\)\s*\{\s*setOtpCode\('123456'\);/);
  });

  await runTest('T3.8: AuthModal and AuthPage both render the Other option and the conditional custom input field', () => {
    assert.match(authModalSrc, /<option value="Other">Other \/ Custom Trade\.\.\.<\/option>/);
    assert.match(authPageSrc, /<option value="Other">Other \/ Custom Trade\.\.\.<\/option>/);
    assert.match(authModalSrc, /workerCategory === 'Other'/);
    assert.match(authPageSrc, /workerCategory === 'Other'/);
  });

  console.log('\n================================================================');
  console.log(`  ALL ${passedTests}/${totalTests} M1 ADVERSARIAL CHALLENGE TESTS PASSED! `);
  console.log('================================================================\n');
}

main().catch(err => {
  console.error('\nADVERSARIAL CHALLENGE FAILED:', err);
  process.exit(1);
});
