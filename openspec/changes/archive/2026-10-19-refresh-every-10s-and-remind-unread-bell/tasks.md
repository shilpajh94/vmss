## 1. 10-second interval

- [x] 1.1 Export `LIVE_REFRESH_INTERVAL_MS = 10_000` from
  `src/presentation/hooks/use-polling.ts`.
- [x] 1.2 Replace every `intervalMs: 15_000` with the constant (13 call
  sites), and replace `use-live-dashboard.ts`'s local
  `POLL_INTERVAL_MS`.
- [x] 1.3 Audit Trail (`use-admin-audit-trail.ts`):
  - add `'background'` load support (no toast, no cue on a failed
    background load)
  - add `usePolling` with `isBusy` while a report is downloading
  - add `usePageRefresh`, keeping the current filters and page

## 2. Shared refresh control

- [x] 2.1 `refresh-context.tsx`:
  - add optional `hasUnsavedChanges` to `PageRefreshState`
  - give `RefreshProvider` a shell fallback that refreshes the
    notification feed, tracking its own `isRefreshing`/`lastUpdatedAt`
  - expose `activeRefresh ?? fallback`
- [x] 2.2 `AppTopBar.tsx` `RefreshControl`:
  - always render
  - when `hasUnsavedChanges` is set, open a `ConfirmDialog` ("Discard
    unsaved changes?" / "Discard and refresh") before calling `refresh`
- [x] 2.3 Add a `useUnsavedChanges(initial, current)` helper (JSON
  comparison) under `src/presentation/hooks/`.

## 3. Forms register a confirmed refresh

- [x] 3.1 Admin edit/create forms: Branch (create), Building, Department,
  Floor, Host Employee, Kiosk, Visitor Category, Workflow, Role (create),
  and Role permissions.
  - each registers `usePageRefresh` with a `reload` that re-fetches its
    record or reference data and resets the form
  - each reports `hasUnsavedChanges`
  - none polls
- [x] 3.2 Organisation Configs: add `hasUnsavedChanges` to its existing
  registration, and make sure a confirmed refresh resets the form to the
  re-fetched values.
- [x] 3.3 Register Visitor wizard (`StaffVisitorRegistrationPage`):
  - register a refresh that reloads the wizard's reference data and
    resets it to step 1
  - any entered field counts as unsaved

## 4. Reminder ring

- [x] 4.1 In `NotificationBell.tsx`:
  - move the ring trigger to a local `ringKey`, bumped on each
    `newArrivalCount` change
  - add a 30s reminder timeout (`UNREAD_REMINDER_INTERVAL_MS`), re-armed
    on each `ringKey` change, while `unreadCount > 0`, the popover is
    closed, and the tab is visible
  - re-arm it on `visibilitychange`
  - cleared when any of those conditions stops holding

## 5. Verification

- [x] 5.1 Run `npm run build` and `npm run lint`. Do not run prettier.
- [x] 5.2 Extend `e2e/test_notification_bell.py`:
  - with unread notifications, the bell gets a fresh ring roughly every
    30s, observed by a remounted icon wrapper
  - after "Mark all read", no further ring comes within 35s
- [x] 5.3 Add `e2e/test_live_refresh.py`:
  - on the Branches list, a branch created through the API appears
    within about 12s with no user action
  - the top-bar refresh control is present on Reception Desks, Security
    Gates, New Branch, Edit Department, the Audit Trail, and Register
    Visitor
  - on Edit Department, typing then refreshing shows the discard
    confirmation: cancel keeps the typed value, and confirm restores the
    saved one
- [x] 5.4 Check in the browser network tab that list pages poll every
  ~10s, nothing polls while the tab is hidden, and form pages never poll.
- [x] 5.5 Run `npm run e2e` (full suite), not at the same time as API
  pytest.
