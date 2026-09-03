"""Async dispatch for `invitations` (API-11). Every task resolves its own
tenant-bound session from a `tenant_schema` argument (`background-jobs.md`
§4) — never the request's session, which is long closed by the time a task
runs — and binds `request_id`/`tenant_schema` into `structlog`'s context at
the top of the body (`logging-observability.md` §1) so a failed send is
traceable back to the request that triggered it.

Two distinct notifications, not one with a conditional attachment
(`add-invitation-approval-flow-and-role-resync/design.md` Decision 2):
`send_approval_notification` (tracking ID + QR code) is only ever enqueued
once an invitation is actually `approved` — at creation when the tenant
auto-approves, or later via `POST /invitations/{id}/approve`.
`send_tracking_notification` (tracking ID only, no QR) is enqueued when
creation instead leaves the invitation `submitted` (awaiting approval).

`send_approval_notification` takes the already-encrypted `qr_token` as an
explicit argument rather than deriving it itself
(`add-qr-checkin-security/design.md`) — the token is generated and
persisted once, at approval time, by the service layer (which already has
a real tenant-bound session in hand); the task only ever renders the QR
image from it and attaches it, with no database read of its own for the
token.
"""

import asyncio
import uuid

import structlog

from vmss_api.core.celery_app import celery_app
from vmss_api.core.database import engine, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.invitations import notifications
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.qr import generate_qr_png

_RETRY_KWARGS = {
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "max_retries": 5,
}


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_approval_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str, qr_token: str
) -> None:
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_approval_notification(tenant_schema, invitation_id, qr_token))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "approval_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
            )
        raise


async def _send_approval_notification(
    tenant_schema: str, invitation_id: str, qr_token: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            # Idempotent against redelivery/retry (background-jobs.md §2): a
            # missing invitation (the row somehow removed since the task was
            # enqueued) has nothing left to notify about. There's no separate
            # "already notified" flag to guard on beyond that — creation and
            # the approve action each enqueue this exactly once, atomically
            # with the state change that triggered it, so the only source of
            # a duplicate send is Celery's own at-least-once redelivery,
            # which the idempotency-key cache on the creating request already
            # bounds (api-conventions.md §3).
            if invitation is None:
                return
            subject = "Your visit is confirmed"
            body = (
                f"Your registration is confirmed. Tracking ID: {invitation.tracking_id}.\n"
                "Present the attached QR code at check-in."
            )
            qr_png = await generate_qr_png(qr_token)
            await _dispatch(
                invitation,
                subject=subject,
                body=body,
                attachment=notifications.make_attachment(qr_png, "visit-qr.png", "image/png"),
            )
    finally:
        # `send_approval_notification`/`send_tracking_notification` below run
        # this coroutine via a fresh `asyncio.run()` call per task, but
        # `core/database.py::engine` is a single, process-wide `AsyncEngine`
        # built once at import — its pooled asyncpg connections are bound to
        # whichever loop first used them. A worker process handling a second
        # task on a new loop would otherwise reuse a connection tied to this
        # (about-to-close) loop and fail with "got Future ... attached to a
        # different loop" (reproduced directly once a real worker processed
        # more than one task — see SQLAlchemy's asyncio docs on disposing an
        # engine before switching event loops).
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_tracking_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_tracking_notification(tenant_schema, invitation_id))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "tracking_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
            )
        raise


async def _send_tracking_notification(tenant_schema: str, invitation_id: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            if invitation is None:
                return
            subject = "Your registration is received"
            body = (
                f"Your registration is awaiting approval. Tracking ID: "
                f"{invitation.tracking_id}.\n"
                "You'll receive a check-in QR code once it's approved."
            )
            await _dispatch(invitation, subject=subject, body=body)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_denial_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """add-invitation-lifecycle-actions/design.md Decision 7: structurally
    identical to `send_tracking_notification` above — same tenant-scoped
    session, `request_id` context binding, retry policy, and `_dispatch`
    helper — only the subject/body differ.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_denial_notification(tenant_schema, invitation_id))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "denial_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
            )
        raise


async def _send_denial_notification(tenant_schema: str, invitation_id: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            if invitation is None:
                return
            subject = "Your visit request was not approved"
            body = (
                f"Your registration was not approved. Tracking ID: "
                f"{invitation.tracking_id}.\n"
                f"Reason: {invitation.denial_reason}"
            )
            await _dispatch(invitation, subject=subject, body=body)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_reschedule_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """add-reschedule-notification/design.md: structurally identical to
    `send_denial_notification` above — same tenant-scoped session,
    `request_id` context binding, retry policy, and `_dispatch` helper —
    only the subject/body differ.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_reschedule_notification(tenant_schema, invitation_id))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "reschedule_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
            )
        raise


async def _send_reschedule_notification(tenant_schema: str, invitation_id: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            if invitation is None:
                return
            subject = "Your visit has been rescheduled"
            body = (
                f"Your visit has been rescheduled. New date: "
                f"{invitation.preferred_visit_date}, time: "
                f"{invitation.preferred_visit_time}. Tracking ID: "
                f"{invitation.tracking_id}."
            )
            await _dispatch(invitation, subject=subject, body=body)
    finally:
        await engine.dispose()


async def _dispatch(invitation: Invitation, *, subject: str, body: str, attachment=None) -> None:
    """Routes to email or SMS per the invitation's `preferred_contact_method`
    — never both. The `assert`s below are a data-integrity check, not
    optional-narrowing convenience: `schemas.py`'s validators already
    guarantee the contact info for the chosen method is present, so a
    failure here means that guarantee was violated somewhere upstream, and
    it's correct to let this raise loudly rather than silently no-op.
    """
    if invitation.primary_contact_preferred_contact_method == "email":
        assert invitation.primary_contact_email is not None
        await notifications.email_sender.send(
            to=invitation.primary_contact_email, subject=subject, body=body, attachment=attachment
        )
    else:
        assert invitation.primary_contact_phone is not None
        await notifications.sms_sender.send(to=invitation.primary_contact_phone, body=body)
