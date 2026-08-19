## Why

API-13 and API-14 ask for a walk-in visitor registration endpoint and a
proper file-upload service for ID/photo evidence, for the Flutter app.
Cross-checking the shared Figma exports (`Requirements/portal-image-*.png`
for the web portal, `Requirements/app-image-*.png` for the app) against the
already-built pre-registration feature (`invitations`, API-09) shows the two
wizards are the same six-step form (Visitor Info → Visit Info → Carried
Items → Vehicle Info → Consent → Review) with the same field set, and
`Requirements/register-type-{individual,group}.txt` match `InvitationCreate`'s
JSON contract field-for-field. The only real difference is *who* is filling
the form out and *when*: an employee pre-registering a future visit from the
web portal (already built), versus a visitor registering themselves on
arrival from the app, with no prior invitation. Building a second, parallel
schema/endpoint for walk-in would duplicate a contract that already exists
and drift from it the first time either one changes.

## What Changes

- Add `POST /api/v1/registrations/walk-in`: a public, rate-limited endpoint
  that accepts the *same* multipart contract as `POST /invitations`
  (`InvitationCreate` JSON payload + ID-proof file parts, reusing the
  existing `invitations.schemas` shapes directly — no parallel schema), and
  is called by the visitor themselves from the app rather than by an
  authenticated employee.
- Add a device-bound credential (`X-Device-Key` header, resolved server-side
  to a fixed tenant + branch) as the auth mechanism for this new endpoint —
  a kiosk/app instance is provisioned once per branch; the caller never
  supplies `tenantId`/`branchId` itself, consistent with
  `security-architecture.md`'s "tenant_id is never read from a request body,
  query param, or path param and trusted" rule extended to branch.
- Extend the existing `Invitation` model/table (not a new table) with a
  `source` column (`staff_pre_registration` | `visitor_walk_in`) and relax
  `created_by_user_id` to nullable, since a walk-in registration has no
  authenticated staff creator. `invitations.service.create_invitation` gains
  a `source` parameter; its existing callers are unaffected (default stays
  `staff_pre_registration`).
- The walk-in call creates the registration record only — same posture as
  today's `invitations` feature (no approval-workflow evaluation, no
  check-in). Actual check-in/badge issuance remains the not-yet-built
  `checkin` feature's job.
- **BREAKING**: none. `POST /invitations`'s existing contract, auth, and
  response shape are unchanged.
- Implement an S3-compatible backend for `core/storage.py`'s `save`/`url_for`
  interface (API-14), selected via a `STORAGE_BACKEND` setting
  (`local` | `s3`), so both `invitations` and the new walk-in endpoint get
  real object storage without any call-site change — the two-function
  interface `invitations.md` already documents as "swap this later" is now
  implemented rather than deferred.
- Explicitly out of scope for this change (recorded, not silently dropped):
  OTP verification of the visitor's contact (shown in the Figma as "OTP will
  be sent to this email" but backed by no API anywhere today), and any
  approval-workflow evaluation against `ApprovalWorkflowRule`s.

## Capabilities

### New Capabilities
- `registrations`: the walk-in visitor registration endpoint — device-bound
  auth, rate limiting, reuse of the `InvitationCreate` contract, and the
  `source` discriminator linking a walk-in submission to the same
  `Invitation` record type pre-registration uses.
- `file-storage`: the object-storage backend behind `core/storage.py`'s
  `save`/`url_for` interface, covering content validation, size limits, and
  the S3-compatible implementation selected by `STORAGE_BACKEND`.

### Modified Capabilities
<!-- No existing `openspec/specs/<path>/spec.md` covers `invitations` today
     (the feature's spec lives only inside the archived
     `merge-invitation-registration-into-creation` change), so the
     `Invitation` model/service changes described above are captured as
     design/impact detail in this change rather than as a delta against a
     capability that has no current baseline spec to delta from. -->

## Impact

- **Code**: new `src/vmss_api/registrations/` feature package
  (`router.py`, `service.py`, `schemas.py`, `deps.py`, `models.py`,
  `repository.py`, `tests.py`); `src/vmss_api/invitations/models.py`
  (`source` column, nullable `created_by_user_id`),
  `src/vmss_api/invitations/service.py` (`source` parameter on
  `create_invitation`); `src/vmss_api/core/storage.py` (S3 backend behind the
  existing interface); `src/vmss_api/core/config.py` (`storage_backend` and
  S3 connection settings).
- **Database**: one `alembic_tenant/` migration (add `invitations.source`,
  drop the `NOT NULL` on `invitations.created_by_user_id`); one `alembic/`
  migration for the new global-schema device-credential table.
- **API surface**: one new public endpoint (`POST /registrations/walk-in`);
  no change to any existing endpoint's request/response contract.
- **Dependencies**: an S3-compatible client library (e.g. `boto3`/`aioboto3`)
  added via `uv add`, needed only for the `s3` storage backend.
- **Docs**: new `docs/features/registrations.md`; update
  `docs/features/invitations.md`'s "Not yet built" section (walk-in is no
  longer a variant to defer) and its "File uploads" section (S3 backend now
  implemented, not just planned).
