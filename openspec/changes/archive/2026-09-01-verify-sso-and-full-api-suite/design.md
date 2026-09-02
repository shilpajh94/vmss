## Context

See `proposal.md` - Why for motivation and the "all 19 APIs" scope note.
This design extends `openspec/changes/archive/2026-08-21-complete-api-test-
coverage/design.md`'s workflow-ordered matrix (stages 1-7, API-01..API-15)
with a new Stage "SSO Login" (API-19) inserted right after Auth/RBAC —
confirmed by reading `src/vmss_api/sso/router.py`/`service.py`/`tests.py`
and re-running the full suite before writing this design:

- Current baseline: **345 tests pass** (`ddev exec uv run pytest`), across
  10 feature packages (the original 9 plus `sso`) and `core`/
  `tests/test_api_documentation.py`.
- `sso/tests.py` already has 26 tests from `add-sso-oidc-login`, covering
  most of `testing-standards.md` §2's bar. Reading every test body (not
  just names — the prior audit's own risk callout) surfaced four concrete
  gaps and one real security finding, detailed in the Stage 8 matrix below.
- Stages 1-7 (API-01..API-15) were fully re-audited 3 days ago
  (2026-08-21) and only two files have changed since: `auth/router.py`
  (login rate limit 5/min → 3/min) and `auth/rbac_catalog.py` (two new
  permission codes, `sso-config:manage`/`:view`, added to the `admin`
  role's grant list). Neither change touches those stages' own endpoints
  or logic — this pass re-confirms them are still green rather than
  re-deriving all 27 of the prior matrix's rows from scratch.

## Goals / Non-Goals

**Goals:**
- Prove SSO (API-19) actually works end-to-end via the test suite, not just
  "the code was written and 26 tests pass" — specifically the gaps below.
- Re-confirm stages 1-7 (API-01..API-15) are still fully green, catching
  any regression the two auth-related changes above might have caused.
- Fix the concrete gaps and the SSRF finding below, within the same
  stop-and-report threshold `complete-api-test-coverage` established.
- End with a green full suite, clean `ruff`/`mypy`, and a closing summary
  the user can review before committing.

**Non-Goals:**
- Not re-deriving stages 1-7's full 27-row matrix verbatim — see Context.
  If re-running the suite for those stages surfaces an unexpected failure,
  that becomes its own stop-and-report finding, not a sign to re-audit
  everything from scratch.
- Not the four manual, live-IdP steps in `add-sso-oidc-login/tasks.md` §11
  (real browser, real Entra ID tenant) — out of reach in this environment
  and already flagged there as a separate follow-up.
- Not archiving `add-sso-oidc-login` (syncing its delta specs into
  `openspec/specs/`) — a separate, later action once this audit confirms
  the code is solid.
- Not a full SSRF-hardening policy (per-tenant URL allow-listing, DNS-
  rebinding protection). See the SSRF decision below for what is and isn't
  in scope here.

## Decisions

### Stage 8 — SSO Login (`sso`, API-19) — inserted after Auth/RBAC

| # | Endpoint | Auth/Permission | Isolation | Known gap (found during this design's review) |
|---|---|---|---|---|
| S1 | `GET /auth/sso/config` | `sso-config:view` | tenant-scoped | **No permission-denied test** — only the "not configured" 404 path is tested with an authorized user. |
| S2 | `PUT /auth/sso/config` | `sso-config:manage` | tenant-scoped | Covered (happy path + masked-secret + permission-denied). |
| S3 | `POST /auth/sso/config/test` | `sso-config:manage` | n/a (no persistence) | **No permission-denied test.** **SSRF**: `discoveryUrl` is an unvalidated `str` — the server will issue outbound GET/POST requests to *any* URL an authenticated caller supplies (`oidc_client.fetch_discovery_document`/`test_client_credentials`), including internal/private/link-local/cloud-metadata addresses. `sso-config:manage` is admin-only, but `security-architecture.md`'s general posture (validate all input, don't trust it downstream) and OWASP's SSRF category both call for a basic guard here regardless of caller privilege. |
| S4 | `GET /auth/sso/role-mappings` | `sso-config:view` | tenant-scoped | Covered (permission-denied tested). |
| S5 | `POST /auth/sso/role-mappings` | `sso-config:manage` | tenant-scoped | Covered for not-found-role and duplicate-group-claim; **no permission-denied test** (only the `:view`-gated list endpoint's denial is tested, which doesn't prove `:manage` is actually enforced on create). |
| S6 | `DELETE /auth/sso/role-mappings/{id}` | `sso-config:manage` | tenant-scoped | Covered for the happy path; **no not-found (404) test** and no permission-denied test. |
| S7 | `GET /auth/sso/{tenant_slug}/login` | public | n/a (resolves tenant from a public slug) | Covered: no-provider-configured 409, unknown-tenant 404, and the full happy-path redirect. **Not rate-limited at all** — `security-architecture.md` §2: "rate limiting... on every unauthenticated endpoint," and this is now an alternate login entry point exactly like `POST /auth/login`. |
| S8 | `GET /auth/sso/callback` | public | n/a | Covered: unrecognized/replayed state, wrong-signature and expired ID tokens, missing-email-claim, failure-audit-write. **Not rate-limited.** |
| S9 | `POST /auth/sso/exchange` | public | n/a | Covered: reuse-rejected, expiry-rejected, wrong-token-type-rejected. **Not rate-limited** — and this is the endpoint that actually hands out real access/refresh tokens, making it at least as sensitive as `POST /auth/login`. |
| S10 | `POST /auth/logout` | any authenticated user | tenant-scoped | **Zero test coverage** — not referenced anywhere in any `tests.py`. Needs: happy path (audit entry written, 200 returned), and the standard 401-when-unauthenticated case every other authenticated endpoint gets. |
| S11 | Cross-tenant SSO isolation (repository-level, already in `sso/tests.py`) | — | tenant-scoped | The existing test is named `test_sso_config_and_role_mappings_are_tenant_isolated` but its body only asserts `SsoProvider` isolation — `SsoRoleMapping` isolation is asserted by name but never actually checked. |

### SSRF guard: fix inline, scoped to `oidc_client.py`

Meets the stop-and-report threshold's "fix inline" bar: confined to
`oidc_client.py`'s two entry points that take a caller-supplied URL
(`fetch_discovery_document`, called by both `test_provider_config` and
`save_provider_config`'s eventual login flow), and makes behavior match
what a security-conscious reading of `security-architecture.md` already
implies without contradicting any documented contract. The guard:

- Reject any `discovery_url` whose scheme isn't `https` (already the only
  scheme every real OIDC provider uses — rejecting `http` is not a feature
  regression).
- Resolve the host and reject if it lands in a private, loopback,
  link-local, or multicast range (`ipaddress.ip_address(...).is_private`/
  `is_loopback`/`is_link_local`/`is_multicast` after a DNS lookup) — this
  is the standard "block the cloud-metadata/internal-network" SSRF
  mitigation, cheap to add and to test (mock the resolved IP rather than
  depending on real DNS in CI).

**Alternative considered**: a per-tenant admin-configured allow-list of
acceptable discovery-URL domains. Rejected as out of scope for this
audit — it's a product/config decision (which domains are "acceptable" is
not obvious — every real customer's IdP is a different domain), not a
one-function bug fix, so it's flagged as a stop-and-report follow-up
instead of built here.

### Rate limiting: fix inline, matching `POST /auth/login`'s existing pattern

Add `@limiter.limit(...)` to `GET /auth/sso/{tenant_slug}/login`,
`GET /auth/sso/callback`, and `POST /auth/sso/exchange` — the same
`slowapi` limiter `auth/router.py` already uses, at the same `3/minute`
per-IP threshold as the password-login path they're an alternative to
(consistent, not stricter or looser without a stated reason). This is a
`rate-limiting` capability-adjacent fix, but adding a rate limit that
matches an already-documented policy ("every unauthenticated endpoint is
rate-limited") to an endpoint that should already have had one is a bug
fix, not a new requirement — no `Modified Capabilities` entry needed,
matching this change's `skip_specs: true`.

### Re-confirming stages 1-7 without re-deriving the matrix

Run the full suite; for each of the 7 original stages, spot-check that the
specific rows the 2026-08-21 audit flagged as fixed (employee-sync
duplicate-in-batch 409, invitation orphaned-upload ordering, branch
`/provision` transaction rollback, Redis-namespace isolation for
`identity_verification`) still pass, since those are the ones most likely
to regress silently. If the full suite is green and those specific
regression tests still exist and pass, stages 1-7 are confirmed without
re-writing their matrix.

## Risks / Trade-offs

- **SSRF guard could reject a legitimate discovery URL** if a real IdP
  resolves to an IP this guard's range-check misclassifies (unlikely for a
  major public IdP like Entra ID/Google/Okta, all of which serve from
  public, non-private ranges) → mitigation: the guard only blocks
  private/loopback/link-local/multicast ranges, not all non-Azure hosts,
  so any genuinely public IdP is unaffected.
- **Rate-limiting the callback endpoint** could, in theory, reject a
  legitimate IdP redirect if a staff member double-clicks "sign in" or an
  IdP retries the redirect → mitigation: `3/minute` is generous for a
  human-driven, one-shot redirect; `auth/tests.py`'s existing pattern
  (`monkeypatch.setattr(limiter, "enabled", True)` only inside the specific
  rate-limit test, disabled by default under `ENVIRONMENT=test`) means this
  doesn't affect any other test's behavior.
- **Stages 1-7 "spot-check" approach** could miss a genuine regression the
  2026-08-21 audit's specific named tests don't happen to cover →
  mitigation: the full-suite run itself is the actual safety net (345
  tests, not just the 4 named ones); the spot-check is an extra, targeted
  look at the highest-risk-of-regression items, not the only check.

## Open Questions

- Should `sso-config:manage`'s SSRF exposure eventually get a full
  per-tenant domain allow-list, or is the private-IP-range guard sufficient
  long-term? Deferred per the SSRF decision above — revisit only if a
  customer's threat model requires it.
