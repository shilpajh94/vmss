import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.approvals.schemas import CurrentApprovalStepOut
from vmss_api.auth.models import User
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.core.config import settings
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.redis import get_redis
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.storage import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    validate_image_only,
    validate_upload,
)
from vmss_api.core.storage import save as storage_save
from vmss_api.core.storage import url_for as storage_url_for
from vmss_api.form_builder import service as form_builder_service
from vmss_api.form_builder import validation as form_builder_validation
from vmss_api.invitations import badge, push_notifications, tasks
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.invitations.qr_token import decrypt_invitation_token, encrypt_invitation_token
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.schemas import (
    InvitationCreate,
    InvitationEditRequest,
    InvitationLookupPrefillOut,
    InvitationSortableField,
    RegistrationSource,
    VisitDetailsSubmit,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch, Building, Department
from vmss_api.org_structure.repository import CompanyRepository, DepartmentRepository
from vmss_api.org_structure.service import get_default_host_role
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


def _resolve_tenant_timezone(tenant: Tenant) -> ZoneInfo:
    """Mirrors `dashboard/service.py::_resolve_tenant_timezone` — falls back
    to UTC (logged at `WARNING`) rather than raising when `Tenant.timezone`
    isn't a real IANA zone name. Kept as a small local duplicate rather than
    a cross-feature import (qr-checkin-scheduling-photo-email/design.md
    Decision 1 — no existing import between `invitations` and `dashboard`,
    and one two-line helper doesn't justify introducing one).
    """
    try:
        return ZoneInfo(tenant.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("invitations_invalid_tenant_timezone", tenant_timezone=tenant.timezone)
        return ZoneInfo("UTC")


def _end_of_visit_day_utc(visit_date: date, tenant: Tenant) -> datetime:
    """Access for an approved visit is valid through the end of the visit
    day itself, not the fixed creation-time TTL `expires_at` starts out
    with — computed in the tenant's local timezone (the same zone
    `check_in_by_qr_token`'s same-day gate uses) and converted to UTC for
    storage.
    """
    tz = _resolve_tenant_timezone(tenant)
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


def _validate_photo(content: bytes, max_size: int) -> str:
    """Same content-sniffing/size approach as `_validate_id_proof`, but
    image-only (no PDF) — a profile photo, unlike an ID-proof scan, is never
    a document (checkin-approval-workflow-improvements spec.md "Visitor and
    Primary Contact Registration Optionally Captures a Profile Photo").
    """
    return validate_image_only(content, max_size_bytes=max_size, field_label="photo")


def _group_field_file_id(group: dict[str, Any]) -> str | None:
    """The id of `group`'s own `file_upload`-typed field, or `None` if it
    has none (add-group-field-file-upload). Mirrors the "first field of a
    given `fieldType`" convention `invitations/router.py::
    _group_collected_visitor_detail_outs` already uses for `email`/`phone`
    — only the first such field is supported; a group defining more than
    one `file_upload` field is unusual enough that "first" is an acceptable
    simplification, same as that function's own. Referenced by id
    (restructure-walkin-payload-by-field-id), never by key.
    """
    return next(
        (field["id"] for field in group.get("fields", []) if field["fieldType"] == "file_upload"),
        None,
    )


async def _resolve_visit_detail_ids(
    tenant_db: AsyncSession, visit_details: VisitDetailsSubmit
) -> dict[str, Any]:
    """spec.md "Visit Details Optionally Accept Catalog IDs Alongside Free
    Text": each of `purposeId`/`durationId`/`departmentId`, if supplied, must
    resolve to an existing, active row in this tenant's schema — its
    canonical display value then overwrites the paired free-text field,
    never the other way round. Omitted ids leave their paired free-text
    field untouched, identical to today's behavior.

    `hostId`/`hostNameOrEmail` are deliberately never resolved here anymore
    (role-based-invitation-workflow) — an invitation's host is established
    exclusively by delegating its host-nomination step (whichever step
    that turns out to be — see `_build_approval_steps` below and the
    `approvals` capability), never by anything submitted at creation. Both
    fields are still accepted on the wire (for an un-updated client) but
    are silently ignored: `host_name_or_email` is always `None` at creation,
    `host_id` is always `None` until a delegation resolves it.
    """
    resolved: dict[str, Any] = {
        "purpose_of_visit": visit_details.purpose_of_visit,
        "expected_duration": visit_details.expected_duration,
        "department_to_visit": visit_details.department_to_visit,
        "purpose_id": None,
        "duration_id": None,
        "department_id": None,
    }
    if visit_details.purpose_id is not None:
        purpose = await VisitPurposeRepository(tenant_db).get_active(visit_details.purpose_id)
        if purpose is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown purposeId")
        resolved["purpose_id"] = purpose.id
        resolved["purpose_of_visit"] = purpose.name
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


async def _resolve_active_branch(tenant_db: AsyncSession, branch_id: uuid.UUID) -> uuid.UUID:
    stmt = select(Branch.id).where(
        Branch.id == branch_id, Branch.is_active.is_(True), Branch.deleted_at.is_(None)
    )
    if (await tenant_db.execute(stmt)).scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown or inactive branch"
        )
    return branch_id


async def _resolve_building(
    tenant_db: AsyncSession, building_id: uuid.UUID | None, branch_id: uuid.UUID
) -> uuid.UUID | None:
    if building_id is None:
        return None
    stmt = select(Building.id).where(
        Building.id == building_id,
        Building.branch_id == branch_id,
        Building.is_active.is_(True),
        Building.deleted_at.is_(None),
    )
    if (await tenant_db.execute(stmt)).scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown building for the selected branch",
        )
    return building_id


async def _match_department_by_name(
    tenant_db: AsyncSession, branch_id: uuid.UUID, name: str
) -> uuid.UUID | None:
    stmt = select(Department.id).where(
        Department.branch_id == branch_id,
        Department.is_active.is_(True),
        Department.deleted_at.is_(None),
        func.lower(Department.name) == name.strip().lower(),
    )
    matches = (await tenant_db.execute(stmt)).scalars().all()
    return matches[0] if len(matches) == 1 else None


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
    rules: list[Any], *, invitation_id: uuid.UUID, owning_role_id: uuid.UUID, now: datetime
) -> list[InvitationApprovalStep]:
    """Snapshots a category's active `ApprovalWorkflowRule`s (already
    ordered by `step_order`) into `InvitationApprovalStep` rows — a
    point-in-time copy, not a live reference (design.md Decision 1).

    A category with at least one active rule produces exactly the rules it
    configures, unchanged — no separate ownership step is inserted ahead of
    them (revises role-based-invitation-workflow's original "always an
    unconditional stepOrder-0 ownership step" design: that step was
    unconditional specifically so an invitation always had *somewhere* to
    nominate a host from, but a category's own first configured level
    already serves that purpose just as well, and forcing a redundant
    step in front of it — most visibly when that first level is already the
    tenant's default host role, e.g. reception — produced two consecutive
    reception approvals before reaching the category's real workflow, which
    didn't match what was configured in admin). The first snapshotted step
    is always the invitation's host-nomination step regardless of which
    role it's for — see `approvals/repository.py::get_first_step` and
    `approvals/service.py::delegate_step`, neither of which assume that
    step's `step_order` is a literal `0` anymore.

    A category with **no** active rules still gets exactly one synthetic
    step, `step_order` 0, role-identified for `owning_role_id` (the tenant's
    default host role) — this is the only case that step still exists —
    preserving two invariants that predate this change: every submitted
    invitation has at least one step (so blanket `POST /invitations/{id}
    /approve` stays unavailable for every submitted invitation, not just
    workflow-backed ones), and there's still somewhere to nominate a host
    from even when the category has no configured workflow at all.

    Every step but the first has its `escalates_at`/`auto_approves_at` left
    null here, computed later when it actually becomes the current pending
    step (`approvals/service.py::approve_step`/`_activate_next_step`, per
    specs/approvals/spec.md "Escalation and Auto-Approve Timestamps") — the
    first step is the one exception, since it's current from the moment
    it's snapshotted (there's no earlier step whose approval would trigger
    `_activate_next_step` for it), so its own clock is computed right here
    instead, the same way `_activate_next_step` computes any other step's.
    """
    if not rules:
        return [
            InvitationApprovalStep(
                id=uuid.uuid4(),
                invitation_id=invitation_id,
                step_order=0,
                approver_role_id=owning_role_id,
                approver_user_id=None,
                is_mandatory=True,
                status="pending",
                escalation_minutes=None,
                auto_approve_minutes=None,
                escalates_at=None,
                auto_approves_at=None,
            )
        ]

    first_rule, *later_rules = rules
    steps: list[InvitationApprovalStep] = [
        InvitationApprovalStep(
            id=uuid.uuid4(),
            invitation_id=invitation_id,
            step_order=first_rule.step_order,
            approver_role_id=first_rule.approver_role_id,
            approver_user_id=None,
            is_mandatory=first_rule.is_mandatory,
            status="pending",
            escalation_minutes=first_rule.escalation_minutes,
            auto_approve_minutes=first_rule.auto_approve_minutes,
            escalates_at=(
                now + timedelta(minutes=first_rule.escalation_minutes)
                if first_rule.escalation_minutes is not None
                else None
            ),
            auto_approves_at=(
                now + timedelta(minutes=first_rule.auto_approve_minutes)
                if first_rule.auto_approve_minutes is not None
                else None
            ),
        )
    ]
    steps.extend(
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
            escalates_at=None,
            auto_approves_at=None,
        )
        for rule in later_rules
    )
    return steps


async def create_invitation(
    tenant_db: AsyncSession,
    payload: InvitationCreate,
    *,
    branch_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    tenant: Tenant,
    primary_contact_id_proof_content: bytes | None,
    visitor_id_proof_contents: list[bytes],
    primary_contact_photo_content: bytes | None,
    visitor_photo_contents: list[bytes],
    group_field_file_contents: dict[str, list[bytes]] | None = None,
    primary_contact_custom_field_file_contents: dict[str, list[bytes]] | None = None,
    visitor_custom_field_file_contents: dict[str, list[bytes]] | None = None,
    vehicle_custom_field_file_contents: dict[str, list[bytes]] | None = None,
    custom_field_file_contents: dict[str, list[bytes]] | None = None,
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

    `group_field_file_contents` (add-group-field-file-upload) is keyed by
    admin-defined group id (restructure-walkin-payload-by-field-id), each
    value an order-matched list of raw file bytes for that group's own
    `file_upload`-typed field, one per submitted instance in
    `payload.group_values[group_id]` — the router's counterpart to
    `visitor_id_proof_contents` for the fixed `visitors` list, since a
    custom group's fields are branch-specific and unknown at route
    -declaration time. Only a group with exactly one `file_upload` field is
    supported; that field's *client-supplied JSON value*, if any, is
    rejected (`_group_field_file_id` below) — the file is the only valid
    source of that field's answer.

    `primary_contact_custom_field_file_contents`/`visitor_custom_field_file_contents`/
    `vehicle_custom_field_file_contents`/`custom_field_file_contents`
    (add-inline-custom-field-file-upload) are the standalone (non-grouped)
    counterpart to `group_field_file_contents` above — an admin-authored
    `file_upload` field directly on Visitor Info/Vehicle Info/any other step,
    not one assigned to a repeatable group. Each is keyed by field id (not
    group id, so — unlike a group — every `file_upload` field at a scope is
    supported, not just the first), the primary-contact/invitation-level
    dicts holding an at-most-one-element list per id, the visitor/vehicle
    ones an order-matched list per id, one entry per submitted
    `payload.visitors`/`payload.vehicles` row. Same "file is the only valid
    source of that field's answer" rule as the group case.

    `created_by_user_id` is `None` for a walk-in registration — there is no
    authenticated staff creator to record
    (add-walkin-visitor-registration/design.md Decision 1).
    """
    # Validated before any file I/O, same "fail fast" reasoning as the
    # optional catalog ids resolved right below.
    visitor_category_id = await _resolve_active_category(tenant_db, payload.visitor_category_id)

    # Validated (and, where an id is present, resolved to its canonical
    # display value) before any file I/O, so a bad `purposeId`/`hostId`/
    # `durationId`/`departmentId` fails fast without wasting a storage write.
    visit_details = await _resolve_visit_detail_ids(tenant_db, payload.visit_details)

    # Branch-configured requiredness/allow-lists (form-builder), resolved
    # once, ahead of every check below that depends on it — see
    # `openspec/changes/form-builder/design.md` Decision 5.
    redis = await get_redis()
    effective_form = await form_builder_service.resolve_effective_form(
        tenant_db, redis, tenant_id=tenant.id, branch_id=branch_id
    )
    id_proof_required = form_builder_validation.is_field_required(
        effective_form, "visitor_info", "id_proof_upload", default=False
    )
    photo_required = form_builder_validation.is_field_required(
        effective_form, "visitor_info", "profile_photo", default=False
    )
    # No requiredness check for "Expected Duration" (unlike ID proof/photo
    # above) — the visitor-facing wizards no longer collect this field at
    # all (make-expected-duration-optional), so there's no client left that
    # could ever satisfy a branch-configured requirement for it; enforcing
    # one here would just permanently reject every submission instead.
    required_consent_field_ids = form_builder_validation.required_consent_field_ids(effective_form)
    allowed_consent_field_ids = form_builder_validation.allowed_consent_field_ids(effective_form)
    allowed_carried_item_keys = form_builder_validation.allowed_carried_item_keys(effective_form)
    allowed_id_proof_types = form_builder_validation.allowed_id_proof_types(effective_form)
    allowed_vehicle_types = form_builder_validation.allowed_vehicle_types(effective_form)

    # ID proof: every visitor (primary + each co-visitor) supplies one,
    # matched 1:1, unless the calling branch has deactivated it — see
    # specs/invitations/spec.md (delta) "Every Visitor Has a Reachable
    # Contact and a Validated ID Proof".
    if id_proof_required:
        if len(payload.visitors) != len(visitor_id_proof_contents):
            logger.warning(
                "registration_form_config_validation_failed",
                branch_id=str(branch_id),
                check="required_field",
                field="id_proof_upload",
                reason="visitor_id_proof_count_mismatch",
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Visitor list and uploaded ID proof files must match in count",
            )
        if (
            payload.primary_contact.id_proof_type is None
            or primary_contact_id_proof_content is None
        ):
            logger.warning(
                "registration_form_config_validation_failed",
                branch_id=str(branch_id),
                check="required_field",
                field="id_proof_upload",
                reason="primary_contact_id_proof_missing",
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="ID proof is required for the primary contact",
            )
        if any(visitor.id_proof_type is None for visitor in payload.visitors):
            logger.warning(
                "registration_form_config_validation_failed",
                branch_id=str(branch_id),
                check="required_field",
                field="id_proof_upload",
                reason="visitor_id_proof_type_missing",
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="ID proof type is required for every visitor",
            )
    elif len(visitor_id_proof_contents) > len(payload.visitors):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="More ID proof files were uploaded than visitors listed",
        )

    # specs/invitations/spec.md (delta) "Every Visitor Has a Reachable
    # Contact and a Validated ID Proof" — a supplied ID proof type must be
    # one of the calling branch's currently configured options, mirroring
    # the carried-items/consent-keys allow-list checks below
    # (make-id-proof-and-vehicle-type-configurable).
    supplied_id_proof_types = {
        v.id_proof_type for v in payload.visitors if v.id_proof_type is not None
    }
    if payload.primary_contact.id_proof_type is not None:
        supplied_id_proof_types.add(payload.primary_contact.id_proof_type)
    invalid_id_proof_types = (
        set()
        if allowed_id_proof_types is None
        else supplied_id_proof_types - allowed_id_proof_types
    )
    if invalid_id_proof_types:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="id_proof_type",
            reason="unknown_id_proof_type",
            values=sorted(invalid_id_proof_types),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown ID proof type(s): {', '.join(sorted(invalid_id_proof_types))}",
        )

    if photo_required and primary_contact_photo_content is None:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="required_field",
            field="profile_photo",
            reason="primary_contact_photo_missing",
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A profile photo is required for the primary contact",
        )

    # specs/invitations/spec.md (delta) "Carried Items and Vehicles Are
    # Optional Structured Declarations" — every declared item must be one
    # of the calling branch's currently configured Carried Items keys.
    invalid_items = set(payload.carried_items.items) - allowed_carried_item_keys
    if invalid_items:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="carried_item",
            reason="unknown_carried_item_key",
            keys=sorted(invalid_items),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown carried item(s): {', '.join(sorted(invalid_items))}",
        )

    # specs/invitations/spec.md (delta) "Carried Items and Vehicles Are
    # Optional Structured Declarations" — a declared vehicle's type must be
    # one of the calling branch's currently configured Vehicle Type options
    # (make-id-proof-and-vehicle-type-configurable).
    invalid_vehicle_types = (
        set()
        if allowed_vehicle_types is None
        else {v.vehicle_type for v in payload.vehicles} - allowed_vehicle_types
    )
    if invalid_vehicle_types:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="vehicle_type",
            reason="unknown_vehicle_type",
            values=sorted(invalid_vehicle_types),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown vehicle type(s): {', '.join(sorted(invalid_vehicle_types))}",
        )

    # specs/invitations/spec.md (delta) "Carried Items and Vehicles Are
    # Optional Structured Declarations" (add-repeatable-field-groups) — the
    # declared vehicle count must fall within the branch's currently
    # published Vehicle Info group instance range.
    vehicle_group = form_builder_validation.vehicle_info_group(effective_form)
    try:
        form_builder_validation.validate_group_instance_count(
            vehicle_group, len(payload.vehicles), scope="This invitation"
        )
    except HTTPException:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="group_instance_count",
            reason="vehicle_count_out_of_range",
            count=len(payload.vehicles),
        )
        raise

    # specs/invitations/spec.md (delta) "A Group Registration's Visitor
    # Count Is Capped By the Visitor Info Group's Configured Maximum"
    # (add-repeatable-field-groups) — retires the standalone
    # `settings.invitation_max_group_visitors` check in favor of this
    # group's own `maxInstances`, the same enforcement path every other
    # group already uses.
    visitor_group = form_builder_validation.visitor_info_group(effective_form)
    try:
        form_builder_validation.validate_group_instance_count(
            visitor_group, len(payload.visitors), scope="A group registration"
        )
    except HTTPException:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="group_instance_count",
            reason="visitor_count_out_of_range",
            count=len(payload.visitors),
        )
        raise

    # specs/invitations/spec.md (delta) "Consent Is Mandatory and Recorded"
    # (restructure-walkin-payload-by-field-id) — the payload must not
    # introduce a `fieldId` outside the calling branch's currently
    # configured Consent Agreement set, mirroring the carried-items
    # allow-list check above. A `fieldId` belonging to a different branch's
    # form is rejected here identically — `allowed_consent_field_ids` only
    # ever reflects the resolved branch's own effective form.
    consents_dict = payload.consents_dict
    invalid_consent_field_ids = set(consents_dict) - allowed_consent_field_ids
    if invalid_consent_field_ids:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="consent_field_id",
            reason="unknown_consent_field_id",
            field_ids=sorted(invalid_consent_field_ids),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown consent field id(s): {', '.join(sorted(invalid_consent_field_ids))}",
        )

    # ... and every consent the calling branch's Consent Agreement step
    # marks required must be accepted.
    accepted_consent_field_ids = {fid for fid, accepted in consents_dict.items() if accepted}
    missing_consents = required_consent_field_ids - accepted_consent_field_ids
    if missing_consents:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="consent_field_id",
            reason="missing_required_consent",
            field_ids=sorted(missing_consents),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Missing required consent(s): {', '.join(sorted(missing_consents))}",
        )

    # specs/invitations/spec.md (delta) "A Retyped System Field's
    # Submitted Value Is Validated Against Its Currently Configured Type"
    # (make-system-field-types-editable) — every other system field Form
    # Builder allows to be retyped, checked in one loop rather than a
    # near-duplicate `if` block per key. `host`/`department_to_visit` are
    # deliberately excluded: neither is a Form Builder field any more
    # (remove-dead-host-department-system-fields) — `host_name_or_email` is
    # always discarded by `_resolve_visit_detail_ids`
    # (role-based-invitation-workflow), and `department_to_visit` is always
    # free text or resolved from the `departmentId` catalog above, never
    # constrained by a Form Builder-configured option list. Including
    # either here would trip `allowed_options_for_system_field`'s
    # "field isn't part of the active configuration at all" branch — `[]`,
    # rejecting every value — since the field no longer exists in the
    # effective form at all.
    retypeable_field_values: list[tuple[str, str | None]] = [
        ("full_name", payload.primary_contact.full_name),
        *[("full_name", visitor.full_name) for visitor in payload.visitors],
        ("purpose_of_visit", visit_details["purpose_of_visit"]),
        # Blank normalized to `None` here specifically (unlike the other
        # entries in this list): "Expected Duration" is unconditionally
        # optional and no visitor-facing wizard collects it any more
        # (make-expected-duration-optional, see the `id_proof_required`/
        # `photo_required` note above) — a walk-in/staff client that still
        # submits `""` for it means "not answered," not "answered with an
        # invalid option," so it must skip the allow-list check the same
        # way an omitted value does.
        ("expected_duration", visit_details["expected_duration"] or None),
        ("additional_notes", payload.visit_details.additional_notes),
        *[("license_plate", vehicle.license_plate) for vehicle in payload.vehicles],
    ]
    for field_key, value in retypeable_field_values:
        if value is None:
            continue
        allowed_values = form_builder_validation.allowed_options_for_system_field(
            effective_form, field_key
        )
        if allowed_values is not None and value not in allowed_values:
            logger.warning(
                "registration_form_config_validation_failed",
                branch_id=str(branch_id),
                check="retypeable_system_field",
                reason="unknown_option",
                field=field_key,
                value=value,
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid value for '{field_key}': {value!r}",
            )

    # specs/invitations/spec.md (delta) "Invitation Creation Captures
    # Admin-Defined Custom Field Answers" — each admin-authored field's
    # answer is validated at the same scope its step's own fields are
    # already captured at (add-generic-custom-field-support/design.md
    # Decision 1/2).
    visitor_info_custom_fields = form_builder_validation.custom_fields_for_step(
        effective_form, "visitor_info"
    )
    vehicle_info_custom_fields = form_builder_validation.custom_fields_for_step(
        effective_form, "vehicle_info"
    )
    invitation_scope_custom_fields = form_builder_validation.custom_fields_for_invitation_scope(
        effective_form
    )

    # The primary contact's Visitor Info-step answers are sourced from the
    # invitation-level `customFields` array rather than a nested
    # `primaryContact.customFields` — there is exactly one primary contact
    # per invitation, so partitioning the flat, field-id-keyed map by which
    # step a field belongs to unambiguously recovers "the primary contact's
    # answers" without a separate nested array. Each `visitors[i]` entry
    # still answers Visitor Info fields through its own nested `customFields`
    # array (`VisitorSubmit.custom_field_values`), since a group registration
    # has more than one such answer set and a flat map can't distinguish
    # whose answer is whose.
    visitor_info_field_ids = {field["id"] for field in visitor_info_custom_fields}
    primary_contact_custom_field_values = {
        field_id: value
        for field_id, value in payload.custom_field_values.items()
        if field_id in visitor_info_field_ids
    }
    invitation_level_custom_field_values = {
        field_id: value
        for field_id, value in payload.custom_field_values.items()
        if field_id not in visitor_info_field_ids
    }

    def _validate_custom_fields(
        fields: list[dict[str, Any]],
        values: dict[str, Any],
        *,
        scope: str,
        skip_required: bool = False,
    ) -> None:
        try:
            form_builder_validation.validate_custom_field_values(
                fields, values, scope=scope, skip_required=skip_required
            )
        except HTTPException:
            logger.warning(
                "registration_form_config_validation_failed",
                branch_id=str(branch_id),
                check="custom_field",
                scope=scope,
            )
            raise

    # An admin-authored `file_upload` field on an ordinary (non-grouped)
    # step (add-inline-custom-field-file-upload) — a co-visitor "additional
    # document" field, say — can only be answered from a multipart file,
    # never a JSON value in `customFields`, same rule
    # `_group_field_file_id`/the group-instance loop below already applies
    # to a group's own `file_upload` field. Unlike a group (where only the
    # first `file_upload` field is read, since the group id alone can't
    # disambiguate which field a file belongs to), each of these fields has
    # its own multipart part name (`customFieldFiles[<fieldId>]` etc. — see
    # `router.py::create_invitation`), so every `file_upload` field at a
    # given scope is supported, not just the first. Referenced by field id
    # throughout (restructure-walkin-payload-by-field-id), never by key.
    visitor_info_file_ids = {
        field["id"] for field in visitor_info_custom_fields if field["fieldType"] == "file_upload"
    }
    vehicle_info_file_ids = {
        field["id"] for field in vehicle_info_custom_fields if field["fieldType"] == "file_upload"
    }
    invitation_scope_file_ids = {
        field["id"]
        for field in invitation_scope_custom_fields
        if field["fieldType"] == "file_upload"
    }

    def _reject_json_value_for_file_fields(
        values: dict[str, Any], file_ids: set[str], *, scope: str
    ) -> None:
        for field_id in file_ids:
            if values.get(field_id) is not None:
                logger.warning(
                    "registration_form_config_validation_failed",
                    branch_id=str(branch_id),
                    check="custom_field",
                    reason="file_field_value_supplied_inline",
                    field_id=field_id,
                    scope=scope,
                )
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"'{field_id}' for {scope} must be uploaded as a file, "
                        "not supplied as a value"
                    ),
                )

    _reject_json_value_for_file_fields(
        primary_contact_custom_field_values,
        visitor_info_file_ids,
        scope="the primary contact",
    )
    _validate_custom_fields(
        [f for f in visitor_info_custom_fields if f["id"] not in visitor_info_file_ids],
        primary_contact_custom_field_values,
        scope="the primary contact",
    )
    for index, visitor in enumerate(payload.visitors):
        _reject_json_value_for_file_fields(
            visitor.custom_field_values, visitor_info_file_ids, scope=f"visitor {index + 1}"
        )
        _validate_custom_fields(
            [f for f in visitor_info_custom_fields if f["id"] not in visitor_info_file_ids],
            visitor.custom_field_values,
            scope=f"visitor {index + 1}",
        )
    for index, vehicle in enumerate(payload.vehicles):
        _reject_json_value_for_file_fields(
            vehicle.custom_field_values, vehicle_info_file_ids, scope=f"vehicle {index + 1}"
        )
        _validate_custom_fields(
            [f for f in vehicle_info_custom_fields if f["id"] not in vehicle_info_file_ids],
            vehicle.custom_field_values,
            scope=f"vehicle {index + 1}",
        )
    _reject_json_value_for_file_fields(
        invitation_level_custom_field_values, invitation_scope_file_ids, scope="the invitation"
    )
    _validate_custom_fields(
        [f for f in invitation_scope_custom_fields if f["id"] not in invitation_scope_file_ids],
        invitation_level_custom_field_values,
        scope="the invitation",
    )

    # Presence/count validation only (fail fast, before any file I/O) — the
    # matching content-type validation and storage write happens later,
    # alongside the primary-contact/visitor ID-proof files, mirroring the
    # group-instance file upload's own two-phase split below.
    primary_contact_custom_field_file_contents = primary_contact_custom_field_file_contents or {}
    visitor_custom_field_file_contents = visitor_custom_field_file_contents or {}
    vehicle_custom_field_file_contents = vehicle_custom_field_file_contents or {}
    custom_field_file_contents = custom_field_file_contents or {}
    for field in visitor_info_custom_fields:
        field_id = field["id"]
        if field_id not in visitor_info_file_ids:
            continue
        label = field.get("label") or field_id
        primary_files = primary_contact_custom_field_file_contents.get(field_id, [])
        if len(primary_files) > 1:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Only one file may be uploaded for '{label}'",
            )
        if field["isRequired"] and not primary_files:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"'{label}' requires an uploaded file for the primary contact",
            )
        visitor_files = visitor_custom_field_file_contents.get(field_id, [])
        if field["isRequired"]:
            if len(visitor_files) != len(payload.visitors):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"'{label}' requires an uploaded file for every visitor",
                )
        elif len(visitor_files) > len(payload.visitors):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"More '{label}' files were uploaded than visitors listed",
            )
    for field in vehicle_info_custom_fields:
        field_id = field["id"]
        if field_id not in vehicle_info_file_ids:
            continue
        label = field.get("label") or field_id
        vehicle_files = vehicle_custom_field_file_contents.get(field_id, [])
        if field["isRequired"]:
            if len(vehicle_files) != len(payload.vehicles):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"'{label}' requires an uploaded file for every vehicle",
                )
        elif len(vehicle_files) > len(payload.vehicles):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"More '{label}' files were uploaded than vehicles listed",
            )
    for field in invitation_scope_custom_fields:
        field_id = field["id"]
        if field_id not in invitation_scope_file_ids:
            continue
        label = field.get("label") or field_id
        files = custom_field_file_contents.get(field_id, [])
        if len(files) > 1:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Only one file may be uploaded for '{label}'",
            )
        if field["isRequired"] and not files:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"'{label}' requires an uploaded file",
            )

    # specs/invitations/spec.md (delta) "An Admin-Defined Repeatable Group's
    # Answers Are Accepted as an Array of Per-Instance Values"
    # (add-repeatable-field-groups) — every admin-defined group's submitted
    # instance count must fall within its configured range, and each
    # instance's values must validate against that group's own fields.
    custom_groups = form_builder_validation.custom_groups_for_invitation_scope(effective_form)
    custom_groups_by_id = {group["id"]: group for group in custom_groups}
    unknown_group_ids = set(payload.group_values) - set(custom_groups_by_id)
    if unknown_group_ids:
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="group_id",
            reason="unknown_group_id",
            group_ids=sorted(unknown_group_ids),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown field group id(s): {', '.join(sorted(unknown_group_ids))}",
        )
    # specs/invitations/spec.md (delta) "A Hidden Custom Field Group's
    # Fields Are Not Required At Submission" (add-repeatable-field-groups)
    # — the values map a custom group's own `visibilityCondition` is
    # evaluated against: every invitation-scope locked field a group could
    # watch (Visit Details/Carried Items' own seeded fields), merged with
    # the invitation-level admin-authored answers a group's condition could
    # equally watch. `registration_type` is included so a group defined
    # directly on Visitor Info/Vehicle Info (e.g. an "Additional Visitors"
    # group replacing the fixed `visitors` list) can watch it too — the
    # same system field its own step's `is_field_required`/retyping checks
    # reference.
    #
    # `VisibilityCondition.field_key` (form-builder's own authoring-time
    # config — out of this change's scope, see design.md Non-Goals)
    # references a field by *key*, not id, so the invitation-level custom
    # field answers merged in here are re-keyed from `fieldId` back to
    # `key` for exactly this evaluation, without changing the id-keyed
    # representation used everywhere else (`payload.custom_field_values`).
    invitation_scope_fields_by_id = {f["id"]: f for f in invitation_scope_custom_fields}
    custom_field_values_by_key = {
        invitation_scope_fields_by_id[field_id]["key"]: value
        for field_id, value in payload.custom_field_values.items()
        if field_id in invitation_scope_fields_by_id
    }
    invitation_scope_values: dict[str, Any] = {
        "registration_type": payload.registration_type,
        "purpose_of_visit": visit_details["purpose_of_visit"],
        "expected_duration": visit_details["expected_duration"],
        "department_to_visit": visit_details["department_to_visit"],
        "additional_notes": payload.visit_details.additional_notes,
        "preferred_visit_date": str(payload.visit_details.preferred_visit_date),
        "preferred_visit_time": str(payload.visit_details.preferred_visit_time),
        "items": payload.carried_items.items,
        "item_description": payload.carried_items.item_description,
        **custom_field_values_by_key,
    }

    # Reused below (`group_field_file_contents` validation/storage) so that
    # phase doesn't have to recompute a group's visibility a second time.
    group_visibility: dict[str, bool] = {}
    for group_id, group in custom_groups_by_id.items():
        instances = payload.group_values.get(group_id, [])
        is_visible = form_builder_validation.is_group_visible(group, invitation_scope_values)
        group_visibility[group_id] = is_visible
        try:
            form_builder_validation.validate_group_instance_count(
                group,
                len(instances),
                scope=f"Field group '{group['name']}'",
                skip_minimum=not is_visible,
            )
        except HTTPException:
            logger.warning(
                "registration_form_config_validation_failed",
                branch_id=str(branch_id),
                check="group_instance_count",
                reason="custom_group_count_out_of_range",
                group_id=group_id,
                count=len(instances),
            )
            raise
        file_field_id = _group_field_file_id(group)
        # A `file_upload` field's answer can only come from
        # `group_field_file_contents` below — never from the JSON instance
        # dict, which has no way to carry raw file bytes — so it's excluded
        # from the generic (JSON-value) validation pass here, and any value
        # a caller supplied for it anyway is rejected outright rather than
        # silently ignored (add-group-field-file-upload).
        validated_fields = (
            group["fields"]
            if file_field_id is None
            else [field for field in group["fields"] if field["id"] != file_field_id]
        )
        for index, instance in enumerate(instances):
            if file_field_id is not None and instance.get(file_field_id) is not None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"'{file_field_id}' in '{group['name']}' instance {index + 1} must be "
                        "uploaded as a file, not supplied as a value"
                    ),
                )
            _validate_custom_fields(
                validated_fields,
                instance,
                scope=f"'{group['name']}' instance {index + 1}",
                skip_required=not is_visible,
            )

    repo = InvitationRepository(tenant_db)

    # specs/invitations/spec.md (delta) "A Returning Primary Contact's Full
    # Name Is Locked to Their Prior Invitation" / "...Matched by Phone Has
    # Their Email Carried Forward". Email is the primary identity key; phone
    # is only ever consulted when no email was submitted this visit, so a
    # genuinely new (non-matching) email is never rescued by a phone match
    # against a different prior invitation
    # (dedupe-repeat-visitor-registrations/design.md Decision 5).
    returning_contact: Invitation | None = None
    if payload.primary_contact.email is not None:
        returning_contact = await repo.get_latest_by_primary_contact_email(
            payload.primary_contact.email
        )
    elif payload.primary_contact.phone is not None:
        returning_contact = await repo.get_latest_by_primary_contact_phone(
            payload.primary_contact.phone
        )
    primary_contact_full_name = (
        returning_contact.primary_contact_full_name
        if returning_contact is not None
        else payload.primary_contact.full_name
    )
    primary_contact_email = (
        returning_contact.primary_contact_email
        if returning_contact is not None
        else payload.primary_contact.email
    )

    tracking_id = await _generate_unique_tracking_id(repo)
    now = datetime.now(UTC)
    expires_at = _end_of_visit_day_utc(payload.visit_details.preferred_visit_date, tenant)
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

    # Validate every present file before persisting any of them (spec.md
    # "Each Visitor Has at Least One Reachable Contact and an ID Proof") —
    # otherwise a later visitor's invalid file would abort the request
    # after an earlier visitor's file was already written to storage.
    # Photos, and (when not required) ID-proof files, may be entirely
    # absent for a given visitor: `None` in, `None` out, skipping
    # validation and storage for that one.
    max_photo_size = settings.invitation_max_photo_size_bytes
    primary_content_type = (
        _validate_id_proof(primary_contact_id_proof_content, max_size)
        if primary_contact_id_proof_content is not None
        else None
    )
    visitor_content_types = [
        _validate_id_proof(content, max_size) if content is not None else None
        for content in visitor_id_proof_contents
    ]
    primary_photo_content_type = (
        _validate_photo(primary_contact_photo_content, max_photo_size)
        if primary_contact_photo_content is not None
        else None
    )
    visitor_photo_content_types = [
        _validate_photo(content, max_photo_size) for content in visitor_photo_contents
    ]

    # Group-instance file uploads (add-group-field-file-upload): validated
    # up front, same "fail before any storage write" ordering as the block
    # above — `group_field_content_types[group_key][index]` pairs with
    # `group_field_file_contents[group_key][index]` for the storage phase
    # below. A group with no `file_upload` field, or with none of its
    # instances' files supplied, is skipped entirely.
    group_field_file_contents = group_field_file_contents or {}
    group_field_ids: dict[str, str] = {}
    group_field_content_types: dict[str, list[str]] = {}
    for group_id, group in custom_groups_by_id.items():
        file_field_id = _group_field_file_id(group)
        if file_field_id is None:
            continue
        group_field_ids[group_id] = file_field_id
        instances = payload.group_values.get(group_id, [])
        files = group_field_file_contents.get(group_id, [])
        field = next(f for f in group["fields"] if f["id"] == file_field_id)
        is_required = bool(field["isRequired"]) and group_visibility[group_id]
        if is_required and len(files) != len(instances):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Field group '{group['name']}' requires an uploaded file for every instance"
                ),
            )
        if not is_required and len(files) > len(instances):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"More files were uploaded than instances of '{group['name']}'",
            )
        group_field_content_types[group_id] = [_validate_id_proof(f, max_size) for f in files]

    primary_key = (
        await storage_save(
            tenant.id,
            "invitations/id-proof",
            primary_contact_id_proof_content,
            primary_content_type,
        )
        if primary_contact_id_proof_content is not None and primary_content_type is not None
        else None
    )
    primary_photo_key = (
        await storage_save(
            tenant.id,
            "invitations/photos",
            primary_contact_photo_content,
            primary_photo_content_type,
        )
        if primary_contact_photo_content is not None and primary_photo_content_type is not None
        else None
    )
    # `payload.group_values` is a plain (uncached) property that rebuilds a
    # brand-new dict from `payload.groups` on every access — mutating one
    # access's result (as this loop used to) is silently discarded once
    # `group_field_values` below re-reads the property fresh. So the storage
    # keys are collected separately here and merged in at persistence time,
    # the same "validate/store, then merge back" shape as
    # `custom_field_storage`/`primary_contact_custom_field_storage`.
    group_field_storage: dict[str, dict[int, dict[str, str]]] = {}
    for group_id, file_field_id in group_field_ids.items():
        files = group_field_file_contents.get(group_id, [])
        content_types = group_field_content_types[group_id]
        for index, content in enumerate(files):
            storage_key = await storage_save(
                tenant.id, "invitations/group-files", content, content_types[index]
            )
            group_field_storage.setdefault(group_id, {}).setdefault(index, {})[file_field_id] = (
                storage_key
            )

    # Inline (non-grouped) custom-field file uploads
    # (add-inline-custom-field-file-upload): validated for presence/count
    # above, so every entry reaching this loop is safe to store — same
    # "content-type validate, then store, then write the storage key back"
    # shape as the group loop above, keyed by field key rather than group
    # key. Storage key, never the raw upload, lands in the persisted
    # `customFieldValues`/`primaryContactCustomFieldValues` map, same as
    # `groupFieldValues`'s own `file_upload` field — all three are resolved
    # to a signed URL on read by `invitations/router.py`'s
    # `_resolve_custom_field_file_values` (add-generic-custom-field-file-
    # url-resolution), keyed off `InvitationDetailFormContext`'s file-field
    # sets below.
    primary_contact_custom_field_storage: dict[str, str] = {}
    for key, files in primary_contact_custom_field_file_contents.items():
        if not files:
            continue
        content_type = _validate_id_proof(files[0], max_size)
        primary_contact_custom_field_storage[key] = await storage_save(
            tenant.id, "invitations/custom-fields", files[0], content_type
        )
    custom_field_storage: dict[str, str] = {}
    for key, files in custom_field_file_contents.items():
        if not files:
            continue
        content_type = _validate_id_proof(files[0], max_size)
        custom_field_storage[key] = await storage_save(
            tenant.id, "invitations/custom-fields", files[0], content_type
        )
    visitor_custom_field_storage: dict[str, list[str]] = {
        key: [
            await storage_save(
                tenant.id,
                "invitations/custom-fields",
                content,
                _validate_id_proof(content, max_size),
            )
            for content in files
        ]
        for key, files in visitor_custom_field_file_contents.items()
    }
    vehicle_custom_field_storage: dict[str, list[str]] = {
        key: [
            await storage_save(
                tenant.id,
                "invitations/custom-fields",
                content,
                _validate_id_proof(content, max_size),
            )
            for content in files
        ]
        for key, files in vehicle_custom_field_file_contents.items()
    }

    if source == RegistrationSource.visitor_walk_in and payload.branch_id is not None:
        # A kiosk's device branch is only the default; the visitor's own
        # branch selection wins, provided it is an active branch.
        branch_id = await _resolve_active_branch(tenant_db, payload.branch_id)
    building_id = await _resolve_building(tenant_db, payload.building_id, branch_id)
    if visit_details["department_id"] is None and visit_details["department_to_visit"]:
        # Free-text department with no `departmentId`: link it to the branch's
        # department of the same name so the detail view returns the record.
        visit_details["department_id"] = await _match_department_by_name(
            tenant_db, branch_id, visit_details["department_to_visit"]
        )

    invitation = Invitation(
        id=uuid.uuid4(),
        branch_id=branch_id,
        building_id=building_id,
        created_by_user_id=created_by_user_id,
        source=source.value,
        registration_type=payload.registration_type.value,
        status=initial_status,
        visitor_category_id=visitor_category_id,
        tracking_id=tracking_id,
        expires_at=expires_at,
        submitted_at=now,
        approved_at=approved_at,
        primary_contact_full_name=primary_contact_full_name,
        primary_contact_email=primary_contact_email,
        primary_contact_phone=payload.primary_contact.phone,
        primary_contact_preferred_contact_method=(
            payload.primary_contact.preferred_contact_method.value
        ),
        primary_contact_id_proof_type=payload.primary_contact.id_proof_type,
        primary_contact_id_proof_storage_key=primary_key,
        primary_contact_photo_storage_key=primary_photo_key,
        primary_contact_custom_field_values={
            **primary_contact_custom_field_values,
            **primary_contact_custom_field_storage,
        },
        purpose_of_visit=visit_details["purpose_of_visit"],
        # Never client-supplied at creation anymore — see
        # `_resolve_visit_detail_ids`. Established later, exclusively by
        # delegating the ownership step (`approvals/service.py::delegate_step`).
        host_name_or_email=None,
        preferred_visit_date=payload.visit_details.preferred_visit_date,
        preferred_visit_time=payload.visit_details.preferred_visit_time,
        expected_duration=visit_details["expected_duration"],
        department_to_visit=visit_details["department_to_visit"],
        additional_notes=payload.visit_details.additional_notes,
        purpose_id=visit_details["purpose_id"],
        host_id=None,
        duration_id=visit_details["duration_id"],
        department_id=visit_details["department_id"],
        carried_items=list(payload.carried_items.items),
        carried_items_description=payload.carried_items.item_description,
        consents=dict(consents_dict),
        consent_recorded_at=now,
        custom_field_values={**invitation_level_custom_field_values, **custom_field_storage},
        group_field_values={
            group_id: [
                {**instance, **group_field_storage.get(group_id, {}).get(index, {})}
                for index, instance in enumerate(instances)
            ]
            for group_id, instances in payload.group_values.items()
        },
    )
    tenant_db.add(invitation)

    def _merge_indexed_file_storage(
        base: dict[str, Any], storage: dict[str, list[str]], index: int
    ) -> dict[str, Any]:
        """`storage` (`visitor_custom_field_storage`/`vehicle_custom_field_storage`
        above) is order-matched per field key, same convention as
        `visitor_id_proof_contents` — may be shorter than the visitor/vehicle
        list for a field with no file at this index."""
        merged = dict(base)
        for key, values in storage.items():
            if index < len(values):
                merged[key] = values[index]
        return merged

    visitor_rows = [
        InvitationVisitor(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            full_name=visitor.full_name,
            email=visitor.email,
            phone=visitor.phone,
            id_proof_type=visitor.id_proof_type,
            # ID-proof files are order-matched but, when the branch has
            # deactivated ID proof, may be entirely absent or shorter than
            # the visitor list — same "beyond the supplied count simply has
            # none" posture the photo handling below already had.
            id_proof_storage_key=(
                await storage_save(
                    tenant.id,
                    "invitations/id-proof",
                    visitor_id_proof_contents[idx],
                    visitor_content_types[idx],
                )
                if idx < len(visitor_id_proof_contents)
                and visitor_id_proof_contents[idx] is not None
                else None
            ),
            # Photos are order-matched but may be shorter than the visitor
            # list — a visitor beyond the supplied photo count simply has
            # none.
            photo_storage_key=(
                await storage_save(
                    tenant.id,
                    "invitations/photos",
                    visitor_photo_contents[idx],
                    visitor_photo_content_types[idx],
                )
                if idx < len(visitor_photo_contents)
                else None
            ),
            custom_field_values=_merge_indexed_file_storage(
                visitor.custom_field_values, visitor_custom_field_storage, idx
            ),
        )
        for idx, visitor in enumerate(payload.visitors)
    ]
    vehicle_rows = [
        InvitationVehicle(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            vehicle_type=vehicle.vehicle_type,
            license_plate=vehicle.license_plate,
            make_model=vehicle.make_model,
            color=vehicle.color,
            custom_field_values=_merge_indexed_file_storage(
                vehicle.custom_field_values, vehicle_custom_field_storage, idx
            ),
        )
        for idx, vehicle in enumerate(payload.vehicles)
    ]
    repo.add_visitors(visitor_rows)
    repo.add_vehicles(vehicle_rows)

    # Snapshot the category's active workflow rules into ordered steps,
    # exactly as configured — see `_build_approval_steps` for when a
    # synthetic ownership step still gets added (only when the category has
    # no active rules at all) — only for a `submitted` (not auto-approved)
    # invitation, and only once, in the same transaction as the `Invitation`
    # insert above (design.md Decision 1). Every submitted invitation still
    # gets at least one step, regardless of whether the category has any
    # active rules.
    if not auto_approved:
        rules = await ApprovalWorkflowRuleRepository(tenant_db).list_active_for_category(
            visitor_category_id
        )
        owning_role = await get_default_host_role(tenant_db)
        InvitationApprovalStepRepository(tenant_db).add_steps(
            _build_approval_steps(
                rules, invitation_id=invitation.id, owning_role_id=owning_role.id, now=now
            )
        )

    # Generated in the same transaction as the invitation itself when it's
    # already `approved` (design.md "Token generation moves to approval
    # time, persisted") — never for a `submitted` invitation, matching
    # "a QR code is never included until the invitation is approved".
    qr_code = await _issue_qr_code(tenant_db, invitation, tenant=tenant) if auto_approved else None

    await tenant_db.commit()

    created = await repo.get_with_children(invitation.id)
    assert created is not None  # just committed; guaranteed to exist

    if auto_approved:
        assert qr_code is not None
        tasks.send_approval_notification.delay(
            request_id=_current_request_id(),
            tenant_schema=tenant.schema_name,
            invitation_id=str(invitation.id),
            qr_token=qr_code.qr_token,
        )
    else:
        tasks.send_tracking_notification.delay(
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
            if current_step.approver_role_id is not None:
                tasks.send_submission_role_email_notification.delay(
                    request_id=_current_request_id(),
                    tenant_schema=tenant.schema_name,
                    invitation_id=str(invitation.id),
                    role_id=str(current_step.approver_role_id),
                    branch_id=str(invitation.branch_id),
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
    expires_at = (
        _end_of_visit_day_utc(invitation.preferred_visit_date, tenant)
        if invitation.preferred_visit_date is not None
        else None
    )
    updated = await InvitationRepository(tenant_db).approve_if_submitted(
        invitation.id, expires_at=expires_at
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not awaiting approval")
    qr_code = await _issue_qr_code(tenant_db, updated, tenant=tenant)
    await tenant_db.commit()
    tasks.send_approval_notification.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
        qr_token=qr_code.qr_token,
    )
    await _notify_host(tenant, updated, push_notifications.approved)
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


async def get_invitation_location(
    tenant_db: AsyncSession, invitation: Invitation
) -> tuple[Branch, Department | None, Building | None]:
    """Resolves `invitation`'s branch and, when it has a `department_id` on
    file, that department's building — backs the `branch`/`building`/
    `department` fields on `InvitationDetailOut` and `InvitationQrCheckInOut`
    (enrich-invitation-checkin-and-detail-views/design.md Decision 5).
    """
    return await InvitationRepository(tenant_db).get_location(
        branch_id=invitation.branch_id,
        department_id=invitation.department_id,
        building_id=invitation.building_id,
    )


@dataclass(frozen=True)
class InvitationDetailFormContext:
    """Per-branch form-builder lookups `invitations/router.py`'s detail-view
    serializers need to render `GET /invitations/{id}` (add-generic-custom-
    field-file-url-resolution): `visitor_info_groups` (keyed by group id —
    backs `_group_collected_visitor_detail_outs`'s visitor synthesis), plus
    which `file_upload`-typed field ids appear in each of `customFields`/
    `primaryContactCustomFields`/a vehicle's `customFields`/a `groups`
    instance (restructure-walkin-payload-by-field-id — referenced by id,
    never by key), so those readers know which raw storage keys need
    resolving to a signed URL rather than being serialized straight from
    the ORM (see the note on `service.py::create_invitation`'s
    `customFieldValues`/`primaryContactCustomFieldValues`/`groupFieldValues`
    storage — "no reader resolves it to a signed URL yet").
    """

    visitor_info_groups: dict[str, dict[str, Any]]
    invitation_scope_file_ids: set[str]
    visitor_info_file_ids: set[str]
    vehicle_info_file_ids: set[str]
    group_file_ids: dict[str, set[str]]


async def get_invitation_detail_form_context(
    tenant_db: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> InvitationDetailFormContext:
    """Resolves `branch_id`'s effective form once and derives every
    form-shape lookup the detail view's serializers need, rather than each
    one separately re-resolving it (still a Redis round-trip per call even
    though `resolve_effective_form` itself is cache-backed)."""
    redis = await get_redis()
    effective_form = await form_builder_service.resolve_effective_form(
        tenant_db, redis, tenant_id=tenant.id, branch_id=branch_id
    )
    visitor_info_file_ids = {
        field["id"]
        for field in form_builder_validation.custom_fields_for_step(effective_form, "visitor_info")
        if field["fieldType"] == "file_upload"
    }
    vehicle_info_file_ids = {
        field["id"]
        for field in form_builder_validation.custom_fields_for_step(effective_form, "vehicle_info")
        if field["fieldType"] == "file_upload"
    }
    invitation_scope_file_ids = {
        field["id"]
        for field in form_builder_validation.custom_fields_for_invitation_scope(effective_form)
        if field["fieldType"] == "file_upload"
    }
    group_file_ids = {
        group["id"]: {
            field["id"] for field in group["fields"] if field["fieldType"] == "file_upload"
        }
        for group in form_builder_validation.custom_groups_for_invitation_scope(effective_form)
    }
    return InvitationDetailFormContext(
        visitor_info_groups=form_builder_validation.custom_groups_for_step(
            effective_form, "visitor_info"
        ),
        invitation_scope_file_ids=invitation_scope_file_ids,
        visitor_info_file_ids=visitor_info_file_ids,
        vehicle_info_file_ids=vehicle_info_file_ids,
        group_file_ids=group_file_ids,
    )


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
    await _notify_host(tenant, updated, push_notifications.denied)
    return updated


async def _perform_check_in(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    actor_user_id: uuid.UUID | None,
    tenant: Tenant,
) -> tuple[Invitation, bool]:
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

    Returns `(invitation, changed)` — `changed` is `False` for the
    idempotent-no-op case below, so the caller (the router's audit-log
    background task) can skip writing an audit entry for a call that
    performed no actual transition.

    A repeat call while already `checked_in` is treated as an idempotent
    no-op success (returns the invitation unchanged) rather than a 409 — no
    second `UPDATE`, no re-stamped `checkedInAt`, no duplicate host
    notification or audit entry, since nothing about the invitation's state
    actually changed. This is deliberately checked before the watchlist gate
    below: a flag added after a visitor already entered must not turn their
    repeat/duplicate check-in call into an error.
    """
    if invitation.check_in_status == "checked_in":
        return invitation, False
    if invitation.watchlist_flagged:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation is watchlist-flagged; override required before check-in",
        )
    if invitation.status not in ("approved", "checked_in", "checked_out"):
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
    await _notify_host(tenant, updated, push_notifications.checked_in)
    return updated, True


async def check_in_invitation_by_tracking_id(
    tenant_db: AsyncSession, tracking_id: str, *, tenant: Tenant
) -> tuple[Invitation, bool]:
    """`PATCH /api/v2/invitations/{trackingId}/check-in` — public,
    unauthenticated, tracking-ID-keyed (spec.md "An Approved Invitation Can
    Be Publicly Checked In By Tracking ID"). No authenticated caller, so no
    branch authorization check and no human actor recorded.
    """
    invitation = await InvitationRepository(tenant_db).get_by_tracking_id(tracking_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return await _perform_check_in(tenant_db, invitation, actor_user_id=None, tenant=tenant)


async def _get_invitation_by_qr_token_or_400(
    tenant_db: AsyncSession, token: str, *, tenant: Tenant
) -> Invitation:
    """Shared by both QR endpoints — an invalid/tampered token and an
    invitation that doesn't exist are folded into the same rejection
    (`invalid token`) so neither response reveals which failure actually
    occurred.
    """
    invitation_id = decrypt_invitation_token(token)
    invitation = (
        await InvitationRepository(tenant_db).get_with_children(invitation_id)
        if invitation_id
        else None
    )
    if invitation is None:
        logger.warning("qr_check_in_invalid_token", tenant_id=str(tenant.id))
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Verification failed — invalid token"
        )
    return invitation


async def check_in_by_qr_token(
    tenant_db: AsyncSession, token: str, *, tenant: Tenant
) -> tuple[Invitation, str, bool]:
    """`PATCH /api/v2/invitations/qr/{token}/check-in` — public,
    unauthenticated, driven by the encrypted QR token rather than the
    tracking ID (spec.md "QR Check-In Token Is Encrypted and
    Tamper-Evident" / "QR Check-In Endpoint Transitions an Eligible
    Visitor to Checked-In"). Entry only: `unused`/`checked_out` ->
    `checked_in`. A repeat scan while already `checked_in` is an idempotent
    no-op success (same "Verification passed" message, unchanged data) —
    not a 409 — mirroring `_perform_check_in`'s identical rule; the caller
    still uses `check_out_by_qr_token` to actually exit. Also rejects a scan
    attempted before the invitation's `preferred_visit_date` (date-only,
    tenant-local calendar day) with `425 Too Early`, distinct from the
    `410 Gone` used for expiry — see qr-checkin-scheduling-photo-email/
    design.md Decisions 1-2. An invitation with no `preferred_visit_date`
    set skips that check entirely.

    Returns `(invitation, message, changed)` — `message` is the
    human-readable outcome the caller surfaces directly ("Verification
    passed"), matching the confirmed frontend spec's response contract;
    `changed` is `False` for the idempotent-no-op case below, so the
    caller (the router's audit-log background task) can skip writing an
    audit entry for a scan that performed no actual transition.
    """
    invitation = await _get_invitation_by_qr_token_or_400(tenant_db, token, tenant=tenant)

    if invitation.check_in_status == "checked_in":
        return invitation, "Verification passed", False
    if invitation.status not in ("approved", "checked_in", "checked_out"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Verification failed — invitation not approved"
        )
    if invitation.watchlist_flagged:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation is watchlist-flagged; override required before check-in",
        )
    today_local = datetime.now(UTC).astimezone(_resolve_tenant_timezone(tenant)).date()
    if (
        invitation.preferred_visit_date is not None
        and invitation.preferred_visit_date > today_local
    ):
        raise HTTPException(
            status.HTTP_425_TOO_EARLY,
            detail="Verification failed — visit window not yet open",
        )
    if invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status.HTTP_410_GONE, detail="Verification failed — visit window expired"
        )
    updated = await InvitationRepository(tenant_db).check_in_by_qr_if_eligible(
        invitation.id, today_local=today_local
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is no longer eligible for check-in"
        )

    await tenant_db.commit()
    await _notify_host(tenant, updated, push_notifications.checked_in)
    return updated, "Verification passed", True


async def check_out_by_qr_token(
    tenant_db: AsyncSession, token: str, *, tenant: Tenant
) -> tuple[Invitation, str]:
    """`PATCH /api/v2/invitations/qr/{token}/check-out` — public,
    unauthenticated exit counterpart of `check_in_by_qr_token` (spec.md "QR
    Check-Out Endpoint Transitions a Checked-In Visitor to Checked-Out").
    Exit only: `checked_in` -> `checked_out`, never subject to the expiry
    check (a visit that legitimately continues past `expires_at` can still
    be closed out). Rejects with 409 when the invitation isn't currently
    `checked_in`.
    """
    invitation = await _get_invitation_by_qr_token_or_400(tenant_db, token, tenant=tenant)

    if invitation.check_in_status != "checked_in":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not currently checked in"
        )
    updated = await InvitationRepository(tenant_db).check_out_by_qr_if_eligible(invitation.id)
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is no longer eligible for check-out"
        )

    await tenant_db.commit()
    await _notify_host(tenant, updated, push_notifications.checked_out)
    return updated, "Checked out successfully"


async def check_out_invitation(
    tenant_db: AsyncSession, invitation: Invitation, *, user_id: uuid.UUID, tenant: Tenant
) -> Invitation:
    updated = await InvitationRepository(tenant_db).check_out_if_checked_in(
        invitation.id, user_id=user_id
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not checked in")
    await tenant_db.commit()
    await _notify_host(tenant, updated, push_notifications.checked_out)
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
    expires_at = (
        _end_of_visit_day_utc(preferred_visit_date, tenant)
        if invitation.status == "approved"
        else None
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
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    await _notify_host(tenant, updated, push_notifications.rescheduled)
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
    if invitation.status not in _RESCHEDULABLE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation can no longer be edited")
    if payload.poc_user_id is not None or payload.poc_role_id is not None:
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
    if not changes:
        return invitation
    updated = await InvitationRepository(tenant_db).edit_if_eligible(invitation.id, **changes)
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation can no longer be edited")
    await tenant_db.commit()
    tasks.send_edit_notification.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(updated.id),
    )
    await _notify_host(tenant, updated, push_notifications.edited)
    if "poc_user_id" in changes or "poc_role_id" in changes:
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
                request_id=_current_request_id(),
                tenant_schema=tenant.schema_name,
                invitation_id=str(updated.id),
                poc_id=str(updated.poc_user_id),
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
    qr_code = await _issue_qr_code(tenant_db, invitation, tenant=tenant)
    png = await badge.render_badge_png(
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        expires_at=invitation.expires_at,
        qr_token=qr_code.qr_token,
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
    qr_code = await _issue_qr_code(tenant_db, invitation, tenant=tenant)
    png = await badge.render_badge_png(
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        expires_at=invitation.expires_at,
        qr_token=qr_code.qr_token,
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

    Every caller invokes this as a trailing read *after* its own mutation
    has already committed — role-based-invitation-workflow made this read
    path reachable for every submitted invitation (previously only
    workflow-backed ones), which surfaced a latent issue: a plain `SELECT`
    still opens an implicit transaction, and nothing after this point
    commits it, leaving the caller's session `idle in transaction` for the
    rest of a test (or an unusually long-lived request). Committing here —
    a pure read, so there's nothing to lose by doing so — closes that
    transaction out immediately rather than leaving it open until whatever
    eventually closes the session.
    """
    if invitation.status != "submitted":
        return None
    repo = InvitationApprovalStepRepository(tenant_db)
    current = await repo.get_current_pending(invitation.id)
    if current is None:
        return None
    total_steps = await repo.count_for_invitation(invitation.id)
    await tenant_db.commit()
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
    default_host_role_id: uuid.UUID | None = None,
    status: str | None,
    registration_type: str | None,
    source: str | None,
    search: str | None,
    page: int,
    page_size: int,
    sort_by: InvitationSortableField,
    sort_order: SortOrder,
) -> tuple[list[Invitation], int]:
    return await InvitationRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        relevant_to_user_id=relevant_to_user_id,
        default_host_role_id=default_host_role_id,
        status=status,
        registration_type=registration_type,
        source=source,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def is_invitation_relevant_to(
    tenant_db: AsyncSession,
    invitation_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    default_host_role_id: uuid.UUID,
) -> bool:
    return await InvitationRepository(tenant_db).is_relevant_to(
        invitation_id, user_id=user_id, default_host_role_id=default_host_role_id
    )


async def get_prefill_by_email(
    tenant_db: AsyncSession, email: str, branch_scope: BranchScope, user: User
) -> InvitationLookupPrefillOut | None:
    """Backs `GET /invitations/lookup-by-email`
    (`add-invitation-lookup-by-email/proposal.md`) — `None` on no match is
    the normal, expected case, not an error (spec.md "No Matching
    Invitation Returns Null Data, Not an Error"). `photo_url` is resolved
    unconditionally; `id_proof_url` only when `user` holds `documents:view`
    at the matched invitation's branch — same split
    `router.py::_to_invitation_detail_out` uses for the staff detail view
    (design.md "photoUrl unconditional, idProofUrl gated...")."""
    invitation = await InvitationRepository(tenant_db).get_latest_for_prefill_by_email(
        email, branch_scope
    )
    if invitation is None:
        return None
    include_documents = user.has_permission("documents:view", invitation.branch_id)
    photo_key = invitation.primary_contact_photo_storage_key
    id_proof_key = invitation.primary_contact_id_proof_storage_key
    return InvitationLookupPrefillOut(
        full_name=invitation.primary_contact_full_name,
        phone=invitation.primary_contact_phone,
        preferred_contact_method=invitation.primary_contact_preferred_contact_method,
        visitor_category_id=invitation.visitor_category_id,
        id_proof_type=invitation.primary_contact_id_proof_type,
        photo_url=await storage_url_for(photo_key) if photo_key is not None else None,
        id_proof_url=(
            await storage_url_for(id_proof_key)
            if include_documents and id_proof_key is not None
            else None
        ),
    )


async def email_qr_png(schema_name: str, invitation_id: uuid.UUID) -> bytes | None:
    """The check-in QR a confirmation/reschedule email references by URL
    (serve-email-images-by-url-and-complete-contact design.md Decision 1),
    rendered from the token persisted at approval — the same bytes the
    email used to embed. `None` when the invitation or its QR row doesn't
    exist. The caller has already verified the URL signature; the schema
    comes from the signed tenant id, never the raw request.
    """
    async with tenant_session_scope(schema_name) as session:
        repository = InvitationRepository(session)
        if await repository.get(invitation_id) is None:
            return None
        qr_code = await repository.get_qr_code(invitation_id)
    if qr_code is None:
        return None
    return await generate_qr_png(qr_code.qr_token)
