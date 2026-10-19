## 1. Manual-only spinner

- [x] 1.1 In `AppTopBar.tsx` `RefreshControl`:
  - add `isManualRefreshPending`, set on click (including after a
    confirmed discard)
  - clear it on the page's `isRefreshing` going true then false after
    the click, or after a 15s safety timeout
  - spin the icon only while it is set (design.md Decision 1)
- [x] 1.2 Remove the "Updated …" label, `formatRelativeTime`, and the 30s
  "now" tick. Keep the "Couldn't refresh · retrying" warning.

## 2. Drop `lastUpdatedAt`

- [x] 2.1 `refresh-context.tsx`: remove `lastUpdatedAt` from
  `PageRefreshState`, `usePageRefresh`, and the shell fallback's state.
- [x] 2.2 Remove `lastUpdatedAt` state and setters from every hook that
  passed it, using `tsc` errors as the checklist. That includes the list
  hooks, `use-live-dashboard.ts` (and its `oldestSuccess` memo),
  `use-invitations-board.ts`/staff and admin invitations, Organisation
  Configs, the Audit Trail, and `use-form-page-refresh.ts`.

## 3. Clock

- [x] 3.1 Add `TopBarClock` to `AppTopBar.tsx`:
  - 24-hour `HH:MM:SS` built from padded `getHours`/`getMinutes`/
    `getSeconds`
  - first tick aligned to the next whole second, then every 1000 ms
  - `hidden md:inline tabular-nums`, with no `aria-live`
  - placed before the refresh control

## 3a. Notification read race (found during verification)

- [x] 3a.1 In `notification-center-context.tsx`, discard a feed refresh
  response if a mark-read or mark-all-read started or finished after that
  refresh was requested. Otherwise a stale poll overwrites the optimistic
  zero, and the bell keeps reminding about notifications that were
  already read (design.md Decision 4).

## 4. Verification

- [x] 4.1 Run `npm run build` and `npm run lint`. Do not run prettier.
- [x] 4.2 Add e2e coverage (`e2e/test_live_refresh.py`):
  - the top bar shows `HH:MM:SS` matching the browser's local time
    within 2s, and it advances
  - no "Updated" text is in the top bar
  - the refresh icon has no `animate-spin` across a background poll on
    the admin Dashboard
  - it does spin after a click, and stops afterwards
  - at 360px the clock is hidden and the top bar doesn't wrap
- [x] 4.3 Run the full `npm run e2e` suite, not at the same time as API
  pytest.
