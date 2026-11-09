import json
import uuid
from datetime import date
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
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ValidationError
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import FormData
from starlette.datastructures import UploadFile as StarletteUploadFile

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.deps import (
    get_current_user,
    get_pagination,
    get_tenant,
    get_tenant_db,
    require_permission,
)
from vmss_api.core.idempotency import Idempotency, idempotency
from vmss_api.core.logging import logger
from vmss_api.core.middleware import enforce_upload_file_count
from vmss_api.core.public_access import flag_legacy_access, strict_public_access
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import (
    error_response,
    paginated_response,
    success_response,
    validation_error_response,
)
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.core.security import decode_token
from vmss_api.core.tenancy import get_token_payload
from vmss_api.devices.deps import make_device_dependency
from vmss_api.devices.models import Device
from vmss_api.invitations import service
from vmss_api.invitations.deps import track_default_tenant, track_default_tenant_db
from vmss_api.invitations.presenters import (
    _attach_devices,
    _device_diff,
    _to_badge_out,
    _to_check_in_out,
    _to_invitation_detail_out,
    _to_list_item_out,
    _to_qr_check_in_out,
    _to_tracking_out,
    to_invitation_out,
)
from vmss_api.invitations.schemas import (
    BadgeOut,
    CalendarDateRange,
    CalendarEventOut,
    CalendarFeedOut,
    CalendarScope,
    CarriedItemsSubmit,
    CheckInCodeRequest,
    ClearInvitationsOut,
    ClearInvitationsRequest,
    ExportFormat,
    InvitationCheckInOut,
    InvitationCreate,
    InvitationDenyRequest,
    InvitationDetailOut,
    InvitationEditRequest,
    InvitationExportDateRange,
    InvitationExtendRequest,
    InvitationListItemOut,
    InvitationLookupPrefillOut,
    InvitationOut,
    InvitationPrimaryContactCreate,
    InvitationQrCheckInOut,
    InvitationRescheduleRequest,
    InvitationRevertApprovalRequest,
    InvitationSortableField,
    InvitationStatus,
    InvitationTrackingOut,
    InvitationTrackingSummaryOut,
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
    optional_bearer_scheme,
    optional_caller,
    require_branch_scope,
)
from vmss_api.org_structure.service import get_default_host_role
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/invitations", tags=["invitations"])

# Module-level singleton (ruff B008: a `File(...)` call as a literal argument
# default is flagged the same as a mutable literal default) — an
# `individual` registration simply sends no files under this field name.
_MIN_PHONE_DIGITS = 7

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
        "branchId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "buildingId": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
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
        "branchId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "buildingId": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
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


async def _parse_prefixed_multipart_files(
    form_data: FormData, prefix: str, *, limit: int
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


# --- API-09: employee creates a fully completed invitation ------------------


@router.post(
    "",
    response_model=Envelope[InvitationOut],
    status_code=status.HTTP_201_CREATED,
    openapi_extra=_INVITATION_PAYLOAD_EXAMPLES,
)
async def create_invitation(
    request: Request,
    idem: Annotated[Idempotency, Depends(idempotency)],
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
                "back to `visitDetails.branchId` (or top-level `branchId`) when "
                "omitted; one of the two is required."
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
    cached = await idem.begin(
        tenant.id, "invitations", idempotency_key, caller=str(user.id), body=payload
    )
    if cached is not None:
        return cached

    try:
        create_payload = InvitationCreate.model_validate_json(payload)
    except ValidationError as exc:
        return validation_error_response(exc)

    branch_id = x_branch_id if x_branch_id is not None else create_payload.effective_branch_id
    if branch_id is None:
        return error_response(
            message=(
                "visitDetails.branchId in the payload (or the X-Branch-ID header) is "
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
    enforce_upload_file_count(form_data)
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
    await idem.store(response)
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
    invitation = await service.approve_invitation(
        tenant_db, invitation, tenant=tenant, actor_user_id=user.id
    )
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
        tenant_db, invitation, reason=payload.reason, tenant=tenant, actor_user_id=user.id
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


@router.patch(
    "/{invitation_id}/revert-approval",
    response_model=Envelope[InvitationOut],
)
async def revert_invitation_approval(
    invitation_id: uuid.UUID,
    payload: InvitationRevertApprovalRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Sends a mistakenly approved, not-yet-checked-in invitation back to
    `submitted` with a mandatory reason (spec.md "An Approved,
    Not-Yet-Checked-In Invitation Can Have Its Approval Reverted").
    """
    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(
        tenant_db, user, "invitations:revert-approval", invitation.branch_id
    )
    invitation = await service.revert_invitation_approval(
        tenant_db, invitation, user=user, reason=payload.reason, tenant=tenant
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_approval_reverted",
        entity_type="Invitation",
        entity_id=invitation.id,
        diff={"status": {"before": "approved", "after": "submitted"}, "reason": payload.reason},
    )
    current_approval_step = await service.get_current_approval_step(tenant_db, invitation)
    return success_response(data=to_invitation_out(invitation, current_approval_step))


# --- add-public-checkin-endpoint: public check-in by tracking ID ------------
# A second, minimal router mounted at /api/v2 (see api.py/main.py) — not a
# wholesale re-exposure of every v1 invitations route under v2, just this one
# endpoint (design.md Decision 1).

router_v2 = APIRouter(prefix="/invitations", tags=["invitations"])

# Optional `device-id` header (devices spec). Bound to each route's own
# tenant-session dependency so the lookup runs against the right schema.
_public_device = make_device_dependency(track_default_tenant_db)
_staff_device = make_device_dependency(get_tenant_db)


# Registered before `/{tracking_id}/check-in`: `/code/check-in` would otherwise be
# captured by it with `tracking_id="code"`.
@router_v2.patch(
    "/code/check-in",
    response_model=Envelope[InvitationQrCheckInOut],
)
@limiter.limit("10/minute")
async def check_in_by_code(
    request: Request,
    payload: CheckInCodeRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(track_default_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
    device: Annotated[Device | None, Depends(_public_device)],
    idem: Annotated[Idempotency, Depends(idempotency)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Use a fresh key per physical attempt so a retry of one "
                "check-in isn't deduped against a later check-out. See "
                "api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """Public, unauthenticated check-in with the numeric code sent by SMS in
    place of a QR (spec.md "Public Check-In by Code"). Same rules and
    response as `PATCH /api/v2/invitations/qr/{token}/check-in`; repeated
    failed codes from one IP lock that IP out (429).
    """
    cached = await idem.begin(
        tenant.id,
        "invitations",
        idempotency_key,
        caller=str(device.id) if device else "anonymous",
        body=payload.model_dump_json(),
    )
    if cached is not None:
        return cached

    invitation, message, changed = await service.check_in_by_code(
        tenant_db, payload.code, tenant=tenant, client_ip=get_remote_address(request), device=device
    )
    if changed:
        background_tasks.add_task(
            record_audit_log,
            tenant.schema_name,
            actor_user_id=None,
            action="invitation_code_checked_in",
            entity_type="Invitation",
            entity_id=invitation.id,
            diff=_device_diff(device),
        )
    branch, department, building = await service.get_invitation_location(tenant_db, invitation)
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    out = await _to_qr_check_in_out(
        invitation,
        branch=branch,
        department=department,
        building=building,
        form_context=form_context,
    )
    response = success_response(
        data=await _attach_devices(out, invitation, tenant_db), message=message
    )
    await idem.store(response)
    return response


@router_v2.patch(
    "/code/check-out",
    response_model=Envelope[InvitationQrCheckInOut],
)
@limiter.limit("10/minute")
async def check_out_by_code(
    request: Request,
    payload: CheckInCodeRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(track_default_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
    device: Annotated[Device | None, Depends(_public_device)],
    idem: Annotated[Idempotency, Depends(idempotency)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Fresh key per physical attempt. See api-conventions.md §3.",
        ),
    ] = None,
) -> JSONResponse:
    """Public, unauthenticated check-out with the SMS check-in code (spec.md
    "Public Check-Out by Code"). Same rules as the QR check-out: never
    expiry-blocked, 409 unless currently `checked_in`.
    """
    cached = await idem.begin(
        tenant.id,
        "invitations",
        idempotency_key,
        caller=str(device.id) if device else "anonymous",
        body=payload.model_dump_json(),
    )
    if cached is not None:
        return cached

    invitation, message = await service.check_out_by_code(
        tenant_db, payload.code, tenant=tenant, client_ip=get_remote_address(request), device=device
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action="invitation_code_checked_out",
        entity_type="Invitation",
        entity_id=invitation.id,
        diff=_device_diff(device),
    )
    branch, department, building = await service.get_invitation_location(tenant_db, invitation)
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    out = await _to_qr_check_in_out(
        invitation,
        branch=branch,
        department=department,
        building=building,
        form_context=form_context,
    )
    response = success_response(
        data=await _attach_devices(out, invitation, tenant_db), message=message
    )
    await idem.store(response)
    return response


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
    device: Annotated[Device | None, Depends(_public_device)],
    idem: Annotated[Idempotency, Depends(idempotency)],
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
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(optional_bearer_scheme)
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
    cached = await idem.begin(
        tenant.id,
        "invitations",
        idempotency_key,
        caller=str(device.id) if device else "anonymous",
        body="",
    )
    if cached is not None:
        return cached

    trusted = device is not None
    if not trusted:
        # public-endpoint-hardening: anonymous remote check-in by tracking ID
        # is allowed only while hardening is off (and flagged as deprecated).
        caller = await optional_caller(tenant_db, credentials)
        branch_id = await service.branch_of_tracking_id(tenant_db, tracking_id)
        trusted = (
            caller is not None
            and branch_id is not None
            and caller.has_permission("invitations:checkin", branch_id)
        )
        if not trusted and strict_public_access():
            return error_response(
                "A registered device or staff sign-in is required to check in",
                status.HTTP_401_UNAUTHORIZED,
            )

    invitation, changed = await service.check_in_invitation_by_tracking_id(
        tenant_db, tracking_id, tenant=tenant, device=device
    )
    if changed:
        background_tasks.add_task(
            record_audit_log,
            tenant.schema_name,
            actor_user_id=None,
            action="invitation_checked_in_public",
            entity_type="Invitation",
            entity_id=invitation.id,
            diff=_device_diff(device),
        )
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    out = await _to_check_in_out(invitation, form_context=form_context)
    response = success_response(data=await _attach_devices(out, invitation, tenant_db))
    await idem.store(response)
    return response if trusted else flag_legacy_access(response, feature_doc="invitations.md")


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
    device: Annotated[Device | None, Depends(_public_device)],
    idem: Annotated[Idempotency, Depends(idempotency)],
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
    performing a second transition (when zone access is on and the device is
    tied to one zone, that zone is still re-judged against the visit's current
    allowed zones: 403 if no longer allowed, visit stays checked in) — use
    `PATCH /api/v2/invitations/qr/{token}/check-out` to actually exit.
    Expiry is enforced on every entry, including a re-entry. Shares its
    already-checked-in state (and therefore this idempotent-no-op behavior)
    with `PATCH /api/v2/invitations/{trackingId}/check-in` — both endpoints
    read/write the same `checkInStatus` column, so a visitor checked in via
    one is recognized as already-checked-in by the other.
    """
    cached = await idem.begin(
        tenant.id,
        "invitations",
        idempotency_key,
        caller=str(device.id) if device else "anonymous",
        body="",
    )
    if cached is not None:
        return cached

    invitation, message, changed = await service.check_in_by_qr_token(
        tenant_db, token, tenant=tenant, device=device
    )
    if changed:
        background_tasks.add_task(
            record_audit_log,
            tenant.schema_name,
            actor_user_id=None,
            action="invitation_qr_checked_in",
            entity_type="Invitation",
            entity_id=invitation.id,
            diff=_device_diff(device),
        )
    branch, department, building = await service.get_invitation_location(tenant_db, invitation)
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    out = await _to_qr_check_in_out(
        invitation,
        branch=branch,
        department=department,
        building=building,
        form_context=form_context,
    )
    response = success_response(
        data=await _attach_devices(out, invitation, tenant_db), message=message
    )
    await idem.store(response)
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
    device: Annotated[Device | None, Depends(_public_device)],
    idem: Annotated[Idempotency, Depends(idempotency)],
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
    cached = await idem.begin(
        tenant.id,
        "invitations",
        idempotency_key,
        caller=str(device.id) if device else "anonymous",
        body="",
    )
    if cached is not None:
        return cached

    invitation, message = await service.check_out_by_qr_token(
        tenant_db, token, tenant=tenant, device=device
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action="invitation_qr_checked_out",
        entity_type="Invitation",
        entity_id=invitation.id,
        diff=_device_diff(device),
    )
    branch, department, building = await service.get_invitation_location(tenant_db, invitation)
    form_context = await service.get_invitation_detail_form_context(
        tenant_db, tenant, invitation.branch_id
    )
    out = await _to_qr_check_in_out(
        invitation,
        branch=branch,
        department=department,
        building=building,
        form_context=form_context,
    )
    response = success_response(
        data=await _attach_devices(out, invitation, tenant_db), message=message
    )
    await idem.store(response)
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
    device: Annotated[Device | None, Depends(_staff_device)],
    idem: Annotated[Idempotency, Depends(idempotency)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", description="Optional — see check-in.")
    ] = None,
) -> JSONResponse:
    """Transitions a `checked_in` invitation to `checked_out`, closing the
    visit (spec.md "A Checked-In Invitation Can Be Checked Out"). The optional
    `Idempotency-Key` is scoped to this route and caller, so a key reused from
    check-in can't replay the check-in response here.
    """
    cached = await idem.begin(
        tenant.id, "invitations", idempotency_key, caller=str(user.id), body=""
    )
    if cached is not None:
        return cached

    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(
        tenant_db, user, "invitations:checkout", invitation.branch_id
    )
    invitation = await service.check_out_invitation(
        tenant_db, invitation, user_id=user.id, tenant=tenant, device=device
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_checked_out",
        entity_type="Invitation",
        entity_id=invitation.id,
        diff=_device_diff(device),
    )
    out = await _attach_devices(to_invitation_out(invitation), invitation, tenant_db)
    response = success_response(data=out)
    await idem.store(response)
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
        actor_user_id=user.id,
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
    # Leaving `archived` restarts approval, so the response names the step
    # it now waits on (auto-checkout-and-archive-no-shows).
    current_approval_step = await service.get_current_approval_step(tenant_db, invitation)
    return success_response(data=to_invitation_out(invitation, current_approval_step))


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
    # Leaving `archived` restarts approval, so the response names the step
    # it now waits on (auto-checkout-and-archive-no-shows).
    current_approval_step = await service.get_current_approval_step(tenant_db, invitation)
    return success_response(data=to_invitation_out(invitation, current_approval_step))


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
        tenant_db,
        invitation,
        new_expires_at=payload.expires_at,
        tenant=tenant,
        actor_user_id=user.id,
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
    idem: Annotated[Idempotency, Depends(idempotency)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", description="Optional — see check-in.")
    ] = None,
) -> JSONResponse:
    """Issues a printable badge for an `approved`/`checked_in` invitation
    (spec.md "A Badge Can Be Printed for an Approved or Active Visit").
    """
    cached = await idem.begin(
        tenant.id, "invitations", idempotency_key, caller=str(user.id), body=""
    )
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
    await idem.store(response)
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


def _list_drill_down(
    visit_date_from: Annotated[date | None, Query(alias="visitDateFrom")] = None,
    visit_date_to: Annotated[date | None, Query(alias="visitDateTo")] = None,
    upcoming: Annotated[bool, Query()] = False,
    exclude_expired: Annotated[bool, Query(alias="excludeExpired")] = False,
    branch_id: Annotated[uuid.UUID | None, Query(alias="branchId")] = None,
) -> service.ListDrillDown | None:
    """specs/invitations/spec.md "Invitation List Supports Dashboard
    Drill-Down Filters" — shared by the list and the export. `None` when
    none is given, so the existing paths stay untouched.
    """
    if visit_date_from and visit_date_to and visit_date_from > visit_date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="visitDateFrom must not be later than visitDateTo",
        )
    drill_down = service.ListDrillDown(
        visit_date_from=visit_date_from,
        visit_date_to=visit_date_to,
        upcoming=upcoming,
        exclude_expired=exclude_expired,
        branch_id=branch_id,
    )
    return None if drill_down == service.ListDrillDown() else drill_down


def _drill_down_audit(drill_down: service.ListDrillDown | None) -> dict[str, Any]:
    """The export audit entry's drill-down filters, JSON-ready."""
    if drill_down is None:
        return {}
    return {
        "visit_date_from": drill_down.visit_date_from and drill_down.visit_date_from.isoformat(),
        "visit_date_to": drill_down.visit_date_to and drill_down.visit_date_to.isoformat(),
        "upcoming": drill_down.upcoming,
        "exclude_expired": drill_down.exclude_expired,
        "branch_id": drill_down.branch_id and str(drill_down.branch_id),
    }


@router.get(
    "",
    response_model=PaginatedEnvelope[InvitationListItemOut],
)
async def list_invitations(
    token_payload: Annotated[dict[str, Any], Depends(get_token_payload)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    drill_down: Annotated[service.ListDrillDown | None, Depends(_list_drill_down)],
    x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
    relevant_to_me: Annotated[bool, Query(alias="relevantToMe")] = False,
    sort_by: Annotated[InvitationSortableField, Query(alias="sortBy")] = "submitted_at",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
    status_filter: Annotated[InvitationStatus | None, Query(alias="status")] = None,
    registration_type: Annotated[RegistrationType | None, Query(alias="registrationType")] = None,
    source: Annotated[RegistrationSource | None, Query(alias="source")] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    purpose_of_visit: Annotated[str | None, Query(alias="purposeOfVisit", max_length=255)] = None,
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
    (restrict-delegated-invitation-visibility). `purposeOfVisit` is an
    exact-match filter ("Invitation List Supports a Purpose-of-Visit
    Filter") so the paged web board can filter server-side.
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
    if drill_down is not None and drill_down.branch_id is not None and not relevant_to_me:
        # Narrowing only: `branchId` must lie inside the caller's view-all
        # scope (404/403 otherwise). Under relevantToMe it just filters.
        await authorize_branch_id(tenant_db, user, "invitations:view-all", drill_down.branch_id)
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
        purpose_of_visit=purpose_of_visit,
        # The tenant id, not `get_tenant`: the tenant itself is only needed
        # for a visit-date filter's timezone, so the service loads it then.
        # (`get_tenant` here would also roll back the shared session under
        # the test client and expire objects the list tests still hold.)
        tenant_id=uuid.UUID(token_payload["tenant_id"]),
        drill_down=drill_down,
    )
    current_steps = await service.current_approval_steps(tenant_db, invitations)
    return paginated_response(
        data=[
            await _to_list_item_out(invitation, current_steps.get(invitation.id))
            for invitation in invitations
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


# --- add-clear-all-invitations ----------------------------------------------
# Registered before "/{invitation_id}" like "/export" below.


@router.post(
    "/clear-all",
    response_model=Envelope[ClearInvitationsOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def clear_invitations(
    payload: ClearInvitationsRequest,
    idem: Annotated[Idempotency, Depends(idempotency)],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    user: Annotated[User, Depends(require_permission("invitations:clear-all"))],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional. A retried request with the same key returns the "
                "original response instead of enqueueing a second run."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """Permanently deletes (after a verified backup) every invitation in the
    caller's tenant, or only those whose visit date falls in `month` /
    `fromDate`..`toDate`. Runs in the background.
    """
    cached = await idem.begin(
        tenant.id,
        "invitations",
        idempotency_key,
        caller=str(user.id),
        body=payload.model_dump_json(),
    )
    if cached is not None:
        return cached
    try:
        result = await service.request_clear_invitations(tenant, user, payload)
    except service.ClearInProgressError:
        return error_response(
            message="A clear or purge is already running for this tenant",
            status_code=status.HTTP_409_CONFLICT,
        )
    response = success_response(data=result, status_code=status.HTTP_202_ACCEPTED)
    await idem.store(response)
    return response


# --- add-invitation-export ---------------------------------------------------
# Registered before "/{invitation_id}" for the same reason as "/track" below.


@router.get(
    "/export",
    response_class=Response,
    responses={
        200: {
            "description": "The matching invitations as a file, one row per visitor.",
            "content": {
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}
                },
            },
        }
    },
)
async def export_invitations(
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(require_branch_scope("invitations:export"))],
    export_format: Annotated[ExportFormat, Query(alias="format")] = ExportFormat.csv,
    relevant_to_me: Annotated[bool, Query(alias="relevantToMe")] = False,
    status_filter: Annotated[InvitationStatus | None, Query(alias="status")] = None,
    registration_type: Annotated[RegistrationType | None, Query(alias="registrationType")] = None,
    source: Annotated[RegistrationSource | None, Query(alias="source")] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    purpose_of_visit: Annotated[str | None, Query(alias="purposeOfVisit", max_length=255)] = None,
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    drill_down: Annotated[service.ListDrillDown | None, Depends(_list_drill_down)] = None,
) -> Response:
    """specs/invitation-export/spec.md — a raw file download, so it's the
    documented exception to `success_response`; every error path is still
    the JSON envelope. Unlike `GET /invitations`, `relevantToMe` narrows the
    `invitations:export` branch scope rather than replacing it
    (add-invitation-export/design.md Decision 2), so a `host` without the
    export grant can't reach it through their personal worklist.
    """
    try:
        date_range = InvitationExportDateRange(date_from=date_from, date_to=date_to)
    except ValidationError as exc:
        return validation_error_response(exc)

    if drill_down is not None and drill_down.branch_id is not None:
        await authorize_branch_id(tenant_db, user, "invitations:export", drill_down.branch_id)
    default_host_role_id = (await get_default_host_role(tenant_db)).id if relevant_to_me else None
    filters: dict[str, Any] = {
        "relevant_to_me": relevant_to_me,
        "status": status_filter.value if status_filter is not None else None,
        "registration_type": registration_type.value if registration_type is not None else None,
        "source": source.value if source is not None else None,
        "search": search,
        "purpose_of_visit": purpose_of_visit,
        "date_from": date_from.isoformat() if date_from is not None else None,
        "date_to": date_to.isoformat() if date_to is not None else None,
        **_drill_down_audit(drill_down),
    }
    try:
        export_file = await service.export_invitations(
            tenant_db,
            tenant,
            branch_scope=branch_scope,
            relevant_to_user_id=user.id if relevant_to_me else None,
            default_host_role_id=default_host_role_id,
            status=filters["status"],
            registration_type=filters["registration_type"],
            source=filters["source"],
            search=search,
            purpose_of_visit=purpose_of_visit,
            date_range=date_range,
            export_format=export_format,
            drill_down=drill_down,
        )
    except service.ExportTooLargeError as exc:
        logger.warning("invitations_export_too_large", format=export_format.value)
        return error_response(message=str(exc), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    audit_filters = {key: value for key, value in filters.items() if value not in (None, False)}
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitations_exported",
        entity_type="Invitation",
        diff={
            "filters": audit_filters,
            "format": export_format.value,
            "row_count": export_file.row_count,
        },
    )
    logger.info(
        "invitations_exported",
        format=export_format.value,
        row_count=export_file.row_count,
        # `search` can hold a visitor's name — kept in the audit entry, not
        # the log line (logging-observability.md §2).
        filters={key: value for key, value in audit_filters.items() if key != "search"},
    )
    return Response(
        content=export_file.content,
        media_type=export_file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{export_file.filename}"'},
    )


# --- add-staff-calendar ------------------------------------------------------
# Registered before "/{invitation_id}" for the same reason as "/track" below.


@router.get(
    "/calendar",
    response_model=Envelope[CalendarFeedOut],
)
async def get_invitation_calendar(
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    scope: Annotated[CalendarScope, Query()] = CalendarScope.auto,
    statuses: Annotated[list[InvitationStatus] | None, Query(alias="status")] = None,
    per_day_limit: Annotated[int | None, Query(alias="perDayLimit", ge=1, le=100)] = None,
    x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
) -> JSONResponse:
    """specs/invitation-calendar — no `require_permission` here: `mine` is
    open to any authenticated staff user (like `relevantToMe`), and whether
    `branch` applies is only known once `scope=auto` is resolved, so the
    `invitations:view-all` check happens in the service (design.md D2).
    Bounded by the 42-day range and a 1,000-event cap with exact `days`
    totals instead of page/pageSize (design.md D1).
    """
    try:
        date_range = CalendarDateRange(date_from=date_from, date_to=date_to)
    except ValidationError as exc:
        return validation_error_response(exc)

    feed = await service.get_calendar_feed(
        tenant_db,
        tenant,
        user,
        date_range=date_range,
        scope=scope,
        statuses=statuses,
        x_branch_id=x_branch_id,
        per_day_limit=per_day_limit,
    )
    return success_response(data=feed)


@router.get(
    "/calendar/day",
    response_model=PaginatedEnvelope[CalendarEventOut],
)
async def get_invitation_calendar_day(
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    day: Annotated[date, Query(alias="date")],
    scope: Annotated[CalendarScope, Query()] = CalendarScope.auto,
    statuses: Annotated[list[InvitationStatus] | None, Query(alias="status")] = None,
    x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
) -> JSONResponse:
    """specs/invitation-calendar "One Day's Visits Are Available Page by
    Page" — the same scope, branch, status and order rules as the feed
    (improve-calendar-scale-and-theme-switch design.md A1/A3). The applied
    scope rides in `X-Calendar-Scope`, since the standard paginated
    envelope has no slot for it.
    """
    page, page_size = pagination
    events, total, applied = await service.get_calendar_day_page(
        tenant_db,
        tenant,
        user,
        day=day,
        scope=scope,
        statuses=statuses,
        x_branch_id=x_branch_id,
        page=page,
        page_size=page_size,
    )
    result = paginated_response(data=events, page=page, page_size=page_size, total=total)
    result.headers["X-Calendar-Scope"] = applied
    return result


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


@router.get(
    "/lookup-by-phone",
    response_model=Envelope[InvitationLookupPrefillOut | None],
)
async def lookup_invitation_by_phone(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(require_branch_scope("invitations:create"))],
    phone: Annotated[str, Query(min_length=1, max_length=50)],
) -> JSONResponse:
    """Phone counterpart of `lookup-by-email`
    (reception-phone-prefill-lookup/proposal.md) — same permission,
    branch scoping, and `documents:view` gate on `idProofUrl`; `email` is
    included so the Reception form can fill it from a phone number.
    """
    digits = service.phone_digits(phone)
    if len(digits) < _MIN_PHONE_DIGITS:
        return error_response(
            message=f"phone must contain at least {_MIN_PHONE_DIGITS} digits",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    result = await service.get_prefill_by_phone(tenant_db, digits, branch_scope, user)
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
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(optional_bearer_scheme)
    ] = None,
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
    # public-endpoint-hardening: listing an address's tracking IDs needs proof
    # the caller controls that address (an OTP proof token) once hardening is
    # on; until then it's served as before and flagged as deprecated.
    proven = _proves_ownership_of(credentials, email)
    if not proven and strict_public_access():
        return error_response(
            "Verify this email address with a one-time code first",
            status.HTTP_401_UNAUTHORIZED,
        )
    invitations = await service.track_by_email(tenant_db, email)
    response = success_response(
        data=[
            InvitationTrackingSummaryOut(tracking_id=inv.tracking_id, status=inv.status)
            for inv in invitations
        ]
    )
    return response if proven else flag_legacy_access(response, feature_doc="invitations.md")


def _proves_ownership_of(credentials: HTTPAuthorizationCredentials | None, email: str) -> bool:
    """A valid `identity_verified` proof token (OTP verify) issued for this
    same email address. Never raises: anything else is simply "no proof"."""
    if credentials is None:
        return False
    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        return False
    subject = str(payload.get("sub", ""))
    return (
        payload.get("type") == "identity_verified"
        and subject.strip().lower() == email.strip().lower()
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
    out = await _to_invitation_detail_out(
        invitation,
        current_approval_step,
        branch=branch,
        department=department,
        building=building,
        include_documents=include_documents,
        form_context=form_context,
    )
    return success_response(data=await _attach_devices(out, invitation, tenant_db))
