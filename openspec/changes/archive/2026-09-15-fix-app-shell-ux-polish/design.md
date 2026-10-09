## Context

See `proposal.md` - Why for motivation. Relevant current state:

- There is no shared app-shell layout component. Every admin/staff page duplicates the same markup (`<div className="flex min-h-screen w-full items-stretch ...">` containing a sidebar, top bar, and `<main>`), e.g. `admin-branches.tsx`, `admin-dashboard.tsx`, and the staff equivalents with `DashboardSidebar`. Nothing is `fixed`/`sticky`; `min-h-screen` lets the whole wrapper grow past the viewport, so the sidebar/top bar scroll with content, and no ancestor sets `overflow-x: hidden`.
- `use-invitations-board.ts` already implements the target polling pattern: a `setInterval` guarded by an `actionInProgressRef` that skips a tick while a mutation/dialog is open, plus a manual `refresh()`. It's currently 30s and used only by the invitations board and staff dashboard.
- Routing is plain `react-router` `<BrowserRouter>`/`<Routes>/<Route>` under one `RootLayout` (`src/App.tsx`) — no animation library, no partial wiring for transitions.
- A shared `LoadingState`/`Spinner` component already exists (`src/presentation/components/ui/LoadingState.tsx`). **Correction after full-codebase audit**: it is used correctly by every single page — cross-checking every hook with `isLoading` state (`grep -rl setIsLoading src/presentation/pages`) against every page rendering `LoadingState` showed a 1:1 match, and direct reading of `admin-invitations.tsx`/`staff-dashboard.tsx` confirmed both already gate on `isLoading` correctly via the shared `useInvitationsBoard` hook. There is no loading-indicator gap anywhere; task group 4 in tasks.md is closed as "no change needed."
- Back buttons already exist on most create/edit form pages via a `ChevronLeftIcon` + handler pattern (not raw `navigate(-1)`); top-level list pages reached from the sidebar have none, which is correct per the resolved scope. **Correction after code inspection**: there is no branch → building → floor → department route hierarchy — `/admin/branches`, `/admin/buildings`, `/admin/floors`, `/admin/departments` are independent top-level sidebar routes (confirmed in `App.tsx`/`AdminSidebar.tsx`); floors are not nested under buildings. The actual gap is three specific sub-pages that are reached by navigating from a list page's "Add"/"Edit" action but, unlike the other 8 form pages, only have a "Cancel" button in the form footer and no header-level back control: `admin-branches/admin-branch-create.tsx`, `admin-roles/admin-role-create-form.tsx`, and `admin-roles/admin-role-permissions-form.tsx`.

## Goals / Non-Goals

**Goals:**
- One shared shell layout component that every admin and staff page adopts, so the fixed-sidebar/scrollable-content behavior is enforced structurally, not by convention.
- A generalized version of the existing polling pattern (interval + in-progress guard + manual refresh) that other operational pages can adopt without re-deriving it.
- A drop-in transition wrapper and back-button component so individual pages opt in with minimal changes.

**Non-Goals:**
- No new npm dependency (per the resolved animation approach: CSS-only, no framer-motion).
- No change to what data any page fetches or how it's fetched (repository/use-case layer) — this only changes when/how often it refetches and how it's presented.
- No redesign of visual styling, color, or typography (that's `design-theme`'s territory) — only layout/scroll/transition/refresh/back-navigation behavior.
- Not attempting a full app-wide design system audit; scope is the four reported issues.

## Decisions

**1. Shared shell component (`AppShell`) replacing per-page duplicated markup.**
Extract one `AppShell` component (`src/presentation/components/AppShell.tsx`) taking `sidebar` and `children` (or a `variant: 'admin' | 'staff'` plus active-item prop) and rendering:
```
<div className="flex h-screen w-full overflow-hidden">
  <aside className="shrink-0 h-screen overflow-y-auto">{sidebar}</aside>
  <div className="flex flex-1 flex-col min-w-0 h-screen overflow-hidden">
    <TopBar />  {/* sticky/shrink-0, not scrolled */}
    <main className="flex-1 overflow-y-auto overflow-x-hidden">{children}</main>
  </div>
</div>
```
`h-screen` (not `min-h-screen`) + `overflow-hidden` on the outer wrapper is the key fix: it caps the shell at the viewport height so only `<main>` scrolls. `overflow-x-hidden` on `<main>` plus a global `overflow-x: hidden` on `html`/`body` closes the horizontal-scroll gap for content that doesn't self-contain (belt-and-suspenders — individual wide tables should also wrap themselves in `overflow-x-auto`).
*Alternative considered*: fix each page's wrapper in place (add `overflow-hidden`/`h-screen` classes to every page's existing duplicated markup) without extracting a shared component. Rejected — it would leave ~15 pages independently responsible for maintaining the same fragile class combination, which is exactly how the bug was introduced in the first place.

**2. Page-transition animation: CSS-only, keyed on route location.**
Wrap the routed content in a small `RouteTransition` component that keys a container `div` on `location.pathname` and applies a CSS fade/slight-slide via `@keyframes` + a transition class toggled through the existing DOM key-remount (no `AnimatePresence`-style exit animation, since that needs a library to keep the outgoing node mounted during unmount). This means only the *entering* view animates in; there's no animated exit. That's an accepted trade-off for staying dependency-free — see Risks.
`@media (prefers-reduced-motion: reduce)` disables the animation (sets it to an instant, zero-duration state) to satisfy the spec's reduced-motion scenario.
*Alternative considered*: `framer-motion`'s `AnimatePresence` for true enter/exit crossfade. Rejected per the resolved answer (no new dependency) — the visual gap this closes (page jump) is fixed well enough by an enter-only fade for the reported problem.

**3. Auto-refresh: generalize the existing hook rather than bolt polling onto each page separately.**
Extract the interval/guard/manual-refresh logic already in `use-invitations-board.ts` into a small reusable hook (e.g. `usePolling(fetchFn, { intervalMs: 15_000, isBusy })`) that any page's existing data hook can call, passing its own fetch function and an `isBusy` flag (mutation/dialog open). `use-invitations-board.ts` becomes the first caller of the extracted hook at `intervalMs: 15_000`; other list pages' hooks (`use-admin-branches`, `use-admin-departments`, etc.) adopt the same hook with their own fetch function.
*Alternative considered*: give every page its own bespoke `setInterval`. Rejected — that's the loop-and-duplicate pattern that made the invitations board's guard logic (skip-while-busy) something every other page would have to reinvent (and could get subtly wrong, e.g. refreshing out from under an open edit dialog).

**4. Back-navigation: a shared `BackButton` component driven by an explicit parent route, not raw `navigate(-1)`.**
`navigate(-1)` breaks if the user arrived via a direct link/refresh (no history entry to go back to) or came from an unrelated page. Instead, each page declares its logical parent route explicitly, and the shared `BackButton` navigates there directly — consistent with how 8 of the 11 admin form pages already implement this via a header `ChevronLeftIcon` + handler. The 3 pages missing it (`admin-branch-create.tsx` → `/admin/branches`, `admin-role-create-form.tsx` → `/admin/roles`, `admin-role-permissions-form.tsx` → `/admin/roles`) adopt the same shared `BackButton` component so the pattern is consistent everywhere instead of each page re-implementing its own chevron button.

## Risks / Trade-offs

- **[Risk] CSS-only page transition has no true exit animation (outgoing view unmounts instantly)** → Mitigation: the fade-in on the incoming view is still a large improvement over the current zero-animation snap, and it fully resolves the "jumping" complaint without adding a dependency; revisit with `framer-motion` later if an exit animation becomes a real ask.
- **[Risk] Extracting `AppShell` touches every admin/staff page's top-level markup** → Mitigation: this is a mechanical, low-logic-risk change (swap wrapper markup, keep each page's existing content as `children`); do it page-by-page behind the same shared component so each page can be verified independently, and existing page-level tests/behavior are unaffected since only the outer wrapper changes.
- **[Risk] Widening auto-refresh to ~13 pages increases backend request volume (15s × N open tabs × N pages)** → Mitigation: this is frontend-only polling against existing read endpoints with no new load-bearing computation; if volume becomes a concern later, the shared `usePolling` hook is the one place to add backoff/visibility-based pausing (e.g. pause when the browser tab is not visible) — flagged as a possible follow-up, not required for this change.
- **[Risk] Skip-while-busy guard could mask a stale-data window if a dialog is left open a long time** → Mitigation: this already exists today in the invitations board and is an accepted, currently-working trade-off; not introduced by this change.

## Migration Plan

- No data migration or backend change. Rollout is page-by-page within the frontend: introduce `AppShell`, `RouteTransition`, `usePolling`, and `BackButton` as new shared components first, then migrate each page to adopt them one at a time (tasks.md sequences this). Each page remains fully functional both before and after its own migration step, so this can land as one PR or be split without a broken intermediate state.
- Rollback is a plain revert (frontend-only, no schema/version compatibility concerns).
