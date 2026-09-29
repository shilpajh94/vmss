## 1. Tenant Schema Maintenance

- [x] 1.1 Extract the per-schema upgrade logic in
      `src/vmss_api/platform/service.py::_run_tenant_migrations_sync` into a
      standalone callable usable outside `create_tenant`, with no change to
      its existing single-tenant-provisioning behavior.
- [x] 1.2 Add a script entry point (alongside `scripts/provision_tenant.py`)
      that lists every tenant from the global `tenants` table and applies
      the extracted upgrade to each schema currently below the
      `alembic_tenant` head.
- [x] 1.3 Add a drift-check function that compares each tenant's
      `tenant_schema_versions` row against the current `alembic_tenant` head
      and returns the lagging tenants.
- [x] 1.4 Call the drift check from `src/vmss_api/backend_pre_start.py` (or
      an equivalent startup hook) and log a `WARNING` via the centralized
      `structlog` logger for each lagging tenant, per
      `logging-observability.md` §3.
- [x] 1.5 Add tests: upgrading a tenant already at head is a no-op; upgrading
      a tenant below head reaches head; the drift check reports a lagging
      tenant and reports none when all tenants are current.
- [x] 1.6 Run the new upgrade-all-tenants script against the dev environment
      to apply the pending `afb2544db111`/`762e2a7cf5d1` migrations to the
      dev tenant schema.
- [x] 1.7 Discovered mid-implementation: after 1.6, `GET /form-builder/steps`
      still 403s for the dev admin user — the global `permissions` catalog
      and `tenant_default`'s `admin` role were never resynced after
      `form-builder:view`/`form-builder:manage` were added to
      `auth/rbac_catalog.py`. Make `upgrade_tenant_schema` also call
      `auth.rbac_catalog.seed_default_roles` and
      `form_builder.service.seed_default_form_config` for the tenant it just
      migrated (both already idempotent, both already used together in
      `create_tenant`), so "upgrade an existing tenant" fully mirrors
      "provision a new one."
- [x] 1.8 Add a test: a tenant whose standard role is missing a catalog
      permission has it granted after `upgrade_tenant_schema`/
      `upgrade_all_tenant_schemas` runs, without disturbing grants already
      held beyond the catalog.
- [x] 1.9 Re-run `scripts/upgrade_all_tenants.py` against the dev environment
      and confirm `GET /form-builder/steps` returns 200 for the seeded dev
      admin user.

## 2. Invitation Consents Validation

- [x] 2.1 Add `allowed_consent_keys(effective_form)` to
      `src/vmss_api/form_builder/validation.py`, mirroring the existing
      `allowed_carried_item_keys`.
- [x] 2.2 In `src/vmss_api/invitations/service.py`, validate
      `payload.consents` against `allowed_consent_keys`: reject any key not
      in the set and reject a payload with more keys than the configured
      set, using the same validation-error path as the existing
      `invalid_items` check (`service.py:404-408`).
- [x] 2.3 Add tests: an unknown consent key is rejected; an oversized
      consents payload is rejected; a request using exactly the branch's
      configured consent keys (with required ones `true`) is accepted.

## 3. Registrations Upload Size Limit

- [x] 3.1 In `src/vmss_api/registrations/router.py`, pass the same
      `id_proof_limit` byte cap already used in
      `src/vmss_api/invitations/router.py` to the
      `primary_contact_id_proof_file.read(...)` call.
- [x] 3.2 Add a test asserting an oversized ID-proof upload on the
      registrations endpoint is rejected before the full file is buffered,
      matching the existing invitations upload test.

## 4. Verification

- [x] 4.1 Run
      `ddev exec uv run pytest src/vmss_api/form_builder/tests.py src/vmss_api/invitations/tests.py src/vmss_api/registrations/tests.py`
      and confirm all pass.
- [x] 4.2 Manually load `/admin/form-builder` against the dev environment
      and confirm the "Registration Steps" list loads without the
      "Something went wrong" error.
- [x] 4.3 Update `docs/features/form_builder.md` with a short note on how to
      apply pending tenant migrations after this change (pointer to the new
      script), per `project-rules.md`'s "New Features" documentation
      expectation.
