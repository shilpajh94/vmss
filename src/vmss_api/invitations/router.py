import json
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.approvals.schemas import CurrentApprovalStepOut
from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_pagination, get_tenant, get_tenant_db
from vmss_api.core.rate_limit import limiter
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import (
    error_response,
    mark_deprecated,
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
    ConsentsSubmit,
    InvitationCreate,
    InvitationDenyRequest,
    InvitationDetailOut,
    InvitationExtendRequest,
    InvitationListItemOut,
    InvitationOut,
    InvitationPrimaryContactCreate,
    InvitationQrCheckInOut,
    InvitationRescheduleRequest,
    InvitationSortableField,
    InvitationTrackingOut,
    InvitationTrackingSummaryOut,
    InvitationVehicleOut,
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
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/invitations", tags=["invitations"])

_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
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
    "consents": {
        "termsAccepted": True,
        "dataProcessingAccepted": True,
        "safetyGuidelinesAccepted": True,
    },
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
    "consents": {
        "termsAccepted": True,
        "dataProcessingAccepted": True,
        "safetyGuidelinesAccepted": True,
    },
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
    """
    nested: list[tuple[str, type[BaseModel]]] = [
        ("primaryContact", InvitationPrimaryContactCreate),
        ("each entry in visitors", VisitorSubmit),
        ("visitDetails", VisitDetailsSubmit),
        ("carriedItems", CarriedItemsSubmit),
        ("each entry in vehicles", VehicleSubmit),
        ("consents", ConsentsSubmit),
    ]
    lines = [
        "Required fields (generated from the schemas below, not hand-typed):",
        f"- Top level: {', '.join(InvitationCreate.model_json_schema()['required'])}",
    ]
    for label, model in nested:
        required = model.model_json_schema().get("required", [])
        lines.append(f"- {label}: {', '.join(required) if required else '(none required)'}")
    lines.append(
        "Note: `email`/`phone` are each individually optional above, but at "
        "least one is required on every contact/visitor entry — enforced by "
        "a cross-field rule, not a schema-level `required` marker."
    )
    return "\n".join(lines)


# Rendered directly in Swagger's Parameters table for the `payload` field —
# unlike `_INVITATION_PAYLOAD_EXAMPLES` above, a Form/File parameter's own
# `description` is confirmed to render regardless of content type and without
# opening "Try it out" (document-invitation-create-payload-shape/design.md
# Decision 1).
_PAYLOAD_DESCRIPTION = (
    "JSON-encoded InvitationCreate: registrationType, primaryContact (with "
    "idProofType), visitors, visitDetails, carriedItems, vehicles, consents "
    "(camelCase).\n\n"
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
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        current_approval_step=current_approval_step,
    )


def _to_qr_check_in_out(invitation) -> InvitationQrCheckInOut:
    return InvitationQrCheckInOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        check_in_status=invitation.check_in_status,
        registration_type=invitation.registration_type,
        source=invitation.source,
        visitor_category_id=invitation.visitor_category_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        primary_contact_email=invitation.primary_contact_email,
        primary_contact_phone=invitation.primary_contact_phone,
        host_id=invitation.host_id,
        host_name_or_email=invitation.host_name_or_email,
        purpose_of_visit=invitation.purpose_of_visit,
        department_to_visit=invitation.department_to_visit,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        expected_duration=invitation.expected_duration,
        additional_notes=invitation.additional_notes,
        carried_items=invitation.carried_items,
        carried_items_description=invitation.carried_items_description,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        checked_in_at=invitation.checked_in_at,
        checked_out_at=invitation.checked_out_at,
        expires_at=invitation.expires_at,
        visitors=[
            InvitationVisitorOut(
                id=v.id,
                full_name=v.full_name,
                email=v.email,
                phone=v.phone,
                id_proof_type=v.id_proof_type,
            )
            for v in invitation.visitors
        ],
        vehicles=[
            InvitationVehicleOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                license_plate=v.license_plate,
                make_model=v.make_model,
                color=v.color,
            )
            for v in invitation.vehicles
        ],
    )


def _to_list_item_out(invitation) -> InvitationListItemOut:
    return InvitationListItemOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        registration_type=RegistrationType(invitation.registration_type),
        source=RegistrationSource(invitation.source),
        status=invitation.status,
        visitor_category_id=invitation.visitor_category_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        purpose_of_visit=invitation.purpose_of_visit,
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
    )


def _to_tracking_out(
    invitation, current_approval_step: CurrentApprovalStepOut | None = None
) -> InvitationTrackingOut:
    return InvitationTrackingOut(
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        registration_type=invitation.registration_type,
        source=invitation.source,
        visitor_category_id=invitation.visitor_category_id,
        current_approval_step=current_approval_step,
        primary_contact_full_name=invitation.primary_contact_full_name,
        purpose_of_visit=invitation.purpose_of_visit,
        host_name_or_email=invitation.host_name_or_email,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        expected_duration=invitation.expected_duration,
        department_to_visit=invitation.department_to_visit,
        additional_notes=invitation.additional_notes,
        carried_items=invitation.carried_items,
        carried_items_description=invitation.carried_items_description,
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
        visitors=[
            InvitationVisitorOut(
                id=v.id,
                full_name=v.full_name,
                email=v.email,
                phone=v.phone,
                id_proof_type=v.id_proof_type,
            )
            for v in invitation.visitors
        ],
        vehicles=[
            InvitationVehicleOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                license_plate=v.license_plate,
                make_model=v.make_model,
                color=v.color,
            )
            for v in invitation.vehicles
        ],
    )


def _to_invitation_detail_out(
    invitation, current_approval_step: CurrentApprovalStepOut | None = None
) -> InvitationDetailOut:
    return InvitationDetailOut(
        id=invitation.id,
        branch_id=invitation.branch_id,
        source=RegistrationSource(invitation.source),
        created_by_user_id=invitation.created_by_user_id,
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        registration_type=invitation.registration_type,
        visitor_category_id=invitation.visitor_category_id,
        current_approval_step=current_approval_step,
        primary_contact_full_name=invitation.primary_contact_full_name,
        purpose_of_visit=invitation.purpose_of_visit,
        host_name_or_email=invitation.host_name_or_email,
        host_id=invitation.host_id,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        expected_duration=invitation.expected_duration,
        department_to_visit=invitation.department_to_visit,
        additional_notes=invitation.additional_notes,
        carried_items=invitation.carried_items,
        carried_items_description=invitation.carried_items_description,
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
            InvitationVisitorOut(
                id=v.id,
                full_name=v.full_name,
                email=v.email,
                phone=v.phone,
                id_proof_type=v.id_proof_type,
            )
            for v in invitation.visitors
        ],
        vehicles=[
            InvitationVehicleOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                license_plate=v.license_plate,
                make_model=v.make_model,
                color=v.color,
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


def _idempotency_cache_key(tenant_id: uuid.UUID, idempotency_key: str) -> str:
    return f"vmss:{tenant_id}:invitations:idempotency:{idempotency_key}"


async def _cached_response(
    tenant_id: uuid.UUID, idempotency_key: str | None
) -> JSONResponse | None:
    """api-conventions.md §3 — a retried multipart submission with the same
    `Idempotency-Key` returns the original response instead of re-processing
    (which would otherwise create duplicate visitor rows and send a second
    confirmation email).
    """
    if idempotency_key is None:
        return None
    redis = await get_redis()
    cached = await redis.get(_idempotency_cache_key(tenant_id, idempotency_key))
    if cached is None:
        return None
    payload = json.loads(cached)
    return JSONResponse(content=payload["body"], status_code=payload["status"])


async def _cache_response(
    tenant_id: uuid.UUID, idempotency_key: str | None, response: JSONResponse
) -> None:
    if idempotency_key is None:
        return
    redis = await get_redis()
    await redis.set(
        _idempotency_cache_key(tenant_id, idempotency_key),
        json.dumps({"status": response.status_code, "body": json.loads(bytes(response.body))}),
        ex=_IDEMPOTENCY_TTL_SECONDS,
    )


# --- API-09: employee creates a fully completed invitation ------------------


@router.post(
    "",
    response_model=Envelope[InvitationOut],
    status_code=status.HTTP_201_CREATED,
    openapi_extra=_INVITATION_PAYLOAD_EXAMPLES,
)
async def create_invitation(
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: Annotated[str, Form(description=_PAYLOAD_DESCRIPTION)],
    primary_contact_id_proof_file: Annotated[
        UploadFile,
        File(
            description=(
                "Primary contact's ID-proof image/PDF upload — paired with "
                "`payload.primaryContact`. See `visitorIdProofFiles` below "
                "for the co-visitor equivalent."
            )
        ),
    ],
    visitor_id_proof_files: list[UploadFile] = _NO_VISITOR_FILES,
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

    primary_content = await primary_contact_id_proof_file.read()
    visitor_contents = [await f.read() for f in visitor_id_proof_files]

    invitation = await service.create_invitation(
        tenant_db,
        create_payload,
        branch_id=branch.id,
        created_by_user_id=user.id,
        tenant=tenant,
        primary_contact_id_proof_content=primary_content,
        visitor_id_proof_contents=visitor_contents,
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


@router.patch(
    "/{invitation_id}/check-in",
    response_model=Envelope[InvitationOut],
)
async def check_in_invitation(
    invitation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional. Omitting it simply forgoes retry-dedup safety — a "
                "retried request with no key may check in twice. See "
                "api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """Transitions an `approved` invitation to `checked_in` (spec.md "An
    Approved Invitation Can Be Checked In"), rejected with 409 while
    `watchlistFlagged` is set and not yet overridden (spec.md "A
    Watchlist-Flagged Invitation Blocks Check-In Until Overridden").

    **Deprecated** — see `PATCH /api/v2/invitations/{trackingId}/check-in`
    for the public, tracking-ID-keyed replacement
    (add-public-checkin-endpoint/design.md). This route stays fully
    functional during the migration window; api-conventions.md §2 governs
    its eventual removal.
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation = await service.get_invitation(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:checkin", invitation.branch_id)
    invitation = await service.check_in_invitation(
        tenant_db, invitation, user_id=user.id, tenant=tenant
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_checked_in",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    response = success_response(data=to_invitation_out(invitation))
    await _cache_response(tenant.id, idempotency_key, response)
    return mark_deprecated(response)


# --- add-public-checkin-endpoint: public check-in by tracking ID ------------
# A second, minimal router mounted at /api/v2 (see api.py/main.py) — not a
# wholesale re-exposure of every v1 invitations route under v2, just this one
# endpoint (design.md Decision 1).

router_v2 = APIRouter(prefix="/invitations", tags=["invitations"])


@router_v2.patch(
    "/{tracking_id}/check-in",
    response_model=Envelope[InvitationOut],
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
                "Optional. Omitting it simply forgoes retry-dedup safety — a "
                "retried request with no key may check in twice. See "
                "api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """Public, unauthenticated counterpart of
    `PATCH /api/v1/invitations/{id}/check-in`, keyed by the invitation's
    `tracking_id` instead of its internal UUID `id` (spec.md "An Approved
    Invitation Can Be Publicly Checked In By Tracking ID") — for a kiosk or
    the visitor's own device checking in from the QR/badge code, with no
    staff bearer token. Same 409/404/`Idempotency-Key` behavior as the
    staff-authenticated route; no branch authorization check, since there is
    no authenticated caller to check it against.
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation = await service.check_in_invitation_by_tracking_id(
        tenant_db, tracking_id, tenant=tenant
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action="invitation_checked_in_public",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    response = success_response(data=to_invitation_out(invitation))
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
    """Public, unauthenticated QR check-in
    (`add-qr-checkin-security/design.md`) — scanning an invitation's
    encrypted check-in token toggles its `checkInStatus`: `unused` or
    `checked_out` (currently outside) -> `checked_in` on a valid scan,
    `checked_in` -> `checked_out` on the next scan of that same token.
    Cycles for as many entry/exit round trips as the visitor makes during
    their visit (e.g. leaving for lunch and returning) — `checked_out` is
    not a dead end, and expiry is enforced on every entry, including a
    re-entry. Distinct from
    `PATCH /api/v2/invitations/{trackingId}/check-in` — that route stays
    the manual desk fallback, keyed by the human-readable tracking ID and
    unaffected by this one.
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation, message = await service.check_in_by_qr_token(tenant_db, token, tenant=tenant)
    action = (
        "invitation_qr_checked_in"
        if invitation.check_in_status == "checked_in"
        else ("invitation_qr_checked_out")
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action=action,
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    response = success_response(data=_to_qr_check_in_out(invitation), message=message)
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
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    registration_type: Annotated[RegistrationType | None, Query(alias="registrationType")] = None,
    source: Annotated[RegistrationSource | None, Query(alias="source")] = None,
) -> JSONResponse:
    """specs/invitations/spec.md "Employee Lists Invitations at Their
    Authorized Branches" (the default, branch-scoped mode) and "Caller
    Lists Invitations Relevant to Themselves via relevantToMe" —
    `relevantToMe=true` is a distinct personal worklist that bypasses the
    `invitations:view` branch-permission check entirely rather than
    narrowing it, so `X-Branch-ID` is read directly here (not via
    `require_branch_scope`'s `Depends()`) and only consulted when
    `relevantToMe` is not set (invitation-relevant-to-me-and-delegation/
    design.md "relevantToMe is implemented as a distinct query path, not a
    require_branch_scope variant").
    """
    page, page_size = pagination
    branch_scope: BranchScope | None = None
    if not relevant_to_me:
        branch_scope = await require_branch_scope("invitations:view")(
            user=user, tenant_db=tenant_db, x_branch_id=x_branch_id
        )
    invitations, total = await service.list_invitations_page(
        tenant_db,
        branch_scope=branch_scope,
        relevant_to_user_id=user.id if relevant_to_me else None,
        status=status_filter,
        registration_type=registration_type.value if registration_type is not None else None,
        source=source.value if source is not None else None,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[_to_list_item_out(invitation) for invitation in invitations],
        page=page,
        page_size=page_size,
        total=total,
    )


# --- API-12: public tracking lookup ------------------------------------------


@router.get(
    "/track",
    response_model=Envelope[InvitationTrackingOut | list[InvitationTrackingSummaryOut]],
)
@limiter.limit("20/minute")
async def track_invitation(
    request: Request,
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
        return success_response(data=_to_tracking_out(invitation, current_approval_step))

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
) -> JSONResponse:
    """Authenticated, branch-scoped single-invitation detail view (spec.md
    "Authenticated Detail Lookup by Invitation ID") — the staff-facing
    counterpart of the public `GET /invitations/track` lookup above.
    """
    invitation = await service.get_invitation_detail(tenant_db, invitation_id)
    await authorize_branch_id_tolerant(tenant_db, user, "invitations:view", invitation.branch_id)
    current_approval_step = await service.get_current_approval_step(tenant_db, invitation)
    return success_response(data=_to_invitation_detail_out(invitation, current_approval_step))
