"""Async push dispatch for `notifications` (add-invitation-push-
notifications). Mirrors `invitations/tasks.py`'s shape exactly: resolves its
own tenant-bound session from a `tenant_schema` argument
(`background-jobs.md` §4), binds `request_id`/`tenant_schema` into
`structlog`'s context at the top of the body (`logging-observability.md`
§1), and disposes the shared engine before returning so a second task on a
new event loop doesn't reuse a connection bound to this one (see
`invitations/tasks.py`'s own docstring for why).

Takes `user_ids`, not device tokens, as its enqueue-time argument
(design.md Decision 2) — devices for those users are resolved fresh inside
the task body, since which devices a user currently has can change between
enqueue and task execution, but *who* the recipient is (already resolved by
the caller) should not be re-derived here.
"""

import asyncio
import uuid

import structlog

from vmss_api.core.celery_app import celery_app
from vmss_api.core.database import engine, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.notifications import fcm
from vmss_api.notifications.repository import DeviceTokenRepository

_RETRY_KWARGS = {
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "max_retries": 5,
}


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_push(
    self,
    *,
    request_id: str,
    tenant_schema: str,
    user_ids: list[str],
    title: str,
    body: str,
    data: dict[str, str],
) -> None:
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_push(tenant_schema, user_ids, title, body, data))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "push_dispatch_exhausted",
                tenant_schema=tenant_schema,
                user_ids=user_ids,
            )
        raise


async def _send_push(
    tenant_schema: str, user_ids: list[str], title: str, body: str, data: dict[str, str]
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            repo = DeviceTokenRepository(session)
            devices = await repo.list_tokens_for_users([uuid.UUID(u) for u in user_ids])
            # A resolved recipient with zero registered devices is not an
            # error (specs/notifications/spec.md "Recipient has no
            # registered device") — nothing to send, nothing to clean up.
            if not devices:
                return
            messages = [
                fcm.PushMessage(token=device.fcm_token, title=title, body=body, data=data)
                for device in devices
            ]
            results = await fcm.push_sender.send_each(messages)
            invalid_tokens = [result.token for result in results if result.token_invalid]
            if invalid_tokens:
                await repo.delete_by_tokens(invalid_tokens)
                await session.commit()
            failed = [r for r in results if not r.success and not r.token_invalid]
            if failed:
                logger.warning(
                    "push_dispatch_partial_failure",
                    tenant_schema=tenant_schema,
                    failed_count=len(failed),
                    total_count=len(results),
                )
                raise fcm.PushDeliveryError(
                    f"{len(failed)} of {len(results)} push sends failed"
                )
    finally:
        await engine.dispose()
