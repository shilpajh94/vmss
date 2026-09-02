import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.approvals.schemas import CurrentApprovalStepOut
from vmss_api.auth.repository import UserRepository
from vmss_api.core.config import settings
from vmss_api.core.logging import logger
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.storage import FileTooLargeError, UnsupportedFileTypeError, validate_upload
from vmss_api.core.storage import save as storage_save
from vmss_api.invitations import badge, push_notifications, tasks
from vmss_api.invitations.models import Invitation, InvitationVehicle, InvitationVisitor
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.schemas import (
    InvitationCreate,
    InvitationSortableField,
    RegistrationSource,
    VisitDetailsSubmit,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.repository import CompanyRepository, DepartmentRepository
from vmss_api.tenant.models import Tenant
from vmss_api.visit_info.repository import VisitDurationRepository, VisitPurposeRepository
from vmss_api.visitors.repository import ApprovalWorkflowRuleRepository, VisitorCategoryRepository


async def _generate_unique_tracking_id(repo: InvitationRepository) -> str:
    """`INV-XXXXXXXX` — 32 bits of randomness is more than enough given this
    only needs to be unique per tenant schema, but the retry loop (rather
    than trusting a single draw) is what actually guarantees it against the
    unique constraint, not the odds.
    """
    for _ in range(5):
        candidate = "INV-" + secrets.token_hex(4).upper()
        if await repo.get_by_tracking_id(candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique invitation tracking id")


async def _generate_unique_badge_number(repo: InvitationRepository) -> str:
    """`BDG-XXXXXXXX` — same retry-against-uniqueness shape as
    `_generate_unique_tracking_id` above (design.md Decision 4).
    """
    for _ in range(5):
        candidate = "BDG-" + secrets.token_hex(4).upper()
        if await repo.get_by_badge_number(candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique badge number")


def _current_request_id() -> str:
    return structlog.contextvars.get_contextvars().get("request_id", "")


def _validate_id_proof(content: bytes, max_size: int) -> str:
    """Returns the sniffed content type. No storage I/O — call this for
    every visitor's file before persisting any of them, so a submission
    rejected because one visitor's file is invalid never leaves an earlier
    visitor's file written to storage.
    """
    try:
        return validate_upload(content, max_size_bytes=max_size)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


async def _resolve_visit_detail_ids(
    tenant_db: AsyncSession, visit_details: VisitDetailsSubmit
) -> dict[str, Any]:
    """spec.md "Visit Details Optionally Accept Catalog IDs Alongside Free
    Text": each of `purposeId`/`hostId`/`durationId`/`departmentId`, if
    supplied, must resolve to an existing, active row in this tenant's
    schema — its canonical display value then overwrites the paired
    free-text field, never the other way round. Omitted ids leave their
    paired free-text field untouched, identical to today's behavior.
    """
    resolved: dict[str, Any] = {
        "purpose_of_visit": visit_details.purpose_of_visit,
        "host_name_or_email": visit_details.host_name_or_email,
        "expected_duration": visit_details.expected_duration,
        "department_to_visit": visit_details.department_to_visit,
        "purpose_id": None,
        "host_id": None,
        "duration_id": None,
        "department_id": None,
    }
    if visit_details.purpose_id is not None:
        purpose = await VisitPurposeRepository(tenant_db).get_active(visit_details.purpose_id)
        if purpose is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown purposeId")
        resolved["purpose_id"] = purpose.id
        resolved["purpose_of_visit"] = purpose.name
    if visit_details.host_id is not None:
        host = await UserRepository(tenant_db).get_active(visit_details.host_id)
        if host is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown hostId")
        resolved["host_id"] = host.id
        resolved["host_name_or_email"] = host.full_name
    if visit_details.duration_id is not None:
        duration = await VisitDurationRepository(tenant_db).get_active(visit_details.duration_id)
        if duration is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown durationId")
        resolved["duration_id"] = duration.id
        resolved["expected_duration"] = duration.name
    if visit_details.department_id is not None:
        department = await DepartmentRepository(tenant_db).get_active(visit_details.department_id)
        if department is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown departmentId"
            )
        resolved["department_id"] = department.id
        resolved["department_to_visit"] = department.name
    return resolved


async def _resolve_active_category(
    tenant_db: AsyncSession, visitor_category_id: uuid.UUID
) -> uuid.UUID:
    """spec.md "Missing visitor category is rejected" /
    "Unknown, inactive, or cross-tenant visitor category is rejected" —
    validated before any file I/O, same "fail fast" ordering
    `_resolve_visit_detail_ids` already uses for the optional catalog ids.
    """
    category = await VisitorCategoryRepository(tenant_db).get_active(visitor_category_id)
    if category is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown or inactive visitorCategoryId"
        )
    return category.id


def _build_approval_steps(
    rules: list[Any], *, invitation_id: uuid.UUID, now: datetime, host_id: uuid.UUID | None
) -> list[InvitationApprovalStep]:
    """Snapshots a category's active `ApprovalWorkflowRule`s (already
    ordered by `step_order`) into `InvitationApprovalStep` rows — a
    point-in-time copy, not a live reference (design.md Decision 1). When
    `host_id` is not None, an implicit host-identified step is prepended at
    `step_order` 0, ahead of the role-identified steps (specs/approvals/
    spec.md "Submission Snapshots the Category's Active Workflow Into
    Ordered Steps" — add-approval-step-id-and-host-routing). Only the step
    that is current the moment this snapshot is taken — the host step if
    one was prepended, else the first rule step — has its
    `escalates_at`/`auto_approves_at` computed here, relative to `now` (the
    submission timestamp); every later step's pair is computed when it
    becomes the current pending step, i.e. when the step before it is
    approved (`approvals/service.py::approve_step`), per specs/approvals/
    spec.md "Escalation and Auto-Approve Timestamps". The host step never
    has escalation/auto-approve minutes to compute from — no
    `ApprovalWorkflowRule` backs it — so its pair stays null
    (add-approval-step-id-and-host-routing/design.md).
    """
    steps: list[InvitationApprovalStep] = []
    if host_id is not None:
        steps.append(
            InvitationApprovalStep(
                id=uuid.uuid4(),
                invitation_id=invitation_id,
                step_order=0,
                approver_role_id=None,
                approver_user_id=host_id,
                is_mandatory=True,
                status="pending",
                escalation_minutes=None,
                auto_approve_minutes=None,
                escalates_at=None,
                auto_approves_at=None,
            )
        )
    for index, rule in enumerate(rules):
        is_first = index == 0 and host_id is None
        steps.append(
            InvitationApprovalStep(
                id=uuid.uuid4(),
                invitation_id=invitation_id,
                step_order=rule.step_order,
                approver_role_id=rule.approver_role_id,
                approver_user_id=None,
                is_mandatory=rule.is_mandatory,
                status="pending",
                escalation_minutes=rule.escalation_minutes,
                auto_approve_minutes=rule.auto_approve_minutes,
                # Only the first step is current the moment it's snapshotted
                # — every later step's pair is computed when it becomes
                # current instead (`approvals/service.py::_advance_step_clock`).
                escalates_at=(
                    now + timedelta(minutes=rule.escalation_minutes)
                    if is_first and rule.escalation_minutes is not None
                    else None
                ),
                auto_approves_at=(
                    now + timedelta(minutes=rule.auto_approve_minutes)
                    if is_first and rule.auto_approve_minutes is not None
                    else None
                ),
            )
        )
    return steps


async def create_invitation(
    tenant_db: AsyncSession,
    payload: InvitationCreate,
    *,
    branch_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    tenant: Tenant,
    primary_contact_id_proof_content: bytes,
    visitor_id_proof_contents: list[bytes],
    source: RegistrationSource = RegistrationSource.staff_pre_registration,
) -> Invitation:
    """API-09 (and, via `source=visitor_walk_in`, API-13). Creates a fully
    populated invitation in a single call — the validation, ID-proof
    storage, and child-row construction that used to happen in a separate
    self-registration step (API-10, now removed) happen here instead
    (design.md Decisions 1 and 2). Generates the human-readable expiry-bound
    tracking ID and, depending on whether the tenant's Company profile
    auto-approves pre-registered visitors, either resolves the invitation
    as `approved` right away or leaves it `submitted` (awaiting approval)
    — see `add-invitation-approval-flow-and-role-resync/design.md` Decision
    1. Either way, the corresponding notification is enqueued
    (API-11) — never sent inline (`background-jobs.md` §5).

    `created_by_user_id` is `None` for a walk-in registration — there is no
    authenticated staff creator to record
    (add-walkin-visitor-registration/design.md Decision 1).
    """
    if len(payload.visitors) > settings.invitation_max_group_visitors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"A group registration may not list more than "
            f"{settings.invitation_max_group_visitors} visitors",
        )
    if len(payload.visitors) != len(visitor_id_proof_contents):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Visitor list and uploaded ID proof files must match in count",
        )

    # Validated before any file I/O, same "fail fast" reasoning as the
    # optional catalog ids resolved right below.
    visitor_category_id = await _resolve_active_category(tenant_db, payload.visitor_category_id)

    # Validated (and, where an id is present, resolved to its canonical
    # display value) before any file I/O, so a bad `purposeId`/`hostId`/
    # `durationId`/`departmentId` fails fast without wasting a storage write.
    visit_details = await _resolve_visit_detail_ids(tenant_db, payload.visit_details)

    repo = InvitationRepository(tenant_db)
    tracking_id = await _generate_unique_tracking_id(repo)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.invitation_token_ttl_hours)
    max_size = settings.invitation_max_upload_size_bytes

    # Resolved once, at creation, rather than recomputed later — an
    # invitation's approval state is a stable, recorded fact of what
    # actually happened (design.md Decision 1). Defaults to the more
    # conservative "awaiting approval" path when no Company profile is
    # configured yet, matching the column's own default.
    company = await CompanyRepository(tenant_db).get_singleton()
    auto_approved = company is not None and company.auto_approve_pre_registered_visitors
    initial_status = "approved" if auto_approved else "submitted"
    approved_at = now if auto_approved else None

    # Validate every file before persisting any of them (spec.md "Each Visitor
    # Has at Least One Reachable Contact and an ID Proof") — otherwise a later
    # visitor's invalid file would abort the request after an earlier
    # visitor's file was already written to storage.
    primary_content_type = _validate_id_proof(primary_contact_id_proof_content, max_size)
    visitor_content_types = [
        _validate_id_proof(content, max_size) for content in visitor_id_proof_contents
    ]

    primary_key = await storage_save(
        tenant.id, "invitations/id-proof", primary_contact_id_proof_content, primary_content_type
    )

    invitation = Invitation(
        id=uuid.uuid4(),
        branch_id=branch_id,
        created_by_user_id=created_by_user_id,
        source=source.value,
        registration_type=payload.registration_type.value,
        status=initial_status,
        visitor_category_id=visitor_category_id,
        tracking_id=tracking_id,
        expires_at=expires_at,
        submitted_at=now,
        approved_at=approved_at,
        primary_contact_full_name=payload.primary_contact.full_name,
        primary_contact_email=payload.primary_contact.email,
        primary_contact_phone=payload.primary_contact.phone,
        primary_contact_preferred_contact_method=(
            payload.primary_contact.preferred_contact_method.value
        ),
        primary_contact_id_proof_type=payload.primary_contact.id_proof_type.value,
        primary_contact_id_proof_storage_key=primary_key,
        purpose_of_visit=visit_details["purpose_of_visit"],
        host_name_or_email=visit_details["host_name_or_email"],
        preferred_visit_date=payload.visit_details.preferred_visit_date,
        preferred_visit_time=payload.visit_details.preferred_visit_time,
        expected_duration=visit_details["expected_duration"],
        department_to_visit=visit_details["department_to_visit"],
        additional_notes=payload.visit_details.additional_notes,
        purpose_id=visit_details["purpose_id"],
        host_id=visit_details["host_id"],
        duration_id=visit_details["duration_id"],
        department_id=visit_details["department_id"],
        carried_items=[item.value for item in payload.carried_items.items],
        carried_items_description=payload.carried_items.item_description,
        terms_accepted=payload.consents.terms_accepted,
        data_processing_accepted=payload.consents.data_processing_accepted,
        safety_guidelines_accepted=payload.consents.safety_guidelines_accepted,
        consent_recorded_at=now,
    )
    tenant_db.add(invitation)

    visitor_rows = [
        InvitationVisitor(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            full_name=visitor.full_name,
            email=visitor.email,
            phone=visitor.phone,
            id_proof_type=visitor.id_proof_type.value,
            id_proof_storage_key=await storage_save(
                tenant.id, "invitations/id-proof", content, content_type
            ),
        )
        for visitor, content, content_type in zip(
            payload.visitors, visitor_id_proof_contents, visitor_content_types, strict=True
        )
    ]
    vehicle_rows = [
        InvitationVehicle(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            vehicle_type=vehicle.vehicle_type.value,
            license_plate=vehicle.license_plate,
            make_model=vehicle.make_model,
            color=vehicle.color,
        )
        for vehicle in payload.vehicles
    ]
    repo.add_visitors(visitor_rows)
    repo.add_vehicles(vehicle_rows)

    # Snapshot the category's active workflow rules into ordered steps
    # (specs/approvals/spec.md "Submission Snapshots the Category's Active
    # Workflow Into Ordered Steps") — only for a `submitted` (not
    # auto-approved) invitation, and only once, in the same transaction as
    # the `Invitation` insert above (design.md Decision 1). A resolved host
    # additionally gets an implicit step 0 ahead of the role chain
    # (add-approval-step-id-and-host-routing/design.md) — unconditional
    # whenever the host resolves, regardless of whether the category has
    # any active rules. Neither a host nor any active rules: no steps,
    # today's single-approve behavior.
    if not auto_approved:
        rules = await ApprovalWorkflowRuleRepository(tenant_db).list_active_for_category(
            visitor_category_id
        )
        host_id = visit_details["host_id"]
        if rules or host_id is not None:
            InvitationApprovalStepRepository(tenant_db).add_steps(
                _build_approval_steps(rules, invitation_id=invitation.id, now=now, host_id=host_id)
            )

    await tenant_db.commit()

    created = await repo.get_with_children(invitation.id)
    assert created is not None  # just committed; guaranteed to exist

    notification_task = (
        tasks.send_approval_notification if auto_approved else tasks.send_tracking_notification
    )
    notification_task.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(invitation.id),
    )

    # Staff-facing push, additional to the visitor email/SMS above
    # (specs/invitations/spec.md "Invitation Submission Notifies the
    # Approval Workflow's First Approver(s) via Push"). An auto-approved
    # invitation never has approval steps, so `current_step` is always None
    # on that path and no push fires — matching "Auto-Approved Invitations
    # Do Not Trigger a Submission Push".
    if not auto_approved:
        current_step = await InvitationApprovalStepRepository(tenant_db).get_current_pending(
            invitation.id
        )
        if current_step is not None:
            title, body, data = push_notifications.step_awaiting_approval(created)
            await notifications_service.notify_step_approver(
                tenant_db,
                tenant_schema=tenant.schema_name,
                approver_user_id=current_step.approver_user_id,
                approver_role_id=current_step.approver_role_id,
                branch_id=invitation.branch_id,
                title=title,
                body=body,
                data=data,
            )
        else:
            # No resolved host and no active workflow rules — nobody to
            # notify (proposal.md's "no push recipient" case).
            logger.warning("push_notify_no_approval_step", invitation_id=str(invitation.id))

    return created


async def get_invitation(tenant_db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
    """Plain by-id fetch, no eager-loaded children — used by
    `POST /invitations/{id}/approve` to resolve the invitation's own
    `branch_id` for `authorize_branch_id_tolerant` before the state
    transition.
    """
    invitation = await InvitationRepository(tenant_db).get(invitation_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


async def approve_invitation(
    tenant_db: AsyncSession, invitation: Invitation, *, tenant: Tenant
) -> Invitation:
    """Transitions a `submitted` invitation to `approved` and enqueues the
    approval notification (`add-invitation-approval-flow-and-role-resync/
    design.md` Decision 3), mirroring `create_invitation`'s own
    dispatch-after-commit pattern. `router.py` fetches `invitation` and
    resolves branch authorization (404/403) before calling this — a
    not-found or unauthorized invitation never reaches here.

    The transition itself goes through `InvitationRepository
    .approve_if_submitted` — a single conditional `UPDATE`, not a
    read-then-write on the `invitation` object already in hand — so two
    concurrent approval requests for the same invitation can't both pass a
    status check and both dispatch a notification (see
    codebase-review-and-e2e-scenario-test/design.md).

    Rejected with 409 (design.md Decision 3) if the invitation still has a
    `pending` `InvitationApprovalStep` — that invitation must be approved
    step by step through `POST /invitations/{id}/approval-steps/{stepId}
    /approve` instead (specs/invitations/spec.md "Blanket approve rejected
    for a workflow-backed invitation"). Checking for a *pending* step, not
    merely "any step at all", is what lets `approvals.service.approve_step`
    call this function verbatim to finalize the last step (design.md
    Decision 2) — by then every step is already `approved`, so this guard
    correctly falls through instead of rejecting its own caller.
    """
    if await InvitationApprovalStepRepository(tenant_db).has_pending_for_invitation(invitation.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation has a configured approval workflow; approve its steps instead",
        )
    updated = await InvitationRepository(tenant_db).approve_if_submitted(invitation.id)
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not awaiting approval")
    await tenant_db.commit()
    tasks.send_approval_notification.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    if updated.host_id is not None:
        title, body, data = push_notifications.approved(updated)
        await notifications_service.notify_user(
            tenant_schema=tenant.schema_name,
            user_id=updated.host_id,
            title=title,
            body=body,
            data=data,
        )
    return updated


async def get_invitation_detail(tenant_db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
    """Eager-loaded counterpart of `get_invitation` — backs
    `GET /invitations/{id}`, whose response schema (`InvitationDetailOut`)
    serializes `visitors`/`vehicles` the same way `InvitationTrackingOut`
    does.
    """
    invitation = await InvitationRepository(tenant_db).get_with_children(invitation_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


async def deny_invitation(
    tenant_db: AsyncSession, invitation: Invitation, *, reason: str, tenant: Tenant
) -> Invitation:
    """Transitions a `submitted` invitation to `denied` and enqueues the
    denial notification — mirrors `approve_invitation`'s own
    dispatch-after-commit pattern (spec.md "A Submitted Invitation Can Be
    Denied With a Reason").
    """
    updated = await InvitationRepository(tenant_db).deny_if_submitted(invitation.id, reason=reason)
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not awaiting approval")
    await tenant_db.commit()
    tasks.send_denial_notification.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    if updated.host_id is not None:
        title, body, data = push_notifications.denied(updated)
        await notifications_service.notify_user(
            tenant_schema=tenant.schema_name,
            user_id=updated.host_id,
            title=title,
            body=body,
            data=data,
        )
    return updated


async def _perform_check_in(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    actor_user_id: uuid.UUID | None,
    tenant: Tenant,
) -> Invitation:
    """spec.md "An Approved Invitation Can Be Checked In" /
    "A Watchlist-Flagged Invitation Blocks Check-In Until Overridden" /
    "An Approved Invitation Can Be Publicly Checked In By Tracking ID". The
    pre-check below gives a caller a specific reason for the 409 (flagged vs.
    wrong status); the repository's atomic `WHERE` clause re-checks both
    conditions so a race with a concurrent flag/status change can't slip a
    check-in through between this read and the write.

    `actor_user_id` is `None` for the public, tracking-ID-keyed check-in path
    (there is no authenticated caller to record) — `checked_in_by_user_id` is
    nullable at the model level for exactly this case.
    """
    if invitation.watchlist_flagged:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation is watchlist-flagged; override required before check-in",
        )
    if invitation.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not approved")
    updated = await InvitationRepository(tenant_db).check_in_if_eligible(
        invitation.id, user_id=actor_user_id
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation is no longer eligible for check-in",
        )
    await tenant_db.commit()
    if updated.host_id is not None:
        title, body, data = push_notifications.checked_in(updated)
        await notifications_service.notify_user(
            tenant_schema=tenant.schema_name,
            user_id=updated.host_id,
            title=title,
            body=body,
            data=data,
        )
    return updated


async def check_in_invitation(
    tenant_db: AsyncSession, invitation: Invitation, *, user_id: uuid.UUID, tenant: Tenant
) -> Invitation:
    """`PATCH /api/v1/invitations/{id}/check-in` — staff-authenticated,
    UUID-keyed. See `_perform_check_in` for the shared transition logic.
    """
    return await _perform_check_in(tenant_db, invitation, actor_user_id=user_id, tenant=tenant)


async def check_in_invitation_by_tracking_id(
    tenant_db: AsyncSession, tracking_id: str, *, tenant: Tenant
) -> Invitation:
    """`PATCH /api/v2/invitations/{trackingId}/check-in` — public,
    unauthenticated, tracking-ID-keyed (spec.md "An Approved Invitation Can
    Be Publicly Checked In By Tracking ID"). No authenticated caller, so no
    branch authorization check and no human actor recorded.
    """
    invitation = await InvitationRepository(tenant_db).get_by_tracking_id(tracking_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return await _perform_check_in(tenant_db, invitation, actor_user_id=None, tenant=tenant)


async def check_out_invitation(
    tenant_db: AsyncSession, invitation: Invitation, *, user_id: uuid.UUID, tenant: Tenant
) -> Invitation:
    updated = await InvitationRepository(tenant_db).check_out_if_checked_in(
        invitation.id, user_id=user_id
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not checked in")
    await tenant_db.commit()
    if updated.host_id is not None:
        title, body, data = push_notifications.checked_out(updated)
        await notifications_service.notify_user(
            tenant_schema=tenant.schema_name,
            user_id=updated.host_id,
            title=title,
            body=body,
            data=data,
        )
    return updated


_RESCHEDULABLE_STATUSES = ("submitted", "approved")
_ACTIVE_STATUSES = ("approved", "checked_in")


async def reschedule_invitation(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    preferred_visit_date: Any,
    preferred_visit_time: Any,
    tenant: Tenant,
) -> Invitation:
    """Notifies the primary contact of the new date/time on success
    (specs/invitations/spec.md "Reschedule Dispatches a Notification to the
    Primary Contact") — enqueued only after the commit below, never for a
    request rejected by either guard.
    """
    if invitation.status not in _RESCHEDULABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation can no longer be rescheduled"
        )
    updated = await InvitationRepository(tenant_db).reschedule_if_eligible(
        invitation.id,
        preferred_visit_date=preferred_visit_date,
        preferred_visit_time=preferred_visit_time,
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation can no longer be rescheduled"
        )
    await tenant_db.commit()
    tasks.send_reschedule_notification.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    if updated.host_id is not None:
        title, body, data = push_notifications.rescheduled(updated)
        await notifications_service.notify_user(
            tenant_schema=tenant.schema_name,
            user_id=updated.host_id,
            title=title,
            body=body,
            data=data,
        )
    return updated


async def extend_invitation(
    tenant_db: AsyncSession, invitation: Invitation, *, new_expires_at: datetime
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
    return updated


async def issue_badge(
    tenant_db: AsyncSession, invitation: Invitation, *, tenant: Tenant
) -> Invitation:
    """spec.md "A Badge Can Be Printed for an Approved or Active Visit" —
    generates the badge number and renders the image before the guarded
    `UPDATE`, same "validate/generate before the write" ordering
    `create_invitation` already uses for ID-proof uploads.
    """
    if invitation.status not in _ACTIVE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not eligible for a badge"
        )
    if invitation.badge_number is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A badge is already issued for this invitation; use the reprint endpoint",
        )
    repo = InvitationRepository(tenant_db)
    badge_number = await _generate_unique_badge_number(repo)
    png = await badge.render_badge_png(
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        expires_at=invitation.expires_at,
    )
    storage_key = await storage_save(tenant.id, "invitations/badges", png, "image/png")
    updated = await repo.issue_badge_if_eligible(
        invitation.id, badge_number=badge_number, badge_storage_key=storage_key
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not eligible for a badge"
        )
    await tenant_db.commit()
    return updated


async def reprint_badge(
    tenant_db: AsyncSession, invitation: Invitation, *, tenant: Tenant
) -> Invitation:
    """spec.md "A Badge Can Be Reprinted" — re-renders from the invitation's
    *current* data (not what was captured at original issuance), so a
    reprint after a reschedule/extension reflects the up-to-date values.
    """
    if invitation.badge_number is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No badge has been issued for this invitation yet; use the issuance endpoint",
        )
    png = await badge.render_badge_png(
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        expires_at=invitation.expires_at,
    )
    storage_key = await storage_save(tenant.id, "invitations/badges", png, "image/png")
    updated = await InvitationRepository(tenant_db).reprint_badge_if_issued(
        invitation.id, badge_storage_key=storage_key
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No badge has been issued for this invitation yet; use the issuance endpoint",
        )
    await tenant_db.commit()
    return updated


async def override_watchlist(
    tenant_db: AsyncSession, invitation: Invitation, *, user_id: uuid.UUID, reason: str
) -> Invitation:
    """spec.md "A Watchlist-Flagged Invitation Blocks Check-In Until
    Overridden" — clears the flag only; it does not itself check the
    invitation in.
    """
    updated = await InvitationRepository(tenant_db).override_watchlist_if_flagged(
        invitation.id, user_id=user_id, reason=reason
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not currently watchlist-flagged"
        )
    await tenant_db.commit()
    return updated


async def get_current_approval_step(
    tenant_db: AsyncSession, invitation: Invitation
) -> CurrentApprovalStepOut | None:
    """Backs the `currentApprovalStep` field on `InvitationOut`/
    `InvitationTrackingOut`/`InvitationDetailOut` (design.md Decision 7) —
    two indexed queries (current pending step + total count), run only for a
    single-invitation lookup, never for `GET /invitations` list rows
    (query-performance.md §2). `None` for an invitation with no snapshotted
    steps, or one that is no longer `submitted`
    (specs/invitations/spec.md "Non-workflow invitation omits step
    progress").
    """
    if invitation.status != "submitted":
        return None
    repo = InvitationApprovalStepRepository(tenant_db)
    current = await repo.get_current_pending(invitation.id)
    if current is None:
        return None
    total_steps = await repo.count_for_invitation(invitation.id)
    return CurrentApprovalStepOut(
        id=current.id,
        step_order=current.step_order,
        approver_role_id=current.approver_role_id,
        approver_user_id=current.approver_user_id,
        total_steps=total_steps,
        delegated_to_user_id=current.delegated_to_user_id,
    )


async def track_by_tracking_id(tenant_db: AsyncSession, tracking_id: str) -> Invitation:
    invitation = await InvitationRepository(tenant_db).get_by_tracking_id(tracking_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


async def track_by_email(tenant_db: AsyncSession, email: str) -> list[Invitation]:
    """Deliberately returns bare `Invitation` rows with no eager-loaded
    children — the router maps these onto `InvitationTrackingSummaryOut`
    (tracking id + status only), never the full-detail schema, per spec.md's
    minimal-disclosure requirement.
    """
    return await InvitationRepository(tenant_db).list_by_primary_contact_email(email)


async def list_invitations_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope | None,
    relevant_to_user_id: uuid.UUID | None = None,
    status: str | None,
    registration_type: str | None,
    source: str | None,
    page: int,
    page_size: int,
    sort_by: InvitationSortableField,
    sort_order: SortOrder,
) -> tuple[list[Invitation], int]:
    return await InvitationRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        relevant_to_user_id=relevant_to_user_id,
        status=status,
        registration_type=registration_type,
        source=source,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
