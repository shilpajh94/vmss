## Why

Staff and admins can't see the paging controls or the last rows of
data on several pages. A browser check on 2026-10-20 (admin login,
1280×720 and 1440×900) found three causes:

- **List pages hide their pagination.** On the paged admin lists, the
  `Showing 1-20 of N` footer and its Previous/Next buttons sit inside the
  scrolling data region, after the last table row. On a 900px-tall window
  the footer is about 1650px down, so it can't be seen until the user
  scrolls the table to the end. The table's bottom edge is also cut off at
  the window, so the list looks unfinished.
- **The week board overflows short screens.** The board has a 420px
  minimum height. At 1280×720 (and similar laptops, such as 1366×768),
  less than 420px is left under the toolbar. The board runs past the
  bottom of the window, so each column's last visits and its
  `All N visits` footer are cut off. The page also scrolls a little,
  which breaks the "board fits the page" design.
- **Day view scrolls the whole page.** A busy day makes the page
  1600–2300px taller than the window. The title, toolbar and view
  switcher scroll away, and the `Showing X of Y` progress line is only
  reached at the very bottom.

## What Changes

- **Pagination is pinned below the data on paged list pages.**
  - From `lg` up, the pagination footer sits outside the scrolling data
    region, directly under it. It is always visible, and only the rows
    scroll.
  - This covers every page that uses the shared `Pagination` control
    (branches, buildings, floors, departments, roles, employees, visitor
    categories, kiosks, devices, audit trail) and the workflows list's
    own footer.
  - The table's rounded bottom edge stays visible above the footer.
  - Below `lg` the whole page still scrolls, and the footer stays after
    the last row.
- **The week board always fits the window from `lg` up.**
  - The board's height floor drops from 420px to 240px, so it fits a
    720px-tall window without the page scrolling.
  - On a window too short even for that, the page scrolls and keeps its
    bottom gap, so the board's bottom edge can still be reached.
- **Day view gets its own scrolling panel.**
  - From `lg` up, Day view fills the page height like Week view. The
    title, toolbar and view switcher stay in place, and only the day's
    timeline scrolls inside its card.
  - The card has a fixed header row: the day's date and a visit count.
    It also has a fixed footer row with the `Showing X of Y` /
    `All N visits` / loading / retry status.
  - Sticky hour headings keep working inside the card.
  - Loading more visits is triggered by scrolling the card, not the page.
  - Below `lg` Day view keeps scrolling with the page, as it does today.
- **Week columns show their paging status in a fixed column footer**,
  not at the end of each column's scroll. A column's `Showing X of Y` or
  `All N visits` line is visible without scrolling the column.
- Month view, the invitation boards and the API are unchanged.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `responsive-layout`: adds a requirement that paged list pages keep
  their pagination footer visible below the scrolling data from `lg` up.
- `staff-calendar`:
  - adds a requirement that Day view scrolls its timeline inside its own
    panel from `lg` up;
  - adds a requirement that each day's paging status (Week columns and
    Day view) stays in a fixed footer;
  - adds a requirement that the Week board fits short desktop windows.

## Impact

- **Shared layout:**
  - `components/PageContentLayout.tsx`: the existing `footer` slot is
    used for pagination. A new opt-in `fitBody` prop keeps the footer
    directly under short lists.
  - `components/Pagination.tsx`: an optional `itemLabel` prop, so the
    workflows list can use the shared control.
- **List pages** (move `<Pagination>` from the body to `footer`):
  - `admin-branches`, `admin-buildings`, `admin-floors`,
    `admin-departments`, `admin-roles`, `admin-host-employees`,
    `admin-visitor-categories`, `admin-kiosks`, `admin-devices`,
    `admin-audit-trail`.
  - `admin-workflows` (its footer is moved out of `WorkflowListTable`).
- **Calendar:**
  - `calendar-page.tsx`: fill-height for Day view as well as Week.
  - `DayAgenda.tsx`: fixed header, scrolling body, fixed footer.
  - `PagedDayList.tsx`: the status row moves out of the scrolled list
    into a footer the parent places. The sentinel stays in the list.
  - `WeekBoard.tsx`: column footer and the lower height floor.
- **Tests:**
  - `e2e/test_responsive_matrix.py`: pagination is visible without
    scrolling on paged lists at 1280×720 and 1440×900.
  - `e2e/test_staff_calendar.py`: Day view panel scrolling, fixed
    footers, and the week board fitting a 1280×720 window.
- **API and dependencies:** none.
- **Sequencing:** builds on `fix-page-bottom-gap-and-full-day-calendar`
  and `calendar-working-hours-and-roomier-week`. Both are implemented
  but not archived. This change only adds requirements, so it doesn't
  conflict with their spec deltas.
