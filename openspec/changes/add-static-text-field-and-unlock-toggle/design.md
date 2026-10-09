## Context

See proposal.md for motivation. Key facts about the current implementation
that shape this design (confirmed by reading the code, not just docs):

- `FormField.field_type` is a plain `String(30)` column
  (`src/vmss_api/form_builder/models.py`), validated only by the
  `FormFieldType` `StrEnum` in `schemas.py` — adding a new member needs no
  Alembic migration in either `alembic/` or `alembic_tenant/`.
- `FormField.label`/`help_text` already exist as free-text columns with no
  other required semantics — reusing them as a `static_text` field's
  title/body needs no new column.
- `update_field` (`service.py`) already rejects a locked field's
  `isActive`/`isRequired` transition to `false`, but does **not** reject a
  `label`/`placeholder`/`help_text`/`options` change on a locked field —
  that restriction exists only in the frontend (`FieldPropertiesPanel.tsx`
  disables the inputs unconditionally when `field.isLocked`). This means
  the "unlock" the admin needs is a frontend affordance on top of an
  already-correct backend contract, not a new backend capability.
- `validate_custom_field_values` (`form_builder/validation.py`) only
  rejects a submission for (a) an unknown field key or (b) a missing value
  for a field whose `isRequired` is `true`. A `static_text` field that is
  never `isRequired` and never receives a submitted value trips neither
  check — no changes needed there.
- `CustomFieldsSection.tsx` (`VMMS_WEB`) already renders every non-system
  field on a step generically through `DynamicField`, and this same
  component is shared by both the visitor wizard and the staff wizard
  (confirmed: `registrations/service.py::create_walk_in_registration`
  delegates to `invitations/service.py::create_invitation` for the same
  validation, and both wizards resolve the same `GET /form-builder/effective`
  and import the same step components). A new field type or an edited
  field label needs no separate staff-side wiring.

## Goals / Non-Goals

**Goals:**
- Add `static_text` as a real, usable field type: creatable, editable,
  publishable, and rendered (heading + body, no input) on both wizards.
- Let an admin edit a locked field's label/placeholder/description/options
  through an explicit unlock gesture, without loosening the existing
  required/active/field-type protections on locked fields.
- Confirm (with tests) that both land identically on staff and visitor
  forms via the existing shared pipeline.

**Non-Goals:**
- No rich-text/HTML formatting for `static_text` body content — same
  plain-text posture as `help_text` everywhere else (`help_text` is a
  `String(500)` column with no HTML sanitization pipeline; adding one is
  out of scope). A longer body than fits should still work since
  `help_text`'s 500-char cap already applies uniformly today.
- No change to `rich_text_block` — it stays an inert, unimplemented enum
  value, unrelated to `static_text` (per the user's explicit choice to keep
  the two separate rather than repurpose `rich_text_block`).
- No persisted "unlocked" state — unlocking a field for editing is
  client-side UI state local to the Field Properties panel, not a new
  database column or API field. `is_locked` itself never changes.
- No new permission — unlocking rides the same `form_builder:manage`
  permission that already gates every field mutation; there is no new
  capability being exposed, only a UI gate coming off already-permitted
  edits.
- Does not touch `dropdown_select`/`checkbox_list` options CRUD itself
  (already fully implemented) beyond making that existing editor usable on
  a locked field once unlocked.

## Decisions

**1. `static_text` is a new, distinct `FormFieldType` value, not a
repurposing of `rich_text_block`.**
User's explicit choice. Alternative considered (finish building
`rich_text_block` instead of adding a new type): rejected per that
decision — keeps `rich_text_block` available as a distinct future concept
(e.g. actual rich/HTML formatting) without conflating it with a plain
title+body display block.

**2. Reuse `label` and `help_text` as the field's title and body; no new
column.**
`label` already means "the text shown for this field" for every other
type, and `help_text` already means "admin-authored static content shown
alongside the field" (per the already-shipped description feature). A
`static_text` field is just the case where the body *is* the field's
entire content instead of a caption under some other control — no new
data shape is needed. Alternative considered: a dedicated `content` column
— rejected as pure duplication of `help_text`'s existing meaning for no
behavioral gain, mirroring the same reasoning the
`form-builder-content-and-option-editing` change already applied when it
introduced `help_text`'s UI.

**3. `static_text` is forced non-required, and requires non-empty
`help_text`, enforced in the schema/service layer, not just the UI.**
`FormFieldCreate` gets a model validator rejecting `field_type ==
static_text` combined with `is_required=True` or blank `help_text`.
`FormFieldUpdate` has no `field_type` field (a field's type is immutable
after creation, already true for every type), so the same
`is_required=True` rejection for an existing `static_text` field is
enforced in `service.py::update_field` by checking the target row's
existing `field_type` before applying the change. Enforcing this
server-side (not just disabling the UI control) matches this project's
posture elsewhere (e.g. `_check_options` already rejects invalid state
server-side rather than trusting the admin UI alone).

**4. Rendering: `DynamicField`'s `renderControl` gets one new branch that
returns only a heading built from `field.label`; the wrapper's existing,
unconditional `ExpandableText(field.helpText)` call becomes the body.**
`DynamicField` already renders `renderControl(props)` followed
unconditionally by `<ExpandableText text={props.field.helpText} />` for
every field type. Adding a `static_text` branch that renders just the
heading — and doing nothing else — means the body is "for free" from the
mechanism that already renders every other field type's description,
truncated with the same see-more/see-less control. Alternative considered:
a dedicated `StaticTextBlock` component bypassing the shared wrapper
entirely — rejected as unnecessary duplication; the existing wrapper
already does exactly what's needed once `renderControl` stops trying to
render an input for this type.

**5. Lock/unlock is a per-open ephemeral toggle in `FieldPropertiesPanel`,
not a persisted flag, and does not touch `update_field`'s existing
`is_locked` enforcement.**
`FieldPropertiesPanel` already has a `useEffect` keyed on `field.id` that
resets all local draft state when the admin switches fields (added by the
`fix-field-properties-panel-poll-reset` change, to stop a background poll
from clobbering in-progress edits). A new `isUnlockedForEditing` boolean
resets to `false` in that same effect and in `reset()`, giving "switch
fields" and "reset" the same discard-and-relock behavior for free.
Alternative considered: persist unlock state as a new `FormField` column
(e.g. `content_editable`) — rejected: it would let the *server* forget a
field is meant to stay guarded between sessions is exactly backwards (the
guard is about preventing an accidental edit in the moment, not about who
is allowed to edit it — permission already governs that), and it would be
the one part of this change needing a migration for no behavioral
requirement that asks for cross-session persistence.

**6. Backend enforcement for locked fields' label/placeholder/help_text/
options is intentionally left as-is (permissive), matching the posture the
`form-builder-content-and-option-editing` change already documented and
chose not to tighten.**
That change's design.md explicitly noted: "The backend's own lock
enforcement only actually blocks flipping `isActive`/`isRequired` to
`false` and blocks delete/reorder... The frontend's stricter posture...
is a deliberate UX choice already in place." This change's unlock
affordance is consistent with that existing precedent — it doesn't need to
loosen or tighten the backend, only change when the frontend's stricter
posture applies. Revisiting whether the backend should independently
enforce this (defense in depth beyond "the UI happens to disable the
input") is a separate concern from what the user asked for here, and is
called out as a residual risk below rather than solved in this change.

## Risks / Trade-offs

- [Risk] Because backend enforcement for label/placeholder/help_text/
  options on a locked field was already absent before this change (see
  Decision 6), a direct API call (bypassing the admin UI and its unlock
  gesture entirely) could always edit those properties on a locked field,
  before and after this change. → Mitigation: unchanged risk profile
  (not introduced by this change); `require_permission("form_builder:manage")`
  already gates the endpoint to admins, and the properties this covers
  (label/placeholder/description/options) carry no security-sensitive
  weight — flagged for the user to decide whether a follow-up change
  should add server-side enforcement mirroring the new UI gate, but not
  blocking this change.
- [Risk] Reusing `help_text`'s existing 500-character cap for a
  `static_text` field's body may be too short for a lengthy Terms &
  Conditions document. → Mitigation: acceptable for this iteration (matches
  the cap every other field's description already has); a longer-body need
  can raise the shared `help_text` max length in a follow-up without a
  structural change, since nothing about this design assumes 500 chars
  specifically.
- [Risk] An admin unlocks a field, makes an edit, and the panel's poll
  cycle (the same 15s background poll `fix-field-properties-panel-poll-reset`
  addressed) ticks mid-edit. → Mitigation: that fix's `useEffect` already
  keys off `field.id`, not the `field` object reference, so a background
  refresh of the same field's server data does not reset `isUnlockedForEditing`
  or the in-progress draft — the new state rides the same fix, no new
  bug class introduced.

## Migration Plan

No database migration (`field_type` is a free-text column; no new columns
needed for either half of this change). Rollout is a normal backend +
frontend deploy; the new field type and the unlock affordance are both
purely additive — existing fields, steps, and published configs are
unaffected until an admin explicitly creates a `static_text` field or
unlocks an existing locked field to edit it.
