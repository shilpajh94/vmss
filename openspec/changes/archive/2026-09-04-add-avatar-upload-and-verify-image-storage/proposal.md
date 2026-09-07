## Why

The test release requires that every image/file upload (profile picture,
invitation/visitor photos, ID-proof scans, badges, QR check-in images) not
only saves and persists a storage reference in the database, but that the
reference returned on list/detail responses is genuinely usable by the
frontend to render an image — not merely a non-null string. A grounded audit
(file:line evidence, see `design.md`) found this is not true today:

- `core/storage.py::url_for()` returns a **raw server filesystem path** in
  the default `local` backend (`storage_backend = "local"`), not an
  HTTP-reachable URL. Every already-shipped `*PhotoUrl`/`badgeUrl` response
  field in `invitations` is built directly from this value, so in local/dev
  — the default for a fresh checkout, and the environment this release will
  actually be tested in — a browser cannot render any of these images. The
  bug is silent: the existing test suite only asserts the field `is not
  None`, and one test (`invitations/tests.py:4612`) even reads the value
  back as a local filesystem path, which is itself evidence the bug was
  never caught.
- The `avatar_url` column on `User` (`auth/models.py:93`) has **zero write
  paths anywhere in the codebase** — no upload endpoint, no admin-set field
  — and is missing from `UserOut` (so `GET /auth/me` can't surface it even
  if it were set) and from `EmployeeDirectoryOut` (unlike its sibling
  `EmployeeOut`). "Profile pic upload" as a working feature does not exist
  yet.
- Two smaller, concretely-cited gaps: invitation file uploads check size
  only after the full body is already buffered into memory, contrary to
  `file-upload-handling.md` §1; and the QR check-in image is written to
  storage once (`invitations/service.py:129`) but never read back by any
  endpoint — the visitor-facing QR image is actually regenerated from
  `qr_token` at send time (`invitations/tasks.py:85`), making the stored
  file dead weight.

Fixing these now, before the release, is what closes the gap between "the
field is present in the API response" and "the feature actually works for
the frontend."

## What Changes

- **Fix image/file URL resolution for the local storage backend** — add an
  authenticated download route (permission-checked the same way the
  underlying resource already is) that the local backend's resolved
  reference points to, so a `*PhotoUrl`/`badgeUrl` field is a real,
  browser-fetchable HTTP URL in both `local` and `s3` modes. The S3 backend
  already does this correctly via presigned URLs; local needs to reach
  parity. Every existing response field built from `storage.url_for()`
  (`invitations`: primary contact photo, visitor photos, badge) is updated
  to the new resolution path — response field names and shapes stay the
  same, only what the string resolves to changes, so this is additive from
  the client's perspective (a previously-unusable value becomes usable, not
  a rename).
- **Add profile-picture (avatar) upload** — a new authenticated endpoint for
  a user to upload their own avatar, validated through the same
  `storage.validate_upload`/magic-byte/size-limit pattern already
  established in `invitations/service.py`. `avatar_url` is added to
  `UserOut` (currently missing) so `GET /auth/me` returns it, and
  `EmployeeDirectoryOut` is aligned with `EmployeeOut` to include it too.
- **Close the pre-buffer size-check gap** in `invitations/router.py`'s
  upload handling (`file-upload-handling.md` §1) — reject an oversized file
  before its full content is read into memory, not after.
- **QR check-in image dead-storage-write — investigated, not closed this
  release**: confirmed the persisted QR image is never read back (the
  visitor-facing image is independently regenerated from `qr_token` for
  email). Closing it turned out to require a schema migration
  (`InvitationQRCode.image_storage_key` is `NOT NULL`, not nullable as
  first assumed) — deferred to a follow-up change that can do the column
  migration and the write removal together, rather than adding
  release-day migration risk for a purely cosmetic cleanup. See
  `design.md` Decision 4.
- **Decide and document the ID-proof URL exposure question** — confirm
  whether omitting `id_proof_url`/`primaryContactIdProofUrl` from every
  response is a deliberate PII-minimization decision consistent with
  `security-architecture.md` §4 ("access to raw document images is itself a
  permission"), and if so document it explicitly rather than leaving it
  looking like an oversight; if a legitimate need exists, add a
  permission-gated download endpoint instead of exposing it inline.
- **Test coverage** — for every upload endpoint (existing invitations
  photo/ID-proof, and the new avatar endpoint): wrong-type, oversized, and
  disguised-extension rejection (extending the existing pattern already
  proven for invitations); and for at least one representative photo/badge
  field per feature, assert the returned URL is actually fetchable end to
  end (not just non-null), on both a list endpoint and a detail endpoint
  where both exist.
- **Explicitly out of scope**: malware/content scanning remains the
  already-flagged, documented pre-production open item
  (`file-upload-handling.md` §4) — not touched by this change.

## Capabilities

### New Capabilities

None — every change extends an existing capability's contract; no new
top-level domain is introduced.

### Modified Capabilities

- `file-storage`: `url_for()`'s local-backend behavior changes from
  "resolves to a raw filesystem path" to "resolves to a client-fetchable
  HTTP URL," matching the S3 backend's existing contract.
- `auth`: adds a self-service avatar upload requirement and fixes
  `UserOut`/`EmployeeDirectoryOut` to actually surface `avatar_url`.
- `invitations`: fixes the pre-buffer size-check ordering, resolves the QR
  image dead-write, and documents/resolves the ID-proof URL exposure
  decision.

## Impact

- **Affected core files**: `core/storage.py` (URL resolution), a new
  authenticated download route (location decided in `design.md`).
- **Affected auth files**: `auth/router.py`, `auth/service.py`,
  `auth/schemas.py` (new avatar upload endpoint + `UserOut`/
  `EmployeeDirectoryOut` fields), `auth/tests.py`.
- **Affected invitations files**: `invitations/router.py` (buffer-order fix,
  QR image resolution), `invitations/service.py`, `invitations/schemas.py`
  (if the ID-proof decision adds a field/endpoint), `invitations/tests.py`.
- **No new dependencies.** No tenant-schema migration expected (avatar
  storage key reuses the existing `avatar_url` column) — confirmed in
  `design.md`.
- **No breaking changes**: every response field that changes meaning
  (photo/badge URLs) goes from non-functional to functional in local mode
  without changing its name, type, or presence — existing clients that
  already treat these as opaque strings are unaffected; only a client that
  was already trying to load one as an image starts working.
