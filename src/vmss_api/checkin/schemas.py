import uuid
from datetime import datetime

from pydantic import Field

from vmss_api.core.schemas import CamelModel


class VisitSearchOut(CamelModel):
    id: uuid.UUID
    tracking_id: str
    full_name: str
    phone: str | None
    status: str
    check_in_status: str
    branch_id: uuid.UUID
    has_photo: bool
    id_verified_at: datetime | None
    has_active_badge: bool


class VerifyIdOut(CamelModel):
    id: uuid.UUID
    id_verified_at: datetime
    id_verified_by_user_id: uuid.UUID | None


class BadgeScanRequest(CamelModel):
    token: str = Field(min_length=1, max_length=2048)


class BadgeScanOut(CamelModel):
    id: uuid.UUID
    tracking_id: str
    status: str
    check_in_status: str


class BadgePrintRef(CamelModel):
    """The JSON the print route hands to the idempotency cache; a replay
    re-renders the PDF from this row rather than caching PDF bytes."""

    badge_print_id: uuid.UUID


class BadgeCardOut(CamelModel):
    """What the frontend needs to draw the ID-card badge itself. `token` is the
    signed, jti-bound badge token the QR must carry; `photo_url` is a `data:`
    URL because the stored photo sits behind auth and an `<img>` can't send
    a bearer header."""

    token: str
    visitor_name: str
    purpose: str | None
    host_name: str | None
    photo_url: str | None
