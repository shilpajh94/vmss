## Why

A live bug was reported: walk-in registration starts failing once the branch
a kiosk's device credential is provisioned for gets soft-deleted. A
code-level audit (four independent passes — referential-integrity, RBAC/
tenant-isolation, query-performance/code-standards, test-coverage — across
every feature package) traced this to its actual root cause and found the
same "a soft-deleted `org_structure` row keeps being referenced by something
that assumes it's still live" pattern recurring in one other place
(invitation approval), plus a related gap: nothing stops a branch from being
soft-deleted while active children or device credentials still point at it
in the first place, unlike the equivalent guard that already exists for
`Role` deletion. The same audit also found 20 `org_structure` routes and 2
`invitations` routes enforce permissions correctly today but do it via an
inline call inside the handler/service body rather than the
`Depends(require_permission(...))` pattern `security-architecture.md` §1 and
`fastapi-architecture.md` §6 mandate — functionally safe now, but one
handler copy-pasted from the wrong sibling away from silently shipping an
unprotected mutation. Most other audited dimensions (tenant isolation,
eager-loading, N+1 queries, `response_model`/`CamelModel` coverage,
structlog usage, PII/OTP logging, idempotency, Celery retry config, test
factories) came back clean and are explicitly not touched by this change.

## What Changes

- **Block branch deletion while it's still referenced** (`org_structure`):
  soft-deleting a `Branch` is rejected with 409 while it has any active
  (non-soft-deleted) `Building`/`Floor`/`Department`/`ReceptionDesk`/
  `SecurityGate` child, or any active `RegistrationDeviceKey` provisioned
  against it — mirroring the guard `delete_role` already applies for active
  `UserBranchRole` grants. This is the actual fix for the reported bug: it
  stops a branch from being deleted out from under a live kiosk credential
  in the first place, rather than only handling the failure after the fact.
- **Reject creating a new child under an already soft-deleted parent**
  (`org_structure`): creating a `Building`/`Department` under a soft-deleted
  `Branch`, a `Floor` under a soft-deleted `Building`, or a
  `ReceptionDesk`/`SecurityGate` under a soft-deleted `Floor`/`Branch` is
  rejected the same way an unknown parent id already is (404, since a
  soft-deleted row is invisible to normal lookups) — closing a gap where
  only "child survives parent's later deletion" was previously tested, never
  "parent was already gone at creation time."
- **Tolerate a since-soft-deleted branch when approving an invitation**
  (`invitations`): approving a `submitted` invitation whose `branchId` was
  soft-deleted after the invitation was created currently 404s ("Branch not
  found") on an otherwise-valid, pending approval — the same bug class as
  the walk-in issue, on a different endpoint. `approve_invitation` switches
  to the tolerant branch-resolution helper `org_structure/service.py` already
  uses for `Floor`/`ReceptionDesk` (resolve for authorization purposes even
  if the branch is now soft-deleted), instead of treating the invitation
  itself as not-found.
- **RBAC route-dependency migration was investigated and dropped.** The
  audit flagged 20 `org_structure` routes and 2 `invitations` routes for
  checking permissions inline rather than via
  `Depends(require_permission(...))`. Implementation confirmed this can't be
  done as a mechanical decorator swap: `require_permission(code)` calls
  `user.has_permission(code, branch_id=None)` — a **company-wide grant
  only** (`auth/models.py::User.has_permission`'s own docstring). These
  routes' in-body/in-service checks are deliberately branch-scoped
  (`user.has_permission(code, branch_id=<resolved branch>)`) so a caller
  holding the permission only at their own branch — not company-wide — can
  still act; `org_structure/service.py::get_branch`'s docstring documents
  this as an intentional prior move *away* from the blanket dependency.
  Wiring `Depends(require_permission(...))` as originally planned would
  silently reject every non-company-wide caller on these routes — a real
  regression, not a safe refactor. A correct fix needs a branch-aware
  per-entity dependency (resolve the target's branch, then check the
  permission at that branch, before the handler runs) — a larger, separate
  effort with its own review, left out of this change to keep this change's
  risk low.
- **`UserRepository` inherits `TenantScopedRepository[User]`** (`auth`):
  every other tenant-table repository already does; `UserRepository`
  currently re-implements the `deleted_at IS NULL` filter by hand on each
  query. No behavior change — same filter, same queries, now guaranteed by
  the base class instead of by each method remembering to add it.
- **Close the test-coverage gaps the audit found**, per
  `testing-standards.md` §2, all for already-existing (not newly invented)
  requirements:
  - `registrations`: a device credential that resolves to a soft-deleted
    branch is rejected the same way an inactive one is (401, `WARNING`-
    logged, no 500) — this is the direct regression test for the reported
    bug.
  - `org_structure`: the new branch-deletion guard (409 with active
    children/device keys; success once none remain) and the new
    create-under-deleted-parent rejection (404), for each entity level.
  - `invitations`: approving an invitation whose branch was soft-deleted
    after submission now succeeds.
  - `auth`: `assign_branch_role` rejects a soft-deleted role and a
    soft-deleted branch (today only unknown-id is tested).
  - `platform`: `POST /platform/tenants` gets a permission-denied/negative-
    auth test (today only `GET /platform/tenants` has one).
  - `visit_info`: tenant-isolation tests for `GET /visit-info/departments`
    and `GET /visit-info/options` (today only `search_hosts` has one).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `org-structure`: adds the branch-deletion referential-integrity guard and
  the create-under-soft-deleted-parent rejection as new requirements.
- `invitations`: adds tolerant branch resolution for approving an invitation
  whose branch was soft-deleted after submission.

## Impact

- **Code**: `src/vmss_api/org_structure/repository.py`/`service.py`/
  `router.py` (delete-branch guard against active children/device keys;
  `create-under-deleted-parent` behavior verified, not changed),
  `src/vmss_api/registrations/repository.py` (device-key-by-branch lookup
  for the guard), `src/vmss_api/invitations/service.py`/`router.py`/
  `src/vmss_api/org_structure/deps.py` (tolerant branch resolution on
  invitation approval), `src/vmss_api/auth/repository.py` (`UserRepository`
  base class change). The RBAC route-dependency migration originally
  planned here was dropped — see "What Changes" above.
- **Tests**: new cases added to `org_structure/tests.py`,
  `invitations/tests.py`, `registrations/tests.py`, `auth/tests.py`,
  `platform/tests.py`, `visit_info/tests.py` per the coverage list above.
  No existing test is expected to change behavior; a few existing
  branch-deletion-happy-path fixtures may need an active-child/device-key
  cleanup added if they incidentally relied on deleting a branch that still
  has children.
- **Compatibility**: the branch-deletion guard changes response code for one
  previously-unrestricted case (deleting a branch with active children/
  device keys now returns 409 instead of succeeding) — this is a new
  restriction closing a data-integrity gap, not a change to any
  already-documented success/error contract. Every other change in this
  proposal is either a pure implementation-detail refactor (RBAC dependency
  placement, `UserRepository` base class) or a test-only addition; no
  existing client-observable behavior changes.
