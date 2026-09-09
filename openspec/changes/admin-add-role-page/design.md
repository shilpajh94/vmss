## Context

Roles today are served through `HostEmployeeRepository` (`src/data/repositories/host-employee-repository.ts`), which already owns `listRoles`, `updateRolePermissions`, and `resyncRolePermissions`, backed by `HttpHostEmployeeRepository` and endpoints under `/auth/roles`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Let an admin create a custom role with a name, optional description, and a permission set, using the same data-api-layer pattern as the existing role features.
- Reuse the existing permission-catalog checklist UI/UX from the permission-edit page rather than inventing a new interaction.

**Non-Goals:**
- Role deletion or renaming (not requested).
- Changing how `isStandard` is computed — the backend decides this; the frontend never sends it and always treats admin-created roles as backend-determined.
- Any change to the permission-edit page's own behavior.

## Decisions

- **Extend `HostEmployeeRepository` with `createRole` rather than introducing a new port.** All existing role operations (`listRoles`, `updateRolePermissions`, `resyncRolePermissions`) already live on this port and share `HttpHostEmployeeRepository`/`ApiClient`. Adding a fourth role method keeps one adapter per backend resource area instead of splitting roles across two ports for no behavioral reason.
- **New endpoint `CREATE_ROLE`: `POST /auth/roles`, `hasToken: true`.** Matches the existing `/auth/roles` base used by `LIST_ROLES` (`GET /auth/roles`) and `UPDATE_ROLE` (`PUT /auth/roles/:id`) — same resource, different verb.
- **New input type `RoleCreateInput`** (`name: string`, `description?: string`, `permissionCodes: string[]`) added alongside `RoleOutSchema` in `src/domain/entities/role-out-schema.ts`, and the create response reuses the existing `RoleResponseSchema`/`RoleOutSchema` — no new response shape needed since a created role has the same shape as any other `RoleOut`.
- **New page reuses the permission-edit page's checklist layout** (`AdminRolePermissionsFormPage`'s permission list markup) plus two new inputs (name, description) instead of a from-scratch form, keeping the two role forms visually consistent.
- **Client-side required-name validation only** (no other field-level validation) — the backend is the source of truth for any additional constraints (e.g. name uniqueness), surfaced via the existing error-notification path on a failed create call.

## Risks / Trade-offs

- [Backend may reject duplicate role names or enforce constraints not visible to the frontend] → Surfaced through the existing "show backend error message via toast, stay on page" pattern already used for permission-edit save failures; no separate duplicate-check needed client-side.
- [Reusing `HostEmployeeRepository` for a fourth role method keeps growing an already multi-purpose port] → Acceptable for now since it matches the codebase's existing precedent; a future dedicated `RoleRepository` split is a separate refactor, not part of this change.
