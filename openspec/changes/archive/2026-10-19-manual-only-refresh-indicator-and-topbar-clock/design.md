## Context

`AppTopBar.tsx`'s `RefreshControl` renders whatever the active page
publishes through `RefreshContext`:
- **Spinner:** it spins whenever `isRefreshing` is true.
- **Label:** it shows `Updated {relative time}` from `lastUpdatedAt`,
  re-rendered by a 30s "now" tick.
- **Background polls reach it:**
  - `use-live-dashboard` sets `isRefreshing` from every resource's
    `isLoading`, including polls.
  - `use-invitations-board` counts column reloads that polls trigger.
  - Every list hook sets `lastUpdatedAt` on every successful load,
    background ones included.

About 20 hooks pass `lastUpdatedAt` today, through `usePageRefresh` or
`useFormPageRefresh`, plus the shell fallback in `RefreshProvider`.

## Goals / Non-Goals

**Goals:**
- The spinner means "your refresh is running", and nothing else.
- No last-updated label, and no dead state left behind for it.
- A 1-second 24-hour clock that never shifts the layout.

**Non-Goals:**
- Changing what pages do on refresh, or how they poll.
- A timezone setting. The clock uses the device's local time.
- Changing the "Couldn't refresh · retrying" warning.

## Decisions

### 1. The control owns the "manual refresh in progress" state

`RefreshControl` keeps a local `isManualRefreshPending` flag:
- **On click:** it sets the flag, and starts the refresh (or the discard
  confirmation first, on a form).
- **Clearing:** it clears the flag once it has seen the page's
  `isRefreshing` go true and then false again after the click.
- **Safety stop:** a 15-second timeout clears it anyway, so a page whose
  refresh never reports progress can't leave the icon spinning forever.
- **Spinning:** the icon spins only while the flag is set.

Background polls still change `isRefreshing`, but with no click pending
the control ignores them.

*Alternative considered*: having every page's `refresh` return a
promise for the control to await. That means touching every hook's
`retry`, and several refreshes fan out to more than one load (the board
reloads every column), so "done" would have to be re-plumbed per page.
Watching the existing `isRefreshing` transition needs no page changes.
- *Edge case*: if the user clicks while a background poll is already in
  flight, `isRefreshing` is already true. The flag then clears when the
  combined loading settles, which is at worst slightly early, and the
  data is still fresh.

### 2. Remove `lastUpdatedAt` end to end

The field is dropped from `PageRefreshState`, from `usePageRefresh`'s
effect dependencies, from the shell fallback (`fallbackUpdatedAt`), and
from `useFormPageRefresh`. Each hook loses its `lastUpdatedAt` state and
its `setLastUpdatedAt(new Date())` calls. `use-live-dashboard` loses the
`oldestSuccess` memo, which only fed it. TypeScript's excess-property
check flags every remaining call site, so nothing is missed. The
control's 30s "now" tick goes too.
- *Alternative considered*: keeping the field and just not rendering it.
  That leaves 20 hooks maintaining state nobody reads.

### 3. `TopBarClock`: a self-contained, second-aligned ticker

A small `TopBarClock` component inside `AppTopBar.tsx`:
- **Timing:** it schedules its first update for the next whole second
  (`1000 - Date.now() % 1000` ms) and then every 1000 ms, so it stays in
  step with the device clock rather than drifting by when it mounted.
- **Formatting:** `getHours()`, `getMinutes()`, and `getSeconds()`, each
  padded to 2 digits. It doesn't use `toLocaleTimeString`, whose output
  varies by locale (12/24-hour, separators).
- **Markup:** `<time className="hidden md:inline tabular-nums …">`. The
  fixed-width digits mean ticks never shift the controls beside it. There
  is no `aria-live`, so screen readers aren't flooded once a second.
- **Scope:** only the clock re-renders each second, because the state
  lives in its own component, not in `AppTopBar`.

It sits immediately before `RefreshControl` in the top bar's right-hand
group.

### 4. A read discards feed responses that were in flight

Found while verifying this change. A feed refresh requested before a
"mark read" or "Mark all read" reached the server can resolve afterwards.
Its stale unread count then overwrites the optimistic update: the badge
jumps back to the old count, and the 30s reminder rings for notifications
that are already read.

The fix is in `NotificationCenterProvider`. It keeps a
`readVersionRef` that is bumped when a read starts and again when it
settles. `refresh` records the version when it starts and drops its
response if the version has changed by the time the response arrives.
The next poll, or the error-path refetch a failed read already does,
brings in anything newer.
- *Alternative considered*: always refetching after a read succeeds.
  That would cost an extra request per click, and still race with a poll
  that was already in flight.

## Risks / Trade-offs

- [The clock is wrong if the device clock is wrong] → it's acceptable,
  and it's what the user's own taskbar shows too.
- [The 15s safety timeout could end the spin while a very slow manual
  refresh is still running] → the data still arrives. Only the cue stops
  early, and 15s is well beyond the API's normal response times.
