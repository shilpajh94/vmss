import uuid
from typing import Literal

from pydantic import EmailStr, Field

from vmss_api.core.schemas import CamelModel

EmployeeSortableField = Literal["name", "created_at"]


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class BranchRoleOut(CamelModel):
    role_name: str
    branch_id: uuid.UUID | None


class UserOut(CamelModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    branch_roles: list[BranchRoleOut]


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
