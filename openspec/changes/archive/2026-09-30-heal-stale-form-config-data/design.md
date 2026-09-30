## Context

The dev tenant (`tenant_default`) has these rows:
- `form_fields` row `447184ab-…`: key `terms_conditions`, label "Terms &
  Conditions", type `signature_pad`, not required, active, `options` null,
  help text holding the terms, step `visitor_info`, no group. Created
  2026-09-22.
- `form_config_versions`: the tenant-default version 24 (published
  2026-09-22) contains that field. The branch "QA Form Builder Branch"
  version 3 (published 2026-09-25) doesn't.

Reproduced:
- `GET /form-builder/steps` fails with a 500 from `FormFieldOut`'s enum.
  The traceback is in `router.py::_step_out`.
- `GET /form-builder/effective` returns 200 with the raw snapshot.
- Running the web app's `EffectiveFormStepListResponseSchema` against the
  live response gives 31 issues:
  - 27 fields: `hideLabel` is undefined;
  - 3 groups: `visibilityCondition` is undefined;
  - 1 field: `fieldType` is `signature_pad`.

  So the page shows "Step 0 of 0" and the load error. The same parser
  accepts the branch-scoped version 3, published 25 Sep.

Snapshot shape: a list of steps, each with a flat `fields` list (each
field carries `groupId`) and `groups` holding `fieldKeys`. Fields are
camelCase dicts.

There's a precedent for this kind of data repair in a tenant migration:
`24b02534e970_remove_dead_host_department_system_fields`. It uses raw
SQL against `version_table_schema`, rewrites snapshots in Python, logs via
stdlib `logging`, and has a no-op downgrade.

## Goals / Non-Goals

**Goals:**
- the forms load again in every environment, with the terms kept as a
  consent checkbox;
- an old snapshot, or a future stale type, can never take down a whole
  form again. The API serves snapshots in the current shape.

**Non-Goals:**
- reintroducing a signature capture type;
- changing the supported catalog or the API contract;
- the web-side tolerance, which is `tolerate-unknown-form-field-types` in
  VMMS_WEB.

## Decisions

### 0. Normalise snapshots on read, through the current schema
`resolve_effective_form` returns `version.snapshot` verbatim. Old
snapshots, and any future snapshot written before a schema addition, leak
their old shape. The fix is a single `normalize_snapshot(snapshot) ->
list[dict]` in `form_builder/schemas.py`. It runs each step's fields and
groups through their current Pydantic models, whose defaults fill missing
keys:
- `hide_label` defaults to `False`, as it already does on `FormFieldOut`;
- the effective group model's `visibility_condition` gets a `None`
  default.

It then dumps back with `by_alias=True, mode="json"`. Unsupported field
types are dropped first (Decision 3), so model validation can't fail on
them. Unknown extra keys are ignored.

A field or group that still fails validation for another reason is
dropped and logged at WARNING (`form_snapshot_entry_invalid`), rather than
failing the whole form.

This also runs on the cached value, and before caching. So the cache
never holds, or serves, an old shape.

*Alternative:* backfill in the migration only. That fixes today's data,
but the next schema addition would break old snapshots again.
Rejected as the only measure; the migration is kept as well (Decision 1),
so the stored data is clean.

*Implementation note:* the normaliser works on dicts, in the new
`form_builder/snapshot.py`, rather than round-tripping through Pydantic
models. A model round trip would re-serialise values (UUIDs, extra keys
like `fieldKeys`), which the spec forbids. Instead it has an explicit
defaults table (`SNAPSHOT_FIELD_DEFAULTS` / `SNAPSHOT_GROUP_DEFAULTS`),
plus a derived `fieldIds` rebuilt from `fieldKeys`: older snapshots lack
that key too, and `validation.py` and the walk-in mapping read it. The
table is kept honest by `test_normalized_snapshot_matches_current_shape`,
which fails whenever `_step_to_snapshot` emits a key that the table can't
restore.

### 1. Repair via a tenant migration, not a script
The data is tenant-scoped and must be fixed in every tenant schema,
including ones provisioned later from old dumps. An Alembic tenant
revision runs through the existing `upgrade_all_tenant_schemas`
path. That's the same mechanism as the `24b02534e970` precedent. A
one-off script would be forgotten per environment.

Revision `heal_stale_form_config_data`, `down_revision =
"b7c2e9a4d1f3"`. Before opening a PR, check that
`alembic -c alembic_tenant.ini heads` still shows a single head.

### 2. Mapping
```
_REMAP = {
    "signature_pad":   ("checkbox_single", clear_options=True),
    "rich_text_block": ("static_text",     clear_options=False),
    "dynamic_table":   ("textarea",        clear_options=True),
}
```
`checkbox_single` must not declare options (form-builder "Field Types Are
Constrained To a Supported Set"), so `options` is set to NULL/`None`.
Everything else (`is_required`, `help_text`, `validation_rules`, width,
order, `visibility_condition`) is kept.

`signature_pad` becomes `checkbox_single` because the product decision
is that the terms text stays and the visitor ticks to agree. It stays
optional because the row was optional; making it required is an admin
choice. `rich_text_block` becomes `static_text` because both are
content-only. `dynamic_table` becomes `textarea` as the nearest free-form
capture.

Steps:
1. `UPDATE {schema}.form_fields SET field_type = CASE …, options = CASE …
   WHERE field_type IN (…)`. This includes soft-deleted rows, so an undelete
   can't resurrect a broken row.
2. Then, for each row of `form_config_versions`, walk
   `snapshot[*].fields[*]`, rewrite the matching `fieldType` and `options`,
   and `UPDATE` only when something changed.
3. In the same pass, add `hideLabel: false` to snapshot fields that lack
   it, and `visibilityCondition: null` to snapshot groups that lack it.
4. Log the counts, and each converted field's id, key and old→new type,
   at INFO.

It's idempotent: a second run finds no matching types. The downgrade is a
no-op, because the old types are unsupported and restoring them would
re-break the forms.

### 3. Resilient serving: one helper, three call sites
In `form_builder/schemas.py`, add
`SUPPORTED_FIELD_TYPES = frozenset(FormFieldType)` and a helper:
- `drop_unsupported_fields(fields, *, source)` for ORM rows, and
- `drop_unsupported_snapshot_fields(snapshot)` for dict snapshots,

each logging `form_field_unknown_type_skipped` at WARNING with
`field_id`, `field_key`, `field_type` and `source`.

It's applied at three places:
- `router.py`: `_step_out`, `list_fields`, and the group/step reads that
  build `FormFieldOut` lists. There's no single-field GET. A `PATCH` of an unsupported row returns
  422 unless it sets a supported `fieldType`; retyping is the admin's
  repair path.
- `service.py::resolve_effective_form`: apply `normalize_snapshot`
  (Decision 0, which filters as its first step) before caching and on
  every cache read. It works on a copy, so the stored snapshot isn't
  mutated.
- `validation.py`: no edit needed. Every validator's input is the
  effective form from `resolve_effective_form`, which is already
  normalised. So an unsupported required field is neither required nor
  validated, as proven by
  `test_required_field_of_a_removed_type_is_never_required_on_submission`.

Group `fieldKeys` naming a dropped field are left as they are. Renderers
already resolve group members by key against the field list, and a
missing key simply renders nothing. This is covered by a test.

*Alternative:* make `FormFieldOut.field_type` a plain `str`. That leaks
unsupported types to clients, which is exactly what broke the web app.
Rejected.

### 4. Cache
The effective-form cache (`vmss:{tenant}:form-builder:effective:*`, TTL
300 s) may hold the pre-migration snapshot for up to 5 minutes. The
Decision 0 normaliser runs before caching and on every cache read, so a
stale cached entry is harmless. No Redis access from the migration.

## Risks / Trade-offs

- [An admin intended a real signature capture] → There's no such UI; the
  type never worked. The migration log names the converted field so an
  admin can retype it.
- [The skip hides a data problem] → A WARNING is logged on every skip,
  naming the field. After this migration, the dev tenant should log none.
- [A snapshot field is dropped while a draft row still exists] → Both are
  migrated together; skipping is only the safety net.

## Migration Plan

1. Deploy.
2. Run `uv run alembic -c alembic_tenant.ini upgrade head` per tenant, or
   `scripts/upgrade_all_tenants.py`.
3. Verify with `GET /form-builder/effective`:
   - no unsupported types, and `terms_conditions` is `checkbox_single`;
   - the web app's parser accepts the response.

Rollback: the revert redeploys the old code; the data stays converted,
which the old code handles fine.
