---
trigger: glob
globs: src/vmss_api/**/tests.py,tests/**/*.py
---

# Testing Standards — VMSS_API

`project-rules.md` mandates real-Postgres tests via `pytest`/`httpx.AsyncClient`;
this covers how test data is built and what a feature's tests must actually cover.

## 1. Test Data via Factories, Not Hand-Built Dicts

- Build test rows through a factory keyed to the SQLAlchemy model (e.g.
  `polyfactory`'s `SQLAlchemyFactory`), not copy-pasted literal dicts repeated
  across every test function. When a model gains a new required column, a factory
  fails loudly at the one definition site instead of a dozen hand-built fixtures
  silently producing rows that happen to still pass because the column was
  nullable-by-accident in a migration.

## 2. What a Feature's Tests Must Cover

Per feature (`<feature>/tests.py` or `tests/` subpackage), at minimum:
- The happy path for every endpoint the router exposes.
- At least one **permission-denied** case (`require_permission` rejects a caller
  lacking the permission) — RBAC is real from day one
  (`security-architecture.md` §1), so it needs a real test, not just an assumption
  the dependency works.
- At least one **tenant-isolation** case — a repository call against a
  session bound to one tenant's schema must not see another tenant's row,
  even once a second tenant schema exists in the test DB (`make_tenant_schema`/
  `open_tenant_session` fixtures in `conftest.py`). This is the test that
  catches a repository method built against the wrong session, or one that
  constructs its own engine instead of using the tenant-bound session it's
  given (`database-architecture.md` §3). See `auth/tests.py::test_tenant_schema_isolation`
  for the reference example.

## 3. Unit-ish vs. Integration

There's no SQLite/mock-DB fast-unit tier here (deliberately — see
`project-rules.md`'s no-SQLite rule). "Unit-style" tests still run against the real
`vmss_test` Postgres database but call the service/repository layer directly to
cover business-rule edge cases (e.g. overstay-detection boundary conditions) that
would be slow or awkward to enumerate by going through the full HTTP endpoint for
every case. Endpoint-level tests via `httpx.AsyncClient` cover the request/response
contract, auth, and status codes.

## 4. Coverage

Track via `pytest --cov`; no hard-coded numeric gate exists yet. A PR that adds an
endpoint or service method without a corresponding test in §2's list should be
treated as incomplete, not as "coverage number didn't drop enough to block."

## 5. Test Scope While Implementing a Change

When implementing a change request or a suggestion task (including `/opsx:apply`),
do **not** run the full `pytest` or e2e suite. Run only the targeted set:

- the tests of every feature package the change edits;
- the tests of any other area that depends on the changed code — it imports it,
  calls it, or consumes its output (a shared `core/` helper, a schema reused
  elsewhere, a Celery task, a tenant migration, a response shape the web client
  reads). Find these by grepping for imports of the changed module/symbol
  (`grep -rn "from vmss_api.<feature>" src tests`) and following its consumers;
- `tests/test_api_documentation.py` when a route or response schema is added,
  removed, or registered.

If nothing else depends on the changed code, the change's own feature tests are
enough. Run the targeted set as one sequential
`ddev exec uv run pytest <paths>` invocation, never parallel processes (they race
on the shared test DB).

If a `tasks.md` step says "run the full suite", run the targeted set instead and
say so in the task's completion note. The full suite still runs in the CI merge
gate (`git-workflow.md` §4) and whenever the user explicitly asks for it.

When reporting verification, list the test modules run and their result, and name
each dependent area included and why — that's what lets a reviewer spot one that
was missed.
