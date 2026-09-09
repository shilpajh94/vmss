"""Tenant-scoped audit trail history: filterable/paginated listing and
detail view of recorded `AuditLog` entries, plus asynchronous CSV/PDF report
generation and time-boxed download
(`openspec/changes/add-audit-trail-history`). Company-wide, not
branch-scoped — same posture as `reports/router.py`.

Static sub-paths (`/reports`, `/reports/{job_id}`) are registered before the
generic `/{audit_log_id}` route below so FastAPI doesn't try to match
`"reports"` against the `uuid.UUID` path converter first.
"""

import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.audit_trail import service
from vmss_api.audit_trail.schemas import (
    AuditLogDetailOut,
    AuditLogOut,
    AuditLogSortableField,
    AuditReportJobOut,
    AuditReportRequest,
    ReportFormat,
)
from vmss_api.audit_trail.service import (
    ReportFileNotAvailableError,
    ReportJobNotFoundError,
    ReportStorageError,
)
from vmss_api.auth.models import User
from vmss_api.core.deps import get_pagination, get_tenant, get_tenant_db, require_permission
from vmss_api.core.logging import logger
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import error_response, paginated_response, success_response
from vmss_api.core.schemas import Envelope, PaginatedEnvelope, SortOrder
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/audit-trail", tags=["audit-trail"])

_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


def _idempotency_cache_key(tenant_id: uuid.UUID, idempotency_key: str) -> str:
    return f"vmss:{tenant_id}:audit-trail:idempotency:{idempotency_key}"


async def _cached_response(
    tenant_id: uuid.UUID, idempotency_key: str | None
) -> JSONResponse | None:
    """api-conventions.md §3 — a retried report request with the same
    `Idempotency-Key` returns the original response instead of enqueueing a
    second Celery job.
    """
    if idempotency_key is None:
        return None
    redis = await get_redis()
    cached = await redis.get(_idempotency_cache_key(tenant_id, idempotency_key))
    if cached is None:
        return None
    payload = json.loads(cached)
    return JSONResponse(content=payload["body"], status_code=payload["status"])


async def _cache_response(
    tenant_id: uuid.UUID, idempotency_key: str | None, response: JSONResponse
) -> None:
    if idempotency_key is None:
        return
    redis = await get_redis()
    await redis.set(
        _idempotency_cache_key(tenant_id, idempotency_key),
        json.dumps({"status": response.status_code, "body": json.loads(bytes(response.body))}),
        ex=_IDEMPOTENCY_TTL_SECONDS,
    )


@router.get(
    "",
    response_model=PaginatedEnvelope[AuditLogOut],
    dependencies=[Depends(require_permission("audit-logs:view"))],
)
async def list_audit_trail(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    actor_user_id: Annotated[uuid.UUID | None, Query(alias="actorUserId")] = None,
    action: Annotated[str | None, Query()] = None,
    entity_type: Annotated[str | None, Query(alias="entityType")] = None,
    entity_id: Annotated[uuid.UUID | None, Query(alias="entityId")] = None,
    created_after: Annotated[datetime | None, Query(alias="createdAfter")] = None,
    created_before: Annotated[datetime | None, Query(alias="createdBefore")] = None,
    sort_by: Annotated[AuditLogSortableField, Query(alias="sortBy")] = "created_at",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
) -> JSONResponse:
    page, page_size = pagination
    entries, total = await service.list_audit_logs(
        tenant_db,
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
    logger.info("audit_trail_listed", result_count=len(entries))
    return paginated_response(
        data=[AuditLogOut.model_validate(entry) for entry in entries],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/reports",
    response_model=Envelope[AuditReportJobOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_audit_report(
    payload: AuditReportRequest,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(require_permission("audit-logs:export"))],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional. Omitting it forgoes retry-dedup safety — a "
                "retried request with no key enqueues a second report job. "
                "See api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    job = await service.request_audit_report(
        tenant_db,
        tenant_id=tenant.id,
        tenant_schema=tenant.schema_name,
        requested_by_user_id=user.id,
        formats=list(payload.formats),
        actor_user_id=payload.actor_user_id,
        action=payload.action,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        created_after=payload.created_after,
        created_before=payload.created_before,
    )
    logger.info("audit_report_requested", job_id=str(job.id), formats=payload.formats)
    job_out = await service.to_report_job_out(job)
    response = success_response(data=job_out, status_code=status.HTTP_202_ACCEPTED)
    await _cache_response(tenant.id, idempotency_key, response)
    return response


@router.get(
    "/reports/{job_id}",
    response_model=Envelope[AuditReportJobOut],
    dependencies=[Depends(require_permission("audit-logs:export"))],
)
async def get_audit_report(
    job_id: uuid.UUID, tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]
) -> JSONResponse:
    try:
        job_out = await service.get_report_job(tenant_db, job_id)
    except ReportJobNotFoundError:
        return error_response(message="Report job not found", status_code=status.HTTP_404_NOT_FOUND)
    return success_response(data=job_out)


@router.get(
    "/reports/{job_id}/download",
    dependencies=[Depends(require_permission("audit-logs:export"))],
)
async def download_audit_report(
    job_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    fmt: Annotated[ReportFormat, Query(alias="format")],
) -> Response:
    """Streams a `ready` report job's generated file. Not JSON, so it's the
    documented exception to `fastapi-architecture.md` §5's
    `success_response`/`error_response` rule (a raw file response) — error
    cases below still use `error_response` since those *are* JSON.
    """
    try:
        content, content_type, filename = await service.get_report_file(tenant_db, job_id, fmt)
    except ReportJobNotFoundError:
        return error_response(message="Report job not found", status_code=status.HTTP_404_NOT_FOUND)
    except ReportFileNotAvailableError:
        return error_response(
            message="Report file is not available", status_code=status.HTTP_404_NOT_FOUND
        )
    except ReportStorageError as exc:
        # Caught here (rather than left to the global handler) specifically
        # so this still returns through the router's normal path: an
        # exception raised for the bare `Exception` class unwinds past
        # `CORSMiddleware` entirely (core/middleware.py's
        # `unhandled_exception_handler` docstring) and a client would see a
        # misleading CORS error instead of this 500.
        logger.error("audit_report_storage_error", job_id=str(job_id), format=fmt, error=str(exc))
        return error_response(
            message="Report file could not be retrieved",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    logger.info("audit_report_downloaded", job_id=str(job_id), format=fmt)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{audit_log_id}",
    response_model=Envelope[AuditLogDetailOut],
    dependencies=[Depends(require_permission("audit-logs:view"))],
)
async def get_audit_trail_entry(
    audit_log_id: uuid.UUID, tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]
) -> JSONResponse:
    entry = await service.get_audit_log(tenant_db, audit_log_id)
    if entry is None:
        return error_response(
            message="Audit log entry not found", status_code=status.HTTP_404_NOT_FOUND
        )
    logger.info("audit_trail_entry_viewed", audit_log_id=str(audit_log_id))
    return success_response(data=AuditLogDetailOut.model_validate(entry))
