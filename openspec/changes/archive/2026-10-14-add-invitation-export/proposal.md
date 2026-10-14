## Why

Reception, security and admin staff need to take invitation data out of VMSS
by lifecycle status. Examples: "everyone who checked in today" for a
security handover, "all approved visitors for next week" for a gate list,
or "denied visitors this month" for a compliance review. Today the only
way to get this data is to page through `GET /invitations` 100 rows at a
time and copy it by hand. That listing also shows one row per invitation,
so the co-visitors of a group invitation never appear.

## What Changes

- New endpoint `GET /invitations/export` that returns a downloadable file
  (not the JSON envelope) of the invitations that match the filters.
- Two formats, chosen with `format=csv|xlsx` (default `csv`).
- **One row per visitor**: the primary contact is one row, and each
  co-visitor of a group invitation is another row. Every row repeats its
  parent invitation's fields (tracking ID, status, branch, host, purpose,
  visit date and the lifecycle timestamps).
- Filters are the same as `GET /invitations`: `status`, `registrationType`,
  `source`, `search`, `purposeOfVisit`, `X-Branch-ID` and `relevantToMe`.
  The export adds a `dateFrom`/`dateTo` range. When `status` is set, the
  range applies to the timestamp for that status: `checked_in` filters on
  `checkedInAt`, `approved` on `approvedAt`, and so on. Without `status`,
  it applies to the creation time.
- The export is capped at a fixed number of rows. A request that would
  go over the cap is rejected with 422 and a message asking the caller to
  narrow the filters. The file is never silently cut short.
- A new permission, `invitations:export`. It is granted by default to the
  roles that already hold `invitations:view-all` (`admin`, `reception`,
  `security`), and a tenant migration backfills the grant for existing
  tenants.
- Each export is written to the audit trail (actor, filters, format, row
  count), because it is a bulk read of PII.
- The exported file contains no ID-proof documents, photos, storage keys
  or signed URLs. The ID-proof *type* is included; the document is not.
- Cell values are escaped against spreadsheet formula injection.
- New dependency: `openpyxl`, for XLSX output.

No breaking changes. `GET /invitations` is unchanged.

## Capabilities

### New Capabilities
- `invitation-export`: staff export of invitations as CSV/XLSX, one row
  per visitor. Covers the filter and date-range semantics, the row cap,
  the permission and branch scoping, which columns are included and
  excluded, formula-injection safety, and audit logging.

### Modified Capabilities
<!-- None: GET /invitations and its requirements are unchanged; the export
     reuses its filter semantics by reference rather than altering them. -->

## Impact

- **Code**: `invitations/router.py` (new route, registered before
  `/{invitation_id}`), `invitations/service.py`, `invitations/repository.py`
  (a filter builder shared with `list_page`, plus a non-paginated,
  visitor-eager-loading query), a new `invitations/export.py` that renders
  the files, `invitations/schemas.py` (the format enum and the export
  query schema), and `auth/rbac_catalog.py`.
- **Migrations**: one `alembic_tenant` migration that grants
  `invitations:export`. It chains after whatever the tenant head is when
  the change is implemented.
- **Dependencies**: `openpyxl` (`uv add openpyxl`).
- **API clients**: the VMMS_WEB invitation board gets an export action in
  a separate repo. The API change is additive, so `v1` can ship without
  waiting for it.
- **Docs**: `docs/features/invitations.md`.
