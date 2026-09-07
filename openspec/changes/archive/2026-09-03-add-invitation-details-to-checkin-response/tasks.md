## 1. Response Schema

- [x] 1.1 Add `InvitationCheckInOut` to `invitations/schemas.py`: every
      field `InvitationOut` has today (`id`, `tracking_id`,
      `registration_type`, `source`, `status`, `visitor_category_id`,
      `host_id`, `expires_at`, `submitted_at`, `approved_at`,
      `current_approval_step`) plus `primary_contact_full_name`,
      `purpose_of_visit`, `host_name_or_email`, `preferred_visit_date`,
      `preferred_visit_time`, `expected_duration`, `department_to_visit`,
      `additional_notes`, `carried_items`, `carried_items_description`,
      `visitors: list[InvitationVisitorOut]`,
      `vehicles: list[InvitationVehicleOut]` — matching
      `InvitationTrackingOut`'s existing field types exactly.

## 2. Data Fetch

- [x] 2.1 `router.py::check_in_invitation`: replace
      `service.get_invitation(tenant_db, invitation_id)` with
      `service.get_invitation_detail(tenant_db, invitation_id)` so
      `.visitors`/`.vehicles` (both `lazy="raise"`) are eager-loaded on the
      identity-mapped instance before `_perform_check_in`'s
      `UPDATE ... RETURNING` runs (design.md "Reuse
      `service.get_invitation_detail`").
- [x] 2.2 Update `service.get_invitation_detail`'s docstring to note it now
      backs two callers (`GET /invitations/{id}` and
      `PATCH /api/v1/invitations/{id}/check-in`), not just the first.

## 3. Response Mapping

- [x] 3.1 Add `_to_check_in_out(invitation, current_approval_step=None) ->
      InvitationCheckInOut` in `router.py`, populating fields the same way
      `_to_tracking_out` does (same source attributes, same
      `InvitationVisitorOut`/`InvitationVehicleOut` per-row mapping).
- [x] 3.2 `router.py::check_in_invitation`: switch its `response_model`
      from `Envelope[InvitationOut]` to `Envelope[InvitationCheckInOut]`
      and call `_to_check_in_out` instead of `to_invitation_out`.

## 4. Tests

- [x] 4.1 Endpoint test: a successful `PATCH /api/v1/invitations/{id}/
      check-in` response includes primary contact name, host display name,
      purpose of visit, department, preferred visit date/time, expected
      duration, additional notes, and carried items, alongside the
      already-present fields.
- [x] 4.2 Endpoint test: a `group` registration's check-in response
      includes every co-visitor, not just the primary contact.
- [x] 4.3 Endpoint test: an invitation with declared vehicles has them all
      present in the check-in response.
- [x] 4.4 Endpoint test: an `individual` registration's check-in response
      has an empty `visitors` list (not an error, not omitted).
- [x] 4.5 Endpoint test: the response does not include `branchId`,
      `createdByUserId`, badge fields, or watchlist-override fields.
- [x] 4.6 Endpoint test: a check-in rejected for wrong status (not
      `approved`) or an unresolved watchlist flag still returns the
      existing generic 409 with no visitor/host/visit detail leaked.
- [x] 4.7 Permission-denied case: a caller without `invitations:checkin` at
      the invitation's branch is rejected with 403 (existing behavior —
      confirm it's still covered, add if missing per
      `testing-standards.md` §2). Confirmed: already covered by
      `test_check_in_invitation_requires_permission`.
- [x] 4.8 Tenant-isolation case: confirm existing coverage that this
      endpoint's fetch cannot resolve an invitation belonging to another
      tenant's schema (existing behavior — confirm it's still covered, add
      if missing per `testing-standards.md` §2). Confirmed: already
      covered by `test_check_in_repository_tenant_schema_isolation`.

## 5. Documentation

- [x] 5.1 Update `docs/features/invitations.md`'s endpoint table row for
      `PATCH /api/v1/invitations/{id}/check-in` and the "Lifecycle actions"
      section to describe the expanded response. Endpoint table row
      updated with the new response shape; the "Lifecycle actions"
      section is state-machine-focused (status transitions, badge,
      watchlist) and doesn't describe any endpoint's response field set
      elsewhere, so it needed no change.
