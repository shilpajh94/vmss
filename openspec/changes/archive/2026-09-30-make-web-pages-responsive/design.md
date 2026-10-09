## Context

- The stack is React 19, react-router 8, Tailwind v4 (`@tailwindcss/vite`,
  tokens in `src/styles/theme.css` via `@theme`/`@utility`), and
  `@dnd-kit` for form-builder reordering. There is no unit/e2e test
  runner, and verification today is manual plus `tsc -b` + `oxlint`.
- `AppShell` = `h-screen` flex row: `{sidebar}` plus a column holding
  `{topBar}` and a scrolling `<main>`. The sidebars are `<aside
  class="w-[280px] shrink-0">`. `AdminLayout`/`StaffLayout` pass the
  sidebar and top bar in. `reception-dashboard.tsx` builds its own
  `min-h-screen` row with `ReceptionSidebar` + `ReceptionTopBar` instead
  of using `AppShell`.
- `index.html` already has the `width=device-width` viewport meta.
- Pattern inventory: 9 admin forms wrap content in `w-[1160px]`, 11 list
  pages use a hand-built `<table>`, ~30 fixed `grid-cols-N` sites, and 3
  sidebar variants. `ui/Modal` is already `max-h-[90vh] w-full
  max-w-*`, so it is close to what's needed. The staff board is
  `flex gap-4 overflow-x-auto` of `KanbanColumn flex-1`.

## Goals / Non-Goals

**Goals:**
- Fix it at the shared-component level first, so pages pick up most of the
  behavior automatically, and keep per-page edits to class changes.
- Mobile-first Tailwind classes (`base` = phone, then `sm:`/`md:`/`lg:`).
  Desktop (`lg:`) output stays pixel-equivalent to today.

**Non-Goals:**
- Visual redesign, new colors, or new components beyond the drawer, board
  status selector, and wizard progress header.
- A card-list alternative to tables on phone. Tables use column hiding +
  contained scroll instead (see Decision 4).
- PWA/offline, native app parity, or print styles.
- Adding a test framework. That's a separate decision, and verification
  here is a manual viewport matrix (tasks §8).

## Decisions

### 1. Breakpoints: Tailwind defaults, `lg` is the shell switch
Use Tailwind's default `sm 640 / md 768 / lg 1024` rather than custom
ones, so they're predictable for anyone reading the classes. `lg` is where
the sidebar docks. 1024px minus a 280px sidebar leaves 744px, which is the
narrowest content width the desktop layouts were checked at, and tablets
in landscape (1024) get the docked sidebar.

### 2. Drawer lives in `AppShell`, not in each sidebar
`AppShell` owns `isNavOpen` state and renders the sidebar twice by CSS
only. It's one element, positioned `fixed inset-y-0 left-0 z-40
-translate-x-full transition-transform` below `lg` (plus
`translate-x-0` when open), and `lg:static lg:translate-x-0`. The
backdrop is a `lg:hidden` button. A small `NavDrawerContext` exposes
`openNav`/`closeNav`/`isNavOpen`, so:
- each top bar (Admin, Reception, and a new minimal staff top bar where
  there's none today) renders a `lg:hidden` menu button;
- sidebars call `closeNav()` in their item click handler. Route change
  also closes it via a `useLocation` effect in `AppShell`, as a
  belt-and-braces measure.

Escape handling, body scroll lock (`overflow-hidden` on the shell root
while open), and focus management use a small `useFocusTrap` hook. It's
about 30 lines, which is enough to avoid a dependency. Sidebars change
only `w-[280px]` → `w-[min(280px,85vw)] lg:w-[280px]` and gain a
`lg:hidden` close button in their header.

*Alternative:* a separate mobile-nav component (bottom tab bar). Rejected:
admin has 15+ nav items, which don't fit a tab bar, and duplicating the
nav lists means they'll drift.

### 3. `useBreakpoint` only where CSS can't do it
Most adaptation is pure CSS. A `useMediaQuery('(min-width: 1024px)')`
hook (via `matchMedia` + `useSyncExternalStore`) is used only where the
render tree differs:
- the kanban board (one column vs all);
- the wizard (rail vs progress header);
- closing the drawer on resize to `lg`.

That keeps the hook's re-render surface tiny.

### 4. Tables: contained scroll + priority columns

As built, this is done on the `<table>` element rather than per cell.
`components/ui/responsive-table.ts` exports literal Tailwind
arbitrary-variant classes. `max-md:[&_tr>*:nth-child(n)]:hidden` hides
column *n* in the header and body, and
`[&_tr>*:last-child]:sticky right-0` pins the actions column. Each table
declares only which 1-based columns to hide. This is safe because no table
uses `colSpan`.

Wrap every `<table>` in the existing contained-scroll pattern (`overflow-x-auto`
on a bordered wrapper, already required by the app-shell spec). Mark
non-essential `<th>`/`<td>` with `hidden md:table-cell`. The row-actions
cell gets `sticky right-0 bg-surface` so it's reachable without
horizontal scroll. The alternative, a per-table card layout on phone,
doubles each table's markup across 11 tables. It's rejected for now, and
admin tables are rarely used on phones.

### 5. Kanban: status selector below `lg`
`staff-dashboard` keeps one `activeStatus` state, defaulting to the first
column that has cards. Below `lg` it renders `SegmentedToggle`, which is
already in `ui/`, or a horizontally scrollable chip row when there are
more than 3 columns, with counts. It then renders just that column's
`KanbanColumn`, full width. Data and filters are shared, so switching
doesn't refetch. At `lg` and up, today's `flex` row is unchanged.

### 6. Wizard: progress header below `md`
`StepSidebar` stays for `md:` up. A new `StepProgressHeader` (in the same
folder) takes the same `steps`/`currentIndex`/`onSelect` props, so both
are fed from one source of truth (the configured step list), which
satisfies "same steps, same order". The action footer becomes `sticky
bottom-0` with a surface background below `md`.

### 7. Tokens: responsive page padding
`@utility p-page-content` becomes `padding: 1rem` with `@media (width >=
48rem) { 1.5rem }` and `@media (width >= 64rem) { 2rem }`, and similarly
`gap-page-section` goes 1rem → 1.5rem. Every page using the token adapts
with no per-page edit. Pages with a literal `p-8` are switched to the
token.

### 8. Fixed widths → `w-full max-w-[…]`
Mechanical replacement: `w-[1160px]` → `w-full max-w-[1160px]`,
`w-[480px]` → `w-full max-w-[480px]`, and so on. Grids go `grid-cols-3`
→ `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`. Each site is reviewed
rather than regex-replaced blindly, because some fixed widths are icon or
avatar sizes that must stay.

### 9. Touch
- The `ui/` primitives get `min-h-10 min-w-10` hit areas below `lg`,
  using padding, not visual size, where the visual is small.
- Hover-revealed row actions become `opacity-100 lg:opacity-0
  lg:group-hover:opacity-100`.
- Form builder: `useSensors(useSensor(MouseSensor, { distance: 4 }),
  useSensor(TouchSensor, { activationConstraint: { delay: 200,
  tolerance: 5 } }))` at all 3 sites, with ≥40px drag handles below `lg`.
  This is *MouseSensor*, not the previous `PointerSensor`. Pointer events
  also fire for touch, so `PointerSensor` + `TouchSensor` would let a
  finger drag start through the 4px-distance pointer path and fight page
  scrolling. Mouse + Touch is dnd-kit's documented pairing. The delay
  keeps a swipe as a scroll.
- Invitation board: cards are dragged onto the Approved/Denied column with
  native HTML5 drag-and-drop, which has no touch support. Below `lg`, a
  draggable card therefore also shows "Approve" and "Deny" buttons wired
  to the same `approve` / `requestDeny` handlers the column drop uses.
  Desktop is unchanged (`VisitRequestCard` `onMoveToApproved` /
  `onMoveToDenied`).
- No hover-only affordances were found in the codebase, so there was
  nothing to convert.
- Inputs: `text-base sm:text-[current]` on `TextField`, `TextareaField`,
  `SelectField`, and `AutocompleteField`, to stop iOS focus zoom.

## Risks / Trade-offs

- [Breaking desktop layout while adding mobile classes] → Desktop styles
  move under `lg:` explicitly. Every touched page is checked at 1440 in
  the manual matrix before and after, with screenshots compared.
- [Sticky actions column overlapping content in wide tables] → It gets a
  left border/shadow, and is used only for the actions cell.
- [Form builder is still cramped on phone] → Stacking makes it usable,
  but building forms on a phone is an edge case. It's acceptable for it
  to be functional rather than comfortable at 360px.
- [No automated regression coverage] → The manual matrix is recorded in
  tasks. Adding Playwright viewport screenshots is suggested as a
  follow-up.
- [Change touches every page, so merge-conflict risk with in-flight
  changes (e.g. `improve-listing-ux`, `optimize-web-code-reuse-and-performance`)]
  → Land shared components first as their own PR, then pages in small
  batches per area (tasks groups 3–7).

## Migration Plan

Frontend-only. Ship in the batches from tasks.md: shell + tokens + ui
primitives, then admin pages, then staff/reception, then public. Each
batch is independently deployable, and rollback is a revert of that
batch.
