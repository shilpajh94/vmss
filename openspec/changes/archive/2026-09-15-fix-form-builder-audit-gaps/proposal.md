## Why

The `/admin/form-builder` "Registration Steps" screen fails with a generic
"Something went wrong loading the registration steps" error. Root-cause
investigation traced this to the dev tenant schema never having been
upgraded to the `afb2544db111` migration that creates the form-builder
tables (`form_steps`/`form_fields`/`form_config_versions`) — the feature's
code and migration shipped, but nothing re-applied `alembic_tenant`
migrations to the *existing* tenant schema, so the API 500s on a missing
table. A follow-up audit of the rest of the currently uncommitted diff
(invitations, registrations) surfaced two related gaps worth fixing in the
same pass since they were found by the same review: an unbounded/unvalidated
`consents` payload on invitation creation, and a missing upload-size check on
the registrations ID-proof endpoint that the sibling invitations endpoint
already enforces.

## What Changes

- Apply the pending `alembic_tenant` migrations (through `afb2544db111`/
  `762e2a7cf5d1`) to every existing tenant schema, unblocking the
  form-builder admin screen.
- Add a repeatable "upgrade all tenants" ops command
  (`database-architecture.md` §5 flags this as a known-missing piece) that
  applies any pending `alembic_tenant` revisions to every tenant schema
  currently below head, plus a startup/prestart check that logs a `WARNING`
  when a tenant schema is behind head, so a new tenant-scoped migration
  landing without being applied everywhere is caught before it reaches a
  user-visible 500 again.
- The same upgrade operation also re-runs `auth/rbac_catalog.py`'s
  (already idempotent) `seed_default_roles` and `form_builder/service.py`'s
  `seed_default_form_config` for the tenant — discovered mid-implementation
  that fixing only the missing table still left an existing tenant's admin
  role 403'd on `GET /form-builder/steps`, since nothing had granted it the
  `form-builder:view`/`form-builder:manage` permissions added alongside this
  feature. Without this, the form-builder screen still fails for every
  already-provisioned tenant even after the table exists.
- Bound and allow-list `InvitationCreate.consents` the same way
  `carried_items.items` already is: cap the number of keys, cap key length,
  and reject any key not in the branch's configured consent set, instead of
  persisting an arbitrary client-supplied dict into the audit-relevant
  `invitations.consents` JSONB column.
- Enforce the existing "uploaded file size is bounded" requirement
  (`file-storage` capability) on the registrations primary-contact ID-proof
  upload endpoint, which currently reads the upload without a byte-limit
  argument — the sibling invitations upload path enforces this already.

## Capabilities

### New Capabilities
- `tenant-schema-maintenance`: keeping every tenant's Postgres schema
  up to date with the `alembic_tenant` migration head — an explicit "upgrade
  all tenants" operation and a drift check that surfaces a tenant schema
  lagging behind head before it causes a runtime failure.

### Modified Capabilities
- `invitations`: `consents` on invitation creation becomes a bounded,
  allow-listed payload (mirroring the existing `carried_items` validation)
  instead of an unconstrained `dict[str, bool]`.

## Impact

- `src/vmss_api/platform/service.py` — the existing per-tenant migration
  runner (`run_tenant_migrations`/`create_tenant`) gains a callable "upgrade
  all tenants" path; a new `scripts/` entry point or admin task invokes it.
- `src/vmss_api/backend_pre_start.py` (or equivalent prestart hook) — add the
  drift check/warning.
- `src/vmss_api/invitations/schemas.py`, `src/vmss_api/invitations/service.py`
  — validation for `consents`.
- `src/vmss_api/registrations/router.py` — byte-limit on the ID-proof file
  read, matching `src/vmss_api/invitations/router.py`.
- Dev/staging tenant schemas — a one-time migration apply to unblock the
  form-builder screen locally.
