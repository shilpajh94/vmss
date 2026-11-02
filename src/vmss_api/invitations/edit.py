"""Changing an existing invitation: reschedule, edit and extend. Split out of
`service.py`, which re-exports every name.
"""

import uuid
from datetime import UTC, date, datetime, tzinfo
from functools import partial
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import User
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.core.logging import current_request_id
from vmss_api.core.redis import get_redis
from vmss_api.form_builder import service as form_builder_service
from vmss_api.form_builder import validation as form_builder_validation
from vmss_api.invitations import push_notifications, tasks
from vmss_api.invitations.common import (
    _ACTIVE_STATUSES,
    _end_of_visit_day_utc,
    _match_department_by_name,
    _notify_activated_approver,
    _notify_host,
    _notify_responsible_staff,
    _push_point_of_contact,
    _resolve_building,
    _restart_approval,
    resolve_visit_timezone,
)
from vmss_api.invitations.models import (
    Invitation,
)
from vmss_api.invitations.repository import (
    InvitationRepository,
)
from vmss_api.invitations.schemas import (
    InvitationEditRequest,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.repository import (
    DepartmentRepository,
)
from vmss_api.tenant.models import Tenant
from vmss_api.visit_info.repository import VisitDurationRepository, VisitPurposeRepository
from vmss_api.visitors.repository import ApprovalWorkflowRuleRepository

_RESCHEDULABLE_STATUSES = ("submitted", "approved")


_LOCATION_EDIT_FIELDS = frozenset({"department_to_visit", "department_id", "building_id"})


async def _reject_past_visit_date(
    tenant_db: AsyncSession, tenant: Tenant, visit_date: date
) -> tzinfo:
    """Leaving `archived` needs a date the visitor can still make — today or
    later in the visit timezone (design.md D6). Returns the zone so the
    caller can realign `expires_at` without resolving it twice.
    """
    tz = await resolve_visit_timezone(tenant_db, tenant)
    if visit_date < datetime.now(UTC).astimezone(tz).date():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="New visit date cannot be in the past",
        )
    return tz


async def _reschedule_archived(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    preferred_visit_date: date,
    preferred_visit_time: Any,
    tenant: Tenant,
    actor_user_id: uuid.UUID,
) -> Invitation:
    """An archived no-show goes back to `submitted` for re-approval on its new
    date, never straight to `approved` — the Company auto-approve setting is
    a creation-time rule only (design.md D6). The original QR row is kept;
    re-approval re-sends that same pass.
    """
    tz = await _reject_past_visit_date(tenant_db, tenant, preferred_visit_date)
    updated = await InvitationRepository(tenant_db).reschedule_archived_if_eligible(
        invitation.id,
        preferred_visit_date=preferred_visit_date,
        preferred_visit_time=preferred_visit_time,
        expires_at=_end_of_visit_day_utc(preferred_visit_date, tz),
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation can no longer be rescheduled"
        )
    activated_step = await _restart_approval(tenant_db, updated)
    await tenant_db.commit()
    tasks.send_reschedule_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    await _notify_host(tenant, updated, push_notifications.rescheduled)
    await _notify_responsible_staff(
        tenant_db, tenant, updated, event="rescheduled", actor_user_id=actor_user_id
    )
    await _notify_activated_approver(tenant_db, tenant, updated, activated_step)
    return updated


async def reschedule_invitation(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    preferred_visit_date: Any,
    preferred_visit_time: Any,
    tenant: Tenant,
    actor_user_id: uuid.UUID,
) -> Invitation:
    """Notifies the primary contact of the new date/time on success
    (specs/invitations/spec.md "Reschedule Dispatches a Notification to the
    Primary Contact") — enqueued only after the commit below, never for a
    request rejected by either guard.
    """
    if invitation.status == "archived":
        return await _reschedule_archived(
            tenant_db,
            invitation,
            preferred_visit_date=preferred_visit_date,
            preferred_visit_time=preferred_visit_time,
            tenant=tenant,
            actor_user_id=actor_user_id,
        )
    if invitation.status not in _RESCHEDULABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation can no longer be rescheduled"
        )
    # Realigned for `submitted` too, not just `approved` — otherwise a
    # pending invitation moved to a later day keeps the old day's expiry
    # (expire-invitation-at-end-of-visit-day/design.md D2).
    expires_at = _end_of_visit_day_utc(
        preferred_visit_date, await resolve_visit_timezone(tenant_db, tenant)
    )
    updated = await InvitationRepository(tenant_db).reschedule_if_eligible(
        invitation.id,
        preferred_visit_date=preferred_visit_date,
        preferred_visit_time=preferred_visit_time,
        expires_at=expires_at,
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation can no longer be rescheduled"
        )
    await tenant_db.commit()
    tasks.send_reschedule_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    await _notify_host(tenant, updated, push_notifications.rescheduled)
    await _notify_responsible_staff(
        tenant_db, tenant, updated, event="rescheduled", actor_user_id=actor_user_id
    )
    return updated


async def _resolve_edit_changes(
    tenant_db: AsyncSession, payload: InvitationEditRequest, branch_id: uuid.UUID
) -> dict[str, Any]:
    """Same catalog-id-overwrites-free-text resolution
    `_resolve_visit_detail_ids` applies at creation, scoped to whichever
    fields the caller actually supplied (`exclude_unset`) — an omitted field
    is left alone, not reset to null.
    """
    changes: dict[str, Any] = payload.model_dump(
        exclude_unset=True,
        include={
            "purpose_of_visit",
            "preferred_visit_date",
            "preferred_visit_time",
            "expected_duration",
            "department_to_visit",
            "additional_notes",
            "checked_out_at",
        },
    )
    if payload.purpose_id is not None:
        purpose = await VisitPurposeRepository(tenant_db).get_active(payload.purpose_id)
        if purpose is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown purposeId")
        changes["purpose_id"] = purpose.id
        changes["purpose_of_visit"] = purpose.name
    if payload.duration_id is not None:
        duration = await VisitDurationRepository(tenant_db).get_active(payload.duration_id)
        if duration is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown durationId")
        changes["duration_id"] = duration.id
        changes["expected_duration"] = duration.name
    elif "expected_duration" in changes:
        # Free-text edit: drop the old catalog link so `duration_id` can't
        # keep pointing at a duration that no longer matches the text.
        changes["duration_id"] = None
    if payload.department_id is not None:
        department = await DepartmentRepository(tenant_db).get_active(payload.department_id)
        if department is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown departmentId"
            )
        changes["department_id"] = department.id
        changes["department_to_visit"] = department.name
    elif changes.get("department_to_visit"):
        # Free-text edit: re-link (or clear a now-stale link) by branch + name.
        changes["department_id"] = await _match_department_by_name(
            tenant_db, branch_id, changes["department_to_visit"]
        )
    if payload.building_id is not None:
        changes["building_id"] = await _resolve_building(tenant_db, payload.building_id, branch_id)
    if payload.poc_user_id is not None:
        poc_user = await UserRepository(tenant_db).get_active(payload.poc_user_id)
        if poc_user is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown pocUserId")
        changes["poc_user_id"] = poc_user.id
        changes["poc_role_id"] = None
        changes["poc_name"] = poc_user.full_name
    elif payload.poc_role_id is not None:
        poc_role = await RoleRepository(tenant_db).get(payload.poc_role_id)
        if poc_role is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown pocRoleId")
        changes["poc_role_id"] = poc_role.id
        changes["poc_user_id"] = None
        changes["poc_name"] = poc_role.name
    return changes


def _validate_checked_out_at(invitation: Invitation, checked_out_at: datetime | None) -> None:
    if checked_out_at is None:
        return
    if checked_out_at > datetime.now(UTC):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="checkedOutAt cannot be in the future"
        )
    if invitation.checked_in_at is not None and checked_out_at < invitation.checked_in_at:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="checkedOutAt cannot be earlier than the check-in time",
        )


async def _poc_eligible(tenant_db: AsyncSession, invitation: Invitation) -> bool:
    """Server-side mirror of the frontend's Edit-modal Point-of-Contact
    gating (add-invitation-point-of-contact) — a client-supplied
    `pocUserId`/`pocRoleId` can't be trusted to reflect it, so
    `edit_invitation` re-derives it here rather than trusting the caller
    only got this far because the UI disabled the field. Eligible when
    either:

    - the invitation's visitor category has no configured active
      `ApprovalWorkflowRule`s (nothing to be "mid-workflow" relative to), or
    - the invitation is currently at its final approval level: its current
      pending step (if any) is the last-`step_order` snapshotted step, or
      there is no pending step left at all (workflow already finalized,
      i.e. at/past the final level).

    Compares against the *max* snapshotted `step_order`, not
    `total_steps - 1` — `_build_approval_steps` copies `step_order` directly
    from each category's own `ApprovalWorkflowRule.step_order`, which isn't
    guaranteed to be a contiguous 0-based sequence.
    """
    if invitation.visitor_category_id is None:
        return True
    active_rules = await ApprovalWorkflowRuleRepository(tenant_db).list_active_for_category(
        invitation.visitor_category_id
    )
    if not active_rules:
        return True
    step_repo = InvitationApprovalStepRepository(tenant_db)
    current = await step_repo.get_current_pending(invitation.id)
    if current is None:
        return True
    steps = await step_repo.list_for_invitation(invitation.id)
    return current.step_order == steps[-1].step_order


async def _resolve_custom_field_edit(
    tenant_db: AsyncSession,
    tenant: Tenant,
    invitation: Invitation,
    payload: InvitationEditRequest,
) -> dict[str, Any]:
    """Validates the supplied `customFields` against the branch's effective
    form and merges them over the stored answers, split by scope the same
    way `create_invitation` does (Visitor Info fields are the primary
    contact's, the rest invitation-level) so `GET` reads them back. Only the
    supplied fields are checked for requiredness, so an invitation predating
    a newly-required field can still be edited. `file_upload` fields are
    skipped — they can't be answered from JSON.
    """
    effective_form = await form_builder_service.resolve_effective_form(
        tenant_db, await get_redis(), tenant_id=tenant.id, branch_id=invitation.branch_id
    )
    visitor_info_fields = form_builder_validation.custom_fields_for_step(
        effective_form, "visitor_info"
    )
    visitor_info_ids = {f["id"] for f in visitor_info_fields}
    scope_fields = form_builder_validation.custom_fields_for_invitation_scope(effective_form)
    all_fields = {f["id"]: f for f in [*visitor_info_fields, *scope_fields]}

    supplied = payload.custom_field_values
    unknown = set(supplied) - set(all_fields)
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown custom field id(s): {', '.join(sorted(unknown))}",
        )
    supplied = {k: v for k, v in supplied.items() if all_fields[k]["fieldType"] != "file_upload"}
    for field_id, value in supplied.items():
        if all_fields[field_id]["isRequired"] and value in (None, "", []):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Missing required custom field(s): {all_fields[field_id]['label']}",
            )
    form_builder_validation.validate_custom_field_values(
        [all_fields[k] for k in supplied], supplied, scope="the invitation"
    )
    return {
        "primary_contact_custom_field_values": {
            **invitation.primary_contact_custom_field_values,
            **{k: v for k, v in supplied.items() if k in visitor_info_ids},
        },
        "custom_field_values": {
            **invitation.custom_field_values,
            **{k: v for k, v in supplied.items() if k not in visitor_info_ids},
        },
    }


async def edit_invitation(
    tenant_db: AsyncSession,
    invitation: Invitation,
    payload: InvitationEditRequest,
    *,
    tenant: Tenant,
    user: User,
) -> Invitation:
    """spec.md "Authorized Caller Edits Non-Personal Invitation Details" —
    changes only the visit-detail fields the caller supplied; the visitor's
    own personal fields, `visitorCategoryId`, and the host are never
    accepted by `InvitationEditRequest` in the first place (rejected at the
    schema level via `extra="forbid"`). Same eligible-status set as
    `reschedule_invitation`. Notifies the primary contact by email
    describing the change, and the resolved host (if any) by push — the
    same `_notify_host` no-op-when-unresolved guard every other lifecycle
    action already uses.

    `pocUserId`/`pocRoleId` (add-invitation-point-of-contact) are the one
    field pair here gated by a *second* permission on top of the router's
    own `invitations:edit` check: the caller must additionally hold
    `invitations:approve` at the invitation's branch — same permission the
    approvals capability already requires to act on/delegate a step — since
    naming who visitors get routed to is closer to an approval action than
    a visit-detail edit. Setting either notifies the newly-named point of
    contact (push, and email when a specific person was named — mirroring
    `delegate_step`'s host-assigned notification) in addition to the
    unconditional visitor edit-notification email/host push below, which
    already reflects the invitation's current `pocName` regardless of what
    changed.

    Setting either is additionally gated by `_poc_eligible`: the visitor
    category must have no configured approval workflow, or the invitation
    must currently be at its final approval level. Enforced here rather
    than trusted from the client, even though the frontend already disables
    the field outside that window.
    """
    # A checked-in visit's location details (department/building) can still be
    # corrected; every other field the client sends is ignored once the visit
    # is underway (the edit modal always submits the whole form).
    checked_in = invitation.status == "checked_in"
    # An archived no-show stays editable; only a date change takes it out of
    # `archived`, back into approval (auto-checkout-and-archive-no-shows D7).
    # Gated on exactly `archived` so a concurrent reschedule can't be undone.
    archived = invitation.status == "archived"
    # A closed visit only accepts a corrected check-out time; the rest of the
    # form is ignored, same as for a checked-in visit above.
    checked_out = invitation.status == "checked_out"
    if payload.checked_out_at is not None and not checked_out:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Check-out time can only be edited once the visit is checked out",
        )
    allowed_statuses: tuple[str, ...]
    if checked_out:
        allowed_statuses = ("checked_out",)
    elif checked_in:
        allowed_statuses = (*_RESCHEDULABLE_STATUSES, "checked_in")
    elif archived:
        allowed_statuses = ("archived",)
    else:
        allowed_statuses = _RESCHEDULABLE_STATUSES
    if invitation.status not in allowed_statuses:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation can no longer be edited")
    if checked_out:
        if payload.checked_out_at is not None and not user.has_permission(
            "invitations:checkout", branch_id=invitation.branch_id
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Caller lacks invitations:checkout required to edit the check-out time",
            )
        _validate_checked_out_at(invitation, payload.checked_out_at)
    elif not checked_in and (payload.poc_user_id is not None or payload.poc_role_id is not None):
        if not user.has_permission("invitations:approve", branch_id=invitation.branch_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Caller lacks invitations:approve required to set the point of contact",
            )
        if not await _poc_eligible(tenant_db, invitation):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=(
                    "Point of contact can only be set when the visitor category has no "
                    "configured approval workflow or the invitation is at its final "
                    "approval level"
                ),
            )
    changes = await _resolve_edit_changes(tenant_db, payload, invitation.branch_id)
    if payload.custom_fields is not None and not (checked_in or checked_out):
        changes.update(await _resolve_custom_field_edit(tenant_db, tenant, invitation, payload))
    if checked_in:
        changes = {k: v for k, v in changes.items() if k in _LOCATION_EDIT_FIELDS}
    elif checked_out:
        changes = {k: v for k, v in changes.items() if k == "checked_out_at"}
        if changes:
            # A person set this time, so it's no longer the sweep's expiry stamp.
            changes.update(checked_out_by_user_id=user.id, checked_out_automatically=False)
    if not changes:
        return invitation
    # Only an actual date change realigns expiry: the edit modal resubmits
    # the unchanged date on every save, which would otherwise wipe a staff
    # expiry extension (expire-invitation-at-end-of-visit-day/design.md D2).
    new_visit_date = changes.get("preferred_visit_date")
    leaves_archive = False
    if new_visit_date is not None and new_visit_date != invitation.preferred_visit_date:
        if archived:
            tz = await _reject_past_visit_date(tenant_db, tenant, new_visit_date)
            changes.update(status="submitted", approved_at=None)
            leaves_archive = True
        else:
            tz = await resolve_visit_timezone(tenant_db, tenant)
        changes["expires_at"] = _end_of_visit_day_utc(new_visit_date, tz)
    updated = await InvitationRepository(tenant_db).edit_if_eligible(
        invitation.id, allowed_statuses=allowed_statuses, **changes
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation can no longer be edited")
    activated_step = await _restart_approval(tenant_db, updated) if leaves_archive else None
    await tenant_db.commit()
    if checked_out:
        # A time correction on a closed visit isn't news to the host/visitor.
        return updated
    tasks.send_edit_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    await _notify_host(tenant, updated, push_notifications.edited)
    await _notify_activated_approver(tenant_db, tenant, updated, activated_step)
    poc_changed = "poc_user_id" in changes or "poc_role_id" in changes
    # A newly named point of contact gets `poc_assigned` below instead — one
    # push per edit, never "details updated" on top (design.md D3).
    if not poc_changed:
        await _push_point_of_contact(
            tenant_db,
            tenant,
            updated,
            push_builder=push_notifications.edited,
            actor_user_id=user.id,
        )
    if poc_changed:
        title, body, data = push_notifications.poc_assigned(updated)
        await notifications_service.notify_step_approver(
            tenant_db,
            tenant_schema=tenant.schema_name,
            approver_user_id=updated.poc_user_id,
            approver_role_id=updated.poc_role_id,
            branch_id=updated.branch_id,
            title=title,
            body=body,
            data=data,
        )
        if updated.poc_user_id is not None:
            tasks.send_poc_creation_notification.delay(
                request_id=current_request_id(),
                tenant_schema=tenant.schema_name,
                invitation_id=str(updated.id),
                poc_id=str(updated.poc_user_id),
            )
    return updated


async def extend_invitation(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    new_expires_at: datetime,
    tenant: Tenant,
    actor_user_id: uuid.UUID | None = None,
) -> Invitation:
    if invitation.status not in _ACTIVE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not active")
    if new_expires_at <= invitation.expires_at:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="New expiry must be later than the current expiry",
        )
    updated = await InvitationRepository(tenant_db).extend_if_eligible(
        invitation.id, new_expires_at=new_expires_at
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not active")
    await tenant_db.commit()
    tz = await resolve_visit_timezone(tenant_db, tenant)
    extended = partial(push_notifications.extended, tz=tz)
    await _notify_host(tenant, updated, extended)
    await _push_point_of_contact(
        tenant_db, tenant, updated, push_builder=extended, actor_user_id=actor_user_id
    )
    return updated
