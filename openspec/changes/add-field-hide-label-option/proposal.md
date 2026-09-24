## Why

An admin building a form sometimes wants a field's input to appear without
its label showing on the visitor-facing form — e.g. a single field on a
step whose step name/description already makes its purpose obvious, or a
field placed inline where a placeholder alone is sufficient. Today a
field's `label` always renders; there's no per-field way to suppress it,
so admins resort to workarounds like an empty-looking label, which still
occupies layout space and reads oddly in the admin UI. This change adds an
explicit `hideLabel` flag admins can toggle per field.

## What Changes

- Add `hide_label: bool` (default `false`) to a form field. A field still
  declares a non-empty `label` at creation (used in the admin UI, in
  validation error messages, and as the accessible name for the field) —
  `hideLabel` only controls whether that label is rendered visually on the
  visitor-facing form. It does not change validation, submission, or any
  other field behavior.
- `hideLabel` is settable at field creation (`FormFieldCreate`) and
  editable afterward via field update (`FormFieldUpdate`), for any field
  type, the same way `width` is — no lock-based restriction beyond what
  already applies to editing any other display property of a locked field.
- `hideLabel` is included in `FormFieldOut` (the admin-facing field read
  model) and in the effective-form snapshot returned by
  `GET /form-builder/effective` (the payload the visitor-facing renderer
  consumes) — this is the signal the frontend acts on to actually omit the
  label from its render; that rendering change itself happens in the
  separate frontend repo, out of scope here.

## Capabilities

### Modified Capabilities
- `form-builder`: a field gains a new `hideLabel` display property,
  settable at creation and update time, exposed on both the admin read
  model and the published effective-form snapshot.

## Impact

- `src/vmss_api/form_builder/models.py`: `FormField` gains a
  `hide_label: Mapped[bool]` column (default `False`).
- `src/vmss_api/form_builder/schemas.py`: `hide_label` added to
  `FormFieldCreate`, `FormFieldUpdate`, and `FormFieldOut`.
- `src/vmss_api/form_builder/service.py`: `_step_to_snapshot`'s per-field
  dict gains `"hideLabel": f.hide_label`, so it flows into both the draft
  steps listing and the published effective-form snapshot (the same
  function backs both — see design.md).
- `alembic_tenant/`: a new tenant-schema migration adding the
  `hide_label` column to `form_fields`, applied to every existing tenant
  schema the same way any other tenant migration is
  (`database-architecture.md` §5).
- No change to `invitations`/`registrations` submission validation —
  `hideLabel` is a display-only property, not consulted by
  `form_builder/validation.py`.
