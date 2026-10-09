## Context

`employeeHasRoleAtBranch` (`role-name-match.ts`) requires `branchRole.branchId === branchId` whenever the invitation has a branch, so a `branchId: null` ("All Branch") assignment never matches. `use-invitations-board.ts` (`loadNextStepCandidates`) and `DelegateInvitationModal.tsx` both use it, so both pickers go empty for tenants whose host role is assigned with All Branch. The strictness was added because the backend once rejected null-branch delegates; the user now wants these employees listed.

## Goals / Non-Goals

**Goals:** list role holders for the branch plus All Branch holders, consistently in both pickers.

**Non-Goals:** changing backend calls, role-name resolution (`/auth/roles` 403 fallback), approval-step indexing, or admin role assignment UI.

## Decisions

- **Change the shared helper, not each caller.** Update `employeeHasRoleAtBranch` (and `employeeAtBranch` for the fallback/ownership paths) so a matching assignment counts when `!branchId || branchRole.branchId === branchId || branchRole.branchId == null`. One edit keeps both pickers identical. Alternative: per-caller filters (duplicates logic, risks drift).
- **Keep server as final authority.** No client change on submit; existing error toast surfaces a backend rejection.
- **Verify the actual cause before editing.** The screenshot shows an empty list; the first task checks the real `GET /auth/employees` data to confirm the excluded employees are All Branch holders (vs. a role-name mismatch), so the fix targets the right cause.

## Risks / Trade-offs

- [Backend may still reject All Branch delegates] → selection fails on submit with the backend's message, after Reception's approval already went through (approve-then-delegate is not atomic). Flag to the backend team; revert the helper change if rejection is confirmed.
- [Cause turns out to be a role-name mismatch, not All Branch] → pause and update these artifacts.
