// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CredentialRegistry
 * @dev Manages individual Verifiable Credentials (Identity, Skill, Safety),
 * their cryptographic hashes, issuers, expiration, and revocation status.
 */
contract CredentialRegistry {
    address public admin;

    struct Credential {
        bytes32 credId;
        string credType;
        bytes32 workerDidHash;
        address issuer;
        string ipfsCid;
        uint256 issuedAt;
        uint256 expiresAt;
        bool isRevoked;
        string revocationReason;
    }

    mapping(bytes32 => Credential) public credentials;
    mapping(address => bool) public authorizedIssuers;

    event CredentialIssued(bytes32 indexed credId, string credType, bytes32 indexed workerDidHash, address indexed issuer, string ipfsCid);
    event CredentialRevoked(bytes32 indexed credId, string reason);

    modifier onlyAdmin() {
        require(msg.sender == admin, "CredentialRegistry: Only admin");
        _;
    }

    modifier onlyIssuer() {
        require(authorizedIssuers[msg.sender] || msg.sender == admin, "CredentialRegistry: Only authorized issuer");
        _;
    }

    constructor() {
        admin = msg.sender;
        authorizedIssuers[msg.sender] = true;
    }

    function setIssuer(address issuer, bool status) external onlyAdmin {
        authorizedIssuers[issuer] = status;
    }

    function issueCredential(
        bytes32 credId,
        string calldata credType,
        string calldata workerDid,
        string calldata ipfsCid,
        uint256 validityDuration
    ) external onlyIssuer {
        require(credentials[credId].issuedAt == 0, "Credential ID already exists");
        bytes32 didHash = keccak256(bytes(workerDid));

        credentials[credId] = Credential({
            credId: credId,
            credType: credType,
            workerDidHash: didHash,
            issuer: msg.sender,
            ipfsCid: ipfsCid,
            issuedAt: block.timestamp,
            expiresAt: validityDuration > 0 ? block.timestamp + validityDuration : 0,
            isRevoked: false,
            revocationReason: ""
        });

        emit CredentialIssued(credId, credType, didHash, msg.sender, ipfsCid);
    }

    function revokeCredential(bytes32 credId, string calldata reason) external onlyIssuer {
        require(credentials[credId].issuedAt != 0, "Credential not found");
        require(!credentials[credId].isRevoked, "Credential already revoked");

        credentials[credId].isRevoked = true;
        credentials[credId].revocationReason = reason;

        emit CredentialRevoked(credId, reason);
    }

    function isCredentialValid(bytes32 credId) external view returns (bool) {
        Credential memory c = credentials[credId];
        if (c.issuedAt == 0 || c.isRevoked) {
            return false;
        }
        if (c.expiresAt > 0 && block.timestamp > c.expiresAt) {
            return false;
        }
        return true;
    }
}
