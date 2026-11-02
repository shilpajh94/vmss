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
from celery import Task
from sqlalchemy.exc import SQLAlchemyError

from vmss_api.core.celery_app import DEFAULT_RETRY_KWARGS, celery_app
from vmss_api.core.database import engine, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.notifications import fcm
from vmss_api.notifications.repository import DeviceTokenRepository, NotificationRepository

_RETRY_KWARGS = DEFAULT_RETRY_KWARGS


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_push(
    self: Task,
    *,
    request_id: str,
    tenant_schema: str,
    user_ids: list[str],
    title: str,
    body: str,
    data: dict[str, str],
    dispatch_id: str | None = None,
) -> None:
    """`dispatch_id` keys the in-app notification rows so a redelivery or
    retry doesn't duplicate them. Optional only so a task enqueued before
    this argument existed still runs (it then gets a fresh id, without the
    dedupe).
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    resolved_dispatch_id = uuid.UUID(dispatch_id) if dispatch_id else uuid.uuid4()
    try:
        asyncio.run(
            _send_push(tenant_schema, user_ids, title, body, data, dispatch_id=resolved_dispatch_id)
        )
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "push_dispatch_exhausted",
                tenant_schema=tenant_schema,
                user_ids=user_ids,
            )
        raise


async def _send_push(
    tenant_schema: str,
    user_ids: list[str],
    title: str,
    body: str,
    data: dict[str, str],
    *,
    dispatch_id: uuid.UUID,
) -> None:
    recipient_ids = [uuid.UUID(u) for u in user_ids]
    try:
        async with tenant_session_scope(tenant_schema) as session:
            # Recorded and committed before any FCM call, so the in-app copy
            # exists even when every send fails (fix-web-push-and-add-
            # notification-feed design.md D1). A recording failure is logged
            # and never blocks the push itself — retrying the whole task
            # for it would also re-send to every device.
            try:
                await NotificationRepository(session).record_for_users(
                    dispatch_id=dispatch_id,
                    user_ids=recipient_ids,
                    title=title,
                    body=body,
                    data=data,
                )
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                logger.warning(
                    "notification_record_failed",
                    tenant_schema=tenant_schema,
                    dispatch_id=str(dispatch_id),
                    recipient_count=len(recipient_ids),
                    exc_info=True,
                )
            repo = DeviceTokenRepository(session)
            devices = await repo.list_tokens_for_users(recipient_ids)
            # A resolved recipient with zero registered devices is not an
            # error (specs/notifications/spec.md "Recipient has no
            # registered device") — but logged, so a push that reached
            # nobody isn't indistinguishable from a delivered one.
            if not devices:
                logger.info(
                    "push_no_registered_devices",
                    tenant_schema=tenant_schema,
                    recipient_count=len(recipient_ids),
                )
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
                raise fcm.PushDeliveryError(f"{len(failed)} of {len(results)} push sends failed")
    finally:
        await engine.dispose()
