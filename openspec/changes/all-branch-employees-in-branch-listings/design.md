## Context

`UserRepository.list_employees_page` filters a branch-scoped view with
`Department.branch_id IN scope OR EXISTS(UserBranchRole at scope or NULL)`.
`auth/models.py::User.has_branch_access` already treats a NULL role-grant branch
as every branch, but a user with no department and no grant at all is not
matched. See proposal.md for the symptom.

## Goals / Non-Goals

**Goals:**
- Branch-scoped listing = branch members ∪ all-branch employees, one row each.
- Keep the single-query, `EXISTS`-based, no-fan-out shape (query-performance.md).

**Non-Goals:**
- Changing who may disable/enable/delete, or adding branch-scoped authorization
  to those actions.
- Introducing an explicit "all branches" flag column or migration.
- Changing the unscoped listing or response schema.

## Decisions

1. **Derive "all-branch" instead of storing it.** An employee is all-branch if
   `department_id IS NULL` and no `UserBranchRole` row has a non-NULL
   `branch_id`, or they hold a NULL-`branch_id` grant (already covered).
   Alternative: a new `all_branches` boolean — rejected: duplicates what role
   grants already express and needs a migration plus backfill.
2. **Extend the existing `or_` clause** with
   `and_(User.department_id.is_(None), ~EXISTS(UserBranchRole with branch_id NOT NULL))`.
   Uses `EXISTS`, so no duplicates and `total` stays correct. Alternative:
   a join plus `DISTINCT` — rejected, breaks count/pagination.
3. **Employee with a department at another branch but a company-wide grant**
   stays visible everywhere (existing behavior, kept).

## Risks / Trade-offs

- [An unassigned new employee (no department, no grant) now shows in every
  branch] → intended by the request; they were previously invisible to branch
  views.
- [Delegate pickers may now list people with no `invitations:approve`] → the
  `role` filter and service-side delegate validation still apply.

## Open Questions

- Is "no department and no branch grant" the intended meaning of "mapped to all
  branches", or does the portal write an explicit company-wide grant? Both are
  covered; confirm during review.
