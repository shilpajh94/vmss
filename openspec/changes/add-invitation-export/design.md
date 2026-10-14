## Context

See proposal.md for why this change is needed, and the two spec deltas for
the required behaviour. The relevant parts of the current code are:

- **Shared board logic:** `use-invitations-board.ts` drives both boards. It
  builds a `ColumnQuery` (`relevantToMe`, `registrationType`, `source`,
  `search`, `purposeOfVisit`) from its filter state. `scope` is `'mine'`
  on the staff dashboard and `'all'` on the admin board. Only the admin
  board exposes the Status and Source filters.
- **Status values:** the admin page's `STATUS_OPTIONS` are already the
  API's status values (`submitted`, `approved`, `checked_in`,
  `checked_out`, `denied`).
- **Role checks:** `StaffUser` exposes only `isAdmin` and `isReception`,
  derived from role names. The web app has no permission list, and the
  existing `canCheckOut` gate is role-based in the same way.
- **Authenticated downloads:** `ApiClient.downloadBlob` already does an
  authenticated GET that returns a `Blob`. It raises an `ApiError`
  carrying the server's error message for non-2xx responses. Audit-trail
  downloads use it and save the file with a temporary `<a download>` link.
- **CORS:** the API's `CORSMiddleware` sets no `expose_headers`, so the
  browser can't read `Content-Disposition` on a cross-origin response.

## Goals / Non-Goals

**Goals:**
- One dialog component and one export path, shared by both boards, in the
  same way `BoardFilterBar` is shared.
- No API change.

**Non-Goals:**
- Permission-based gating. The web app has no permission list; showing the
  button by role matches how `canCheckOut` works today. A tenant that
  grants `invitations:export` to a custom role can still use the API
  directly. Exposing permissions to the web app is a separate change.
- A Security-role UI. Security has no web board today.
- Progress for large exports. The API caps an export at 10,000 rows and
  returns it in a single response.

## Decisions

### 1. Data layer: new endpoint, repository method and use case
- Add `EXPORT_INVITATIONS: { endpoint: "/invitations/export", method: "GET",
  hasToken: true }` to `api-endpoints.ts`.
- Add `export(params: InvitationExportParams): Promise<Blob>` to the
  repository behind `ListVisitRequestsUseCase`
  (`VisitRequestSummaryRepository`), since it serves the same resource.
  Its HTTP implementation calls `apiClient.downloadBlob` with
  `format`, `status`, `dateFrom`, `dateTo`, `registrationType`, `source`,
  `search`, `purposeOfVisit` and `relevantToMe` as query parameters.
  `buildQueryString` already drops undefined values.
- Add `ExportInvitationsUseCase`, wired in `composition-root.ts` and
  exposed through `useAppDependencies()`, following the pattern of
  `downloadAuditReportUseCase`.

*Alternative considered:* a new standalone repository. That would mean
more wiring for one method on a resource an existing repository already
owns.

### 2. The filename is built by the client
The filename `invitations-<status|all>-<YYYYMMDD>.<ext>` uses the
browser's local date and is saved through the same temporary-anchor
pattern as audit-trail downloads. A small `saveBlob(blob, filename)`
utility in `presentation/utils/` replaces the inlined anchor code, and the
audit-trail hook switches to it as well.

*Alternative considered:* adding `expose_headers=["Content-Disposition"]`
to the API's CORS settings and reading the server's filename. That makes
this a two-repo change for a cosmetic gain; the two names differ only
around midnight, when the browser's timezone and the visit timezone
disagree.

### 3. State lives in `use-invitations-board`, the UI in `ExportInvitationsModal`
The board hook gains these values:
- `isExportOpen`, `openExport()` and `closeExport()`,
- `exportInvitations(choice)`, which returns a promise, and
- `isExporting` and `exportError`.

It also exposes `canExport`:
- `scope === 'all' ? Boolean(currentUser?.isAdmin) :
  Boolean(currentUser?.isReception)`.
- The admin board is only reachable by admins, but checking explicitly
  keeps the rule in one place.

`exportInvitations` combines the dialog's choice (status, dates, format)
with the board's current `columnQuery`, including `relevantToMe`. It
always uses the debounced search, so the export matches what the board
shows.

`ExportInvitationsModal` lives in
`components/invitation-board/` and is a controlled component. Its props
are `initialStatus`, a `summary` of the other active filters as labels,
`isExporting`, `errorMessage`, `onConfirm` and `onClose`. It builds on the
existing `Modal`, `SelectField`, native `<input type="date">` fields
(the same as `RescheduleInvitationModal`) and `SegmentedToggle` for
CSV/Excel. It holds its own form state, so editing the dialog never
changes the board's filters (spec "Changing the dialog does not change the
board").

The admin board's Export button goes in the page's title row, because
the filter bar's search field and four dropdowns already fill a 1440px
row. The staff dashboard's bar has only two dropdowns, so it takes the
button through a new `trailingAction` slot on `BoardFilterBar`. Both
pages use a shared `ExportInvitationsButton`.

The labels and values for the status, source and registration-type options move from
`admin-invitations.tsx` into a shared `invitation-board/filter-options.ts`.
The dialog then shows the same labels the filter bar uses.

### 4. Validation and error handling
- **Before sending:** From later than To disables the confirm button and
  shows an inline message. The API's 422 for the same case is a backstop.
- **Server rejections:** on an `ApiError`, the message (for example the
  API's "…Narrow the filters…" text for an over-cap export) is set as
  `exportError` and shown inside the dialog. The dialog stays open with
  its state intact. A toast is not used, because the user needs to keep
  the dialog open to adjust it.
- **401:** handled by the existing `ensureOk` session-expiry path, the
  same as every other call.
- **Repeat clicks:** `isExporting` disables the confirm button, and
  `exportInvitations` returns early while an export is already in flight.

### 5. Date-hint copy is fixed per status
The hint text comes from a fixed map: `submitted` → "Submitted date",
`approved` → "Approval date", `denied` → "Denial date", `checked_in` →
"Check-in date", `checked_out` → "Check-out date", and All → "Created
date". This mirrors the API's own status-to-timestamp mapping.

## Risks / Trade-offs

- [Role-based gating can drift from the real permission, for example a
  custom role that holds `invitations:export`, or Reception with the grant
  removed] → In the second case the API returns 403 and the dialog shows
  the message. A proper fix is to expose permissions to the web app, which
  is out of scope.
- [The web build ships before the API is deployed] → The button gets an
  error (404, or 422 because `export` is parsed as an invitation id) and
  shows it in the dialog; nothing breaks. Deploy the API first.
- [The browser's date can differ from the visit-timezone date near
  midnight, in the filename only] → Accepted; this is cosmetic.
- [A large XLSX takes a few seconds to generate] → The busy state on the
  confirm button covers it.
