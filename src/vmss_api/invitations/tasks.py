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
a real tenant-bound session in hand); the task only ever signs a URL for the
QR (or renders it inline as the fallback), with no database read of its
own for the token. `send_reschedule_notification`, which has no
token argument, re-shows the same QR for an approved visit by reading the persisted token
(`InvitationRepository.get_qr_code`). Either way the email references the
QR by a signed public URL when `EMAIL_ASSET_BASE_URL` is set, and embeds it
inline only as the fallback.
"""

import asyncio
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.repository import UserRepository
from vmss_api.core import portal_links
from vmss_api.core.celery_app import celery_app
from vmss_api.core.database import AsyncSessionLocal, engine, tenant_session_scope
from vmss_api.core.email_assets import base_url as email_asset_base_url
from vmss_api.core.email_assets import sign_qr_url
from vmss_api.core.email_rendering import TemplateRenderError, display_name, render_email
from vmss_api.core.logging import logger
from vmss_api.invitations import notifications
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.org_structure.models import Branch
from vmss_api.org_structure.repository import CompanyRepository
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

# `cid:` content id the confirmation and reschedule templates' QR block
# falls back to when no public asset URL is configured. Normally the QR is
# a signed URL and the message carries no image part at all
# (serve-email-images-by-url-and-complete-contact design.md Decision 3).
_QR_CID = "visit-qr@vmss"

_CONTACT_TITLE = "Your point of contact"


def _contact(name: str, detail: str | None) -> dict[str, str | None]:
    return {"contact_title": _CONTACT_TITLE, "contact_name": name, "contact_detail": detail}


async def _resolve_contact(
    session: AsyncSession,
    invitation: Invitation,
    *,
    branch: Branch | None,
    front_desk_contact: str | None,
) -> dict[str, str | None]:
    """The "Your point of contact" block — always present on a visitor
    visit email (email-notifications "Visitor Visit Emails Always Name a
    Point of Contact"). First available of: the invitation's own POC, the
    resolved host, the branch's contact person, the front desk, then
    "Reception at {branch}". A name that isn't trustworthy (`display_name`)
    skips to the next step rather than greeting the visitor with an id.
    At most three sequential user lookups, never a loop.
    """
    users = UserRepository(session)
    poc_name = display_name(invitation.poc_name)
    if poc_name:
        detail = None
        if invitation.poc_user_id is not None:
            poc_user = await users.get_active(invitation.poc_user_id)
            if poc_user is not None:
                detail = poc_user.phone_number or poc_user.email
        return _contact(poc_name, detail)
    for user_id in (
        invitation.host_id,
        branch.contact_person_user_id if branch is not None else None,
    ):
        if user_id is None:
            continue
        person = await users.get_active(user_id)
        name = display_name(person.full_name, person.email) if person is not None else None
        if person is not None and name:
            return _contact(name, person.phone_number or person.email)
    if front_desk_contact:
        return _contact("Front desk", front_desk_contact)
    return _contact(f"Reception at {branch.name}" if branch is not None else "Reception", None)


async def _invitation_email_context(
    session: AsyncSession,
    invitation: Invitation,
    *,
    recipient_name: str | None,
    recipient_email: str | None,
) -> dict[str, Any]:
    """The context keys every invitation email template reads; each task
    adds only its own extras on top. Dates/times are passed as the real
    `date`/`time` values — the templates' `visit_datetime` filter formats
    them — and names raw, since `display_name` decides whether they're
    usable. "Where" comes from the org chart (`get_location`: department →
    floor → building, plus the branch), not the free-text field alone
    (refine-email-templates-and-visimio-brand design.md Decision 3).
    """
    company = await CompanyRepository(session).get_singleton()
    place = None
    department = invitation.department_to_visit
    front_desk_contact = None
    branch = None
    if invitation.branch_id is not None:
        branch, department_row, building = await InvitationRepository(session).get_location(
            branch_id=invitation.branch_id, department_id=invitation.department_id
        )
        address = ", ".join(part for part in (branch.address, branch.city) if part)
        place = " · ".join(
            part for part in (building.name if building else None, branch.name, address) if part
        )
        if department_row is not None:
            department = department_row.name
        front_desk_contact = branch.contact_phone or branch.contact_email
    if front_desk_contact is None and company is not None:
        front_desk_contact = company.phone or company.email
    return {
        "company_name": company.legal_name if company is not None else None,
        "logo_url": company.logo_url if company is not None else None,
        "recipient_name": recipient_name,
        "recipient_email": recipient_email,
        "tracking_id": invitation.tracking_id,
        "visitor_name": invitation.primary_contact_full_name,
        "purpose": invitation.purpose_of_visit,
        "visit_date": invitation.preferred_visit_date,
        "visit_time": invitation.preferred_visit_time,
        "previous_visit_date": invitation.previous_preferred_visit_date,
        "previous_visit_time": invitation.previous_preferred_visit_time,
        "duration": invitation.expected_duration,
        "department": department,
        "place": place or None,
        "front_desk_contact": front_desk_contact,
        "is_approved": invitation.status == "approved",
        "visitor_track_url": portal_links.visitor_track_url(),
        "visitor_request_url": portal_links.visitor_request_url(),
        "staff_login_url": portal_links.staff_login_url(),
        **await _resolve_contact(
            session, invitation, branch=branch, front_desk_contact=front_desk_contact
        ),
    }


async def _qr_source(
    session: AsyncSession, tenant_schema: str, invitation: Invitation, qr_token: str
) -> tuple[str, list[notifications.InlineImage]]:
    """`(qr_src, inline_images)` for the check-in pass block. A signed,
    expiring public URL when `EMAIL_ASSET_BASE_URL` is set — no image part
    in the message at all — else the inline `cid:` fallback, so the pass is
    never lost (invitations "Check-In QR Images Are Served From a Signed
    Public URL").
    """
    if email_asset_base_url() is not None:
        tenant = await TenantRepository(session).get_by_schema_name(tenant_schema)
        if tenant is not None:
            url = sign_qr_url(tenant.id, invitation.id, invitation.expires_at)
            if url is not None:
                return url, []
    qr_png = await generate_qr_png(qr_token)
    return f"cid:{_QR_CID}", [notifications.make_inline_image(qr_png, "image/png", _QR_CID)]


# Each email's call-to-action: button label, and the `_invitation_email_context`
# key holding its URL (add-portal-links-to-emails, email-notifications
# "Actionable Emails Link Directly to the Relevant Portal Page").
_CTAS: dict[str, tuple[str, str]] = {
    "tracking_only": ("Track your request", "visitor_track_url"),
    "visit_confirmation": ("View your visit", "visitor_track_url"),
    "reschedule": ("View your visit", "visitor_track_url"),
    "edit": ("View your visit", "visitor_track_url"),
    "denial": ("Submit a new request", "visitor_request_url"),
    "approval_reverted": ("Track your request", "visitor_track_url"),
    "submission_role": ("Review request", "staff_login_url"),
    "host_assigned": ("View visit", "staff_login_url"),
    "poc_assigned": ("View visit", "staff_login_url"),
    "staff_lifecycle_update": ("View visit", "staff_login_url"),
}


def _cta(template_name: str, context: dict[str, Any]) -> dict[str, str] | None:
    """`None` when the type has no link or no portal URL is configured —
    the template then omits its button.
    """
    if template_name not in _CTAS:
        return None
    label, url_key = _CTAS[template_name]
    url = context.get(url_key)
    return {"label": label, "url": url} if url else None


def _render_or_fallback(
    template_name: str, context: dict[str, Any], *, fallback_subject: str
) -> tuple[str, str, str | None]:
    """Returns `(subject, text_body, html_body)`. spec.md "Template
    Rendering Failure Falls Back to a Minimal Plain-Text Email" — on any
    rendering failure, `html_body` is `None` and the text is a minimal
    tracking-ID message (plus the email's link, when it has one), so the
    recipient still gets something deliverable.
    """
    cta = _cta(template_name, context)
    context = {**context, "cta": cta}
    try:
        rendered = render_email(template_name, context)
    except TemplateRenderError:
        logger.error(
            "email_template_render_failed",
            template_name=template_name,
            tracking_id=context.get("tracking_id"),
        )
        body = (
            f"Tracking ID: {context.get('tracking_id')}\n"
            "There's an update on your visit. Look up this tracking ID in the "
            "visitor portal, or contact the front desk, for the details."
        )
        if cta is not None:
            body += f"\n\n{cta['label']}: {cta['url']}"
        return fallback_subject, body, None
    return rendered.subject, rendered.text, rendered.html


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
            # spec.md "Approval Notification Email Includes Full Visit and
            # Host Detail": the point-of-contact block (POC, else resolved
            # host, else front desk) and the place of visit come from
            # `_invitation_email_context`, shared with reschedule/edit.
            qr_src, qr_images = await _qr_source(session, tenant_schema, invitation, qr_token)
            context = {
                **await _invitation_email_context(
                    session,
                    invitation,
                    recipient_name=invitation.primary_contact_full_name,
                    recipient_email=invitation.primary_contact_email,
                ),
                "qr_src": qr_src,
            }
            subject, body, html_body = _render_or_fallback(
                "visit_confirmation", context, fallback_subject="Your visit is confirmed"
            )
            sms_body = (
                f"Your registration is confirmed. Tracking ID: {invitation.tracking_id}.\n"
                "Present the attached QR code at check-in."
            )
            # Never an attachment (invitations spec "Visit-Confirmation Email
            # Embeds the QR Code in a Dedicated Scannable Block"). A
            # plain-text-only fallback send carries no image at all, and its
            # text directs the visitor to quote the tracking ID instead.
            await _dispatch(
                invitation,
                subject=subject,
                body=body,
                sms_body=sms_body,
                html_body=html_body,
                inline_images=qr_images if html_body is not None else [],
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
            subject, body, html_body = _render_or_fallback(
                "tracking_only",
                await _invitation_email_context(
                    session,
                    invitation,
                    recipient_name=invitation.primary_contact_full_name,
                    recipient_email=invitation.primary_contact_email,
                ),
                fallback_subject="We've received your visit request",
            )
            sms_body = (
                f"Your registration is awaiting approval. Tracking ID: "
                f"{invitation.tracking_id}.\n"
                "You'll receive a check-in QR code once it's approved."
            )
            await _dispatch(
                invitation, subject=subject, body=body, sms_body=sms_body, html_body=html_body
            )
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
            subject, body, html_body = _render_or_fallback(
                "denial",
                {
                    **await _invitation_email_context(
                        session,
                        invitation,
                        recipient_name=invitation.primary_contact_full_name,
                        recipient_email=invitation.primary_contact_email,
                    ),
                    "denial_reason": invitation.denial_reason,
                },
                fallback_subject="Your visit request wasn't approved",
            )
            sms_body = (
                f"Your registration was not approved. Tracking ID: "
                f"{invitation.tracking_id}.\n"
                f"Reason: {invitation.denial_reason}"
            )
            await _dispatch(
                invitation, subject=subject, body=body, sms_body=sms_body, html_body=html_body
            )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_approval_revert_notification(
    self, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """add-invitation-approval-revert/design.md Decision 8: same shape as
    `send_denial_notification`. Idempotent per `background-jobs.md` §2 — it
    only sends while the invitation is still in the reverted state, so a
    redelivery after a quick re-approval doesn't tell the visitor their
    (now valid again) pass is on hold.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_send_approval_revert_notification(tenant_schema, invitation_id))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "approval_revert_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
            )
        raise


async def _send_approval_revert_notification(tenant_schema: str, invitation_id: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            if (
                invitation is None
                or invitation.status != "submitted"
                or invitation.approval_reverted_at is None
            ):
                return
            # The revert reason is deliberately not passed: it's an internal
            # note, not addressed to the visitor (design.md Decision 8).
            subject, body, html_body = _render_or_fallback(
                "approval_reverted",
                await _invitation_email_context(
                    session,
                    invitation,
                    recipient_name=invitation.primary_contact_full_name,
                    recipient_email=invitation.primary_contact_email,
                ),
                fallback_subject="Your visit approval has been withdrawn",
            )
            sms_body = (
                f"The approval for your visit has been withdrawn while it's reviewed "
                f"again; your pass won't admit you until it's re-approved. Tracking ID: "
                f"{invitation.tracking_id}."
            )
            await _dispatch(
                invitation, subject=subject, body=body, sms_body=sms_body, html_body=html_body
            )
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
            context = await _invitation_email_context(
                session,
                invitation,
                recipient_name=invitation.primary_contact_full_name,
                recipient_email=invitation.primary_contact_email,
            )
            # invitations spec "Reschedule Dispatches a Notification to the
            # Primary Contact": an approved visit gets its existing QR (same
            # token as at approval — a reschedule never re-issues one)
            # re-embedded inline; a still-submitted one has no QR yet.
            qr_images: list[notifications.InlineImage] = []
            if invitation.status == "approved":
                qr_code = await InvitationRepository(session).get_qr_code(invitation.id)
                if qr_code is None:
                    logger.warning(
                        "reschedule_notification_qr_missing",
                        tenant_schema=tenant_schema,
                        invitation_id=invitation_id,
                    )
                else:
                    context["qr_src"], qr_images = await _qr_source(
                        session, tenant_schema, invitation, qr_code.qr_token
                    )
            subject, body, html_body = _render_or_fallback(
                "reschedule", context, fallback_subject="Your visit has been rescheduled"
            )
            sms_body = (
                f"Your visit has been rescheduled. New date: "
                f"{invitation.preferred_visit_date}, time: "
                f"{invitation.preferred_visit_time}. Tracking ID: "
                f"{invitation.tracking_id}."
            )
            await _dispatch(
                invitation,
                subject=subject,
                body=body,
                sms_body=sms_body,
                html_body=html_body,
                inline_images=qr_images if html_body is not None else [],
            )
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
            subject, body, html_body = _render_or_fallback(
                "edit",
                {
                    **await _invitation_email_context(
                        session,
                        invitation,
                        recipient_name=invitation.primary_contact_full_name,
                        recipient_email=invitation.primary_contact_email,
                    ),
                    "poc_name": invitation.poc_name,
                },
                fallback_subject="Your visit details have changed",
            )
            sms_body = (
                "Some details of your upcoming visit have changed. Tracking "
                f"ID: {invitation.tracking_id}.\n"
                f"Purpose: {invitation.purpose_of_visit or 'Not specified'}\n"
                f"Date: {invitation.preferred_visit_date}, time: "
                f"{invitation.preferred_visit_time}\n"
                f"Duration: {invitation.expected_duration or 'Not specified'}\n"
                f"Department: {invitation.department_to_visit or 'Not specified'}"
            )
            if invitation.poc_name:
                sms_body += f"\nPoint of contact: {invitation.poc_name}"
            await _dispatch(
                invitation, subject=subject, body=body, sms_body=sms_body, html_body=html_body
            )
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
            # Built once — only the greeting differs per recipient, so the
            # loop below re-renders from this dict without another query.
            shared_context = await _invitation_email_context(
                session, invitation, recipient_name=None, recipient_email=None
            )
            for role_user in users:
                # Defensive: `User.email` is a required column today, so
                # this never actually skips anyone — kept so a future schema
                # change (or a row this repository call somehow returns with
                # a blank email) degrades to "skip that one recipient"
                # rather than failing the whole dispatch.
                if not role_user.email:
                    continue
                subject, body, html_body = _render_or_fallback(
                    "submission_role",
                    {
                        **shared_context,
                        "recipient_name": role_user.full_name,
                        "recipient_email": role_user.email,
                    },
                    fallback_subject="New visit request awaiting triage",
                )
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
            subject, body, html_body = _render_or_fallback(
                "host_assigned",
                await _invitation_email_context(
                    session, invitation, recipient_name=host.full_name, recipient_email=host.email
                ),
                fallback_subject="You've been named host for a visit",
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
            subject, body, html_body = _render_or_fallback(
                "poc_assigned",
                {
                    **await _invitation_email_context(
                        session, invitation, recipient_name=poc.full_name, recipient_email=poc.email
                    ),
                    "visitor_phone": invitation.primary_contact_phone,
                    "visitor_email": invitation.primary_contact_email,
                },
                fallback_subject="You're the point of contact for a visit",
            )
            await notifications.email_sender.send(
                to=poc.email, subject=subject, body=body, html_body=html_body
            )
    finally:
        await engine.dispose()


# --- Staff lifecycle email (staff-lifecycle-emails-and-dashboard-landing) ---

StaffLifecycleEvent = Literal["denied", "approval_reverted", "rescheduled"]

# The statuses a reschedule can never leave an invitation in — a staff email
# arriving after the visit was denied or already happened is stale.
_RESCHEDULE_STALE_STATUSES = frozenset({"denied", "checked_in", "checked_out"})


def _staff_event_still_current(invitation: Invitation, event: StaffLifecycleEvent) -> bool:
    """Redelivery guard (background-jobs.md §2; invitations spec "Denial,
    Approval Revert, and Reschedule Email the Responsible Staff"): skip the
    send once the invitation no longer reflects `event`.
    """
    if event == "denied":
        return invitation.status == "denied"
    if event == "approval_reverted":
        return invitation.status == "submitted" and invitation.approval_reverted_at is not None
    return invitation.status not in _RESCHEDULE_STALE_STATUSES


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_staff_lifecycle_notification(
    self,
    *,
    request_id: str,
    tenant_schema: str,
    invitation_id: str,
    recipient_user_id: str,
    actor_user_id: str,
    event: StaffLifecycleEvent,
) -> None:
    """Emails one responsible staff member (resolved host or named point of
    contact) that the invitation was denied, had its approval reverted, or
    was rescheduled. One task per recipient, with the recipient passed
    explicitly — same reasoning as `send_host_creation_notification`: a
    retry never re-sends to someone already emailed, and an
    exhausted-retries log names who went unnotified.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(
            _send_staff_lifecycle_notification(
                tenant_schema, invitation_id, recipient_user_id, actor_user_id, event
            )
        )
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "staff_lifecycle_notification_dispatch_exhausted",
                tenant_schema=tenant_schema,
                invitation_id=invitation_id,
                recipient_user_id=recipient_user_id,
                lifecycle_event=event,
            )
        raise


async def _send_staff_lifecycle_notification(
    tenant_schema: str,
    invitation_id: str,
    recipient_user_id: str,
    actor_user_id: str,
    event: StaffLifecycleEvent,
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            if invitation is None or not _staff_event_still_current(invitation, event):
                return
            users = UserRepository(session)
            recipient = await users.get_active(uuid.UUID(recipient_user_id))
            if recipient is None:
                logger.warning(
                    "staff_lifecycle_notification_recipient_not_found",
                    tenant_schema=tenant_schema,
                    invitation_id=invitation_id,
                    recipient_user_id=recipient_user_id,
                    lifecycle_event=event,
                )
                return
            # A deactivated actor still has a usable name; only a deleted one
            # falls back to the template's "A staff member".
            actor = await users.get_by_id(uuid.UUID(actor_user_id))
            if event == "denied":
                reason = invitation.denial_reason
            elif event == "approval_reverted":
                reason = invitation.approval_revert_reason
            else:
                reason = None
            subject, body, html_body = _render_or_fallback(
                "staff_lifecycle_update",
                {
                    **await _invitation_email_context(
                        session,
                        invitation,
                        recipient_name=recipient.full_name,
                        recipient_email=recipient.email,
                    ),
                    "event": event,
                    "actor_name": actor.full_name if actor is not None else None,
                    "reason": reason,
                    "awaiting_approval": invitation.status == "submitted",
                    "visitor_phone": invitation.primary_contact_phone,
                    "visitor_email": invitation.primary_contact_email,
                },
                fallback_subject=_STAFF_LIFECYCLE_FALLBACK_SUBJECTS[event],
            )
            await notifications.email_sender.send(
                to=recipient.email, subject=subject, body=body, html_body=html_body
            )
    finally:
        await engine.dispose()


_STAFF_LIFECYCLE_FALLBACK_SUBJECTS: dict[str, str] = {
    "denied": "A visit request was denied",
    "approval_reverted": "Approval withdrawn for a visit",
    "rescheduled": "A visit has been rescheduled",
}


async def _dispatch(
    invitation: Invitation,
    *,
    subject: str,
    body: str,
    sms_body: str,
    html_body: str | None = None,
    inline_images: Sequence[notifications.InlineImage] = (),
) -> None:
    """Routes to email or SMS per the invitation's `preferred_contact_method`
    — never both. `body`/`html_body` are the email's plain-text and HTML
    parts; the SMS path sends `sms_body` instead — a deliberately short
    one-liner, since the full plain-text email (greeting, detail rows,
    footer) would span several billable SMS segments
    (redesign-notification-email-templates leaves SMS copy unchanged). The
    `assert`s below are a data-integrity check, not optional-narrowing
    convenience: `schemas.py`'s validators already
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
            inline_images=inline_images,
        )
    else:
        assert invitation.primary_contact_phone is not None
        await notifications.sms_sender.send(to=invitation.primary_contact_phone, body=sms_body)


# --- Visit-lifecycle sweep (auto-checkout-and-archive-no-shows) --------------
# Same dispatcher/per-tenant split as `reports.tasks` (background-jobs
# "Scheduled Tasks Run Independently of Any Request"). No Redis run-marker:
# each transition is a conditional bulk `UPDATE`, so a redelivered or
# concurrent run simply matches nothing already transitioned (design.md D2).


@celery_app.task(bind=True)
def dispatch_visit_lifecycle_sweep(self) -> None:
    structlog.contextvars.bind_contextvars(task="dispatch_visit_lifecycle_sweep")
    asyncio.run(_dispatch_visit_lifecycle_sweep())


async def _dispatch_visit_lifecycle_sweep() -> None:
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Tenant).where(Tenant.is_active.is_(True), Tenant.deleted_at.is_(None))
            tenants = list((await session.execute(stmt)).scalars().all())
    finally:
        await engine.dispose()
    for tenant in tenants:
        try:
            sweep_tenant_visit_lifecycle.delay(
                tenant_id=str(tenant.id), tenant_schema=tenant.schema_name
            )
        except Exception:
            logger.error(
                "visit_lifecycle_sweep_enqueue_failed",
                tenant_id=str(tenant.id),
                tenant_schema=tenant.schema_name,
            )


@celery_app.task(bind=True, **_RETRY_KWARGS)
def sweep_tenant_visit_lifecycle(self, *, tenant_id: str, tenant_schema: str) -> None:
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_sweep_tenant_visit_lifecycle(tenant_schema))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "visit_lifecycle_sweep_exhausted",
                tenant_id=tenant_id,
                tenant_schema=tenant_schema,
            )
        raise


async def _sweep_tenant_visit_lifecycle(tenant_schema: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            checked_out, archived = await sweep_visit_lifecycle(session, now=datetime.now(UTC))
    finally:
        await engine.dispose()
    logger.info(
        "visit_lifecycle_swept",
        tenant_schema=tenant_schema,
        auto_checked_out=checked_out,
        archived=archived,
    )


async def sweep_visit_lifecycle(session: AsyncSession, *, now: datetime) -> tuple[int, int]:
    """Auto-checks-out expired check-ins and archives approved no-shows, each
    with its audit rows, in one commit. Sends nothing — both transitions are
    deliberately silent (visit-lifecycle-sweep spec). Returns
    `(auto_checked_out, archived)` counts.
    """
    repo = InvitationRepository(session)
    checked_out_ids = await repo.auto_check_out_expired(now=now)
    await repo.record_system_audit(
        checked_out_ids, action="invitation_auto_checked_out", diff={"reason": "expired"}
    )
    archived_ids = await repo.archive_expired_no_shows(now=now)
    await repo.record_system_audit(
        archived_ids, action="invitation_archived", diff={"reason": "no_show"}
    )
    await session.commit()
    return len(checked_out_ids), len(archived_ids)
