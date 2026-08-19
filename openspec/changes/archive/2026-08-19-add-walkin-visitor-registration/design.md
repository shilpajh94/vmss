## Context

`invitations` (API-09/12) already implements the full six-step visit-record
contract as `InvitationCreate` (`src/vmss_api/invitations/schemas.py`),
persisted to `Invitation`/`InvitationVisitor`/`InvitationVehicle`
(`src/vmss_api/invitations/models.py`), created via
`invitations.router.create_invitation` → `invitations.service.create_invitation`,
which is authenticated (`require_branch_permission("invitations:create")`,
branch resolved from `X-Branch-ID`), validates and stores each ID-proof
upload through `core/storage.py` (local-disk in dev), and dispatches a Celery
visit-confirmation task. See `proposal.md` for why the Figma cross-check
shows this is the same form a walk-in visitor fills out, just with a
different actor and no advance invitation.

No device/API-key auth concept exists anywhere in this codebase today — the
closest precedent is `tenant_user_index` (`platform/models.py`, global
schema): a lookup table that resolves an unauthenticated identifier to a
tenant before any tenant-scoped session can be opened, the same shape of
problem a kiosk device credential has to solve.

## Goals / Non-Goals

**Goals:**
- One JSON contract for both staff pre-registration and visitor walk-in —
  no parallel schema to keep in sync.
- A visitor can submit a complete registration with no bearer token, while
  tenant/branch resolution stays exactly as trustworthy as an authenticated
  request's (never client-supplied).
- `core/storage.py`'s two-function interface gains a real S3-compatible
  implementation, benefiting both `invitations` and the new endpoint without
  either call site changing.

**Non-Goals:**
- No check-in/badge issuance. That is the not-yet-built `checkin` feature's
  job; this change only produces the same kind of record `invitations`
  already produces.
- No OTP verification of the visitor's contact info. The Figma shows it;
  nothing in the codebase implements it yet for any endpoint, and adding it
  here would mean designing a whole new OTP subsystem as a side effect of a
  registration-endpoint change. Tracked as a follow-up.
- No approval-workflow evaluation against `ApprovalWorkflowRule`. Same
  posture `invitations` already has — that's the not-yet-built `approvals`
  feature's job.
- No change to `POST /invitations`'s existing contract, auth, or response.

## Decisions

### Decision 1: Reuse the `Invitation` table with a `source` column, not a new table
**Choice**: Add `source: Mapped[str]` (`staff_pre_registration` |
`visitor_walk_in`, default `staff_pre_registration`) to `Invitation`, and
relax `created_by_user_id` to nullable. `invitations.service.create_invitation`
gains a `source: RegistrationSource = RegistrationSource.staff_pre_registration`
parameter; the new walk-in path passes `visitor_walk_in` and
`created_by_user_id=None`.

**Why**: The record produced is genuinely the same thing — a tracking ID,
a status, a visit record, visitors, vehicles. A second table (`WalkInRegistration`)
would need its own tracking-ID scheme, its own tracking-lookup endpoint, and
would fork the moment either evolves. A `source` column keeps one
source of truth and lets a future report ("today's arrivals") query across
both channels with one filter.

**Alternative considered**: A separate `WalkInRegistration` table +
duplicated tracking-lookup logic. Rejected — it's exactly the parallel
contract the proposal is trying to avoid, just moved from the schema layer
to the table layer.

### Decision 2: New `registrations` feature package, thin over `invitations`
**Choice**: `src/vmss_api/registrations/` owns only what's genuinely new: the
device-credential model/repository, the device-auth dependency, rate
limiting, and the router for `POST /registrations/walk-in`. Its router calls
`invitations.service.create_invitation` directly (passing `source`) rather
than reimplementing creation logic — `registrations` has no `Invitation`
repository of its own.

**Why**: `fastapi-architecture.md` §6 already sanctions `core` importing from
`auth`/`tenant` as "cross-cutting infrastructure every other feature needs";
this is the same shape of exception in miniature — `registrations` needs
`invitations`'s creation logic the same way `core`'s tenancy chain needs
`auth`'s `User` model. The alternative (duplicating `create_invitation`'s
body into `registrations/service.py`) would immediately drift the moment
either changes.

**Alternative considered**: Fold the new endpoint directly into
`invitations/router.py` behind a `channel` field on `InvitationCreate` (the
"one route, client-supplied flag" option). Rejected per the earlier
discussion with the user — it mixes a fully-authenticated dependency chain
(`require_branch_permission`) and a public, rate-limited, device-keyed one
behind a single route, which is exactly the kind of place an auth bug hides.

### Decision 3: Device credential is a new global-schema table, resolved before tenancy
**Choice**: `registrations/models.py::RegistrationDeviceKey` (`GlobalBase`,
alongside the precedent of `platform`'s `tenant_user_index`): `id`,
`tenant_id`, `branch_id`, `key_hash` (Argon2, never the raw key at rest),
`label`, `is_active`, timestamps. The walk-in router depends on a new
`registrations/deps.py::get_registration_device` that reads `X-Device-Key`,
hashes and looks it up in the global schema, and yields the resolved
`(tenant, branch)` — structurally identical to how `get_tenant`/`get_tenant_db`
already resolve an authenticated request, just keyed by device instead of by
JWT claim.

**Why**: The auth-routing problem here is the same one `tenant_user_index`
solves for login (`database-architecture.md` §2's "auth-routing problem"):
the request has to resolve *which* tenant schema to open before anything
tenant-scoped can run, and the credential that does that resolving has to
live somewhere reachable pre-tenant, i.e. the global schema.

**Alternative considered**: A signed QR/link scanned per-visit encoding
tenant+branch. Rejected for this change (not chosen when discussed with the
user) — it requires a physical signage/provisioning flow of its own and adds
a second credential concept; a device-bound key is closer to how a kiosk app
is actually deployed (provisioned once per branch, not re-issued per
visitor).

**Provisioning**: out of scope for this change's UI — a superadmin/admin
issues a device key via a script or a future `platform`/`org_structure`
endpoint. This change only builds the verification side
(`get_registration_device`); issuing one is a `tasks.md` item scoped to "make
this testable," not a full management UI.

### Decision 4: Storage backend selected by config, not by caller
**Choice**: `core/storage.py`'s `save`/`url_for` bodies branch on
`settings.storage_backend` (`local` | `s3`). The S3 branch uses an
S3-compatible async client, bucket/credentials/endpoint from `settings`
(`STORAGE_S3_BUCKET`, `STORAGE_S3_REGION`, `STORAGE_S3_ENDPOINT_URL` for
non-AWS S3-compatible providers, credentials via the client's standard
credential chain — never hardcoded). `url_for` returns a pre-signed,
time-boxed URL rather than a raw path when the backend is `s3`.

**Why**: `invitations.md` already documents this as the intended shape
("swapping to S3-compatible object storage in prod is a new implementation
behind the same two functions") — API-14 is that swap, not a redesign. Both
`invitations` and the new walk-in endpoint automatically get real object
storage with zero call-site changes, since both already only ever handle
opaque storage keys.

**Alternative considered**: A separate `S3StorageService` class injected via
DI instead of a config-branched free function. Rejected as unnecessary
churn — nothing else about `core/storage.py`'s two call sites needs
swapping at runtime within one process; config selects the backend once at
startup.

## Risks / Trade-offs

- **[Risk]** A compromised or leaked device key lets an attacker create
  walk-in registrations (and consume the primary contact's ID-proof upload
  path) against that branch indefinitely. → **Mitigation**: keys are stored
  hashed, rate-limited per §"Requirement: Walk-in registration is
  rate-limited", and `is_active` can be flipped off immediately; rotation is
  a `tasks.md` item.
- **[Risk]** No OTP means a walk-in registration's stated identity is
  unverified beyond the uploaded ID-proof image itself. → **Mitigation**:
  this is the same trust level `invitations`'s employee-attested flow
  already has (an employee affirms the visitor's identity on their behalf);
  explicitly flagged as a follow-up, consistent with
  `security-architecture.md` §2's existing "fake-entry prevention" open
  item.
- **[Risk]** Making `created_by_user_id` nullable is a schema change to a
  table three existing endpoints already read from
  (`create_invitation`/`track_by_tracking_id`/`track_by_email`). →
  **Mitigation**: nullable is strictly weaker than the current constraint
  (every existing row already has a non-null value), so no backfill is
  needed and no existing query changes behavior.
- **[Trade-off]** `registrations` importing `invitations.service` directly is
  a feature-to-feature dependency the directory-structure convention doesn't
  explicitly bless (unlike `core`→`auth`/`tenant`). Accepted deliberately
  (Decision 2) because the alternative is contract duplication; if a third
  registration channel ever appears, revisit whether this logic should move
  down into something both depend on (e.g. a shared `registration_core`)
  rather than adding a third importer of `invitations.service`.

## Migration Plan

1. `alembic_tenant/` migration: add `invitations.source` (`NOT NULL DEFAULT
   'staff_pre_registration'`), drop `NOT NULL` on
   `invitations.created_by_user_id`. Applied to every existing tenant schema
   per `database-architecture.md` §5 (no autogenerate loop per tenant —
   authored once, applied to each).
2. `alembic/` migration: create the global-schema `registration_device_keys`
   table.
3. Deploy code (new `registrations` package, `invitations` model/service
   changes, `core/storage.py` S3 backend) — additive only, no existing route
   changes behavior.
4. Provision at least one device key per branch that needs walk-in
   registration (manual/script step, not a UI in this change).
5. Rollback: both migrations are additive (new column default-backed, new
   table) and reversible with standard `alembic downgrade`; no data
   transformation to undo.
