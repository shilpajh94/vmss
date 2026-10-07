## Why

The visitor request form and the staff Register Visitor form don't load:
"Step 0 of 0", then "Something went wrong loading the registration
form". The admin Form Builder's step list also fails, with HTTP 500 on
`GET /form-builder/steps`. Every branch without its own published form
is affected, because they all fall back to the tenant-default form.

The tenant-default published form (version 24, published 22 Sep 2026)
fails in three ways. Running the web app's parser against the live
`GET /form-builder/effective` response shows:
1. **A field of a removed type.** "Terms & Conditions"
   (`terms_conditions`, optional, with the terms text in its help text) is
   a `signature_pad` field. `update-form-field-type-catalog` (24 Sep)
   removed `signature_pad`, `dynamic_table` and `rich_text_block`, stating
   that no stored rows used them, so it shipped with no data migration.
   The draft row makes `GET /form-builder/steps` 500, because
   `FormFieldOut`'s enum rejects it.
2. **27 fields lack `hideLabel`.** That key arrived with
   `add-field-hide-label-option` after this snapshot was published.
3. **3 groups lack `visibilityCondition`.** That key arrived with
   conditional field groups, also after this snapshot was published.

`GET /form-builder/effective` returns the stored snapshot as-is. So an
older snapshot reaches clients in an outdated shape, and the web app's
strict parser rejects the whole form. The branch-scoped version 3,
published 25 Sep, parses fine, which confirms that the snapshot's age is
the problem.

Any tenant whose default form was last published before a schema
addition is exposed, and every future field-schema change would repeat
this.

## What Changes

- **Snapshots are served in the current shape.** Every form the API
  returns from a stored snapshot (the effective form) is normalised on
  read:
  - a missing key gets its schema default: `hideLabel` false, and a
    group's `visibilityCondition` null;
  - a field of an unsupported type is dropped, with a warning logged.

  So a client always receives a snapshot that matches today's
  `FormFieldOut`/group schema, however old it is.
- **The admin reads skip unsupported rows** (the step list and step/field
  reads) instead of failing with a 500, and log a warning.
- **Submission validation ignores an unsupported field**, and never
  requires one.
- **Data repair (tenant migration):**
  - it converts removed types to supported ones in `form_fields` rows and
    every snapshot:
    - `signature_pad` becomes `checkbox_single`, a consent checkbox. The
      label, help text and required flag are kept, and options are
      cleared. This matches the product decision.
    - `rich_text_block` becomes `static_text`.
    - `dynamic_table` becomes `textarea`, with options cleared.
  - it backfills missing `hideLabel` and `visibilityCondition` keys in
    stored snapshots.

  It's idempotent, logs what it converted, and has a no-op downgrade.
- No API contract change: responses only ever contain supported types and
  the documented keys.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `form-builder`: adds requirements that a published form is always
  served in the current shape, that an unsupported stored field never
  breaks retrieval or submission, and that removed field types are
  migrated to supported ones.

## Impact

- New `alembic_tenant/versions/<rev>_heal_stale_form_config_data.py`,
  revising the current head `b7c2e9a4d1f3`.
- `form_builder/schemas.py`: a snapshot normaliser and the supported-type
  helper. `form_builder/service.py::resolve_effective_form`,
  `form_builder/router.py` serializers and `form_builder/validation.py`
  use it.
- Tests in `form_builder/tests.py`, plus a migration test.
- Docs: `docs/features/form_builder.md`.
- The web counterpart is `tolerate-unknown-form-field-types` in VMMS_WEB,
  which defaults the same keys and drops unknown field types on the
  client.
