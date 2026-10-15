import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, computed_field

from vmss_api.core.schemas import CamelModel

SortableField = Literal["name", "created_at", "approval_status"]


class OperatingMode(StrEnum):
    kiosk = "kiosk"
    security = "security"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"


class DeviceRegister(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    device_id: str = Field(min_length=1, max_length=255)
    branch_id: uuid.UUID
    building_id: uuid.UUID | None = None
    operating_mode: OperatingMode


class DeviceOut(CamelModel):
    id: uuid.UUID
    device_id: str
    name: str
    branch_id: uuid.UUID
    branch_name: str | None = None
    building_id: uuid.UUID | None
    building_name: str | None = None
    operating_mode: OperatingMode
    approval_status: ApprovalStatus
    is_active: bool
    approved_at: datetime | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_approve(self) -> bool:
        return self.approval_status == ApprovalStatus.pending

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_enable(self) -> bool:
        return self.approval_status == ApprovalStatus.approved and not self.is_active

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_disable(self) -> bool:
        return self.approval_status == ApprovalStatus.approved and self.is_active


class DeviceRegistrationOut(CamelModel):
    id: uuid.UUID
    device_id: str
    approval_status: ApprovalStatus
    is_active: bool


class DeviceBriefOut(CamelModel):
    """Embedded in invitation check-in/out responses."""

    id: uuid.UUID
    device_id: str
    name: str
    operating_mode: OperatingMode


class KioskLocationValidationSetting(CamelModel):
    enforce_kiosk_location_validation: bool
