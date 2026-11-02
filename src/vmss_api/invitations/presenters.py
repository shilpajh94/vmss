"""Response presenters for invitations: turn ORM rows into the API's out
schemas, resolving storage keys to signed URLs. Shared by the invitation,
approval and registration routers (moved out of `router.py` unchanged).
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.schemas import CurrentApprovalStepOut
from vmss_api.core.storage import url_for as storage_url_for
from vmss_api.core.storage import url_for_optional
from vmss_api.devices import service as device_service
from vmss_api.devices.models import Device
from vmss_api.invitations import service
from vmss_api.invitations.models import Invitation, InvitationVisitor
from vmss_api.invitations.schemas import (
    BadgeOut,
    ConsentValue,
    ContactMethod,
    CustomFieldValue,
    FieldGroupValuesOut,
    InvitationBranchOut,
    InvitationBuildingOut,
    InvitationCheckInOut,
    InvitationDepartmentOut,
    InvitationDetailOut,
    InvitationListItemOut,
    InvitationOut,
    InvitationQrCheckInOut,
    InvitationTrackingOut,
    InvitationVehicleOut,
    InvitationVisitorDetailOut,
    InvitationVisitorOut,
    RegistrationSource,
    RegistrationType,
)
from vmss_api.org_structure.models import Branch, Building, Department


def to_invitation_out(
    invitation: Invitation, current_approval_step: CurrentApprovalStepOut | None = None
) -> InvitationOut:
    return InvitationOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        registration_type=RegistrationType(invitation.registration_type),
        source=RegistrationSource(invitation.source),
        status=invitation.status,
        visitor_category_id=invitation.visitor_category_id,
        host_id=invitation.host_id,
        poc_user_id=invitation.poc_user_id,
        poc_role_id=invitation.poc_role_id,
        poc_name=invitation.poc_name,
        building_id=invitation.building_id,
        department_id=invitation.department_id,
        department_to_visit=invitation.department_to_visit,
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        current_approval_step=current_approval_step,
        approval_reverted_at=invitation.approval_reverted_at,
        approval_reverted_by_user_id=invitation.approval_reverted_by_user_id,
        approval_revert_reason=invitation.approval_revert_reason,
        archived_at=invitation.archived_at,
        checked_out_automatically=invitation.checked_out_automatically,
    )


async def _resolve_photo_url(storage_key: str | None) -> str | None:
    return await url_for_optional(storage_key)


async def _resolve_document_url(storage_key: str | None) -> str | None:
    """Same resolution as `_resolve_photo_url`, kept as a separate function
    so every call site is a visible, greppable instance of "this resolves a
    raw ID-proof document" — callers MUST only invoke this once the caller
    is confirmed to hold `documents:view` (enrich-invitation-checkin-and-
    detail-views/design.md Decision 4); never call it unconditionally.
    """
    return await url_for_optional(storage_key)


async def _resolve_custom_field_file_values(
    values: dict[str, Any], file_ids: set[str], *, include_documents: bool
) -> dict[str, Any]:
    """Rewrites `values` (a `{fieldId: value}`-shaped map — a persisted
    `customFieldValues`/`primaryContactCustomFieldValues`, or one
    `groupFieldValues` instance — restructure-walkin-payload-by-field-id)
    so every `file_upload`-typed field in it (`file_ids`) holds a signed,
    viewable URL instead of the raw storage key `service.create_invitation`
    persisted for it (add-generic-custom-field-file-url-resolution) —
    mirrors how `primary_contact_photo_url`/`id_proof_url` are already
    resolved before serializing rather than left as opaque keys.

    Gated by `include_documents` the same as `_resolve_document_url`: a
    caller without `documents:view` for this invitation's branch gets
    `None` for these ids rather than the raw key or a resolved URL, since
    a generic file-upload field is exactly the kind of place an ID scan or
    other sensitive document can end up.

    `file_ids` reflects the branch's *current* effective form, not the form
    as it was when `values` was persisted — if a field's type was changed to
    `file_upload` after an older invitation already stored a non-file value
    under that id, `values[field_id]` may be a bool/number/list/dict rather
    than a storage key. `_resolve_document_url` -> `storage_url_for` ->
    `quote()` crashes on anything that isn't `str`/`bytes`, so such values
    are treated as "no file" (`None`) rather than passed to it.
    """
    if not file_ids:
        return values
    resolved = dict(values)
    for field_id in file_ids:
        if field_id not in resolved:
            continue
        storage_key = resolved[field_id]
        resolved[field_id] = (
            await _resolve_document_url(storage_key)
            if include_documents and isinstance(storage_key, str)
            else None
        )
    return resolved


async def _resolve_group_field_values(
    group_field_values: dict[str, list[dict[str, Any]]],
    group_file_ids: dict[str, set[str]],
    *,
    include_documents: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Applies `_resolve_custom_field_file_values` to every instance of
    every group in `group_field_values` (keyed by group id) — the same
    per-group-instance resolution `_to_invitation_detail_out` needs,
    factored out so the check-in/QR/tracking responses
    (add-generic-custom-field-file-url-resolution) can share it instead of
    re-deriving the dict comprehension.
    """
    return {
        group_id: [
            await _resolve_custom_field_file_values(
                instance, group_file_ids.get(group_id, set()), include_documents=include_documents
            )
            for instance in instances
        ]
        for group_id, instances in group_field_values.items()
    }


def _dict_to_custom_fields(
    field_meta: dict[str, dict[str, str]], values: dict[str, Any]
) -> list[CustomFieldValue]:
    """`{str(fieldId): value}` -> the wire's `list[{fieldId, value}]` shape
    (restructure-walkin-payload-by-field-id) — the response-side
    counterpart of `invitations/schemas.py::_custom_fields_to_dict`."""
    return [
        CustomFieldValue(
            field_id=uuid.UUID(fid),
            field_name=field_meta.get(fid, {}).get("label"),
            field_key=field_meta.get(fid, {}).get("key"),
            value=value,
        )
        for fid, value in values.items()
    ]


def _dict_to_consents(
    field_meta: dict[str, dict[str, str]], values: dict[str, bool]
) -> list[ConsentValue]:
    return [
        ConsentValue(
            field_id=uuid.UUID(fid),
            field_name=field_meta.get(fid, {}).get("label"),
            field_key=field_meta.get(fid, {}).get("key"),
            accepted=accepted,
        )
        for fid, accepted in values.items()
    ]


def _dict_to_groups(
    field_meta: dict[str, dict[str, str]],
    values: dict[str, list[dict[str, Any]]],
    group_names: dict[str, str],
) -> list[FieldGroupValuesOut]:
    return [
        FieldGroupValuesOut(
            group_id=uuid.UUID(group_id),
            group_name=group_names.get(group_id),
            instances=[_dict_to_custom_fields(field_meta, instance) for instance in instances],
        )
        for group_id, instances in values.items()
    ]


async def _to_visitor_outs(
    visitors: Sequence[InvitationVisitor],
    visitor_info_file_ids: set[str],
    field_meta: dict[str, dict[str, str]],
) -> list[InvitationVisitorOut]:
    """Used by every response except the staff detail view — deliberately
    produces `InvitationVisitorOut`, which has no ID-proof document field
    at all (see that schema's docstring). None of these callers are ever
    behind a `documents:view` check (public check-in/QR/tracking endpoints,
    add-generic-custom-field-file-url-resolution) — `include_documents` is
    always `False`, so a `file_upload`-typed field's raw storage key never
    reaches an unauthenticated caller; it's dropped to `None` the same way
    `InvitationVisitorOut` already omits `idProofUrl` entirely.
    """
    return [
        InvitationVisitorOut(
            id=v.id,
            full_name=v.full_name,
            email=v.email,
            phone=v.phone,
            id_proof_type=v.id_proof_type,
            photo_url=await _resolve_photo_url(v.photo_storage_key),
            custom_fields=_dict_to_custom_fields(
                field_meta,
                await _resolve_custom_field_file_values(
                    v.custom_field_values, visitor_info_file_ids, include_documents=False
                ),
            ),
        )
        for v in visitors
    ]


async def _to_visitor_detail_outs(
    visitors: Sequence[InvitationVisitor],
    *,
    include_documents: bool,
    visitor_info_file_ids: set[str],
    field_meta: dict[str, dict[str, str]],
) -> list[InvitationVisitorDetailOut]:
    """Staff detail view (`GET /invitations/{id}`) only. `include_documents`
    is the caller's already-resolved `documents:view` grant — when `False`,
    `id_proof_url` is left `None` without ever calling
    `_resolve_document_url` (no storage lookup for a document the caller
    can't see)."""
    return [
        InvitationVisitorDetailOut(
            id=v.id,
            full_name=v.full_name,
            email=v.email,
            phone=v.phone,
            id_proof_type=v.id_proof_type,
            id_proof_url=(
                await _resolve_document_url(v.id_proof_storage_key) if include_documents else None
            ),
            photo_url=await _resolve_photo_url(v.photo_storage_key),
            custom_fields=_dict_to_custom_fields(
                field_meta,
                await _resolve_custom_field_file_values(
                    v.custom_field_values,
                    visitor_info_file_ids,
                    include_documents=include_documents,
                ),
            ),
        )
        for v in visitors
    ]


def _to_location_outs(
    branch: Branch,
    department: Department | None,
    building: Building | None,
    department_to_visit: str | None = None,
) -> tuple[InvitationBranchOut, InvitationBuildingOut | None, InvitationDepartmentOut | None]:
    branch_out = InvitationBranchOut(
        id=branch.id,
        name=branch.name,
        code=branch.code,
        address=branch.address,
        city=branch.city,
    )
    building_out = (
        InvitationBuildingOut(id=building.id, name=building.name, code=building.code)
        if building is not None
        else None
    )
    department_out = (
        InvitationDepartmentOut(id=department.id, name=department.name, code=department.code)
        if department is not None
        else InvitationDepartmentOut(name=department_to_visit)
        if department_to_visit
        else None
    )
    return branch_out, building_out, department_out


async def _to_qr_check_in_out(
    invitation: Invitation,
    *,
    branch: Branch,
    department: Department | None,
    building: Building | None,
    form_context: service.InvitationDetailFormContext,
) -> InvitationQrCheckInOut:
    """Public, unauthenticated QR check-in/check-out. There is no
    `documents:view` caller to gate on, so no ID-proof document or
    `file_upload` field resolves to a URL here (spec.md "QR Check-In
    Response Surfaces Full Invitation Detail": that stays exclusive to the
    authenticated staff detail view). Visitors use `InvitationVisitorOut`,
    which has no `idProofUrl` key at all. Raw storage keys are never
    returned."""
    branch_out, building_out, department_out = _to_location_outs(
        branch, department, building, invitation.department_to_visit
    )
    return InvitationQrCheckInOut(
        id=invitation.id,
        branch_id=invitation.branch_id,
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        check_in_status=invitation.check_in_status,
        registration_type=invitation.registration_type,
        source=invitation.source,
        visitor_category_id=invitation.visitor_category_id,
        branch=branch_out,
        building=building_out,
        department=department_out,
        primary_contact_full_name=invitation.primary_contact_full_name,
        primary_contact_photo_url=await _resolve_photo_url(
            invitation.primary_contact_photo_storage_key
        ),
        primary_contact_preferred_contact_method=ContactMethod(
            invitation.primary_contact_preferred_contact_method
        ),
        primary_contact_id_proof_type=invitation.primary_contact_id_proof_type,
        primary_contact_email=invitation.primary_contact_email,
        primary_contact_phone=invitation.primary_contact_phone,
        host_id=invitation.host_id,
        host_name_or_email=invitation.host_name_or_email,
        poc_user_id=invitation.poc_user_id,
        poc_role_id=invitation.poc_role_id,
        poc_name=invitation.poc_name,
        purpose_of_visit=invitation.purpose_of_visit,
        purpose_id=invitation.purpose_id,
        duration_id=invitation.duration_id,
        department_id=invitation.department_id,
        department_to_visit=invitation.department_to_visit,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        expected_duration=invitation.expected_duration,
        additional_notes=invitation.additional_notes,
        carried_items=invitation.carried_items,
        carried_items_description=invitation.carried_items_description,
        consents=_dict_to_consents(form_context.field_meta, invitation.consents),
        consent_recorded_at=invitation.consent_recorded_at,
        custom_fields=_dict_to_custom_fields(
            form_context.field_meta,
            {
                **await _resolve_custom_field_file_values(
                    invitation.primary_contact_custom_field_values,
                    form_context.visitor_info_file_ids,
                    include_documents=False,
                ),
                **await _resolve_custom_field_file_values(
                    invitation.custom_field_values,
                    form_context.invitation_scope_file_ids,
                    include_documents=False,
                ),
            },
        ),
        groups=_dict_to_groups(
            form_context.field_meta,
            await _resolve_group_field_values(
                invitation.group_field_values, form_context.group_file_ids, include_documents=False
            ),
            form_context.group_names,
        ),
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        checked_in_at=invitation.checked_in_at,
        checked_out_at=invitation.checked_out_at,
        expires_at=invitation.expires_at,
        visitors=[
            InvitationVisitorOut(**visitor.model_dump(exclude={"id_proof_url"}))
            for visitor in [
                *await _to_visitor_detail_outs(
                    invitation.visitors,
                    include_documents=False,
                    visitor_info_file_ids=form_context.visitor_info_file_ids,
                    field_meta=form_context.field_meta,
                ),
                *await _group_collected_visitor_detail_outs(
                    invitation,
                    form_context.visitor_info_groups,
                    include_documents=False,
                    field_meta=form_context.field_meta,
                ),
            ]
        ],
        vehicles=[
            InvitationVehicleOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                license_plate=v.license_plate,
                make_model=v.make_model,
                color=v.color,
                custom_fields=_dict_to_custom_fields(
                    form_context.field_meta,
                    await _resolve_custom_field_file_values(
                        v.custom_field_values,
                        form_context.vehicle_info_file_ids,
                        include_documents=False,
                    ),
                ),
            )
            for v in invitation.vehicles
        ],
        archived_at=invitation.archived_at,
        checked_out_automatically=invitation.checked_out_automatically,
    )


async def _to_list_item_out(
    invitation: Invitation, current_approval_step: CurrentApprovalStepOut | None = None
) -> InvitationListItemOut:
    return InvitationListItemOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        registration_type=RegistrationType(invitation.registration_type),
        source=RegistrationSource(invitation.source),
        status=invitation.status,
        visitor_category_id=invitation.visitor_category_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        primary_contact_email=invitation.primary_contact_email,
        primary_contact_phone=invitation.primary_contact_phone,
        primary_contact_photo_url=await _resolve_photo_url(
            invitation.primary_contact_photo_storage_key
        ),
        purpose_of_visit=invitation.purpose_of_visit,
        department_to_visit=invitation.department_to_visit,
        department_id=invitation.department_id,
        building_id=invitation.building_id,
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        archived_at=invitation.archived_at,
        checked_out_automatically=invitation.checked_out_automatically,
        status_changed_at=service.status_changed_at(invitation),
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        current_approval_step=current_approval_step,
    )


async def _to_tracking_out(
    invitation: Invitation,
    current_approval_step: CurrentApprovalStepOut | None = None,
    *,
    form_context: service.InvitationDetailFormContext,
) -> InvitationTrackingOut:
    """Public, unauthenticated tracking lookup — see `_to_visitor_outs` on
    why every `file_upload` field resolves with `include_documents=False`."""
    return InvitationTrackingOut(
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        registration_type=invitation.registration_type,
        source=invitation.source,
        visitor_category_id=invitation.visitor_category_id,
        current_approval_step=current_approval_step,
        primary_contact_full_name=invitation.primary_contact_full_name,
        primary_contact_photo_url=await _resolve_photo_url(
            invitation.primary_contact_photo_storage_key
        ),
        purpose_of_visit=invitation.purpose_of_visit,
        host_name_or_email=invitation.host_name_or_email,
        poc_user_id=invitation.poc_user_id,
        poc_role_id=invitation.poc_role_id,
        poc_name=invitation.poc_name,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        expected_duration=invitation.expected_duration,
        department_to_visit=invitation.department_to_visit,
        additional_notes=invitation.additional_notes,
        carried_items=invitation.carried_items,
        carried_items_description=invitation.carried_items_description,
        custom_fields=_dict_to_custom_fields(
            form_context.field_meta,
            {
                **await _resolve_custom_field_file_values(
                    invitation.primary_contact_custom_field_values,
                    form_context.visitor_info_file_ids,
                    include_documents=False,
                ),
                **await _resolve_custom_field_file_values(
                    invitation.custom_field_values,
                    form_context.invitation_scope_file_ids,
                    include_documents=False,
                ),
            },
        ),
        groups=_dict_to_groups(
            form_context.field_meta,
            await _resolve_group_field_values(
                invitation.group_field_values, form_context.group_file_ids, include_documents=False
            ),
            form_context.group_names,
        ),
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        visitors=await _to_visitor_outs(
            invitation.visitors, form_context.visitor_info_file_ids, form_context.field_meta
        ),
        vehicles=[
            InvitationVehicleOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                license_plate=v.license_plate,
                make_model=v.make_model,
                color=v.color,
                custom_fields=_dict_to_custom_fields(
                    form_context.field_meta,
                    await _resolve_custom_field_file_values(
                        v.custom_field_values,
                        form_context.vehicle_info_file_ids,
                        include_documents=False,
                    ),
                ),
            )
            for v in invitation.vehicles
        ],
        archived_at=invitation.archived_at,
        checked_out_automatically=invitation.checked_out_automatically,
    )


async def _to_check_in_out(
    invitation: Invitation,
    current_approval_step: CurrentApprovalStepOut | None = None,
    *,
    form_context: service.InvitationDetailFormContext,
) -> InvitationCheckInOut:
    """Public, unauthenticated staff/desk check-in — see `_to_visitor_outs`
    on why every `file_upload` field resolves with `include_documents=False`."""
    return InvitationCheckInOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        registration_type=RegistrationType(invitation.registration_type),
        source=RegistrationSource(invitation.source),
        status=invitation.status,
        visitor_category_id=invitation.visitor_category_id,
        host_id=invitation.host_id,
        poc_user_id=invitation.poc_user_id,
        poc_role_id=invitation.poc_role_id,
        poc_name=invitation.poc_name,
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        current_approval_step=current_approval_step,
        primary_contact_full_name=invitation.primary_contact_full_name,
        primary_contact_photo_url=await _resolve_photo_url(
            invitation.primary_contact_photo_storage_key
        ),
        purpose_of_visit=invitation.purpose_of_visit,
        host_name_or_email=invitation.host_name_or_email,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        expected_duration=invitation.expected_duration,
        department_to_visit=invitation.department_to_visit,
        additional_notes=invitation.additional_notes,
        carried_items=invitation.carried_items,
        carried_items_description=invitation.carried_items_description,
        custom_fields=_dict_to_custom_fields(
            form_context.field_meta,
            {
                **await _resolve_custom_field_file_values(
                    invitation.primary_contact_custom_field_values,
                    form_context.visitor_info_file_ids,
                    include_documents=False,
                ),
                **await _resolve_custom_field_file_values(
                    invitation.custom_field_values,
                    form_context.invitation_scope_file_ids,
                    include_documents=False,
                ),
            },
        ),
        groups=_dict_to_groups(
            form_context.field_meta,
            await _resolve_group_field_values(
                invitation.group_field_values, form_context.group_file_ids, include_documents=False
            ),
            form_context.group_names,
        ),
        visitors=await _to_visitor_outs(
            invitation.visitors, form_context.visitor_info_file_ids, form_context.field_meta
        ),
        vehicles=[
            InvitationVehicleOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                license_plate=v.license_plate,
                make_model=v.make_model,
                color=v.color,
                custom_fields=_dict_to_custom_fields(
                    form_context.field_meta,
                    await _resolve_custom_field_file_values(
                        v.custom_field_values,
                        form_context.vehicle_info_file_ids,
                        include_documents=False,
                    ),
                ),
            )
            for v in invitation.vehicles
        ],
        archived_at=invitation.archived_at,
        checked_out_automatically=invitation.checked_out_automatically,
    )


async def _group_collected_visitor_detail_outs(
    invitation: Invitation,
    visitor_info_groups: dict[str, dict[str, Any]],
    *,
    include_documents: bool,
    field_meta: dict[str, dict[str, str]],
) -> list[InvitationVisitorDetailOut]:
    """A branch that collects additional visitors through an admin-defined
    repeatable group on Visitor Info instead of the fixed `visitors` list
    (the built-in "Visitors" system group is no longer admin-configurable
    — `form_builder/defaults.py`) has that data in `group_field_values`,
    not `visitors`. Synthesizes a visitor-shaped entry per submitted
    instance of such a group so it surfaces through the same `visitors`
    array/UI rendering, with no separate response shape for the frontend to
    special-case.

    There's no reserved "this is the name field" marker on a group — an
    admin's fields are arbitrary — so `fullName` falls back to the group's
    first-configured field's value (`fieldIds[0]`, the only ordering signal
    available — restructure-walkin-payload-by-field-id). `email`/`phone`
    instead use Form Builder's own typed field system: the group's first
    field of `fieldType` `"email"`/`"phone"` (there can be at most a
    handful of fields per group, so "first" only matters if an admin adds
    more than one of the same type). Every field the client actually
    submitted is still in `customFields` regardless.

    `idProofUrl` (add-group-field-file-upload) resolves the same way:
    `service.create_invitation` already overwrote the group's first
    `file_upload`-typed field's value with a storage key at submission
    time (never a client-supplied value — see
    `service.py::_group_field_file_id`), so this only has to resolve that
    id to a URL, gated by `include_documents` (`documents:view`) the same
    as `_to_visitor_detail_outs`'s `idProofUrl`. `idProofType` has no
    `fieldType` of its own to key off the way email/phone do, so it's
    populated only when the group happens to define a field literally keyed
    `id_proof_type` — the same key the fixed `visitors`/`primaryContact`
    system field uses — rather than inventing a new convention.
    """
    results: list[InvitationVisitorDetailOut] = []
    for group_id, instances in invitation.group_field_values.items():
        group = visitor_info_groups.get(group_id)
        if group is None:
            continue
        fields = group.get("fields") or []
        name_field_id = next(iter(group.get("fieldIds", [])), None)
        email_field_id = next((f["id"] for f in fields if f["fieldType"] == "email"), None)
        phone_field_id = next((f["id"] for f in fields if f["fieldType"] == "phone"), None)
        id_proof_url_field_id = next(
            (f["id"] for f in fields if f["fieldType"] == "file_upload"), None
        )
        id_proof_type_field_id = next(
            (f["id"] for f in fields if f["key"] == "id_proof_type"), None
        )
        group_file_ids = {f["id"] for f in fields if f["fieldType"] == "file_upload"}
        for index, instance in enumerate(instances):
            display_name = instance.get(name_field_id) if name_field_id else None
            email = instance.get(email_field_id) if email_field_id else None
            phone = instance.get(phone_field_id) if phone_field_id else None
            id_proof_type = instance.get(id_proof_type_field_id) if id_proof_type_field_id else None
            id_proof_storage_key = (
                instance.get(id_proof_url_field_id) if id_proof_url_field_id else None
            )
            results.append(
                InvitationVisitorDetailOut(
                    id=uuid.uuid5(invitation.id, f"{group_id}:{index}"),
                    full_name=str(display_name) if display_name else "Additional Visitor",
                    email=str(email) if email else None,
                    phone=str(phone) if phone else None,
                    id_proof_type=str(id_proof_type) if id_proof_type else None,
                    id_proof_url=(
                        await _resolve_document_url(id_proof_storage_key)
                        if isinstance(id_proof_storage_key, str) and include_documents
                        else None
                    ),
                    photo_url=None,
                    custom_fields=_dict_to_custom_fields(
                        field_meta,
                        await _resolve_custom_field_file_values(
                            instance, group_file_ids, include_documents=include_documents
                        ),
                    ),
                )
            )
    return results


async def _to_invitation_detail_out(
    invitation: Invitation,
    current_approval_step: CurrentApprovalStepOut | None = None,
    *,
    branch: Branch,
    department: Department | None,
    building: Building | None,
    include_documents: bool,
    form_context: service.InvitationDetailFormContext,
) -> InvitationDetailOut:
    branch_out, building_out, department_out = _to_location_outs(
        branch, department, building, invitation.department_to_visit
    )
    resolved_group_field_values = await _resolve_group_field_values(
        invitation.group_field_values,
        form_context.group_file_ids,
        include_documents=include_documents,
    )
    return InvitationDetailOut(
        id=invitation.id,
        branch_id=invitation.branch_id,
        branch=branch_out,
        building=building_out,
        department=department_out,
        source=RegistrationSource(invitation.source),
        created_by_user_id=invitation.created_by_user_id,
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        registration_type=invitation.registration_type,
        visitor_category_id=invitation.visitor_category_id,
        current_approval_step=current_approval_step,
        primary_contact_full_name=invitation.primary_contact_full_name,
        primary_contact_email=invitation.primary_contact_email,
        primary_contact_phone=invitation.primary_contact_phone,
        primary_contact_preferred_contact_method=ContactMethod(
            invitation.primary_contact_preferred_contact_method
        ),
        primary_contact_photo_url=await _resolve_photo_url(
            invitation.primary_contact_photo_storage_key
        ),
        primary_contact_id_proof_type=invitation.primary_contact_id_proof_type,
        primary_contact_id_proof_url=(
            await _resolve_document_url(invitation.primary_contact_id_proof_storage_key)
            if include_documents
            else None
        ),
        purpose_of_visit=invitation.purpose_of_visit,
        purpose_id=invitation.purpose_id,
        host_name_or_email=invitation.host_name_or_email,
        host_id=invitation.host_id,
        duration_id=invitation.duration_id,
        department_id=invitation.department_id,
        poc_user_id=invitation.poc_user_id,
        poc_role_id=invitation.poc_role_id,
        poc_name=invitation.poc_name,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        previous_preferred_visit_date=invitation.previous_preferred_visit_date,
        previous_preferred_visit_time=invitation.previous_preferred_visit_time,
        rescheduled_at=invitation.rescheduled_at,
        reschedule_count=invitation.reschedule_count,
        expected_duration=invitation.expected_duration,
        department_to_visit=invitation.department_to_visit,
        additional_notes=invitation.additional_notes,
        carried_items=invitation.carried_items,
        carried_items_description=invitation.carried_items_description,
        consents=_dict_to_consents(form_context.field_meta, invitation.consents),
        consent_recorded_at=invitation.consent_recorded_at,
        custom_fields=_dict_to_custom_fields(
            form_context.field_meta,
            {
                **await _resolve_custom_field_file_values(
                    invitation.primary_contact_custom_field_values,
                    form_context.visitor_info_file_ids,
                    include_documents=include_documents,
                ),
                **await _resolve_custom_field_file_values(
                    invitation.custom_field_values,
                    form_context.invitation_scope_file_ids,
                    include_documents=include_documents,
                ),
            },
        ),
        groups=_dict_to_groups(
            form_context.field_meta, resolved_group_field_values, form_context.group_names
        ),
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        approval_reverted_at=invitation.approval_reverted_at,
        approval_reverted_by_user_id=invitation.approval_reverted_by_user_id,
        approval_revert_reason=invitation.approval_revert_reason,
        denial_reason=invitation.denial_reason,
        denied_at=invitation.denied_at,
        checked_in_at=invitation.checked_in_at,
        checked_in_by_user_id=invitation.checked_in_by_user_id,
        checked_out_at=invitation.checked_out_at,
        checked_out_by_user_id=invitation.checked_out_by_user_id,
        badge_number=invitation.badge_number,
        badge_issued_at=invitation.badge_issued_at,
        badge_reprint_count=invitation.badge_reprint_count,
        watchlist_flagged=invitation.watchlist_flagged,
        watchlist_override_at=invitation.watchlist_override_at,
        watchlist_override_reason=invitation.watchlist_override_reason,
        watchlist_override_by_user_id=invitation.watchlist_override_by_user_id,
        visitors=[
            *await _to_visitor_detail_outs(
                invitation.visitors,
                include_documents=include_documents,
                visitor_info_file_ids=form_context.visitor_info_file_ids,
                field_meta=form_context.field_meta,
            ),
            *await _group_collected_visitor_detail_outs(
                invitation,
                form_context.visitor_info_groups,
                include_documents=include_documents,
                field_meta=form_context.field_meta,
            ),
        ],
        vehicles=[
            InvitationVehicleOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                license_plate=v.license_plate,
                make_model=v.make_model,
                color=v.color,
                custom_fields=_dict_to_custom_fields(
                    form_context.field_meta,
                    await _resolve_custom_field_file_values(
                        v.custom_field_values,
                        form_context.vehicle_info_file_ids,
                        include_documents=include_documents,
                    ),
                ),
            )
            for v in invitation.vehicles
        ],
        archived_at=invitation.archived_at,
        checked_out_automatically=invitation.checked_out_automatically,
    )


async def _to_badge_out(invitation: Invitation) -> BadgeOut:
    assert invitation.badge_number is not None and invitation.badge_issued_at is not None
    assert invitation.badge_storage_key is not None  # set together with badge_number
    return BadgeOut(
        badge_number=invitation.badge_number,
        badge_url=await storage_url_for(invitation.badge_storage_key),
        issued_at=invitation.badge_issued_at,
        reprint_count=invitation.badge_reprint_count,
    )


async def _attach_devices[
    T: (InvitationOut, InvitationCheckInOut, InvitationQrCheckInOut, InvitationDetailOut)
](out: T, invitation: Invitation, tenant_db: AsyncSession) -> T:
    """Fills `checkInDevice`/`checkOutDevice` with one lookup for both ids."""
    briefs = await device_service.device_briefs(
        tenant_db, invitation.check_in_device_id, invitation.check_out_device_id
    )
    check_in_id, check_out_id = invitation.check_in_device_id, invitation.check_out_device_id
    out.check_in_device = briefs.get(check_in_id) if check_in_id is not None else None
    out.check_out_device = briefs.get(check_out_id) if check_out_id is not None else None
    return out


def _device_diff(device: Device | None) -> dict[str, str] | None:
    return {"device_id": device.device_id} if device else None
