## Why

The admin/staff web app has accumulated four whole-app UX problems, all reported directly from real usage: (1) the sidebar and top navbar scroll away with the page instead of staying fixed, and pages can scroll both vertically and horizontally at once; (2) operational list/dashboard pages have no live auto-refresh — staff must click a manual refresh button to see new activity; (3) navigating between routes has no transition animation, so pages visibly jump/snap; and (4) some pages give no loading feedback during a fetch, and drill-down pages (e.g. branch → building → floor) have no way back except browser navigation. None of these are isolated to one page — they're systemic gaps in the shared app shell and its cross-cutting conventions, so they need a shell-level and convention-level fix rather than a per-page patch.

## What Changes

- Introduce a shared, fixed-position app shell layout (sidebar + top navbar pinned; only the main content region scrolls) used by every admin and staff page, replacing the current per-page duplicated flex markup that has no scroll containment.
- Add a global horizontal-overflow guard so no page can trigger page-level horizontal scrolling; any content that must scroll horizontally (e.g. a wide table) does so in its own contained, scrollable region instead.
- Add a lightweight CSS-only page-transition (fade/slide) on route change, applied once at the shell/router level so it covers every route without per-page wiring.
- Extend the existing 30-second silent auto-refresh (currently only on the invitations board / staff dashboard) to a shared 15-second polling convention applied to all live operational list/dashboard pages (branches, buildings, floors, departments, reception desks, security gates, host employees, visitor categories, approval workflows, invitations, roles, admin dashboard, staff dashboard) — polling pauses while a mutation/dialog is in progress, matching the existing guard pattern. The existing manual refresh button is kept alongside auto-refresh, not removed, so staff can still force an immediate refresh.
- Verified the loading-indicator convention: every page-level view with an async data fetch, including the invitations board and staff dashboard, already shows the shared `LoadingState`/`Spinner` component while its fetch is in flight (confirmed by cross-checking every hook with `isLoading` state against its page's `LoadingState` usage). No gap found — no change needed here; this was reported as a symptom but the underlying cause turned out to be the missing auto-refresh (below) making pages feel unresponsive between manual refreshes, not an absent loading indicator.
- Add a shared back-navigation affordance to drill-down/nested pages that are reached by navigating from another page rather than directly from the sidebar (e.g. branch → building → floor → department hierarchy, and other detail views reached via a route param). Top-level pages reachable directly from the sidebar are unchanged — sidebar navigation remains their primary wayfinding.

## Capabilities

### New Capabilities
- `live-data-refresh`: shared 15-second background polling convention for operational list/dashboard pages, coexisting with an on-demand manual refresh control.

### Modified Capabilities
- `app-shell`: add requirements for a fixed sidebar/navbar with an independently scrolling content region, a page-level horizontal-overflow guard, a shared route-transition animation, and a shared back-navigation affordance for drill-down pages.

## Impact

- **Affected code**: `src/presentation/components/` (new shared shell/layout component, back-button component, transition wrapper), every admin/staff page under `src/presentation/pages/**` (adopt the shared shell instead of duplicated markup), `src/presentation/hooks/use-invitations-board.ts` (interval 30s → 15s, reused/generalized for other pages), `src/App.tsx` / root layout (mount point for the transition wrapper), global stylesheet (`src/styles/index.css` / `theme.css`) for the horizontal-overflow guard.
- **Affected pages**: all 25 admin page files (every list page plus its create/edit/step-editor forms: branches, buildings, dashboard, departments, floors, form builder, host employees, invitations, organisation configs, reception desks, roles, security gates, visitor categories, workflows) and all 3 staff pages using the same layout pattern (dashboard, visitor registration, audit trail).
- **Dependencies**: none added — animations are CSS-only, no new npm package.
- **No backend/API impact** — this is frontend-only (VMMS_WEB); no VMSS_API changes.
