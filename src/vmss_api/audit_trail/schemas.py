import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from vmss_api.core.schemas import CamelModel

AuditLogSortableField = Literal["created_at", "action", "entity_type"]
ReportFormat = Literal["csv", "pdf"]


class AuditLogOut(CamelModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    created_at: datetime


class AuditLogDetailOut(AuditLogOut):
    """Same fields as the list row, plus the recorded before/after `diff` —
    a separate schema (not just reusing `AuditLogOut` for the detail
    response) per `database-architecture.md` §4's request/response
    separation convention.
    """

    diff: dict[str, Any] | None


class AuditReportRequest(CamelModel):
    """Same filter set the list endpoint accepts, plus the requested
    format(s). At least one format is required — an empty list would
    enqueue a job that produces nothing.
    """

    actor_user_id: uuid.UUID | None = None
    action: str | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    formats: list[ReportFormat] = Field(min_length=1)


class AuditReportJobOut(CamelModel):
    """`status`/`formats` are plain `str`/`list[str]`, not the `ReportFormat`
    literal above — this schema mirrors `AuditReportJob`'s stored columns
    (`Mapped[str]`/JSONB), matching the codebase's existing convention for a
    model-status-mirroring output schema (e.g. `invitations/schemas.py`'s
    `InvitationOut.status: str`) rather than re-validating a value the
    database already constrains.
    """

    id: uuid.UUID
    status: str
    formats: list[str]
    requested_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    csv_download_url: str | None = None
    pdf_download_url: str | None = None
