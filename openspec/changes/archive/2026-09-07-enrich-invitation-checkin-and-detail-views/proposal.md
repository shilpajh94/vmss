## Why

Security staff scanning a visitor's QR code at the gate, and staff viewing
an invitation's detail record, currently cannot see the visitor's ID-proof
type, or which building/department the visit resolves to — they only see a
raw `branchId` (on the detail view) and nothing at all on the QR check-in
response, forcing a follow-up lookup or a walk to a printed floor
directory. This closes that gap while keeping the ID-proof *document image*
itself behind its own permission on the one endpoint where a permission
check is actually possible, per `security-architecture.md` §4 ("access to
raw document images is itself a permission, not implied by can view visitor
record").

**Correction from initial scoping**: this change originally targeted
`PATCH /api/v2/invitations/{trackingId}/check-in` as "the check-in API."
That endpoint is confirmed public/unauthenticated (no `user` dependency,
no branch authorization — see `service.py::check_in_invitation_by_tracking_id`'s
own docstring), so a permission-gated field cannot be added to it, and it
is now **out of scope**, unchanged. The actual target, per user
clarification, is `PATCH /api/v2/invitations/qr/{token}/check-in` — also
unauthenticated, but on a stronger trust tier: the signed, encrypted QR
token itself (not a guessable tracking ID) is the credential
(`security-architecture.md` §2), and this endpoint already discloses the
primary contact's email/phone and host today on that basis. Because there
is still no permission to check on this route, the ID-proof *document
image* stays off it — only `idProofType` (not sensitive on its own, and
already exposed for visitors on other responses) is added there.

## What Changes

- Add a new `documents:view` permission to the RBAC catalog. Granted by
  default to `reception` and `security` (the roles that perform desk-side
  ID verification via the staff detail view); not granted to `host`.
- `GET /invitations/{id}` (staff detail view, authenticated,
  `invitations:view`-gated):
  - Always include the primary contact's `idProofType` (already stored,
    never surfaced before).
  - Include a resolved, fetchable `idProofUrl` for the primary contact and
    for each visitor **only when the caller holds `documents:view`**;
    `null` otherwise. Additive to the existing `invitations:view` check,
    not a replacement for it.
  - Include resolved branch details (`name`, `code`, `address`, `city`) in
    addition to the existing raw `branchId` (kept, unchanged).
  - Include resolved building and department details (`name`, `code`) when
    resolvable via the invitation's optional `departmentId` → floor →
    building chain; `null` when the invitation has no `departmentId` on
    file (free-text `departmentToVisit` is unaffected and still always
    present).
- `PATCH /api/v2/invitations/qr/{token}/check-in` and
  `PATCH /api/v2/invitations/qr/{token}/check-out` (public, QR-token-keyed,
  unauthenticated — no permission to gate anything by):
  - Always include the primary contact's and each visitor's `idProofType`.
  - Always include resolved branch/building/department detail (same
    resolution rule as above), consistent with this endpoint's existing
    posture of surfacing full registration detail to a valid-token holder.
  - Do **not** include an ID-proof document image/URL — that stays
    exclusive to the authenticated detail view, where `documents:view` can
    actually be checked.
- Profile image (`photoUrl`) is **not** a gap — already resolved and
  returned on both responses today; no change needed there.
- Out of scope, unchanged: `PATCH /api/v2/invitations/{trackingId}/check-in`
  (public tracking-ID check-in, `InvitationCheckInOut`) and the tracking/
  email lookup endpoints (`InvitationTrackingOut`,
  `InvitationTrackingSummaryOut`) — adding an ID-proof document or
  additional internal detail to those would contradict their "minimally
  revealing" posture, and there remains no permission mechanism on any of
  them to gate a document by.

## Capabilities

### Modified Capabilities
- `invitations`: staff detail view and QR check-in/check-out response
  shapes gain ID-proof type (both) and document (detail view only,
  permission-gated) plus resolved branch/building/department detail.

## Impact

- `src/vmss_api/invitations/schemas.py` — `InvitationDetailOut`,
  `InvitationQrCheckInOut`, `InvitationVisitorOut` gain new fields; new
  nested schemas for resolved branch/building/department; primary-contact
  ID-proof fields added to both response schemas.
- `src/vmss_api/invitations/router.py` — `_to_invitation_detail_out`,
  `_to_qr_check_in_out`, `_to_visitor_outs` resolve the new fields;
  branch/building/department lookups added (query-performance.md §1
  eager-loading applies).
- `src/vmss_api/auth/rbac_catalog.py` — new `documents:view` permission
  code; `reception`/`security` role grants updated.
- No database migration — no new columns, only new response fields
  resolved from data already stored.
