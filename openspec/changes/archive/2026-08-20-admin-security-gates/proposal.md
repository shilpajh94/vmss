## Why

Admins currently have no way to register or manage the physical security gates and turnstiles that control building access. The sidebar already reserves a "Security Gates" nav slot, but activating it does nothing yet. The Figma design (node `203:1418`, "Security Gates & Turnstiles") specifies the screen needed to close this gap.

## What Changes

- Add a new **Security Gates & Turnstiles Register** admin screen at `/admin/security-gates` listing each gate's name/ID, building, floor, gate type (Bidirectional / Entry Only / Exit Only / High Security), auth method, and connectivity status (Online / Maintenance / Offline), with per-row Edit and Delete actions.
- Add dedicated **Register Gate** (`/admin/security-gates/new`) and **Edit Gate** (`/admin/security-gates/:id/edit`) pages, mirroring the existing admin-reception-desks form pattern: gate name/ID, building (from existing buildings), floor (from the selected building's floors), gate type, auth method (free text), and connectivity status.
- Wire the reserved `security-gates` sidebar item to navigate to the new list page.
- Add the full data layer for security gates: domain schema, repository port, infrastructure adapter, use cases (list/create/update/delete), API endpoints, and composition-root wiring, following the existing branches/departments/buildings/floors/reception-desks pattern.
- Display (non-functional) "Filters" affordance per the design, consistent with how Filters is presented on the other admin register screens.

## Capabilities

### New Capabilities
- `admin-security-gates`: Super Admin screen to view, add, edit, and delete security gates/turnstiles, each associated with a building and, optionally, a floor.

### Modified Capabilities
(none — no existing capability's requirements change)

## Impact

- New: `src/domain/entities/security-gate-schema.ts` (+ `security-gate-out-schema.ts` wire schema), `src/data/repositories/security-gate-repository.ts`, `src/data/use-cases/{list,create,update,delete}-security-gate.ts`, `src/infrastructure/security-gate-repository.ts`.
- Modified: `src/data/api/api-endpoints.ts` (new `LIST/CREATE/UPDATE/DELETE_SECURITY_GATE` entries), `src/composition-root.ts` (new lazy resolvers + `AppDependencies` entries), `src/App.tsx` (three new routes), `src/presentation/components/AdminSidebar.tsx` (`handleActivate` case for `security-gates`).
- New presentation: `src/presentation/pages/admin-security-gates/` (list page, form page, `Components/SecurityGatesTable.tsx`, `hooks/use-admin-security-gates.ts`, `hooks/use-admin-security-gate-form.ts`), following the `admin-reception-desks` folder shape.
- Depends on existing `admin-buildings` and `admin-floors` data (buildings/floors lists) for the form's relational dropdowns.
