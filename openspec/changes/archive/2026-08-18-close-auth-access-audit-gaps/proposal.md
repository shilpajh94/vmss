## Why

The user asked to re-verify, against the requirement text in
`Visitor Management System Product Configuration.pdf` and the original API
spec lines below, whether the already-delivered Auth & Access implementation
is actually correct:

> API-01 · Auth & Access · JWT auth + branch/location-scoped access context
> middleware (single company, many branches). Carry company_id from day one
> for future multi-tenant readiness.
>
> API-02 · Auth & Access · Role-based access control (Admin, Reception,
> Security, Host, Visitor), scoped per branch/location.

A prior compliance audit (`archive/2026-08-17-core-api-compliance-audit`)
already marked both items "Compliant" using a compressed one-line
description of each. Re-reading the two requirements at their original,
fuller wording surfaced two things that one-line description had smoothed
over — not functional defects, but traceability gaps that make the
implementation harder to verify against the requirement text than it should
be.

**Audit result:**

| API | Requirement | Verdict |
|---|---|---|
| API-01 | JWT auth | **Compliant** — PyJWT access + refresh tokens, Argon2 password hashing (`core/security.py`). |
| API-01 | Branch/location-scoped access context | **Compliant, via a different mechanism than "middleware."** `org_structure/deps.py::get_branch_context` resolves and authorizes `X-Branch-ID` as a FastAPI dependency, not an ASGI middleware — the project's own `fastapi-architecture.md` §6 mandates the DI pattern over ad-hoc middleware, so this is the correct implementation of the requirement's intent, not a deviation to fix. |
| API-01 | Carry company_id from day one for future multi-tenant readiness | **Functionally satisfied, traceability gap.** `grep -rn "company_id" src/` returns zero matches. The requirement's intent — a stable identifier carried on every token/request so a second tenant can be onboarded later without a redesign — is already met by `tenant_id` (JWT claim, `core/security.py`; bound into every log line, `core/tenancy.py::get_current_user`). Schema-per-tenant means one Postgres schema *is* one company account, so `tenant_id` already **is** the requirement's "company_id." Nothing in the specs or docs says so explicitly, which is how this audit almost re-flagged it as missing. |
| API-02 | Roles: Admin, Reception, Security, Host, Visitor | **Compliant.** `auth/rbac_catalog.py::ROLE_PERMISSIONS` has exactly these five keys, seeded into every tenant at provisioning (`platform/service.py::create_tenant`). |
| API-02 | Scoped per branch/location | **Compliant.** `UserBranchRole(user_id, role_id, branch_id)` — a concrete `branch_id` scopes the grant to one branch, `NULL` means company-wide (used for Admin). Enforced end-to-end on org-structure/employee endpoints, not just modeled — see `docs/features/org_structure.md`. Covered by `auth/tests.py::test_assign_branch_role_scopes_access_to_that_branch` and `test_tenant_schema_isolation`. |
| API-02 | The "Visitor" role specifically | **Compliant but inert by design, undocumented as such.** `ROLE_PERMISSIONS["visitor"] = []` — a visitor never authenticates through this JWT/RBAC system at all (`security-architecture.md` §2: visitor-facing flows are unauthenticated, signed-token/QR based). The row exists only so the catalog literally lists all five names the requirement asks for. Nothing currently stops `POST /auth/users/{id}/branch-roles` from granting the "visitor" role to a real staff `User` row, which would be harmless (zero permissions) but semantically confused — a `User` is staff, not a visitor. |

## What Changes

- **No change** to JWT issuance, branch-context resolution, or the RBAC
  permission model — all verified correct as built.
- Document, in both `docs/features/auth.md` and a new baseline spec for the
  `auth` capability (below), that `tenant_id` is the concrete field that
  satisfies API-01's "carry company_id from day one" requirement, and why the
  separate `org_structure.Company` row (this tenant's own business profile —
  `org_structure/models.py::Company`) is deliberately *not* carried in request
  context or JWT claims: exactly one `Company` row is enforced per tenant
  schema, so there is no ambiguity for a per-request identifier to resolve.
- Add a guard in `auth/service.py::assign_branch_role` rejecting an attempt to
  grant the `visitor` role to a `User`, with a short doc note in
  `auth/rbac_catalog.py` explaining the role exists only to keep the catalog's
  five names complete and is intentionally never assignable.
- **Non-goal, explicitly deferred**: introducing an actual `company_id`
  column/claim distinct from `tenant_id` and `Company.id`. Nothing in the
  product requirement, the codebase's own multi-tenancy design
  (`database-architecture.md` §2), or this audit surfaces a real scenario
  where a tenant would ever span more than one company — if that changes,
  it's a schema/tenancy redesign, not a docs fix, and out of scope here.

## Capabilities

### New Capabilities
- `auth`: baseline requirements for JWT issuance, tenant/branch-context
  resolution, and branch-scoped RBAC — the `auth` feature package
  (`src/vmss_api/auth/`) has never had a baseline spec captured (only
  `api-compliance-hardening` and `api-documentation` exist under
  `openspec/specs/` today), so this change establishes it rather than
  reopening `api-compliance-hardening` for an unrelated feature area.

### Modified Capabilities
- None.

## Impact

- **Code**: `src/vmss_api/auth/service.py` (`assign_branch_role` guard),
  `src/vmss_api/auth/rbac_catalog.py` (comment only).
- **Docs**: `docs/features/auth.md` (tenant_id ↔ company_id equivalence,
  visitor-role non-assignability).
- **Tests**: one new case in `auth/tests.py` —
  attempting to assign the `visitor` role via
  `POST /auth/users/{id}/branch-roles` returns a 4xx and creates no
  `UserBranchRole` row.
- **No breaking changes**: the guard only rejects a request shape nothing
  currently relies on (no existing test or seed script assigns "visitor" to a
  `User`).
- **Out of scope**: the API-06 approval-evaluation engine and API-11 SMS
  gateway gaps flagged in the prior compliance audit are untouched by this
  change.
