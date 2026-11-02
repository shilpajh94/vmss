import uuid
from typing import Any

from vmss_api.auth.repository import AuditLogWriter
from vmss_api.core.database import tenant_session_scope


async def record_audit_log(
    schema_name: str,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    diff: dict[str, Any] | None = None,
) -> None:
    """Writes one `AuditLog` row for a mutating action, per
    security-architecture.md §5. Intended to run via FastAPI's
    `BackgroundTasks` (`background_tasks.add_task(record_audit_log, ...)`)
    so it executes after the response is sent — "must not block the request
    path" per that same rule — rather than inline in the request handler.

    Opens its own tenant-bound session instead of reusing the request's: by
    the time a background task runs, the request's session (yielded by
    `get_tenant_db`) has already been closed.
    """
    async with tenant_session_scope(schema_name) as session:
        AuditLogWriter(session).add(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            diff=diff,
        )
        await session.commit()
