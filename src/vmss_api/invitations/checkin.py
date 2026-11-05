"""Gate actions: check-in and check-out (by tracking ID, QR token or code),
badges and the watchlist override. Split out of `service.py`, which re-
exports every name.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.logging import logger
from vmss_api.core.storage import save as storage_save
from vmss_api.devices import service as device_service
from vmss_api.devices.models import Device
from vmss_api.invitations import badge, code_lockout, push_notifications
from vmss_api.invitations.common import (
    _ACTIVE_STATUSES,
    _generate_unique_badge_number,
    _issue_qr_code,
    _notify_host,
    _push_point_of_contact,
    resolve_visit_timezone,
)
from vmss_api.invitations.models import (
    Invitation,
)
from vmss_api.invitations.qr_token import decrypt_invitation_token
from vmss_api.invitations.repository import (
    InvitationRepository,
)
from vmss_api.tenant.models import Tenant


async def _enforce_device_location(
    tenant_db: AsyncSession, device: Device | None, invitation: Invitation
) -> None:
    """Branch/building mismatch guard (devices spec "Check-In Validates
    Device Branch and Building"). Runs before the state change so a
    rejection leaves no trace. No-op without a device or with the tenant
    setting off."""
    if device is None or not await device_service.get_enforce_location_validation(tenant_db):
        return
    device_service.check_device_location(
        device,
        invitation_branch_id=invitation.branch_id,
        invitation_building_id=invitation.building_id,
    )


# An archived no-show's pass is inert until rescheduled (auto-checkout-and-
# archive-no-shows spec "An Archived Invitation Does Not Admit the Visitor").
_ARCHIVED_CHECK_IN_DETAIL = "Invitation is archived; reschedule it to admit the visitor"


def _enforce_id_verified_at_check_in(invitation: Invitation, tenant: Tenant) -> None:
    """Badge printing never checks ID; check-in does, when the admin toggle
    `badge_print_requires_id_verification` is on (badge flow enabled). Shared by
    the tracking-ID, QR-token, check-in-code and badge-scan paths.
    """
    if (
        tenant.badge_print_flow_enabled
        and tenant.badge_print_requires_id_verification
        and invitation.id_verified_at is None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="ID not verified; verify ID before check-in"
        )


async def _perform_check_in(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    actor_user_id: uuid.UUID | None,
    tenant: Tenant,
    device: Device | None = None,
) -> tuple[Invitation, bool]:
    """spec.md "An Approved Invitation Can Be Checked In" /
    "A Watchlist-Flagged Invitation Blocks Check-In Until Overridden" /
    "An Approved Invitation Can Be Publicly Checked In By Tracking ID". The
    pre-check below gives a caller a specific reason for the 409 (flagged vs.
    wrong status); the repository's atomic `WHERE` clause re-checks both
    conditions so a race with a concurrent flag/status change can't slip a
    check-in through between this read and the write.

    `actor_user_id` is `None` for the public, tracking-ID-keyed check-in path
    (there is no authenticated caller to record) — `checked_in_by_user_id` is
    nullable at the model level for exactly this case.

    Returns `(invitation, changed)` — `changed` is `False` for the
    idempotent-no-op case below, so the caller (the router's audit-log
    background task) can skip writing an audit entry for a call that
    performed no actual transition.

    A repeat call while already `checked_in` is treated as an idempotent
    no-op success (returns the invitation unchanged) rather than a 409 — no
    second `UPDATE`, no re-stamped `checkedInAt`, no duplicate host
    notification or audit entry, since nothing about the invitation's state
    actually changed. This is deliberately checked before the watchlist gate
    below: a flag added after a visitor already entered must not turn their
    repeat/duplicate check-in call into an error.
    """
    # Before the idempotent early return, so a repeat call from a device at the
    # wrong branch/building is rejected rather than silently succeeding.
    await _enforce_device_location(tenant_db, device, invitation)
    if invitation.check_in_status == "checked_in":
        return invitation, False
    if invitation.status == "archived":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_ARCHIVED_CHECK_IN_DETAIL)
    if invitation.watchlist_flagged:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation is watchlist-flagged; override required before check-in",
        )
    if invitation.status not in ("approved", "checked_in", "checked_out"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not approved")
    _enforce_id_verified_at_check_in(invitation, tenant)
    updated = await InvitationRepository(tenant_db).check_in_if_eligible(
        invitation.id, user_id=actor_user_id, device_pk=device.id if device else None
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation is no longer eligible for check-in",
        )
    await tenant_db.commit()
    await _notify_host(tenant, updated, push_notifications.checked_in)
    await _push_point_of_contact(
        tenant_db,
        tenant,
        updated,
        push_builder=push_notifications.checked_in,
        actor_user_id=actor_user_id,
    )
    return updated, True


async def branch_of_tracking_id(tenant_db: AsyncSession, tracking_id: str) -> uuid.UUID | None:
    """Read-only: the branch an invitation belongs to, so a caller's branch
    permission can be checked before any state change (public-endpoint-
    hardening's strict tracking-ID check-in)."""
    invitation = await InvitationRepository(tenant_db).get_by_tracking_id(tracking_id)
    return invitation.branch_id if invitation is not None else None


async def check_in_invitation_by_tracking_id(
    tenant_db: AsyncSession, tracking_id: str, *, tenant: Tenant, device: Device | None = None
) -> tuple[Invitation, bool]:
    """`PATCH /api/v2/invitations/{trackingId}/check-in` — public,
    unauthenticated, tracking-ID-keyed (spec.md "An Approved Invitation Can
    Be Publicly Checked In By Tracking ID"). No authenticated caller, so no
    branch authorization check and no human actor recorded.
    """
    invitation = await InvitationRepository(tenant_db).get_by_tracking_id(tracking_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return await _perform_check_in(
        tenant_db, invitation, actor_user_id=None, tenant=tenant, device=device
    )


async def _get_invitation_by_qr_token_or_400(
    tenant_db: AsyncSession, token: str, *, tenant: Tenant
) -> Invitation:
    """Shared by both QR endpoints — an invalid/tampered token and an
    invitation that doesn't exist are folded into the same rejection
    (`invalid token`) so neither response reveals which failure actually
    occurred.
    """
    invitation_id = decrypt_invitation_token(token)
    invitation = (
        await InvitationRepository(tenant_db).get_with_children(invitation_id)
        if invitation_id
        else None
    )
    if invitation is None:
        logger.warning("qr_check_in_invalid_token", tenant_id=str(tenant.id))
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Verification failed — invalid token"
        )
    return invitation


async def check_in_by_qr_token(
    tenant_db: AsyncSession, token: str, *, tenant: Tenant, device: Device | None = None
) -> tuple[Invitation, str, bool]:
    """`PATCH /api/v2/invitations/qr/{token}/check-in` — public,
    unauthenticated, driven by the encrypted QR token rather than the
    tracking ID (spec.md "QR Check-In Token Is Encrypted and
    Tamper-Evident" / "QR Check-In Endpoint Transitions an Eligible
    Visitor to Checked-In"). Entry only: `unused`/`checked_out` ->
    `checked_in`. A repeat scan while already `checked_in` is an idempotent
    no-op success (same "Verification passed" message, unchanged data) —
    not a 409 — mirroring `_perform_check_in`'s identical rule; the caller
    still uses `check_out_by_qr_token` to actually exit. Also rejects a scan
    attempted before the invitation's `preferred_visit_date` (date-only,
    tenant-local calendar day) with `425 Too Early`, distinct from the
    `410 Gone` used for expiry — see qr-checkin-scheduling-photo-email/
    design.md Decisions 1-2. An invitation with no `preferred_visit_date`
    set skips that check entirely.

    Returns `(invitation, message, changed)` — `message` is the
    human-readable outcome the caller surfaces directly ("Verification
    passed"), matching the confirmed frontend spec's response contract;
    `changed` is `False` for the idempotent-no-op case below, so the
    caller (the router's audit-log background task) can skip writing an
    audit entry for a scan that performed no actual transition.
    """
    invitation = await _get_invitation_by_qr_token_or_400(tenant_db, token, tenant=tenant)
    return await _check_in_resolved(tenant_db, invitation, tenant=tenant, device=device)


async def _check_in_resolved(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    tenant: Tenant,
    device: Device | None = None,
) -> tuple[Invitation, str, bool]:
    """Entry rules shared by the QR-token and check-in-code endpoints — only
    how the invitation is resolved differs between them.
    """
    # Before the idempotent early return — see `_perform_check_in`.
    await _enforce_device_location(tenant_db, device, invitation)
    if invitation.check_in_status == "checked_in":
        return invitation, "Verification passed", False
    if invitation.status == "archived":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_ARCHIVED_CHECK_IN_DETAIL)
    if invitation.status not in ("approved", "checked_in", "checked_out"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Verification failed — invitation not approved"
        )
    if invitation.watchlist_flagged:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Invitation is watchlist-flagged; override required before check-in",
        )
    today_local = (
        datetime.now(UTC).astimezone(await resolve_visit_timezone(tenant_db, tenant)).date()
    )
    if (
        invitation.preferred_visit_date is not None
        and invitation.preferred_visit_date > today_local
    ):
        raise HTTPException(
            status.HTTP_425_TOO_EARLY,
            detail="Verification failed — visit window not yet open",
        )
    if invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status.HTTP_410_GONE, detail="Verification failed — visit window expired"
        )
    _enforce_id_verified_at_check_in(invitation, tenant)
    # add-zone-access-control: a check-in from a security device tied to one zone
    # is also an entry into that zone (judged and logged here, before the commit).
    if tenant.zone_access_enabled:
        from vmss_api.access_control.checkin_gate import enforce_checkin_zone

        await enforce_checkin_zone(tenant_db, tenant, invitation, device, today_local=today_local)
    updated = await InvitationRepository(tenant_db).check_in_by_qr_if_eligible(
        invitation.id, today_local=today_local, device_pk=device.id if device else None
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is no longer eligible for check-in"
        )

    await tenant_db.commit()
    await _notify_host(tenant, updated, push_notifications.checked_in)
    await _push_point_of_contact(
        tenant_db, tenant, updated, push_builder=push_notifications.checked_in, actor_user_id=None
    )
    return updated, "Verification passed", True


async def check_out_by_qr_token(
    tenant_db: AsyncSession, token: str, *, tenant: Tenant, device: Device | None = None
) -> tuple[Invitation, str]:
    """`PATCH /api/v2/invitations/qr/{token}/check-out` — public,
    unauthenticated exit counterpart of `check_in_by_qr_token` (spec.md "QR
    Check-Out Endpoint Transitions a Checked-In Visitor to Checked-Out").
    Exit only: `checked_in` -> `checked_out`, never subject to the expiry
    check (a visit that legitimately continues past `expires_at` can still
    be closed out). Rejects with 409 when the invitation isn't currently
    `checked_in`.
    """
    invitation = await _get_invitation_by_qr_token_or_400(tenant_db, token, tenant=tenant)
    return await _check_out_resolved(tenant_db, invitation, tenant=tenant, device=device)


async def _check_out_resolved(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    tenant: Tenant,
    device: Device | None = None,
) -> tuple[Invitation, str]:
    """Exit rules shared by the QR-token and check-in-code endpoints."""
    if invitation.check_in_status != "checked_in":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not currently checked in"
        )
    updated = await InvitationRepository(tenant_db).check_out_by_qr_if_eligible(
        invitation.id, device_pk=device.id if device else None
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is no longer eligible for check-out"
        )

    await tenant_db.commit()
    await _notify_host(tenant, updated, push_notifications.checked_out)
    await _push_point_of_contact(
        tenant_db, tenant, updated, push_builder=push_notifications.checked_out, actor_user_id=None
    )
    return updated, "Checked out successfully"


async def _get_invitation_by_checkin_code_or_400(
    tenant_db: AsyncSession, code: str, *, tenant: Tenant, client_ip: str
) -> Invitation:
    """Unknown codes get the same generic rejection as a bad QR token, and the
    submitted code is never logged. A locked-out IP is refused before any
    lookup, so a valid guess after lockout can't succeed.
    """
    await code_lockout.ensure_not_locked_out(tenant.id, client_ip)
    invitation = await InvitationRepository(tenant_db).get_by_checkin_code(code)
    if invitation is None:
        await code_lockout.record_failure(tenant.id, client_ip)
        logger.warning("checkin_code_invalid", tenant_id=str(tenant.id), ip=client_ip)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Verification failed — invalid code"
        )
    return invitation


async def check_in_by_code(
    tenant_db: AsyncSession,
    code: str,
    *,
    tenant: Tenant,
    client_ip: str,
    device: Device | None = None,
) -> tuple[Invitation, str, bool]:
    """`PATCH /api/v2/invitations/code/check-in` (spec.md "Public Check-In by
    Code") — identical to `check_in_by_qr_token` apart from resolution.
    """
    invitation = await _get_invitation_by_checkin_code_or_400(
        tenant_db, code, tenant=tenant, client_ip=client_ip
    )
    return await _check_in_resolved(tenant_db, invitation, tenant=tenant, device=device)


async def check_out_by_code(
    tenant_db: AsyncSession,
    code: str,
    *,
    tenant: Tenant,
    client_ip: str,
    device: Device | None = None,
) -> tuple[Invitation, str]:
    """`PATCH /api/v2/invitations/code/check-out` (spec.md "Public Check-Out
    by Code") — identical to `check_out_by_qr_token` apart from resolution.
    """
    invitation = await _get_invitation_by_checkin_code_or_400(
        tenant_db, code, tenant=tenant, client_ip=client_ip
    )
    return await _check_out_resolved(tenant_db, invitation, tenant=tenant, device=device)


async def check_out_invitation(
    tenant_db: AsyncSession,
    invitation: Invitation,
    *,
    user_id: uuid.UUID,
    tenant: Tenant,
    device: Device | None = None,
) -> Invitation:
    updated = await InvitationRepository(tenant_db).check_out_if_checked_in(
        invitation.id, user_id=user_id, device_pk=device.id if device else None
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is not checked in")
    await tenant_db.commit()
    await _notify_host(tenant, updated, push_notifications.checked_out)
    await _push_point_of_contact(
        tenant_db,
        tenant,
        updated,
        push_builder=push_notifications.checked_out,
        actor_user_id=user_id,
    )
    return updated


async def issue_badge(
    tenant_db: AsyncSession, invitation: Invitation, *, tenant: Tenant
) -> Invitation:
    """spec.md "A Badge Can Be Printed for an Approved or Active Visit" —
    generates the badge number and renders the image before the guarded
    `UPDATE`, same "validate/generate before the write" ordering
    `create_invitation` already uses for ID-proof uploads.
    """
    if invitation.status not in _ACTIVE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not eligible for a badge"
        )
    if invitation.badge_number is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A badge is already issued for this invitation; use the reprint endpoint",
        )
    repo = InvitationRepository(tenant_db)
    badge_number = await _generate_unique_badge_number(repo)
    qr_code = await _issue_qr_code(tenant_db, invitation, tenant=tenant)
    png = await badge.render_badge_png(
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        expires_at=invitation.expires_at,
        qr_token=qr_code.qr_token,
    )
    storage_key = await storage_save(tenant.id, "invitations/badges", png, "image/png")
    updated = await repo.issue_badge_if_eligible(
        invitation.id, badge_number=badge_number, badge_storage_key=storage_key
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not eligible for a badge"
        )
    await tenant_db.commit()
    return updated


async def reprint_badge(
    tenant_db: AsyncSession, invitation: Invitation, *, tenant: Tenant
) -> Invitation:
    """spec.md "A Badge Can Be Reprinted" — re-renders from the invitation's
    *current* data (not what was captured at original issuance), so a
    reprint after a reschedule/extension reflects the up-to-date values.
    """
    if invitation.badge_number is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No badge has been issued for this invitation yet; use the issuance endpoint",
        )
    qr_code = await _issue_qr_code(tenant_db, invitation, tenant=tenant)
    png = await badge.render_badge_png(
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        expires_at=invitation.expires_at,
        qr_token=qr_code.qr_token,
    )
    storage_key = await storage_save(tenant.id, "invitations/badges", png, "image/png")
    updated = await InvitationRepository(tenant_db).reprint_badge_if_issued(
        invitation.id, badge_storage_key=storage_key
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No badge has been issued for this invitation yet; use the issuance endpoint",
        )
    await tenant_db.commit()
    return updated


async def override_watchlist(
    tenant_db: AsyncSession, invitation: Invitation, *, user_id: uuid.UUID, reason: str
) -> Invitation:
    """spec.md "A Watchlist-Flagged Invitation Blocks Check-In Until
    Overridden" — clears the flag only; it does not itself check the
    invitation in.
    """
    updated = await InvitationRepository(tenant_db).override_watchlist_if_flagged(
        invitation.id, user_id=user_id, reason=reason
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Invitation is not currently watchlist-flagged"
        )
    await tenant_db.commit()
    return updated
