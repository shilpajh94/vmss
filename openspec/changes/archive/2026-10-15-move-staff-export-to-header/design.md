## Context

See proposal.md for the motivation and `specs/staff-dashboard/spec.md` for
the behavior.

Relevant current state:

- **Admin.** `admin-invitations.tsx` renders Export in its own title row
  (`<h1>Invitations</h1>` plus the button, `justify-between`) above
  `BoardFilterBar`, and passes no `trailingAction`.
- **Staff.** `staff-dashboard.tsx` renders `WorkspaceHeader` (the "Visits"
  title on the left; Refresh, a divider, the bell, the avatar and Sign out
  on the right, `flex-wrap` on the outer row), then `BoardFilterBar` with
  `trailingAction={canExport ? <ExportInvitationsButton/> : undefined}`.
- **Who sees Export.** `canExport` (in `useInvitationsBoard`) is admin-only
  on the `'all'` scope and Reception-only on `'mine'`. This change doesn't
  touch it.
- **Narrow widths.** `WorkspaceHeader` already shrinks below `md`: Sign out
  hides its text and the name block hides. At 360px the right-hand group
  is roughly Refresh, bell, avatar and Sign out, with little spare width.

## Goals / Non-Goals

**Goals:**
- A staff filter bar laid out exactly like the admin bar.
- Export reachable in one click from the staff header at every width.

**Non-Goals:**
- Restyling "Clear filters", or changing what it resets.
- Unifying `WorkspaceHeader` with admin's `PageContentLayout` header.
- Removing `BoardFilterBar.trailingAction`. It's optional cleanup, left in
  place to keep the diff small.

## Decisions

### D1. `WorkspaceHeader` takes a `leadingAction?: ReactNode`, rendered first in the right-hand group
The staff page passes
`leadingAction={canExport ? <ExportInvitationsButton compact .../> : undefined}`.
Putting it before Refresh keeps the account controls (bell, avatar, Sign
out) at the far right, where they already are on every page.
- *Alternative:* a separate title row above the bar, like admin's
  (rejected: staff already has a header row with the title, and a second
  "Visits" row would duplicate it).
- *Alternative:* render Export after Sign out (rejected: it would split
  the account cluster).

### D2. `ExportInvitationsButton` gets an opt-in `compact` prop
With `compact`, the label is wrapped in `hidden md:inline`, and the button
gets `aria-label="Export"` and roughly 40×40 sizing below `md` (`px-2.5`).
The admin page doesn't pass it, so its button is unchanged.
- *Alternative:* always hide the label on narrow screens (rejected: that
  would change the admin page, which has room on its title row).

### D3. Reconcile the two pending deltas in planning artifacts, not in code
Both are VMMS_WEB openspec changes:
- `add-invitation-export/specs/staff-dashboard/spec.md`: change "last
  control in its search and filter bar" to the header placement, change
  its "Dialog opens with all statuses" scenario to the active-status
  preselection, and change the in-bar wrap scenario to the header
  behavior.
- `align-staff-board-filters-with-admin/specs/staff-dashboard/spec.md`:
  drop Export from "The workspace header and search bar are compact" and
  its 1024px scenario.

Otherwise, archiving them in any order would write contradictory
requirements into the main `staff-dashboard` spec.

## Risks / Trade-offs

- **360px header crowding.** With Export added, Refresh, Export, bell,
  avatar and Sign out must fit in about 328px. → Compact Export is about
  40px. If it still doesn't fit, the outer row's existing `flex-wrap` moves
  the whole right-hand group under the title rather than clipping. The
  360px scenario checks for no horizontal scroll.
- **Discoverability.** Export moves away from the filters it reflects. →
  Admin has worked this way since `add-invitation-export`, and the dialog
  still lists the applied filters.
