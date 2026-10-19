## Context

- **`usePolling`** (`hooks/use-polling.ts`) runs a page's silent
  `fetchSilently` on an interval:
  - it skips a tick while `isBusy` (a mutation or dialog is open) or while
    the tab is hidden
  - it re-fetches on `visibilitychange`/`focus`, throttled to once per 5s
  - every caller passes `15_000`: the 12 admin list/board hooks,
    `use-invitations-board`, and `use-live-dashboard` (which uses its own
    `POLL_INTERVAL_MS`)
- **`RefreshProvider` / `usePageRefresh`** (`context/refresh-context.tsx`):
  a page publishes `{ refresh, isRefreshing, lastUpdatedAt, hasFailed }`,
  and `AppTopBar`'s `RefreshControl` renders only when a page has
  registered. Unregistered today:
  - the Reception Desks and Security Gates placeholders
  - the Audit Trail
  - the 10 admin create/edit form pages
  - the Register Visitor wizard

  Organisation Configs registers but doesn't poll.
- **Form state:** there is no shared unsaved-changes tracking. Each form
  hook holds its own values.
- **`NotificationBell`:** rings on `newArrivalCount` changes by remounting
  a keyed `<span>` with the `motion-bell-ring` class (from
  `show-exact-unread-count-and-ring-bell`).

## Goals / Non-Goals

**Goals:**
- One interval constant, so the 10s value lives in one place.
- The top-bar refresh control is never absent on an admin or staff page.
- Forms are protected: no auto-refresh, and a confirmed manual refresh
  when there are unsaved changes.
- A reminder ring driven by the same keyed-remount mechanism.

**Non-Goals:**
- Server push (WebSocket/SSE), or any API change.
- Changing the bell's 60s feed poll.
- A navigation-away "unsaved changes" guard. This change only guards the
  refresh button.

## Decisions

### 1. `LIVE_REFRESH_INTERVAL_MS = 10_000`, exported from `use-polling.ts`

Every `usePolling` caller passes this constant instead of a literal, and
`use-live-dashboard` drops its local `POLL_INTERVAL_MS`. The Audit Trail
hook adds `usePolling(() => load('background'), { intervalMs, isBusy })`,
where `isBusy` covers a report download in progress. It also adds
`usePageRefresh`, so its filters and page are kept, because the load
already reads them from state. That needs a `'background'` load mode,
which `useLoadTracker` already provides. The Form Builder and its step
editor keep polling: they are list-style management pages whose edits
happen in dialogs, which `isBusy` already guards.
*Alternative considered*: making the interval a `usePolling` default. An
explicit constant keeps each call site readable, and still gives one
place to change it.

### 2. Shell fallback refresh in `RefreshProvider`

`RefreshProvider` gets a `fallback: PageRefreshState` built from
`useNotificationCenter().refresh`. It has its own `isRefreshing` and
`lastUpdatedAt`, tracked in the provider. `AppTopBar` renders
`activeRefresh ?? fallback`, so the control always shows. A page that
registers still overrides the fallback, exactly as today. This makes
the placeholders, and any future page that forgets to register,
correct by default.
- This requires `RefreshProvider` to sit inside
  `NotificationCenterProvider`. The tasks include checking the provider
  order in `App.tsx`.

### 3. Forms register with `hasUnsavedChanges`, and the top bar confirms

`PageRefreshState` gains an optional `hasUnsavedChanges?: boolean`.
`RefreshControl` behaves as follows:
- **No unsaved changes:** it calls `refresh()` at once.
- **Unsaved changes:** it opens a `ConfirmDialog`, titled "Discard
  unsaved changes?", with the confirm button "Discard and refresh"
  (`tone="danger"`), and calls `refresh()` only on confirm.

Each form hook registers
`usePageRefresh({ refresh: reload, isRefreshing, lastUpdatedAt, hasUnsavedChanges })`,
where `reload`:
- on an edit page, re-fetches the record (and any reference lists it
  loads) and resets the form values to it
- on a create page, re-fetches its reference lists and resets the form to
  its initial values

`hasUnsavedChanges` comes from a small shared helper,
`useUnsavedChanges(initial, current)`: a JSON comparison of the loaded or
initial values against the current ones. That fits these forms, whose
values are plain serialisable objects. The Register Visitor wizard counts
any entered field on any step as unsaved, and resets to step 1.
Organisation Configs already registers; it adds `hasUnsavedChanges` and
keeps no polling.
- *Alternative considered*: a page-local refresh button on forms. The
  existing spec requires the one shared top-bar control, so the
  confirmation lives there and is shared by all forms.

### 4. Reminder ring: a 30s timer that bumps a local ring key

`NotificationBell` replaces "key = `newArrivalCount`" with a local
`ringKey` state that both triggers increment:
- An effect on `newArrivalCount > 0` changes bumps `ringKey`. This keeps
  today's behaviour.
- A timer effect, dependent on `ringKey`, `unreadCount`, `isOpen`, and
  visibility, schedules a single `setTimeout(30_000)` while
  `unreadCount > 0 && !isOpen`. When it fires, it bumps `ringKey` if the
  tab is visible.

Because the timer is re-armed on every `ringKey` change, a new-arrival
ring restarts the 30s wait. When the count drops to 0 or the popover
opens, the cleanup clears it. A `visibilitychange` listener re-arms the
timer when the tab becomes visible again, so a background tab gets no
backlog of rings. Reduced motion is already handled by the global CSS
rule. The constant is `UNREAD_REMINDER_INTERVAL_MS = 30_000`.

## Risks / Trade-offs

- [API load: each open tab polls 1.5× as often] → hidden tabs don't
  poll, authenticated endpoints aren't rate-limited, and dashboards
  already batch their requests per tick. Watch for it in the QA load run
  (`loadtests/`).
- [A JSON-comparison dirty check calls a form "dirty" after the user
  types and then reverts the same value] → it doesn't: a revert compares
  equal again. A field the form normalises (trimming, for example) could
  give false positives, but the worst outcome is an extra confirmation.
- [A repeating ring every 30s could annoy someone leaving notifications
  unread on purpose] → it's the behaviour requested. Reading them, or
  "Mark all read", stops it. If it proves noisy, a later change could add
  a user setting.
