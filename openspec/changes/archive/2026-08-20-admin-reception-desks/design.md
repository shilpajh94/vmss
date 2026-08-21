## Context

See proposal.md - Why. This capability follows the existing admin CRUD pattern already established by `admin-branches`, `admin-buildings`, `admin-departments`, and `admin-floors` (spec-per-screen, `data/` → `infrastructure/` → `presentation/` layering per `.claude/rules/clean-architecture.md` and `.claude/rules/data-api-layer.md`). It reuses `Building` (`src/domain/entities/building-schema.ts`), `Floor` (`src/domain/entities/floor-schema.ts`, which already carries `buildingId`), and `HostEmployee` (`src/domain/entities/host-employee-schema.ts`) as relation targets. `AdminSidebar` already reserves the `reception-desks` nav key and label; `AdminTopBar` (`src/presentation/components/AdminTopBar.tsx`) only accepts `description`/`breadcrumb`/`currentUser` and hardcodes the "Organization Admin" heading — this capability reuses it as-is rather than adding a title prop, consistent with every other admin screen.

## Goals / Non-Goals

**Goals:**
- Deliver the Reception Desks Register (list) and Add/Edit Reception Desk pages matching the Figma design (node `203:1249`) and the existing admin CRUD architecture.
- Support a three-state status (Active / Maintenance / Inactive), not the two-state `isActive` boolean used by Branch/Building/Department/Floor.
- Support a Building → Floor cascading dropdown in the form, since the Figma table always shows a floor per desk.

**Non-Goals:**
- Real filtering behind the "Filters" button (matches existing admin screens, which also render it inert).
- A "24 Hours (Rotational)" structured schedule type. Operating hours are two optional free-text fields (`operatingHoursFrom`/`operatingHoursTo`), matching `Branch`'s existing pattern; free-form values like "24 Hours (Rotational)" are supported only as opaque text, not as a distinct schedule mode.
- Assigning more than one receptionist per desk, or scheduling shifts.
- Any change to Building, Floor, or Host Employee CRUD screens themselves.

## Decisions

- **Status as an enum, not `isActive`**: `ReceptionDeskSchema.status: z.enum(["active", "maintenance", "inactive"]).default("active")`. Alternative considered: reuse `isActive: boolean` and treat "Maintenance" as a UI-only sub-state — rejected because the design shows Maintenance as a first-class, independently selectable status the backend must persist, not a derived UI label.
- **Denormalized display fields on the read model**: like `Building.branchName` and `Department.branchName`, `ReceptionDesk` carries `buildingName` and, when present, `floorName` and `receptionistName` (backend-resolved) so the table can render names without an extra client-side join. `Input` types (`Omit<ReceptionDesk, "id" | "buildingName" | "floorName" | "receptionistName">`) carry only the ids for create/update, matching `BuildingInput`.
- **Floor field cascades from Building**: the Add/Edit form loads buildings and floors up front (via existing `listBuildingsUseCase` / `listFloorsUseCase`) and filters the Floor options client-side to `floor.buildingId === values.buildingId`, clearing `floorId` on building change. Alternative considered: lazy-fetch floors per building — rejected, floors are already listed in full for `admin-floors` and the dataset is small, so an extra network round-trip isn't warranted.
- **Assigned Receptionist sourced from Host Employees**: reuses `listHostEmployeesUseCase` (already powering `admin-host-employees`) rather than introducing a separate "receptionist" entity, since a receptionist is just a host employee assigned to a desk.
- **Top bar reuses the existing hardcoded "Organization Admin" heading**: the Figma frame's "Reception Operations" heading is not introduced as a new capability of `AdminTopBar`; the page passes only `description` (Reception-Desks-specific copy) and `currentUser`, identical to every other admin list/form page. Changing `AdminTopBar` to support a custom title is out of scope for this change.
- **New endpoints follow the existing REST shape**: `LIST_RECEPTION_DESKS`/`CREATE_RECEPTION_DESK` at `/reception-desks`, `UPDATE_/DELETE_RECEPTION_DESK` at `/reception-desks/:id`, all `hasToken: true`, mirroring `LIST_/CREATE_/UPDATE_/DELETE_FLOOR`.

## Risks / Trade-offs

- [Floor list not scoped server-side to a building] → Mitigated by client-side filtering on the already-fetched full floor list, same approach already implicitly available via `Floor.buildingId`; revisit only if the floor list grows large enough to need server-side scoping.
- [Three-state status is a schema shape unique to this entity] → Contained to `reception-desk-schema.ts`; no shared status-badge component changes required since `ReceptionDesksTable` owns its own badge rendering, same as `DepartmentsTable` owns its two-state badge today.
- [Assigned Receptionist has no dedicated backend relation beyond a `receptionistUserId` FK] → Consistent with `Department.headOfDepartmentUserId`'s existing pattern; if reassignment history or shift scheduling is needed later, that is a separate capability.
