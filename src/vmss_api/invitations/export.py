"""Row building and file rendering for `GET /invitations/export`
(add-invitation-export/design.md Decision 5). Pure functions, no session —
the renderers run via `anyio.to_thread.run_sync` since they're CPU-bound.

One row per person: the primary contact first, then each co-visitor, every
row repeating its invitation's fields. No document, photo, storage key, or
URL ever reaches a row, whatever the caller's `documents:view` grant.

Rows carry typed values; each renderer formats them for its own format, so
XLSX gets native date cells and no CSV-only formula guard
(improve-invitation-export-readability/design.md Decision 2).
"""

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet._write_only import WriteOnlyWorksheet

from vmss_api.invitations.models import Invitation
from vmss_api.invitations.repository import InvitationExportNames

type ExportValue = str | date | datetime | time | None
type ExportRow = dict[str, ExportValue]


@dataclass(frozen=True)
class ExportColumn:
    """`statuses` is `None` for a column every export carries, otherwise
    the `status` filters it can hold a value for (design.md Decision 1).
    `timestamp` columns get the export timezone appended to their header.
    """

    key: str
    header: str
    width: int
    statuses: frozenset[str] | None = None
    timestamp: bool = False


_APPROVED_ONWARD = frozenset({"approved", "checked_in", "checked_out"})
_CHECKED_IN_ONWARD = frozenset({"checked_in", "checked_out"})
_DENIED = frozenset({"denied"})
_CHECKED_OUT = frozenset({"checked_out"})
_EVERY_STATUS = frozenset({"submitted", "approved", "denied", "checked_in", "checked_out"})

COLUMNS: tuple[ExportColumn, ...] = (
    ExportColumn("tracking_id", "Tracking ID", 14),
    ExportColumn("status", "Status", 13),
    ExportColumn("visitor_name", "Visitor Name", 24),
    ExportColumn("visitor_role", "Visitor Role", 16),
    ExportColumn("email", "Email", 30),
    ExportColumn("phone", "Phone Number", 18),
    ExportColumn("id_proof_type", "ID Proof Type", 16),
    ExportColumn("visitor_category", "Visitor Category", 20),
    ExportColumn("registration_type", "Registration Type", 12),
    ExportColumn("source", "Source", 22),
    ExportColumn("branch", "Branch", 18),
    ExportColumn("building", "Building", 18),
    ExportColumn("department", "Department", 20),
    ExportColumn("host", "Host", 22),
    ExportColumn("point_of_contact", "Point of Contact", 22),
    ExportColumn("purpose_of_visit", "Purpose of Visit", 22),
    ExportColumn("visit_date", "Visit Date", 12),
    ExportColumn("visit_time", "Visit Time", 10),
    ExportColumn("expected_duration", "Expected Duration", 16),
    ExportColumn("badge_number", "Badge Number", 14),
    ExportColumn("vehicle_numbers", "Vehicle Number(s)", 20),
    ExportColumn("carried_items", "Carried Items", 28),
    ExportColumn("additional_notes", "Additional Notes", 36),
    ExportColumn("requested_at", "Requested At", 20, _EVERY_STATUS, timestamp=True),
    ExportColumn("approved_at", "Approved At", 20, _APPROVED_ONWARD, timestamp=True),
    ExportColumn("denied_at", "Denied At", 20, _DENIED, timestamp=True),
    ExportColumn("denial_reason", "Denial Reason", 30, _DENIED),
    ExportColumn("checked_in_at", "Checked In At", 20, _CHECKED_IN_ONWARD, timestamp=True),
    ExportColumn("checked_in_by", "Checked In By", 22, _CHECKED_IN_ONWARD),
    ExportColumn("checked_out_at", "Checked Out At", 20, _CHECKED_OUT, timestamp=True),
    ExportColumn("checked_out_by", "Checked Out By", 22, _CHECKED_OUT),
)


def columns_for(status: str | None) -> tuple[ExportColumn, ...]:
    """Every column for an unfiltered export; otherwise drops the lifecycle
    columns that can't hold a value for `status`.
    """
    if status is None:
        return COLUMNS
    return tuple(c for c in COLUMNS if c.statuses is None or status in c.statuses)


def header_labels(columns: Sequence[ExportColumn], tz_name: str) -> list[str]:
    return [f"{c.header} ({tz_name})" if c.timestamp else c.header for c in columns]


# Status and source wording copies VMMS_WEB's invitation-board
# `filter-options.ts`, so the file reads the same as the board.
STATUS_LABELS = {
    "submitted": "Requested",
    "approved": "Approved",
    "denied": "Denied",
    "checked_in": "Checked-in",
    "checked_out": "Checked-out",
}
SOURCE_LABELS = {
    "staff_pre_registration": "Staff Pre-Registration",
    "visitor_walk_in": "Visitor Walk-in",
}
REGISTRATION_TYPE_LABELS = {"individual": "Individual", "group": "Group"}

PRIMARY_CONTACT = "Primary Contact"
CO_VISITOR = "Co-Visitor"


def label(code: str, labels: Mapping[str, str]) -> str:
    """Falls back to Title Case so a code missing from `labels` still never
    reaches the file raw.
    """
    return labels.get(code) or code.replace("_", " ").title()


# OWASP CSV-injection guidance: a leading one of these makes a spreadsheet
# evaluate the cell as a formula.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value: str) -> str:
    """Prefix `'` so a formula-like value is shown as literal text. CSV only
    — it has no cell types, so `+91…` phone numbers export as `'+91…`, the
    documented cost of the guard. XLSX relies on string-typed cells instead.
    """
    return f"'{value}" if value.startswith(_FORMULA_TRIGGERS) else value


def _text(value: str | None) -> str | None:
    return value or None


def _local(value: datetime | None, tz: tzinfo) -> datetime | None:
    """Naive tz-local wall time — the timezone is stated once, in the header."""
    return value.astimezone(tz).replace(tzinfo=None) if value else None


def _carried_items(invitation: Invitation) -> str | None:
    items = ", ".join(item for item in invitation.carried_items or [] if item)
    description = invitation.carried_items_description
    if items and description:
        return f"{items} — {description}"
    return items or description or None


def build_rows(
    invitations: Sequence[tuple[Invitation, InvitationExportNames]], tz: tzinfo
) -> list[ExportRow]:
    rows: list[ExportRow] = []
    for invitation, names in invitations:
        shared: ExportRow = {
            "tracking_id": invitation.tracking_id,
            "status": label(invitation.status, STATUS_LABELS),
            "visitor_category": _text(names.visitor_category),
            "registration_type": label(invitation.registration_type, REGISTRATION_TYPE_LABELS),
            "source": label(invitation.source, SOURCE_LABELS),
            "branch": _text(names.branch),
            "building": _text(names.building),
            "department": _text(names.department or invitation.department_to_visit),
            "host": _text(names.host or invitation.host_name_or_email),
            "point_of_contact": _text(invitation.poc_name),
            "purpose_of_visit": _text(invitation.purpose_of_visit),
            "visit_date": invitation.preferred_visit_date,
            "visit_time": invitation.preferred_visit_time,
            "expected_duration": _text(invitation.expected_duration),
            "badge_number": _text(invitation.badge_number),
            "vehicle_numbers": _text(", ".join(v.license_plate for v in invitation.vehicles)),
            "carried_items": _carried_items(invitation),
            "additional_notes": _text(invitation.additional_notes),
            "requested_at": _local(invitation.submitted_at, tz),
            "approved_at": _local(invitation.approved_at, tz),
            "denied_at": _local(invitation.denied_at, tz),
            "denial_reason": _text(invitation.denial_reason),
            "checked_in_at": _local(invitation.checked_in_at, tz),
            "checked_in_by": _text(names.checked_in_by),
            "checked_out_at": _local(invitation.checked_out_at, tz),
            "checked_out_by": _text(names.checked_out_by),
        }
        people = [
            (
                PRIMARY_CONTACT,
                invitation.primary_contact_full_name,
                invitation.primary_contact_email,
                invitation.primary_contact_phone,
                invitation.primary_contact_id_proof_type,
            ),
            *(
                (CO_VISITOR, v.full_name, v.email, v.phone, v.id_proof_type)
                for v in invitation.visitors
            ),
        ]
        for role, name, email, phone, id_proof_type in people:
            rows.append(
                {
                    **shared,
                    "visitor_name": _text(name),
                    "visitor_role": role,
                    "email": _text(email),
                    "phone": _text(phone),
                    "id_proof_type": _text(id_proof_type),
                }
            )
    return rows


def _csv_cell(value: ExportValue) -> str:
    # `datetime` before `date`: it's a `date` subclass.
    if value is None:
        return ""
    if isinstance(value, datetime):
        return f"{value:%Y-%m-%d %H:%M}"
    if isinstance(value, date):
        return f"{value:%Y-%m-%d}"
    if isinstance(value, time):
        return f"{value:%H:%M}"
    return neutralize(value)


def render_csv(rows: Sequence[ExportRow], columns: Sequence[ExportColumn], tz_name: str) -> bytes:
    """UTF-8 with a BOM, so Excel detects the encoding of non-ASCII names."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header_labels(columns, tz_name))
    writer.writerows([_csv_cell(row.get(c.key)) for c in columns] for row in rows)
    return buffer.getvalue().encode("utf-8-sig")


_XLSX_NUMBER_FORMATS: tuple[tuple[type, str], ...] = (
    (datetime, "yyyy-mm-dd hh:mm"),
    (date, "yyyy-mm-dd"),
    (time, "hh:mm"),
)
_BOLD = Font(bold=True)


def _xlsx_cell(sheet: WriteOnlyWorksheet, value: ExportValue) -> WriteOnlyCell:
    if isinstance(value, str):
        # Stored as a string-typed cell, so a formula-like value is never
        # evaluated — no `neutralize` prefix needed.
        cell = WriteOnlyCell(sheet, value=ILLEGAL_CHARACTERS_RE.sub("", value))
        cell.data_type = "s"
        return cell
    cell = WriteOnlyCell(sheet, value=value)
    for kind, number_format in _XLSX_NUMBER_FORMATS:
        if isinstance(value, kind):
            cell.number_format = number_format
            break
    return cell


def render_xlsx(rows: Sequence[ExportRow], columns: Sequence[ExportColumn], tz_name: str) -> bytes:
    """Write-only workbook with a bold, frozen, filterable header row. Sheet
    settings must be in place before the first `append` in write-only mode.
    """
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Invitations")
    last_column = get_column_letter(len(columns))
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{last_column}{len(rows) + 1}"
    for index, column in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = column.width

    header_cells = []
    for header in header_labels(columns, tz_name):
        cell = _xlsx_cell(sheet, header)
        cell.font = _BOLD
        header_cells.append(cell)
    sheet.append(header_cells)
    for row in rows:
        sheet.append([_xlsx_cell(sheet, row.get(c.key)) for c in columns])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
