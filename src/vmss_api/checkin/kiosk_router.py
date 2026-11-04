"""Kiosk (device-authenticated) mirror of the staff badge routes
(add-kiosk-badge-print-flow). No bearer token: the `device-id` header naming an
approved kiosk is the credential, and the device — not a user — supplies the
branch scope. Business rules are the staff ones, via `checkin.service`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address

from vmss_api.auth.audit import record_audit_log
from vmss_api.checkin import service
from vmss_api.checkin.kiosk_deps import KioskContext, get_kiosk_context
from vmss_api.checkin.kiosk_schemas import KioskVisitOut
from vmss_api.checkin.repository import CheckinRepository
from vmss_api.checkin.schemas import BadgeCardOut, BadgePrintRef, VerifyIdOut
from vmss_api.core.config import settings
from vmss_api.core.idempotency import Idempotency, idempotency
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import error_response, success_response
from vmss_api.core.schemas import Envelope

router = APIRouter(prefix="/kiosk/checkin", tags=["kiosk-checkin"])


def _device_key(request: Request) -> str:
    return request.headers.get("device-id") or get_remote_address(request)


def _limited(func):  # noqa: ANN001, ANN202
    """Two buckets per route: client IP, and the `device-id` header value. The
    IP bucket stops a caller rotating made-up device ids to dodge the limit."""
    func = limiter.limit(settings.kiosk_badge_rate_limit, key_func=_device_key)(func)
    return limiter.limit(settings.kiosk_badge_rate_limit)(func)


def _card_response(card: BadgeCardOut) -> JSONResponse:
    response = success_response(data=card)
    response.headers["Cache-Control"] = "no-store"
    return response


def _first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name.strip() else ""


def _to_kiosk_out(visit, has_active_badge: bool) -> KioskVisitOut:  # noqa: ANN001
    return KioskVisitOut(
        id=visit.id,
        tracking_id=visit.tracking_id,
        visitor_first_name=_first_name(visit.primary_contact_full_name),
        status=visit.status,
        check_in_status=visit.check_in_status,
        has_photo=bool(visit.primary_contact_photo_storage_key),
        id_verified_at=visit.id_verified_at,
        has_active_badge=has_active_badge,
        unmet_conditions=service.unmet_print_conditions(visit),
    )


def _audit(
    background_tasks: BackgroundTasks,
    ctx: KioskContext,
    action: str,
    visit_id: uuid.UUID,
    **diff: object,
) -> None:
    background_tasks.add_task(
        record_audit_log,
        ctx.tenant.schema_name,
        actor_user_id=None,
        action=f"kiosk_{action}",
        entity_type="Invitation",
        entity_id=visit_id,
        diff={"device_id": ctx.device.device_id, **diff},
    )


@router.get("/search", response_model=Envelope[KioskVisitOut])
@_limited
async def kiosk_search_visit(
    request: Request,
    ctx: Annotated[KioskContext, Depends(get_kiosk_context)],
    q: Annotated[str, Query(min_length=1, max_length=32)],
) -> JSONResponse:
    """Exact `trackingId` or numeric check-in code only — no name or phone
    search — returning at most one visit with no contact details. `404` when
    nothing matches in this kiosk's branch today. The query is never logged."""
    visit = await service.find_kiosk_visit(ctx.tenant_db, ctx.device, q.strip(), tenant=ctx.tenant)
    active = await CheckinRepository(ctx.tenant_db).get_active_print(visit.id)
    return success_response(data=_to_kiosk_out(visit, active is not None))


@router.post("/{visit_id}/verify-id", response_model=Envelope[VerifyIdOut])
@_limited
async def kiosk_verify_id(
    request: Request,
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[KioskContext, Depends(get_kiosk_context)],
) -> JSONResponse:
    """The visitor presents their ID at the kiosk; this is device-attested (no
    receptionist confirms it) and recorded against the device. Idempotent."""
    visit = await service.get_kiosk_visit(ctx.tenant_db, ctx.device, visit_id, tenant=ctx.tenant)
    first_time = visit.id_verified_at is None
    updated = await service.verify_id(ctx.tenant_db, visit, device=ctx.device)
    if first_time:
        _audit(background_tasks, ctx, "visit_id_verified", updated.id)
    assert updated.id_verified_at is not None
    return success_response(
        data=VerifyIdOut(
            id=updated.id,
            id_verified_at=updated.id_verified_at,
            id_verified_by_user_id=None,
        )
    )


@router.post("/{visit_id}/photo", response_model=Envelope[KioskVisitOut])
@_limited
async def kiosk_upload_photo(
    request: Request,
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[KioskContext, Depends(get_kiosk_context)],
    file: Annotated[UploadFile, File(description="Visitor photo (JPEG/PNG only).")],
) -> JSONResponse:
    """Captures a photo for a visit registered without one. `409
    photo_already_captured` if one exists; `422` for a non-image or oversized
    file. Returns the refreshed kiosk row."""
    visit = await service.get_kiosk_visit(ctx.tenant_db, ctx.device, visit_id, tenant=ctx.tenant)
    content = await file.read(settings.invitation_max_photo_size_bytes + 1)
    updated = await service.attach_photo(ctx.tenant_db, visit, content, tenant=ctx.tenant)
    _audit(background_tasks, ctx, "visit_photo_captured", updated.id)
    active = await CheckinRepository(ctx.tenant_db).get_active_print(updated.id)
    return success_response(data=_to_kiosk_out(updated, active is not None))


@router.post("/{visit_id}/badge", response_model=Envelope[BadgeCardOut])
@_limited
async def kiosk_print_badge(
    request: Request,
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[KioskContext, Depends(get_kiosk_context)],
    idem: Annotated[Idempotency, Depends(idempotency)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Optional. A retry with the same key returns the same card.",
        ),
    ] = None,
) -> JSONResponse:
    """Prints the visit's first badge and returns the card data as JSON. Needs
    an approved/checked-in visit with a photo and verified ID (`409` names every
    unmet condition). A second print while a badge is active is a `409`."""
    cached = await idem.begin(
        ctx.tenant.id,
        "kiosk-checkin",
        idempotency_key,
        caller=str(ctx.device.id),
        body=str(visit_id),
    )
    if cached is not None:
        replay = await _replay(ctx, cached)
        return replay if replay is not None else cached
    visit = await service.get_kiosk_visit(ctx.tenant_db, ctx.device, visit_id, tenant=ctx.tenant)
    row, card = await service.print_badge(
        ctx.tenant_db, visit, device=ctx.device, tenant=ctx.tenant
    )
    _audit(background_tasks, ctx, "badge_printed", visit.id, jti=row.jti)
    await idem.store(success_response(data=BadgePrintRef(badge_print_id=row.id)))
    return _card_response(card)


async def _replay(ctx: KioskContext, cached: JSONResponse) -> JSONResponse | None:
    import json

    try:
        body = json.loads(bytes(cached.body))
        print_id = uuid.UUID(body["data"]["badgePrintId"])
    except (ValueError, KeyError, TypeError):
        return None
    rendered = await service.render_existing_print(ctx.tenant_db, print_id, tenant=ctx.tenant)
    if rendered is None:
        return None
    row, card = rendered
    # Only this device's own print may be replayed (the cache key already
    # includes the device; this guards a row from another visit's print).
    if row.printed_by_device_id != ctx.device.id:
        return None
    return _card_response(card)


@router.get("/{visit_id}/badge", response_model=Envelope[BadgeCardOut])
@_limited
async def kiosk_reprint_badge(
    request: Request,
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[KioskContext, Depends(get_kiosk_context)],
    reason: Annotated[
        str, Query(min_length=1, max_length=255, description="Why, e.g. lost or damaged.")
    ],
) -> JSONResponse:
    """Reprints the badge. **State-changing despite being a GET:** the previous
    QR is deactivated and a new one issued, so the response is `no-store` and a
    `reason` is mandatory. Every reprint is audited."""
    if not reason.strip():
        return error_response("reason must not be blank", 422)
    visit = await service.get_kiosk_visit(ctx.tenant_db, ctx.device, visit_id, tenant=ctx.tenant)
    row, card = await service.reprint_badge(
        ctx.tenant_db, visit, device=ctx.device, tenant=ctx.tenant, reason=reason.strip()
    )
    _audit(background_tasks, ctx, "badge_reprinted", visit.id, jti=row.jti, reason=reason.strip())
    return _card_response(card)
