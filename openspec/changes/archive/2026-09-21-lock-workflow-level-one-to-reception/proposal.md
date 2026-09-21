## Why

Level 1 (stepOrder 0) of an approval workflow is treated as "Reception's step" throughout the rest of the app — the reception-only dashboard guard, the "Approve & Delegate" action, the "Pending:" next-step preview, and the delegate-blocking rule all hardcode `stepOrder === 0` as meaning Reception. But the Add/Edit Workflow form lets an admin assign *any* role to Level 1, with no default and no validation tying it to Reception. Picking a different role there would silently break all of that reception-specific behavior, since none of it checks the role name — only the position.

## What Changes

- On the Add/Edit Workflow page, Level 1's approver is fixed to the organisation's "Reception" role — pre-filled and not editable, for both new workflows and existing ones being edited (if an existing workflow's Level 1 is some other role, saving the edit corrects it to Reception).
- Level 1 can never be removed via "Remove level", regardless of how many levels exist (today only "the last remaining level" is protected).
- If no role named "Reception" exists in the organisation's role catalog, the form shows a clear error instead of silently leaving Level 1 unset — a workflow cannot be configured until that role exists.
- Every level after Level 1 is unaffected — still a free choice from the organisation's roles, exactly as today.

## Capabilities

### Modified Capabilities
- `admin-approval-workflows`: Level 1's approver is fixed to the Reception role (pre-filled, locked, un-removable) instead of a free role selection; a missing Reception role is surfaced as a blocking error.

## Impact

- **Affected code**:
  - `src/presentation/pages/admin-workflows/hooks/use-admin-workflow-form.ts` — resolve the "Reception" role from the already-fetched `roles` list (case-insensitive name match, same convention as `isReception`/`isAdmin` elsewhere); force `levels[0].approverRoleId` to that role's id on load (both create and edit mode) and keep it pinned there; surface a blocking error when no such role exists; `removeLevel` refuses index 0 unconditionally.
  - `src/presentation/pages/admin-workflows/admin-workflow-form.tsx` — Level 1's `SelectField` renders disabled/locked with a fixed value; its "Remove level" button is disabled for index 0 regardless of `levels.length`.
  - `openspec/specs/admin-approval-workflows/spec.md` — requirements updated per above.
- **Not affected**: levels 2+ (still freely assignable to any role), the backend API surface (no new/changed endpoints — same `saveWorkflowUseCase`/rule shape, just a constrained value for one field), and every other page/capability that already assumes stepOrder 0 = Reception (this change makes that assumption actually enforced at the point workflows are configured, rather than just relied upon elsewhere).
