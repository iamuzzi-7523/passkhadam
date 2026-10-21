// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./OrganizationRegistry.sol";

/**
 * @title WelfareSchemeRegistry
 * @dev Manages government welfare schemes, records cross-state claims,
 * validates authorized government authority wallets, enforces dynamic cooldown periods,
 * and tracks cryptographically derived SHA-256 Claim IDs.
 */
contract WelfareSchemeRegistry {
    OrganizationRegistry public orgRegistry;
    address public admin;

    struct Scheme {
        uint256 id;
        string name;
        string description;
        uint256 amount;
        uint256 cooldownPeriodSeconds;
        bool isCrossStateAllowed;
        bool isActive;
    }

    struct Claim {
        uint256 claimId;
        uint256 schemeId;
        string sha256ClaimId;
        bytes32 workerDidHash;
        address govOfficer;
        string officerState;
        uint256 amount;
        uint256 timestamp;
        bool isDisbursed;
    }

    uint256 public nextSchemeId = 1;
    uint256 public nextClaimId = 1;

    mapping(uint256 => Scheme) public schemes;
    mapping(uint256 => Claim) public claims;

    // Mapping: workerDidHash => schemeId => lastClaimTimestamp
    mapping(bytes32 => mapping(uint256 => uint256)) public lastClaimTime;
    
    // Mapping: workerDidHash => claimId list
    mapping(bytes32 => uint256[]) private workerClaims;

    event SchemeRegistered(uint256 indexed schemeId, string name, uint256 amount);
    event BenefitClaimed(
        uint256 indexed claimId,
        uint256 indexed schemeId,
        string sha256ClaimId,
        bytes32 indexed workerDidHash,
        address govOfficer,
        string officerState,
        uint256 amount
    );

    modifier onlyAdmin() {
        require(msg.sender == admin, "WelfareSchemeRegistry: Only platform admin");
        _;
    }

    constructor(address _orgRegistryAddress) {
        orgRegistry = OrganizationRegistry(_orgRegistryAddress);
        admin = msg.sender;
    }

    function registerScheme(
        string calldata name,
        string calldata description,
        uint256 amount,
        uint256 cooldownPeriodSeconds,
        bool isCrossStateAllowed
    ) external onlyAdmin returns (uint256) {
        uint256 sid = nextSchemeId++;
        schemes[sid] = Scheme({
            id: sid,
            name: name,
            description: description,
            amount: amount,
            cooldownPeriodSeconds: cooldownPeriodSeconds,
            isCrossStateAllowed: isCrossStateAllowed,
            isActive: true
        });

        emit SchemeRegistered(sid, name, amount);
        return sid;
    }

    function recordClaim(
        uint256 schemeId,
        string calldata workerDid,
        string calldata officerState,
        string calldata sha256ClaimId
    ) external returns (uint256) {
        require(orgRegistry.isOrganizationApproved(msg.sender), "Government authority not approved on-chain");
        require(schemes[schemeId].isActive, "Scheme is not active");

        Scheme memory s = schemes[schemeId];
        bytes32 didHash = keccak256(bytes(workerDid));

        uint256 lastTime = lastClaimTime[didHash][schemeId];
        if (lastTime > 0) {
            require(
                block.timestamp >= lastTime + s.cooldownPeriodSeconds,
                "WelfareSchemeRegistry: Duplicate claim prevented. Cooldown period active."
            );
        }

        uint256 cid = nextClaimId++;
        claims[cid] = Claim({
            claimId: cid,
            schemeId: schemeId,
            sha256ClaimId: sha256ClaimId,
            workerDidHash: didHash,
            govOfficer: msg.sender,
            officerState: officerState,
            amount: s.amount,
            timestamp: block.timestamp,
            isDisbursed: true
        });

        lastClaimTime[didHash][schemeId] = block.timestamp;
        workerClaims[didHash].push(cid);

        emit BenefitClaimed(cid, schemeId, sha256ClaimId, didHash, msg.sender, officerState, s.amount);
        return cid;
    }

    function getWorkerClaimIds(string calldata workerDid) external view returns (uint256[] memory) {
        bytes32 didHash = keccak256(bytes(workerDid));
        return workerClaims[didHash];
    }

    function isWorkerEligibleForScheme(
        string calldata workerDid,
        uint256 schemeId
    ) external view returns (bool eligible, string memory reason) {
        if (!schemes[schemeId].isActive) {
            return (false, "Scheme is inactive");
        }
        bytes32 didHash = keccak256(bytes(workerDid));
        uint256 lastTime = lastClaimTime[didHash][schemeId];
        if (lastTime > 0 && block.timestamp < lastTime + schemes[schemeId].cooldownPeriodSeconds) {
            return (false, "Cooldown period active for this scheme");
        }
        return (true, "Eligible");
    }
}
