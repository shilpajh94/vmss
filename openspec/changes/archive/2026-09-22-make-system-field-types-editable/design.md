## Context

See proposal.md for motivation. Key facts confirmed by reading the code:

- `FormField.field_type` is a plain `String(30)` column
  (`form_builder/models.py`), so no Alembic migration is needed for any
  type reassignment covered here.
- Seeded system fields (`form_builder/defaults.py::DEFAULT_STEP_SPECS`),
  all `is_system=True`:

  | key | field_type | is_locked | is_required | wire representation |
  |---|---|---|---|---|
  | `registration_type` | toggle_switch | locked | required | `RegistrationType` enum, DB filter column |
  | `full_name` | text | locked | required | plain `String(255)` |
  | `email` | email | locked | not required | `EmailStr`, notification target |
  | `phone` | phone | locked | not required | `String(50)`, notification target |
  | `visitor_category` | dropdown_select | locked | required | catalog-driven options |
  | `preferred_contact_method` | toggle_switch | locked | required | `ContactMethod` enum, drives dispatch channel |
  | `id_proof_type` | dropdown_select | toggleable | required | plain `str`, already dynamically validated |
  | `id_proof_upload` | file_upload | toggleable | required | stored file reference |
  | `profile_photo` | file_upload | toggleable | required | stored file reference |
  | `purpose_of_visit` | text | locked | required | plain `String(255)` |
  | `host` | text | locked | not required | plain `str` |
  | `preferred_visit_date` | date_picker | locked | required | `date`, real DB `Date` column |
  | `preferred_visit_time` | time_picker | locked | required | `time`, real DB `Time` column |
  | `department_to_visit` | text | locked | not required | plain `str` |
  | `expected_duration` | text | toggleable | required | plain `str` |
  | `additional_notes` | textarea | toggleable | not required | plain `str` |
  | `vehicle_type` | dropdown_select | locked | required | plain `str`, already dynamically validated |
  | `license_plate` | text | locked | required | plain `str` |

- `email`/`phone` feed `_require_reachable_contact`/
  `_require_contact_for_method` (`invitations/schemas.py`) — at least one
  must be present, and whichever `preferred_contact_method` selects must
  be present — and are the literal address/number notification dispatch
  sends to.
- `registration_type` is a real `RegistrationType` enum on
  `InvitationCreate`, a `list_invitations` filter column
  (`invitations/repository.py`), and drives
  `_check_visitor_list_matches_registration_type`.
- `preferred_visit_date`/`preferred_visit_time` are the only two seeded
  system fields whose DB column is not `String` — they're real
  `Date`/`Time` columns, consumed as such by overstay detection and the
  emergency report (per `project-rules.md`'s directory map).
- `update_field` (`form_builder/service.py`, ~line 451) currently rejects
  any `field_type` change when `field_row.is_system` is true —
  unconditionally, regardless of `is_locked`. This is the one property
  where the backend, not just the frontend, currently enforces the
  restriction (contrast with label/placeholder/`help_text`/options, which
  the backend has never restricted for a locked field —
  `add-static-text-field-and-unlock-toggle`'s design doc already
  established that the "lock" for those is UI-only).
- `form_builder/validation.py::allowed_id_proof_types`/
  `allowed_vehicle_types` already read the effective form's configured
  `options` for those two keys and validate a submission against them —
  the pattern this change generalizes.

## Goals / Non-Goals

**Goals:**
- Let an admin change a retypeable system field's `field_type`, gated by
  the existing lock/unlock affordance for locked fields and directly
  editable for toggleable ones — matching how those fields' other
  properties already behave.
- Keep the exclusion list enforcement server-side (not just a frontend
  `disabled` attribute), since `field_type` is the one property the
  backend already actively enforces here.
- Make a retyped field's submitted value actually validated against its
  new type, not just rendered differently — closing the gap where
  `field_type` would otherwise be cosmetic for these keys.

**Non-Goals:**
- No change to the excluded fields' behavior at all — `email`, `phone`,
  `preferred_contact_method`, `registration_type`,
  `preferred_visit_date`, `preferred_visit_time`, `id_proof_upload`,
  `profile_photo`, `visitor_category` keep exactly today's fixed-type,
  fixed-validation behavior. Making any of these genuinely retypeable is
  a separate, materially larger redesign (moving them off typed DB
  columns/Pydantic types into generic storage, and updating every
  downstream consumer — `InvitationOut`, tracking/QR responses,
  notification templating, reports, overstay detection) and is
  explicitly out of scope here.
- No change to Required/Active editability for any system field — those
  stay exactly as fixed as they are today, unaffected by unlock state.
- No change to `id_proof_type`/`vehicle_type`'s existing dynamic-options
  validation mechanism itself — this change reuses and generalizes it,
  not replaces it.
- No new database migration — every field this change makes retypeable
  is already `String`-backed.

## Decisions

**1. The exclusion list is keyed by field `key`, not by any new column or
flag.**
`TYPE_LOCKED_SYSTEM_FIELD_KEYS` is a fixed constant (backend) mirrored by
an equivalent frontend constant, both enumerating the nine excluded keys
by name. Alternative considered: a new `FormField.type_locked: bool`
column, seeded true for the excluded keys. Rejected — the exclusion list
is not admin-configurable data (an admin should never be able to flip a
column to unlock `email`'s type without a code change, since doing so
would break notification dispatch); it's a fixed property of what these
specific keys mean to the rest of the system, so it belongs in code, the
same way `OPTION_REQUIRED_TYPES` and `CONTENT_ONLY_FIELD_TYPES` already
do for field-type semantics.

**2. Backend enforcement drops from "reject if `is_system`" to "reject
if `key` is in the exclusion list" — `is_locked` plays no role in backend
enforcement.**
Consistent with the existing pattern (Decision context above): the
backend has never enforced "locked" for the other three properties this
unlock toggle covers. Adding server-side unlock-state enforcement just
for `field_type` would be a new, inconsistent rule with no corresponding
persisted state to check (unlock is client-side-only by design). The
frontend remains the only place "locked-and-not-yet-unlocked" is
enforced for `field_type`, exactly as it already is for label/
placeholder/`help_text`/options.

**3. Submission-time validation generalizes the existing
`allowed_id_proof_types` pattern into one field-key-driven helper rather
than one bespoke function per newly-retypeable field.**
`allowed_options_for_system_field(effective_form, field_key) -> list[str]
| None` (returns `None` when the field's current type isn't
option-bearing, meaning "validate as free text instead"; `[]` when the
field is absent from the branch's active config, meaning "nothing is
valid" — the same tri-state distinction `allowed_id_proof_types`/
`allowed_vehicle_types` now also need, since `id_proof_type`/
`vehicle_type` are themselves retypeable — their return type changed from
`set[str]` to `set[str] | None` accordingly). `invitations/service.py`
calls it once per retypeable field at submission time, except `host`:
`VisitDetailsSubmit.host_name_or_email` is always discarded by
`_resolve_visit_detail_ids` (role-based-invitation-workflow) before
persistence, so there is no value to validate — including it in the loop
would check a value that goes nowhere.
Alternative considered: extend `custom_field_values`' generic validation
path to also cover these system keys. Rejected — that path is deliberately
scoped to admin-authored (`is_system=False`) fields today
(`custom_fields_for_step` filters them out), and folding system fields
into it would mean teaching it about `_require_reachable_contact`-style
cross-field rules that don't apply to custom fields; a small, explicit
per-key validation call in `invitations/service.py` (where those other
system-field rules already live) is more consistent with the existing
code shape than growing the generic path's responsibility.

**4. A field's stored *value* is not touched, re-validated, or migrated
when its type changes.**
Changing "Purpose of Visit" from `text` to `dropdown_select` does not
retroactively alter or re-validate any already-submitted invitation's
`purpose_of_visit` value — exactly like changing a `dropdown_select`
field's `options` list today doesn't touch historical submissions that
used a since-removed option. This is forward-only, matching the existing
Form Builder edit model.

## Risks / Trade-offs

- **[Risk]** An admin could still misunderstand the boundary — e.g.
  expect "Host" (retypeable) and "Registration Type" (excluded) to behave
  the same way since both look like ordinary system fields in the UI. →
  **Mitigation**: the field-specific explanatory text (spec's third
  requirement) states the concrete reason per excluded field rather than
  a generic message, and `docs/features/form_builder.md` documents the
  full exclusion list with rationale.
- **[Risk]** Generalizing `allowed_options_for_system_field` touches a
  code path (`invitations/service.py`'s submission validation) that's
  already dense with per-field rules (contact reachability, ID proof,
  consent). Adding seven more field-key checks in the same function
  risks the function becoming hard to follow. → **Mitigation**: implement
  as one loop over a `(field_key, submitted_value)` list rather than
  seven near-duplicate `if` blocks, matching how carried-items/consent-key
  validation already iterates a list rather than hardcoding each key.
- **[Trade-off]** Keeping the exclusion list in code (Decision 1) means a
  future genuinely-safe-to-retype field addition (e.g. if `host` gained a
  cross-cutting typed consumer later) requires a code change, not just
  data reseeding. Accepted — this is the same trade-off `OPTION_REQUIRED_
  TYPES`/`CONTENT_ONLY_FIELD_TYPES` already make, and the alternative
  (admin-configurable exclusion) risks an admin unlocking a field that
  isn't actually safe to retype.

## Migration Plan

No database migration. Deploy is a normal backend + frontend release:
backend change (loosened `update_field` gate + new dynamic validation)
can ship ahead of or alongside the frontend change (which only exposes
the now-permitted edits in the UI) without breaking either side — the
backend was already the more restrictive of the two, so shipping it first
is safe. No rollback concerns beyond a normal revert, since no stored data
shape changes.
