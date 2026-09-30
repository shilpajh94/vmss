import uuid
from typing import Literal

from pydantic import Field

from vmss_api.core.schemas import CamelModel

SortableField = Literal["name", "created_at"]


class KioskCreate(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class KioskUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class KioskVisibilityUpdate(CamelModel):
    is_hidden: bool


class KioskOut(CamelModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    is_hidden: bool
