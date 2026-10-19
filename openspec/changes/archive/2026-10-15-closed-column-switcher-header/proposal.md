## Why

The Closed column added by `group-closed-board-statuses` stacks two rows:
a "Closed" title with a combined count, and then the Checked-out / Denied /
Archived switcher. The title doesn't help anyone. Users think in the three
statuses, not in "Closed". The combined count (33) mixes check-outs,
denials, and no-shows into one number nobody acts on. The title row also
costs vertical space and adds a heading the other columns don't have.

## What Changes

- Remove the "Closed" title row and its combined total from the desktop
  Closed column.
- The Checked-out / Denied / Archived switcher becomes the column's header,
  in the same place as the other columns' headers. It keeps the
  label-over-count segments, each with its own count, and is styled like a
  column header: rounded, tinted, with a left accent border in the selected
  status's colour.
- The switcher header is the same height as the other column headers
  (40px), so the first card in all four columns starts at the same height.
  Measured in-app: label and count on a single row needs about 250px before
  padding, which doesn't fit the 240–246px columns at 1366px with the full
  sidebar. A compact stacked layout fits both the width and the height.
- Nothing else changes: grouping, selection, the remembered choice, status
  filter behaviour, paging, the phone/tablet tabs, and the admin board
  (which shares the same component).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `staff-dashboard`: "Closed statuses share one column on desktop" drops
  the "Closed" title and combined total. The switcher becomes the column
  header at the same height as the other headers.

## Impact

- **Code (VMMS_WEB):** `invitation-board/ClosedStatusesColumn.tsx` only.
  The admin board picks this up automatically, since its requirement points
  to the staff one.
- **Ordering:** this modifies a requirement that `group-closed-board-statuses`
  adds, which itself depends on `declutter-invitation-board`. Archive order:
  `declutter-invitation-board`, then `group-closed-board-statuses`, then
  this change.
- **API / dependencies:** none.
- **Verification:** lint, typecheck, and build; Playwright QA re-run of the
  Closed-column checks plus header-height alignment at 1280, 1366, and
  1536px.
