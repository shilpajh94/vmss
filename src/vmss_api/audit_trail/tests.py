import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import AuditLogFactory, PermissionFactory, RoleFactory, UserFactory
from vmss_api.audit_trail import tasks
from vmss_api.audit_trail.models import AuditReportJob
from vmss_api.audit_trail.repository import AuditLogRepository, AuditReportJobRepository
from vmss_api.auth.models import AuditLog, User, UserBranchRole
from vmss_api.core.security import hash_password
from vmss_api.core.storage import url_for as storage_url_for
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant


async def _build_user_with_permissions(
    db_session: AsyncSession, tenant: Tenant, *, email: str, permission_codes: list[str]
) -> User:
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in permission_codes
    ]
    role = RoleFactory.build(id=uuid.uuid4(), name=f"role-{email}", permissions=permissions)
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=None)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("correct-password"),
        full_name="Test User",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _seed_audit_log(
    db_session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str = "invitation_checked_in",
    entity_type: str = "Invitation",
    entity_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    diff: dict | None = None,
) -> AuditLog:
    entry = AuditLogFactory.build(
        id=uuid.uuid4(),
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id or uuid.uuid4(),
        diff=diff,
        created_at=created_at or datetime.now(UTC),
    )
    db_session.add(entry)
    await db_session.commit()
    return entry


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Listing ----------------------------------------------------------------


async def test_list_audit_trail_returns_all_entries_unfiltered(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token
) -> None:
    older = await _seed_audit_log(
        db_session, actor_user_id=user.id, created_at=datetime.now(UTC) - timedelta(hours=1)
    )
    newer = await _seed_audit_log(db_session, actor_user_id=user.id, created_at=datetime.now(UTC))

    token = issue_token(user)
    response = await client.get("/api/v1/audit-trail", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    ids = [row["id"] for row in body["data"]]
    assert str(newer.id) in ids and str(older.id) in ids
    # Newest first by default.
    assert ids.index(str(newer.id)) < ids.index(str(older.id))
    assert body["pagination"]["total"] == 2


async def test_list_audit_trail_filters_narrow_results(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token
) -> None:
    await _seed_audit_log(db_session, actor_user_id=user.id, action="invitation_checked_in")
    await _seed_audit_log(db_session, actor_user_id=user.id, action="invitation_denied")

    token = issue_token(user)
    response = await client.get(
        "/api/v1/audit-trail", params={"action": "invitation_denied"}, headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["action"] == "invitation_denied"


async def test_list_audit_trail_pagination_metadata_accurate(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token
) -> None:
    for _ in range(3):
        await _seed_audit_log(db_session, actor_user_id=user.id)

    token = issue_token(user)
    response = await client.get(
        "/api/v1/audit-trail",
        params={"page": 1, "pageSize": 2},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["pagination"] == {"page": 1, "pageSize": 2, "total": 3, "totalPages": 2}


async def test_list_audit_trail_rejects_invalid_sort_by(
    client: AsyncClient, user: User, issue_token
) -> None:
    token = issue_token(user)
    response = await client.get(
        "/api/v1/audit-trail", params={"sortBy": "not-a-real-column"}, headers=_auth_headers(token)
    )
    assert response.status_code == 422


async def test_list_audit_trail_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get("/api/v1/audit-trail", headers=_auth_headers(token))
    assert response.status_code == 403


# --- Detail -------------------------------------------------------------


async def test_get_audit_trail_entry_includes_diff(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token
) -> None:
    entry = await _seed_audit_log(
        db_session,
        actor_user_id=user.id,
        diff={"before": {"status": "submitted"}, "after": {"status": "approved"}},
    )

    token = issue_token(user)
    response = await client.get(f"/api/v1/audit-trail/{entry.id}", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == str(entry.id)
    assert body["diff"] == {"before": {"status": "submitted"}, "after": {"status": "approved"}}


async def test_get_audit_trail_entry_not_found(
    client: AsyncClient, user: User, issue_token
) -> None:
    token = issue_token(user)
    response = await client.get(f"/api/v1/audit-trail/{uuid.uuid4()}", headers=_auth_headers(token))
    assert response.status_code == 404


# --- Write/read integration (verify-audit-trail-and-delegation-full-suite) --


async def test_login_action_is_retrievable_via_audit_trail(
    client: AsyncClient, user: User, issue_token
) -> None:
    """Every other test in this file asserts against an `AuditLogFactory`
    -seeded row, proving the read side (`GET /audit-trail`) in isolation
    from whatever actually writes a row. This closes that loop with the
    simplest available real mutating action that calls `record_audit_log`
    as a `BackgroundTasks` job (`auth/router.py::login`): a real
    `POST /auth/login`, then confirming the resulting entry is retrievable
    with the correct `action`/`entityType`/`entityId`/`actorUserId` via
    `GET /audit-trail`, and its `diff` via `GET /audit-trail/{id}`
    (verify-audit-trail-and-delegation-full-suite/design.md Decision 2). No
    sleep/retry needed — `httpx.AsyncClient` over `ASGITransport` awaits the
    whole in-process ASGI call, `BackgroundTasks` included, before
    `client.post` returns.
    """
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    assert login_response.status_code == 200

    token = issue_token(user)
    list_response = await client.get(
        "/api/v1/audit-trail",
        params={"action": "login", "entityId": str(user.id)},
        headers=_auth_headers(token),
    )
    assert list_response.status_code == 200
    entries = list_response.json()["data"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["actorUserId"] == str(user.id)
    assert entry["entityType"] == "User"
    assert entry["entityId"] == str(user.id)

    detail_response = await client.get(
        f"/api/v1/audit-trail/{entry['id']}", headers=_auth_headers(token)
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["diff"] is None


# --- Tenant isolation -----------------------------------------------------


async def test_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, user: User, db_session: AsyncSession
) -> None:
    """Neither an `AuditLog` entry nor a report job created in the default
    test tenant's schema is reachable from a session bound to a different
    tenant's schema — schema-per-tenant isolation is structural, not a
    WHERE clause (database-architecture.md §3, testing-standards.md §2).
    """
    entry = await _seed_audit_log(db_session, actor_user_id=user.id)
    job = await AuditReportJobRepository(db_session).create(
        id_=uuid.uuid4(),
        requested_by_user_id=user.id,
        filters={},
        formats=["csv"],
    )
    await db_session.commit()

    other_schema = "tenant_other_audit_trail_test"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        assert await AuditLogRepository(other_session).get(entry.id) is None
        assert await AuditReportJobRepository(other_session).get(job.id) is None


# --- Report requests --------------------------------------------------------


async def test_request_audit_report_requires_export_permission(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, issue_token
) -> None:
    """A caller holding only the view permission (not export) is denied —
    specs/audit-trail/spec.md "Caller without the export permission cannot
    request a report".
    """
    view_only_user = await _build_user_with_permissions(
        db_session,
        tenant,
        email="view-only@acme-test.example",
        permission_codes=["audit-logs:view"],
    )
    token = issue_token(view_only_user)
    response = await client.post(
        "/api/v1/audit-trail/reports", json={"formats": ["csv"]}, headers=_auth_headers(token)
    )
    assert response.status_code == 403

    jobs = (await db_session.execute(select(AuditReportJob))).scalars().all()
    assert jobs == []


async def test_request_audit_report_enqueues_job(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, monkeypatch
) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(tasks.generate_audit_report, "delay", lambda **kw: calls.append(kw))

    token = issue_token(user)
    response = await client.post(
        "/api/v1/audit-trail/reports",
        json={"formats": ["csv", "pdf"]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 202
    body = response.json()["data"]
    assert body["status"] == "pending"
    assert body["formats"] == ["csv", "pdf"]
    assert len(calls) == 1
    assert calls[0]["job_id"] == body["id"]

    job = await AuditReportJobRepository(db_session).get(uuid.UUID(body["id"]))
    assert job is not None and job.status == "pending"


async def test_request_audit_report_idempotency_key_replay(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, monkeypatch
) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(tasks.generate_audit_report, "delay", lambda **kw: calls.append(kw))

    token = issue_token(user)
    headers = {**_auth_headers(token), "Idempotency-Key": "report-key-1"}

    first = await client.post(
        "/api/v1/audit-trail/reports", json={"formats": ["csv"]}, headers=headers
    )
    second = await client.post(
        "/api/v1/audit-trail/reports", json={"formats": ["csv"]}, headers=headers
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json() == second.json()
    assert len(calls) == 1

    jobs = (await db_session.execute(select(AuditReportJob))).scalars().all()
    assert len(jobs) == 1


async def test_get_report_job_not_found(client: AsyncClient, user: User, issue_token) -> None:
    token = issue_token(user)
    response = await client.get(
        f"/api/v1/audit-trail/reports/{uuid.uuid4()}", headers=_auth_headers(token)
    )
    assert response.status_code == 404


# --- Report generation (Celery task, invoked directly per reports/tests.py's
# pattern of calling the private async coroutine rather than going through
# Celery/asyncio.run for real) --------------------------------------------


async def test_generate_audit_report_end_to_end_via_polling(
    client: AsyncClient,
    user: User,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token,
    monkeypatch,
) -> None:
    await _seed_audit_log(db_session, actor_user_id=user.id, action="invitation_checked_in")
    await _seed_audit_log(db_session, actor_user_id=user.id, action="invitation_denied")

    monkeypatch.setattr(tasks.generate_audit_report, "delay", lambda **kw: None)

    token = issue_token(user)
    create_response = await client.post(
        "/api/v1/audit-trail/reports",
        json={"formats": ["csv", "pdf"]},
        headers=_auth_headers(token),
    )
    job_id = create_response.json()["data"]["id"]

    await tasks._generate_audit_report(job_id, str(tenant.id), tenant.schema_name)

    poll_response = await client.get(
        f"/api/v1/audit-trail/reports/{job_id}", headers=_auth_headers(token)
    )
    assert poll_response.status_code == 200
    body = poll_response.json()["data"]
    assert body["status"] == "ready"
    assert body["csvDownloadUrl"] is not None
    assert body["pdfDownloadUrl"] is not None


# --- Report download --------------------------------------------------------


async def test_download_audit_report_returns_generated_file(
    client: AsyncClient,
    user: User,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token,
    monkeypatch,
) -> None:
    await _seed_audit_log(db_session, actor_user_id=user.id)
    monkeypatch.setattr(tasks.generate_audit_report, "delay", lambda **kw: None)

    token = issue_token(user)
    create_response = await client.post(
        "/api/v1/audit-trail/reports",
        json={"formats": ["csv", "pdf"]},
        headers=_auth_headers(token),
    )
    job_id = create_response.json()["data"]["id"]
    await tasks._generate_audit_report(job_id, str(tenant.id), tenant.schema_name)

    response = await client.get(
        f"/api/v1/audit-trail/reports/{job_id}/download",
        params={"format": "csv"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert str(user.id) in response.text


async def test_download_audit_report_requires_export_permission(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, issue_token
) -> None:
    view_only_user = await _build_user_with_permissions(
        db_session,
        tenant,
        email="view-only-download@acme-test.example",
        permission_codes=["audit-logs:view"],
    )
    token = issue_token(view_only_user)
    response = await client.get(
        f"/api/v1/audit-trail/reports/{uuid.uuid4()}/download",
        params={"format": "csv"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


async def test_download_audit_report_not_found(
    client: AsyncClient, user: User, issue_token
) -> None:
    token = issue_token(user)
    response = await client.get(
        f"/api/v1/audit-trail/reports/{uuid.uuid4()}/download",
        params={"format": "csv"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


async def test_download_audit_report_format_not_generated(
    client: AsyncClient,
    user: User,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token,
    monkeypatch,
) -> None:
    """The job only ever generated a CSV — asking this same, now-`ready` job
    for the PDF it never produced is a 404, not a 200 with stale/wrong
    content.
    """
    await _seed_audit_log(db_session, actor_user_id=user.id)
    monkeypatch.setattr(tasks.generate_audit_report, "delay", lambda **kw: None)

    token = issue_token(user)
    create_response = await client.post(
        "/api/v1/audit-trail/reports", json={"formats": ["csv"]}, headers=_auth_headers(token)
    )
    job_id = create_response.json()["data"]["id"]
    await tasks._generate_audit_report(job_id, str(tenant.id), tenant.schema_name)

    response = await client.get(
        f"/api/v1/audit-trail/reports/{job_id}/download",
        params={"format": "pdf"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


async def test_download_audit_report_not_ready_yet(
    client: AsyncClient, user: User, issue_token, monkeypatch
) -> None:
    monkeypatch.setattr(tasks.generate_audit_report, "delay", lambda **kw: None)
    token = issue_token(user)
    create_response = await client.post(
        "/api/v1/audit-trail/reports", json={"formats": ["csv"]}, headers=_auth_headers(token)
    )
    job_id = create_response.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/audit-trail/reports/{job_id}/download",
        params={"format": "csv"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


async def test_generate_audit_report_reflects_filtered_data(
    db_session: AsyncSession, user: User, tenant: Tenant
) -> None:
    matching = await _seed_audit_log(db_session, actor_user_id=user.id, action="invitation_denied")
    await _seed_audit_log(db_session, actor_user_id=user.id, action="invitation_checked_in")

    job = await AuditReportJobRepository(db_session).create(
        id_=uuid.uuid4(),
        requested_by_user_id=user.id,
        filters={"action": "invitation_denied"},
        formats=["csv"],
    )
    await db_session.commit()

    await tasks._generate_audit_report(str(job.id), str(tenant.id), tenant.schema_name)

    await db_session.refresh(job)
    assert job.status == "ready"
    assert job.csv_storage_key is not None

    csv_path = await storage_url_for(job.csv_storage_key)
    csv_content = Path(csv_path).read_text()
    assert str(matching.id) in csv_content
    assert "invitation_checked_in" not in csv_content


async def test_generate_audit_report_redelivery_is_idempotent(
    db_session: AsyncSession, user: User, tenant: Tenant
) -> None:
    await _seed_audit_log(db_session, actor_user_id=user.id)
    job = await AuditReportJobRepository(db_session).create(
        id_=uuid.uuid4(), requested_by_user_id=user.id, filters={}, formats=["csv"]
    )
    await db_session.commit()

    await tasks._generate_audit_report(str(job.id), str(tenant.id), tenant.schema_name)
    await db_session.refresh(job)
    first_key = job.csv_storage_key
    assert job.status == "ready"

    # Redelivery: the row is already `ready`, so this must be a no-op, not a
    # second write or an exception (background-jobs.md §2).
    await tasks._generate_audit_report(str(job.id), str(tenant.id), tenant.schema_name)
    await db_session.refresh(job)
    assert job.status == "ready"
    assert job.csv_storage_key == first_key


async def test_generate_audit_report_retry_exhaustion_marks_job_failed(
    db_session: AsyncSession, user: User, tenant: Tenant, monkeypatch
) -> None:
    await _seed_audit_log(db_session, actor_user_id=user.id)
    job = await AuditReportJobRepository(db_session).create(
        id_=uuid.uuid4(), requested_by_user_id=user.id, filters={}, formats=["csv"]
    )
    await db_session.commit()

    def _boom(entries):
        raise RuntimeError("rendering exploded")

    monkeypatch.setattr(tasks, "_render_csv", _boom)
    logged_error = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged_error.append((event, kw)))
    # `max_retries=0` — the first failure is already "exhausted", matching
    # `reports/tests.py::test_reports_snapshot_retry_exhaustion_logs_error_with_tenant_context`'s
    # trick to avoid actually sleeping through `retry_backoff`.
    monkeypatch.setattr(tasks.generate_audit_report, "max_retries", 0)

    result = await asyncio.to_thread(
        tasks.generate_audit_report.apply,
        kwargs={
            "job_id": str(job.id),
            "tenant_id": str(tenant.id),
            "tenant_schema": tenant.schema_name,
            "request_id": "test-request-id",
        },
    )

    assert result.failed()
    assert logged_error and logged_error[0][0] == "audit_report_generation_exhausted"

    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_message
