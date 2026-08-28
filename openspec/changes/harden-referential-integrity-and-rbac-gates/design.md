## Context

See `proposal.md` — Why/What Changes for the audit findings and root cause.
Relevant existing code shapes this design:

- `org_structure/service.py::delete_role` (actually `auth/service.py`) already
  guards role deletion against active `UserBranchRole` grants via
  `RoleRepository.has_active_grants()` before soft-deleting — this is the
  pattern to mirror for `delete_branch`.
- `org_structure/service.py` already has "tolerant" resolvers
  (`_resolve_building_branch_id_tolerant`, `_resolve_floor_branch_id_tolerant`)
  that authorize against a parent's branch even if that parent (or the branch
  itself) has since been soft-deleted, added for Floor/ReceptionDesk. This is
  the pattern to extend to invitation approval.
- `RegistrationDeviceKey` (`registrations/models.py`) intentionally carries no
  FK to `branches` — it lives in the tenant schema like a branch does, but
  the repo's convention treats device-key-to-branch as an application-level
  reference, not a DB constraint, so "still referenced" has to be checked by
  an explicit query, not left to Postgres.
- `org_structure/repository.py::get_including_deleted` already exists for
  reading a soft-deleted row when authorization needs to tolerate one — no
  new repository primitive is needed for the tolerant-approval fix.

## Goals / Non-Goals

**Goals:**
- Make it structurally impossible to soft-delete a `Branch` while a live
  kiosk credential or org-chart child still depends on it.
- Close the two known instances of "an authorization/lookup path 404s on a
  since-soft-deleted `org_structure` row it should tolerate" (walk-in device
  resolution already tolerates this correctly today; invitation approval
  does not).

**Non-Goals:**
- No change to which permission codes gate which actions, no change to
  branch-scoping semantics, no change to any response shape or status code
  for a request that already succeeds today under the same preconditions.
- Not building a generic "cascade soft-delete" mechanism — deletion stays
  deliberately blocked (409) rather than auto-cascading, consistent with
  the existing `Role`/`UserBranchRole` precedent (block, don't cascade).
- Not adding a force-delete/override path for the new branch-deletion guard
  — an operator who genuinely needs to remove a branch with active children
  deletes the children first, same as today's role-deletion workflow.
- **Not migrating `org_structure`/`invitations` permission checks to a
  route-level `Depends(require_permission(...))`.** This was the original
  plan for the 22 flagged routes, dropped once implementation confirmed it
  would be a regression, not a refactor — see the Decisions section below.

## Decisions

**Block, don't cascade, on branch deletion.** Mirrors the existing
`Role`/`UserBranchRole` guard exactly rather than introducing a new
cascade-delete concept into a codebase that has none. Alternative
considered: cascade-soft-delete every child when a branch is deleted. Rejected
because it's a bigger, riskier, less reversible behavior change (soft-
deleting a whole tree because one `PUT` touched the top) for a bug whose
actual complaint is "this silently broke something," not "deleting a branch
should also delete its buildings."

**Deactivate, don't delete, an orphaned check.** The guard checks for
*active* `RegistrationDeviceKey` rows (`is_active = true`), not merely
"any row referencing this branch," so a device key an operator has already
deactivated doesn't block an otherwise-legitimate branch deletion.

**Reuse the existing tolerant-resolution helper shape for invitation
approval**, rather than inventing a new one. `approve_invitation`'s branch
authorization becomes "resolve the invitation's own `branch_id` for
authorization, tolerating a soft-deleted row" — the same shape as
`_resolve_floor_branch_id_tolerant`, applied to a `branch_id` that's already
on hand from the invitation row itself (no repository call needed beyond
what `authorize_branch_id`'s tolerant variant already does).

**RBAC dependency migration: investigated, then dropped as originally
scoped.** The plan was `dependencies=[Depends(require_permission("<same
code already checked inline>"))]` on each of the 22 routes, deleting the
now-redundant in-body/in-service check. Before touching any router code,
`core/tenancy.py::require_permission` and `auth/models.py::User.has_permission`
were re-read to confirm the exact semantics being moved: `require_permission`
calls `has_permission(code, branch_id=None)` — by the method's own
docstring, "a company-wide grant only." Every one of the 22 routes' actual
checks passes a *resolved branch id* (`has_permission(code,
branch_id=building.branch_id)` and friends), specifically so a role granted
only at one branch (not company-wide) can still act there —
`org_structure/service.py::get_branch`'s docstring documents this as a
deliberate earlier move *away* from the blanket dependency, for exactly
this reason. Swapping in `Depends(require_permission(...))` would silently
turn every branch-scoped-only grant into a 403, which is a functional
regression on real, working RBAC configurations (any tenant with a
branch-scoped Building/Floor/Desk manager who isn't also company-wide),
not the zero-behavior-change refactor the proposal called for. A correct
version would need a per-entity dependency that resolves the target's
branch (the same lookup `get_building`/`get_floor`/... already do) *before*
checking the permission at that branch — functionally equivalent to today's
in-body check, just invoked as a `Depends()` instead of a call inside the
handler/service body. That is a legitimate follow-up, but it means writing
and reviewing roughly 20 new per-entity dependency functions rather than a
one-line decorator addition per route — enough scope and risk on its own
that it belongs in its own change, reviewed on its own, rather than bundled
into a change whose other four items are narrowly-scoped bug fixes. Dropped
from this change; the in-body checks are unchanged and remain correct.

## Risks / Trade-offs

- [Risk] The new branch-deletion guard could break an existing test fixture
  that deletes a branch without first cleaning up its children/device keys,
  since that was previously unguarded. → Mitigation: run the full suite
  after implementing the guard; any fixture relying on the old
  unrestricted-delete behavior gets an explicit cleanup step added (delete
  children first), not a weakening of the new guard.
- [Risk] `UserRepository` inheriting `TenantScopedRepository[User]` could
  change query behavior if any existing method relied on seeing soft-deleted
  users (e.g. an audit/history read). → Mitigation: audit `UserRepository`'s
  existing methods before switching the base class; any method that
  genuinely needs soft-deleted rows keeps an explicit
  `include_deleted`-style override rather than losing that capability.

## Migration Plan

No data migration. Deploy as a normal code change; the branch-deletion guard
takes effect immediately for any delete request made after deploy — no
existing data is altered, only future delete attempts against branches that
already have active children/device keys start returning 409 instead of
succeeding. Rollback is a plain revert; nothing here is one-way.
