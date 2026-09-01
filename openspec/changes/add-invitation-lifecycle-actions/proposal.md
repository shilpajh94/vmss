## Why

The invitations capability today only covers create, list, approve, and the two
public tracking lookups. Everything that happens to an invitation *after* it's
submitted — a reviewer rejecting it, the visitor actually arriving and leaving,
a reschedule/expiry-extension request, badge printing at reception, and clearing
a flagged visitor for entry — has no API surface at all. A frontend gap analysis
identified 8 endpoints, all under `/invitations/{id}/...`, that the live backend
is missing and that the reception/security portal needs to complete the visitor
lifecycle it already renders screens for.

## What Changes

- Add `GET /invitations/{id}` — authenticated, branch-scoped detail view (the
  only existing by-id read is the public, tracking-ID-keyed `GET
  /invitations/track`; there is no staff-facing single-invitation lookup today).
- Add `PATCH /invitations/{id}/deny` — transitions `submitted` → `denied` with a
  mandatory reason, dispatching a denial notification. New permission
  `invitations:deny`.
- Add `PATCH /invitations/{id}/check-in` — transitions `approved` → `checked_in`,
  blocked with 409 if the invitation is watchlist-flagged and not yet overridden.
  Accepts `Idempotency-Key` (api-conventions.md §3). New permission
  `invitations:checkin`.
- Add `PATCH /invitations/{id}/check-out` — transitions `checked_in` →
  `checked_out`, closing the visit. Accepts `Idempotency-Key`. New permission
  `invitations:checkout`.
- Add `PATCH /invitations/{id}/reschedule` — changes `preferredVisitDate`/
  `preferredVisitTime` while the invitation is `submitted` or `approved` (before
  check-in). New permission `invitations:reschedule`.
- Add `PATCH /invitations/{id}/extend` — pushes `expiresAt` forward for an
  `approved` or `checked_in` visit. New permission `invitations:extend`.
- Add `POST /invitations/{id}/badge` and `POST /invitations/{id}/badge/reprint`
  — renders a printable badge (PNG: visitor name, tracking ID, QR code, expiry),
  stores it via the existing storage interface, and returns a retrieval URL.
  Reprint re-renders and increments a reprint counter; it requires a badge to
  already be issued. New permission `invitations:badge`.
- Add `POST /invitations/{id}/watchlist-override` — admin-only action that
  clears a `watchlistFlagged` invitation so check-in can proceed, recording who
  overrode it, when, and why. New permission `invitations:watchlist-override`.
  This change does **not** build automatic watchlist/blacklist matching — the
  `watchlistFlagged` column is new but nothing in this change sets it to `true`;
  that's left to a future watchlist-matching capability. The override endpoint
  and the check-in gate it unblocks are built now so the contract exists ahead
  of that feature.
- Extend `Invitation` with new columns for each of the above (denial, check-in/
  out, badge, watchlist-override timestamps/actors/reasons) and new `status`
  values (`denied`, `checked_in`, `checked_out`) — additive, no existing column
  or status value changes meaning.
- Add the 7 new permission codes to the RBAC catalog (`invitations:deny`,
  `invitations:checkin`, `invitations:checkout`, `invitations:reschedule`,
  `invitations:extend`, `invitations:badge`, `invitations:watchlist-override`)
  and grant the relevant subset to the `reception`, `security`, and `host`
  standard roles — `admin` gets all of them automatically.

None of this is a **BREAKING** change: every addition is a new endpoint, new
column, or new permission code; no existing endpoint's request/response
contract or status value's meaning changes.

## Capabilities

### New Capabilities
(none — every change below is additional behavior on the existing `invitations`
capability)

### Modified Capabilities
- `invitations`: adds the 8 lifecycle endpoints above, the new `Invitation`
  status values and columns they operate on, and the corresponding RBAC
  permission codes.

## Impact

- **Code**: `src/vmss_api/invitations/{models,schemas,service,repository,router,tasks,notifications}.py`.
- **DB**: one Alembic tenant migration (`alembic_tenant/`) adding the new
  `invitations` columns.
- **RBAC**: `src/vmss_api/auth/rbac_catalog.py` — new permission codes and role
  grants; existing tenants get backfilled via `seed_default_roles`'s existing
  union-merge behavior.
- **Docs**: `docs/features/invitations.md` gains the 8 new endpoints.
- **No dependency changes**: badge rendering reuses `qrcode[pil]` (already a
  dependency via `invitations/qr.py`) and Pillow for compositing — no new
  library added.
