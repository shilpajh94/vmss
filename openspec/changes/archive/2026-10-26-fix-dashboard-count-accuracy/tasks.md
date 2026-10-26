> Design: `VMSS_API/openspec/changes/fix-dashboard-count-accuracy/design.md`, decision D7 has the link table. No separate web design.md.
> Prerequisites: the VMSS_API change of the same name is implemented (the new fields and params exist), and `live-dashboards-and-analytics` is archived here, so the MODIFIED deltas have a main spec to apply to.

## 1. Data layer

- [x] 1.1 Add `scheduledTodayCheckedInCount`, `openPendingApprovalCount` and `oldestOpenPendingSubmittedAt` to the dashboard overview Zod schema, and `openAwaitingApproval` to the my-overview schema (required fields)
- [x] 1.2 Add `visitDateFrom`, `visitDateTo`, `upcoming`, `excludeExpired` and `branchId` to `ListVisitRequestsParams` and the export params in `visit-request-summary-repository.ts`, sent only when set

## 2. Dashboard links (design D7)

- [x] 2.1 In `dashboard-format.ts`, replace `boardStatusPath` with a `boardDrillDownPath(basePath, { statuses, visitDateFrom, visitDateTo, upcoming, excludeExpired, branchId })` builder (repeated `status`); keep `boardInvitationPath`
- [x] 2.2 `BranchDashboard`: switch the tiles to the new fields and the D7 links, and pass `dashboard.branchId` into every link (tiles, status bars, both cards)
- [x] 2.3 `PersonalDashboard`: "Awaiting Approval" uses `openAwaitingApproval`; switch the tiles and the Upcoming card to the D7 links
- [x] 2.4 `RecentCheckinsCard` "View all" → `checked_in` + `checked_out`; `UpcomingVisitorsCard` "View all" → `upcoming=true`; both take an optional `branchId`
- [x] 2.5 `StatusBarsChart`: each bar links with its status and `visitDateFrom` = the first `dailyTrend` date, `visitDateTo` = `today`, plus `branchId`

## 3. Boards read the drill-down

- [x] 3.1 `use-invitations-board.ts`: read every `status` value (`getAll`), plus `visitDateFrom`, `visitDateTo`, `upcoming`, `excludeExpired` and `branchId` from the URL once on load; drop malformed values silently; hold them in state and add them to `columnQuery` and the export call
- [x] 3.2 Add a "From dashboard" chip row to the shared board filter bar (both boards): one removable chip per drill-down param, the branch shown by name (from the branch options already loaded), and "Clear filters" clears them; `isFiltering` counts them
- [x] 3.3 Check that the closed-statuses column still shows denied/archived results when a drill-down includes them (status bars for `denied`/`archived`)

## 4. Verification

- [x] 4.1 e2e (new module, `e2e/test_dashboard_drill_down.py`): for admin, reception and host, follow every counted link (each tile and status bar) and assert the sum of the board's column totals equals its number; include one run with a branch selected. The Upcoming card's "View all" has the same URL as the Upcoming tile; Recent Check-ins "View all" is checked by URL in `test_live_dashboards.py` (it shows no total to compare)
- [x] 4.2 e2e: open `/admin/invitations` with drill-down params, remove a chip, and assert the board widens; export from a drilled-down board and assert the request carries the drill-down filters (row-level export parity is the API's `test_export_applies_the_drill_down_filters`)
- [x] 4.3 `npm run lint` and `tsc -b`; run only the new e2e module and `test_auth_and_dashboards.py`, not the full suite
- [x] 4.4 Manual check at 360 px and 1440 px that the chip row wraps without clipping in light and dark mode
