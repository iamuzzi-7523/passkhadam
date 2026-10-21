const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("PASSKHADAM Decentralized Identity Platform Contracts (v0.3)", function () {
  let admin, issuer, employer, govOfficer, workerAccount;
  let identityRegistry, credRegistry, orgRegistry, employmentRegistry, welfareRegistry;

  const sampleWorkerDid = "did:passkhadam:worker:8f29d7e35b1c0984";
  const sampleCredHash = ethers.keccak256(ethers.toUtf8Bytes("Sample Verifiable Credential Payload"));
  const sampleIpfsCid = "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx";

  beforeEach(async function () {
    [admin, issuer, employer, govOfficer, workerAccount] = await ethers.getSigners();

    // 1. Deploy WorkerIdentityRegistry
    const IdentityFactory = await ethers.getContractFactory("WorkerIdentityRegistry");
    identityRegistry = await IdentityFactory.deploy();
    await identityRegistry.waitForDeployment();
    await identityRegistry.setIssuer(issuer.address, true);

    // 2. Deploy CredentialRegistry
    const CredFactory = await ethers.getContractFactory("CredentialRegistry");
    credRegistry = await CredFactory.deploy();
    await credRegistry.waitForDeployment();
    await credRegistry.setIssuer(issuer.address, true);

    // 3. Deploy OrganizationRegistry
    const OrgFactory = await ethers.getContractFactory("OrganizationRegistry");
    orgRegistry = await OrgFactory.deploy();
    await orgRegistry.waitForDeployment();

    // 4. Deploy EmploymentRegistry
    const EmpFactory = await ethers.getContractFactory("EmploymentRegistry");
    employmentRegistry = await EmpFactory.deploy(await orgRegistry.getAddress());
    await employmentRegistry.waitForDeployment();

    // 5. Deploy WelfareSchemeRegistry
    const WelfareFactory = await ethers.getContractFactory("WelfareSchemeRegistry");
    welfareRegistry = await WelfareFactory.deploy(await orgRegistry.getAddress());
    await welfareRegistry.waitForDeployment();
  });

  describe("WorkerIdentityRegistry", function () {
    it("should allow authorized issuer to register a worker DID without storing raw PII", async function () {
      await expect(
        identityRegistry.connect(issuer).registerWorker(sampleWorkerDid, sampleCredHash, sampleIpfsCid)
      ).to.emit(identityRegistry, "WorkerRegistered");

      const worker = await identityRegistry.getWorkerByDid(sampleWorkerDid);
      expect(worker.didString).to.equal(sampleWorkerDid);
      expect(worker.credentialHash).to.equal(sampleCredHash);
      expect(worker.ipfsCid).to.equal(sampleIpfsCid);
      expect(worker.isRegistered).to.be.true;
      expect(worker.isRevoked).to.be.false;
    });

    it("should prevent duplicate registration of the same DID", async function () {
      await identityRegistry.connect(issuer).registerWorker(sampleWorkerDid, sampleCredHash, sampleIpfsCid);
      await expect(
        identityRegistry.connect(issuer).registerWorker(sampleWorkerDid, sampleCredHash, sampleIpfsCid)
      ).to.be.revertedWith("Worker already registered");
    });

    it("should allow revoking a worker identity with reason", async function () {
      await identityRegistry.connect(issuer).registerWorker(sampleWorkerDid, sampleCredHash, sampleIpfsCid);
      await identityRegistry.connect(issuer).revokeWorker(sampleWorkerDid, "Aadhaar reported compromised");

      const isValid = await identityRegistry.isWorkerValid(sampleWorkerDid);
      expect(isValid).to.be.false;

      const worker = await identityRegistry.getWorkerByDid(sampleWorkerDid);
      expect(worker.isRevoked).to.be.true;
      expect(worker.revocationReason).to.equal("Aadhaar reported compromised");
    });
  });

  describe("OrganizationRegistry & Scope Permissions", function () {
    it("should register employer in PENDING status and allow admin to approve with categories, levels, and nature", async function () {
      await orgRegistry.connect(employer).registerOrganization(
        "Apex Infra Ltd",
        "CIN-123456",
        "KA",
        0, // OrgType.EMPLOYER
        ["Mason", "Electrician"]
      );

      expect(await orgRegistry.isOrganizationApproved(employer.address)).to.be.false;

      // Admin approves
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 1, "Documents verified"); // 1 = APPROVED
      expect(await orgRegistry.isOrganizationApproved(employer.address)).to.be.true;
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Mason")).to.be.true;
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Plumber")).to.be.false;
      expect(await orgRegistry.isLevelAuthorized(employer.address, "Skilled")).to.be.true;
      expect(await orgRegistry.isNatureAuthorized(employer.address, "Contract")).to.be.true;
    });

    it("should allow admin to dynamically authorize an additional category", async function () {
      await orgRegistry.connect(employer).registerOrganization("Apex Infra Ltd", "CIN-123456", "KA", 0, ["Mason"]);
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 1, "Approved");
      
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Plumber")).to.be.false;
      await orgRegistry.connect(admin).authorizeCategory(employer.address, "Plumber");
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Plumber")).to.be.true;
    });

    it("should allow admin to revoke an authorized category and emit CategoryRevoked event", async function () {
      await orgRegistry.connect(employer).registerOrganization(
        "Apex Infra Ltd",
        "CIN-123456",
        "KA",
        0,
        ["Mason", "Electrician"]
      );
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 1, "Approved");
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Mason")).to.be.true;

      // Admin revokes "Mason"
      await expect(orgRegistry.connect(admin).revokeCategory(employer.address, "Mason"))
        .to.emit(orgRegistry, "CategoryRevoked")
        .withArgs(employer.address, "Mason");

      // Verify category is no longer authorized
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Mason")).to.be.false;
      expect(await orgRegistry.isCategoryApproved(employer.address, "Mason")).to.be.false;
      expect(await orgRegistry.approvedCategories(employer.address, "Mason")).to.be.false;

      // Unrevoked category remains active
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Electrician")).to.be.true;
    });

    it("should revert when non-admin attempts to revoke a category", async function () {
      await orgRegistry.connect(employer).registerOrganization("Apex Infra Ltd", "CIN-123456", "KA", 0, ["Mason"]);
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 1, "Approved");

      await expect(
        orgRegistry.connect(employer).revokeCategory(employer.address, "Mason")
      ).to.be.revertedWith("OrganizationRegistry: Only platform admin");

      await expect(
        orgRegistry.connect(workerAccount).revokeCategory(employer.address, "Mason")
      ).to.be.revertedWith("OrganizationRegistry: Only platform admin");

      // Category remains authorized
      expect(await orgRegistry.isCategoryAuthorized(employer.address, "Mason")).to.be.true;
    });

    it("should revert when revoking a category on a non-approved organization", async function () {
      // 1. Pending organization
      await orgRegistry.connect(employer).registerOrganization("Pending Corp", "CIN-PENDING-001", "KA", 0, ["Mason"]);
      await expect(
        orgRegistry.connect(admin).revokeCategory(employer.address, "Mason")
      ).to.be.revertedWith("Org not approved");

      // 2. Unregistered address
      await expect(
        orgRegistry.connect(admin).revokeCategory(workerAccount.address, "Mason")
      ).to.be.revertedWith("Org not approved");

      // 3. Suspended organization
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 1, "Approved");
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 3, "Suspended for compliance");
      await expect(
        orgRegistry.connect(admin).revokeCategory(employer.address, "Mason")
      ).to.be.revertedWith("Org not approved");
    });
  });

  describe("EmploymentRegistry & Lifecycle Audits", function () {
    beforeEach(async function () {
      await orgRegistry.connect(employer).registerOrganization("Apex Infra Ltd", "CIN-123456", "KA", 0, ["Mason"]);
      await orgRegistry.connect(admin).setOrganizationStatus(employer.address, 1, "Approved");
      await identityRegistry.connect(issuer).registerWorker(sampleWorkerDid, sampleCredHash, sampleIpfsCid);
    });

    it("should create employment with verified category, level, and nature", async function () {
      const tx = await employmentRegistry.connect(employer).createEmployment(
        sampleWorkerDid,
        "Mason",
        "Skilled",
        "Contract",
        "Lead Mason",
        "Bengaluru, KA",
        Math.floor(Date.now() / 1000) + 86400 * 180
      );
      await expect(tx).to.emit(employmentRegistry, "EmploymentCreated");

      const empIds = await employmentRegistry.getWorkerEmploymentIds(sampleWorkerDid);
      expect(empIds.length).to.equal(1);

      const emp = await employmentRegistry.employments(empIds[0]);
      expect(emp.category).to.equal("Mason");
      expect(emp.level).to.equal("Skilled");
      expect(emp.natureOfEmployment).to.equal("Contract");
      expect(emp.status).to.equal(0); // ACTIVE
    });

    it("should record DISMISSED status in event history without deleting historical record", async function () {
      await employmentRegistry.connect(employer).createEmployment(
        sampleWorkerDid,
        "Mason",
        "Skilled",
        "Contract",
        "Lead Mason",
        "Bengaluru, KA",
        0
      );
      const empIds = await employmentRegistry.getWorkerEmploymentIds(sampleWorkerDid);
      
      // 5 = DISMISSED
      await employmentRegistry.connect(employer).updateEmploymentStatus(empIds[0], 5, "Safety violation");
      const emp = await employmentRegistry.employments(empIds[0]);
      expect(emp.status).to.equal(5);
      expect(emp.statusReason).to.equal("Safety violation");

      // Verify event history length is 2 (Created + Dismissed)
      const eventCount = await employmentRegistry.getEmploymentEventsCount(empIds[0]);
      expect(eventCount).to.equal(2);
    });
  });

  describe("WelfareSchemeRegistry & SHA-256 Claim Tracking", function () {
    let schemeId;
    const testClaimSha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

    beforeEach(async function () {
      await orgRegistry.connect(govOfficer).registerOrganization("Govt of Maharashtra Welfare Dept", "MH-DEPT-99", "MH", 1, []);
      await orgRegistry.connect(admin).setOrganizationStatus(govOfficer.address, 1, "Verified Authority");

      const tx = await welfareRegistry.connect(admin).registerScheme(
        "Interstate Migrant Worker Relief",
        "Relief disbursement for registered cross-state workers",
        5000,
        2592000, // 30 days
        true
      );
      await tx.wait();
      schemeId = 1;
    });

    it("should record claim with cryptographically derived Claim ID across states", async function () {
      const claimTx = await welfareRegistry.connect(govOfficer).recordClaim(schemeId, sampleWorkerDid, "MH", testClaimSha);
      await expect(claimTx).to.emit(welfareRegistry, "BenefitClaimed");

      const workerClaims = await welfareRegistry.getWorkerClaimIds(sampleWorkerDid);
      expect(workerClaims.length).to.equal(1);

      const claim = await welfareRegistry.claims(workerClaims[0]);
      expect(claim.sha256ClaimId).to.equal(testClaimSha);
      expect(claim.officerState).to.equal("MH");
      expect(claim.amount).to.equal(5000);
      expect(claim.isDisbursed).to.be.true;
    });

    it("should prevent duplicate claim within 30-day cooldown period", async function () {
      await welfareRegistry.connect(govOfficer).recordClaim(schemeId, sampleWorkerDid, "MH", testClaimSha);
      await expect(
        welfareRegistry.connect(govOfficer).recordClaim(schemeId, sampleWorkerDid, "MH", testClaimSha)
      ).to.be.revertedWith("WelfareSchemeRegistry: Duplicate claim prevented. Cooldown period active.");
    });
  });
});
