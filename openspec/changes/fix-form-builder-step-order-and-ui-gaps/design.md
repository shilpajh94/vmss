## Context

See `proposal.md` for motivation and the investigation findings it
summarizes. Relevant current state this design builds on:

- `form_builder/service.py::create_step` (`:183-206`) computes
  `order_index = max(all existing steps' order_index) + 1` — unconditionally
  past every step, including the locked trailing run (Review & Confirm).
- `form_builder/service.py::_assert_locked_positions_unchanged` (added by
  `fix-form-builder-config-gaps`) compares by *position in the current
  sorted sequence*, not raw `order_index` value — it doesn't care about
  gaps, but it does implicitly assume that whatever position a locked step
  currently occupies is where it's supposed to be. It doesn't (and
  shouldn't) second-guess that; it's `create_step`'s job to never let a
  locked step's "supposed to be first-two/last" position become false in
  the first place.
- The only three `is_locked = true` steps are `visitor_info`, `visit_details`,
  `review_confirm` (`defaults.py`) — no endpoint anywhere lets an admin
  create a new locked step or change `is_locked` on an existing one. This
  fixed identity is what makes a deterministic repair possible: which step
  is "leading" vs. "trailing" locked is knowable from `key` alone, not just
  from position.
- `admin-form-builder.tsx::partitionSteps` (added by
  `fix-form-builder-config-gaps`) finds the locked leading/trailing runs by
  scanning for contiguous `isLocked` steps from each end — correct only if
  the invariant this change restores already holds.
- `RegistrationStepper.tsx` (staff wizard) is a single `flex` row,
  `whitespace-nowrap`, no wrap/scroll. `StepSidebar.tsx` (public wizard) is
  `flex-col` and has no equivalent problem.
- `FieldPropertiesPanel.tsx`'s `Active` toggle (`:108`) already exists and
  renders for any non-locked field, inside the same bordered box as
  "Validation Rules."

## Goals / Non-Goals

**Goals:**
- Make "locked steps occupy the first-two/last positions" an invariant
  every step-creating operation upholds, not just something reorder
  rejects after the fact.
- Repair any scope already in the corrupted state without losing or
  altering any step/field's actual configuration.
- Stop the admin UI from accepting an operation (creating a Visitor
  Info/Visit Details field) that has never had anywhere to take effect.
- Fix the two concrete UI-layout/discoverability issues reported
  (step-bar overflow, Active toggle placement).

**Non-Goals:**
- No support for admin-authored custom fields on Visitor Info/Visit
  Details (confirmed with the user — out of scope, would need new
  Invitation-side storage and a rendering-model change).
- No automatic deletion of the already-created orphaned field — flagged
  for the admin to remove themselves (Decision 4).
- No change to the draft/publish/reorder mechanics beyond what's needed to
  fix the ordering invariant — publish's snapshot logic, the Redis cache,
  and the locked-position reorder guard from `fix-form-builder-config-gaps`
  are already correct and untouched.

## Decisions

### Decision 1: `create_step` inserts before the locked trailing run, by renumbering
Load the scope's current steps sorted by `order_index`. Count the
contiguous run of `is_locked` steps at the tail (today, always exactly
`review_confirm`, but computed generically rather than hardcoded to one
key) to find the insertion index — one past the last non-locked step, or
equivalently immediately before that trailing run. Build the full ordered
id list with the new step inserted at that index, then assign
`order_index = position` across the whole list (the same renumbering
`reorder_steps` already does). This is one extra read + a handful of
in-place updates on create — negligible cost against a CRUD operation that
already round-trips to the database.

*Why renumber instead of a fractional/gap-based index*: `order_index` is a
plain integer with no gap-reservation scheme today, and reordering already
fully renumbers on every call — introducing fractional indices here would
be a second, inconsistent ordering strategy for no real benefit at this
scale (a scope has, realistically, a handful to a few dozen steps).

### Decision 2: Lazy, idempotent repair for already-corrupted scopes
A new `_ensure_step_order_valid(tenant_db, branch_id)` runs at the same
call sites `_ensure_scope_seeded` already does (`list_steps`, `create_step`,
`reorder_steps`, `publish`): load the scope's steps, and if any is_locked
step is not in its expected relative segment (leading: `visitor_info` then
`visit_details`, by key, in that order; trailing: `review_confirm`), correct
it. Correction: leading locked steps in their fixed key order, then every
non-locked step in its *current* relative order to each other (nothing
about a custom step's relative ordering to other custom steps changes),
then the trailing locked step(s) — renumbered the same way as Decision 1.
If the order is already valid, this is a no-op (one read, no writes) — safe
to call unconditionally on every scope access rather than requiring a
separate migration/ops script.

*Why fixed key order for locked steps, not "whatever relative order they're
currently in"*: the corrupted state might have locked steps in a
technically-still-sensible relative order (unlikely to be scrambled beyond
also being non-contiguous) or might not; keying off the known, fixed
identity of the three locked steps removes any ambiguity about what
"correct" means, rather than trying to infer intent from already-corrupted
data.

*Why lazy rather than a dedicated one-off script*: this codebase's existing
pattern (`_ensure_scope_seeded`) is exactly this shape — cheap idempotent
self-healing on access — and every code path that would need to run a
manual repair script already calls through `list_steps`/`create_step`/
`reorder_steps`/`publish`, so a separate ops script would just be a second
way to trigger the same logic for no added coverage.

### Decision 3: Reject new-field creation on Visitor Info/Visit Details by step key
`create_field` checks `step.key in {"visitor_info", "visit_details"}` before
doing anything else and rejects with 422 if so. This is a step-key check,
not a new column/flag — the "fully configurable vs. fixed" distinction is
already fully determined by which of the six canonical (or any custom)
step keys is involved; no new data model concept is needed.

*Why reject at creation only, not retroactively block editing the seeded
fields*: updating an *existing* seeded field on these two steps (toggling
active/required within what a toggleable field allows) is exactly what
these steps are supposed to support and is unaffected — only creating a
*new* field is being restricted.

### Decision 4: Flag, don't delete, the pre-existing orphaned field
The Field Editor's field list marks any field on Visitor Info/Visit Details
whose `key` isn't in that step's seeded set (a client-side check against a
small known-keys list mirroring `defaults.py`) with a plain "can't be shown
on the visitor form" note, leaving the existing delete control as the
admin's action to take. No backend deletion logic is added.

## Risks / Trade-offs

- **The lazy repair runs an extra read on every `list_steps`/`create_step`/
  `reorder_steps`/`publish` call** → Negligible: one already-in-hand list of
  a scope's steps (a handful to a few dozen rows), checked in memory; no
  extra query beyond what these functions already issue.
- **A scope's custom-step relative order could theoretically be considered
  "wrong" in some subjective sense once repaired** → Not a concern in
  practice: the repair never reorders custom steps relative to each other,
  only relative to the locked ones — an admin who created "test" before
  "test 2" still sees them in that order, just correctly positioned before
  Review & Confirm instead of after it.
- **Flagging (not deleting) the orphaned field leaves it in the draft
  indefinitely if the admin never notices the flag** → Acceptable: it's
  inert (never reaches the visitor form either way), and the flag is the
  same kind of passive information the UI already surfaces elsewhere (e.g.
  the "Inactive" badge on a deactivated field); deleting it silently would
  be the worse trade-off (see Non-Goals).

## Migration Plan

No database migration. Deploy order:
1. Backend: ship `create_step`'s fixed insertion point and the lazy repair
   together (the repair is what makes existing corrupted scopes safe
   immediately, without waiting for an admin to trigger it) — both are
   pure `order_index` renumbering, no other column touched.
2. Backend: ship the Visitor Info/Visit Details field-creation rejection.
3. Frontend: ship the add-field-button restriction, the orphaned-field
   flag, the step-bar scroll fallback, and the Active-toggle placement
   together — independent of each other, safe to land in one pass.
