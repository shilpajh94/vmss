## Why

The product needs an Admin area, separate from the existing Staff visitor-management portal, where a Super Admin can configure organisation-wide settings. The first screen of that area — Organisation Configs — is fully specified in Figma (node `203:8`) and must be implemented pixel-accurate to that design so admins can set the organisation's identity, logo, timezone, and visitor/security policy defaults.

## What Changes

- Add a new Admin section (`/admin/...`) with its own persistent sidebar navigation (Dashboard, Organisation Configs, Branches, Departments, Buildings, Floors, Reception Desks, Security Gates, Host Employees, Visitor Categories) and top bar (breadcrumb/title, workspace search, notification bell, signed-in admin profile), matching the Figma layout. Only "Organisation Configs" is wired to a real page in this change — the other nine nav items render per the design but are inert, following the same "visible but not yet functional" pattern already used for the Staff dashboard's "Help & Support" and "Filters" affordances.
- Add the **Organisation Configs** page (`/admin/organisation-configs`) with:
  - A "General Information" card: organisation name, organisation logo upload, default timezone.
  - A "Visitor Policy & Security" card: auto-approve pre-registered visitors toggle, pass badge expiry duration.
  - "Cancel Changes" (resets unsaved edits to the last-loaded values) and "Save Configs" (persists changes) actions.
- Reuse the existing staff auth session (`sessionStorage` token, `GetCurrentStaffUserUseCase`) to gate the Admin section and populate the profile in the top bar, since no separate admin authentication system exists yet.
- Reuse the existing toast system for save success/failure feedback, and the existing `LoadingState`/error-with-retry patterns for the initial config load.
- Add a new shared `ToggleSwitch` UI component (no existing on/off switch component in the design system).

## Capabilities

### New Capabilities
- `admin-organisation-configs`: the Admin section shell (sidebar + top bar) and the Organisation Configs page — viewing and editing organisation name, logo, default timezone, auto-approve policy, and pass badge expiry duration.

### Modified Capabilities
_None — no existing capability's requirements change._

## Impact

- **New route**: `/admin/organisation-configs` in `src/App.tsx`.
- **New presentation code**: `src/presentation/components/AdminSidebar.tsx` (shared for future admin pages), `src/presentation/pages/admin-organisation-configs/` (page, hook, components), `src/presentation/components/ui/ToggleSwitch.tsx`.
- **New domain schema**: `src/domain/entities/organisation-config-schema.ts`.
- **New data layer**: `src/data/repositories/organisation-config-repository.ts` (port), `src/data/use-cases/get-organisation-config.ts`, `src/data/use-cases/update-organisation-config.ts`, `src/data/use-cases/upload-organisation-logo.ts`.
- **New infrastructure**: `src/infrastructure/organisation-config-repository.ts` (adapter), new entries in `src/data/api/api-endpoints.ts` (`GET_ORGANISATION_CONFIG`, `UPDATE_ORGANISATION_CONFIG`, `UPLOAD_ORGANISATION_LOGO`).
- **Composition root**: `src/composition-root.ts` gains `organisationConfigRepository`, `getOrganisationConfigUseCase`, `updateOrganisationConfigUseCase`, `uploadOrganisationLogoUseCase` on `AppDependencies`.
- **No backend changes are made by this change** — it assumes the three new endpoints exist or will be stubbed; exact request/response shapes are defined in the new domain schema.
