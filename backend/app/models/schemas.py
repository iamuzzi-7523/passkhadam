import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Generic, TypeVar
from pydantic import BaseModel, Field, EmailStr, model_validator, field_serializer

# Auth & User Schemas
class UserRegister(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str
    role: str = "WORKER" # WORKER | EMPLOYER | GOVERNMENT | ADMIN | AADHAAR_ADMIN
    firebase_uid: Optional[str] = None
    id_token: Optional[str] = None
    is_email_verified: Optional[bool] = False
    is_phone_verified: Optional[bool] = False
    organization_address: Optional[str] = None
    organization_name: Optional[str] = None
    organization_status: Optional[str] = None
    registration_number: Optional[str] = None
    registration_ref_number: Optional[str] = None
    categories_requested: Optional[List[str]] = None
    levels_requested: Optional[List[str]] = None
    natures_requested: Optional[List[str]] = None
    business_type: Optional[str] = None
    nature_of_business: Optional[str] = None
    contact_person: Optional[str] = None
    worker_category: Optional[str] = None
    skills: Optional[List[str]] = None
    origin_state: Optional[str] = None
    current_state: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "email" in data and isinstance(data["email"], str):
                data["email"] = data["email"].strip().lower()
        return data

class UserLogin(BaseModel):
    email: str
    password: str
    id_token: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "email" in data and isinstance(data["email"], str):
                data["email"] = data["email"].strip().lower()
        return data

class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    role: str
    is_email_verified: bool
    is_phone_verified: bool
    created_at: datetime
    firebase_uid: Optional[str] = None
    status: Optional[str] = "ACTIVE"
    organization_address: Optional[str] = None
    organization_name: Optional[str] = None
    organization_status: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class OrganizationInfo(BaseModel):
    address: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    org_type: Optional[str] = None
    categories: Optional[List[str]] = None
    levels: Optional[List[str]] = None
    natures: Optional[List[str]] = None

class UserContextResponse(BaseModel):
    id: int
    user_id: Optional[str] = None
    firebase_uid: Optional[str] = None
    email: str
    full_name: str
    role: str
    status: str = "ACTIVE"
    is_email_verified: bool = True
    is_phone_verified: bool = True
    phone: Optional[str] = None
    organization: Optional[OrganizationInfo] = None
    organization_address: Optional[str] = None
    organization_name: Optional[str] = None
    organization_status: Optional[str] = None
    profile_id: Optional[str] = None
    profile_status: Optional[str] = None  # COMPLETE, PENDING, PENDING_VERIFICATION, PENDING_REVIEW
    authority_level: Optional[str] = None  # NATIONAL, STATE, DISTRICT, BLOCK
    state: Optional[str] = None
    district: Optional[str] = None
    block: Optional[str] = None
    worker_profile: Optional[Dict[str, Any]] = None
    is_demo: bool = False
    permissions: List[str] = []
    benefit_permissions: List[str] = []

class EmployerActivationRequest(BaseModel):
    activation_token: str
    password: Optional[str] = None

class EmployerActivationResponse(BaseModel):
    status: str
    message: str
    email: Optional[str] = None
    organization_status: Optional[str] = None

# Worker Profile Schemas
class WorkerProfileUpdate(BaseModel):
    dob: Optional[str] = None
    gender: Optional[str] = None
    origin_state: Optional[str] = None
    current_state: Optional[str] = None
    address: Optional[str] = None
    worker_category: Optional[str] = None
    skills: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def reject_client_did(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "did" in data or "worker_did" in data:
                raise ValueError("Client-supplied DID is strictly forbidden. DIDs are derived server-side.")
        return data

class AadhaarVerifyRequest(BaseModel):
    aadhaar_number: str
    full_name: str = Field(..., min_length=2, description="Full legal name of the Aadhaar cardholder")

    @model_validator(mode="before")
    @classmethod
    def reject_client_did(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "did" in data or "worker_did" in data:
                raise ValueError("Client-supplied DID is strictly forbidden. DIDs are derived server-side.")
            if "aadhaar_number" in data and isinstance(data["aadhaar_number"], str):
                data["aadhaar_number"] = "".join(filter(str.isdigit, data["aadhaar_number"]))
        return data

# ============================================================================
# WORKER REGISTRATION & LIFECYCLE SCHEMAS (Milestone 3)
# ============================================================================

class WorkerRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, description="Full legal name of the worker")
    email: EmailStr = Field(..., description="Worker email address")
    phone: str = Field(..., min_length=10, description="Worker phone number")
    password: Optional[str] = Field("passkhadam123", description="Worker login password")
    aadhaar_number: Optional[str] = Field(None, description="Optional 12-digit Aadhaar number for immediate onboarding")
    origin_state: Optional[str] = "Karnataka"
    current_state: Optional[str] = "Karnataka"
    worker_category: Optional[str] = "Mason"
    skills: Optional[List[str]] = Field(default_factory=lambda: ["Mason", "Plumbing Assistance"])
    firebase_uid: Optional[str] = None
    id_token: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "did" in data or "worker_did" in data:
                raise ValueError("Client-supplied DID is strictly forbidden. DIDs are derived server-side.")
            if "email" in data and isinstance(data["email"], str):
                data["email"] = data["email"].strip().lower()
            if "aadhaar_number" in data and isinstance(data["aadhaar_number"], str):
                data["aadhaar_number"] = "".join(filter(str.isdigit, data["aadhaar_number"]))
        return data

class WorkerRegisterResponse(BaseModel):
    success: bool = True
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    profile: Dict[str, Any]
    did_state: str

class WorkerLifecycleStatusResponse(BaseModel):
    current_state: str
    is_aadhaar_verified: bool
    is_credential_anchored: bool
    did: Optional[str] = None
    masked_aadhaar: Optional[str] = None
    ipfs_cid: Optional[str] = None
    credential_hash: Optional[str] = None
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    failure_reason: Optional[str] = None
    steps_completed: List[str]
    allowed_next_actions: List[str]

class CredentialIssueRequest(BaseModel):
    worker_did: str
    title: str
    credential_type: str = "Skill" # Identity, Safety, Skill, Experience, Welfare, Induction
    issuer_name: Optional[str] = None
    skills: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    valid_days: Optional[int] = 365

class CredentialResponse(BaseModel):
    id: str
    title: str
    type: str
    issuer: str
    issuer_role: str
    status: str
    worker_did: str
    skills: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    anchored: bool = True
    created_at: Optional[str] = None
    expires_at: Optional[str] = None

class EmployerRegister(BaseModel):
    company_name: str
    registration_number: str
    business_address: str = "Industrial Sector 4, Bengaluru, KA"
    contact_person: Optional[str] = None
    email: str
    phone: str
    business_type: str = "Construction & Infrastructure"
    nature_of_business: str = "Civil Engineering & Contracting"
    categories_requested: List[str] = ["Mason", "Electrician"]
    levels_requested: List[str] = ["Skilled", "Semi-Skilled"]
    natures_requested: List[str] = ["Contract", "Project-Based"]
    expected_workforce: int = 50
    password: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_employer_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Field aliases for company name
            if not data.get("company_name"):
                data["company_name"] = data.get("organization_name") or data.get("name") or ""
            if isinstance(data.get("company_name"), str):
                data["company_name"] = data["company_name"].strip()

            # Field aliases for registration number
            if not data.get("registration_number"):
                data["registration_number"] = (
                    data.get("registration_ref_number") or 
                    data.get("org_reg_no") or 
                    data.get("reg_number") or ""
                )
            if isinstance(data.get("registration_number"), str):
                data["registration_number"] = data["registration_number"].strip()

            # Contact person fallback
            if not data.get("contact_person"):
                data["contact_person"] = data.get("full_name") or data.get("company_name") or "Authorized Representative"

            # Email & phone normalization
            if not data.get("email") and data.get("official_email"):
                data["email"] = data["official_email"]
            if isinstance(data.get("email"), str):
                data["email"] = data["email"].strip().lower()

            if not data.get("phone") and data.get("official_phone"):
                data["phone"] = data["official_phone"]

            # Categories requested normalization (supports list or comma-separated string)
            cats = data.get("categories_requested") or data.get("categories") or data.get("category")
            if isinstance(cats, str):
                data["categories_requested"] = [c.strip() for c in cats.split(",") if c.strip()]
            elif isinstance(cats, list):
                data["categories_requested"] = [str(c).strip() for c in cats if str(c).strip()]
            elif cats is None:
                data["categories_requested"] = ["Mason", "Electrician"]

        return data

class CategoryRequest(BaseModel):
    category: str
    reason: str

class CreateEmploymentRequest(BaseModel):
    worker_did: str
    category: str
    level: str = "Skilled"
    nature_of_employment: str = "Contract"
    job_role: str
    work_location: str
    expected_end_date: Optional[int] = 0

class UpdateEmploymentStatusRequest(BaseModel):
    employment_id: int
    new_status: str # ACTIVE | COMPLETED | TERMINATED | DISMISSED | RESIGNED | SUSPENDED
    reason: str

# Government & Welfare Schemas
class WelfareClaimRequest(BaseModel):
    scheme_id: int
    worker_did: str
    officer_state: str
    gov_officer_wallet: Optional[str] = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
    officer_wallet: Optional[str] = None

# Admin Schemas
class OrgApprovalRequest(BaseModel):
    org_address: str
    approved: bool
    reason: str = ""
    authorized_categories: Optional[List[str]] = None

# OTP & Verification Schemas
class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str
    session_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_otp(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_val = data.get("otp") if data.get("otp") not in (None, "") else data.get("otp_code")
            if raw_val is not None:
                data["otp"] = str(raw_val).strip()
        return data

    @property
    def otp_code(self) -> str:
        return self.otp

class OTPResponse(BaseModel):
    success: bool
    session_id: str
    message: str
    simulated_sms: Optional[str] = None
    expires_in: int = 300

# Email OTP Schemas
class SendEmailOTPRequest(BaseModel):
    email: EmailStr

    @model_validator(mode="before")
    @classmethod
    def normalize_email(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "email" in data and isinstance(data["email"], str):
                data["email"] = data["email"].strip().lower()
        return data

class VerifyEmailOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str
    session_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_otp_code(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "email" in data and isinstance(data["email"], str):
                data["email"] = data["email"].strip().lower()
            raw_val = data.get("otp_code") if data.get("otp_code") not in (None, "") else data.get("otp")
            if raw_val is not None:
                data["otp_code"] = str(raw_val).strip()
        return data

    @property
    def otp(self) -> str:
        return self.otp_code

class EmailOTPResponse(BaseModel):
    status: str = "SENT"
    success: bool = True
    session_id: Optional[str] = None
    email: Optional[str] = None
    message: str
    expires_in: int = 300
    otp_code: Optional[str] = None
    simulated_email: Optional[Union[Dict[str, Any], str]] = None
    delivery_mode: Optional[str] = "simulated"

class VerifyEmailOTPResponse(BaseModel):
    verified: bool = True
    message: str
    email: str

class NetworkConfigRequest(BaseModel):
    active_network: Optional[str] = None
    active_ipfs_provider: Optional[str] = None
    rpc_url: Optional[str] = None
    chain_id: Optional[int] = None
    pinata_api_key: Optional[str] = None


# ============================================================================
# MOCK AADHAAR CRUD, SERVICE AUTH & AUDIT SCHEMAS (Milestone 4)
# ============================================================================

class AadhaarRecordCreate(BaseModel):
    aadhaar_number: str = Field(..., description="12-digit unique Aadhaar number")
    full_name: str = Field(..., min_length=2, description="Full demographic name")
    dob: str = Field(..., description="Date of birth YYYY-MM-DD")
    gender: str = Field(..., description="Gender: Male, Female, Other")
    origin_state: str = Field(..., description="State of origin")
    address: Optional[str] = Field(None, description="Demographic residential address")
    status: Optional[str] = Field("ACTIVE", description="Initial record status: ACTIVE, INACTIVE, SUSPENDED")

    @model_validator(mode="before")
    @classmethod
    def clean_aadhaar(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "aadhaar_number" in data and isinstance(data["aadhaar_number"], str):
                cleaned = "".join(filter(str.isdigit, data["aadhaar_number"]))
                if len(cleaned) != 12:
                    raise ValueError("Aadhaar number must contain exactly 12 numeric digits")
                data["aadhaar_number"] = cleaned
            if "full_name" in data and isinstance(data["full_name"], str):
                data["full_name"] = " ".join(data["full_name"].strip().split())
        return data


class AadhaarRecordUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2)
    dob: Optional[str] = None
    gender: Optional[str] = None
    origin_state: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def reject_immutable_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "aadhaar_number" in data or "record_id" in data or "aadhaar_hash" in data:
                raise ValueError("Aadhaar number, record_id, and hash cannot be modified")
        return data


class AadhaarRecordStatusUpdate(BaseModel):
    status: str = Field(..., description="New status: ACTIVE, INACTIVE, SUSPENDED")


class AadhaarRecordResponse(BaseModel):
    record_id: str
    masked_aadhaar: str
    masked_number: Optional[str] = None
    full_name: str
    dob: str
    gender: str
    origin_state: str
    address: Optional[str] = None
    status: Optional[str] = 'ACTIVE'
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def populate_masked_number(self):
        val = self.masked_number or self.masked_aadhaar
        if val:
            self.masked_number = val.replace("-", " ")
        return self

    class Config:
        from_attributes = True


class AadhaarVerifyServiceResponse(BaseModel):
    verified: bool
    status: str
    masked_aadhaar: str
    origin_state: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    latency_ms: float
    request_id: str
    reason: Optional[str] = None


class AadhaarAuditLogResponse(BaseModel):
    id: int
    request_id: str
    record_id: Optional[str] = None
    masked_aadhaar: str
    supplied_name: Optional[str] = None
    name_matched: bool
    aadhaar_matched: bool
    record_status: Optional[str] = None
    result_code: str
    response_time_ms: Optional[float] = None
    requester_role: Optional[str] = None
    originating_service: str
    failure_reason: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# ============================================================================
# MILESTONE 5: EMPLOYER DUAL STATE MACHINE, GOVERNANCE & HIERARCHY SCHEMAS
# ============================================================================

class OrganizationReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE, REJECT, REQUEST_MORE_INFO, SUSPEND, REACTIVATE")
    reason: Optional[str] = Field(None, description="Mandatory reason for REJECT, REQUEST_MORE_INFO, SUSPEND, DISABLE")
    requested_information: Optional[str] = None
    notes: Optional[str] = None

class OrganizationResponse(BaseModel):
    id: int
    name: str
    registration_ref_number: Optional[str] = None
    registration_number: Optional[str] = None
    business_type: Optional[str] = None
    nature_of_business: Optional[str] = None
    official_email: Optional[str] = None
    official_phone: Optional[str] = None
    phone: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    org_address: Optional[str] = None
    status: str
    verification_status: Optional[str] = None
    rejection_reason: Optional[str] = None
    suspension_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def populate_phone_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("official_phone") and data.get("phone"):
                data["official_phone"] = data["phone"]
            if not data.get("phone") and data.get("official_phone"):
                data["phone"] = data["official_phone"]
        return data

    @model_validator(mode="after")
    def populate_verification_status(self):
        if not self.verification_status and self.status:
            self.verification_status = self.status
        return self

    class Config:
        from_attributes = True

class CategoryReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE, APPROVED, REJECT, REJECTED, REQUEST_MORE_INFO, MORE_INFO_REQUESTED, SUSPEND, SUSPENDED, DISCONTINUE, DISCONTINUED")
    reason: Optional[str] = Field(None, description="Mandatory reason for REJECT, REQUEST_MORE_INFO, SUSPEND, DISCONTINUE")
    requested_information: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: Any) -> Any:
        if isinstance(data, dict) and "action" in data and isinstance(data["action"], str):
            data["action"] = data["action"].strip().upper()
        return data

class CategoryDiscontinueRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory administrative justification for discontinuation")

class CategoryAuthorizationRequestResponse(BaseModel):
    id: int
    organization_id: int
    organization_name: Optional[str] = None
    registration_ref_number: Optional[str] = None
    category: str
    skill_level: Optional[str] = None
    nature_of_employment: Optional[str] = None
    status: str
    is_active_scope: bool
    request_version: int = 1
    reason: Optional[str] = None
    review_reason: Optional[str] = None
    requested_information: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class GovernmentOfficerCreate(BaseModel):
    full_name: str = Field(..., min_length=2)
    official_email: EmailStr
    phone: Optional[str] = "+91 9876543212"
    department: str = "Migrant Labour Welfare Department"
    designation: Optional[str] = "Labour Welfare Commissioner"
    authority_level: str = Field(..., description="NATIONAL, STATE, DISTRICT, BLOCK, or LOCAL")
    state: Optional[str] = None
    state_name: Optional[str] = None
    district: Optional[str] = None
    district_name: Optional[str] = None
    block: Optional[str] = None
    local_name: Optional[str] = None
    wallet_address: Optional[str] = None
    officer_name: Optional[str] = None
    permissions: List[str] = Field(
        default_factory=lambda: [
            "WORKER_VERIFICATION",
            "CROSS_STATE_VERIFICATION",
            "VIEW_EMPLOYMENT",
            "VIEW_WELFARE_ELIGIBILITY",
            "CREATE_BENEFIT_CLAIM",
            "DISBURSE_BENEFIT",
            "VIEW_CLAIM_HISTORY",
            "AUDIT_VIEW"
        ]
    )
    benefit_permissions: List[str] = Field(
        default_factory=lambda: ["1", "2"]
    )
    expires_at: Optional[datetime] = None
    custom_message: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_geographic_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("state") and data.get("state_name"):
                data["state"] = data["state_name"]
            if not data.get("district") and data.get("district_name"):
                data["district"] = data["district_name"]
            if not data.get("block") and data.get("local_name"):
                data["block"] = data["local_name"]
            if not data.get("officer_name") and data.get("full_name"):
                data["officer_name"] = data["full_name"]
            lvl = str(data.get("authority_level", "")).strip().upper()
            if lvl == "LOCAL":
                lvl = "BLOCK"
            data["authority_level"] = lvl
        return data

class GovernmentOfficerUpdate(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    authority_level: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    block: Optional[str] = None
    wallet_address: Optional[str] = None
    permissions: Optional[List[str]] = None
    benefit_permissions: Optional[List[str]] = None
    expires_at: Optional[datetime] = None

class GovernmentOfficerStatusUpdate(BaseModel):
    status: str = Field(..., description="ACTIVE, SUSPENDED, DISABLED, INACTIVE")
    reason: Optional[str] = None

class GovernmentOfficerResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    officer_reference_id: Optional[str] = None
    officer_name: Optional[str] = None
    full_name: Optional[str] = None
    official_email: Optional[str] = None
    phone: Optional[str] = None
    department: str
    designation: Optional[str] = None
    authority_level: str
    state: Optional[str] = None
    district: Optional[str] = None
    block: Optional[str] = None
    wallet_address: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    benefit_permissions: List[str] = Field(default_factory=list)
    status: str
    suspension_reason: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None
    activation_link: Optional[str] = None
    raw_token: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_officer_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("full_name") and data.get("officer_name"):
                data["full_name"] = data["officer_name"]
            if not data.get("officer_name") and data.get("full_name"):
                data["officer_name"] = data["full_name"]
            if "permissions" not in data and "permissions_json" in data:
                try:
                    data["permissions"] = json.loads(data["permissions_json"]) if data["permissions_json"] else []
                except Exception:
                    data["permissions"] = []
            if "benefit_permissions" not in data and "benefit_permissions_json" in data:
                try:
                    data["benefit_permissions"] = json.loads(data["benefit_permissions_json"]) if data["benefit_permissions_json"] else []
                except Exception:
                    data["benefit_permissions"] = []
        return data

    class Config:
        from_attributes = True


# ============================================================================
# MILESTONE 3: STANDARDIZED PAGINATION ENVELOPES (R4)
# ============================================================================

T = TypeVar('T')

class PaginatedEnvelope(BaseModel, Generic[T]):
    total_count: int
    page: int
    page_size: int
    total_pages: int
    items: List[T]

class PaginatedOrganizationResponse(PaginatedEnvelope[OrganizationResponse]):
    pass

PaginatedOrganizationsResponse = PaginatedOrganizationResponse

class PaginatedCategoryRequestResponse(PaginatedEnvelope[CategoryAuthorizationRequestResponse]):
    pass

PaginatedCategoryAuthorizationRequestResponse = PaginatedCategoryRequestResponse

class PaginatedGovernmentOfficerResponse(PaginatedEnvelope[GovernmentOfficerResponse]):
    pass

class ResendActivationRequest(BaseModel):
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    reason: Optional[str] = None

class ResendActivationResponse(BaseModel):
    success: bool = True
    message: str
    recipient_email: str
    attempt_count: int
    activation_link: Optional[str] = None
    raw_token: Optional[str] = None
    delivery_status: Optional[str] = "SENT"
    delivery_error: Optional[str] = None
    is_smtp_configured: Optional[bool] = False

class AccountActivationRequest(BaseModel):
    activation_token: Optional[str] = None
    token: Optional[str] = None
    password: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_token(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw = data.get("activation_token") or data.get("token")
            if raw:
                data["activation_token"] = str(raw).strip()
                data["token"] = str(raw).strip()
        return data

class GovernmentActivationRequest(AccountActivationRequest):
    pass

class GovernmentActivationStatusResponse(BaseModel):
    status: str
    officer_name: Optional[str] = None
    official_email: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    authority_level: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None

class GovernanceAuditLogResponse(BaseModel):
    id: int
    actor_firebase_uid: str
    actor_user_id: Optional[int] = None
    actor_role: str
    action: str
    target_type: str
    target_id: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    reason: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime

    @field_serializer("timestamp")
    def serialize_timestamp(self, ts: datetime, _info):
        if ts.tzinfo is None:
            return ts.isoformat() + "Z"
        return ts.isoformat()

    class Config:
        from_attributes = True

class DisputeCreateRequest(BaseModel):
    employment_id: int
    reason: str = Field(..., min_length=5, description="Reason for dispute")
    claim_amount_inr: Optional[float] = 0.0

class DisputeResolutionRequest(BaseModel):
    employment_id: Optional[int] = None
    resolution_status: str = Field(..., description="COMPLETED, TERMINATED, ACTIVE, or DISMISSED")
    resolution_notes: str = Field(..., min_length=5, description="Official adjudication notes")
    settlement_amount_inr: Optional[float] = 0.0

class DisputeResolutionResponse(BaseModel):
    success: bool = True
    employment_id: int
    new_status: str
    resolution_notes: str
    settlement_amount_inr: float = 0.0
    adjudicated_by: str
    adjudicated_at: datetime


