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
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from typing import Any, Literal

import structlog
from celery import Task
from redis.asyncio import from_url as redis_from_url
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import AuditLog
from vmss_api.auth.repository import UserRepository
from vmss_api.core import portal_links
from vmss_api.core.celery_app import DEFAULT_RETRY_KWARGS, celery_app
from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, engine, tenant_session_scope
from vmss_api.core.email_assets import base_url as email_asset_base_url
from vmss_api.core.email_assets import sign_qr_url
from vmss_api.core.email_rendering import TemplateRenderError, display_name, render_email
from vmss_api.core.logging import logger
from vmss_api.core.notification_dedupe import send_once
from vmss_api.core.sms import SmsInvalidNumberError, SmsNotConfiguredError, SmsTemplate
from vmss_api.core.whatsapp import WhatsAppTemplate
from vmss_api.form_builder import validation as form_builder_validation
from vmss_api.form_builder.defaults import DEFAULT_EFFECTIVE_FORM
from vmss_api.form_builder.repository import FormConfigVersionRepository
from vmss_api.form_builder.snapshot import normalize_snapshot
from vmss_api.invitations import notifications, retention
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.qr import generate_qr_png, generate_qr_png_rgb
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch
from vmss_api.org_structure.repository import CompanyRepository
from vmss_api.tenant.repository import TenantRepository

# `cid:` content id the confirmation and reschedule templates' QR block
# falls back to when no public asset URL is configured. Normally the QR is
# a signed URL and the message carries no image part at all
# (serve-email-images-by-url-and-complete-contact design.md Decision 3).
_QR_CID = "visit-qr@vmss"

_CONTACT_TITLE = "Your point of contact"


def _contact(name: str, detail: str | None) -> dict[str, str | None]:
    return {"contact_title": _CONTACT_TITLE, "contact_name": name, "contact_detail": detail}


def _visit_when(invitation: Invitation) -> str:
    visit_date, visit_time = invitation.preferred_visit_date, invitation.preferred_visit_time
    date_part = visit_date.strftime("%d %b %Y") if isinstance(visit_date, date) else "-"
    if isinstance(visit_time, time):
        return f"{date_part} {visit_time.strftime('%H:%M')}"
    return date_part


def _visitor_update_variables(invitation: Invitation, contact_name: str | None) -> list[object]:
    """Variables shared by the approved pending and rescheduled SMS templates
    and the WhatsApp `visit_request_received__...pending`, `visit_rescheduled`
    and `visitor_updates` templates: name, tracking ID, when, point of contact.
    """
    return [
        invitation.primary_contact_full_name,
        invitation.tracking_id,
        _visit_when(invitation),
        contact_name or "Front desk",
    ]


def _denial_variables(invitation: Invitation) -> list[object]:
    """The approved denial SMS / WhatsApp `visit_request_denied__request_denied`
    template: "Hello {{1}}, your visit request {{2}} for {{3}} could not be
    approved. Reason: {{4}}." Gateways reject an empty variable, hence the
    reason fallback.
    """
    return [
        invitation.primary_contact_full_name,
        invitation.tracking_id,
        _visit_when(invitation),
        (invitation.denial_reason or "").strip() or "Not specified",
    ]


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


async def _custom_field_rows(
    session: AsyncSession, invitation: Invitation
) -> tuple[str | None, list[tuple[str, str]]]:
    """`(duration, rows)` — the invitation's admin-defined answers as
    `(label, value)` rows for the "Visit details" table. An answer to a
    custom field labelled "Expected Duration" replaces the built-in
    `expected_duration` value rather than appearing as a second row, since
    that's where an edit via `customFields` lands. `file_upload` answers
    are skipped.
    """
    duration = invitation.expected_duration
    answers = {
        **(invitation.primary_contact_custom_field_values or {}),
        **(invitation.custom_field_values or {}),
    }
    if not answers:
        return duration, []
    version = await FormConfigVersionRepository(session).get_for_scope(invitation.branch_id)
    if version is None and invitation.branch_id is not None:
        version = await FormConfigVersionRepository(session).get_for_scope(None)
    form = normalize_snapshot(
        version.snapshot if version is not None else DEFAULT_EFFECTIVE_FORM, source="email"
    )
    fields = [
        *form_builder_validation.custom_fields_for_step(form, "visitor_info"),
        *form_builder_validation.custom_fields_for_invitation_scope(form),
    ]
    rows: list[tuple[str, str]] = []
    for field in fields:
        value = answers.get(field["id"])
        if value in (None, "", []) or field["fieldType"] == "file_upload":
            continue
        text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
        label = field.get("label") or field["key"]
        if label.strip().lower() == "expected duration":
            duration = text
        else:
            rows.append((label, text))
    return duration, rows


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
    duration, custom_fields = await _custom_field_rows(session, invitation)
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
        "duration": duration,
        "custom_fields": custom_fields,
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


async def _load_invitation(session: AsyncSession, invitation_id: str) -> Invitation | None:
    """A task's invitation by its serialized id. Deliberately `session.get`,
    not a soft-delete-filtering repository read: every task already checks
    the row's state itself, and that behaviour predates this helper."""
    return await session.get(Invitation, uuid.UUID(invitation_id))


def _run_task(
    task: Task,
    event: str,
    work: Callable[[], Coroutine[Any, Any, None]],
    *,
    request_id: str,
    tenant_schema: str,
    **log_fields: object,
) -> None:
    """The body every notification task shares: bind the enqueuing
    request's id (logging-observability.md §1), run `work`, and log at
    ERROR once retries are exhausted (background-jobs.md §4) before
    re-raising so Celery's autoretry sees the failure."""
    structlog.contextvars.bind_contextvars(request_id=request_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(work())
    except Exception:
        if task.request.retries >= task.max_retries:
            logger.error(f"{event}_dispatch_exhausted", tenant_schema=tenant_schema, **log_fields)
        raise


_RETRY_KWARGS = {
    **DEFAULT_RETRY_KWARGS,
    # A blank setting or an unusable number fails identically on every retry.
    "dont_autoretry_for": (SmsNotConfiguredError, SmsInvalidNumberError),
}


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_approval_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str, qr_token: str
) -> None:
    _run_task(
        self,
        "approval_notification",
        lambda: _send_approval_notification(tenant_schema, invitation_id, qr_token),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
    )


async def _badge_flow_active(session: AsyncSession, tenant_schema: str) -> bool:
    """True when the tenant has the badge print flow toggled on."""
    tenant = await TenantRepository(session).get_by_schema_name(tenant_schema)
    return tenant is not None and tenant.badge_print_flow_enabled


async def _send_approval_notification(
    tenant_schema: str, invitation_id: str, qr_token: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await _load_invitation(session, invitation_id)
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
            # add-badge-print-flow: when the flow is on, the visitor's QR is
            # printed on the badge at reception, so the email carries none.
            badge_flow = await _badge_flow_active(session, tenant_schema)
            if badge_flow:
                qr_src, qr_images = None, []
            else:
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
            # add-badge-print-flow: email-only "bring your ID" callout. The key is
            # added only when the flow is on for this tenant, so the context (and
            # so the rendered email) is unchanged for everyone else.
            if badge_flow:
                context["badge_flow_enabled"] = True
            subject, body, html_body = _render_or_fallback(
                "visit_confirmation", context, fallback_subject="Your visit is confirmed"
            )
            # An SMS contact can't scan a QR image, so approval issued them a
            # numeric check-in code instead (add-sms-numeric-checkin-code).
            # Read back from the row, never passed as a task argument, so it
            # stays out of the broker payload and task logs.
            if invitation.checkin_code is not None:
                sms_template = SmsTemplate.registration_confirmed_code
                sms_variables = [invitation.tracking_id, invitation.checkin_code]
            else:
                sms_template = SmsTemplate.registration_confirmed
                sms_variables = [invitation.tracking_id]
            # Never an attachment (invitations spec "Visit-Confirmation Email
            # Embeds the QR Code in a Dedicated Scannable Block"). A
            # plain-text-only fallback send carries no image at all, and its
            # text directs the visitor to quote the tracking ID instead.
            # The WhatsApp `qr` template: image header (the QR PNG, uploaded to
            # the gateway as media) plus name / tracking ID / date variables.
            await _dispatch(
                invitation,
                tenant_schema=tenant_schema,
                subject=subject,
                body=body,
                sms_template=sms_template,
                sms_variables=sms_variables,
                html_body=html_body,
                inline_images=qr_images if html_body is not None else [],
                whatsapp_variables=[
                    invitation.primary_contact_full_name,
                    invitation.tracking_id,
                    _visit_when(invitation),
                ],
                whatsapp_header_image_png=(
                    await generate_qr_png_rgb(qr_token)
                    if invitation.primary_contact_preferred_contact_method == "whatsapp"
                    else None
                ),
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


@dataclass(frozen=True)
class _VisitorNotice:
    """One email/SMS/WhatsApp notice to an invitation's primary contact.
    Each send renders `template` (falling back to a plain message with
    `fallback_subject`) and hands it to `_dispatch` on the contact's
    preferred channel."""

    template: str
    fallback_subject: str
    sms_template: SmsTemplate
    sms_variables: Callable[[Invitation, dict[str, Any]], list[object]]
    extra_context: Callable[[Invitation], dict[str, Any]] = lambda _invitation: {}
    whatsapp_variables: Callable[[Invitation, dict[str, Any]], list[object]] | None = None
    # Fills `context["qr_src"]` and returns the inline images to attach.
    qr: (
        Callable[
            [AsyncSession, str, Invitation, dict[str, Any]],
            Coroutine[Any, Any, list[notifications.InlineImage]],
        ]
        | None
    ) = None


def _update_variables(invitation: Invitation, context: dict[str, Any]) -> list[object]:
    return _visitor_update_variables(invitation, context.get("contact_name"))


async def _reschedule_qr(
    session: AsyncSession, tenant_schema: str, invitation: Invitation, context: dict[str, Any]
) -> list[notifications.InlineImage]:
    """invitations spec "Reschedule Dispatches a Notification to the
    Primary Contact": an approved visit gets its existing QR (same token as
    at approval — a reschedule never re-issues one) re-embedded inline; a
    still-submitted one has no QR yet."""
    if invitation.status != "approved" or await _badge_flow_active(session, tenant_schema):
        return []
    qr_code = await InvitationRepository(session).get_qr_code(invitation.id)
    if qr_code is None:
        logger.warning(
            "reschedule_notification_qr_missing",
            tenant_schema=tenant_schema,
            invitation_id=str(invitation.id),
        )
        return []
    context["qr_src"], qr_images = await _qr_source(
        session, tenant_schema, invitation, qr_code.qr_token
    )
    return qr_images


_TRACKING_NOTICE = _VisitorNotice(
    template="tracking_only",
    fallback_subject="We've received your visit request",
    sms_template=SmsTemplate.registration_pending,
    sms_variables=_update_variables,
)
# add-invitation-lifecycle-actions/design.md Decision 7.
_DENIAL_NOTICE = _VisitorNotice(
    template="denial",
    fallback_subject="Your visit request wasn't approved",
    sms_template=SmsTemplate.registration_denied,
    sms_variables=lambda invitation, _context: _denial_variables(invitation),
    extra_context=lambda invitation: {"denial_reason": invitation.denial_reason},
)
# add-reschedule-notification/design.md.
_RESCHEDULE_NOTICE = _VisitorNotice(
    template="reschedule",
    fallback_subject="Your visit has been rescheduled",
    sms_template=SmsTemplate.visit_rescheduled,
    sms_variables=_update_variables,
    qr=_reschedule_qr,
)
# role-based-invitation-workflow: fires on a successful `PATCH
# /invitations/{id}/edit`. The resolved host, if any, is told by push
# (`invitations/edit.py::edit_invitation`), not by this email.
_EDIT_NOTICE = _VisitorNotice(
    template="edit",
    fallback_subject="Your visit details have changed",
    sms_template=SmsTemplate.visit_details_changed,
    sms_variables=lambda invitation, _context: [
        invitation.tracking_id,
        invitation.preferred_visit_date,
        invitation.preferred_visit_time,
    ],
    extra_context=lambda invitation: {"poc_name": invitation.poc_name},
    whatsapp_variables=_update_variables,
)


async def _send_visitor_notice(
    tenant_schema: str, invitation_id: str, notice: _VisitorNotice
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await _load_invitation(session, invitation_id)
            if invitation is None:
                return
            context = {
                **await _invitation_email_context(
                    session,
                    invitation,
                    recipient_name=invitation.primary_contact_full_name,
                    recipient_email=invitation.primary_contact_email,
                ),
                **notice.extra_context(invitation),
            }
            qr_images = (
                await notice.qr(session, tenant_schema, invitation, context) if notice.qr else []
            )
            subject, body, html_body = _render_or_fallback(
                notice.template, context, fallback_subject=notice.fallback_subject
            )
            await _dispatch(
                invitation,
                tenant_schema=tenant_schema,
                subject=subject,
                body=body,
                sms_template=notice.sms_template,
                sms_variables=notice.sms_variables(invitation, context),
                html_body=html_body,
                inline_images=qr_images if html_body is not None else [],
                whatsapp_variables=(
                    notice.whatsapp_variables(invitation, context)
                    if notice.whatsapp_variables
                    else None
                ),
            )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_tracking_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    _run_task(
        self,
        "tracking_notification",
        lambda: _send_visitor_notice(tenant_schema, invitation_id, _TRACKING_NOTICE),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
    )


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_denial_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """add-invitation-lifecycle-actions/design.md Decision 7: structurally
    identical to `send_tracking_notification` above — same tenant-scoped
    session, `request_id` context binding, retry policy, and `_dispatch`
    helper — only the subject/body differ.
    """
    _run_task(
        self,
        "denial_notification",
        lambda: _send_visitor_notice(tenant_schema, invitation_id, _DENIAL_NOTICE),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
    )


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_approval_revert_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """add-invitation-approval-revert/design.md Decision 8: same shape as
    `send_denial_notification`. Idempotent per `background-jobs.md` §2 — it
    only sends while the invitation is still in the reverted state, so a
    redelivery after a quick re-approval doesn't tell the visitor their
    (now valid again) pass is on hold.
    """
    _run_task(
        self,
        "approval_revert_notification",
        lambda: _send_approval_revert_notification(tenant_schema, invitation_id),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
    )


async def _send_approval_revert_notification(tenant_schema: str, invitation_id: str) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await _load_invitation(session, invitation_id)
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
            # No DLT/WhatsApp template is registered for this notice yet, so a
            # phone-preferring contact falls back to email until one is
            # (audit-and-harden-api-and-web design.md D2).
            method = invitation.primary_contact_preferred_contact_method
            prefix = "fast2sms_whatsapp_template_" if method == "whatsapp" else "fast2sms_template_"
            phone_template_ready = bool(
                getattr(settings, f"{prefix}{SmsTemplate.approval_reverted.value}")
            )
            if method == "email" or phone_template_ready:
                await _dispatch(
                    invitation,
                    tenant_schema=tenant_schema,
                    subject=subject,
                    body=body,
                    sms_template=SmsTemplate.approval_reverted,
                    sms_variables=[
                        invitation.primary_contact_full_name,
                        invitation.tracking_id,
                        _visit_when(invitation),
                    ],
                    html_body=html_body,
                )
            elif invitation.primary_contact_email:
                await send_once(
                    tenant_scope=tenant_schema,
                    channel="email",
                    recipient=invitation.primary_contact_email,
                    send=partial(
                        notifications.email_sender.send,
                        to=invitation.primary_contact_email,
                        subject=subject,
                        body=body,
                        html_body=html_body,
                    ),
                )
            else:
                logger.warning(
                    "approval_revert_notification_skipped_no_channel",
                    tenant_schema=tenant_schema,
                    invitation_id=invitation_id,
                    preferred_contact_method=method,
                )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_reschedule_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """add-reschedule-notification/design.md: structurally identical to
    `send_denial_notification` above — same tenant-scoped session,
    `request_id` context binding, retry policy, and `_dispatch` helper —
    only the subject/body differ.
    """
    _run_task(
        self,
        "reschedule_notification",
        lambda: _send_visitor_notice(tenant_schema, invitation_id, _RESCHEDULE_NOTICE),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
    )


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_edit_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str
) -> None:
    """role-based-invitation-workflow: structurally identical to
    `send_reschedule_notification` above — same tenant-scoped session,
    `request_id` context binding, retry policy, and `_dispatch` helper —
    only the subject/body differ. Fires on a successful `PATCH
    /invitations/{id}/edit`, to the primary contact; the resolved host (if
    any) is separately notified via push (`invitations/service.py::
    edit_invitation`), not this email.
    """
    _run_task(
        self,
        "edit_notification",
        lambda: _send_visitor_notice(tenant_schema, invitation_id, _EDIT_NOTICE),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
    )


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_submission_role_email_notification(
    self: Task,
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
    _run_task(
        self,
        "submission_role_email_notification",
        lambda: _send_submission_role_email_notification(
            tenant_schema, invitation_id, role_id, branch_id
        ),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
        role_id=role_id,
    )


async def _send_submission_role_email_notification(
    tenant_schema: str, invitation_id: str, role_id: str, branch_id: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await _load_invitation(session, invitation_id)
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
                await send_once(
                    tenant_scope=tenant_schema,
                    channel="email",
                    recipient=role_user.email,
                    send=partial(
                        notifications.email_sender.send,
                        to=role_user.email,
                        subject=subject,
                        body=body,
                        html_body=html_body,
                    ),
                )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_host_creation_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str, host_id: str
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
    _run_task(
        self,
        "host_creation_notification",
        lambda: _send_host_creation_notification(tenant_schema, invitation_id, host_id),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
        host_id=host_id,
    )


async def _send_host_creation_notification(
    tenant_schema: str, invitation_id: str, host_id: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await _load_invitation(session, invitation_id)
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
            await send_once(
                tenant_scope=tenant_schema,
                channel="email",
                recipient=host.email,
                send=partial(
                    notifications.email_sender.send,
                    to=host.email,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                ),
            )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, **_RETRY_KWARGS)
def send_poc_creation_notification(
    self: Task, *, request_id: str, tenant_schema: str, invitation_id: str, poc_id: str
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
    _run_task(
        self,
        "poc_creation_notification",
        lambda: _send_poc_creation_notification(tenant_schema, invitation_id, poc_id),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
        poc_id=poc_id,
    )


async def _send_poc_creation_notification(
    tenant_schema: str, invitation_id: str, poc_id: str
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await _load_invitation(session, invitation_id)
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
            await send_once(
                tenant_scope=tenant_schema,
                channel="email",
                recipient=poc.email,
                send=partial(
                    notifications.email_sender.send,
                    to=poc.email,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                ),
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
    self: Task,
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
    _run_task(
        self,
        "staff_lifecycle_notification",
        lambda: _send_staff_lifecycle_notification(
            tenant_schema, invitation_id, recipient_user_id, actor_user_id, event
        ),
        request_id=request_id,
        tenant_schema=tenant_schema,
        invitation_id=invitation_id,
        recipient_user_id=recipient_user_id,
        lifecycle_event=event,
    )


async def _send_staff_lifecycle_notification(
    tenant_schema: str,
    invitation_id: str,
    recipient_user_id: str,
    actor_user_id: str,
    event: StaffLifecycleEvent,
) -> None:
    try:
        async with tenant_session_scope(tenant_schema) as session:
            invitation = await _load_invitation(session, invitation_id)
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
            await send_once(
                tenant_scope=tenant_schema,
                channel="email",
                recipient=recipient.email,
                send=partial(
                    notifications.email_sender.send,
                    to=recipient.email,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                ),
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
    tenant_schema: str,
    subject: str,
    body: str,
    sms_template: SmsTemplate,
    sms_variables: Sequence[object],
    html_body: str | None = None,
    inline_images: Sequence[notifications.InlineImage] = (),
    whatsapp_variables: Sequence[object] | None = None,
    whatsapp_header_image_png: bytes | None = None,
) -> None:
    """Routes to email, SMS or WhatsApp per the invitation's
    `preferred_contact_method` — never more than one. `body`/`html_body` are
    the email's plain-text and HTML parts; SMS and WhatsApp send the
    DLT/Meta-approved template named by `sms_template` (the WhatsApp
    template shares its name) with `sms_variables` in template order. The
    `assert`s below are a data-integrity check, not optional-narrowing
    convenience: `schemas.py`'s validators already
    guarantee the contact info for the chosen method is present, so a
    failure here means that guarantee was violated somewhere upstream, and
    it's correct to let this raise loudly rather than silently no-op.
    """
    method = invitation.primary_contact_preferred_contact_method
    if method == "email":
        email = invitation.primary_contact_email
        assert email is not None
        await send_once(
            tenant_scope=tenant_schema,
            channel="email",
            recipient=email,
            send=partial(
                notifications.email_sender.send,
                to=email,
                subject=subject,
                body=body,
                html_body=html_body,
                inline_images=inline_images,
            ),
        )
        return
    phone = invitation.primary_contact_phone
    assert phone is not None
    if method == "whatsapp":
        await send_once(
            tenant_scope=tenant_schema,
            channel="whatsapp",
            recipient=phone,
            send=partial(
                notifications.whatsapp_sender.send,
                to=phone,
                template=WhatsAppTemplate(sms_template.value),
                variables=sms_variables if whatsapp_variables is None else whatsapp_variables,
                header_image_png=whatsapp_header_image_png,
            ),
        )
    else:
        await send_once(
            tenant_scope=tenant_schema,
            channel="sms",
            recipient=phone,
            send=partial(
                notifications.sms_sender.send,
                to=phone,
                template=sms_template,
                variables=sms_variables,
            ),
        )


# --- Visit-lifecycle sweep (auto-checkout-and-archive-no-shows) --------------
# Same dispatcher/per-tenant split as `reports.tasks` (background-jobs
# "Scheduled Tasks Run Independently of Any Request"). No Redis run-marker:
# each transition is a conditional bulk `UPDATE`, so a redelivered or
# concurrent run simply matches nothing already transitioned (design.md D2).


@celery_app.task(bind=True)
def dispatch_visit_lifecycle_sweep(self: Task) -> None:
    structlog.contextvars.bind_contextvars(task="dispatch_visit_lifecycle_sweep")
    asyncio.run(_dispatch_visit_lifecycle_sweep())


async def _dispatch_visit_lifecycle_sweep() -> None:
    try:
        async with AsyncSessionLocal() as session:
            tenants = await TenantRepository(session).list_active()
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
def sweep_tenant_visit_lifecycle(self: Task, *, tenant_id: str, tenant_schema: str) -> None:
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
            now = datetime.now(UTC)
            checked_out, archived = await sweep_visit_lifecycle(session, now=now)
            # Rides the same per-tenant tick rather than a second beat
            # schedule; committed separately, after the lifecycle commit, so
            # a purge error can't undo a check-out or archive.
            purged = await notifications_service.purge_expired_notifications(session, now=now)
    finally:
        await engine.dispose()
    logger.info(
        "visit_lifecycle_swept",
        tenant_schema=tenant_schema,
        auto_checked_out=checked_out,
        archived=archived,
        notifications_purged=purged,
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


# --- Invitation retention purge -------------------------------------------
# Daily beat -> one task per tenant, same dispatcher/worker split as the
# lifecycle sweep above. Idempotent by construction: eligibility is
# re-evaluated from the database on every run and each batch's backup holds
# exactly that batch's delete ids, so a redelivery either finds nothing or
# re-backs-up and deletes only rows that still exist. The Redis key is a
# per-tenant run lock (released when the run ends, success or failure so a
# retry can proceed), preventing two workers purging the same tenant at once.

_PURGE_LOCK_TTL_SECONDS = 60 * 60


@celery_app.task(bind=True)
def dispatch_invitation_purge(self: Task) -> None:
    structlog.contextvars.bind_contextvars(task="dispatch_invitation_purge")
    if settings.invitation_retention_days <= 0:
        return
    asyncio.run(_dispatch_invitation_purge())


async def _dispatch_invitation_purge() -> None:
    try:
        async with AsyncSessionLocal() as session:
            tenants = await TenantRepository(session).list_active()
    finally:
        await engine.dispose()
    for tenant in tenants:
        try:
            purge_tenant_invitations.delay(
                tenant_id=str(tenant.id), tenant_schema=tenant.schema_name
            )
        except Exception:
            logger.error(
                "invitation_purge_enqueue_failed",
                tenant_id=str(tenant.id),
                tenant_schema=tenant.schema_name,
            )


@celery_app.task(bind=True, **_RETRY_KWARGS)
def purge_tenant_invitations(self: Task, *, tenant_id: str, tenant_schema: str) -> None:
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id, tenant_schema=tenant_schema)
    try:
        asyncio.run(_purge_tenant_invitations(tenant_id, tenant_schema))
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "invitation_purge_exhausted",
                tenant_id=tenant_id,
                tenant_schema=tenant_schema,
                exc_info=True,
            )
        raise


async def _purge_tenant_invitations(tenant_id: str, tenant_schema: str) -> None:
    if settings.invitation_retention_days <= 0:
        return
    lock_key = purge_lock_key(tenant_id)
    # Dedicated client, not the shared module-level one — same cross-event-loop
    # hazard `reports/tasks.py` documents.
    redis = redis_from_url(settings.redis_url, decode_responses=True)
    try:
        if not await redis.set(lock_key, "1", nx=True, ex=_PURGE_LOCK_TTL_SECONDS):
            return
        try:
            await purge_expired_invitations(uuid.UUID(tenant_id), tenant_schema)
        finally:
            await redis.delete(lock_key)
    finally:
        await redis.aclose()
        await engine.dispose()


async def purge_expired_invitations(
    tenant_id: uuid.UUID, tenant_schema: str, *, now: datetime | None = None
) -> int:
    """Backs up, verifies, then hard-deletes one tenant's expired invitations
    in batches. A backup that can't be written or verified raises *before*
    anything in that batch is deleted. Writes one audit entry for the run
    (even if a later batch raised, so what was already deleted is recorded).
    Returns the number of invitations purged.
    """
    now = now or datetime.now(UTC)
    cutoff = now.date() - timedelta(days=settings.invitation_retention_days)

    async def select_ids(repo: InvitationRepository) -> list[uuid.UUID]:
        return await repo.list_expired_ids(
            cutoff=cutoff, limit=settings.invitation_purge_batch_size
        )

    purged, backup_keys = await _backup_and_delete_batches(
        tenant_id,
        tenant_schema,
        select_ids,
        now=now,
        audit_action="invitations_purged",
        actor_user_id=None,
        audit_context={"cutoff": cutoff.isoformat()},
    )
    if purged:
        logger.info(
            "invitations_purged",
            tenant_id=str(tenant_id),
            count=purged,
            cutoff=cutoff.isoformat(),
            backup_keys=backup_keys,
        )
    return purged


async def _backup_and_delete_batches(
    tenant_id: uuid.UUID,
    tenant_schema: str,
    select_ids: Callable[[InvitationRepository], Awaitable[list[uuid.UUID]]],
    *,
    now: datetime,
    audit_action: str,
    actor_user_id: uuid.UUID | None,
    audit_context: dict[str, Any],
) -> tuple[int, list[str]]:
    """Shared by the retention purge and admin clear-all: for each batch
    `select_ids` returns, writes and verifies a backup, then hard-deletes the
    batch and its dependents. The audit entry is written in `finally` so what
    was deleted before a failure is still recorded.
    """
    purged = 0
    backup_keys: list[str] = []
    try:
        async with tenant_session_scope(tenant_schema) as session:
            repo = InvitationRepository(session)
            while True:
                ids = await select_ids(repo)
                if not ids:
                    break
                records = await repo.load_rows_for_backup(ids)
                backup_keys.append(
                    await retention.write_verified_backup(tenant_id, records, run_date=now)
                )
                deleted = await repo.delete_with_children(ids)
                await session.commit()
                purged += deleted
                if deleted == 0:
                    break
    finally:
        if purged:
            async with tenant_session_scope(tenant_schema) as session:
                session.add(
                    AuditLog(
                        id=uuid.uuid4(),
                        actor_user_id=actor_user_id,
                        action=audit_action,
                        entity_type="invitation",
                        entity_id=None,
                        diff={**audit_context, "count": purged, "backup_keys": backup_keys},
                    )
                )
                await session.commit()
    return purged, backup_keys


def purge_lock_key(tenant_id: str) -> str:
    return f"vmss:{tenant_id}:invitations:purge:lock"


@celery_app.task(bind=True, **_RETRY_KWARGS)
def clear_tenant_invitations(
    self: Task,
    *,
    tenant_id: str,
    tenant_schema: str,
    actor_user_id: str,
    include_checked_in: bool,
    from_date: str | None,
    to_date: str | None,
    request_id: str,
) -> None:
    structlog.contextvars.bind_contextvars(
        request_id=request_id, tenant_id=tenant_id, tenant_schema=tenant_schema
    )
    try:
        asyncio.run(
            _clear_tenant_invitations(
                tenant_id,
                tenant_schema,
                uuid.UUID(actor_user_id),
                include_checked_in,
                date.fromisoformat(from_date) if from_date else None,
                date.fromisoformat(to_date) if to_date else None,
            )
        )
    except Exception:
        if self.request.retries >= self.max_retries:
            logger.error(
                "invitation_clear_exhausted",
                tenant_id=tenant_id,
                tenant_schema=tenant_schema,
                actor_user_id=actor_user_id,
                entity_type="invitation",
                exc_info=True,
            )
        raise


async def _clear_tenant_invitations(
    tenant_id: str,
    tenant_schema: str,
    actor_user_id: uuid.UUID,
    include_checked_in: bool,
    from_date: date | None,
    to_date: date | None,
) -> int:
    # Same lock as the retention purge so the two can never overlap; losing
    # the race is a silent no-op (the endpoint's 409 pre-check is best effort).
    redis = redis_from_url(settings.redis_url, decode_responses=True)
    try:
        lock_key = purge_lock_key(tenant_id)
        if not await redis.set(lock_key, "1", nx=True, ex=_PURGE_LOCK_TTL_SECONDS):
            logger.warning("invitation_clear_skipped_locked", tenant_id=tenant_id)
            return 0
        try:
            return await clear_invitations(
                uuid.UUID(tenant_id),
                tenant_schema,
                actor_user_id=actor_user_id,
                include_checked_in=include_checked_in,
                from_date=from_date,
                to_date=to_date,
            )
        finally:
            await redis.delete(lock_key)
    finally:
        await redis.aclose()
        await engine.dispose()


async def clear_invitations(
    tenant_id: uuid.UUID,
    tenant_schema: str,
    *,
    actor_user_id: uuid.UUID,
    include_checked_in: bool,
    from_date: date | None,
    to_date: date | None,
    now: datetime | None = None,
) -> int:
    """Admin clear-all body (no lock): backs up then hard-deletes every
    invitation in scope. Idempotent — a repeat finds nothing left to delete.
    Returns the number of invitations deleted.
    """
    now = now or datetime.now(UTC)

    async def select_ids(repo: InvitationRepository) -> list[uuid.UUID]:
        return await repo.list_ids_for_clear(
            limit=settings.invitation_purge_batch_size,
            include_checked_in=include_checked_in,
            from_date=from_date,
            to_date=to_date,
        )

    deleted, backup_keys = await _backup_and_delete_batches(
        tenant_id,
        tenant_schema,
        select_ids,
        now=now,
        audit_action="invitations_cleared",
        actor_user_id=actor_user_id,
        audit_context={
            "scope": (
                {
                    "from_date": from_date.isoformat() if from_date else None,
                    "to_date": to_date.isoformat() if to_date else None,
                }
                if from_date or to_date
                else None
            ),
            "include_checked_in": include_checked_in,
        },
    )
    if deleted:
        logger.info(
            "invitations_cleared",
            tenant_id=str(tenant_id),
            actor_user_id=str(actor_user_id),
            count=deleted,
            backup_keys=backup_keys,
        )
    return deleted
