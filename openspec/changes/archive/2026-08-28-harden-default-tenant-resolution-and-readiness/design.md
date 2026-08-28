## Context

See `proposal.md` - Why for the root-cause chain. Four call sites resolve
`settings.default_tenant_slug` today, three of them independently:

- `registrations/deps.py::_resolve_default_device_context` - resolves
  default tenant AND `settings.registration_default_branch_code`; logs
  `ERROR` via `logger.error(event, reason=..., **fields)` distinguishing
  not-found vs. inactive; raises 401
  `"Registration service is not configured for this environment"`.
- `visit_info/router.py` - imports `get_registration_device` directly
  (the same function above), so it already inherits this behavior exactly.
  No change needed there.
- `identity_verification/deps.py::default_tenant_id` - resolves only the
  default tenant (no branch concept in this feature); no `logger` call at
  all; raises 404 `"Tenant not found or inactive"`.
- `invitations/deps.py::track_default_tenant_db` - resolves only the
  default tenant; no `logger` call at all; raises 404
  `"Tenant not found or inactive"`.

`main.py::health_ready` checks `SELECT 1` against Postgres and `PING`
against Redis only.

## Goals / Non-Goals

**Goals:**
- One resolver function backs all default-tenant lookups; a default-branch
  lookup layers on top of it for the one caller (`registrations`) that
  needs it.
- `identity_verification` and `invitations` gain the same `ERROR`-level,
  not-found/inactive-distinguishing log the resolver already produces for
  `registrations`, with zero change to either feature's client-facing
  status code or message.
- `/health/ready` fails closed (503) when the default tenant or default
  branch doesn't resolve, without adding a second live database round trip
  beyond what the resolver itself already does.

**Non-Goals:**
- Not replacing the single-default-tenant design with real hostname/header
  -based multi-tenant routing for these public endpoints - that is the
  already-flagged, separately-tracked limitation each feature's docs
  describe (`docs/features/identity_verification.md`,
  `docs/features/invitations.md`).
- Not changing `registrations`' own behavior or tests - it is the reference
  implementation the other two are brought in line with.
- Not fixing `vmss-dev`'s actual misconfigured state - an operational
  action outside this change (`proposal.md` - Impact).

## Decisions

**Shared resolver lives in `core/tenancy.py`, not a new module.**
`core/tenancy.py` already owns the JWT-based `get_tenant`/`get_current_user`
chain and is the one place `fastapi-architecture.md` §6 already sanctions
for cross-feature tenant-resolution infrastructure. Adding
`resolve_default_tenant(db) -> Tenant` (raises a typed
`DefaultTenantUnresolved` exception on failure, carrying `reason:
"not_found" | "inactive"`) here keeps the "core is allowed to import
`auth`/`tenant`" exception (`fastapi-architecture.md` §6) as the only
upward dependency, rather than inventing a second one for
`identity_verification`/`invitations`/`registrations` to import from each
other.

Alternative considered: put the shared resolver in `registrations/deps.py`
and have `identity_verification`/`invitations` import from there. Rejected
- nothing about default-tenant resolution is conceptually owned by
`registrations`; it happens to be first to implement it correctly. Making
two unrelated features depend on a third feature's internal module for
shared infrastructure is the wrong dependency direction.

**`resolve_default_tenant` raises; each caller translates.** The resolver
itself does not raise an `HTTPException` - it raises
`DefaultTenantUnresolved(reason=...)`, a plain exception `core/tenancy.py`
defines. Each of the three call sites catches it and raises its own
existing status code/message (401 for `registrations`, 404 for
`identity_verification`/`invitations`), logging `ERROR` with the
distinguishing `reason` before doing so. This is what makes "no
client-visible contract change" possible: the resolver centralizes
detection and logging, not the response shape, which legitimately differs
per feature today and isn't this change's concern to unify.

**Default-branch resolution stays in `registrations/deps.py`.** Only
`registrations` (and `visit_info` via it) needs a default branch; extending
the shared resolver to also handle branch would force
`identity_verification`/`invitations` to depend on `org_structure` for a
concept they don't use. `_resolve_default_device_context` keeps its branch
lookup exactly as-is, calling the new shared `resolve_default_tenant` in
place of its own inline tenant lookup.

**Readiness check reuses the same resolver and branch lookup, does not
duplicate the query.** `health_ready` calls
`core.tenancy.resolve_default_tenant(db)`, and - only if that succeeds -
opens `tenant_session_scope` on the result and calls
`BranchRepository.get_by_code(settings.registration_default_branch_code)`,
the same call `_resolve_default_device_context` makes. Either failure
returns 503 with a body distinguishing "default tenant unresolved" from
"default branch unresolved" from the existing "dependency unreachable"
case, per the new `environment-configuration` requirement's two distinct
scenarios.

Alternative considered: a separate `/health/ready/registration` sub-probe.
Rejected as unnecessary surface - one `/health/ready` response with a
distinguishing field/message covers the requirement without a second
endpoint clients or ops tooling would need to know about.

## Risks / Trade-offs

- [Readiness check now does 1-2 extra queries (tenant lookup, and, if that
  resolves, a tenant-schema branch lookup) per `/health/ready` call] ->
  Acceptable: this endpoint is polled by infra health checks at a low
  frequency (seconds-to-minutes interval), not per-request; the existing
  DB/Redis round trips already dominate its latency.
- [A deployment that never configures `TENANT_DEFAULT_SLUG` /
  `REGISTRATION_DEFAULT_BRANCH_CODE` to a provisioned pair will now show
  `/health/ready` as permanently unready] -> Intentional per this change's
  purpose; `vmss-dev` is exactly this case today, and the fix is the
  operational provisioning step in `proposal.md` - Impact, not a code
  change. A future orchestrator that gates traffic on readiness should
  route around this deployment until it's provisioned correctly, which is
  the desired outcome.
- [Centralizing the resolver in `core/tenancy.py` touches three features'
  import graphs at once] -> Mitigated by keeping every call site's own
  status code, message, and test file unchanged - only the internal lookup
  and logging call move, verified by re-running each feature's existing
  tests unchanged plus the new logging-assertion tests.

## Migration Plan

1. Add `resolve_default_tenant`/`DefaultTenantUnresolved` to
   `core/tenancy.py`.
2. Switch `registrations/deps.py`, `identity_verification/deps.py`,
   `invitations/deps.py` to call it, each keeping its own
   exception-translation and status code.
3. Extend `health_ready` with the default-tenant/branch check.
4. Update the three features' docs and `docs/features/configuration.md`.
5. No data migration, no config change required by this step itself; no
   rollback concern beyond a normal code revert since behavior for a
   correctly-configured deployment is unchanged.
