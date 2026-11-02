"""GET /invitations/export."""

import csv
import io
import re
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import openpyxl
import pytest
from httpx import AsyncClient
from openpyxl.utils import get_column_letter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BranchFactory,
    InvitationFactory,
    InvitationVehicleFactory,
    RoleFactory,
    UserFactory,
    VisitorCategoryFactory,
)
from vmss_api.auth.models import AuditLog, User
from vmss_api.auth.rbac_catalog import seed_default_roles
from vmss_api.core.config import settings
from vmss_api.invitations import export as invitation_export
from vmss_api.invitations.schemas import (
    InvitationExportDateRange,
    InvitationStatus,
    RegistrationSource,
    RegistrationType,
)
from vmss_api.invitations.tests.helpers import (
    _ALL_HEADERS,
    _KOLKATA,
    _XLSX_MEDIA_TYPE,
    _base_header,
    _build_invitation,
    _csv_headers,
    _csv_rows,
    _export_visitor,
    _get_or_create_permission,
    _host_role,
    _login,
    _make_role_holder,
    _names,
    _reception_holder,
    _service_export,
)
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

# --- add-invitation-export: GET /invitations/export --------------------------


def test_export_build_rows_one_per_person_primary_contact_first() -> None:
    individual = InvitationFactory.build(
        id=uuid.uuid4(), registration_type="individual", source="staff_pre_registration"
    )
    individual.visitors = []
    group = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="group",
        source="visitor_walk_in",
        primary_contact_full_name="Group Lead",
    )
    group.visitors = [_export_visitor(group.id, f"Guest {i}") for i in range(3)]
    names = _names(branch="Main")

    rows = invitation_export.build_rows([(individual, names), (group, names)], ZoneInfo("UTC"))

    assert len(rows) == 5
    assert rows[0]["visitor_role"] == invitation_export.PRIMARY_CONTACT
    group_rows = rows[1:]
    assert {row["tracking_id"] for row in group_rows} == {group.tracking_id}
    assert [row["visitor_role"] for row in group_rows] == [
        invitation_export.PRIMARY_CONTACT,
        *[invitation_export.CO_VISITOR] * 3,
    ]
    assert group_rows[0]["visitor_name"] == "Group Lead"
    assert "secret" not in repr(rows)


def test_export_labels_cover_every_enum_member_and_fall_back_readably() -> None:
    """Spec "Exported Values Are Human-Readable Labels"."""
    assert set(InvitationStatus) <= invitation_export.STATUS_LABELS.keys()
    assert set(RegistrationSource) <= invitation_export.SOURCE_LABELS.keys()
    assert set(RegistrationType) <= invitation_export.REGISTRATION_TYPE_LABELS.keys()
    assert invitation_export.label("pending", invitation_export.STATUS_LABELS) == "Pending"

    invitation = InvitationFactory.build(
        id=uuid.uuid4(), registration_type="group", source="visitor_walk_in", status="checked_in"
    )
    invitation.visitors = []
    [row] = invitation_export.build_rows([(invitation, _names())], ZoneInfo("UTC"))
    assert (row["status"], row["source"], row["registration_type"]) == (
        "Checked-in",
        "Visitor Walk-in",
        "Group",
    )


@pytest.mark.parametrize(
    ("status", "lifecycle_headers"),
    [
        ("submitted", ["Requested At"]),
        ("approved", ["Requested At", "Approved At"]),
        ("denied", ["Requested At", "Denied At", "Denial Reason"]),
        ("checked_in", ["Requested At", "Approved At", "Checked In At", "Checked In By"]),
        (
            "checked_out",
            [
                "Requested At",
                "Approved At",
                "Checked In At",
                "Checked In By",
                "Checked Out At",
                "Checked Out By",
            ],
        ),
        ("archived", ["Requested At", "Approved At", "Archived At"]),
        (
            None,
            [
                "Requested At",
                "Approved At",
                "Denied At",
                "Denial Reason",
                "Checked In At",
                "Checked In By",
                "Checked Out At",
                "Checked Out By",
                "Archived At",
            ],
        ),
    ],
)
def test_export_columns_follow_the_status_filter(
    status: str | None, lifecycle_headers: list[str]
) -> None:
    """Spec "Date Columns Follow the Status Filter"."""
    headers = [column.header for column in invitation_export.columns_for(status)]
    assert headers == _ALL_HEADERS[: _ALL_HEADERS.index("Requested At")] + lifecycle_headers
    assert len(invitation_export.columns_for(None)) == 32


def test_export_formats_timestamps_in_the_given_timezone() -> None:
    """Spec "Status-specific timestamps populated" and "XLSX dates are real
    date values".
    """
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="individual",
        source="staff_pre_registration",
        checked_in_at=datetime(2026, 10, 13, 9, 5, 42, tzinfo=UTC),
        approved_at=datetime(2026, 10, 12, 4, 0, tzinfo=UTC),
        preferred_visit_date=date(2026, 10, 13),
        preferred_visit_time=time(10, 0),
        denied_at=None,
    )
    invitation.visitors = []
    rows = invitation_export.build_rows([(invitation, _names())], ZoneInfo(_KOLKATA))
    columns = invitation_export.COLUMNS

    content = invitation_export.render_csv(rows, columns, _KOLKATA)
    [csv_row] = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    assert csv_row[f"Checked In At ({_KOLKATA})"] == "2026-10-13 14:35"
    assert csv_row[f"Approved At ({_KOLKATA})"] == "2026-10-12 09:30"
    assert csv_row["Visit Date"] == "2026-10-13"
    assert csv_row["Visit Time"] == "10:00"
    assert csv_row[f"Denied At ({_KOLKATA})"] == ""

    sheet = openpyxl.load_workbook(
        io.BytesIO(invitation_export.render_xlsx(rows, columns, _KOLKATA))
    ).active
    headers = [cell.value for cell in sheet[1]]
    data = {header: cell for header, cell in zip(headers, sheet[2], strict=True)}
    assert data[f"Checked In At ({_KOLKATA})"].value == datetime(2026, 10, 13, 14, 35, 42)
    assert data[f"Checked In At ({_KOLKATA})"].number_format == "yyyy-mm-dd hh:mm"
    assert data["Visit Date"].is_date
    assert data["Visit Date"].number_format == "yyyy-mm-dd"


@pytest.mark.parametrize("trigger", ["=", "+", "-", "@", "\t", "\r"])
def test_export_neutralizes_formula_triggers_in_csv_and_types_cells_in_xlsx(trigger: str) -> None:
    """Spec "Exported Cells Are Safe Against Formula Injection": CSV gets
    the `'` guard, XLSX keeps the original text in a string-typed cell.
    """
    payload = f'{trigger}HYPERLINK("http://evil","x")'
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        registration_type="individual",
        source="staff_pre_registration",
        primary_contact_full_name=payload,
        primary_contact_phone="+919800000261",
    )
    invitation.visitors = []
    rows = invitation_export.build_rows([(invitation, _names())], ZoneInfo("UTC"))
    columns = invitation_export.COLUMNS

    [csv_row] = _csv_rows(invitation_export.render_csv(rows, columns, "UTC"))
    assert csv_row["Visitor Name"] == f"'{payload}"
    assert csv_row["Phone Number"] == "'+919800000261"

    sheet = openpyxl.load_workbook(
        io.BytesIO(invitation_export.render_xlsx(rows, columns, "UTC"))
    ).active
    headers = [cell.value for cell in sheet[1]]
    data = {header: cell for header, cell in zip(headers, sheet[2], strict=True)}
    for cell in sheet[2]:
        assert cell.data_type != "f"
    # XML parsing normalizes a carriage return to a newline on read-back.
    assert data["Visitor Name"].value == payload.replace("\r", "\n")
    assert data["Visitor Name"].data_type == "s"
    assert data["Phone Number"].value == "+919800000261"
    assert data["Phone Number"].data_type == "s"


def test_export_xlsx_header_is_bold_frozen_and_filterable() -> None:
    """Spec "XLSX Export Is Presented for Reading"."""
    columns = invitation_export.columns_for("approved")
    sheet = openpyxl.load_workbook(
        io.BytesIO(invitation_export.render_xlsx([], columns, "UTC"))
    ).active
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == f"A1:{get_column_letter(len(columns))}1"
    assert all(cell.font.b for cell in sheet[1])
    assert sheet.column_dimensions["A"].width == columns[0].width


async def test_export_invitations_csv_by_default(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="approved")
    db_session.add(invitation)
    await db_session.commit()
    tracking_id = invitation.tracking_id

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    disposition = response.headers["content-disposition"]
    assert re.fullmatch(
        r'attachment; filename="invitations-approved-\d{4}-\d{2}-\d{2}\.csv"', disposition
    )
    assert [_base_header(h) for h in _csv_headers(response.content)] == [
        column.header for column in invitation_export.columns_for("approved")
    ]
    rows = _csv_rows(response.content)
    assert [row["Tracking ID"] for row in rows] == [tracking_id]
    assert rows[0]["Status"] == "Approved"
    assert rows[0]["Branch"] == "Main Branch"


async def test_export_invitations_xlsx_on_request(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()
    tracking_id = invitation.tracking_id

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"format": "xlsx"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == _XLSX_MEDIA_TYPE
    assert 'filename="invitations-all-' in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.xlsx"')
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    values = [[c.value for c in row] for row in sheet.iter_rows()]
    assert [_base_header(h) for h in values[0]] == _ALL_HEADERS
    assert [row[0] for row in values[1:]] == [tracking_id]


async def test_export_denied_status_shows_reason_and_drops_later_columns(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    """Spec "Denied export shows the reason" and "Approved export omits
    later-stage columns".
    """
    denied = _build_invitation(
        db_session,
        branch.id,
        status="denied",
        denied_at=datetime.now(UTC),
        denial_reason="No host available",
    )
    approved = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add_all([denied, approved])
    await db_session.commit()

    denied_file = await _service_export(db_session, tenant, status="denied")
    headers = [_base_header(h) for h in _csv_headers(denied_file.content)]
    assert "Denial Reason" in headers
    assert "Approved At" not in headers
    assert [row["Denial Reason"] for row in _csv_rows(denied_file.content)] == ["No host available"]

    approved_file = await _service_export(db_session, tenant, status="approved")
    headers = [_base_header(h) for h in _csv_headers(approved_file.content)]
    assert {"Requested At", "Approved At"} <= set(headers)
    assert not {
        "Denied At",
        "Denial Reason",
        "Checked In At",
        "Checked In By",
        "Checked Out At",
        "Checked Out By",
    } & set(headers)


async def test_export_group_rows_repeat_visit_details(
    db_session: AsyncSession, tenant: Tenant, branch: Branch, user: User
) -> None:
    """Spec "Visit-level details repeated on group rows" and "Check-in and
    check-out staff named".
    """
    checker_out = UserFactory.build(
        id=uuid.uuid4(), email="gate-officer@acme-test.example", full_name="Gate Officer"
    )
    category = VisitorCategoryFactory.build(id=uuid.uuid4(), name="Vendor", code="EXPORT-VENDOR")
    db_session.add_all([checker_out, category])
    await db_session.flush()
    group = _build_invitation(
        db_session,
        branch.id,
        registration_type="group",
        status="checked_out",
        visitor_category_id=category.id,
        badge_number="B-0042",
        poc_name="Front Desk",
        carried_items=["Laptop", "Toolbox"],
        carried_items_description="Sealed",
        additional_notes="Arrives by cab",
        checked_in_by_user_id=user.id,
        checked_out_by_user_id=checker_out.id,
    )
    group.visitors = [_export_visitor(group.id, f"Guest {i}") for i in range(2)]
    group.vehicles = [
        InvitationVehicleFactory.build(id=uuid.uuid4(), license_plate=plate)
        for plate in ("KA-01-AB-1234", "KL-07-CD-5678")
    ]
    db_session.add(group)
    await db_session.commit()

    rows = _csv_rows((await _service_export(db_session, tenant)).content)

    assert len(rows) == 3
    for row in rows:
        assert row["Badge Number"] == "B-0042"
        assert set(row["Vehicle Number(s)"].split(", ")) == {"KA-01-AB-1234", "KL-07-CD-5678"}
        assert row["Visitor Category"] == "Vendor"
        assert row["Point of Contact"] == "Front Desk"
        assert row["Carried Items"] == "Laptop, Toolbox — Sealed"
        assert row["Additional Notes"] == "Arrives by cab"
        assert row["Checked In By"] == "Admin User"
        assert row["Checked Out By"] == "Gate Officer"
        assert row["Status"] == "Checked-out"


async def test_export_invitations_no_match_returns_header_only(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"status": "denied"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert _csv_rows(response.content) == []


@pytest.mark.parametrize(
    "params",
    [
        {"format": "pdf"},
        {"dateFrom": "2026-10-14", "dateTo": "2026-10-13"},
        {"status": "cancelled"},
    ],
)
async def test_export_invitations_rejects_invalid_params(
    client: AsyncClient, user: User, params: dict[str, str]
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
    assert "content-disposition" not in response.headers


async def test_export_checked_in_for_one_day_uses_visit_timezone(
    db_session: AsyncSession, branch: Branch
) -> None:
    """Spec "Export checked-in visitors for one day" — the day boundary is
    the visit timezone's midnight, not UTC's.
    """
    same_day = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        checked_in_at=datetime(2026, 10, 12, 19, 0, tzinfo=UTC),  # 00:30 IST on the 13th
    )
    day_before = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        checked_in_at=datetime(2026, 10, 12, 18, 0, tzinfo=UTC),  # 23:30 IST on the 12th
    )
    approved = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        checked_in_at=datetime(2026, 10, 12, 19, 0, tzinfo=UTC),
    )
    db_session.add_all([same_day, day_before, approved])
    await db_session.commit()

    export_file = await _service_export(
        db_session,
        SimpleNamespace(timezone=_KOLKATA),
        status="checked_in",
        date_range=InvitationExportDateRange(
            date_from=date(2026, 10, 13), date_to=date(2026, 10, 13)
        ),
    )

    rows = _csv_rows(export_file.content)
    assert [row["Tracking ID"] for row in rows] == [same_day.tracking_id]
    assert export_file.row_count == 1
    assert export_file.filename.startswith("invitations-checked-in-")


async def test_export_approved_excludes_invitations_that_moved_on(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    approved = _build_invitation(db_session, branch.id, status="approved")
    checked_in = _build_invitation(
        db_session, branch.id, status="checked_in", checked_in_at=datetime.now(UTC)
    )
    db_session.add_all([approved, checked_in])
    await db_session.commit()

    export_file = await _service_export(db_session, tenant, status="approved")

    assert [r["Tracking ID"] for r in _csv_rows(export_file.content)] == [approved.tracking_id]


async def test_export_date_range_without_status_filters_on_created_at(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    inside = _build_invitation(
        db_session, branch.id, status="denied", created_at=datetime(2026, 10, 5, 9, tzinfo=UTC)
    )
    outside = _build_invitation(
        db_session, branch.id, status="approved", created_at=datetime(2026, 9, 5, 9, tzinfo=UTC)
    )
    db_session.add_all([inside, outside])
    await db_session.commit()

    export_file = await _service_export(
        db_session,
        tenant,
        date_range=InvitationExportDateRange(
            date_from=date(2026, 10, 1), date_to=date(2026, 10, 31)
        ),
    )

    assert [r["Tracking ID"] for r in _csv_rows(export_file.content)] == [inside.tracking_id]


async def test_export_group_invitation_rows_are_adjacent_without_document_references(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    """Spec "Group invitation yields a row per person" and "No document or
    photo references leak" — the service never consults `documents:view`,
    so no caller can get storage keys or URLs into the file.
    """
    group = _build_invitation(
        db_session,
        branch.id,
        registration_type="group",
        primary_contact_id_proof_storage_key="vmss:secret-primary-id",
        primary_contact_photo_storage_key="vmss:secret-primary-photo",
    )
    group.visitors = [_export_visitor(group.id, f"Guest {i}") for i in range(3)]
    individual = _build_invitation(db_session, branch.id)
    db_session.add_all([group, individual])
    await db_session.commit()

    export_file = await _service_export(db_session, tenant)

    rows = _csv_rows(export_file.content)
    assert len(rows) == 5
    group_positions = [i for i, row in enumerate(rows) if row["Tracking ID"] == group.tracking_id]
    assert group_positions == list(range(group_positions[0], group_positions[0] + 4))
    assert rows[group_positions[0]]["Visitor Role"] == invitation_export.PRIMARY_CONTACT
    body = export_file.content.decode("utf-8-sig")
    assert "secret" not in body
    assert "http" not in body


async def test_export_list_filters_narrow_the_export_like_the_list(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    match = _build_invitation(
        db_session,
        branch.id,
        registration_type="individual",
        source="visitor_walk_in",
        purpose_of_visit="Interview",
        primary_contact_full_name="Priya Export",
    )
    wrong_source = _build_invitation(
        db_session,
        branch.id,
        source="staff_pre_registration",
        purpose_of_visit="Interview",
        primary_contact_full_name="Priya Export",
    )
    wrong_purpose = _build_invitation(
        db_session,
        branch.id,
        source="visitor_walk_in",
        purpose_of_visit="Delivery",
        primary_contact_full_name="Priya Export",
    )
    wrong_name = _build_invitation(
        db_session,
        branch.id,
        source="visitor_walk_in",
        purpose_of_visit="Interview",
        primary_contact_full_name="Someone Else",
    )
    db_session.add_all([match, wrong_source, wrong_purpose, wrong_name])
    await db_session.commit()

    export_file = await _service_export(
        db_session,
        tenant,
        registration_type="individual",
        source="visitor_walk_in",
        purpose_of_visit="Interview",
        search="priya",
    )

    assert [r["Tracking ID"] for r in _csv_rows(export_file.content)] == [match.tracking_id]


async def test_export_row_cap_rejects_over_and_allows_exactly_at_the_cap(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = _build_invitation(db_session, branch.id, registration_type="group")
    db_session.add(group)
    await db_session.flush()
    db_session.add_all([_export_visitor(group.id, f"Guest {i}") for i in range(2)])
    await db_session.commit()
    # The request shares this session; `group.visitors` was loaded empty at
    # build time and an already-loaded collection isn't refilled.
    db_session.expire(group, ["visitors"])
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(settings, "invitation_export_max_rows", 2)
    over = await client.get("/api/v1/invitations/export", headers=headers)
    assert over.status_code == 422, over.text
    assert "Narrow the filters" in over.json()["message"]
    assert "content-disposition" not in over.headers

    monkeypatch.setattr(settings, "invitation_export_max_rows", 3)
    at_cap = await client.get("/api/v1/invitations/export", headers=headers)
    assert at_cap.status_code == 200, at_cap.text
    assert len(_csv_rows(at_cap.content)) == 3

    actions = (
        (
            await db_session.execute(
                select(AuditLog.diff).where(AuditLog.action == "invitations_exported")
            )
        )
        .scalars()
        .all()
    )
    assert [diff["row_count"] for diff in actions] == [3]


async def test_export_successful_export_is_audited_with_filters(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    db_session.add_all([_build_invitation(db_session, branch.id, status="approved")])
    await db_session.commit()
    user_id = user.id

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations/export",
        params={"status": "approved", "format": "xlsx", "search": "INV"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    [entry] = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "invitations_exported")
            )
        )
        .scalars()
        .all()
    )
    assert entry.actor_user_id == user_id
    assert entry.entity_type == "Invitation"
    assert entry.diff == {
        "filters": {"status": "approved", "search": "INV"},
        "format": "xlsx",
        "row_count": 1,
    }


async def test_export_reception_exports_their_branch_only(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    await seed_default_roles(db_session)
    other_branch = BranchFactory.build(id=uuid.uuid4(), name="Other Branch", code="OTHER")
    db_session.add(other_branch)
    await db_session.flush()
    receptionist = await _reception_holder(db_session, branch.id)
    own = _build_invitation(db_session, branch.id)
    elsewhere = _build_invitation(db_session, other_branch.id)
    db_session.add_all([own, elsewhere])
    await db_session.commit()
    own_tracking_id, other_branch_id = own.tracking_id, other_branch.id
    token = issue_token(receptionist)

    response = await client.get(
        "/api/v1/invitations/export",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200, response.text
    assert [r["Tracking ID"] for r in _csv_rows(response.content)] == [own_tracking_id]

    response = await client.get(
        "/api/v1/invitations/export",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(other_branch_id)},
    )
    assert response.status_code == 403, response.text


async def test_export_requires_invitations_export_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """Spec "Caller without invitations:export is denied" and "Host is
    denied by default" — `relevantToMe` narrows the export scope, it never
    replaces the permission check.
    """
    viewer_role = RoleFactory.build(
        id=uuid.uuid4(),
        name="board-viewer",
        permissions=[await _get_or_create_permission(db_session, "invitations:view-all")],
    )
    db_session.add(viewer_role)
    await db_session.flush()
    viewer = _make_role_holder(db_session, viewer_role, branch.id)
    host = _make_role_holder(db_session, await _host_role(db_session), branch.id)
    db_session.add(_build_invitation(db_session, branch.id))
    await db_session.commit()

    viewer_token, host_token = issue_token(viewer), issue_token(host)

    for token, params in (
        (viewer_token, {}),
        (host_token, {}),
        (host_token, {"relevantToMe": "true"}),
    ):
        response = await client.get(
            "/api/v1/invitations/export",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, response.text
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "invitations_exported")
        )
        == 0
    )


async def test_export_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession, branch: Branch
) -> None:
    """testing-standards.md §2: an export through one tenant's session never
    sees another tenant schema's invitations.
    """
    other_schema = "tenant_other_export_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        other_branch = BranchFactory.build(id=uuid.uuid4(), name="Elsewhere", code="ELSE")
        other_session.add(other_branch)
        await other_session.flush()
        foreign = _build_invitation(other_session, other_branch.id)
        other_session.add(foreign)
        await other_session.commit()
        foreign_tracking_id = foreign.tracking_id

    own = _build_invitation(db_session, branch.id)
    db_session.add(own)
    await db_session.commit()

    export_file = await _service_export(db_session, SimpleNamespace(timezone="UTC"))

    tracking_ids = [r["Tracking ID"] for r in _csv_rows(export_file.content)]
    assert tracking_ids == [own.tracking_id]
    assert foreign_tracking_id not in tracking_ids
