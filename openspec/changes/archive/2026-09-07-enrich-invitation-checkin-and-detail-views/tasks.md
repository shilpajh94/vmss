## 1. Permission Catalog

- [x] 1.1 Add `documents:view` to `PERMISSION_CODES` in
      `src/vmss_api/auth/rbac_catalog.py`.
- [x] 1.2 Add `documents:view` to the `reception` and `security` entries in
      `ROLE_PERMISSIONS`; leave `host` and `visitor` unchanged.
- [x] 1.3 Update `docs/features/auth.md` to list `documents:view` and note
      that existing tenants pick it up via the standard-roles resync
      endpoint.

## 2. Schemas

- [x] 2.1 Add `InvitationBranchOut`, `InvitationBuildingOut`,
      `InvitationDepartmentOut` (id, name, code — address/city additionally
      on branch) to `src/vmss_api/invitations/schemas.py`.
- [x] 2.2 Add a new `InvitationVisitorDetailOut` schema (same fields as
      `InvitationVisitorOut` plus `id_proof_url`), used exclusively by
      `InvitationDetailOut.visitors`. `InvitationVisitorOut` itself is left
      unchanged — it's also reused by `InvitationTrackingOut` and
      `InvitationCheckInOut`, which must never carry a document-URL field
      (design.md Decision 3 — corrected after discovering those two also
      shared the schema).
- [x] 2.3 Confirm `InvitationQrCheckInOut.visitors` keeps using the
      unmodified `InvitationVisitorOut` (no document-URL field at all).
- [x] 2.4 Add `primary_contact_id_proof_type: str | None`,
      `primary_contact_id_proof_url: str | None = None`, `branch:
      InvitationBranchOut`, `building: InvitationBuildingOut | None`,
      `department: InvitationDepartmentOut | None` to `InvitationDetailOut`
      (in addition to its existing raw `branch_id`, which stays unchanged;
      `visitors` field type changed to `list[InvitationVisitorDetailOut]`).
- [x] 2.5 Add `primary_contact_id_proof_type: str | None` (no `_url`
      counterpart), `branch: InvitationBranchOut`, `building:
      InvitationBuildingOut | None`, `department: InvitationDepartmentOut |
      None` to `InvitationQrCheckInOut`.
- [x] 2.6 Confirm `InvitationCheckInOut` (tracking-ID check-in) and
      `InvitationTrackingOut`/`InvitationTrackingSummaryOut` are untouched
      — out of scope per proposal.md.

## 3. Repository / Data Access

- [x] 3.1 Added `InvitationRepository.get_location(*, branch_id,
      department_id)` in `src/vmss_api/invitations/repository.py`: one
      query, `select(Branch, Department, Building).outerjoin(...)`,
      mirroring `auth/repository.py::list_employees_page`'s established
      cross-package join pattern (no new `relationship()` on `Invitation`).
- [x] 3.2 Same method resolves `Department` (via `department_id`),
      `Floor` (via `Department.floor_id`, join-only, not selected), and
      `Building` (via `Floor.building_id`) in that one query — returns
      `(Branch, Department | None, Building | None)`.
- [x] 3.3 Implemented as a small follow-up query (`service.py::
      get_invitation_location`), called once per request alongside the
      existing invitation fetch/transition — not one query per related
      entity, and not a per-row loop (`query-performance.md` §1/§2). The
      QR check-in/check-out transition methods
      (`check_in_by_qr_if_eligible`/`check_out_by_qr_if_eligible`) are
      unchanged; the router calls `get_invitation_location` on their
      `updated` result afterward.

## 4. Router

- [x] 4.1 Added `_resolve_document_url` in
      `src/vmss_api/invitations/router.py` mirroring `_resolve_photo_url`;
      only called from `_to_invitation_detail_out`/`_to_visitor_detail_outs`
      when `include_documents` is `True`.
- [x] 4.2 Added `_to_location_outs(branch, department, building)` helper
      building `InvitationBranchOut`/`InvitationBuildingOut | None`/
      `InvitationDepartmentOut | None`, shared by `_to_invitation_detail_out`
      and `_to_qr_check_in_out`.
- [x] 4.3 Updated `_to_invitation_detail_out` (now takes `branch`,
      `department`, `building`, `include_documents` as keyword args):
      resolves `primary_contact_id_proof_type`/`primary_contact_id_proof_url`
      (gated), `branch`/`building`/`department`; visitor list now built via
      new `_to_visitor_detail_outs(visitors, include_documents=...)`.
- [x] 4.4 Updated `_to_qr_check_in_out` (now takes `branch`, `department`,
      `building` as keyword args): resolves `primary_contact_id_proof_type`
      (no URL) and `branch`/`building`/`department`; visitor list
      unchanged (`_to_visitor_outs` → `InvitationVisitorOut`, no document
      field).
- [x] 4.5 In `get_invitation_detail`, added
      `user.has_permission("documents:view", invitation.branch_id)` (after
      the existing `invitations:view` check) and
      `service.get_invitation_location`, threaded into
      `_to_invitation_detail_out`. Both QR check-in/check-out endpoints
      call `service.get_invitation_location` and pass the result into
      `_to_qr_check_in_out`.

## 5. Tests

- [x] 5.1 Detail view (`GET /invitations/{id}`): caller with
      `invitations:view` + `documents:view` sees `idProofUrl` populated for
      primary contact and every visitor
      (`test_get_invitation_detail_includes_id_proof_url_with_documents_view`).
- [x] 5.2 Detail view: caller with `invitations:view` only (no
      `documents:view`) succeeds with `idProofUrl` `null` everywhere, all
      other new fields (branch/building/department, `idProofType`) still
      present (`test_get_invitation_detail_omits_id_proof_url_without_documents_view`).
- [x] 5.3 Detail view: branch is always present; building/department are
      populated when `departmentId` resolves through to a building, and
      `null` when `departmentId` is unset or its department has no
      `floorId` (three tests:
      `test_get_invitation_detail_includes_resolved_branch_detail`,
      `test_get_invitation_detail_includes_building_and_department_when_resolvable`,
      `test_get_invitation_detail_building_and_department_null_when_no_department_id`,
      `test_get_invitation_detail_building_null_when_department_has_no_floor`).
- [x] 5.4 QR check-in response: `idProofType` present for primary contact
      and every visitor; no `idProofUrl` field present anywhere in the
      response, asserting the *key* is absent, not just `null`
      (`test_qr_check_in_response_includes_id_proof_type_but_never_a_document_url`).
- [x] 5.5 QR check-in/check-out response: branch/building/department
      resolved the same way as the detail view
      (`test_qr_check_in_and_check_out_response_include_resolved_branch_building_department`).
- [x] 5.6 Permission-denied case: already covered by the existing
      `test_get_invitation_detail_denied_for_viewer_scoped_elsewhere` — 403
      before any new field is considered, unchanged.
- [x] 5.7 Tenant-isolation case: `InvitationRepository.get_location` run
      against a session bound to a different tenant schema resolves that
      schema's own `Branch` row, never the calling tenant's
      (`test_get_location_repository_tenant_schema_isolation`).
- [x] 5.8 Tracking-ID check-in (`InvitationCheckInOut`) and tracking
      lookup responses asserted unchanged
      (`test_public_check_in_response_omits_out_of_scope_new_fields`,
      `test_track_by_tracking_id_omits_out_of_scope_new_fields`).
- [x] 5.9 Standard-roles resync test: resyncing a pre-existing tenant's
      Reception/Security roles grants `documents:view`
      (`test_resync_role_permissions_backfills_documents_view` in
      `auth/tests.py`).

## 6. Documentation

- [x] 6.1 Updated `docs/features/invitations.md`: endpoint table rows for
      `GET /invitations/{id}` and both QR endpoints, plus a new "Resolved
      location and permission-gated ID-proof documents" section; also
      noted the `documents:view` gate in `docs/features/auth.md`.
- [x] 6.2 Extended `tests/test_api_documentation.py`'s camelCase/response-
      schema regression test with `InvitationBranchOut`,
      `InvitationVisitorDetailOut`, `InvitationDetailOut`, and
      `InvitationQrCheckInOut` entries (`api-documentation.md` §5).
