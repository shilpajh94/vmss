## Context

Three independent gaps were found in one review pass and are bundled here
because they share a root cause category (a new capability's server-side
enforcement lagging what the client/schema already implies) and a common
reviewer. See `proposal.md` for the "why" of each. Relevant existing code:

- `src/vmss_api/platform/service.py::_run_tenant_migrations_sync` /
  `create_tenant` — the only place `alembic_tenant` migrations are currently
  applied, and only at tenant-provisioning time.
- `src/vmss_api/backend_pre_start.py` — the existing prestart hook pattern
  (waits for Postgres, uses `structlog` via `core/logging.py`), the natural
  home for a drift check.
- `src/vmss_api/invitations/service.py:364-408` — the existing
  `allowed_carried_item_keys` / `invalid_items` allow-list pattern to mirror
  for `consents`.
- `src/vmss_api/invitations/router.py:765-780` vs.
  `src/vmss_api/registrations/router.py:150-153` — the existing
  `.read(<limit>)` pattern to port over.
- `src/vmss_api/auth/rbac_catalog.py::seed_default_roles` — already
  idempotent and already documents (in its own docstring) re-running it to
  backfill a permission added to `PERMISSION_CODES`/`ROLE_PERMISSIONS`
  after a tenant's roles were first seeded. Verified directly against dev:
  the global `permissions` table had **zero** `form-builder:%` rows and
  `tenant_default`'s `admin` role had zero grants for them — a caller with
  every table fix in this change still gets a `403 Insufficient permission`
  on `GET /form-builder/steps`, which the frontend surfaces as the same
  generic "Something went wrong" error. `form_builder/service.py::seed_default_form_config`
  is the same shape (idempotent, already called by `create_tenant`).

## Goals / Non-Goals

**Goals:**
- Make the dev tenant (and any other existing tenant) schema match the
  `alembic_tenant` migration head, and make that reproducible on demand
  rather than a one-off manual fix.
- Catch a future instance of "migration shipped, existing tenant never
  upgraded" at startup instead of as a 500 in the browser.
- Bring `consents` validation to parity with the existing `carried_items`
  validation, using the same mechanism already in the codebase.
- Bring the registrations upload path to parity with the existing
  invitations upload path's size enforcement.

**Non-Goals:**
- No change to the two-Alembic-tree structure or to how a *new* tenant is
  provisioned (`create_tenant` already runs migrations correctly for a
  brand-new schema).
- No general-purpose "drift dashboard" — the startup check is a log line,
  not a new admin UI.
- No change to which consent keys or upload size limits are configured per
  branch — only that the existing configured sets are actually enforced.

## Decisions

**Upgrade-all-tenants as a reusable function, called from both a one-off
script and (optionally) an ops task.** Extract the per-schema upgrade logic
already in `_run_tenant_migrations_sync` into a function that takes a schema
name and is callable in a loop over every row in the global `tenants` table
(reading each tenant's `schema_name`, per `database-architecture.md` §2).
Add a thin `scripts/` entry point that iterates all tenants and calls it —
consistent with `scripts/provision_tenant.py` and
`scripts/seed_demo_workflow.py`'s existing pattern of a standalone script
invoked via `ddev exec uv run python -m scripts.<name>`. Alternative
considered: a Celery task — rejected because this is an operator-triggered,
infrequent action (run after authoring a tenant migration), not
request-triggered background work per `background-jobs.md`'s scope.

**Drift check reads `tenant_schema_versions` (global), not the per-tenant
`alembic_version` table.** `database-architecture.md` §5 already documents
`tenant_schema_versions` as the fast-lookup mirror of per-tenant
`alembic_version`, updated by the same migration-apply call. The startup
check compares each tenant's cached version against the `alembic_tenant`
head (resolved via Alembic's `ScriptDirectory.get_current_head()`) and logs
`WARNING` per lagging tenant — one global-schema query, no per-tenant
connection needed at startup, matching the existing rationale for that
table's existence.

**`consents` validation reuses `form_builder_validation` /
`allowed_carried_item_keys`-style resolution, not a hardcoded key list.**
The branch's configured consent keys already come from the effective form
(`resolve_effective_form`, already called in `invitations/service.py:358-360`
for carried items). Add an analogous
`form_builder_validation.allowed_consent_keys(effective_form)` and apply the
same `set(payload.consents) - allowed_consent_keys` rejection used for
carried items (`service.py:404-408`), plus a count check
(`len(payload.consents) > len(allowed_consent_keys)`) — both raise the same
validation-error shape already used for `invalid_items`, so no new error
envelope is introduced.

**`upgrade_tenant_schema` also re-runs `seed_default_roles` and
`seed_default_form_config` for the tenant it just migrated, not just the
Alembic upgrade.** Discovered mid-implementation: fixing only the missing
`form_steps` table left the dev admin user 403'd on the same screen, because
nothing ever re-syncs an *existing* tenant's RBAC grants or form defaults
against the catalog the way `create_tenant` does for a brand-new one. Since
both seed functions are already idempotent and already used together in
`create_tenant`'s provisioning sequence (schema → migrate → seed roles →
seed form config), `upgrade_tenant_schema` runs the same three steps
(migrate → seed roles → seed form config) instead of just the migration —
making "bring an existing tenant up to date" a true mirror of "provision a
new one," rather than a second, narrower code path that only handles schema
drift and leaves catalog drift for someone to discover independently later.
This is why the capability is named `tenant-schema-maintenance` broadly
rather than "tenant migration maintenance" — schema and catalog staying in
sync are the same operational concern from an operator's point of view (run
one command, this tenant is current).

**Registrations upload limit reuses the existing configured limit constant,
not a new setting.** `invitations/router.py` already reads `id_proof_limit`/
`photo_limit` from settings (per `file-upload-handling.md` §1's "tune per
artifact type"). `registrations/router.py`'s ID-proof field is the same
artifact type, so it reads the same `id_proof_limit` constant rather than
introducing a second, possibly-diverging limit.

## Risks / Trade-offs

- [Upgrading a tenant schema mid-flight while requests are in-flight against
  it could race a long-running transaction] → Mitigation: this ops action is
  run manually by an operator during a low-traffic window, same as today's
  manual `alembic upgrade head` workflow for the global schema; no change to
  how migrations themselves are written (still additive/backward-compatible
  per normal Alembic practice).
- [Tightening `consents` validation to an allow-list is a **behavior change**
  for any existing client already sending extra/unrecognized consent keys] →
  Mitigation: today those extra keys are silently persisted into an
  audit-relevant column with no product value; rejecting them is the
  intended tightening the proposal calls for, and matches how
  `carried_items` already behaves.
- [A startup `WARNING` for drift is easy to miss in log volume] → Mitigation:
  matches the existing `database_not_ready`-style structured log the
  prestart hook already emits (`backend_pre_start.py`), so it's picked up by
  whatever already scrapes prestart logs; a louder alerting channel is out of
  scope for this change.

## Migration Plan

1. Land the `_run_tenant_migrations_sync` extraction and the "upgrade all
   tenants" script/function (no behavior change to existing single-tenant
   provisioning).
2. Run the upgrade-all-tenants script against the dev environment to close
   the immediate `form_steps` table gap.
3. Add the startup drift-check log line.
4. Land the `consents` allow-list/size-cap validation and the registrations
   upload byte-limit fix.
5. Re-run `ddev exec uv run pytest src/vmss_api/form_builder/tests.py
   src/vmss_api/invitations/tests.py src/vmss_api/registrations/tests.py` and
   confirm the `/admin/form-builder` screen loads against the dev DB.

Rollback: each of the four fixes is independently revertible (separate
files); the tenant-upgrade script itself is non-destructive (Alembic
upgrade-only, no downgrade run as part of it).
