"""Badge print flow business rules (add-badge-print-flow).

Visits are `Invitation` rows. Existing check-in/out state transitions are
reused from `invitations.checkin` rather than duplicated, so `status` and
`check_in_status` stay in step with every other entry/exit path.
"""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.checkin import badge_pdf, badge_token
from vmss_api.checkin.badge_token import BadgeClaims
from vmss_api.checkin.models import BadgePrint
from vmss_api.checkin.repository import CheckinRepository
from vmss_api.core.config import settings
from vmss_api.core.logging import logger
from vmss_api.core.storage import load as storage_load
from vmss_api.core.storage import save as storage_save
from vmss_api.core.storage import validate_image_only
from vmss_api.core.tenancy import TenantContext
from vmss_api.invitations.checkin import _check_out_resolved, _perform_check_in
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.tenant.repository import TenantRepository

_PRINTABLE_STATUSES = ("approved", "checked_in")
_INVALID_TOKEN = "Invalid badge token"


def tenant_today(tenant: TenantContext, now: datetime | None = None) -> date:
    return (
        (now or datetime.now(ZoneInfo(tenant.timezone)))
        .astimezone(ZoneInfo(tenant.timezone))
        .date()
    )


def unmet_print_conditions(invitation: Invitation) -> list[str]:
    unmet: list[str] = []
    if invitation.status not in _PRINTABLE_STATUSES:
        unmet.append("visit_not_approved")
    if not invitation.primary_contact_photo_storage_key:
        unmet.append("photo_missing")
    if invitation.id_verified_at is None:
        unmet.append("id_not_verified")
    return unmet


async def get_visit_or_404(repo: CheckinRepository, visit_id: uuid.UUID) -> Invitation:
    visit = await repo.get_visit(visit_id)
    if visit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Visit not found")
    return visit


async def verify_id(tenant_db: AsyncSession, visit: Invitation, *, user: User) -> Invitation:
    updated = await CheckinRepository(tenant_db).mark_id_verified(visit.id, user_id=user.id)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Visit not found")
    await tenant_db.commit()
    return updated


async def attach_photo(
    tenant_db: AsyncSession, visit: Invitation, content: bytes, *, tenant: TenantContext
) -> Invitation:
    """Captures the primary contact's photo for a visit registered without
    one, so the print gate's `photo_missing` can be cleared at the desk. Never
    replaces an existing photo: changing the face on a visit that may already
    hold a live badge is not something reception can do silently."""
    if visit.primary_contact_photo_storage_key:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="photo_already_captured")
    content_type = validate_image_only(
        content, max_size_bytes=settings.invitation_max_photo_size_bytes, field_label="photo"
    )
    key = await storage_save(tenant.id, "invitations/photos", content, content_type)
    updated = await CheckinRepository(tenant_db).set_photo_if_missing(visit.id, key)
    if updated is None:
        # Lost a race with another upload (or the visit vanished).
        await tenant_db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="photo_already_captured")
    await tenant_db.commit()
    return updated


async def _render(
    tenant_db: AsyncSession, visit: Invitation, row: BadgePrint, *, tenant: TenantContext
) -> bytes:
    # The badge carries the visit's existing check-in QR, so the existing
    # check-in/check-out scanners work on it. A visit with no stored QR (none
    # was issued) falls back to the signed badge token.
    qr_code = await InvitationRepository(tenant_db).get_qr_code(visit.id)
    if qr_code is not None:
        token = qr_code.qr_token
    else:
        token = badge_token.issue_badge_token(
            visit_id=visit.id,
            tenant_id=tenant.id,
            day=row.day,
            jti=row.jti,
            timezone=tenant.timezone,
        )
    assert visit.primary_contact_photo_storage_key is not None  # guaranteed by the gate
    photo = await storage_load(visit.primary_contact_photo_storage_key)
    return await badge_pdf.render_badge_pdf(
        visitor_name=visit.primary_contact_full_name,
        host_name=visit.host_name_or_email or "-",
        visit_date=row.day,
        photo_bytes=photo,
        qr_token=token,
        organisation_name=tenant.name,
        tracking_id=visit.tracking_id,
    )


async def render_existing_print(
    tenant_db: AsyncSession, print_id: uuid.UUID, *, tenant: TenantContext
) -> tuple[BadgePrint, bytes] | None:
    """Idempotent replay: the same PDF, rebuilt from the stored row."""
    repo = CheckinRepository(tenant_db)
    row = await repo.get_print(print_id)
    if row is None:
        return None
    visit = await repo.get_visit(row.visit_id)
    if visit is None or not visit.primary_contact_photo_storage_key:
        return None
    return row, await _render(tenant_db, visit, row, tenant=tenant)


async def _create_print(
    tenant_db: AsyncSession,
    visit: Invitation,
    *,
    user: User,
    tenant: TenantContext,
    reprint_reason: str | None,
) -> tuple[BadgePrint, bytes]:
    unmet = unmet_print_conditions(visit)
    if unmet:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            # The global handler renders `str(detail)`, so the codes are inline.
            detail="Badge cannot be printed yet: " + ", ".join(unmet),
        )
    repo = CheckinRepository(tenant_db)
    is_reprint = reprint_reason is not None
    if is_reprint and not await repo.has_any_print(visit.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No badge has been printed for this visit yet; use the print endpoint",
        )
    if not is_reprint and await repo.get_active_print(visit.id) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A badge is already active for this visit; use the reprint endpoint",
        )
    try:
        if is_reprint:
            await repo.deactivate_active_for_visit(visit.id)
        row = await repo.insert_print(
            visit_id=visit.id,
            printed_by_user_id=user.id,
            jti=badge_token.new_jti(),
            day=tenant_today(tenant),
            reprint_reason=reprint_reason,
        )
        # Render before commit: a render failure leaves the old badge active.
        pdf = await _render(tenant_db, visit, row, tenant=tenant)
        await tenant_db.commit()
    except IntegrityError:
        await tenant_db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A badge is already active for this visit"
        ) from None
    except Exception:
        await tenant_db.rollback()
        raise
    return row, pdf


async def print_badge(
    tenant_db: AsyncSession, visit: Invitation, *, user: User, tenant: TenantContext
) -> tuple[BadgePrint, bytes]:
    return await _create_print(tenant_db, visit, user=user, tenant=tenant, reprint_reason=None)


async def reprint_badge(
    tenant_db: AsyncSession,
    visit: Invitation,
    *,
    user: User,
    tenant: TenantContext,
    reason: str,
) -> tuple[BadgePrint, bytes]:
    return await _create_print(tenant_db, visit, user=user, tenant=tenant, reprint_reason=reason)


# --- badge scan ---------------------------------------------------------------


def invalid_token() -> HTTPException:
    """One response for every failure mode, never revealing which check failed."""
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID_TOKEN)


async def resolve_active_badge(
    tenant_db: AsyncSession, claims: BadgeClaims, *, tenant: TenantContext
) -> tuple[Invitation, BadgePrint]:
    """The token is ours and intact (`verify_badge_token`); now it must also be
    for today in the tenant's clock, and its `jti` row must still be active."""
    repo = CheckinRepository(tenant_db)
    row = await repo.get_print_by_jti(claims.jti)
    if (
        row is None
        or not row.active
        or row.visit_id != claims.visit_id
        or row.day != claims.day
        or claims.day != tenant_today(tenant)
    ):
        raise invalid_token()
    visit = await repo.get_visit(claims.visit_id)
    if visit is None:
        raise invalid_token()
    return visit, row


async def check_out_by_badge(
    tenant_db: AsyncSession, visit: Invitation, row: BadgePrint, *, tenant: TenantContext
) -> Invitation:
    """Closes the visit and deactivates the badge in one commit: the
    deactivation is flushed first and `_check_out_resolved` commits both, or a
    409 rolls both back."""
    if visit.check_in_status != "checked_in":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not currently checked in"
        )
    repo = CheckinRepository(tenant_db)
    await repo.deactivate_by_jti(row.jti)
    try:
        updated, _ = await _check_out_resolved(tenant_db, visit, tenant=tenant)  # type: ignore[arg-type]
    except HTTPException:
        await tenant_db.rollback()
        raise
    return updated


async def check_in_by_badge(
    tenant_db: AsyncSession, visit: Invitation, *, tenant: TenantContext
) -> Invitation:
    """First entry by scanning the active badge. Unlike check-out this leaves
    the badge active so it still works for check-out and re-entry; a visit
    that is already inside or stepped out must use those instead."""
    if visit.check_in_status in ("checked_in", "checked_out"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Visit is already checked in; use check-out"
        )
    updated, _ = await _perform_check_in(
        tenant_db,
        visit,
        actor_user_id=None,
        tenant=tenant,  # type: ignore[arg-type]
    )
    logger.info("badge_check_in", visit_id=str(visit.id), tenant_id=str(tenant.id))
    return updated


async def re_enter_by_badge(
    tenant_db: AsyncSession, visit: Invitation, *, tenant: TenantContext
) -> Invitation:
    if visit.check_in_status != "checked_out":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Visit is not currently stepped out")
    updated, _ = await _perform_check_in(
        tenant_db,
        visit,
        actor_user_id=None,
        tenant=tenant,  # type: ignore[arg-type]
    )
    logger.info("badge_re_entry", visit_id=str(visit.id), tenant_id=str(tenant.id))
    return updated


async def resolve_scan_tenant(db: AsyncSession, claims: BadgeClaims) -> TenantContext:
    """Scan endpoints carry no bearer token: the tenant comes from the `tid`
    claim of a token whose signature has already verified — never from a
    request field (security-architecture.md §1). Flag-off is a 404, like every
    other badge-flow route."""
    tenant = await TenantRepository(db).get(claims.tenant_id)
    if tenant is None or not tenant.is_active:
        raise invalid_token()
    if not tenant.badge_print_flow_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    return TenantContext(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        schema_name=tenant.schema_name,
        is_active=tenant.is_active,
        timezone=tenant.timezone,
        badge_print_flow_enabled=tenant.badge_print_flow_enabled,
    )
