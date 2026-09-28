## Context

See `proposal.md` - Why. Relevant current state:

- `FormStep`/`FormField` (`form_builder/models.py:14-96`) — a step owns a
  flat, ordered list of fields; there is no grouping construct. A
  `dynamic_table` value exists in the `FormFieldType` enum
  (`schemas.py`) but is an unimplemented stub (renders a "not supported
  inline yet" placeholder) — a single-field concept, unrelated to a
  multi-field repeatable container, and out of scope here.
- Vehicle Info's "add another vehicle" and Visitor Info's "add another
  co-visitor" are each hard-coded: a dedicated table
  (`InvitationVehicle`/`InvitationVisitor`, `invitations/models.py`),
  bespoke request/response array fields, and a bespoke frontend
  add/edit/remove component (`VehicleInfoStep.tsx`). Both tables carry
  more than form answers — `InvitationVisitor.id_proof_storage_key`/
  `photo_storage_key`/`checked_in_at` and `InvitationVehicle`'s typed
  columns are read directly by check-in, badge issuance, and audit code
  outside form-builder.
- `Invitation.custom_field_values` / `InvitationVisitor.custom_field_values`
  / `InvitationVehicle.custom_field_values` (JSONB, one flat map each) are
  today's only generic answer-storage mechanism
  (`add-generic-custom-field-support/design.md` Decisions 1 and 6 chose
  JSONB columns over a normalized answer table, since nothing queries
  answers across invitations).
- `GenericConfiguredStep.tsx` renders a custom step's fields as one flat
  list with no repeat affordance at all.
- A field's own `visibility_condition` (`_check_visibility_condition` in
  `form_builder/service.py`) is validated **only at authoring time** —
  same-step reference exists, no dangling reference, no cycle. Nothing in
  `invitations/service.py`/`form_builder/validation.py` evaluates a
  condition against a submission's actual values to decide whether that
  field's `isRequired` should apply. A field authored with both
  `isRequired: true` and a `visibility_condition` today still blocks
  submission when hidden — a pre-existing gap this change does not fix at
  the field level (see Non-Goals), but does fix at the group level, since
  the new requirement explicitly asks for it there.
- `settings.invitation_max_group_visitors` (`core/config.py`, default 20)
  is a bare settings constant, checked once in
  `invitations/service.py::create_invitation`
  (`if len(payload.visitors) > settings.invitation_max_group_visitors`).
  It has no corresponding spec requirement in `openspec/specs/invitations/
  spec.md` today — the cap exists in code but was never formalized.

## Goals / Non-Goals

**Goals:**
- One definition mechanism (`FormFieldGroup`) and one validation code path
  decide "does this group repeat, and how many instances are allowed" for
  Vehicle Info, Visitor Info, and any admin-authored group alike.
- A custom repeatable group's answers round-trip through invitation
  creation and detail the same way Vehicle Info's already do.
- A group can be shown/hidden based on another field's value on the same
  step, using the same `visibility_condition` shape a field already has.
- A hidden group's fields are never treated as required, regardless of
  their own `isRequired` flag, evaluated per-submission against that
  submission's own values.
- Migration is behavior-preserving: no existing branch's live form changes
  shape until an admin edits it (same posture as the original
  `form-builder` change), **except** the Visitor Info group-visitor-count
  cap's enforcement mechanism, which changes from a settings constant to
  the group's own `maxInstances` — deliberately, at the same numeric
  value, so no tenant's actual accepted range changes at migration time.

**Non-Goals:**
- Collapsing `InvitationVehicle`/`InvitationVisitor` into a generic
  instance table — see Decision 3.
- Changing Visitor Info's registration-type-driven cardinality *rule*
  (individual = 0 co-visitors, group = 1+) — untouched. What changes is
  only which mechanism enforces the *upper bound* on top of that rule
  (settings constant → group `maxInstances`) — see the revised Decision 5.
- Restructuring the seeded Visitor Info step into multiple groups
  (e.g. separate "Individual Fields"/"Primary Contact"/"Add Visitor"
  groups gated by `registrationType`). The request's own example
  illustrating conditional groups used this structure, but — confirmed
  with the user — it's illustrative of the general capability, not a
  mandate to reseed Visitor Info. The seeded Visitor Info step stays the
  single repeatable group it already is; conditional groups are available
  to an admin building a *custom* step, and to Visitor Info in a future
  change if that reseeding is ever actually requested.
- Nested groups (a group containing another group) — explicitly one
  level: a `FormFieldGroup` has no parent-group reference, matching the
  request's own "one level of nesting only."
- Runtime (submission-time) evaluation of a plain *field's* own
  `visibility_condition` to skip its required-check — the request asks
  for this only at the group level; extending it to bare fields too is a
  separate, reasonable follow-up but not asked for here (see Context).
- File-upload fields inside a *custom* repeatable group (Vehicle Info's
  and Visitor Info's own upload fields are unaffected). No product
  requirement asked for per-instance file uploads on a new custom group,
  and it would need its own order-matched multipart handling
  (`invitations/spec.md` "Every Visitor Has a Reachable Contact and a
  Validated ID Proof") designed separately.
- A query/reporting UI over group-instance answers — same posture as
  `add-generic-custom-field-support/design.md`'s JSONB non-goal.

## Decisions

### Decision 1: `FormFieldGroup` is a new table, not a JSON blob on `FormStep`
Add `form_field_groups` (`id`, `step_id` FK, `key`, `name`, `is_system`,
`is_locked`, `is_repeatable`, `min_instances`, `max_instances`,
`visibility_condition` JSONB, `order_index`) and a nullable
`FormField.group_id` FK. This mirrors how
`FormStep`/`FormField` are already modeled (one row per entity, not a
JSON array on the parent), so existing per-field CRUD, reordering, and
the branch/default-scope unique-index pattern
(`uq_form_field_step_key`-style) extend unchanged to groups instead of
requiring a parallel JSON-diffing code path.

**Alternative considered**: store `groups: list[{...}]` as a JSONB column
on `FormStep`. Rejected — every existing field operation (create, delete,
reorder, publish-time snapshotting) is row-based; a JSON-array sibling
would need its own optimistic-concurrency and validation handling instead
of reusing what's already there.

### Decision 2: Custom group-instance answers are a new JSONB column on `Invitation`, not a new table
Add `Invitation.group_field_values: dict[str, list[dict[str, Any]]]`
(JSONB, default `{}`) — keyed by group key, holding an ordered list of
per-instance answer maps — for any repeatable group other than Vehicle
Info/Visitor Info. This follows the same precedent
`add-generic-custom-field-support/design.md` Decision 1/6 already set for
every other answer bucket on `Invitation`: no requirement needs to query
"which invitations have group X, instance Y, field Z = value", so a JSONB
column keeps the read/round-trip path identical to
`custom_field_values`/`carried_items`/`consents` with no new join.

**Alternative considered**: a normalized `invitation_group_instances`
table (one row per instance, FK to `Invitation`, `group_key`,
`instance_index`, `values` JSONB). Rejected for the same reason a
normalized answer table was rejected before — no current query need, and
it reintroduces a join for something JSONB already handles.

### Decision 3: Vehicle Info and Visitor Info keep their existing dedicated tables — "unify" happens at the config/validation layer, not physical storage
`InvitationVehicle` and `InvitationVisitor` are not migrated onto
`group_field_values`. Both tables carry structurally-typed state beyond
form answers that other features read directly: order-matched ID-proof/
photo file storage keys and validation (`invitations/spec.md` "Every
Visitor Has a Reachable Contact and a Validated ID Proof", "Visitor and
Primary Contact Registration Optionally Captures a Profile Photo"),
per-visitor check-in/badge state, and audit-trail entity references.
Collapsing them into a generic JSONB-array column would force check-in,
badge issuance, and audit code to change for no product benefit the
request asked for — the failure being fixed is "an admin-authored group
can't repeat," not "Vehicle Info's storage is inconvenient."

What *does* unify (this is what closes the actual gap): `form_builder`
seeds Vehicle Info's and Visitor Info's existing fields under one
`FormFieldGroup` each (per the `form-builder` spec delta), and
`invitations/validation.py` gains a single
`validate_group_instance_count(group, submitted_count)` path that Vehicle
Info, Visitor Info, and every custom group call — replacing today's
hard-coded "accept any number of vehicles" check with a read of the same
`min_instances`/`max_instances` a custom group's submission is checked
against. One admin-facing authoring model, one server-side counting rule,
two storage tables for the two entities that structurally need them, one
new JSONB bucket for everything else.

**Deviation flagged for review**: this keeps Vehicle Info/Visitor Info's
tables where an earlier framing of this change ("retire their
special-cased tables") suggested removing them. That framing is not
carried forward for the reasons above — retiring the tables is a
disproportionate, cross-feature migration (check-in/badge/audit) with no
stated product benefit. If full physical unification is actually wanted
for a different reason (e.g. a future requirement to query across
vehicles and custom groups uniformly), that's a separate change with its
own justification.

### Decision 4: Request/response contract adds one optional map, doesn't touch existing ones
Invitation creation (and walk-in registration) accepts an optional
`groupValues: dict[str, list[dict[str, Any]]]` at the request's top level
for custom groups, alongside the existing `vehicles`/`visitors`/
`customFieldValues` fields, which are unchanged in shape. This is
additive per `api-conventions.md` §2 (new optional request field) — no
version bump needed. Each entry's field values are validated against that
group's field definitions using the same
type/required/`options`/`validationRules` machinery
`add-generic-custom-field-support/design.md` Decision 5 already
established; no new validation DSL.

### Decision 5 (revised): Visitor Info's group has no *admin-editable* instance range, but its `maxInstances` is now the single enforcement point for the upper bound
Visitor Info's seeded group is repeatable (so it renders through the same
shared frontend component as every other group) and does not expose
`min_instances`/`max_instances` to the admin via the Form Builder API —
cardinality's *lower* bound stays governed entirely by the existing
`registrationType` rule (`invitations/spec.md` "Visitor List Matches
Registration Type"), untouched by this change; running two independent
minimum rules against the same group (registration type *and* an
admin-set minimum) would let an admin configure a floor that contradicts
what registration type already guarantees, with no way to reconcile a
conflict.

The *upper* bound is different: today it's a separate, previously
undocumented mechanism — `settings.invitation_max_group_visitors`, a bare
config constant checked once in `create_invitation` (Context above). This
change retires that check and instead seeds the group's own
`max_instances` from that setting's current value at migration time
(Migration Plan), routing enforcement through the same
`validate_group_instance_count` path every other group (including Vehicle
Info's) already uses — "so there's only one place capping the count," per
the request. The admin still can't edit it through the Form Builder API
(same reasoning as the minimum), but the *code* no longer maintains two
parallel enforcement mechanisms for the same concern.

**Trade-off, flagged explicitly**: today an operator can change
`INVITATION_MAX_GROUP_VISITORS` via environment variable with no
deployment-time data migration. After this change, since the cap lives in
a per-scope database row instead of a process-wide setting, changing it
requires either a manual per-scope DB update or a future change that adds
an admin-facing (or ops-facing) path to edit it — there is no such path
in this change. Accepted per the request's explicit ask for a single
source of truth; revisit if that operational flexibility turns out to be
needed in practice.

**Alternative considered**: keep `settings.invitation_max_group_visitors`
as a fallback default used only when the group's `max_instances` is
`NULL`, so an operator retains env-var control until a branch's admin
(hypothetically) sets an explicit value. Rejected — the request asks for
retirement, not a fallback-of-a-fallback, and a silently-still-alive
settings value the admin can never see or edit through the product would
be a confusing hidden second source of truth, which is exactly what this
decision is meant to eliminate.

### Decision 6: One shared frontend component renders every group
A single repeatable-group component (add/edit/remove instance rows, one
row per instance, rendering that group's fields) replaces
`VehicleInfoStep.tsx`'s bespoke implementation and becomes what
`GenericConfiguredStep.tsx` and the co-visitor list step render for their
own groups — parameterized by field list, `isRepeatable`,
`min`/`maxInstances`, the current instance array, and `onChange`. Reuses
the existing `CustomFieldsSection`/`DynamicField` components per-instance
unchanged.

### Decision 7: A group's `visibility_condition` reuses the field-level shape and authoring checks, plus one group-specific guard
A `FormFieldGroup.visibility_condition` is the exact same
`{fieldKey, operator, value}` shape and column type `FormField.
visibility_condition` already uses, validated at authoring time with the
same "target field exists on the same step" check `_check_visibility_
condition` already performs for fields. No transitive-cycle walk is
needed for a group's condition the way one is for a field's: a field's
condition can chain through other fields' conditions (A watches B watches
C...), which is why that cycle-walk exists, but nothing can ever
reference a *group's* condition — the `fieldKey` operand only ever names
a field, never a group — so a group's condition can never be part of any
cycle. The one guard a group's condition does need, that a field's
doesn't: the watched field must not itself be a member of the group whose
condition it's on (a group-level self-reference — "show this group when
one of its own fields equals X" is circular in the same spirit as a field
referencing itself, since the field in question is only present/relevant
when the group is already shown).

**Alternative considered**: let a group's condition also reference
another *group* (e.g. "show Group B whenever Group A is visible").
Rejected — the request's condition shape only ever names a `fieldKey`,
and introducing a group-to-group reference would need its own cycle-walk
machinery mirroring the field-level one, for a capability nothing asked
for; an admin wanting that effect can already point both groups'
conditions at the same underlying field.

### Decision 8: A hidden group's fields skip required-field validation, evaluated at submission time against that submission's actual values — new evaluation logic, scoped to groups only
`invitations/validation.py` gains a function that, given a group's
`visibility_condition` and the values map the group's own step-scope
already validates against (Visit Details/Carried Items/a custom step's
`customFieldValues`, or a repeatable group's own per-instance value map),
evaluates whether the group is currently visible and, if not, excludes
every one of its fields from `validate_custom_field_values`'s
missing-required check for that submission — the field's own answer, if
supplied anyway, is still validated for type/options/length if present,
just not required.

This is genuinely new runtime evaluation, not an extension of something
that already existed: as Context notes, a plain field's own
`visibility_condition` is checked only at authoring time today, never
against submitted values. This change adds that evaluation capability at
the group level only, since that's what was asked for. A field's own,
independent `visibility_condition` (unrelated to any group) still isn't
evaluated at submission time after this change — flagged as a known,
intentionally out-of-scope gap (Non-Goals), not silently fixed as a side
effect.

**Alternative considered**: also fix field-level runtime evaluation in
this same change, since the gap sits right next to the new group-level
code. Rejected for scope discipline — the request didn't ask for it, and
bundling an unrelated-but-adjacent fix into this change makes it harder
to review and roll back independently. Worth a follow-up change if it
turns out to matter in practice (e.g. an admin reports a hidden,
`isRequired` field still blocking submission).

## Risks / Trade-offs

- **[Risk]** Already-published `FormConfigVersion` snapshots predate group
  definitions entirely. → **Mitigation**: submission validation treats a
  snapshot step with no group data as one implicit non-repeatable group
  per currently-ungrouped field (today's flat behavior) and, for Vehicle
  Info/Visitor Info specifically, as an unlimited repeatable group
  (today's actual behavior) — no tenant sees a behavior change until an
  admin edits and republishes, matching the original `form-builder`
  change's migration posture. **Implementation note**: the migration does
  *not* force a republish of every scope's snapshot (running the async
  `publish()` service from a raw-SQL Alembic migration isn't practical) —
  this fallback is the actual steady state for a pre-existing snapshot
  until its scope is next published, not merely a transient safety net.
- **[Risk]** A custom group with a high configured maximum and many fields
  could grow `group_field_values` large enough to matter for row size. →
  **Mitigation**: no index on the column (never queried by key, only
  round-tripped by invitation id), consistent with the same accepted risk
  on `custom_field_values`; revisit if a real size problem shows up.
- **[Risk]** Frontend Step Editor gains a new nesting level (groups within
  a step). → **Mitigation**: reuse the existing `@dnd-kit` reorder
  mechanism at the group level too rather than a new library.
- **[Risk]** Retiring `settings.invitation_max_group_visitors` removes an
  operator's ability to tune the group-visitor cap via environment
  variable without a data migration (Decision 5's trade-off). →
  **Mitigation**: none built into this change — accepted per the
  request's explicit "single source of truth" ask; a future change can
  add an ops-facing endpoint/script to edit a scope's Visitor Info group
  `maxInstances` directly if this turns out to matter.
- **[Risk]** A hidden group's fields skipping required-validation only at
  the group level (not for a bare field's own condition) could read as an
  inconsistency to an admin who doesn't know the distinction. →
  **Mitigation**: documented explicitly in `docs/features/form_builder.md`
  and flagged here (Non-Goals) rather than silently left undiscoverable.

## Migration Plan

1. `alembic_tenant` revision: create `form_field_groups` (including
   `visibility_condition` JSONB); add `form_fields.group_id` (nullable FK,
   no default); add `invitations.group_field_values` (JSONB,
   `server_default='{}'`). Applied to every tenant schema per
   `database-architecture.md` §5.
2. Same revision, data backfill: for every existing branch (and the
   tenant default) that already has a Vehicle Info or Visitor Info step,
   create that step's seeded locked group row and set `group_id` on its
   existing fields — mirrors how the original `form-builder` migration
   seeded every existing branch's effective form from today's fixed
   fields (behavior-preserving, per `project_form_builder` decisions).
   The Visitor Info group's `max_instances` is set to the current value of
   `settings.invitation_max_group_visitors` (read at migration-run time,
   a plain Python constant — no DB dependency), so the numeric cap is
   identical immediately before and after this migration for every
   existing tenant.
3. No forced republish: an already-published scope's live snapshot keeps
   validating exactly as before (Risks section above) until an admin next
   publishes that scope, at which point the newly backfilled draft groups
   (step 2) are picked up automatically by the existing `publish()` code
   path — no separate migration step needed to make that happen.
4. No rollback data loss risk: `group_id`/`group_field_values` are
   additive/nullable; a rollback migration drops the new table/columns
   without touching existing field/step data.
