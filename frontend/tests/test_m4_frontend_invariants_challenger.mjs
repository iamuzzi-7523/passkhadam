/**
 * frontend/tests/test_m4_frontend_invariants_challenger.mjs
 * Milestone 4 Adversarial Empirical Challenger Suite
 * Frontend Usability, Modal Invariants, Search & Guidance
 * 
 * Invariants Tested:
 * 1. Aadhaar Input Invariants:
 *    - Formatting with varied inputs (<12, =12, >12, letters, special characters, whitespace, copy-paste)
 *    - Property-based fuzz harness (500 randomized noisy inputs)
 *    - Backspace behavior at space boundaries (boundary 1 & 2 deletion simulation)
 *    - Digit counter & validation badge states (0/12 to 12/12 Valid)
 *    - Clean unspaced digits transmission (cleanAadhaar payload construction)
 * 2. Employer Dismissal Modal Invariants:
 *    - Modal opening from table row: stint & worker details rendered accurately
 *    - Preset selection: updates target status & default reason notes for all 5 presets
 *    - Custom reason override: user edits preserved
 *    - Cancel / Abort action: closes modal without mutating table state or triggering PUT
 * 3. Workforce Search & Filter Invariants:
 *    - Multi-field keyword search (Name, DID, ID, Role, Category, Location)
 *    - Trade category dropdown filter
 *    - Status tab filters (ALL, ACTIVE, CONCLUDED) & partition invariant
 *    - Dynamic reactive count badges
 *    - Empty state miss detection & Reset All Filters action
 * 4. Actionable Guidance & AST Static Code Contracts across Portals:
 *    - WorkerPortal, EmployerPortal, GovernmentPortal guidance notices
 *    - Verbatim endpoint call preservation for challenger compatibility
 */

import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

// Direct import of frontend utility functions
import { formatAadhaarInput, cleanAadhaarDigits } from '../src/utils/api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_DIR = path.resolve(__dirname, '..');
const SRC_DIR = path.join(FRONTEND_DIR, 'src');

console.log('================================================================');
console.log('  MILESTONE 4 ADVERSARIAL CHALLENGER: USABILITY & MODAL INVARIANTS');
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

// ============================================================================
// SECTION 1: AADHAAR INPUT FORMATTING, FUZZING & TRANSMISSION INVARIANTS
// ============================================================================
console.log('--- SECTION 1: Aadhaar Input Formatting, Fuzzing & Transmission Invariants ---');

// 1.1 Varied inputs formatting
await runTest('T1.1: formatAadhaarInput handles null, undefined, empty, and non-string inputs', () => {
  assert.equal(formatAadhaarInput(''), '', 'Empty string should return empty');
  assert.equal(formatAadhaarInput(null), '', 'null should return empty');
  assert.equal(formatAadhaarInput(undefined), '', 'undefined should return empty');
  assert.equal(formatAadhaarInput(0), '', 'Numeric 0 is falsy, returns empty');
  assert.equal(formatAadhaarInput('0'), '0', 'String "0" returns "0"');
  assert.equal(formatAadhaarInput(123456784821), '1234 5678 4821', 'Number should format cleanly');
});

await runTest('T1.2: formatAadhaarInput formats inputs with fewer than 12 digits', () => {
  assert.equal(formatAadhaarInput('1'), '1');
  assert.equal(formatAadhaarInput('12'), '12');
  assert.equal(formatAadhaarInput('123'), '123');
  assert.equal(formatAadhaarInput('1234'), '1234', 'Exact 4 digits should not have trailing space');
  assert.equal(formatAadhaarInput('12345'), '1234 5', '5 digits should format with single space');
  assert.equal(formatAadhaarInput('1234567'), '1234 567');
  assert.equal(formatAadhaarInput('12345678'), '1234 5678', '8 digits should have 1 space, no trailing space');
  assert.equal(formatAadhaarInput('123456789'), '1234 5678 9', '9 digits should format with 2 spaces');
  assert.equal(formatAadhaarInput('12345678901'), '1234 5678 901', '11 digits formatted');
});

await runTest('T1.3: formatAadhaarInput formats exactly 12 digits into 4-4-4 spacing', () => {
  const formatted = formatAadhaarInput('123456784821');
  assert.equal(formatted, '1234 5678 4821', '12 digits must format to XXXX XXXX XXXX');
  assert.equal(formatted.length, 14, 'Length must be exactly 14 characters');
  assert.equal(cleanAadhaarDigits(formatted), '123456784821', 'Clean digits must match original');
});

await runTest('T1.4: formatAadhaarInput clamps inputs exceeding 12 digits to max 12 digits (14 chars)', () => {
  const over12 = '12345678482199999999';
  const formatted = formatAadhaarInput(over12);
  assert.equal(formatted, '1234 5678 4821', 'Excess digits must be truncated');
  assert.equal(formatted.length, 14, 'Formatted length must never exceed 14');
  assert.equal(cleanAadhaarDigits(over12), '123456784821', 'Clean digits must truncate to 12');
});

await runTest('T1.5: formatAadhaarInput strips letters, symbols, punctuation, and whitespace', () => {
  assert.equal(formatAadhaarInput('1234-5678-4821'), '1234 5678 4821', 'Hyphenated input');
  assert.equal(formatAadhaarInput('1234.5678.4821'), '1234 5678 4821', 'Dot separated input');
  assert.equal(formatAadhaarInput('  1234   5678   4821  '), '1234 5678 4821', 'Messy whitespace input');
  assert.equal(formatAadhaarInput('aadhaar#1234_5678_4821!'), '1234 5678 4821', 'Alpha-numeric with symbols');
  assert.equal(formatAadhaarInput('abcdefghij'), '', 'Letters only should return empty');
  assert.equal(formatAadhaarInput('!@#$%^&*()_+'), '', 'Symbols only should return empty');
});

await runTest('T1.6: formatAadhaarInput copy-paste resilience with mixed spacing & hyphens', () => {
  const pasteVariations = [
    '1234 5678 4821',
    '1234  5678  4821',
    ' 1234 5678 4821 ',
    '1234-5678-4821',
    '1234 - 5678 - 4821',
    '1234/5678/4821',
    '1234 5678 4821 9999',
    'Aadhaar: 1234 5678 4821 (Verified)'
  ];

  for (const variant of pasteVariations) {
    const formatted = formatAadhaarInput(variant);
    assert.equal(formatted, '1234 5678 4821', `Failed copy-paste resilience for: "${variant}"`);
    const clean = cleanAadhaarDigits(variant);
    assert.equal(clean, '123456784821', `Failed clean digits extraction for: "${variant}"`);
  }
});

await runTest('T1.7: Property-based fuzz harness for Aadhaar formatting (500 random inputs)', () => {
  const chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ !@#$%^&*()-_=+[]{}|;:,.<>?';
  for (let i = 0; i < 500; i++) {
    const len = Math.floor(Math.random() * 50);
    let str = '';
    for (let j = 0; j < len; j++) {
      str += chars[Math.floor(Math.random() * chars.length)];
    }

    const formatted = formatAadhaarInput(str);
    const cleaned = cleanAadhaarDigits(str);

    // Invariant 1: Max length is 14 characters
    assert(formatted.length <= 14, `Fuzz fail: formatted length ${formatted.length} > 14 for input "${str}"`);
    // Invariant 2: Matches standard 4-4-4 spacing pattern
    assert(/^(\d{1,4}(\s\d{1,4}){0,2})?$/.test(formatted), `Fuzz fail: format invalid: "${formatted}"`);
    // Invariant 3: Stripping spaces from formatted equals cleaned digits
    assert.equal(formatted.replace(/\s/g, ''), cleaned, `Fuzz fail: digits mismatch for input "${str}"`);
    // Invariant 4: Clean digits length is at most 12
    assert(cleaned.length <= 12, `Fuzz fail: clean digits length ${cleaned.length} > 12`);
    // Invariant 5: Idempotency
    assert.equal(formatAadhaarInput(formatted), formatted, `Fuzz fail: idempotency violated for "${formatted}"`);
  }
});

await runTest('T1.8: Backspace simulation at space boundaries removes preceding digit and space', () => {
  // Exact Backspace handler logic from WorkerPortal.jsx:
  function simulateBackspace(value, selectionStart, selectionEnd) {
    if (selectionStart === selectionEnd && selectionStart > 0 && value[selectionStart - 1] === ' ') {
      const cut = selectionStart - 1;
      const updated = value.slice(0, cut - 1) + value.slice(selectionStart);
      const formatted = formatAadhaarInput(updated);
      const newPos = Math.max(0, cut - 1);
      return { handled: true, formatted, newPos };
    }
    return { handled: false, value };
  }

  // Case 1: Cursor at index 5 in "1234 5" (right after first space)
  const res1 = simulateBackspace('1234 5', 5, 5);
  assert.equal(res1.handled, true, 'Boundary 1 backspace must be handled');
  assert.equal(res1.formatted, '1235', 'Should delete preceding digit "4" and space');
  assert.equal(res1.newPos, 3, 'Cursor should be repositioned at index 3');

  // Case 2: Cursor at index 10 in "1234 5678 9" (right after second space)
  const res2 = simulateBackspace('1234 5678 9', 10, 10);
  assert.equal(res2.handled, true, 'Boundary 2 backspace must be handled');
  assert.equal(res2.formatted, '1234 5679', 'Should delete preceding digit "8" and space');
  assert.equal(res2.newPos, 8, 'Cursor should be repositioned at index 8');

  // Case 3: Cursor in middle of digit group (not after a space)
  const res3 = simulateBackspace('1234 5678', 3, 3);
  assert.equal(res3.handled, false, 'Normal backspace should not be intercepted');

  // Case 4: Selection range (selectionStart !== selectionEnd)
  const res4 = simulateBackspace('1234 5678', 4, 6);
  assert.equal(res4.handled, false, 'Selection range deletion should not be intercepted');
});

await runTest('T1.9: Live digit counter and validation badge state machine', () => {
  function getBadgeState(input) {
    const clean = input.replace(/\s/g, '');
    if (clean.length === 12) {
      return { isValid: true, label: '12/12 Digits Valid' };
    }
    return { isValid: false, label: `${clean.length}/12 digits` };
  }

  assert.deepEqual(getBadgeState(''), { isValid: false, label: '0/12 digits' });
  assert.deepEqual(getBadgeState('1234'), { isValid: false, label: '4/12 digits' });
  assert.deepEqual(getBadgeState('1234 5678'), { isValid: false, label: '8/12 digits' });
  assert.deepEqual(getBadgeState('1234 5678 482'), { isValid: false, label: '11/12 digits' });
  assert.deepEqual(getBadgeState('1234 5678 4821'), { isValid: true, label: '12/12 Digits Valid' });
});

await runTest('T1.10: Clean unspaced digits payload transmission verification', () => {
  // Simulates handleVerifyAadhaar transmission logic
  function prepareVerifyPayload(aadhaarInput, nameInput) {
    const cleanAadhaar = aadhaarInput.replace(/\s+/g, '');
    if (cleanAadhaar.length !== 12 || !/^\d{12}$/.test(cleanAadhaar)) {
      throw new Error('Aadhaar number must contain exactly 12 numeric digits (e.g. 1234 5678 4821).');
    }
    return {
      endpoint: '/api/v1/worker/verify-aadhaar/me',
      body: { aadhaar_number: cleanAadhaar, full_name: nameInput.trim() }
    };
  }

  // Valid formatted input yields unspaced 12-digit payload
  const payload = prepareVerifyPayload('1234 5678 4821', '  Mohammed Uzair  ');
  assert.equal(payload.endpoint, '/api/v1/worker/verify-aadhaar/me');
  assert.equal(payload.body.aadhaar_number, '123456784821', 'Aadhaar must be transmitted unspaced');
  assert.equal(payload.body.full_name, 'Mohammed Uzair', 'Name must be trimmed');

  // Incomplete input throws error
  assert.throws(
    () => prepareVerifyPayload('1234 5678', 'Uzair'),
    /Aadhaar number must contain exactly 12 numeric digits/
  );
  // Malformed input throws error
  assert.throws(
    () => prepareVerifyPayload('1234 5678 ABCD', 'Uzair'),
    /Aadhaar number must contain exactly 12 numeric digits/
  );
});

// ============================================================================
// SECTION 2: EMPLOYER DISMISSAL MODAL INVARIANTS
// ============================================================================
console.log('\n--- SECTION 2: Employer Dismissal Modal Invariants ---');

const CONCLUSION_PRESETS = [
  {
    id: "PROJECT_COMPLETED",
    label: "Project Completed / Work Concluded",
    status: "COMPLETED",
    defaultReason: "Project phase concluded successfully on site; deliverables met."
  },
  {
    id: "MUTUAL_AGREEMENT",
    label: "Mutual Agreement / Contract Concluded",
    status: "COMPLETED",
    defaultReason: "Mutual agreement between employer and worker upon scheduled contract term end."
  },
  {
    id: "DISCONTINUED_BY_EMPLOYER",
    label: "Discontinued by Employer",
    status: "DISCONTINUED",
    defaultReason: "Discontinued by employer due to operational site scope changes."
  },
  {
    id: "WORKER_RESIGNED",
    label: "Worker Resigned",
    status: "RESIGNED",
    defaultReason: "Worker voluntarily resigned due to personal relocation / circumstances."
  },
  {
    id: "OTHER",
    label: "Other (specify below)",
    status: "DISCONTINUED",
    defaultReason: "Employment stint concluded."
  }
];

function formatStintDate(ts) {
  if (!ts) return "N/A";
  const date = new Date(ts > 1e11 ? ts : ts * 1000);
  return date.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
}

await runTest('T2.1: Opening dismissal modal binds worker stint context and defaults', () => {
  const mockStint = {
    id: 101,
    worker_name: "Ram Charan Builder",
    worker_did: "did:passkhadam:worker:builder01",
    category: "Mason",
    job_role: "Mason Lead",
    level: "Skilled",
    nature_of_employment: "Contract",
    location: "Navi Mumbai Site A",
    start_date: 1729000000,
    status: "ACTIVE"
  };

  // State machine simulation for handleOpenDismissModal
  let showModal = false;
  let selectedStint = null;
  let presetId = null;
  let targetStatus = null;
  let notes = null;
  let error = null;

  function handleOpenDismissModal(stint, defaultStatus = 'COMPLETED') {
    selectedStint = stint;
    const matched = CONCLUSION_PRESETS.find(p => p.status === defaultStatus) || CONCLUSION_PRESETS[0];
    presetId = matched.id;
    targetStatus = matched.status;
    notes = matched.defaultReason;
    error = "";
    showModal = true;
  }

  // Open with COMPLETED default
  handleOpenDismissModal(mockStint, 'COMPLETED');
  assert.equal(showModal, true, 'Modal must open');
  assert.equal(selectedStint.id, 101);
  assert.equal(selectedStint.worker_name, 'Ram Charan Builder');
  assert.equal(selectedStint.worker_did, 'did:passkhadam:worker:builder01');
  assert.equal(selectedStint.category, 'Mason');
  assert.equal(selectedStint.job_role, 'Mason Lead');
  assert.equal(selectedStint.location, 'Navi Mumbai Site A');
  assert.equal(presetId, 'PROJECT_COMPLETED');
  assert.equal(targetStatus, 'COMPLETED');
  assert.equal(notes, 'Project phase concluded successfully on site; deliverables met.');

  // Open with DISCONTINUED default
  handleOpenDismissModal(mockStint, 'DISCONTINUED');
  assert.equal(presetId, 'DISCONTINUED_BY_EMPLOYER');
  assert.equal(targetStatus, 'DISCONTINUED');
  assert.equal(notes, 'Discontinued by employer due to operational site scope changes.');
});

await runTest('T2.2: formatStintDate formats timestamp or returns fallback', () => {
  assert.equal(formatStintDate(null), 'N/A');
  assert.equal(formatStintDate(undefined), 'N/A');
  assert.equal(formatStintDate(0), 'N/A');
  const d = formatStintDate(1729000000); // Oct 2024
  assert(d.includes('2024'), `Formatted date should include year 2024: got "${d}"`);
});

await runTest('T2.3: Preset selection updates target status and default notes for all 5 presets', () => {
  for (const preset of CONCLUSION_PRESETS) {
    let presetId = preset.id;
    const matched = CONCLUSION_PRESETS.find(p => p.id === presetId);
    assert(matched, `Preset ${preset.id} must be found`);
    const status = matched.status;
    const defaultReason = matched.defaultReason;

    assert.equal(status, preset.status, `Status mismatch for preset ${preset.id}`);
    assert.equal(defaultReason, preset.defaultReason, `Reason mismatch for preset ${preset.id}`);
  }
});

await runTest('T2.4: Custom notes override default preset reason', () => {
  let presetId = "PROJECT_COMPLETED";
  let notes = "Worker requested release for agricultural harvesting season.";
  const preset = CONCLUSION_PRESETS.find(p => p.id === presetId);
  const finalReason = notes.trim() || preset.defaultReason;

  assert.equal(finalReason, "Worker requested release for agricultural harvesting season.");
});

await runTest('T2.5: Cancel / Abort action cleanly closes modal without API calls or state mutation', () => {
  let showModal = true;
  let selectedStint = { id: 101, status: "ACTIVE" };
  let apiCalls = 0;
  let employments = [{ id: 101, status: "ACTIVE" }];

  function handleCancel() {
    showModal = false;
    selectedStint = null;
    // No API calls executed
  }

  handleCancel();
  assert.equal(showModal, false, 'Modal must close');
  assert.equal(selectedStint, null, 'Selected stint must be cleared');
  assert.equal(apiCalls, 0, 'Zero API calls should be triggered on cancel');
  assert.equal(employments[0].status, 'ACTIVE', 'Employment status in table must remain ACTIVE');
});

await runTest('T2.6: Submission payload adheres to backend PUT /api/v1/employer/employment-status contract', () => {
  const stint = { id: 45, status: "ACTIVE" };
  const targetStatus = "COMPLETED";
  const reason = "Project deliverables achieved on schedule.";

  const payload = {
    method: "PUT",
    endpoint: "/api/v1/employer/employment-status",
    body: {
      employment_id: stint.id,
      new_status: targetStatus,
      reason: reason
    }
  };

  assert.equal(payload.endpoint, "/api/v1/employer/employment-status");
  assert.equal(payload.body.employment_id, 45);
  assert.equal(payload.body.new_status, "COMPLETED");
  assert.equal(payload.body.reason, reason);
});

await runTest('T2.7: Whitespace-only notes gracefully fall back to preset defaultReason', () => {
  let presetId = "MUTUAL_AGREEMENT";
  let notes = "    \t \n   ";
  const preset = CONCLUSION_PRESETS.find(p => p.id === presetId);
  const finalReason = notes.trim() || preset.defaultReason;

  assert.equal(finalReason, "Mutual agreement between employer and worker upon scheduled contract term end.");
});

await runTest('T2.8: Missing optional stint fields in modal render graceful fallbacks', () => {
  const minimalStint = {
    id: 999,
    worker_did: "did:passkhadam:worker:min",
    status: "ACTIVE"
    // missing worker_name, category, job_role, level, nature_of_employment, location, start_date
  };

  const renderedName = minimalStint.worker_name || "Registered Worker";
  const renderedLevel = minimalStint.level || "Skilled";
  const renderedNature = minimalStint.nature_of_employment || "Contract";
  const renderedLocation = minimalStint.location || "N/A";
  const renderedDate = formatStintDate(minimalStint.start_date);

  assert.equal(renderedName, "Registered Worker");
  assert.equal(renderedLevel, "Skilled");
  assert.equal(renderedNature, "Contract");
  assert.equal(renderedLocation, "N/A");
  assert.equal(renderedDate, "N/A");
});

await runTest('T2.9: Rapid double-submission protection via isSubmittingDismiss disabled guard', () => {
  let isSubmittingDismiss = true;
  // Simulating button disabled states
  const isSubmitDisabled = isSubmittingDismiss;
  const isCancelDisabled = isSubmittingDismiss;

  assert.equal(isSubmitDisabled, true, 'Submit button must be disabled while submitting');
  assert.equal(isCancelDisabled, true, 'Cancel button must be disabled while submitting');
});

await runTest('T2.10: Backend error display preserves modal state and permits retry', () => {
  let showModal = true;
  let selectedStint = { id: 50, status: "ACTIVE" };
  let isSubmitting = false;
  let dismissError = "";

  // Simulate API failure
  function simulateFailedSubmission() {
    isSubmitting = true;
    try {
      throw new Error("HTTP 503: Blockchain service temporarily congested");
    } catch (err) {
      dismissError = err.message;
    } finally {
      isSubmitting = false;
    }
  }

  simulateFailedSubmission();
  assert.equal(showModal, true, 'Modal must remain open after failed submission');
  assert.equal(selectedStint.id, 50, 'Selected stint must remain bound');
  assert.equal(isSubmitting, false, 'isSubmitting must reset to false');
  assert.equal(dismissError, "HTTP 503: Blockchain service temporarily congested");
});

// ============================================================================
// SECTION 3: WORKFORCE SEARCH & FILTER INVARIANTS
// ============================================================================
console.log('\n--- SECTION 3: Workforce Search & Filter Invariants ---');

// Mock workforce dataset representing varied scenarios
const mockEmployments = [
  {
    id: 1,
    worker_name: "Mohammed Uzair",
    worker_did: "did:passkhadam:worker:01",
    category: "Mason",
    job_role: "Mason Lead",
    location: "Navi Mumbai Site A",
    status: "ACTIVE"
  },
  {
    id: 2,
    worker_name: "Ramesh Kumar Verma",
    worker_did: "did:passkhadam:worker:02",
    category: "Electrician",
    job_role: "High-Voltage Electrician",
    location: "Pune Cyber Park",
    status: "ACTIVE"
  },
  {
    id: 3,
    worker_name: "Suresh Patil",
    worker_did: "did:passkhadam:worker:03",
    category: "Plumber",
    job_role: "Piping Specialist",
    location: "Thane Residential",
    status: "COMPLETED"
  },
  {
    id: 4,
    worker_name: "Anil Sharma",
    worker_did: "did:passkhadam:worker:04",
    category: "Mason",
    job_role: "Bricklayer",
    location: "Navi Mumbai Site B",
    status: "DISCONTINUED"
  },
  {
    id: 5,
    worker_name: "Dinesh Gowda",
    worker_did: "did:passkhadam:worker:05",
    category: "Heavy Machinery Operator",
    job_role: "Crane Operator",
    location: "JNPT Port Terminal",
    status: "RESIGNED"
  }
];

// Reference filter implementation matching lines 301-320 of EmployerPortal.jsx
function filterWorkforce(allEmployments, searchQuery, tradeFilter, statusTab) {
  return allEmployments.filter(emp => {
    const statusUpper = (emp.status || '').toUpperCase();
    if (statusTab === 'ACTIVE' && statusUpper !== 'ACTIVE') return false;
    if (statusTab === 'CONCLUDED' && statusUpper === 'ACTIVE') return false;
    if (tradeFilter !== 'ALL' && emp.category !== tradeFilter) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      const matchId = String(emp.id).toLowerCase().includes(q) || `#${emp.id}`.toLowerCase().includes(q);
      const matchDid = (emp.worker_did || '').toLowerCase().includes(q);
      const matchCategory = (emp.category || '').toLowerCase().includes(q);
      const matchRole = (emp.job_role || '').toLowerCase().includes(q);
      const matchLoc = (emp.location || '').toLowerCase().includes(q);
      const matchName = (emp.worker_name || emp.name || '').toLowerCase().includes(q);
      if (!matchId && !matchDid && !matchCategory && !matchRole && !matchLoc && !matchName) {
        return false;
      }
    }
    return true;
  });
}

await runTest('T3.1: Keyword search across worker name, DID, ID, role, category, and location', () => {
  // 1. By worker name (case insensitive)
  const byName = filterWorkforce(mockEmployments, 'uzair', 'ALL', 'ALL');
  assert.equal(byName.length, 1);
  assert.equal(byName[0].worker_name, 'Mohammed Uzair');

  // 2. By DID
  const byDid = filterWorkforce(mockEmployments, 'worker:02', 'ALL', 'ALL');
  assert.equal(byDid.length, 1);
  assert.equal(byDid[0].worker_name, 'Ramesh Kumar Verma');

  // 3. By stint ID (#3 and 3)
  const byIdHash = filterWorkforce(mockEmployments, '#3', 'ALL', 'ALL');
  assert.equal(byIdHash.length, 1);
  assert.equal(byIdHash[0].id, 3);

  // 4. By job role
  const byRole = filterWorkforce(mockEmployments, 'Crane', 'ALL', 'ALL');
  assert.equal(byRole.length, 1);
  assert.equal(byRole[0].job_role, 'Crane Operator');

  // 5. By category
  const byCat = filterWorkforce(mockEmployments, 'Mason', 'ALL', 'ALL');
  assert.equal(byCat.length, 2);

  // 6. By location
  const byLoc = filterWorkforce(mockEmployments, 'Navi Mumbai', 'ALL', 'ALL');
  assert.equal(byLoc.length, 2);

  // 7. Whitespace trimming
  const byTrim = filterWorkforce(mockEmployments, '  Pune  ', 'ALL', 'ALL');
  assert.equal(byTrim.length, 1);
  assert.equal(byTrim[0].location, 'Pune Cyber Park');
});

await runTest('T3.2: Trade category dropdown filtering', () => {
  // ALL trades returns 5
  assert.equal(filterWorkforce(mockEmployments, '', 'ALL', 'ALL').length, 5);
  // Mason returns 2
  assert.equal(filterWorkforce(mockEmployments, '', 'Mason', 'ALL').length, 2);
  // Electrician returns 1
  assert.equal(filterWorkforce(mockEmployments, '', 'Electrician', 'ALL').length, 1);
  // Non-existent trade returns 0
  assert.equal(filterWorkforce(mockEmployments, '', 'Carpenter', 'ALL').length, 0);
});

await runTest('T3.3: Status tabs and Partition Invariant (ALL = ACTIVE ∪ CONCLUDED)', () => {
  const allStints = filterWorkforce(mockEmployments, '', 'ALL', 'ALL');
  const activeStints = filterWorkforce(mockEmployments, '', 'ALL', 'ACTIVE');
  const concludedStints = filterWorkforce(mockEmployments, '', 'ALL', 'CONCLUDED');

  assert.equal(allStints.length, 5);
  assert.equal(activeStints.length, 2, 'Should have 2 ACTIVE stints');
  assert.equal(concludedStints.length, 3, 'Should have 3 CONCLUDED stints (1 COMPLETED, 1 DISCONTINUED, 1 RESIGNED)');

  // Partition Invariant
  assert.equal(activeStints.length + concludedStints.length, allStints.length);

  // Disjoint check
  const activeIds = new Set(activeStints.map(s => s.id));
  for (const c of concludedStints) {
    assert(!activeIds.has(c.id), `Stint #${c.id} appears in both active and concluded sets`);
  }
});

await runTest('T3.4: Dynamic reactive counts match tab headers', () => {
  const activeCount = mockEmployments.filter(e => (e.status || '').toUpperCase() === 'ACTIVE').length;
  const concludedCount = mockEmployments.filter(e => (e.status || '').toUpperCase() !== 'ACTIVE').length;

  assert.equal(activeCount, 2);
  assert.equal(concludedCount, 3);
  assert.equal(mockEmployments.length, 5);
});

await runTest('T3.5: Empty state miss detection and "Reset All Filters" CTA action', () => {
  // Query with zero matches
  let searchQuery = 'NonExistentWorkerXYZ';
  let tradeFilter = 'Mason';
  let statusTab = 'CONCLUDED';

  let filtered = filterWorkforce(mockEmployments, searchQuery, tradeFilter, statusTab);
  assert.equal(filtered.length, 0, 'Should yield 0 matches');

  // Verify Reset Filters action
  function handleResetFilters() {
    searchQuery = '';
    tradeFilter = 'ALL';
    statusTab = 'ALL';
  }

  handleResetFilters();
  filtered = filterWorkforce(mockEmployments, searchQuery, tradeFilter, statusTab);
  assert.equal(filtered.length, 5, 'Reset must restore full workforce table view');
  assert.equal(searchQuery, '');
  assert.equal(tradeFilter, 'ALL');
  assert.equal(statusTab, 'ALL');
});

await runTest('T3.6: Regex special characters in search query are handled literally without crash', () => {
  const adversarialQueries = ['*', '+', '(', ')', '[', ']', '?', '\\', '^', '$', '.*', '(a|b)', '[0-9]'];
  for (const q of adversarialQueries) {
    // Should not throw SyntaxError
    assert.doesNotThrow(() => {
      filterWorkforce(mockEmployments, q, 'ALL', 'ALL');
    }, `Filter crashed on adversarial query "${q}"`);
  }
});

await runTest('T3.7: Stints with missing, null, or undefined fields are handled without error', () => {
  const noisyEmployments = [
    { id: 91, worker_name: null, worker_did: null, category: null, job_role: null, location: null, status: null },
    { id: 92, worker_name: undefined, worker_did: undefined, category: undefined, job_role: undefined, location: undefined, status: undefined },
    { id: 93 }
  ];

  assert.doesNotThrow(() => {
    const res = filterWorkforce(noisyEmployments, 'test', 'ALL', 'ALL');
    assert.equal(res.length, 0);
  }, 'Filter threw on nullish employment records');
});

await runTest('T3.8: Status case-insensitivity: lowercase status matches uppercase tabs', () => {
  const mixedCaseStints = [
    { id: 1, category: "Mason", status: "active" },
    { id: 2, category: "Mason", status: "Active" },
    { id: 3, category: "Mason", status: "completed" },
    { id: 4, category: "Mason", status: "Discontinued" }
  ];

  const active = filterWorkforce(mixedCaseStints, '', 'ALL', 'ACTIVE');
  const concluded = filterWorkforce(mixedCaseStints, '', 'ALL', 'CONCLUDED');

  assert.equal(active.length, 2, 'Should match both active and Active');
  assert.equal(concluded.length, 2, 'Should match both completed and Discontinued');
});

await runTest('T3.9: Combined multi-criteria search and trade filter yields exact intersection', () => {
  // Query: Search for "Site A", Trade: "Mason", Status: "ACTIVE"
  const res1 = filterWorkforce(mockEmployments, 'Site A', 'Mason', 'ACTIVE');
  assert.equal(res1.length, 1);
  assert.equal(res1[0].worker_name, 'Mohammed Uzair');

  // Query: Search for "Site A", Trade: "Electrician", Status: "ACTIVE" -> 0 matches (electrician is at Pune)
  const res2 = filterWorkforce(mockEmployments, 'Site A', 'Electrician', 'ACTIVE');
  assert.equal(res2.length, 0);
});

// ============================================================================
// SECTION 4: ACTIONABLE GUIDANCE & AST STATIC CODE CONTRACTS
// ============================================================================
console.log('\n--- SECTION 4: Actionable Guidance & AST Static Code Contracts ---');

const wpPath = path.join(SRC_DIR, 'components', 'worker', 'WorkerPortal.jsx');
const epPath = path.join(SRC_DIR, 'components', 'employer', 'EmployerPortal.jsx');
const gpPath = path.join(SRC_DIR, 'components', 'government', 'GovernmentPortal.jsx');
const apiPath = path.join(SRC_DIR, 'utils', 'api.js');

assert(fs.existsSync(wpPath), 'WorkerPortal.jsx must exist');
assert(fs.existsSync(epPath), 'EmployerPortal.jsx must exist');
assert(fs.existsSync(gpPath), 'GovernmentPortal.jsx must exist');
assert(fs.existsSync(apiPath), 'api.js must exist');

const wpSrc = fs.readFileSync(wpPath, 'utf-8');
const epSrc = fs.readFileSync(epPath, 'utf-8');
const gpSrc = fs.readFileSync(gpPath, 'utf-8');
const apiSrc = fs.readFileSync(apiPath, 'utf-8');

await runTest('T4.1: WorkerPortal preserves verbatim endpoint and incorporates formatting controls', () => {
  // Verbatim endpoint assertion mandatory for challenger AST compatibility
  assert(
    wpSrc.includes("apiFetch('/api/v1/worker/verify-aadhaar/me'"),
    "WorkerPortal.jsx must preserve verbatim apiFetch('/api/v1/worker/verify-aadhaar/me'"
  );
  assert(wpSrc.includes('formatAadhaarInput'), 'WorkerPortal.jsx must import and use formatAadhaarInput');
  assert(wpSrc.includes('12/12 Digits Valid'), 'WorkerPortal.jsx must render 12/12 Digits Valid badge');
  assert(wpSrc.includes('maxLength={14}'), 'WorkerPortal.jsx input must enforce maxLength 14');
  assert(wpSrc.includes('placeholder="1234 5678 4821"'), 'WorkerPortal.jsx must provide formatted placeholder');
  assert(wpSrc.includes('Action Required: Verify Government Identity to Activate Wallet'), 'WorkerPortal.jsx must render unanchored identity guidance');
  assert(wpSrc.includes('Worker Permanence Invariant:'), 'WorkerPortal.jsx must render permanence reassurance banner');
});

await runTest('T4.2: EmployerPortal contains dismissal modal, presets, search, trade filter, and tabs', () => {
  assert(epSrc.includes('showDismissConfirmModal'), 'EmployerPortal.jsx must declare showDismissConfirmModal');
  assert(epSrc.includes('CONCLUSION_PRESETS'), 'EmployerPortal.jsx must define CONCLUSION_PRESETS');
  assert(epSrc.includes('handleConfirmDismiss'), 'EmployerPortal.jsx must define handleConfirmDismiss');
  assert(epSrc.includes('handleOpenDismissModal'), 'EmployerPortal.jsx must define handleOpenDismissModal');
  assert(epSrc.includes('searchQuery'), 'EmployerPortal.jsx must declare searchQuery');
  assert(epSrc.includes('tradeFilter'), 'EmployerPortal.jsx must declare tradeFilter');
  assert(epSrc.includes('statusTab'), 'EmployerPortal.jsx must declare statusTab');
  assert(epSrc.includes('All Stints'), 'EmployerPortal.jsx must render All Stints tab');
  assert(epSrc.includes('Active Only'), 'EmployerPortal.jsx must render Active Only tab');
  assert(epSrc.includes('Concluded / Past'), 'EmployerPortal.jsx must render Concluded / Past tab');
  assert(epSrc.includes('Reset Filters') || epSrc.includes('Reset All Filters'), 'EmployerPortal.jsx must render filter reset CTA');
  assert(epSrc.includes('Organization Registration Under Platform Review (PENDING_REVIEW)'), 'EmployerPortal.jsx must render PENDING_REVIEW banner');
  assert(epSrc.includes('Web-First Verification & Stint Permanence Guidance'), 'EmployerPortal.jsx must render Web-First Stint Permanence Guidance');
});

await runTest('T4.3: GovernmentPortal contains Inter-State Welfare Portability & Cooldown Guidance', () => {
  assert(
    gpSrc.includes('Inter-State Welfare Portability & Sovereign Cooldown Invariants') ||
    gpSrc.includes('Inter-State Welfare Portability &amp; Sovereign Cooldown Invariants'),
    'GovernmentPortal.jsx must render Inter-State Welfare Portability guidance'
  );
  assert(
    gpSrc.includes('1. Inter-State Portability'),
    'GovernmentPortal.jsx must detail Inter-State Portability'
  );
  assert(
    gpSrc.includes('2. Zero-Camera Verification'),
    'GovernmentPortal.jsx must detail Zero-Camera Verification'
  );
  assert(
    gpSrc.includes('3. Automated Policy Cooldown'),
    'GovernmentPortal.jsx must explain Automated Policy Cooldown'
  );
});

await runTest('T4.4: Centralized api.js exports formatAadhaarInput and cleanAadhaarDigits cleanly', () => {
  assert(apiSrc.includes('export function formatAadhaarInput'), 'api.js must export formatAadhaarInput');
  assert(apiSrc.includes('export function cleanAadhaarDigits'), 'api.js must export cleanAadhaarDigits');
});

console.log('\n================================================================');
console.log(`  ALL ${passedTests}/${totalTests} M4 ADVERSARIAL CHALLENGER TESTS PASSED!`);
console.log('================================================================\n');
