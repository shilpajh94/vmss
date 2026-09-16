## 1. Single refresh control

- [x] 1.1 Remove the icon-only refresh button and the standalone "Refresh" button from `SearchActionBar.tsx`, along with the now-unused `onRefresh` prop on that component.
- [x] 1.2 Confirm `WorkspaceHeader`'s existing "Refresh" button remains the only refresh control rendered on `staff-dashboard.tsx`.

## 2. Silent, pausable auto-refresh

- [x] 2.1 Add a `silent?: boolean` parameter to `loadDashboard` in `use-invitations-board.ts` that skips `setIsLoading`/`setErrorMessage` toggling but still updates state and still calls `toast.error` on failure.
- [x] 2.2 Add a ref that is `true` whenever any of `pendingDenyId`, `pendingRescheduleId`, `pendingDelegateId`, `denyingId`, `reschedulingId`, or `delegatingId` is set, and `false` otherwise.
- [x] 2.3 Add a `useEffect` that starts a 30-second `setInterval` calling `loadDashboard({ silent: true })` when that ref is `false` (no-op tick otherwise), clearing the interval on unmount.
- [x] 2.4 Verify manual `refresh()` is unaffected (still non-silent, still resets `isLoading`/`errorMessage` as today).

## 3. Purpose of Visit / Registration Type filters

- [x] 3.1 Add `purposeFilter` and `registrationTypeFilter` state (default "all") to `use-invitations-board.ts`, alongside `search`.
- [x] 3.2 Derive the distinct `purposeOfVisit` values present in `visitRequests` for the Purpose-of-Visit dropdown's options (plus an "All" option).
- [x] 3.3 Extend the `filteredRequests` memo to also require a match on `purposeFilter` (when not "all") and `registrationTypeFilter` (when not "all"), in addition to the existing search match.
- [x] 3.4 Return the new filter state, setters, and derived purpose options from `useInvitationsBoard`.
- [x] 3.5 In `SearchActionBar.tsx`, replace the inert "Filters" button with two `DropdownFilter` controls (Purpose of Visit, Registration Type — Individual/Group), following the existing pattern in `staff-audit-trail/Components/AuditFilterBar.tsx` / `DropdownFilter.tsx`. (Promoted `DropdownFilter` to `src/presentation/components/ui/DropdownFilter.tsx` so both `staff-dashboard` and `staff-audit-trail` can share it without a cross-feature import, per the architecture rule.)
- [x] 3.6 Wire the new filter props through `use-staff-dashboard.ts` and `staff-dashboard.tsx` into `SearchActionBar`. (`use-staff-dashboard.ts` already spreads the full board object, so only `staff-dashboard.tsx` needed updating.)
- [x] 3.7 Confirm `admin-invitations.tsx` (which also uses `useInvitationsBoard` but renders no Filters UI) still shows an unfiltered board — its new filter state stays at the "all" default since it never sets it.

## 4. Verification

- [x] 4.1 Manually exercise the staff dashboard: confirm exactly one Refresh button is visible and the "Filters" placeholder is replaced by working dropdowns. **Note**: `/staff/dashboard` requires a live SSO-issued session against the real dev backend (`VITE_API_BASE_URL=https://vmss-dev.mypits.org/api/v1` in `.env.local`) with no local credentials available in this environment, so the header/toolbar were instead verified by mounting the real `WorkspaceHeader` + `SearchActionBar` components in a temporary isolated preview route (not committed) against mock data via Playwright/Chromium — confirmed exactly one "Refresh" button, zero leftover "Filters" buttons, and both new dropdowns render (screenshot matched the intended design). The 30s auto-refresh interval and its pause-during-action behavior were verified by code review of `use-invitations-board.ts` (interval + ref logic) rather than live-observed, since that also requires an authenticated session; recommend a manual check post-deploy.
- [x] 4.2 Manually exercise filtering: same temporary preview harness confirmed selecting Purpose of Visit alone, Registration Type alone, and both together correctly narrow the mock list via AND logic; combining with an active search term further narrows correctly; clearing all filters restores the full list.
- [x] 4.3 Confirm `admin-invitations` board behavior is unchanged. Verified by code review: `admin-invitations.tsx` and `use-admin-invitations.ts` were not modified, and the new filter/auto-refresh fields added to `useInvitationsBoard`'s return value are additive (new state defaulting to "all"/unpaused) and simply unused by that page, so its existing single-fetch, manual-refresh, no-filter-UI behavior is unaffected. `tsc -b` and `oxlint` both pass across the full project.
