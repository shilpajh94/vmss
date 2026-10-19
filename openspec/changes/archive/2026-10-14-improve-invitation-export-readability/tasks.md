## 1. Data loading

- [x] 1.1 Extend `InvitationExportNames` with `visitor_category`, `checked_in_by` and `checked_out_by`
- [x] 1.2 In `InvitationRepository.list_for_export`, outer-join `VisitorCategory` and two more aliased `User`s (check-in and check-out), and add `selectinload(Invitation.vehicles)` next to `visitors`. It must stay one statement plus the eager loads, with no per-row queries (design.md Decision 4).

## 2. Column model and labels (`invitations/export.py`)

- [x] 2.1 Replace `HEADERS` with an ordered `ExportColumn(key, header, lifecycle, width)` table covering the 31 columns in the spec's order, and add `columns_for(status)` implementing the per-status lifecycle table (design.md Decision 1)
- [x] 2.2 Add `STATUS_LABELS`, `SOURCE_LABELS`, `REGISTRATION_TYPE_LABELS` and `ROLE_LABELS` matching the web board's wording, plus a `_label` fallback that turns `snake_case` into Title Case (design.md Decision 3)
- [x] 2.3 Rewrite `build_rows` to return typed values keyed by column key: labels for the enum fields, naive tz-local `datetime` for timestamps, `date`/`time` for the visit date and time, `", "`-joined license plates, carried items with the description appended after `" — "`, and `None` for missing values. Remove the `neutralize` calls from row building.

## 3. Renderers

- [x] 3.1 `render_csv(rows, columns, tz_name)`: write timestamp headers with ` (<tz name>)`, format dates as `YYYY-MM-DD`, times as `HH:MM` and timestamps as `YYYY-MM-DD HH:MM`, write `None` as empty, and apply `neutralize` to every text cell. Keep the UTF-8 BOM.
- [x] 3.2 `render_xlsx(rows, columns, tz_name)`: write native date/datetime/time cells with the matching `number_format`, and text as string-typed cells with illegal characters stripped and no `'` prefix. Before the first append, set a bold header, `freeze_panes = "A2"`, an auto-filter over the header and data rows, and the per-column widths (design.md Decisions 2 and 6).

## 4. Service

- [x] 4.1 In `service.export_invitations`, pass `columns_for(status)` and the tz name (`ZoneInfo.key` or `str(tz)`) to the renderer, and change the filename to `invitations-<status with hyphens|all>-<YYYY-MM-DD>.<ext>`

## 5. Tests (`invitations/tests.py`, factories only)

- [x] 5.1 Update the existing export tests for the new filename (`invitations-checked-in-`, `invitations-all-`, the dashed date) and the new headers and column order
- [x] 5.2 Unit: every `InvitationStatus`, `RegistrationSource` and `RegistrationType` member has an explicit label, an unknown code such as `pending` renders as `Pending`, and no enum-column cell contains an underscore
- [x] 5.3 Unit: `columns_for` returns exactly the spec's lifecycle columns for each of the five statuses and all 31 columns for `None`. An endpoint test checks that `status=approved` has no Denied At, Checked In or Checked Out headers, and that `status=denied` includes Denial Reason with its value.
- [x] 5.4 Unit: a non-UTC timezone (`Asia/Kolkata`) gives a `Checked In At (Asia/Kolkata)` header and a `2026-10-13 14:35` CSV cell. When re-opened, the XLSX file has `datetime` and `date` values (not strings) in the timestamp and Visit Date cells.
- [x] 5.5 Unit: formula injection. In CSV, `=`, `+`, `-`, `@`, `\t` and `\r` values get the `'` prefix and the phone becomes `'+919800000261`. In XLSX, the same values are string-typed cells holding the exact original text (the phone is `+919800000261`), and no cell is a formula.
- [x] 5.6 Endpoint: a group invitation with a badge, two vehicles, a carried item, a POC, a visitor category and check-in/check-out users repeats those values on every row, with both plates in one cell and the staff full names shown. Add any needed `InvitationVehicleFactory` fields.
- [x] 5.7 Unit: the XLSX header row is bold, the sheet has `freeze_panes == "A2"`, and the auto-filter covers the header row
- [x] 5.8 Re-run the existing no-leak, permission-denied, tenant-isolation and row-cap export tests unchanged, and confirm they still pass

## 6. Docs and checks

- [x] 6.1 Update `docs/features/invitations.md`: the new column list and order, the per-status lifecycle columns, the header timezone and date formats, the labels, the filename format, and the revised formula-escaping note (CSV only; XLSX uses typed cells)
- [x] 6.2 Run `ddev exec uv run ruff check`, `ruff format --check`, `mypy` on the touched modules, and `ddev exec uv run pytest src/vmss_api/invitations tests/test_api_documentation.py` (not in parallel with another pytest run). Diff any failures against the known pre-existing failure sets before treating them as regressions.

## 7. Follow-up outside this repo

- [ ] 7.1 VMMS_WEB: update `filter-options.ts::exportFilename` to `invitations-<status with hyphens|all>-<YYYY-MM-DD>.<ext>` so browser downloads match the API filename. Raise it as a separate VMMS_WEB change; do not edit it from this one.
