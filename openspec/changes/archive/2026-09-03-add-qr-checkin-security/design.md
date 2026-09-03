## Context

See `proposal.md` - Why for the motivation (unsigned QR payload, no expiry
enforcement at check-in). Relevant existing state:

- `Invitation.status` (plain string) already carries both the approval
  workflow (`submitted`/`approved`/`denied`) and the check-in lifecycle
  (`checked_in`/`checked_out`), set by the existing tracking-ID check-in
  path (`invitations/repository.py`, `check_in_if_eligible` /
  `check_out_if_checked_in`).
- The public check-in endpoint
  (`PATCH /api/v2/invitations/{trackingId}/check-in`) resolves its tenant
  via `track_default_tenant` — a hardcoded single-tenant shortcut, not a
  claim carried by the request. This is pre-existing behavior this change
  does not fix (see Decisions).
- `expires_at` exists on `Invitation` today but is only used by the
  reschedule/extend action — never checked at check-in.
- QR rendering (`invitations/qr.py::generate_qr_png`) happens on the fly
  inside the approval-notification Celery task (`invitations/tasks.py`),
  keyed off the plain `tracking_id`, and the image is discarded after the
  email send.
- `core/storage.py` already provides a backend-agnostic
  `save(tenant_id, category, content, content_type) -> key` /
  `url_for(key)` pair (local disk in dev, S3 in prod), used today for
  ID-proof uploads and badge images.
- `core/encryption.py` already provides Fernet-based authenticated
  encryption for "encrypt now, decrypt later" secrets (used today for SSO
  client secrets), with its own docstring stating that a future feature
  needing the same guarantee should reuse the pattern rather than invent
  its own scheme.

## Goals / Non-Goals

**Goals:**
- Make the QR payload tamper-evident and stop it from encoding anything
  human-readable.
- Enforce `expires_at` on the entry transition without touching the exit
  transition's behavior.
- Give the scanning client one action (scan) that carries the visitor
  through any number of entry/exit cycles over the course of one visit —
  a visitor may leave and return (lunch, a multi-building site) more than
  once before their invitation expires.
- Expand the check-in response so the frontend doesn't need a second
  lookup for visitor/host/time detail.

**Non-Goals:**
- Fixing the default-tenant shortcut in tenant resolution — out of scope
  per the confirmed decision to encrypt only `invitation_id` (not
  `tenant_id`) for this release.
- Reconciling `check_in_status` with the existing `status` column into a
  single field — they stay parallel per the confirmed decision; a future
  change may consolidate them.
- Adding real scheduled visit start/end times — expiry validation uses
  the existing `expires_at` only, per the confirmed decision.
- Changing the manual, tracking-ID-keyed check-in path — it is untouched.

## Decisions

### Token construction: Fernet authenticated encryption over `invitation_id` only
Authenticated encryption (confidentiality + tamper detection) over a
signature-only scheme (e.g. HMAC of the plaintext id) because the token
should not leak the invitation id in the clear either — an HMAC-signed
plaintext id is verifiable but still readable.

Implemented via the `cryptography` package's `Fernet`, reusing the exact
pattern already established in `core/encryption.py` (built for "encrypt
now, decrypt later" secrets, with its own docstring inviting reuse rather
than a per-feature ad hoc scheme) — not a bespoke AES-GCM module. Fernet
already gives tamper detection (`InvalidToken` on any modified ciphertext)
and URL-safe base64 output with no extra encoding step, and has an
established rotation path (`MultiFernet`) if one is ever needed.

`invitations/qr_token.py` mirrors `core/encryption.py`'s shape (an
`lru_cache`d `Fernet` instance, a `NotConfigured`-style error when the key
is unset) but is keyed by its own dedicated setting
(`qr_token_encryption_key`), not the existing `sso_encryption_key` —
deliberately not sharing key material with SSO client-secret encryption,
so rotating one secret's key for a security incident doesn't silently
invalidate every outstanding, unscanned QR code (or vice versa). This is
the "reuse the scheme, not the key" reading of `core/encryption.py`'s
reuse invitation.

Payload is `invitation_id` alone, not `(tenant_id, invitation_id)` —
confirmed decision, accepting that this inherits the existing
default-tenant resolution shortcut rather than fixing it now. The
encryption key lives in `settings` (`core/config.py`), sourced from
`.env`, with a placeholder entry added to `.env.example` (same posture as
`sso_encryption_key`: unset by default, fails loudly the first time it's
actually used rather than silently no-op'ing).

**Alternatives considered**:
- A bespoke AES-256-GCM module with a custom nonce and key-id byte for
  future rotation. Rejected once `core/encryption.py` was found — it
  already solves tamper-evident, reversible encryption for this codebase,
  and a second, parallel crypto primitive would contradict its own stated
  purpose.
- A random opaque token stored in a lookup table (no encryption,
  DB-authenticated instead of crypto-authenticated). Rejected because it
  reopens the expiry-sync problem this change is trying to close — a
  stored token needs its own validity bookkeeping kept in sync with
  `Invitation.expires_at`, whereas decrypting straight to `invitation_id`
  and reading `expires_at` live has exactly one source of truth.

### `check_in_status` kept parallel to `status`, not merged
Confirmed decision. `status` keeps transitioning exactly as it does today
via the existing tracking-ID endpoint; the new QR endpoint updates both
`status` and `check_in_status` together in the same transaction, so
`status`-based consumers (the "who's inside" emergency report, in
particular) stay correct without being touched. `check_in_status` is the
QR endpoint's own gate condition (`unused`/`checked_in`/`checked_out`);
`status` remains the gate condition for the existing tracking-ID endpoint.
Implemented as a plain `String` column, matching the existing convention
on `status` (documented there as deliberate — avoids an `ALTER TYPE`
migration for a native Postgres enum).

**Alternative considered**: retire `status`'s checked_in/checked_out
values in favor of `check_in_status` everywhere. Rejected for this change
because it touches every existing reader of `status` (flagged, not
executed, per the confirmed decision) — a candidate for a dedicated
follow-up change.

### No independent `expires_at` on `InvitationQRCode`
The new table stores the issued token and its image storage key only.
Expiry is always read live from `Invitation.expires_at` at scan time.
This is a direct consequence of the confirmed expiry decision and avoids
the sync bug a duplicated `expires_at` would introduce (e.g. the existing
reschedule/extend action would otherwise need to remember to update a
second row).

### QR image storage via the existing `core/storage.py` service
Uses `save(tenant_id, category=f"invitations/{invitation_id}/qr", ...)`
rather than a hand-built `public/images/...` filesystem path, so dev
(local disk) and prod (S3) behave the same way this already does for
ID-proof and badge uploads, and so no code reads or writes a client- or
caller-influenced path (`file-upload-handling.md` §3).

### Single-scan state machine, no separate preview endpoint
Confirmed via the shared frontend requirement spec: the scan itself
performs the transition (`unused`→`checked_in`→`checked_out`); there is no
separate "preview details, then confirm" step. This keeps the endpoint
surface to one new route:
`PATCH /api/v2/invitations/qr/{token}/check-in`.

### `checkInStatus` cycles indefinitely; `checked_out` is not terminal
Corrected after review: the initial design treated `checked_out` as a
dead end (a third scan rejected 409 "already completed"), assuming a
visit is exactly one entry and one exit. That's wrong — a visitor
legitimately has multiple entry points during a single visit (leaving for
lunch and returning, moving between buildings on a multi-building site),
so `checked_out` must behave exactly like `unused` as far as the next
scan is concerned: both mean "currently outside," and either transitions
to `checked_in` on a valid scan (subject to the same expiry check as any
other entry). The distinction between `unused` and `checked_out` is kept
only for what it records (never entered vs. entered-and-left at least
once), not for how the gate behaves — there is no longer any
`checkInStatus` value that rejects a scan outright; every value has a
defined next transition, bounded only by the invitation's own expiry.

**Scope note**: this cycling behavior applies to the QR endpoint only.
The existing manual, tracking-ID-keyed check-in/check-out endpoints
(`v1`/`v2`) are unchanged and remain single-round-trip — their own
repository methods (`check_in_if_eligible`, gated on `status ==
"approved"`) don't admit a `checked_out` row back to `checked_in`. A
visitor whose QR check-in has cycled past one round trip is only
re-admittable via the QR endpoint, not the manual one. Reconciling that
asymmetry is out of scope here; flagged as a candidate for whichever
change eventually reconciles `status`/`check_in_status` (see "kept
parallel to status, not merged" above).

### Token generation moves to approval time, persisted
Today's QR is regenerated in-memory per notification send. This change
generates the token and image once, when the invitation becomes
`approved`, and persists both (`InvitationQRCode`) — so a resent
notification or a badge reprint reuses the same issued code instead of a
new one each time, satisfying the new "token is generated once" spec
requirement.

## Risks / Trade-offs

- **Key management**: losing or rotating `qr_token_encryption_key`
  invalidates every outstanding, unscanned QR code. Mitigation: Fernet has
  an established multi-key rotation path (`MultiFernet`) if this is ever
  needed — not built now (single key, per the confirmed scope), but
  available without a token-format break, unlike a bespoke scheme would
  require.
- **Default-tenant shortcut persists**: encrypting only `invitation_id`
  (confirmed decision) means this change does not close the existing
  single-tenant assumption in the public check-in path. Mitigation: none
  for this change — explicitly flagged as inherited, not introduced, and
  should be revisited before a second tenant is provisioned.
- **Two status fields to reason about**: `status` and `check_in_status`
  both partially describe "is this visitor on-site." Mitigation: only the
  QR endpoint writes `check_in_status` as its gate; both endpoints keep
  `status` updated identically to today, so no existing reader's behavior
  changes.
- **`checkedInAt`/`checkedOutAt` reflect only the latest cycle**: with
  cycling, these single-value columns on `Invitation` get overwritten on
  every re-entry/re-exit, so the row itself only ever shows the most
  recent one. Mitigation: full history isn't lost — the audit log already
  writes one entry per scan (`invitation_qr_checked_in`/
  `invitation_qr_checked_out`, task 7.1), so a complete in/out history is
  reconstructable from there if it's ever needed; no new column/table
  added for this.
- **Idempotency-Key reuse across scans**: because the same token drives
  both entry and exit, a scanning client that reuses one `Idempotency-Key`
  across both physical scans would get the exit request incorrectly
  deduped against the entry response. Mitigation: documented as a client
  contract in the shared frontend spec (fresh key per physical scan);
  worth a defensive check in the endpoint (reject/ignore an
  `Idempotency-Key` reused across a status transition) if this proves
  error-prone in practice — not required for the initial implementation.

## Migration Plan

- One `alembic_tenant` migration: new `invitation_qr_codes` table, new
  `Invitation.check_in_status` column (default `unused`, backfilled for
  existing rows). Tenant-scoped, applied per tenant via the existing
  provisioning/upgrade-all-tenants path (`database-architecture.md` §5) —
  no global-schema change.
- No backward-compatibility shim needed for previously issued QR codes:
  no QR content has ever been persisted before this change (today's QR is
  generated in-memory and discarded), so there is nothing in the field to
  migrate or invalidate.
- Rollback: drop the new table/column; the existing tracking-ID check-in
  path is unaffected either way since it doesn't read either.
