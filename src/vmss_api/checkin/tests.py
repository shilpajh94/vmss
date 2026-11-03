"""Badge print flow (add-badge-print-flow). Real Postgres, same fixtures as the
other features; the flow is switched on per-test via `flow_on`."""

import io
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import AuditLog, User
from vmss_api.checkin import badge_token
from vmss_api.checkin.models import BadgePrint
from vmss_api.checkin.repository import CheckinRepository
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.storage import save as storage_save
from vmss_api.invitations.models import Invitation, InvitationQRCode
from vmss_api.invitations.tests.helpers import _build_invitation
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


@pytest.fixture
async def flow_on(monkeypatch, db_session: AsyncSession, tenant: Tenant) -> None:
    tenant.badge_print_flow_enabled = True
    await db_session.commit()


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "gray").save(buffer, format="PNG")
    return buffer.getvalue()


async def _visit(
    db_session: AsyncSession,
    tenant_id: uuid.UUID,
    branch: Branch,
    *,
    photo: bool = True,
    verified: bool = True,
    status: str = "approved",
    check_in_status: str = "unused",
    **overrides,
) -> Invitation:
    key = (
        await storage_save(tenant_id, "invitations/photos", _png(), "image/png") if photo else None
    )
    visit = _build_invitation(
        db_session,
        branch.id,
        status=status,
        check_in_status=check_in_status,
        primary_contact_full_name="Alice Visitor",
        primary_contact_phone="+91 95442 32271",
        primary_contact_photo_storage_key=key,
        host_name_or_email="Host One",
        id_verified_at=datetime.now(UTC) if verified else None,
        id_verified_by_user_id=None,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        **overrides,
    )
    db_session.add(visit)
    await db_session.commit()
    return visit


def _auth(issue_token: Callable[[User], str], user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user)}"}


async def _prints(db_session: AsyncSession, visit_id: uuid.UUID) -> list[BadgePrint]:
    rows = await db_session.execute(
        select(BadgePrint).where(BadgePrint.visit_id == visit_id).order_by(BadgePrint.printed_at)
    )
    return list(rows.scalars())


def _token(
    row: BadgePrint, tenant_id: uuid.UUID, visit_id: uuid.UUID, day: date | None = None
) -> str:
    return badge_token.issue_badge_token(
        visit_id=visit_id, tenant_id=tenant_id, day=day or row.day, jti=row.jti, timezone="UTC"
    )


# --- flag gating --------------------------------------------------------------


async def test_tenant_flag_off_returns_404(
    client: AsyncClient, user: User, issue_token, tenant: Tenant
) -> None:
    response = await client.get(
        "/api/v1/checkin/search", params={"q": "alice"}, headers=_auth(issue_token, user)
    )
    assert response.status_code == 404


async def test_scan_endpoints_404_when_flag_off(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession, monkeypatch
) -> None:
    token = badge_token.issue_badge_token(
        visit_id=uuid.uuid4(),
        tenant_id=tenant.id,
        day=datetime.now(UTC).date(),
        jti="abc",
        timezone="UTC",
    )
    response = await client.post("/api/v1/checkin/badge/check-out", json={"token": token})
    assert response.status_code == 404


# --- search -------------------------------------------------------------------


@pytest.mark.parametrize(
    "query_for",
    [
        lambda v: "alice",
        lambda v: "+91 95442-32271",
        lambda v: v.tracking_id,
        lambda v: v.checkin_code,
    ],
    ids=["name", "phone", "tracking-id", "checkin-code"],
)
async def test_search_matches_each_field(
    flow_on, client, user, issue_token, db_session, tenant, branch, query_for
) -> None:
    visit = await _visit(db_session, tenant.id, branch, checkin_code="12345678")
    response = await client.get(
        "/api/v1/checkin/search",
        params={"q": query_for(visit)},
        headers=_auth(issue_token, user),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert [row["id"] for row in data] == [str(visit.id)]
    assert data[0]["hasPhoto"] is True
    assert response.json()["pagination"]["total"] == 1


async def test_search_does_not_treat_wildcards_as_patterns(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    await _visit(db_session, tenant.id, branch)
    response = await client.get(
        "/api/v1/checkin/search", params={"q": "%"}, headers=_auth(issue_token, user)
    )
    assert response.json()["data"] == []


async def test_search_permission_denied(
    flow_on, client, user_without_permissions, issue_token
) -> None:
    response = await client.get(
        "/api/v1/checkin/search",
        params={"q": "alice"},
        headers=_auth(issue_token, user_without_permissions),
    )
    assert response.status_code == 403


# --- verify-id ----------------------------------------------------------------


async def test_verify_id_is_idempotent(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, verified=False)
    headers = _auth(issue_token, user)
    first = await client.post(f"/api/v1/checkin/{visit.id}/verify-id", headers=headers)
    second = await client.post(f"/api/v1/checkin/{visit.id}/verify-id", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["idVerifiedAt"] == second.json()["data"]["idVerifiedAt"]


async def test_verify_id_permission_denied(
    flow_on, client, user_without_permissions, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, verified=False)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/verify-id",
        headers=_auth(issue_token, user_without_permissions),
    )
    assert response.status_code == 403


# --- photo upload ---------------------------------------------------------------


async def test_upload_photo_clears_photo_missing(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, photo=False)
    headers = _auth(issue_token, user)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/photo",
        headers=headers,
        files={"file": ("p.png", _png(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["hasPhoto"] is True
    printed = await client.post(f"/api/v1/checkin/{visit.id}/badge", headers=headers)
    assert printed.status_code == 200


async def test_upload_photo_never_replaces_existing(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, photo=True)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/photo",
        headers=_auth(issue_token, user),
        files={"file": ("p.png", _png(), "image/png")},
    )
    assert response.status_code == 409
    assert "photo_already_captured" in response.json()["message"]


async def test_upload_photo_rejects_non_image(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, photo=False)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/photo",
        headers=_auth(issue_token, user),
        files={"file": ("p.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 422


async def test_upload_photo_permission_denied(
    flow_on, client, user_without_permissions, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, photo=False)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/photo",
        headers=_auth(issue_token, user_without_permissions),
        files={"file": ("p.png", _png(), "image/png")},
    )
    assert response.status_code == 403


# --- print gate ---------------------------------------------------------------


async def test_print_gate_lists_every_unmet_condition(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, photo=False, verified=False)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/badge", headers=_auth(issue_token, user)
    )
    assert response.status_code == 409
    message = response.json()["message"]
    assert "photo_missing" in message
    assert "id_not_verified" in message


async def test_print_gate_rejects_unapproved_visit(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch, status="submitted")
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/badge", headers=_auth(issue_token, user)
    )
    assert response.status_code == 409
    assert "visit_not_approved" in response.json()["message"]


# --- print / reprint ----------------------------------------------------------


async def test_print_returns_card_json_and_records_row_and_audit(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/badge", headers=_auth(issue_token, user)
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    card = response.json()["data"]
    assert card["visitorName"] == visit.primary_contact_full_name
    assert card["photoUrl"].startswith("data:image/")
    assert set(card) == {"token", "visitorName", "purpose", "hostName", "photoUrl"}
    claims = badge_token.verify_badge_token(card["token"])
    assert claims is not None and claims.visit_id == visit.id

    rows = await _prints(db_session, visit.id)
    assert len(rows) == 1 and rows[0].active and rows[0].reprint_reason is None
    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert "badge_printed" in actions


async def test_card_token_is_invitation_qr_token_when_one_exists(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    db_session.add(
        InvitationQRCode(
            invitation_id=visit.id, qr_token="invitation-qr-token", image_storage_key="k"
        )
    )
    await db_session.commit()
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/badge", headers=_auth(issue_token, user)
    )
    assert response.status_code == 200
    assert response.json()["data"]["token"] == "invitation-qr-token"


async def test_print_permission_denied(
    flow_on, client, user_without_permissions, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    response = await client.post(
        f"/api/v1/checkin/{visit.id}/badge", headers=_auth(issue_token, user_without_permissions)
    )
    assert response.status_code == 403
    assert await _prints(db_session, visit.id) == []


async def test_print_idempotency_key_replays_without_second_row(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    headers = {**_auth(issue_token, user), "Idempotency-Key": "print-1"}
    first = await client.post(f"/api/v1/checkin/{visit.id}/badge", headers=headers)
    second = await client.post(f"/api/v1/checkin/{visit.id}/badge", headers=headers)
    assert first.status_code == second.status_code == 200
    assert second.json()["data"] == first.json()["data"]
    assert len(await _prints(db_session, visit.id)) == 1


async def test_second_print_without_reprint_is_409(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    headers = _auth(issue_token, user)
    await client.post(f"/api/v1/checkin/{visit.id}/badge", headers=headers)
    again = await client.post(f"/api/v1/checkin/{visit.id}/badge", headers=headers)
    assert again.status_code == 409
    assert len(await _prints(db_session, visit.id)) == 1


async def test_reprint_invalidates_old_badge(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    tenant_id = tenant.id
    visit = await _visit(
        db_session, tenant_id, branch, status="checked_in", check_in_status="checked_in"
    )
    visit_id = visit.id
    headers = _auth(issue_token, user)
    await client.post(f"/api/v1/checkin/{visit_id}/badge", headers=headers)
    db_session.expire_all()
    old = (await _prints(db_session, visit_id))[0]
    old_token = _token(old, tenant_id, visit_id)

    reprint = await client.get(
        f"/api/v1/checkin/{visit_id}/badge", params={"reason": "lost"}, headers=headers
    )
    assert reprint.status_code == 200
    assert reprint.headers["cache-control"] == "no-store"
    new_claims = badge_token.verify_badge_token(reprint.json()["data"]["token"])
    assert (
        new_claims is not None and new_claims.jti != badge_token.verify_badge_token(old_token).jti
    )

    db_session.expire_all()
    rows = await _prints(db_session, visit_id)
    assert [r.active for r in rows] == [False, True]
    assert rows[1].reprint_reason == "lost" and rows[1].jti != rows[0].jti

    scan = await client.post("/api/v1/checkin/badge/check-out", json={"token": old_token})
    assert scan.status_code == 400


async def test_reprint_requires_reason(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    visit_id = visit.id
    headers = _auth(issue_token, user)
    await client.post(f"/api/v1/checkin/{visit_id}/badge", headers=headers)
    missing = await client.get(f"/api/v1/checkin/{visit_id}/badge", headers=headers)
    blank = await client.get(
        f"/api/v1/checkin/{visit_id}/badge", params={"reason": "  "}, headers=headers
    )
    assert missing.status_code == 422 and blank.status_code == 422
    db_session.expire_all()
    assert [r.active for r in await _prints(db_session, visit_id)] == [True]


async def test_reprint_before_first_print_is_409(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    response = await client.get(
        f"/api/v1/checkin/{visit.id}/badge",
        params={"reason": "lost"},
        headers=_auth(issue_token, user),
    )
    assert response.status_code == 409


# --- scan: tokens, checkout, re-entry -----------------------------------------


async def _printed(
    client, user, issue_token, db_session, tenant, branch, *, step_out=False, **visit_kwargs
):
    tenant_id = tenant.id
    visit = await _visit(db_session, tenant_id, branch, **visit_kwargs)
    visit_id = visit.id
    await client.post(f"/api/v1/checkin/{visit.id}/badge", headers=_auth(issue_token, user))
    db_session.expire_all()
    if step_out:
        # Printing needs approved/checked_in, so step out after the print.
        await db_session.execute(
            update(Invitation)
            .where(Invitation.id == visit_id)
            .values(status="checked_out", check_in_status="checked_out")
        )
        await db_session.commit()
    row = (await _prints(db_session, visit_id))[0]
    visit = SimpleNamespace(id=visit_id)
    return visit, row, _token(row, tenant_id, visit.id), tenant_id


async def test_scan_checkout_closes_visit_and_kills_token(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit, row, token, _ = await _printed(
        client,
        user,
        issue_token,
        db_session,
        tenant,
        branch,
        status="checked_in",
        check_in_status="checked_in",
    )
    response = await client.post("/api/v1/checkin/badge/check-out", json={"token": token})
    assert response.status_code == 200
    assert response.json()["data"]["checkInStatus"] == "checked_out"

    db_session.expire_all()
    assert (await _prints(db_session, visit.id))[0].active is False
    again = await client.post("/api/v1/checkin/badge/check-out", json={"token": token})
    assert again.status_code == 400
    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert "badge_checked_out" in actions


async def test_scan_checkout_of_visit_not_checked_in_is_409_and_keeps_token(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit, _, token, _ = await _printed(client, user, issue_token, db_session, tenant, branch)
    response = await client.post("/api/v1/checkin/badge/check-out", json={"token": token})
    assert response.status_code == 409
    db_session.expire_all()
    assert (await _prints(db_session, visit.id))[0].active is True


async def test_tampered_token_is_rejected(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    _, _, token, _ = await _printed(
        client,
        user,
        issue_token,
        db_session,
        tenant,
        branch,
        status="checked_in",
        check_in_status="checked_in",
    )
    flipped = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
    response = await client.post("/api/v1/checkin/badge/check-out", json={"token": flipped})
    assert response.status_code == 400
    assert response.json()["message"] == "Invalid badge token"


async def test_wrong_day_token_is_rejected(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit, row, _, tenant_id = await _printed(
        client,
        user,
        issue_token,
        db_session,
        tenant,
        branch,
        status="checked_in",
        check_in_status="checked_in",
    )
    tomorrow = row.day + timedelta(days=1)
    token = _token(row, tenant_id, visit.id, day=tomorrow)
    response = await client.post("/api/v1/checkin/badge/check-out", json={"token": token})
    assert response.status_code == 400


async def test_expired_token_is_rejected(tenant: Tenant) -> None:
    token = badge_token.issue_badge_token(
        visit_id=uuid.uuid4(),
        tenant_id=tenant.id,
        day=date(2020, 1, 1),
        jti="old",
        timezone="UTC",
    )
    assert badge_token.verify_badge_token(token) is None


async def test_token_signed_with_other_secret_is_rejected(monkeypatch, tenant: Tenant) -> None:
    token = badge_token.issue_badge_token(
        visit_id=uuid.uuid4(),
        tenant_id=tenant.id,
        day=datetime.now(UTC).date(),
        jti="j",
        timezone="UTC",
    )
    monkeypatch.setattr(settings, "jwt_secret_key", "another-secret-" + "y" * 32)
    assert badge_token.verify_badge_token(token) is None


async def test_re_entry_same_day(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit, _, token, _ = await _printed(
        client,
        user,
        issue_token,
        db_session,
        tenant,
        branch,
        status="checked_in",
        check_in_status="checked_in",
        step_out=True,
    )
    response = await client.post("/api/v1/checkin/badge/re-enter", json={"token": token})
    assert response.status_code == 200
    assert response.json()["data"]["checkInStatus"] == "checked_in"


async def test_re_entry_next_day_is_rejected(
    flow_on, client, user, issue_token, db_session, tenant, branch
) -> None:
    visit, row, _, tenant_id = await _printed(
        client,
        user,
        issue_token,
        db_session,
        tenant,
        branch,
        status="checked_in",
        check_in_status="checked_in",
        step_out=True,
    )
    token = _token(row, tenant_id, visit.id, day=row.day - timedelta(days=1))
    response = await client.post("/api/v1/checkin/badge/re-enter", json={"token": token})
    assert response.status_code == 400


async def test_scan_rate_limit_trips(flow_on, client, tenant, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.post("/api/v1/checkin/badge/check-out", json={"token": "junk"})
        for _ in range(45)
    ]
    assert any(r.status_code == 429 for r in responses)


# --- tenant isolation ---------------------------------------------------------


async def test_checkin_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, db_session, tenant, branch
) -> None:
    visit = await _visit(db_session, tenant.id, branch)
    await make_tenant_schema("tenant_other_test_checkin")
    async with open_tenant_session("tenant_other_test_checkin") as other:
        repo = CheckinRepository(other)
        assert await repo.get_visit(visit.id) is None
        rows, total = await repo.search_visits("alice", "all", limit=10, offset=0)
        assert rows == [] and total == 0
        assert await repo.get_active_print(visit.id) is None
