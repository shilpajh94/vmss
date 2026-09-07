## Context

See `proposal.md` - Why for the audit findings this design closes. Key
facts that shape the approach (file:line references from that audit):

- `core/storage.py::url_for()` (`:112-126`) already branches on
  `settings.storage_backend`: for `"s3"` it returns a presigned, time-boxed
  URL (`:175-184`); for `"local"` (the default, `core/config.py:146`) it
  returns `str(_path_for(key))` — a bare filesystem path. `url_for()`'s own
  docstring already says a caller needing client-fetchable content "should
  use `load()` behind its own authenticated route instead" — no feature
  does this today.
- `avatar_url` (`auth/models.py:93`) exists, is nullable, `String(500)`, and
  has zero write paths and one missing read path (`UserOut`). No migration
  exists that assumes a particular value shape (opaque key vs. resolved
  URL) beyond "string, max 500 chars."
- `invitations/service.py` already validates every upload via
  `storage.validate_upload(content, max_size_bytes=...)` (`:142-155`,
  `:357-378`), fed by `content = await file.read()` in `invitations/
  router.py:638-643` — the size check runs, but only after `.read()` has
  already fully buffered the file.
- `invitations/service.py:129` writes the rendered QR PNG to storage at
  issuance; `invitations/tasks.py:85` independently regenerates the same
  QR image from `qr_token` for the actual email attachment. No code path
  reads `image_storage_key` back.

## Goals / Non-Goals

**Goals:**
- Make every existing and new client-facing `*Url` field a genuinely
  fetchable HTTP reference in both storage backends, with zero call-site
  changes in the features that already build these fields from
  `url_for()`.
- Ship profile-picture upload as a working, tested, end-to-end feature.
- Fix the two smaller, independently-cited gaps (pre-buffer size check,
  QR dead write) without expanding scope beyond what the proposal commits
  to.

**Non-Goals:**
- Malware/content scanning (`file-upload-handling.md` §4) — remains the
  existing, documented pre-production open item.
- Exposing ID-proof scan images via any URL — this design keeps that
  content unreachable by any response field, as a deliberate decision
  (below), not an oversight.
- Renaming the `avatar_url` column or any other storage-key column —
  no migration is introduced by this change.
- Removing the `image_storage_key` column from `InvitationQRCode` — only
  the write into it stops; dropping the column is a separate,
  migration-bearing cleanup left for later.

## Decisions

### 1. Local backend serves files via a signed, time-boxed URL — not a raw path, not a permission-checked route

**Decision**: `url_for()`'s local branch generates a signed URL of the form
`/files/local/{key-urlsafe}?exp=<unix-ts>&sig=<hmac>` instead of a raw
path. A new, small, storage-owned route (not owned by any feature)
verifies the HMAC signature and expiry, then streams the file via the
existing `storage.load()`, setting `Content-Type` from the same
magic-byte sniff `validate_upload` already does on save. The HMAC key is
a new `settings.storage_local_url_secret` (falls back to
`settings.jwt_secret_key` if unset — the only general-purpose secret this
codebase already defines — avoiding a new required `.env` entry).
TTL is a new `settings.storage_local_presigned_url_ttl_seconds`, mirroring
the existing `storage_s3_presigned_url_ttl_seconds` naming.

**Why**: This is the closest possible parity with the S3 backend's
existing, already-accepted security model — a presigned URL's signature
*is* the authorization, not a second permission check at fetch time. It
requires **zero changes** in `invitations`, `auth`, or any other caller:
every place that already does `storage_url_for(key)` keeps working, and
the returned string simply becomes fetchable instead of being a dead
path. This directly satisfies the proposal's "additive from the client's
perspective" framing.

**Alternatives considered**:
- *Per-feature authenticated download route* (e.g. `GET /invitations/
  {id}/photo`, `GET /auth/me/avatar`), reusing each resource's existing
  permission dependency. Rejected as the primary mechanism: it would
  require a new route and a `url_for` call-site rewrite in every one of
  the ~6 places that build a photo/badge URL today, for no security
  benefit over a signed URL — the caller already decided the requester
  may see this resource at the moment it built the response containing
  the URL. Static local-disk serving would still need its own route to
  avoid mounting the whole `var/storage` tree publicly.
- *Mount local storage under StaticFiles*: rejected outright — this would
  make every uploaded file (including ID-proof scans) reachable by
  anyone who can guess or intercept a key, with no expiry and no
  ability to revoke, the opposite of the tenant-scoped, permission-gated
  model `security-architecture.md` §4 requires for documents.

**Where it lives**: a new `core/storage_router.py` (`router = APIRouter
(prefix="/files", tags=["file-storage"])`), registered in `api.py`
alongside feature routers. This is cross-cutting storage infrastructure,
not a feature — it has no `service.py`/`schemas.py` of its own beyond the
sign/verify helpers added to `core/storage.py`.

### 2. Avatar upload reuses the existing `avatar_url` column to store the opaque key

**Decision**: `POST /auth/me/avatar` writes the storage key returned by
`storage.save(...)` directly into `User.avatar_url`, resolving it through
`storage.url_for()` at response-construction time in `auth/router.py` —
the same pattern `invitations` already uses for `photo_storage_key` →
`photo_url`.

**Why**: The proposal committed to no schema migration for this change.
Reusing the column avoids one; the naming mismatch (a column literally
named `..._url` holding an opaque key, not a URL) is real but cosmetic —
`invitations` already draws the same key/URL distinction with correctly
named columns, so this is a one-column, one-migration cleanup that can
follow later without touching behavior.

**Alternative considered**: add a new `avatar_storage_key` column and
migration, deprecate `avatar_url` as a computed/response-only field.
Rejected only for *this* change given the release-day timing constraint;
noted here so it isn't silently forgotten.

**Size/type limits**: new `settings.avatar_max_upload_size_bytes`
(default 2 MiB, matching `invitation_max_photo_size_bytes`), same
JPEG/PNG allow-list as invitation photos — no new validation code path,
just a new call site into the existing `storage.validate_upload`.

### 3. Pre-buffer size check via a bounded read, not a `Content-Length` trust

**Decision**: replace `content = await file.read()` with `content = await
file.read(max_size_bytes + 1)`; if `len(content) > max_size_bytes`,
reject immediately without reading further. Apply this at each of the
four read sites in `invitations/router.py` (`:638-643`) and the new
avatar upload route.

**Why**: `Content-Length` on a multipart part is not reliably present or
trustworthy (chunked transfer encoding omits it); bounding the read
itself is correct regardless of what headers claim, and is a minimal,
localized change — it satisfies the spec's existing (already-written,
already-violated) "before buffering the full upload into memory"
scenarios without restructuring the upload flow.

### 4. QR image: keep the write — reverted during implementation

**Original decision** (superseded): remove the `storage.save(...)` call for
the rendered QR PNG in `invitations/service.py`'s issuance path (`:129`),
on the assumption that `InvitationQRCode.image_storage_key` was a nullable
column that could simply go unpopulated going forward.

**Reverted because**: `image_storage_key` is actually `Mapped[str]` —
**not** nullable (`invitations/models.py:219`). Dropping the write would
violate the column's `NOT NULL` constraint on every future QR issuance
without a migration to relax it, which contradicts this change's own
"no migration" scope (Goals/Non-Goals, and the proposal's Impact section).
Adding that migration now, on release day, to remove a purely-cosmetic
dead write carries more risk than the cleanup is worth.

**Current decision**: keep the existing write unchanged. The observation
stands — no code path reads `image_storage_key` back, and the visitor-
facing QR image is independently regenerated from `qr_token` for the
email attachment (`invitations/tasks.py:85`) — but closing it is deferred
to a follow-up change that can pair the column-nullability migration with
removing the write in one deliberate, reviewed step, not bundled into a
release-day image-storage fix.

### 5. ID-proof scans stay unexposed by URL — documented, not silently omitted

**Decision**: no response field or endpoint is added for
`id_proof_storage_key`/`primary_contact_id_proof_storage_key`. Add a code
comment at both column definitions in `invitations/models.py` stating
this is deliberate, citing `security-architecture.md` §4 ("access to raw
document images is itself a permission, not implied by can view visitor
record") and noting no such permission or endpoint exists yet.

**Why**: this matches the project's own documented security posture, and
inventing a viewing feature that wasn't requested (by the user or by any
existing product doc) risks adding an under-specified PII-access surface
on a release day. If ID-proof viewing becomes a real requirement, it
should get its own proposal with an explicit `documents:view`-style
permission, per the security architecture's own stated model.

## Risks / Trade-offs

- **[Risk] The signed local URL's secret defaults to `settings.
  jwt_secret_key` if `storage_local_url_secret` is unset** → mitigation: document the new
  setting in `.env.example` with its own generated value in every real
  environment; the fallback exists only so a fresh dev checkout doesn't
  hard-fail on a missing key, not as a recommended production posture.
- **[Risk] A signed local URL, once issued, is valid for any bearer until
  it expires (same as S3 presigned URLs already accepted in this
  codebase)** → mitigation: keep the TTL short (mirror the existing S3
  default), and note this is a pre-existing accepted trade-off, not a new
  one introduced here.
- **[Trade-off] `avatar_url` stores a key, not a URL, despite its name**
  → mitigation: documented in Decision 2 as a deliberate, temporary
  inconsistency with a clear follow-up.
- **[Risk] Bounded `file.read(max_size_bytes + 1)` changes behavior for
  any caller relying on multiple `.read()` calls returning the remaining
  content** → mitigation: each of these read sites currently does exactly
  one `.read()` call per file and immediately hands the result to
  validation/storage; confirmed no site reads a file in a loop.

## Migration Plan

- No database migration. `avatar_url` and `InvitationQRCode.
  image_storage_key` both already exist and are already nullable.
- New settings (`storage_local_url_secret`,
  `storage_local_presigned_url_ttl_seconds`, `avatar_max_upload_size_bytes`)
  ship with safe defaults so existing deployments don't require an `.env`
  change to keep working; `.env.example` is updated per
  `database-architecture.md` §8.
- Rollback: each decision is independently revertable — the signed-URL
  route can be removed with `url_for()` reverting to its previous local
  behavior; the avatar endpoint can be disabled without affecting any
  other feature; the QR-write removal and the bounded-read fix are both
  simple, isolated diffs.
