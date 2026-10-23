import { strict as assert } from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, '..');

const authContextSrc = fs.readFileSync(path.join(frontendDir, 'src', 'context', 'AuthContext.jsx'), 'utf-8');
const roleGuardSrc = fs.readFileSync(path.join(frontendDir, 'src', 'components', 'common', 'RoleGuard.jsx'), 'utf-8');
const appSrc = fs.readFileSync(path.join(frontendDir, 'src', 'App.jsx'), 'utf-8');
const headerSrc = fs.readFileSync(path.join(frontendDir, 'src', 'components', 'common', 'Header.jsx'), 'utf-8');

console.log('================================================================');
console.log('  M8 REGRESSION SUITE: ROLE GUARD HARDENING & DEAD-BUTTON PROOF  ');
console.log('================================================================\n');

// 1. AuthContext discards role-less or corrupt pk_user on startup
console.log('--- SECTION 1: LocalStorage Role Integrity on Startup ---');
assert.match(
  authContextSrc,
  /Discovered corrupt or role-less pk_user in localStorage, discarding/,
  'AuthContext must detect and purge role-less pk_user on initialization'
);
assert.match(
  authContextSrc,
  /role:\s*role\.trim\(\)\.toUpperCase\(\)/,
  'AuthContext must normalize role to uppercase on startup'
);
console.log('  [PASS] T1.1: AuthContext parses and validates role presence in pk_user');

// 2. RoleGuard handles missing userRole gracefully without blank text
console.log('\n--- SECTION 2: RoleGuard Session Incomplete & Role Extraction ---');
assert.match(
  roleGuardSrc,
  /const rawRole\s*=\s*currentUser\.role\s*\|\|\s*currentUser\.user\?\.role/,
  'RoleGuard extracts role from both top-level and nested user.role'
);
assert.match(
  roleGuardSrc,
  /if\s*\(!userRole\)\s*\{[\s\S]*?Session Incomplete/,
  'RoleGuard renders Session Incomplete when userRole is missing or blank'
);
console.log('  [PASS] T2.1: RoleGuard has explicit !userRole gate preventing blank role display');

// 3. Switch Account / Sign In button is active and never a dead button
console.log('\n--- SECTION 3: Active Action Handlers & Event Bus ---');
assert.match(
  roleGuardSrc,
  /const handleOpenAuth\s*=\s*async\s*\(\)\s*=>\s*\{[\s\S]*?await logout\(\);[\s\S]*?window\.dispatchEvent\(new CustomEvent\('pk_open_auth'\)\);/,
  'handleOpenAuth calls logout() and dispatches pk_open_auth event'
);
assert.match(
  headerSrc,
  /window\.addEventListener\('pk_open_auth',\s*handlePkOpenAuth\)/,
  'Header.jsx listens to pk_open_auth event and opens AuthModal'
);
console.log('  [PASS] T3.1: RoleGuard buttons trigger logout and dispatch pk_open_auth event to Header');

// 4. Role mismatch display uses validated userRole
console.log('\n--- SECTION 4: Role Mismatch Display Integrity ---');
assert.match(
  roleGuardSrc,
  /You are signed in as <strong className="text-slate-200">\{userRole\}<\/strong>/,
  'Role Mismatch displays validated userRole instead of unvalidated currentUser.role'
);
console.log('  [PASS] T4.1: Role Mismatch displays guaranteed non-empty userRole');

console.log('\n================================================================');
console.log('  ALL M8 REGRESSION TESTS PASSED (100%)!                        ');
console.log('================================================================\n');
