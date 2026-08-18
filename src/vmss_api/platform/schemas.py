import uuid

from pydantic import EmailStr, Field

from vmss_api.core.schemas import CamelModel


class PlatformLoginRequest(CamelModel):
    email: EmailStr
    password: str


class PlatformTokenResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"


class TenantCreateRequest(CamelModel):
    name: str = Field(max_length=255)
    slug: str = Field(max_length=100, pattern=r"^[a-z0-9-]+$")


class TenantSummaryOut(CamelModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
