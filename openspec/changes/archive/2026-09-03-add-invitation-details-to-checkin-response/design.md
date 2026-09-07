## Context

See `proposal.md` - Why. Relevant existing state:

- `Invitation.visitors`/`Invitation.vehicles` are `lazy="raise"`
  relationships (`invitations/models.py`) — a forgotten eager-load fails
  loudly instead of silently serializing an empty list
  (`query-performance.md` §1).
- `router.py::check_in_invitation` currently fetches via
  `service.get_invitation(tenant_db, invitation_id)` — a plain fetch, no
  eager-loading — then calls `service.check_in_invitation`, which delegates
  to `_perform_check_in`. That function's actual state transition is
  `InvitationRepository.check_in_if_eligible`, an atomic
  `UPDATE ... RETURNING Invitation` (`repository.py:118-147`) that re-checks
  `status`/`watchlist_flagged` in the `WHERE` clause to close a
  read-then-write race. The `Invitation` instance the caller ultimately
  serializes is whatever this `RETURNING` call hands back, not the object
  from the initial fetch.
- This exact eager-load-then-atomic-update sequencing was already solved
  for the token-based QR check-in
  (`2026-09-03-qr-checkin-full-registration-detail`): `check_in_by_qr_token`
  fetches via `InvitationRepository.get_with_children` (which populates
  `visitors`/`vehicles` into the session's identity map for that row)
  *before* calling its own `UPDATE ... RETURNING`
  (`check_in_by_qr_if_eligible`). Because both calls resolve the same
  primary key within the same session, SQLAlchemy merges the `RETURNING`
  row's columns into the already-identity-mapped instance rather than
  handing back a fresh, relationship-empty one — the previously eager-loaded
  `visitors`/`vehicles` collections survive untouched. That change shipped
  and is in production use, so the technique is proven, not speculative.
- `service.get_invitation_detail` already exists and is exactly this
  eager-loaded fetch (`InvitationRepository.get_with_children` plus a 404
  check) — currently used only by `GET /invitations/{id}`.

## Goals / Non-Goals

**Goals:**
- Get `PATCH /api/v1/invitations/{id}/check-in`'s success response to the
  field set confirmed with the requester (matches `InvitationTrackingOut`,
  additive on top of today's `InvitationOut` fields), without a second
  query round-trip or a `MissingGreenlet`/lazy-load error.

**Non-Goals:**
- Changing the state machine, watchlist gate, idempotency behavior, or
  deprecation status of this endpoint — response payload only.
- Touching `InvitationOut` itself, or any other endpoint that returns it
  (`POST /invitations`, `PATCH /{id}/deny`, the tracking-ID and walk-in
  paths) — see proposal.md's Impact for why those are explicitly out of
  scope here.
- Adding `checkedInAt`/`checkedOutAt` or primary-contact email/phone the
  way the QR response has them — the requester asked specifically for the
  tracking-lookup shape, which doesn't carry those fields, and staying
  additive-only on top of it avoids inventing fields nobody asked for.

## Decisions

### New schema `InvitationCheckInOut`, not a widened `InvitationOut`
`InvitationOut` backs five other response paths today. Widening it would
change all of their payloads too — silently expanding scope past what was
confirmed. A dedicated schema, scoped to this one route, keeps the change
additive and contained, matching how `InvitationQrCheckInOut` was already
kept separate from `InvitationTrackingOut` for the same reason (schemas.py's
own docstring on `InvitationDetailOut` makes the same "deliberately a
separate schema" call for the public/staff split).

**Alternative considered**: add the new fields as `| None = None` directly
on `InvitationOut`. Rejected — every other consumer of `InvitationOut`
would need to either populate them or be reviewed as intentionally leaving
them `null`, which is exactly the kind of scope creep the requester didn't
ask for.

### Reuse `service.get_invitation_detail`, not a new eager-load method
`check_in_invitation`'s router function swaps its initial
`service.get_invitation(tenant_db, invitation_id)` call for
`service.get_invitation_detail(tenant_db, invitation_id)` — already the
`get_with_children`-backed eager-loaded fetch `GET /invitations/{id}` uses,
and the same technique `check_in_by_qr_token` already relies on (see
Context). No new repository or service method. `authorize_branch_id_
tolerant` only needs `.branch_id`, which the eager-loaded fetch carries the
same as the plain one, so the swap is transparent to the authorization
check that runs between the fetch and the check-in call.

**Alternative considered**: re-fetch with children *after*
`check_in_invitation` returns, as a second query. Rejected — an unnecessary
round-trip when the identity-map behavior already makes the single
eager-loaded fetch sufficient (proven by the QR path), and it would leave a
window where the second fetch could observe a different row than the one
that was just transitioned (e.g. a concurrent checkout) — a mismatch the
existing atomic `UPDATE ... RETURNING` doesn't have.

`service.get_invitation_detail`'s docstring currently says it backs only
`GET /invitations/{id}` — update it to note the check-in route as a second
caller, rather than forking a same-shaped method under a different name.

### Response mapper mirrors `_to_tracking_out`, not `_to_qr_check_in_out`
The new `_to_check_in_out` (or similarly named) mapper in `router.py`
populates `InvitationCheckInOut` the same field-by-field way
`_to_tracking_out` already does for `InvitationTrackingOut` — same source
attributes, same `InvitationVisitorOut`/`InvitationVehicleOut` list
comprehensions — since the target shape is explicitly "match the tracking
lookup," not the QR endpoint's shape (which additionally carries
`checkInStatus`/`checkedInAt`/`checkedOutAt`/primary-contact email+phone
that this change deliberately excludes, per Non-Goals).

## Risks / Trade-offs

- **One extra join per check-in call**: `get_invitation_detail` issues
  `selectinload` queries for `visitors`/`vehicles` even for the common
  individual-registration-with-no-vehicles case — a small, bounded cost
  (indexed FK lookups, typically empty results), the same cost the
  tracking lookup and QR check-in already pay on every call. Not worth a
  conditional/lazy variant for this one endpoint.
- **Two authenticated response schemas now describe overlapping fields**
  (`InvitationCheckInOut` and `InvitationTrackingOut`) with no shared base
  class → future field additions to one could drift from the other.
  Accepted for now, consistent with how `InvitationQrCheckInOut` already
  duplicates rather than inherits; introducing a shared base is a
  larger refactor than this change's scope and would touch the other,
  explicitly-out-of-scope endpoints too.
