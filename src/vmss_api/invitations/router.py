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

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_pagination, get_tenant, get_tenant_db
from vmss_api.core.rate_limit import limiter
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import error_response, paginated_response, success_response
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.invitations import service
from vmss_api.invitations.deps import track_default_tenant_db
from vmss_api.invitations.schemas import (
    CarriedItemsSubmit,
    ConsentsSubmit,
    InvitationCreate,
    InvitationListItemOut,
    InvitationOut,
    InvitationPrimaryContactCreate,
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
)
from vmss_api.org_structure.deps import authorize_branch_id, require_branch_scope
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


def _to_invitation_out(invitation) -> InvitationOut:
    return InvitationOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        registration_type=RegistrationType(invitation.registration_type),
        source=RegistrationSource(invitation.source),
        status=invitation.status,
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
    )


def _to_list_item_out(invitation) -> InvitationListItemOut:
    return InvitationListItemOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        registration_type=RegistrationType(invitation.registration_type),
        source=RegistrationSource(invitation.source),
        status=invitation.status,
        primary_contact_full_name=invitation.primary_contact_full_name,
        purpose_of_visit=invitation.purpose_of_visit,
        expires_at=invitation.expires_at,
        submitted_at=invitation.submitted_at,
        approved_at=invitation.approved_at,
    )


def _to_tracking_out(invitation) -> InvitationTrackingOut:
    return InvitationTrackingOut(
        tracking_id=invitation.tracking_id,
        status=invitation.status,
        registration_type=invitation.registration_type,
        source=invitation.source,
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
    response = success_response(
        data=_to_invitation_out(invitation),
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
    await authorize_branch_id(tenant_db, user, "invitations:approve", invitation.branch_id)
    invitation = await service.approve_invitation(tenant_db, invitation, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_approved",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    return success_response(data=_to_invitation_out(invitation))


# --- Employee listing ---------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedEnvelope[InvitationListItemOut],
)
async def list_invitations(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_scope: Annotated[BranchScope, Depends(require_branch_scope("invitations:view"))],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[InvitationSortableField, Query(alias="sortBy")] = "submitted_at",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    registration_type: Annotated[RegistrationType | None, Query(alias="registrationType")] = None,
    source: Annotated[RegistrationSource | None, Query(alias="source")] = None,
) -> JSONResponse:
    page, page_size = pagination
    invitations, total = await service.list_invitations_page(
        tenant_db,
        branch_scope=branch_scope,
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
        return success_response(data=_to_tracking_out(invitation))

    assert email is not None  # exactly one of the two is guaranteed set above
    invitations = await service.track_by_email(tenant_db, email)
    return success_response(
        data=[
            InvitationTrackingSummaryOut(tracking_id=inv.tracking_id, status=inv.status)
            for inv in invitations
        ]
    )
