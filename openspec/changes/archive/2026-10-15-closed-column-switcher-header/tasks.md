## 1. Switcher as the column header

- [x] 1.1 In `ClosedStatusesColumn.tsx`, delete the "Closed" header element,
      `grandTotal`, and the fixed `headerAccent`; change the column wrapper's
      `gap-2` to `gap-3` to match `KanbanColumn` — design.md Decision 3.
- [x] 1.2 Restyle the tablist as the header box: `h-10 rounded-[10px]
      border-l-4 p-[3px] gap-[3px]`, with the border and tint taken from the
      selected status's `ACCENT_CLASSES` — Decisions 1–2.
- [x] 1.3 Compress segments to fit 40px: `flex-auto min-w-0 py-1`, label and
      count both 11px with `leading-[13px]` (label semibold, count bold);
      selected = `bg-surface shadow-sm` with `text-text` label and accent
      count, unselected = `text-text-muted` with hover wash. Keep
      `role="tab"`, `aria-selected`, `aria-controls`, and the
      "<label>, <count>" accessible name.
- [x] 1.4 Update the component's leading comment to describe the switcher as
      the header (no title row).

## 2. Verification

- [x] 2.1 `npm run lint`, `npx tsc -b`, and `npm run build` clean.
- [x] 2.2 Playwright at 1280, 1366, and 1536px, sidebar expanded and
      collapsed: switcher header height equals the other headers' (40px);
      first card top is equal across all four columns; no "Closed" text in
      the column; no label truncated (`scrollWidth <= clientWidth`).
- [x] 2.3 Re-run the `group-closed-board-statuses` Closed-column QA suite
      (selection, no refetch on switch, filter focus, persistence, admin
      independence, mobile tabs, blocked storage) — all green.
- [x] 2.4 Screenshot each selected state (Checked-out, Denied, Archived) to
      confirm the header accent follows the selection.
- [x] 2.5 Archive order when done: `declutter-invitation-board`, then
      `group-closed-board-statuses`, then this change; run
      `openspec validate closed-column-switcher-header --strict` after the
      second.
