## 1. Branch Deletion Referential-Integrity Guard (org_structure)

- [x] 1.1 Add a repository check (`org_structure/repository.py`,
      `BranchRepository` or a shared helper) that reports whether a branch
      has any active (non-soft-deleted) `Building`, `Floor`, `Department`,
      `ReceptionDesk`, or `SecurityGate` — a single query per entity type or
      one combined query, not a per-row loop (`query-performance.md` §2).
- [x] 1.2 Add a check for any active (`is_active = true`)
      `RegistrationDeviceKey` referencing the branch (global-schema-adjacent
      lookup consistent with how `registrations/deps.py` already resolves
      device keys against a branch id).
- [x] 1.3 Wire both checks into `org_structure/service.py::delete_branch`,
      mirroring `auth/service.py::delete_role`'s
      `has_active_grants()` guard: return 409 via `error_response` if either
      check finds an active reference, leaving the branch undeleted.
- [x] 1.4 Confirm the 409 error message distinguishes "active children" from
      "active device credentials" (or lists both) so an operator knows what
      to clean up first, without leaking internal ids beyond what
      `org_structure`'s existing 409 responses already expose.

## 2. Verify Creating a Child Under an Already Soft-Deleted Parent Is Rejected (org_structure)

- [x] 2.1 Confirmed by code inspection: `create_building`, `create_department`,
      and `create_security_gate` all resolve their `branchId` via
      `org_structure/deps.py::authorize_branch_id`, which uses
      `BranchRepository.get()` (excludes soft-deleted rows) before the
      service layer runs — a soft-deleted branch already 404s. `create_floor`
      resolves its building via `service.resolve_building_branch_id`
      (non-tolerant) before authorizing, and `create_reception_desk`
      resolves its floor via `service.resolve_floor_branch_id` (also
      non-tolerant) — both already 404 on a soft-deleted parent. No code
      change needed; this task is the verification record for task 6.2's
      tests, which assert this documented-but-previously-untested behavior.

## 3. Tolerant Branch Resolution for Invitation Approval

- [x] 3.1 Add `BranchRepository.get_including_deleted` (`org_structure/
      repository.py`), mirroring `BuildingRepository`/`FloorRepository`'s
      existing method of the same name.
- [x] 3.2 Add `authorize_branch_id_tolerant` (`org_structure/deps.py`),
      identical to `authorize_branch_id` except it resolves the branch via
      `get_including_deleted` instead of `get()`, so a since-soft-deleted
      branch no longer 404s.
- [x] 3.3 In `invitations/router.py::approve_invitation`, replace the
      `authorize_branch_id` call with `authorize_branch_id_tolerant` — the
      caller's own branch-permission check (`invitations:approve` at that
      branch) still runs against the invitation's recorded `branch_id`
      exactly as before; only the branch-existence tolerance changes.

## 4. UserRepository Base Class Consistency (auth)

- [x] 4.1 Audit `auth/repository.py::UserRepository`'s existing methods for
      any that intentionally read soft-deleted users (e.g. an audit/history
      path) before switching its base class.
- [x] 4.2 Change `UserRepository` to inherit `TenantScopedRepository[User]`,
      removing its hand-written `deleted_at IS NULL` filters in favor of the
      base class's. If 4.1 found a method that needs soft-deleted rows,
      give it an explicit override (e.g. a dedicated
      `get_including_deleted`-style method) rather than losing that
      capability.
- [x] 4.3 Run `auth/tests.py` to confirm no behavior change.

## 5. Test Coverage

- [x] 5.1 `org_structure/tests.py`: add tests for the new branch-deletion
      guard — 409 with an active child of each entity type, 409 with an
      active device key, and success once none remain (task 1's scenarios).
- [x] 5.2 `org_structure/tests.py`: add tests for creating a
      Building/Department/Floor/ReceptionDesk/SecurityGate under an
      already-soft-deleted parent, asserting 404 for each entity level
      (task 2's already-correct behavior, previously untested).
- [x] 5.3 `invitations/tests.py`: add a test that approves a `submitted`
      invitation whose branch was soft-deleted after creation, asserting
      the approval succeeds (task 3's scenario).
- [x] 5.4 `registrations/tests.py`: add a regression test — a device
      credential resolving to a soft-deleted branch is rejected the same
      way an inactive one is (401, no 500), as the direct repro/regression
      test for the originally reported bug.
- [x] 5.5 `auth/tests.py`: add tests for `assign_branch_role` rejecting a
      soft-deleted role and a soft-deleted branch (today only unknown-id is
      tested).
- [x] 5.6 `platform/tests.py`: add a permission-denied/negative-auth test
      for `POST /platform/tenants` (today only `GET /platform/tenants` has
      one).
- [x] 5.7 `visit_info/tests.py`: add tenant-isolation tests for
      `GET /visit-info/departments` and `GET /visit-info/options` (today
      only `search_hosts` has one).
- [x] 5.8 Build all new test rows through the existing `factories.py`
      `SQLAlchemyFactory` subclasses, consistent with `testing-standards.md`
      §1 and the pattern already used throughout these files.

## 6. Verification

- [x] 6.1 Run `ddev exec uv run pytest` for the full suite; confirm 100%
      green including every new test from Section 5.
- [x] 6.2 Run `ddev exec uv run ruff check` and
      `ddev exec uv run ruff format --check` on the full tree.
- [x] 6.3 Run `ddev exec uv run mypy` on `core/`, `auth/`, and any other
      touched module in strict scope per `project-rules.md`'s static-typing
      rule.
- [x] 6.4 Manually re-verify the original reported scenario end-to-end:
      soft-delete a branch with an active walk-in device key provisioned
      against it — confirm the delete is now rejected with 409 instead of
      succeeding, and that an already-existing (pre-fix) orphaned device
      key against a soft-deleted branch still fails walk-in registration
      cleanly (401, not 500).
- [x] 6.5 Confirm no existing test's assertions changed meaning — only new
      tests were added and only the specific behaviors in Sections 1-4
      changed, per `proposal.md`'s compatibility note. Note: the RBAC
      route-dependency migration originally planned as a Section 4 was
      dropped mid-implementation (see `design.md` Decisions) — no
      `org_structure`/`invitations` router permission-check code changes.
