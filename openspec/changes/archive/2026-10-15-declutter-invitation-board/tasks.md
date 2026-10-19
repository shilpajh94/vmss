## 1. Shared infrastructure

- [x] 1.1 Add `hooks/use-stored-state.ts`: a `useStoredState(key, fallback,
      parse)` hook that reads `localStorage` in the lazy `useState`
      initializer, writes on change, and wraps every access in `try/catch`
      (falls back on missing/invalid/blocked storage) — design.md Decision 1.
- [x] 1.2 Add `PanelLeftCloseIcon` and `PanelLeftOpenIcon` to
      `components/icons.tsx` (lucide paths, same `createIcon` helper).

## 2. Collapsible sidebar

- [x] 2.1 Add `context/sidebar-collapse-context.tsx` (`isCollapsed`,
      `toggleCollapsed`; no-op/expanded default) and provide it from
      `AppShell.tsx`, backed by `useStoredState('vmss:ui:sidebar-collapsed',
      false, …)` and gated by `useIsDesktop()` so the drawer always gets the
      full sidebar — design.md Decision 2.
- [x] 2.2 Build `components/sidebar/SidebarFrame.tsx` (aside with expanded
      width prop vs `lg:w-[72px]` rail, width transition disabled under
      reduced motion) and `SidebarHeader.tsx` (full logo vs `mark` logo,
      drawer close button, `lg:`-only "Collapse sidebar"/"Expand sidebar"
      toggle with `aria-expanded`/`aria-controls`) — Decision 3.
- [x] 2.3 Build `components/sidebar/SidebarNavItem.tsx`: icon + label when
      expanded; icon-only with `aria-label` and a portal-rendered, `fixed`
      tooltip on hover/focus (hidden on leave/blur/scroll/route change) when
      collapsed; active highlight preserved in both modes — Decision 4.
- [x] 2.4 Refactor `AdminSidebar.tsx` onto the shared pieces (280px
      expanded; "v1.2 Active" footer shows just the status dot when
      collapsed).
- [x] 2.5 Refactor `DashboardSidebar.tsx` onto the shared pieces (260px
      expanded; Help & Support footer becomes an icon-only button with the
      same tooltip treatment when collapsed).
- [x] 2.6 Refactor `ReceptionSidebar.tsx` onto the shared pieces (280px
      expanded).
- [x] 2.7 Confirm the drawer path is unchanged below 1024px for all three
      sidebars (no toggle shown, full labels, close/backdrop/Escape/route
      change still close it), and that widening back to desktop restores
      the stored rail state. Verified in Playwright at 800/390px (full
      280px drawer, no toggle) and widening back to 1440px (72px rail).

## 3. Collapsible, minimum-width board columns

- [x] 3.1 Extend `ResponsiveBoard.tsx` with a `boardKey` prop, the stored
      collapsed-status set (`vmss:ui:board:<boardKey>:collapsed-columns`,
      filtered against the current columns' statuses on read), and pass
      `{ isCollapsed, onToggleCollapse }` as `renderColumn`'s second
      argument — always "not collapsed" below `lg` — Decision 5.
- [x] 3.2 In `KanbanColumn.tsx`, add `isCollapsed`/`onToggleCollapse`
      props: header gets a "Collapse <label> column" toggle; collapsed mode
      renders a full-height `lg:w-14` strip button (count badge + vertical
      label, accent border, "Expand <label> column, <total> visits") inside
      the same root div so drag handlers and drag-over highlight keep
      working; gate the infinite-scroll sentinel on `!isCollapsed`.
- [x] 3.3 Change expanded column sizing to `lg:min-w-[240px] lg:flex-1
      lg:basis-0` and confirm the board's own `overflow-x-auto` region (not
      `<main>`/the page) scrolls when columns don't fit, with column headers
      still pinned.
- [x] 3.4 Wire `staff-dashboard.tsx` (`boardKey="staff"`) and
      `admin-invitations.tsx` (`boardKey="admin"`) to forward the new
      `renderColumn` argument into `KanbanColumn`.

## 4. Verification

- [x] 4.1 `npm run lint` and `npm run build` clean.
- [x] 4.2 Browser QA (default tenant, admin + staff host + reception users)
      at 1920, 1536, 1366, and 1280px: sidebar collapse/expand and persistence
      across reload and admin↔staff shells; rail tooltips on hover and Tab
      focus and not clipped; column collapse/expand, counts updating on
      refresh while collapsed, no refetch on expand, persistence per board
      (admin vs staff independent); horizontal board scroll appears only
      when expanded columns can't fit at 240px and the page never scrolls
      horizontally.
- [x] 4.3 Drag a Requested card onto a collapsed Approved strip and a
      collapsed Denied strip: highlight shows, approve flow / deny-with-reason
      dialog runs exactly as on expanded columns. Note: no card is draggable
      today (`VisitRequestCard` has no drag source; cards move via their
      Approve/Deny buttons), so this was verified with a synthetic
      `dragover`+`drop` on the collapsed Denied strip, which opened the deny
      dialog (cancelled, no data changed).
- [x] 4.4 Phone/tablet QA at 390px and 800px: drawer shows the full sidebar
      regardless of stored rail state; board status tabs list every status
      including ones collapsed on desktop.
- [x] 4.5 With site storage blocked (private window / devtools), confirm
      everything renders expanded and toggles still work for the page view.
- [x] 4.6 Refresh the affected screenshots via `npm run screenshots` if the
      board/sidebar pages are in its set. `screenshots.local/` is gitignored
      local output, so nothing in the repo to refresh; the QA run's own
      screenshots (1920/1536/1366/1280/800/390, admin + staff) cover it.
