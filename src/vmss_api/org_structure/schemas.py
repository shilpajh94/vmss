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


class CompanyUpdate(CamelModel):
    legal_name: str | None = Field(default=None, max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


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


class BranchCreate(CamelModel):
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    address: str | None = Field(default=None, max_length=500)


class BranchUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class BranchOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    is_active: bool


class BuildingCreate(CamelModel):
    branch_id: uuid.UUID
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)
    address: str | None = Field(default=None, max_length=500)


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


class FloorCreate(CamelModel):
    building_id: uuid.UUID
    name: str = Field(max_length=255)
    floor_number: int


class FloorUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    floor_number: int | None = None
    is_active: bool | None = None


class FloorOut(CamelModel):
    id: uuid.UUID
    building_id: uuid.UUID
    name: str
    floor_number: int
    is_active: bool


class DepartmentCreate(CamelModel):
    floor_id: uuid.UUID
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)


class DepartmentUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class DepartmentOut(CamelModel):
    id: uuid.UUID
    floor_id: uuid.UUID
    name: str
    code: str
    is_active: bool


class ReceptionDeskCreate(CamelModel):
    floor_id: uuid.UUID
    name: str = Field(max_length=255)
    code: str = Field(max_length=50)


class ReceptionDeskUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class ReceptionDeskOut(CamelModel):
    id: uuid.UUID
    floor_id: uuid.UUID
    name: str
    code: str
    is_active: bool


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


class SecurityGateUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    building_id: uuid.UUID | None = None
    gate_type: GateType | None = None
    is_active: bool | None = None


class SecurityGateOut(CamelModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    building_id: uuid.UUID | None
    name: str
    code: str
    gate_type: str
    is_active: bool


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
    floor_number: int
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
