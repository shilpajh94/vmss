import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.checkin import service
from vmss_api.checkin.badge_token import verify_badge_token
from vmss_api.checkin.repository import CheckinRepository
from vmss_api.checkin.schemas import (
    BadgePrintRef,
    BadgeScanOut,
    BadgeScanRequest,
    VerifyIdOut,
    VisitSearchOut,
)
from vmss_api.core.config import settings
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.deps import (
    get_current_user,
    get_db,
    get_pagination,
    get_tenant,
    get_tenant_db,
    require_badge_print_flow,
)
from vmss_api.core.idempotency import Idempotency, idempotency
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import error_response, paginated_response, success_response
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope
from vmss_api.core.tenancy import TenantContext
from vmss_api.org_structure.deps import authorize_branch_id_tolerant, require_branch_scope

_PERMISSION = "visitors:print_badge"

router = APIRouter(prefix="/checkin", tags=["checkin"])

_PDF_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "The badge as a PDF (A6 portrait).",
        "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
    }
}


def _pdf_response(pdf: bytes, *, tracking_id: str, print_id: uuid.UUID) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="badge-{tracking_id}.pdf"',
            "X-Badge-Print-Id": str(print_id),
            # A reprint mutates state, and a print response holds a live QR:
            # neither may be cached or replayed by an intermediary.
            "Cache-Control": "no-store",
        },
    )


def _to_search_out(visit, has_active_badge: bool) -> VisitSearchOut:  # noqa: ANN001
    return VisitSearchOut(
        id=visit.id,
        tracking_id=visit.tracking_id,
        full_name=visit.primary_contact_full_name,
        phone=visit.primary_contact_phone,
        status=visit.status,
        check_in_status=visit.check_in_status,
        branch_id=visit.branch_id,
        has_photo=bool(visit.primary_contact_photo_storage_key),
        id_verified_at=visit.id_verified_at,
        has_active_badge=has_active_badge,
    )


@router.get(
    "/search",
    response_model=PaginatedEnvelope[VisitSearchOut],
    dependencies=[Depends(require_badge_print_flow)],
)
async def search_visits(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_scope: Annotated[BranchScope, Depends(require_branch_scope(_PERMISSION))],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    q: Annotated[str, Query(min_length=1, max_length=255)],
) -> JSONResponse:
    """Reception finds a visit by name, phone, invitation code (`trackingId`) or
    numeric check-in code. Read-only. Query text is never logged in full."""
    page, page_size = pagination
    rows, total = await CheckinRepository(tenant_db).search_visits(
        q.strip(), branch_scope, limit=page_size, offset=(page - 1) * page_size
    )
    return paginated_response(
        data=[_to_search_out(visit, active) for visit, active in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{visit_id}/verify-id",
    response_model=Envelope[VerifyIdOut],
    dependencies=[Depends(require_badge_print_flow)],
)
async def verify_id(
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Reception confirms they checked the visitor's physical ID. Repeating the
    call keeps the original timestamp and verifier."""
    visit = await service.get_visit_or_404(CheckinRepository(tenant_db), visit_id)
    await authorize_branch_id_tolerant(tenant_db, user, _PERMISSION, visit.branch_id)
    first_time = visit.id_verified_at is None
    updated = await service.verify_id(tenant_db, visit, user=user)
    if first_time:
        background_tasks.add_task(
            record_audit_log,
            tenant.schema_name,
            actor_user_id=user.id,
            action="visit_id_verified",
            entity_type="Invitation",
            entity_id=updated.id,
        )
    assert updated.id_verified_at is not None
    return success_response(
        data=VerifyIdOut(
            id=updated.id,
            id_verified_at=updated.id_verified_at,
            id_verified_by_user_id=updated.id_verified_by_user_id,
        )
    )


@router.post(
    "/{visit_id}/photo",
    response_model=Envelope[VisitSearchOut],
    dependencies=[Depends(require_badge_print_flow)],
)
async def upload_photo(
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: Annotated[
        UploadFile,
        File(
            description="Primary contact's photo (JPEG/PNG only), up to the invitation photo limit."
        ),
    ],
) -> JSONResponse:
    """Captures a photo for a visit that was registered without one, clearing
    the print gate's `photo_missing`. `409 photo_already_captured` if the visit
    already has a photo (it is never replaced); `422` for a non-image or an
    oversized file. Returns the refreshed search row."""
    repo = CheckinRepository(tenant_db)
    visit = await service.get_visit_or_404(repo, visit_id)
    await authorize_branch_id_tolerant(tenant_db, user, _PERMISSION, visit.branch_id)
    # Read one byte past the limit so an oversized file is detected, not truncated silently.
    content = await file.read(settings.invitation_max_photo_size_bytes + 1)
    updated = await service.attach_photo(tenant_db, visit, content, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="visit_photo_captured",
        entity_type="Invitation",
        entity_id=updated.id,
    )
    active = await repo.get_active_print(updated.id)
    return success_response(data=_to_search_out(updated, active is not None))


@router.post(
    "/{visit_id}/badge",
    response_class=Response,
    responses=_PDF_RESPONSE,
    dependencies=[Depends(require_badge_print_flow)],
)
async def print_badge(
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    idem: Annotated[Idempotency, Depends(idempotency)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional. A retry with the same key returns the same PDF and never "
                "creates a second badge row."
            ),
        ),
    ] = None,
) -> Response:
    """Prints the visit's first badge as a PDF. Needs an approved/checked-in
    visit with a photo and a verified ID (`409` names every unmet condition).
    A second print while a badge is active is a `409`; use the reprint endpoint."""
    cached = await idem.begin(
        tenant.id, "checkin", idempotency_key, caller=str(user.id), body=str(visit_id)
    )
    if cached is not None:
        replay = await _replay(tenant_db, cached, tenant=tenant)
        return replay if replay is not None else cached

    visit = await service.get_visit_or_404(CheckinRepository(tenant_db), visit_id)
    await authorize_branch_id_tolerant(tenant_db, user, _PERMISSION, visit.branch_id)
    row, pdf = await service.print_badge(tenant_db, visit, user=user, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="badge_printed",
        entity_type="Invitation",
        entity_id=visit.id,
        diff={"jti": row.jti},
    )
    await idem.store(success_response(data=BadgePrintRef(badge_print_id=row.id)))
    return _pdf_response(pdf, tracking_id=visit.tracking_id, print_id=row.id)


async def _replay(
    tenant_db: AsyncSession, cached: JSONResponse, *, tenant: TenantContext
) -> Response | None:
    """A cached print response is `{data: {badgePrintId}}`; rebuild the PDF
    from that row. Anything else cached (an in-flight 409, say) is returned as-is."""
    try:
        body = json.loads(bytes(cached.body))
        print_id = uuid.UUID(body["data"]["badgePrintId"])
    except (ValueError, KeyError, TypeError):
        return None
    rendered = await service.render_existing_print(tenant_db, print_id, tenant=tenant)
    if rendered is None:
        return None
    row, pdf = rendered
    visit = await CheckinRepository(tenant_db).get_visit(row.visit_id)
    assert visit is not None
    return _pdf_response(pdf, tracking_id=visit.tracking_id, print_id=row.id)


@router.get(
    "/{visit_id}/badge",
    response_class=Response,
    responses=_PDF_RESPONSE,
    dependencies=[Depends(require_badge_print_flow)],
)
async def reprint_badge(
    visit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    reason: Annotated[
        str, Query(min_length=1, max_length=255, description="Why, e.g. lost or damaged.")
    ],
) -> Response:
    """Reprints the badge. **State-changing despite being a GET:** the previous
    QR is deactivated and a new one issued, so the response is `no-store` and a
    `reason` is mandatory. Unlimited reprints; every one is audited."""
    if not reason.strip():
        return _blank_reason()
    visit = await service.get_visit_or_404(CheckinRepository(tenant_db), visit_id)
    await authorize_branch_id_tolerant(tenant_db, user, _PERMISSION, visit.branch_id)
    row, pdf = await service.reprint_badge(
        tenant_db, visit, user=user, tenant=tenant, reason=reason.strip()
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="badge_reprinted",
        entity_type="Invitation",
        entity_id=visit.id,
        diff={"jti": row.jti, "reason": reason.strip()},
    )
    return _pdf_response(pdf, tracking_id=visit.tracking_id, print_id=row.id)


def _blank_reason() -> Response:
    return error_response("reason must not be blank", 422)


# --- badge scan (the token is the credential) --------------------------------


def _scan_out(visit) -> BadgeScanOut:  # noqa: ANN001
    return BadgeScanOut(
        id=visit.id,
        tracking_id=visit.tracking_id,
        status=visit.status,
        check_in_status=visit.check_in_status,
    )


async def _open_scan(db: AsyncSession, token: str):  # noqa: ANN202
    claims = verify_badge_token(token)
    if claims is None:
        raise service.invalid_token()
    tenant = await service.resolve_scan_tenant(db, claims)
    return claims, tenant


@router.post("/badge/check-out", response_model=Envelope[BadgeScanOut])
@limiter.limit(settings.badge_scan_rate_limit)
async def check_out_by_badge(
    request: Request,
    payload: BadgeScanRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Unauthenticated: possessing a valid, active, same-day badge token is the
    credential (like the existing QR check-out). Closes the visit and
    deactivates the badge. Reception can instead search and use the existing
    check-out endpoint."""
    claims, tenant = await _open_scan(db, payload.token)
    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        visit, row = await service.resolve_active_badge(tenant_db, claims, tenant=tenant)
        updated = await service.check_out_by_badge(tenant_db, visit, row, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action="badge_checked_out",
        entity_type="Invitation",
        entity_id=updated.id,
        diff={"jti": row.jti},
    )
    return success_response(data=_scan_out(updated), message="Checked out successfully")


@router.post("/badge/check-in", response_model=Envelope[BadgeScanOut])
@limiter.limit(settings.badge_scan_rate_limit)
async def check_in_by_badge(
    request: Request,
    payload: BadgeScanRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """First entry by scanning an active, same-day badge. The badge stays
    active so the same QR can check the visitor out later."""
    claims, tenant = await _open_scan(db, payload.token)
    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        visit, row = await service.resolve_active_badge(tenant_db, claims, tenant=tenant)
        updated = await service.check_in_by_badge(tenant_db, visit, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action="badge_checked_in",
        entity_type="Invitation",
        entity_id=updated.id,
        diff={"jti": row.jti},
    )
    return success_response(data=_scan_out(updated), message="Checked in successfully")


@router.post("/badge/re-enter", response_model=Envelope[BadgeScanOut])
@limiter.limit(settings.badge_scan_rate_limit)
async def re_enter_by_badge(
    request: Request,
    payload: BadgeScanRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Same-day return for a visitor currently stepped out, by scanning an
    active badge. Not possible after the badge's day or once it is deactivated."""
    claims, tenant = await _open_scan(db, payload.token)
    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        visit, row = await service.resolve_active_badge(tenant_db, claims, tenant=tenant)
        updated = await service.re_enter_by_badge(tenant_db, visit, tenant=tenant)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=None,
        action="badge_re_entered",
        entity_type="Invitation",
        entity_id=updated.id,
        diff={"jti": row.jti},
    )
    return success_response(data=_scan_out(updated), message="Welcome back")
