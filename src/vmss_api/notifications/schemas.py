import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from vmss_api.core.schemas import CamelModel


class DevicePlatform(StrEnum):
    web = "web"
    android = "android"
    ios = "ios"


class DeviceRegisterRequest(CamelModel):
    fcm_token: str = Field(min_length=1, max_length=4096)
    platform: DevicePlatform


class DeviceOut(CamelModel):
    id: uuid.UUID
    platform: DevicePlatform
    last_seen_at: datetime
