## Context

See `proposal.md` - Why. Relevant existing conventions this design builds on (see `.claude/rules/clean-architecture.md` and `.claude/rules/data-api-layer.md`):

- The Staff portal already has an analogous shell: `DashboardSidebar` (`src/presentation/components/DashboardSidebar.tsx`) + a `WorkspaceHeader`-style top bar per page, gated by a `sessionStorage` token checked in a page hook (see `use-staff-dashboard.ts`), with `GetCurrentStaffUserUseCase` supplying the signed-in user's name/role.
- Shared form primitives already exist under `src/presentation/components/ui/`: `TextField`, `SelectField`, `FileUploadField` (with built-in type/size validation and an `onUpload` callback returning a `fileRef`), `LoadingState`, `EmptyState`. No on/off switch component exists yet.
- The toast system (`src/presentation/components/toast/toast-context.tsx`, `useToast()`) is the established pattern for success/error notifications alongside inline error states.
- `FileUploadField.onUpload` mirrors `UploadVisitorDocumentUseCase`: it takes a `File`, calls a use case that hits an upload endpoint via `ApiClient.uploadFile`, and returns a `fileRef` string.
- The Figma design (node `203:8`) uses a teal accent (`#0b8b84`) for the sidebar logo mark, active nav item, toggle, and primary button — this differs from the app's existing `--color-secondary-accent` token (`#06b6d4`, cyan), which the Staff portal (login, dashboard, audit trail) already relies on.

## Goals / Non-Goals

**Goals:**
- Stand up the Admin section shell (sidebar + top bar) as shared, reusable presentation code so later admin pages (Branches, Departments, etc.) can adopt the same sidebar without rework.
- Implement the Organisation Configs page to match the Figma design pixel-for-pixel, using the project's existing clean-architecture layering (domain schema → repository port → infrastructure adapter → use case → hook → page).
- Reuse existing shared UI primitives (`TextField`, `SelectField`, `FileUploadField`, `LoadingState`, toasts) wherever the design's inputs match their behavior.

**Non-Goals:**
- No separate admin authentication/authorization system — this change reuses the existing staff auth token and does not add role-based access control.
- No implementation of the other nine sidebar destinations (Dashboard, Branches, Departments, Buildings, Floors, Reception Desks, Security Gates, Host Employees, Visitor Categories) or of workspace search/notifications — these render per the design as inert affordances only, matching the existing "visible but not yet functional" pattern used for Staff dashboard's "Help & Support" and "Filters".
- No backend implementation — this change assumes the three new endpoints exist and defines only their expected request/response shape via the new Zod schema.

## Decisions

- **New `AdminSidebar` component instead of extending `DashboardSidebar`.** The Admin nav item set (10 items, admin-specific icons) is entirely different from the Staff nav item set (3 items). Reusing `DashboardSidebar` would require overloading its `activeItem` union and icon map with unrelated items. A separate `src/presentation/components/AdminSidebar.tsx`, built the same way (icon+label array, `activeItem` prop, `useNavigate` for the one wired item), keeps both sidebars simple and independently evolvable, and gives future admin pages a ready-made shared component.
- **Scoped teal accent token, not a global token change.** Introduce `--color-admin-accent: #0b8b84` (and reuse existing neutrals for the dark sidebar: `--color-primary` for `#0f172a`, `#334155`/`#94a3b8` as one-off values consistent with how `DashboardSidebar` already uses literal hex for its own dark-sidebar shades) in `src/styles/theme.css`, and apply it only within `AdminSidebar` and the Organisation Configs page. Alternative considered: reuse `--color-secondary-accent` and accept the color drift from Figma, or repaint `--color-secondary-accent` app-wide to the Figma teal — rejected because the task calls for pixel parity with this Figma screen specifically, and repainting the shared token would silently change the already-shipped Staff login/dashboard/audit-trail screens.
- **New `ToggleSwitch` shared UI component.** None of the existing `ui/` primitives render an on/off switch (`Checkbox` is a checkbox with a label, `SegmentedToggle` is a multi-option segmented control). Add `src/presentation/components/ui/ToggleSwitch.tsx` with a `{ checked, onChange, label }` API consistent with `Checkbox`'s prop shape, so it composes the same way in a form.
- **Logo upload reuses the `FileUploadField` + `onUpload` pattern from visitor document upload.** `UploadOrganisationLogoUseCase` wraps a new `uploadLogo(file): Promise<UploadResponse>` method on `OrganisationConfigRepository`, mirroring how `VisitRequestRepository.uploadDocument` backs `UploadVisitorDocumentUseCase`. The adapter calls `ApiClient.uploadFile` against `UPLOAD_ORGANISATION_LOGO`. On success, the returned `fileRef` is stored as the pending logo value; it is only persisted org-wide when "Save Configs" is activated (upload and save are separate network calls, matching the design's two independent actions).
- **One `OrganisationConfigSchema` covers both cards.** Even though the design splits the form into "General Information" and "Visitor Policy & Security" cards, both map to a single organisation configuration resource (one GET, one PUT) — there is no indication these are separate backend resources, and splitting them would double the network calls for a single save action.
- **Form state and dirty-tracking live in a page hook** (`use-admin-organisation-configs.ts`), following the existing `use-staff-dashboard.ts` / `use-staff-audit-trail.ts` pattern: the hook holds the last-loaded/saved config plus the in-progress edited form state, exposes field setters, `save`, and `cancel` (which resets edited state back to the last-loaded/saved config), and drives loading/error/toast side effects.
- **Timezone and badge-expiry options are a fixed, hardcoded list** for this change (no "list options" endpoint exists or is proposed). The Figma design shows one example value per field ("GMT+00:00 (London, Lisbon)", "8 Hours (Standard Business Day)"); the option lists are an implementation-level content decision, not a spec-level behavior, so they are left to `tasks.md`/implementation rather than enumerated in the spec.

## Risks / Trade-offs

- [Two accent tokens (`--color-secondary-accent` cyan, `--color-admin-accent` teal) coexist in the theme] → Acceptable short-term trade-off to keep this change scoped to the Admin section; if a future change unifies Staff and Admin visual language, both call sites can be repainted to a single token then.
- [Hardcoded timezone/duration option lists may not match what the backend ultimately accepts] → `OrganisationConfigSchema` validates the response shape, not the option list; once a real endpoint is available the option lists can be swapped for a fetched list without changing the schema or the page's structure.
- [No admin-specific auth/authorization] → Anyone with a valid staff token can currently reach `/admin/organisation-configs`; acceptable for this change per the Non-Goals above, but should be revisited before this ships to real admins.
