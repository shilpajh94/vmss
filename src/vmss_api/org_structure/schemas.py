import uuid
from enum import StrEnum
from typing import Literal

from pydantic import EmailStr, Field

from vmss_api.core.schemas import CamelModel

# Whitelisted sort columns for the org-structure list endpoints
# (api-conventions.md §1) — every one of these entities has `name` and
# `created_at`, so one shared type covers all of them.
SortableField = Literal["name", "created_at"]


class CompanyCreate(CamelModel):
    legal_name: str = Field(max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    default_timezone: str | None = Field(default=None, max_length=50)
    auto_approve_pre_registered_visitors: bool = False
    # Upper bound is a generous week-in-minutes ceiling — a badge that's
    # still "valid" a week after issue isn't really expiring at all — while
    # `ge=1` rules out a zero/negative duration a client could otherwise send
    # to make every badge expire instantly.
    badge_expiry_duration_minutes: int | None = Field(default=None, ge=1, le=10_080)


class CompanyUpdate(CamelModel):
    legal_name: str | None = Field(default=None, max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    default_timezone: str | None = Field(default=None, max_length=50)
    auto_approve_pre_registered_visitors: bool | None = None
    badge_expiry_duration_minutes: int | None = Field(default=None, ge=1, le=10_080)


class CompanyOut(CamelModel):
    id: uuid.UUID
    legal_name: str
    registration_number: str | None
    tax_id: str | None
    email: str | None
    phone: str | None
    address: str | None
    logo_url: str | None
    is_active: bool
    default_timezone: str | None
    auto_approve_pre_registered_visitors: bool
    badge_expiry_duration_minutes: int | None


class BranchCreate(CamelModel):
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    contact_person_user_id: uuid.UUID | None = None
    contact_email: EmailStr | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    operating_hours_from: str | None = Field(default=None, max_length=10)
    operating_hours_to: str | None = Field(default=None, max_length=10)
    notes: str | None = Field(default=None, max_length=2000)


class BranchUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    contact_person_user_id: uuid.UUID | None = None
    contact_email: EmailStr | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    operating_hours_from: str | None = Field(default=None, max_length=10)
    operating_hours_to: str | None = Field(default=None, max_length=10)
    notes: str | None = Field(default=None, max_length=2000)


class BranchOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    is_active: bool
    city: str | None
    country: str | None
    contact_person_user_id: uuid.UUID | None
    contact_email: str | None
    contact_phone: str | None
    operating_hours_from: str | None
    operating_hours_to: str | None
    notes: str | None


class BuildingCreate(CamelModel):
    branch_id: uuid.UUID
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class BuildingUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class BuildingOut(CamelModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    code: str
    address: str | None
    is_active: bool


class FloorCapacityType(StrEnum):
    guests = "guests"
    staff = "staff"


class FloorAccessLevel(StrEnum):
    public = "public"
    restricted = "restricted"
    secure = "secure"


# Bounds are physically-plausible, not database-derived (`floor_number`/
# `capacity` have no DB-side limit of their own — see `models.py`): a handful
# of basement levels below ground, a generous upper bound no real building
# comes close to, and a per-floor headcount ceiling that would already be an
# extraordinary building if reached.
_FLOOR_NUMBER_MIN = -20
_FLOOR_NUMBER_MAX = 200
_FLOOR_CAPACITY_MAX = 100_000


class FloorCreate(CamelModel):
    building_id: uuid.UUID
    name: str = Field(max_length=255)
    floor_number: int = Field(ge=_FLOOR_NUMBER_MIN, le=_FLOOR_NUMBER_MAX)
    capacity: int | None = Field(default=None, ge=0, le=_FLOOR_CAPACITY_MAX)
    capacity_type: FloorCapacityType | None = None
    access_level: FloorAccessLevel | None = None


class FloorUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    floor_number: int | None = Field(default=None, ge=_FLOOR_NUMBER_MIN, le=_FLOOR_NUMBER_MAX)
    is_active: bool | None = None
    capacity: int | None = Field(default=None, ge=0, le=_FLOOR_CAPACITY_MAX)
    capacity_type: FloorCapacityType | None = None
    access_level: FloorAccessLevel | None = None


class FloorOut(CamelModel):
    id: uuid.UUID
    building_id: uuid.UUID
    name: str
    floor_number: int
    is_active: bool
    capacity: int | None
    capacity_type: str | None
    access_level: str | None


class DepartmentCreate(CamelModel):
    branch_id: uuid.UUID
    floor_id: uuid.UUID | None = None
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    head_of_department_user_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=2000)


class DepartmentUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    floor_id: uuid.UUID | None = None
    head_of_department_user_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=2000)


class DepartmentOut(CamelModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    floor_id: uuid.UUID | None
    name: str
    code: str
    is_active: bool
    head_of_department_user_id: uuid.UUID | None
    description: str | None


class DeskStatus(StrEnum):
    active = "active"
    maintenance = "maintenance"
    inactive = "inactive"


class ReceptionDeskCreate(CamelModel):
    floor_id: uuid.UUID
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    status: DeskStatus = DeskStatus.active
    assigned_receptionist_user_id: uuid.UUID | None = None
    operating_hours_from: str | None = Field(default=None, max_length=10)
    operating_hours_to: str | None = Field(default=None, max_length=10)


class ReceptionDeskUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    status: DeskStatus | None = None
    assigned_receptionist_user_id: uuid.UUID | None = None
    operating_hours_from: str | None = Field(default=None, max_length=10)
    operating_hours_to: str | None = Field(default=None, max_length=10)


class ReceptionDeskOut(CamelModel):
    id: uuid.UUID
    floor_id: uuid.UUID
    name: str
    code: str
    status: str
    assigned_receptionist_user_id: uuid.UUID | None
    operating_hours_from: str | None
    operating_hours_to: str | None


class GateType(StrEnum):
    entry = "entry"
    exit = "exit"
    both = "both"


class SecurityGateCreate(CamelModel):
    branch_id: uuid.UUID
    building_id: uuid.UUID | None = None
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    gate_type: GateType = GateType.both
    high_security: bool = False


class SecurityGateUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    building_id: uuid.UUID | None = None
    gate_type: GateType | None = None
    high_security: bool | None = None


class SecurityGateOut(CamelModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    building_id: uuid.UUID | None
    name: str
    code: str
    gate_type: str
    high_security: bool


# --- Branch provisioning (bulk bootstrap) ---------------------------------
#
# One admin-only, transactional call that scaffolds a brand-new Branch plus
# as much of its Building -> Floor -> Department/ReceptionDesk chain and
# SecurityGates as the caller wants to hand it, instead of one client-side
# round trip per entity. Distinct from plain `BranchCreate` (above), which
# only ever creates the bare `Branch` row itself.


class ProvisionDepartment(CamelModel):
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)


class ProvisionReceptionDesk(CamelModel):
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)


class ProvisionSecurityGate(CamelModel):
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    gate_type: GateType = GateType.both


class ProvisionFloor(CamelModel):
    name: str = Field(max_length=255)
    floor_number: int = Field(ge=_FLOOR_NUMBER_MIN, le=_FLOOR_NUMBER_MAX)
    departments: list[ProvisionDepartment] = Field(default_factory=list)
    reception_desks: list[ProvisionReceptionDesk] = Field(default_factory=list)


class ProvisionBuilding(CamelModel):
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    address: str | None = Field(default=None, max_length=500)
    floors: list[ProvisionFloor] = Field(default_factory=list)
    # Gates narrowed to this building specifically — branch-wide gates (no
    # building) go in `BranchProvisionRequest.security_gates` instead.
    security_gates: list[ProvisionSecurityGate] = Field(default_factory=list)


class BranchProvisionRequest(CamelModel):
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    address: str | None = Field(default=None, max_length=500)
    buildings: list[ProvisionBuilding] = Field(default_factory=list)
    security_gates: list[ProvisionSecurityGate] = Field(default_factory=list)


class BranchProvisionResponse(CamelModel):
    branch: BranchOut
    buildings_created: int
    floors_created: int
    departments_created: int
    reception_desks_created: int
    security_gates_created: int
