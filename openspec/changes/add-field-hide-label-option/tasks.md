## 1. Data Model

- [x] 1.1 In `src/vmss_api/form_builder/models.py`, add
      `hide_label: Mapped[bool] = mapped_column(Boolean, default=False)` to
      `FormField`, alongside `is_required`/`is_active`/`width`.
- [x] 1.2 Generate a tenant-schema migration
      (`ddev exec uv run alembic -c alembic_tenant.ini revision --autogenerate -m "add hide_label to form_fields"`
      or the project's equivalent tenant-migration command) adding
      `hide_label BOOLEAN NOT NULL DEFAULT false` to `form_fields`. Confirm
      it targets `alembic_tenant/versions/`, not the global `alembic/`
      tree, and chains onto the current tenant-schema head.

## 2. Schemas

- [x] 2.1 In `src/vmss_api/form_builder/schemas.py`, add
      `hide_label: bool = False` to `FormFieldCreate`.
- [x] 2.2 Add `hide_label: bool | None = None` to `FormFieldUpdate`
      (matching the `exclude_unset=True` partial-update pattern every
      other optional-to-change property already follows there).
- [x] 2.3 Add `hide_label: bool` to `FormFieldOut`.

## 3. Service Layer

- [x] 3.1 In `src/vmss_api/form_builder/service.py`'s `create_field`
      (or equivalent field-creation path), pass `hide_label=payload.hide_label`
      through to the new `FormField` row, matching how `width=payload.width.value`
      is passed today. Also wired `hide_label` through the two other
      `FormField(...)` construction sites: system-field seeding
      (`hide_label=False`, matching the existing `width="full"` literal)
      and branch-scope cloning (`hide_label=source_field.hide_label`,
      matching `width=source_field.width`).
- [x] 3.2 Confirm `update_field` picks up `hide_label` automatically via
      its existing `payload.model_dump(exclude_unset=True)` /
      attribute-assignment pattern — no special-case branch needed since
      `hideLabel` isn't subject to any of the existing type-dependent or
      lock-dependent checks (see design.md Decisions). Verify by reading
      the updated function; add a code change only if the update path
      turns out to allow-list fields explicitly rather than applying
      `changes` generically.
- [x] 3.3 In `_step_to_snapshot`, add `"hideLabel": f.hide_label` to the
      per-field dict alongside `"width": f.width`, so it reaches both the
      draft `GET /form-builder/steps` response and the published
      effective-form snapshot (`GET /form-builder/effective`).

## 4. System Field Defaults

- [x] 4.1 Check `src/vmss_api/form_builder/defaults.py`'s system-field seed
      catalog — no explicit `hide_label` needed for any seeded field
      (defaults to `False`, matching today's always-visible-label
      behavior), but confirm the seed construction doesn't require every
      field to explicitly enumerate every column. Handled directly in the
      `FormField(...)` seeding constructor (task 3.1) rather than
      `defaults.py`'s `FieldSpec` dataclass, matching how `width` is
      already hardcoded to `"full"` at that same construction site rather
      than carried on `FieldSpec`.

## 5. Tests

- [x] 5.1 In `src/vmss_api/form_builder/tests.py`, add a test that creating
      a field with `hideLabel: true` succeeds and the response reports
      `hideLabel: true`.
- [x] 5.2 Add a test that creating a field without `hideLabel` defaults to
      `hideLabel: false`.
- [x] 5.3 Add a test that updating an existing field's `hideLabel` from
      `false` to `true` (and back) persists and is reflected in
      `GET /form-builder/steps`.
- [x] 5.4 Add a test that publishing a branch's form after setting
      `hideLabel: true` on a field surfaces `hideLabel: true` in
      `GET /form-builder/effective`'s snapshot for that field.
- [x] 5.5 Add/extend a submission test confirming `hideLabel: true` has no
      effect on required-field validation — a required field with
      `hideLabel: true` still rejects a missing value the same way an
      always-visible required field does.
- [x] 5.6 Run `ddev exec uv run pytest src/vmss_api/form_builder/tests.py`
      and confirm the full suite passes: **101/101 passed**. Also ran
      `src/vmss_api/invitations/tests.py`: 327/328 passed; the one
      failure (`test_get_invitation_detail_includes_id_proof_url_with_documents_view`)
      is the same pre-existing flake identified in the earlier
      `update-form-field-type-catalog` change (`polyfactory` randomly
      generating `None` for `InvitationVisitorFactory`'s unpinned
      `id_proof_storage_key`), unrelated to `hideLabel`.
      Note: the local `vmss_test` database's `tenant_acme_test` schema was
      stale from before this session (missing the new `hide_label`
      column, since `Base.metadata.create_all` only creates missing
      tables, not missing columns on existing ones) — dropped that schema
      so the session fixture recreated it from current model metadata.

## 6. Documentation

- [x] 6.1 Update `docs/features/form_builder.md` to document `hideLabel`
      alongside the existing `width` display-property documentation, per
      `project-rules.md`'s "New Features" documentation expectation.
- [x] 6.2 Prepare a frontend handoff note (same pattern as the
      `update-form-field-type-catalog` change) describing the new
      `hideLabel` field on `GET /form-builder/effective`'s snapshot, so
      the React portal's field renderer can act on it — actually
      implementing that rendering change is out of scope for this repo.
      Note included in the apply-completion summary below, ready to
      paste/send.
