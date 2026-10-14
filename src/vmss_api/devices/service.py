import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.logging import logger
from vmss_api.core.schemas import SortOrder
from vmss_api.devices.models import Device, TenantSettings
from vmss_api.devices.repository import DeviceRepository, TenantSettingsRepository
from vmss_api.devices.schemas import (
    ApprovalStatus,
    DeviceBriefOut,
    DeviceOut,
    DeviceRegister,
    OperatingMode,
)
from vmss_api.org_structure.repository import BranchRepository, BuildingRepository


async def _get_or_404(repo: DeviceRepository, device_pk: uuid.UUID) -> Device:
    device = await repo.get(device_pk)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


async def _validate_location(
    tenant_db: AsyncSession, branch_id: uuid.UUID, building_id: uuid.UUID | None
) -> None:
    branch = await BranchRepository(tenant_db).get(branch_id)
    if branch is None or not branch.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Branch not found")
    if building_id is None:
        return
    building = await BuildingRepository(tenant_db).get(building_id)
    if building is None or not building.is_active or building.branch_id != branch_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Building not found in the selected branch",
        )


async def register_device(tenant_db: AsyncSession, payload: DeviceRegister) -> tuple[Device, bool]:
    """Returns `(device, created)`. An existing live `device_id` is returned
    as-is and never mutated, so a device can't relocate itself after
    approval (design.md Decision 5)."""
    repo = DeviceRepository(tenant_db)
    existing = await repo.get_by_device_id(payload.device_id)
    if existing is not None:
        return existing, False
    await _validate_location(tenant_db, payload.branch_id, payload.building_id)
    device = Device(
        id=uuid.uuid4(),
        device_id=payload.device_id,
        name=payload.name,
        branch_id=payload.branch_id,
        building_id=payload.building_id,
        operating_mode=payload.operating_mode.value,
        approval_status=ApprovalStatus.pending.value,
        is_active=False,
    )
    tenant_db.add(device)
    try:
        await tenant_db.commit()
    except IntegrityError:
        # Two simultaneous first registrations of the same device_id.
        await tenant_db.rollback()
        existing = await repo.get_by_device_id(payload.device_id)
        if existing is None:
            raise
        return existing, False
    await tenant_db.refresh(device)
    return device, True


async def list_devices_page(
    tenant_db: AsyncSession,
    *,
    approval_status: ApprovalStatus | None,
    is_active: bool | None,
    operating_mode: OperatingMode | None,
    branch_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[DeviceOut], int]:
    rows, total = await DeviceRepository(tenant_db).list_page(
        approval_status=approval_status.value if approval_status else None,
        is_active=is_active,
        operating_mode=operating_mode.value if operating_mode else None,
        branch_id=branch_id,
        building_id=building_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [_to_out(d, branch_name, building_name) for d, branch_name, building_name in rows], total


def _to_out(device: Device, branch_name: str | None, building_name: str | None) -> DeviceOut:
    out = DeviceOut.model_validate(device)
    out.branch_name = branch_name
    out.building_name = building_name
    return out


async def get_device_out(tenant_db: AsyncSession, device_pk: uuid.UUID) -> DeviceOut:
    repo = DeviceRepository(tenant_db)
    device = await _get_or_404(repo, device_pk)
    return _to_out(device, *await repo.names_for(device))


async def approve_device(
    tenant_db: AsyncSession, device_pk: uuid.UUID, *, approver_id: uuid.UUID
) -> tuple[DeviceOut, bool]:
    """Returns `(device, changed)`; approving an approved device is a no-op."""
    repo = DeviceRepository(tenant_db)
    device = await _get_or_404(repo, device_pk)
    changed = device.approval_status != ApprovalStatus.approved.value
    if changed:
        device.approval_status = ApprovalStatus.approved.value
        device.is_active = True
        device.approved_at = datetime.now(UTC)
        device.approved_by_user_id = approver_id
        await tenant_db.commit()
        await tenant_db.refresh(device)
    return _to_out(device, *await repo.names_for(device)), changed


async def set_device_active(
    tenant_db: AsyncSession, device_pk: uuid.UUID, *, active: bool
) -> tuple[DeviceOut, bool]:
    repo = DeviceRepository(tenant_db)
    device = await _get_or_404(repo, device_pk)
    if device.approval_status != ApprovalStatus.approved.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Device must be approved before it can be enabled"
        )
    changed = device.is_active != active
    if changed:
        device.is_active = active
        await tenant_db.commit()
        await tenant_db.refresh(device)
    return _to_out(device, *await repo.names_for(device)), changed


async def delete_device(tenant_db: AsyncSession, device_pk: uuid.UUID) -> None:
    repo = DeviceRepository(tenant_db)
    device = await _get_or_404(repo, device_pk)
    await repo.soft_delete(device)
    await tenant_db.commit()


async def resolve_usable_device(tenant_db: AsyncSession, device_id: str) -> Device:
    """403 unless the `device-id` header names a live, approved, enabled
    device. The three failure causes share one message so the response
    doesn't reveal which device ids exist."""
    device = await DeviceRepository(tenant_db).get_by_device_id(device_id)
    if (
        device is None
        or device.approval_status != ApprovalStatus.approved.value
        or not device.is_active
    ):
        logger.warning("device_not_authorized", device_id=device_id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Device is not authorized")
    return device


async def device_briefs(
    tenant_db: AsyncSession, *device_pks: uuid.UUID | None
) -> dict[uuid.UUID, DeviceBriefOut]:
    found = await DeviceRepository(tenant_db).get_many(p for p in device_pks if p is not None)
    return {pk: DeviceBriefOut.model_validate(d) for pk, d in found.items()}


async def get_enforce_location_validation(tenant_db: AsyncSession) -> bool:
    row = await TenantSettingsRepository(tenant_db).get()
    return True if row is None else row.enforce_kiosk_location_validation


async def set_enforce_location_validation(tenant_db: AsyncSession, enabled: bool) -> bool:
    repo = TenantSettingsRepository(tenant_db)
    row = await repo.get()
    if row is None:
        row = TenantSettings(id=uuid.uuid4(), enforce_kiosk_location_validation=enabled)
        tenant_db.add(row)
    else:
        row.enforce_kiosk_location_validation = enabled
    await tenant_db.commit()
    return enabled


def check_device_location(
    device: Device, *, invitation_branch_id: uuid.UUID, invitation_building_id: uuid.UUID | None
) -> None:
    """422 when the device's registered branch (or, if the invitation has
    one, building) differs from the invitation's. Call only when enforcement
    is on and before any state change."""
    if device.branch_id != invitation_branch_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Check-in not allowed: this device is registered to a different branch",
        )
    if invitation_building_id is not None and device.building_id != invitation_building_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Check-in not allowed: this device is registered to a different building",
        )
