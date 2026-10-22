## 1. Migration

- [x] 1.1 Create an `alembic_tenant/versions/` data-only revision on the current tenant head that appends `whatsapp` to `form_fields.options` for `preferred_contact_method` (non-deleted rows, skipping rows that already contain it)
- [x] 1.2 In the same revision rewrite every `form_config_versions.snapshot` so the `preferred_contact_method` field in any step gets `whatsapp` appended if absent; update only changed rows
- [x] 1.3 Log rows/snapshots touched per schema; make `downgrade()` a documented no-op; document the Redis cache flush in the docstring

## 2. Tests

- [x] 2.1 Test the migration against a tenant schema seeded with the old options: draft row and a published snapshot both gain `whatsapp` after upgrade, with existing options and order kept
- [x] 2.2 Test idempotency (second run changes nothing, no duplicate) and that other fields and steps are untouched
- [x] 2.3 Run `ruff check`, `ruff format --check` and the `pytest` suite, including the tenant-isolation test

## 3. Docs and rollout

- [x] 3.1 Note in `docs/features/form_builder.md` that the contact-method field offers `email`, `sms` and `whatsapp`, and add the rollout order and cache-flush step
- [ ] 3.2 After deploy, run the tenant upgrade, flush `form-builder:effective:*` keys, and confirm the effective form lists `whatsapp` for an existing tenant
