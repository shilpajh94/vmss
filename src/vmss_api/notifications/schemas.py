import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

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


class NotificationOut(CamelModel):
    """`data` is the push payload's `data` verbatim (`invitationId`,
    `trackingId`, `action`, `reason`, ...) — keys are already camelCase on
    the wire, so the alias generator doesn't touch them (it only renames
    this model's own fields).
    """

    id: uuid.UUID
    title: str
    body: str
    data: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class UnreadCountOut(CamelModel):
    unread_count: int
