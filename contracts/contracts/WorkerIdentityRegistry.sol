// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title WorkerIdentityRegistry
 * @dev Anchors decentralized worker identities (DIDs), encrypted IPFS credential CIDs,
 * and cryptographic integrity hashes. Does NOT store any Aadhaar numbers or raw PII.
 */
contract WorkerIdentityRegistry {
    address public admin;

    struct WorkerIdentity {
        string did;
        bytes32 credentialHash;
        string ipfsCid;
        uint256 issueTimestamp;
        uint256 updatedAt;
        bool isRegistered;
        bool isRevoked;
        string revocationReason;
    }

    // Mapping from keccak256(did) => WorkerIdentity
    mapping(bytes32 => WorkerIdentity) private workers;
    
    // Authorized identity issuers (e.g. Identity Authority / Aadhaar verification bridge)
    mapping(address => bool) public authorizedIssuers;

    event IssuerAuthorized(address indexed issuer);
    event IssuerRevoked(address indexed issuer);
    event WorkerRegistered(bytes32 indexed didHash, string did, bytes32 credentialHash, string ipfsCid);
    event CredentialUpdated(bytes32 indexed didHash, bytes32 newCredentialHash, string newIpfsCid);
    event WorkerRevoked(bytes32 indexed didHash, string reason);
    event WorkerReactivated(bytes32 indexed didHash);

    modifier onlyAdmin() {
        require(msg.sender == admin, "WorkerIdentityRegistry: Only admin authorized");
        _;
    }

    modifier onlyIssuer() {
        require(authorizedIssuers[msg.sender] || msg.sender == admin, "WorkerIdentityRegistry: Only authorized issuer");
        _;
    }

    constructor() {
        admin = msg.sender;
        authorizedIssuers[msg.sender] = true;
    }

    function setIssuer(address issuer, bool status) external onlyAdmin {
        authorizedIssuers[issuer] = status;
        if (status) {
            emit IssuerAuthorized(issuer);
        } else {
            emit IssuerRevoked(issuer);
        }
    }

    function registerWorker(
        string calldata did,
        bytes32 credentialHash,
        string calldata ipfsCid
    ) external onlyIssuer {
        bytes32 didHash = keccak256(bytes(did));
        require(!workers[didHash].isRegistered, "Worker already registered");
        require(credentialHash != bytes32(0), "Invalid credential hash");

        workers[didHash] = WorkerIdentity({
            did: did,
            credentialHash: credentialHash,
            ipfsCid: ipfsCid,
            issueTimestamp: block.timestamp,
            updatedAt: block.timestamp,
            isRegistered: true,
            isRevoked: false,
            revocationReason: ""
        });

        emit WorkerRegistered(didHash, did, credentialHash, ipfsCid);
    }

    function updateCredential(
        string calldata did,
        bytes32 newCredentialHash,
        string calldata newIpfsCid
    ) external onlyIssuer {
        bytes32 didHash = keccak256(bytes(did));
        require(workers[didHash].isRegistered, "Worker not registered");
        require(!workers[didHash].isRevoked, "Worker is revoked");

        workers[didHash].credentialHash = newCredentialHash;
        workers[didHash].ipfsCid = newIpfsCid;
        workers[didHash].updatedAt = block.timestamp;

        emit CredentialUpdated(didHash, newCredentialHash, newIpfsCid);
    }

    function revokeWorker(string calldata did, string calldata reason) external onlyIssuer {
        bytes32 didHash = keccak256(bytes(did));
        require(workers[didHash].isRegistered, "Worker not registered");
        require(!workers[didHash].isRevoked, "Worker already revoked");

        workers[didHash].isRevoked = true;
        workers[didHash].revocationReason = reason;
        workers[didHash].updatedAt = block.timestamp;

        emit WorkerRevoked(didHash, reason);
    }

    function reactivateWorker(string calldata did) external onlyAdmin {
        bytes32 didHash = keccak256(bytes(did));
        require(workers[didHash].isRegistered, "Worker not registered");
        require(workers[didHash].isRevoked, "Worker not revoked");

        workers[didHash].isRevoked = false;
        workers[didHash].revocationReason = "";
        workers[didHash].updatedAt = block.timestamp;

        emit WorkerReactivated(didHash);
    }

    function getWorkerByDid(string calldata did) external view returns (
        string memory didString,
        bytes32 credentialHash,
        string memory ipfsCid,
        uint256 issueTimestamp,
        uint256 updatedAt,
        bool isRegistered,
        bool isRevoked,
        string memory revocationReason
    ) {
        bytes32 didHash = keccak256(bytes(did));
        WorkerIdentity memory w = workers[didHash];
        return (
            w.did,
            w.credentialHash,
            w.ipfsCid,
            w.issueTimestamp,
            w.updatedAt,
            w.isRegistered,
            w.isRevoked,
            w.revocationReason
        );
    }

    function isWorkerValid(string calldata did) external view returns (bool) {
        bytes32 didHash = keccak256(bytes(did));
        return workers[didHash].isRegistered && !workers[didHash].isRevoked;
    }
}
