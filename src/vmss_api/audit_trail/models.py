"""`AuditReportJob` tracks async generation of CSV/PDF audit-trail report
files. `AuditLog` itself is owned by `auth/models.py` (written via
`auth/audit.py::record_audit_log`) — this feature only reads it; see
`repository.py::AuditLogRepository`.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin


class AuditReportJob(Base, TimestampMixin):
    """One requested audit-trail report export. `status` moves
    `pending` -> `ready` | `failed` exactly once, updated by
    `tasks.py::generate_audit_report` — which checks this column before
    doing any work, so a redelivered task is a no-op once the job has
    already reached a terminal state (`background-jobs.md` §2).

    `csv_storage_key`/`pdf_storage_key` are opaque storage keys
    (`core/storage.py`), never a URL — a download URL is resolved fresh on
    every poll via `storage.url_for` (design.md Decision 2) rather than
    stored, so no long-lived secret sits in this row.
    """

    __tablename__ = "audit_report_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    formats: Mapped[list[str]] = mapped_column(JSONB)
    csv_storage_key: Mapped[str | None] = mapped_column(String(500))
    pdf_storage_key: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(String(2000))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
