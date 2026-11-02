"""Per-recipient "already sent" markers for notification tasks
(background-jobs.md §2, audit-and-harden-api-and-web design.md D3).

A Celery retry or broker redelivery re-runs a task under the *same* task id,
while every new logical event is a new `.delay()` with a new id — so
`(task id, channel, recipient)` identifies exactly one intended send. The
marker is written only after the provider call succeeds, which also makes a
multi-recipient loop resumable: a retry after a mid-loop failure skips the
recipients already reached instead of messaging them twice.

Outside a Celery task (a direct call from a test) there is no task id and
every send goes through unchanged. If Redis is unreachable the send still
happens: a rare duplicate beats a notification that never goes out.
"""

import hashlib
from collections.abc import Awaitable, Callable

from celery import current_task
from redis.asyncio import from_url as redis_from_url

from vmss_api.core.config import settings
from vmss_api.core.logging import logger

SENT_MARKER_TTL_SECONDS = 7 * 24 * 60 * 60


def _current_task_id() -> str | None:
    request = getattr(current_task, "request", None)
    return getattr(request, "id", None) if request is not None else None


def _marker_key(tenant_scope: str, task_id: str, channel: str, recipient: str) -> str:
    recipient_hash = hashlib.sha256(recipient.strip().lower().encode()).hexdigest()[:24]
    return f"vmss:{tenant_scope}:notifications:sent:{task_id}:{channel}:{recipient_hash}"


async def send_once(
    *,
    tenant_scope: str,
    channel: str,
    recipient: str,
    send: Callable[[], Awaitable[None]],
) -> bool:
    """Runs `send` unless this task execution already delivered to
    `recipient` on `channel`. Returns whether `send` ran.

    `tenant_scope` is the tenant's schema name: notification tasks are
    enqueued with the schema, not the tenant id.
    """
    task_id = _current_task_id()
    if task_id is None:
        await send()
        return True
    key = _marker_key(tenant_scope, task_id, channel, recipient)
    # A dedicated client per call: each task body runs in its own
    # `asyncio.run()` loop, and the shared `core/redis.py` client's pooled
    # connections can't cross loops (same hazard as `engine.dispose()`).
    redis = redis_from_url(settings.redis_url, decode_responses=True)
    try:
        try:
            if await redis.exists(key):
                logger.info("notification_already_sent", channel=channel, tenant_scope=tenant_scope)
                return False
        except Exception:
            logger.warning("notification_dedupe_unavailable", channel=channel, exc_info=True)
            await send()
            return True
        await send()
        try:
            await redis.set(key, "1", ex=SENT_MARKER_TTL_SECONDS)
        except Exception:
            logger.warning("notification_dedupe_mark_failed", channel=channel, exc_info=True)
        return True
    finally:
        await redis.aclose()
