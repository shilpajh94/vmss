## Why

`declutter-visits-board` redesigned the invitation cards, and `/admin/invitations` already uses them because it shares the board component with `/staff/dashboard`. The admin page's own header bar was left as it was, so the two portals still look and behave differently above the board:

- Admin has a small pill-shaped search field. Staff has a full-width 40px one.
- Admin hides its filters behind a "Filters" toggle that opens a separate panel. Staff shows its filters inline.
- Admin can't filter by Purpose of Visit, which staff can.

The user asked for the admin side to match what was done in the staff portal.

## What Changes

- The admin Invitations page replaces its pill search and "Filters" toggle panel with the same inline search-and-filter bar the staff dashboard uses:
  - a 40px search field that takes the remaining width
  - icon dropdown filters at the same height
  - all controls on one row on wide screens, wrapping on narrow ones
- The admin bar adds the **Purpose of Visit** filter, which it didn't have. Its options come from the same list as the staff dashboard's.
- The admin bar keeps its admin-only **Status** and **Source** filters, now shown as inline dropdowns with "All statuses" and "All sources" defaults, next to Purpose and Registration Type. The board behaviour behind them is unchanged: a status filter still loads only that status's column.
- A "Clear filters" action appears inline whenever any filter differs from its default.
- **BREAKING (UX, minor)**: the "Filters" toggle button and its pop-open panel are removed from the admin page. Every filter is always visible instead.
- The staff dashboard looks the same as before. Its bar becomes a shared component that both pages render, so the two can't drift apart again.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `admin-invitations`: adds a requirement for the inline search-and-filter bar (Purpose, Registration Type, Status and Source filters, always visible, with Clear filters). What search matches on is unchanged.

## Impact

- `src/presentation/pages/staff-dashboard/Components/SearchActionBar.tsx` moves to `src/presentation/components/invitation-board/BoardFilterBar.tsx` and gains optional extra filters plus a Clear filters action. `staff-dashboard.tsx` imports it from the new location.
- `src/presentation/pages/admin-invitations/admin-invitations.tsx`:
  - drops the pill search, the `SlidersIcon` toggle, `isFilterPanelOpen` and the `SelectField` panel
  - renders `BoardFilterBar` with Purpose, Type, Status and Source
- `src/presentation/hooks/use-invitations-board.ts`: no changes expected. It already holds `purposeFilter`, `purposeOptions`, `statusFilter` and `sourceFilter` for both pages.
- Out of scope: the dashboard "Upcoming visitors" and "Recent check-ins" lists, and the visitor-facing pages. These are read-only lists without the cluttered-card problem, and the user's answer named the staff-portal design specifically. They can follow as a separate change.
- No API changes.
