## Why

The staff Visits dashboard (`/staff/dashboard`) currently renders three separate "Refresh" controls (one in the workspace header, two more stacked in the search/toolbar row) that all do the same thing, which reads as broken rather than intentional. The board also never updates on its own — staff must manually click Refresh to see new requests — and the "Filters" control next to search is purely decorative today (per the existing `staff-dashboard` spec: "Filters affordance is presented but not yet functional"), so staff have no way to narrow the board beyond free-text search.

## What Changes

- Remove the two redundant refresh controls from the search/toolbar row (`SearchActionBar`), keeping exactly one "Refresh" action on the page, in the workspace header.
- Add automatic background refresh of the visit-requests board on a fixed interval, so the board stays current without a manual click. Auto-refresh runs silently (no full-board loading state) and does not fire while a deny/reschedule/delegate action or modal is in progress, to avoid disrupting in-flight staff actions. **Assumption**: interval is 30 seconds; no existing polling convention exists in the codebase to match, so this is a reasonable default rather than a stated requirement — flag if a different cadence is wanted.
- Make the "Filters" control functional: staff can filter the board by Purpose of Visit and by Registration Type (Individual / Group), combinable with each other and with the existing search box. Reuses the existing `DropdownFilter` component pattern already used on the Audit Trail page. **Assumption**: these two fields were chosen because they're already present on every visit request (`purposeOfVisit`, `registrationType`) and match the filter-bar pattern already shipped elsewhere in the app; a status filter is not included since status is already expressed as the four board columns.

## Capabilities

### Modified Capabilities
- `staff-dashboard`: "Refresh reloads the visit-requests list" gains a single-control requirement; new requirement for automatic periodic refresh; "Filters affordance is presented but not yet functional" is replaced with a functional Purpose-of-Visit / Registration-Type filter requirement.

## Impact

- `src/presentation/pages/staff-dashboard/Components/SearchActionBar.tsx` — remove the two extra refresh buttons, wire "Filters" to real state and dropdown controls.
- `src/presentation/pages/staff-dashboard/Components/WorkspaceHeader.tsx` — remains the sole refresh control (no change expected beyond confirming it stays).
- `src/presentation/hooks/use-invitations-board.ts` (shared by `staff-dashboard` and `admin-invitations`) — add interval-based silent auto-refresh and filter state/derivation; must not regress `admin-invitations`, which also consumes this hook but has no Filters UI today, so filter state should default to "no filters applied" there.
- `src/presentation/pages/staff-dashboard/hooks/use-staff-dashboard.ts` — expose new filter state/handlers to the page.
- No API, schema, or composition-root changes — filtering is client-side over already-fetched `VisitRequestSummary` data.
