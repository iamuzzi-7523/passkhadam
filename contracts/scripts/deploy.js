const fs = require("fs");
const path = require("path");
const { ethers } = require("hardhat");

async function main() {
  console.log("🚀 Starting PASSKHADAM smart contract deployment...");

  const [deployer] = await ethers.getSigners();
  console.log(`Deploying from account: ${deployer.address}`);

  // 1. WorkerIdentityRegistry
  const IdentityFactory = await ethers.getContractFactory("WorkerIdentityRegistry");
  const identityRegistry = await IdentityFactory.deploy();
  await identityRegistry.waitForDeployment();
  const identityAddr = await identityRegistry.getAddress();
  console.log(`✓ WorkerIdentityRegistry deployed to: ${identityAddr}`);

  // 2. CredentialRegistry
  const CredFactory = await ethers.getContractFactory("CredentialRegistry");
  const credRegistry = await CredFactory.deploy();
  await credRegistry.waitForDeployment();
  const credAddr = await credRegistry.getAddress();
  console.log(`✓ CredentialRegistry deployed to: ${credAddr}`);

  // 3. OrganizationRegistry
  const OrgFactory = await ethers.getContractFactory("OrganizationRegistry");
  const orgRegistry = await OrgFactory.deploy();
  await orgRegistry.waitForDeployment();
  const orgAddr = await orgRegistry.getAddress();
  console.log(`✓ OrganizationRegistry deployed to: ${orgAddr}`);

  // 4. EmploymentRegistry
  const EmpFactory = await ethers.getContractFactory("EmploymentRegistry");
  const employmentRegistry = await EmpFactory.deploy(orgAddr);
  await employmentRegistry.waitForDeployment();
  const empAddr = await employmentRegistry.getAddress();
  console.log(`✓ EmploymentRegistry deployed to: ${empAddr}`);

  // 5. WelfareSchemeRegistry
  const WelfareFactory = await ethers.getContractFactory("WelfareSchemeRegistry");
  const welfareRegistry = await WelfareFactory.deploy(orgAddr);
  await welfareRegistry.waitForDeployment();
  const welfareAddr = await welfareRegistry.getAddress();
  console.log(`✓ WelfareSchemeRegistry deployed to: ${welfareAddr}`);

  // Pre-seed default Welfare Scheme for Interstate Migrants
  console.log("Seeding initial government welfare schemes...");
  const tx1 = await welfareRegistry.registerScheme(
    "National Interstate Migrant Relief",
    "Direct financial support and travel subsidy for interstate registered workers",
    3000,
    30 * 86400, // 30-day cooldown
    true
  );
  await tx1.wait();

  const tx2 = await welfareRegistry.registerScheme(
    "Construction Workers Safety & Skill Grant",
    "Special tooling and PPE certification grant",
    5000,
    60 * 86400, // 60-day cooldown
    true
  );
  await tx2.wait();
  console.log("✓ Initial welfare schemes seeded.");

  // Save contract addresses and ABIs for Backend & Frontend
  const activeNetwork = await ethers.provider.getNetwork();
  const deployedContracts = {
    network: hre.network.name,
    chainId: Number(activeNetwork.chainId),
    deployer: deployer.address,
    contracts: {
      WorkerIdentityRegistry: {
        address: identityAddr,
        abi: JSON.parse(fs.readFileSync(path.join(__dirname, "../artifacts/contracts/WorkerIdentityRegistry.sol/WorkerIdentityRegistry.json"))).abi
      },
      CredentialRegistry: {
        address: credAddr,
        abi: JSON.parse(fs.readFileSync(path.join(__dirname, "../artifacts/contracts/CredentialRegistry.sol/CredentialRegistry.json"))).abi
      },
      OrganizationRegistry: {
        address: orgAddr,
        abi: JSON.parse(fs.readFileSync(path.join(__dirname, "../artifacts/contracts/OrganizationRegistry.sol/OrganizationRegistry.json"))).abi
      },
      EmploymentRegistry: {
        address: empAddr,
        abi: JSON.parse(fs.readFileSync(path.join(__dirname, "../artifacts/contracts/EmploymentRegistry.sol/EmploymentRegistry.json"))).abi
      },
      WelfareSchemeRegistry: {
        address: welfareAddr,
        abi: JSON.parse(fs.readFileSync(path.join(__dirname, "../artifacts/contracts/WelfareSchemeRegistry.sol/WelfareSchemeRegistry.json"))).abi
      }
    }
  };

  const outputDir = path.join(__dirname, "../../backend/app/blockchain");
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  fs.writeFileSync(path.join(outputDir, "deployed_contracts.json"), JSON.stringify(deployedContracts, null, 2));
  console.log(`✓ Deployed contracts metadata saved to backend/app/blockchain/deployed_contracts.json`);
}

main().catch((error) => {
  console.error("Error during deployment:", error);
  process.exitCode = 1;
});
