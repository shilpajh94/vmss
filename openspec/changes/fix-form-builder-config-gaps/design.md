## Context

See `proposal.md` for motivation and the investigation findings it
summarizes. Relevant current state this design builds on:

- `form_builder/service.py::reorder_steps`/`reorder_fields` (`:235-249`,
  `:400-414`) validate only that the submitted id set matches the existing
  set — no `is_locked` check.
- `form_builder/service.py::publish` (`:489-531`) already filters the
  snapshot correctly on both `step.isActive` and each field's `isActive`
  (`:507-513`), and is the sole place that invalidates the Redis
  effective-form cache (`:530`) — this part needs no change.
- `VMMS_WEB`'s admin Form Builder has two pages: the Steps overview
  (`admin-form-builder.tsx`, holds "Publish Changes") and the Step/Field
  Editor (`admin-form-builder-step-editor.tsx`, holds per-field CRUD +
  `@dnd-kit` field reorder via `SortableFieldRow.tsx`, no publish action).
- `use-effective-form.ts` + `GenericConfiguredStep`/`DynamicField` already
  exist and are consumed only by `CarriedItemsStep`/`ConsentStep`
  (shared by both the public and staff wizards). `VisitorInfoStep`,
  `VisitDetailsStep`, `VehicleInfoStep` render fixed JSX with no dependency
  on the fetched effective form.
- `InvitationVehicle` has no `custom_field_values` column (deliberately not
  added in the original `form-builder` change — see its `tasks.md` §1.3);
  Vehicle Info's field *set* is still exactly `vehicleType`, `licensePlate`
  (locked), `make`/`model`, `color` (toggleable) — no genuinely new
  admin-authored Vehicle Info field has anywhere to persist its value yet.

## Goals / Non-Goals

**Goals:**
- Make locked step/field positions actually immutable (server-enforced, not
  just UI-suggested).
- Give admins a working step-reorder UI, consistent with the existing
  field-reorder UI's interaction pattern.
- Make every toggleable field's active/required state on Visitor Info, Visit
  Details, and Vehicle Info reactive on both wizards, matching what Carried
  Items/Consent Agreement already do.
- Make publish state and the publish action visible and reachable from the
  Field Editor page, and stop success messaging from implying an unpublished
  change is already live.

**Non-Goals:**
- No change to the draft/publish/cache architecture itself (Decisions 1 and
  6 of the original `form-builder` design) — it is already correct and
  symmetric between steps and fields; this change only makes its state
  visible from one more screen.
- No `InvitationVehicle.custom_field_values` (or equivalent) column, and no
  rendering path for a genuinely new admin-authored Vehicle Info field
  beyond `make`/`model`/`color`. That storage gap predates this change and
  is unrelated to the three reported bugs (all three are about *existing*
  fields/steps not reflecting configuration, not about a missing storage
  path for new field types on a specific step). Flagged here, not silently
  reintroduced as in-scope.
- No rendering support added for `file_upload`/`dynamic_table`/
  `signature_pad`/`rich_text_block` inside `DynamicField` — `CarriedItemsStep`/
  `ConsentStep` already show a "not supported inline yet" placeholder for
  those types; that is a pre-existing, separate type-coverage gap, not the
  publish-visibility or reactivity bug this change fixes.
- No draft-vs-published diff endpoint. "Has unpublished changes" is tracked
  as a simple client-side flag (see Decision 4), not a computed
  field-by-field diff against the last published snapshot.

## Decisions

### Decision 1: Lock guard compares sorted position, not raw `order_index` value
`reorder_steps`/`reorder_fields` already load `steps`/`fields` and can sort
them by their *current* `order_index` to get the current sequence. The
guard: zip the current sequence and the requested `ordered_ids` sequence by
position; for every position where the current item `is_locked`, the
requested item at that same position must have the same id. Any mismatch is
a 422, and nothing is written.

*Why compare positions, not raw index values*: `order_index` values can have
gaps after a delete (a soft-deleted or removed toggleable step doesn't
necessarily trigger a renumbering of survivors). Comparing by position in
the sorted sequence is robust to that — it directly encodes "first two and
last stay put" regardless of what integer values happen to be stored, and
requires no renumbering/backfill migration.

*Alternative considered*: only require locked siblings keep their relative
order to each other (allowing them to shift as a block if a step is
inserted/removed around them). Rejected — doesn't match the literal
requirement ("first two and last are fixed"), and is looser than what the
admin-facing behavior should guarantee: an admin should never be able to
observe Visitor Info anywhere but first, or Review & Confirm anywhere but
last, regardless of how many toggleable/custom steps exist in between.

*Alternative considered*: reject the whole reorder request only if it's
literally impossible to satisfy (e.g. more locked ids than available fixed
slots) rather than position-by-position. Rejected as unnecessary complexity
— the position-zip check is simpler, gives a precise 422 on any violation,
and the locked-id set only ever contains the three fixed steps (or, for
fields, whatever a step's seeded locked fields are), so no such edge case
exists in practice.

### Decision 2: Frontend step reorder scopes `@dnd-kit`'s `SortableContext` to the non-locked middle run only
Steps are always locked-first-two, then toggleable/custom, then
locked-last, by construction (`defaults.py` seeds them that way, and
"customize this branch" clones the same shape; nothing in this change or the
original one lets an admin insert a new step before Visitor Info or after
Review & Confirm). The Steps overview page therefore renders: two
non-draggable `StepCard`s, then a `SortableContext` wrapping only the
toggleable/custom steps (drag handle shown only on these, mirroring
`SortableFieldRow`'s existing pattern for fields), then one more
non-draggable `StepCard` for Review & Confirm. On drop, the handler submits
the full six(+)-id list to `POST /form-builder/steps/reorder` with the two
locked bookends unchanged and the middle run in its new order — satisfying
Decision 1's server-side guard by construction, not by coincidence.

*Why not a single `SortableContext` over all steps with per-item
`disabled`*: `@dnd-kit` supports disabling individual sortable items, but
scoping the context to only the reorderable subset is simpler to reason
about and reuses the exact component (`SortableFieldRow`-equivalent)
already proven for fields, rather than adding conditional drag-disable logic
to `StepCard`.

### Decision 3: Visitor Info/Visit Details/Vehicle Info become "effective-form-aware," not "config-driven-rendered"
Unlike Carried Items/Consent Agreement (whose field *set* is genuinely
dynamic and rendered through `DynamicField`/`GenericConfiguredStep`),
Visitor Info/Visit Details/Vehicle Info keep their existing fixed JSX layout
— their field set doesn't change, only whether each toggleable field is
shown/required does. Each of these three step components takes the same
`useEffectiveForm` result already fetched once per wizard (no new fetch) and
looks up its own toggleable fields by key to decide show/hide and
required/optional — the same lookup shape `requiredConsentKeys` already
uses for Consent Agreement, applied per-field instead of building a whole
dynamic list. A field's presence in the (already active-only) effective-form
snapshot *is* its active state — `form_builder/service.py::publish` already
excludes inactive fields from the snapshot entirely, so "field absent" and
"field inactive" are the same observation, matching how
`form_builder/validation.py::is_field_required` reads it server-side.

**Scope, revised during implementation**: only fields the backend actually
gates dynamically are made reactive here:
- Visitor Info: `id_proof_upload` (driving both the ID-proof-type dropdown
  and the ID-proof-upload file input — `invitations/service.py` derives one
  `id_proof_required` flag from `id_proof_upload` alone, `default=False`;
  there is no separate dynamic check for `id_proof_type`) and
  `profile_photo` (`default=False`).
- Vehicle Info: `make_model`, `color` — already structurally optional in
  `VehicleSubmit` regardless of form-builder config (per the original
  `form-builder` change's task 1.3), so reactivity here is a pure
  visibility/labeling improvement with no backend-consistency risk either
  way.

**`expected_duration` (Visit Details) is explicitly excluded, discovered
during implementation, not at proposal time**: `VisitDetailsSubmit.expected_duration`
(`invitations/schemas.py`) is a plain required `str` with no default — it is
structurally mandatory regardless of the branch's form-builder
configuration, and unlike ID proof/photo, `invitations/service.py` never
calls `is_field_required` for it at all. The original `form-builder`
change's "known remaining gaps" note describing this field as
"stricter-than-necessary" was itself incorrect — deactivating "Expected
Duration" in form-builder today doesn't loosen the backend at all, so making
the frontend hide the field would create a strictly worse bug: a visitor
who never sees the field still has it rejected as missing at submission
time, with no field on screen to fix. Making `expected_duration` genuinely
optional end-to-end (relaxing the Pydantic schema, adding the dynamic
`is_field_required` call, a migration-free but behavior-changing backend
edit) is a distinct fix, out of scope here — flagged in Risks/Trade-offs
below rather than silently left half-done. `additional_notes` has no such
issue (`str | None = None` already) and is made reactive as planned.

*Why not swap these three steps to the generic `DynamicField` renderer*:
their fields aren't a caller-defined list — they're a fixed, typed set
mapped 1:1 to real `Invitation`/`InvitationVehicle` columns (per the
original design's Decision 4, storage stays hybrid). Swapping them to a
config-driven list would require either fabricating list entries for fixed
columns (indirection with no benefit) or partially special-casing the
generic renderer for typed fields — more invasive than the bug warrants.
Looking up each field's active/required state by key is the minimal change
that makes them reactive.

### Decision 4: "Unpublished changes" is a client-side, per-scope session flag, not a server diff
`useAdminFormBuilder`-family hooks (Steps overview and Field/Step Editor)
share one publish-state slice, keyed by the currently selected scope
(branch id or tenant default): set `hasUnpublishedChanges = true` after any
successful draft mutation (step/field create, update, delete, reorder) for
that scope; set it back to `false` after a successful publish for that
scope; initialize it to `false` on scope load. Both pages read this same
state (lifted to the shared Form Builder page/context both routes already
sit under) so the Field Editor page can show the same "Publish Changes"
action and an "Unpublished changes" banner the Steps overview page shows.

*Why not compute it from the server*: the backend has no draft-vs-published
diff endpoint, and building one (walking both trees and deep-comparing) is
meaningfully more work than the bug requires — a same-session dirty flag is
sufficient to stop the specific reported confusion ("I edited a field, saw
a success toast, and had no idea publishing was still needed"). A page
reload losing the flag and defaulting to "no unpublished changes shown" is
an acceptable trade-off: it's the same information an admin already had
before this fix (none), not a regression.

*Alternative considered*: always show the Publish button unconditionally on
both pages with no dirty-tracking at all (simplest possible fix — the Steps
overview page's existing button already works this way). Rejected as the
sole fix because it does nothing to address the "toasts imply the change is
already live" half of the bug — an always-visible button an admin doesn't
know to look for still leaves the misleading toast copy in place. The dirty
flag directly powers the corrective banner/copy; the button also being
reachable is necessary but not sufficient on its own.

### Decision 5: Toast copy update is the minimal fix for the "looks live" half of the bug
`use-admin-form-builder-step-editor.ts`'s existing toasts ("Field created.",
"Field properties saved.") gain a second sentence: "Publish to update the
visitor form." No new toast component or notification system — just copy,
paired with Decision 4's banner for anyone who dismisses the toast without
reading it.

## Risks / Trade-offs

- **Locked-position guard could reject a legitimate future admin action**
  (e.g. an intentional future feature letting an admin promote a custom step
  to run before Visit Details) → Not a concern today: nothing in the current
  or original design allows creating a new locked step or reordering
  relative to locked ones on purpose; if that changes, the guard's position
  is where to loosen it, called out explicitly in the spec delta rather than
  left implicit.
- **Client-side "unpublished changes" flag can be wrong across browser tabs
  or sessions** (admin A publishes from tab 1, tab 2 still thinks it's
  dirty, or vice versa) → Acceptable: same class of staleness the page
  already has for its listed steps/fields today (no live sync), and the
  worst case is a harmless false-positive "unpublished changes" banner, not
  a false negative that hides a real pending change.
- **Vehicle Info / new-field-type gaps remain open** (custom
  `custom_field_values` storage, `file_upload`/`dynamic_table`/
  `signature_pad`/`rich_text_block` rendering) → Explicitly out of scope
  (Non-Goals); flagged for the user rather than silently left implicit, per
  this project's existing convention for tracked-but-deferred items (e.g.
  `file-upload-handling.md` §4's malware-scanning item).
- **"Expected Duration" (Visit Details) still can't be safely deactivated** —
  discovered during implementation (Decision 3): `invitations/schemas.py`'s
  `VisitDetailsSubmit.expected_duration` is structurally required with no
  dynamic form-builder check at all, unlike ID proof/photo. Deactivating it
  in the admin Form Builder today has no effect on the backend and, had this
  change made the frontend hide it anyway, would have caused submissions to
  fail with no visible field to fix — worse than the status quo. Left
  unchanged in this fix; needs its own follow-up (relax the Pydantic field,
  add an `is_field_required(effective_form, "visit_details",
  "expected_duration", default=True)` call in `invitations/service.py`,
  mirroring the ID-proof/photo pattern) before the admin toggle for this
  specific field can be trusted end-to-end. `additional_notes` has no
  equivalent issue and is fixed as originally planned.

## Migration Plan

No database migration. Deploy order:
1. Backend: ship the `reorder_steps`/`reorder_fields` lock guard and its
   tests first — purely additive validation (rejects a previously-accepted
   but never-intentionally-used permutation; no existing correct workflow
   depends on reordering locked steps/fields).
2. Frontend: ship the step drag-and-drop UI, the three steps' effective-form
   reactivity, and the publish-visibility/toast changes together, since they
   share the same pages/hooks and are easiest to verify as one pass through
   the admin Form Builder + both wizards.
3. No backfill and no rollback complexity — every change is additive
   behavior or a stricter validation on an endpoint that had no legitimate
   caller relying on the looser behavior.
