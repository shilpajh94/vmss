## Why

An admin building a custom registration step today has no way to let a
visitor add multiple instances of the same set of fields — every
admin-authored field is a single flat answer per step
(`add-generic-custom-field-support`'s `customFieldValues` mechanism). This
already works for the two built-in entities: Vehicle Info's vehicles and
Visitor Info's co-visitors are each a hardcoded one-to-many table
(`InvitationVehicle`/`InvitationVisitor`) with its own dedicated "add
another" UI. But that pattern isn't something an admin can create — it's
special-cased to exactly those two entities in code. On a group visit with
several visitors bringing several vehicles, or any other multi-instance
data an admin might want to capture (one entry per parcel, one entry per
pet, one entry per accompanying document), staff either can't capture it
per-instance at all or are forced to flatten several answers into one set
of fields, which is the exact "adding vehicle details one by one" failure
reported for the custom form. This change generalizes the existing
Vehicle/Visitor "add another" pattern into a **repeatable field group**
primitive any admin can define, on any step, through the Form Builder —
and rebuilds Vehicle Info and Visitor Info on top of the same primitive so
there's one mechanism instead of two hardcoded ones plus a gap.

A group also needs to be *conditionally shown*, not just repeated — e.g.
an admin building a step around a "Registration Type" toggle wants to show
one section only for one branch of that toggle. Today only a single
*field* can declare a `visibility_condition`; there is no way to show or
hide a whole cluster of fields together, or to have a hidden field's
`isRequired` flag correctly not block submission — a field currently
authored with both `isRequired` and a `visibility_condition` still blocks
submission when hidden, since nothing evaluates that condition against
the submitted values at submission time today (only at authoring time, to
reject a dangling reference or a cycle). This change adds the same
conditional-visibility mechanism to groups, and makes a hidden group's
fields skip required-field validation — closing that gap at the group
level (field-level runtime evaluation remains a separate, unaddressed
gap — see design.md).

## What Changes

- **New: field groups within a step.** A `FormStep` can now have zero or
  more named `FormFieldGroup`s; each of a step's fields either belongs to
  exactly one group or remains ungrouped (today's flat behavior, unchanged
  for steps that never use groups). Groups do not nest — one level only,
  a group's own fields are always step-level fields, never another group.
- **New: a group can be marked repeatable, with an admin-configurable
  instance range.** A repeatable group carries an optional minimum and
  maximum instance count (e.g. "at least 1, at most 5 vehicles"); a
  non-repeatable group behaves as exactly one implicit instance, matching
  today's flat-field behavior.
- **New: a group can declare conditional visibility, independently of
  repeatable.** A group may carry a `visibility_condition`
  (`{fieldKey, operator, value}`, the same shape a field already uses)
  referencing another field on the *same step*; the group (and every
  field inside it) renders only when that condition holds. A group can be
  conditional only, repeatable only, both, or neither (a plain
  always-visible section — today's only behavior). When a group's
  condition evaluates false against a submission's values, none of that
  group's fields are treated as required for that submission, regardless
  of their own `isRequired` flag.
- **Step Editor gains group authoring.** An admin can create a group,
  assign existing/new fields to it, toggle it repeatable with a min/max,
  and set a conditional-visibility rule — for any step, not only the two
  built-in ones.
- **Vehicle Info and Visitor Info are rebuilt on the generic mechanism.**
  Both become system-seeded, locked, repeatable groups on their respective
  steps instead of code paths special-cased in `form_builder/service.py`
  and `invitations/validation.py`. Their existing wire contract
  (`vehicles`/`visitors` arrays, one `customFieldValues` map per instance)
  and their dedicated storage tables are preserved — this is an internal
  consolidation of validation/config logic, not a breaking API change (see
  design.md for why the tables stay separate from the new generic one).
  Vehicle Info's group's instance range is admin-configurable, unchanged
  from the original version of this change. Visitor Info's group's
  instance count still isn't admin-editable — its upper bound now comes
  from the group's own `maxInstances`, seeded from the current value of
  `settings.invitation_max_group_visitors`, which this change retires as
  a separate enforcement path (see design.md for the operational
  trade-off this introduces). The seeded Visitor Info step itself is
  **not** restructured into multiple groups — see design.md's Non-Goals.
- **Custom repeatable groups get real submission and storage support.**
  A group an admin defines on any step (including brand-new custom steps)
  is submitted as an array of per-instance answer maps, validated against
  that group's fields and its min/max, and persisted so it round-trips
  through invitation detail/lookup the same way vehicles do today.
- **Visitor-facing wizard gains one shared repeatable-group block.** A
  single add/edit/remove-instance component replaces `VehicleInfoStep`'s
  bespoke implementation and `GenericConfiguredStep`'s flat-only rendering,
  reused everywhere a group (built-in or custom) appears.
- Publish (`FormConfigVersion` snapshot) carries group definitions, so the
  renderer and submission validation see the same structure the admin
  configured.

## Capabilities

### New Capabilities
(none — this extends the existing form-builder engine and its consumers)

### Modified Capabilities
- `form-builder`: adds field-group definition (grouping, repeatable
  toggle, min/max instance count, conditional visibility) as a
  configurable part of a step, on top of today's flat per-step field
  list.
- `invitations`: vehicle and co-visitor submission is validated against
  the branch's configured group min/max instead of the current hardcoded
  "zero or more, no limit"/settings-constant acceptance; any admin-defined
  repeatable group on another step is accepted as an array of per-instance
  answers and persisted, with a hidden group's fields skipped for
  required-field validation. Supersedes part of "Carried Items and
  Vehicles Are Optional Structured Declarations," and formalizes (as a
  spec requirement, replacing a previously-undocumented settings check)
  the group-registration visitor-count cap.
- `registrations`: walk-in registration's form-builder enforcement
  ("Walk-in Registration Enforces the Server-Resolved Branch's
  Form-Builder Configuration") gains the same group min/max validation,
  since it resolves the same effective form as employee-created
  invitations.

## Impact

- **Backend — form-builder**: `form_builder/models.py` (new
  `FormFieldGroup` table, including a `visibility_condition` JSONB column;
  `FormField.group_id` nullable FK), `schemas.py`, `service.py`,
  `validation.py`, `defaults.py` (seed Vehicle Info/Visitor Info as locked
  repeatable groups; seed Visitor Info's group `maxInstances` from
  `settings.invitation_max_group_visitors`), `repository.py`.
- **Backend — invitations/registrations**: `invitations/models.py` (new
  generic table for custom-group instances, e.g.
  `invitation_group_instances`; `InvitationVehicle`/`InvitationVisitor`
  unchanged in shape), `invitations/schemas.py`, `invitations/service.py`
  (removes the standalone `invitation_max_group_visitors` check),
  `invitations/validation.py` (group-visibility evaluation against
  submitted values), `registrations/service.py` (shared effective-form
  resolution path), `core/config.py` (deprecates
  `invitation_max_group_visitors` once the migration has captured its
  value).
- **Migrations**: `alembic_tenant/` revision(s) for the new table/columns
  (including the group `visibility_condition` column) and the Visitor
  Info group `maxInstances` backfill, applied to every tenant schema per
  `database-architecture.md` §5.
- **Frontend (`VMMS_WEB`)**: Step Editor admin UI (group authoring,
  min/max controls, a conditional-visibility rule picker reusing whatever
  UI already exists for a field's own `visibilityCondition`), a new
  shared repeatable-group wizard component, refactor of
  `VehicleInfoStep.tsx` and the co-visitor step onto it,
  `GenericConfiguredStep.tsx` gains group-aware rendering plus client-side
  evaluation of a group's visibility condition.
- **Docs**: `docs/features/form_builder.md`, `docs/features/invitations.md`
  updated per `project-rules.md`'s "New Features" documentation
  requirement.
