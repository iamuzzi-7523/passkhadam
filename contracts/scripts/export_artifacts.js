const fs = require("fs");
const path = require("path");

function main() {
  console.log("Exporting PASSKHADAM contract ABIs...");

  const contractsList = [
    "WorkerIdentityRegistry",
    "CredentialRegistry",
    "OrganizationRegistry",
    "EmploymentRegistry",
    "WelfareSchemeRegistry"
  ];

  const deployedMetadata = {
    network: "hardhat",
    chainId: 1337,
    deployer: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    contracts: {}
  };

  // Deterministic addresses when deployed in order by account 0
  const deterministicAddresses = {
    WorkerIdentityRegistry: "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    CredentialRegistry: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
    OrganizationRegistry: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
    EmploymentRegistry: "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
    WelfareSchemeRegistry: "0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9"
  };

  for (const name of contractsList) {
    const artifactPath = path.join(__dirname, `../artifacts/contracts/${name}.sol/${name}.json`);
    if (fs.existsSync(artifactPath)) {
      const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf-8"));
      deployedMetadata.contracts[name] = {
        address: deterministicAddresses[name],
        abi: artifact.abi
      };
      console.log(`✓ Exported ${name}`);
    } else {
      console.error(`Artifact not found: ${artifactPath}`);
    }
  }

  const outDir = path.join(__dirname, "../../backend/app/blockchain");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  fs.writeFileSync(path.join(outDir, "deployed_contracts.json"), JSON.stringify(deployedMetadata, null, 2));
  console.log("✓ Contract metadata successfully written to backend/app/blockchain/deployed_contracts.json");
}

main();
