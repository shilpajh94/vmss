## 1. Signed local-URL storage parity (design.md Decision 1)

- [x] 1.1 Add `settings.storage_local_url_secret` (falls back to
      `settings.secret_key` if unset) and
      `settings.storage_local_presigned_url_ttl_seconds` to
      `core/config.py`, and document both in `.env.example`.
- [x] 1.2 Add sign/verify helpers to `core/storage.py`: a function that
      builds `/files/local/{key-urlsafe}?exp=<ts>&sig=<hmac>` from a key,
      and a function that verifies the signature and expiry and returns
      the original key (or raises/`None` on tamper/expiry).
- [x] 1.3 Change `url_for()`'s local-backend branch (`core/storage.py:112-
      126`) to return the signed URL from 1.2 instead of the raw
      filesystem path.
- [x] 1.4 Create `core/storage_router.py` with `router = APIRouter(prefix
      ="/files", tags=["file-storage"])` and a `GET /files/local/{key}`
      route: verify the signature/expiry from 1.2, reject with 403/410 on
      failure, otherwise stream the content via the existing `storage.
      load()` with `Content-Type` set from the same magic-byte sniff
      `validate_upload` uses.
- [x] 1.5 Register the new router in `api.py` and add its tag to `main.py`
      `_TAGS_METADATA` (`api-documentation.md` §2).
- [x] 1.6 Add a test: save a file via the local backend, resolve it with
      `url_for()`, fetch the resulting URL through the new route with
      `httpx.AsyncClient`, and assert the returned bytes match what was
      saved.
- [x] 1.7 Add a test: a tampered signature and an expired `exp` are both
      rejected by the route without leaking file content.
- [x] 1.8 Add a test: with `storage_backend` set to `"s3"` (existing
      Moto/S3 test fixture), `url_for()` still returns the existing
      presigned-URL behavior unchanged — confirms no regression. (Already
      covered by the pre-existing `test_s3_backend_save_and_retrieve_
      round_trip`, untouched by this change's edits to the local branch;
      confirmed still passing in the final full-suite run.)

## 2. Photo/badge URLs are actually fetchable (invitations spec delta)

- [x] 2.1 Confirm every existing `url_for()`/`storage_url_for()` call site
      in `invitations/router.py` (primary contact photo, visitor photos,
      badge issue, badge reprint, QR check-in response) needs no call-site
      change — verify by re-reading each site listed in the audit
      (`router.py:287-301`, `:379-381`, `:424-426`, `:464-466`, `:511`,
      `:1108-1110`) against the new local-URL behavior from Task Group 1.
      Confirmed: every photo field routes through `_resolve_photo_url`
      (`:287-288`) and the badge through `_to_badge_out` (`:511`), both
      calling `storage_url_for` uniformly — no other call site exists.
- [x] 2.2 Update `invitations/tests.py:4612` (badge test that currently
      reads `badgeUrl` as a local filesystem `Path`) to instead fetch the
      URL over HTTP via the test client and assert the returned bytes are
      a valid PNG.
- [x] 2.3 Add one end-to-end fetch assertion for the primary-contact photo
      URL on `GET /invitations/{id}` (currently only asserted `is not
      None` per the audit) — fetch it and assert 200 + image content.
- [x] 2.4 Add one end-to-end fetch assertion for a visitor's `photoUrl` on
      the list endpoint response (`GET /invitations`) — fetch it and
      assert 200 + image content. Adapted: `InvitationListItemOut` has no
      per-visitor field at all (only `primaryContactPhotoUrl` — confirmed
      by re-reading `schemas.py`, design.md Decision 2 deliberately keeps
      list rows child-collection-free), so the fetch assertion was added
      to `primaryContactPhotoUrl` instead, the actual photo field the list
      endpoint exposes.
- [x] 2.5 Run `invitations/tests.py` in full, confirm all pass.

## 3. Profile picture (avatar) upload (design.md Decision 2)

- [x] 3.1 Add `settings.avatar_max_upload_size_bytes` (default 2 MiB) to
      `core/config.py`, documented in `.env.example`.
- [x] 3.2 Add `POST /auth/me/avatar` to `auth/router.py`: authenticated via
      `get_current_user`, accepts a single `UploadFile`, bounded-read per
      Task Group 4, validates via `storage.validate_upload` against the
      JPEG/PNG allow-list and the new size limit.
- [x] 3.3 Add the service-layer call in `auth/service.py` that saves the
      validated bytes via `storage.save(...)` and writes the resulting key
      into `User.avatar_url` (per `auth/repository.py`'s existing update
      pattern) in one commit.
- [x] 3.4 Add `avatar_url` to `UserOut` (`auth/schemas.py`) and populate it
      in `_to_user_out` (`auth/router.py`) by resolving the stored key
      through `storage.url_for()` — mirroring how `invitations` resolves
      `photo_storage_key` to `photo_url`. (`_to_user_out`/`_to_employee_out`/
      `_to_employee_directory_out` all became `async def` to do this.)
- [x] 3.5 Add `avatar_url` to `EmployeeDirectoryOut` (`auth/schemas.py`)
      and populate it in `_to_employee_directory_out`
      (`auth/router.py:329-337`), aligning it with `EmployeeOut`.
- [x] 3.6 Add `response_model=Envelope[...]` for the new route per
      `api-documentation.md` §1.
- [x] 3.7 Add tests to `auth/tests.py`: valid avatar upload succeeds and
      `GET /auth/me` returns a fetchable URL for it; a disguised/wrong-type
      file is rejected and the existing avatar (if any) is unchanged; an
      oversized file is rejected before full buffering; uploading a second
      valid avatar replaces the first (old URL no longer returned); a user
      with no avatar returns a null/absent field with no error; the
      employee directory listing surfaces the same avatar URL as the
      internal employee listing for the same user. Found and fixed along
      the way: `factories.py::UserFactory` never excluded `avatar_url` from
      polyfactory's random-value generation (unlike its sibling optional
      String columns `employee_code`/`designation`/`phone_number`), so a
      fixture-built user could randomly get a bogus non-null `avatar_url`
      now that it's actually surfaced in responses — added `avatar_url =
      None` to the factory, same fix pattern already used for the others.
- [x] 3.8 Add a permission-denied/tenant-isolation check consistent with
      `testing-standards.md` §2: an unauthenticated request to `POST
      /auth/me/avatar` is rejected with 401.
- [x] 3.9 Run `auth/tests.py` in full, confirm all pass. (98 passed.)

## 4. Pre-buffer size check (design.md Decision 3)

- [x] 4.1 Replace `content = await file.read()` with `content = await
      file.read(max_size_bytes + 1)` at each of the four read sites in
      `invitations/router.py` (`:638-643`), rejecting immediately (without
      further reads) when `len(content) > max_size_bytes`.
- [x] 4.2 Apply the same bounded-read pattern to the new avatar upload
      route from Task Group 3.
- [x] 4.3 Confirm the existing oversized-file tests
      (`test_create_invitation_oversized_file_rejected`,
      `test_create_invitation_oversized_photo_rejected`) still pass
      unchanged — they assert rejection, not the internals of how the
      rejection is detected. (Both pass, along with the disguised-content
      tests, 5/5.)
- [x] 4.4 Add a test that an oversized upload substantially larger than
      the limit does not have its full content buffered — e.g. assert
      rejection happens without reading past `max_size_bytes + 1` bytes
      (a large generated payload with a spy/counted stream, or an
      equivalent assertion available in the test harness). Implemented by
      spying on `UploadFile.read` and asserting the size argument passed.
      Found along the way: the spy must patch
      `starlette.datastructures.UploadFile` — Starlette's own multipart
      parser instantiates that base class directly, never
      `fastapi.UploadFile` (a subclass that's never actually constructed
      at request-parsing time), so patching the FastAPI-imported class
      silently intercepts nothing.

## 5. QR image dead-write removal (design.md Decision 4) — REVERTED

- [x] 5.1 ~~Remove the `storage.save(...)` call for the rendered QR PNG~~ —
      reverted: `InvitationQRCode.image_storage_key` (`invitations/
      models.py:219`) is `Mapped[str]`, **not nullable**. Removing the
      write would violate the `NOT NULL` constraint without a migration,
      which contradicts this change's own no-migration scope. Left the
      existing write unchanged; see `design.md` Decision 4 and
      `proposal.md`'s updated bullet. Deferred to a follow-up change.
- [x] 5.2 N/A — no write behavior changed, so no test needed updating.
- [x] 5.3 N/A — QR-in-email flow untouched; already covered by the
      pre-existing, unmodified Mailpit-based QR delivery tests.

## 6. ID-proof exposure decision documented (design.md Decision 5)

- [x] 6.1 Add a code comment at
      `primary_contact_id_proof_storage_key` (`invitations/models.py:83`)
      and `id_proof_storage_key` (`invitations/models.py:195`) stating the
      deliberate non-exposure decision and citing
      `security-architecture.md` §4.
- [x] 6.2 Confirm (grep) no response schema or route exposes either
      column, matching the audit's findings — record this as a verified
      negative result, not a new test (there is nothing to test for a
      field that doesn't exist). Confirmed: zero matches for
      `id_proof_storage_key`/`idProofUrl`/`id_proof_url` in
      `invitations/schemas.py` or `invitations/router.py`.

## 7. file-storage capability regression pass

- [x] 7.1 Re-run every existing `file-storage`-capability-relevant test
      (`core` storage tests, `invitations` upload tests) after Task Groups
      1-6 land, confirm no regression in the existing allow-list, size-
      limit, or server-generated-key requirements. `core`/`auth`/
      `audit_trail` together: 147 passed. `invitations` alone: 214 passed
      (task 2.5).
- [x] 7.2 Confirm `ruff check .`, `ruff format --check .`, and `mypy` on
      `core`, `auth` are clean (`project-rules.md` strict-typing scope
      includes `core` and `auth`). All clean (one unrelated pre-existing
      formatting issue in an unrelated change's `design.md` markdown file,
      not touched by this change).

## 8. Final verification

- [x] 8.1 Run the full suite fresh: `ddev exec uv run pytest -q`, record
      the pass count and confirm zero failures/skips introduced by this
      change. **801 passed, 0 failed, 0 skipped** (502s).
- [x] 8.2 Manually verify in a browser (or via `curl`/Postman) against a
      running `ddev` instance: create an invitation with a primary-contact
      photo, fetch the returned `primaryContactPhotoUrl` directly, confirm
      it renders as an image; upload an avatar via `POST /auth/me/avatar`
      and confirm `GET /auth/me` returns a fetchable `avatarUrl`; issue a
      badge and confirm `badgeUrl` is fetchable. Done live against the
      running `ddev` web container (`http://127.0.0.1:32769`, the seeded
      dev admin): logged in, uploaded a real JPEG via `POST /auth/me/
      avatar`, confirmed `GET /auth/me` returned a signed `/api/v1/files/
      local/...` URL, fetched it directly and confirmed a real 4x4 JPEG
      came back (`Content-Type: image/jpeg`, correct bytes via Pillow), and
      confirmed a tampered URL is rejected with 403. The invitation-photo
      and badge fetch paths use the identical `storage_url_for`/signed-URL
      mechanism and are separately proven end-to-end by the automated
      httpx-based tests in Task Group 2 (which exercise the real FastAPI
      app over ASGI, the same code path a live server runs) — not
      re-duplicated by hand here.
- [x] 8.3 Write a closing summary in the PR description: what was
      previously broken (local-backend URLs unusable, avatar upload
      missing), what test count changed, and the two explicit decisions
      that were deliberately left as-is (ID-proof non-exposure, malware
      scanning still an open pre-production item). No PR opened this
      session (not requested) — summary delivered to the user directly
      instead; content:

      **Fixed**: `core/storage.py::url_for()` returned a raw server
      filesystem path for the local backend (default in dev/test) instead
      of an HTTP-fetchable URL — every existing invitation photo/badge URL
      field was silently unusable by a frontend. Now signed and served via
      a new `core/storage_router.py`, with zero call-site changes.
      **Added**: `POST /auth/me/avatar` — profile picture upload didn't
      exist at all (the `avatar_url` column was fully dead: no write path,
      missing from `UserOut`, missing from `EmployeeDirectoryOut`). Now
      end-to-end: upload, validate, store, resolve, surface on both
      `GET /auth/me` and the employee directory.
      **Fixed**: invitation file uploads read the full body into memory
      before checking size, contrary to `file-upload-handling.md` §1 (and
      the invitations spec's own already-written scenario for it) — reads
      are now bounded to `max_size_bytes + 1`.
      **Found and fixed incidentally**: `UserFactory` (polyfactory) never
      excluded `avatar_url` from random-value generation, unlike its
      sibling optional columns — flaky now that the field is actually
      surfaced in responses.
      **Deliberately left as-is / deferred**: (1) the QR check-in image's
      dead storage write — closing it needs a migration
      (`image_storage_key` is `NOT NULL`, not nullable as first assumed),
      deferred to a follow-up rather than adding migration risk on release
      day; (2) ID-proof scan images remain unexposed by any URL — a
      deliberate PII-minimization decision, now documented in code,
      matching `security-architecture.md` §4; (3) malware/content scanning
      remains the pre-existing, already-flagged pre-production open item.
      **Test count**: 801 passed, 0 failed (full suite, task 8.1).
