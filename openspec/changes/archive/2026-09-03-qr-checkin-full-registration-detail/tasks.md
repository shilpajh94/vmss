## 1. Response Schema

- [x] 1.1 Add to `InvitationQrCheckInOut` (`invitations/schemas.py`):
      `registration_type`, `source`, `visitor_category_id`,
      `preferred_visit_date`, `preferred_visit_time`, `expected_duration`,
      `additional_notes`, `carried_items`, `carried_items_description`,
      `visitors: list[InvitationVisitorOut]`,
      `vehicles: list[InvitationVehicleOut]` — matching
      `InvitationTrackingOut`'s existing field types exactly.

## 2. Data Fetch

- [x] 2.1 `service.py::check_in_by_qr_token`: replace
      `InvitationRepository(tenant_db).get(invitation_id)` with
      `.get_with_children(invitation_id)` so `.visitors`/`.vehicles`
      (both `lazy="raise"`) are eager-loaded before the response mapper
      touches them.

## 3. Response Mapping

- [x] 3.1 `router.py::_to_qr_check_in_out`: populate the new fields from
      the invitation, mapping `visitors`/`vehicles` the same way
      `_to_tracking_out` already does (`InvitationVisitorOut`/
      `InvitationVehicleOut` per row).

## 4. Tests

- [x] 4.1 Endpoint test: a `group` registration's QR check-in success
      response includes every co-visitor (not just the primary contact).
      (`test_qr_check_in_response_includes_group_co_visitors`)
- [x] 4.2 Endpoint test: an invitation with declared vehicles has them
      all present in the QR check-in success response.
      (`test_qr_check_in_response_includes_declared_vehicles`)
- [x] 4.3 Endpoint test: an `individual` registration's QR check-in
      response has an empty `visitors` list (not an error, not omitted).
      (`test_qr_check_in_individual_registration_has_empty_visitor_list`)
- [x] 4.4 No existing QR check-in test asserts an exact response key
      set (verified via grep) — nothing needed updating.

## 5. Documentation

- [x] 5.1 Update `docs/features/invitations.md`'s QR check-in section to
      list the expanded response fields.
