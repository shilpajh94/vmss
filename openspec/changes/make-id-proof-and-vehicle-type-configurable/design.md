## Context

See proposal.md for motivation. This was discovered through live
investigation (querying the dev database and the running frontend
bundle), not a code-review guess — confirmed facts that shape this design:

- `IdProofType`/`VehicleType` (`invitations/schemas.py`) are hardcoded
  `StrEnum`s used *only* as the Pydantic type of three request fields
  (`VisitorSubmit.id_proof_type`, `InvitationPrimaryContactCreate.id_proof_type`,
  `VehicleSubmit.vehicle_type`) — nothing else in the codebase references
  them (confirmed by grep). The underlying DB columns
  (`invitations/models.py`) are already plain `String`/`String | None` —
  the enum only exists at the Pydantic validation boundary.
- `CarriedItemsSubmit.items` already solves the identical problem for
  Carried Items: a plain `list[str]`, validated dynamically in
  `invitations/service.py::create_invitation` against
  `form_builder_validation.allowed_carried_item_keys(effective_form)`
  (itself just `_find_field(effective_form, "carried_items", "items")["options"]`).
  This change applies the exact same pattern to `id_proof_type`/
  `vehicle_type` — no new architecture, just two new
  `allowed_*` helpers and two new validation blocks shaped like the
  existing carried-items one.
- `form_builder/service.py::_requires_static_options` currently exempts
  *every* `is_system` field from needing non-empty `options`, with a
  docstring reasoning that applies specifically to `visitor_category`
  (whose real options come from the live `VisitorCategory` catalog) — not
  to `id_proof_type`/`vehicle_type`, which have no such external catalog
  and, after this change, *are* the source of truth for their own valid
  values.
- The frontend already has the exact prop-threading pattern needed:
  `VisitorInfoFieldState` (shared between the visitor and staff wizards'
  hooks, `use-visitor-request-wizard.ts`/`use-staff-visitor-registration-wizard.ts`)
  and `VehicleInfoStep.tsx`'s own `VehicleInfoFieldState` already carry
  branch-resolved `*Active`/`*Required` booleans for these steps' non-
  locked fields (`idProofActive`, `makeModelActive`, ...). Both wizards
  independently compute these via `useMemo` reading the resolved
  effective-form fields — extending each with an `Options: string[]` is
  the same shape of change, not a new mechanism.
- Confirmed (verified live, not guessed): `defaults.py`'s seeded `options`
  for `id_proof_type` (`["Aadhaar Card", "Passport", "Driving License",
  "Other"]`) and `vehicle_type` (`["2_wheeler", "4_wheeler", "heavy"]`)
  already exactly match the hardcoded enums and the frontend's hardcoded
  constants — so a tenant that has never customized either field sees
  *zero* behavior change after this ships.

## Goals / Non-Goals

**Goals:**
- Make the Form Builder options editor the actual, load-bearing source of
  truth for ID Proof Type and Vehicle Type choices, end to end (backend
  validation + both wizards' rendering).
- Reuse the carried-items/consent-keys validation pattern and the
  `*FieldState` prop-threading pattern already established in this
  codebase, rather than inventing new mechanisms.
- Preserve default (never-customized) behavior exactly.

**Non-Goals:**
- Visitor Category is untouched — its exemption from the options-required
  rule stays, and its catalog (a separate feature) is not part of this
  change.
- No change to how carried items or consent keys are already validated —
  those already work this way.
- No UI change to *how* an admin edits these two fields' options — the
  options editor (add/remove/reorder) already exists and already works for
  both (they're `dropdown_select`, not locked-for-options); this change
  only makes that editing *matter*.
- No data migration for existing invitations — their stored
  `idProofType`/`vehicleType` values are already plain strings that match
  the default option sets, so nothing needs backfilling.

## Decisions

**1. Loosen the Pydantic type to plain `str`, validate dynamically in the
service layer — don't invent a "configurable enum" abstraction.**
Matches `CarriedItemsSubmit.items`'s existing precedent exactly. An
alternative — a Pydantic validator that reads the DB at parse time — was
not seriously considered: schemas in this codebase are deliberately kept
free of DB access (`invitations/schemas.py`'s existing comments on
`items`/consent fields make this explicit), with dynamic checks living in
`service.py` after structural parsing succeeds.

**2. Two new `form_builder/validation.py` helpers,
`allowed_id_proof_types`/`allowed_vehicle_types`, each a one-line
`_find_field(...)["options"]` lookup — not a single generic
"allowed options for any field key" helper.**
Alternative considered: a generic `allowed_options_for(effective_form,
step_key, field_key)` used by all four call sites (carried items,
id proof type, vehicle type, and any future case). Rejected for this
change: `allowed_carried_item_keys` already exists with its own name and
docstring tying it to Carried Items specifically, and unifying it
retroactively is a refactor orthogonal to this change's goal — worth
proposing separately if a fourth case shows up, not bundled here.

**3. Narrow `_requires_static_options`'s exemption to a named field key
(`visitor_category`), not a blanket `is_system` check.**
The function's own docstring already only justifies the exemption for
`visitor_category`'s live-catalog case — the blanket `is_system` check was
simply broader than the stated reasoning, and this change corrects that
rather than adding a parallel, competing rule. Concretely:
`_EXTERNALLY_CATALOGED_FIELD_KEYS = frozenset({"visitor_category"})`, and
`_requires_static_options` checks `field_row.key not in
_EXTERNALLY_CATALOGED_FIELD_KEYS` instead of `not field_row.is_system`.

**4. Frontend: extend the existing `*FieldState` shapes with an `Options:
string[]` field; don't introduce a separate hook or context for this.**
Both `VisitorInfoFieldState` and `VehicleInfoFieldState` are already
computed once per wizard (via `useMemo` reading the resolved effective
form) and threaded down as a single prop — adding one more field to an
existing, already-plumbed shape is the smallest change that fits the
existing pattern. The two wizards' hooks each compute this independently
today (duplicated, not shared, for `vehicleInfoFields`) — this change
preserves that existing duplication rather than refactoring it into a
shared hook, since deduplicating it is a separate, pre-existing concern
unrelated to this proposal's goal.

**5. Display-only lookups (Review & Confirm, visitor detail tables) show
the raw stored string directly instead of mapping through a label table.**
Once `idProofType`/`vehicleType` are plain admin-configured strings (like
any other dropdown answer), there's no separate "value vs. display label"
distinction left to preserve — the option's value *is* its label (e.g.
"Aadhaar Card"), matching how every other admin-configured dropdown answer
already displays via `prettifyKey`/raw value elsewhere in the app.

## Risks / Trade-offs

- [Risk] **BREAKING for any client that hardcodes the old fixed value
  sets** (e.g. a mobile app, or a stale cached frontend build) — a request
  using an old value that an admin has since removed from the branch's
  configured options would now be rejected where it previously would have
  been the admin's problem to have kept the code in sync anyway. →
  Mitigation: default (unconfigured) branches keep the exact same accepted
  value set (Decision context above confirms an exact match), so this only
  bites a branch that has actually been customized — the intended,
  desired behavior change. Flagged in proposal.md as **BREAKING** per
  `api-conventions.md` §2's definition (tightens/changes validation
  semantics on an existing field) — since there is exactly one API version
  today and no external (non-VMMS_WEB) client is known to exist yet, per
  `project-rules.md`'s "Web portal is React, mobile is Flutter... separate
  repos", a v2 bump is not proposed here; flagged for the user to confirm
  this is acceptable given Flutter mobile's current state before shipping.
- [Risk] An admin empties "ID Proof Type"'s or "Vehicle Type"'s options
  without realizing publish will now reject it (new behavior, previously
  silently allowed since they were exempt). → Mitigation: this is the
  same "must declare a non-empty options list" rejection the admin UI
  already surfaces inline for every other option-bearing field
  (`fix-field-type-editing-and-lock-ux`'s "Clearing every option from an
  option-required field type is rejected" scenario) — no new UI needed,
  just no longer skipping the check for these two fields.
- [Risk] `vehicle_type` is `is_locked: true` in `defaults.py` (unlike
  `id_proof_type`, which is toggleable) — editing its options requires the
  admin to first select "Unlock to Edit" (per the prior lock/unlock
  change). → Mitigation: this is already-shipped, expected behavior for a
  locked field's options editor; no special-casing needed here.

## Migration Plan

No database migration (columns are already plain strings). Backend and
frontend should deploy together: deploying the backend's loosened
validation alone is safe (still accepts every value the old enums did,
plus whatever a branch has additionally configured); deploying the
frontend alone without the backend change would render live options from
Form Builder but have them rejected by the still-enum-validated backend —
so the backend validation change should land no later than the frontend
change, not after it.
