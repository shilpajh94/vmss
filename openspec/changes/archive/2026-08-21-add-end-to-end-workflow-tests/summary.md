## Closing Summary — `add-end-to-end-workflow-tests`

## What was built

Two new root-level test files, both fully passing on the real, chained
sequence they claim to test (no step's input was hardcoded or guessed —
each came from the real prior HTTP response):

- **`tests/test_workflow_staff_admin.py`** — one test,
  `test_staff_admin_full_workflow`: platform login → real tenant
  provisioning (`POST /platform/tenants`, real schema + real Alembic
  migration run) → the one documented non-API seed step → tenant-admin
  login → company → branch → building → floor → department → reception
  desk → security gate → second staff user + branch-role grant → employee
  directory sync → visitor category → approval-workflow rule → listings →
  a PUT (department rename) and DELETE (security gate) with follow-up GETs
  → the cross-branch reports rollup reflecting the final state.
- **`tests/test_workflow_visitor.py`** — two tests: the invitation-created
  path (staff creates invitation → visitor OTP request/verify → public
  tracking lookup) and the walk-in variant (device-key registration →
  public tracking lookup).

## Test counts

| Point | Passed |
|---|---|
| Before this change (`complete-api-test-coverage`'s final state) | 296 |
| After `test_workflow_visitor.py` | 298 |
| After `test_workflow_staff_admin.py` | 299 |
| Final full-suite confirmation | **299**, 0 failures |

`ruff check`/`ruff format --check` clean on both new files.

## Answering the question that prompted this change

Every one of the previously-audited per-endpoint tests builds its fixtures
directly (factories, direct DB inserts) rather than by chaining real API
calls — so no, the prior work did not prove the APIs compose into a working
end-to-end journey the way a real caller would exercise them. This change
adds exactly that: two tests where each step's input is the previous step's
real, parsed response.

## What this surfaced that isolated tests could not

1. **No per-tenant schema routing had ever actually been exercised.** The
   shared `client` fixture hardcodes `get_tenant_db` to one schema
   regardless of the caller's tenant — every existing test, including ones
   simulating "different tenants," was really only ever hitting the same
   physical schema. `test_staff_admin_full_workflow` is the first test in
   the repo to provision a genuinely new tenant and prove the dynamic
   `core/tenancy.py` schema-resolution chain works against it for real.
2. **There is no first-admin-bootstrap API.** `platform/service.py::create_tenant`
   seeds roles, not users — confirmed, not assumed, by reading the service
   function. A brand-new tenant has no way to get its first user through
   the API alone. This is flagged as a real product gap (design.md's Open
   Questions), not fixed here — deciding how a tenant should get its first
   admin (a dedicated endpoint, a required provisioning parameter, a
   CLI-only step) is a product decision for a separate change.
3. **`GET /auth/employees` requires a department + employee code, by
   design** — a plain `POST /auth/users` account never appears there on its
   own. Confirmed against the endpoint's own docstring
   (`auth/router.py:238-243`) and its repository query
   (`auth/repository.py:96-111`) — not a bug. The staff/admin test also
   calls `POST /auth/employees/sync` so its listing assertion is meaningful
   rather than vacuous.
4. **A design correction, made during implementation, not after the fact**:
   this change's own design.md originally said not to drop the provisioned
   test schema. That was wrong — provisioning through the real API path
   seeds `role_permissions` rows that FK into the shared `global.permissions`
   table, and leaving them behind broke later tests' fixture teardown with
   a foreign-key violation (reproduced directly while building the test).
   Fixed by dropping the schema in a `finally` block, matching the existing
   precedent in `platform/tests.py`. design.md has been corrected to match
   what was actually built, with the reasoning for the correction recorded
   in place.

## No production bugs found

Both chains composed correctly against the documented API contracts on the
first correctly-shaped attempt. No `router.py`/`service.py`/`repository.py`
file was touched by this change.

## Left open (unchanged from design.md's Open Questions)

- Whether/how the product should gain a first-admin-bootstrap mechanism —
  a real, now-doubly-confirmed gap, still a future product decision, not
  resolved by this change.
