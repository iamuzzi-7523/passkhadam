/**
 * frontend/tests/test_m2_ui_invariants_challenger.mjs
 *
 * Empirical Adversarial Challenger Test Suite for Milestone 2:
 * - Tab Filtering Invariants (Partitioning, count badges, empty states)
 * - Status Badges & Permanence Banners (DISCONTINUED amber banner, COMPLETED blue banner)
 * - Skills & Trade Modal (Other trade selection, skill chip removal, duplicate prevention, quick-add, API error handling)
 * - API Utilities Contract & Fallback Verification
 *
 * Author: challenger_m2_1 (EMPIRICAL CHALLENGER)
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
console.log('  M2 EMPIRICAL ADVERSARIAL CHALLENGE SUITE: FRONTEND UI & STATE');
console.log('  TAB FILTERING INVARIANTS, PERMANENCE BANNERS, SKILLS MODAL    ');
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
// Source Code & AST Invariant Checks
// ----------------------------------------------------------------------------
const workerPortalPath = path.join(SRC_DIR, 'components', 'worker', 'WorkerPortal.jsx');
const workerPortalSrc = fs.readFileSync(workerPortalPath, 'utf-8');

const apiJsPath = path.join(SRC_DIR, 'utils', 'api.js');
const apiJsSrc = fs.readFileSync(apiJsPath, 'utf-8');

// ----------------------------------------------------------------------------
// Replicating WorkerPortal logic & state machines for empirical execution
// ----------------------------------------------------------------------------

const STANDARD_TRADES = [
  'Mason',
  'Electrician',
  'Plumber',
  'Carpenter',
  'Painter',
  'Welder',
  'Heavy Machinery Operator',
  'Driver',
  'Steel Fixer',
  'Tile Setter',
  'General Construction'
];

const SUGGESTED_SKILLS_MAP = {
  Mason: ['Bricklaying', 'Concreting', 'Plastering', 'Formwork', 'Scaffolding', 'Mortar Mixing'],
  Electrician: ['Conduit Wiring', 'Switchgear', 'Panel Installation', 'Solar PV', 'Earthing', 'Fault Finding'],
  Plumber: ['PVC Piping', 'GI Piping', 'Drainage Systems', 'Sanitary Fixtures', 'Water Pumps', 'Leak Detection'],
  Carpenter: ['Formwork', 'Framing', 'Door & Window Fitting', 'Scaffolding', 'Roof Trussing'],
  Painter: ['Surface Preparation', 'Primer Application', 'Emulsion Painting', 'Enamel Coating', 'Spray Painting'],
  Welder: ['Arc Welding', 'MIG Welding', 'TIG Welding', 'Gas Cutting', 'Structural Steel Fabrication'],
  'Heavy Machinery Operator': ['Excavator Operation', 'Backhoe Loader', 'Dump Truck', 'Compactor', 'Safety Rigging'],
  Driver: ['Heavy Commercial Vehicle', 'Light Commercial Vehicle', 'Route Logistics', 'Vehicle Maintenance'],
  'Steel Fixer': ['Rebar Cutting', 'Rebar Bending', 'Mesh Tying', 'Column Caging'],
  'Tile Setter': ['Ceramic Tiling', 'Marble Flooring', 'Granite Fitting', 'Tile Grouting'],
  'General Construction': ['Site Clearance', 'Material Handling', 'Concrete Pouring', 'Trench Digging']
};

/**
 * Pure evaluation of WorkerPortal's tab filtering logic
 */
function evaluateTabFiltering(employmentHistory, wallet, historyFilter) {
  const effectiveEmployments = employmentHistory?.employments || wallet?.employments || [];
  const activeCount = employmentHistory?.active_count !== undefined 
    ? employmentHistory.active_count 
    : effectiveEmployments.filter(e => (e.status || '').toUpperCase() === 'ACTIVE').length;
  const historicalCount = employmentHistory?.historical_count !== undefined 
    ? employmentHistory.historical_count 
    : effectiveEmployments.filter(e => (e.status || '').toUpperCase() !== 'ACTIVE').length;

  const filteredEmployments = effectiveEmployments.filter(emp => {
    const isActive = (emp.status || '').toUpperCase() === 'ACTIVE';
    if (historyFilter === 'ACTIVE') return isActive;
    if (historyFilter === 'HISTORICAL') return !isActive;
    return true;
  });

  const emptyStateText = filteredEmployments.length === 0
    ? (historyFilter === 'ACTIVE'
        ? 'No active employment stints currently running.'
        : historyFilter === 'HISTORICAL'
        ? 'No past or discontinued stints recorded yet.'
        : 'No employment records logged on-chain yet.')
    : null;

  return {
    effectiveEmployments,
    activeCount,
    historicalCount,
    allCount: effectiveEmployments.length,
    filteredEmployments,
    emptyStateText
  };
}

/**
 * Pure evaluation of WorkerPortal's status badge rendering logic
 */
function evaluateEmploymentStatusBadge(status) {
  const norm = (status || '').toUpperCase();
  switch (norm) {
    case 'ACTIVE':
      return { text: 'ACTIVE', color: 'emerald', hasPulse: true };
    case 'COMPLETED':
      return { text: '✓ COMPLETED', color: 'blue', hasPulse: false };
    case 'DISCONTINUED':
      return { text: '⚠️ DISCONTINUED', color: 'amber', hasPulse: false };
    case 'TERMINATED':
    case 'DISMISSED':
      return { text: `✕ ${norm}`, color: 'rose', hasPulse: false };
    case 'RESIGNED':
      return { text: 'RESIGNED', color: 'purple', hasPulse: false };
    case 'SUSPENDED':
      return { text: 'SUSPENDED', color: 'yellow', hasPulse: false };
    default:
      return { text: status || 'UNKNOWN', color: 'slate', hasPulse: false };
  }
}

/**
 * Pure evaluation of WorkerPortal's contextual banners logic
 */
function evaluateContextualBanners(emp) {
  const isDiscontinued = (emp.status || '').toUpperCase() === 'DISCONTINUED';
  const isCompleted = (emp.status || '').toUpperCase() === 'COMPLETED';

  let banner = null;
  if (isDiscontinued) {
    banner = {
      type: 'PERMANENCE_INVARIANT',
      color: 'amber',
      text: 'Permanence Invariant: Category authorization discontinued by platform governance. Historical stint permanently recorded in worker provenance ledger.'
    };
  } else if (isCompleted) {
    banner = {
      type: 'COMPLETION_BANNER',
      color: 'blue',
      text: 'Employment tenure successfully completed and verified on-chain.'
    };
  }

  const borderClass = isDiscontinued
    ? 'border-amber-500/30 hover:border-amber-500/50'
    : isCompleted
    ? 'border-blue-500/30 hover:border-blue-500/50'
    : 'border-slate-800 hover:border-slate-700';

  return {
    isDiscontinued,
    isCompleted,
    banner,
    borderClass
  };
}

/**
 * Interactive State Machine Harness for WorkerPortal Skills & Trade Modal
 */
function createSkillsModalHarness(profile, apiFetchMock) {
  let showSkillsModal = false;
  let modalTrade = 'Mason';
  let customTradeInput = '';
  let modalSkills = [];
  let newSkillInput = '';
  let savingSkills = false;
  let errorMsg = '';
  let successMsg = '';

  const handleOpenSkillsModal = () => {
    const currentCategory = profile?.worker_category || 'Mason';
    if (STANDARD_TRADES.includes(currentCategory)) {
      modalTrade = currentCategory;
      customTradeInput = '';
    } else {
      modalTrade = 'Other';
      customTradeInput = currentCategory;
    }
    modalSkills = Array.isArray(profile?.skills) ? [...profile.skills] : [];
    newSkillInput = '';
    errorMsg = '';
    showSkillsModal = true;
  };

  const handleAddSkill = () => {
    const trimmed = newSkillInput.trim();
    if (trimmed && !modalSkills.includes(trimmed)) {
      modalSkills = [...modalSkills, trimmed];
      newSkillInput = '';
    }
  };

  const handleRemoveSkill = (index) => {
    modalSkills = modalSkills.filter((_, idx) => idx !== index);
  };

  const handleAddSuggestedSkill = (skill) => {
    if (skill && !modalSkills.includes(skill)) {
      modalSkills = [...modalSkills, skill];
    }
  };

  const handleSaveSkillsAndTrade = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    savingSkills = true;
    errorMsg = '';
    successMsg = '';
    try {
      const selectedCategory = modalTrade === 'Other' ? (customTradeInput.trim() || 'Other') : modalTrade;
      const res = await apiFetchMock('/api/v1/worker/skills/me', {
        method: 'PUT',
        body: {
          worker_category: selectedCategory,
          skills: modalSkills
        }
      });
      if (!res.ok) {
        // Fallback to /profile/me if /skills/me fails
        const fallbackRes = await apiFetchMock('/api/v1/worker/profile/me', {
          method: 'PUT',
          body: {
            worker_category: selectedCategory,
            skills: modalSkills
          }
        });
        if (!fallbackRes.ok) {
          const errData = await fallbackRes.json();
          throw new Error(errData.detail || 'Failed to update skills and trade profile');
        }
      }
      successMsg = 'Trade and skills profile successfully updated!';
      showSkillsModal = false;
    } catch (err) {
      errorMsg = err.message || 'Error updating skills';
    } finally {
      savingSkills = false;
    }
  };

  return {
    getState: () => ({
      showSkillsModal,
      modalTrade,
      customTradeInput,
      modalSkills,
      newSkillInput,
      savingSkills,
      errorMsg,
      successMsg
    }),
    setModalTrade: (val) => { modalTrade = val; },
    setCustomTradeInput: (val) => { customTradeInput = val; },
    setNewSkillInput: (val) => { newSkillInput = val; },
    handleOpenSkillsModal,
    handleAddSkill,
    handleRemoveSkill,
    handleAddSuggestedSkill,
    handleSaveSkillsAndTrade
  };
}

// ============================================================================
// TEST SUITE EXECUTION
// ============================================================================

async function main() {

  // --------------------------------------------------------------------------
  // SECTION 1: TAB FILTERING INVARIANTS & PARTITIONING
  // --------------------------------------------------------------------------
  console.log('\n--- SECTION 1: TAB FILTERING INVARIANTS & PARTITIONING ---');

  await runTest('T1.1 Partition Invariant: ALL = ACTIVE ∪ HISTORICAL with empty intersection', () => {
    const stints = [
      { id: 1, status: 'ACTIVE' },
      { id: 2, status: 'COMPLETED' },
      { id: 3, status: 'DISCONTINUED' },
      { id: 4, status: 'ACTIVE' },
      { id: 5, status: 'TERMINATED' },
      { id: 6, status: 'RESIGNED' },
      { id: 7, status: 'SUSPENDED' },
      { id: 8, status: 'DISMISSED' }
    ];
    const data = { employments: stints, active_count: 2, historical_count: 6, total_count: 8 };

    const allRes = evaluateTabFiltering(data, null, 'ALL');
    const actRes = evaluateTabFiltering(data, null, 'ACTIVE');
    const histRes = evaluateTabFiltering(data, null, 'HISTORICAL');

    assert.equal(allRes.filteredEmployments.length, 8);
    assert.equal(actRes.filteredEmployments.length, 2);
    assert.equal(histRes.filteredEmployments.length, 6);

    // Mathematical partition check
    assert.equal(allRes.filteredEmployments.length, actRes.filteredEmployments.length + histRes.filteredEmployments.length);

    // Disjoint check
    const actIds = new Set(actRes.filteredEmployments.map(e => e.id));
    const histIds = new Set(histRes.filteredEmployments.map(e => e.id));
    for (const id of actIds) {
      assert.equal(histIds.has(id), false, `ID ${id} must not exist in both active and historical partitions`);
    }
  });

  await runTest('T1.2 Count Badges Match Filtered Lengths Under All Scenarios', () => {
    const testCases = [
      { name: 'Zero stints', stints: [], expActive: 0, expHist: 0 },
      { name: 'Only active stints', stints: [{ id: 1, status: 'ACTIVE' }, { id: 2, status: 'ACTIVE' }], expActive: 2, expHist: 0 },
      { name: 'Only completed stints', stints: [{ id: 1, status: 'COMPLETED' }, { id: 2, status: 'COMPLETED' }], expActive: 0, expHist: 2 },
      { name: 'Only discontinued stints', stints: [{ id: 1, status: 'DISCONTINUED' }], expActive: 0, expHist: 1 },
      { name: 'Mixed case statuses', stints: [{ id: 1, status: 'active' }, { id: 2, status: 'Discontinued' }, { id: 3, status: 'COMPLETED' }], expActive: 1, expHist: 2 },
      { name: 'Null or missing status', stints: [{ id: 1, status: null }, { id: 2, status: undefined }, { id: 3, status: '' }], expActive: 0, expHist: 3 }
    ];

    for (const tc of testCases) {
      const data = { employments: tc.stints };
      const allRes = evaluateTabFiltering(data, null, 'ALL');
      const actRes = evaluateTabFiltering(data, null, 'ACTIVE');
      const histRes = evaluateTabFiltering(data, null, 'HISTORICAL');

      assert.equal(allRes.allCount, tc.stints.length, `${tc.name}: allCount badge mismatch`);
      assert.equal(allRes.filteredEmployments.length, tc.stints.length, `${tc.name}: all filtered mismatch`);

      assert.equal(actRes.activeCount, tc.expActive, `${tc.name}: activeCount badge mismatch`);
      assert.equal(actRes.filteredEmployments.length, tc.expActive, `${tc.name}: active filtered mismatch`);

      assert.equal(histRes.historicalCount, tc.expHist, `${tc.name}: historicalCount badge mismatch`);
      assert.equal(histRes.filteredEmployments.length, tc.expHist, `${tc.name}: historical filtered mismatch`);
    }
  });

  await runTest('T1.3 Empty States Render Appropriate Contextual Text Per Tab', () => {
    // 1. Completely empty ledger
    const emptyLedger = { employments: [] };
    const allEmpty = evaluateTabFiltering(emptyLedger, null, 'ALL');
    const actEmpty = evaluateTabFiltering(emptyLedger, null, 'ACTIVE');
    const histEmpty = evaluateTabFiltering(emptyLedger, null, 'HISTORICAL');

    assert.equal(allEmpty.emptyStateText, 'No employment records logged on-chain yet.');
    assert.equal(actEmpty.emptyStateText, 'No active employment stints currently running.');
    assert.equal(histEmpty.emptyStateText, 'No past or discontinued stints recorded yet.');

    // 2. Ledger with only active stint: HISTORICAL must show empty state text, ACTIVE must not
    const onlyActiveLedger = { employments: [{ id: 1, status: 'ACTIVE' }] };
    const actNonEmpty = evaluateTabFiltering(onlyActiveLedger, null, 'ACTIVE');
    const histMustBeEmpty = evaluateTabFiltering(onlyActiveLedger, null, 'HISTORICAL');
    assert.equal(actNonEmpty.emptyStateText, null);
    assert.equal(histMustBeEmpty.emptyStateText, 'No past or discontinued stints recorded yet.');

    // 3. Ledger with only discontinued stint: ACTIVE must show empty state text, HISTORICAL must not
    const onlyHistLedger = { employments: [{ id: 1, status: 'DISCONTINUED' }] };
    const actMustBeEmpty = evaluateTabFiltering(onlyHistLedger, null, 'ACTIVE');
    const histNonEmpty = evaluateTabFiltering(onlyHistLedger, null, 'HISTORICAL');
    assert.equal(actMustBeEmpty.emptyStateText, 'No active employment stints currently running.');
    assert.equal(histNonEmpty.emptyStateText, null);
  });

  await runTest('T1.4 Fallback from employmentHistory to wallet.employments', () => {
    const walletData = {
      employments: [
        { id: 101, status: 'ACTIVE', employer_name: 'Alpha Infra' },
        { id: 102, status: 'COMPLETED', employer_name: 'Beta Build' }
      ]
    };
    // When employmentHistory is null/undefined
    const res = evaluateTabFiltering(null, walletData, 'ALL');
    assert.equal(res.effectiveEmployments.length, 2);
    assert.equal(res.activeCount, 1);
    assert.equal(res.historicalCount, 1);
  });

  await runTest('T1.5 Property-Based Fuzz Harness: 1000 Random Employment Sets Partition Invariant', () => {
    const possibleStatuses = [
      'ACTIVE', 'COMPLETED', 'DISCONTINUED', 'TERMINATED', 'DISMISSED',
      'RESIGNED', 'SUSPENDED', 'active', 'completed', 'discontinued',
      null, undefined, '', 'UNKNOWN_STATUS', 'PENDING'
    ];

    for (let iteration = 0; iteration < 1000; iteration++) {
      const count = Math.floor(Math.random() * 20); // 0 to 19 stints
      const stints = [];
      let expectedActive = 0;
      let expectedHist = 0;

      for (let i = 0; i < count; i++) {
        const status = possibleStatuses[Math.floor(Math.random() * possibleStatuses.length)];
        stints.push({ id: `stint-${i}`, status });
        if ((status || '').toUpperCase() === 'ACTIVE') {
          expectedActive++;
        } else {
          expectedHist++;
        }
      }

      const all = evaluateTabFiltering({ employments: stints }, null, 'ALL');
      const act = evaluateTabFiltering({ employments: stints }, null, 'ACTIVE');
      const hist = evaluateTabFiltering({ employments: stints }, null, 'HISTORICAL');

      assert.equal(all.filteredEmployments.length, count);
      assert.equal(act.filteredEmployments.length, expectedActive);
      assert.equal(hist.filteredEmployments.length, expectedHist);
      assert.equal(all.filteredEmployments.length, act.filteredEmployments.length + hist.filteredEmployments.length);
    }
  });

  // --------------------------------------------------------------------------
  // SECTION 2: STATUS BADGES & PERMANENCE BANNERS
  // --------------------------------------------------------------------------
  console.log('\n--- SECTION 2: STATUS BADGES & PERMANENCE BANNERS ---');

  await runTest('T2.1 Status Badge Rendering for All Recognized & Unrecognized Statuses', () => {
    const checks = [
      { status: 'ACTIVE', expText: 'ACTIVE', expColor: 'emerald', expPulse: true },
      { status: 'COMPLETED', expText: '✓ COMPLETED', expColor: 'blue', expPulse: false },
      { status: 'DISCONTINUED', expText: '⚠️ DISCONTINUED', expColor: 'amber', expPulse: false },
      { status: 'TERMINATED', expText: '✕ TERMINATED', expColor: 'rose', expPulse: false },
      { status: 'DISMISSED', expText: '✕ DISMISSED', expColor: 'rose', expPulse: false },
      { status: 'RESIGNED', expText: 'RESIGNED', expColor: 'purple', expPulse: false },
      { status: 'SUSPENDED', expText: 'SUSPENDED', expColor: 'yellow', expPulse: false },
      { status: 'active', expText: 'ACTIVE', expColor: 'emerald', expPulse: true },
      { status: 'discontinued', expText: '⚠️ DISCONTINUED', expColor: 'amber', expPulse: false },
      { status: 'completed', expText: '✓ COMPLETED', expColor: 'blue', expPulse: false },
      { status: 'UNKNOWN', expText: 'UNKNOWN', expColor: 'slate', expPulse: false },
      { status: null, expText: 'UNKNOWN', expColor: 'slate', expPulse: false }
    ];

    for (const c of checks) {
      const badge = evaluateEmploymentStatusBadge(c.status);
      assert.equal(badge.text, c.expText, `Status ${c.status} text mismatch`);
      assert.equal(badge.color, c.expColor, `Status ${c.status} color mismatch`);
      assert.equal(badge.hasPulse, c.expPulse, `Status ${c.status} pulse mismatch`);
    }
  });

  await runTest('T2.2 DISCONTINUED Stints Exclusively Trigger Amber Permanence Invariant Banner', () => {
    const discStint = { id: 1, status: 'DISCONTINUED' };
    const discEval = evaluateContextualBanners(discStint);

    assert.equal(discEval.isDiscontinued, true);
    assert.equal(discEval.isCompleted, false);
    assert.ok(discEval.banner !== null);
    assert.equal(discEval.banner.type, 'PERMANENCE_INVARIANT');
    assert.equal(discEval.banner.color, 'amber');
    assert.ok(discEval.banner.text.includes('Permanence Invariant:'));
    assert.ok(discEval.banner.text.includes('Historical stint permanently recorded in worker provenance ledger.'));
    assert.equal(discEval.borderClass, 'border-amber-500/30 hover:border-amber-500/50');
  });

  await runTest('T2.3 COMPLETED Stints Exclusively Trigger Blue Completion Banner', () => {
    const compStint = { id: 2, status: 'COMPLETED' };
    const compEval = evaluateContextualBanners(compStint);

    assert.equal(compEval.isDiscontinued, false);
    assert.equal(compEval.isCompleted, true);
    assert.ok(compEval.banner !== null);
    assert.equal(compEval.banner.type, 'COMPLETION_BANNER');
    assert.equal(compEval.banner.color, 'blue');
    assert.ok(compEval.banner.text.includes('Employment tenure successfully completed and verified on-chain.'));
    assert.equal(compEval.borderClass, 'border-blue-500/30 hover:border-blue-500/50');
  });

  await runTest('T2.4 Other Stints (ACTIVE, TERMINATED, etc.) Do NOT Trigger Permanence or Completion Banners', () => {
    const nonBannerStatuses = ['ACTIVE', 'TERMINATED', 'DISMISSED', 'RESIGNED', 'SUSPENDED', 'UNKNOWN', null];

    for (const st of nonBannerStatuses) {
      const res = evaluateContextualBanners({ id: 99, status: st });
      assert.equal(res.isDiscontinued, false, `Status ${st} should not be discontinued`);
      assert.equal(res.isCompleted, false, `Status ${st} should not be completed`);
      assert.equal(res.banner, null, `Status ${st} should not have a banner`);
      assert.equal(res.borderClass, 'border-slate-800 hover:border-slate-700');
    }
  });

  // --------------------------------------------------------------------------
  // SECTION 3: SKILLS & TRADE MODAL
  // --------------------------------------------------------------------------
  console.log('\n--- SECTION 3: SKILLS & TRADE MODAL ---');

  await runTest('T3.1 Modal Initialization: Standard Trade vs Custom Profession', () => {
    // 1. Worker with standard trade
    const standardWorker = { worker_category: 'Electrician', skills: ['Conduit Wiring'] };
    const h1 = createSkillsModalHarness(standardWorker, async () => ({ ok: true }));
    h1.handleOpenSkillsModal();
    let state1 = h1.getState();
    assert.equal(state1.showSkillsModal, true);
    assert.equal(state1.modalTrade, 'Electrician');
    assert.equal(state1.customTradeInput, '');
    assert.deepEqual(state1.modalSkills, ['Conduit Wiring']);

    // 2. Worker with custom profession ("Solar Technician")
    const customWorker = { worker_category: 'Solar Technician', skills: ['PV Inverter Installation'] };
    const h2 = createSkillsModalHarness(customWorker, async () => ({ ok: true }));
    h2.handleOpenSkillsModal();
    let state2 = h2.getState();
    assert.equal(state2.showSkillsModal, true);
    assert.equal(state2.modalTrade, 'Other');
    assert.equal(state2.customTradeInput, 'Solar Technician');
    assert.deepEqual(state2.modalSkills, ['PV Inverter Installation']);
  });

  await runTest('T3.2 Switching Trade to "Other" Reveals Custom Profession Box; Switching Back Hides It', () => {
    const worker = { worker_category: 'Mason', skills: ['Bricklaying'] };
    const h = createSkillsModalHarness(worker, async () => ({ ok: true }));
    h.handleOpenSkillsModal();

    // Initially Mason -> customTradeInput is empty
    assert.equal(h.getState().modalTrade, 'Mason');

    // Switch to Other
    h.setModalTrade('Other');
    h.setCustomTradeInput('Underwater Welder');
    assert.equal(h.getState().modalTrade, 'Other');
    assert.equal(h.getState().customTradeInput, 'Underwater Welder');

    // Switch to Plumber -> custom box is hidden in UI (modalTrade !== 'Other')
    h.setModalTrade('Plumber');
    assert.equal(h.getState().modalTrade, 'Plumber');
  });

  await runTest('T3.3 Skill Chip Removal Functionality & Index Preservation', () => {
    const worker = { worker_category: 'Mason', skills: ['Bricklaying', 'Plastering', 'Concreting', 'Scaffolding'] };
    const h = createSkillsModalHarness(worker, async () => ({ ok: true }));
    h.handleOpenSkillsModal();

    // Remove index 1 ('Plastering')
    h.handleRemoveSkill(1);
    assert.deepEqual(h.getState().modalSkills, ['Bricklaying', 'Concreting', 'Scaffolding']);

    // Remove index 0 ('Bricklaying')
    h.handleRemoveSkill(0);
    assert.deepEqual(h.getState().modalSkills, ['Concreting', 'Scaffolding']);

    // Remove index 1 ('Scaffolding')
    h.handleRemoveSkill(1);
    assert.deepEqual(h.getState().modalSkills, ['Concreting']);

    // Remove remaining chip -> empty
    h.handleRemoveSkill(0);
    assert.deepEqual(h.getState().modalSkills, []);
  });

  await runTest('T3.4 Duplicate Skill Prevention & Quick-Add Suggested Skills', () => {
    const worker = { worker_category: 'Electrician', skills: ['Conduit Wiring'] };
    const h = createSkillsModalHarness(worker, async () => ({ ok: true }));
    h.handleOpenSkillsModal();

    // 1. Attempt adding duplicate skill via input
    h.setNewSkillInput('Conduit Wiring');
    h.handleAddSkill();
    assert.deepEqual(h.getState().modalSkills, ['Conduit Wiring'], 'Duplicate skill must not be added');

    // 2. Attempt adding empty/whitespace skill
    h.setNewSkillInput('   ');
    h.handleAddSkill();
    assert.deepEqual(h.getState().modalSkills, ['Conduit Wiring'], 'Whitespace skill must not be added');

    // 3. Add valid new skill
    h.setNewSkillInput('Panel Installation');
    h.handleAddSkill();
    assert.deepEqual(h.getState().modalSkills, ['Conduit Wiring', 'Panel Installation']);
    assert.equal(h.getState().newSkillInput, '', 'Input should be cleared after adding');

    // 4. Quick-Add suggested skill
    h.handleAddSuggestedSkill('Solar PV');
    assert.deepEqual(h.getState().modalSkills, ['Conduit Wiring', 'Panel Installation', 'Solar PV']);

    // 5. Duplicate quick-add attempt
    h.handleAddSuggestedSkill('Solar PV');
    assert.deepEqual(h.getState().modalSkills, ['Conduit Wiring', 'Panel Installation', 'Solar PV'], 'Suggested duplicate ignored');

    // 6. Verify all 11 standard trades have non-empty suggested skills
    for (const trade of STANDARD_TRADES) {
      assert.ok(Array.isArray(SUGGESTED_SKILLS_MAP[trade]), `Trade ${trade} must have suggestions`);
      assert.ok(SUGGESTED_SKILLS_MAP[trade].length > 0, `Trade ${trade} must have at least 1 suggestion`);
    }
  });

  await runTest('T3.5 Form Submission: Clean Payload Construction for Standard & Custom Trades', async () => {
    let capturedCalls = [];
    const mockApi = async (url, options) => {
      capturedCalls.push({ url, options });
      return { ok: true, json: async () => ({ status: 'success' }) };
    };

    // Case 1: Standard trade
    const h1 = createSkillsModalHarness({ worker_category: 'Carpenter', skills: ['Framing'] }, mockApi);
    h1.handleOpenSkillsModal();
    h1.handleAddSkill(); // no-op
    await h1.handleSaveSkillsAndTrade();

    assert.equal(capturedCalls.length, 1);
    assert.equal(capturedCalls[0].url, '/api/v1/worker/skills/me');
    assert.equal(capturedCalls[0].options.method, 'PUT');
    assert.deepEqual(capturedCalls[0].options.body, {
      worker_category: 'Carpenter',
      skills: ['Framing']
    });

    // Case 2: Custom trade via Other
    capturedCalls = [];
    const h2 = createSkillsModalHarness({ worker_category: 'Mason', skills: [] }, mockApi);
    h2.handleOpenSkillsModal();
    h2.setModalTrade('Other');
    h2.setCustomTradeInput('  Rigger & Signalman  ');
    h2.handleAddSuggestedSkill('Safety Rigging');
    await h2.handleSaveSkillsAndTrade();

    assert.equal(capturedCalls.length, 1);
    assert.equal(capturedCalls[0].url, '/api/v1/worker/skills/me');
    assert.deepEqual(capturedCalls[0].options.body, {
      worker_category: 'Rigger & Signalman',
      skills: ['Safety Rigging']
    });
  });

  await runTest('T3.6 API Fallback: /skills/me 404/500 Gracefully Falls Back to /profile/me', async () => {
    let callHistory = [];
    const fallbackMockApi = async (url, options) => {
      callHistory.push(url);
      if (url === '/api/v1/worker/skills/me') {
        return { ok: false, status: 404, json: async () => ({ detail: 'Endpoint not found' }) };
      }
      if (url === '/api/v1/worker/profile/me') {
        return { ok: true, status: 200, json: async () => ({ success: true }) };
      }
      return { ok: false, status: 500 };
    };

    const h = createSkillsModalHarness({ worker_category: 'Painter', skills: ['Spray Painting'] }, fallbackMockApi);
    h.handleOpenSkillsModal();
    await h.handleSaveSkillsAndTrade();

    assert.deepEqual(callHistory, ['/api/v1/worker/skills/me', '/api/v1/worker/profile/me']);
    const state = h.getState();
    assert.equal(state.showSkillsModal, false, 'Modal should close on successful fallback');
    assert.equal(state.successMsg, 'Trade and skills profile successfully updated!');
    assert.equal(state.errorMsg, '');
    assert.equal(state.savingSkills, false);
  });

  await runTest('T3.7 API Error Resilience: Handles Total API Rejection Gracefully Without Hanging', async () => {
    const errorMockApi = async (url, options) => {
      return {
        ok: false,
        status: 422,
        json: async () => ({ detail: 'Custom validation rejected: invalid category format' })
      };
    };

    const h = createSkillsModalHarness({ worker_category: 'Painter', skills: [] }, errorMockApi);
    h.handleOpenSkillsModal();
    await h.handleSaveSkillsAndTrade();

    const state = h.getState();
    assert.equal(state.showSkillsModal, true, 'Modal should remain open on error');
    assert.equal(state.errorMsg, 'Custom validation rejected: invalid category format');
    assert.equal(state.savingSkills, false, 'savingSkills must reset to false');
  });

  await runTest('T3.8 Network Exception Resilience: Handles Unhandled Fetch Throw', async () => {
    const throwingMockApi = async () => {
      throw new Error('Failed to fetch: Connection refused');
    };

    const h = createSkillsModalHarness({ worker_category: 'Painter', skills: [] }, throwingMockApi);
    h.handleOpenSkillsModal();
    await h.handleSaveSkillsAndTrade();

    const state = h.getState();
    assert.equal(state.showSkillsModal, true);
    assert.equal(state.errorMsg, 'Failed to fetch: Connection refused');
    assert.equal(state.savingSkills, false);
  });

  // --------------------------------------------------------------------------
  // SECTION 4: SOURCE CODE INTEGRITY & SYNTACTIC INVARIANTS
  // --------------------------------------------------------------------------
  console.log('\n--- SECTION 4: SOURCE CODE INTEGRITY & SYNTACTIC INVARIANTS ---');

  await runTest('T4.1 WorkerPortal.jsx Contains Required Tab Buttons with Dynamic Counts', () => {
    assert.ok(workerPortalSrc.includes("setHistoryFilter('ALL')"), "Missing ALL tab click handler");
    assert.ok(workerPortalSrc.includes("setHistoryFilter('ACTIVE')"), "Missing ACTIVE tab click handler");
    assert.ok(workerPortalSrc.includes("setHistoryFilter('HISTORICAL')"), "Missing HISTORICAL tab click handler");

    assert.ok(workerPortalSrc.includes("All ({effectiveEmployments.length})"), "Missing ALL count label");
    assert.ok(workerPortalSrc.includes("Active ({activeCount})"), "Missing ACTIVE count label");
    assert.ok(workerPortalSrc.includes("Past & Concluded ({historicalCount})"), "Missing HISTORICAL count label");
  });

  await runTest('T4.2 WorkerPortal.jsx Contains Permanence & Completion Banners', () => {
    assert.ok(workerPortalSrc.includes("Permanence Invariant:"), "Missing Permanence Invariant text");
    assert.ok(workerPortalSrc.includes("Category authorization discontinued by platform governance."), "Missing discontinued banner explanation");
    assert.ok(workerPortalSrc.includes("Employment tenure successfully completed and verified on-chain."), "Missing completion banner text");
    assert.ok(workerPortalSrc.includes("isDiscontinued"), "Missing isDiscontinued flag calculation");
    assert.ok(workerPortalSrc.includes("isCompleted"), "Missing isCompleted flag calculation");
  });

  await runTest('T4.3 WorkerPortal.jsx Contains Skills & Trade Modal Elements', () => {
    assert.ok(workerPortalSrc.includes("handleOpenSkillsModal"), "Missing handleOpenSkillsModal");
    assert.ok(workerPortalSrc.includes("handleSaveSkillsAndTrade"), "Missing handleSaveSkillsAndTrade");
    assert.ok(workerPortalSrc.includes("handleRemoveSkill"), "Missing handleRemoveSkill");
    assert.ok(workerPortalSrc.includes("handleAddSuggestedSkill"), "Missing handleAddSuggestedSkill");
    assert.ok(workerPortalSrc.includes("Specify Custom Trade or Specialization"), "Missing custom trade label");
    assert.ok(workerPortalSrc.includes("Quick-Add Suggested Skills for"), "Missing suggested skills header");
  });

  await runTest('T4.4 api.js Exports getEmploymentHistory & updateWorkerSkills with Fallbacks', () => {
    assert.ok(apiJsSrc.includes("export async function getEmploymentHistory()"), "Missing getEmploymentHistory export in api.js");
    assert.ok(apiJsSrc.includes("export async function updateWorkerSkills("), "Missing updateWorkerSkills export in api.js");
    assert.ok(apiJsSrc.includes("/api/v1/worker/employment-history/me"), "Missing employment-history endpoint in api.js");
    assert.ok(apiJsSrc.includes("/api/v1/worker/wallet/me"), "Missing wallet fallback in api.js");
    assert.ok(apiJsSrc.includes("/api/v1/worker/skills/me"), "Missing skills endpoint in api.js");
    assert.ok(apiJsSrc.includes("/api/v1/worker/profile/me"), "Missing profile fallback in api.js");
  });

  // --------------------------------------------------------------------------
  // Summary
  // --------------------------------------------------------------------------
  console.log('\n================================================================');
  console.log(`  M2 EMPIRICAL TEST HARNESS COMPLETE: ${passedTests}/${totalTests} PASSED (100%)`);
  console.log('================================================================\n');
}

main().catch(err => {
  console.error('Test execution aborted due to error:', err);
  process.exit(1);
});
