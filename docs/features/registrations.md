# Registrations (Walk-in Visitor Registration)

Lets a visitor who arrives with no prior invitation register themselves
on-site from the app — API-13 — reusing the exact same visit-record contract
`invitations` (pre-registration, API-09) already defines, since a Figma
cross-check of the web-portal and app wizards showed they're the same
six-step form with a different actor. See
`openspec/changes/add-walkin-visitor-registration/` for the proposal/design
this feature was built from.

`registrations` owns no `Invitation` table of its own — it delegates
creation to `invitations.service.create_invitation` (passing
`source=RegistrationSource.visitor_walk_in`), and owns only what's genuinely
new: the device-credential model (`RegistrationDeviceKey`, global schema) and
the router/dependency that authenticates a walk-in request by device instead
of by JWT.

## Endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| POST | `/api/v1/registrations/walk-in` | `X-Device-Key` (no bearer token) | 20/minute per IP | A visitor registers themselves on arrival: primary contact, co-visitors, visit details, carried items, vehicles, and consent — identical multipart shape to `POST /invitations` (JSON `payload` Form field + ID-proof file parts, plus the same primary-contact profile-photo file part, now mandatory — see "Primary contact profile photo" below). Creates the same kind of `Invitation` record pre-registration does, tagged `source: "visitorWalkIn"`, immediately `status: "submitted"`. Accepts an optional `Idempotency-Key` header, same semantics as `POST /invitations`. |

No separate tracking-lookup endpoint here — a walk-in registration's tracking
ID works with the existing `GET /invitations/track` (both lookup forms),
since it's stored in the same table.

Since `POST /registrations/walk-in` submits the identical `VisitDetailsSubmit`
shape `POST /invitations` does, it also inherits that schema's optional
`purposeId`/`hostId`/`durationId`/`departmentId` catalog-id fields — see
`docs/features/invitations.md`'s "Optional catalog ids on visit details" and
`docs/features/visit_info.md` for where those ids come from
(`GET /hosts/search`, `GET /visit-info/departments`,
`GET /visit-info/options`).

## Device credential authentication

Unlike every other tenant-scoped endpoint in this API, `POST
/registrations/walk-in` has no user, no `X-Branch-ID` header, and no
permission check — it's called from a branch's own kiosk/app instance, which
authenticates itself with an `X-Device-Key` header. The server resolves that
key to exactly one `(tenant, branch)` pair; the request payload carries no
tenant/branch identifier at all, so there's nothing for a client to spoof
(`security-architecture.md`'s tenant-trust-boundary rule, extended to
branch).

This is structurally the same problem `platform.models.TenantUserIndex`
solves for login (`database-architecture.md` §2's "auth-routing problem"):
which tenant schema to open has to be known before anything tenant-scoped —
here, the branch itself — can be checked. `RegistrationDeviceKey` lives in
the global schema for the same reason.

### Fallback when no `X-Device-Key` is sent at all

`X-Device-Key` is optional, not required: a request with no header at all
falls back to `registrations/deps.py::_resolve_default_device_context`
instead of the 401 it used to get unconditionally. This exists for the
public web portal, which — unlike the Flutter kiosk app — has nowhere safe
to hold a provisioned device secret. The fallback resolves tenant/branch
from server-side config only, never from anything the caller supplies (the
same tenant-trust-boundary rule `security-architecture.md` states for
`tenant_id`, extended to branch):

| Setting | Default | Purpose |
|---|---|---|
| `default_tenant_slug` (`configuration.md`) | — | Which tenant's schema the fallback opens. |
| `REGISTRATION_DEFAULT_BRANCH_CODE` | `MAIN` | Which branch, within that tenant, a header-less walk-in is attributed to. |

If either lookup fails (no such tenant, tenant inactive, no branch with
that code, branch inactive), the fallback still 401s — it never falls
through to an unscoped or partially-resolved registration — but with a
message and log level distinct from an invalid device key. This is a
server-side configuration gap (nothing the caller sent was wrong), so it
gets `_DEFAULT_TENANT_UNCONFIGURED_DETAIL` ("Registration service is not
configured for this environment") and is logged at `ERROR`
(`registration_default_tenant_unconfigured` /
`registration_default_branch_unconfigured`) instead of the `WARNING` an
actually-invalid key produces — per `logging-observability.md` §3, a
missing default tenant/branch needs a human to look, not a log line nobody
alerts on.

**Sanctioned default path, not a stopgap**: this path has no credential at
all — it trades the device key's authentication away for availability,
leaving this fallback an unauthenticated write (and file-upload) call
against one fixed branch, protected only by the route's rate limit. That
trade-off is the reviewed, intended behavior for callers with nowhere safe
to hold a device secret (see `openspec/specs/registrations/spec.md`'s
"authenticated by a device credential, not a user" requirement), not an
open gap. Every use is logged at `WARNING`
(`registration_device_key_absent`) so it stays visible/auditable rather
than silently normalized. Binding this path to the visitor's OTP-verified
`identity_verification` proof token remains a separate, not-yet-scheduled
improvement — see `security-architecture.md` §2's "fake-entry prevention"
open item.

### Provisioning a device key

No management endpoint exists yet — issue one via:

```
ddev exec uv run python scripts/provision_registration_device.py \
    --tenant-slug <slug> --branch-id <uuid> --label "Main Branch kiosk"
```

The raw key is printed exactly once; only its Argon2 hash is stored. Deactivate
a compromised or retired device by flipping its `is_active` flag (no CLI for
this yet — direct DB update, or a future management endpoint).

## What creating a walk-in registration does *not* do

- **No check-in.** This call creates the registration record only — no badge
  issuance, no "checked in" state. That's the not-yet-built `checkin`
  feature's job, the same way it is for a staff pre-registration once the
  invited visitor actually arrives.
- **No OTP verification.** The Figma wizard shows "OTP will be sent to your
  email" on this step. The OTP mechanism itself now exists — see
  `docs/features/identity_verification.md` (API-15) — but this endpoint
  does not call it: creating a walk-in registration does not require or
  check a verified-contact proof. Wiring that gate in is a separate,
  later change, tracked there, not silently skipped.
  `security-architecture.md` §2 already lists OTP handling as a requirement
  for visitor-facing public endpoints generally.
- **No approval-workflow evaluation.** Same posture `invitations` has today —
  the not-yet-built `approvals` feature's job.

### Primary contact profile photo (`require-primary-contact-photo`)

`POST /registrations/walk-in` accepts the same `primary_contact_photo_file`/
`visitor_photo_files` parts `POST /invitations` does — its own router
declares these file parameters independently (its multipart file contract
is not automatically inherited the way the JSON `payload` schema is), but
the validation, storage, and response shape (`photoUrl`/
`primaryContactPhotoUrl`) are identical: image-only (JPEG/PNG),
`INVITATION_MAX_PHOTO_SIZE_BYTES` (default 2 MB). **`primary_contact_photo_file`
is mandatory** — a request omitting it is rejected with a validation error
and creates no registration record, the same way an omitted
`primary_contact_id_proof_file` already is (`require-primary-contact-photo`
— **BREAKING**, tightened in `v1` directly rather than shipped as a new
version). Co-visitor (`visitor_photo_files`) entries remain optional. See
`docs/features/invitations.md`'s "Primary contact profile photo" section
for the full behavior.

### Repeatable form-builder group file uploads (`add-group-field-file-upload`)

`POST /registrations/walk-in` accepts an admin-defined repeatable group's
own `file_upload`-typed field the same way `POST /invitations` does: one
multipart list part named `groupFieldFiles[<groupKey>]`, order-matched to
that group's `payload.groupValues[<groupKey>]` instances — no `instanceIndex`
or field key in the part name, since only a group's first `file_upload`
field is supported. The file field must be omitted (or `null`) from the
corresponding `groupValues` instance dict; supplying a value there instead
of the file is rejected with a 422. See `docs/features/invitations.md`'s
"Repeatable group file uploads" section for the full validation/storage
behavior — it is shared verbatim via `invitations.service.create_invitation`.

## File uploads (API-14)

ID-proof uploads go through the same `core/storage.py::validate_upload` +
`save`/`url_for` interface `invitations` uses — real content-sniffing via
`python-magic`, size-limit enforcement, opaque storage keys. As of this
feature, that interface has a real S3-compatible backend, not just a
local-disk one, selected by configuration:

| Setting | Default | Purpose |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` (disk) or `s3`. |
| `STORAGE_S3_BUCKET` | unset | Required when `STORAGE_BACKEND=s3`. Read by `Settings`, not boto3 — boto3 has no env var of its own for a bucket name. |
| `STORAGE_S3_REGION` | unset | Region to pass to the S3 client explicitly. Leave unset to fall back to boto3's own `AWS_DEFAULT_REGION` resolution. |
| `STORAGE_S3_ENDPOINT_URL` | unset | Only for a non-AWS S3-compatible provider (e.g. MinIO). Leave unset for AWS's default endpoint resolution. |
| `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION` | unset | Required when `STORAGE_BACKEND=s3`. Read directly by boto3's default credential provider chain, not by `Settings` — see `docs/features/configuration.md`. |
| `STORAGE_S3_PRESIGNED_URL_TTL_SECONDS` | `300` | How long a `url_for` pre-signed URL stays valid when the backend is `s3`. |

Switching backends is a config change only — no call site in `invitations`
or `registrations` branches on which one is active; both only ever handle
the opaque storage key `save` returns.

## Not yet built (flagged, not silently dropped)

- **Device key management endpoint/UI.** Provisioning is CLI-only today
  (`scripts/provision_registration_device.py`); rotation is a direct DB
  update to `is_active`/`key_hash`.
- **Wiring OTP verification into this endpoint**, **check-in**,
  **approval-workflow evaluation** — see above.
