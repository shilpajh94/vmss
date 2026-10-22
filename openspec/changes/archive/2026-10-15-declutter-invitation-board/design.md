## Context

See proposal.md (Why). The relevant current structure:

- `AppShell.tsx` owns the docked/drawer sidebar and provides
  `NavDrawerContext` (`isNavOpen`/`openNav`/`closeNav`). It renders whichever
  `sidebar` element the layout passes: `AdminSidebar` (280px),
  `DashboardSidebar` (staff, 260px), or `ReceptionSidebar` (280px). The three
  sidebars duplicate the same header/nav/footer markup. Each nav list is an
  `overflow-y-auto` scroll container.
- The sidebar wrapper div in `AppShell` carries `lg:translate-x-0`. In
  Tailwind v4 that emits the `translate` property, which makes the wrapper the
  containing block for any `position: fixed` descendant.
- `ResponsiveBoard.tsx` renders all columns in a
  `flex … gap-3 overflow-x-auto` row from `lg` up, and status tabs below
  `lg`. `KanbanColumn.tsx` is `flex-1 lg:min-w-[170px]`. Its root div carries
  the native HTML5 `onDragOver`/`onDrop` handlers. Its card list is the
  infinite-scroll area (`useInfiniteScrollSentinel`). Card data and paging
  state live in the page (`use-paged-board-columns`), not in the column.
- Both board pages (`staff-dashboard.tsx`, `admin-invitations.tsx`) call
  `<ResponsiveBoard columns renderColumn>`.
- Nothing in VMMS_WEB uses `localStorage` yet. The only tooltip is
  `IconActionButton`'s CSS tooltip (absolute, `group-hover`).
- Width math at `lg+` (padding `p-page-content` = 32px a side, 12px gaps,
  six columns): 1920px with a 280px sidebar gives ~252px per column. 1536px
  gives ~188px, and 1366px gives ~160px. So the 240px floor mostly bites on
  laptops, and collapsing the sidebar and one or two sparse columns is what
  removes the horizontal scroll there. Example: 1536px with the rail and one
  collapsed strip gives ~257px for each of five columns.

## Goals / Non-Goals

**Goals:**
- One collapse mechanism shared by all three sidebars, not three copies.
- One column-collapse mechanism shared by both boards, keyed per board.
- No first-paint flicker: stored state is applied on the initial render.
- Zero behaviour change below 1024px.

**Non-Goals:**
- Syncing layout preferences to the server or across devices.
- Animating column collapse beyond a simple width transition.
- Refactoring board data loading. Paging stays exactly as it is.

## Decisions

### 1. A small persisted-state hook, used for both preferences
Add `hooks/use-stored-state.ts`:
`useStoredState<T>(key, fallback, parse: (raw: unknown) => T | undefined)`.
It reads `localStorage` in the `useState` lazy initializer, so the value is
there on the first render and there's no flicker. It writes on change. Every
read and write is wrapped in `try/catch`, and an unparseable or invalid value
falls back. Keys are namespaced: `vmss:ui:sidebar-collapsed` and
`vmss:ui:board:<boardKey>:collapsed-columns`, where `boardKey` is `staff` or
`admin`. The column value is an array of status strings, filtered against
the board's known statuses on read, so a renamed or removed status is
ignored rather than throwing.

*Alternative:* a context-wide preferences store. That's overkill for two
values, and a hook keeps each preference local to its owner.

### 2. Sidebar collapse state lives in `AppShell`, exposed via context
`AppShell` owns `isSidebarCollapsed` (stored) and exposes
`{ isCollapsed, toggleCollapsed }` through a new `SidebarCollapseContext`,
next to `NavDrawerContext`. The context's `isCollapsed` is
`stored && isDesktop`, so a drawer below `lg` always gets the full sidebar,
and widening back re-applies the stored choice. The context default is
"expanded, no-op toggle", so a sidebar rendered outside the shell still
works. This mirrors how `NavDrawerContext` already works.

*Alternative:* each layout (`AdminLayout`, `StaffLayout`) owning the state.
The spec says the choice is shared between the shells, and `AppShell` is
the one component both already use.

### 3. Extract shared sidebar building blocks
Add `components/sidebar/` with `SidebarFrame` (the `<aside>`: width
`lg:w-[280px]`/`lg:w-[260px]` vs `lg:w-[72px]`, padding, a `transition-[width]
duration-200 motion-reduce:transition-none`), `SidebarHeader` (full logo or
`BrandLogo variant="mark"`, the drawer close button, and the
`lg:`-only collapse toggle with `aria-expanded` and `aria-controls` = the
drawer id), and `SidebarNavItem` (icon plus label, or icon only with
tooltip). The three sidebars keep their own `NAV_ITEMS`, routing, and footer
content, and compose these pieces. Footers render icon-only when collapsed:
the Help & Support icon, and the admin status dot. New icons
`PanelLeftCloseIcon`/`PanelLeftOpenIcon` (lucide paths) go in `icons.tsx`.

*Alternative:* add collapse conditionals inline in all three sidebars. That
triples the markup we already duplicate, and that duplication is how the
three would drift.

### 4. Rail tooltips render through a portal
The nav list scrolls (`overflow-y-auto`), so an absolutely positioned
tooltip like `IconActionButton`'s would be clipped at the rail's edge. A
`fixed` tooltip inside the sidebar is also unreliable, because the wrapper's
`translate` makes it the containing block (see Context). `SidebarNavItem`
therefore shows its label in a `createPortal(…, document.body)` element. The
element is positioned `fixed` from the button's `getBoundingClientRect()` on
`pointerenter`/`focus`, and hidden on `pointerleave`/`blur`, on scroll, and
on route change. The button's `aria-label` carries the name, so the tooltip
itself is `aria-hidden`.

*Alternative:* a `title` attribute. It doesn't show on keyboard focus, and
the spec requires that, matching the existing card icon-button convention.

### 5. Column collapse is owned by `ResponsiveBoard`
`ResponsiveBoard` gains a `boardKey` prop and owns the collapsed set
(Decision 1). `renderColumn` becomes `(column, { isCollapsed,
onToggleCollapse })`. The second argument is always "not collapsed" below
`lg`, so the tab layout ignores the stored desktop state. Both pages
forward these two values to `KanbanColumn`.

`KanbanColumn` keeps its root div, and with it the drag handlers and the
drag-over state, in both modes:
- **Expanded:** the existing header gains a small toggle button
  (`ChevronLeftIcon`, label "Collapse <label> column", `aria-expanded`).
  Sizing is `lg:min-w-[240px] lg:flex-1 lg:basis-0`, so expanded columns share
  space evenly and stop at 240px. The board's existing `overflow-x-auto`
  handles the overflow.
- **Collapsed:** the header and card list are replaced by a single
  full-height button. It is `lg:w-14 lg:flex-none`, with an accent left
  border, the count badge on top, and the label in `[writing-mode:vertical-rl]`.
  Its `aria-label` is "Expand <label> column, <total> visits". The drag-over
  ring applies to this strip. The infinite-scroll sentinel is unmounted with
  the list, and `enabled` is gated on `!isCollapsed`, so no pages load while
  collapsed.

Collapsing doesn't change the column's React `key`, and paging state lives
in the page, so expanding shows the already-loaded cards with no refetch.
Other columns aren't touched, so they keep their scroll positions.

*Alternative:* put collapse state in each page. Both pages would need
identical code, and `ResponsiveBoard` is already the shared desktop/mobile
switch.

### 6. No auto-collapse, no forced minimum of expanded columns
Columns change state only on user action (proposal Non-goals). Collapsing
all six is allowed. The strips then sit left-aligned, and the user can
expand any of them. Adding a "must keep one expanded" rule would only add
a confusing disabled state.

## Risks / Trade-offs

- [Native HTML5 drag-and-drop onto a 56px strip is a small target] →
  The strip is the column's full height, which is a larger target than many
  expanded-column drop zones. It also gets the same highlight on drag-over.
- [Horizontal scroll at 1366–1536px with everything expanded] → This is
  intentional per the spec, since truncation is the bug. Collapsing the rail
  or sparse columns removes it, and the choice persists, so users pay this
  once.
- [Sidebar width transition reflows the board each frame] → 200ms only,
  disabled under `prefers-reduced-motion`. The board has no measurement
  logic that depends on width.
- [`localStorage` blocked (private mode or policy)] → `try/catch` fallback
  to expanded, and toggling still works in memory for that page view
  (spec scenario).
- [Three sidebars refactored at once could regress drawer behaviour] →
  Drawer logic stays in `AppShell` and is untouched. QA covers the 800px
  drawer path for all three roles.

## Migration Plan

Frontend-only and additive. There are no stored values to migrate, because
missing keys mean "expanded". Rolling back the deploy just leaves inert keys
in `localStorage`.
