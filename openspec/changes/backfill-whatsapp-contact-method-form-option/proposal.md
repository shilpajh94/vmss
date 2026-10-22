## Why

`integrate-fast2sms-dlt-sms` adds `whatsapp` as a `preferredContactMethod` and adds it to the seeded Preferred Contact Method field's options in `form_builder/defaults.py`. That only reaches tenants seeded *after* the change: `seed_default_form_config` seeds a tenant only if it has no steps yet, and a scope that has ever been published serves its frozen `form_config_versions.snapshot`, not the draft. So every existing tenant's form still offers only `email` and `sms`, and a frontend that renders options from the form config never shows WhatsApp for them. The field is `is_locked`, so an admin can't add the option themselves.

## What Changes

- Add a tenant-schema data migration that appends `"whatsapp"` to the `preferred_contact_method` field's `options` in both stores: the live draft (`form_fields`) and every published snapshot (`form_config_versions.snapshot`).
- The migration is idempotent (skips rows that already list `whatsapp`) and preserves any other options and their order.
- Operational note: `resolve_effective_form`'s cache must be flushed (or expire) after the migration, as with earlier form-builder data migrations.
- No API or schema change. No change for tenants provisioned after `integrate-fast2sms-dlt-sms`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `form-builder`: the system-seeded Preferred Contact Method field offers `whatsapp` for every tenant, including tenants seeded before WhatsApp existed.

## Impact

- Code: one new `alembic_tenant/versions/` revision (data-only). No application code changes.
- Operations: runs once per tenant schema via the existing tenant-upgrade path (`platform/service.py::upgrade_tenant_schema` / `upgrade_all_tenant_schemas`); Redis effective-form cache for each tenant needs a flush.
- Depends on `integrate-fast2sms-dlt-sms`: shipping this before WhatsApp delivery is deployed would show visitors a contact method that can't be delivered.
