import type { HostEmployee } from '../../domain/entities/host-employee-schema'

// `ApprovalWorkflowRule`/Role names and `HostEmployee.branchRoles[].roleName`
// come from separate API responses that are supposed to reference the same
// Role record but are compared as plain strings — trim/casing differences
// between where a role name is configured and where it's assigned would
// otherwise make an eligible employee invisible to the delegate/approve
// pickers. Mirrors the case-insensitive check already used for the
// hardcoded "reception" role (see use-admin-workflow-form.ts).
export function roleNamesMatch(a: string | undefined | null, b: string | undefined | null): boolean {
  if (!a || !b) return false
  return a.trim().toLowerCase() === b.trim().toLowerCase()
}

// A `branchRole` with no `branchId` is an "All branches" assignment and counts
// at every branch. (The backend previously rejected such grants at submit time;
// if that still happens the server error is surfaced to the user.)
//
// The backend enforces that a delegate actually holds the step's approver
// role *at the invitation's own branch* (confirmed via the real API error:
// "Delegate does not hold this step's approver role at the invitation's
// branch", and via direct API inspection: a `branchRole` assigned with no
// `branchId` at all does NOT satisfy this check — a "global" role grant is
// not treated as valid everywhere, it simply isn't branch-scoped at all).
// So a `branchRole` only counts here when it has an explicit `branchId`
// that matches the invitation's own — matching by role name alone (as the
// delegate/approve pickers used to) could offer someone who holds the role
// with no branch assignment, or at a *different* branch, either of which
// the backend then rejects. If the invitation itself has no `branchId`,
// branch can't be scoped on either side, so any matching role counts.
export function employeeHasRoleAtBranch(
  employee: HostEmployee,
  roleName: string | undefined | null,
  branchId: string | undefined | null,
): boolean {
  return employee.branchRoles.some(
    (branchRole) => roleNamesMatch(branchRole.roleName, roleName) && (!branchId || !branchRole.branchId || branchRole.branchId === branchId),
  )
}

// Same branch scoping as `employeeHasRoleAtBranch`, but without the role-name
// requirement — for the invitation's ownership step, where any active
// employee at the invitation's branch can become the actual host regardless
// of which role they hold.
export function employeeAtBranch(employee: HostEmployee, branchId: string | undefined | null): boolean {
  return employee.branchRoles.some((branchRole) => !branchId || !branchRole.branchId || branchRole.branchId === branchId)
}
