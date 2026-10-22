## Why

The top-bar refresh button is meant for manual refresh, but it also
reacts to the automatic 10-second background refresh:
- **Spinning:** its icon spins on every background poll on the dashboards
  and the invitation boards.
- **"Updated …" label:** the label beside it resets to "Updated just now"
  every 10 seconds on every page.

So the button looks busy when nobody pressed it, and the label carries no
information. Separately, staff and admins have asked for the current time
in the top bar.

## What Changes

- **Spinner:** the refresh icon spins only for a refresh the user started,
  from the click until that refresh finishes. Background polls no longer
  move it.
- **Label:** the "Updated just now / Updated 2m ago" label is removed from
  the top bar on every admin and staff page. The "Couldn't refresh ·
  retrying" warning stays, because it tells the user the page may be
  stale.
- **Clock:** the admin and staff top bars show a live clock in 24-hour
  `HH:MM:SS` format (for example `14:05:09`), in the device's local time.
  It ticks every second and sits beside the refresh button, from tablet
  width (768px) up. It is hidden on phones so the top bar stays one row.
- **Clean-up:** pages stop tracking a last-updated time, since nothing
  displays it any more.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `live-data-refresh`: "A manual refresh control remains available
  alongside automatic refresh". The control spins only for user-started
  refreshes, and shows no last-updated time.
- `staff-dashboard`: "Refresh reloads the visit-requests list" no longer
  shows an "Updated …" time.
- `app-shell`: "Top bar compacts on small screens" hides the clock on
  phones instead of the removed label. A new requirement adds the live
  clock.

## Impact

- **Code**:
  - `src/presentation/components/AppTopBar.tsx`: the refresh control's
    spin logic, the removed label, and the new clock component.
  - `src/presentation/context/refresh-context.tsx`: `lastUpdatedAt`
    removed from `PageRefreshState` and from the shell fallback.
  - Every page hook that passed `lastUpdatedAt`, about 20, drops it, plus
    the state that only existed to feed it.
  - `src/presentation/hooks/use-form-page-refresh.ts`: same.
- **Tests**: e2e coverage for the clock, the label's absence, and the
  icon staying still during a background refresh.
- **API**: no change.
