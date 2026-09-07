## Why

The primary contact's profile photo is currently optional on both
`POST /invitations` and `POST /registrations/walk-in`, so a visit can be
created with only the ID-proof scan on file. For desk-side and gate
verification (matching the person in front of you to the person on
record), the ID proof alone is not enough — a live-captured profile photo
of the primary contact is needed on every visit, not just when the
creating caller happens to supply one.

## What Changes

- **BREAKING**: The primary contact's profile photo (`primaryContactPhotoFile`)
  becomes a **required** multipart file part on both `POST /invitations`
  and `POST /registrations/walk-in` — a request omitting it is rejected
  with a validation error and creates no invitation/registration record.
  Applied to the existing `v1` endpoints directly (not shipped as a new
  `v2` alongside a deprecated `v1`) — a deliberate, explicitly confirmed
  deviation from `api-conventions.md` §2's normal versioning guidance for
  a breaking change; existing callers (web portal, Flutter app, walk-in
  kiosk) must send a primary contact photo on their next deploy or every
  creation request will start failing.
- Co-visitor (`visitors[]`) profile photos remain optional and unchanged —
  this requirement is scoped to the primary contact only.
- Content validation (real image content check against the JPEG/PNG
  allow-list, max upload size) is unchanged — the primary contact's photo
  now goes through the same "required file" path the ID-proof file
  already does, not new validation logic.
- Not a code change, but closing the loop on a related question raised
  alongside this request: the QR check-in/check-out cycle
  (`PATCH /api/v2/invitations/qr/{token}/check-in` and `.../check-out`)
  already supports repeated check-in/check-out cycles for the same
  invitation today (verified against the existing passing test
  `test_qr_check_in_and_check_out_full_lifecycle`). The "second check-in
  doesn't register" symptom reported alongside this request was reproduced
  as a client sending the same `Idempotency-Key` on every attempt, which
  deliberately replays the first response for 24h
  (`api-conventions.md` §3) — a fresh key per physical scan is required
  client-side. This change adds a documentation clarification (task 6) but
  no spec or code change for check-in, since no behavior gap exists there.

## Capabilities

### Modified Capabilities
- `invitations`: "Visitor and Primary Contact Registration Optionally
  Captures a Profile Photo" is re-scoped — the primary contact's photo is
  now mandatory; co-visitor photos remain optional (requirement title kept
  unchanged; behavior updated).

## Impact

- `src/vmss_api/invitations/router.py` — `create_invitation`'s
  `primary_contact_photo_file` parameter loses its `| None` type and `=
  None` default, becoming required like `primary_contact_id_proof_file`.
- `src/vmss_api/registrations/router.py` — `create_walk_in_registration`'s
  identical parameter, same change (both endpoints share this exact
  multipart contract).
- `src/vmss_api/invitations/service.py` — the create-invitation function's
  `primary_contact_photo_content: bytes | None` parameter and its
  validate/store branch: validation becomes unconditional instead of
  "only if provided"; `registrations/service.py` passes through unchanged
  (it already just forwards to this function).
- `docs/features/invitations.md` / `docs/features/registrations.md` —
  updated to describe the now-mandatory photo, and a note on
  `Idempotency-Key` uniqueness per physical QR scan.
- No database migration: `primary_contact_photo_storage_key` was already
  a nullable column and stays nullable at the DB level (existing rows
  before this change may still have no photo) — only the API-layer
  validation tightens.
