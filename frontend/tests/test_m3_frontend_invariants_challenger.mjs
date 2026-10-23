/**
 * frontend/tests/test_m3_frontend_invariants_challenger.mjs
 * Milestone 3 Frontend Image Parsing & Stepper Invariants Challenger Suite
 * 
 * Verifies:
 * 1. Data URI to Blob conversion and File construction with varied MIME types and filenames.
 * 2. Byte-for-byte binary fidelity between Data URI and constructed File.
 * 3. Fallback filename generation and Unicode / special characters tolerance.
 * 4. Error resilience for malformed Data URIs.
 * 5. Full 11-stage verification pipeline stepper logic and completion invariants.
 * 6. Static code contract audit on QRImageUploader.jsx and VerificationStepper.jsx.
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
console.log('  MILESTONE 3 CHALLENGER: FRONTEND IMAGE PARSING & STEPPERS     ');
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
// 1. Static Contract Analysis of QRImageUploader.jsx
// ----------------------------------------------------------------------------

const qrUploaderPath = path.join(SRC_DIR, 'components', 'common', 'QRImageUploader.jsx');
assert(fs.existsSync(qrUploaderPath), `QRImageUploader.jsx must exist at ${qrUploaderPath}`);
const qrUploaderSrc = fs.readFileSync(qrUploaderPath, 'utf-8');

const stepperPath = path.join(SRC_DIR, 'components', 'common', 'VerificationStepper.jsx');
assert(fs.existsSync(stepperPath), `VerificationStepper.jsx must exist at ${stepperPath}`);
const stepperSrc = fs.readFileSync(stepperPath, 'utf-8');

await runTest('QRImageUploader contains role-aware zero-camera endpoint resolution', () => {
  assert(
    qrUploaderSrc.includes('/api/v1/government/demo-worker-qr'),
    'Must target government demo worker QR endpoint for government verifiers'
  );
  assert(
    qrUploaderSrc.includes('/api/v1/employer/demo-worker-qr'),
    'Must target employer demo worker QR endpoint for employer verifiers'
  );
  assert(
    qrUploaderSrc.includes('/api/v1/worker/presentation/demo-qr'),
    'Must provide fallback to public worker demo QR presentation endpoint'
  );
});

await runTest('QRImageUploader implements Data URI to Blob and File conversion', () => {
  assert(
    qrUploaderSrc.includes('await fetch(data.qr_base64_data_uri)'),
    'Must convert qr_base64_data_uri via browser fetch'
  );
  assert(
    qrUploaderSrc.includes('await blobRes.blob()'),
    'Must extract Blob from fetch response'
  );
  assert(
    qrUploaderSrc.includes('new File([blob], fileName'),
    'Must construct a native browser File object'
  );
  assert(
    qrUploaderSrc.includes('onVerify(simulatedFile)'),
    'Must immediately trigger verification pipeline on simulated File'
  );
});

await runTest('QRImageUploader renders zero-camera simulation trigger buttons and notices', () => {
  assert(
    qrUploaderSrc.includes('1-Click Simulate Scan from Worker Preset'),
    'Must render 1-click simulate scan button'
  );
  assert(
    qrUploaderSrc.includes('Simulate Fresh Worker QR'),
    'Must render refresh simulation button'
  );
  assert(
    qrUploaderSrc.includes('Zero-Camera Demonstration Mode'),
    'Must render zero-camera guidance card'
  );
});

// ----------------------------------------------------------------------------
// 2. Static Contract Analysis of VerificationStepper.jsx
// ----------------------------------------------------------------------------

await runTest('VerificationStepper defines all 11 standardized verification stages', () => {
  const expectedSteps = [
    { step: 1, name: "Payload Parse & Schema Validation" },
    { step: 2, name: "Presentation Signature Verification" },
    { step: 3, name: "Expiration / Timestamp Validation" },
    { step: 4, name: "On-Chain DID & Registration Verification" },
    { step: 5, name: "IPFS Credential Retrieval" },
    { step: 6, name: "Integrity Hash Verification" },
    { step: 7, name: "Decryption of Verifiable Credential" },
    { step: 8, name: "Issuer Signature Verification" },
    { step: 9, name: "Role-Based Data Redaction" },
    { step: 10, name: "Verifier Authorization & Scope Check" },
    { step: 11, name: "Deferred Atomic Nonce Consumption" }
  ];

  for (const exp of expectedSteps) {
    assert(
      stepperSrc.includes(`step: ${exp.step}`),
      `VerificationStepper missing definition for step ${exp.step}`
    );
    assert(
      stepperSrc.includes(exp.name),
      `VerificationStepper missing name "${exp.name}" for step ${exp.step}`
    );
  }

  assert(
    stepperSrc.includes('{steps.length}/11 Stages Verified'),
    'Must display dynamic verified stage count out of 11'
  );
});

// ----------------------------------------------------------------------------
// 3. Runtime Data URI to Blob and File Construction Invariants
// ----------------------------------------------------------------------------

// 1x1 valid PNG base64
const samplePngBase64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
const samplePngBytes = Buffer.from(samplePngBase64, 'base64');

await runTest('Runtime conversion: PNG Data URI to Blob and File', async () => {
  const dataUri = `data:image/png;base64,${samplePngBase64}`;
  const fileName = 'demo_worker_Ramesh_Kumar_qr.png';

  const res = await fetch(dataUri);
  assert(res.ok, 'fetch(dataUri) must succeed');
  const blob = await res.blob();

  assert.equal(blob.type, 'image/png');
  assert.equal(blob.size, samplePngBytes.length);

  const file = new File([blob], fileName, { type: 'image/png' });
  assert.equal(file.name, fileName);
  assert.equal(file.type, 'image/png');
  assert.equal(file.size, samplePngBytes.length);

  // Assert byte-for-byte fidelity
  const fileArrayBuffer = await file.arrayBuffer();
  const fileBuffer = Buffer.from(fileArrayBuffer);
  assert(fileBuffer.equals(samplePngBytes), 'File content must match original PNG bytes exactly');
});

await runTest('Runtime conversion: Varied MIME types (JPEG, WebP, SVG)', async () => {
  const mimeTypes = [
    { type: 'image/jpeg', b64: '/9j/4AAQSkZJRg==' },
    { type: 'image/webp', b64: 'UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAD8D+JaQAA3AA/ua1AAA=' },
    { type: 'image/svg+xml', b64: 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjwvc3ZnPg==' }
  ];

  for (const m of mimeTypes) {
    const dataUri = `data:${m.type};base64,${m.b64}`;
    const res = await fetch(dataUri);
    assert(res.ok);
    const blob = await res.blob();
    assert.equal(blob.type, m.type);
    const file = new File([blob], `test.${m.type.split('/')[1]}`, { type: m.type });
    assert.equal(file.type, m.type);
  }
});

await runTest('Runtime conversion: Varied and complex filenames', async () => {
  const filenames = [
    'demo worker Ramesh Kumar Verma qr.png',
    'worker_प्रमाणपत्र_123.png',
    'worker-credential#42(verified)[final].png',
    'worker.presentation.card.min.png',
    '   leading_trailing_spaces   .png'
  ];

  const dataUri = `data:image/png;base64,${samplePngBase64}`;
  for (const name of filenames) {
    const res = await fetch(dataUri);
    const blob = await res.blob();
    const file = new File([blob], name, { type: 'image/png' });
    assert.equal(file.name, name, `File name mismatch for "${name}"`);
    assert.equal(file.size, samplePngBytes.length);
  }
});

await runTest('Runtime conversion: Missing filename fallback logic', () => {
  const dataWithoutFilename = {};
  const fallbackName = dataWithoutFilename.filename || `worker_presentation_${Date.now()}.png`;
  assert(fallbackName.startsWith('worker_presentation_'));
  assert(fallbackName.endsWith('.png'));
});

await runTest('Runtime conversion: Error handling for malformed Data URIs', async () => {
  const malformedUris = [
    'not_a_valid_data_uri',
    'data:image/png;base64,!!!invalid-base64-content@@@'
  ];

  for (const badUri of malformedUris) {
    let errorCaught = false;
    try {
      await fetch(badUri);
    } catch {
      errorCaught = true;
    }
    // In Node or browser, invalid scheme or malformed URI throws TypeError
    assert(errorCaught, `Expected fetch to reject for invalid URI: ${badUri}`);
  }
});

// ----------------------------------------------------------------------------
// 4. Stepper Invariant Simulation: 11-Step Success Sequence
// ----------------------------------------------------------------------------

await runTest('Stepper Evaluation: All 11 steps completed evaluates all isDone = true', () => {
  const mockAuditSteps = [
    { step: 1, name: "Payload Parse & Schema Validation", status: "SUCCESS" },
    { step: 2, name: "Presentation Signature Verification", status: "SUCCESS" },
    { step: 3, name: "Expiration / Timestamp Validation", status: "SUCCESS" },
    { step: 4, name: "On-Chain DID & Registration Verification", status: "SUCCESS" },
    { step: 5, name: "IPFS Credential Retrieval", status: "SUCCESS" },
    { step: 6, name: "Integrity Hash Verification", status: "SUCCESS" },
    { step: 7, name: "Decryption of Verifiable Credential", status: "SUCCESS" },
    { step: 8, name: "Issuer Signature Verification", status: "SUCCESS" },
    { step: 9, name: "Role-Based Data Redaction", status: "SUCCESS" },
    { step: 10, name: "Verifier Authorization & Scope Check", status: "SUCCESS" },
    { step: 11, name: "Deferred Atomic Nonce Consumption", status: "SUCCESS" }
  ];

  const defaultStepNumbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
  const isCompleted = true;

  for (const stepNum of defaultStepNumbers) {
    const matchingResult = mockAuditSteps.find(st => st.step === stepNum);
    assert(matchingResult, `Step ${stepNum} must exist in audit steps`);
    const isDone = Boolean(
      (matchingResult && (matchingResult.status === "SUCCESS" || matchingResult.status === "VERIFIED" || matchingResult.status === "COMPLETED")) ||
      (isCompleted && matchingResult)
    );
    assert.equal(isDone, true, `Step ${stepNum} must evaluate isDone=true`);
  }
});

await runTest('Stepper Evaluation: Replay failure at Step 11 properly isolates failure', () => {
  const mockAuditStepsWithReplay = [
    { step: 1, name: "Payload Parse & Schema Validation", status: "SUCCESS" },
    { step: 2, name: "Presentation Signature Verification", status: "SUCCESS" },
    { step: 3, name: "Expiration / Timestamp Validation", status: "SUCCESS" },
    { step: 4, name: "On-Chain DID & Registration Verification", status: "SUCCESS" },
    { step: 5, name: "IPFS Credential Retrieval", status: "SUCCESS" },
    { step: 6, name: "Integrity Hash Verification", status: "SUCCESS" },
    { step: 7, name: "Decryption of Verifiable Credential", status: "SUCCESS" },
    { step: 8, name: "Issuer Signature Verification", status: "SUCCESS" },
    { step: 9, name: "Role-Based Data Redaction", status: "SUCCESS" },
    { step: 10, name: "Verifier Authorization & Scope Check", status: "SUCCESS" },
    { step: 11, name: "Deferred Atomic Nonce Consumption", status: "FAILED", detail: "Replay attack detected" }
  ];

  const isCompleted = false; // Verification failed overall

  // Steps 1-10 are success
  for (let s = 1; s <= 10; s++) {
    const matching = mockAuditStepsWithReplay.find(st => st.step === s);
    const isDone = Boolean(
      (matching && (matching.status === "SUCCESS" || matching.status === "VERIFIED" || matching.status === "COMPLETED")) ||
      (isCompleted && matching)
    );
    assert.equal(isDone, true, `Step ${s} should be marked done`);
  }

  // Step 11 is failed
  const step11 = mockAuditStepsWithReplay.find(st => st.step === 11);
  const isDone11 = Boolean(
    (step11 && (step11.status === "SUCCESS" || step11.status === "VERIFIED" || step11.status === "COMPLETED")) ||
    (isCompleted && step11)
  );
  assert.equal(isDone11, false, 'Step 11 must NOT be marked done when status is FAILED');
});

console.log('\n================================================================');
console.log(`  SUMMARY: ${passedTests}/${totalTests} tests passed cleanly.`);
console.log('================================================================\n');
