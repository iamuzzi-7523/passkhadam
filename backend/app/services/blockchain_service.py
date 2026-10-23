import os
import json
import time
import hashlib
import logging
logger = logging.getLogger('blockchain_service')
from typing import Dict, Any, List, Optional
from web3 import Web3

try:
    from app.core.config import settings
except Exception:
    settings = None

class BlockchainService:
    """
    Manages interaction with the PASSKHADAM EVM Smart Contracts.
    Uses Web3.py for backend EVM interaction and maintains an in-process
    verified state ledger mirroring exact smart contract invariants.
    """
    def __init__(self):
        rpc_url = os.getenv("WEB3_RPC_URL") or os.getenv("RPC_URL")
        if not rpc_url and settings:
            rpc_url = getattr(settings, "WEB3_RPC_URL", None) or getattr(settings, "RPC_URL", None)
        if not rpc_url:
            rpc_url = "http://127.0.0.1:8545"
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 0.5}))
        self.is_connected = False
        self._last_conn_check = 0
        try:
            self.is_connected = self.w3.is_connected()
            self._last_conn_check = time.time()
        except Exception:
            self.is_connected = False

        # Load deployed artifacts
        artifacts_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "blockchain", "deployed_contracts.json"
        )
        self.metadata = {}
        if os.path.exists(artifacts_path):
            with open(artifacts_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

        self._init_worker_contract()
        self._init_organization_contract()

        # On-Chain Registries
        self.worker_registry: Dict[str, Dict[str, Any]] = {}
        self.organizations: Dict[str, Dict[str, Any]] = {
            "0x90F79bf6EB2c4f870365E785982E1f101E93b906": {
                "name": "Apex Infrastructure & Construction Ltd",
                "reg_number": "CIN-U45200KA2018PTC112345",
                "state_code": "KA",
                "org_type": "EMPLOYER",
                "status": "APPROVED",
                "categories": ["Mason", "Electrician", "Plumber"],
                "levels": ["Skilled", "Semi-Skilled", "Unskilled"],
                "natures": ["Contract", "Permanent", "Project-Based"],
                "registered_at": int(time.time()) - 86400 * 30
            },
            "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65": {
                "name": "Maharashtra State Migrant Welfare Board",
                "reg_number": "MH-GOV-WELFARE-441",
                "state_code": "MH",
                "org_type": "GOVERNMENT",
                "status": "APPROVED",
                "categories": [],
                "levels": [],
                "natures": [],
                "registered_at": int(time.time()) - 86400 * 60
            }
        }
        self.employments: Dict[int, Dict[str, Any]] = {}
        self.employment_events: Dict[int, List[Dict[str, Any]]] = {}
        self.next_emp_id = 1
        
        self.schemes: Dict[int, Dict[str, Any]] = {
            1: {
                "id": 1,
                "name": "Interstate Migrant Worker Relief Scheme",
                "description": "Financial mobility and emergency relief for registered interstate workers",
                "amount": 3000,
                "cooldown_seconds": 30 * 86400, # 30-day policy
                "is_active": True
            },
            2: {
                "id": 2,
                "name": "BOCW Safety & Skill Empowerment Grant",
                "description": "Building & Other Construction Workers safety tooling and certification grant",
                "amount": 5000,
                "cooldown_seconds": 60 * 86400,
                "is_active": True
            }
        }
        self.claims: Dict[int, Dict[str, Any]] = {}
        self.next_claim_id = 1
        self.last_claim_times: Dict[str, Dict[int, int]] = {} # did -> scheme_id -> timestamp

    # --- Worker Identity Registry (Authoritative EVM Anchoring & Receipt Confirmation) ---

    def _init_worker_contract(self):
        """Initializes Web3 contract instance for WorkerIdentityRegistry if connected."""
        self.worker_identity_contract = None
        self.worker_registry_address = None
        self.worker_registry_abi = None

        contracts_meta = self.metadata.get("contracts", {})
        worker_meta = contracts_meta.get("WorkerIdentityRegistry", {})
        addr = worker_meta.get("address")
        abi = worker_meta.get("abi")

        if addr and abi:
            try:
                self.worker_registry_address = Web3.to_checksum_address(addr)
                self.worker_registry_abi = abi
                if self.is_connected:
                    self.worker_identity_contract = self.w3.eth.contract(
                        address=self.worker_registry_address,
                        abi=self.worker_registry_abi
                    )
            except Exception:
                pass

    def _init_organization_contract(self):
        """Initializes Web3 contract instance for OrganizationRegistry if connected."""
        self.organization_contract = None
        self.organization_registry_address = None
        self.organization_registry_abi = None

        contracts_meta = self.metadata.get("contracts", {})
        org_meta = contracts_meta.get("OrganizationRegistry", {})
        addr = org_meta.get("address")
        abi = org_meta.get("abi")

        if addr and abi:
            try:
                self.organization_registry_address = Web3.to_checksum_address(addr)
                self.organization_registry_abi = abi
                if self.is_connected:
                    self.organization_contract = self.w3.eth.contract(
                        address=self.organization_registry_address,
                        abi=self.organization_registry_abi
                    )
            except Exception:
                pass

    def _get_issuer_account(self) -> str:
        """Resolves authorized issuer account for sending transactions."""
        try:
            if self.is_connected and len(self.w3.eth.accounts) > 0:
                return self.w3.eth.accounts[0]
        except Exception:
            pass
        return self.metadata.get("deployer", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")

    def _format_cred_hash_bytes32(self, cred_hash: str) -> bytes:
        """Converts credential hash into exact 32-byte representation for Solidity bytes32."""
        if isinstance(cred_hash, (bytes, bytearray)):
            return bytes(cred_hash[:32]).ljust(32, b'\0')
        clean_hex = str(cred_hash)
        if clean_hex.startswith("0x"):
            clean_hex = clean_hex[2:]
        try:
            if len(clean_hex) == 64:
                return bytes.fromhex(clean_hex)
        except Exception:
            pass
        return hashlib.sha256(str(cred_hash).encode("utf-8")).digest()

    def _execute_contract_write(self, contract_func_call) -> Any:
        """
        Executes a smart contract write call.
        - If SEPOLIA_PRIVATE_KEY or AUTHORITY_PRIVATE_KEY is set:
          Signs locally with the private key and broadcasts raw transaction via eth_sendRawTransaction.
        - If node has unlocked accounts (local Hardhat/Ganache):
          Uses .transact({"from": accounts[0]}).
        - If remote RPC without private key:
          Raises descriptive error.
        """
        private_key = os.getenv("SEPOLIA_PRIVATE_KEY") or os.getenv("AUTHORITY_PRIVATE_KEY")
        if private_key:
            clean_key = private_key.strip()
            if not clean_key.startswith("0x") and len(clean_key) == 64:
                clean_key = "0x" + clean_key
            account = self.w3.eth.account.from_key(clean_key)
            nonce = self.w3.eth.get_transaction_count(account.address)
            gas_price = self.w3.eth.gas_price
            chain_id = getattr(self.w3.eth, 'chain_id', 11155111)

            tx = contract_func_call.build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': chain_id
            })
            signed = self.w3.eth.account.sign_transaction(tx, private_key=clean_key)
            tx_hash_bytes = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=30)
            return receipt

        if self.is_connected and len(self.w3.eth.accounts) > 0:
            issuer = self.w3.eth.accounts[0]
            tx_hash_bytes = contract_func_call.transact({"from": issuer})
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=15)
            return receipt

        raise PermissionError(
            "Remote RPC endpoint (Alchemy) does not hold private keys for eth_sendTransaction. "
            "Configure 'SEPOLIA_PRIVATE_KEY' in Render to sign on-chain transactions, "
            "or set 'CHAIN_MODE=simulated' to use the verified cloud ledger."
        )

    def register_worker(self, did: str, cred_hash: str, ipfs_cid: str) -> Dict[str, Any]:
        """
        Anchors worker identity on WorkerIdentityRegistry contract and awaits receipt confirmation.
        Enforces idempotency, receipt status 1, and authoritative on-chain verification.
        """
        if not did:
            raise ValueError("Worker DID cannot be empty")
        if not cred_hash or cred_hash == "0x" + "0" * 64:
            raise ValueError("Invalid credential hash")

        # Check local registry pre-condition
        if did in self.worker_registry and self.worker_registry[did].get("is_registered"):
            raise ValueError("Worker DID already anchored on blockchain")

        now = int(time.time())
        tx_hash = None
        block_number = None
        chain_id = 1337
        contract_addr = self.worker_registry_address or "0x5FbDB2315678afecb367f032d93F642f64180aa3"

        chain_mode = os.getenv("CHAIN_MODE", "").lower()
        has_private_key = bool(os.getenv("SEPOLIA_PRIVATE_KEY") or os.getenv("AUTHORITY_PRIVATE_KEY"))
        has_local_accounts = len(self.w3.eth.accounts) > 0 if self.is_connected else False
        can_transact = self.is_connected and (has_private_key or has_local_accounts)

        # 1. Live EVM Mode (Signing key or local unlocked node available)
        if can_transact and self.worker_identity_contract and chain_mode != "simulated":
            try:
                # Check on-chain validity before submitting
                if self.is_worker_valid(did):
                    raise ValueError("Worker DID already anchored on blockchain")

                cred_hash_bytes = self._format_cred_hash_bytes32(cred_hash)

                # Submit transaction (signed raw tx if remote, or unlocked transact if local)
                call_func = self.worker_identity_contract.functions.registerWorker(
                    did,
                    cred_hash_bytes,
                    ipfs_cid
                )
                receipt = self._execute_contract_write(call_func)
                if receipt.status != 1:
                    raise RuntimeError("Transaction failed on-chain (reverted)")

                tx_hash = receipt.transactionHash.hex() if hasattr(receipt.transactionHash, 'hex') else str(receipt.transactionHash)
                if not tx_hash.startswith("0x"):
                    tx_hash = "0x" + tx_hash
                block_number = receipt.blockNumber
                chain_id = getattr(self.w3.eth, 'chain_id', 11155111)

                # Perform explicit authoritative read verification
                onchain_tuple = self.worker_identity_contract.functions.getWorkerByDid(did).call()
                if not onchain_tuple[5]:  # isRegistered
                    raise RuntimeError("Authoritative EVM read verification failed: isRegistered is False")

            except ValueError as ve:
                raise ve
            except Exception as e:
                err_msg = str(e)
                if "Worker already registered" in err_msg or "already anchored" in err_msg:
                    raise ValueError("Worker DID already anchored on blockchain")
                elif "Invalid credential hash" in err_msg:
                    raise ValueError("Invalid credential hash")
                elif "Only authorized issuer" in err_msg:
                    raise PermissionError("WorkerIdentityRegistry: Only authorized issuer")
                elif "Connection refused" in err_msg or "Failed to connect" in err_msg:
                    raise ConnectionError(f"RPC connection failure: {err_msg}")
                else:
                    raise RuntimeError(f"Blockchain anchoring error: {err_msg}")
        else:
            # 2. Simulated / Cloud Ledger Mode
            if chain_mode in ["sepolia", "strict"] and not has_private_key:
                raise PermissionError("SEPOLIA_PRIVATE_KEY is required in strict mode to sign on-chain transactions via Alchemy.")

            sim_tx = "0x" + hashlib.sha256(f"tx:{did}:{now}".encode("utf-8")).hexdigest()
            tx_hash = sim_tx
            block_number = 1
            if self.is_connected:
                try:
                    chain_id = getattr(self.w3.eth, 'chain_id', 11155111)
                except Exception:
                    chain_id = 1337

        record = {
            "did": did,
            "credential_hash": cred_hash,
            "ipfs_cid": ipfs_cid,
            "issue_timestamp": now,
            "updated_at": now,
            "is_registered": True,
            "is_revoked": False,
            "revocation_reason": "",
            "tx_hash": tx_hash,
            "block_number": block_number,
            "chain_id": chain_id,
            "contract_address": contract_addr,
            "status": 1
        }
        self.worker_registry[did] = record
        return record

    def check_connection(self) -> bool:
        """Dynamically tests connection to Hardhat node and initializes contracts if reconnected."""
        now = time.time()
        if now - getattr(self, "_last_conn_check", 0) < 3.0:
            return self.is_connected
        self._last_conn_check = now
        try:
            connected = bool(self.w3.is_connected())
            if connected and not self.is_connected:
                self.is_connected = True
                self._init_worker_contract()
                self._init_organization_contract()
            elif not connected:
                self.is_connected = False
        except Exception:
            self.is_connected = False
        return self.is_connected

    def get_worker(self, did: str) -> Optional[Dict[str, Any]]:
        """Queries authoritative worker identity state from EVM contract, cached ledger, or SQLite."""
        self.check_connection()
        if self.is_connected and self.worker_identity_contract:
            try:
                onchain_tuple = self.worker_identity_contract.functions.getWorkerByDid(did).call()
                if onchain_tuple[5]:  # isRegistered
                    cached = self.worker_registry.get(did, {})
                    cred_h_bytes = onchain_tuple[1]
                    cred_h_str = "0x" + cred_h_bytes.hex() if isinstance(cred_h_bytes, (bytes, bytearray)) else str(cred_h_bytes)
                    record = {
                        "did": onchain_tuple[0],
                        "credential_hash": cached.get("credential_hash") or cred_h_str,
                        "ipfs_cid": cached.get("ipfs_cid") or onchain_tuple[2],
                        "issue_timestamp": onchain_tuple[3],
                        "updated_at": onchain_tuple[4],
                        "is_registered": onchain_tuple[5],
                        "is_revoked": onchain_tuple[6],
                        "revocation_reason": onchain_tuple[7],
                        "tx_hash": cached.get("tx_hash"),
                        "block_number": cached.get("block_number"),
                        "chain_id": cached.get("chain_id", 1337),
                        "contract_address": self.worker_registry_address or "0x5FbDB2315678afecb367f032d93F642f64180aa3",
                        "status": 1
                    }
                    self.worker_registry[did] = record
                    return record
            except Exception:
                pass

        # Check memory cache
        if did in self.worker_registry:
            return self.worker_registry[did]

        # Fallback to persistent SQLite relational store
        try:
            from app.models.db import SessionLocal, DBWorkerProfile
            db = SessionLocal()
            try:
                profile = db.query(DBWorkerProfile).filter(
                    DBWorkerProfile.did == did,
                    DBWorkerProfile.is_credential_anchored == True
                ).first()
                if profile:
                    issue_ts = int(profile.created_at.timestamp()) if profile.created_at else int(time.time())
                    update_ts = int(profile.updated_at.timestamp()) if profile.updated_at else int(time.time())
                    record = {
                        "did": profile.did,
                        "credential_hash": profile.credential_hash,
                        "ipfs_cid": profile.ipfs_cid,
                        "issue_timestamp": issue_ts,
                        "updated_at": update_ts,
                        "is_registered": True,
                        "is_revoked": (profile.did_state == "REVOKED"),
                        "revocation_reason": profile.failure_reason or "",
                        "tx_hash": profile.tx_hash or f"0xsim_{hashlib.sha256(did.encode()).hexdigest()[:32]}",
                        "block_number": profile.block_number or 1,
                        "chain_id": profile.chain_id or 1337,
                        "contract_address": profile.contract_address or (self.worker_registry_address or "0x5FbDB2315678afecb367f032d93F642f64180aa3"),
                        "status": 1
                    }
                    self.worker_registry[did] = record
                    return record
            finally:
                db.close()
        except Exception:
            pass

        return None

    def is_worker_valid(self, did: str) -> bool:
        """
        Checks if worker DID is registered and active on blockchain or cached/database ledger.
        Gracefully falls back to cached ledger and SQLite DBWorkerProfile if the contract call
        returns False (e.g. local/demo DID on an external testnet) or raises an exception,
        while strictly preserving explicit on-chain and local revocation invariants.
        """
        if not did:
            return False

        self.check_connection()
        if self.is_connected and self.worker_identity_contract:
            try:
                onchain_valid = bool(self.worker_identity_contract.functions.isWorkerValid(did).call())
                if onchain_valid:
                    # Invariant: If on-chain reports valid, ensure local memory cache does not carry an explicit revocation
                    cached = self.worker_registry.get(did)
                    if cached and cached.get("is_revoked"):
                        return False
                    return True
            except Exception:
                pass

        # Robust Fallback: Query authoritative local state via get_worker(did)
        # get_worker queries: 1) on-chain getWorkerByDid (capturing on-chain revocation),
        # 2) in-memory cache self.worker_registry, 3) persistent SQLite DBWorkerProfile.
        w = self.get_worker(did)
        return bool(w and w.get("is_registered") and not w.get("is_revoked"))

    def sync_from_database(self, db=None) -> int:
        """
        Hydrates all anchored worker profiles from the SQLite database into the active worker registry.
        If Hardhat node is connected, re-anchors any unanchored workers on-chain.
        """
        from app.models.db import SessionLocal, DBWorkerProfile
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        synced_count = 0
        try:
            self.check_connection()
            profiles = db.query(DBWorkerProfile).filter(
                DBWorkerProfile.did.isnot(None),
                DBWorkerProfile.is_credential_anchored == True
            ).all()

            for p in profiles:
                issue_ts = int(p.created_at.timestamp()) if p.created_at else int(time.time())
                update_ts = int(p.updated_at.timestamp()) if p.updated_at else int(time.time())
                record = {
                    "did": p.did,
                    "credential_hash": p.credential_hash,
                    "ipfs_cid": p.ipfs_cid,
                    "issue_timestamp": issue_ts,
                    "updated_at": update_ts,
                    "is_registered": True,
                    "is_revoked": (p.did_state == "REVOKED"),
                    "revocation_reason": p.failure_reason or "",
                    "tx_hash": p.tx_hash or f"0xsim_{hashlib.sha256(p.did.encode()).hexdigest()[:32]}",
                    "block_number": p.block_number or 1,
                    "chain_id": p.chain_id or 1337,
                    "contract_address": p.contract_address or (self.worker_registry_address or "0x5FbDB2315678afecb367f032d93F642f64180aa3"),
                    "status": 1
                }
                self.worker_registry[p.did] = record
                synced_count += 1

                # If EVM connected and not on-chain, anchor on contract
                if self.is_connected and self.worker_identity_contract and p.did and p.credential_hash and p.ipfs_cid:
                    try:
                        if not self.worker_identity_contract.functions.isWorkerValid(p.did).call():
                            issuer = self._get_issuer_account()
                            cred_hash_bytes = self._format_cred_hash_bytes32(p.credential_hash)
                            tx = self.worker_identity_contract.functions.registerWorker(
                                p.did, cred_hash_bytes, p.ipfs_cid
                            ).transact({"from": issuer})
                            receipt = self.w3.eth.wait_for_transaction_receipt(tx, timeout=10)
                            if receipt.status == 1:
                                self.worker_registry[p.did]["tx_hash"] = receipt.transactionHash.hex()
                    except Exception:
                        pass

            # Also sync active government officers into self.organizations
            try:
                from app.models.db import DBGovernmentOfficer, DBEmployment, DBWelfareClaim
                active_officers = db.query(DBGovernmentOfficer).filter(
                    DBGovernmentOfficer.status.in_(["ACTIVE", "APPROVED"])
                ).all()
                for off in active_officers:
                    if off.wallet_address:
                        self.organizations[off.wallet_address] = {
                            "id": off.id,
                            "name": off.department or off.officer_name or off.full_name,
                            "reg_number": off.officer_reference_id,
                            "state_code": off.state or "ALL",
                            "org_type": "GOVERNMENT",
                            "status": "APPROVED",
                            "categories": [],
                            "levels": [],
                            "natures": [],
                            "registered_at": int(time.time())
                        }

                # Hydrate employments from database
                db_emps = db.query(DBEmployment).all()
                for de in db_emps:
                    self.employments[de.id] = {
                        "id": de.id,
                        "worker_did": de.worker_did,
                        "employer_address": de.employer_address,
                        "employer_name": de.employer_name,
                        "category": de.category,
                        "level": de.level,
                        "nature_of_employment": de.nature_of_employment,
                        "job_role": de.job_role,
                        "location": de.location,
                        "start_date": de.start_date,
                        "end_date": de.end_date,
                        "status": de.status,
                        "status_reason": de.status_reason or "Historical Stint",
                        "tx_hash": de.tx_hash
                    }
                    if de.id not in self.employment_events:
                        self.employment_events[de.id] = [{
                            "status": de.status,
                            "reason": de.status_reason or "Historical Stint",
                            "timestamp": de.start_date or int(time.time())
                        }]
                    if de.id >= self.next_emp_id:
                        self.next_emp_id = de.id + 1

                # Hydrate welfare claims from database
                db_claims = db.query(DBWelfareClaim).all()
                for dc in db_claims:
                    self.claims[dc.id] = {
                        "claim_id": dc.id,
                        "sha256_claim_id": dc.claim_id_hex or f"claim_{dc.id}",
                        "scheme_id": dc.scheme_id,
                        "scheme_name": dc.scheme_name or "Welfare Scheme",
                        "worker_did": dc.worker_did,
                        "gov_officer": dc.gov_address,
                        "officer_state": dc.officer_state,
                        "amount": 0,
                        "timestamp": dc.disbursed_at,
                        "is_disbursed": True
                    }
                    if dc.worker_did not in self.last_claim_times:
                        self.last_claim_times[dc.worker_did] = {}
                    self.last_claim_times[dc.worker_did][dc.scheme_id] = max(
                        self.last_claim_times[dc.worker_did].get(dc.scheme_id, 0),
                        dc.disbursed_at
                    )
                    if dc.id >= self.next_claim_id:
                        self.next_claim_id = dc.id + 1
            except Exception as e:
                logger.warning(f"Failed to sync state from database: {e}")
        finally:
            if close_db:
                db.close()
        return synced_count

    def revoke_worker(self, did: str, caller_authority: str, reason: str):
        # Scoped revocation: only identity authority or admin can revoke identity credential
        if caller_authority not in ["IDENTITY_AUTHORITY", "ADMIN"]:
            raise PermissionError("Unauthorized: Only authorized Identity Authority can revoke worker DID")

        chain_mode = os.getenv("CHAIN_MODE", "").lower()
        has_private_key = bool(os.getenv("SEPOLIA_PRIVATE_KEY") or os.getenv("AUTHORITY_PRIVATE_KEY"))
        has_local_accounts = len(self.w3.eth.accounts) > 0 if self.is_connected else False
        can_transact = self.is_connected and (has_private_key or has_local_accounts)

        if can_transact and self.worker_identity_contract and chain_mode != "simulated":
            try:
                call_func = self.worker_identity_contract.functions.revokeWorker(did, reason)
                receipt = self._execute_contract_write(call_func)
                if receipt.status != 1:
                    raise RuntimeError("Revocation transaction reverted on-chain")
            except Exception as e:
                raise e

        if did in self.worker_registry:
            self.worker_registry[did]["is_revoked"] = True
            self.worker_registry[did]["revocation_reason"] = reason
            self.worker_registry[did]["updated_at"] = int(time.time())

    # --- Organization Registry ---

    def register_organization(self, address: str, name: str, reg_num: str, state_code: str, org_type: str, categories: List[str]):
        self.organizations[address] = {
            "name": name,
            "reg_number": reg_num,
            "state_code": state_code,
            "org_type": org_type,
            "status": "PENDING",
            "categories": categories,
            "levels": ["Skilled", "Semi-Skilled", "Unskilled"],
            "natures": ["Contract", "Permanent", "Project-Based"],
            "registered_at": int(time.time())
        }

    def _to_valid_checksum_address(self, address: str) -> str:
        if not address:
            return Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
        addr_str = str(address).strip()
        try:
            return Web3.to_checksum_address(addr_str)
        except (ValueError, TypeError):
            hex_part = hashlib.sha256(addr_str.encode("utf-8")).hexdigest()[:40]
            return Web3.to_checksum_address(f"0x{hex_part}")

    def set_org_status(self, address: str, status: str, reason: str = ""):
        status_map = {
            "PENDING": 0,
            "APPROVED": 1,
            "ACTIVE": 1,
            "REJECTED": 2,
            "SUSPENDED": 3,
            "DISABLED": 3
        }
        status_upper = status.upper()
        status_code = status_map.get(status_upper, 0)

        chain_mode = os.getenv("CHAIN_MODE", "").lower()
        has_private_key = bool(os.getenv("SEPOLIA_PRIVATE_KEY") or os.getenv("AUTHORITY_PRIVATE_KEY"))
        has_local_accounts = len(self.w3.eth.accounts) > 0 if self.is_connected else False
        can_transact = self.is_connected and (has_private_key or has_local_accounts)

        if can_transact and self.organization_contract and chain_mode != "simulated":
            try:
                checksum_addr = self._to_valid_checksum_address(address)
                call_func = self.organization_contract.functions.setOrganizationStatus(
                    checksum_addr,
                    status_code,
                    reason or ""
                )
                receipt = self._execute_contract_write(call_func)
                if receipt.status != 1:
                    raise RuntimeError(f"Organization status transaction reverted on-chain for {address}")
            except Exception as e:
                raise RuntimeError(f"Blockchain setOrganizationStatus error: {str(e)}")

        if address and address in self.organizations:
            self.organizations[address]["status"] = status_upper
            self.organizations[address]["reason"] = reason

    def authorize_category(self, address: str, category: str):
        chain_mode = os.getenv("CHAIN_MODE", "").lower()
        has_private_key = bool(os.getenv("SEPOLIA_PRIVATE_KEY") or os.getenv("AUTHORITY_PRIVATE_KEY"))
        has_local_accounts = len(self.w3.eth.accounts) > 0 if self.is_connected else False
        can_transact = self.is_connected and (has_private_key or has_local_accounts)

        if can_transact and self.organization_contract and chain_mode != "simulated":
            try:
                checksum_addr = self._to_valid_checksum_address(address)
                call_func = self.organization_contract.functions.authorizeCategory(
                    checksum_addr,
                    category
                )
                receipt = self._execute_contract_write(call_func)
                if receipt.status != 1:
                    raise RuntimeError(f"Authorize category transaction reverted on-chain for {category}")
            except Exception as e:
                raise RuntimeError(f"Blockchain authorizeCategory error: {str(e)}")

        if address not in self.organizations:
            self._sync_org_from_db(address)
        if address not in self.organizations:
            self.organizations[address] = {
                "name": "Employer Organization",
                "reg_number": "REG-M5",
                "state_code": "KA",
                "org_type": "EMPLOYER",
                "status": "APPROVED",
                "categories": [category],
                "levels": ["Skilled", "Semi-Skilled", "Unskilled"],
                "natures": ["Contract", "Permanent", "Project-Based"],
                "registered_at": int(time.time())
            }
        else:
            cat_clean = category.strip().lower()
            if not any(c.strip().lower() == cat_clean for c in self.organizations[address]["categories"]):
                self.organizations[address]["categories"].append(category)

    def revoke_category(self, address: str, category: str):
        chain_mode = os.getenv("CHAIN_MODE", "").lower()
        has_private_key = bool(os.getenv("SEPOLIA_PRIVATE_KEY") or os.getenv("AUTHORITY_PRIVATE_KEY"))
        has_local_accounts = len(self.w3.eth.accounts) > 0 if self.is_connected else False
        can_transact = self.is_connected and (has_private_key or has_local_accounts)

        if can_transact and self.organization_contract and chain_mode != "simulated":
            try:
                checksum_addr = self._to_valid_checksum_address(address)
                call_func = self.organization_contract.functions.revokeCategory(
                    checksum_addr,
                    category
                )
                receipt = self._execute_contract_write(call_func)
                if receipt.status != 1:
                    raise RuntimeError(f"Revoke category transaction reverted on-chain for {category}")
            except Exception as e:
                raise RuntimeError(f"Blockchain revokeCategory error: {str(e)}")

        if address in self.organizations:
            if category in self.organizations[address].get("categories", []):
                self.organizations[address]["categories"].remove(category)

    def _sync_org_from_db(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Authoritatively rehydrates organization standing and active approved category scopes from SQLite.
        Prevents state loss on backend restarts and guarantees parity between off-chain governance and employment creation.
        """
        if not address:
            return None
        try:
            from app.models.db import (
                SessionLocal, DBEmployerOrganization, DBCategoryAuthorizationRequest,
                DBUser, DBGovernmentOfficer
            )
            from sqlalchemy import func
            db = SessionLocal()
            try:
                addr_clean = str(address).strip().lower()
                # 1. Match all orgs with this org_address
                matching_orgs = db.query(DBEmployerOrganization).filter(
                    func.lower(DBEmployerOrganization.org_address) == addr_clean
                ).all()

                # 2. Match by hex ID if address is derived from org id (0x{org.id:040x})
                if not matching_orgs and addr_clean.startswith("0x"):
                    try:
                        org_id = int(addr_clean, 16)
                        single = db.query(DBEmployerOrganization).filter(DBEmployerOrganization.id == org_id).first()
                        if single:
                            matching_orgs = [single]
                    except Exception:
                        pass

                # 3. Match via DBUser.organization_address
                if not matching_orgs:
                    users = db.query(DBUser).filter(func.lower(DBUser.organization_address) == addr_clean).all()
                    matching_orgs = [u.employer_organization for u in users if u.employer_organization]

                if matching_orgs:
                    org_ids = [o.id for o in matching_orgs]
                    # Query active approved category scopes across all orgs using this address
                    active_scopes = db.query(DBCategoryAuthorizationRequest).filter(
                        DBCategoryAuthorizationRequest.organization_id.in_(org_ids),
                        DBCategoryAuthorizationRequest.is_active_scope == True
                    ).all()

                    approved_cats = [s.category for s in active_scopes if s.category]
                    active_levels = [s.skill_level for s in active_scopes if s.skill_level]
                    active_natures = [s.nature_of_employment for s in active_scopes if s.nature_of_employment]

                    # Prefer the primary/newest org record for metadata
                    primary_org = sorted(matching_orgs, key=lambda o: (o.status in ["APPROVED", "ACTIVE"], o.id), reverse=True)[0]

                    existing = self.organizations.get(address, {})
                    merged_cats = list(dict.fromkeys(existing.get("categories", []) + approved_cats))
                    default_levels = ["Skilled", "Semi-Skilled", "Unskilled"]
                    merged_levels = list(dict.fromkeys(existing.get("levels", []) + active_levels + default_levels))
                    default_natures = ["Contract", "Permanent", "Project-Based"]
                    merged_natures = list(dict.fromkeys(existing.get("natures", []) + active_natures + default_natures))

                    org_record = {
                        "id": primary_org.id,
                        "name": primary_org.name or "Employer Organization",
                        "reg_number": primary_org.registration_ref_number or primary_org.registration_number or "REG-DEFAULT",
                        "state_code": primary_org.state_code or "KA",
                        "org_type": "EMPLOYER",
                        "status": primary_org.status or "APPROVED",
                        "categories": merged_cats,
                        "levels": merged_levels,
                        "natures": merged_natures,
                        "registered_at": int(primary_org.created_at.timestamp()) if primary_org.created_at else int(time.time())
                    }
                    self.organizations[address] = org_record
                    return org_record

                # 4. Match via DBGovernmentOfficer (wallet_address, reference ID, or linked user)
                gov_officer = db.query(DBGovernmentOfficer).filter(
                    (func.lower(DBGovernmentOfficer.wallet_address) == addr_clean) |
                    (func.lower(DBGovernmentOfficer.officer_reference_id) == addr_clean)
                ).first()

                if not gov_officer and (addr_clean.startswith("0xgov_") or addr_clean.startswith("0xgov")):
                    gov_officer = db.query(DBGovernmentOfficer).filter(
                        func.lower(DBGovernmentOfficer.wallet_address).contains(addr_clean)
                    ).first()

                if not gov_officer:
                    gov_user = db.query(DBUser).filter(
                        (func.lower(DBUser.organization_address) == addr_clean) &
                        (DBUser.role == "GOVERNMENT")
                    ).first()
                    if gov_user and gov_user.government_officer:
                        gov_officer = gov_user.government_officer

                if gov_officer and gov_officer.status in ["ACTIVE", "APPROVED"]:
                    gov_record = {
                        "id": gov_officer.id,
                        "name": gov_officer.department or gov_officer.officer_name or gov_officer.full_name or "Government Authority",
                        "reg_number": gov_officer.officer_reference_id or "GOV-OFF",
                        "state_code": gov_officer.state or "ALL",
                        "org_type": "GOVERNMENT",
                        "status": "APPROVED",
                        "categories": [],
                        "levels": [],
                        "natures": [],
                        "registered_at": int(time.time())
                    }
                    self.organizations[address] = gov_record
                    if gov_officer.wallet_address:
                        self.organizations[gov_officer.wallet_address] = gov_record
                    return gov_record
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to sync organization/officer from DB for {address}: {e}")
        return None

    def is_org_approved(self, address: str) -> bool:
        if self.is_connected and self.organization_contract:
            try:
                checksum_addr = self._to_valid_checksum_address(address)
                if bool(self.organization_contract.functions.isOrganizationApproved(checksum_addr).call()):
                    return True
            except Exception:
                pass
        org = self.organizations.get(address)
        if not org or org.get("status") not in ["APPROVED", "ACTIVE"]:
            org = self._sync_org_from_db(address)
        return bool(org and org.get("status") in ["APPROVED", "ACTIVE"])

    def is_category_authorized(self, address: str, category: str) -> bool:
        if self.is_connected and self.organization_contract:
            try:
                checksum_addr = self._to_valid_checksum_address(address)
                if bool(self.organization_contract.functions.isCategoryAuthorized(checksum_addr, category).call()):
                    return True
            except Exception:
                pass
        org = self.organizations.get(address)
        if not org:
            org = self._sync_org_from_db(address)
        if not org or org.get("status") not in ["APPROVED", "ACTIVE"]:
            return False
        cat_clean = (category or "").strip().lower()
        return any(c.strip().lower() == cat_clean for c in org.get("categories", []))

    def get_organization_categories(self, address: str) -> List[str]:
        if self.is_connected and self.organization_contract:
            try:
                checksum_addr = self._to_valid_checksum_address(address)
                onchain_cats = list(self.organization_contract.functions.getOrganizationCategories(checksum_addr).call())
                if onchain_cats:
                    return onchain_cats
            except Exception:
                pass
        org = self.organizations.get(address)
        if not org or not org.get("categories"):
            org = self._sync_org_from_db(address)
        return list((org or {}).get("categories", []))

    def is_level_authorized(self, address: str, level: str) -> bool:
        org = self.organizations.get(address)
        lvl_clean = (level or "").strip().lower()
        if not org:
            org = self._sync_org_from_db(address)
        if not org or org.get("status") not in ["APPROVED", "ACTIVE"]:
            return False
        levels = org.get("levels", [])
        return any(l.strip().lower() == lvl_clean for l in levels)

    def is_nature_authorized(self, address: str, nature: str) -> bool:
        org = self.organizations.get(address)
        nat_clean = (nature or "").strip().lower()
        if not org:
            org = self._sync_org_from_db(address)
        if not org or org.get("status") not in ["APPROVED", "ACTIVE"]:
            return False
        natures = org.get("natures", [])
        return any(n.strip().lower() == nat_clean for n in natures)

    # --- Employment Registry (Event-Driven Lifecycle) ---

    def create_employment(
        self,
        worker_did: str,
        employer_address: str,
        category: str,
        job_role: str,
        location: str,
        level: str = "Skilled",
        nature_of_employment: str = "Contract",
        end_date: int = 0
    ) -> Dict[str, Any]:
        if not self.is_org_approved(employer_address):
            raise ValueError("Employer is not approved on-chain")
        if not self.is_category_authorized(employer_address, category):
            raise ValueError(f"Category '{category}' is not authorized for employer")
        if not self.is_level_authorized(employer_address, level):
            raise ValueError(f"Employment level '{level}' is not authorized for employer")
        if not self.is_nature_authorized(employer_address, nature_of_employment):
            raise ValueError(f"Nature of employment '{nature_of_employment}' is not authorized")

        emp_id = self.next_emp_id
        self.next_emp_id += 1

        record = {
            "id": emp_id,
            "worker_did": worker_did,
            "employer_address": employer_address,
            "employer_name": self.organizations.get(employer_address, {}).get("name", "Employer"),
            "category": category,
            "level": level,
            "nature_of_employment": nature_of_employment,
            "job_role": job_role,
            "location": location,
            "start_date": int(time.time()),
            "end_date": end_date,
            "status": "ACTIVE",
            "status_reason": "Stint Initiated"
        }
        self.employments[emp_id] = record
        self.employment_events[emp_id] = [{
            "status": "ACTIVE",
            "reason": "Employment Created",
            "timestamp": int(time.time())
        }]
        try:
            from app.models.db import SessionLocal, DBEmployment
            db = SessionLocal()
            try:
                db_emp = DBEmployment(
                    worker_did=worker_did,
                    employer_address=employer_address,
                    employer_name=record["employer_name"],
                    category=category,
                    level=level,
                    nature_of_employment=nature_of_employment,
                    job_role=job_role,
                    location=location,
                    start_date=record["start_date"],
                    end_date=record["end_date"],
                    status="ACTIVE",
                    status_reason="Stint Initiated"
                )
                db.add(db_emp)
                db.commit()
                db.refresh(db_emp)
                record["id"] = db_emp.id
                if emp_id != db_emp.id:
                    if emp_id in self.employments:
                        del self.employments[emp_id]
                    if emp_id in self.employment_events:
                        self.employment_events[db_emp.id] = self.employment_events.pop(emp_id)
                if db_emp.id not in self.employment_events:
                    self.employment_events[db_emp.id] = []
                self.employments[db_emp.id] = record
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to persist DBEmployment: {e}")
        return record

    def update_employment_status(self, emp_id: int, caller_address: str, new_status: str, reason: str, db=None):
        # 1. Lazy-load from DB if record not currently in memory
        if emp_id not in self.employments:
            try:
                from app.models.db import SessionLocal, DBEmployment
                chk_db = db or SessionLocal()
                chk_close = (db is None)
                try:
                    de = chk_db.query(DBEmployment).filter(DBEmployment.id == emp_id).first()
                    if de:
                        self.employments[de.id] = {
                            "id": de.id,
                            "worker_did": de.worker_did,
                            "employer_address": de.employer_address,
                            "employer_name": de.employer_name,
                            "category": de.category,
                            "level": de.level,
                            "nature_of_employment": de.nature_of_employment,
                            "job_role": de.job_role,
                            "location": de.location,
                            "start_date": de.start_date,
                            "end_date": de.end_date,
                            "status": de.status,
                            "status_reason": de.status_reason or "Historical Stint",
                            "tx_hash": de.tx_hash
                        }
                finally:
                    if chk_close:
                        chk_db.close()
            except Exception as e:
                logger.warning(f"Error checking DBEmployment for #{emp_id}: {e}")

        if emp_id not in self.employments:
            raise ValueError("Employment record not found")
        # Scoped authority: only the employing organization can update its employment record
        if self.employments[emp_id]["employer_address"] != caller_address and caller_address != "ADMIN":
            raise PermissionError("Unauthorized: Only employing organization can update employment status")

        # 2. Status enum validation (including DISCONTINUED)
        valid_statuses = ["ACTIVE", "COMPLETED", "TERMINATED", "DISMISSED", "RESIGNED", "SUSPENDED", "DISCONTINUED"]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

        self.employments[emp_id]["status"] = new_status
        self.employments[emp_id]["status_reason"] = reason
        if new_status in ["COMPLETED", "TERMINATED", "DISMISSED", "RESIGNED", "DISCONTINUED"]:
            self.employments[emp_id]["end_date"] = int(time.time())

        # 3. Append to immutable event history (preserves audit trail)
        if emp_id not in self.employment_events:
            self.employment_events[emp_id] = []
        self.employment_events[emp_id].append({
            "status": new_status,
            "reason": reason,
            "timestamp": int(time.time())
        })

        # 4. Persist update to DBEmployment in SQLite
        close_db = False
        try:
            from app.models.db import SessionLocal, DBEmployment
            session = db
            if session is None:
                session = SessionLocal()
                close_db = True
            try:
                db_emp = session.query(DBEmployment).filter(DBEmployment.id == emp_id).first()
                if db_emp:
                    db_emp.status = new_status
                    db_emp.status_reason = reason
                    if new_status in ["COMPLETED", "TERMINATED", "DISMISSED", "RESIGNED", "DISCONTINUED"]:
                        db_emp.end_date = self.employments[emp_id]["end_date"]
                    session.commit()
                    session.refresh(db_emp)
            except Exception as e:
                session.rollback()
                logger.warning(f"Failed to persist DBEmployment status update for #{emp_id}: {e}")
            finally:
                if close_db:
                    session.close()
        except Exception as e:
            logger.warning(f"Session error in update_employment_status: {e}")

        return self.employments[emp_id]

    def get_worker_employments(self, worker_did: str) -> List[Dict[str, Any]]:
        # Returns all historical and active employments (immutable history)
        seen_ids = set()
        results = []
        for emp in list(self.employments.values()):
            if emp.get("worker_did") == worker_did:
                eid = emp.get("id")
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    results.append(emp)
        try:
            from app.models.db import SessionLocal, DBEmployment
            db = SessionLocal()
            try:
                db_emps = db.query(DBEmployment).filter(DBEmployment.worker_did == worker_did).all()
                for de in db_emps:
                    if de.id not in seen_ids:
                        seen_ids.add(de.id)
                        rec = {
                            "id": de.id,
                            "worker_did": de.worker_did,
                            "employer_address": de.employer_address,
                            "employer_name": de.employer_name,
                            "category": de.category,
                            "level": de.level,
                            "nature_of_employment": de.nature_of_employment,
                            "job_role": de.job_role,
                            "location": de.location,
                            "start_date": de.start_date,
                            "end_date": de.end_date,
                            "status": de.status,
                            "status_reason": de.status_reason or "Historical Stint",
                            "tx_hash": de.tx_hash
                        }
                        results.append(rec)
                        self.employments[de.id] = rec
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to rehydrate DBEmployment for {worker_did}: {e}")
        return results

    def get_active_workforce(self, employer_address: str) -> List[Dict[str, Any]]:
        # Returns only actively employed workers on employer roster
        return [emp for emp in self.employments.values() if emp["employer_address"] == employer_address and emp["status"] == "ACTIVE"]

    # --- Welfare Scheme Registry ---

    def record_welfare_claim(self, scheme_id: int, worker_did: str, gov_address: str, officer_state: str) -> Dict[str, Any]:
        if not self.is_org_approved(gov_address):
            raise ValueError("Government authority is not approved on-chain")
        
        scheme = self.schemes.get(scheme_id)
        if not scheme or not scheme["is_active"]:
            raise ValueError("Scheme not active")

        # Dynamic cooldown calculation based on 30-day policy
        last_time = self.last_claim_times.get(worker_did, {}).get(scheme_id, 0)
        now = int(time.time())
        if last_time > 0 and (now < last_time + scheme["cooldown_seconds"]):
            remaining_seconds = (last_time + scheme["cooldown_seconds"]) - now
            remaining_days = max(1, remaining_seconds // 86400)
            raise ValueError(f"Duplicate claim prevented. Cooldown active for {remaining_days} more days.")

        claim_id = self.next_claim_id
        self.next_claim_id += 1

        # Deterministically derive unique SHA-256 Claim ID
        canonical_claim_payload = f"{claim_id}:{worker_did}:{scheme_id}:{gov_address}:{officer_state}:{now}"
        sha256_claim_id = hashlib.sha256(canonical_claim_payload.encode("utf-8")).hexdigest()

        claim = {
            "claim_id": claim_id,
            "sha256_claim_id": sha256_claim_id,
            "scheme_id": scheme_id,
            "scheme_name": scheme["name"],
            "worker_did": worker_did,
            "gov_officer": gov_address,
            "officer_state": officer_state,
            "amount": scheme["amount"],
            "timestamp": now,
            "is_disbursed": True
        }
        self.claims[claim_id] = claim

        if worker_did not in self.last_claim_times:
            self.last_claim_times[worker_did] = {}
        self.last_claim_times[worker_did][scheme_id] = now

        try:
            from app.models.db import SessionLocal, DBWelfareClaim
            db = SessionLocal()
            try:
                db_claim = DBWelfareClaim(
                    scheme_id=scheme_id,
                    scheme_name=claim["scheme_name"],
                    worker_did=worker_did,
                    gov_address=gov_address,
                    officer_state=officer_state,
                    claim_id_hex=sha256_claim_id,
                    claim_hash=sha256_claim_id,
                    disbursed_at=now
                )
                db.add(db_claim)
                db.commit()
                db.refresh(db_claim)
                claim["claim_id"] = db_claim.id
                if claim_id != db_claim.id and claim_id in self.claims:
                    del self.claims[claim_id]
                self.claims[db_claim.id] = claim
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to persist DBWelfareClaim: {e}")
        return claim

    def get_worker_claims(self, worker_did: str) -> List[Dict[str, Any]]:
        seen_hashes = set()
        results = []
        for c in list(self.claims.values()):
            if c.get("worker_did") == worker_did:
                h = c.get("sha256_claim_id") or c.get("claim_id")
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    results.append(c)
        try:
            from app.models.db import SessionLocal, DBWelfareClaim
            db = SessionLocal()
            try:
                db_claims = db.query(DBWelfareClaim).filter(DBWelfareClaim.worker_did == worker_did).all()
                for dc in db_claims:
                    h = dc.claim_id_hex or f"claim_{dc.id}"
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        c_dict = {
                            "claim_id": dc.id,
                            "sha256_claim_id": h,
                            "scheme_id": dc.scheme_id,
                            "scheme_name": dc.scheme_name or "Welfare Scheme",
                            "worker_did": dc.worker_did,
                            "gov_officer": dc.gov_address,
                            "officer_state": dc.officer_state,
                            "amount": 0,
                            "timestamp": dc.disbursed_at,
                            "is_disbursed": True
                        }
                        results.append(c_dict)
                        self.claims[dc.id] = c_dict
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to rehydrate DBWelfareClaim for {worker_did}: {e}")
        return results

blockchain_service = BlockchainService()
