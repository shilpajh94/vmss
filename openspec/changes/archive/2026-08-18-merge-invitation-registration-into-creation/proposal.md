## Why

`POST /api/v1/invitations` (API-09) currently creates only a minimal invitation
*shell* (`registrationType` + a bare-bones primary contact); the visitor
supplies everything else — co-visitor list, visit details, carried items,
vehicles, consents, and ID-proof uploads — later, through a separate public
self-registration link (`POST /invitations/{trackingToken}/register`, API-10).
That two-phase split is documented and deliberate
(`openspec/changes/add-pre-registration/design.md` Decision 1), but it no
longer matches how this API is meant to be used: the caller wants to submit
the complete visit record — visitors, visit details, items, vehicles, and
consents, including ID-proof files — directly to `POST /invitations` in a
single authenticated call, the same shape API-10 already accepts. This change
collapses the two endpoints into one so that creating an invitation *is*
registering the full visit, with no separate follow-up step.

## What Changes

- **BREAKING**: `POST /api/v1/invitations` (API-09) changes from a JSON
  request accepting only `{registrationType, primaryContact}` to a
  `multipart/form-data` request accepting the full visit record: a JSON
  `payload` part (`registrationType`, `primaryContact` with `idProofType`,
  `visitors[]` each with `idProofType`, `visitDetails`, `carriedItems`,
  `vehicles`, `consents`) plus separate file parts for the primary contact's
  and every visitor's ID-proof upload — the same multipart shape API-10 uses
  today. The endpoint creates a fully populated, immediately-`submitted`
  invitation in one call; there is no more intermediate `pending` shell state.
- **BREAKING**: `POST /invitations/{trackingToken}/register` (API-10) is
  removed. There is no longer a separate public self-registration step, and
  the signed invitation JWT that authorized it is no longer minted or
  verified for that purpose.
- `InvitationOut`'s `registrationLink` field is removed — there is nothing
  left to link to, since creation itself completes the visit record.
- The QR code attached to the visit-confirmation notification now encodes the
  plain `trackingId` instead of a signed invitation JWT — the JWT's only
  reason to exist (resolving tenancy on an unauthenticated write endpoint with
  no bearer token, `add-pre-registration/design.md` Decision 9) goes away
  once there is no more unauthenticated write endpoint. `core/security.py`'s
  `create_invitation_token`/`decode_invitation_token` and
  `invitations/deps.py`'s `get_invitation_claims`/`get_invitation_tenant`/
  `get_invitation_tenant_db` are removed as dead code.
- The two dispatch tasks (`send_invitation_link` — "please register" — and
  `send_registration_confirmation` — "you're confirmed") collapse into one
  `send_visit_confirmation` task, fired once at creation instead of twice
  across two requests.
- Consent (`termsAccepted`, `dataProcessingAccepted`, `safetyGuidelinesAccepted`)
  and every visitor's ID-proof upload are now captured by the authenticated
  caller at creation time, on the visitor's behalf, rather than affirmed and
  uploaded by the visitor themselves in a separate step — called out as an
  accepted trade-off in `design.md`.
- `GET /invitations/track` (API-12) keeps its existing response shapes
  unchanged, but a looked-up invitation is now always in its final, fully
  detailed state immediately after creation — there is no more transient
  shell/pending state for a caller to observe.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: `POST /invitations` request/response contract changes from a
  minimal JSON shell-creation call to a full multipart visit-registration
  call; `POST /invitations/{trackingToken}/register` is removed; the tracking
  token's role as an unauthenticated write-authorization mechanism is removed;
  tracking lookup no longer has a pending/shell state to describe.

## Impact

- `src/vmss_api/invitations/router.py` — `create_invitation` route becomes
  multipart (JSON `payload` part + file parts, mirroring the current
  `submit_self_registration` route); `submit_self_registration` route and its
  `openapi_extra` examples are removed.
- `src/vmss_api/invitations/schemas.py` — `InvitationCreate` absorbs
  `SelfRegistrationSubmit`'s fields (visitors, visit details, carried items,
  vehicles, consents, ID-proof types); `SelfRegistrationSubmit`,
  `SelfRegistrationOut` are removed; `InvitationOut` drops `registrationLink`.
- `src/vmss_api/invitations/service.py` — `create_invitation` absorbs
  `submit_self_registration`'s validation, file storage, and child-row
  creation logic; `submit_self_registration` is removed.
- `src/vmss_api/invitations/deps.py` — `get_invitation_claims`,
  `get_invitation_tenant`, `get_invitation_tenant_db` are removed;
  `track_default_tenant_db` is unaffected.
- `src/vmss_api/invitations/tasks.py` — `send_invitation_link` and
  `send_registration_confirmation` collapse into `send_visit_confirmation`.
- `src/vmss_api/invitations/models.py` — no schema/column changes; all fields
  already exist on `Invitation` (previously filled across two writes, now
  filled in one). No new Alembic migration required.
- `src/vmss_api/core/security.py` — `create_invitation_token`/
  `decode_invitation_token` removed.
- `src/vmss_api/invitations/tests.py` — API-09/API-10 test split collapses
  into one set of tests against the merged endpoint; permission-denied and
  tenant-isolation cases (`testing-standards.md` §2) are re-verified against
  the new request shape.
- `docs/features/invitations.md` — updated to describe the merged endpoint and
  the removal of API-10 (see design.md for why this ships as an immediate
  breaking change rather than a deprecation window).
