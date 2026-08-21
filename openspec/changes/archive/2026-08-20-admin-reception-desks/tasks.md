## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/reception-desk-schema.ts`: `ReceptionDeskSchema` (`id`, `buildingId`, `buildingName`, `floorId?`, `floorName?`, `name`, `receptionistUserId?`, `receptionistName?`, `operatingHoursFrom?`, `operatingHoursTo?`, `status: "active" | "maintenance" | "inactive"`), `ReceptionDesk` type, and `ReceptionDeskInput = Omit<ReceptionDesk, "id" | "buildingName" | "floorName" | "receptionistName">`.

## 2. API endpoints

- [x] 2.1 Add `LIST_RECEPTION_DESKS` (`GET /reception-desks`), `CREATE_RECEPTION_DESK` (`POST /reception-desks`), `UPDATE_RECEPTION_DESK` (`PUT /reception-desks/:id`), `DELETE_RECEPTION_DESK` (`DELETE /reception-desks/:id`) to `src/data/api/api-endpoints.ts`, all `hasToken: true`.

## 3. Repository port and adapter

- [x] 3.1 Add `src/data/repositories/reception-desk-repository.ts` port: `list(): Promise<ReceptionDesk[]>`, `create(input: ReceptionDeskInput): Promise<ReceptionDesk>`, `update(id: string, input: ReceptionDeskInput): Promise<ReceptionDesk>`, `remove(id: string): Promise<void>`.
- [x] 3.2 Add `src/infrastructure/reception-desk-repository.ts` implementing the port via `ApiClient.makeRequest` + `ReceptionDeskSchema`, following `src/infrastructure/department-repository.ts`.

## 4. Use cases

- [x] 4.1 Add `src/data/use-cases/list-reception-desks.ts`, `create-reception-desk.ts`, `update-reception-desk.ts`, `delete-reception-desk.ts` (or a combined module if the project's existing convention groups CRUD use cases for one entity — check `src/data/use-cases/create-department.ts` / `update-department.ts` for the split-file precedent), each constructor-injected with `ReceptionDeskRepository`.

## 5. Composition root wiring

- [x] 5.1 Add lazy resolvers for the reception-desk repository and use cases in `src/composition-root.ts`, and expose `listReceptionDesksUseCase`, `createReceptionDeskUseCase`, `updateReceptionDeskUseCase`, `deleteReceptionDeskUseCase` on `AppDependencies`.

## 6. Reception Desks list page

- [x] 6.1 Add `src/presentation/pages/admin-reception-desks/hooks/use-admin-reception-desks.ts`: loads current user + reception desks, exposes loading/error/retry, delete-with-confirmation flow, and success/error toasts, following `admin-departments`' list hook.
- [x] 6.2 Add `src/presentation/pages/admin-reception-desks/Components/ReceptionDesksTable.tsx`: columns for Desk Name, Building, Floor, Assigned Receptionist, Operating Hours, Status (three-state badge: Active/Maintenance/Inactive), Actions (Edit/Delete), following `DepartmentsTable.tsx`'s shape.
- [x] 6.3 Add `src/presentation/pages/admin-reception-desks/admin-reception-desks.tsx`: renders `AdminSidebar` (`activeItem="reception-desks"`), `AdminTopBar` (Reception-Desks-specific `description`), header with "Add Desk" button and inert "Filters" control, the table, shared empty state (zero desks) and error state (load failure) per `admin-departments.tsx`.

## 7. Add/Edit Reception Desk page

- [x] 7.1 Add `src/presentation/pages/admin-reception-desks/hooks/use-admin-reception-desk-form.ts`: loads current user, buildings, floors, and host employees; detects edit mode via `useParams<{ id: string }>`; filters Floor options to the selected building and clears `floorId` on building change; validates required `name`/`buildingId`; calls create/update use case; success/error toasts; navigates back to the list on success or cancel.
- [x] 7.2 Add `src/presentation/pages/admin-reception-desks/admin-reception-desk-form.tsx`: presentational page with Desk Name, Building select, Floor select (building-scoped), Assigned Receptionist select (optional, host employees), Operating Hours From/To, Status select (Active/Maintenance/Inactive, default Active), Save/Cancel, driven entirely by the hook.

## 8. Routing and navigation

- [x] 8.1 Register `/admin/reception-desks`, `/admin/reception-desks/new`, `/admin/reception-desks/:id/edit` routes in `src/App.tsx`.
- [x] 8.2 Add the `if (key === 'reception-desks') navigate('/admin/reception-desks')` case to `handleActivate` in `src/presentation/components/AdminSidebar.tsx`.

## 9. Verification

- [x] 9.1 Manually verify: list loads/empty/error states, add desk (validation + success + failure-retains-values), edit desk (pre-fill + success + failure), delete (confirm/cancel/success/failure), Building→Floor cascading, Filters is inert — against the Figma design (node `203:1249`).
