"""Creating an invitation: payload validation against the effective form,
location resolution, uploads, approval steps and the post-commit notices.
Split out of `service.py`, which re-exports every name.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.core.config import settings
from vmss_api.core.logging import current_request_id, logger
from vmss_api.core.redis import get_redis
from vmss_api.core.storage import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    validate_image_only,
    validate_upload,
)
from vmss_api.core.storage import save as storage_save
from vmss_api.form_builder import service as form_builder_service
from vmss_api.form_builder import validation as form_builder_validation
from vmss_api.invitations import push_notifications, tasks
from vmss_api.invitations.common import (
    _end_of_visit_day_utc,
    _issue_checkin_code,
    _issue_qr_code,
    _match_department_by_name,
    _resolve_building,
    _unique_code,
    _visit_timezone,
)
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.invitations.repository import (
    InvitationRepository,
)
from vmss_api.invitations.schemas import (
    InvitationCreate,
    RegistrationSource,
    RegistrationType,
    VisitDetailsSubmit,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.repository import (
    BranchRepository,
    CompanyRepository,
    DepartmentRepository,
)
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
    return await _unique_code(
        lambda: "INV-" + secrets.token_hex(4).upper(),
        repo.get_by_tracking_id,
        attempts=5,
        what="invitation tracking id",
    )


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
    if not await BranchRepository(tenant_db).is_active(branch_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown or inactive branch"
        )
    return branch_id


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


@dataclass
class _UploadContentTypes:
    """Sniffed content types, validated before any file is stored."""

    primary_id_proof: str | None
    visitor_id_proofs: list[str | None]
    primary_photo: str | None
    visitor_photos: list[str]
    # Group id -> that group's `file_upload` field id, and the per-instance
    # content types of its files.
    group_file_field_ids: dict[str, str]
    group_files: dict[str, list[str]]


@dataclass
class _StoredUploads:
    """Storage keys for everything `_persist_uploads` wrote."""

    primary_id_proof: str | None
    primary_photo: str | None
    visitor_id_proofs: list[str | None]
    visitor_photos: list[str | None]
    group_fields: dict[str, dict[int, dict[str, str]]]
    primary_contact_custom_fields: dict[str, str]
    custom_fields: dict[str, str]
    visitor_custom_fields: dict[str, list[str]]
    vehicle_custom_fields: dict[str, list[str]]


def _validate_uploads(
    payload: InvitationCreate,
    *,
    custom_groups_by_id: dict[str, dict[str, Any]],
    group_visibility: dict[str, bool],
    primary_contact_id_proof_content: bytes | None,
    visitor_id_proof_contents: list[bytes],
    primary_contact_photo_content: bytes | None,
    visitor_photo_contents: list[bytes],
    group_field_file_contents: dict[str, list[bytes]],
) -> _UploadContentTypes:
    """Validates every present file before persisting any of them (spec.md
    "Each Visitor Has at Least One Reachable Contact and an ID Proof") —
    otherwise a later visitor's invalid file would abort the request after
    an earlier visitor's file was already written to storage. Photos, and
    (when not required) ID-proof files, may be entirely absent for a given
    visitor: `None` in, `None` out, skipping validation and storage for
    that one.
    """
    max_size = settings.invitation_max_upload_size_bytes
    max_photo_size = settings.invitation_max_photo_size_bytes
    primary_content_type = (
        _validate_id_proof(primary_contact_id_proof_content, max_size)
        if primary_contact_id_proof_content is not None
        else None
    )
    visitor_content_types: list[str | None] = [
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
    # `group_field_file_contents[group_key][index]` for the storage phase.
    # A group with no `file_upload` field, or with none of its instances'
    # files supplied, is skipped entirely.
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

    return _UploadContentTypes(
        primary_id_proof=primary_content_type,
        visitor_id_proofs=visitor_content_types,
        primary_photo=primary_photo_content_type,
        visitor_photos=visitor_photo_content_types,
        group_file_field_ids=group_field_ids,
        group_files=group_field_content_types,
    )


async def _persist_uploads(
    tenant: Tenant,
    content_types: _UploadContentTypes,
    *,
    primary_contact_id_proof_content: bytes | None,
    visitor_id_proof_contents: list[bytes],
    primary_contact_photo_content: bytes | None,
    visitor_photo_contents: list[bytes],
    group_field_file_contents: dict[str, list[bytes]],
    primary_contact_custom_field_file_contents: dict[str, list[bytes]],
    custom_field_file_contents: dict[str, list[bytes]],
    visitor_custom_field_file_contents: dict[str, list[bytes]],
    vehicle_custom_field_file_contents: dict[str, list[bytes]],
    visitor_count: int,
) -> _StoredUploads:
    """Writes every upload, in the order the inline code always did, and
    returns the storage keys. Only called once `_validate_uploads` and the
    location checks have passed."""
    max_size = settings.invitation_max_upload_size_bytes
    primary_key = (
        await storage_save(
            tenant.id,
            "invitations/id-proof",
            primary_contact_id_proof_content,
            content_types.primary_id_proof,
        )
        if primary_contact_id_proof_content is not None
        and content_types.primary_id_proof is not None
        else None
    )
    primary_photo_key = (
        await storage_save(
            tenant.id,
            "invitations/photos",
            primary_contact_photo_content,
            content_types.primary_photo,
        )
        if primary_contact_photo_content is not None and content_types.primary_photo is not None
        else None
    )
    # `payload.group_values` is a plain (uncached) property that rebuilds a
    # brand-new dict from `payload.groups` on every access — mutating one
    # access's result is silently discarded once `group_field_values` re-reads
    # the property fresh. So the storage keys are collected separately here
    # and merged in at persistence time, the same "validate/store, then merge
    # back" shape as `custom_field_storage`/`primary_contact_custom_field_storage`.
    group_field_storage: dict[str, dict[int, dict[str, str]]] = {}
    for group_id, file_field_id in content_types.group_file_field_ids.items():
        files = group_field_file_contents.get(group_id, [])
        group_content_types = content_types.group_files[group_id]
        for index, content in enumerate(files):
            storage_key = await storage_save(
                tenant.id, "invitations/group-files", content, group_content_types[index]
            )
            group_field_storage.setdefault(group_id, {}).setdefault(index, {})[file_field_id] = (
                storage_key
            )

    # Inline (non-grouped) custom-field file uploads
    # (add-inline-custom-field-file-upload): validated for presence/count
    # earlier, so every entry reaching this loop is safe to store — same
    # "content-type validate, then store, then write the storage key back"
    # shape as the group loop above, keyed by field key rather than group
    # key. Storage key, never the raw upload, lands in the persisted
    # `customFieldValues`/`primaryContactCustomFieldValues` map, same as
    # `groupFieldValues`'s own `file_upload` field — all three are resolved
    # to a signed URL on read by `invitations/presenters.py`'s
    # `_resolve_custom_field_file_values` (add-generic-custom-field-file-
    # url-resolution), keyed off `InvitationDetailFormContext`'s file-field
    # sets.
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

    # Per visitor, ID proof then photo, as the visitor rows were built.
    visitor_id_proof_keys: list[str | None] = []
    visitor_photo_keys: list[str | None] = []
    for idx in range(visitor_count):
        # ID-proof files are order-matched but, when the branch has
        # deactivated ID proof, may be entirely absent or shorter than the
        # visitor list — same "beyond the supplied count simply has none"
        # posture as photos. A present file always has a content type.
        id_proof_type = (
            content_types.visitor_id_proofs[idx] if idx < len(visitor_id_proof_contents) else None
        )
        visitor_id_proof_keys.append(
            await storage_save(
                tenant.id, "invitations/id-proof", visitor_id_proof_contents[idx], id_proof_type
            )
            if id_proof_type is not None
            else None
        )
        # Photos are order-matched but may be shorter than the visitor list —
        # a visitor beyond the supplied photo count simply has none.
        visitor_photo_keys.append(
            await storage_save(
                tenant.id,
                "invitations/photos",
                visitor_photo_contents[idx],
                content_types.visitor_photos[idx],
            )
            if idx < len(visitor_photo_contents)
            else None
        )

    return _StoredUploads(
        primary_id_proof=primary_key,
        primary_photo=primary_photo_key,
        visitor_id_proofs=visitor_id_proof_keys,
        visitor_photos=visitor_photo_keys,
        group_fields=group_field_storage,
        primary_contact_custom_fields=primary_contact_custom_field_storage,
        custom_fields=custom_field_storage,
        visitor_custom_fields=visitor_custom_field_storage,
        vehicle_custom_fields=vehicle_custom_field_storage,
    )


def _merge_indexed_file_storage(
    base: dict[str, Any], storage: dict[str, list[str]], index: int
) -> dict[str, Any]:
    """`storage` (`_StoredUploads.visitor_custom_fields`/`vehicle_custom_fields`)
    is order-matched per field key, same convention as
    `visitor_id_proof_contents` — may be shorter than the visitor/vehicle
    list for a field with no file at this index."""
    merged = dict(base)
    for key, values in storage.items():
        if index < len(values):
            merged[key] = values[index]
    return merged


def _build_invitation_rows(
    tenant_db: AsyncSession,
    repo: InvitationRepository,
    payload: InvitationCreate,
    stored: _StoredUploads,
    *,
    branch_id: uuid.UUID,
    building_id: uuid.UUID | None,
    created_by_user_id: uuid.UUID | None,
    source: RegistrationSource,
    initial_status: str,
    visitor_category_id: uuid.UUID,
    tracking_id: str,
    expires_at: datetime,
    now: datetime,
    approved_at: datetime | None,
    primary_contact_full_name: str,
    primary_contact_email: str | None,
    primary_contact_custom_field_values: dict[str, Any],
    invitation_level_custom_field_values: dict[str, Any],
    visit_details: dict[str, Any],
    consents: dict[str, bool],
) -> Invitation:
    """Adds the invitation and its visitor and vehicle rows to the session."""
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
        primary_contact_id_proof_storage_key=stored.primary_id_proof,
        primary_contact_photo_storage_key=stored.primary_photo,
        primary_contact_custom_field_values={
            **primary_contact_custom_field_values,
            **stored.primary_contact_custom_fields,
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
        consents=dict(consents),
        consent_recorded_at=now,
        custom_field_values={**invitation_level_custom_field_values, **stored.custom_fields},
        group_field_values={
            group_id: [
                {**instance, **stored.group_fields.get(group_id, {}).get(index, {})}
                for index, instance in enumerate(instances)
            ]
            for group_id, instances in payload.group_values.items()
        },
    )
    tenant_db.add(invitation)

    repo.add_visitors(
        [
            InvitationVisitor(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                full_name=visitor.full_name,
                email=visitor.email,
                phone=visitor.phone,
                id_proof_type=visitor.id_proof_type,
                id_proof_storage_key=stored.visitor_id_proofs[idx],
                photo_storage_key=stored.visitor_photos[idx],
                custom_field_values=_merge_indexed_file_storage(
                    visitor.custom_field_values, stored.visitor_custom_fields, idx
                ),
            )
            for idx, visitor in enumerate(payload.visitors)
        ]
    )
    repo.add_vehicles(
        [
            InvitationVehicle(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                vehicle_type=vehicle.vehicle_type,
                license_plate=vehicle.license_plate,
                make_model=vehicle.make_model,
                color=vehicle.color,
                custom_field_values=_merge_indexed_file_storage(
                    vehicle.custom_field_values, stored.vehicle_custom_fields, idx
                ),
            )
            for idx, vehicle in enumerate(payload.vehicles)
        ]
    )
    return invitation


async def _resolve_approval(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    tenant: Tenant,
    auto_approved: bool,
    visitor_category_id: uuid.UUID,
    now: datetime,
) -> InvitationQRCode | None:
    """Sets up approval in the same transaction as the invitation insert
    (design.md Decision 1). Returns the QR code of an auto-approved
    invitation, `None` for one awaiting approval."""
    # Snapshot the category's active workflow rules into ordered steps,
    # exactly as configured — see `_build_approval_steps` for when a
    # synthetic ownership step still gets added (only when the category has
    # no active rules at all) — only for a `submitted` (not auto-approved)
    # invitation, and only once. Every submitted invitation still gets at
    # least one step, regardless of whether the category has any active
    # rules.
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
        return None

    # Generated in the same transaction as the invitation itself when it's
    # already `approved` (design.md "Token generation moves to approval
    # time, persisted") — never for a `submitted` invitation, matching
    # "a QR code is never included until the invitation is approved".
    qr_code = await _issue_qr_code(tenant_db, invitation, tenant=tenant)
    await _issue_checkin_code(tenant_db, invitation)
    return qr_code


async def _post_commit_notify(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    tenant: Tenant,
    qr_code: InvitationQRCode | None,
) -> None:
    """Enqueues the visitor notice and, for an invitation awaiting approval,
    pushes and emails its first approver(s). Runs after the commit, so a
    worker never reads a row that isn't there yet. `qr_code` is set exactly
    when the invitation was auto-approved."""
    if qr_code is not None:
        tasks.send_approval_notification.delay(
            request_id=current_request_id(),
            tenant_schema=tenant.schema_name,
            invitation_id=str(invitation.id),
            qr_token=qr_code.qr_token,
        )
        return

    tasks.send_tracking_notification.delay(
        request_id=current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(invitation.id),
    )

    # Staff-facing push, additional to the visitor email/SMS above
    # (specs/invitations/spec.md "Invitation Submission Notifies the
    # Approval Workflow's First Approver(s) via Push"). An auto-approved
    # invitation never has approval steps, so no push fires for one —
    # matching "Auto-Approved Invitations Do Not Trigger a Submission Push".
    current_step = await InvitationApprovalStepRepository(tenant_db).get_current_pending(
        invitation.id
    )
    if current_step is None:
        # No resolved host and no active workflow rules — nobody to notify
        # (proposal.md's "no push recipient" case).
        logger.warning("push_notify_no_approval_step", invitation_id=str(invitation.id))
        return
    title, body, data = push_notifications.step_awaiting_approval(invitation)
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
            request_id=current_request_id(),
            tenant_schema=tenant.schema_name,
            invitation_id=str(invitation.id),
            role_id=str(current_step.approver_role_id),
            branch_id=str(invitation.branch_id),
        )


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
    visitor_group_instances = (
        payload.group_values.get(str(visitor_group["id"]), []) if visitor_group else []
    )
    try:
        # Individual registrations have no additional-visitor list, so the
        # group's minimum must not be applied to their zero count.
        form_builder_validation.validate_group_instance_count(
            visitor_group,
            len(payload.visitors),
            scope="A group registration",
            skip_minimum=payload.registration_type != RegistrationType.group
            or bool(visitor_group_instances),
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
    # specs/invitations/spec.md "Visitor List Matches Registration Type": a
    # group needs at least one visitor, either in `visitors` or as instances
    # of a field group. A branch may collect extra visitors in an
    # admin-defined Visitor Info group, which this can't tell apart from
    # other groups, so any non-empty group counts. The seeded group isn't
    # repeatable and its `minInstances` is unset, so the check above can't
    # supply this floor (audit-and-harden design.md G38).
    if (
        payload.registration_type == RegistrationType.group
        and not payload.visitors
        and not any(group.instances for group in payload.groups)
    ):
        logger.warning(
            "registration_form_config_validation_failed",
            branch_id=str(branch_id),
            check="group_instance_count",
            reason="group_without_visitors",
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A group registration must list at least one visitor",
        )

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

    # Resolved once, at creation, rather than recomputed later — an
    # invitation's approval state is a stable, recorded fact of what
    # actually happened (design.md Decision 1). Defaults to the more
    # conservative "awaiting approval" path when no Company profile is
    # configured yet, matching the column's own default.
    company = await CompanyRepository(tenant_db).get_singleton()
    auto_approved = company is not None and company.auto_approve_pre_registered_visitors
    expires_at = _end_of_visit_day_utc(
        payload.visit_details.preferred_visit_date, _visit_timezone(company, tenant)
    )
    initial_status = "approved" if auto_approved else "submitted"
    approved_at = now if auto_approved else None

    group_field_file_contents = group_field_file_contents or {}
    content_types = _validate_uploads(
        payload,
        custom_groups_by_id=custom_groups_by_id,
        group_visibility=group_visibility,
        primary_contact_id_proof_content=primary_contact_id_proof_content,
        visitor_id_proof_contents=visitor_id_proof_contents,
        primary_contact_photo_content=primary_contact_photo_content,
        visitor_photo_contents=visitor_photo_contents,
        group_field_file_contents=group_field_file_contents,
    )

    # Branch/building/department are resolved before the first storage
    # write, so a 422 for a bad location leaves no orphaned uploads behind.
    if source == RegistrationSource.visitor_walk_in and payload.effective_branch_id is not None:
        # A kiosk's device branch is only the default; the visitor's own
        # branch selection wins, provided it is an active branch.
        branch_id = await _resolve_active_branch(tenant_db, payload.effective_branch_id)
    building_id = await _resolve_building(tenant_db, payload.effective_building_id, branch_id)
    if visit_details["department_id"] is None and visit_details["department_to_visit"]:
        # Free-text department with no `departmentId`: link it to the branch's
        # department of the same name so the detail view returns the record.
        visit_details["department_id"] = await _match_department_by_name(
            tenant_db, branch_id, visit_details["department_to_visit"]
        )

    stored = await _persist_uploads(
        tenant,
        content_types,
        primary_contact_id_proof_content=primary_contact_id_proof_content,
        visitor_id_proof_contents=visitor_id_proof_contents,
        primary_contact_photo_content=primary_contact_photo_content,
        visitor_photo_contents=visitor_photo_contents,
        group_field_file_contents=group_field_file_contents,
        primary_contact_custom_field_file_contents=primary_contact_custom_field_file_contents,
        custom_field_file_contents=custom_field_file_contents,
        visitor_custom_field_file_contents=visitor_custom_field_file_contents,
        vehicle_custom_field_file_contents=vehicle_custom_field_file_contents,
        visitor_count=len(payload.visitors),
    )
    invitation = _build_invitation_rows(
        tenant_db,
        repo,
        payload,
        stored,
        branch_id=branch_id,
        building_id=building_id,
        created_by_user_id=created_by_user_id,
        source=source,
        initial_status=initial_status,
        visitor_category_id=visitor_category_id,
        tracking_id=tracking_id,
        expires_at=expires_at,
        now=now,
        approved_at=approved_at,
        primary_contact_full_name=primary_contact_full_name,
        primary_contact_email=primary_contact_email,
        primary_contact_custom_field_values=primary_contact_custom_field_values,
        invitation_level_custom_field_values=invitation_level_custom_field_values,
        visit_details=visit_details,
        consents=consents_dict,
    )
    qr_code = await _resolve_approval(
        tenant_db,
        invitation,
        tenant=tenant,
        auto_approved=auto_approved,
        visitor_category_id=visitor_category_id,
        now=now,
    )

    await tenant_db.commit()

    created = await repo.get_with_children(invitation.id)
    assert created is not None  # just committed; guaranteed to exist

    await _post_commit_notify(tenant_db, created, tenant=tenant, qr_code=qr_code)
    return created
