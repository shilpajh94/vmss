import uuid
from typing import Literal

from pydantic import EmailStr, Field

from vmss_api.core.schemas import CamelModel

EmployeeSortableField = Literal["name", "created_at"]
RoleSortableField = Literal["name", "created_at"]


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class BranchRoleOut(CamelModel):
    id: uuid.UUID
    role_name: str
    branch_id: uuid.UUID | None


class UserOut(CamelModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    avatar_url: str | None = None
    branch_roles: list[BranchRoleOut]


class RoleCreateRequest(CamelModel):
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permission_codes: list[str] = Field(
        default_factory=list, examples=[["visitors:checkin", "invitations:create"]]
    )


class RoleUpdateRequest(CamelModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permission_codes: list[str] | None = Field(
        default=None, examples=[["visitors:checkin", "invitations:create"]]
    )


class RoleOut(CamelModel):
    id: uuid.UUID
    name: str
    description: str | None
    permission_codes: list[str]
    is_standard: bool


class RolePermissionResyncEntryOut(CamelModel):
    """One standard role's result from `POST /auth/roles/resync-permissions`
    — empty `grantedPermissionCodes` means that role already had everything
    the current catalog grants it.
    """

    role_name: str
    granted_permission_codes: list[str]


class PermissionOut(CamelModel):
    """`GET /auth/permissions`'s catalog entry — see
    `Requirement: Role Permission Codes Must Exist in the Catalog` in
    openspec/specs/auth/spec.md. Lets a role-creation/update form populate
    its permission-code choices instead of guessing, which is what today's
    `Unknown permission code(s): string` reports actually stem from.
    """

    code: str
    description: str


class RoleVerifyResponse(CamelModel):
    name: str
    available: bool


class UserCreateRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(max_length=255)


class BranchRoleAssignRequest(CamelModel):
    role_id: uuid.UUID
    branch_id: uuid.UUID | None = None


class EmployeeSyncItem(CamelModel):
    email: EmailStr
    full_name: str = Field(max_length=255)
    employee_code: str = Field(max_length=50)
    phone_number: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=100)
    department_id: uuid.UUID | None = None


class EmployeeSyncRequest(CamelModel):
    employees: list[EmployeeSyncItem] = Field(min_length=1, max_length=1000)


class EmployeeCreateRequest(CamelModel):
    email: EmailStr
    full_name: str = Field(max_length=255)
    employee_code: str = Field(max_length=50)
    department_id: uuid.UUID
    phone_number: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=100)


class EmployeeSyncResult(CamelModel):
    created: list[EmailStr]
    updated: list[EmailStr]
    deactivated: list[EmailStr]


class EmployeeOut(CamelModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    employee_code: str | None
    phone_number: str | None
    designation: str | None
    department_id: uuid.UUID | None
    is_active: bool
    avatar_url: str | None
    branch_roles: list[BranchRoleOut]


class EmployeeDirectoryOut(CamelModel):
    """Reduced-field projection of `EmployeeOut` for the public host-picker
    listing (`router.py::list_employee_directory`) — deliberately omits
    `email`/`phone_number`/`employee_code`: those are PII, and this endpoint
    has no bearer token to gate access to them
    (security-architecture.md §4's PII-handling posture).
    """

    id: uuid.UUID
    full_name: str
    designation: str | None
    department_id: uuid.UUID | None
    avatar_url: str | None = None


class AvatarUploadOut(CamelModel):
    """`POST /auth/me/avatar`'s response — just the newly resolved URL, since
    the caller already knows who they are.
    """

    avatar_url: str | None
