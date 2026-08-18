## Phase 1 — Core implementation, verified against the group-registration payload

Both `registration_type` values run through the same `InvitationCreate`
schema/service/route (design.md Decision 1), so there is one implementation,
not two. "Group first" means: build it once, and make the group JSON below
the payload every task in this phase is written and manually verified
against, since it's the superset shape (multiple visitors, multiple
vehicles, non-empty carried items) — an individual payload is just this
shape with `visitors: []`/`vehicles: []`.

Reference payload (multipart `payload` part; ID-proof files travel as
separate parts named `primary_contact.id_proof_file` and
`visitors[0].id_proof_file`, `visitors[1].id_proof_file`, ... matched by
index):
```json
{
  "registration_type": "group",
  "primary_contact": {
    "full_name": "Priya Sharma",
    "email": "priya.sharma@enterprise-ugo.co",
    "phone": "+91 98765 43210",
    "preferred_contact_method": "email",
    "id_proof_type": "Aadhaar Card"
  },
  "visitors": [
    {
      "full_name": "Alexander Pierce",
      "email": "alexander.p@enterprise-ugo.co",
      "phone": null,
      "id_proof_type": "Aadhaar Card"
    },
    {
      "full_name": "Clara Oswald",
      "email": null,
      "phone": "+1 (555) 014-0362",
      "id_proof_type": "Passport"
    }
  ],
  "visit_details": {
    "purpose_of_visit": "Business Meeting",
    "host_name_or_email": "Rahul Nair",
    "preferred_visit_date": "2026-08-15",
    "preferred_visit_time": "14:30",
    "expected_duration": "1-2 hours",
    "department_to_visit": "Engineering",
    "additional_notes": "Wheelchair access required for one visitor."
  },
  "carried_items": {
    "items": ["laptop_tablet", "mobile_phone"],
    "item_description": "2x company laptops, personal phones."
  },
  "vehicles": [
    {"vehicle_type": "4_wheeler", "license_plate": "KA-01-AB-1234", "make_model": "Honda City", "color": "White"},
    {"vehicle_type": "2_wheeler", "license_plate": "KA-05-CD-5678", "make_model": "Honda Activa", "color": "Black"}
  ],
  "consents": {
    "terms_accepted": true,
    "data_processing_accepted": true,
    "safety_guidelines_accepted": true
  }
}
```
(camelCase over the wire per `fastapi-architecture.md` §3 — the field names
above are the Python/snake_case side; the actual HTTP request uses
`registrationType`, `primaryContact`, `idProofType`, etc.)

### 1. Schemas (`invitations/schemas.py`)

- [x] 1.1 Extend `InvitationPrimaryContactCreate` with `id_proof_type: IdProofType`.
- [x] 1.2 Add `visitors: list[VisitorSubmit]`, `visit_details: VisitDetailsSubmit`,
      `carried_items: CarriedItemsSubmit`, `vehicles: list[VehicleSubmit]`, and
      `consents: ConsentsSubmit` to `InvitationCreate`, plus the
      individual/group visitor-count `model_validator` currently on
      `SelfRegistrationSubmit`.
- [x] 1.3 Delete `SelfRegistrationSubmit` and `PrimaryContactSubmit` (folded
      into `InvitationPrimaryContactCreate`/`InvitationCreate`); keep
      `VisitorSubmit`, `VisitDetailsSubmit`, `CarriedItemsSubmit`,
      `VehicleSubmit`, `ConsentsSubmit` as shared nested schemas.
- [x] 1.4 Delete `SelfRegistrationOut`.
- [x] 1.5 Remove `registration_link` from `InvitationOut`; add `submitted_at`
      so the creation response reflects the same completeness
      `InvitationTrackingOut` does.
- [x] 1.6 Sanity-check: `InvitationCreate.model_validate_json(...)` against the
      reference group payload above parses cleanly and rejects it if
      `visitors` is emptied out (group requires at least one). Verified via
      `test_create_group_invitation_success_with_visitors_and_vehicles` and
      `test_create_group_invitation_with_empty_visitor_list_rejected`.
- [x] 1.7 **Added, not in the original breakdown**: extend
      `InvitationTrackingOut` with `expected_duration`, `department_to_visit`,
      `additional_notes`, `carried_items`, `carried_items_description` — this
      change's own `specs/invitations/spec.md` ("Tracking Lookup by ID
      Returns Everything Captured at Creation") requires it, but no task in
      this file originally covered it (it was `harden-invitation-tracking-
      fidelity`'s job, which is still unapplied). Implemented here so this
      change's own spec is actually satisfied by its own tasks.

### 2. Service (`invitations/service.py`)

- [x] 2.1 Merge `submit_self_registration`'s validation (visitor/file count
      match, `invitation_max_group_visitors` limit), file validation/storage
      (`_validate_and_store`), and child-row construction
      (`InvitationVisitor`/`InvitationVehicle`) into `create_invitation`.
- [x] 2.2 Build the `Invitation` row with every field set and
      `status="submitted"`, `submitted_at=now` in one `INSERT` — no
      follow-up `UPDATE`. For the reference payload this means 2
      `InvitationVisitor` rows and 2 `InvitationVehicle` rows are created
      alongside it in the same transaction.
- [x] 2.3 Delete `submit_self_registration` and the now-unused
      `registration_type`-matches-invitation check it performed (nothing to
      compare against anymore — the type is set once, at creation).
- [x] 2.4 Replace the `tasks.send_invitation_link.delay(...)` call with
      `tasks.send_visit_confirmation.delay(...)`, passing `invitation_id` and
      `tenant.schema_name` only (no `registration_link`/`tracking_token` —
      the task loads the invitation and reads `tracking_id` itself, per
      design.md Decision 3).
- [x] 2.5 Remove the `create_invitation_token` import and the
      `registration_link` construction in `create_invitation`.

### 3. Router (`invitations/router.py`)

- [x] 3.1 Change `create_invitation`'s route to accept
      `Form(payload) + File(primary_contact_id_proof_file) + File(visitor_id_proof_files)`,
      matching `submit_self_registration`'s current parameter shape; parse
      `payload` via `InvitationCreate.model_validate_json`.
- [x] 3.2 Move `_SELF_REGISTRATION_PAYLOAD_EXAMPLES` (renamed
      `_INVITATION_PAYLOAD_EXAMPLES`) onto the `create_invitation` route's
      `openapi_extra`; both individual and group examples included from the
      start (implemented as one pass rather than phase-gated).
- [x] 3.3 Delete the `submit_self_registration` route entirely, along with
      its now-unused `SelfRegistrationOut`/`SelfRegistrationSubmit` imports.
- [x] 3.4 Delete the `get_invitation_claims`/`get_invitation_tenant`/
      `get_invitation_tenant_db` imports (dependency functions themselves are
      removed in section 5).
- [x] 3.5 Update `_to_invitation_out` to stop passing `registration_link` and
      to pass `submitted_at`.
- [x] 3.6 Keep the existing `Idempotency-Key` handling on `create_invitation`
      unchanged (still keyed by `(tenant_id, idempotency_key)`).

### 4. Background tasks (`invitations/tasks.py`)

- [x] 4.1 Delete `send_invitation_link`/`_send_invitation_link`.
- [x] 4.2 Rename `send_registration_confirmation`/
      `_send_registration_confirmation` to `send_visit_confirmation`/
      `_send_visit_confirmation`; change its signature to take
      `invitation_id`/`tenant_schema` only (drop `tracking_token`) and
      generate the QR from `invitation.tracking_id` loaded inside the task.
- [x] 4.3 Update the task's idempotency guard: skip if the invitation is
      missing (redelivery after the row was somehow removed). Chose "accept
      at-least-once notification" (design.md's second option) over adding a
      new `notified` column — there's no cheap existing signal to guard on
      beyond invitation existence, and creation enqueues this task exactly
      once per request, already bounded by the idempotency-key cache.

### 5. Security & deps cleanup

- [x] 5.1 Delete `create_invitation_token`/`decode_invitation_token` from
      `core/security.py`.
- [x] 5.2 Delete `get_invitation_claims`, `get_invitation_tenant`,
      `get_invitation_tenant_db` from `invitations/deps.py`; keep
      `track_default_tenant_db` and its module docstring (trim the parts
      describing the two now-removed dependencies).
- [x] 5.3 Grepped the codebase for any other reference to
      `create_invitation_token`/`decode_invitation_token`/
      `get_invitation_claims`/`get_invitation_tenant`/`get_invitation_tenant_db`
      — none remained outside the files already updated.

### 6. Tests — group registration path (`invitations/tests.py`)

- [x] 6.1 Add the group happy-path test: POST the reference payload above as
      multipart (2 visitor ID-proof files + 1 primary-contact ID-proof file)
      and assert `201`, `status: submitted`, a tracking ID, and that both
      `InvitationVisitor` and both `InvitationVehicle` rows persisted with the
      right field values.
- [x] 6.2 Add group-specific validation tests: empty `visitors` list on a
      `group` request is rejected with 422; visitor-list length exceeding
      `invitation_max_group_visitors` is rejected with 422; visitor/file count
      mismatch (e.g. 2 visitors, 1 file) is rejected with 422.
- [x] 6.3 Add the `invitations:create` permission-denied test
      (`testing-standards.md` §2) using the group multipart request shape
      (parametrized alongside the individual shape — see 7.3).
- [x] 6.4 Add the tenant-isolation test (`testing-standards.md` §2) using the
      group multipart request shape (parametrized alongside the individual
      shape — see 7.3).
- [x] 6.5 Add an idempotency test: retrying `POST /invitations` with the same
      `Idempotency-Key` and the group multipart body creates exactly one
      invitation (one set of visitor/vehicle rows) and triggers exactly one
      `send_visit_confirmation` dispatch.
- [x] 6.6 Update `GET /invitations/track` tests for a group invitation to
      assert the tracking-by-ID response includes both visitors and both
      vehicles immediately after creation (no `pending` shell state to
      observe).
- [x] 6.7 Deleted the old API-09 minimal-shell test(s) and the API-10
      (`submit_self_registration`) group-path tests that exercised the
      now-removed route.

## Phase 2 — Individual registration path

Implemented in the same pass as Phase 1 rather than as a strictly separate
iteration, since both registration types share one schema/service/route and
splitting the work in time added no verification value here.

- [x] 7.1 Add the individual happy-path test: POST an individual payload
      (`visitors: []`, no co-visitor files, primary contact ID-proof file
      only) and assert `201`, `status: submitted`, a tracking ID, and that no
      `InvitationVisitor` rows were created.
- [x] 7.2 Add the individual-specific validation test: a non-empty `visitors`
      list on an `individual` request is rejected with 422.
- [x] 7.3 Parametrized the permission-denied and tenant-isolation tests
      (6.3/6.4) over both the individual and group payload shapes to confirm
      they're not accidentally group-specific.
- [x] 7.4 Update `GET /invitations/track` tests for an individual invitation
      (empty `visitors`/`vehicles` arrays, everything else populated).
- [x] 7.5 Both individual and group examples are present in `openapi_extra`
      (task 3.2) — verified by
      `tests/test_api_documentation.py::test_invitation_multipart_payload_examples_documented`.

## Phase 3 — Documentation and final verification

- [x] 8.1 Updated `docs/features/invitations.md`: describes the merged
      `POST /invitations` contract (multipart, full payload, both
      registration types), removed the API-10 section, and notes the removed
      JWT tracking-token mechanism per `api-documentation.md`.
- [x] 8.2 Confirmed `settings.invitation_registration_base_url` had no
      remaining references once the registration link was removed; deleted
      the setting and its `.env.example` entry.
- [x] 8.3 No factory/fixture built a minimal `InvitationCreate` *schema*
      payload (tests always went through the real API). Updated the unrelated
      but now-stale `InvitationFactory` (`factories.py`, a direct-DB-row
      SQLAlchemy factory, unused by any test) so its `status` default matches
      reality (`"submitted"`, not `"pending"`) instead of describing a shell
      state no code path produces anymore.
- [x] 8.4 `ddev exec uv run ruff check .` and `ddev exec uv run ruff format --check .`
      — both clean across the whole repo.
- [x] 8.5 `ddev exec uv run mypy src/vmss_api/core src/vmss_api/auth
      src/vmss_api/invitations` — clean, no issues found.
- [x] 8.6 `ddev exec uv run pytest` — full suite green, 174/174 passed
      (25 in `invitations/tests.py`), no regressions elsewhere.
