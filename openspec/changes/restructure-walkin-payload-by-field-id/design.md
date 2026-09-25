## Context

See `proposal.md` for motivation. Current state, precisely:

- `FormField`/`FormFieldGroup` already have a stable UUID `id` primary key
  (`form_builder/models.py`), but neither `FormFieldUpdate` nor
  `FormFieldGroupUpdate` (`form_builder/schemas.py`) exposes a way to rename
  `key` after creation — `key` is set once at creation and never mutated by
  the API today.
- The submission payload (`InvitationCreate` and its nested `VisitorSubmit`/
  `InvitationPrimaryContactCreate`/`VehicleSubmit`, `invitations/schemas.py`)
  captures admin-authored answers as `dict[str, Any]`/`dict[str, bool]`
  maps keyed by `FormField.key`/`FormFieldGroup.key`: `customFieldValues`
  (four places), `consents`, `groupValues`.
- `form_builder/validation.py` resolves every one of those maps back to a
  field/group definition by re-reading `field["key"]`/`group["key"]` out of
  the Redis-cached `FormConfigVersion.snapshot` (`resolve_effective_form`) —
  never by `id`, even though the snapshot's dicts already carry `id`
  (`FormFieldOut.id`/`FormFieldGroupOut.id`).
- `registrations` (`WalkInRegistrationCreate`) re-exports `InvitationCreate`
  directly and owns no schema of its own — it inherits this change with no
  separate schema work, only its own tests/docs.
- Storage is `JSONB` (`Invitation.custom_field_values`,
  `.primary_contact_custom_field_values`, `.consents`,
  `InvitationVisitor.custom_field_values`,
  `InvitationVehicle.custom_field_values`) — no column-type migration
  needed, only a data (key-string → id-string) backfill.
- Two changes that introduced parts of today's key-keyed behavior —
  `add-generic-custom-field-support` and `add-repeatable-field-groups` —
  are still open (unarchived): their own spec deltas, not the main
  `openspec/specs/invitations/spec.md`, are where "Invitation Creation
  Captures Admin-Defined Custom Field Answers" and "An Admin-Defined
  Repeatable Group's Answers Are Accepted as an Array of Per-Instance
  Values" currently live, even though their code has already shipped (per
  their own `tasks.md`). This change's spec deltas modify those
  not-yet-archived requirements directly (see Decisions).

## Goals / Non-Goals

**Goals:**
- Every admin-authored answer (custom field, consent, repeatable group) is
  joined to its live `FormField`/`FormFieldGroup` definition by `id`, at
  both submission time and in every response that echoes it back.
- One consistent EAV shape (`{fieldId, value}` / `{groupId, instances}`)
  across custom fields, consents, and groups — not three different
  key-keying conventions for what's structurally the same concept.
- Locked/system fields keep their existing named, hardcoded Pydantic
  fields untouched — this change only touches the admin-authored EAV
  surface.
- Existing tenant data remains readable after rollout (best-effort
  backfill), and a submission referencing a stale/foreign id fails the
  same "unknown field" way an unknown key does today — never a 500, never
  a silent no-op.

**Non-Goals:**
- Not re-architecting `FormField`/`FormFieldGroup` storage, the draft/
  publish lifecycle, or `resolve_effective_form`'s Redis-caching mechanism
  — this change only touches how a submitted/returned *value* is joined to
  a field definition, not how that definition itself is authored or
  published.
- Not making `key` renameable — that's a separate Form Builder admin-UX
  feature, out of scope here, and not this change's justification (see
  proposal.md's "Why" note that today's `key` already isn't renameable).
- Not touching `carriedItems.items`, `idProofType`, or `vehicleType` —
  these validate a field's own submitted *option value* against that one
  field's `options` list, not a reference to *another* field, so the
  key-vs-id join problem doesn't apply to them.
- Not changing the React portal / Flutter app — flagged as required
  follow-up work in a separate repo, not part of this change's tasks.

## Decisions

**Decision 1 — Wire shape: array of `{fieldId, value}` pairs, not a
dict keyed by id string.**
Considered keeping a dict shape (`dict[UUID, Any]` serialized as
`dict[str, Any]` with UUID-string keys) to minimize the diff. Rejected:
`api-documentation.md` §1/§5 requires every response schema to be a typed
`CamelModel` reachable through `response_model` for Swagger to render it
usefully — a dict with dynamic UUID-string keys renders in OpenAPI as an
opaque `additionalProperties` blob with no field-level shape, whereas an
array of `{fieldId, value}` objects is a proper typed list Swagger can
document per-property. This also matches the array shape already used
elsewhere in this payload for repeated structure (`visitors`, `vehicles`).

**Decision 2 — Groups referenced by `groupId`, not by group key, contrary
to the illustrative payload sketch that motivated this change.**
The sketch that prompted this change kept `groups` as a dict keyed by
group *name* (e.g. `"vehicles": [...]`) while switching only field
references to `fieldId`. This design applies the same id-referencing
principle to groups too, for consistency with Decision 1 and because
`FormFieldGroup.key` has exactly the same non-renameable-today status as
`FormField.key` — there's no principled reason to trust one string key and
not the other. `groups` becomes `list[{groupId: UUID, instances:
list[list[{fieldId, value}]]}]`.

**Decision 3 — Treat this change's invitations spec deltas as directly
modifying the not-yet-archived requirements from
`add-generic-custom-field-support`/`add-repeatable-field-groups`, rather
than waiting for those to archive first.**
Alternative considered: block this change until those two are archived,
so its own deltas cleanly `MODIFIED` main-spec text. Rejected as
unnecessary process overhead — their `tasks.md` already record the
underlying mechanism as shipped, so the main spec being behind is a
documentation lag, not a signal the behavior is still in flux. Practical
consequence for whoever runs `/opsx:archive`: archive
`add-generic-custom-field-support` and `add-repeatable-field-groups`
first (or in the same batch, in that order), then this change, so each
archive step's diff against the main spec lines up with what actually
changed. Archiving this change first, before those two, would leave the
main spec's "Invitation Creation Captures Admin-Defined Custom Field
Answers" requirement text unreconciled between two pending deltas.

**Decision 4 — Data migration is best-effort, not blocking.**
A tenant-schema Alembic migration (`alembic_tenant/versions/`) walks each
existing `Invitation`/`InvitationVisitor`/`InvitationVehicle` row's
key-keyed JSONB and rewrites it to id-keyed JSONB using the *current* live
`form_fields.key → id` mapping at migration time. A stored key with no
current live match (the field was deleted after that historical
submission) is left under its original key untouched, and the migration
logs how many such orphaned keys it left per tenant — an operator signal,
not a blocking failure — since there is no live field left to correctly
re-key it against, and dropping historical data silently would be worse
than leaving it queryable under its old key.

**Decision 5 — Unknown vs. cross-branch id both reject as "unknown",
with no distinct error code.**
A `fieldId`/`groupId` that's well-formed UUID syntax but belongs to
another branch/tenant's form is rejected identically to one that doesn't
exist anywhere — matching today's precedent for cross-tenant lookups
elsewhere in the system (`security-architecture.md`'s tenant trust
boundary) and avoiding leaking "that id exists, just not here" as a
distinguishable signal to an unauthenticated walk-in caller.

## Risks / Trade-offs

- [Risk] Existing in-flight React/Flutter clients built against the
  key-keyed shape break the moment this ships to v1, with no dual-read
  transition window → Mitigation: this repo's own precedent already
  treats a nested-shape break as landing directly in v1 (the parent
  `form-builder` change did the same for carried-item/vehicle/consent
  shapes); coordinate the client-side update as a paired deploy, not a
  staged rollout, and call this out explicitly to both client teams before
  merging (proposal.md Impact).
- [Risk] The backfill migration runs per tenant
  (`database-architecture.md` §5) — a tenant not yet migrated at the
  moment new code deploys would have old rows unreadable in the new shape
  until its migration runs → Mitigation: apply the tenant migration as
  part of the same deploy step that ships the code change, the same
  sequencing every other tenant-schema migration already follows.
- [Risk] Sequencing this change's archive against the two still-open
  predecessor changes (Decision 3) is a manual step a future archiver
  could get wrong → Mitigation: called out explicitly here and should be
  restated in this change's own `tasks.md` as a pre-archive checklist item.
- [Trade-off] Array-of-pairs (Decision 1) is more verbose on the wire than
  a dict for a caller with many custom fields → accepted, since Swagger
  documentability (`api-documentation.md`) is the stronger constraint for
  this codebase, and payload sizes here (tens of fields at most,
  `max_length` capped) are small enough that verbosity has no real cost.
