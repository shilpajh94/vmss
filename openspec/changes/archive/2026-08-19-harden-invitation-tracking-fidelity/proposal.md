## Why

The user asked to verify the already-delivered Pre-Registration
implementation against:

> API-09 · Pre-Registration · Create invitation (single or group), generate
> expiry-bound tracking ID
>
> API-10 · Pre-Registration · Public visitor self-registration endpoint
> (multi-step: contact, visitor list, visit info, items, vehicle, consent)

against two concrete JSON payloads (one `group`, one `individual`) and a
six-step Figma reference (Visitor Info → Visit Info → Carried Items →
Vehicle Info → Consent Agreement → Review & Confirm), with the instruction
to confirm the API follows that exact JSON shape and is proven by tests.

**This is already built, and matches almost exactly.** Field-by-field
comparison of the two supplied JSON payloads against
`SelfRegistrationSubmit`/`PrimaryContactSubmit`/`VisitorSubmit`/
`VisitDetailsSubmit`/`CarriedItemsSubmit`/`VehicleSubmit`/`ConsentsSubmit`
(`invitations/schemas.py`) found **every field name, nesting shape, and enum
value** (`registration_type`, `preferred_contact_method`, `id_proof_type`,
`carried_items.items` category codes, `vehicles[].vehicle_type` codes) is
already implemented — the wire format is camelCase per this codebase's
`CamelModel` convention (`fastapi-architecture.md` §3) rather than the
snake_case the user wrote by hand, which is a presentation difference, not a
contract difference. The multipart shape
(`primary_contact_id_proof_file` + `visitor_id_proof_files`, matched to
`payload.visitors` by order) matches the user's `<multipart part: ...>`
annotations exactly. In fact, the two example payloads supplied are close
enough to this feature's own existing test fixtures
(`invitations/tests.py::_individual_submission`/`_group_submission` — same
names: Priya Sharma, Alexander Pierce, Clara Oswald, Meera Krishnan; same
vehicle plates) that they read as a corroboration of the existing test data,
not a new contract.

**Audit result:**

| API | Requirement | Verdict |
|---|---|---|
| API-09 | Create invitation (single/group), expiry-bound tracking ID | **Compliant** — `POST /invitations` creates the minimal shell, generates a signed, time-boxed tracking token (`core/security.py::create_invitation_token`) and a human-readable `INV-XXXXXXXX` id, dispatches the link asynchronously, and is idempotency-key safe. |
| API-10 | Public multi-step self-registration | **Compliant** — every field in both supplied JSON payloads is accepted, validated (contact-method-aware reachability checks, registration-type/visitor-list consistency, group-size cap, real magic-byte file validation, not just extension/`Content-Type`), and persisted correctly — traced through `service.py::submit_self_registration` line by line against both payloads. |
| Cross-cutting | Test coverage for full field fidelity | **Gap** — the existing success tests (`test_self_register_individual_success`, `test_self_register_group_success_with_visitors_and_vehicles`) assert only visitor/vehicle *counts* and `carried_items`, not that `visit_details` (purpose, host, date, time, duration, department, notes), `carried_items_description`, or per-vehicle/per-visitor field detail actually round-trip correctly. A regression silently dropping one of these fields in `service.py` would pass every existing test today. |
| Cross-cutting | Tracking lookup completeness (API-12, but directly implicated by "does the API return what was submitted") | **Gap, confirmed by reading code, not inference** — `InvitationTrackingOut` (`GET /invitations/track?trackingId=`), whose own docstring calls it "Full detail," omits `expectedDuration`, `departmentToVisit`, `additionalNotes`, and `carriedItems`/`carriedItemsDescription` — all captured during self-registration (`service.py` assigns every one of them to the `Invitation` row) but never surfaced back to the visitor who submitted them. `docs/features/invitations.md` itself describes this endpoint as a "Full status/visit-summary lookup," which the current schema doesn't fully deliver on. |

## What Changes

- Add `expected_duration`, `department_to_visit`, `additional_notes`,
  `carried_items`, and `carried_items_description` to
  `InvitationTrackingOut` (`invitations/schemas.py`) and the corresponding
  mapping in `router.py::_to_tracking_out`, so a visitor looking up their
  own submission by tracking ID sees everything they submitted — closing
  the gap between the docstring's "full detail" claim and what the schema
  actually returns.
- Extend `_individual_submission()`/`_group_submission()`
  (`invitations/tests.py`) to include `additionalNotes` (both payloads) and
  full vehicle #2 detail (`makeModel`/`color`) in the group payload,
  matching the two JSON payloads the user supplied byte-for-byte — not a
  new fixture, closing the small gap between what these fixtures already
  cover and what the user handed over.
- Add field-level assertions to the two self-registration success tests
  (and the tracking-by-id test) confirming every `visit_details`,
  `carried_items`, per-vehicle, and per-visitor field submitted is both
  persisted correctly and visible through `GET /invitations/track`.
- **No changes** to `POST /invitations`, `POST /invitations/{token}/register`
  request handling, validation rules, or file-upload logic — all already
  correct.

## Capabilities

### New Capabilities
- `invitations`: baseline requirements for API-09/API-10 (and the tracking
  lookup's field-completeness requirement API-12 shares) — the
  `invitations` feature package has never had a baseline spec captured
  under `openspec/specs/` (its original build lives only in
  `openspec/changes/add-pre-registration/`, already archived), so this
  change establishes it — same reasoning as every other capability baseline
  established this session.

### Modified Capabilities
- None.

## Impact

- **Code**: `src/vmss_api/invitations/schemas.py` (`InvitationTrackingOut`
  gains 5 fields), `src/vmss_api/invitations/router.py`
  (`_to_tracking_out` populates them).
- **Tests**: `src/vmss_api/invitations/tests.py` — fixture additions plus
  new field-level assertions in 3 existing tests (no new test functions
  needed; the gap is assertion depth, not missing scenarios).
- **Docs**: no change needed to `docs/features/invitations.md` — its
  existing "Full status/visit-summary lookup" description becomes accurate
  once the schema is fixed, rather than needing correction.
- **No breaking changes**: purely additive response fields; existing
  clients reading a subset of `InvitationTrackingOut` are unaffected.
- **Out of scope**: the SMS gateway and approval-evaluation-engine gaps
  already flagged as open items in this feature's own docs are untouched.
