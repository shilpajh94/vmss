## Context

See proposal.md - Why for motivation. Two facts, confirmed by reading the
actual fixtures/code (not assumed), shape this design:

1. **The shared `client` fixture (`conftest.py`) hardcodes tenant-schema
   routing.** `get_tenant_db` is overridden to always yield the *same*
   `db_session`, bound to the one default tenant schema (`tenant_acme_test`)
   every other test in the repo shares — regardless of which tenant a
   request's JWT claims. This means every existing test, even ones that log
   in as different "tenants," is actually only ever exercising one physical
   schema. No existing test proves the real per-request dynamic schema
   resolution (`core/tenancy.py`'s `get_tenant` → `get_tenant_db` chain,
   `database-architecture.md` §2) actually works for more than one tenant.
2. **There is no API to bootstrap a brand-new tenant's first user.**
   `platform/service.py::create_tenant` provisions the schema, runs
   migrations, and seeds the standard *roles* catalog
   (`seed_default_roles`) — it does not create any `User` row. Every
   `POST /auth/users` call requires `users:manage`, which requires already
   being authenticated as *someone* in that tenant. There is no
   self-registration endpoint. This is a real, load-bearing gap in the
   product's onboarding story, not something to route around silently.

## Goals / Non-Goals

**Goals:**
- Prove the staff/admin chain end-to-end against a **genuinely freshly
  provisioned tenant** (not the shared default schema), so the dynamic
  per-tenant schema-routing machinery gets exercised by at least one test,
  the way it actually behaves in production.
- Prove the visitor chain end-to-end (invitation-created and walk-in
  variants) using real HTTP responses carried forward, not fixture
  shortcuts, for every step an API already supports.
- Surface, rather than paper over, the exact point where "no shortcut
  fixtures" becomes impossible (the missing first-user-bootstrap API) —
  document it as a finding, not a silent workaround.

**Non-Goals:**
- Not a fix for the missing first-admin-bootstrap gap — that's a product
  decision (build a provisioning-time admin-seed endpoint? a CLI-only
  onboarding step? something else?), out of scope here.
- Not a replacement for the per-endpoint scenario tests
  `complete-api-test-coverage` already built — this adds a different kind
  of test (compositional/chained), it doesn't duplicate or replace the
  isolated ones.
- Not a performance/load test. Real tenant provisioning (real `CREATE
  SCHEMA` + real Alembic migration run) is deliberately exercised once, in
  one test, accepting the wall-clock cost — not stress-tested.

## Decisions

### File locations

Two new root-level test files, following the existing convention that
cross-feature integration tests live in root `tests/`
(`fastapi-architecture.md`/`project-rules.md` — `tests/test_api_documentation.py`
is the existing precedent):
- `tests/test_workflow_staff_admin.py`
- `tests/test_workflow_visitor.py`

Neither belongs inside any single feature's `tests.py` — each chain spans
5+ feature packages.

### Staff/admin chain: a bespoke `get_tenant_db` override, not the shared `client` fixture

To make "login" and everything after it actually operate against the
tenant just provisioned (not the shared default schema), this test builds
its own `AsyncClient` with dependency overrides rather than depending on
the shared `client` fixture:
- `get_db` → the existing `db_session` (global-schema tables: the tenant
  registry, `TenantUserIndex`, role/permission catalog reads — same as
  every other test).
- `get_tenant_db` → a generator wrapping `core.database.tenant_session_scope(schema_name)`,
  where `schema_name` is computed by the test itself as
  `f"{settings.tenant_schema_prefix}{slug}"` — deterministic from the
  `slug` the test already chose for `POST /platform/tenants`, the same way
  `platform/service.py::create_tenant` computes it. (`TenantSummaryOut`
  deliberately doesn't expose `schema_name` over the wire — that's
  correct API design, not a gap; the test doesn't need the API to expose
  an internal implementation detail it already knows from its own request.)

Sequence:
1. `POST /platform/auth/login` as the fixture `superadmin` → platform token.
2. `POST /platform/tenants` with a UUID-suffixed slug (e.g.
   `e2e-staff-<hex8>`, avoiding collision across runs; see Risks on
   accumulation) → real schema created, real migrations run, roles seeded.
3. **The one unavoidable non-API step**: open a session on the new schema
   directly (`tenant_session_scope`, not the API) and insert exactly one
   `User` row + one company-wide `UserBranchRole` granting the already-
   seeded `"admin"` standard role (looked up by name, not re-created — this
   proves `seed_default_roles`' output is actually usable, not just that a
   role named "admin" exists somewhere). This mirrors what a real
   onboarding runbook or seed script does today, per Context point 2 — the
   test's docstring says so explicitly, so it reads as a documented
   exception, not an oversight.
4. Swap the `get_tenant_db` override to point at the new schema (step
   above's `schema_name`).
5. `POST /auth/login` with that seeded admin's credentials → real access
   token. Every step below carries this token forward.
6. `POST /auth/users` (create a second staff user) → `POST
   /auth/users/{id}/branch-roles` (needs a branch, so this happens after
   step 7's branch exists — reorder: create the org structure first, then
   the second user's branch-role grant, so every id used is a real id from
   a real prior response, never guessed).
7. Org structure chain: `POST /company` → `POST /branches` → `POST
   /buildings` → `POST /floors` → `POST /departments` → `POST
   /reception-desks` → `POST /security-gates`, each using the previous
   step's real returned id where the next request needs a parent id.
8. `POST /visitor-categories`, `POST /approval-workflow-rules`.
9. Listing: `GET /auth/employees`, `GET /branches`, `GET
   /visitor-categories` — assert the entities created above are actually
   present (not just that the list call 200s).
10. CRUD close-out: `PUT`/`DELETE` on at least one entity created earlier
    (e.g. update the department's name, delete the security gate), then a
    follow-up `GET` proving the change/removal is visible.
11. `GET /reports/branches/rollup` — assert the counts reflect the final
    state (one branch, one building, one floor, one department minus any
    deleted, etc.) — this is the "dashboard" step, and it's the one place
    this test proves something no per-feature test can: that everything
    built through steps 6-10, in a schema that didn't exist when the test
    started, rolls up correctly.

### Visitor chain: the existing default schema is sufficient, no override needed

Unlike the staff/admin chain, there's no value in provisioning a second
fresh tenant here — the point of this chain is proving invitation-creation
→ identity-verification → tracking compose correctly, not re-proving
schema routing (already covered above). Uses the shared `client` fixture
and the existing `tenant`/`branch`/`user` conftest fixtures as its (already
established, unavoidable-in-every-test) starting point:
1. `POST /invitations` (authenticated staff member, from the `user`
   fixture) → real `trackingId` from the response.
2. `POST /identity-verification/otp/request` → `POST
   /identity-verification/otp/verify` (the visitor's own identity check,
   unauthenticated) → proof token from the response.
3. `GET /invitations/track?trackingId=...` using the tracking id from step
   1's real response (not a value the test already knew ahead of time) →
   assert the response reflects the invitation just created.

A second variant swaps step 1 for `POST /registrations/walk-in`
(device-key-authenticated) feeding the same tracking id into step 3, since
`proposal.md` calls out both intake paths.

Notification/OTP side effects: reuse the same mocking *pattern* the
existing per-feature tests already use (`invitations/tests.py` monkeypatches
`tasks.send_visit_confirmation.delay`; `identity_verification/tests.py` uses
the real Redis instance, only the sender adapters are stubbed) — defined
locally in the new file, since feature-local autouse fixtures aren't shared
across files via conftest.py.

### Slug uniqueness and schema cleanup

The staff/admin test's slug includes a random suffix
(`uuid.uuid4().hex[:8]`) so re-running the suite doesn't 409 on a
leftover schema from a prior run.

**Corrected during implementation** — the original version of this section
said the schema should be left behind afterward, by analogy to
`make_tenant_schema` (used by every tenant-isolation test), which never
drops what it creates. That analogy doesn't hold and the implementation
found this out directly: `make_tenant_schema` only creates empty tables,
while this test provisions through the real `POST /platform/tenants` path,
which also runs `seed_default_roles` and leaves `role_permissions` rows
FK-referencing the shared `global.permissions` table. Left behind, those
rows broke a later test's `db_session` teardown with a
`ForeignKeyViolationError`, which cascaded into an unrelated fixture
insert failing on a duplicate email — reproduced directly while building
this test. The corrected decision: drop the schema in a `finally` block,
matching the existing precedent already in
`platform/tests.py::test_create_tenant_provisions_real_schema`/
`test_create_tenant_success_via_endpoint`, which guard against exactly
this for the same reason. `vmss_test` schema accumulation from
`make_tenant_schema`-style empty-table provisioning remains a separate,
pre-existing, accepted characteristic this change doesn't touch — the
correction above is specific to provisioning through the real API path.

## Risks / Trade-offs

- **[Real Alembic migration run inside a test]** → adds real wall-clock
  cost (schema creation + full migration run), same cost
  `platform/tests.py::test_create_tenant_provisions_real_schema` already
  accepts once. Mitigation: exactly one test pays this cost for the whole
  staff/admin chain; nothing else in this change provisions a second
  tenant.
- **[The one non-API seed step could be misread as "cheating"]** →
  mitigation: it's the one honestly-unavoidable step given Context point
  2, documented in the test's own docstring and called out again here and
  in the closing summary, not hidden.
- **[`vmss_test` schema accumulation over many local runs, from
  `make_tenant_schema`-style fixtures elsewhere in the suite]** →
  mitigation: pre-existing, not something this change's own test
  contributes to — see the corrected "Slug uniqueness and schema cleanup"
  decision above, where this test's own provisioned schema is dropped in
  a `finally` block.
- **[A chained test failing gives a less localized signal than an isolated
  one — "step 7 failed" doesn't say which of 7 endpoints broke]** →
  mitigation: each step asserts its own response shape/status before
  moving to the next, so a failure's traceback points at the specific
  chained call that broke, not just "the test failed."

## Open Questions

- Should the product actually gain a first-admin-bootstrap mechanism
  (an endpoint, a required provisioning-time parameter, or something else)?
  This change surfaces the gap; deciding how to close it is a separate,
  future change's call, not resolved here.
