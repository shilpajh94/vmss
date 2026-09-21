## Context

`AdminFormBuilderStepEditorPage` polls `load({ silent: true })` every 15
seconds via `usePolling` (`use-admin-form-builder-step-editor.ts`) so the
field list stays fresh without a manual refresh. `isBusy` for that poll only
covers `isAddFieldOpen || pendingDelete !== undefined || isPublishing` — it
does not know or care whether the admin currently has the Field Properties
panel open and is mid-edit on one of the fields the poll is about to
refetch.

Each silent poll tick calls `setFields(sortedFields)` with a brand-new array
of brand-new `FormField` objects parsed from the response, even when nothing
about the data actually changed. `selectedField = fields.find(f => f.id ===
selectedFieldId)` in the parent page therefore also becomes a new object
reference every 15 seconds. `FieldPropertiesPanel` receives this as a new
`field` prop and its `useEffect(() => { ...reset every draft state... },
[field])` re-runs — not because the admin switched fields, but because the
object *identity* changed, even though, for the field being edited, the
*content* is identical to what's already loaded. This resets the admin's
unsaved draft (including anything typed/pasted since the last poll tick)
back to the server's last-fetched values. See proposal.md for the reported
symptom and impact.

## Goals / Non-Goals

**Goals:**
- An admin's unsaved edit in the Field Properties panel (any of its draft
  fields — label, placeholder, description, options, validation rules,
  visibility condition, width) survives a background poll tick for as long
  as they're still editing the same field.
- Keep the 15-second background refresh itself untouched — other consumers
  of `fields` (the row list, publish-state banner) still benefit from it.

**Non-Goals:**
- Not attempting optimistic-merge of a concurrent *external* edit (e.g.
  another admin, in another tab, changing the same field while this admin
  has it open) into the open draft. That's a real but separate concern
  (last-write-wins on save, as today) — out of scope for this fix.
- Not pausing/debouncing the background poll itself. The poll refreshing
  `fields` is fine; the bug is specifically the panel's over-eager re-sync
  from any new `field` reference, not the poll's existence.

## Decisions

**Key the draft-reset `useEffect` on `field.id`, not the `field` object
reference.**
The panel's job is "edit a draft of the field currently selected." The only
event that should discard an unsaved draft and load fresh values is the
admin selecting a *different* field to edit (a different `id`) — not the
parent re-fetching the same field's data in the background. Changing the
effect's dependency from `[field]` to `[field.id]` makes that the literal
behavior: the effect only re-seeds local state when the id changes.

Alternatives considered:
- **Pause the background poll while the panel is open / dirty.** Would also
  fix this, and would additionally preserve the (minor, currently
  unverified-as-relied-upon) behavior where toggling a field's "Required"
  switch directly from its row (`SortableFieldRow`) while that same field's
  panel is open live-updates the panel's Required toggle. Rejected as the
  primary fix because it's a bigger behavioral change (stops *all* background
  refresh while any panel is open, including for fields the admin isn't
  touching) to fix a bug that's really about the panel's own re-sync
  condition being too broad. The id-keyed fix is the narrower, more direct
  correction; pausing the whole poll is a heavier hammer for a smaller nail.
- **Deep-compare `field` content before deciding whether to reset.** Would
  work but adds real complexity (comparing nested `validationRules`/
  `visibilityCondition` objects) for no behavioral gain over the id check —
  the only case a same-id, different-content refresh should win over an
  in-progress draft is the admin's own just-saved update, which already
  matches the draft (see below), so there's nothing meaningful left for a
  deep compare to catch.
- **Track a `isDirty` flag and only skip the reset when dirty.** Rejected as
  unnecessary: keying on `field.id` already captures the right invariant
  (same field selected → don't stomp the draft) without needing to track
  dirtiness separately, and is simpler to reason about.

**Effect on the "external Required-toggle sync" edge case.**
Today, if an admin toggles a field's Required switch from its row
(`SortableFieldRow`) while that same field's Properties panel happens to be
open, the panel's `isRequired` display currently updates on the next poll
tick (because `field`'s reference changes) or immediately (because
`toggleFieldRequired`'s own `setFields` call also changes the reference).
With the id-keyed fix, the *poll-driven* version of this sync stops (poll
ticks with unchanged id + unchanged reference-driven re-seed no longer
re-seed); the *immediate* version (right after `toggleFieldRequired`'s own
`setFields` call) still works today only because it also produces a new
`field` reference at that moment — after this fix, it would need to instead
be recognized as "same id" and thus also stop resetting the panel. This is
an accepted, minor trade-off: toggling Required from the row while that same
field's full panel is open is an edge case, and the panel's own `isActive`
toggle already lets an admin do the equivalent from inside the panel. No
change requested here to reconcile that specific case; noted for awareness.

## Risks / Trade-offs

- [Risk] After this fix, a genuine server-side change to the currently-open
  field (e.g. `toggleFieldRequired` from its row, or another admin's edit)
  will no longer be reflected in the open panel until the admin switches
  away and back, or explicitly clicks Reset. → Mitigation: this is the
  documented, accepted trade-off above; the panel's own Reset button remains
  the explicit way to discard a draft and reload current server values.
- [Risk] Someone later adds a new local draft field to the panel and forgets
  it's covered by the same `useEffect`/`reset()` pair, reintroducing a
  similar bug in a different form (e.g. a field that needs to always track
  the live prop regardless of id). → Mitigation: none beyond code review; the
  panel's existing pattern (every draft field seeded and reset together) is
  a single, findable spot.

## Migration Plan

No data migration; pure frontend behavior fix. No new dependency, no schema
change, no API change. Ships as a normal `VMMS_WEB` deploy.
