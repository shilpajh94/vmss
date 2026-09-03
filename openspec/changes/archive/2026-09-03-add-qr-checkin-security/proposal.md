## Why

The QR code issued for an invitation today just encodes the plain,
human-readable `tracking_id` — unsigned, and never validated against the
invitation's `expires_at` at check-in time. A photographed, forwarded, or
guessed code stays valid indefinitely, and an old-but-still-`approved`
invitation can be checked in long after it should have lapsed. This closes
both gaps: the QR payload becomes an authenticated-encrypted token, and
expiry is enforced as part of the normal check-in lookup rather than an
easily-forgotten extra clause.

## What Changes

- QR payload moves from the plain `tracking_id` string to a token produced
  by encrypting the invitation's `id` (authenticated encryption —
  tamper-evident, not just obfuscated) under a server-side key sourced
  from settings, reusing the same Fernet-based pattern already established
  in `core/encryption.py` rather than a new crypto primitive.
- New `invitation_qr_codes` table (tenant-scoped): one row per invitation,
  storing the exact issued token and the storage key of its rendered PNG
  (via the existing `core/storage.py` service — not a hand-built filesystem
  path), so a resent approval email or a reprinted badge reuses the same
  code instead of silently minting a new one.
- New `check_in_status` column on `Invitation` (plain string, matching the
  project's existing convention for status-like fields): `unused` →
  `checked_in` → `checked_out`. Added **parallel** to the existing `status`
  column, which keeps carrying its current `checked_in`/`checked_out`
  values unchanged — nothing that already reads `status` (including the
  "who's inside" emergency report) needs to change. Both fields are updated
  together in the same transaction by the new endpoint.
- New public endpoint,
  `PATCH /api/v2/invitations/qr/{token}/check-in`, that decrypts the
  scanned token and drives the `check_in_status` state machine directly:
  a valid scan while `unused`/`checked_out` checks the visitor in, a
  valid scan while `checked_in` checks them out — cycling for as many
  entry/exit round trips as the visitor makes (leaving for lunch, moving
  between buildings), not limited to one. No separate preview/confirm
  step — the scan itself performs the transition.
- Expiry (`Invitation.expires_at`) is validated **on every transition into
  `checked_in`** (both the first entry from `unused` and any later
  re-entry from `checked_out`); the exit transition
  (`checked_in` → `checked_out`) is never blocked by expiry, since a visit
  legitimately running past its expiry timestamp shouldn't trap someone
  who is already on-site.
- The existing manual, tracking-ID-keyed check-in path
  (`PATCH /api/v2/invitations/{trackingId}/check-in`) is unchanged — it
  remains the desk fallback for when a camera isn't available.
- The check-in response is expanded beyond today's thin `InvitationOut`
  (which carries no visitor name, host name, or `checkedInAt`) to surface
  visitor contact, resolved host name, purpose/department, the full
  submitted/approved/checked-in/checked-out timeline, `expiresAt`, and
  `checkInStatus`.
- Token generation moves to invitation-approval time (already the trigger
  for QR rendering today), producing and persisting the encrypted token and
  image once per invitation rather than regenerating on the fly per email
  send.

## Capabilities

### New Capabilities

_None — this extends the existing `invitations` capability rather than
introducing a new one; QR check-in has been part of that capability's scope
since API-11._

### Modified Capabilities

- `invitations`: the QR payload's construction (encrypted token, not plain
  tracking ID), the check-in lifecycle it drives (`check_in_status`,
  cycling between `checked_in`/`checked_out` for as many entry/exit round
  trips as the visitor makes), and expiry enforcement on every entry are
  all new or changed requirements against this capability.

## Impact

- **Code**: `src/vmss_api/invitations/models.py` (new `InvitationQRCode`
  model, new `check_in_status` column), `repository.py` (new state-machine
  queries), `service.py` (encrypt/decrypt + validation orchestration),
  `router.py` (new `router_v2` endpoint), `schemas.py` (expanded check-in
  response schema), a new `qr_token.py` module (AES-GCM encrypt/decrypt),
  `tasks.py` (persist token + image at approval instead of generating
  in-memory per email).
- **Config**: new encryption-key setting in `core/config.py`, sourced from
  `.env`, with a placeholder added to `.env.example`.
- **Database**: one `alembic_tenant` migration (new table, new column) —
  tenant-scoped, applied per tenant via the existing provisioning/upgrade
  path.
- **API contract**: additive — a new `/api/v2/invitations/qr/{token}/check-in`
  endpoint; the existing tracking-ID check-in endpoint's request shape is
  unchanged, its response gains fields (additive, non-breaking per
  `api-conventions.md` §2).
- **Frontend/app team**: consumes the new endpoint and the expanded
  response shape; confirmed via the shared requirement spec ahead of this
  proposal (single-scan-drives-state flow, per-scan `Idempotency-Key`).
