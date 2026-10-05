## Why

The portal is laid out for a desktop monitor only. Across 24 pages the
codebase has 7 Tailwind breakpoint classes in total, and 22 pages have
none. The shells use fixed widths: a 280px sidebar that is always visible,
1160px form containers, and a 220px wizard step rail. The consequences:
- On a phone or tablet the sidebar eats most of the screen.
- Admin forms overflow.
- The visitor self-registration wizard is unusable on a phone, which is the
  device most visitors actually use.

Reception and security staff also work from tablets at the desk and gate.

## What Changes

- Define a supported device range and breakpoints: phone 360–639px, large
  phone/small tablet 640–767px (`sm`), tablet 768–1023px (`md`), desktop
  ≥1024px (`lg`). Every page must be fully usable from 360px wide upward,
  with no horizontal page scroll.
- Staff/admin shells (`AppShell` with Admin, Dashboard, and Reception
  sidebars):
  - Below `lg`, the sidebar becomes an off-canvas drawer, opened from a
    hamburger button in the top bar and closed by the backdrop, Esc, or
    navigating.
  - The top bar compacts: the breadcrumb truncates and the description
    hides on phone.
  - At `lg` and up the layout is unchanged.
- `reception-dashboard` stops using its own full-screen layout and uses the
  shared shell.
- Public shell (`PortalHeader`, `PortalFooter`, and the landing, request
  wizard, and track pages):
  - Header padding and footer stack adapt to width.
  - The request wizard's step rail becomes a compact horizontal "Step X of
    N" progress bar below `md`.
- Page content:
  - Fixed pixel widths (`w-[1160px]`, `w-[480px]`, …) become
    `w-full max-w-*`.
  - Multi-column form grids collapse to 1 column on phone and 2 on tablet.
  - Page header action rows wrap.
  - Filter bars stack.
- Data tables: each table keeps its columns and scrolls inside its own
  container. Low-priority columns hide below `md`, and the row-actions
  column stays pinned and reachable.
- Kanban boards (staff and reception invitation boards):
  - Below `lg`, show one column at a time behind a status tab/segmented
    selector with counts.
  - On desktop they stay side by side.
- Modals: full-width with a small margin on phone (bottom-sheet style
  below `sm`), with the body scrolling inside and the footer actions
  sticky.
- Touch:
  - Interactive controls are at least 40×40px on touch layouts.
  - Hover-only affordances get a visible or tap alternative.
  - The form-builder drag-and-drop enables a touch sensor alongside the
    pointer sensor.
- Form builder: panels stack on phone and tablet.

## Capabilities

### New Capabilities
- `responsive-layout`: Cross-page layout contract. It covers the
  supported viewport range and breakpoints, and the behavior of fluid
  widths and form grids, data tables, kanban boards, modals, and page
  headers/filters across breakpoints. It also sets touch-target and
  hover-alternative rules.

### Modified Capabilities
- `app-shell`: The fixed-sidebar requirement now applies from `lg` up.
  Below `lg`, the sidebar is an off-canvas drawer with a top-bar toggle,
  and the reception dashboard renders inside the shared shell.
- `visitor-request-wizard`: The step navigation adapts below `md` to a
  compact progress indicator instead of the fixed-width side rail.

## Impact

- Shared components: `AppShell`, `AdminSidebar`, `DashboardSidebar`,
  `ReceptionSidebar`, `AdminTopBar`, `PortalHeader`, `PortalFooter`,
  `PublicLayout`, `StaffLayout`, `PageContentLayout`, `ui/Modal`,
  `ConfirmDialog`, `Pagination`, `DropdownFilter`, `invitation-board/*`,
  and `dashboard/*`.
- All 24 page folders under `src/presentation/pages/`: class-level
  changes only, no data-flow changes.
- `src/styles/theme.css`: responsive `p-page-content` and
  `gap-page-section` values.
- New tiny hook `useMediaQuery` / `useBreakpoint` under
  `presentation/hooks`, plus a drawer-open state in the shell.
- No API change, no new runtime dependency (Tailwind v4 breakpoints and
  `@dnd-kit/core` `TouchSensor` are already available), no routing change.
