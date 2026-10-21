import time
import hashlib
import pytest
from app.services.blockchain_service import BlockchainService


def test_welfare_dynamic_cooldown_and_sha256_derivation():
    bs = BlockchainService()

    worker_did = "did:passkhadam:worker:test_welfare_999"
    gov_wallet = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
    officer_state = "Maharashtra"
    scheme_id = 1  # 30-day cooldown (2,592,000s)

    # 1.1 Initial valid claim
    claim1 = bs.record_welfare_claim(
        scheme_id=scheme_id,
        worker_did=worker_did,
        gov_address=gov_wallet,
        officer_state=officer_state
    )
    assert claim1["claim_id"] == 1
    assert claim1["is_disbursed"] is True

    # 1.2 Deterministic SHA-256 derivation verification
    claim_id = claim1["claim_id"]
    timestamp = claim1["timestamp"]
    expected_payload = f"{claim_id}:{worker_did}:{scheme_id}:{gov_wallet}:{officer_state}:{timestamp}"
    expected_sha256 = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
    assert claim1["sha256_claim_id"] == expected_sha256

    # 1.3 Avalanche property verification (1-param variation produces distinct hash)
    perturbed_payload = f"{claim_id}:{worker_did}:{scheme_id}:{gov_wallet}:Karnataka:{timestamp}"
    perturbed_sha256 = hashlib.sha256(perturbed_payload.encode("utf-8")).hexdigest()
    assert perturbed_sha256 != expected_sha256

    # 1.4 Immediate double claim prevention (t = 0)
    with pytest.raises(ValueError, match="Duplicate claim prevented"):
        bs.record_welfare_claim(
            scheme_id=scheme_id,
            worker_did=worker_did,
            gov_address=gov_wallet,
            officer_state=officer_state
        )

    # 1.5 Adversarial boundary test: t = 29 days (cooldown - 3600s)
    cooldown = bs.schemes[scheme_id]["cooldown_seconds"]
    bs.last_claim_times[worker_did][scheme_id] = int(time.time()) - (cooldown - 3600)
    with pytest.raises(ValueError, match="Cooldown active for"):
        bs.record_welfare_claim(
            scheme_id=scheme_id,
            worker_did=worker_did,
            gov_address=gov_wallet,
            officer_state=officer_state
        )

    # 1.6 Boundary expiry test: t = 30 days + 1 second
    bs.last_claim_times[worker_did][scheme_id] = int(time.time()) - (cooldown + 1)
    claim2 = bs.record_welfare_claim(
        scheme_id=scheme_id,
        worker_did=worker_did,
        gov_address=gov_wallet,
        officer_state=officer_state
    )
    assert claim2["claim_id"] == 2
    assert claim2["sha256_claim_id"] != claim1["sha256_claim_id"]

    # 1.7 Unapproved government authority rejection
    with pytest.raises(ValueError, match="Government authority is not approved"):
        bs.record_welfare_claim(
            scheme_id=scheme_id,
            worker_did=worker_did,
            gov_address="0xFakeGovUnauthorizedWallet9999",
            officer_state=officer_state
        )


def test_employment_lifecycle_and_history_preservation():
    bs = BlockchainService()

    worker_did = "did:passkhadam:worker:emp_stress_worker_777"
    employer_addr = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"  # Pre-approved Apex Infra Ltd

    # 2.1 Stint Creation
    record = bs.create_employment(
        worker_did=worker_did,
        employer_address=employer_addr,
        category="Mason",
        level="Skilled",
        nature_of_employment="Contract",
        job_role="Senior Bricklayer",
        location="Site Alpha, Pune",
        end_date=int(time.time()) + 86400 * 90
    )
    emp_id = record["id"]
    assert record["status"] == "ACTIVE"
    assert len(bs.employment_events[emp_id]) == 1

    # 2.2 Transition to DISMISSED
    bs.update_employment_status(
        emp_id=emp_id,
        caller_address=employer_addr,
        new_status="DISMISSED",
        reason="Repeated safety breach on scaffolding"
    )

    # 2.3 Verify append-only history and non-deletion
    assert emp_id in bs.employments
    updated_record = bs.employments[emp_id]
    assert updated_record["status"] == "DISMISSED"
    assert updated_record["status_reason"] == "Repeated safety breach on scaffolding"
    assert updated_record["end_date"] > 0
    assert updated_record["category"] == "Mason"
    assert updated_record["level"] == "Skilled"
    assert updated_record["job_role"] == "Senior Bricklayer"
    assert updated_record["employer_address"] == employer_addr

    events = bs.employment_events[emp_id]
    assert len(events) == 2
    assert events[0]["status"] == "ACTIVE"
    assert events[1]["status"] == "DISMISSED"

    # 2.4 Transition to COMPLETED
    bs.update_employment_status(
        emp_id=emp_id,
        caller_address=employer_addr,
        new_status="COMPLETED",
        reason="Labor tribunal mutual settlement completed"
    )
    assert len(bs.employment_events[emp_id]) == 3
    assert bs.employments[emp_id]["status"] == "COMPLETED"

    # 2.5 Active workforce vs Historical stints
    active_roster = bs.get_active_workforce(employer_addr)
    historical_stints = bs.get_worker_employments(worker_did)
    assert not any(e["id"] == emp_id for e in active_roster)
    assert any(e["id"] == emp_id for e in historical_stints)

    # 2.6 Unauthorized caller attack
    with pytest.raises(PermissionError, match="Only employing organization"):
        bs.update_employment_status(
            emp_id=emp_id,
            caller_address="0xMaliciousAttackerAddress9999",
            new_status="ACTIVE",
            reason="Unauthorized restoration"
        )


def test_organization_permissions_scoped_authority():
    bs = BlockchainService()

    worker_did = "did:passkhadam:worker:org_perm_stress_001"
    approved_employer = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
    unapproved_employer = "0x2546BcD3c84621e976D8185a91A922aE77ECEc30"

    # 3.1 Unapproved employer
    with pytest.raises(ValueError, match="Employer is not approved"):
        bs.create_employment(
            worker_did=worker_did,
            employer_address=unapproved_employer,
            category="Mason",
            level="Skilled",
            nature_of_employment="Contract",
            job_role="Helper",
            location="Site B"
        )

    # 3.2 Unauthorized category
    with pytest.raises(ValueError, match="is not authorized for employer"):
        bs.create_employment(
            worker_did=worker_did,
            employer_address=approved_employer,
            category="NuclearEngineer",
            level="Skilled",
            nature_of_employment="Contract",
            job_role="Specialist",
            location="Site B"
        )

    # 3.3 Unauthorized level
    with pytest.raises(ValueError, match="level 'MasterGrandArchitect' is not authorized"):
        bs.create_employment(
            worker_did=worker_did,
            employer_address=approved_employer,
            category="Mason",
            level="MasterGrandArchitect",
            nature_of_employment="Contract",
            job_role="Architect",
            location="Site B"
        )

    # 3.4 Unauthorized nature of employment
    with pytest.raises(ValueError, match="Nature of employment 'InformalCashInHand' is not authorized"):
        bs.create_employment(
            worker_did=worker_did,
            employer_address=approved_employer,
            category="Mason",
            level="Skilled",
            nature_of_employment="InformalCashInHand",
            job_role="Bricklayer",
            location="Site B"
        )


def test_worker_identity_duplicate_did_and_integrity():
    bs = BlockchainService()

    worker_did = "did:passkhadam:worker:unique_worker_identity_101"
    cred_hash = "0x" + hashlib.sha256(b"EncryptedPayload101").hexdigest()
    ipfs_cid = "QmUniqueHash101Base58"

    # 4.1 First registration
    w1 = bs.register_worker(
        did=worker_did,
        cred_hash=cred_hash,
        ipfs_cid=ipfs_cid
    )
    assert w1["did"] == worker_did
    assert w1["is_registered"] is True
    assert w1["is_revoked"] is False

    # 4.2 Duplicate DID registration
    with pytest.raises(ValueError, match="already"):
        bs.register_worker(
            did=worker_did,
            cred_hash="0x" + hashlib.sha256(b"TamperedPayload").hexdigest(),
            ipfs_cid="QmTamperedIpfsCid"
        )

    # 4.3 Worker validation check
    assert bs.is_worker_valid(worker_did) is True
