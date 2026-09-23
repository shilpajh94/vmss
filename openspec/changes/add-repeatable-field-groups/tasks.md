## 0. Status of the original implementation

The first pass of this change (repeatable field groups without conditional
visibility, Vehicle Info's admin-configurable range, the generic
repeatable-group mechanism) was already implemented, tested, and verified
against a real Postgres tenant schema and a clean frontend build — see the
git history for `form_builder/`, `invitations/`, `registrations/`, and
`VMMS_WEB`'s form-builder/wizard files. That work stays as-is except where
a task below explicitly says to rework it. This section exists so `/opsx:
apply` doesn't re-do work that's already correct.

**Kept unchanged (do not redo):** `FormFieldGroup` model/table, the
group-key branch-wide uniqueness check, `min_instances`/`max_instances`
with `max >= min` validation, locked-group delete/non-repeatable guards,
group CRUD endpoints, publish-snapshot group definitions, Vehicle Info's
admin-configurable range, custom repeatable groups' `groupValues`
submission/persistence/validation, the shared frontend
`RepeatableFieldGroup` component, `GenericConfiguredStep.tsx`'s
grouped/ungrouped field split (including the non-repeatable-group fix),
all `add-repeatable-field-groups` tests already passing.

**Needs rework (tasks below):** Visitor Info's group-visitor-count cap
(currently untouched — still enforced by the old
`settings.invitation_max_group_visitors` check, not the group's own
`maxInstances`).

**Net new (tasks below):** group-level `visibilityCondition` (conditional
groups) end to end — model, authoring validation, publish snapshot,
submission-time evaluation, hidden-group-skips-required, and the
corresponding frontend/admin UI.

## 1. Database & Migrations

- [x] 1.1–1.7 (original migration `b8e3f4a1c6d2`) — done, unchanged.
- [x] 1.8 Add `visibility_condition` (JSONB, nullable) to `form_field_groups`
      (`form_builder/models.py::FormFieldGroup`).
- [x] 1.9 New `alembic_tenant` revision (down-revision `b8e3f4a1c6d2`):
      `op.add_column` for `form_field_groups.visibility_condition`
      (`schema=` explicit, same table this migration doesn't own but
      already exists from 1.4 — so this needs the `op.add_column`
      `schema_translate_map` gotcha the same way `form_fields.group_id`
      did). In the same revision, backfill: read
      `settings.invitation_max_group_visitors` (a plain Python constant at
      migration-run time) and `UPDATE` every existing Visitor Info
      (`"visitors"` key) group row's `max_instances` to that value, for
      every branch and the tenant default — so the numeric cap is
      identical immediately before/after this migration for every
      existing tenant (design.md Migration Plan step 2).
- [x] 1.10 Run `alembic -c alembic_tenant.ini heads` to confirm a single
      head; apply to the dev `tenant_default` schema and verify via
      `psql` that its Visitor Info group's `max_instances` now matches
      `settings.invitation_max_group_visitors`'s current value (20 by
      default).

## 2. Form Builder — Backend

- [x] 2.1–2.7 (original) — done, unchanged.
- [x] 2.8 `schemas.py`: add `visibility_condition: VisibilityCondition |
      None` to `FormFieldGroupCreate`/`FormFieldGroupUpdate`/
      `FormFieldGroupOut` (reuse the existing `VisibilityCondition` model
      fields already use — same shape, no new schema needed).
- [x] 2.9 `service.py`: authoring-time validation for a group's condition —
      extract `_check_visibility_condition`'s "target field exists on this
      step" check into a form usable for both fields and groups, add a
      group-specific self-reference guard (target field must not be a
      member of the group whose condition it's on), and call it from
      `create_group`/`update_group`. No transitive-cycle walk needed for
      groups (design.md Decision 7 — nothing can reference a group's
      condition).
- [x] 2.10 `defaults.py`: seed the Visitor Info group's `max_instances`
      from `settings.invitation_max_group_visitors` in
      `_materialize_defaults_if_empty` (new-tenant/new-branch path,
      complementing 1.9's backfill for existing ones).
- [x] 2.11 `service.py::_step_to_snapshot` / `defaults.py`'s effective-form
      builders: include each group's `visibilityCondition` in the
      published snapshot and the in-code fallback shape, alongside the
      fields already there.
- [x] 2.12 `validation.py`: add a function evaluating a group dict's
      `visibilityCondition` against a values map (the same
      equals/not_equals comparison `_validate_value_against_field`-
      adjacent code already does for fields), returning whether the group
      is currently visible for that submission.

## 3. Invitations & Registrations — Backend

- [x] 3.1–3.5 (original) — done, unchanged.
- [x] 3.6 `invitations/service.py`: remove the standalone
      `if len(payload.visitors) > settings.invitation_max_group_visitors`
      check; add a `visitor_info_group(effective_form)` lookup (mirrors
      `vehicle_info_group`) and call
      `validate_group_instance_count(visitor_info_group, len(payload.
      visitors), scope=...)` instead, so the Visitor Info group's
      `maxInstances` becomes the sole enforcement path (design.md revised
      Decision 5). `core/config.py`'s `invitation_max_group_visitors`
      setting stays defined (the migration needs to read it) but is no
      longer consulted by `create_invitation` after this task.
- [x] 3.7 `invitations/service.py`: for each custom group evaluated in the
      existing `custom_groups_for_invitation_scope` loop, use 2.12's
      evaluator against the group's own scope values (or the invitation-
      level `customFieldValues`/top-level submitted fields, whichever the
      group's condition's watched field lives in) to determine visibility;
      when hidden, skip the missing-required check for that group's fields
      in `validate_custom_field_values` while still validating any
      value that was supplied anyway (specs/invitations/spec.md "A Hidden
      Custom Field Group's Fields Are Not Required At Submission").
- [x] 3.8 Confirm `registrations/service.py` needs no change (thin
      passthrough — inherits 3.6/3.7 automatically, same as the original
      implementation's tasks 3.5).

## 4. Frontend — Admin Step Editor (`VMMS_WEB`)

- [x] 4.1–4.4 (original) — done, unchanged.
- [x] 4.5 Find the existing field-level `visibilityCondition` authoring UI
      (the control that lets an admin pick a watched field/operator/value
      for a *field*, referenced in `docs/features/form_builder.md`'s
      "Field types" section) and add the equivalent control to
      `GroupCard.tsx`, wired to `saveGroupProperties({visibilityCondition:
      ...})`.
- [x] 4.6 Surface a group-condition rejection (dangling reference,
      self-reference) inline via the same `saveGroupProperties` error
      contract already used for the min/max range.

## 5. Frontend — Visitor Wizard (`VMMS_WEB`)

- [x] 5.1, 5.4, 5.5 (original) — done, unchanged. 5.2/5.3 remain
      deliberately not done, per the original tasks.md's recorded
      rationale.
- [x] 5.7 Add `visibilityCondition` to the domain's `EffectiveFormFieldGroup`
      zod schema (`form-builder-schema.ts`).
- [x] 5.8 `GenericConfiguredStep.tsx`: evaluate each group's
      `visibilityCondition` against the step's current `value`/other
      groups' current instance data (whichever scope the watched field
      lives in) and skip rendering a hidden group entirely — mirroring
      whatever pattern the wizard already uses to conditionally render a
      single hidden *field* (find and reuse it, per docs/proposal.md's
      note that a field's own condition already renders conditionally on
      the visitor form today, even though the *server* doesn't evaluate it
      at submission time — see design.md Decision 8's field/group
      distinction, which is a backend-only asymmetry, not a frontend one).

## 6. Documentation

- [x] 6.1, 6.2 (original) — done, unchanged.
- [x] 6.3 `docs/features/form_builder.md`: document group-level
      `visibilityCondition` (same shape as field-level, plus the
      self-reference guard and "no transitive cycle needed" rationale),
      and that a hidden group's fields are never required.
- [x] 6.4 `docs/features/invitations.md`: document the visitor-count cap
      now coming from Visitor Info's group `maxInstances` (replacing the
      old `INVITATION_MAX_GROUP_VISITORS` mention, if any), and the
      hidden-custom-group-skips-required behavior.
- [x] 6.5 Note the retired-setting operational trade-off (design.md's
      flagged risk — no more env-var-only tuning of the group-visitor cap)
      somewhere an operator would find it, e.g. `.env.example`'s comment
      on `INVITATION_MAX_GROUP_VISITORS` if that key stays there for
      migration-authoring reference.

## 7. Testing

- [x] 7.1–7.4 (original) — done, unchanged.
- [x] 7.6 Rework `invitations/tests.py::
      test_create_group_invitation_exceeding_max_visitors_rejected` — it
      currently does `monkeypatch.setattr(settings,
      "invitation_max_group_visitors", 1)`, which will stop having any
      effect once task 3.6 lands. Replace with setting the branch's
      Visitor Info group's `maxInstances` to 1 via the Form Builder API
      (mirroring `_update_and_publish_group_range` from the original
      change's tests) before submitting the oversized group payload.
- [x] 7.7 `form_builder/tests.py`: group conditional-visibility authoring —
      accept a valid same-step reference, reject a dangling reference,
      reject a self-reference (watching a field that's a member of the
      group itself), publish-then-effective-form includes the group's
      `visibilityCondition`.
- [x] 7.8 `invitations/tests.py`: a hidden custom group's required field is
      not required (accepted); the same group visible (condition true, or
      no condition) still requires it (rejected); a value supplied for a
      hidden group's field is still type/option-validated.
- [x] 7.9 Migration verification (mirrors 7.4's approach): apply the new
      migration (1.9) to the dev `tenant_default` schema, confirm via
      `psql` the Visitor Info group's `visibility_condition` column exists
      (NULL for the seeded row) and its `max_instances` now matches
      `settings.invitation_max_group_visitors`; verify `downgrade -1` and
      re-`upgrade head` round-trip cleanly.
- [x] 7.10 Full regression: re-run `form_builder/tests.py`,
      `invitations/tests.py`, `registrations/tests.py` in full after 3.6's
      removal of the settings-based check, to confirm nothing else
      depended on it.
- [x] 7.11 Frontend: `tsc -b`, `oxlint`, `vite build` clean after 4.5/4.6/
      5.7/5.8.
- [ ] 7.12 A live browser click-through (create a conditional + repeatable
      custom group, publish, confirm it shows/hides correctly on the
      visitor wizard as the watched field changes, submit) — still not
      done from the original change's 7.5, carried forward here.
