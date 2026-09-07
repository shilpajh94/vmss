## 1. Router

- [x] 1.1 In `src/vmss_api/invitations/router.py::create_invitation`, change
      `primary_contact_photo_file` from
      `Annotated[UploadFile | None, File(...)] = None` to
      `Annotated[UploadFile, File(...)]` (no default), matching
      `primary_contact_id_proof_file`'s existing declaration. Update its
      `description` to state the photo is now required. (Reordered ahead
      of `visitor_id_proof_files`/`visitor_photo_files` to keep every
      no-default parameter before the defaulted ones — Python's own
      parameter-ordering rule, not a FastAPI requirement.)
- [x] 1.2 Same change to `primary_contact_photo_file` in
      `src/vmss_api/registrations/router.py::create_walk_in_registration`.
- [x] 1.3 In both routers, changed the `primary_contact_photo_content`
      read to an unconditional read, matching how the ID-proof file is
      already read.

## 2. Service

- [x] 2.1 In `src/vmss_api/invitations/service.py::create_invitation`,
      changed `primary_contact_photo_content` from `bytes | None` to
      `bytes`.
- [x] 2.2 Made the primary-contact photo validate/store branch
      unconditional, mirroring the primary-contact ID-proof content's own
      unconditional validate/store lines immediately above it.
- [x] 2.3 `src/vmss_api/registrations/service.py` needed only a type-
      annotation fix (`bytes | None` → `bytes`, matching the now-always-
      bytes value it forwards) and a docstring update — no logic change,
      as expected.

## 3. Tests

- [x] 3.1 `POST /invitations` without a `primaryContactPhotoFile` part is
      rejected with a validation error; no invitation record is created
      (`test_create_invitation_without_primary_contact_photo_rejected`,
      replacing the old `test_create_invitation_without_photo_succeeds`
      which asserted the opposite, now-superseded behavior).
- [x] 3.2 `POST /invitations` with a valid `primaryContactPhotoFile` still
      succeeds — the shared `_create_invitation` test helper now always
      includes it, so every existing test built on that helper (the large
      majority of the suite) continues to exercise the success path
      correctly with no per-test change needed.
- [x] 3.3 `POST /invitations` for a `group` registration with the
      mandatory primary contact photo but no co-visitor photos still
      succeeds, with `photoUrl: null` for each co-visitor
      (`test_create_group_invitation_with_visitor_photos_returns_photo_urls`,
      already covered this and needed only the added primary contact photo
      part).
- [x] 3.4 Repeated 3.1-3.3 for `POST /registrations/walk-in`: the shared
      `_create_walk_in` helper now always includes the primary contact
      photo, and a new
      `test_walk_in_registration_without_primary_contact_photo_rejected`
      covers the rejection case.
- [x] 3.5 Disguised-content and oversized-upload rejection for the
      primary contact photo were already unconditionally-supplied cases
      on both endpoints (`test_create_invitation_disguised_photo_rejected`,
      `test_create_invitation_pdf_photo_rejected`,
      `test_create_invitation_oversized_photo_rejected`,
      `test_walk_in_registration_disguised_photo_rejected`) — unaffected,
      still pass.
- [x] 3.6 Audited every other test in `invitations/tests.py` and
      `registrations/tests.py` that built a creation/walk-in multipart
      request outside the shared helpers
      (`test_create_invitation_without_branch_header_or_payload_rejected`,
      `test_create_invitation_branch_id_in_payload_used_when_header_omitted`,
      `test_create_invitation_disguised_file_rejected`,
      `test_create_group_invitation_earlier_visitor_file_not_stored_when_later_invalid`,
      `test_walk_in_registration_disguised_file_rejected`) — added the
      primary contact photo part to each so the test's own point (not the
      now-unrelated missing-photo path) is what's actually being exercised.
      A full-suite run also caught two more caller groups outside these two
      test files that needed the same fix: `approvals/tests.py` (3 tests
      calling `invitations_service.create_invitation` directly with
      `primary_contact_photo_content=None`, now `_jpeg_bytes()`) and the
      root-level `tests/test_workflow_full_lifecycle.py` /
      `tests/test_workflow_visitor.py` end-to-end tests (built their own
      multipart `files=[...]` list with no photo part).
      Also fixed `test_create_invitation_oversized_file_read_is_bounded`,
      whose `read_sizes` assertion needed to account for the now-always-
      read primary contact photo file.

## 4. Documentation

- [x] 4.1 Updated `docs/features/invitations.md`'s `POST /invitations` row
      (added a **BREAKING** note) and renamed/rewrote its "Optional
      profile photo" section to "Primary contact profile photo" —
      mandatory for the primary contact, still optional for co-visitors.
      Updated the QR check-in response field description to match.
- [x] 4.2 Updated `docs/features/registrations.md`'s `POST /registrations
      /walk-in` row and its "Optional profile photo" section (renamed
      "Primary contact profile photo") to match.
- [x] 4.3 Added a note in `docs/features/invitations.md`'s "QR check-in"
      section clarifying that `.../check-in` and `.../check-out` cache
      per `Idempotency-Key` for 24h, so a client reusing one fixed key
      across multiple scans will see every call after the first replay
      that first response — not a bug in the check-in/check-out cycle
      itself.
