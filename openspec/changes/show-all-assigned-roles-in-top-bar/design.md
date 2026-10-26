## Context

`StaffAuthRepository.getCurrentUser` builds `StaffUser.role` from `branchRoles[0]?.roleName ?? 'Staff'`, so only the first grant reaches `AppTopBar` (`currentUser?.role`). `role` has no other consumers; routing uses `isAdmin` / `isReception` and page logic uses `branchRoles`.

## Goals / Non-Goals

**Goals:** show all assigned roles in the top bar without growing it.
**Non-Goals:** showing which branch each role applies at, role badges/menus, or changing routing/permission logic.

## Decisions

- **`role: string` → `roles: string[]` in `StaffUserSchema`.** One source of truth, derived in the adapter: distinct `roleName`s from `branchRoles` in grant order (`[...new Set(...)]`), falling back to `['Staff']` when empty. Keeping a joined string would push display formatting into the infrastructure layer; a list leaves formatting to the UI. Removing the old field makes the compiler flag any missed consumer.
- **Render as `roles.join(', ')`** in the existing 11px muted line, with `truncate` and `title` set to the same text. The user block is already `hidden md:flex` and the bar is a single row, so truncation (with a width cap such as `max-w-48`) protects the layout rather than wrapping.
- **Distinct, not per-branch.** A role held at several branches is listed once; branch scoping is out of scope for a header label.
- **Role casing** is left as the backend returns it (the screenshot shows lowercase "reception"); no capitalisation change.

## Risks / Trade-offs

- Renaming `role` is a small breaking change to the domain type; mitigated by `tsc -b` catching every consumer (only `AppTopBar` today).
- Assumption: "listed" means all roles shown comma-separated in the existing spot, rather than a dropdown or badges. Easy to revisit if a different presentation is preferred.
