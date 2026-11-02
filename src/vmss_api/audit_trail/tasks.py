"""Async generation of CSV/PDF audit-trail report files
(`add-audit-trail-history/design.md` Decisions 4-5). Resolves its own
tenant-bound session from a `tenant_schema` argument (`background-jobs.md`
§4) and re-checks the job's `status` before doing any work, so a
redelivered task is a no-op once the job has already reached `ready`/
`failed` (`background-jobs.md` §2).
"""

import asyncio
import csv
import io
import uuid
from datetime import datetime

import anyio
import structlog
from celery import Task
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.audit_trail.models import AuditReportJob
from vmss_api.audit_trail.repository import AuditLogRepository, AuditReportJobRepository
from vmss_api.auth.models import AuditLog
from vmss_api.core.celery_app import DEFAULT_RETRY_KWARGS, celery_app
from vmss_api.core.database import engine, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.storage import save as storage_save

_RETRY_KWARGS = DEFAULT_RETRY_KWARGS

_REPORT_HEADERS = ["id", "actor_user_id", "action", "entity_type", "entity_id", "created_at"]


@celery_app.task(bind=True, **_RETRY_KWARGS)
def generate_audit_report(
    self: Task, *, job_id: str, tenant_id: str, tenant_schema: str, request_id: str
) -> None:
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_generate_audit_report(job_id, tenant_id, tenant_schema))
    except Exception:
        if self.request.retries >= self.max_retries:
            asyncio.run(_mark_job_failed(job_id, tenant_schema))
            logger.error(
                "audit_report_generation_exhausted", job_id=job_id, tenant_schema=tenant_schema
            )
        raise


async def _generate_audit_report(job_id: str, tenant_id: str, tenant_schema: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            job_repo = AuditReportJobRepository(session)
            job = await job_repo.get(uuid.UUID(job_id))
            if job is None or job.status != "pending":
                # Idempotent under redelivery: already terminal (`ready`/
                # `failed`), or the row genuinely isn't there.
                return
            entries = await _fetch_entries(session, job)
            csv_key = None
            pdf_key = None
            if "csv" in job.formats:
                csv_bytes = await anyio.to_thread.run_sync(_render_csv, entries)
                csv_key = await storage_save(
                    uuid.UUID(tenant_id), "audit-trail/reports", csv_bytes, "text/csv"
                )
            if "pdf" in job.formats:
                pdf_bytes = await anyio.to_thread.run_sync(_render_pdf, entries)
                pdf_key = await storage_save(
                    uuid.UUID(tenant_id), "audit-trail/reports", pdf_bytes, "application/pdf"
                )
            await job_repo.mark_ready(job, csv_storage_key=csv_key, pdf_storage_key=pdf_key)
            await session.commit()
    finally:
        # Fresh `asyncio.run()` per task execution; `engine` is one
        # process-wide `AsyncEngine` bound to whichever loop last used it —
        # see `reports/tasks.py` for the same requirement.
        await engine.dispose()


async def _mark_job_failed(job_id: str, tenant_schema: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            job_repo = AuditReportJobRepository(session)
            job = await job_repo.get(uuid.UUID(job_id))
            if job is None or job.status != "pending":
                return
            await job_repo.mark_failed(job, error_message="Report generation failed.")
            await session.commit()
    finally:
        await engine.dispose()


async def _fetch_entries(session: AsyncSession, job: AuditReportJob) -> list[AuditLog]:
    f = job.filters
    return await AuditLogRepository(session).list_all(
        actor_user_id=uuid.UUID(f["actor_user_id"]) if f.get("actor_user_id") else None,
        action=f.get("action"),
        entity_type=f.get("entity_type"),
        entity_id=uuid.UUID(f["entity_id"]) if f.get("entity_id") else None,
        created_after=datetime.fromisoformat(f["created_after"])
        if f.get("created_after")
        else None,
        created_before=datetime.fromisoformat(f["created_before"])
        if f.get("created_before")
        else None,
    )


def _entry_row(entry: AuditLog) -> list[str]:
    return [
        str(entry.id),
        str(entry.actor_user_id) if entry.actor_user_id else "",
        entry.action,
        entry.entity_type,
        str(entry.entity_id) if entry.entity_id else "",
        entry.created_at.isoformat(),
    ]


def _render_csv(entries: list[AuditLog]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_REPORT_HEADERS)
    for entry in entries:
        writer.writerow(_entry_row(entry))
    return buffer.getvalue().encode("utf-8")


def _render_pdf(entries: list[AuditLog]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    rows = [_REPORT_HEADERS, *[_entry_row(entry) for entry in entries]]
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
            ]
        )
    )
    doc.build([table])
    return buffer.getvalue()
