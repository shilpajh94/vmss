# Changelog

## Unreleased — Export invitations (`add-invitation-export`)

- New **Export** button on `/admin/invitations` (Admin, in the title row) and on `/staff/dashboard` (Reception only, at the end of the filter bar; hosts don't see it). It opens an **Export invitations** dialog with a Status choice (prefilled from the admin board's Status filter), optional From/To dates, and CSV or Excel. The board's search, purpose, type and source filters also apply, and the dialog lists them.
- The date range applies to the chosen status's date (for example the check-in date for Checked-in), or the created date for All statuses. From later than To is blocked in the dialog.
- The file downloads as `invitations-<status|all>-<YYYYMMDD>.csv|xlsx`, one row per visitor. If the API rejects an export (for example too many rows), the dialog stays open and shows the message.
- Needs VMSS_API's `add-invitation-export` (`GET /invitations/export`) and its tenant migration granting `invitations:export`.
- **Responsive fix:** the board filter bar now wraps when its controls don't fit, instead of forcing one row and clipping. This fixes the admin Source dropdown at 1280px and "Clear filters" at 1280–1440px (both already broken before this change), and keeps the staff Export button visible at 1024px.
- Shared helpers: `saveBlob` (now also used by audit-trail downloads), and `invitation-board/filter-options.ts` for the status, source and registration-type option lists. `BoardFilterBar` gains an optional `trailingAction` slot.

## Unreleased — Admin Invitations filter bar (`align-admin-invitations-filter-bar`)

- `/admin/invitations` now uses the same inline search-and-filter bar as the staff dashboard (shared `BoardFilterBar`): a 40px search with Purpose, Registration Type, Status and Source dropdowns always visible, on one row from `xl` up. The "Filters" toggle and its pop-open panel are gone.
- Admins can now filter by Purpose of Visit. "Clear filters" resets all four dropdowns and keeps the search text.

## Unreleased — Visits board declutter (`declutter-visits-board`)

- Visit cards on `/staff/dashboard` and `/admin/invitations` now show only their deciding actions as labelled buttons (Approve/Deny side by side, or Check Out). Visitor info, Reschedule, Edit and Delegate are a row of compact icon buttons on each card, each with a tooltip on hover and focus.
- **Clicking a card now opens Visitor Info**; cards no longer expand. Approval progress is on the card's "Level X/Y · Pending" badge. `?invitationId=` notification links open Visitor Info.
- Denser card layout (name + REQ ID beside the avatar, one truncated purpose · host line, scheduled time under it), tighter column spacing, and a slimmer staff-dashboard header whose search and filters share one row on desktop.
- `DropdownFilter` is now 200px wide from `sm` up (was 220px); this also affects the audit-trail filter bar.

## Unreleased — `feature/admin-features` (uncommitted working tree changes)

_Documents the changes currently sitting uncommitted on top of `96cde92` ("changes"). 60 modified/deleted files, 3 new files. Recorded 2026-08-24._

### Admin login route rename: `/staff/login` → `/admin/login`

- `src/App.tsx` — `StaffLoginPage` is now routed at `/admin/login` instead of `/staff/login`.
- Every admin/staff page hook's "no session token → redirect" guard now points at `/admin/login` instead of `/staff/login`:
  `use-admin-branch-create.ts`, `use-admin-branches.ts`, `use-admin-building-form.ts`, `use-admin-buildings.ts`,
  `use-admin-dashboard.ts`, `use-admin-department-form.ts`, `use-admin-departments.ts`, `use-admin-floor-form.ts`,
  `use-admin-floors.ts`, `use-admin-host-employee-form.ts`, `use-admin-host-employees.ts`,
  `use-admin-organisation-configs.ts`, `use-admin-reception-desk-form.ts`, `use-admin-reception-desks.ts`,
  `use-admin-security-gate-form.ts`, `use-admin-security-gates.ts`, `use-admin-visitor-categories.ts`,
  `use-admin-visitor-category-form.ts`, `use-staff-audit-trail.ts`, `use-staff-dashboard.ts`,
  `staff-visitor-registration.tsx`.
- The login screen's copy changed from "Staff Portal" / "STAFF GATEWAY" to "Admin Portal" / "ADMIN GATEWAY"
  (`LoginFormCard.tsx`, `StaffGatewayHeader.tsx`).
- `openspec/specs/staff-login/spec.md` updated to match: the "Staff login screen is reachable at a dedicated route"
  requirement now targets `/admin/login`, with a new scenario asserting `/staff/login` no longer serves the login
  screen, and a new requirement that any expired/unauthorized session redirects to `/admin/login`.
- The `openspec/changes/staff-password-login/` proposal (design/proposal/tasks/spec files) was deleted from the
  active changes directory — its work is complete and reflected directly in `openspec/specs/staff-login/spec.md`.
  Two archived copies now exist under `openspec/changes/archive/` (untracked, not yet `git add`ed):
  `2026-08-24-staff-password-login/` and `2026-08-24-rename-staff-login-to-admin-login/`.

### Sign-out added to the admin top bar

- `src/presentation/components/AdminTopBar.tsx` — adds a "Sign out" button that clears `sessionStorage['token']`
  and navigates to `/admin/login`. Previously only the staff dashboard, audit trail, and visitor-registration
  pages exposed sign-out; the shared admin top bar (used by every `/admin/*` page) now does too.

### Host employee creation moved from a per-employee create call to a directory sync

The backend dropped its per-employee create endpoint (`POST /auth/users`) in favor of a company-wide roster sync
(`POST /auth/employees/sync`) that replaces the entire employee list in one call — there is no more per-employee
password.

- `src/data/api/api-endpoints.ts` — `CREATE_HOST_EMPLOYEE` (`/auth/users`) replaced by `SYNC_EMPLOYEES`
  (`/auth/employees/sync`).
- New `src/domain/entities/employee-sync-schema.ts` (untracked, new file) — `EmployeeSyncItemSchema`,
  `EmployeeSyncResultSchema` (`created`/`updated`/`deactivated`), `EmployeeSyncResponseSchema`.
- `src/domain/entities/host-employee-schema.ts` — `HostEmployeeCreateInputSchema` drops `password`, adds
  `employeeCode` (required), `phoneNumber`, `designation`, `departmentId` (all optional).
- `src/infrastructure/host-employee-repository.ts` — `create()` now: fetches the current roster via `list()`,
  appends the new employee to it, POSTs the full roster to `SYNC_EMPLOYEES`, re-fetches the roster, and finds the
  newly created employee by email to return it (then assigns a role/branch if requested). This is a fan-out
  workaround for the missing per-employee endpoint, not a design choice — adding one employee costs a full
  roster round-trip.
- `src/presentation/pages/admin-host-employees/admin-host-employee-form.tsx` and
  `hooks/use-admin-host-employee-form.ts` — the "Temporary Password" field (with its "Generate" button) is
  replaced by "Employee Code" (required), "Designation," "Phone Number," and a "Department" select
  (previously disabled with a "not supported by the backend yet" note — department assignment now works).

### Organisation logo upload removed — backend has no file storage endpoint

- `src/data/api/api-endpoints.ts` — `UPLOAD_ORGANISATION_LOGO` endpoint removed.
- `src/domain/entities/upload-response-schema.ts` — deleted.
- `src/data/use-cases/upload-organisation-logo.ts` — deleted.
- `src/data/repositories/organisation-config-repository.ts` / `src/infrastructure/organisation-config-repository.ts`
  — `uploadLogo()` removed from the port and adapter.
- `src/composition-root.ts` — `uploadOrganisationLogoUseCase` removed from `AppDependencies` and its resolver.
- `use-admin-organisation-configs.ts` / `admin-organisation-configs.tsx` / `GeneralInformationCard.tsx` — picking a
  logo file now only creates a local `URL.createObjectURL` preview (`previewLogo`/`logoPreview`/`setLogoPreview`);
  nothing is uploaded or persisted. The helper text now says the preview isn't saved until the backend adds file
  storage support.

### Reception desk: schema now matches the real backend contract

- `src/domain/entities/reception-desk-out-schema.ts` — `buildingId` removed (a desk's building is derived from its
  floor); `floorId` is now required, not nullable; adds `code` (required); `receptionistUserId` renamed to
  `assignedReceptionistUserId`.
- `src/domain/entities/reception-desk-schema.ts` — `floorId` is now required (was optional); adds `code` (required).
- `src/infrastructure/reception-desk-repository.ts` — building name/id are now looked up via the desk's floor
  (`floorById` map) rather than being sent/received directly; create/update payloads drop `buildingId` and add
  `code`/`status`/`assignedReceptionistUserId`; a comment notes the update contract has no `floorId` field (a
  desk's floor can't change after creation).
- `admin-reception-desk-form.tsx` / `use-admin-reception-desk-form.ts` — adds a required "Desk Code" field; "Floor"
  is now required (was optional); both "Building" and "Floor" selects are disabled in edit mode (can't be changed
  after creation); reception desks table gains a "CODE" column.

### Security gate: schema now matches the real backend contract; floor removed, branch/highSecurity added

- `src/domain/entities/security-gate-out-schema.ts` / `security-gate-schema.ts` — `floorId`/`floorName` removed
  entirely (gates are no longer per-floor); `buildingId` is now nullable on the wire; adds `branchId` (wire-only,
  used to resolve which branch a gate belongs to), `code` (required), `highSecurity: boolean`; `gateType` enum
  changed from `bidirectional | entry_only | exit_only | high_security` to `entry | exit | both` (high-security is
  now the separate `highSecurity` boolean instead of a gate type).
- `src/infrastructure/security-gate-repository.ts` — no longer depends on `FloorRepository`; `create()` looks up
  the building's `branchId` and sends it (throws if the building has no branch); a comment notes the update
  contract has no `branchId` field (a gate's branch can't change after creation).
- `src/composition-root.ts` — `HttpSecurityGateRepository` is now constructed with just `(apiClient,
  buildingRepository)`, no `floorRepository`.
- `admin-security-gate-form.tsx` / `use-admin-security-gate-form.ts` — floor selection removed entirely; adds a
  required "Gate Code" field and a "High Security" `ToggleSwitch`; gate type options reduced to Entry/Exit/Both.
- `SecurityGatesTable.tsx` — "FLOOR" column removed, "CODE" column added; the gate-type badge and a separate
  "High Security" badge are now shown side by side (previously high-security was one of the gate-type values).

### Visitor category: free-text fields replaced with enums, added `code` and numeric duration

- `src/domain/entities/visitor-category-out-schema.ts` / `visitor-category-schema.ts` — adds `code` (required);
  `ndaRequired`/`escortRequired` (free-text strings) replaced by `ndaRequirement: "digital" | "signed_pdf" |
  "optional" | "none"` and `escortRequirement: "self_escort" | "access_logs_only" | "always_required" |
  "gate_check_in_only"`; `maxDuration` (free-text string) replaced by `maxDurationMinutes: number`.
- `src/infrastructure/visitor-category-repository.ts` — maps/sends the renamed and re-typed fields.
- `admin-visitor-category-form.tsx` / `use-admin-visitor-category-form.ts` — "NDA Required" and "Escort Required"
  are now `SelectField` dropdowns instead of free-text inputs; "Max Duration" is now a number input (minutes)
  instead of free text; adds a required "Category Code" field.
- `VisitorCategoriesTable.tsx` — adds a "CODE" column; NDA/escort values are rendered via label lookup tables
  instead of raw strings; max duration is formatted from minutes (e.g. "8 hr" / "45 min").

### Environment / build config

- `.env.example` and `vite.config.ts` — `VITE_API_BASE_URL` / dev-server proxy target changed from
  `https://vmss-dev.mypits.org` to `https://vmss-new-api.ddev.site:8443`, pointing local dev at the new backend
  that the above contract changes were written against.

### Small shared-UI changes

- `src/presentation/components/ui/SelectField.tsx` — adds a `disabled` prop (used to lock the reception desk
  form's Building/Floor selects in edit mode).

### New/moved OpenSpec artifacts (untracked)

- `openspec/changes/archive/2026-08-24-staff-password-login/` and
  `openspec/changes/archive/2026-08-24-rename-staff-login-to-admin-login/` — archived OpenSpec change proposals
  for the password-login and `/admin/login` rename work described above. Not yet staged.
