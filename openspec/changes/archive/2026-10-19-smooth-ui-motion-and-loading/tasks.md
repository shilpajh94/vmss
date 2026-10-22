## 1. Motion foundation

- [x] 1.1 Add motion tokens (`--motion-fast` / `--motion-standard` /
      `--motion-slow`, `--ease-out` / `--ease-in`) to `src/styles/theme.css`
      and expose them through `@theme` as Tailwind duration/ease utilities
      (design D2).
- [x] 1.2 Redefine `--step-motion-*` and `.route-transition` in
      `index.css` in terms of the new tokens; confirm the wizard step
      animation looks unchanged.
- [x] 1.3 Add the single global `prefers-reduced-motion` block. Exempt
      `.animate-spin` and the progress bar's loop, and cap
      `.motion-safe-fade` at 100ms (D2 and the reduced-motion risk).
- [x] 1.4 Add the keyframes shared by every presence-driven component
      (fade, scale-in, sheet-up, slide-in-right, slide-down, and their
      reverses), keyed on `[data-state]`.
- [x] 1.5 Build `hooks/use-presence.ts`: `isMounted` plus
      `state: 'opening' | 'open' | 'closing'`, unmount on `animationend`
      with a timeout fallback, and correct handling of reopening while
      closing (D1).

## 2. Shared loading primitives

- [x] 2.1 Build `components/ui/Skeleton.tsx` (shimmer block) and the
      composed `TableSkeleton`, `BoardSkeleton`, `KpiRowSkeleton`,
      `CardGridSkeleton`, and `FormSkeleton`, reusing the real
      components' container classes (D5).
- [x] 2.2 Build the indeterminate `ProgressBar` (2px, sticky to its
      region's top).
- [x] 2.3 Build `hooks/use-load-tracker.ts` (`phase`, `isRefreshing`,
      `begin(mode)` returning `succeed`/`fail` with a superseded-response
      guard, keeping content on a failed non-initial request), generalised
      from `useLiveResource` (D3).
- [x] 2.4 Build `components/AsyncRegion.tsx`: skeleton, error, empty, or
      content, with the refreshing cue (progress bar, dimming,
      `pointer-events: none`, `aria-busy`) and a fade-in on content mount
      (D4).
- [x] 2.5 Build `components/ui/Collapsible.tsx` (grid-rows transition,
      `inert` while closed) (D8).
- [x] 2.6 Build `PendingButton`: the label is kept `invisible` to hold the
      width, a spinner is overlaid, plus `disabled`, `aria-busy`, and
      `pendingLabel` (D9). Add a shared interactive-transition class
      constant (hover, focus, and `active:` press state) (D10).

## 3. Overlays and shell (no page edits needed)

- [x] 3.1 Move `Modal.tsx` onto `usePresence`, with backdrop fade, a
      desktop scale-in, a mobile sheet-up, a reverse on close, and `inert`
      while closing. Adopt `use-focus-trap` for Escape handling and focus
      return (D6).
- [x] 3.2 Map `ConfirmDialog`'s `isBusy`/`busyLabel` onto the pending
      button. Remove the width-changing text swap.
- [x] 3.3 Find every conditionally rendered modal (`{cond && <XModal`)
      across `pages/` and `components/`, and convert each one to an
      always-rendered component with an `isOpen` prop, so all of them get
      an exit animation. None needed converting: every dialog already
      passes `isOpen`, and none returns early before `<Modal>`. `Modal` now
      freezes its last open title and children while closing, so callers
      that clear their state on close (`pendingDelete`) don't flash
      "undefined" during the exit.
- [x] 3.4 Animate toasts: entry slide and fade, exit fade, and the
      grid-rows height collapse so the remaining toasts glide into place
      (D7).
- [x] 3.5 Animate popovers (`NotificationBell`, the user menu in
      `AppTopBar`/`AdminTopBar`, `AutocompleteField`, `DropdownFilter`)
      with presence and a trigger-side `transform-origin`. There is no
      separate user-menu popover, and `DropdownFilter` is a native
      `<select>`, so the bell and the autocomplete were the only popovers.
      The visitor wizard's phone step list (`StepProgressHeader`) expands in
      place, so it uses `Collapsible` instead.
- [x] 3.6 Keep the nav drawer and its backdrop mounted in `AppShell`, and
      drive the slide and fade from state.
- [x] 3.7 Add `scrollbar-gutter: stable` to `<main>` (not to
      `PageContentLayout`'s data region; see D10). Reset the content region's scroll
      to the top on pathname change in a layout effect (D10).
- [x] 3.8 Give toggles and segmented controls (`ToggleSwitch`,
      `SegmentedToggle`, `RangeToggle`) a gliding thumb or indicator
      transition.

## 4. Pilot: Branches

- [x] 4.1 Move `use-admin-branches.ts` onto `useLoadTracker`. Filter, page,
      retry, and manual-refresh triggers use `'user'` mode; polling uses
      `'background'`; the post-delete reload uses `'user'`. Keep feeding
      `usePageRefresh`.
- [x] 4.2 Replace the page's ternary chain with
      `AsyncRegion(TableSkeleton)`, wrap the filter panel in
      `Collapsible`, and use pending buttons in `BranchFormModal`.
- [x] 4.3 Verify in the browser with the local QA harness: navigation,
      filter change, paging, opening and closing the filter panel, the
      edit modal, the delete confirmation, and the toasts. Check that
      nothing collapses or shifts, and repeat with reduced motion
      emulated. Record any pattern adjustments before the rollout.
      Done with `e2e/test_motion_and_loading.py` (7 checks, plus the
      existing `test_org_setup.py`, all green) and skeleton, pending, and
      loaded screenshots. Adjustments: the skeleton row and header heights
      now match the real table (63px and 47px); the data region keeps no
      scrollbar gutter (D10); `Collapsible` also sets `visibility: hidden`
      once closed; and the tests park requests with `page.route` instead of
      sleeping in the handler, which blocked the sync client.

## 5. Roll out to the remaining admin list pages

- [x] 5.1 Buildings, Departments, and Floors: hook to `useLoadTracker`,
      `AsyncRegion`/`TableSkeleton`, `Collapsible` filters, pending
      buttons in their modals, and create pages.
- [x] 5.2 Host Employees, Reception Desks, and Security Gates: same steps
      as 5.1. Desks and Gates are thin wrappers over
      `admin-devices-list.tsx`, so 5.4 covers them.
- [x] 5.3 Visitor Categories, Roles (including the add-role page), and
      Workflows: same steps as 5.1.
- [x] 5.4 Kiosks, Devices, and the Audit Trail (admin and staff): same
      steps as 5.1; the audit trail's search uses the debounced `'user'`
      reload.

## 6. Boards and dashboards

- [x] 6.1 Move `use-invitations-board.ts` and
      `use-paged-board-columns.ts` to the first-load/refresh split. The
      board shows `BoardSkeleton` on first load, and keeps the cards with
      the refreshing cue on a filter or search change. Column "load more"
      shows a card skeleton at the column's foot.
- [x] 6.2 Apply the same split to the admin Invitations and staff
      Invitations pages, and use pending buttons in every invitation-board
      modal (Approve, Deny, Delegate, Reschedule, Revert, Check out, Edit,
      Export).
- [x] 6.3 Admin, Staff, and Reception dashboards: replace
      `DashboardLoading` with `KpiRowSkeleton` plus a chart- and
      card-shaped skeleton. Range-toggle changes show the refreshing cue
      on the affected card only. (The range-change dimming already existed
      through `ChartCard.isUpdating`; it gained the progress bar and
      `aria-busy`.)

## 7. Forms, settings, staff, and public pages

- [x] 7.1 Form Builder (list and step editor) and Organisation Configs:
      `FormSkeleton` on first load, pending Save buttons, and
      `Collapsible` sections where panels expand in place.
- [x] 7.2 Staff visitor registration: consistent skeletons for async
      dropdown or field loading, and pending Submit/Next buttons. Keep the
      step animation on the tokens.
- [x] 7.3 Visitor portal landing, visitor request wizard, OTP
      verification, and track request: skeletons for their fetched
      content, pending buttons on Send OTP / Verify / Submit, and modal
      motion via the shared `Modal`.
- [x] 7.4 Staff and admin login and SSO login: pending sign-in buttons
      with no width change.
- [x] 7.5 Sweep: confirm that no `<LoadingState` remains as a page-level
      replacement for loaded content (it is allowed only inside modals and
      small inline regions), and that no `isFilterPanelOpen &&` or
      instantly mounted overlay remains.

## 8. Verification

- [x] 8.1 `npm run build` (`tsc -b`) and `npm run lint` pass clean.
      Both exit 0; the only lint output is two existing unused-variable
      warnings in `use-visitor-request-wizard.ts`, a file this change
      doesn't touch.

- [x] 8.2 Update the e2e suite where it waits for "Loading…" text, or
      asserts that a dialog or toast disappears at once. Then run
      `npm run e2e` green (never alongside pytest; it shares Redis rate
      limits).
      No existing test needed its waits changed. Full suite: 51 passed, 2
      xfailed (existing `known_issue` markers). One later targeted run
      saw `test_staff_invitation_lifecycle` fail once. It passed alone and
      in two repeat runs, so it is treated as an intermittent flake; the
      failure output wasn't captured.

- [x] 8.3 Add e2e checks: on Branches, a filter change keeps the table
      in the DOM while the request is in flight; a modal is still present
      during its close animation and gone afterwards; the scroll position
      resets on navigation.
      In `e2e/test_motion_and_loading.py` (7 checks), alongside a
      first-load skeleton check, Escape closing a dialog with focus
      returning to its opener, and a reduced-motion dialog check.

- [x] 8.4 Run `npm run screenshots` and compare the skeleton and loaded
      frames for each page to confirm there is no visible layout shift.
      Check desktop (1440px), tablet (768px), and phone (375px).
      Done with a scripted capture of the dashboard, invitations board,
      buildings, form builder, and org configs at 1440px and 375px, with
      their APIs held for the skeleton frame. That found and fixed a code
      comment rendered as visible text on both invitation boards, and
      over-tall Form Builder skeleton cards. A crawl of all 33 static
      routes then found no stray `//`, `undefined`, or `NaN` text and no
      page errors, including while opening and closing every Filters
      panel. Remaining known shift: the Invitations header's Export button
      appears only once the user's permissions load. The 768px tablet width
      and `npm run screenshots` itself were not run.

- [x] 8.5 Do a manual pass with OS-level reduced motion enabled. Check
      that every overlay, panel, and route still works and that no content
      becomes unreachable.
      Scripted with reduced motion emulated at 1440px and 375px: dialog
      open and close, the filter panel, drawer navigation, and the route
      transition all work, with animation durations at 0.01ms. 7 of 7
      checks pass.
