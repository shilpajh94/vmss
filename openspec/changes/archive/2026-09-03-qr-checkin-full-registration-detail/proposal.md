## Why

The QR check-in success response (`PATCH /api/v2/invitations/qr/{token}/check-in`)
was scoped to a lean set of fields — primary contact, host, purpose,
department, timeline, expiry — sufficient for the frontend spec agreed at
the time, but it stops short of "everything captured at registration."
A caller scanning at a gate can't yet see who else is in the group, what
vehicle they brought, or what items they're carrying, even though this
information exists on the invitation and is already surfaced by the
existing public tracking lookup (`GET /invitations/track?trackingId=`).
Confirmed with the requester: the QR check-in response should match that
existing "everything captured at registration" shape.

## What Changes

- `InvitationQrCheckInOut` (the QR check-in response schema) gains the
  fields already present on `InvitationTrackingOut` but missing here:
  `registrationType`, `source`, `visitorCategoryId`,
  `preferredVisitDate`/`preferredVisitTime`/`expectedDuration`,
  `additionalNotes`, `carriedItems`/`carriedItemsDescription`, the
  co-visitor list (`visitors`), and the vehicle list (`vehicles`). The
  fields already on the QR response (`id`, `checkInStatus`,
  `checkedInAt`/`checkedOutAt`, primary contact email/phone, `hostId`)
  are unchanged.
- `currentApprovalStep` is deliberately **not** added — it's only ever
  populated for a `submitted` invitation, and a QR token is never issued
  before `approved` (`add-qr-checkin-security`'s own "Token is generated
  once at approval" requirement), so it would always serialize `null` on
  this endpoint. Not worth the field.
- The service call backing this endpoint switches from a plain,
  no-eager-load fetch to the same eager-loaded fetch the tracking lookup
  already uses, so `visitors`/`vehicles` (both `lazy="raise"`
  relationships) don't raise when the response schema serializes them.
- No change to the request shape, the state-machine/expiry/watchlist
  behavior, or any other endpoint — purely a response-payload expansion.
  Additive per `api-conventions.md` §2 (new optional-to-consumers response
  fields), no version bump needed.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `invitations`: the QR check-in response's "surfaces full invitation
  detail" requirement (`add-qr-checkin-security`) is amended — "full"
  now explicitly includes co-visitors, vehicles, carried items, and
  registration metadata, not just primary-contact/host/timeline fields.

## Impact

- **Code**: `src/vmss_api/invitations/schemas.py` (`InvitationQrCheckInOut`
  gains fields), `src/vmss_api/invitations/router.py`
  (`_to_qr_check_in_out` mapper populates them), `src/vmss_api/invitations/
  service.py` (`check_in_by_qr_token` fetches with children eager-loaded,
  matching `query-performance.md` §1's "eager-load what the caller will
  access").
- **API contract**: additive only — existing consumers of the current,
  narrower response are unaffected; new fields simply appear alongside
  what's already there.
- **Frontend**: the shared frontend spec artifact (already flagged as
  needing an update for the cycling-lifecycle correction) will need this
  field expansion folded in too before republishing.
