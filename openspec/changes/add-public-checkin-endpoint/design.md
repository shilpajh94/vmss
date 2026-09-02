## Context

See `proposal.md` - Why for motivation. Relevant current state:

- `PATCH /api/v1/invitations/{id}/check-in` (`invitations/router.py`) requires
  `Depends(get_current_user)` + `authorize_branch_id_tolerant(..., "invitations:checkin", ...)`,
  keyed by the invitation's UUID `id`, and writes an `AuditLog` row with
  `actor_user_id=user.id`.
- `GET /invitations/track` (same file) is the one existing precedent for a
  public, unauthenticated, `tracking_id`-keyed route: it resolves tenancy via
  `invitations/deps.py::track_default_tenant_db` (falls back to
  `settings.default_tenant_slug` since there's no JWT to read a `tenant_id`
  claim from) and is throttled with `@limiter.limit("20/minute")`.
- `auth/audit.py::record_audit_log` already accepts `actor_user_id: uuid.UUID
  | None` — the walk-in registration flow (API-13) already calls it with
  `None` for its unauthenticated writer, so no signature change is needed
  there.
- Only `/api/v1` exists today (`main.py`); there is no `/api/v2` mount or
  precedent for a `Deprecation` response header anywhere in the codebase.

## Goals / Non-Goals

**Goals:**
- Let a caller with only an invitation's `tracking_id` (no bearer token)
  transition it `approved` → `checked_in`, with the same 409/404/idempotency
  guarantees the staff endpoint already gives.
- Deprecate, without removing, the staff `v1` check-in route, following
  `api-conventions.md` §2's versioning rule instead of mutating `v1`'s
  contract in place.

**Non-Goals:**
- Re-exposing every existing `v1` route under `/api/v2`. This change mounts
  `/api/v2` for exactly one route; other resources' breaking changes make
  their own versioning decisions later.
- Any change to who can *approve* an invitation, or to the watchlist-override
  flow — this only affects the check-in transition itself.
- Deciding the v1 route's actual removal date (see Open Questions).

## Decisions

**1. New route lives in `invitations/router.py` as a second router object,
`router_v2`, aggregated by a new `api_router_v2` in `api.py`, mounted at
`/api/v2` in `main.py`.**
Keeps the feature's routes in one file (`fastapi-architecture.md` §1) rather
than a parallel `invitations_v2/` package, while keeping `/api/v2` additive:
`api_router_v2.include_router(invitations.router.router_v2)` only, not a
second `include_router` call per existing feature. Alternative considered:
mount the *same* `router` object under both prefixes — rejected, since that
would put every current `v1` invitations route under `v2` too, contradicting
the point of scoping the breaking change to one endpoint
(`api-conventions.md` §2's "a new prefix for *that resource*", not the whole
API).

**2. Tenant resolution reuses the `track_default_tenant_db` pattern.**
Add a sibling dependency, `track_default_tenant`, in `invitations/deps.py`
that also calls `resolve_default_tenant` but returns the `Tenant` (not a
bound session) — needed for the idempotency cache key (`tenant.id`) and the
audit call's `tenant.schema_name`, neither of which `track_default_tenant_db`
exposes today. Both dependencies independently resolve the same single-row
`tenants` lookup; this is two cheap, independent per-request dependency
calls, not the N-per-item loop `query-performance.md` §2 warns about.

**3. Shared check-in transition logic is factored into a private service
helper.**
`service.check_in_invitation` (staff) and the new
`service.check_in_invitation_by_tracking_id` (public) both need the same
409-on-not-approved / 409-on-watchlist-flagged / status-transition logic,
differing only in how the `Invitation` row is looked up (`get(id)` vs
`get_by_tracking_id`) and what `actor_user_id` gets recorded. Factor the
shared part into a private `_perform_check_in(invitation, *, actor_user_id)`
helper both call, rather than duplicating the 409/watchlist checks — this is
genuine shared behavior, not a speculative abstraction.

**4. Public check-in's audit action is a distinct string,
`invitation_checked_in_public`, not a reuse of `invitation_checked_in`.**
The emergency "who's inside" feature and other audit consumers
(`security-architecture.md` §5) benefit from being able to tell a
staff-performed check-in apart from a visitor's own kiosk/self check-in
without inferring it from a null actor. Alternative considered: keep one
action string and rely on `actor_user_id IS NULL`; rejected as a less
discoverable signal for anyone querying the audit log directly.

**5. `Deprecation` header via a small `core/responses.py` helper, not
per-route header assignment.**
Add `mark_deprecated(response: JSONResponse) -> JSONResponse` that sets the
header and returns the response, called as
`return mark_deprecated(success_response(...))` at the one `v1` check-in call
site. First precedent for a deprecated route in this codebase; a shared
helper means the next deprecation (per `api-conventions.md` §2) has an
established, one-line pattern instead of each author reinventing the header
name/format.

## Risks / Trade-offs

- **[Risk] A public, write-capable endpoint keyed by a guessable-in-principle
  string turns a wrong guess into a real state change (a false check-in),
  not just a data leak** — the read-only `GET /invitations/track` accepted
  this trade-off for disclosure; check-in additionally lets an unauthenticated
  caller flip `approved` → `checked_in` for an invitation they don't own if
  they guess correctly. `tracking_id` already carries 32 bits of randomness
  (`service.py::_generate_unique_tracking_id`) and the route is rate-limited
  at 20/minute/IP, the same posture already accepted for the read path — but
  a wrong check-in corrupts the "who's inside" emergency report
  (`security-architecture.md` §5) in a way a wrong *read* doesn't. → Flagged
  as an open item to confirm with the security-architecture owner before
  production launch, consistent with how `file-upload-handling.md` §4 and
  `security-architecture.md` §2 flag comparable open questions rather than
  silently under-building.
- **[Risk] `/api/v2` becomes a dumping ground for unrelated future changes**
  once it exists. → Mitigation: this design and the proposal explicitly scope
  `/api/v2` to this one route; future breaking changes to other resources
  make their own versioning call rather than defaulting to "just add it to
  v2."
- **[Risk] Two independent `resolve_default_tenant` calls per request**
  (Decision 2) instead of one. → Low cost (single indexed-row lookup, not a
  loop); accepted for the isolation it gives the two dependencies.

## Migration Plan

- Purely additive: no Alembic migration (no schema change — `tracking_id` is
  already unique + indexed; `status` stays the existing string column).
- Deploy `v2` route and `v1` deprecation header together; `v1` behavior is
  unchanged apart from the added header, so existing staff/portal clients
  need no changes to keep working.
- Rollback: revert the `v2` route/mount and the `mark_deprecated` call site;
  no data migration to undo since no stored data shape changed.

## Open Questions

- What is the actual `v1` removal date to publish in the `Deprecation` header
  and `docs/features/invitations.md`? Not needed to implement this change
  (the header/note format doesn't depend on the specific date), but must be
  set before `v1` is actually removed.
- Does the risk noted above (public write access via a guessable-in-principle
  identifier) need an additional control — e.g. a short-lived, single-use
  token embedded in the QR alongside `tracking_id`, rather than the bare
  tracking code — before this ships to production? Flagged for the
  security-architecture owner; doesn't change this change's spec, approach,
  or tasks either way.
