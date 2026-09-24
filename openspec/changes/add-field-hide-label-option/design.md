## Context

A `FormField` already carries one purely-visual property with the exact
shape this change needs: `width` (`half`/`full`) — stored on the model,
passed through `FormFieldCreate`/`FormFieldUpdate`/`FormFieldOut`
unchanged, and copied into `_step_to_snapshot`'s per-field dict
(`src/vmss_api/form_builder/service.py`) with no validation-layer
involvement, since `form_builder/validation.py` only ever reads
`fieldType`/`options`/`validationRules`/`isRequired` when checking a
submitted value. `hideLabel` is the same shape of property: a display hint
consumed by the frontend renderer, irrelevant to submission validation.
See proposal.md - Why for the motivation.

## Goals / Non-Goals

**Goals:**
- Add `hideLabel` with the minimum plumbing needed for it to reach the
  effective-form snapshot the frontend renderer reads.

**Non-Goals:**
- No frontend rendering change — that's the separate React portal repo's
  work, out of scope for this backend change (see the earlier
  `update-form-field-type-catalog` change's handoff note for the pattern
  of flagging frontend-side follow-up work).
- No restriction on which field types may set `hideLabel`. `static_text`
  uses `label` as its rendered heading text (per the existing "static_text
  is a display-only content block" behavior) — `hideLabel: true` on a
  `static_text` field simply means that heading doesn't render, which is a
  legitimate admin choice (body content with no heading), not a case this
  change needs to special-case or reject.
- No lock-based gating beyond what already exists. Locked-field
  restrictions on `is_active`/`is_required`/`field_type` are enforced
  server-side (`service.py::update_field`); label/placeholder/description/
  options are *not* server-enforced today — the "disabled unless
  unlocked" behavior for those lives entirely in the Field Properties
  panel (frontend). `hideLabel` follows the same posture as `width`: no
  new server-side lock check.

## Decisions

- **New column, not folded into an existing JSONB blob.** `validation_rules`
  and `visibility_condition` are JSONB because they're structured,
  variable-shape data. `hideLabel` is a single boolean, the same shape as
  `is_required`/`is_active`/`width` — it gets its own typed column
  (`hide_label: Mapped[bool]`, default `False`), consistent with how every
  other simple flag on `FormField` is modeled, rather than inventing a
  generic "display options" JSON bucket for one flag.
- **`hideLabel` flows through `_step_to_snapshot` only** — no separate
  code path for "draft" vs "published" representations, because
  `_step_to_snapshot` already is that single source for both (confirmed by
  reading `service.py`: the admin `GET /form-builder/steps` listing and
  the publish flow that populates `FormConfigVersion` both build from this
  same function). Adding one key to its per-field dict is sufficient;
  `resolve_effective_form` (`GET /form-builder/effective`, the
  public/consumer-facing endpoint) needs no separate change since it reads
  the already-published snapshot.
- **`label` stays mandatory even when `hideLabel` is `true`.** Rejected
  making `label` optional when `hideLabel` is set: the accessible-name/
  validation-error-message use of `label` doesn't go away just because the
  visitor-facing form doesn't show it visually, and keeping `label`
  unconditionally required avoids a second code path in
  `FormFieldCreate`'s validation for "required unless hideLabel".

## Risks / Trade-offs

- [An admin sets `hideLabel: true` on a field with no `placeholder` either,
  leaving a visitor with no visible cue at all for what the input is for]
  → Out of scope to prevent server-side — this is a content-authoring
  concern for the admin UI to surface as a warning, not a validation rule;
  `label` remains available as the accessible name regardless, so the
  field is not unusable, just visually unlabeled.

## Migration Plan

- One tenant-schema Alembic migration (`alembic_tenant/versions/`) adding
  `hide_label BOOLEAN NOT NULL DEFAULT false` to `form_fields`, authored
  once and applied to every existing tenant schema per
  `database-architecture.md` §5 — same mechanism as any other tenant
  migration, no per-tenant authoring needed. Backfill is implicit via the
  column default; no data migration script required.
