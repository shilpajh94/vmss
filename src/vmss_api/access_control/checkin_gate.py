"""Zone check at front-desk QR / code check-in (add-zone-access-control).

When the tenant's zone toggle is on and the check-in comes from a security
device linked to exactly one zone, the check-in is also an entry into that zone:
it is judged by `can_enter` and logged in `zone_access_events`. A device that is
absent, not in security mode, or linked to no zone / several zones is not tied to
one zone, so the check-in proceeds exactly as before and nothing is logged.

Imported lazily by `invitations/checkin.py` (this module reaches back into
`invitations`/`checkin`, so a top-level import would be circular).
"""

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.access_control.decision import DenyReason, can_enter
from vmss_api.access_control.repository import (
    ZoneEventRepository,
    ZoneMappingRepository,
    ZoneRepository,
)
from vmss_api.access_control.service import alert_security_of_denial
from vmss_api.auth.repository import AuditLogWriter
from vmss_api.core.logging import logger
from vmss_api.devices.models import Device
from vmss_api.invitations.models import Invitation
from vmss_api.tenant.models import Tenant


class ZoneEntryDenied(HTTPException):
    """403 at check-in; `reason` is the stable `DenyReason` value."""

    def __init__(self, reason: DenyReason) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, detail="Zone entry denied")
        self.reason = reason


async def enforce_checkin_zone(
    tenant_db: AsyncSession,
    tenant: Tenant,
    invitation: Invitation,
    device: Device | None,
    *,
    today_local: date,
) -> None:
    """Call after the ordinary eligibility checks and before the check-in is
    committed. Allowed: stages an `entry` event in the caller's transaction, so it
    commits (or rolls back) together with the check-in. Denied: commits a `denied`
    event and an audit row, alerts Security, and raises `ZoneEntryDenied` so the
    visitor is not checked in."""
    if not tenant.zone_access_enabled or device is None or device.operating_mode != "security":
        return
    zones = await ZoneRepository(tenant_db).live_zones_for_gate(device.id)
    if len(zones) != 1:
        if len(zones) > 1:
            logger.info("checkin_zone_ambiguous", device_id=str(device.id), zone_count=len(zones))
        return
    zone = zones[0]
    allowed_ids = await ZoneMappingRepository(tenant_db).effective_zone_ids(
        invitation.id, invitation.visitor_category_id, invitation.branch_id
    )
    # Judged as the visit will stand once this check-in succeeds, so the
    # "not checked in yet" rule (which only matters for door scans) cannot fire.
    after_check_in = SimpleNamespace(
        status="checked_in",
        check_in_status="checked_in",
        branch_id=invitation.branch_id,
        expires_at=invitation.expires_at,
        preferred_visit_date=invitation.preferred_visit_date,
        watchlist_flagged=invitation.watchlist_flagged,
        watchlist_override_at=invitation.watchlist_override_at,
    )
    now = datetime.now(UTC)
    decision = can_enter(
        after_check_in,
        zone,
        gate_serves_zone=True,
        allowed_zone_ids=allowed_ids,
        now=now,
        local_today=today_local,
    )
    events = ZoneEventRepository(tenant_db)
    events.add(
        invitation_id=invitation.id,
        zone_id=zone.id,
        gate_id=device.id,
        direction="entry",
        decision="allowed" if decision.allowed else "denied",
        reason=decision.reason.value if decision.reason else None,
        scanned_by_user_id=None,
        occurred_at=now,
    )
    if decision.allowed or decision.reason is None:
        return
    reason = decision.reason
    logger.warning(
        "zone_entry_denied",
        invitation_id=str(invitation.id),
        zone_id=str(zone.id),
        gate_id=str(device.id),
        reason=reason.value,
        source="checkin",
    )
    AuditLogWriter(tenant_db).add(
        actor_user_id=None,
        action="zone_entry_denied",
        entity_type="Invitation",
        entity_id=invitation.id,
        diff={"zone_id": str(zone.id), "gate_id": str(device.id), "reason": reason.value},
    )
    await tenant_db.commit()
    await _alert(tenant, invitation.branch_id, invitation.id, zone.id, zone.name, reason)
    raise ZoneEntryDenied(reason)


async def _alert(
    tenant: Tenant,
    branch_id: uuid.UUID,
    invitation_id: uuid.UUID,
    zone_id: uuid.UUID,
    zone_name: str,
    reason: DenyReason,
) -> None:
    # Never let an alert problem turn a clean denial into a 500.
    try:
        await alert_security_of_denial(
            tenant_id=tenant.id,
            tenant_schema=tenant.schema_name,
            branch_id=branch_id,
            invitation_id=invitation_id,
            zone_id=zone_id,
            zone_name=zone_name,
            reason=reason,
        )
    except Exception:
        logger.warning("zone_denial_alert_failed", exc_info=True)
