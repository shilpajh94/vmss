## Why

A user with several roles assigned sees only one role name under their name in the top bar (the screenshot shows just "reception"), because the current-user mapping keeps only the first role grant. That misrepresents what access the person has.

## What Changes

- Show every distinct role name assigned to the signed-in user in the top bar's user block, not just the first.
- Replace the single-string `StaffUser.role` with a list of distinct role names (the top bar is its only consumer), keeping the `'Staff'` fallback when no role is granted.
- Long lists are truncated visually with the full list available on hover/focus (title), so the top bar stays on one row.
- Not changed: dashboard routing, `isAdmin` / `isReception`, `branchRoles`, the login flow.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `app-shell`: the top bar's user block lists all of the signed-in user's assigned roles.

## Impact

- `src/domain/entities/staff-user-schema.ts` (`role` → `roles`)
- `src/infrastructure/staff-auth-repository.ts` (`getCurrentUser` mapping)
- `src/presentation/components/AppTopBar.tsx` (render)
- Any fixtures or mocks constructing a `StaffUser` (type check will surface them).
- No API, endpoint, or composition-root changes.
