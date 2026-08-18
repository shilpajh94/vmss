## 1. Re-Audit API-01 and API-02 (no code change)

- [x] 1.1 Confirmed JWT access/refresh issuance, Argon2 hashing, and
      token-type/expiry rejection are compliant as built
      (`core/security.py`) — no change.
- [x] 1.2 Confirmed branch-context resolution via
      `org_structure/deps.py::get_branch_context` (a FastAPI dependency, not
      ASGI middleware) correctly implements the requirement's intent per
      `fastapi-architecture.md` §6 — no change.
- [x] 1.3 Confirmed `tenant_id` (JWT claim + structlog context) is the field
      satisfying "carry company_id from day one for future multi-tenant
      readiness" — `grep -rn "company_id" src/` returns nothing, and that's
      expected once the tenant_id/company_id equivalence is documented
      (task 2 below), not a gap to fix in code.
- [x] 1.4 Confirmed the five RBAC roles (Admin, Reception, Security, Host,
      Visitor) are seeded correctly and branch-scoped grants are enforced end
      to end — no change.

## 2. Document the tenant_id ↔ "company_id" Equivalence (design.md Decision 1)

- [x] 2.1 Add a section to `docs/features/auth.md` stating explicitly that
      `tenant_id` is the field satisfying API-01's "carry company_id from day
      one" clause, and why `org_structure.Company` (business-profile data,
      one row per tenant) is a different concept, intentionally not carried
      in JWT claims or request-scoped logging context.
- [x] 2.2 Cross-link that section from `docs/features/org_structure.md`'s
      existing `Company` documentation, so a reader starting from either file
      finds the equivalence.

## 3. Reject Assigning the "Visitor" Role to a User (design.md Decision 2)

- [x] 3.1 In `auth/service.py::assign_branch_role`, after resolving `role`,
      reject with a 409 (matching the existing duplicate-email 409
      convention in `create_user`) when `role.name == "visitor"`, before any
      `UserBranchRole` row is created.
- [x] 3.2 Add a short comment in `auth/rbac_catalog.py` next to
      `"visitor": []` noting it exists only to satisfy the five-role
      requirement and is enforced as non-assignable in
      `service.py::assign_branch_role`.
- [x] 3.3 Add `test_assign_visitor_role_to_user_rejected` to `auth/tests.py`:
      a caller with `users:manage` attempts to grant the seeded "visitor"
      role to a `User` via `POST /auth/users/{id}/branch-roles`; assert 409
      and that no new `UserBranchRole` row exists for that user afterward.

## 4. Final Verification

- [x] 4.1 `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`
      clean on `src/vmss_api/auth/`.
- [x] 4.2 `ddev exec uv run mypy src/vmss_api/auth` — clean (strict scope per
      `project-rules.md`).
- [x] 4.3 `ddev exec uv run pytest src/vmss_api/auth/tests.py` — all existing
      cases plus the new 3.3 case green (19 passed).
- [x] 4.4 Full `ddev exec uv run pytest` — no regressions elsewhere (159
      passed, zero failures).
