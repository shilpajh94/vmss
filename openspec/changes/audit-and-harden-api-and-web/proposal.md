## Why

A read-only audit of every page (2026-10-20, web at `bd887e2`) found several
problems in the web app:
- **Data-integrity bugs.** Adding one employee re-posts the whole roster to
  the API's replace-all sync, deactivating anyone past the first 100. Admin
  lists sent without a token read the default tenant. Edits to branch codes
  and parent selects are silently dropped.
- **Functional gaps.** Error messages from the API are hidden behind generic
  toasts. Tracking statuses are mapped to values the API no longer uses.
  Dead buttons remain.
- **Performance waste.** Every 10-second poll re-fetches the current user and
  all option lists. The board makes one request per card. The public pages
  ship a 1.18 MB bundle that includes Firebase.
- **Accessibility failures.** Some controls show no focus indicator, and
  `text-faint` fails contrast.
- **Responsive breakage.** The form-builder field row breaks at 360px,
  inputs under 16px make phones zoom, and long file names are clipped.

This change fixes all of that without changing what each page does for its
users.

This is the **web half of a paired change**. The shared design, the
decisions D1–D15 and the gap register live in
`VMSS_API/openspec/changes/audit-and-harden-api-and-web/design.md`. The API
half must reach its §4 (additive fields: `permissionCodes`, the list-item
visit date/time and `currentApprovalStep`, and detail devices) before this
half's §3 and §4 can start. This change also replaces the stale
`optimize-web-code-reuse-and-performance` (0/44); see D15.

## What Changes

**P0: data-integrity and contract bugs**
- Create an employee through `POST /auth/employees` instead of re-posting the
  roster to `/auth/employees/sync`.
- Send the session token on every master-data request whenever one exists.
- Make Branch Code and the parent Branch/Building selects read-only on edit,
  since the API ignores those fields there.
- Save the default timezone as an IANA name.
- Remap tracking statuses to the API's real enum.
- Accept the nullable `purposeOfVisit`/`submittedAt` without failing the
  whole list.
- Read the detail's existing `customFields` for primary-contact answers.
- Submit and display the purpose-of-visit **label**, not its slug (QA F11).
- Filter inactive visitor categories and inactive employees out of pickers,
  and page through option lists beyond 100 entries.

**P1: functional fixes using existing APIs**
- Show the API's validation and conflict messages instead of "Something went
  wrong".
- Stop trimming passwords.
- Tell credential, rate-limit and network failures apart at login.
- Call `POST /auth/logout` on sign-out.
- After sign-in, return to the page that was originally requested (deep
  links from push and email).
- Add a not-found route.
- Guard admin and staff routes once, at the layout, by permission (QA F7),
  using the API's new `permissionCodes`.
- Hide actions the caller isn't permitted to use, such as "Register visitor"
  for Security.
- Add an unsaved-changes guard to the wizards, the long admin forms and the
  form-builder field panel.
- Respect the API's `maxLength` limits and validate email and phone formats.
- Block reschedule dates in the past in the UI.
- Mark required fields (QA F12).
- Fix the staff Review step, where two sticky bars cover each other.
- Show the board card's schedule and approval level from the list item.
- **Removed dead UI:** the "Import Hosts" stub, the Organisation Configs
  "Filters" stub and logo picker (logo saving isn't supported by the API),
  the disabled "Track via Email", and the `href="#"` footer links (now
  config-driven, hidden when unset). Each is recorded in the gap register.

**P2: performance**
- Lazy-load every route group, load Firebase only after login, and serve the
  hero image as AVIF/WebP.
- Use one `useLiveResource` contract: load reference data once, toast only
  when the initial load fails, and show "retrying" on a failing poll.
- Drop the board's per-card detail fetches.
- Memoize the board cards.
- Load Geist weight 600.

**P2: accessibility (new `accessibility` spec)**
- Visible focus on every control.
- AA contrast for the text tokens.
- Labelled inputs.
- `role="alert"`/`role="status"` on error and loading states.
- No nested interactive elements on the board card.

**P3: responsive polish and consistency**
- Every page-level item from the responsiveness matrix: 16px inputs, 40px
  touch targets, wrapping and truncation, the form-builder row, `dvh`, and
  the top-bar title squeeze.
- Align the motion code to the tokens (no `width`/`padding` animation).
- Shared components: `ErrorState`, `StatusBadge`, `FormPageHeader`/
  `BackButton`, the `moveItem` dnd helper, the unified visitor form entry,
  and `PaginationMetaSchema` adoption.
- Remove `AutocompleteField`, which is unused.

There are no visual redesigns. The only intentional visual change is the
contrast-token darkening (D14).

## Capabilities

### New Capabilities
- `accessibility`: a baseline for focus visibility, colour contrast,
  labelling, live-region announcements and interactive nesting across every
  page.
- `app-performance`: route-level code splitting, a deferred push SDK, a
  public-page bundle budget and an optimised hero image.

### Modified Capabilities
- `app-shell`:
  - only a 401 ends the session; a 403 shows "not permitted" (QA F8);
  - routes and actions are gated by permission;
  - an unknown route shows a not-found page;
  - sign-out revokes the server session;
  - master-data requests carry the token;
  - unsaved input is protected;
  - pickers list every active option.
- `staff-login`:
  - sign-in returns to the originally requested page;
  - the password is sent exactly as typed;
  - failure messages tell the causes apart.
- `live-data-refresh`: a failing background refresh is reported once, as a
  "retrying" state, not a repeating toast; reference data is not re-fetched
  on every poll.
- `async-ui-states`: server-provided validation and conflict messages reach
  the user.
- `admin-host-employees`:
  - creating an employee never alters other employees;
  - the "Import Hosts" stub is removed.
- `admin-branches`: Branch Code is read-only on edit.
- `admin-buildings`, `admin-floors`, `admin-departments`: the parent select
  is read-only on edit.
- `admin-organisation-configs`:
  - the timezone is chosen from IANA zones;
  - the "Filters" stub and the unsaved logo picker are removed.
- `visitor-track-request`:
  - statuses map to the API's lifecycle;
  - the inert "Track via Email" is removed.
- `visitor-request-wizard`: the purpose of visit is submitted as its label.

## Impact

- **Code:**
  - `src/App.tsx` (lazy routes, not-found, guards)
  - `src/presentation/components/{AdminLayout,StaffLayout,AppTopBar,ui/*,invitation-board/*}`
  - `src/presentation/hooks/*` (the new `useLiveResource` and
    `useUnsavedChangesGuard`)
  - every admin list and form hook
  - `src/infrastructure/{host-employee,visit-tracking,staff-auth,organisation-config,visitor-category}-repository.ts`
  - `src/data/api/api-endpoints.ts`
  - `src/domain/entities/*-schema.ts`
  - `src/styles/{theme,fonts,index}.css`
  - `src/assets/images/lobby-hero.*`
- **Dependencies:** none new. Image conversion is a one-off build step;
  `@fontsource/geist/600.css` comes from the already-installed package.
- **API:** consumes the API half's additive fields (`permissionCodes`, the
  list-item `preferredVisitDate`/`preferredVisitTime`/`currentApprovalStep`,
  and detail `checkInDevice`/`checkOutDevice`). Strict
  `PUBLIC_ENDPOINT_HARDENING` on the API has no effect on the web once
  §1 ships.
- **Tests:** unit tests for the new hooks and guards, plus an e2e
  responsive-matrix run (`e2e/test_responsive_matrix.py`) and the existing
  journey suite (`npm run e2e`). These are never run alongside the API's
  pytest.
