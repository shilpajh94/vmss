## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/building-schema.ts` with `CheckpointSchema` (id, name), `FloorSchema` (id, name, checkpoints: `Checkpoint[]`), `BuildingSchema` (id, name, branchId, branchName, streetAddress optional, status: `'active' | 'inactive'`, receptionDesks optional, floors: `Floor[]`), their `z.infer` types, and a `BuildingInputSchema`/type for create/edit payloads (name, branchId, streetAddress optional, status, floors) that excludes `id`, `branchName`, and `receptionDesks`

## 2. API endpoints

- [x] 2.1 Add `LIST_BUILDINGS` (`GET /buildings`, `hasToken: true`), `CREATE_BUILDING` (`POST /buildings`, `hasToken: true`), `UPDATE_BUILDING` (`PUT /buildings`, `hasToken: true`, id via query param), `DELETE_BUILDING` (`DELETE /buildings`, `hasToken: true`, id via query param) to `src/data/api/api-endpoints.ts`

## 3. Repository port, adapter, use cases

- [x] 3.1 Add `src/data/repositories/building-repository.ts` with `BuildingRepository` interface: `list(): Promise<Building[]>`, `create(input: BuildingInput): Promise<Building>`, `update(id: string, input: BuildingInput): Promise<Building>`, `remove(id: string): Promise<void>`
- [x] 3.2 Add `src/infrastructure/building-repository.ts` implementing `BuildingRepository` via `ApiClient.makeRequest` against the new endpoints and schema (list returns `z.array(BuildingSchema)`)
- [x] 3.3 Add `src/data/use-cases/list-buildings.ts` (`ListBuildingsUseCase`)
- [x] 3.4 Add `src/data/use-cases/create-building.ts` (`CreateBuildingUseCase`)
- [x] 3.5 Add `src/data/use-cases/update-building.ts` (`UpdateBuildingUseCase`)
- [x] 3.6 Add `src/data/use-cases/delete-building.ts` (`DeleteBuildingUseCase`)

## 4. Composition root

- [x] 4.1 Wire `resolveBuildingRepository`, `resolveListBuildingsUseCase`, `resolveCreateBuildingUseCase`, `resolveUpdateBuildingUseCase`, `resolveDeleteBuildingUseCase` in `src/composition-root.ts` and expose the four use cases on `AppDependencies`

## 5. Sidebar wiring

- [x] 5.1 Add a `buildings` case to `AdminSidebar.tsx`'s `handleActivate` that navigates to `/admin/buildings`

## 6. Buildings list page

- [x] 6.1 Add `src/presentation/pages/admin-buildings/hooks/use-admin-buildings.ts`: auth-token gate, loads current staff user + building list, exposes loading/error/retry, `requestDelete`, `cancelDelete`, `confirmDelete` (mirrors `use-admin-departments.ts`)
- [x] 6.2 Add `src/presentation/pages/admin-buildings/Components/BuildingsTable.tsx`: table header (Building Name, Branch, Address, Total Floors, Reception Desks, Status, Actions), one row per building with `floors.length` as the floor count, an Active/Inactive badge, and Edit/Delete icon buttons (Edit navigates to `/admin/buildings/:id/edit`)
- [x] 6.3 Add `src/presentation/pages/admin-buildings/admin-buildings.tsx`: renders `AdminSidebar` (`activeItem="buildings"`), `AdminTopBar` (description mode), content header ("Buildings Registry" title, inert "Filters", "Add Building" navigating to `/admin/buildings/new`), `LoadingState`/inline-error-with-retry/`EmptyState`/`BuildingsTable` depending on state, and a `ConfirmDialog` for delete

## 7. Add/Edit Building page: floor and checkpoint modals

- [x] 7.1 Add `src/presentation/pages/admin-buildings/Components/FloorModal.tsx`: `Modal`-based form with a single Floor Name `TextField`, used for both adding and renaming a floor
- [x] 7.2 Add `src/presentation/pages/admin-buildings/Components/CheckpointModal.tsx`: `Modal`-based form with a single Checkpoint Name `TextField`, used for both adding and renaming a checkpoint

## 8. Add/Edit Building page: hook and page

- [x] 8.1 Add `src/presentation/pages/admin-buildings/hooks/use-admin-building-form.ts`: auth-token gate; reads an optional `:id` route param — when present, loads that building via `listBuildingsUseCase` and pre-fills the form (name, branchId, streetAddress, status, floors with their checkpoints) in edit mode, otherwise starts with an empty name/branch/address, status "active", and an empty floors array in add mode; loads the branch list via `listBranchesUseCase` for the Branch dropdown; tracks per-floor expand/collapse state keyed by floor id; exposes `updateField`, floor operations (`openAddFloorModal`, `openEditFloorModal(floor)`, `closeFloorModal`, `saveFloor(name)` — adds with a `crypto.randomUUID()` id or renames depending on modal mode, `requestDeleteFloor(floor)`, `cancelDeleteFloor`, `confirmDeleteFloor`, `toggleFloorExpanded(floorId)`), checkpoint operations scoped to a floor (`openAddCheckpointModal(floorId)`, `openEditCheckpointModal(floorId, checkpoint)`, `closeCheckpointModal`, `saveCheckpoint(name)`, `requestDeleteCheckpoint(floorId, checkpoint)`, `cancelDeleteCheckpoint`, `confirmDeleteCheckpoint`), `submit` (validates name/branch required, calls create or update depending on mode with the current floors array, on success navigates to `/admin/buildings` and toasts success, on failure toasts error and keeps entered values), and `cancel` (navigates to `/admin/buildings`)
- [x] 8.2 Add `src/presentation/pages/admin-buildings/Components/FloorCard.tsx`: renders a floor's name, expand/collapse chevron, Edit/Delete icon buttons, and — when expanded — the "Security Checkpoints" sub-header with "Add Checkpoint" and a list of checkpoint items (name + "Security checkpoint" subtitle, Edit/Delete icon buttons)
- [x] 8.3 Add `src/presentation/pages/admin-buildings/admin-building-form.tsx`: renders `AdminSidebar` (`activeItem="buildings"`), `AdminTopBar` (description mode), a back button + "Add Building"/"Edit Building" header, a form card with "Building Details" (Building Name, Branch `SelectField` populated from the loaded branch list, Street Address, Building Status `ToggleSwitch`) and "Floors" (header with "Add Floor", list of `FloorCard`s) sections, Cancel/Save Building footer actions, `FloorModal`, `CheckpointModal`, and `ConfirmDialog`s for floor/checkpoint deletion

## 9. Routing

- [x] 9.1 Add `/admin/buildings`, `/admin/buildings/new`, and `/admin/buildings/:id/edit` routes to `src/App.tsx`

## 10. Verification

- [x] 10.1 Run the dev server and visually compare `/admin/buildings` and `/admin/buildings/new` against the Figma designs (nodes `203:553` and `218:66`) for layout, spacing, and color fidelity, including a floor expanded and collapsed
- [x] 10.2 Manually verify: Buildings nav item navigates, list load/error/retry, empty state, Add Building navigation + validation + success + failure, Branch dropdown populated from real branch data, add/rename/delete a floor, expand a floor and add/rename/delete a checkpoint, Edit pre-fills every field including floors/checkpoints and updates, Delete confirm/cancel/success/failure, inert Filters
- [x] 10.3 Run lint/type-check and any existing test suite
