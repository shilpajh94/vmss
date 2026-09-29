import uuid

from sqlalchemy import Boolean, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin


class Kiosk(Base, TimestampMixin):
    """An admin-managed kiosk record. Tenant-scoped by schema. Independent of
    `registrations.models.RegistrationDeviceKey` (global-schema credential) —
    see add-kiosk-admin-crud/design.md.
    """

    __tablename__ = "kiosks"
    # Scoped to live rows so a soft-deleted kiosk's name is reusable.
    __table_args__ = (
        Index(
            "ix_kiosks_name_lower",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(2000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
