import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from factories import AuditLogFactory, InvitationVisitorFactory
from vmss_api.auth.models import User
from vmss_api.checkin.models import BadgePrint
from vmss_api.core.schemas import SortOrder
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.tests.helpers import _build_invitation
from vmss_api.notifications.models import Notification
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant
from vmss_api.timeline import service
from vmss_api.timeline.repository import TimelineRepository

_T0 = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


def _auth(issue_token, user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user)}"}


async def _invitation(db_session: AsyncSession, branch: Branch) -> Invitation:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    return invitation


async def _audit(
    db_session: AsyncSession,
    invitation: Invitation,
    action: str,
    at: datetime,
    *,
    actor: User | None = None,
    entity_type: str = "Invitation",
    diff: dict | None = None,
) -> None:
    db_session.add(
        AuditLogFactory.build(
            id=uuid.uuid4(),
            actor_user_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=invitation.id,
            diff=diff,
            created_at=at,
        )
    )
    await db_session.commit()


async def _events(
    client: AsyncClient, issue_token, user: User, invitation_id: uuid.UUID, **params
) -> dict:
    response = await client.get(
        f"/api/v1/invitations/{invitation_id}/timeline",
        params=params,
        headers=_auth(issue_token, user),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_default_order_is_newest_first_and_asc_reverses(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    await _audit(db_session, inv, "invitation_created", _T0)
    await _audit(db_session, inv, "invitation_approved", _T0 + timedelta(hours=1), actor=user)
    await _audit(db_session, inv, "invitation_checked_in", _T0 + timedelta(hours=2))

    body = await _events(client, issue_token, user, inv.id)
    assert [e["eventType"] for e in body["data"]] == ["checked_in", "approved", "invited"]
    assert body["data"][1]["actorName"] == user.full_name
    assert body["pagination"]["total"] == 3

    asc = await _events(client, issue_token, user, inv.id, sortOrder="asc")
    assert [e["eventType"] for e in asc["data"]] == ["invited", "approved", "checked_in"]

    by_type = await _events(client, issue_token, user, inv.id, sortBy="event_type", sortOrder="asc")
    assert [e["eventType"] for e in by_type["data"]] == ["approved", "checked_in", "invited"]


async def test_paging_over_equal_timestamps_returns_each_event_once(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    for _ in range(5):
        await _audit(db_session, inv, "invitation_checked_in", _T0)
    seen = []
    for page in (1, 2, 3):
        body = await _events(client, issue_token, user, inv.id, page=page, pageSize=2)
        seen.extend(body["data"])
    assert len(seen) == 5


async def test_mapping_collapses_variants_and_excludes_unmapped(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    for i, action in enumerate(
        ["invitation_qr_checked_in", "invitation_code_checked_in", "invitation_checked_in_public"]
    ):
        await _audit(db_session, inv, action, _T0 + timedelta(minutes=i))
    await _audit(db_session, inv, "invitations_exported", _T0 + timedelta(minutes=9))
    # Lower-case spelling of the entity type is still this visit's history.
    await _audit(
        db_session,
        inv,
        "invitation_approved",
        _T0 + timedelta(minutes=10),
        entity_type="invitation",
    )

    body = await _events(client, issue_token, user, inv.id)
    types = [e["eventType"] for e in body["data"]]
    assert types.count("checked_in") == 3
    assert "approved" in types
    assert len(types) == 4


async def test_badge_is_shown_once_and_reprint_carries_reason(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    db_session.add_all(
        [
            BadgePrint(
                id=uuid.uuid4(),
                visit_id=inv.id,
                printed_by_user_id=user.id,
                printed_at=_T0,
                jti="j1",
                day=_T0.date(),
                active=False,
            ),
            BadgePrint(
                id=uuid.uuid4(),
                visit_id=inv.id,
                printed_by_user_id=user.id,
                printed_at=_T0 + timedelta(hours=1),
                jti="j2",
                day=_T0.date(),
                active=True,
                reprint_reason="Torn badge",
            ),
        ]
    )
    # The new flow also audits both prints; those rows must not double up.
    await _audit(db_session, inv, "badge_printed", _T0)
    await _audit(db_session, inv, "badge_reprinted", _T0 + timedelta(hours=1))
    # The legacy PNG badge has no badge_prints row, so its audit row counts.
    await _audit(db_session, inv, "invitation_badge_issued", _T0 - timedelta(hours=1))

    body = await _events(client, issue_token, user, inv.id, sortOrder="asc")
    assert [e["eventType"] for e in body["data"]] == [
        "badge_printed",
        "badge_printed",
        "badge_reprinted",
    ]
    assert body["data"][-1]["summary"] == "Badge reprinted: Torn badge"


async def test_fan_out_notification_is_one_event_with_masked_contact(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    dispatch = uuid.uuid4()
    db_session.add(
        Notification(
            id=uuid.uuid4(),
            user_id=user.id,
            dispatch_id=dispatch,
            invitation_id=inv.id,
            title="Sent to bob@example.com or +91 95442 32271",
            body="secret body",
            data={},
            created_at=_T0,
        )
    )
    # Two more recipients of the same dispatch need distinct users.
    for n in range(2):
        extra = User(
            id=uuid.uuid4(),
            email=f"extra{n}@acme-test.example",
            hashed_password="x",
            full_name=f"Extra {n}",
        )
        db_session.add(extra)
        await db_session.flush()
        db_session.add(
            Notification(
                id=uuid.uuid4(),
                user_id=extra.id,
                dispatch_id=dispatch,
                invitation_id=inv.id,
                title="Sent to bob@example.com or +91 95442 32271",
                body="secret body",
                data={},
                created_at=_T0,
            )
        )
    await db_session.commit()

    body = await _events(client, issue_token, user, inv.id)
    assert len(body["data"]) == 1
    summary = body["data"][0]["summary"]
    assert "bob@example.com" not in summary
    assert "95442" not in summary
    assert "secret body" not in str(body)


async def test_response_never_carries_audit_diff_or_extra_fields(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    await _audit(db_session, inv, "invitation_approved", _T0, diff={"idNumber": "1234-5678-9012"})
    body = await _events(client, issue_token, user, inv.id)
    assert set(body["data"][0]) == {"eventType", "occurredAt", "summary", "actorName"}
    assert "1234-5678-9012" not in str(body)


async def test_date_range_filters_events_and_total(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    await _audit(db_session, inv, "invitation_created", _T0)
    await _audit(db_session, inv, "invitation_approved", _T0 + timedelta(hours=2))
    await _audit(db_session, inv, "invitation_checked_in", _T0 + timedelta(hours=4))

    body = await _events(
        client,
        issue_token,
        user,
        inv.id,
        occurredAfter=(_T0 + timedelta(hours=1)).isoformat(),
        occurredBefore=(_T0 + timedelta(hours=3)).isoformat(),
    )
    assert [e["eventType"] for e in body["data"]] == ["approved"]
    assert body["pagination"]["total"] == 1


async def test_sort_by_outside_whitelist_is_rejected(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    response = await client.get(
        f"/api/v1/invitations/{inv.id}/timeline",
        params={"sortBy": "actor_user_id"},
        headers=_auth(issue_token, user),
    )
    assert response.status_code == 422


async def test_query_count_does_not_grow_with_page_size(
    db_session: AsyncSession, user: User, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    for i in range(12):
        await _audit(
            db_session, inv, "invitation_checked_in", _T0 + timedelta(minutes=i), actor=user
        )

    engine = db_session.bind.sync_engine  # type: ignore[union-attr]
    statements: list[str] = []

    def _count(conn, cursor, statement, *args) -> None:
        statements.append(statement)

    async def _run(page_size: int) -> int:
        statements.clear()
        event.listen(engine, "before_cursor_execute", _count)
        try:
            events, _ = await service.get_invitation_timeline(
                db_session,
                inv.id,
                occurred_after=None,
                occurred_before=None,
                page=1,
                page_size=page_size,
                sort_by="occurred_at",
                sort_order=SortOrder.desc,
            )
        finally:
            event.remove(engine, "before_cursor_execute", _count)
        assert len(events) == min(page_size, 12)
        return len(statements)

    assert await _run(2) == await _run(12)


async def test_visitor_timeline_resolves_to_its_invitation(
    client: AsyncClient, user: User, db_session: AsyncSession, issue_token, branch: Branch
) -> None:
    inv = await _invitation(db_session, branch)
    visitor = InvitationVisitorFactory.build(
        id=uuid.uuid4(), invitation_id=inv.id, full_name="Co Visitor"
    )
    db_session.add(visitor)
    await db_session.commit()
    await _audit(db_session, inv, "visit_id_verified", _T0, actor=user)

    response = await client.get(
        f"/api/v1/visitors/{visitor.id}/timeline", headers=_auth(issue_token, user)
    )
    assert response.status_code == 200
    assert [e["eventType"] for e in response.json()["data"]] == ["id_verified"]


async def test_unknown_invitation_and_visitor_return_404(
    client: AsyncClient, user: User, issue_token
) -> None:
    headers = _auth(issue_token, user)
    assert (
        await client.get(f"/api/v1/invitations/{uuid.uuid4()}/timeline", headers=headers)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/visitors/{uuid.uuid4()}/timeline", headers=headers)
    ).status_code == 404


@pytest.mark.parametrize("path", ["invitations", "visitors"])
async def test_permission_denied_without_timeline_view(
    client: AsyncClient, user_without_permissions: User, issue_token, path: str
) -> None:
    response = await client.get(
        f"/api/v1/{path}/{uuid.uuid4()}/timeline",
        headers=_auth(issue_token, user_without_permissions),
    )
    assert response.status_code == 403


async def test_timeline_is_tenant_isolated(
    make_tenant_schema,
    open_tenant_session,
    db_session: AsyncSession,
    branch: Branch,
    tenant: Tenant,
) -> None:
    inv = await _invitation(db_session, branch)
    visitor = InvitationVisitorFactory.build(id=uuid.uuid4(), invitation_id=inv.id)
    db_session.add(visitor)
    await db_session.commit()

    other_schema = "tenant_other_timeline_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        repo = TimelineRepository(other_session)
        assert await repo.invitation_exists(inv.id) is False
        assert await repo.invitation_id_for_visitor(visitor.id) is None
