## Context

`GET /auth/employees` (router.py:257–287, service.py:472–489,
`UserRepository.list_employees_page` repository.py:80–130) is currently
gated by `require_branch_scope("employees:view")`
(`org_structure/deps.py:101–127`), which depends on `get_current_user` and
therefore a bearer token — the token is also this endpoint's only source of
`tenant_id` (`database-architecture.md` §2: tenant is a JWT claim, never a
client-supplied header/param). Removing the token removes the only channel
this endpoint has for resolving which tenant schema to query.

Org-structure already solved exactly this problem for its own public listing
endpoints (`Branch`, `Building`, `Floor`, `Department`, `ReceptionDesk`,
`SecurityGate` — see `openspec/specs/org-structure/spec.md`'s "Master-Data
Listing Endpoints Are Public" requirement): `org_structure/deps.py`'s
`public_tenant_db` (155–180) prefers the tenant from a *presented* token when
one validates, else falls back to `settings.default_tenant_slug`; and
`public_branch_scope` (183–196) makes `X-Branch-ID` optional with no
caller-authorization check. See proposal.md - Why for the product motivation
(frontend no longer wants to send a token on this call); this document is
about reusing that existing mechanism rather than inventing a new one.

## Goals / Non-Goals

**Goals:**
- Make `GET /auth/employees` work with no bearer token, using the same
  tenant/branch resolution mechanism already shipped for org-structure's
  public listing endpoints — no new trust model introduced.
- Add `email` (exact match) and `role` (by name, across any branch-role
  assignment) filters to the same endpoint.
- Drop `authMethod` and `connectivityStatus` from `SecurityGate` cleanly,
  including the DB columns.

**Non-Goals:**
- Changing the single-employee-create endpoint (`POST /auth/employees`) or
  the bulk directory-sync endpoint's auth — both keep requiring
  `employees:manage` and a token. Only the list endpoint changes.
- Changing `ReceptionDesk`'s three-state status or `SecurityGate.highSecurity`
  / `gateType` — explicitly out of scope per the clarified requirements.
- Introducing a general "trust a client-supplied tenant header" mechanism —
  this reuses the existing token-optional-with-default-tenant-fallback
  pattern, not a new one.

## Decisions

**Reuse `public_tenant_db`/`public_branch_scope` for the employee list route,
rather than a bespoke dependency.** These live in `org_structure/deps.py`;
`auth/router.py` will import and depend on them directly the same way
`org_structure/router.py` already does for gates/desks/branches. Alternative
considered: write an `auth`-local equivalent to avoid a cross-package import
— rejected, since `core/tenancy.py` already accepts a sanctioned upward
dependency from `core` onto `auth`/`tenant` (`fastapi-architecture.md` §6),
and `org_structure` importing into `auth` (or `auth`'s router depending on an
`org_structure` dep function) is no worse a coupling than duplicating
tenant-fallback logic in two places — one dependency, one behavior to keep
consistent.

**Drop `require_branch_scope("employees:view")` entirely on this route
instead of making the permission check optional.** There is no caller
identity once the token is optional, so there is nothing to check a
permission against on the (common) unauthenticated path. This matches how
org-structure's public listing endpoints behave — no permission check at
all, full stop — rather than a conditional check that only applies when a
token happens to be present.

**`role` filter matches by name via a join on `UserBranchRole`/`Role`, with
`DISTINCT` on `User.id`.** A user can hold the same or different roles at
multiple branches; filtering must not duplicate a matching user in the page
or inflate `total`. `list_employees_page` (repository.py) already builds a
`conditions` list and a base query — the role filter adds a join and an
`EXISTS`-style condition (or a `DISTINCT`-safe join, whichever the existing
query shape supports more cleanly) rather than a plain join that could
fan out rows before pagination is applied.

**`email` filter is exact match, not partial/`ILIKE`.** `User.email` is
unique and indexed (`auth/models.py:75`); exact match is what "filter by
email" means for a directory lookup (find this one person), keeps the query
sargable against the existing unique index, and avoids turning a directory
filter into a search box with its own UX/perf considerations. If partial
match is wanted later, that is an additive change, not a breaking one.

**`GET /auth/employees` keeps `@limiter.limit("60/minute")`, added during
implementation.** Missed in the original proposal/design pass:
`security-architecture.md` §2 requires rate limiting on every unauthenticated
endpoint, and the six public org-structure listing endpoints already carry
this (`org_structure/router.py`'s `@limiter.limit("60/minute")` on each).
Making the employee list public without the same limit would leave it as
the one unauthenticated endpoint in the API with no rate limit — added to
match, and folded back into the spec delta's "Employee Directory Sync"
requirement.

**Gate field removal is a genuine column drop, not a deprecate-in-place.**
Both fields are confirmed unused outside `org_structure/` (models, schemas,
service, factories, tests, and the archived proposal that introduced them —
`database-architecture.md`'s modeling standards don't call for a soft
"nullable and ignored" transition here since nothing external depends on
these columns). New migration chains after the current tenant-schema head
(`a05c36d976c4`), following the drop pattern already demonstrated in
`524da546af26_desk_gate_tri_state_status.py`'s own `downgrade()` (which drops
these same two columns, among others) — schema-qualify the `op.drop_column`
calls per that migration's own documented `schema=` landmine
(`database-architecture.md` §5 / `gotcha_alembic_add_column_schema_translate_map`
memory: `op.add_column`/`op.drop_column` ignore `schema_translate_map` and
need `schema=` passed explicitly).

## Risks / Trade-offs

- **Employee PII becomes listable with no authentication** (email, phone,
  designation, avatar) → Mitigation: this is the explicitly requested
  behavior and reuses an existing, already-shipped pattern rather than a new
  one; flagged prominently in proposal.md's Impact section as a product/
  security decision to confirm, not silently shipped as "just a technical
  change." No further mitigation is implemented here beyond what the
  proposal calls for — narrowing this later (e.g. requiring a lightweight
  API key) is a follow-up if the confirmation comes back "no, don't expose
  this publicly."
- **Losing `employees:view` company-wide/per-branch scoping semantics** on
  this endpoint means a caller can no longer be limited to only the branches
  they're authorized at — `X-Branch-ID` becomes a pure filter, not an
  authorization boundary → Mitigation: none beyond documenting it; this is
  the direct, unavoidable consequence of removing the token, consistent with
  how the master-data listing endpoints already behave.
- **Dropping `auth_method`/`connectivity_status` columns is irreversible
  without restoring historical data** (the migration's `downgrade()` can
  re-add the columns but not recover values written before the drop) →
  Mitigation: confirmed no other feature reads these fields, and existing
  gate tests referencing them are being removed/rewritten in the same
  change, so there's no silent breakage elsewhere.

## Migration Plan

1. Repository/service/schema/router changes for employee list filters + auth
   removal (no DB migration needed — no new columns).
2. Gate schema/model/service changes removing the two fields.
3. New `alembic_tenant` migration (`down_revision = "a05c36d976c4"`) dropping
   `security_gates.auth_method` and `security_gates.connectivity_status`,
   schema-qualified.
4. Update `SecurityGateFactory` and the two now-invalid gate tests
   (`test_create_security_gate_with_offline_connectivity`,
   `test_update_security_gate_connectivity_status`).
5. Add employee-list filter tests and a no-token-required test; remove/adjust
   any existing permission-denied test that assumed this endpoint required
   `employees:view`.
6. Rollback: revert the code changes and run the migration's `downgrade()`
   to restore the two gate columns (nullable, no data) if this needs to be
   backed out post-deploy.
