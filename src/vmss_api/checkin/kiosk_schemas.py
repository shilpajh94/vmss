import uuid
from datetime import datetime

from vmss_api.core.schemas import CamelModel


class KioskVisitOut(CamelModel):
    """What an unauthenticated kiosk may see about a visit: no phone, email,
    ID document URL or host contact (add-kiosk-badge-print-flow design
    Decision 4). `unmet_conditions` is the print gate's current to-do list."""

    id: uuid.UUID
    tracking_id: str
    visitor_first_name: str
    status: str
    check_in_status: str
    has_photo: bool
    id_verified_at: datetime | None
    has_active_badge: bool
    unmet_conditions: list[str]
