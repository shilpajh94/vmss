from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from vmss_api.auth.rbac_catalog import DELEGATION_ONLY_ROLE_NAMES
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.core.logging import current_request_id, logger
from vmss_api.core.schemas import SortOrder
from vmss_api.notifications import tasks
from vmss_api.notifications.models import DeviceToken, Notification
from vmss_api.notifications.repository import DeviceTokenRepository, NotificationRepository
from vmss_api.notifications.schemas import DevicePlatform

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# In-app notifications are disposable UI state; anything older is purged by
# the recurring visit-lifecycle sweep (fix-web-push-and-add-notification-
# feed design.md D4).
NOTIFICATION_RETENTION = timedelta(days=90)


async def register_device(
    tenant_db: AsyncSession, *, user_id: uuid.UUID, fcm_token: str, platform: DevicePlatform
) -> DeviceToken:
    device = await DeviceTokenRepository(tenant_db).upsert_by_token(
        user_id=user_id, fcm_token=fcm_token, platform=platform.value
    )
    await tenant_db.commit()
    return device


async def unregister_device(tenant_db: AsyncSession, *, user_id: uuid.UUID, fcm_token: str) -> None:
    await DeviceTokenRepository(tenant_db).delete_owned_by_user(
        user_id=user_id, fcm_token=fcm_token
    )
    await tenant_db.commit()


async def notify_user(
    *,
    tenant_schema: str,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    """specs/notifications/spec.md "Push Dispatch Is Addressed by User or by
    Role at a Branch" — dispatch to a specific user id. Enqueues the
    resolved recipient itself (design.md Decision 2): the task resolves
    *devices* for `user_id` fresh at send time, it is never asked to
    re-derive who the recipient is.

    Adds `assignedUserId`/`reason` addressing metadata to the payload
    (role-based-invitation-workflow, "Push Payloads Exclude Sensitive
    Visitor Data") so a client can distinguish this from a role-fan-out push
    — every specific-user dispatch (a resolved host, a step delegate) is
    `reason: "delegated"`, regardless of whether an actual delegation action
    triggered it.
    """
    tasks.send_push.delay(
        request_id=current_request_id(),
        tenant_schema=tenant_schema,
        dispatch_id=str(uuid.uuid4()),
        user_ids=[str(user_id)],
        title=title,
        body=body,
        data={**(data or {}), "assignedUserId": str(user_id), "reason": "delegated"},
    )


async def notify_role_at_branch(
    tenant_db: AsyncSession,
    *,
    tenant_schema: str,
    role_id: uuid.UUID,
    branch_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    exclude_user_ids: Collection[uuid.UUID] = (),
    reason: str = "role_assigned",
) -> None:
    """Resolves every user holding `role_id` at `branch_id` (or company-wide)
    synchronously, then enqueues one dispatch addressed to that resolved set
    (design.md Decision 2/3). Zero holders logs `WARNING` and is otherwise a
    no-op — not an error for the triggering action (proposal.md's "no push
    recipient" case).

    Adds `assignedRoleId`/`reason` addressing metadata to the payload
    (role-based-invitation-workflow), `reason: "role_assigned"` by default —
    the role-fan-out counterpart of `notify_user`'s `assignedUserId`/
    `delegated`. A point-of-contact lifecycle push passes
    `reason="lifecycle_update"` so a client doesn't label it a new
    assignment, and `exclude_user_ids` to skip the actor and the host, who
    already get their own push (staff-lifecycle-emails-and-dashboard-landing
    design.md D4).
    """
    user_ids = [
        user_id
        for user_id in await UserRepository(tenant_db).list_user_ids_holding_role_at_branch(
            role_id, branch_id
        )
        if user_id not in exclude_user_ids
    ]
    if not user_ids:
        logger.warning(
            "push_notify_role_no_holders", role_id=str(role_id), branch_id=str(branch_id)
        )
        return
    tasks.send_push.delay(
        request_id=current_request_id(),
        tenant_schema=tenant_schema,
        dispatch_id=str(uuid.uuid4()),
        user_ids=[str(user_id) for user_id in user_ids],
        title=title,
        body=body,
        data={**(data or {}), "assignedRoleId": str(role_id), "reason": reason},
    )


async def notify_step_approver(
    tenant_db: AsyncSession,
    *,
    tenant_schema: str,
    approver_user_id: uuid.UUID | None,
    approver_role_id: uuid.UUID | None,
    branch_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    """Shared entry point for `invitations/service.py` (submission) and
    `approvals/service.py` (`_activate_next_step`) — both resolve to the same
    "host-identified or role-identified" approver shape
    (`approvals/models.py::InvitationApprovalStep`'s CHECK-enforced XOR), so
    the branch lives here once instead of being duplicated at each call site.

    A role-identified step dispatches to every holder of that role at
    `branch_id`, same as `notify_role_at_branch` — except when the role is
    the tenant's standard `admin` role (matched by name, case-insensitively;
    `admin` is seeded non-renameable/non-deletable per `auth/rbac_catalog.py`,
    so it's a reliable cross-tenant identifier), which SHALL NOT receive a
    push (exclude-admin-role-only-from-push/design.md — a correction of
    restrict-invitation-push-to-hosts-only, which over-broadly excluded
    every role, not just Admin), nor when the role is one of
    `DELEGATION_ONLY_ROLE_NAMES` (`host`) — an undelegated host-identified
    step isn't actionable by any role holder either
    (`approvals/service.py::_caller_matches_step`), so broadcasting "act on
    this now" to every host-eligible employee company-wide would be both
    noisy and misleading. A role id that doesn't resolve to a row dispatches
    normally (fails open, not closed) rather than silently dropping the
    push.
    """
    if approver_user_id is not None:
        await notify_user(
            tenant_schema=tenant_schema, user_id=approver_user_id, title=title, body=body, data=data
        )
        return
    assert approver_role_id is not None  # DB CHECK: exactly one of the two is set
    role = await RoleRepository(tenant_db).get(approver_role_id)
    if role is not None and (
        role.name.lower() == "admin" or role.name.lower() in DELEGATION_ONLY_ROLE_NAMES
    ):
        return
    await notify_role_at_branch(
        tenant_db,
        tenant_schema=tenant_schema,
        role_id=approver_role_id,
        branch_id=branch_id,
        title=title,
        body=body,
        data=data,
    )


async def list_notifications(
    tenant_db: AsyncSession,
    *,
    user_id: uuid.UUID,
    unread_only: bool,
    page: int,
    page_size: int,
    sort_by: str = "created_at",
    sort_order: SortOrder = SortOrder.desc,
) -> tuple[list[Notification], int]:
    return await NotificationRepository(tenant_db).list_page(
        user_id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def count_unread(tenant_db: AsyncSession, *, user_id: uuid.UUID) -> int:
    return await NotificationRepository(tenant_db).count_unread(user_id)


async def mark_read(
    tenant_db: AsyncSession, *, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    """404 for an unknown id and for another user's notification alike, so
    the response never reveals whether someone else's id exists.
    """
    notification = await NotificationRepository(tenant_db).mark_read(user_id, notification_id)
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await tenant_db.commit()
    return notification


async def mark_all_read(tenant_db: AsyncSession, *, user_id: uuid.UUID) -> None:
    await NotificationRepository(tenant_db).mark_all_read(user_id)
    await tenant_db.commit()


async def purge_expired_notifications(session: AsyncSession, *, now: datetime) -> int:
    """Hard-deletes notifications older than `NOTIFICATION_RETENTION`, in its
    own commit. Returns how many were deleted.
    """
    purged = await NotificationRepository(session).purge_older_than(now - NOTIFICATION_RETENTION)
    await session.commit()
    return purged
