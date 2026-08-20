## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/security-gate-schema.ts`: `SecurityGateSchema` (`id`, `buildingId`, `buildingName`, `floorId?`, `floorName?`, `name`, `gateType: "bidirectional" | "entry_only" | "exit_only" | "high_security"`, `authMethod?`, `connectivityStatus: "online" | "maintenance" | "offline"`), `SecurityGate` type, and `SecurityGateInput = Omit<SecurityGate, "id" | "buildingName" | "floorName">`.
- [x] 1.2 Add `src/domain/entities/security-gate-out-schema.ts`: `SecurityGateOutSchema`/`SecurityGateResponseSchema`/`SecurityGateListResponseSchema`, following `reception-desk-out-schema.ts`.

## 2. API endpoints

- [x] 2.1 Add `LIST_SECURITY_GATES` (`GET /security-gates`), `CREATE_SECURITY_GATE` (`POST /security-gates`), `UPDATE_SECURITY_GATE` (`PUT /security-gates/:id`), `DELETE_SECURITY_GATE` (`DELETE /security-gates/:id`) to `src/data/api/api-endpoints.ts`, all `hasToken: true`.

## 3. Repository port and adapter

- [x] 3.1 Add `src/data/repositories/security-gate-repository.ts` port: `list(): Promise<SecurityGate[]>`, `create(input: SecurityGateInput): Promise<SecurityGate>`, `update(id: string, input: SecurityGateInput): Promise<SecurityGate>`, `remove(id: string): Promise<void>`.
- [x] 3.2 Add `src/infrastructure/security-gate-repository.ts` implementing the port via `ApiClient.makeRequest` + `SecurityGateSchema`, resolving `buildingName`/`floorName` from `BuildingRepository`/`FloorRepository`, following `src/infrastructure/reception-desk-repository.ts`.

## 4. Use cases

- [x] 4.1 Add `src/data/use-cases/list-security-gates.ts`, `create-security-gate.ts`, `update-security-gate.ts`, `delete-security-gate.ts`, each constructor-injected with `SecurityGateRepository`.

## 5. Composition root wiring

- [x] 5.1 Add lazy resolvers for the security-gate repository and use cases in `src/composition-root.ts`, and expose `listSecurityGatesUseCase`, `createSecurityGateUseCase`, `updateSecurityGateUseCase`, `deleteSecurityGateUseCase` on `AppDependencies`.

## 6. Security Gates list page

- [x] 6.1 Add `src/presentation/pages/admin-security-gates/hooks/use-admin-security-gates.ts`: loads current user + security gates, exposes loading/error/retry, delete-with-confirmation flow, and success/error toasts, following `use-admin-reception-desks.ts`.
- [x] 6.2 Add `src/presentation/pages/admin-security-gates/Components/SecurityGatesTable.tsx`: columns for Gate Name/ID, Building, Floor, Gate Type (4-state badge), Auth Method, Connectivity (3-state badge), Actions (Edit/Delete), following `ReceptionDesksTable.tsx`'s shape.
- [x] 6.3 Add `src/presentation/pages/admin-security-gates/admin-security-gates.tsx`: renders `AdminSidebar` (`activeItem="security-gates"`), `AdminTopBar` (Security-Gates-specific `description`), header with "Register Gate" button and inert "Filters" control, the table, shared empty state (zero gates) and error state (load failure) per `admin-reception-desks.tsx`.

## 7. Register/Edit Gate page

- [x] 7.1 Add `src/presentation/pages/admin-security-gates/hooks/use-admin-security-gate-form.ts`: loads current user, buildings, and floors; detects edit mode via `useParams<{ id: string }>`; filters Floor options to the selected building and clears `floorId` on building change; validates required `name`/`buildingId`; calls create/update use case; success/error toasts; navigates back to the list on success or cancel.
- [x] 7.2 Add `src/presentation/pages/admin-security-gates/admin-security-gate-form.tsx`: presentational page with Gate Name/ID, Building select, Floor select (building-scoped), Gate Type select (default Bidirectional), Auth Method text field, Connectivity Status select (default Online), Save/Cancel, driven entirely by the hook.

## 8. Routing and navigation

- [x] 8.1 Register `/admin/security-gates`, `/admin/security-gates/new`, `/admin/security-gates/:id/edit` routes in `src/App.tsx`.
- [x] 8.2 Add the `if (key === 'security-gates') navigate('/admin/security-gates')` case to `handleActivate` in `src/presentation/components/AdminSidebar.tsx`.

## 9. Verification

- [x] 9.1 Manually verify: list loads/empty/error states, register gate (validation + success + failure-retains-values), edit gate (pre-fill + success + failure), delete (confirm/cancel/success/failure), Building→Floor cascading, Filters is inert — against the Figma design (node `203:1418`).
