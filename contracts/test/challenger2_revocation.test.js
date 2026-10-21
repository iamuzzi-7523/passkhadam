const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Milestone 1 Adversarial Challenge: OrganizationRegistry & EmploymentRegistry (Challenger_2)", function () {
  let admin, employer1, employer2, unapprovedEmployer, nonAdminAttacker, issuer, worker;
  let orgRegistry, employmentRegistry, identityRegistry;

  const didWorker1 = "did:passkhadam:worker:adversarial:12345678";
  const dummyCredHash = ethers.keccak256(ethers.toUtf8Bytes("TestCred"));
  const dummyIpfsCid = "QmTestAdversarialIpfsHash1234567890";

  beforeEach(async function () {
    [admin, employer1, employer2, unapprovedEmployer, nonAdminAttacker, issuer, worker] = await ethers.getSigners();

    // 1. Deploy OrganizationRegistry
    const OrgFactory = await ethers.getContractFactory("OrganizationRegistry");
    orgRegistry = await OrgFactory.deploy();
    await orgRegistry.waitForDeployment();

    // 2. Deploy WorkerIdentityRegistry
    const IdentityFactory = await ethers.getContractFactory("WorkerIdentityRegistry");
    identityRegistry = await IdentityFactory.deploy();
    await identityRegistry.waitForDeployment();
    await identityRegistry.setIssuer(issuer.address, true);

    // Register worker in identity registry
    await identityRegistry.connect(issuer).registerWorker(didWorker1, dummyCredHash, dummyIpfsCid);

    // 3. Deploy EmploymentRegistry
    const EmpFactory = await ethers.getContractFactory("EmploymentRegistry");
    employmentRegistry = await EmpFactory.deploy(await orgRegistry.getAddress());
    await employmentRegistry.waitForDeployment();

    // 4. Setup approved employer1 with ["Mason", "Electrician", "Plumber"]
    await orgRegistry.connect(employer1).registerOrganization(
      "Employer 1 Construction Ltd",
      "REG-EMP-111",
      "KA",
      0, // EMPLOYER
      ["Mason", "Electrician", "Plumber"]
    );
    await orgRegistry.connect(admin).setOrganizationStatus(employer1.address, 1, "Approved by Platform Admin"); // 1 = APPROVED

    // 5. Setup approved employer2 with ["Mason", "Carpenter"]
    await orgRegistry.connect(employer2).registerOrganization(
      "Employer 2 Infrastructure Ltd",
      "REG-EMP-222",
      "MH",
      0, // EMPLOYER
      ["Mason", "Carpenter"]
    );
    await orgRegistry.connect(admin).setOrganizationStatus(employer2.address, 1, "Approved by Platform Admin");

    // 6. Setup unapproved employer (remains PENDING)
    await orgRegistry.connect(unapprovedEmployer).registerOrganization(
      "Unapproved Fake Corp",
      "REG-FAKE-000",
      "DL",
      0, // EMPLOYER
      ["Mason", "Electrician"]
    );
  });

  describe("Adversarial Requirement 1.1: Non-admin calling revokeCategory -> Revert with 'OrganizationRegistry: Only platform admin'", function () {
    it("should reject non-admin caller attempting to revoke a category", async function () {
      await expect(
        orgRegistry.connect(nonAdminAttacker).revokeCategory(employer1.address, "Mason")
      ).to.be.revertedWith("OrganizationRegistry: Only platform admin");
    });

    it("should reject employer attempting to revoke their own category directly without admin", async function () {
      await expect(
        orgRegistry.connect(employer1).revokeCategory(employer1.address, "Mason")
      ).to.be.revertedWith("OrganizationRegistry: Only platform admin");
    });

    it("should reject unapproved organization caller attempting to revoke category", async function () {
      await expect(
        orgRegistry.connect(unapprovedEmployer).revokeCategory(employer1.address, "Mason")
      ).to.be.revertedWith("OrganizationRegistry: Only platform admin");
    });
  });

  describe("Adversarial Requirement 1.2: Admin calling revokeCategory on unapproved/pending org -> Revert with 'Org not approved'", function () {
    it("should revert when admin attempts to revoke category on PENDING organization", async function () {
      expect(await orgRegistry.isOrganizationApproved(unapprovedEmployer.address)).to.be.false;

      await expect(
        orgRegistry.connect(admin).revokeCategory(unapprovedEmployer.address, "Mason")
      ).to.be.revertedWith("Org not approved");
    });

    it("should revert when admin attempts to revoke category on completely unregistered address", async function () {
      const randomAddress = ethers.Wallet.createRandom().address;
      await expect(
        orgRegistry.connect(admin).revokeCategory(randomAddress, "Mason")
      ).to.be.revertedWith("Org not approved");
    });

    it("should revert when admin attempts to revoke category on SUSPENDED organization", async function () {
      // Suspend employer1
      await orgRegistry.connect(admin).setOrganizationStatus(employer1.address, 3, "Compliance breach"); // 3 = SUSPENDED
      expect(await orgRegistry.isOrganizationApproved(employer1.address)).to.be.false;

      await expect(
        orgRegistry.connect(admin).revokeCategory(employer1.address, "Mason")
      ).to.be.revertedWith("Org not approved");
    });

    it("should revert when admin attempts to revoke category on REJECTED organization", async function () {
      // Reject unapprovedEmployer
      await orgRegistry.connect(admin).setOrganizationStatus(unapprovedEmployer.address, 2, "Failed KYC"); // 2 = REJECTED
      await expect(
        orgRegistry.connect(admin).revokeCategory(unapprovedEmployer.address, "Mason")
      ).to.be.revertedWith("Org not approved");
    });
  });

  describe("Adversarial Requirement 1.3: Revoking one category preserves other approved categories", function () {
    it("should revoke specified category while leaving all other categories untouched", async function () {
      // Initial state: Mason, Electrician, Plumber are all approved
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Mason")).to.be.true;
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Electrician")).to.be.true;
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Plumber")).to.be.true;

      // Admin revokes "Electrician"
      const tx = await orgRegistry.connect(admin).revokeCategory(employer1.address, "Electrician");
      await expect(tx)
        .to.emit(orgRegistry, "CategoryRevoked")
        .withArgs(employer1.address, "Electrician");

      // Verify "Electrician" is now false
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Electrician")).to.be.false;
      expect(await orgRegistry.isCategoryApproved(employer1.address, "Electrician")).to.be.false;
      expect(await orgRegistry.approvedCategories(employer1.address, "Electrician")).to.be.false;

      // Verify "Mason" and "Plumber" remain true
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Mason")).to.be.true;
      expect(await orgRegistry.isCategoryApproved(employer1.address, "Mason")).to.be.true;
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Plumber")).to.be.true;
      expect(await orgRegistry.isCategoryApproved(employer1.address, "Plumber")).to.be.true;
    });

    it("should preserve category authorizations of other employers (cross-tenant isolation)", async function () {
      // Both employer1 and employer2 have "Mason" authorized
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Mason")).to.be.true;
      expect(await orgRegistry.isCategoryAuthorized(employer2.address, "Mason")).to.be.true;

      // Revoke "Mason" only from employer1
      await orgRegistry.connect(admin).revokeCategory(employer1.address, "Mason");

      // employer1 "Mason" is revoked
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Mason")).to.be.false;

      // employer2 "Mason" is STRICTLY PRESERVED
      expect(await orgRegistry.isCategoryAuthorized(employer2.address, "Mason")).to.be.true;
      expect(await orgRegistry.isCategoryApproved(employer2.address, "Mason")).to.be.true;
    });
  });

  describe("Adversarial Requirement 1.4: EmploymentRegistry.createEmployment for revoked category -> Revert with 'Category not authorized for employer'", function () {
    it("should reject createEmployment for revoked category and allow unrevoked category", async function () {
      // Admin revokes "Plumber" from employer1
      await orgRegistry.connect(admin).revokeCategory(employer1.address, "Plumber");

      // Attempting to create employment with revoked category "Plumber" must revert
      await expect(
        employmentRegistry.connect(employer1).createEmployment(
          didWorker1,
          "Plumber",
          "Skilled",
          "Contract",
          "Pipe fitter",
          "Bengaluru, KA",
          Math.floor(Date.now() / 1000) + 86400 * 30
        )
      ).to.be.revertedWith("Category not authorized for employer");

      // Creating employment with active category "Mason" must succeed
      const tx = await employmentRegistry.connect(employer1).createEmployment(
        didWorker1,
        "Mason",
        "Skilled",
        "Contract",
        "Brick mason",
        "Bengaluru, KA",
        Math.floor(Date.now() / 1000) + 86400 * 30
      );
      await expect(tx).to.emit(employmentRegistry, "EmploymentCreated");

      const empIds = await employmentRegistry.getWorkerEmploymentIds(didWorker1);
      expect(empIds.length).to.equal(1);
      const record = await employmentRegistry.employments(empIds[0]);
      expect(record.category).to.equal("Mason");
      expect(record.status).to.equal(0); // ACTIVE
    });

    it("should permit employment creation again if admin re-authorizes previously revoked category", async function () {
      // Revoke "Electrician"
      await orgRegistry.connect(admin).revokeCategory(employer1.address, "Electrician");

      // Must fail
      await expect(
        employmentRegistry.connect(employer1).createEmployment(
          didWorker1,
          "Electrician",
          "Skilled",
          "Contract",
          "Electrician role",
          "Bengaluru, KA",
          0
        )
      ).to.be.revertedWith("Category not authorized for employer");

      // Admin re-authorizes "Electrician"
      await orgRegistry.connect(admin).authorizeCategory(employer1.address, "Electrician");
      expect(await orgRegistry.isCategoryAuthorized(employer1.address, "Electrician")).to.be.true;

      // Now createEmployment must succeed
      await expect(
        employmentRegistry.connect(employer1).createEmployment(
          didWorker1,
          "Electrician",
          "Skilled",
          "Contract",
          "Electrician role",
          "Bengaluru, KA",
          0
        )
      ).to.emit(employmentRegistry, "EmploymentCreated");
    });
  });
});
