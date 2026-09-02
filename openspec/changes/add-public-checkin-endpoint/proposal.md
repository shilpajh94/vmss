## Why

`PATCH /api/v1/invitations/{id}/check-in` requires a staff bearer token
(`invitations:checkin`) and the invitation's internal UUID `id`. That fits a
reception desk operating the check-in on a visitor's behalf, but not a kiosk
or the visitor's own device checking themselves in by scanning the QR/badge
that already encodes the human-readable `tracking_id` (`INV-XXXXXXXX`) — the
visitor has no staff credential and no UUID, only the tracking code. Today
there is no self-service check-in path at all; a visitor arriving at an
unstaffed gate cannot complete a visit already `approved` without a staff
member manually looking them up.

## What Changes

- **BREAKING**: `PATCH /api/v1/invitations/{id}/check-in` is deprecated per
  `api-conventions.md` §2 — `Deprecation` response header, a note with target
  removal date in `docs/features/invitations.md`, kept fully functional for
  existing staff/portal clients during the migration window. Its behavior,
  auth (`invitations:checkin` bearer token), and UUID `id` param are
  unchanged.
- New `PATCH /api/v2/invitations/{trackingId}/check-in` — public,
  unauthenticated, rate-limited (`slowapi`, keyed by IP + endpoint, mirroring
  `GET /invitations/track`'s `20/minute`). Looks the invitation up by its
  `tracking_id` instead of its UUID `id`. Otherwise preserves the existing
  transition semantics: `approved` → `checked_in` only, 409 if not
  `approved`, 409 if `watchlistFlagged` and not yet overridden, `Idempotency-Key`
  supported.
- First `/api/v2` route in the API — introduces the `/api/v2` mount
  alongside `/api/v1` (`main.py`), scoped to this one endpoint for now, not a
  wholesale re-exposure of every `v1` route under `v2`.
- Audit logging for the new route records the check-in with `actor_user_id =
  None` (same nullable-actor pattern the walk-in registration flow already
  uses for unauthenticated writes) rather than omitting the audit trail.
- Tenant resolution for the new route reuses the existing
  `track_default_tenant_db` single-default-tenant fallback
  (`invitations/deps.py`) that `GET /invitations/track` already relies on,
  since a public, tokenless request has no JWT `tenant_id` claim to resolve
  from.

## Capabilities

### New Capabilities
(none — this extends the existing `invitations` capability)

### Modified Capabilities
- `invitations`: adds a second, public/unauthenticated check-in path keyed by
  `tracking_id`; deprecates (does not remove) the existing staff-authenticated,
  UUID-keyed check-in path.

## Impact

- `src/vmss_api/invitations/router.py` — add the `/api/v2` check-in route;
  add `Deprecation` header to the existing `v1` route.
- `src/vmss_api/invitations/service.py` — new service function checking in an
  invitation resolved by `tracking_id` (reuses the same 409/watchlist rules as
  `check_in_invitation`).
- `src/vmss_api/invitations/deps.py` — reuse `track_default_tenant_db` for the
  new route's tenant resolution.
- `src/vmss_api/api.py`, `src/vmss_api/main.py` — mount `/api/v2`.
- `src/vmss_api/auth/audit.py` — no code change; confirms `actor_user_id: None`
  is already a supported call shape.
- `docs/features/invitations.md` — document the new public route, and the
  `v1` route's deprecation note + removal date.
- `openspec/specs/invitations/spec.md` — this capability's check-in
  requirement is currently only staged in the unarchived
  `add-invitation-lifecycle-actions` change, not yet synced into the main
  spec. This change's delta spec is written against that staged requirement
  text (the accurate current behavior) rather than against an absent main-spec
  entry; reconciling the two changes' archival order is a pre-existing gap in
  this repo's OpenSpec bookkeeping, not something this change resolves.
- Tests: `tests/` — new permission-free (no `invitations:checkin`) happy-path
  and 409 cases for the `v2` route; existing `v1` tests unchanged plus one
  assertion that the `Deprecation` header is present.
