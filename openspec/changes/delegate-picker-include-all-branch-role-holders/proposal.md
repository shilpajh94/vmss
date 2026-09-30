## Why

On an invitation's "Approve & Delegate" (and the plain "Delegate") dialog, the employee dropdown shows "No employees are eligible for the next step yet." even though several employees hold the next role (e.g. host). The picker only counts an employee when their role assignment carries an explicit `branchId` equal to the invitation's branch, so employees assigned the role with "All Branch" (no branch) are silently hidden.

## What Changes

- The eligible-employee rule for the next-step / delegate pickers becomes: employee holds the step's role at the invitation's branch **or** holds it with "All Branch" (no branch).
- Applies to both the combined "Approve & Delegate" picker and the plain "Delegate" picker, so they never disagree.
- If the server still rejects a chosen delegate, the existing error notification shows the backend's message (no change to submit handling).

## Capabilities

### New Capabilities

### Modified Capabilities
- `staff-dashboard`: the set of employees offered for the next step / delegation now includes role holders assigned to all branches.

## Impact

- `src/presentation/utils/role-name-match.ts` (`employeeHasRoleAtBranch`, and the `employeeAtBranch` fallback)
- `src/presentation/hooks/use-invitations-board.ts` (`loadNextStepCandidates`)
- `src/presentation/components/invitation-board/DelegateInvitationModal.tsx`
- Presentation-only; no API, schema, or dependency changes.
- Reverses an earlier deliberate strictness (an earlier backend rejected null-branch delegates). The user confirmed this behavior for this change.
