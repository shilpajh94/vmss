import uuid
from typing import Literal

from pydantic import Field

from vmss_api.core.schemas import CamelModel

SsoRoleMappingSortableField = Literal["idp_group_claim_value", "created_at"]


class SsoProviderConfigIn(CamelModel):
    display_name: str = Field(max_length=100, examples=["PIT Solutions"])
    discovery_url: str = Field(
        max_length=500,
        examples=[
            "https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration"
        ],
    )
    client_id: str = Field(max_length=255)
    client_secret: str = Field(max_length=1000)
    is_enabled: bool = True
    allow_admin_login: bool = False


class SsoProviderConfigOut(CamelModel):
    id: uuid.UUID
    display_name: str
    discovery_url: str
    client_id: str
    client_secret_masked: str
    is_enabled: bool
    allow_admin_login: bool


class SsoProviderTestRequest(CamelModel):
    discovery_url: str = Field(max_length=500)
    client_id: str = Field(max_length=255)
    client_secret: str = Field(max_length=1000)


class SsoProviderTestResult(CamelModel):
    success: bool
    message: str


class SsoRoleMappingIn(CamelModel):
    idp_group_claim_value: str = Field(max_length=255, examples=["VMS-Security-Team"])
    role_id: uuid.UUID


class SsoRoleMappingOut(CamelModel):
    id: uuid.UUID
    idp_group_claim_value: str
    role_id: uuid.UUID
    role_name: str


class SsoExchangeRequest(CamelModel):
    code: str = Field(
        max_length=512,
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
