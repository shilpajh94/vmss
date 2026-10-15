import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import DeviceTokenFactory, RoleFactory, UserFactory
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.notifications import fcm, service, tasks
from vmss_api.notifications.repository import DeviceTokenRepository
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


# --- Device registration -----------------------------------------------------


async def test_register_device_success(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/notifications/devices",
        json={"fcmToken": "fcm-token-abc", "platform": "web"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["platform"] == "web"

    stored = await DeviceTokenRepository(db_session).get_by_token("fcm-token-abc")
    assert stored is not None
    assert stored.user_id == user.id


async def test_register_device_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/notifications/devices", json={"fcmToken": "fcm-token-xyz", "platform": "web"}
    )
    assert response.status_code == 401


async def test_register_device_re_registration_updates_existing_row(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    token = await _login(client, user.email)
    await client.post(
        "/api/v1/notifications/devices",
        json={"fcmToken": "same-token", "platform": "web"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await client.post(
        "/api/v1/notifications/devices",
        json={"fcmToken": "same-token", "platform": "android"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    repo = DeviceTokenRepository(db_session)
    stored = await repo.get_by_token("same-token")
    assert stored is not None
    assert stored.platform == "android"
    assert len(await repo.list_tokens_for_users([user.id])) == 1  # updated, not duplicated


async def test_register_device_reassigns_token_from_previous_owner(
    client: AsyncClient,
    user: User,
    user_without_permissions: User,
    db_session: AsyncSession,
) -> None:
    """specs/notifications/spec.md "A token registered by one user cannot be
    silently reassigned to another" — the *newest* registrant owns a token,
    since a device is physically one browser/app install.
    """
    db_session.add(
        DeviceTokenFactory.build(
            id=uuid.uuid4(),
            user_id=user_without_permissions.id,
            fcm_token="shared-token",
            platform="web",
        )
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/notifications/devices",
        json={"fcmToken": "shared-token", "platform": "android"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    stored = await DeviceTokenRepository(db_session).get_by_token("shared-token")
    assert stored is not None
    assert stored.user_id == user.id
    assert stored.platform == "android"


# --- Device unregistration ---------------------------------------------------


async def test_unregister_device_success(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    db_session.add(
        DeviceTokenFactory.build(
            id=uuid.uuid4(), user_id=user.id, fcm_token="to-remove", platform="web"
        )
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.delete(
        "/api/v1/notifications/devices/to-remove", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert await DeviceTokenRepository(db_session).get_by_token("to-remove") is None


async def test_unregister_device_requires_auth(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/notifications/devices/some-token")
    assert response.status_code == 401


async def test_unregister_unknown_device_is_not_an_error(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        "/api/v1/notifications/devices/never-registered",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_unregister_device_owned_by_another_user_is_a_no_op(
    client: AsyncClient,
    user: User,
    user_without_permissions: User,
    db_session: AsyncSession,
) -> None:
    db_session.add(
        DeviceTokenFactory.build(
            id=uuid.uuid4(),
            user_id=user_without_permissions.id,
            fcm_token="someone-elses-token",
            platform="web",
        )
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.delete(
        "/api/v1/notifications/devices/someone-elses-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    stored = await DeviceTokenRepository(db_session).get_by_token("someone-elses-token")
    assert stored is not None  # untouched — belonged to a different user


# --- Tenant isolation ---------------------------------------------------------


async def test_device_token_tenant_isolation(
    make_tenant_schema, open_tenant_session, user: User, db_session: AsyncSession
) -> None:
    """See testing-standards.md §2 / auth/tests.py::test_tenant_schema_isolation
    for the reference example — a session bound to a different tenant's
    schema must not see this tenant's `device_tokens` row.
    """
    db_session.add(
        DeviceTokenFactory.build(
            id=uuid.uuid4(), user_id=user.id, fcm_token="tenant-scoped-token", platform="web"
        )
    )
    await db_session.commit()

    other_schema = "tenant_other_notifications_test"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await DeviceTokenRepository(other_session).get_by_token("tenant-scoped-token")
        assert found is None


# --- Push dispatch task -------------------------------------------------------


async def test_send_push_skips_recipient_with_no_registered_device(tenant: Tenant) -> None:
    result = await asyncio.to_thread(
        tasks.send_push.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "user_ids": [str(uuid.uuid4())],
            "title": "Title",
            "body": "Body",
            "data": {},
        },
    )
    result.get(propagate=True)  # specs/notifications/spec.md: not an error


async def test_send_push_delivers_to_every_registered_device(
    monkeypatch, tenant: Tenant, user: User, db_session: AsyncSession
) -> None:
    db_session.add(
        DeviceTokenFactory.build(
            id=uuid.uuid4(), user_id=user.id, fcm_token="device-a", platform="web"
        )
    )
    db_session.add(
        DeviceTokenFactory.build(
            id=uuid.uuid4(), user_id=user.id, fcm_token="device-b", platform="android"
        )
    )
    await db_session.commit()

    sent_tokens: list[str] = []

    class _RecordingPushSender:
        async def send_each(self, messages):
            sent_tokens.extend(m.token for m in messages)
            return [
                fcm.PushSendResult(token=m.token, success=True, token_invalid=False)
                for m in messages
            ]

    monkeypatch.setattr(fcm, "push_sender", _RecordingPushSender())

    result = await asyncio.to_thread(
        tasks.send_push.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "user_ids": [str(user.id)],
            "title": "Invitation approved",
            "body": "Body",
            "data": {"action": "approved"},
        },
    )
    result.get(propagate=True)
    assert sorted(sent_tokens) == ["device-a", "device-b"]


async def test_send_push_deletes_device_reported_as_unregistered(
    monkeypatch, tenant: Tenant, user: User, db_session: AsyncSession
) -> None:
    """specs/notifications/spec.md "An Invalid or Expired Device Token Is
    Removed on Delivery Failure".
    """
    db_session.add(
        DeviceTokenFactory.build(
            id=uuid.uuid4(), user_id=user.id, fcm_token="invalid-token", platform="web"
        )
    )
    await db_session.commit()

    class _RejectingPushSender:
        async def send_each(self, messages):
            return [
                fcm.PushSendResult(token=m.token, success=False, token_invalid=True)
                for m in messages
            ]

    monkeypatch.setattr(fcm, "push_sender", _RejectingPushSender())

    result = await asyncio.to_thread(
        tasks.send_push.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "user_ids": [str(user.id)],
            "title": "Title",
            "body": "Body",
            "data": {},
        },
    )
    result.get(propagate=True)

    assert await DeviceTokenRepository(db_session).get_by_token("invalid-token") is None


async def test_send_push_exhausted_retries_logs_error(monkeypatch, tenant: Tenant) -> None:
    class _FailingPushSender:
        async def send_each(self, messages):
            raise RuntimeError("FCM is unreachable")

    monkeypatch.setattr(fcm, "push_sender", _FailingPushSender())
    logged = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged.append((event, kw)))
    # `max_retries=0` means the first failure is already "exhausted" — see
    # invitations/tests.py's identical pattern for why `.apply()` needs this
    # rather than actually sleeping through a real `retry_backoff` delay.
    monkeypatch.setattr(tasks.send_push, "max_retries", 0)

    # A recipient with no registered device would short-circuit before ever
    # calling the (failing) sender, so give the task a real device to send to.
    async def _fake_send_push(tenant_schema, user_ids, title, body, data):
        raise RuntimeError("FCM is unreachable")

    monkeypatch.setattr(tasks, "_send_push", _fake_send_push)

    result = await asyncio.to_thread(
        tasks.send_push.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": tenant.schema_name,
            "user_ids": [str(uuid.uuid4())],
            "title": "Title",
            "body": "Body",
            "data": {},
        },
    )
    assert result.failed()
    assert logged and logged[0][0] == "push_dispatch_exhausted"


# --- notify_step_approver's Admin exclusion (exclude-admin-role-only-from-push) -


async def test_notify_step_approver_admin_role_sends_no_push(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    """specs/invitations/spec.md "Submission with an Admin-role first step
    sends no push" / specs/approvals/spec.md "Approving a step activates a
    role-identified step, sending no push" — the role is matched
    case-insensitively, so a role literally named `Admin` (not just the
    lowercase seed spelling) is still excluded.
    """
    admin_role = RoleFactory.build(id=uuid.uuid4(), name="Admin", permissions=[])
    db_session.add(admin_role)
    await db_session.commit()

    user_calls: list[dict] = []
    role_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        user_calls.append(kwargs)

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(service, "notify_role_at_branch", _fake_notify_role_at_branch)

    await service.notify_step_approver(
        db_session,
        tenant_schema=tenant.schema_name,
        approver_user_id=None,
        approver_role_id=admin_role.id,
        branch_id=branch.id,
        title="Title",
        body="Body",
    )

    assert user_calls == []
    assert role_calls == []


async def test_notify_step_approver_non_admin_role_dispatches(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    role = RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[])
    db_session.add(role)
    await db_session.commit()

    role_calls: list[dict] = []

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(service, "notify_role_at_branch", _fake_notify_role_at_branch)

    await service.notify_step_approver(
        db_session,
        tenant_schema=tenant.schema_name,
        approver_user_id=None,
        approver_role_id=role.id,
        branch_id=branch.id,
        title="Title",
        body="Body",
    )

    assert len(role_calls) == 1
    assert role_calls[0]["role_id"] == role.id
    assert role_calls[0]["branch_id"] == branch.id


async def test_notify_step_approver_unresolvable_role_dispatches(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    """design.md "An unresolvable role dispatches normally (fails open, not
    closed)" — a role id that doesn't resolve to any row is treated as "not
    admin" rather than silently dropping the push.
    """
    role_calls: list[dict] = []

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(service, "notify_role_at_branch", _fake_notify_role_at_branch)

    unknown_role_id = uuid.uuid4()
    await service.notify_step_approver(
        db_session,
        tenant_schema=tenant.schema_name,
        approver_user_id=None,
        approver_role_id=unknown_role_id,
        branch_id=branch.id,
        title="Title",
        body="Body",
    )

    assert len(role_calls) == 1
    assert role_calls[0]["role_id"] == unknown_role_id


# --- notify_role_at_branch's own zero-holders no-op path ----------------------


async def test_notify_role_at_branch_zero_holders_logs_warning_and_skips_dispatch(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, monkeypatch
) -> None:
    """proposal.md task 9.3 — every test above that could reach
    `notify_role_at_branch`'s zero-holders branch (e.g.
    `test_notify_step_approver_non_admin_role_dispatches`) monkeypatches the
    function itself out to a fake, so its own real body has never been
    called directly. This calls `service.notify_role_at_branch` for real,
    against a role with no `UserBranchRole` row granting it at `branch`
    (or company-wide), and asserts both halves of the no-op: no push is
    enqueued, and the `WARNING`-level `push_notify_role_no_holders` log
    fires with the role/branch ids.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="no-holders-role", permissions=[])
    db_session.add(role)
    await db_session.commit()

    delay_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_push, "delay", lambda **kwargs: delay_calls.append(kwargs))
    logged_warning: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        service.logger, "warning", lambda event, **kw: logged_warning.append((event, kw))
    )

    await service.notify_role_at_branch(
        db_session,
        tenant_schema=tenant.schema_name,
        role_id=role.id,
        branch_id=branch.id,
        title="Title",
        body="Body",
    )

    assert delay_calls == []
    assert logged_warning and logged_warning[0][0] == "push_notify_role_no_holders"
    assert logged_warning[0][1]["role_id"] == str(role.id)
    assert logged_warning[0][1]["branch_id"] == str(branch.id)


# --- Addressing metadata (role-based-invitation-workflow) --------------------


async def test_notify_user_payload_carries_assigned_user_id_and_reason(
    tenant: Tenant, user: User, monkeypatch
) -> None:
    """specs/notifications/spec.md "Delegation/host-assignment push carries
    assignedUserId and reason delegated".
    """
    delay_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_push, "delay", lambda **kwargs: delay_calls.append(kwargs))

    await service.notify_user(
        tenant_schema=tenant.schema_name, user_id=user.id, title="Title", body="Body"
    )

    assert len(delay_calls) == 1
    data = delay_calls[0]["data"]
    assert data["assignedUserId"] == str(user.id)
    assert data.get("assignedRoleId") is None
    assert data["reason"] == "delegated"


async def test_notify_role_at_branch_payload_carries_assigned_role_id_and_reason(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User, monkeypatch
) -> None:
    """specs/notifications/spec.md "Role-fan-out push carries assignedRoleId
    and reason role_assigned".
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="reception-metadata-test", permissions=[])
    db_session.add(role)
    await db_session.flush()
    db_session.add(
        UserBranchRole(id=uuid.uuid4(), user_id=user.id, role_id=role.id, branch_id=None)
    )
    await db_session.commit()

    delay_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_push, "delay", lambda **kwargs: delay_calls.append(kwargs))

    await service.notify_role_at_branch(
        db_session,
        tenant_schema=tenant.schema_name,
        role_id=role.id,
        branch_id=branch.id,
        title="Title",
        body="Body",
    )

    assert len(delay_calls) == 1
    data = delay_calls[0]["data"]
    assert data["assignedRoleId"] == str(role.id)
    assert data.get("assignedUserId") is None
    assert data["reason"] == "role_assigned"


async def test_notify_role_at_branch_excludes_users_and_overrides_reason(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User, monkeypatch
) -> None:
    """staff-lifecycle-emails-and-dashboard-landing design.md D4 — excluded
    holders are dropped from the fan-out, and a caller-supplied `reason`
    replaces the `role_assigned` default.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="poc-exclusion-test", permissions=[])
    other = UserFactory.build(id=uuid.uuid4())
    db_session.add_all([role, other])
    await db_session.flush()
    db_session.add_all(
        [
            UserBranchRole(id=uuid.uuid4(), user_id=user.id, role_id=role.id, branch_id=None),
            UserBranchRole(id=uuid.uuid4(), user_id=other.id, role_id=role.id, branch_id=None),
        ]
    )
    await db_session.commit()

    delay_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_push, "delay", lambda **kwargs: delay_calls.append(kwargs))

    await service.notify_role_at_branch(
        db_session,
        tenant_schema=tenant.schema_name,
        role_id=role.id,
        branch_id=branch.id,
        title="Title",
        body="Body",
        exclude_user_ids={user.id},
        reason="lifecycle_update",
    )

    assert len(delay_calls) == 1
    assert delay_calls[0]["user_ids"] == [str(other.id)]
    assert delay_calls[0]["data"]["reason"] == "lifecycle_update"


async def test_notify_role_at_branch_all_holders_excluded_skips_dispatch(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User, monkeypatch
) -> None:
    role = RoleFactory.build(id=uuid.uuid4(), name="poc-all-excluded-test", permissions=[])
    db_session.add(role)
    await db_session.flush()
    db_session.add(
        UserBranchRole(id=uuid.uuid4(), user_id=user.id, role_id=role.id, branch_id=None)
    )
    await db_session.commit()

    delay_calls: list[dict] = []
    monkeypatch.setattr(tasks.send_push, "delay", lambda **kwargs: delay_calls.append(kwargs))

    await service.notify_role_at_branch(
        db_session,
        tenant_schema=tenant.schema_name,
        role_id=role.id,
        branch_id=branch.id,
        title="Title",
        body="Body",
        exclude_user_ids={user.id},
    )

    assert delay_calls == []
