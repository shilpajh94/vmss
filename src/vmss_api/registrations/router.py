import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.core.config import settings
from vmss_api.core.idempotency import cache_response as _core_cache_response
from vmss_api.core.idempotency import cached_response as _core_cached_response
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import error_response, success_response
from vmss_api.core.schemas import Envelope
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.router import (
    _INVITATION_PAYLOAD_EXAMPLES,
    _NO_VISITOR_FILES,
    _NO_VISITOR_PHOTOS,
    _parse_prefixed_multipart_files,
    to_invitation_out,
)
from vmss_api.invitations.router import _PAYLOAD_DESCRIPTION as _INVITATION_PAYLOAD_DESCRIPTION
from vmss_api.registrations import service
from vmss_api.registrations.deps import (
    RegistrationDeviceContext,
    get_registration_device,
    get_registration_tenant_db,
)
from vmss_api.registrations.schemas import WalkInRegistrationCreate, WalkInRegistrationOut

router = APIRouter(prefix="/registrations", tags=["registrations"])

# Byte-for-byte the same contract `POST /invitations` documents (design.md
# Decision 2) — reused rather than restated so the two endpoints' docs can
# never drift apart the way two hand-maintained copies eventually would.
_PAYLOAD_DESCRIPTION = _INVITATION_PAYLOAD_DESCRIPTION


async def _cached_response(
    tenant_id: uuid.UUID, idempotency_key: str | None
) -> JSONResponse | None:
    """api-conventions.md §3 — a flaky mobile connection retrying a walk-in
    submission with the same `Idempotency-Key` gets the original response
    back instead of creating a second registration.
    """
    return await _core_cached_response(tenant_id, "registrations", idempotency_key)


async def _cache_response(
    tenant_id: uuid.UUID, idempotency_key: str | None, response: JSONResponse
) -> None:
    await _core_cache_response(tenant_id, "registrations", idempotency_key, response)


@router.post(
    "/walk-in",
    response_model=Envelope[WalkInRegistrationOut],
    status_code=status.HTTP_201_CREATED,
    openapi_extra=_INVITATION_PAYLOAD_EXAMPLES,
)
@limiter.limit("20/minute")
async def create_walk_in_registration(
    request: Request,
    background_tasks: BackgroundTasks,
    device: Annotated[RegistrationDeviceContext, Depends(get_registration_device)],
    tenant_db: Annotated[AsyncSession, Depends(get_registration_tenant_db)],
    payload: Annotated[str, Form(description=_PAYLOAD_DESCRIPTION)],
    primary_contact_id_proof_file: Annotated[
        UploadFile | None,
        File(
            description=(
                "Primary contact's ID-proof image/PDF upload — paired with "
                "`payload.primaryContact`. Required by default, but only "
                "when the resolved branch's published Form Builder "
                "configuration marks ID proof active/required. See "
                "`visitorIdProofFiles` below for the co-visitor equivalent."
            )
        ),
    ] = None,
    primary_contact_photo_file: Annotated[
        UploadFile | None,
        File(
            description=(
                "Profile photo for the primary contact (JPEG/PNG only) — "
                "paired with `payload.primaryContact`. Required by default, "
                "but only when the resolved branch's published Form "
                "Builder configuration marks it active/required. See "
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
                "retried request with no key may create a second "
                "registration. See api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """A visitor registers themselves on arrival, with no staff bearer token
    and no prior invitation — authenticated instead by the device credential
    a branch's kiosk/app instance presents (`X-Device-Key`). Accepts the
    identical multipart contract `POST /invitations` does (spec.md "Walk-in
    registration accepts the same visit-record contract as staff
    pre-registration") and creates the same kind of record, tagged
    `source: "visitor_walk_in"`, with no check-in performed
    (`add-walkin-visitor-registration/design.md` Non-Goals).

    An admin-defined repeatable group's own `file_upload`-typed field
    follows the same `groupFieldFiles[<groupKey>]` convention documented on
    `POST /invitations` (`invitations/router.py::create_invitation`) — a
    multipart list part, order-matched to that group's
    `payload.groupValues[<groupKey>]` instances, read via `request.form()`
    since the group key is branch-specific and unknown at route-declaration
    time. An inline (non-grouped) admin-defined `file_upload` field follows
    the identical `primaryContactCustomFieldFiles[<fieldKey>]`/
    `visitorCustomFieldFiles[<fieldKey>]`/`vehicleCustomFieldFiles[<fieldKey>]`/
    `customFieldFiles[<fieldKey>]` contract also documented there.
    """
    cached = await _cached_response(device.tenant.id, idempotency_key)
    if cached is not None:
        return cached

    try:
        create_payload = WalkInRegistrationCreate.model_validate_json(payload)
    except ValidationError as exc:
        return error_response(message=str(exc), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    # Same "reject an oversized upload before it's fully buffered" guard
    # `POST /invitations` applies (file-upload-handling.md §1) — this
    # endpoint accepts the identical multipart contract, so it reuses the
    # identical limits rather than risking them drifting apart.
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

    # None of these are declared parameters above since the field/group key
    # inside each `[...]` is branch-specific (see the docstring). Starlette
    # caches the parsed multipart body on `request`, so this reuses the same
    # parse the `payload`/`primary_contact_*`/`visitor_*` params already
    # triggered rather than re-reading the request body — identical to
    # `invitations/router.py::create_invitation`.
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

    invitation = await service.create_walk_in_registration(
        tenant_db,
        create_payload,
        branch_id=device.branch_id,
        tenant=device.tenant,
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
        device.tenant.schema_name,
        actor_user_id=None,
        action="walk_in_registration_created",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    current_approval_step = await invitations_service.get_current_approval_step(
        tenant_db, invitation
    )
    response = success_response(
        data=to_invitation_out(invitation, current_approval_step),
        status_code=status.HTTP_201_CREATED,
    )
    await _cache_response(device.tenant.id, idempotency_key, response)
    return response
