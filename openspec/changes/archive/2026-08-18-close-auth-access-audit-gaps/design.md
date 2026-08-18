## Context

See `proposal.md` - Why for the full audit table. This document covers the
two traceability gaps in more depth and the one small code guard scoped to
close them.

**Gap 1 — "company_id" vs. `tenant_id`.** The requirement text asks the
system to "carry company_id from day one for future multi-tenant readiness."
Read literally, and cross-referenced with `grep -rn "company_id" src/`
(zero hits), this looks unimplemented. It isn't: `database-architecture.md`
§2 already committed to schema-per-tenant, where `Tenant.id` (global
schema, carried as the JWT `tenant_id` claim — `core/security.py::_create_token`)
*is* the SaaS-account/company boundary future multi-tenancy would key off of.
Separately, `org_structure/models.py::Company` exists — "this tenant's own
business profile... exactly one row is expected per tenant schema, enforced
in `service.py`" (its own docstring). Two different concepts share the word
"company" here: the requirement's "company_id" (a stable per-account
identifier) maps onto `tenant_id`, not onto `Company.id` (a business-profile
row with no per-request resolution or context binding at all — no
`get_company_context` dependency exists, unlike `get_branch_context`).
Today this mapping exists only in the heads of whoever built it (see the
`project-auth-access-api` memory: "company_id/multi-tenant-readiness was
already solved by the existing schema-per-tenant `tenant_id` design") — it
was never written down anywhere a future auditor (including this one, on
first pass) would find it before re-flagging the requirement as missing.

**Gap 2 — the inert "visitor" role.** `auth/rbac_catalog.py::ROLE_PERMISSIONS`
correctly lists all five roles the requirement names, but `"visitor": []`
is a placeholder that grants nothing and is never meant to be assigned to a
`User` — visitors don't have `User` rows or JWTs at all under this
architecture (`security-architecture.md` §2). `auth/service.py::assign_branch_role`
takes any `role_id` that resolves via `RoleRepository`, with no check against
which roles are meaningful to assign. Assigning "visitor" today would not
grant any privilege (empty permission set) but would create a confusing,
semantically-wrong `UserBranchRole` row — a staff account "playing" the
Visitor role.

## Goals / Non-Goals

**Goals:**
- Make both gaps explicit and permanent in the spec/docs, so this exact
  re-audit question doesn't recur.
- Close the one real (if low-severity) loose end the audit found — the
  assignable-but-meaningless "visitor" role — with the smallest possible
  guard.

**Non-Goals:**
- Introducing a literal `company_id` field distinct from `tenant_id`. No
  scenario in the product requirement or the existing tenancy design needs a
  tenant to represent more than one company; adding one now would be
  speculative schema surface with no current consumer.
- Building a `get_company_context` dependency analogous to
  `get_branch_context`. There is exactly one `Company` row per tenant
  schema (enforced business rule), so there is nothing for a per-request
  header/claim to disambiguate — unlike branch, where a tenant genuinely has
  many.
- Revisiting the branch-context-as-DI-not-middleware architecture. That's
  already the correct implementation of `fastapi-architecture.md` §6's DI
  mandate, not a defect.

## Decisions

### Decision 1: Document the tenant_id ↔ "company_id" equivalence rather than adding a new field

Add a short, explicit section to `docs/features/auth.md` and a spec
requirement (below) stating that `tenant_id` is the field satisfying API-01's
"carry company_id" clause, and why `Company.id` is not that field.

**Alternative considered**: add a `company_id` claim to the JWT anyway,
sourced from the tenant's single `Company` row, purely to match the
requirement's literal wording. Rejected — it would be a second field
carrying information `tenant_id` already carries 1:1 (exactly one `Company`
per tenant), adding a claim that must be kept in sync with zero behavioral
payoff, and inviting exactly the kind of "which one is real" confusion this
change is trying to remove.

### Decision 2: Reject assigning the "visitor" role to a `User`

`assign_branch_role` (`auth/service.py`) raises `HTTPException(409, ...)` (or
the project's existing conflict-response convention — see `create_user`'s
duplicate-email 409 for the precedent) when the resolved `Role.name ==
"visitor"`, before creating the `UserBranchRole` row.

**Alternative considered**: remove the "visitor" row from
`ROLE_PERMISSIONS` entirely, since it grants nothing and can't be assigned.
Rejected — the requirement explicitly names Visitor as one of the five RBAC
roles the catalog must reflect; deleting it would make API-02's own
role-list check ("does the catalog contain these five names") fail literally,
trading a real compliance signal for a marginal cleanup.

## Risks / Trade-offs

- [Risk] Hardcoding the check against the literal string `"visitor"` couples
  `assign_branch_role` to a magic role name rather than a `Role.is_assignable`
  column → Mitigation: only one such role exists today and the catalog is
  small and centrally defined in `rbac_catalog.py`; a schema column is easy
  to add later if a second non-assignable role ever appears, per this
  project's bias against pre-building abstractions for a single case.
- [Trade-off] Documenting `tenant_id` as satisfying "company_id" instead of
  adding a same-named field keeps the schema lean but means anyone grepping
  for `company_id` in this codebase (as this very audit initially did) still
  finds nothing — the fix is a docs/spec pointer, not a code symbol.
  Accepted, since the alternative (a redundant field) is worse.

## Migration Plan

- No data migration. No new dependencies. No `.env`/`settings` changes.
- The `assign_branch_role` guard is a new rejection path on a request shape
  nothing currently sends (no seed script or existing test assigns
  "visitor"), so it is safe to deploy without a compatibility window.
