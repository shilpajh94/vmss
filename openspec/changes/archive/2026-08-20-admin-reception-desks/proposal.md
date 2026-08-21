## Why

Admins currently have no way to register or manage the physical reception desks (front-desk stations, kiosks, entrance welcoming nodes) where visitors are checked in. The sidebar already reserves a "Reception Desks" nav slot, but activating it does nothing yet. The Figma design (node `203:1249`, "Reception Desks Register") specifies the screen needed to close this gap.

## What Changes

- Add a new **Reception Desks Register** admin screen at `/admin/reception-desks` listing each desk's name, building, floor, assigned receptionist, operating hours, and status (Active / Maintenance / Inactive), with per-row Edit and Delete actions.
- Add dedicated **Add Reception Desk** (`/admin/reception-desks/new`) and **Edit Reception Desk** (`/admin/reception-desks/:id/edit`) pages, mirroring the existing admin-departments/admin-floors form pattern: desk name, building (from existing buildings), floor (from the selected building's floors), assigned receptionist (optional, from existing host employees), operating hours (from/to), and status.
- Wire the reserved `reception-desks` sidebar item to navigate to the new list page.
- Add the full data layer for reception desks: domain schema, repository port, infrastructure adapter, use cases (list/create/update/delete), API endpoints, and composition-root wiring, following the existing branches/departments/buildings/floors pattern.
- Display (non-functional) "Filters" affordance per the design, consistent with how Filters is presented on the other admin register screens.

## Capabilities

### New Capabilities
- `admin-reception-desks`: Super Admin screen to view, add, edit, and delete reception desks, each associated with a building, an optional floor, and an optional assigned receptionist.

### Modified Capabilities
(none — no existing capability's requirements change)

## Impact

- New: `src/domain/entities/reception-desk-schema.ts`, `src/data/repositories/reception-desk-repository.ts`, `src/data/use-cases/{list,create,update,delete}-reception-desk.ts` (or a combined use-case module, per existing convention), `src/infrastructure/reception-desk-repository.ts`.
- Modified: `src/data/api/api-endpoints.ts` (new `LIST/CREATE/UPDATE/DELETE_RECEPTION_DESK` entries), `src/composition-root.ts` (new lazy resolvers + `AppDependencies` entries), `src/App.tsx` (three new routes), `src/presentation/components/AdminSidebar.tsx` (`handleActivate` case for `reception-desks`).
- New presentation: `src/presentation/pages/admin-reception-desks/` (list page, form page, `Components/ReceptionDesksTable.tsx`, `hooks/use-admin-reception-desks.ts`, `hooks/use-admin-reception-desk-form.ts`), following the `admin-departments` folder shape.
- Depends on existing `admin-buildings`, `admin-floors`, and `admin-host-employees` data (buildings/floors/host-employees lists) for the form's relational dropdowns.
