## Context

See proposal.md (Why) for the audit. The facts below shape the approach:

- **Data loading is hand-rolled per page.** Each list hook (for example
  `use-admin-branches.ts`) owns a single `isLoading` boolean and a
  `loadX({ silent })` function. The non-silent path sets `isLoading = true`,
  and the page's `isLoading ? <LoadingState/> : …` ternary then unmounts the
  table. Filter, page, and retry calls all take this path. Polling and
  post-mutation reloads already pass `silent: true`.
- **One hook already does it right.** `use-live-dashboard.ts`'s
  `useLiveResource` keeps `data` while re-fetching and drops superseded
  responses with a `requestIdRef`. This is the model this change
  generalises.
- **Motion today:** a CSS-only `.route-transition` keyed on pathname (entry
  only, deliberately no animation library), `--step-motion-*` tokens for
  the wizards, a sidebar width transition, and `animate-spin`. `Modal`
  returns `null` when closed, so it has no exit phase. `Modal` also does
  not use `use-focus-trap`; only the nav drawer does, and that hook already
  restores focus on deactivate.
- Recharts animations are already off (`isAnimationActive={false}`) so a
  poll doesn't re-animate charts. That stays.
- **No component test runner in the web repo.** Verification is `tsc -b`,
  `oxlint`, the Playwright e2e suite (`npm run e2e`), and the local QA
  harness and screenshot script.
- `improve-listing-ux` is open and owns `PageContentLayout`, `Pagination`,
  `RefreshContext`, and `use-paged-list`. This change consumes them and
  does not change their contracts.

## Goals / Non-Goals

**Goals:**
- One shared pattern for each of the following, so a page adopts behaviour
  by using a component instead of re-implementing it: first load versus
  refresh, overlay presence, collapsible regions, and pending buttons.
- Remove every height collapse and layout shift caused by loading. The
  specs (`async-ui-states`, `app-shell`) are the acceptance bar.
- Make reduced motion a single global rule, not something each component
  has to remember.

**Non-Goals:**
- Exit animations for routes. The outgoing page still unmounts at once, as
  `RouteTransition` does today; only the incoming page animates. The
  existing `app-shell` scenario wording ("outgoing transitions out") was
  already satisfied this way and is unchanged.
- A caching or data-fetching layer (React Query/SWR) or cross-page data
  reuse.
- Animating chart data changes, list-item reordering, or Kanban card moves
  between columns (no FLIP). The polled board updates in place.

## Decisions

### D1. CSS animations plus a tiny presence hook; no animation library
Exit animations need the element to stay mounted until its animation
ends. A `usePresence(isOpen, { durationVar })` hook handles this. It
returns `{ isMounted, state: 'open' | 'closing', onAnimationEnd }`, keeps the
node mounted through `closing`, and unmounts on `animationend`. A timeout
of the token duration plus 50 ms acts as a fallback, so a missed event can
never strand an invisible overlay. Components set `data-state={state}`,
and CSS keyframes keyed on `[data-state]` do the motion.

- *Alternative: `motion` / Framer Motion.* It gives `AnimatePresence`
  directly, but adds about 35–50 KB and contradicts `RouteTransition`'s
  documented CSS-only choice. That cost isn't justified for fade, scale,
  and slide.
- *Alternative: the View Transitions API (React Router's `viewTransition`).*
  It snapshots the whole document, including the sidebar, unless every
  persistent region is given a `view-transition-name`. Browser behaviour
  also differs for nested scroll containers. Revisit it later for route
  exits; it isn't needed for this change's acceptance criteria.

### D2. Motion tokens in `theme.css`, with reduced motion as one global rule
Add `--motion-fast` (100ms), `--motion-standard` (180ms), and
`--motion-slow` (280ms, the wizards' existing step duration, so they look
unchanged) on `:root`, exposed as `duration-fast`, `duration-standard`, and
`duration-slow` utilities, because Tailwind v4 has no duration theme
namespace. The easings go under `@theme` as `--ease-motion-out` and
`--ease-motion-in`. These are new names, so overriding Tailwind's built-in
`ease-out` can't change existing transitions. `utils/motion.ts` mirrors the
durations for JS.
`--step-motion-*` and `.route-transition` are redefined in terms of these
tokens.

One `@media (prefers-reduced-motion: reduce)` block sets
`animation-duration` and `transition-duration` to `0.01ms` for everything.
That still fires `animationend`, so presence unmounting works unchanged.
The rule also disables `.skeleton` shimmer. Remaining fades are
effectively instant, which satisfies the spec's 100ms cap without a
separate fade class. A global rule can't be forgotten by a new component;
per-component `motion-reduce:` classes can.

### D3. Split "first load" from "refresh" with one shared tracker
Add `useLoadTracker()` (`hooks/use-load-tracker.ts`), generalised from
`useLiveResource`'s `requestIdRef`. It returns `{ phase: 'initial' |
'ready' | 'error', isRefreshing, begin(mode) }`. `begin` returns a request
handle with `succeed()` and `fail()`. Each returns `false` and changes
nothing when a newer request has superseded it (spec "Out-of-order
responses never overwrite newer results"), so the caller writes state only
when it gets `true`.

- Before anything has loaded, a request keeps `phase = 'initial'`. A retry
  after a failed first load goes back to the skeleton.
- After that, `mode: 'user'` sets `isRefreshing`. This covers filter,
  page, search, retry, manual refresh, and post-mutation reload.
  `'background'` (polling) sets nothing.
- A failed request after the first load leaves `phase` at `'ready'`, so
  the content stays. The caller toasts ("A failed re-fetch keeps the last
  good content").

Page hooks keep their own data state and filter shape. Only the
`isLoading`/`errorMessage` bookkeeping moves to the tracker, which keeps
each of the ~20 hook diffs small. `usePageRefresh` receives `isRefreshing:
phase === 'initial' || isRefreshing`, so the top-bar spinner behaves as
before.

- *Alternative: a `useAsyncView` hook that owns the data too.* It is a
  cleaner API, but every hook that does optimistic local edits
  (`setBranches(map…)`) and multi-resource `Promise.all` loads would have
  to be restructured around one generic `data` object. That is far more
  churn for the same behaviour, so it was dropped during implementation.
- *Alternative: only change pages to render stale data when `isLoading &&
  data.length`.* This is a smaller diff, but it leaves the race condition
  and the error-wipes-content behaviour unsolved.
- *Alternative: React Query.* It is the right long-term tool, but it is a
  new dependency and a data-layer migration, both out of scope.

### D4. `AsyncRegion` replaces each page's ternary chain
Add `<AsyncRegion phase isRefreshing isEmpty skeleton empty error>`. It
renders the skeleton when `phase === 'initial'`, the error block when
`phase === 'error'` (first-load failure only), the empty state when the
view has loaded and has no items, and otherwise its children. When
`isRefreshing` is true it adds:

- a 2px indeterminate progress bar pinned to the region's top
  (`position: sticky`),
- `opacity: 0.6` with `pointer-events: none` on the children, and
- `aria-busy="true"` on the region.

Content mounts with a `--motion-standard` fade-in. This also removes about
17 copies of the same error, loading, empty, and content chain.

### D5. Skeleton primitives sized from the real components
Add `Skeleton` (a block with shimmer) and composed variants:
`TableSkeleton({ columns, rows })`, `BoardSkeleton({ columns })`,
`KpiRowSkeleton({ count })`, `CardGridSkeleton`, and `FormSkeleton({ rows
})`. Each reuses the real component's outer container classes (border,
radius, padding, header height), so the swap doesn't shift layout.
`TableSkeleton` renders `min(pageSize, 8)` rows. That fills a typical
viewport without promising more rows than may arrive. `LoadingState` (the
spinner) stays for modal bodies and small inline fetches.

### D6. `Modal` gains presence, a focus trap, and enter/exit keyframes
`Modal` uses `usePresence(isOpen)`, so all 27 dialogs and `ConfirmDialog`
gain motion with no caller changes. The keyframes are:

- backdrop: opacity 0 → 1,
- panel at `sm` and above: opacity plus `scale(0.96)` → 1,
- panel below `sm`: `translateY(100%)` → 0.

The closing state reverses these with `--ease-in`. The panel also gets
`inert`, which blocks input during the exit. `Modal` adopts
`use-focus-trap`, which supplies the Escape handling and focus return the
spec requires.

Callers that render conditionally (`{x && <SomeModal/>}`) skip the exit
animation. The rollout task converts them to pass `isOpen`.

### D7. Toasts, popovers, and drawer use the same presence pattern
- **Toasts.** `ToastViewport` keeps each dismissed toast mounted in a
  `closing` state. Its wrapper uses the CSS grid trick
  (`grid-template-rows: 1fr → 0fr`) to shrink its height, so the toasts
  below glide up without FLIP measurement. Entry is `translateX(16px)` plus
  a fade on desktop, and `translateY(-8px)` on mobile.
- **Popovers.** `NotificationBell`, the user menu, `AutocompleteField`,
  and `DropdownFilter` use `usePresence`, plus `transform-origin` set to
  the trigger side.
- **Drawer.** `AppShell` keeps the drawer mounted and drives
  `translate-x` and backdrop opacity by state instead of mounting and
  unmounting them.

### D8. `Collapsible` uses the grid-rows technique, not height measuring
`<Collapsible open>` wraps its content in
`display: grid; grid-template-rows: 0fr | 1fr; transition:
grid-template-rows var(--motion-standard)`, with `overflow: hidden` on the
inner element. It sets `inert` while closed, so hidden filter fields can't
be focused. This needs no `ResizeObserver` and handles content that
changes size while open. The 9 `isFilterPanelOpen && (…)` panels and
`ExpandableText` adopt it.

### D9. Pending buttons keep their width by overlaying the spinner
Add `PendingButton` (`components/ui/PendingButton.tsx`), a drop-in
`<button>` with `pending` and `pendingLabel` props. It keeps each caller's
own className, because the app has no shared button styles to unify. While
pending, the label stays rendered with `invisible`, so the width is
preserved. A centred, absolutely positioned `Spinner` sits on top. The
button also gets `disabled` and `aria-busy`, and `pendingLabel` becomes
its accessible name. `ConfirmDialog` maps its existing `isBusy` and
`busyLabel` onto this. The current text-only "Deleting…" labels go away
because they change the button's width.

### D10. Shell-level fixes
- `scrollbar-gutter: stable` on `<main>` only. It was tried on
  `PageContentLayout`'s data region and dropped: with classic scrollbars,
  the reserved strip made the table 15px narrower than the fixed heading
  and filter row above it.
- `RouteTransition` takes a ref to the scroll container (passed from
  `AppShell`). It calls `scrollTo({ top: 0 })` on pathname change, inside
  a layout effect so the reset happens before the first paint.
- Interactive controls get `transition-[background-color,color,
  border-color,box-shadow,transform] duration-fast` and an `active:` state
  (`active:scale-[0.98]` on solid buttons). This is applied through a
  shared class constant rather than edited by hand on each button.

### D11. Rollout order: shared pieces first, Branches as the pilot
1. Shared primitives: tokens, presence, skeletons, `AsyncRegion`,
   `Collapsible`, and `Button`.
2. Global wins with no page edits: `Modal`, toasts, popovers, drawer, and
   the shell fixes.
3. Branches as the pilot list page.
4. The remaining admin lists.
5. Boards and dashboards.
6. Forms and settings, staff pages, and the public and kiosk pages.

Each step ships independently and can be verified with the QA harness.

## Risks / Trade-offs

- [Exit animations delay unmount, so e2e assertions such as "dialog is
  gone" can race the animation.] → Playwright's auto-waiting `expect`
  covers most of these. Audit `toBeHidden` and `count() == 0` checks in the
  e2e suite during rollout. Durations stay at or under 280ms.
- [Dimmed stale rows could be read or acted on while a filter applies.] →
  Pointer events are disabled on the refreshing region, `aria-busy` is
  set, and the progress bar is always visible. Refreshes are typically
  under 500 ms.
- [Skeletons that don't match the real layout cause their own jump.] → D5
  reuses the real containers' classes, and the QA screenshot pass compares
  the skeleton and loaded frames for each page.
- [Conditionally rendered modals (`{open && <X/>}`) silently get no exit
  animation.] → The rollout task greps for this pattern and converts each
  case to `isOpen`.
- [The global reduced-motion rule also kills the looping `animate-spin`.]
  → Exempt `.animate-spin` (and the progress bar's indeterminate loop,
  slowed down) from the 0.01ms override. A spinner is a status indicator,
  not decorative motion.
- [This overlaps the still-open `improve-listing-ux` on the same page
  files.] → Land or archive `improve-listing-ux` first, or rebase this
  change's page tasks onto it. The shared-primitive tasks (§1–2) don't
  conflict.

## Migration Plan

This is web-only and has no API or data migration. Each rollout step in
D11 is an independent commit; rolling back means reverting it.
`useLoadTracker` coexists with the old `isLoading` hooks, so pages migrate
one at a time.
