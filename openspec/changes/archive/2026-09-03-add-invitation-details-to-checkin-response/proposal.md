## Why

The mobile app's QR-scanning flow calls the staff-authenticated
`PATCH /api/v1/invitations/{id}/check-in` and only gets back a thin
`InvitationOut` payload (id, trackingId, registrationType, source, status,
visitorCategoryId, hostId, expiresAt, submittedAt, approvedAt,
currentApprovalStep) — no visitor, host, or visit detail, forcing a second
call. Verified against the current code: this endpoint (`invitations/
router.py`'s `check_in_invitation`, `PATCH /{invitation_id}/check-in`) was
**not** touched by the earlier `qr-checkin-full-registration-detail` change —
that one only expanded the separate, token-based
`PATCH /api/v2/invitations/qr/{token}/check-in` response
(`InvitationQrCheckInOut`). The v1 UUID-keyed endpoint the app is actually
calling still returns the original narrow shape. Confirmed with the
requester: the enriched response should match the existing public tracking
lookup shape (`GET /invitations/track?trackingId=`, `InvitationTrackingOut`)
— visitor contact, host, visit details, carried items, co-visitors, and
vehicles — not the fuller staff-only detail view (`GET /invitations/{id}`),
which additionally carries `branchId`, `createdByUserId`, badge, and
watchlist-override internals that don't belong on this response.

## What Changes

- A new response schema, `InvitationCheckInOut`, carries every field the
  current `InvitationOut` response already returns (`id`, `trackingId`,
  `registrationType`, `source`, `status`, `visitorCategoryId`, `hostId`,
  `expiresAt`, `submittedAt`, `approvedAt`, `currentApprovalStep`) plus the
  fields `InvitationTrackingOut` carries that this response is missing:
  `primaryContactFullName`, `purposeOfVisit`, `hostNameOrEmail`,
  `preferredVisitDate`, `preferredVisitTime`, `expectedDuration`,
  `departmentToVisit`, `additionalNotes`, `carriedItems`,
  `carriedItemsDescription`, `visitors` (the co-visitor list), and
  `vehicles`. This is purely additive to the existing field set — no field
  is renamed or removed, so nothing already parsing today's response
  breaks (`api-conventions.md` §2).
- Only `PATCH /api/v1/invitations/{id}/check-in`
  (`check_in_invitation`) switches to the new schema. `InvitationOut` itself,
  and every other endpoint that returns it today (`POST /invitations`,
  `PATCH /{id}/deny`, `PATCH /api/v2/invitations/{trackingId}/check-in`,
  `POST /registrations/walk-in`, the approval-step endpoints), is
  unchanged — out of scope for this change, per the requester's
  confirmation that only the v1 check-in endpoint needs fixing right now.
- The service call backing this endpoint switches from a plain,
  no-eager-load invitation fetch to the same eager-loaded fetch the
  tracking lookup and QR check-in already use, so `visitors`/`vehicles`
  (both `lazy="raise"` relationships) don't raise when the response
  schema serializes them.
- No change to the request shape, the `approved` → `checked_in` state
  transition, the watchlist gate, idempotency behavior, or the
  **Deprecated** status/header this endpoint already carries in favor of
  the `v2` tracking-ID route — response payload only.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `invitations`: adds a new requirement governing
  `PATCH /api/v1/invitations/{id}/check-in`'s success response shape — no
  such requirement currently exists in the main spec for this endpoint's
  response detail (only its deprecation and its state-transition/watchlist
  behavior are documented elsewhere), so this is an added requirement, not
  a modification of an existing one.

## Impact

- **Code**: `src/vmss_api/invitations/schemas.py` (new
  `InvitationCheckInOut`), `src/vmss_api/invitations/router.py`
  (`check_in_invitation` gets a new mapper and `response_model`, and its
  invitation fetch switches to the eager-loaded variant),
  `src/vmss_api/invitations/service.py` (if the fetch swap needs a new or
  reused service function rather than inlining the repository call).
- **API contract**: additive only for this one endpoint — existing
  consumers of today's narrower response are unaffected; new fields
  simply appear alongside what's already there. Still marked
  `Deprecated` per its existing header; this change does not extend or
  shorten its removal timeline.
- **Docs**: `docs/features/invitations.md`'s endpoint table and lifecycle
  section need the expanded response noted for this route.
- **Out of scope, flagged for a follow-up**: `PATCH /{id}/check-out` and
  `POST /registrations/walk-in` return the same thin `InvitationOut` shape
  today and likely have the same gap, but neither was named by the
  requester — not touched here.
