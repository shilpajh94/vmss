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
| POST | `/api/v1/registrations/walk-in` | `X-Device-Key` (no bearer token) | 20/minute per IP | A visitor registers themselves on arrival: primary contact, co-visitors, visit details, carried items, vehicles, and consent — identical multipart shape to `POST /invitations` (JSON `payload` Form field + ID-proof file parts). Creates the same kind of `Invitation` record pre-registration does, tagged `source: "visitorWalkIn"`, immediately `status: "submitted"`. Accepts an optional `Idempotency-Key` header, same semantics as `POST /invitations`. |

No separate tracking-lookup endpoint here — a walk-in registration's tracking
ID works with the existing `GET /invitations/track` (both lookup forms),
since it's stored in the same table.

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

## File uploads (API-14)

ID-proof uploads go through the same `core/storage.py::validate_upload` +
`save`/`url_for` interface `invitations` uses — real content-sniffing via
`python-magic`, size-limit enforcement, opaque storage keys. As of this
feature, that interface has a real S3-compatible backend, not just a
local-disk one, selected by configuration:

| Setting | Default | Purpose |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` (disk) or `s3`. |
| `AWS_BUCKET` | unset | Required when `STORAGE_BACKEND=s3`. |
| `AWS_DEFAULT_REGION` | unset | AWS region, or the equivalent for an S3-compatible provider. |
| `AWS_ENDPOINT_URL` | unset | Only for a non-AWS S3-compatible provider (e.g. MinIO). Leave unset for AWS. |
| `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` | unset | Required when `STORAGE_BACKEND=s3`. Read directly by boto3, not by `Settings` — see `docs/features/configuration.md`. |
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
