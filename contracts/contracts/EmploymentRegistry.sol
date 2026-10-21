// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./OrganizationRegistry.sol";

/**
 * @title EmploymentRegistry
 * @dev Creates immutable, event-driven portable employment records.
 * Verifies employer authorization, employment category, level, and nature.
 * Preserves append-only historical audit trail.
 */
contract EmploymentRegistry {
    OrganizationRegistry public orgRegistry;
    address public admin;

    enum EmploymentStatus { ACTIVE, COMPLETED, TERMINATED, RESIGNED, SUSPENDED, DISMISSED }

    struct EmploymentEvent {
        EmploymentStatus status;
        string reason;
        uint256 timestamp;
    }

    struct EmploymentRecord {
        uint256 id;
        bytes32 workerDidHash;
        address employerAddress;
        string category;
        string level;
        string natureOfEmployment;
        string jobRole;
        string workLocation;
        uint256 startDate;
        uint256 endDate;
        EmploymentStatus status;
        string statusReason;
    }

    uint256 public nextEmploymentId = 1;
    mapping(uint256 => EmploymentRecord) public employments;
    mapping(uint256 => EmploymentEvent[]) private employmentEvents;
    mapping(bytes32 => uint256[]) private workerEmploymentIds;
    mapping(address => uint256[]) private employerEmploymentIds;

    event EmploymentCreated(
        uint256 indexed id,
        bytes32 indexed workerDidHash,
        address indexed employerAddress,
        string category
    );
    event EmploymentStatusUpdated(uint256 indexed id, EmploymentStatus status, string reason, uint256 timestamp);

    modifier onlyEmployer(uint256 employmentId) {
        require(
            employments[employmentId].employerAddress == msg.sender || msg.sender == admin,
            "EmploymentRegistry: Only employer or admin"
        );
        _;
    }

    constructor(address _orgRegistryAddress) {
        orgRegistry = OrganizationRegistry(_orgRegistryAddress);
        admin = msg.sender;
    }

    function createEmployment(
        string calldata workerDid,
        string calldata category,
        string calldata level,
        string calldata natureOfEmployment,
        string calldata jobRole,
        string calldata workLocation,
        uint256 expectedEndDate
    ) external returns (uint256) {
        require(orgRegistry.isOrganizationApproved(msg.sender), "Employer not approved");
        require(orgRegistry.isCategoryAuthorized(msg.sender, category), "Category not authorized for employer");
        require(orgRegistry.isLevelAuthorized(msg.sender, level), "Level not authorized for employer");
        require(orgRegistry.isNatureAuthorized(msg.sender, natureOfEmployment), "Nature of employment not authorized");

        bytes32 didHash = keccak256(bytes(workerDid));
        uint256 empId = nextEmploymentId++;

        employments[empId] = EmploymentRecord({
            id: empId,
            workerDidHash: didHash,
            employerAddress: msg.sender,
            category: category,
            level: level,
            natureOfEmployment: natureOfEmployment,
            jobRole: jobRole,
            workLocation: workLocation,
            startDate: block.timestamp,
            endDate: expectedEndDate,
            status: EmploymentStatus.ACTIVE,
            statusReason: "Initial Stint Offer"
        });

        employmentEvents[empId].push(EmploymentEvent({
            status: EmploymentStatus.ACTIVE,
            reason: "Stint Created & Started",
            timestamp: block.timestamp
        }));

        workerEmploymentIds[didHash].push(empId);
        employerEmploymentIds[msg.sender].push(empId);

        emit EmploymentCreated(empId, didHash, msg.sender, category);
        return empId;
    }

    function updateEmploymentStatus(
        uint256 employmentId,
        EmploymentStatus newStatus,
        string calldata reason
    ) external onlyEmployer(employmentId) {
        require(employments[employmentId].id != 0, "Employment record not found");
        
        employments[employmentId].status = newStatus;
        employments[employmentId].statusReason = reason;
        if (newStatus == EmploymentStatus.COMPLETED || newStatus == EmploymentStatus.TERMINATED || newStatus == EmploymentStatus.DISMISSED) {
            employments[employmentId].endDate = block.timestamp;
        }

        // Append to immutable event history
        employmentEvents[employmentId].push(EmploymentEvent({
            status: newStatus,
            reason: reason,
            timestamp: block.timestamp
        }));

        emit EmploymentStatusUpdated(employmentId, newStatus, reason, block.timestamp);
    }

    function getWorkerEmploymentIds(string calldata workerDid) external view returns (uint256[] memory) {
        bytes32 didHash = keccak256(bytes(workerDid));
        return workerEmploymentIds[didHash];
    }

    function getEmployerEmploymentIds(address employer) external view returns (uint256[] memory) {
        return employerEmploymentIds[employer];
    }

    function getEmploymentEventsCount(uint256 employmentId) external view returns (uint256) {
        return employmentEvents[employmentId].length;
    }
}
