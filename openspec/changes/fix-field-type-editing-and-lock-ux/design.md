## Context

See proposal.md for motivation. `add-static-text-field-and-unlock-toggle`
is implemented but not yet archived/synced into `openspec/specs/form-
builder/spec.md` — this change's specs delta is written as ADDED
requirements (not MODIFIED against that other change's not-yet-canonical
text) to avoid depending on an unmerged spec. It still assumes that
change's code is present (the `static_text` field type, `CONTENT_ONLY_
FIELD_TYPES`, the Lock/Unlock control, `isUnlockedForEditing`).

Key facts from the current code:

- `FormField.is_system` (`models.py`) is `true` for every seeded field —
  both locked (Full Name, Email, License Plate, ...) and toggleable
  (Additional Notes, ID Proof Upload, ...) — and `false` for every
  admin-authored field (`service.py::create_field` always sets
  `is_system=False`). This is already the boundary the codebase uses
  elsewhere to distinguish "structurally load-bearing" fields from
  admin-authored ones (e.g. `_requires_static_options` exempts `is_system`
  fields from the options-required check because their real options come
  from a live catalog, not static data).
- `is_locked` is a stricter subset of `is_system` (every locked field is a
  system field, but not every system field is locked — e.g. Additional
  Notes is toggleable, not locked) — so gating field-type editability on
  `is_locked` would incorrectly allow changing a toggleable system field's
  type (e.g. ID Proof Upload's `file_upload` type), which is exactly as
  unsafe as changing a locked field's type, since both are read by
  fixed application code (`invitations/service.py`,
  `checkin/service.py`, ...) that assumes a specific type for that key.
  `is_system` is therefore the correct gate, not `is_locked`.
- `FormFieldUpdate` (`schemas.py`) has no `field_type` field today — a
  field's type has never been part of the update contract, not merely
  disabled in the UI (unlike label/placeholder/description/options, which
  the backend already accepted on a locked field before the UI exposed
  editing them — see that change's design.md Decision 6). Adding
  `field_type` to `FormFieldUpdate` is a genuinely new capability, not
  lifting an existing but hidden permission.
- `SortableFieldRow.tsx` renders its "Required" checkbox unconditionally
  for every field — it was never touched by `add-static-text-field-and-
  unlock-toggle`, which only updated `AddFieldModal`/`FieldPropertiesPanel`.
  That's the root cause of proposal issue #1.

## Goals / Non-Goals

**Goals:**
- Stop showing a Required control for a content-only field anywhere in the
  admin UI, including the field list row.
- Let an admin fix an admin-authored field's type after creation, with the
  same safety checks field creation already applies for the resulting type.
- Simplify the Lock/Unlock button's label to a single, unambiguous action.

**Non-Goals:**
- No change to a *system* field's type, ever — locked or toggleable.
- No automatic migration/cleanup of `validation_rules` or
  `visibility_condition` when a field's type changes (e.g. a `minLength`
  rule left on a field switched to `date_picker`) — same accepted-risk
  posture `add-static-text-field-and-unlock-toggle`'s design.md already
  took for options left dangling after an option removal. A follow-up can
  add stricter cross-property consistency checks if this proves to matter
  in practice.
- No change to how a *submitted answer's* historical data displays if a
  field's type changes after visitors have already answered it under the
  old type (e.g. a `text` answer left behind after the field becomes
  `checkbox_list`) — out of scope, same precedent.
- Does not touch `add-static-text-field-and-unlock-toggle`'s archival/sync
  status — that's a separate housekeeping decision for the user, not part
  of this fix.

## Decisions

**1. Field-type editability is gated on `is_system`, not `is_locked`.**
Per Context above — this is the only boundary that actually distinguishes
"safe to retype" from "unsafe," since a toggleable system field is exactly
as structurally load-bearing as a locked one. `FieldPropertiesPanel`'s
Field Type `<SelectField>` becomes editable (using the same
`FIELD_TYPE_CATALOG` `AddFieldModal` already uses) when `!field.isSystem`,
and stays disabled otherwise.

**2. Re-validation on type change reuses the exact rules field creation
already enforces, evaluated against the *resulting* field state.**
`update_field` computes what the field's `is_required`, `help_text`, and
`options` will be *after* applying this update (the payload's value where
provided, the existing row's value otherwise), then runs the same checks
`FormFieldCreate` runs at creation time: option-required type needs
non-empty options; `static_text` can't be required and needs non-empty
help text. This avoids duplicating validation logic under a different name
— it's the same invariant, just checked at a different time.

**3. Options are cleared (not preserved-but-ignored) when the new type
isn't option-bearing.**
Alternative considered: leave `options` as-is until explicitly cleared by
the admin — rejected because a field that used to be a `checkbox_list` and
is now `text` still carrying a stale `options: ["a","b"]` is confusing
state with no consumer (the visitor-facing renderer keys entirely off
`field_type` to decide whether to read `options` at all), and would need
the exact same "is this type option-bearing" check to *decide* to ignore
it — so there is no complexity saved by not clearing it.

**4. Frontend: field type becomes local draft state (`fieldType`), not
read directly from `field.fieldType`, so every other type-dependent control
in the same panel (Options editor, Placeholder/Required for `static_text`)
reacts live as the admin changes the selection before saving.**
`showOptionsEditor`/`isContentOnly` (added by the prior change) are
recomputed from this draft `fieldType` state instead of the prop, matching
how every other draft field (label, placeholder, ...) already works in
this panel. Reset/re-seed on `field.id` change and on "Reset" continue to
restore the field's actual saved type, same as every other property.

**5. Lock/Unlock button copy: "Unlock to Edit" / "Lock", no state prefix.**
Directly addresses proposal issue #3. The button's `aria`/visible content
changes from `${state} — ${action}` to just the action currently available
(`isUnlockedForEditing ? 'Lock' : 'Unlock to Edit'`) — the icon (lock vs.
unlock) already conveys the current state, so the label doesn't need to
restate it.

## Amendment: presence-vs-transition bug found during implementation

Implementing task 2.2 surfaced a bug in `update_field`'s *existing* locked-
field guard, predating this change: `FieldPropertiesPanel.save()` always
resends every property it manages (label, placeholder, `isActive`,
`isRequired`, ...) at its current value when the admin hasn't touched it —
the same pattern this change's `fieldType` now follows too. The original
guard (`changes.get("is_active") is False or changes.get("is_required")
is False`) rejects based on the *value being present and False*, not on
whether it represents an actual attempted transition. A locked field whose
`isRequired` is already `false` (Email, Phone, Host — see `defaults.py`)
would therefore have every save from the panel rejected, since `false` is
always resent. Adding `field_type` with the same presence-only check would
have made this fail for *every* save on *every* system field, locked or
not. Both guards now compare against the field's current value and only
reject a real `true` → `false` (or type-differs) transition. This is
folded into this change (task 2.6) rather than split into a separate one,
since it's the same bug class this change's own new check would otherwise
have inherited and amplified.

## Risks / Trade-offs

- [Risk] Changing a field's type after visitors have already submitted
  answers under the old type leaves those historical answers displaying
  under a type they weren't collected as (e.g. a free-text answer shown
  where a dropdown's option label is now expected). → Mitigation: accepted,
  same posture as the existing options-editing feature's equivalent risk;
  flagged for the user, not solved here — an admin changing a live field's
  type after real submissions exist is expected to understand that
  consequence, the same way renaming/removing a dropdown option already
  carries that risk today.
- [Risk] Clearing `options` on a type change away from an option-bearing
  type is a destructive, unprompted action (no confirmation dialog). →
  Mitigation: acceptable for this iteration — matches this panel's existing
  posture (e.g. emptying an options list already has no separate
  confirmation step beyond the Save button itself); a confirmation dialog
  can be added later if this proves surprising in practice.

## Migration Plan

No database migration (`field_type` remains a free-text column). Rollout
is a normal backend + frontend deploy; existing fields and published
configs are unaffected until an admin explicitly changes a field's type or
opens a locked field's properties panel (only the button's label text
differs there, with identical behavior).
