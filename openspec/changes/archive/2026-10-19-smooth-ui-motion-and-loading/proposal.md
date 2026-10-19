## Why

During a full walkthrough of the portal, almost every page "jumps." It
happens on navigation, when a filter changes, when a list pages, when a
dialog opens, and when a toast appears. An audit of
`src/presentation` traced this to a few patterns repeated on every page,
not to any one screen:

1. **Every re-fetch tears the content down.** List hooks (for example
   `use-admin-branches.ts`) call their loader in non-silent mode whenever a
   filter or page number changes. That flips `isLoading` back to `true`, and
   the page swaps its whole table for a centred `<LoadingState>` spinner.
   The region collapses to the spinner's height, then expands again when the
   rows return. About 17 page folders follow this
   `isLoading ? <LoadingState/> : …` pattern.
2. **The first load does not match the final layout.** Navigation plays the
   180 ms `route-fade-in`. The page then shows a small spinner, and the real
   table, cards, or KPI row replace it. The user sees two layout changes for
   one navigation. No skeleton placeholder exists anywhere in the staff or
   admin areas.
3. **Overlays appear and disappear instantly.** `Modal` (used by 27
   dialogs, including `ConfirmDialog`), the toast viewport, the notification
   bell popover, autocomplete menus, and the inline filter panels (9 pages,
   `isFilterPanelOpen && …`) all mount and unmount with no transition. The
   filter panels also push the content below them down abruptly.
4. **There is no shared motion vocabulary.** Durations and easings are
   ad hoc (`duration-200` in one place, `180ms` in another,
   `--step-motion-*` only for the wizards). Nothing makes a new component
   animate consistently or respect `prefers-reduced-motion`.

This is a user-experience fix across the whole product. It is due now
because the listing, dashboard, and notification work that just landed
added more re-fetch triggers (filters, pagination, range toggles), and each
one makes the jumping more frequent.

## What Changes

- Add a shared set of **motion tokens** (durations and easings) in
  `theme.css`. All animation uses them. Under `prefers-reduced-motion:
  reduce`, all of it is disabled or reduced to an instant opacity change.
- **Keep content on screen during re-fetches.** When a filter, page,
  search, sort, range, or manual refresh triggers a re-fetch after the first
  successful load, the current content stays rendered and in place. The
  page shows a subtle in-progress cue instead: a thin progress bar on the
  data region and reduced opacity on stale rows. Results then swap in place
  without a height collapse. Only the very first load, before any data
  exists, shows a placeholder.
- **Use skeleton placeholders shaped like the content for first loads.**
  Each placeholder matches its layout: table rows for lists, cards for
  Kanban columns, tiles for the KPI row and chart cards, and field rows for
  forms and settings pages. It replaces the centred spinner, so the layout
  does not shift when data arrives. `LoadingState` remains for small inline
  areas such as modal bodies that fetch on open.
- **Animate entry and exit for every overlay.** Modals and confirm dialogs
  fade their backdrop and scale and fade their panel on desktop; on mobile
  the bottom sheet slides up. Toasts slide in and fade out. Popovers such as
  the notification bell, autocomplete, and dropdown menus fade and scale
  from their anchor. Filter panels expand and collapse smoothly instead of
  appearing all at once. Each overlay finishes its exit animation before it
  unmounts.
- **Show pending feedback on every action button.** A button that starts an
  async mutation (Save, Delete, Approve, Check out, and similar) shows an
  inline spinner and keeps its width. It is disabled until the mutation
  settles, so a double click cannot send a second request. This
  standardises the current mix of text-only "Deleting…" labels.
- **Smooth the route transition further.** The incoming page reserves its
  final layout through skeletons, so the existing fade-in no longer runs on
  top of a spinner-to-content swap. Scroll position resets to the top of
  the content region on navigation. Scrollbar gutters are kept stable so
  content does not shift sideways when a page becomes scrollable.
- **Cover public and kiosk pages too.** The visitor portal, the
  track-request page, OTP verification, and the registration wizards get
  the same loading and overlay behaviour. The wizards' existing step
  animation stays as it is and is moved onto the shared motion tokens.

No API change. No new runtime dependency: CSS keyframes/transitions plus a
small presence hook, consistent with `RouteTransition`'s existing CSS-only
approach.

## Capabilities

### New Capabilities

- `ui-motion`: the shared motion tokens, the reduced-motion rule, the
  enter/exit animation contract for overlays (modals, dialogs, sheets,
  popovers, toasts, the nav drawer), collapsible panels, and pending state
  on action buttons.

### Modified Capabilities

- `async-ui-states`: the loading-indicator requirement changes. The
  placeholder now appears only on the first load and must be a skeleton
  shaped like the content. Later re-fetches keep the existing content
  visible with an in-progress cue instead of replacing it. A failed
  re-fetch keeps the last good content and reports the error by toast.
- `app-shell`: the route-transition requirement gains two rules. The
  incoming page must not shift its own layout after it enters (because it
  uses a skeleton first). The content region's scroll resets to the top on
  navigation.

## Impact

- **Code (shared)**: `src/styles/theme.css` (motion tokens),
  `src/styles/index.css` (keyframes, reduced-motion rules, stable
  scrollbar gutter); `components/ui/Modal.tsx` and `ConfirmDialog.tsx`
  (presence and enter/exit); `components/toast/*`; `components/ui/
  LoadingState.tsx` plus new `Skeleton` primitives; new progress-bar and
  `Collapsible` components; a new `AsyncButton` (or a pending prop on
  existing buttons); `components/notification-bell/NotificationBell.tsx`,
  `components/ui/AutocompleteField.tsx`, and `DropdownFilter.tsx`;
  `components/RouteTransition.tsx` and `AppShell.tsx`.
- **Code (per page)**: each list, board, and dashboard hook splits
  `isLoading` into "first load" and "refreshing" states, and each page
  renders the skeleton, a stale-content cue, or content. This affects every
  `pages/admin-*`, `staff-*`, `reception-dashboard`, `visitor-*`, and
  `staff-visitor-registration` page, plus `use-invitations-board.ts`,
  `use-live-dashboard.ts`, and `use-paged-board-columns.ts`.
- **Overlap with `improve-listing-ux`** (still open; its manual check in
  task 3.5 is outstanding). That change introduced the filter and paging
  triggers this change smooths, and it owns `PageContentLayout` and
  `RefreshContext`. This change builds on both without changing their
  contracts. The top-bar refresh spinner keeps reading `isRefreshing`.
- **Tests and QA**: the e2e suite (`npm run e2e`) needs its waits updated
  wherever it currently waits for "Loading…" text to disappear. The
  `screenshots` script should capture pages after their skeletons resolve.
- **Out of scope**: no data-fetching library (React Query/SWR), no
  animation library, no visual redesign of components beyond motion and
  loading states, and no change to the 15-second polling cadence.
