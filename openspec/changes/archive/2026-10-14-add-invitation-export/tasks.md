## 1. Setup and Permission

- [x] 1.1 `ddev exec uv add openpyxl` and commit `pyproject.toml` and `uv.lock`
- [x] 1.2 Add an `invitation_export_max_rows: int = 10_000` setting to `core/config.py`. Mirror it in `.env.example` if same-shaped settings are listed there.
- [x] 1.3 Add `invitations:export` to the permission catalog in `auth/rbac_catalog.py` and to the `admin`, `reception` and `security` defaults. Do not add it to `host`.
- [x] 1.4 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` to confirm there is a single head, then author the idempotent `grant_invitations_export` tenant migration. Follow the pattern in `6054f5200ed1`: the catalog insert and the grant both use `ON CONFLICT DO NOTHING`, and the downgrade removes only this tenant's grants.
- [x] 1.5 Write a migration test, modeled on `tests/test_grant_invitations_revert_approval_migration.py`: `admin`, `reception` and `security` are granted, `host` and custom roles are not, and the upgrade is safe to run twice

## 2. Repository: Shared Filters and Export Queries

- [x] 2.1 Extract `InvitationRepository._list_filters(...)` from `list_page`. It accepts an optional `branch_scope` and an optional relevance filter and combines them with AND. Switch `list_page` to it with no change in behavior, and confirm the existing `GET /invitations` tests still pass.
- [x] 2.2 Add a status-to-timestamp-column mapping (`None` maps to `created_at`) and a date-range clause builder that takes UTC bounds
- [x] 2.3 Add `count_export_rows(...)`: one query returning the sum, over the filtered invitations, of 1 plus the co-visitor count
- [x] 2.4 Add `list_for_export(...)`: the filtered invitations with `selectinload(Invitation.visitors)`, sorted by the mapped timestamp in descending order
- [x] 2.5 Add a single batched lookup query for branch, building and department names and the host display name, keyed by id. No per-row queries.

## 3. Schemas and Rendering

- [x] 3.1 In `invitations/schemas.py`, add an `ExportFormat` enum (`csv`, `xlsx`) and an export query model with `dateFrom`/`dateTo` (dates) and a `dateFrom <= dateTo` validator
- [x] 3.2 Create `invitations/export.py` with the header labels, `build_rows(...)` (one row per person, primary contact first, invitation fields repeated, timestamps in the tenant timezone with their offset, no storage keys or URLs), and the formula-injection neutralizer
- [x] 3.3 Implement `render_csv` (UTF-8 with BOM) and `render_xlsx` (`openpyxl` write-only mode, every cell an explicit string)
- [x] 3.4 Unit tests for `export.py`: individual vs group row expansion, column order, timezone formatting, and the neutralizing of `=`, `+`, `-`, `@`, `\t` and `\r` in both formats. Re-open the XLSX bytes with `openpyxl` and assert that no cell is a formula.

## 4. Service and Route

- [x] 4.1 Add `service.export_invitations(...)`. It turns `dateFrom`/`dateTo` into UTC bounds using `tenant.timezone`, runs the row count, raises the over-cap error, loads the rows and lookups, renders the file through `anyio.to_thread.run_sync`, and returns `(bytes, row_count)`.
- [x] 4.2 Add `GET /invitations/export` in `invitations/router.py`, registered before `/{invitation_id}`. It uses `require_branch_scope("invitations:export")` with `relevantToMe` added on top with AND, accepts the same filter params as the list plus `format`/`dateFrom`/`dateTo`, and returns a `Response` with the correct media type and `Content-Disposition` filename. The over-cap case returns 422 through `error_response`.
- [x] 4.3 Declare `response_class` and the `responses` content types so Swagger shows a file download, and check that `tests/test_api_documentation.py` still passes (update it if it requires `Envelope` on every route)
- [x] 4.4 Add the background `record_audit_log` call (`invitations_exported`, with filters, format and row_count in `diff`) and an `INFO` structlog line, neither containing visitor values. Add no audit entry on rejection.

## 5. Endpoint Tests (`invitations/tests.py`)

- [x] 5.1 Happy path: CSV by default and XLSX on request. Check the content types, the attachment filename (with the status or `all`, and the date), and that the header row is present when nothing matches.
- [x] 5.2 Status and date-range cases: `checked_in` for one day in a non-UTC tenant timezone, `approved` excludes checked-in rows, no status filters on `created_at`, and an inverted range returns 422
- [x] 5.3 A group invitation produces adjacent rows with the primary contact first, and the existing list filters (`registrationType`, `source`, `search`, `purposeOfVisit`) narrow the export the same way they narrow the list
- [x] 5.4 Permission denied: `invitations:view-all` without `invitations:export` returns 403, `host` with or without `relevantToMe` returns 403, and an unauthorized `X-Branch-ID` returns 403
- [x] 5.5 Tenant isolation: an export from one tenant never contains another tenant's rows (use the `make_tenant_schema`/`open_tenant_session` fixtures)
- [x] 5.6 Row cap: over the cap returns 422 with no file and no audit entry, and exactly at the cap succeeds (monkeypatch `settings.invitation_export_max_rows` to a small value)
- [x] 5.7 No leaks: an export by a caller holding `documents:view` contains no storage keys or URLs. A successful export writes one audit entry with the expected `diff`.
- [x] 5.8 Build all test data through the factories in `factories.py`, adding `InvitationVisitorFactory` fields as needed and pinning `id_proof_storage_key` deterministically

## 6. Docs and Verification

- [x] 6.1 Document the endpoint, filters, date-range semantics, row cap, permission, column list and the formula-escaping note in `docs/features/invitations.md`
- [x] 6.2 Run `ddev exec uv run ruff check`, `ruff format --check`, `mypy` on the touched modules, and `ddev exec uv run pytest src/vmss_api/invitations tests/test_api_documentation.py` (not in parallel with other pytest runs). Diff any failures against the known pre-existing failure sets before treating them as regressions.
