## 1. Serve snapshots in the current shape

- [x] 1.1 In `form_builder/schemas.py`, add `SUPPORTED_FIELD_TYPES` and a helper that drops unsupported fields (WARNING `form_field_unknown_type_skipped`), plus `normalize_snapshot`, which fills schema defaults through the current field and group models (design.md Decisions 0 and 3). Give the effective group model's `visibility_condition` a `None` default. Drop and warn on any entry that fails validation for another reason.
- [x] 1.2 In `service.py::resolve_effective_form`, normalise before caching and on every cache read, without mutating the stored snapshot.
- [x] 1.3 In `router.py`, skip unsupported rows in `_step_out`, `list_fields` and the other list reads; a `PATCH` of an unsupported row returns 422 unless it sets a supported type (design.md Decision 3 note). In `validation.py`, ignore unsupported fields during submission validation.
- [x] 1.4 Tests:
  - the effective form from a snapshot lacking `hideLabel` and `visibilityCondition` returns 200 with the defaults filled and every other value unchanged;
  - a snapshot `signature_pad` field is omitted and warned about;
  - a stale cached snapshot is normalised;
  - `GET /form-builder/steps` with a stored `signature_pad` row returns 200 without it;
  - a submission against a required unsupported field isn't rejected for it;
  - a group whose `fieldKeys` names a dropped field still serves;
  - permission-denied and tenant-isolation cases for the steps read (testing-standards §2).

## 2. Data repair

- [x] 2.1 Add tenant migration `heal_stale_form_config_data` (`down_revision = "b7c2e9a4d1f3"`) per design.md Decision 2:
  - remap removed types in `form_fields` rows (including soft-deleted ones) and every snapshot;
  - backfill `hideLabel` and `visibilityCondition` in snapshots;
  - log the conversions;
  - no-op downgrade.

  Confirm `alembic -c alembic_tenant.ini heads` shows one head.
- [x] 2.2 Migration test with seeded rows of all three removed types, a supported row, and an old-shape snapshot. Assert:
  - the types are mapped, options are cleared where specified, and identity and required fields are unchanged;
  - the keys are backfilled;
  - supported, complete entries are untouched;
  - a second run changes nothing.

## 3. Apply and verify

- [x] 3.1 Upgrade the dev tenant. Verify:
  - `GET /form-builder/effective` has `terms_conditions` as `checkbox_single`, and `hideLabel` and `visibilityCondition` everywhere;
  - the web app's `EffectiveFormStepListResponseSchema` parses the live response;
  - `GET /form-builder/steps` returns 200;
  - no skip warnings are logged afterward.
- [x] 3.2 Docs: in `docs/features/form_builder.md`, cover snapshot normalisation, the removed-type mapping, and skip-and-warn.
- [x] 3.3 Run `ruff check`, `ruff format --check` on touched files, and the full `pytest`, comparing failures against the known pre-existing set.
