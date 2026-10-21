const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");
const crypto = require("crypto");

describe("PASSKHADAM Lifecycle & Invariants Adversarial Stress Test Suite (Challenger_2)", function () {
  let admin, issuer, secondIssuer, employer, unauthorizedEmployer, govOfficer, unauthorizedGovOfficer, worker1, worker2, attacker;
  let identityRegistry, credRegistry, orgRegistry, employmentRegistry, welfareRegistry;

  const didWorker1 = "did:passkhadam:worker:1111222233334444";
  const didWorker2 = "did:passkhadam:worker:5555666677778888";
  const sampleCredHash1 = ethers.keccak256(ethers.toUtf8Bytes("EncryptedCredentialPayload_Worker1"));
  const sampleCredHash2 = ethers.keccak256(ethers.toUtf8Bytes("EncryptedCredentialPayload_Worker2"));
  const sampleCid1 = "QmWorker1IpfsCredentialHashMultihashBase58111";
  const sampleCid2 = "QmWorker2IpfsCredentialHashMultihashBase58222";

  beforeEach(async function () {
    [
      admin,
      issuer,
      secondIssuer,
      employer,
      unauthorizedEmployer,
      govOfficer,
      unauthorizedGovOfficer,
      worker1,
      worker2,
      attacker
    ] = await ethers.getSigners();

    // 1. WorkerIdentityRegistry
    const IdentityFactory = await ethers.getContractFactory("WorkerIdentityRegistry");
    identityRegistry = await IdentityFactory.deploy();
    await identityRegistry.waitForDeployment();
    await identityRegistry.setIssuer(issuer.address, true);
    await identityRegistry.setIssuer(secondIssuer.address, true);

    // 2. CredentialRegistry
    const CredFactory = await ethers.getContractFactory("CredentialRegistry");
    credRegistry = await CredFactory.deploy();
    await credRegistry.waitForDeployment();
    await credRegistry.setIssuer(issuer.address, true);

    // 3. OrganizationRegistry
    const OrgFactory = await ethers.getContractFactory("OrganizationRegistry");
    orgRegistry = await OrgFactory.deploy();
    await orgRegistry.waitForDeployment();

    // 4. EmploymentRegistry
    const EmpFactory = await ethers.getContractFactory("EmploymentRegistry");
    employmentRegistry = await EmpFactory.deploy(await orgRegistry.getAddress());
    await employmentRegistry.waitForDeployment();

    // 5. WelfareSchemeRegistry
    const WelfareFactory = await ethers.getContractFactory("WelfareSchemeRegistry");
    welfareRegistry = await WelfareFactory.deploy(await orgRegistry.getAddress());
    await welfareRegistry.waitForDeployment();

    // Setup base authorized employer
    await orgRegistry.connect(employer).registerOrganization(
      "BuildCorp Infrastructure Ltd",
      "CIN-BC-987654",
      "KA",
      0, // EMPLOYER
      ["Mason", "Electrician"]
    );
    await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 1, "Approved by Admin"); // APPROVED

    // Setup unauthorized employer (remains PENDING)
    await orgRegistry.connect(unauthorizedEmployer).registerOrganization(
      "Shadow Shady Corp",
      "CIN-SHADOW-001",
      "DL",
      0,
      ["Mason"]
    );

    // Setup authorized government officer
    await orgRegistry.connect(govOfficer).registerOrganization(
      "Directorate of Migrant Welfare",
      "GOV-MH-WELFARE-42",
      "MH",
      1, // GOVERNMENT
      []
    );
    await orgRegistry.connect(admin).setOrganizationStatus(govOfficer.address, 1, "Gov Officer Approved");

    // Setup worker1 identity
    await identityRegistry.connect(issuer).registerWorker(didWorker1, sampleCredHash1, sampleCid1);
  });

  describe("1. Worker Identity Registry & Duplicate DID Attacks", function () {
    it("should prevent duplicate registration by the same issuer", async function () {
      await expect(
        identityRegistry.connect(issuer).registerWorker(didWorker1, sampleCredHash1, sampleCid1)
      ).to.be.revertedWith("Worker already registered");
    });

    it("should prevent duplicate registration by a DIFFERENT authorized issuer (sybil resistance)", async function () {
      await expect(
        identityRegistry.connect(secondIssuer).registerWorker(didWorker1, sampleCredHash2, sampleCid2)
      ).to.be.revertedWith("Worker already registered");
    });

    it("should prevent unauthorized caller from registering worker identities", async function () {
      await expect(
        identityRegistry.connect(attacker).registerWorker(didWorker2, sampleCredHash2, sampleCid2)
      ).to.be.revertedWith("WorkerIdentityRegistry: Only authorized issuer");
    });

    it("should reject registration with empty/zero credential hash", async function () {
      await expect(
        identityRegistry.connect(issuer).registerWorker(didWorker2, ethers.ZeroHash, sampleCid2)
      ).to.be.revertedWith("Invalid credential hash");
    });

    it("should reject re-registration even after worker identity is REVOKED (tamper/overwrite prevention)", async function () {
      await identityRegistry.connect(issuer).revokeWorker(didWorker1, "Reported compromise");
      expect(await identityRegistry.isWorkerValid(didWorker1)).to.be.false;

      // Attacker/issuer attempts to re-register the same DID with a new credential hash
      await expect(
        identityRegistry.connect(issuer).registerWorker(didWorker1, sampleCredHash2, sampleCid2)
      ).to.be.revertedWith("Worker already registered");
    });

    it("should disallow non-admin from reactivating revoked worker", async function () {
      await identityRegistry.connect(issuer).revokeWorker(didWorker1, "Under investigation");
      await expect(
        identityRegistry.connect(attacker).reactivateWorker(didWorker1)
      ).to.be.revertedWith("WorkerIdentityRegistry: Only admin authorized");

      // Admin reactivation succeeds
      await identityRegistry.connect(admin).reactivateWorker(didWorker1);
      expect(await identityRegistry.isWorkerValid(didWorker1)).to.be.true;
    });
  });

  describe("2. Organization Permissions & Scoped Authority Invariants", function () {
    it("should reject employment creation by unapproved / pending employer", async function () {
      await expect(
        employmentRegistry.connect(unauthorizedEmployer).createEmployment(
          didWorker1,
          "Mason",
          "Skilled",
          "Contract",
          "Bricklayer",
          "Delhi",
          0
        )
      ).to.be.revertedWith("Employer not approved");
    });

    it("should reject employment creation with unauthorized category", async function () {
      // Employer is approved for ["Mason", "Electrician"], NOT "Plumber"
      await expect(
        employmentRegistry.connect(employer).createEmployment(
          didWorker1,
          "Plumber",
          "Skilled",
          "Contract",
          "Pipe fitter",
          "Bengaluru",
          0
        )
      ).to.be.revertedWith("Category not authorized for employer");
    });

    it("should reject employment creation with arbitrary / injection category string", async function () {
      await expect(
        employmentRegistry.connect(employer).createEmployment(
          didWorker1,
          "Mason'; DROP TABLE employments;--",
          "Skilled",
          "Contract",
          "Attacker",
          "Bengaluru",
          0
        )
      ).to.be.revertedWith("Category not authorized for employer");
    });

    it("should reject employment creation with unauthorized employment level", async function () {
      // Default approved levels: Skilled, Semi-Skilled, Unskilled
      await expect(
        employmentRegistry.connect(employer).createEmployment(
          didWorker1,
          "Mason",
          "MasterExecutiveCraftsman",
          "Contract",
          "Lead Mason",
          "Bengaluru",
          0
        )
      ).to.be.revertedWith("Level not authorized for employer");
    });

    it("should reject employment creation with unauthorized nature of employment", async function () {
      // Default approved natures: Contract, Permanent, Project-Based
      await expect(
        employmentRegistry.connect(employer).createEmployment(
          didWorker1,
          "Mason",
          "Skilled",
          "InformalGigEconomy",
          "Lead Mason",
          "Bengaluru",
          0
        )
      ).to.be.revertedWith("Nature of employment not authorized");
    });

    it("should dynamically allow category only after Admin grants explicit authorization", async function () {
      // Initially "Plumber" is rejected
      await expect(
        employmentRegistry.connect(employer).createEmployment(
          didWorker1,
          "Plumber",
          "Skilled",
          "Contract",
          "Sanitary Specialist",
          "Bengaluru",
          0
        )
      ).to.be.revertedWith("Category not authorized for employer");

      // Non-admin cannot authorize category
      await expect(
        orgRegistry.connect(attacker).authorizeCategory(employer.address, "Plumber")
      ).to.be.revertedWith("OrganizationRegistry: Only platform admin");

      // Admin authorizes category
      await orgRegistry.connect(admin).authorizeCategory(employer.address, "Plumber");
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Plumber")).to.be.true;

      // Now createEmployment succeeds
      const tx = await employmentRegistry.connect(employer).createEmployment(
        didWorker1,
        "Plumber",
        "Skilled",
        "Contract",
        "Sanitary Specialist",
        "Bengaluru",
        0
      );
      await expect(tx).to.emit(employmentRegistry, "EmploymentCreated");
    });

    it("should instantly invalidate employer upon status change to SUSPENDED", async function () {
      // Admin suspends employer
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 3, "Compliance breach"); // 3 = SUSPENDED
      expect(await orgRegistry.isOrganizationApproved(employer.address)).to.be.false;

      await expect(
        employmentRegistry.connect(employer).createEmployment(
          didWorker1,
          "Mason",
          "Skilled",
          "Contract",
          "Mason",
          "Bengaluru",
          0
        )
      ).to.be.revertedWith("Employer not approved");
    });

    it("should reject employment creation after Admin revokes an authorized category", async function () {
      // Employer is approved with "Mason" and "Electrician"
      // Admin revokes "Electrician"
      await expect(orgRegistry.connect(admin).revokeCategory(employer.address, "Electrician"))
        .to.emit(orgRegistry, "CategoryRevoked")
        .withArgs(employer.address, "Electrician");

      // Employment creation with revoked category must revert
      await expect(
        employmentRegistry.connect(employer).createEmployment(
          didWorker1,
          "Electrician",
          "Skilled",
          "Contract",
          "Wireman",
          "Bengaluru",
          0
        )
      ).to.be.revertedWith("Category not authorized for employer");

      // Active authorized category "Mason" still succeeds
      const tx = await employmentRegistry.connect(employer).createEmployment(
        didWorker1,
        "Mason",
        "Skilled",
        "Contract",
        "Bricklayer",
        "Bengaluru",
        0
      );
      await expect(tx).to.emit(employmentRegistry, "EmploymentCreated");
    });
  });

  describe("3. Employment Registry Lifecycle & History Preservation Invariants", function () {
    let empId;

    beforeEach(async function () {
      const tx = await employmentRegistry.connect(employer).createEmployment(
        didWorker1,
        "Mason",
        "Skilled",
        "Contract",
        "Senior Bricklayer",
        "Bengaluru Site A",
        0
      );
      const receipt = await tx.wait();
      empId = 1;
    });

    it("should preserve original record intact when transitioned to DISMISSED", async function () {
      const recordBefore = await employmentRegistry.employments(empId);
      expect(recordBefore.status).to.equal(0); // ACTIVE
      expect(recordBefore.category).to.equal("Mason");
      expect(recordBefore.level).to.equal("Skilled");
      expect(recordBefore.employerAddress).to.equal(employer.address);

      // Transition to DISMISSED (status = 5)
      await employmentRegistry.connect(employer).updateEmploymentStatus(empId, 5, "Disciplinary dismissal: misconduct");

      const recordAfter = await employmentRegistry.employments(empId);
      expect(recordAfter.status).to.equal(5); // DISMISSED
      expect(recordAfter.statusReason).to.equal("Disciplinary dismissal: misconduct");
      expect(recordAfter.endDate).to.be.gt(0);

      // Invariant: Core employment attributes MUST NOT be erased or reset
      expect(recordAfter.id).to.equal(empId);
      expect(recordAfter.category).to.equal("Mason");
      expect(recordAfter.level).to.equal("Skilled");
      expect(recordAfter.natureOfEmployment).to.equal("Contract");
      expect(recordAfter.jobRole).to.equal("Senior Bricklayer");
      expect(recordAfter.workLocation).to.equal("Bengaluru Site A");
      expect(recordAfter.employerAddress).to.equal(employer.address);

      // Event history must be append-only with 2 events
      const eventCount = await employmentRegistry.getEmploymentEventsCount(empId);
      expect(eventCount).to.equal(2);
    });

    it("should preserve history across multi-hop lifecycle: ACTIVE -> SUSPENDED -> DISMISSED -> COMPLETED", async function () {
      // 1. ACTIVE -> SUSPENDED (4)
      await employmentRegistry.connect(employer).updateEmploymentStatus(empId, 4, "Under investigation");
      // 2. SUSPENDED -> DISMISSED (5)
      await employmentRegistry.connect(employer).updateEmploymentStatus(empId, 5, "Investigation concluded - dismissed");
      // 3. DISMISSED -> COMPLETED (1) (e.g. settlement/closure)
      await employmentRegistry.connect(employer).updateEmploymentStatus(empId, 1, "Final settlement completed");

      const eventCount = await employmentRegistry.getEmploymentEventsCount(empId);
      expect(eventCount).to.equal(4); // 1 initial + 3 transitions

      const record = await employmentRegistry.employments(empId);
      expect(record.status).to.equal(1); // COMPLETED
      expect(record.statusReason).to.equal("Final settlement completed");

      // Verify worker's employment list still retains this stint ID
      const workerEmps = await employmentRegistry.getWorkerEmploymentIds(didWorker1);
      expect(workerEmps.length).to.equal(1);
      expect(workerEmps[0]).to.equal(empId);
    });

    it("should prevent unauthorized entity from modifying employment status", async function () {
      // Attacker tries to dismiss the worker
      await expect(
        employmentRegistry.connect(attacker).updateEmploymentStatus(empId, 5, "Malicious dismissal")
      ).to.be.revertedWith("EmploymentRegistry: Only employer or admin");

      // Unauthorized employer tries to dismiss
      await expect(
        employmentRegistry.connect(unauthorizedEmployer).updateEmploymentStatus(empId, 5, "Fake employer")
      ).to.be.revertedWith("EmploymentRegistry: Only employer or admin");
    });

    it("should allow admin override to update employment status", async function () {
      await expect(
        employmentRegistry.connect(admin).updateEmploymentStatus(empId, 2, "Admin regulatory termination") // 2 = TERMINATED
      ).to.emit(employmentRegistry, "EmploymentStatusUpdated");

      const record = await employmentRegistry.employments(empId);
      expect(record.status).to.equal(2);
    });
  });

  describe("4. Welfare Scheme Dynamic Cooldown & Deterministic SHA-256 Claim Tracking", function () {
    let scheme1Id, scheme2Id;
    const cooldown30Days = 30 * 24 * 60 * 60; // 2,592,000 seconds

    function computeSha256ClaimId(claimId, workerDid, schemeId, govOfficerAddr, officerState, timestamp) {
      const canonicalPayload = `${claimId}:${workerDid}:${schemeId}:${govOfficerAddr}:${officerState}:${timestamp}`;
      return crypto.createHash("sha256").update(canonicalPayload, "utf8").digest("hex");
    }

    beforeEach(async function () {
      // Scheme 1: 30-day dynamic cooldown, 5000 INR
      const tx1 = await welfareRegistry.connect(admin).registerScheme(
        "Interstate Migrant Worker Relief",
        "Quarterly cash relief for registered migrant workers",
        5000,
        cooldown30Days,
        true
      );
      await tx1.wait();
      scheme1Id = 1;

      // Scheme 2: 7-day cooldown, 2000 INR
      const tx2 = await welfareRegistry.connect(admin).registerScheme(
        "Emergency Monsoon Relief",
        "Immediate emergency grant for migrant laborers",
        2000,
        7 * 24 * 60 * 60,
        true
      );
      await tx2.wait();
      scheme2Id = 2;
    });

    it("should reject benefit claim if government authority is not approved on-chain", async function () {
      const claimSha = computeSha256ClaimId(1, didWorker1, scheme1Id, unauthorizedGovOfficer.address, "DL", 1000);
      await expect(
        welfareRegistry.connect(unauthorizedGovOfficer).recordClaim(scheme1Id, didWorker1, "DL", claimSha)
      ).to.be.revertedWith("Government authority not approved on-chain");
    });

    it("should record claim with deterministic SHA-256 ID and store exact on-chain record", async function () {
      const now = await time.latest();
      const expectedSha256 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "MH", now);

      const tx = await welfareRegistry.connect(govOfficer).recordClaim(
        scheme1Id,
        didWorker1,
        "MH",
        expectedSha256
      );
      await expect(tx).to.emit(welfareRegistry, "BenefitClaimed");

      const claim = await welfareRegistry.claims(1);
      expect(claim.claimId).to.equal(1);
      expect(claim.schemeId).to.equal(scheme1Id);
      expect(claim.sha256ClaimId).to.equal(expectedSha256);
      expect(claim.govOfficer).to.equal(govOfficer.address);
      expect(claim.officerState).to.equal("MH");
      expect(claim.amount).to.equal(5000);
      expect(claim.isDisbursed).to.be.true;

      // Verify SHA-256 determinism: recomputing hash with same inputs produces identical string
      const recomputedSha256 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "MH", now);
      expect(claim.sha256ClaimId).to.equal(recomputedSha256);

      // Verify avalanche effect: modifying even 1 character alters hash entirely
      const perturbedSha256 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "KA", now);
      expect(claim.sha256ClaimId).to.not.equal(perturbedSha256);
    });

    it("should prevent duplicate claim at t=0 (immediate repeat claim)", async function () {
      const now = await time.latest();
      const claimSha1 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "MH", now);

      await welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker1, "MH", claimSha1);

      // Attempt immediate duplicate claim
      const claimSha2 = computeSha256ClaimId(2, didWorker1, scheme1Id, govOfficer.address, "MH", now);
      await expect(
        welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker1, "MH", claimSha2)
      ).to.be.revertedWith("WelfareSchemeRegistry: Duplicate claim prevented. Cooldown period active.");
    });

    it("ADVERSARIAL BOUNDARY: should reject claim at 29 days 23 hours 59 minutes 59 seconds (cooldown - 1s)", async function () {
      const now = await time.latest();
      const claimSha1 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "MH", now);
      await welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker1, "MH", claimSha1);

      // Advance time to exactly 1 second before the 30-day cooldown expires
      await time.increase(cooldown30Days - 2); // -2 because mining next tx will advance by >= 1s

      // Check eligibility check view
      const [eligible, reason] = await welfareRegistry.isWorkerEligibleForScheme(didWorker1, scheme1Id);
      expect(eligible).to.be.false;
      expect(reason).to.equal("Cooldown period active for this scheme");

      // Attempt claim before cooldown expiry
      const claimSha2 = computeSha256ClaimId(2, didWorker1, scheme1Id, govOfficer.address, "MH", await time.latest());
      await expect(
        welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker1, "MH", claimSha2)
      ).to.be.revertedWith("WelfareSchemeRegistry: Duplicate claim prevented. Cooldown period active.");
    });

    it("ADVERSARIAL BOUNDARY: should permit second claim once the full 30-day cooldown has elapsed", async function () {
      const now = await time.latest();
      const claimSha1 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "MH", now);
      await welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker1, "MH", claimSha1);

      // Fast-forward past 30 days (+ 100 seconds safety margin)
      await time.increase(cooldown30Days + 100);

      // Check eligibility view
      const [eligible, reason] = await welfareRegistry.isWorkerEligibleForScheme(didWorker1, scheme1Id);
      expect(eligible).to.be.true;
      expect(reason).to.equal("Eligible");

      // Second claim succeeds
      const newTimestamp = await time.latest();
      const claimSha2 = computeSha256ClaimId(2, didWorker1, scheme1Id, govOfficer.address, "MH", newTimestamp);
      const secondClaimTx = await welfareRegistry.connect(govOfficer).recordClaim(
        scheme1Id,
        didWorker1,
        "MH",
        claimSha2
      );
      await expect(secondClaimTx).to.emit(welfareRegistry, "BenefitClaimed");

      const claimsList = await welfareRegistry.getWorkerClaimIds(didWorker1);
      expect(claimsList.length).to.equal(2);
    });

    it("should allow same worker to claim DIFFERENT welfare scheme without cross-scheme cooldown blocking", async function () {
      // Claim Scheme 1
      const claimSha1 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "MH", await time.latest());
      await welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker1, "MH", claimSha1);

      // Immediately attempt claim on Scheme 2 (Monsoon Relief)
      const claimSha2 = computeSha256ClaimId(2, didWorker1, scheme2Id, govOfficer.address, "MH", await time.latest());
      const tx = await welfareRegistry.connect(govOfficer).recordClaim(scheme2Id, didWorker1, "MH", claimSha2);
      await expect(tx).to.emit(welfareRegistry, "BenefitClaimed");

      const claimsList = await welfareRegistry.getWorkerClaimIds(didWorker1);
      expect(claimsList.length).to.equal(2);
    });

    it("should allow DIFFERENT workers to claim same scheme without cross-worker collision", async function () {
      // Setup worker 2
      await identityRegistry.connect(issuer).registerWorker(didWorker2, sampleCredHash2, sampleCid2);

      // Worker 1 claims Scheme 1
      const claimSha1 = computeSha256ClaimId(1, didWorker1, scheme1Id, govOfficer.address, "MH", await time.latest());
      await welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker1, "MH", claimSha1);

      // Worker 2 claims Scheme 1 immediately
      const claimSha2 = computeSha256ClaimId(2, didWorker2, scheme1Id, govOfficer.address, "MH", await time.latest());
      const txWorker2 = await welfareRegistry.connect(govOfficer).recordClaim(scheme1Id, didWorker2, "MH", claimSha2);
      await expect(txWorker2).to.emit(welfareRegistry, "BenefitClaimed");

      const worker1Claims = await welfareRegistry.getWorkerClaimIds(didWorker1);
      const worker2Claims = await welfareRegistry.getWorkerClaimIds(didWorker2);
      expect(worker1Claims.length).to.equal(1);
      expect(worker2Claims.length).to.equal(1);
      expect(worker1Claims[0]).to.not.equal(worker2Claims[0]);
    });
  });
});
