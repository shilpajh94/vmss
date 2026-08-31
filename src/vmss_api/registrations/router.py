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
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.core.rate_limit import limiter
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import error_response, success_response
from vmss_api.core.schemas import Envelope
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.router import (
    _INVITATION_PAYLOAD_EXAMPLES,
    _NO_VISITOR_FILES,
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

_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

# Byte-for-byte the same contract `POST /invitations` documents (design.md
# Decision 2) — reused rather than restated so the two endpoints' docs can
# never drift apart the way two hand-maintained copies eventually would.
_PAYLOAD_DESCRIPTION = _INVITATION_PAYLOAD_DESCRIPTION


def _idempotency_cache_key(tenant_id: uuid.UUID, idempotency_key: str) -> str:
    return f"vmss:{tenant_id}:registrations:idempotency:{idempotency_key}"


async def _cached_response(
    tenant_id: uuid.UUID, idempotency_key: str | None
) -> JSONResponse | None:
    """api-conventions.md §3 — a flaky mobile connection retrying a walk-in
    submission with the same `Idempotency-Key` gets the original response
    back instead of creating a second registration.
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
    """
    cached = await _cached_response(device.tenant.id, idempotency_key)
    if cached is not None:
        return cached

    try:
        create_payload = WalkInRegistrationCreate.model_validate_json(payload)
    except ValidationError as exc:
        return error_response(message=str(exc), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    primary_content = await primary_contact_id_proof_file.read()
    visitor_contents = [await f.read() for f in visitor_id_proof_files]

    invitation = await service.create_walk_in_registration(
        tenant_db,
        create_payload,
        branch_id=device.branch_id,
        tenant=device.tenant,
        primary_contact_id_proof_content=primary_content,
        visitor_id_proof_contents=visitor_contents,
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
