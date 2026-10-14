## Context

`GET /invitations/export` is built by the unarchived `add-invitation-export`
change (see that change's design.md). The current pipeline is:

- `InvitationRepository.list_for_export` returns `(Invitation,
  InvitationExportNames)` pairs. It outer-joins the branch, building,
  department and host names and eager-loads `visitors`. `vehicles` is
  `lazy="raise"` and is not loaded.
- `export.build_rows(invitations, tz)` returns `list[list[str]]` in a fixed
  `HEADERS` order. Every value is already formatted as a string (ISO
  timestamps) and already passed through `neutralize`.
- `render_csv` / `render_xlsx` write those strings unchanged. XLSX forces
  every cell to the string data type.
- `service.export_invitations` builds the filename as
  `invitations-<status|all>-<YYYYMMDD>.<ext>`.

Because formatting and the formula guard both happen in `build_rows`,
before the format is known, XLSX inherits the CSV-only `'` prefix and
cannot store real date cells. See proposal.md for the problems this
causes and specs/invitation-export/spec.md for the required output.

## Goals / Non-Goals

**Goals:**
- One column definition that drives the headers, the row values and the
  per-status column selection, so they cannot drift apart.
- Formatting that depends on the format (text vs. native date cells, the
  `'` guard) happens in the renderer, not in row building.
- Still no per-row queries.

**Non-Goals:**
- Exporting admin-authored custom form fields, such as a visitor's company
  name collected through the form builder. Those columns vary per branch
  and form version and remain out of scope, as in `add-invitation-export`.
- A caller-chosen column set or a `columns=` parameter.
- Approver names per approval step ("Approved By"). Multi-step approvals
  make one name misleading. Revisit with the approvals report.
- Localized labels or a per-tenant date format.

## Decisions

### 1. A column table drives headers, values and per-status selection
`export.py` defines an ordered tuple of `ExportColumn(key, header,
lifecycle)` entries. `lifecycle` is `None` for a column that always
appears, or the set of statuses it applies to; for example, Approved At
applies to `{approved, checked_in, checked_out}`. A function
`columns_for(status)` returns the full tuple when `status is None`, and
otherwise drops lifecycle columns whose set does not contain `status`.
Headers for timestamp columns are rendered with ` (<tz name>)` appended.
The tz name is `ZoneInfo.key` when available, otherwise `str(tz)`, so the
UTC fallback shows `(UTC)`.

*Alternative considered:* building the full 31-column row and deleting
columns by index afterwards. That approach is fragile when columns move,
and the spec ties the columns to the status, so the table is the natural
place for that rule.

### 2. Rows carry typed values; renderers format them
`build_rows` returns `list[dict[str, ExportValue]]` keyed by column key,
where `ExportValue = str | date | datetime | time | None`. Timestamps are
converted to the export timezone and made naive at this point (the
timezone is already in the header).

- `render_csv(rows, columns, tz_name)` formats dates as `%Y-%m-%d`, times
  as `%H:%M` and timestamps as `%Y-%m-%d %H:%M`. It writes `None` as an
  empty string and applies `neutralize` to every text value.
- `render_xlsx(rows, columns, tz_name)` writes `date`, `datetime` and
  `time` values as native cells with `number_format` values `yyyy-mm-dd`,
  `yyyy-mm-dd hh:mm` and `hh:mm`. It writes text as a string-typed
  `WriteOnlyCell` (`data_type = "s"`) with illegal characters stripped and
  **no** `neutralize`.

The string data type is what stops Excel and LibreOffice from evaluating a
cell as a formula. The `'` prefix was only defense in depth, and it is
exactly what makes phone numbers look wrong.

*Alternative considered:* keeping `neutralize` in XLSX and exempting
values that look like phone numbers. That keeps a fragile heuristic in a
security guard, and it still leaves `-`/`+`-prefixed notes looking wrong.
*Alternative considered:* removing the guard from CSV too and relying on
quoting. Excel ignores CSV quoting when deciding whether a value is a
formula, so the guard stays for CSV.

### 3. Labels are fixed maps with a readable fallback
`STATUS_LABELS`, `SOURCE_LABELS`, `REGISTRATION_TYPE_LABELS` and
`ROLE_LABELS` (`Primary Contact` / `Co-Visitor`) live in `export.py`. The
status and source labels copy the web board's `filter-options.ts`
wording. A `_label(code, mapping)` helper falls back to
`code.replace("_", " ").title()` when a code is missing from the map, so a
future status never leaks as a raw code. A unit test asserts that every
`InvitationStatus`, `RegistrationSource` and `RegistrationType` member has
an explicit label, so the fallback is only a safety net.

The other display values are already names. Purpose and duration come from
the server-written snapshot columns (`purpose_of_visit`,
`expected_duration`). ID-proof types come from the form builder's option
labels, such as "Aadhaar Card". They are exported as stored.

### 4. Extra columns come from the same single query
`list_for_export` is extended, still as one statement plus the existing
`selectinload`:

- an outer join to `VisitorCategory` gives the category name,
- two more aliased `User` outer joins (on `checked_in_by_user_id` and
  `checked_out_by_user_id`) give the check-in and check-out staff names,
- `.options(selectinload(Invitation.vehicles))` loads license plates as
  one extra `IN` query (query-performance.md §1).

`InvitationExportNames` gains `visitor_category`, `checked_in_by` and
`checked_out_by`. The remaining new columns are plain `Invitation`
attributes: `poc_name`, `badge_number`, `denial_reason`,
`additional_notes`, `carried_items` and `carried_items_description`.

Carried Items is `", ".join(carried_items)`. When
`carried_items_description` is set, it is appended after `" — "`, so the
free-text detail is not lost.

`count_export_rows` is unchanged, because vehicles do not add rows.

### 5. Filename formatting in the service
`service.export_invitations` builds
`f"invitations-{(status or 'all').replace('_', '-')}-{datetime.now(tz):%Y-%m-%d}.{ext}"`.
It also passes `status` and the tz name through to the renderer.

The web client currently ignores this header, because it cannot read it
across origins and builds its own name. Its `exportFilename` needs the
same change in VMMS_WEB as a follow-up (proposal.md Impact). The API still
sets the header correctly for direct API callers and Swagger downloads.

### 6. XLSX presentation
Before any rows are appended in write-only mode, the renderer sets:

- `sheet.freeze_panes = "A2"`,
- `sheet.auto_filter.ref` spanning the header row and the data rows (the
  row count is known up front), and
- `sheet.column_dimensions[letter].width` from a per-column width in the
  column table.

Header cells use `Font(bold=True)`. Openpyxl's write-only mode supports
all of these when they are set before the first `append`.

## Risks / Trade-offs

- [Dropping per-cell UTC offsets loses information for a tenant whose
  timezone observes DST: a timestamp in the repeated hour is ambiguous] →
  The header names the IANA zone. The current tenants are in non-DST zones
  (Asia/Kolkata). Exact instants remain in the audit trail and the API.
- [Status-dependent columns change the column count between exports, which
  would break a script that reads columns by position] → The header labels
  are stable, and the endpoint is not released yet. The behavior is
  documented in `docs/features/invitations.md`.
- [Dropping `neutralize` in XLSX relies on the string cell type] → Unit
  tests re-open the workbook and assert that every text cell has
  `data_type == "s"` and that no cell holds a formula. This includes a
  `=HYPERLINK(...)` name and a `+`/`-`-prefixed note.
- [Additional Notes and Carried Items are free text, up to 2,000 characters,
  that staff and visitors type] → They go through the same CSV guard and
  XLSX string typing as every other text value. 2,000 characters is well
  under Excel's 32,767-character cell limit.
- [The web filename keeps underscores until VMMS_WEB is updated] → This is
  tracked as a follow-up task. It does not affect the file's contents.

## Migration Plan

No migration and no new dependency. Archive `add-invitation-export` before
this change, so the `invitation-export` main spec exists for this delta to
modify. Rollback means reverting the code.
