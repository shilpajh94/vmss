## Context

See `proposal.md` - Why. Two independent fixes, bundled into one change
because they were reported together and both block web/app integration.

All six org-structure listing endpoints (`list_branches`,
`list_buildings`, `list_floors`, `list_departments`,
`list_reception_desks`, `list_security_gates`) currently share one
dependency shape in `org_structure/router.py`:

```python
branch_scope: Annotated[BranchScope, Depends(require_branch_scope("<x>:view"))]
tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]
```

`get_tenant_db` (`core/tenancy.py`) resolves the tenant from the JWT's
`tenant_id` claim, and `require_branch_scope` (`org_structure/deps.py`)
requires `get_current_user` to compute which branches the caller is
authorized for. Removing the token means both must be replaced — there is
no JWT to read a tenant or a caller from.

Two existing public-endpoint dependencies already solve the "no JWT, still
need a tenant-bound session" problem the same way, and this design reuses
that precedent instead of inventing a third:
`invitations/deps.py::track_default_tenant_db` and
`identity_verification/deps.py::default_tenant_id` — both resolve
`settings.default_tenant_slug` via `TenantRepository`, flagged in both
places as a known single-tenant limitation to replace with real
hostname/slug-based tenant routing once a second tenant exists.

For the email side: `identity_verification/senders.py::SmtpEmailSender.send`
already catches `aiosmtplib.SMTPException` and logs at `WARNING` with
`error=str(exc)` before raising `EmailDispatchError`. `str(exc)` on an
`aiosmtplib` exception is frequently terse (e.g. just an errno), which is
enough to reproduce "it failed" but not "why" when the failure only happens
on the dev server and can't be reproduced locally against Mailpit.

## Goals / Non-Goals

**Goals:**
- Make the six org-structure listing endpoints callable with no bearer
  token, while leaving every other org-structure endpoint's authentication
  and permission checks untouched.
- Give the dev-server email failure enough server-side log detail (host,
  port, exception type/message) to root-cause without reproducing it
  locally.

**Non-Goals:**
- Diagnosing or fixing the dev server's actual SMTP configuration/network
  path — that happens after this change ships and its logs are read; it is
  an ops/infra follow-up, not part of this change.
- Extending public (no-token) access to any endpoint beyond the six listed
  — get-by-id, create, update, delete, bulk-provision, and employee-directory
  endpoints keep their current authentication and RBAC exactly as-is.
- Merging `identity_verification/senders.py` and `invitations/notifications.py`
  into one shared notifications package — out of scope, per the existing
  `add-identity-verification-otp/design.md` Non-Goals this change doesn't
  revisit.

## Decisions

### Decision 1: New public dependencies in `org_structure/deps.py`, preferring a presented token's own tenant over the default
Add two dependencies local to `org_structure`. `public_tenant_db` was
initially implemented as a straight copy of
`invitations/deps.py::track_default_tenant_db` (always resolve
`settings.default_tenant_slug`, ignore any token) — running the full test
suite during implementation caught this as wrong:
`tests/test_workflow_staff_admin.py::test_staff_admin_full_workflow`
provisions a second, non-default tenant and then, *authenticated* as that
tenant's own admin, calls `GET /branches` expecting its own branches back.
A token-blind resolver sends that request to the default tenant's schema
instead — a real cross-tenant correctness bug the moment a second tenant
exists, not just a test artifact, and exactly what
`database-architecture.md` §2 warns against ("do not add code that assumes
there's only ever one [tenant]"). The corrected version:

```python
async def _tenant_from_bearer_token(
    db: AsyncSession, credentials: HTTPAuthorizationCredentials
) -> Tenant | None:
    """Never raises — an absent/invalid/expired token or one with no
    resolvable tenant just yields None so the caller falls back."""
    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        return None
    if payload.get("type") != "access":
        return None
    raw_tenant_id = payload.get("tenant_id")
    if raw_tenant_id is None:
        return None
    try:
        tenant_id = uuid.UUID(raw_tenant_id)
    except ValueError:
        return None
    return await TenantRepository(db).get(tenant_id)


async def public_tenant_db(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer_scheme)
    ] = None,
) -> AsyncGenerator[AsyncSession]:
    """Prefers the token's own tenant when present and valid; falls back to
    settings.default_tenant_slug otherwise — mirrors
    invitations/deps.py::track_default_tenant_db's single-tenant limitation
    only for the fallback path, not unconditionally."""
    tenant = await _tenant_from_bearer_token(db, credentials) if credentials is not None else None
    if tenant is None:
        tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session


async def public_branch_scope(
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
) -> BranchScope:
    """Public counterpart to require_branch_scope: no caller, so no
    permission check — only validates X-Branch-ID when supplied."""
    if x_branch_id is not None:
        branch = await BranchRepository(tenant_db).get(x_branch_id)
        if branch is None or not branch.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")
        return frozenset({branch.id})
    return "all"
```

Each of the six list endpoints swaps its dependencies:
`Depends(require_branch_scope("<x>:view"))` → `Depends(public_branch_scope)`,
`Depends(get_tenant_db)` → `Depends(public_tenant_db)`. `get_current_user`
is not present on these endpoints today (it's pulled in transitively via
`require_branch_scope`), so removing that one dependency is the entire
change to each function signature. `service.list_*_page(...)` call sites
are unchanged — they already accept `branch_scope: BranchScope` and treat
`"all"` as unscoped, exactly as they do today for a caller with a
company-wide `*:view` permission.

**Alternative considered**: make `get_tenant_db`/`require_branch_scope`
themselves tolerate a missing token. Rejected — those two are the
authenticated code path every other org-structure endpoint (and every
other feature) relies on; branching inside them on "is there a token"
would weaken a shared, security-relevant dependency to special-case one
feature's six endpoints, instead of adding a narrow, obviously-public
alternative next to it.

### Decision 2: Rate limit the six endpoints at 60/minute per IP
`security-architecture.md` §2 requires rate limiting on every
unauthenticated endpoint. The existing public endpoints (OTP request/verify,
invitation tracking) use `@limiter.limit("20/minute")` for actions that
send a message or reveal a specific record. Master-data listing is read-only
and far less abuse-sensitive (it can't be used to spam a visitor or brute-
force a record by id), so a higher ceiling — `60/minute` per IP, the same
`slowapi` `limiter` instance — is used instead of reusing the 20/minute
figure verbatim.

### Decision 3: Log SMTP host/port and exception type/message on dispatch failure, at the existing WARNING level
`SmtpEmailSender.send`'s existing `except aiosmtplib.SMTPException` handler
adds `smtp_host=settings.smtp_host`, `smtp_port=settings.smtp_port`, and
`exception_type=type(exc).__name__` alongside the existing masked
`identifier` and `error=str(exc)` fields, still at `WARNING` (this is a
caught, recoverable failure surfaced to the caller as 503 — not an
unhandled exception, so `logging-observability.md` §3's level policy still
calls for `WARNING`, not `ERROR`). No behavior visible to the caller
changes: the same `EmailDispatchError` is raised, the same 503 with the
same message is returned by `router.py`.

**Alternative considered**: log at `ERROR` instead. Rejected — the
call is caught and handled (a 503 with a stable, documented message), which
is exactly `logging-observability.md` §3's definition of a recoverable
anomaly (`WARNING`), not an unhandled exception or exhausted-retries case
(`ERROR`).

## Risks / Trade-offs

- [Risk] Master-data listing endpoints (branch/building/floor/department/
  desk/gate) become visible to anyone who can reach the API, with no
  authentication — a scraper could enumerate a tenant's entire physical
  footprint (branch names, building/floor/department names, gate/desk
  locations). → Mitigation: this data is operational metadata, not visitor
  PII (no identity documents, no visit records, no personal data) — the
  categories this system's security model treats as sensitive
  (`security-architecture.md` §4) are check-in records and identity
  documents, neither of which these endpoints expose. Rate limiting bounds
  scrape volume per IP; the six endpoints have no reduction in scope beyond
  today aside from the auth check itself (get-by-id/create/update/delete are
  untouched).
- [Risk] `public_tenant_db`/`public_branch_scope` duplicate
  `track_default_tenant_db`'s single-tenant-slug limitation a third time
  (invitations, identity-verification, now org-structure) instead of
  extracting a shared helper. → Mitigation: deliberate, matching this
  codebase's existing choice not to share the near-identical
  `identity_verification/senders.py` / `invitations/notifications.py`
  sender abstractions yet (design.md Non-Goals) — extract a shared
  `core` helper once a second tenant exists and all three call sites need
  to change together anyway, rather than guessing the right shared shape
  now.
- [Risk] A client that depended on getting 401/403 from these six endpoints
  as an access-control signal (e.g. to gate a UI element) will stop seeing
  that. → Mitigation: called out explicitly as a **BREAKING** change in
  `proposal.md`; get-by-id/create/update/delete endpoints for the same
  entities are untouched, so any real access control for mutating this data
  is unaffected.

## Migration Plan

- No database migration. No feature flag — both fixes ship together in one
  deploy; the listing-endpoint change takes effect immediately for every
  existing client (which today all send a token these endpoints will no
  longer inspect, so existing callers keep working unchanged).
- Rollback is a plain revert: reinstating `require_branch_scope`/
  `get_tenant_db` on the six endpoints, or the previous log statement,
  restores prior behavior exactly.
