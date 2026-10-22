These tasks follow the shared design in `VMSS_API/openspec/changes/audit-and-harden-api-and-web/design.md` (D11–D15) and this repo's `design.md` (D-W1–D-W11).

- **Commits:** one section is one commit.
- **Verify after each section:** `npx tsc --noEmit`, then `npm run lint`, then `npm test` if present.
- **Never run Prettier**, or any formatter across files.
- **`vite.config.ts` is skip-worktree.** Tell the user about any edit to it; it will not reach git.
- **Paths:** relative to `src/presentation/` unless they start with `src/`.

## 0. Baseline

- [x] 0.1 *(Baseline taken 2026-10-22. Build: `index-*.js` 1,185.74 kB raw / 289.63 kB gzipped, `UpcomingVisitorsCard-*.js` 380.16 / 109.72 kB, CSS 120.37 / 39.11 kB. `tsc`: clean. `lint`: clean apart from 2 unused-variable warnings (`use-visitor-request-wizard.ts:80`). Screenshots: `scripts/screenshot-pages.py` at 375/768/1440, 57 files kept outside the repo, all "ok".)* Record the baseline:
  - `npm run build`: the size of every JS chunk, gzipped (today `index-*.js` is 1.18 MB raw);
  - `npx tsc --noEmit` and `npm run lint` output;
  - screenshots at 360, 768 and 1280 px of a list page, the board, a dashboard and the step editor (use `e2e/test_responsive_matrix.py`).
- [x] 0.2 *(Checked against the local API: `branchRoles[].permissionCodes`, list-item `preferredVisitDate`/`preferredVisitTime`/`currentApprovalStep` and detail `checkInDevice`/`checkOutDevice` are all present.)* Confirm the API half's §4 is deployed locally. `/auth/me` returns `branchRoles[].permissionCodes`; `GET /invitations` items carry `preferredVisitDate`, `preferredVisitTime` and `currentApprovalStep`; detail carries `checkInDevice`/`checkOutDevice`. Sections 3, 4 and 7.5 wait on this.

## 1. P0 — Data-integrity and contract bugs

- [x] 1.1 *(The repo had no unit-test runner, so `npm test` was added: `node --test` with a small resolve hook (`scripts/unit-test-loader.mjs`), no new dependency, tests in `tests/unit/`, type-checked through `tsconfig.test.json`. `employee-sync-schema.ts` and `SYNC_EMPLOYEES` are deleted.)* Change `src/infrastructure/host-employee-repository.ts:44-99`: create goes through `POST /auth/employees` with `departmentId`, and the roster-resync path is deleted (D-W7). Make Department required in the employee form. Add a unit test that create never calls `/auth/employees/sync`.
- [x] 1.2 *(A caller's own `Authorization` header (the visitor proof token) is never overwritten.)* Change `src/data/api` `api-client.ts` to attach the bearer token whenever a session exists, even on `hasToken:false` endpoints. A 401 on those endpoints clears the token but does not redirect (D-W2). Add a test.
- [x] 1.3 Make Branch Code read-only on edit (`components/.../BranchFormModal.tsx:86-92`). Make the parent select read-only on edit in `admin-building-form.tsx:87-95`, `admin-floor-form.tsx:70` and `admin-department-form.tsx:78`.
- [x] 1.4 *(ICU lists some zones under pre-rename names (`Asia/Calcutta`), so these are shown by their current names, and a stored zone the browser doesn't list stays selectable.)* Change the timezone select to IANA zones with offset labels, upgrading legacy `GMT±HH:MM` values (D-W8), in `pages/admin-organisation-configs/Components/GeneralInformationCard.tsx:7-14`. Block saving a blank organisation name (`use-admin-organisation-configs.ts:85-99`).
- [x] 1.5 *(Timeline: Submitted → Approved → Checked In → Checked Out. `archived` reads "Expired". An unknown status highlights no step.)* Remap the status values in `src/infrastructure/visit-tracking-repository.ts:1-36` to `submitted`, `approved`, `denied`, `checked_in`, `checked_out` and `archived`, with a neutral tone for unknown values. Fix the timeline positions in `pages/visitor-track/Components/StatusPanel.tsx`.
- [x] 1.6 Make `purposeOfVisit` and `submittedAt` `.nullable()` in `src/domain/entities/visit-request-summary-schema.ts:7,12` and `invitation-detail-schema.ts:85,103`. Update the render sites to show "—" for null.
- [x] 1.7 *(The modal already rendered `customFields` under "Additional details". The fix removes the never-sent `primaryContactCustomFields` and its render.)* Change `components/invitation-board/VisitorInfoModal.tsx:290` to render the detail's `customFields`, and drop the never-sent `primaryContactCustomFields` from the schema.
- [x] 1.8 *(Both wizards share `VisitInfoStep`, whose fallback options now carry labels. `purposeLabel()` maps legacy slugs on the board card, Visitor Info, the calendar chip, the upcoming-visitors card and the edit modal.)* Submit the purpose label instead of the slug, with slug→label display for stored values (QA F11). Affects `pages/visitor-request/Components/steps/VisitInfoStep.tsx:54-55`, the staff wizard equivalent, `EditInvitationModal.tsx:155-160` and the board filter `hooks/use-invitations-board.ts:993`.
- [x] 1.9 *(`list({ activeOnly })`. Pickers pass it. Name lookups don't, so inactive rows still resolve. In edit mode, where the parent picker is read-only, forms load the full list instead of doing a one-off get-by-id. Visitor categories have no server-side status filter, so they filter on `isActive`. Employees and roles are fetched in full, with no active filter.)* Add `fetchAllPages` (D-W9) and use it in every picker repository: host employees, branches, buildings, floors, departments, roles and rules. Pass `status:'active'`, and filter `isActive` in `src/infrastructure/visitor-category-repository.ts:22-54`.
- [x] 1.10 Stop trimming the password (`pages/staff-login/hooks/use-staff-login-page.ts:25`). Map 429 to "too many attempts", and network errors or 5xx to "can't reach the server" (`:44`). Apply the same mapping on the SSO login page.

## 2. P1 — Errors, validation and forms

- [x] 2.1 *(`ApiError` now carries the envelope's `errors[]` as `fieldErrors`; `toUserMessage` leads with the first one, and `apiFieldErrors` puts them next to the field on the branch create form. Applied to every admin form and list-page mutation, the form builder, the audit report and both wizards' submit. The board keeps its own messages: several are deliberate client-side `Error`s.)* Add `toUserMessage(error, fallback)` (D-W5). Use it in every form hook's catch block: `use-admin-branch-create.ts:101`, `use-admin-host-employee-form.ts:147,170,188`, `use-admin-workflow-form.ts:159`, `use-admin-form-builder.ts:107,152,192`, and the building, floor, department, visitor-category and org-config hooks.
- [x] 2.2 *(Limits copied from the API's Create/Update schemas. Number inputs go through a new digit-only `ui/WholeNumberField`. The role create form now uses `TextField`/`TextareaField`, which also covers 7.2's role-form item.)* Add a `maxLength` pass-through to `components/ui/TextField.tsx` and `TextareaField`. Set the API limits on every admin and wizard field: branch 255/50/500/2000, category name 100, role 100/255, notes 2000, and so on, taken from the API schemas.
- [x] 2.3 *(The web has no company email/phone form: Org Configs edits only the name and timezone, so that part is N/A. The employee phone is optional and checked only when entered.)* Validate email and phone format on the branch, host-employee and company forms, and on each wizard step. Trim the full name in both wizards (`use-visitor-request-wizard.ts:115,155-195`, `use-staff-visitor-registration-wizard.ts:62`).
- [x] 2.4 *(Shared `form-builder-key.ts` for steps, fields and groups. Create Step now also keeps its input on failure.)* Fix the form-builder name validation:
  - reject keys that start with a digit or are longer than 100 characters, and names made only of symbols, with inline errors (`use-admin-form-builder.ts:139-153`, `AddFieldModal.tsx:20-59`);
  - `CreateGroupModal.tsx:39-49` resets the input only after a successful save;
  - block a blank label in `FieldPropertiesPanel.tsx:217`.
- [x] 2.5 *(A typed past date is blocked too, since `min` only limits the picker. The edit modal's date also gets `min` today; an empty date or time is sent as `null`.)* In `RescheduleInvitationModal.tsx:59`, set `min` to today for every status. In `EditInvitationModal`, send `null` instead of `''` for an empty date.
- [x] 2.6 *(Deviation: floor number 0 (ground) and negatives (basements) stay valid, matching the API's −20…200; capacity 0 is the API's "not set" and stays valid up to 100,000. Decimals and stray signs can't be typed anywhere. Max duration must be ≥ 1.)* Number inputs: block 0, negatives and decimals for the visitor-category max duration (`admin-visitor-category-form.tsx:123`) and the floor number/capacity (`FloorModal.tsx:66`).
- [x] 2.7 *(`TextareaField` gained `required`; all three fields link errors through `aria-describedby`. Newly marked: branch address, building name/branch/code, floor number, org timezone, role name.)* Mark required fields with `*` plus `aria-required`, starting with the branch Address and the building's branch select (QA F12). Audit every admin form for others.
- [x] 2.8 *(`useBlocker` needs a data router, so `App` now uses `createBrowserRouter` with the existing `<Routes>` under one splat route. One shared discard dialog (`UnsavedChangesProvider`). `useFormPageRefresh` returns the guard, and takes a `baseline` for create forms that render while loading, which fixes F13. Modals guard their close only, since the router honours one blocker. Navigating to a sign-in page is never blocked. The visitor wizard counts only the visitor's own edits, not the returning-visitor prefill.)* Add `useUnsavedChangesGuard` (D-W6). Apply it to both wizards (the staff wizard's Cancel at `staff-visitor-registration.tsx:132` must confirm), every admin create and edit form, the branch modal, the edit-invitation modal and the form-builder step editor's field switching (`use-admin-form-builder-step-editor.ts:99`). Fix `hooks/use-form-page-refresh.ts:24-29` so input typed during loading still counts as dirty.
- [x] 2.9 *(`.env.example` is skip-worktree, so the new keys don't reach git. "Contact System Administrator" uses `VITE_SUPPORT_EMAIL` and is hidden without it.)* Remove the dead UI:
  - "Import Hosts" (`admin-host-employees.tsx:74-80`);
  - Org Configs "Filters", the "notification preferences" text and the logo picker (`admin-organisation-configs.tsx:22-28`, `use-admin-organisation-configs.ts:21-23`);
  - "Track via Email" (`TrackingLookupCard.tsx:47-50`);
  - the `href="#"` links (`PortalFooter.tsx:14,17`, `staff-login.tsx:46`, `StaffLoginFooter.tsx:8,11`, `staff-sso-login.tsx:24`, `StaffSsoLoginFooter.tsx:8,11`). These become config-driven (`VITE_PRIVACY_URL`, `VITE_TERMS_URL`, `VITE_SECURITY_URL`, `VITE_SUPPORT_EMAIL`) and are hidden when unset. `.env.example` is skip-worktree, so tell the user.
- [x] 2.10 *(The icon changes from a check to a plus too.)* Rename the sidebar "My actions" entry to "Register Visitor" (`DashboardSidebar.tsx:18,54`, `ReceptionSidebar.tsx:18,50`).
- [x] 2.11 Remove the unused `components/ui/AutocompleteField.tsx`.

## 3. P1 — Session, routing and permissions (needs API §4)

- [x] 3.1 *(`utils/permissions.ts`: `permissionsFor(user)` gives `can(code, branchId?)` and `canAny`, exposed through `usePermissions()`. The fallback mirrors the API's `rbac_catalog.py` grants for the standard role names and warns once in the console. `isAdmin`/`isReception` stay, but only for the landing page and the staff sidebar choice, which the spec defines by role. Kiosk management, kiosk-location settings and the audit-trail check switched to codes too.)* Extend `CurrentUserContext` with `permissions` and `can()`, falling back to role names when `permissionCodes` is absent (D-W1). Replace the role-name checks in `src/infrastructure/staff-auth-repository.ts:30-37`, `can-manage-devices.ts` and `use-invitations-board.ts:891,897`.
- [x] 3.2 *(The routes are now tables (`ADMIN_ROUTES`/`STAFF_ROUTES`) with a `requires` per page, enforced by `RequirePermission`. The codes live in `route-permissions.ts`, so the sidebars hide the same pages. The admin area also needs any `*:manage` code. A refused user lands on their landing page with a "not permitted" toast. A failed `/auth/me` shows an error with Try again.)* Add a `requires` field to each admin and staff route in `src/App.tsx`. Make the guard in `AdminLayout.tsx`/`StaffLayout.tsx` check the token, then the user, then the permission, rendering a skeleton until that resolves (D-W3, QA F7). Surface `/auth/me` failures instead of only logging them with `console.error` (`AdminLayout.tsx:24-31`).
- [x] 3.3 *(29 guards removed (the other two token reads, the notification centre and push, legitimately check for a session). The `loginPath` parameters they needed are gone from the board, dashboard and calendar hooks.)* Delete the 32 per-hook `sessionStorage.getItem('token')` guards, now covered by 3.2.
- [x] 3.4 *(Board approve, deny, delegate (rides on `invitations:approve`), revert, edit, reschedule, check-out and export each check their own code. Sidebar entries are hidden by their page's code, so Register Visitor needs `invitations:create`. Devices need `devices:manage`.)* Hide actions and navigation by permission: "Register Visitor" needs `invitations:create`; check-out, approve, deny, delegate, revert and export each need their own code; device management too.
- [x] 3.5 *(The API client already kept the session on a 403. The failing call shows the 403's own "no permission" message through its normal error path, and a page the user can't open gets a toast from the route guard. There is no global 403 toast, which would fire on every failing background poll. Covered by a unit test.)* Keep the session on a 403 and show a "not permitted" toast; only a 401 ends the session (`api-client.ts`, `SessionExpiryListener.tsx`) (QA F8).
- [x] 3.6 *(`utils/return-path.ts`. SSO carries the return path through the identity-provider round trip in sessionStorage. A return path into an area the user can't use falls back to their landing page.)* Add a `?from=` return path: capture it in the guards and in `SessionExpiryListener.tsx:27`, validate it as same-origin, and use it after sign-in in both login hooks. Signed-in users who open a login page are redirected to their landing page.
- [x] 3.7 *(Logout and push unregistration run together, capped at 4 s. `STAFF_LOGOUT` is `hasToken: false` (the token is still sent), so an already-expired session doesn't fire the session-expired redirect mid sign-out.)* On sign-out, call `POST /auth/logout` before clearing the local session (`AppTopBar.tsx:150-155`), and ignore a failure.
- [x] 3.8 *(Under `PublicLayout`. It links a signed-in user to their dashboard, and anyone else to the portal.)* Add a catch-all `path="*"` route with a `NotFoundPage` linking home.

## 4. P2 — Live data and the board (needs API §4 for 4.4–4.5)

- [ ] 4.1 Add `useLiveResource` (D-W4) with tests covering: reference data loaded once; a failing poll gives no toast and sets `hasFailed`; recovery clears it; out-of-order responses are ignored.
- [ ] 4.2 Move every admin list hook onto it: buildings, roles, devices, branches, floors, departments, host employees, workflows, kiosks, visitor categories and form builder. Remove each hook's `getCurrentStaffUserUseCase` call (the layout context provides the user).
- [ ] 4.3 Move `use-invitations-board.ts` onto it. Load the current user, roles and host employees once (`:195-208`). Only the initial load toasts (`:218-219`).
- [ ] 4.4 Delete the per-card detail fetch loop (`use-invitations-board.ts:345-369`). Cards read `currentApprovalStep`, `preferredVisitDate` and `preferredVisitTime` from the list item (`VisitRequestCard.tsx:132,176`).
- [ ] 4.5 Visitor Info modal: track per-open loading and error state, always show fresh data (no stale signed URLs), and offer an error with retry (`use-invitations-board.ts:421-429`, `staff-invitations.tsx:289`, `admin-invitations.tsx:293`). Show `checkInDevice`/`checkOutDevice` from the detail.
- [ ] 4.6 Wrap `VisitRequestCard` in `React.memo`, giving it stable callbacks from the hook (`KanbanColumn.tsx:150`).
- [ ] 4.7 Show `FormSkeleton` and an error with retry for reference-data failures in `use-admin-branch-create.ts:50-57`, instead of swallowing them.

## 5. P2 — Bundle and asset performance

- [ ] 5.1 Lazy-load every admin, staff, form-builder and wizard route in `src/App.tsx:13-45`. Add a lazy wrapper that reloads once on a chunk-load error, and use the layouts' skeletons as the Suspense fallback.
- [ ] 5.2 Load `firebase/messaging` with a dynamic `import()` after login (`components/push-notifications/PushNotificationsProvider.tsx:3`, `hooks/use-push-notifications.ts:2`).
- [ ] 5.3 Convert `src/assets/images/lobby-hero.png` to AVIF and WebP, with the PNG as fallback. Use `<picture>`/`srcset` with `fetchpriority="high"` on the landing, login, track and OTP pages.
- [ ] 5.4 In `src/styles/fonts.css`, add the Geist 600 import and drop any font weight nothing uses.
- [ ] 5.5 Add `scripts/check-bundle-budget.mjs` and `npm run build:check` (D-W10). Record the landing-page JS before and after; the target is ≤ 350 KB gzipped.
- [ ] 5.6 Memoise the `Map` in `DepartmentsTable.tsx:20`.

## 6. P2 — Accessibility

- [ ] 6.1 Add visible focus rings:
  - `focus-within:` rings on `ui/DropdownFilter.tsx:25` and the board search (`BoardFilterBar.tsx:57-62`, which also gets an `aria-label`);
  - focus rings on `DelegateInvitationModal.tsx:147`, `DenyInvitationModal.tsx:40` and `RevertApprovalModal.tsx:46`;
  - `peer-focus-visible:` on `ui/ToggleSwitch.tsx:28`.
- [ ] 6.2 Contrast tokens (D-W11): `--color-text-faint` in light and dark mode, plus the new `--color-success-text` used by the Active badges. Check every changed pair with a contrast tool, and get the user's approval on before/after screenshots.
- [ ] 6.3 Add a shared `ui/ErrorState` with `role="alert"`, adopted by `AsyncRegion`, `DashboardLoadError` and the 9 inline "Try again" blocks in the admin `*-form.tsx` files. Add `role="status"` to `ui/LoadingState.tsx`.
- [ ] 6.4 Make the `VisitRequestCard.tsx:135-140` title the one button that opens the detail, so the card stops being `role="button"` with nested buttons and the stopPropagation wrappers at :196 and :232 can go.
- [ ] 6.5 In `TrackingLookupCard.tsx:22`, add a label and `aria-describedby` for the error, and wrap it in a `<form>` so Enter submits. Add the visit count to the day button `aria-label` in `calendar/components/MonthGrid.tsx:63-71`.
- [ ] 6.6 Move the hard-coded hex colours on the public and login pages to tokens. The files are listed in the responsiveness audit B30. These pages stay light-only.

## 7. P3 — Responsive fixes

- [ ] 7.1 `admin-form-builder/Components/SortableFieldRow.tsx:29-97` (**broken on phones**): switch to a two-row layout below `md`, add `truncate` to the label, and make every control at least 40px with a 16px select font.
- [ ] 7.2 Bring inputs to 16px on phones (`max-sm:text-base`) with a 40px minimum height: `TrackingLookupCard.tsx:27`, `otp/OtpRequestScreen.tsx:55`, `otp/OtpVerifyScreen.tsx:55`, the Deny, Revert and Delegate modals, `admin-role-create-form.tsx:59,73` (switch it to `TextField`) and `FieldPropertiesPanel.tsx:81`.
- [ ] 7.3 Stop overflow and clipping:
  - `ui/FileUploadField.tsx:85` gets `min-w-0 break-all`;
  - `ReviewConfirmStep.tsx:107,128` gets `min-w-0 break-words`;
  - `PrimaryContactCard.tsx:103-124` and `InlineFileUpload.tsx:73` become `flex-col sm:flex-row` with `min-w-0` and truncate;
  - permission codes get `break-all` (`admin-role-create-form.tsx:84`, `admin-role-permissions-form.tsx:39`);
  - `RegistrationStepper.tsx:25` labels get truncate.
- [ ] 7.4 Touch targets of at least 40px below `lg`:
  - `BackButton.tsx:19` becomes `size-10 lg:size-9`, and the 7 inline copies switch to `BackButton`/`FormPageHeader`;
  - the `max-lg:min-h-10` pattern on the shared buttons covers `ConfirmDialog`, the list headers and `AuditFilterBar`;
  - `GroupCard.tsx:123`, `FieldPropertiesPanel.tsx:84`, `StepCard.tsx:57,66`, `FloorCard.tsx:25,31,39`, `admin-workflow-form.tsx:103`, the host-employee Revoke button, `KanbanColumn.tsx:192`, `PortalFooter.tsx:13-24`, `MonthGrid.tsx:57,64,90`, `CalendarToolbar.tsx:94`, and the `VehicleInfoStep.tsx:141-178` actions (pinned column).
- [ ] 7.5 Staff Review step: hide the page footer on `review_confirm`, so the two sticky bars stop overlapping (`staff-visitor-registration.tsx:150`). Pass the host card's padding to the sticky bar (`ReviewConfirmStep.tsx:440`). Check in a browser at 375 and 700 px.
- [ ] 7.6 `AppTopBar.tsx:158,186`: below `sm`, move the theme and refresh controls into the avatar/overflow menu, so the page title fits at 360px.
- [ ] 7.7 Smaller items:
  - `ui/SegmentedToggle.tsx` wraps or falls back to a select past 3 options;
  - `ui/Modal.tsx:59` uses `90dvh`;
  - `min-h-screen` becomes `min-h-dvh` (`visitor-request.tsx:346,363,384`, `visitor-track.tsx:13`);
  - the `StepSidebar` shows only from `lg`;
  - the `ToggleSwitch` row stacks on phones (`admin-building-form.tsx:117`, `admin-department-form.tsx:114`);
  - `admin-kiosks.tsx:121` becomes `w-full sm:w-48`;
  - the org-config action row loses its width cap at `lg`;
  - the calendar h1 becomes `text-xl md:text-2xl`;
  - the audit-table phone layout stacks;
  - `StatusPanel` labels are smaller at 320px;
  - `IconActionButton` shows a label below `lg`;
  - the `VisitRequestCard.tsx:19,160` avatar tints become tokens.

## 8. P3 — Consistency and refactors carried over from `optimize-web-code-reuse-and-performance` (D15)

- [ ] 8.1 Add `ui/StatusBadge` and replace the identical markup in the Buildings, Departments, Floors and HostEmployees tables.
- [ ] 8.2 Add `FormPageHeader` (back button and title) to every admin `*-form.tsx`, starting with `admin-building-form.tsx:55-60`.
- [ ] 8.3 Add a `moveItem` helper for the 4 splice-based drag handlers (`admin-form-builder.tsx:91`, `admin-form-builder-step-editor.tsx:94,115`, `FieldPropertiesPanel.tsx:211`).
- [ ] 8.4 Unify `createEmptyVisitorFormEntry` and `createEmptyStaffVisitorFormEntry` into one generic shape.
- [ ] 8.5 Replace the inline pagination shapes in the `*-out-schema.ts` files (`floor-out-schema.ts:28`, `role-out-schema.ts:23`, …) with `PaginationMetaSchema`.
- [ ] 8.6 Motion:
  - `StepProgressHeader.tsx:45` animates `scaleX` instead of `width`;
  - `SidebarFrame.tsx:19` uses the motion tokens;
  - align the route-fade token (`index.css:61` vs `theme.css:106`);
  - derive `utils/motion.ts` from the CSS variables;
  - toasts remove themselves on `animationend`;
  - `EditInvitationModal`/`VisitorInfoModal` use `FormSkeleton` instead of hand-built spinners.
- [ ] 8.7 Remove the D-W1 role-name fallback once the API half is confirmed deployed.
- [ ] 8.8 Delete `openspec/changes/optimize-web-code-reuse-and-performance/`. Do not archive it (D15); confirm with the user first.

## 9. Verification and handoff

- [ ] 9.1 `npx tsc --noEmit`, `npm run lint` and `npm run build:check` all clean.
- [ ] 9.2 Run `e2e/test_responsive_matrix.py` at 360/375/768/1024/1280 across every route in the audit matrix, with no horizontal scroll and no clipped text, and run `npm run e2e` journeys for admin, reception, staff and visitor. Don't run them alongside the API's pytest (shared Redis rate limits).
- [ ] 9.3 Manual keyboard pass: tab through a list page, a form, the board and a wizard, checking that focus is visible and the order is logical.
- [ ] 9.4 Record the before and after bundle sizes and screenshots from §0 in the PR.
- [ ] 9.5 Report the remaining open items to the user, by number from the shared gap register.
