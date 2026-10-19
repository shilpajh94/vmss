## Why

Two gaps remain in how the admin and staff portals stay current.

**Auto-refresh.** Operational pages re-fetch every 15 seconds, which is
slow for a front desk watching arrivals. Several pages don't refresh at
all and have no refresh button:
- the Audit Trail
- the Reception Desks and Security Gates placeholders
- every create/edit form, and the Register Visitor wizard

**Unread notifications.** The bell rings only once, when a notification
first arrives. Once that moment passes, a staff member who glanced away
has no further cue that something is still unread.

## What Changes

- **Faster auto-refresh:** every list, board, and dashboard page on the
  admin and staff portals re-fetches every 10 seconds instead of 15. Like
  today, it's a silent background fetch from the API: data updates in
  place, with no reload, spinner, or lost scroll position. The Audit Trail
  joins this set.
- **A refresh button on every page:** every admin and staff page shows the
  shared top-bar refresh button. Pages with no data of their own (the
  Reception Desks and Security Gates placeholders) get a button that
  refreshes the shell's shared data, i.e. the notification feed.
- **Forms never auto-refresh:** this covers create/edit form pages,
  Organisation Configs, and the Register Visitor wizard, so a user's
  typing is never overwritten. Their top-bar button reloads the page's
  data. If the user has unsaved changes, it first asks them to confirm
  discarding those changes.
- **Repeating reminder ring:** while at least one notification is unread
  and the tab is visible, the bell rings again every 30 seconds. It stops
  as soon as everything is read. A new-arrival ring restarts the 30-second
  timer, and the reminder doesn't ring while the notification popover is
  open. Reduced-motion users get no movement.
- **Out of scope:** the bell's own feed poll stays at 60 seconds, and
  nothing changes in the API. "Auto refresh on the backend" means a
  background fetch, not server push.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `live-data-refresh`: all three requirements change.
  - The automatic interval becomes 10 seconds and covers the Audit Trail.
  - Form and wizard pages are excluded from auto-refresh.
  - The manual refresh button is required on every admin and staff page,
    with a discard confirmation on forms that have unsaved changes and a
    shell-level refresh on pages without data.
- `async-ui-states`: "Re-fetching keeps existing content visible" names
  the 10-second background poll instead of the 15-second one.
- `app-shell`: adds a 30-second reminder ring while notifications are
  unread.

## Impact

- **Polling interval:** one shared constant in `use-polling.ts`, used by
  every `usePolling` caller (13 list/board hooks, plus
  `use-live-dashboard.ts`, which drives the admin, staff, and reception
  dashboards).
- **Refresh registration:** `refresh-context.tsx` gains
  `hasUnsavedChanges` and a shell-level fallback. `AppTopBar.tsx` always
  renders the control, and asks for confirmation through `ConfirmDialog`.
- **Forms:** the 10 admin create/edit form pages, Organisation Configs,
  and the Register Visitor wizard each register a refresh, and report
  whether they have unsaved changes.
- **Audit Trail:** `use-admin-audit-trail.ts` adds polling and refresh
  registration.
- **Bell:** `NotificationBell.tsx` gains the reminder timer.
- **API load:** each open admin/staff tab makes 1.5× as many list
  requests. Authenticated endpoints aren't rate-limited (only login and
  public endpoints are), and polling already stops while a tab is hidden.
