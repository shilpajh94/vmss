"""Helpers shared by the invitation service modules: unique codes, visit-day
timezone maths, staff notifications and QR issuing. Split out of
`service.py`, which re-exports every name.
"""

import secrets
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, tzinfo
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.core.logging import current_request_id
from vmss_api.core.storage import save as storage_save
from vmss_api.core.timezones import resolve_timezone
from vmss_api.invitations import push_notifications, tasks
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
)
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.invitations.qr_token import encrypt_invitation_token
from vmss_api.invitations.repository import (
    InvitationRepository,
    VisitDayRange,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Company
from vmss_api.org_structure.repository import (
    BuildingRepository,
    CompanyRepository,
    DepartmentRepository,
)
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

_CHECKIN_CODE_LENGTH = 8


async def _unique_code(
    generate: Callable[[], str],
    is_taken: Callable[[str], Awaitable[object | None]],
    *,
    attempts: int,
    what: str,
) -> str:
    """Draws `generate()` until `is_taken` finds no row with that value.
    The retry loop, not the odds, is what guarantees uniqueness against the
    column's unique constraint."""
    for _ in range(attempts):
        candidate = generate()
        if await is_taken(candidate) is None:
            return candidate
    raise RuntimeError(f"Could not generate a unique {what}")


async def _generate_unique_checkin_code(repo: InvitationRepository) -> str:
    """8 digits from a CSPRNG, retried against uniqueness (same shape as
    `_generate_unique_tracking_id`). Low entropy by design (typed on a kiosk),
    so the public endpoints that accept it are rate limited and locked out.
    """
    return await _unique_code(
        lambda: f"{secrets.randbelow(10**_CHECKIN_CODE_LENGTH):0{_CHECKIN_CODE_LENGTH}d}",
        repo.get_by_checkin_code,
        attempts=10,
        what="invitation check-in code",
    )


async def _issue_checkin_code(tenant_db: AsyncSession, invitation: Invitation) -> None:
    """Get-or-create, only for contacts preferring `sms` (spec.md "SMS-Preferred
    Approved Invitation Gets a Numeric Check-In Code"). Called next to
    `_issue_qr_code` at every approval point; a no-op once a code exists so a
    repeated approval path never rotates it.
    """
    if invitation.primary_contact_preferred_contact_method != "sms":
        return
    if invitation.checkin_code is not None:
        return
    invitation.checkin_code = await _generate_unique_checkin_code(InvitationRepository(tenant_db))


async def _generate_unique_badge_number(repo: InvitationRepository) -> str:
    """`BDG-XXXXXXXX` — same retry-against-uniqueness shape as
    `_generate_unique_tracking_id` above (design.md Decision 4).
    """
    return await _unique_code(
        lambda: "BDG-" + secrets.token_hex(4).upper(),
        repo.get_by_badge_number,
        attempts=5,
        what="badge number",
    )


def _visit_timezone(company: Company | None, tenant: Tenant) -> tzinfo:
    """The zone "the visit day" is measured in — `Company.default_timezone`
    (the value an admin actually edits in org setup), then `Tenant.timezone`
    (a provisioning default), then UTC, via the shared `core/timezones.py`
    rule (expire-invitation-at-end-of-visit-day/design.md D1).
    """
    return resolve_timezone(
        ("company", company.default_timezone if company is not None else None),
        ("tenant", tenant.timezone),
    )


async def resolve_visit_timezone(tenant_db: AsyncSession, tenant: Tenant) -> tzinfo:
    company = await CompanyRepository(tenant_db).get_singleton()
    return _visit_timezone(company, tenant)


@dataclass(frozen=True)
class ListDrillDown:
    """The dashboard drill-down filters of `GET /invitations` and its export
    (fix-dashboard-count-accuracy): plain request values, resolved against
    the visit timezone and the request time by `_drill_down_filters`.
    """

    visit_date_from: date | None = None
    visit_date_to: date | None = None
    upcoming: bool = False
    exclude_expired: bool = False
    branch_id: uuid.UUID | None = None


async def _drill_down_filters(
    tenant_db: AsyncSession, tenant: Tenant | uuid.UUID, drill_down: ListDrillDown
) -> dict[str, Any]:
    """`tenant` may be just its id: the tenant row is then loaded only when
    a visit-date filter needs the visit timezone.
    """
    visit_days = None
    if drill_down.visit_date_from is not None or drill_down.visit_date_to is not None:
        if isinstance(tenant, uuid.UUID):
            loaded = await TenantRepository(tenant_db).get(tenant)
            assert loaded is not None  # the request's own tenant, already resolved
            tenant = loaded
        visit_days = VisitDayRange.local(
            drill_down.visit_date_from,
            drill_down.visit_date_to,
            await resolve_visit_timezone(tenant_db, tenant),
        )
    return {
        "visit_days": visit_days,
        "upcoming": drill_down.upcoming,
        "exclude_expired": drill_down.exclude_expired,
        "now": datetime.now(UTC),
        "branch_id": drill_down.branch_id,
    }


def _end_of_visit_day_utc(visit_date: date, tz: tzinfo) -> datetime:
    """Access is valid through the end of the visit day itself, regardless
    of when the invitation was submitted — 23:59:59 in the visit timezone
    (the same zone `check_in_by_qr_token`'s same-day gate uses), converted
    to UTC for storage.
    """
    local_end = datetime.combine(visit_date, time(23, 59, 59), tzinfo=tz)
    return local_end.astimezone(UTC)


async def _notify_host(
    tenant: Tenant,
    invitation: Invitation,
    push_builder: Callable[[Invitation], tuple[str, str, dict[str, str]]],
) -> None:
    """`project-rules.md` duplication finding — extracted from the identical
    "notify host via push" block repeated across `approve_invitation`,
    `deny_invitation`, `_perform_check_in`, `check_in_by_qr_token`,
    `check_out_invitation`, and `reschedule_invitation`. A no-op when the
    invitation has no resolved host (`hostId` unset — visit-info-lookup-api),
    same guard every call site already had.
    """
    if invitation.host_id is not None:
        title, body, data = push_builder(invitation)
        await notifications_service.notify_user(
            tenant_schema=tenant.schema_name,
            user_id=invitation.host_id,
            title=title,
            body=body,
            data=data,
        )


def _staff_email_recipients(
    invitation: Invitation, *, actor_user_id: uuid.UUID
) -> tuple[uuid.UUID, ...]:
    """Who besides the visitor is emailed about a denial, revert or
    reschedule (staff-lifecycle-emails-and-dashboard-landing design.md D1):
    the resolved host and the named point-of-contact user — once each,
    never the actor. A role-identified point of contact is push-only, like
    everywhere else.
    """
    return tuple(
        dict.fromkeys(
            user_id
            for user_id in (invitation.host_id, invitation.poc_user_id)
            if user_id is not None and user_id != actor_user_id
        )
    )


async def _push_point_of_contact(
    tenant_db: AsyncSession,
    tenant: Tenant,
    invitation: Invitation,
    *,
    push_builder: Callable[[Invitation], tuple[str, str, dict[str, str]]],
    actor_user_id: uuid.UUID | None,
) -> None:
    """The point-of-contact counterpart of `_notify_host`, for every
    lifecycle event that pushes the host (complete-staff-push-coverage
    design.md D1). Never pushes the actor or the host — the host already
    gets `_notify_host`'s push for the same action. `actor_user_id` is None
    for a QR/kiosk action with no human actor. A role-identified point of
    contact fans out as `lifecycle_update`, not a new assignment.
    """
    excluded = {user_id for user_id in (actor_user_id, invitation.host_id) if user_id is not None}
    poc_user_id = invitation.poc_user_id
    poc_role_id = invitation.poc_role_id
    if poc_user_id is None and poc_role_id is None:
        return
    title, body, data = push_builder(invitation)
    if poc_user_id is not None and poc_user_id not in excluded:
        await notifications_service.notify_user(
            tenant_schema=tenant.schema_name,
            user_id=poc_user_id,
            title=title,
            body=body,
            data=data,
        )
    if poc_role_id is not None and invitation.branch_id is not None:
        await notifications_service.notify_role_at_branch(
            tenant_db,
            tenant_schema=tenant.schema_name,
            role_id=poc_role_id,
            branch_id=invitation.branch_id,
            title=title,
            body=body,
            data=data,
            exclude_user_ids=excluded,
            reason="lifecycle_update",
        )


_STAFF_EVENT_PUSH_BUILDERS: dict[
    tasks.StaffLifecycleEvent, Callable[[Invitation], tuple[str, str, dict[str, str]]]
] = {
    "denied": push_notifications.denied,
    "approval_reverted": push_notifications.approval_reverted,
    "rescheduled": push_notifications.rescheduled,
}


async def _notify_responsible_staff(
    tenant_db: AsyncSession,
    tenant: Tenant,
    invitation: Invitation,
    *,
    event: tasks.StaffLifecycleEvent,
    actor_user_id: uuid.UUID,
) -> None:
    """Called after commit, alongside the visitor dispatch and `_notify_host`
    (invitations spec "Denial, Approval Revert, and Reschedule Email the
    Responsible Staff" / "... Push the Point of Contact").
    """
    for recipient_user_id in _staff_email_recipients(invitation, actor_user_id=actor_user_id):
        tasks.send_staff_lifecycle_notification.delay(
            request_id=current_request_id(),
            tenant_schema=tenant.schema_name,
            invitation_id=str(invitation.id),
            recipient_user_id=str(recipient_user_id),
            actor_user_id=str(actor_user_id),
            event=event,
        )
    await _push_point_of_contact(
        tenant_db,
        tenant,
        invitation,
        push_builder=_STAFF_EVENT_PUSH_BUILDERS[event],
        actor_user_id=actor_user_id,
    )


async def _issue_qr_code(
    tenant_db: AsyncSession, invitation: Invitation, *, tenant: Tenant
) -> InvitationQRCode:
    """Idempotent get-or-create: returns the invitation's existing
    `InvitationQRCode` row if one was already issued, otherwise generates
    a fresh encrypted token, renders and persists its QR image, and
    persists the row — called once, at the moment an invitation becomes
    `approved` (spec.md "QR Check-In Token Is Encrypted and Tamper-Evident"
    — "Token is generated once at approval"). Also the reuse point for
    badge issuance/reprint (`4.4`): calling this again for an
    already-issued invitation is a cheap no-op (no storage write), so the
    badge's embedded QR and the emailed QR always encode the same token.
    """
    repo = InvitationRepository(tenant_db)
    existing = await repo.get_qr_code(invitation.id)
    if existing is not None:
        return existing
    token = encrypt_invitation_token(invitation.id)
    qr_png = await generate_qr_png(token)
    storage_key = await storage_save(
        tenant.id, f"invitations/{invitation.id}/qr", qr_png, "image/png"
    )
    qr_code = InvitationQRCode(
        id=uuid.uuid4(),
        invitation_id=invitation.id,
        qr_token=token,
        image_storage_key=storage_key,
    )
    repo.add_qr_code(qr_code)
    return qr_code


async def _resolve_building(
    tenant_db: AsyncSession, building_id: uuid.UUID | None, branch_id: uuid.UUID
) -> uuid.UUID | None:
    if building_id is None:
        return None
    if not await BuildingRepository(tenant_db).is_active_in_branch(building_id, branch_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown building for the selected branch",
        )
    return building_id


async def _match_department_by_name(
    tenant_db: AsyncSession, branch_id: uuid.UUID, name: str
) -> uuid.UUID | None:
    matches = await DepartmentRepository(tenant_db).active_ids_named(branch_id, name)
    return matches[0] if len(matches) == 1 else None


_ACTIVE_STATUSES = ("approved", "checked_in")


async def _restart_approval(
    tenant_db: AsyncSession, invitation: Invitation
) -> InvitationApprovalStep | None:
    """Same workflow restart as `revert_invitation_approval`: every step back
    to `pending`, first one re-activated. Both calls are no-ops for an
    invitation without steps. Caller commits.
    """
    step_repo = InvitationApprovalStepRepository(tenant_db)
    await step_repo.reset_all_for_invitation(invitation.id)
    return await step_repo.activate_current_pending(invitation.id)


async def _notify_activated_approver(
    tenant_db: AsyncSession,
    tenant: Tenant,
    invitation: Invitation,
    activated_step: InvitationApprovalStep | None,
) -> None:
    if activated_step is None:
        return
    title, body, data = push_notifications.step_awaiting_approval(invitation)
    await notifications_service.notify_step_approver(
        tenant_db,
        tenant_schema=tenant.schema_name,
        approver_user_id=activated_step.approver_user_id,
        approver_role_id=activated_step.approver_role_id,
        branch_id=invitation.branch_id,
        title=title,
        body=body,
        data=data,
    )
