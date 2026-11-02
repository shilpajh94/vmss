"""Async dispatch for the daily rollup snapshot job (API-17,
add-background-jobs-and-integration-tests). Two tasks, deliberately split so
one tenant's failure can't block another's (`background-jobs` capability's
"Scheduled Tasks Run Independently of Any Request" requirement):

- `dispatch_daily_rollup_snapshots` — the only Celery-beat-triggered task in
  this codebase (`core/celery_app.py`'s `beat_schedule`). Lists every active
  tenant and enqueues the per-tenant task for each one. Never touches a
  tenant schema and never sends anything itself.
- `send_tenant_rollup_snapshot` — resolves one tenant's session, computes
  the same rollup `GET /reports/branches/rollup` reports, and emails a
  summary to that tenant's Admin-role users. Guarded against redelivery by
  a Redis run-marker (`database-architecture.md` §6's key convention),
  since a beat-triggered task has no client-supplied idempotency key to
  reuse the way `invitations`/`registrations` do.
"""

import asyncio
from datetime import UTC, datetime
from functools import partial
from types import SimpleNamespace
from typing import Any

import structlog
from celery import Task
from redis.asyncio import from_url as redis_from_url

from vmss_api.core.celery_app import DEFAULT_RETRY_KWARGS, celery_app
from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, engine, tenant_session_scope
from vmss_api.core.email_rendering import TemplateRenderError, render_email
from vmss_api.core.emailing import email_sender
from vmss_api.core.logging import logger
from vmss_api.core.notification_dedupe import send_once
from vmss_api.org_structure.models import Company
from vmss_api.org_structure.repository import CompanyRepository
from vmss_api.reports import service
from vmss_api.reports.repository import BranchRollupRepository
from vmss_api.reports.schemas import CrossBranchRollupOut
from vmss_api.tenant.repository import TenantRepository

_RETRY_KWARGS = DEFAULT_RETRY_KWARGS

# A little over one day, so a retry near a UTC-midnight boundary can't fall
# through the marker expiring before the same scheduled run finishes.
_SNAPSHOT_MARKER_TTL_SECONDS = 26 * 60 * 60


@celery_app.task(bind=True)
def dispatch_daily_rollup_snapshots(self: Task) -> None:
    structlog.contextvars.bind_contextvars(task="dispatch_daily_rollup_snapshots")
    asyncio.run(_dispatch_daily_rollup_snapshots())


async def _dispatch_daily_rollup_snapshots() -> None:
    try:
        async with AsyncSessionLocal() as session:
            tenants = await TenantRepository(session).list_active()
    finally:
        # Same cross-event-loop connection-reuse hazard `invitations/tasks.py`
        # documents: this coroutine runs via a fresh `asyncio.run()` per beat
        # tick, but `engine` is one process-wide `AsyncEngine`.
        await engine.dispose()
    for tenant in tenants:
        # One tenant's enqueue failing (e.g. a broker hiccup) must not skip
        # every tenant after it in this same run (`background-jobs`
        # capability: "one tenant's failure does not block another's").
        try:
            send_tenant_rollup_snapshot.delay(
                tenant_id=str(tenant.id), tenant_schema=tenant.schema_name
            )
        except Exception:
            logger.error(
                "reports_snapshot_dispatch_enqueue_failed",
                tenant_id=str(tenant.id),
                tenant_schema=tenant.schema_name,
            )


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_tenant_rollup_snapshot(self: Task, *, tenant_id: str, tenant_schema: str) -> None:
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_tenant_rollup_snapshot(tenant_id, tenant_schema))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "reports_snapshot_dispatch_exhausted",
                tenant_id=tenant_id,
                tenant_schema=tenant_schema,
            )
        raise


async def _send_tenant_rollup_snapshot(tenant_id: str, tenant_schema: str) -> None:
    today = datetime.now(UTC).date().isoformat()
    marker_key = f"vmss:{tenant_id}:reports:snapshot-sent:{today}"
    # A dedicated client for this call, not `core/redis.py`'s shared
    # module-level `redis_client` — same cross-event-loop connection-reuse
    # hazard `engine`/`engine.dispose()` above works around: this coroutine
    # runs via a fresh `asyncio.run()` per task execution, and a pooled
    # connection from a prior execution's loop can't be reused on this one.
    redis = redis_from_url(settings.redis_url, decode_responses=True)
    try:
        already_sent = await redis.exists(marker_key)
    finally:
        await redis.aclose()
    if already_sent:
        # Idempotent against redelivery (background-jobs.md §2): another
        # execution of this task already sent today's snapshot.
        return
    try:
        async with tenant_session_scope(tenant_schema) as session:
            rollup = await service.get_cross_branch_rollup(session)
            admins = await BranchRollupRepository(session).admin_users()
            if not admins:
                # Expected, not broken — a tenant can legitimately have no
                # Admin-role user yet. INFO, not ERROR.
                logger.info(
                    "reports_snapshot_no_admin_recipients",
                    tenant_id=tenant_id,
                    tenant_schema=tenant_schema,
                )
                return
            company = await CompanyRepository(session).get_singleton()
            context = _snapshot_context(rollup, company)
            for admin in admins:
                subject, body, html_body = _render_snapshot_email(
                    rollup,
                    {**context, "recipient_name": admin.full_name, "recipient_email": admin.email},
                )
                # Per-recipient marker: a retry after a mid-loop failure
                # skips the admins already emailed (design.md D3).
                await send_once(
                    tenant_scope=tenant_id,
                    channel="email",
                    recipient=admin.email,
                    send=partial(
                        email_sender.send,
                        to=admin.email,
                        subject=subject,
                        body=body,
                        html_body=html_body,
                    ),
                )
    finally:
        await engine.dispose()
    # Marked only once every recipient succeeded, so a failed send is retried
    # instead of being swallowed by a marker written up front.
    redis = redis_from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.set(marker_key, "1", ex=_SNAPSHOT_MARKER_TTL_SECONDS)
    finally:
        await redis.aclose()


def _snapshot_context(rollup: CrossBranchRollupOut, company: Company | None) -> dict[str, Any]:
    return {
        "company_name": company.legal_name if company is not None else None,
        "logo_url": company.logo_url if company is not None else None,
        "report_date": datetime.now(UTC).date(),
        "total_branches": rollup.total_branches,
        "totals": SimpleNamespace(
            buildings=rollup.total_buildings,
            floors=rollup.total_floors,
            departments=rollup.total_departments,
            reception_desks=rollup.total_reception_desks,
            security_gates=rollup.total_security_gates,
            active_employees=rollup.total_active_employees,
        ),
        "branches": rollup.branches,
    }


def _render_snapshot_email(
    rollup: CrossBranchRollupOut, context: dict[str, Any]
) -> tuple[str, str, str | None]:
    """reports spec "The Rollup Snapshot Email Uses the Branded Snapshot
    Template" — `(subject, text, html)`, degrading to the original
    plain-text summary if the template fails to render.
    """
    try:
        rendered = render_email("daily_snapshot", context)
    except TemplateRenderError:
        logger.error("email_template_render_failed", template_name="daily_snapshot")
        return "Daily branch rollup snapshot", _render_snapshot_body(rollup), None
    return rendered.subject, rendered.text, rendered.html


def _render_snapshot_body(rollup: CrossBranchRollupOut) -> str:
    lines = [f"Cross-branch rollup — {rollup.total_branches} branch(es).", ""]
    for branch in rollup.branches:
        lines.append(
            f"- {branch.branch_name} ({branch.branch_code}): "
            f"{branch.building_count} building(s), {branch.floor_count} floor(s), "
            f"{branch.department_count} department(s), "
            f"{branch.reception_desk_count} reception desk(s), "
            f"{branch.security_gate_count} security gate(s), "
            f"{branch.active_employee_count} active employee(s)."
        )
    lines += [
        "",
        (
            f"Totals: {rollup.total_buildings} building(s), {rollup.total_floors} floor(s), "
            f"{rollup.total_departments} department(s), "
            f"{rollup.total_reception_desks} reception desk(s), "
            f"{rollup.total_security_gates} security gate(s), "
            f"{rollup.total_active_employees} active employee(s)."
        ),
    ]
    return "\n".join(lines)
