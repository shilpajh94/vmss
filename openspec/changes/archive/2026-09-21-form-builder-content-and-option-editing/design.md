## Context

This change is frontend-only (`VMMS_WEB`). The backend already carries
everything needed on the wire:

- `FormField.helpText: string | null` (max 500 chars) is accepted by
  `FormFieldCreate`, `FormFieldUpdate`, and returned by `FormFieldOut` /
  `GET /form-builder/effective` — but no frontend UI writes it, and
  `DynamicField.tsx` never reads it.
- `FormField.options: string[] | null` is accepted by both
  `FormFieldCreate` (required for `dropdown_select`/`checkbox_list`, via
  `OPTION_REQUIRED_TYPES`) and `FormFieldUpdate` (optional, same
  non-empty-if-required check enforced server-side in `update_field`) — but
  `FieldPropertiesPanel.tsx` (the editor for an *existing* field) has no
  options control at all today; only `AddFieldModal.tsx` (creation) exposes
  one.
- The admin UI's existing convention for locked fields is: label/placeholder
  inputs render `disabled={field.isLocked}` in `FieldPropertiesPanel`, and a
  "Locked" badge replaces the active/inactive toggle. The backend's own lock
  enforcement only actually blocks flipping `isActive`/`isRequired` to
  `false` and blocks delete/reorder — it does not reject a label, placeholder,
  `helpText`, or `options` change on a locked field. The frontend's stricter
  posture (disable the whole control, not just certain values) is a
  deliberate UX choice already in place; this change extends the same
  posture to the two new controls rather than relying on the backend's looser
  enforcement.
- No reusable truncate/expand-collapse text component exists anywhere in
  `VMMS_WEB` today (confirmed by search — existing `truncate` usages are
  plain single-line CSS ellipsis with no expand affordance).

See proposal.md for the "why" and the full list of affected files.

## Goals / Non-Goals

**Goals:**
- Let an admin set and later change a field's description (`helpText`) from
  both the creation modal and the properties panel, for any field type.
- Let an admin change an existing option-bearing field's option list, not
  just set it once at creation.
- Render a field's description under its input on the visitor-facing form,
  truncated to its first sentence, with a generic expand/collapse control
  reused across every field type and step.

**Non-Goals:**
- No backend/API/schema changes — `helpText` and `options` are already
  fully supported end to end.
- No change to what happens when an option is removed while a live
  visibility condition (`visibilityCondition.value`) or an in-flight/past
  submission still references it. Today the backend does not cascade-clean
  visibility conditions or historical submission data when an option
  disappears, and this change does not alter that — an admin who renames or
  removes an option that a condition depends on gets whatever behavior
  exists today (the condition simply stops matching). Flagged as a known
  gap, not solved here.
- No rich-text/HTML formatting for the description — it stays a plain
  multi-line text value (matches `helpText`'s existing `str | None`
  contract); "first sentence" truncation operates on plain text.
- Does not touch the still-scaffolded `rich_text_block`/`signature_pad`
  field types — those remain enum-only with no rendering behavior, as
  today. A field's description is a property of *any* field (including a
  plain toggle or checkbox list), not a new field type of its own.
- Does not address the separate, pre-existing gap where `CarriedItemsStep`/
  `ConsentStep` hardcode their own step-intro paragraph instead of rendering
  `FormStep.description` — that's a step-level concern, not a field-level
  one, and out of scope for this change.

## Decisions

**1. Reuse `helpText` as the "static content" field, don't add a new one.**
The proposal's requirement #1 ("admin-added static values, e.g. terms &
conditions text") and requirement #3 ("description below the field, with
see more/less") both describe the same underlying data: free text attached
to a field, authored by an admin, displayed to the visitor. `helpText`
already exists for exactly this on the wire contract. Introducing a second,
parallel "static content" property would duplicate `helpText` for no
behavioral gain and fork two near-identical fields in the schema.
Alternative considered: model this as a distinct `staticContent` field
separate from `helpText` (in case `helpText` was meant for a shorter admin
tooltip rather than visitor-facing body copy) — rejected because nothing in
the current schema, UI, or tests treats `helpText` as anything other than
"free text about this field," and there is no other consumer of `helpText`
today whose meaning this would conflict with.

**2. Label the UI control "Description," not "Help Text."**
The wire field stays `helpText`; only the UI copy changes. "Help text"
reads as a UI hint for filling in a text box; the actual use case (a
terms-and-conditions paragraph, a consent statement's body) is closer to
"description." Renaming the underlying API field was considered and
rejected as unnecessary churn for a label-only concern (see proposal.md
Impact — no backend changes).

**3. Options editor: inline list of text rows with add/remove, matching
`AddFieldModal`'s existing comma-separated convention on submit.**
`FieldPropertiesPanel` will render one text input per existing option (with
a remove button) plus an "Add option" row, mirroring the same option
strings `AddFieldModal` already collects — on save, it sends the same
`options: string[]` shape `FormFieldUpdate` already accepts. Reordering
reuses the same drag-handle pattern `SortableFieldRow` already uses for
field ordering, applied to option rows. Alternative considered: keep
`AddFieldModal`'s single comma-separated text input for the properties
panel too, for consistency — rejected because editing one option out of an
existing seven-option list (e.g. `carried_items`) via comma-separated text
is error-prone (a stray comma silently splits an option in two) once
there's real data to edit rather than composing a fresh list from scratch.

**4. Truncation is a UI-only concern, computed client-side from the plain
`helpText` string; no backend change.**
"First sentence" is derived client-side (e.g. split on the first
`.`/`!`/`?` followed by whitespace or end-of-string) purely for the default
collapsed view — the full text is always already present in `helpText` from
`GET /form-builder/effective`, so no separate "preview" field or backend
truncation is needed. The expand/collapse component takes the full text and
a computed "preview" slice as props; if the computed preview covers the
entire string (single sentence, or no sentence-ending punctuation found),
it renders the full text with no control, per the spec's "single-sentence"
scenario.

**5. One shared expandable-text component, used from `DynamicField`, not
duplicated per field-type branch.**
Since `DynamicField.tsx` already branches per `field.fieldType`, the
straightforward-but-wrong approach would be adding the description render
inside each branch's own JSX. Instead, wrap each branch's existing return
with a small layout helper (or lift the description render to one place
after the type-specific control renders) so every field type gets identical
description behavior for free and a future field type can't forget to wire
it in.

## Risks / Trade-offs

- [Risk] An admin renames/removes an option that a submitted registration
  already recorded, or that a visibility condition still targets by value,
  producing a display mismatch for historical data or a silently
  non-matching condition. → Mitigation: none added by this change (see
  Non-Goals); flagged so the user can decide whether to scope a follow-up
  change once this ships.
- [Risk] "First sentence" splitting on `.`/`!`/`?` can truncate misleadingly
  for text containing abbreviations (e.g. "e.g." or "Inc.") or decimal
  numbers. → Mitigation: acceptable for the terms-and-conditions/consent-
  statement use case this targets; treat as a known heuristic limitation,
  not a defect to solve with full NLP sentence-boundary detection.
- [Risk] Making the options editor freely reorderable/removable on
  `is_locked=False` system-seeded fields (e.g. `carried_items`'s `items`
  field) changes options an admin has never been able to touch before,
  for a field that ships with product-default values. → Mitigation: this is
  exactly the requested capability (req. #2 in the user's ask), not an
  accidental side effect; the existing per-tenant/per-branch scoping already
  isolates the blast radius to one branch's own configuration.

## Migration Plan

No data migration. This is additive UI on top of already-supported API
fields; existing fields with `helpText: null` or `options` already set
continue to work unchanged. Rollout is a normal frontend deploy; no
backend deploy ordering constraint.
