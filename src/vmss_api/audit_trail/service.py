import uuid
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.audit_trail import tasks
from vmss_api.audit_trail.models import AuditReportJob
from vmss_api.audit_trail.repository import AuditLogRepository, AuditReportJobRepository
from vmss_api.audit_trail.schemas import AuditReportJobOut
from vmss_api.auth.models import AuditLog
from vmss_api.core.schemas import SortOrder
from vmss_api.core.storage import url_for as storage_url_for


class ReportJobNotFoundError(Exception):
    """Raised when a report job id doesn't resolve in the caller's tenant
    schema. Under schema-per-tenant this is also how cross-tenant isolation
    holds for report jobs — a job id from another tenant is simply not
    resolvable against this session's schema, never a leak
    (specs/audit-trail/spec.md "Report from another tenant is not
    downloadable").
    """


def _current_request_id() -> str:
    return structlog.contextvars.get_contextvars().get("request_id", "")


async def list_audit_logs(
    tenant_db: AsyncSession,
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
    return await AuditLogRepository(tenant_db).list_page(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_after=created_after,
        created_before=created_before,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_audit_log(tenant_db: AsyncSession, id_: uuid.UUID) -> AuditLog | None:
    return await AuditLogRepository(tenant_db).get(id_)


async def request_audit_report(
    tenant_db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    tenant_schema: str,
    requested_by_user_id: uuid.UUID,
    formats: list[str],
    actor_user_id: uuid.UUID | None,
    action: str | None,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    created_after: datetime | None,
    created_before: datetime | None,
) -> AuditReportJob:
    """Creates the `pending` job row and enqueues generation. The row is
    committed before `.delay()` is called so the task (which may start
    executing before this coroutine's caller returns) always finds it —
    never call the task function directly (`background-jobs.md` §5).
    """
    filters = {
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "created_after": created_after.isoformat() if created_after else None,
        "created_before": created_before.isoformat() if created_before else None,
    }
    job = await AuditReportJobRepository(tenant_db).create(
        id_=uuid.uuid4(),
        requested_by_user_id=requested_by_user_id,
        filters=filters,
        formats=formats,
    )
    await tenant_db.commit()
    tasks.generate_audit_report.delay(
        job_id=str(job.id),
        tenant_id=str(tenant_id),
        tenant_schema=tenant_schema,
        request_id=_current_request_id(),
    )
    return job


async def get_report_job(tenant_db: AsyncSession, id_: uuid.UUID) -> AuditReportJobOut:
    job = await AuditReportJobRepository(tenant_db).get(id_)
    if job is None:
        raise ReportJobNotFoundError
    return await to_report_job_out(job)


async def to_report_job_out(job: AuditReportJob) -> AuditReportJobOut:
    csv_url = await storage_url_for(job.csv_storage_key) if job.csv_storage_key else None
    pdf_url = await storage_url_for(job.pdf_storage_key) if job.pdf_storage_key else None
    return AuditReportJobOut(
        id=job.id,
        status=job.status,
        formats=job.formats,
        requested_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        csv_download_url=csv_url,
        pdf_download_url=pdf_url,
    )
