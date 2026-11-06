import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from vmss_api.core.schemas import CamelModel


class ZoneCreate(CamelModel):
    branch_id: uuid.UUID
    building_id: uuid.UUID | None = None
    floor_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    is_default: bool = False
    gate_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class ZoneUpdate(CamelModel):
    """`branch_id` is immutable: moving a zone would silently invalidate every
    mapping and gate link that was validated against the old branch."""

    building_id: uuid.UUID | None = None
    floor_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    is_default: bool | None = None
    gate_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)


class ZoneOut(CamelModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    building_id: uuid.UUID | None
    floor_id: uuid.UUID | None
    name: str
    code: str
    description: str | None
    is_active: bool
    is_default: bool
    gate_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime


class ZoneSortField(StrEnum):
    name = "name"
    created_at = "created_at"


class ZoneIdsIn(CamelModel):
    """Replaces the whole set; an empty list clears it (invitation: fall back to
    category defaults; category: no defaults)."""

    zone_ids: list[uuid.UUID] = Field(max_length=100)


class ZoneIdsOut(CamelModel):
    zone_ids: list[uuid.UUID]


class ScanDirection(StrEnum):
    entry = "entry"
    exit = "exit"


class ScanRequest(CamelModel):
    token: str = Field(min_length=1, max_length=512)
    gate_id: uuid.UUID
    zone_id: uuid.UUID
    direction: ScanDirection


class ScanOut(CamelModel):
    allowed: bool
    reason: str | None = None
    visitor_name: str | None = None
