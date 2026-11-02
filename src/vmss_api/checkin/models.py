import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base


class BadgePrint(Base):
    """Append-only log of badge prints and reprints (add-badge-print-flow).

    Never soft-deleted or edited except `active` true -> false, so there is
    deliberately no `TimestampMixin` (`database-architecture.md` §4, same as
    `AuditLog`). `jti` is the badge QR token's id; `day` is the tenant-local
    date the token is valid for.
    """

    __tablename__ = "badge_prints"
    __table_args__ = (
        Index(
            "uq_badge_prints_one_active_per_visit",
            "visit_id",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invitations.id"), index=True)
    printed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    printed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    jti: Mapped[str] = mapped_column(String(64), unique=True)
    day: Mapped[date] = mapped_column(Date())
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    reprint_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
