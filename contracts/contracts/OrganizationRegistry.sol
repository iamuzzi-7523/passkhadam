// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title OrganizationRegistry
 * @dev Manages Employer and Government onboarding, Admin approval lifecycle,
 * authorized employment categories, employment levels, and nature of employment.
 */
contract OrganizationRegistry {
    address public admin;

    enum OrgType { EMPLOYER, GOVERNMENT, ISSUER }
    enum OrgStatus { PENDING, APPROVED, REJECTED, SUSPENDED }

    struct Organization {
        address orgAddress;
        string name;
        string registrationNumber;
        string stateCode;
        OrgType orgType;
        OrgStatus status;
        string rejectionOrSuspensionReason;
        uint256 registeredAt;
        uint256 updatedAt;
    }

    mapping(address => Organization) public organizations;
    mapping(address => mapping(string => bool)) public approvedCategories;
    mapping(address => string[]) private orgCategoriesList;

    mapping(address => mapping(string => bool)) public approvedLevels;
    mapping(address => string[]) private orgLevelsList;

    mapping(address => mapping(string => bool)) public approvedNatures;
    mapping(address => string[]) private orgNaturesList;

    address[] public allOrganizations;

    event OrganizationRegistered(address indexed orgAddress, string name, OrgType orgType);
    event OrganizationStatusChanged(address indexed orgAddress, OrgStatus newStatus, string reason);
    event CategoryAuthorized(address indexed orgAddress, string category);
    event CategoryRevoked(address indexed orgAddress, string category);
    event LevelAuthorized(address indexed orgAddress, string level);
    event NatureAuthorized(address indexed orgAddress, string natureOfEmployment);

    modifier onlyAdmin() {
        require(msg.sender == admin, "OrganizationRegistry: Only platform admin");
        _;
    }

    constructor() {
        admin = msg.sender;
    }

    function registerOrganization(
        string calldata name,
        string calldata registrationNumber,
        string calldata stateCode,
        OrgType orgType,
        string[] calldata initialCategories
    ) external {
        require(organizations[msg.sender].registeredAt == 0, "Organization already registered");
        require(bytes(name).length > 0, "Name cannot be empty");

        organizations[msg.sender] = Organization({
            orgAddress: msg.sender,
            name: name,
            registrationNumber: registrationNumber,
            stateCode: stateCode,
            orgType: orgType,
            status: OrgStatus.PENDING,
            rejectionOrSuspensionReason: "",
            registeredAt: block.timestamp,
            updatedAt: block.timestamp
        });

        allOrganizations.push(msg.sender);

        for (uint256 i = 0; i < initialCategories.length; i++) {
            orgCategoriesList[msg.sender].push(initialCategories[i]);
        }

        // By default, approve baseline levels & natures
        orgLevelsList[msg.sender].push("Skilled");
        orgLevelsList[msg.sender].push("Semi-Skilled");
        orgLevelsList[msg.sender].push("Unskilled");

        orgNaturesList[msg.sender].push("Contract");
        orgNaturesList[msg.sender].push("Permanent");
        orgNaturesList[msg.sender].push("Project-Based");

        emit OrganizationRegistered(msg.sender, name, orgType);
    }

    function setOrganizationStatus(
        address orgAddress,
        OrgStatus newStatus,
        string calldata reason
    ) external onlyAdmin {
        require(organizations[orgAddress].registeredAt != 0, "Organization not found");
        organizations[orgAddress].status = newStatus;
        organizations[orgAddress].rejectionOrSuspensionReason = reason;
        organizations[orgAddress].updatedAt = block.timestamp;

        // If approved, activate all initial requested categories, levels & natures
        if (newStatus == OrgStatus.APPROVED) {
            string[] memory cats = orgCategoriesList[orgAddress];
            for (uint256 i = 0; i < cats.length; i++) {
                approvedCategories[orgAddress][cats[i]] = true;
            }
            string[] memory levels = orgLevelsList[orgAddress];
            for (uint256 i = 0; i < levels.length; i++) {
                approvedLevels[orgAddress][levels[i]] = true;
            }
            string[] memory natures = orgNaturesList[orgAddress];
            for (uint256 i = 0; i < natures.length; i++) {
                approvedNatures[orgAddress][natures[i]] = true;
            }
        }

        emit OrganizationStatusChanged(orgAddress, newStatus, reason);
    }

    function authorizeCategory(address orgAddress, string calldata category) external onlyAdmin {
        require(organizations[orgAddress].status == OrgStatus.APPROVED, "Org not approved");
        approvedCategories[orgAddress][category] = true;
        
        bool exists = false;
        string[] memory cats = orgCategoriesList[orgAddress];
        for (uint256 i = 0; i < cats.length; i++) {
            if (keccak256(bytes(cats[i])) == keccak256(bytes(category))) {
                exists = true;
                break;
            }
        }
        if (!exists) {
            orgCategoriesList[orgAddress].push(category);
        }

        emit CategoryAuthorized(orgAddress, category);
    }

    /**
     * @notice Revoke authorization for a specific employment category for an approved organization.
     * @param orgAddress The address of the approved organization.
     * @param category The employment category to revoke (e.g. "Mason").
     */
    function revokeCategory(address orgAddress, string calldata category) external onlyAdmin {
        require(organizations[orgAddress].status == OrgStatus.APPROVED, "Org not approved");
        approvedCategories[orgAddress][category] = false;
        emit CategoryRevoked(orgAddress, category);
    }

    function authorizeLevel(address orgAddress, string calldata level) external onlyAdmin {
        require(organizations[orgAddress].status == OrgStatus.APPROVED, "Org not approved");
        approvedLevels[orgAddress][level] = true;
        emit LevelAuthorized(orgAddress, level);
    }

    function authorizeNature(address orgAddress, string calldata nature) external onlyAdmin {
        require(organizations[orgAddress].status == OrgStatus.APPROVED, "Org not approved");
        approvedNatures[orgAddress][nature] = true;
        emit NatureAuthorized(orgAddress, nature);
    }

    function isOrganizationApproved(address orgAddress) external view returns (bool) {
        return organizations[orgAddress].status == OrgStatus.APPROVED;
    }

    function isCategoryAuthorized(address orgAddress, string calldata category) external view returns (bool) {
        return organizations[orgAddress].status == OrgStatus.APPROVED && approvedCategories[orgAddress][category];
    }

    /**
     * @notice Alias for isCategoryAuthorized to provide uniform interface naming.
     * @param orgAddress The address of the organization.
     * @param category The employment category to check.
     */
    function isCategoryApproved(address orgAddress, string calldata category) external view returns (bool) {
        return organizations[orgAddress].status == OrgStatus.APPROVED && approvedCategories[orgAddress][category];
    }

    function isLevelAuthorized(address orgAddress, string calldata level) external view returns (bool) {
        return organizations[orgAddress].status == OrgStatus.APPROVED && approvedLevels[orgAddress][level];
    }

    function isNatureAuthorized(address orgAddress, string calldata nature) external view returns (bool) {
        return organizations[orgAddress].status == OrgStatus.APPROVED && approvedNatures[orgAddress][nature];
    }

    function getOrganizationCategories(address orgAddress) external view returns (string[] memory) {
        return orgCategoriesList[orgAddress];
    }

    function getAllOrganizationsCount() external view returns (uint256) {
        return allOrganizations.length;
    }
}
