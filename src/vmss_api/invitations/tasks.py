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
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.repository import UserRepository
from vmss_api.core.celery_app import celery_app
from vmss_api.core.database import engine, tenant_session_scope
from vmss_api.core.email_rendering import TemplateRenderError, render_email_html
from vmss_api.core.logging import logger
from vmss_api.invitations import notifications
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.org_structure.repository import CompanyRepository


async def _base_email_context(session: AsyncSession) -> dict[str, Any]:
    """Shared branding context every template's `base.html` layout reads —
    resolved once per dispatch, not hardcoded, so a tenant's own Company
    profile controls its emails' branding.
    """
    company = await CompanyRepository(session).get_singleton()
    return {
        "company_name": company.legal_name if company is not None else None,
        "logo_url": company.logo_url if company is not None else None,
    }


def _render_html_or_none(template_name: str, context: dict[str, Any]) -> str | None:
    """spec.md "Template Rendering Failure Falls Back to a Minimal
    Plain-Text Email" — `None` tells the caller to send with no `html_body`,
    which degrades to the plain-text part it already built (that plain text
    *is* the minimal fallback; there is no separate one to construct).
    """
    try:
        _subject, html_body = render_email_html(template_name, context)
        return html_body
    except TemplateRenderError:
        logger.error("email_template_render_failed", template_name=template_name)
        return None


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
            # spec.md "Approval Notification Email Includes Full Visit and
            # Host Detail" — the resolved host's name/contact when one
            # exists by approval time, otherwise the tenant's own Company
            # contact channel in its place (role-based-invitation-workflow).
            host_name = None
            host_contact = None
            if invitation.host_id is not None:
                host = await UserRepository(session).get_active(invitation.host_id)
                if host is not None:
                    host_name = host.full_name
                    host_contact = host.phone_number or host.email
            company = await CompanyRepository(session).get_singleton()
            front_desk_contact = (company.phone or company.email) if company is not None else None
            html_body = _render_html_or_none(
                "visit_confirmation",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "purpose": invitation.purpose_of_visit,
                    "visit_date": invitation.preferred_visit_date,
                    "visit_time": invitation.preferred_visit_time,
                    "duration": invitation.expected_duration,
                    "department": invitation.department_to_visit,
                    "host_name": host_name,
                    "host_contact": host_contact,
                    "front_desk_contact": front_desk_contact,
                },
            )
            qr_png = await generate_qr_png(qr_token)
            await _dispatch(
                invitation,
                subject=subject,
                body=body,
                html_body=html_body,
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
            html_body = _render_html_or_none(
                "tracking_only",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "purpose": invitation.purpose_of_visit,
                    "visit_date": invitation.preferred_visit_date,
                    "visit_time": invitation.preferred_visit_time,
                },
            )
            await _dispatch(invitation, subject=subject, body=body, html_body=html_body)
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
            html_body = _render_html_or_none(
                "denial",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "denial_reason": invitation.denial_reason,
                },
            )
            await _dispatch(invitation, subject=subject, body=body, html_body=html_body)
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
            html_body = _render_html_or_none(
                "reschedule",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "visit_date": invitation.preferred_visit_date,
                    "visit_time": invitation.preferred_visit_time,
                },
            )
            await _dispatch(invitation, subject=subject, body=body, html_body=html_body)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_edit_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """role-based-invitation-workflow: structurally identical to
    `send_reschedule_notification` above — same tenant-scoped session,
    `request_id` context binding, retry policy, and `_dispatch` helper —
    only the subject/body differ. Fires on a successful `PATCH
    /invitations/{id}/edit`, to the primary contact; the resolved host (if
    any) is separately notified via push (`invitations/service.py::
    edit_invitation`), not this email.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_edit_notification(tenant_schema, invitation_id))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "edit_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
            )
        raise


async def _send_edit_notification(tenant_schema: str, invitation_id: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            if invitation is None:
                return
            subject = "Your visit details have been updated"
            body = (
                "Some details of your upcoming visit have changed. Tracking "
                f"ID: {invitation.tracking_id}.\n"
                f"Purpose: {invitation.purpose_of_visit or 'Not specified'}\n"
                f"Date: {invitation.preferred_visit_date}, time: "
                f"{invitation.preferred_visit_time}\n"
                f"Duration: {invitation.expected_duration or 'Not specified'}\n"
                f"Department: {invitation.department_to_visit or 'Not specified'}"
            )
            html_body = _render_html_or_none(
                "edit",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "purpose": invitation.purpose_of_visit,
                    "visit_date": invitation.preferred_visit_date,
                    "visit_time": invitation.preferred_visit_time,
                    "duration": invitation.expected_duration,
                    "department": invitation.department_to_visit,
                    "poc_name": invitation.poc_name,
                },
            )
            await _dispatch(invitation, subject=subject, body=body, html_body=html_body)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_submission_role_email_notification(
    self,
    *,
    request_id: str,
    tenant_schema: str,
    invitation_id: str,
    role_id: str,
    branch_id: str,
) -> None:
    """role-based-invitation-workflow, spec.md "Invitation Submission
    Notifies the Owning Role via Email" — additive to the existing
    submission push (`notifications_service.notify_step_approver`), fired
    with whichever role the invitation's first (host-nomination) step is
    role-identified for — always true for a non-auto-approved invitation now
    (`invitations/service.py::_build_approval_steps`).
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(
            _send_submission_role_email_notification(
                tenant_schema, invitation_id, role_id, branch_id
            )
        )
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "submission_role_email_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
                role_id=role_id,
            )
        raise


async def _send_submission_role_email_notification(
    tenant_schema: str, invitation_id: str, role_id: str, branch_id: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            if invitation is None:
                return
            users = await UserRepository(session).list_users_holding_role_at_branch(
                uuid.UUID(role_id), uuid.UUID(branch_id)
            )
            if not users:
                # No one currently holds this role at this branch — nothing
                # to notify. Logged, not just returned, because unlike a
                # deleted invitation (benign) this means a role/branch
                # staffing gap silently ate a submission notification.
                logger.warning(
                    "submission_role_email_notification_no_recipients",
                    tenant_schema=tenant_schema,
                    invitation_id=invitation_id,
                    role_id=role_id,
                    branch_id=branch_id,
                )
                return
            subject = "New invitation awaiting triage"
            body = (
                "A new invitation awaits your team's triage.\n"
                f"Tracking ID: {invitation.tracking_id}\n"
                f"Visitor: {invitation.primary_contact_full_name}\n"
                f"Purpose: {invitation.purpose_of_visit or 'Not specified'}"
            )
            html_body = _render_html_or_none(
                "submission_role",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "visitor_name": invitation.primary_contact_full_name,
                    "purpose": invitation.purpose_of_visit,
                },
            )
            for role_user in users:
                # Defensive: `User.email` is a required column today, so
                # this never actually skips anyone — kept so a future schema
                # change (or a row this repository call somehow returns with
                # a blank email) degrades to "skip that one recipient"
                # rather than failing the whole dispatch.
                if not role_user.email:
                    continue
                await notifications.email_sender.send(
                    to=role_user.email, subject=subject, body=body, html_body=html_body
                )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_host_creation_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str, host_id: str
) -> None:
    """Emails the newly resolved host that they've been named host of an
    invitation — a distinct task from the visitor confirmation dispatch
    above, since the recipient (the host, resolved via `UserRepository`) and
    their email address are unrelated to the primary contact's own
    `preferred_contact_method`. Originally fired at creation time when a
    client-supplied host resolved; now fired instead when the invitation's
    ownership step is delegated to a specific person
    (`approvals/service.py::delegate_step`, role-based-invitation-workflow),
    since a host can no longer resolve at creation. `host_id` is passed
    explicitly (resolved by the caller before enqueueing) rather than
    re-derived from `invitation.host_id` here, so an exhausted-retries log
    always names which host went unnotified even if the invitation itself
    has since changed.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_host_creation_notification(tenant_schema, invitation_id, host_id))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "host_creation_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
                host_id=host_id,
            )
        raise


async def _send_host_creation_notification(
    tenant_schema: str, invitation_id: str, host_id: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            # Idempotent against redelivery (background-jobs.md §2): a
            # missing invitation or a host who's since been deactivated/
            # deleted has nothing left to notify.
            if invitation is None:
                return
            host = await UserRepository(session).get_active(uuid.UUID(host_id))
            if host is None:
                # Host was deactivated/deleted between assignment and send —
                # nothing to notify. Logged, not just returned, so a host
                # who never got told they were named host is traceable
                # instead of vanishing with no trace.
                logger.warning(
                    "host_creation_notification_host_not_found",
                    tenant_schema=tenant_schema,
                    invitation_id=invitation_id,
                    host_id=host_id,
                )
                return
            subject = "You've been named host"
            body = (
                "You've been named host of an invitation.\n"
                f"Tracking ID: {invitation.tracking_id}\n"
                f"Visitor: {invitation.primary_contact_full_name}\n"
                f"Purpose: {invitation.purpose_of_visit or 'Not specified'}"
            )
            html_body = _render_html_or_none(
                "host_assigned",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "visitor_name": invitation.primary_contact_full_name,
                    "purpose": invitation.purpose_of_visit,
                    "visit_date": invitation.preferred_visit_date,
                    "visit_time": invitation.preferred_visit_time,
                },
            )
            await notifications.email_sender.send(
                to=host.email, subject=subject, body=body, html_body=html_body
            )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_poc_creation_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str, poc_id: str
) -> None:
    """add-invitation-point-of-contact: structurally identical to
    `send_host_creation_notification` above — emails the newly-named point
    of contact, a distinct task from the visitor confirmation dispatch
    since the recipient and their email are unrelated to the primary
    contact's own `preferred_contact_method`. Only ever enqueued when
    `pocUserId` (a specific person) was set — a role-identified point of
    contact is notified by push only (`invitations/service.py::
    edit_invitation`), same as a role-identified approval step has no email
    counterpart. `poc_id` is passed explicitly (resolved by the caller
    before enqueueing) rather than re-derived from `invitation.poc_user_id`
    here, so an exhausted-retries log always names which person went
    unnotified even if the invitation's point of contact has since changed
    again.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_poc_creation_notification(tenant_schema, invitation_id, poc_id))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "poc_creation_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
                poc_id=poc_id,
            )
        raise


async def _send_poc_creation_notification(
    tenant_schema: str, invitation_id: str, poc_id: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            # Idempotent against redelivery (background-jobs.md §2): a
            # missing invitation or a POC who's since been deactivated/
            # deleted has nothing left to notify.
            if invitation is None:
                return
            poc = await UserRepository(session).get_active(uuid.UUID(poc_id))
            if poc is None:
                logger.warning(
                    "poc_creation_notification_poc_not_found",
                    tenant_schema=tenant_schema,
                    invitation_id=invitation_id,
                    poc_id=poc_id,
                )
                return
            subject = "You've been named point of contact"
            body = (
                "You've been named point of contact for an invitation.\n"
                f"Tracking ID: {invitation.tracking_id}\n"
                f"Visitor: {invitation.primary_contact_full_name}\n"
                f"Purpose: {invitation.purpose_of_visit or 'Not specified'}"
            )
            html_body = _render_html_or_none(
                "poc_assigned",
                {
                    **await _base_email_context(session),
                    "tracking_id": invitation.tracking_id,
                    "visitor_name": invitation.primary_contact_full_name,
                    "purpose": invitation.purpose_of_visit,
                    "visit_date": invitation.preferred_visit_date,
                    "visit_time": invitation.preferred_visit_time,
                },
            )
            await notifications.email_sender.send(
                to=poc.email, subject=subject, body=body, html_body=html_body
            )
    finally:
        await engine.dispose()


async def _dispatch(
    invitation: Invitation,
    *,
    subject: str,
    body: str,
    html_body: str | None = None,
    attachment=None,
) -> None:
    """Routes to email or SMS per the invitation's `preferred_contact_method`
    — never both. `html_body` is ignored on the SMS path (there's no HTML
    concept for a text message); `body` is always sent as the plain-text
    part/message regardless. The `assert`s below are a data-integrity check,
    not optional-narrowing convenience: `schemas.py`'s validators already
    guarantee the contact info for the chosen method is present, so a
    failure here means that guarantee was violated somewhere upstream, and
    it's correct to let this raise loudly rather than silently no-op.
    """
    if invitation.primary_contact_preferred_contact_method == "email":
        assert invitation.primary_contact_email is not None
        await notifications.email_sender.send(
            to=invitation.primary_contact_email,
            subject=subject,
            body=body,
            html_body=html_body,
            attachment=attachment,
        )
    else:
        assert invitation.primary_contact_phone is not None
        await notifications.sms_sender.send(to=invitation.primary_contact_phone, body=body)
