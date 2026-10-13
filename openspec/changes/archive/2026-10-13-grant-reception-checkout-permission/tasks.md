## 1. Catalog default

- [x] 1.1 Add `"invitations:checkout"` to `ROLE_PERMISSIONS["reception"]` in `src/vmss_api/auth/rbac_catalog.py` (next to `invitations:deny`/`invitations:reschedule`)
- [x] 1.2 In `src/vmss_api/auth/tests.py`, extend or add a seeded-roles test (modelled on `test_seeded_roles_grant_invitations_view_all_to_branch_wide_roles_only`): a fresh tenant's `admin`, `reception` and `security` hold `invitations:checkout`; `host` and `visitor` don't
- [x] 1.3 Add a resync test (modelled on `test_resync_role_permissions_backfills_invitations_view_all`): a Reception role seeded without `invitations:checkout` gains it after `auth/service.py::resync_role_permissions`, and a second resync reports nothing new (service-level: the endpoint-level resync tests already fail on HEAD, because `get_tenant`'s `db.rollback()` expires the actor under the shared test session)

## 2. Tenant data migration

- [x] 2.1 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and confirm there is a single head (currently `a7c3e9f1b2d4`)
- [x] 2.2 Add `alembic_tenant/versions/<rev>_grant_reception_invitations_checkout.py` chained off that head. Upgrade: `INSERT INTO "<schema>".role_permissions SELECT r.id, p.id … WHERE lower(r.name) = 'reception' AND p.code = 'invitations:checkout' ON CONFLICT DO NOTHING`. Downgrade: delete only that reception grant and leave the global catalog row untouched (follow `d4e6f8a0b2c3`'s structure and docstring style)
- [x] 2.3 Add `tests/test_grant_reception_invitations_checkout_migration.py` (modelled on `tests/test_grant_invitations_view_all_migration.py`): the upgrade grants Reception; `host` and a custom role are unchanged; running twice adds no duplicate and raises no error; the downgrade removes only the Reception grant
- [x] 2.4 Re-run `alembic -c alembic_tenant.ini heads` and confirm there is still exactly one head

## 3. Endpoint behaviour for Reception

- [x] 3.1 In `src/vmss_api/invitations/tests.py`, add a test: a user holding only `reception` at a branch checks out a `checked_in` invitation there → 200, status `checked_out`, `checked_out_by_user_id` is that user
- [x] 3.2 Add a tenant-isolation/branch test: Reception at branch A gets 403 checking out a `checked_in` invitation at branch B, and the invitation stays `checked_in`
- [x] 3.3 Add a permission-denied test: a user holding only `host` gets 403 on check-out, and the invitation stays `checked_in`

## 4. Docs and verification

- [x] 4.1 Update `docs/features/invitations.md` (check-out section: Admin, Reception and Security may check out) and, if role defaults are listed there, `docs/features/auth.md`
- [x] 4.2 `ddev exec uv run ruff check` and `ruff format --check` are clean; `mypy` is clean on `auth/`
- [x] 4.3 `ddev exec uv run pytest src/vmss_api/auth src/vmss_api/invitations tests/test_grant_reception_invitations_checkout_migration.py` is green. If the test DB predates this change, drop `vmss_test` first
