import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.core.logging import logger
from vmss_api.notifications import tasks
from vmss_api.notifications.models import DeviceToken
from vmss_api.notifications.repository import DeviceTokenRepository
from vmss_api.notifications.schemas import DevicePlatform


def _current_request_id() -> str:
    return structlog.contextvars.get_contextvars().get("request_id", "")


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
        request_id=_current_request_id(),
        tenant_schema=tenant_schema,
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
) -> None:
    """Resolves every user holding `role_id` at `branch_id` (or company-wide)
    synchronously, then enqueues one dispatch addressed to that resolved set
    (design.md Decision 2/3). Zero holders logs `WARNING` and is otherwise a
    no-op — not an error for the triggering action (proposal.md's "no push
    recipient" case).

    Adds `assignedRoleId`/`reason` addressing metadata to the payload
    (role-based-invitation-workflow), `reason: "role_assigned"` — the
    role-fan-out counterpart of `notify_user`'s `assignedUserId`/`delegated`.
    """
    user_ids = await UserRepository(tenant_db).list_user_ids_holding_role_at_branch(
        role_id, branch_id
    )
    if not user_ids:
        logger.warning(
            "push_notify_role_no_holders", role_id=str(role_id), branch_id=str(branch_id)
        )
        return
    tasks.send_push.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant_schema,
        user_ids=[str(user_id) for user_id in user_ids],
        title=title,
        body=body,
        data={**(data or {}), "assignedRoleId": str(role_id), "reason": "role_assigned"},
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
    every role, not just Admin). A role id that doesn't resolve to a row
    dispatches normally (fails open, not closed) rather than silently
    dropping the push.
    """
    if approver_user_id is not None:
        await notify_user(
            tenant_schema=tenant_schema, user_id=approver_user_id, title=title, body=body, data=data
        )
        return
    assert approver_role_id is not None  # DB CHECK: exactly one of the two is set
    role = await RoleRepository(tenant_db).get(approver_role_id)
    if role is not None and role.name.lower() == "admin":
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
