"""Tenant-scoped catalogs backing the walk-in registration wizard's Visit
Info step (`GET /visit-info/options`) — real, seeded purpose/duration lists
in place of the app's previously hardcoded ones. See
openspec/changes/visit-info-lookup-api/design.md.
"""

import uuid

from sqlalchemy import Boolean, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin


class VisitPurpose(Base, TimestampMixin):
    """A selectable reason for a visit. Soft-deleted, not hard-deleted: an
    `Invitation.purpose_id` FK may reference a row after it's retired from
    the active picklist (`is_active=False` retires it without breaking that
    reference).
    """

    __tablename__ = "visit_purposes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class VisitDuration(Base, TimestampMixin):
    """A selectable expected-visit-duration option, carrying a canonical
    `minutes` value alongside its display `name` — the numeric value a
    display string like "Half day (4 hours)" can't carry on its own, and a
    foundation for future overstay-detection work (design.md Goals).
    """

    __tablename__ = "visit_durations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    minutes: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
