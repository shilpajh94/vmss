## Context

`preferred_contact_method` is a seeded `toggle_switch` field in the `contact_details` step, locked, with `options=["email", "sms"]` (`form_builder/defaults.py`; the `whatsapp` entry is added by `integrate-fast2sms-dlt-sms`). Per tenant it exists in two places, as in `alembic_tenant/versions/24b02534e970_*`: the live draft row in `form_fields`, and, once a scope has published, the frozen `form_config_versions.snapshot` JSONB that `resolve_effective_form` serves instead of the draft. `seed_default_form_config` only seeds an empty tenant, so it never back-fills this change onto existing tenants. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Every existing tenant offers `whatsapp` in both stores after the usual tenant upgrade.
- Safe to re-run and safe on tenants whose options an earlier release customised.

**Non-Goals:**
- Making the field's options admin-editable or removing its lock.
- Changing what the API accepts (`ContactMethod` already allows `whatsapp`).
- Reworking `seed_default_form_config` into a general options re-sync.

## Decisions

1. **Data-only Alembic revision in `alembic_tenant/`**, modelled on `24b02534e970`: schema from `op.get_context().version_table_schema`, raw SQL via `op.get_bind()`, logger reporting rows touched per store. Chosen over an ad hoc script because the tenant upgrade path (`upgrade_tenant_schema`) already runs pending revisions per tenant and records the version. Alternative (extend `seed_default_form_config` to re-sync options each run) rejected: it would silently overwrite deliberate changes and broaden every upgrade.
2. **Draft rows**: `UPDATE form_fields SET options = options || '["whatsapp"]'::jsonb` for the row with `key = 'preferred_contact_method'`, `deleted_at IS NULL`, and `NOT options ? 'whatsapp'`. Appending keeps existing order and any custom entries.
3. **Snapshots**: load each `form_config_versions.snapshot`, find the field with `key == 'preferred_contact_method'` in any step, append `whatsapp` if absent, write back only changed rows (same loop and JSONB bind as `24b02534e970`). Done in Python because the field sits in a nested array.
4. **Match by field `key`, not id**: ids differ per tenant, the key is the stable seeded identifier.
5. **Downgrade is a no-op**, documented in the module docstring: removing the option could strand records already created with `whatsapp`.
6. **Cache**: `resolve_effective_form` caches the effective form in Redis (`vmss:{tenant_id}:form-builder:effective:*`). The migration can't reach Redis, so operators flush those keys or wait out the TTL, same instruction as `24b02534e970`.

## Risks / Trade-offs

- A stale cached form keeps hiding WhatsApp until flushed or expired → documented as a rollout step; low impact.
- A tenant that had renamed the field's options manually (not possible while locked) → appending is still correct; the idempotency check is on `whatsapp` only.
- Deploying before WhatsApp delivery is configured lets visitors choose a channel that fails to send → ordering note: run after `integrate-fast2sms-dlt-sms` is live and its Fast2SMS settings are in place.
- Raw SQL against tenant schemas bypasses the repository layer → accepted for a one-off data migration, as in the precedent.

## Migration Plan

1. Deploy `integrate-fast2sms-dlt-sms` with WhatsApp settings configured.
2. Run the tenant upgrade (`upgrade_all_tenant_schemas` / per-tenant upgrade) to apply this revision.
3. Flush each tenant's `form-builder:effective:*` Redis keys.
4. Verify via the effective-form endpoint that the field lists `whatsapp`.
5. Rollback: none needed (no-op downgrade); the extra option is harmless if WhatsApp is switched off server-side because send failures already surface as generic errors.
