import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.access_control.decision import AccessDecision, DenyReason, can_enter
from vmss_api.access_control.models import Zone
from vmss_api.access_control.repository import (
    ZoneEventRepository,
    ZoneMappingRepository,
    ZoneRepository,
)
from vmss_api.access_control.schemas import ScanDirection, ScanRequest, ZoneCreate, ZoneUpdate
from vmss_api.auth.models import User
from vmss_api.auth.repository import RoleRepository
from vmss_api.checkin import service as checkin_service
from vmss_api.checkin.badge_token import verify_badge_token
from vmss_api.core.config import settings
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.redis import get_redis
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.tenancy import TenantContext
from vmss_api.invitations.models import Invitation
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.deps import authorize_branch_id

_SECURITY_ROLE = "security"


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message)


# --- zone CRUD ------------------------------------------------------------------


async def _validate_links(
    repo: ZoneRepository,
    *,
    branch_id: uuid.UUID,
    building_id: uuid.UUID | None,
    floor_id: uuid.UUID | None,
    gate_ids: list[uuid.UUID] | None,
) -> None:
    """Building, floor and gates must belong to the zone's own branch
    (design.md Decision 2) — a FK cannot express that."""
    if building_id is not None and not await repo.building_in_branch(building_id, branch_id):
        raise _unprocessable("Building does not belong to the zone's branch")
    if floor_id is not None and (
        building_id is None or not await repo.floor_in_building(floor_id, building_id)
    ):
        raise _unprocessable("Floor does not belong to the zone's building")
    if gate_ids and await repo.count_gates_in_branch(gate_ids, branch_id) != len(set(gate_ids)):
        raise _unprocessable("Every gate must be a security device of the zone's branch")


async def create_zone(tenant_db: AsyncSession, payload: ZoneCreate) -> tuple[Zone, list[uuid.UUID]]:
    repo = ZoneRepository(tenant_db)
    if await repo.get_by_code(payload.branch_id, payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Zone code already exists")
    await _validate_links(
        repo,
        branch_id=payload.branch_id,
        building_id=payload.building_id,
        floor_id=payload.floor_id,
        gate_ids=payload.gate_ids,
    )
    zone = Zone(
        id=uuid.uuid4(),
        branch_id=payload.branch_id,
        building_id=payload.building_id,
        floor_id=payload.floor_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        is_active=payload.is_active,
    )
    tenant_db.add(zone)
    await tenant_db.flush()
    await repo.replace_gates(zone.id, payload.gate_ids)
    await tenant_db.commit()
    await tenant_db.refresh(zone)
    return zone, sorted(set(payload.gate_ids))


async def get_zone(
    tenant_db: AsyncSession, zone_id: uuid.UUID, user: User, permission_code: str
) -> tuple[Zone, list[uuid.UUID]]:
    repo = ZoneRepository(tenant_db)
    zone = await repo.get(zone_id)
    if zone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone not found")
    await authorize_branch_id(tenant_db, user, permission_code, zone.branch_id)
    return zone, (await repo.gate_ids_by_zone([zone.id]))[zone.id]


async def list_zones_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    is_active: bool | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[tuple[Zone, list[uuid.UUID]]], int]:
    repo = ZoneRepository(tenant_db)
    zones, total = await repo.list_page(
        branch_scope=branch_scope,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    gates = await repo.gate_ids_by_zone([z.id for z in zones])
    return [(z, gates[z.id]) for z in zones], total


async def update_zone(
    tenant_db: AsyncSession, zone_id: uuid.UUID, payload: ZoneUpdate, user: User
) -> tuple[Zone, list[uuid.UUID]]:
    zone, gate_ids = await get_zone(tenant_db, zone_id, user, "zones:manage")
    repo = ZoneRepository(tenant_db)
    fields = payload.model_fields_set
    building_id = payload.building_id if "building_id" in fields else zone.building_id
    floor_id = payload.floor_id if "floor_id" in fields else zone.floor_id
    if "building_id" in fields and "floor_id" not in fields and building_id is None:
        floor_id = None
    new_gates = payload.gate_ids if "gate_ids" in fields else None
    await _validate_links(
        repo,
        branch_id=zone.branch_id,
        building_id=building_id,
        floor_id=floor_id,
        gate_ids=new_gates,
    )
    zone.building_id, zone.floor_id = building_id, floor_id
    for name in ("name", "description", "is_active"):
        if name not in fields:
            continue
        value = getattr(payload, name)
        # `description` may be cleared with null; `name`/`is_active` may not.
        if value is not None or name == "description":
            setattr(zone, name, value)
    if new_gates is not None:
        await repo.replace_gates(zone.id, new_gates)
        gate_ids = sorted(set(new_gates))
    await tenant_db.commit()
    await tenant_db.refresh(zone)
    return zone, gate_ids


async def delete_zone(tenant_db: AsyncSession, zone_id: uuid.UUID, user: User) -> Zone:
    zone, _ = await get_zone(tenant_db, zone_id, user, "zones:manage")
    zone.deleted_at = datetime.now(UTC)
    await tenant_db.commit()
    return zone


# --- allowed-zone mapping -----------------------------------------------------


async def set_category_zones(
    tenant_db: AsyncSession, category_id: uuid.UUID, zone_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    mapping = ZoneMappingRepository(tenant_db)
    if not await mapping.category_exists(category_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Visitor category not found")
    if await ZoneRepository(tenant_db).count_by_ids(zone_ids) != len(set(zone_ids)):
        raise _unprocessable("Every zone must be an existing zone")
    await mapping.replace_category_zones(category_id, zone_ids)
    await tenant_db.commit()
    return sorted(set(zone_ids))


async def get_category_zones(tenant_db: AsyncSession, category_id: uuid.UUID) -> list[uuid.UUID]:
    mapping = ZoneMappingRepository(tenant_db)
    if not await mapping.category_exists(category_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Visitor category not found")
    return sorted(await mapping.category_zone_ids(category_id))


async def _editable_invitation(
    tenant_db: AsyncSession, invitation_id: uuid.UUID, user: User, permission_code: str
) -> Invitation:
    invitation = await ZoneMappingRepository(tenant_db).get_invitation(invitation_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if not user.has_permission(permission_code, branch_id=invitation.branch_id):
        logger.warning(
            "permission_denied",
            permission_code=permission_code,
            branch_id=str(invitation.branch_id),
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permission")
    return invitation


async def set_invitation_zones(
    tenant_db: AsyncSession, invitation_id: uuid.UUID, zone_ids: list[uuid.UUID], user: User
) -> list[uuid.UUID]:
    """Reception's per-visit mapping. Reuses `invitations:edit`, so reception
    needs no extra grant (design.md Decision 10)."""
    invitation = await _editable_invitation(tenant_db, invitation_id, user, "invitations:edit")
    if await ZoneRepository(tenant_db).count_in_branch(zone_ids, invitation.branch_id) != len(
        set(zone_ids)
    ):
        raise _unprocessable("Every zone must be an existing zone of the invitation's branch")
    await ZoneMappingRepository(tenant_db).replace_invitation_zones(
        invitation_id, zone_ids, assigned_by_user_id=user.id
    )
    await tenant_db.commit()
    return sorted(set(zone_ids))


async def get_invitation_zones(
    tenant_db: AsyncSession, invitation_id: uuid.UUID, user: User
) -> list[uuid.UUID]:
    invitation = await _editable_invitation(tenant_db, invitation_id, user, "zones:view")
    return sorted(await ZoneMappingRepository(tenant_db).invitation_zone_ids(invitation.id))


# --- gate scan ---------------------------------------------------------------


@dataclass(frozen=True)
class ScanResult:
    decision: AccessDecision
    direction: ScanDirection
    visit: Invitation
    zone: Zone
    gate_id: uuid.UUID


async def scan(
    tenant_db: AsyncSession,
    *,
    user: User,
    tenant: TenantContext,
    payload: ScanRequest,
    now: datetime | None = None,
) -> ScanResult:
    """One gate scan. The badge token must be ours, for this caller's tenant,
    active and for today (`resolve_active_badge`) — every failure is the same
    generic invalid-token response. Exit is never denied (design.md Decision 6)."""
    now = now or datetime.now(UTC)
    claims = verify_badge_token(payload.token)
    if claims is None or claims.tenant_id != tenant.id:
        raise checkin_service.invalid_token()
    visit, _ = await checkin_service.resolve_active_badge(tenant_db, claims, tenant=tenant)
    if not user.has_permission("access:scan", branch_id=visit.branch_id):
        logger.warning(
            "permission_denied", permission_code="access:scan", branch_id=str(visit.branch_id)
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permission")

    zones = ZoneRepository(tenant_db)
    events = ZoneEventRepository(tenant_db)
    zone = await zones.get_including_deleted(payload.zone_id)
    gate = await events.get_gate(payload.gate_id)
    if zone is None or gate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone or gate device not found")

    if payload.direction is ScanDirection.exit:
        decision = AccessDecision(allowed=True)
    else:
        allowed_ids = await ZoneMappingRepository(tenant_db).effective_zone_ids(
            visit.id, visit.visitor_category_id
        )
        decision = can_enter(
            visit,
            zone,
            gate_serves_zone=await zones.gate_serves_zone(zone.id, gate.id),
            allowed_zone_ids=allowed_ids,
            now=now,
            local_today=checkin_service.tenant_today(tenant, now),
        )
    events.add(
        invitation_id=visit.id,
        zone_id=zone.id,
        gate_id=gate.id,
        direction=payload.direction.value,
        decision="allowed" if decision.allowed else "denied",
        reason=decision.reason.value if decision.reason else None,
        scanned_by_user_id=user.id,
        occurred_at=now,
    )
    await tenant_db.commit()
    return ScanResult(
        decision=decision, direction=payload.direction, visit=visit, zone=zone, gate_id=gate.id
    )


# --- denied-entry alert -------------------------------------------------------


async def alert_security_of_denial(
    *,
    tenant_id: uuid.UUID,
    tenant_schema: str,
    branch_id: uuid.UUID,
    invitation_id: uuid.UUID,
    zone_id: uuid.UUID,
    zone_name: str,
    reason: DenyReason,
) -> None:
    """Background task: push to Security at the visit's branch, at most once per
    (visit, zone, reason) per dedupe window. Names the zone and reason code,
    never the visitor (design.md Decision 7). Redis trouble means a rare
    duplicate alert rather than none, same stance as `core/notification_dedupe.py`."""
    key = f"vmss:{tenant_id}:access_control:denial:{invitation_id}:{zone_id}:{reason.value}"
    try:
        first = await (await get_redis()).set(
            key, "1", nx=True, ex=settings.zone_denial_alert_dedupe_seconds
        )
        if not first:
            return
    except Exception:
        logger.warning("zone_denial_alert_dedupe_unavailable", exc_info=True)
    async with tenant_session_scope(tenant_schema) as tenant_db:
        role = await RoleRepository(tenant_db).get_by_name_case_insensitive(_SECURITY_ROLE)
        if role is None:
            logger.warning("zone_denial_alert_no_security_role", branch_id=str(branch_id))
            return
        await notifications_service.notify_role_at_branch(
            tenant_db,
            tenant_schema=tenant_schema,
            role_id=role.id,
            branch_id=branch_id,
            title="Zone entry denied",
            body=f"Entry to {zone_name} was denied ({reason.value}).",
            data={"type": "zone_entry_denied", "zoneId": str(zone_id), "reason": reason.value},
            reason="zone_entry_denied",
        )
