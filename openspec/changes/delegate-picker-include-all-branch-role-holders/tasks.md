## 1. Confirm the cause

- [ ] 1.1 Inspect the employees' `branchRoles` for the affected role (Network tab `GET /auth/employees`, or read-only API call with the user's permission) and confirm the missing employees hold it with `branchId: null`

## 2. Implementation

- [x] 2.1 Update `employeeHasRoleAtBranch` and `employeeAtBranch` in `role-name-match.ts` to also accept `branchId == null` assignments; refresh its explanatory comment
- [x] 2.2 Confirm `loadNextStepCandidates` and `DelegateInvitationModal` need no further change (both use the helpers)

## 3. Verification

- [ ] 3.1 Reproduce: invitation with several next-role holders (mix of branch-specific and All Branch) lists all of them in "Approve & Delegate" and "Delegate"
- [ ] 3.2 A holder only at another branch is not listed
- [x] 3.3 Run type-check
