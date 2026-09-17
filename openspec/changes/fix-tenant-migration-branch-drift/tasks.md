## 1. Merge the diverged migration heads

- [x] 1.1 Run `alembic -c alembic_tenant.ini merge -m "merge poc and form-builder heads" c1d8e5f9a2b3 f1a2c7e9b3d5` to generate the merge revision under `alembic_tenant/versions/`.
- [x] 1.2 Verify `alembic -c alembic_tenant.ini heads` now reports exactly one head, and that the merge revision's `upgrade()`/`downgrade()` bodies are no-ops (pure graph reconciliation, no DDL).
- [x] 1.3 Confirm the merge revision's `down_revision` is the tuple `("c1d8e5f9a2b3", "f1a2c7e9b3d5")` so environments missing either branch pick up both.

## 2. Harden multi-head detection

- [x] 2.1 Add a shared helper (e.g. in `platform/service.py`) that calls `ScriptDirectory.get_heads()` for the `alembic_tenant` config and returns/raises a distinct, typed condition when `len(heads) > 1`, instead of letting callers hit a raw `CommandError`.
- [x] 2.2 Update `get_tenant_migration_head` and `upgrade_all_tenant_schemas` to use that helper, per the "Every Existing Tenant Can Be Upgraded to the Current Migration Head" spec's new multi-head scenario.
- [x] 2.3 Update `backend_pre_start.py::check_tenant_schema_drift` to catch the multi-head condition and log at `ERROR` (identifying the ambiguous heads), keeping the existing per-tenant-lag `WARNING` path unchanged, per the "A Tenant Schema Lagging Behind Head..." spec's new scenario.
- [x] 2.4 Add/extend a test (alongside the existing `platform/tests.py::...get_tenant_migration_head` coverage) that asserts the multi-head condition is surfaced distinctly rather than raising an unhandled `CommandError`.

## 3. Add a CI guard against future unmerged branches

- [x] 3.1 Add a step to the relevant CI pipeline config (`CI-CD/Azure-Pipeline-API-DEV.yml` or equivalent) that runs `alembic -c alembic_tenant.ini heads` (or the new helper from 2.1) and fails the build when more than one head is reported.
- [x] 3.2 Confirm the existing `QualityTest`/`Scanning` CI job actually runs `pytest`, so the multi-head regression test from 2.4 (and the rest of the suite) executes in CI rather than only locally. Added Postgres 17 + Redis 8 service containers, `scripts/lint.sh` (ruff check/format/mypy), and `scripts/test.sh` (pytest) to both `Azure-Pipeline-API-DEV.yml` and `Azure-Pipeline-API-STAGE.yml`'s previously-empty `Scanning` job. Fixed the pre-existing issues this newly-enabled gate surfaced (two `ruff` findings unrelated to this change, two pre-existing `mypy` errors, a missing `pytest-cov` dev dependency `scripts/test.sh` already assumed, and excluded `openspec/`'s illustrative code fences from `ruff format`/`check` scope) so the gate is actually green, not red on day one for unrelated reasons. Unverified against a real Azure Pipelines run — flag for confirmation on the next CI trigger.

## 4. Apply the fix to existing tenant schemas

- [x] 4.0 Applied to this session's local `ddev` dev environment (the one actually reproducing the bug): ran `scripts/upgrade_all_tenants.py` against it, confirmed `tenant_default` is now on `f74620cd4ffa`, `invitations.poc_user_id`/`poc_role_id`/`poc_name` exist, and the startup drift check reports `tenant_schema_drift_check_clean`.
- [ ] 4.1 Deploy the merge migration and hardened code to staging.
- [ ] 4.2 Run `scripts/upgrade_all_tenants.py` (or the equivalent ops entrypoint) against staging; confirm `tenant_schema_versions` reflects the merged head and that submitting an invitation no longer raises `UndefinedColumnError`.
- [ ] 4.3 Repeat against production (`tenant_default`, and any other tenant schema that exists by deploy time), coordinating timing with whoever owns deploys.
- [ ] 4.4 Confirm the startup drift check reports no lagging tenants and no multi-head `ERROR` after the run.

4.1–4.4 require staging/production deploy access this session doesn't have (no deploy pipeline is wired up yet per `project-rules.md`'s Deployment section) — left for whoever owns those environments, using the same `scripts/upgrade_all_tenants.py` run already verified locally in 4.0.
