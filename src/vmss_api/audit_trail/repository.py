import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.audit_trail.models import AuditReportJob
from vmss_api.auth.models import AuditLog
from vmss_api.core.database import TenantScopedRepository, order_clause
from vmss_api.core.schemas import SortOrder

_SORT_COLUMNS: dict[str, Any] = {
    "created_at": AuditLog.created_at,
    "action": AuditLog.action,
    "entity_type": AuditLog.entity_type,
}


class AuditLogRepository:
    """Read-only queries over `AuditLog` (owned by `auth/models.py`, written
    via `auth/audit.py::record_audit_log`). Not a `TenantScopedRepository`
    subclass — `AuditLog` is deliberately append-only with no `deleted_at`
    column (see its docstring), so the soft-delete filter that base class
    applies doesn't apply here.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_page(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str | None,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        created_after: datetime | None,
        created_before: datetime | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[AuditLog], int]:
        filters = self._filters(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_after=created_after,
            created_before=created_before,
        )
        total = await self._count(filters)
        column = _SORT_COLUMNS[sort_by]
        stmt = (
            select(AuditLog)
            .where(*filters)
            .order_by(order_clause(column, sort_order))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    async def list_all(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str | None,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        created_after: datetime | None,
        created_before: datetime | None,
    ) -> list[AuditLog]:
        """Unpaginated variant for report generation
        (`tasks.py::generate_audit_report`) — shares `_filters` with
        `list_page` so a report's rows are computed by the exact same
        filter logic the list endpoint uses (`query-performance.md` §2,
        specs/audit-trail/spec.md "Report job reflects the filtered data at
        request time").
        """
        filters = self._filters(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_after=created_after,
            created_before=created_before,
        )
        stmt = select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, id_: uuid.UUID) -> AuditLog | None:
        stmt = select(AuditLog).where(AuditLog.id == id_)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _count(self, filters: list[Any]) -> int:
        stmt = select(func.count()).select_from(AuditLog).where(*filters)
        return (await self.session.execute(stmt)).scalar_one()

    @staticmethod
    def _filters(
        *,
        actor_user_id: uuid.UUID | None,
        action: str | None,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        created_after: datetime | None,
        created_before: datetime | None,
    ) -> list[Any]:
        filters: list[Any] = []
        if actor_user_id is not None:
            filters.append(AuditLog.actor_user_id == actor_user_id)
        if action is not None:
            filters.append(AuditLog.action == action)
        if entity_type is not None:
            filters.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            filters.append(AuditLog.entity_id == entity_id)
        if created_after is not None:
            filters.append(AuditLog.created_at >= created_after)
        if created_before is not None:
            filters.append(AuditLog.created_at <= created_before)
        return filters


class AuditReportJobRepository(TenantScopedRepository[AuditReportJob]):
    model = AuditReportJob

    async def create(
        self,
        *,
        id_: uuid.UUID,
        requested_by_user_id: uuid.UUID,
        filters: dict[str, Any],
        formats: list[str],
    ) -> AuditReportJob:
        job = AuditReportJob(
            id=id_,
            requested_by_user_id=requested_by_user_id,
            status="pending",
            filters=filters,
            formats=formats,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def mark_ready(
        self,
        job: AuditReportJob,
        *,
        csv_storage_key: str | None,
        pdf_storage_key: str | None,
    ) -> None:
        job.status = "ready"
        job.csv_storage_key = csv_storage_key
        job.pdf_storage_key = pdf_storage_key
        job.completed_at = datetime.now(UTC)
        await self.session.flush()

    async def mark_failed(self, job: AuditReportJob, *, error_message: str) -> None:
        job.status = "failed"
        job.error_message = error_message
        job.completed_at = datetime.now(UTC)
        await self.session.flush()
