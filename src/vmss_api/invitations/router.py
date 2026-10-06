import json
import uuid
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from vmss_api.approvals.schemas import CurrentApprovalStepOut
from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.deps import get_current_user, get_pagination, get_tenant, get_tenant_db
from vmss_api.core.idempotency import cache_response as _core_cache_response
from vmss_api.core.idempotency import cached_response as _core_cached_response
from vmss_api.core.logging import logger
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import (
    error_response,
    paginated_response,
    success_response,
)
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.core.storage import url_for as storage_url_for
from vmss_api.invitations import service
from vmss_api.invitations.deps import track_default_tenant, track_default_tenant_db
from vmss_api.invitations.schemas import (
    BadgeOut,
    CarriedItemsSubmit,
    ConsentValue,
    ContactMethod,
    CustomFieldValue,
    FieldGroupValuesOut,
    InvitationBranchOut,
    InvitationBuildingOut,
    InvitationCheckInOut,
    InvitationCreate,
    InvitationDenyRequest,
    InvitationDepartmentOut,
    InvitationDetailOut,
    InvitationEditRequest,
    InvitationExtendRequest,
    InvitationListItemOut,
    InvitationLookupPrefillOut,
    InvitationOut,
    InvitationPrimaryContactCreate,
    InvitationQrCheckInOut,
    InvitationRescheduleRequest,
    InvitationSortableField,
    InvitationStatus,
    InvitationTrackingOut,
    InvitationTrackingSummaryOut,
    InvitationVehicleOut,
    InvitationVisitorDetailOut,
    InvitationVisitorOut,
    RegistrationSource,
    RegistrationType,
    VehicleSubmit,
    VisitDetailsSubmit,
    VisitorSubmit,
    WatchlistOverrideRequest,
)
from vmss_api.org_structure.deps import (
    authorize_branch_id,
    authorize_branch_id_tolerant,
    require_branch_scope,
)
from vmss_api.org_structure.models import Branch, Building, Department
from vmss_api.org_structure.service import get_default_host_role
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/invitations", tags=["invitations"])

# Module-level singleton (ruff B008: a `File(...)` call as a literal argument
# default is flagged the same as a mutable literal default) — an
# `individual` registration simply sends no files under this field name.
_NO_VISITOR_FILES = File(
    default_factory=list,
    description=(
        "Each co-visitor's ID-proof image/PDF upload, matched to "
        "`payload.visitors` by order (first file -> `visitors[0]`, etc.). "
        "Omit entirely for an individual registration. See "
        "`primaryContactIdProofFile` above for the primary contact's own "
        "upload, which travels as a separate field."
    ),
)
# Same rationale as `_NO_VISITOR_FILES` above (ruff B008) — an optional,
# order-matched list of co-visitor profile photos, independent of and
# possibly shorter than `visitor_id_proof_files` (a photo is never required).
_NO_VISITOR_PHOTOS = File(
    default_factory=list,
    description=(
        "Optional profile photo per co-visitor (JPEG/PNG only), matched to "
        "`payload.visitors` by order. May be shorter than the visitor list "
        "— omit an entry for any visitor with no photo."
    ),
)

# Single source of truth for both Swagger-facing example mechanisms below —
# the `openapi_extra` multipart examples (Decision kept from the earlier
# fix) and the `payload` Form field's own `description` (new — see
# document-invitation-create-payload-shape/design.md Decision 1). Keeping one
# dict per registration type means both channels can never drift apart.
_INDIVIDUAL_PAYLOAD_EXAMPLE = {
    "registrationType": "individual",
    "visitorCategoryId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "primaryContact": {
        "fullName": "Meera Krishnan",
        "email": "meera.krishnan@example.com",
        "phone": "+91 90000 11122",
        "preferredContactMethod": "email",
        "idProofType": "Passport",
    },
    "visitors": [],
    "visitDetails": {
        "purposeOfVisit": "Interview",
        "hostNameOrEmail": "hr@enterprise-ugo.co",
        "preferredVisitDate": "2026-08-12",
        "preferredVisitTime": "10:00",
        "expectedDuration": "< 1 hour",
        "departmentToVisit": "Human Resources",
        "additionalNotes": "",
    },
    "carriedItems": {"items": [], "itemDescription": ""},
    "vehicles": [],
    # Referenced by fieldId (restructure-walkin-payload-by-field-id), never
    # by key/label — one entry per field the calling branch's published
    # Consent Agreement step currently declares. Left empty here rather
    # than illustrated with fixed ids: a real caller must resolve the
    # actual field ids from the branch's currently-published form
    # (form-builder's effective-form read), never hardcode them.
    "consents": [],
}

_GROUP_PAYLOAD_EXAMPLE = {
    "registrationType": "group",
    "visitorCategoryId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "primaryContact": {
        "fullName": "Priya Sharma",
        "email": "priya.sharma@enterprise-ugo.co",
        "phone": "+91 98765 43210",
        "preferredContactMethod": "email",
        "idProofType": "Aadhaar Card",
    },
    "visitors": [
        {
            "fullName": "Alexander Pierce",
            "email": "alexander.p@enterprise-ugo.co",
            "phone": None,
            "idProofType": "Aadhaar Card",
        },
        {
            "fullName": "Clara Oswald",
            "email": None,
            "phone": "+1 (555) 014-0362",
            "idProofType": "Passport",
        },
    ],
    "visitDetails": {
        "purposeOfVisit": "Business Meeting",
        "hostNameOrEmail": "Rahul Nair",
        "preferredVisitDate": "2026-08-15",
        "preferredVisitTime": "14:30",
        "expectedDuration": "1-2 hours",
        "departmentToVisit": "Engineering",
        "additionalNotes": "Wheelchair access required for one visitor.",
    },
    "carriedItems": {
        "items": ["laptop_tablet", "mobile_phone"],
        "itemDescription": "2x company laptops, personal phones.",
    },
    "vehicles": [
        {
            "vehicleType": "4_wheeler",
            "licensePlate": "KA-01-AB-1234",
            "makeModel": "Honda City",
            "color": "White",
        },
        {
            "vehicleType": "2_wheeler",
            "licensePlate": "KA-05-CD-5678",
            "makeModel": "Honda Activa",
            "color": "Black",
        },
    ],
    "consents": [],
}

# This route combines three Form/File params into one synthesized multipart
# body, so FastAPI does not surface any single param's own `openapi_examples`
# (verified against the installed FastAPI: it only reads examples off the
# route's single combined body field). `openapi_extra` is the mechanism that
# actually reaches `requestBody.content['multipart/form-data'].examples` — but
# Swagger UI does not apply those examples when populating a multipart "Try
# it out" form (it only does this for JSON bodies), so this alone is not
# sufficient for this project's actual `/docs` rendering; see `_PAYLOAD_
# DESCRIPTION` below for the channel that reliably renders.
_INVITATION_PAYLOAD_EXAMPLES = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "examples": {
                    "individual": {
                        "summary": "Individual registration, no co-visitors or vehicles",
                        "value": {"payload": json.dumps(_INDIVIDUAL_PAYLOAD_EXAMPLE)},
                    },
                    "group": {
                        "summary": "Group registration with co-visitors and vehicles",
                        "value": {"payload": json.dumps(_GROUP_PAYLOAD_EXAMPLE)},
                    },
                }
            }
        }
    }
}


def _required_fields_summary() -> str:
    """Built from each schema's own `.model_json_schema()["required"]` list
    — not hand-typed — so this text can't silently drift from the actual
    validators as fields change
    (verify-invitation-validation-and-dispatch/design.md Decision 2).
    `email`/`phone` are each individually optional in every schema below
    since "at least one of the two" is a cross-field business rule a JSON
    Schema `required` entry can't express; called out explicitly instead of
    left to look like an oversight.

    Structurally-mandatory only — `idProofType` (per visitor/primary
    contact), the primary contact's photo file, and which `consents`
    field ids must be `accepted: true` are additionally branch-configurable
    (`form-builder`): required by default, but not required if the calling
    branch's published configuration has deactivated/relaxed them. See the
    note appended below.
    """
    nested: list[tuple[str, type[BaseModel]]] = [
        ("primaryContact", InvitationPrimaryContactCreate),
        ("each entry in visitors", VisitorSubmit),
        ("visitDetails", VisitDetailsSubmit),
        ("carriedItems", CarriedItemsSubmit),
        ("each entry in vehicles", VehicleSubmit),
    ]
    lines = [
        "Required fields (generated from the schemas below, not hand-typed):",
        f"- Top level: {', '.join(InvitationCreate.model_json_schema()['required'])}",
    ]
    for label, model in nested:
        required = model.model_json_schema().get("required", [])
        lines.append(f"- {label}: {', '.join(required) if required else '(none required)'}")
    lines.append(
        "- consents: optional, defaults to `[]` if omitted; see the branch-configurable note below."
    )
    lines.append(
        "Note: `email`/`phone` are each individually optional above, but at "
        "least one is required on every contact/visitor entry — enforced by "
        "a cross-field rule, not a schema-level `required` marker."
    )
    lines.append(
        "Note: `idProofType`/the ID-proof and primary-contact-photo files "
        "default to required, and the default three Consent Agreement "
        "fields (terms accepted, data processing accepted, safety "
        "guidelines accepted) default to all being required — but every "
        "branch can reconfigure these via the Form Builder admin "
        "capability, so the effective requirement for a given branch/call "
        "may differ from this schema-level default. `consents`, "
        "`customFields`, and `groups` are all referenced by the field/group "
        "id from that branch's currently published form (fetched via the "
        "form-builder effective-form read), never by a hardcoded key — see "
        "restructure-walkin-payload-by-field-id."
    )
    return "\n".join(lines)


# Rendered directly in Swagger's Parameters table for the `payload` field —
# unlike `_INVITATION_PAYLOAD_EXAMPLES` above, a Form/File parameter's own
# `description` is confirmed to render regardless of content type and without
# opening "Try it out" (document-invitation-create-payload-shape/design.md
# Decision 1).
_PAYLOAD_DESCRIPTION = (
    "JSON-encoded InvitationCreate: registrationType, primaryContact (with "
    "idProofType), visitors, visitDetails, carriedItems, vehicles, consents, "
    "customFields, groups (camelCase). `consents`/`customFields`/`groups` "
    "reference the calling branch's form-builder field/group ids, never a "
    "key/label.\n\n"
    'Example for `registrationType: "individual"`:\n'
    f"```json\n{json.dumps(_INDIVIDUAL_PAYLOAD_EXAMPLE, indent=2)}\n```\n\n"
    'Example for `registrationType: "group"`:\n'
    f"```json\n{json.dumps(_GROUP_PAYLOAD_EXAMPLE, indent=2)}\n```\n\n"
    f"{_required_fields_summary()}"
)


def to_invitation_out(
    invitation, current_approval_step: CurrentApprovalStepOut | None = None
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
    )


async def _resolve_photo_url(storage_key: str | None) -> str | None:
    return await storage_url_for(storage_key) if storage_key is not None else None


async def _resolve_document_url(storage_key: str | None) -> str | None:
    """Same resolution as `_resolve_photo_url`, kept as a separate function
    so every call site is a visible, greppable instance of "this resolves a
    raw ID-proof document" — callers MUST only invoke this once the caller
    is confirmed to hold `documents:view` (enrich-invitation-checkin-and-
    detail-views/design.md Decision 4); never call it unconditionally.
    """
    return await storage_url_for(storage_key) if storage_key is not None else None


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
) -> list[FieldGroupValuesOut]:
    return [
        FieldGroupValuesOut(
            group_id=uuid.UUID(group_id),
            instances=[_dict_to_custom_fields(field_meta, instance) for instance in instances],
        )
        for group_id, instances in values.items()
    ]


async def _to_visitor_outs(
    visitors, visitor_info_file_ids: set[str], field_meta: dict[str, dict[str, str]]
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
    visitors,
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
    invitation,
    *,
    branch: Branch,
    department: Department | None,
    building: Building | None,
    form_context: service.InvitationDetailFormContext,
) -> InvitationQrCheckInOut:
    """Public, unauthenticated QR check-in/check-out (`documents:view` is
    never granted here — see `_to_visitor_outs`). The primary contact's own
    ID proof URL is the one document resolved anyway (the signed QR token
    is the capability); every `file_upload` field is resolved with
    `include_documents=False`: raw storage keys are stripped to `None`
    rather than leaked to an anonymous caller."""
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
        primary_contact_id_proof_url=await _resolve_document_url(
            invitation.primary_contact_id_proof_storage_key
        ),
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
        ),
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        checked_in_at=invitation.checked_in_at,
        checked_out_at=invitation.checked_out_at,
        expires_at=invitation.expires_at,
        visitors=[
            *await _to_visitor_outs(
                invitation.visitors, form_context.visitor_info_file_ids, form_context.field_meta
            ),
            *[
                InvitationVisitorOut(
                    id=v.id,
                    full_name=v.full_name,
                    email=v.email,
                    phone=v.phone,
                    id_proof_type=v.id_proof_type,
                    photo_url=v.photo_url,
                    custom_fields=v.custom_fields,
                )
                for v in await _group_collected_visitor_detail_outs(
                    invitation,
                    form_context.visitor_info_groups,
                    include_documents=False,
                    field_meta=form_context.field_meta,
                )
            ],
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
    )


async def _to_list_item_out(invitation) -> InvitationListItemOut:
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
    )


async def _to_tracking_out(
    invitation,
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
    )


async def _to_check_in_out(
    invitation,
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
    )


async def _group_collected_visitor_detail_outs(
    invitation,
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
    invitation,
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
        groups=_dict_to_groups(form_context.field_meta, resolved_group_field_values),
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
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
    )


async def _to_badge_out(invitation) -> BadgeOut:
    assert invitation.badge_number is not None and invitation.badge_issued_at is not None
    return BadgeOut(
        badge_number=invitation.badge_number,
        badge_url=await storage_url_for(invitation.badge_storage_key),
        issued_at=invitation.badge_issued_at,
        reprint_count=invitation.badge_reprint_count,
    )


async def _parse_prefixed_multipart_files(
    form_data, prefix: str, *, limit: int
) -> dict[str, list[bytes]]:
    """Parses every `<prefix>[<key>]` multipart list part into
    `{key: [bytes, ...]}` — the shared convention `groupFieldFiles`
    (add-group-field-file-upload) and `customFieldFiles`/
    `primaryContactCustomFieldFiles`/`visitorCustomFieldFiles`/
    `vehicleCustomFieldFiles` (add-inline-custom-field-file-upload) all use.
    `<key>` is expected to be a group id or field id
    (restructure-walkin-payload-by-field-id) — branch-specific and unknown
    at route-declaration time either way — read via `request.form()` instead of
    a declared `File(...)` param. Filtered against Starlette's own
    `UploadFile` (not `fastapi.UploadFile`, a subclass FastAPI only
    constructs for its own declared `File(...)` params) —
    `request.form()`'s multipart parser builds the Starlette one directly,
    so `isinstance(value, fastapi.UploadFile)` here would silently match
    nothing. Shared by `registrations/router.py::create_walk_in_registration`
    as well, which accepts the identical contract.
    """
    result: dict[str, list[bytes]] = {}
    marker = f"{prefix}["
    for key in set(form_data.keys()):
        if key.startswith(marker) and key.endswith("]"):
            bracket_id = key[len(marker) : -1]
            result[bracket_id] = [
                await value.read(limit)
                for value in form_data.getlist(key)
                if isinstance(value, StarletteUploadFile)
            ]
    return result


async def _cached_response(
    tenant_id: uuid.UUID, idempotency_key: str | None
) -> JSONResponse | None:
    """api-conventions.md §3 — a retried multipart submission with the same
    `Idempotency-Key` returns the original response instead of re-processing
    (which would otherwise create duplicate visitor rows and send a second
    confirmation email).
    """
    return await _core_cached_response(tenant_id, "invitations", idempotency_key)


async def _cache_response(
    tenant_id: uuid.UUID, idempotency_key: str | None, response: JSONResponse
) -> None:
    await _core_cache_response(tenant_id, "invitations", idempotency_key, response)


# --- API-09: employee creates a fully completed invitation ------------------


@router.post(
    "",
    response_model=Envelope[InvitationOut],
    status_code=status.HTTP_201_CREATED,
    openapi_extra=_INVITATION_PAYLOAD_EXAMPLES,
)
async def create_invitation(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: Annotated[str, Form(description=_PAYLOAD_DESCRIPTION)],
    primary_contact_id_proof_file: Annotated[
        UploadFile | None,
        File(
            description=(
                "Primary contact's ID-proof image/PDF upload — paired with "
                "`payload.primaryContact`. Required by default, but only "
                "when the calling branch's published Form Builder "
                "configuration marks ID proof active/required (it may be "
                "omitted otherwise). See `visitorIdProofFiles` below for "
                "the co-visitor equivalent."
            )
        ),
    ] = None,
    primary_contact_photo_file: Annotated[
        UploadFile | None,
        File(
            description=(
                "Profile photo for the primary contact (JPEG/PNG only) — "
                "paired with `payload.primaryContact`. Required by default, "
                "but only when the calling branch's published Form Builder "
                "configuration marks it active/required. See "
                "`visitorPhotoFiles` below for the (always optional) "
                "co-visitor equivalent."
            )
        ),
    ] = None,
    visitor_id_proof_files: list[UploadFile] = _NO_VISITOR_FILES,
    visitor_photo_files: list[UploadFile] = _NO_VISITOR_PHOTOS,
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional. Omitting it simply forgoes retry-dedup safety — a "
                "retried request with no key may create a second invitation. "
                "See api-conventions.md §3."
            ),
        ),
    ] = None,
    x_branch_id: Annotated[
        uuid.UUID | None,
        Header(
            alias="X-Branch-ID",
            description=(
                "Which branch this invitation belongs to. Optional — falls "
                "back to `branchId` in the payload when omitted; one of the "
                "two is required."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """A single authenticated call creates a fully completed invitation —
    primary contact, co-visitors, visit details, carried items, vehicles,
    and consent, each with their own ID-proof upload — and immediately
    returns a tracking ID (design.md Decisions 1 and 2). A retried request
    reuses the same `Idempotency-Key` semantics (`api-conventions.md` §3) so
    it can't create a second invitation.

    An admin-defined repeatable group's own `file_upload`-typed field
    (add-group-field-file-upload) has no fixed multipart parameter — its
    group id is branch-specific and unknown at route-declaration time — so
    it isn't one of the typed `File(...)` params above. Instead, for a
    group with such a field, the caller sends one multipart list part named
    `groupFieldFiles[<groupId>]`, order-matched to that same group's
    `payload.groups` entry's `instances` (the same "list, order matched to
    instances" convention `visitorIdProofFiles` already uses for the fixed
    `visitors` list). Read below via `request.form()` rather than a
    declared parameter, since the set of valid ids isn't known until
    `service.create_invitation` resolves the branch's active Form Builder
    configuration.

    An admin-defined `file_upload`-typed field that is *not* assigned to a
    group (add-inline-custom-field-file-upload) — e.g. an "additional
    document" field added directly on Visitor Info — uses the same
    `request.form()` convention, one multipart part per scope, keyed by
    field id (restructure-walkin-payload-by-field-id — not group id, so,
    unlike a group, every `file_upload` field at a scope is supported, not
    just the first):
    - `primaryContactCustomFieldFiles[<fieldId>]` — at most one file,
      paired with the invitation-level `payload.customFields` (a Visitor
      Info-step field id there is understood as the primary contact's
      answer — see `service.py::create_invitation`).
    - `visitorCustomFieldFiles[<fieldId>]` — order-matched to
      `payload.visitors`, same convention as `visitorIdProofFiles`.
    - `vehicleCustomFieldFiles[<fieldId>]` — order-matched to
      `payload.vehicles`.
    - `customFieldFiles[<fieldId>]` — at most one file, paired with the
      invitation-level `payload.customFields` (Visit Details/Carried Items/a
      custom step).

    In every case, the field's id must be **omitted** (or its entry left
    out entirely) from the corresponding `customFields` array — supplying
    any other value for it is rejected with `422`, never silently
    overwritten; the file is the only valid source of that field's answer.
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    try:
        create_payload = InvitationCreate.model_validate_json(payload)
    except ValidationError as exc:
        return error_response(message=str(exc), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    branch_id = x_branch_id if x_branch_id is not None else create_payload.branch_id
    if branch_id is None:
        return error_response(
            message=(
                "branchId in the payload (or the X-Branch-ID header) is "
                "required to determine which branch this invitation belongs to"
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    branch = await authorize_branch_id(tenant_db, user, "invitations:create", branch_id)

    # Bounded reads (file-upload-handling.md §1, add-avatar-upload-and-
    # verify-image-storage/design.md Decision 3): reject an oversized file
    # before its full content is buffered into memory, rather than reading
    # it all and only then checking `len()` in `service.py`'s validation.
    id_proof_limit = settings.invitation_max_upload_size_bytes + 1
    photo_limit = settings.invitation_max_photo_size_bytes + 1
    primary_content = (
        await primary_contact_id_proof_file.read(id_proof_limit)
        if primary_contact_id_proof_file is not None
        else None
    )
    visitor_contents = [await f.read(id_proof_limit) for f in visitor_id_proof_files]
    primary_photo_content = (
        await primary_contact_photo_file.read(photo_limit)
        if primary_contact_photo_file is not None
        else None
    )
    visitor_photo_contents = [await f.read(photo_limit) for f in visitor_photo_files]

    # See `_parse_prefixed_multipart_files`'s docstring: none of these are
    # declared params since the field/group key inside each `[...]` is
    # branch-specific. Starlette caches the parsed multipart body on
    # `request`, so this reuses the same parse the `payload`/
    # `primary_contact_*`/`visitor_*` params above already triggered rather
    # than re-reading the request body.
    form_data = await request.form()
    group_field_file_contents = await _parse_prefixed_multipart_files(
        form_data, "groupFieldFiles", limit=id_proof_limit
    )
    primary_contact_custom_field_file_contents = await _parse_prefixed_multipart_files(
        form_data, "primaryContactCustomFieldFiles", limit=id_proof_limit
    )
    visitor_custom_field_file_contents = await _parse_prefixed_multipart_files(
        form_data, "visitorCustomFieldFiles", limit=id_proof_limit
    )
    vehicle_custom_field_file_contents = await _parse_prefixed_multipart_files(
        form_data, "vehicleCustomFieldFiles", limit=id_proof_limit
    )
    custom_field_file_contents = await _parse_prefixed_multipart_files(
        form_data, "customFieldFiles", limit=id_proof_limit
    )

    invitation = await service.create_invitation(
        tenant_db,
        create_payload,
        branch_id=branch.id,
        created_by_user_id=user.id,
        tenant=tenant,
        primary_contact_id_proof_content=primary_content,
        visitor_id_proof_contents=visitor_contents,
        primary_contact_photo_content=primary_photo_content,
        visitor_photo_contents=visitor_photo_contents,
        group_field_file_contents=group_field_file_contents,
        primary_contact_custom_field_file_contents=primary_contact_custom_field_file_contents,
        visitor_custom_field_file_contents=visitor_custom_field_file_contents,
        vehicle_custom_field_file_contents=vehicle_custom_field_file_contents,
        custom_field_file_contents=custom_field_file_contents,
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_created",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    current_approval_step = await service.get_current_approval_step(tenant_db, invitation)
    response = success_response(
        data=to_invitation_out(invitation, current_approval_step),
        status_code=status.HTTP_201_CREATED,
    )
    await _cache_response(tenant.id, idempotency_key, response)
    return response


# --- Manual approval ----------------------------------------------------------


@router.post(
    "/{invitation_id}/approve",
    response_model=Envelope[InvitationOut],
)
async def approve_invitation(
    invitation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Transitions a `submitted` invitation to `approved` and dispatches
    the QR-bearing approval notification at that point
    (`add-invitation-approval-flow-and-role-resync/design.md` Decision 3).
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:approve", invitation.branch_id)
    invitation = await service.approve_invitation(tenant_db, invitation, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_approved",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    return success_response(data=to_invitation_out(invitation))


# --- add-invitation-lifecycle-actions: deny / check-in / check-out / --------
# --- reschedule / extend / badge / watchlist-override -----------------------


@router.patch(
    "/{invitation_id}/deny",
    response_model=Envelope[InvitationOut],
)
async def deny_invitation(
    invitation_id: uuid.UUID,
    payload: InvitationDenyRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Transitions a `submitted` invitation to `denied` with a mandatory
    reason (spec.md "A Submitted Invitation Can Be Denied With a Reason").
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:deny", invitation.branch_id)
    invitation = await service.deny_invitation(
        tenant_db, invitation, reason=payload.reason, tenant=tenant
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_denied",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    return success_response(data=to_invitation_out(invitation))


# --- add-public-checkin-endpoint: public check-in by tracking ID ------------
# A second, minimal router mounted at /api/v2 (see api.py/main.py) — not a
# wholesale re-exposure of every v1 invitations route under v2, just this one
# endpoint (design.md Decision 1).

router_v2 = APIRouter(prefix="/invitations", tags=["invitations"])


@router_v2.patch(
    "/{tracking_id}/check-in",
    response_model=Envelope[InvitationCheckInOut],
)
@limiter.limit("20/minute")
async def check_in_invitation_by_tracking_id(
    request: Request,
    tracking_id: str,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(track_default_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional. A repeat check-in call is already an idempotent "
                "no-op once the invitation is checked in (allow-multiple-"
                "checkins), so omitting this key is safe against a bare "
                "retry; it still dedupes two *distinct* requests that "
                "happen to race (e.g. concurrent double-taps). See "
                "api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """The single staff/desk-facing check-in endpoint (spec.md "Staff
    Check-In Has One Canonical Endpoint"), keyed by the invitation's
    `tracking_id` instead of its internal UUID `id` (spec.md "An Approved
    Invitation Can Be Publicly Checked In By Tracking ID") — for a kiosk,
    the visitor's own device checking in from the QR/badge code, or a staff
    desk view, with no staff bearer token required. `checkInStatus` cycles
    `unused`/`checked_out` -> `checked_in` indefinitely (allow-multiple-
    checkins) — `checked_out` is not terminal, mirroring the QR endpoint's
    re-entry rule; a call while already `checked_in` is a 200 idempotent
    no-op, not an error. Returns the same full invitation detail the legacy
    staff-authenticated route used to (spec.md "Staff Check-In Response
    Surfaces Full Invitation Detail"). No branch authorization check, since
    there is no authenticated caller to check it against.
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation, changed = await service.check_in_invitation_by_tracking_id(
        tenant_db, tracking_id, tenant=tenant
    )
    if changed:
        background_tasks.add_task(
            record_audit_log,
            tenant.schema_name,
            actor_user_id=None,
            action="invitation_checked_in_public",
            entity_type="Invitation",
            entity_id=invitation.id,
        )
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    response = success_response(data=await _to_check_in_out(invitation, form_context=form_context))
    await _cache_response(tenant.id, idempotency_key, response)
    return response


@router_v2.patch(
    "/qr/{token}/check-in",
    response_model=Envelope[InvitationQrCheckInOut],
)
@limiter.limit("20/minute")
async def check_in_by_qr_token(
    request: Request,
    token: str,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(track_default_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Required in practice, not just optional retry-dedup safety: "
                "the same QR token drives both the entry and exit scan, so a "
                "fresh key per physical scan keeps a network retry of one "
                "scan from being deduped against the other. See "
                "api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """Public, unauthenticated QR check-in (spec.md "QR Check-In Endpoint
    Transitions an Eligible Visitor to Checked-In") — scanning an
    invitation's encrypted check-in token transitions `checkInStatus` from
    `unused`/`checked_out` (currently outside) to `checked_in`. This
    endpoint no longer toggles: calling it while already `checked_in`
    returns 200 as an idempotent no-op (unchanged data) rather than
    performing a second transition — use
    `PATCH /api/v2/invitations/qr/{token}/check-out` to actually exit.
    Expiry is enforced on every entry, including a re-entry. Shares its
    already-checked-in state (and therefore this idempotent-no-op behavior)
    with `PATCH /api/v2/invitations/{trackingId}/check-in` — both endpoints
    read/write the same `checkInStatus` column, so a visitor checked in via
    one is recognized as already-checked-in by the other.
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation, message, changed = await service.check_in_by_qr_token(
        tenant_db, token, tenant=tenant
    )
    if changed:
        background_tasks.add_task(
            record_audit_log,
            tenant.schema_name,
            actor_user_id=None,
            action="invitation_qr_checked_in",
            entity_type="Invitation",
            entity_id=invitation.id,
        )
    branch, department, building = await service.get_invitation_location(tenant_db, invitation)
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    response = success_response(
        data=await _to_qr_check_in_out(
            invitation,
            branch=branch,
            department=department,
            building=building,
            form_context=form_context,
        ),
        message=message,
    )
    await _cache_response(tenant.id, idempotency_key, response)
    return response


@router_v2.patch(
    "/qr/{token}/check-out",
    response_model=Envelope[InvitationQrCheckInOut],
)
@limiter.limit("20/minute")
async def check_out_by_qr_token(
    request: Request,
    token: str,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(track_default_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Required in practice, not just optional retry-dedup safety: "
                "a fresh key per physical scan keeps a network retry from "
                "being deduped against a different scan. See "
                "api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """Public, unauthenticated QR check-out (spec.md "QR Check-Out Endpoint
    Transitions a Checked-In Visitor to Checked-Out") — exit counterpart of
    `PATCH /api/v2/invitations/qr/{token}/check-in`. Transitions
    `checkInStatus` from `checked_in` to `checked_out`; never expiry-blocked
    (a visit that legitimately continues past `expiresAt` can still be
    closed out). Rejects with 409 when the invitation isn't currently
    `checked_in`.
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation, message = await service.check_out_by_qr_token(tenant_db, token, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action="invitation_qr_checked_out",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    branch, department, building = await service.get_invitation_location(tenant_db, invitation)
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    response = success_response(
        data=await _to_qr_check_in_out(
            invitation,
            branch=branch,
            department=department,
            building=building,
            form_context=form_context,
        ),
        message=message,
    )
    await _cache_response(tenant.id, idempotency_key, response)
    return response


@router.patch(
    "/{invitation_id}/check-out",
    response_model=Envelope[InvitationOut],
)
async def check_out_invitation(
    invitation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", description="Optional — see check-in.")
    ] = None,
) -> JSONResponse:
    """Transitions a `checked_in` invitation to `checked_out`, closing the
    visit (spec.md "A Checked-In Invitation Can Be Checked Out").
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(
        tenant_db, user, "invitations:checkout", invitation.branch_id
    )
    invitation = await service.check_out_invitation(
        tenant_db, invitation, user_id=user.id, tenant=tenant
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_checked_out",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    response = success_response(data=to_invitation_out(invitation))
    await _cache_response(tenant.id, idempotency_key, response)
    return response


@router.patch(
    "/{invitation_id}/reschedule",
    response_model=Envelope[InvitationOut],
)
async def reschedule_invitation(
    invitation_id: uuid.UUID,
    payload: InvitationRescheduleRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Changes the visit date/time while the invitation is `submitted` or
    `approved` (spec.md "Visit Date/Time Can Be Rescheduled Before
    Check-In").
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(
        tenant_db, user, "invitations:reschedule", invitation.branch_id
    )
    previous_preferred_visit_date = invitation.preferred_visit_date
    previous_preferred_visit_time = invitation.preferred_visit_time
    invitation = await service.reschedule_invitation(
        tenant_db,
        invitation,
        preferred_visit_date=payload.preferred_visit_date,
        preferred_visit_time=payload.preferred_visit_time,
        tenant=tenant,
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_rescheduled",
        entity_type="Invitation",
        entity_id=invitation.id,
        diff={
            "before": {
                "preferredVisitDate": (
                    previous_preferred_visit_date.isoformat()
                    if previous_preferred_visit_date
                    else None
                ),
                "preferredVisitTime": (
                    previous_preferred_visit_time.isoformat()
                    if previous_preferred_visit_time
                    else None
                ),
            },
            "after": {
                "preferredVisitDate": (
                    invitation.preferred_visit_date.isoformat()
                    if invitation.preferred_visit_date
                    else None
                ),
                "preferredVisitTime": (
                    invitation.preferred_visit_time.isoformat()
                    if invitation.preferred_visit_time
                    else None
                ),
            },
        },
    )
    return success_response(data=to_invitation_out(invitation))


@router.patch(
    "/{invitation_id}/edit",
    response_model=Envelope[InvitationOut],
)
async def edit_invitation(
    invitation_id: uuid.UUID,
    payload: InvitationEditRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Edits an invitation's non-personal visit details — purpose, date/
    time, duration, department, notes — while it is `submitted` or
    `approved` (role-based-invitation-workflow, spec.md "Authorized Caller
    Edits Non-Personal Invitation Details"). Never accepts the visitor's own
    personal fields, `visitorCategoryId`, or the host — host reassignment
    stays exclusively the `approvals` capability's delegation endpoint's job.

    Also accepts `pocUserId`/`pocRoleId` (add-invitation-point-of-contact) —
    the invitation's point of contact, settable to a specific person or a
    role at any time, independent of the approval workflow's current step.
    Setting either requires `invitations:approve` at the invitation's
    branch, checked in `service.edit_invitation` in addition to this
    endpoint's own `invitations:edit` gate.
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:edit", invitation.branch_id)
    invitation = await service.edit_invitation(
        tenant_db, invitation, payload, tenant=tenant, user=user
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_edited",
        entity_type="Invitation",
        entity_id=invitation.id,
        diff=payload.model_dump(exclude_unset=True, mode="json"),
    )
    return success_response(data=to_invitation_out(invitation))


@router.patch(
    "/{invitation_id}/extend",
    response_model=Envelope[InvitationOut],
)
async def extend_invitation(
    invitation_id: uuid.UUID,
    payload: InvitationExtendRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Pushes `expiresAt` forward for an `approved`/`checked_in` visit
    (spec.md "An Active Visit's Expiry Can Be Extended").
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:extend", invitation.branch_id)
    invitation = await service.extend_invitation(
        tenant_db, invitation, new_expires_at=payload.expires_at
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_extended",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    return success_response(data=to_invitation_out(invitation))


@router.post(
    "/{invitation_id}/badge",
    response_model=Envelope[BadgeOut],
    status_code=status.HTTP_201_CREATED,
)
async def issue_badge(
    invitation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", description="Optional — see check-in.")
    ] = None,
) -> JSONResponse:
    """Issues a printable badge for an `approved`/`checked_in` invitation
    (spec.md "A Badge Can Be Printed for an Approved or Active Visit").
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:badge", invitation.branch_id)
    invitation = await service.issue_badge(tenant_db, invitation, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_badge_issued",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    response = success_response(
        data=await _to_badge_out(invitation), status_code=status.HTTP_201_CREATED
    )
    await _cache_response(tenant.id, idempotency_key, response)
    return response


@router.post(
    "/{invitation_id}/badge/reprint",
    response_model=Envelope[BadgeOut],
)
async def reprint_badge(
    invitation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Re-renders an already-issued badge and increments its reprint count
    (spec.md "A Badge Can Be Reprinted").
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:badge", invitation.branch_id)
    invitation = await service.reprint_badge(tenant_db, invitation, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_badge_reprinted",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    return success_response(data=await _to_badge_out(invitation))


@router.post(
    "/{invitation_id}/watchlist-override",
    response_model=Envelope[InvitationOut],
)
async def override_watchlist(
    invitation_id: uuid.UUID,
    payload: WatchlistOverrideRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Admin-only override that clears `watchlistFlagged` so check-in can
    proceed (spec.md "A Watchlist-Flagged Invitation Blocks Check-In Until
    Overridden"). Does not itself check the invitation in.
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(
        tenant_db, user, "invitations:watchlist-override", invitation.branch_id
    )
    invitation = await service.override_watchlist(
        tenant_db, invitation, user_id=user.id, reason=payload.reason
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_watchlist_overridden",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    return success_response(data=to_invitation_out(invitation))


# --- Employee listing ---------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedEnvelope[InvitationListItemOut],
)
async def list_invitations(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
    relevant_to_me: Annotated[bool, Query(alias="relevantToMe")] = False,
    sort_by: Annotated[InvitationSortableField, Query(alias="sortBy")] = "submitted_at",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
    status_filter: Annotated[InvitationStatus | None, Query(alias="status")] = None,
    registration_type: Annotated[RegistrationType | None, Query(alias="registrationType")] = None,
    source: Annotated[RegistrationSource | None, Query(alias="source")] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> JSONResponse:
    """specs/invitations/spec.md "Employee Lists Invitations at Their
    Authorized Branches" (the default, branch-scoped mode) and "Caller
    Lists Invitations Relevant to Themselves via relevantToMe" —
    `relevantToMe=true` is a distinct personal worklist that bypasses the
    `invitations:view-all` branch-permission check entirely rather than
    narrowing it, so `X-Branch-ID` is read directly here (not via
    `require_branch_scope`'s `Depends()`) and only consulted when
    `relevantToMe` is not set (invitation-relevant-to-me-and-delegation/
    design.md "relevantToMe is implemented as a distinct query path, not a
    require_branch_scope variant"). The branch-scoped mode needs
    `invitations:view-all`, not `invitations:view`: a `host` holds only the
    latter and finds their work via `relevantToMe`
    (restrict-delegated-invitation-visibility).
    """
    page, page_size = pagination
    branch_scope: BranchScope | None = None
    default_host_role_id: uuid.UUID | None = None
    if not relevant_to_me:
        branch_scope = await require_branch_scope("invitations:view-all")(
            user=user, tenant_db=tenant_db, x_branch_id=x_branch_id
        )
    else:
        default_host_role_id = (await get_default_host_role(tenant_db)).id
    invitations, total = await service.list_invitations_page(
        tenant_db,
        branch_scope=branch_scope,
        relevant_to_user_id=user.id if relevant_to_me else None,
        default_host_role_id=default_host_role_id,
        status=status_filter.value if status_filter is not None else None,
        registration_type=registration_type.value if registration_type is not None else None,
        source=source.value if source is not None else None,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[await _to_list_item_out(invitation) for invitation in invitations],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/lookup-by-email",
    response_model=Envelope[InvitationLookupPrefillOut | None],
)
async def lookup_invitation_by_email(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(require_branch_scope("invitations:create"))],
    email: Annotated[EmailStr, Query()],
) -> JSONResponse:
    """Staff-authenticated prefill lookup for the create-invitation
    wizard's Primary Contact fields (add-invitation-lookup-by-email/
    proposal.md) — `data: null` on no match is a normal case, not an error,
    same convention `visitor_return_visit` already uses. `photoUrl` is
    always resolved; `idProofUrl` only when `user` holds `documents:view`
    at the matched invitation's branch (design.md).
    """
    result = await service.get_prefill_by_email(tenant_db, email, branch_scope, user)
    return success_response(data=result)


# --- API-12: public tracking lookup ------------------------------------------


@router.get(
    "/track",
    response_model=Envelope[InvitationTrackingOut | list[InvitationTrackingSummaryOut]],
)
@limiter.limit("20/minute")
async def track_invitation(
    request: Request,
    tenant: Annotated[Tenant, Depends(track_default_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
    tracking_id: Annotated[str | None, Query(alias="trackingId")] = None,
    email: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    if (tracking_id is None) == (email is None):
        return error_response(
            message="Provide exactly one of trackingId or email",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if tracking_id is not None:
        invitation = await service.track_by_tracking_id(tenant_db, tracking_id)
        current_approval_step = await service.get_current_approval_step(tenant_db, invitation)
        form_context = await service.get_invitation_detail_form_context(
            tenant_db, tenant, invitation.branch_id
        )
        return success_response(
            data=await _to_tracking_out(
                invitation, current_approval_step, form_context=form_context
            )
        )

    assert email is not None  # exactly one of the two is guaranteed set above
    invitations = await service.track_by_email(tenant_db, email)
    return success_response(
        data=[
            InvitationTrackingSummaryOut(tracking_id=inv.tracking_id, status=inv.status)
            for inv in invitations
        ]
    )


# --- add-invitation-lifecycle-actions: authenticated detail lookup -----------
# Registered after "/track" above so that literal path is matched first —
# FastAPI resolves routes for the same method in registration order, and
# "/track" would otherwise be swallowed by "/{invitation_id}"'s UUID
# validation (and fail with 422) before ever reaching this route.


@router.get(
    "/{invitation_id}",
    response_model=Envelope[InvitationDetailOut],
)
async def get_invitation_detail(
    invitation_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    tenant: Annotated[Tenant, Depends(get_tenant)],
) -> JSONResponse:
    """Authenticated, branch-scoped single-invitation detail view (spec.md
    "Authenticated Detail Lookup by Invitation ID") — the staff-facing
    counterpart of the public `GET /invitations/track` lookup above.

    Only a branch-wide viewer (`invitations:view-all`) or a participant — the
    same (a)–(e) rule as `relevantToMe` — may see it. A non-participant
    holding `invitations:view` gets the same 404 as a missing id, so an
    uninvolved host can't tell the invitation exists; a caller with no grant
    keeps the 403 `authorize_branch_id_tolerant` raises
    (restrict-delegated-invitation-visibility/design.md Decision 3).
    """
    invitation = await service.get_invitation_detail(tenant_db, invitation_id)
    if user.has_permission("invitations:view-all", invitation.branch_id):
        await authorize_branch_id_tolerant(
            tenant_db, user, "invitations:view-all", invitation.branch_id
        )
    else:
        default_host_role = await get_default_host_role(tenant_db)
        is_participant = await service.is_invitation_relevant_to(
            tenant_db,
            invitation.id,
            user_id=user.id,
            default_host_role_id=default_host_role.id,
        )
        if not is_participant:
            if user.has_permission("invitations:view", invitation.branch_id):
                logger.warning(
                    "invitation_detail_denied_non_participant",
                    invitation_id=str(invitation.id),
                )
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
            await authorize_branch_id_tolerant(
                tenant_db, user, "invitations:view-all", invitation.branch_id
            )
    current_approval_step = await service.get_current_approval_step(tenant_db, invitation)
    branch, department, building = await service.get_invitation_location(tenant_db, invitation)
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    include_documents = user.has_permission("documents:view", invitation.branch_id)
    return success_response(
        data=await _to_invitation_detail_out(
            invitation,
            current_approval_step,
            branch=branch,
            department=department,
            building=building,
            include_documents=include_documents,
            form_context=form_context,
        )
    )
