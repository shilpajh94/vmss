## Context

See `proposal.md` - Why. Relevant existing state:

- `Invitation.visitors`/`Invitation.vehicles` are `lazy="raise"`
  relationships (`invitations/models.py`) — deliberately so a forgotten
  eager-load fails loudly instead of silently serializing an empty list
  (`query-performance.md` §1).
- `service.py::check_in_by_qr_token` currently fetches the invitation via
  `InvitationRepository(tenant_db).get(invitation_id)` — a plain fetch,
  no eager-loading. It has never touched `.visitors`/`.vehicles`, so this
  has never mattered until now.
- `InvitationRepository._with_children()` (used by `get_with_children`,
  backing the existing tracking lookup and staff detail view) already
  eager-loads both via `selectinload` — the exact loading this endpoint
  now needs too.

## Goals / Non-Goals

**Goals:**
- Expand the QR check-in response to the field set confirmed with the
  requester (matches `InvitationTrackingOut`), without a second query
  round-trip or a `MissingGreenlet`/lazy-load error.

**Non-Goals:**
- Changing what the request accepts, the state machine, expiry, or
  watchlist behavior — response payload only.
- Adding `currentApprovalStep` — always `null` post-approval, not worth
  the field (see proposal.md).

## Decisions

### Reuse `InvitationRepository.get_with_children`, not a new eager-load method
`check_in_by_qr_token` switches from `.get(invitation_id)` to
`.get_with_children(invitation_id)` — the same method the tracking
lookup and staff detail view already use, rather than writing a new
QR-specific eager-loading query. One eager-loading shape for "callers
that serialize visitors/vehicles" is easier to keep correct than a
second, parallel one that could drift.

**Alternative considered**: a QR-specific repository method with its own
`selectinload` call. Rejected — no QR-specific filtering/shape is needed
here that `get_with_children` doesn't already provide; a second method
would just be `_with_children()` copied, not a real distinction.

## Risks / Trade-offs

- **One extra join per scan**: `get_with_children` issues `selectinload`
  queries for `visitors`/`vehicles` even for the (common) individual
  registration with zero vehicles — a small, bounded cost (indexed FK
  lookups, typically empty results), consistent with what the tracking
  lookup already pays on every call. Not worth a conditional/lazy variant
  for this endpoint alone.
