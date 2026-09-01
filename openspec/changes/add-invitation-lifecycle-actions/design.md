## Context

`invitations/models.py::Invitation.status` is a plain string, already
documented as staying that way "for future values (`cancelled`/`expired`)".
`invitations/router.py`'s existing `approve_invitation` establishes the
pattern every new by-id action below follows: fetch via
`service.get_invitation` (404 if missing) → `authorize_branch_id_tolerant(...,
permission_code, invitation.branch_id)` (403 if unauthorized) → an atomic
conditional `UPDATE ... WHERE status = X RETURNING *` in the repository (409 if
the row wasn't in the expected state) → commit → `background_tasks.add_task`
for the audit log → enqueue a Celery notification task if applicable. See
proposal.md for why these 8 endpoints are needed and what user-selected
answers fixed their scope (extend `invitations` in place; badge is a rendered
PNG; watchlist-override is override-only, no matching logic).

## Goals / Non-Goals

**Goals:**
- Add all 8 endpoints as new routes on the existing `invitations` router
  (prefix stays `/invitations`), reusing `InvitationRepository`/`service.py`.
- Keep every new mutation an atomic conditional `UPDATE`, matching
  `approve_if_submitted`'s concurrency-safety pattern — no read-then-write
  race on `status`.
- Reuse `qr.py`'s QR generation for badges; add Pillow-based compositing only
  (Pillow is already present transitively via `qrcode[pil]`).

**Non-Goals:**
- No automatic watchlist/blacklist matching (proposal.md's explicit scope
  boundary) — `watchlistFlagged` is set by nothing in this change; it exists
  so the override endpoint and the check-in gate have something to operate on
  ahead of that future capability.
- No new top-level `checkin` package — project-rules.md reserves that name for
  a future dedicated capability (e.g. overstay detection across all visits,
  gate/RFID integration), but these specific 8 endpoints are URL- and
  data-scoped to a single `Invitation` row, so they stay in the feature that
  already owns that table.
- No hardware/printer integration — "print" means "render and store an image
  a reception device can retrieve and send to its own printer," not a
  server-to-printer protocol.

## Decisions

### 1. New `Invitation` columns, all additive

```python
# status: existing String(20) column — three new values used by this change,
# alongside the existing "submitted"/"approved":
#   "denied", "checked_in", "checked_out"

denial_reason: Mapped[str | None] = mapped_column(String(500))
denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
checked_in_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
checked_out_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))

badge_number: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
badge_storage_key: Mapped[str | None] = mapped_column(String(500))
badge_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
badge_reprint_count: Mapped[int] = mapped_column(Integer, default=0)

watchlist_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
watchlist_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
watchlist_override_reason: Mapped[str | None] = mapped_column(String(500))
watchlist_override_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
```

One Alembic tenant migration adds all of them together (`database-architecture.md`
§5) — they're one logical change, not eight separate migrations.

**Alternative considered**: a separate `InvitationLifecycleEvent` audit table
(one row per transition) instead of flat columns. Rejected for this change —
`AuditLog` (security-architecture.md §5) already records every mutation with
actor/timestamp/entity; a parallel per-transition table on top of that would
duplicate what `AuditLog` exists to do, for no query this API needs today
(nothing asks "show me the history of status changes," only "what is the
current state"). Revisit if that reporting need shows up.

### 2. `GET /invitations/{id}` gets its own response schema, not `InvitationTrackingOut`

`InvitationTrackingOut` (the public tracking-by-ID shape) deliberately excludes
`branchId`, `createdByUserId`, and now must also exclude badge/watchlist
internals from an unauthenticated caller. A new `InvitationDetailOut`
(`CamelModel`) carries everything `InvitationTrackingOut` does plus `id`,
`branchId`, `source`, `createdByUserId`, and every new lifecycle field. Two
schemas, not one flag-driven schema, for the same reason
`database-architecture.md` §4 requires separate request/response schemas per
direction — a public and a staff-only view of the same row are different
contracts that happen to overlap, not one contract with a visibility toggle.

### 3. Badge rendering: PNG via Pillow, not a new PDF library

The recommended option from the proposal review said "PDF or PNG" — PNG is
chosen specifically because `qrcode[pil]` already pulls in Pillow, so
compositing a QR code plus text onto a canvas needs no new dependency
(`project-rules.md`'s "bump deliberately" — adding `reportlab`/`weasyprint`
for one feature is exactly the kind of dependency creep that rule guards
against). `storage.py`'s `_ALLOWED_CONTENT_TYPES` already includes
`image/png`, so `storage.save(..., content_type="image/png")` needs no
change. Rendering happens in a new `invitations/badge.py` (mirroring
`qr.py`'s shape: a pure `_render_png` function wrapped in an
`anyio.to_thread.run_sync` call per `fastapi-architecture.md` §4), reusing
`qr.py::generate_qr_png` for the QR portion rather than duplicating QR
generation.

### 4. Badge number format and reprint semantics

`BDG-XXXXXXXX` (8 hex chars), generated the same way
`_generate_unique_tracking_id` generates `INV-XXXXXXXX` — a short retry loop
against a uniqueness check, not a sequence table. Reprint keeps the same
`badge_number` (it identifies the *visit*, not the physical printout) but
writes a new `badge_storage_key` each time (the rendered image is regenerated
from current data — see spec.md "Reprint reflects data changed since original
issuance") and increments `badge_reprint_count`. The old storage object is not
deleted; storage cleanup for orphaned keys is out of scope here, same as
nothing today prunes stale ID-proof uploads.

### 5. Permission codes: one per action, following the existing `invitations:*` grain

`invitations:create/view/approve/cancel` are already four separate codes for
four separate actions on the same table — the new actions follow the same
grain rather than introducing a coarser "manage" code:

| Code | Granted to (beyond `admin`) |
|---|---|
| `invitations:deny` | `reception`, `host` (the same roles that hold `invitations:approve` today — denial is the other branch of the same decision) |
| `invitations:checkin` | `security` (gate-facing role) |
| `invitations:checkout` | `security` |
| `invitations:reschedule` | `reception`, `host` |
| `invitations:extend` | `reception`, `host` |
| `invitations:badge` | `reception` (badge printing is a front-desk action) |
| `invitations:watchlist-override` | *(admin only — no other standard role, matching the image's "Admin override for a flagged visitor")* |

`seed_default_roles`'s existing union-merge backfill (already handling this
exact situation for `invitations:create` per its own docstring) picks these up
for tenants provisioned before this change with no extra migration work.

### 6. Idempotency-Key scope

Per `api-conventions.md` §3, check-in and check-out — the two actions a flaky
reception/gate device network genuinely retries — accept `Idempotency-Key`,
cached with the same `_idempotency_cache_key`/`_cached_response`/
`_cache_response` helpers `router.py` already defines for `POST /invitations`
(reused as-is; the cache key is already namespaced per `(tenant_id,
idempotency_key)`, and a client is expected to use a distinct key per logical
action). Badge issuance also accepts it (issuing a badge is a "do this once"
action with the same retry risk as invitation creation). Reprint, deny,
reschedule, extend, and watchlist-override do not: each is either naturally
safe to retry (reschedule/extend just reset the same target values; reprint's
whole purpose is repeatability) or already guarded by the same conditional-
`UPDATE`-plus-409 pattern `approve_invitation` relies on today without
`Idempotency-Key` (deny, watchlist-override).

### 7. Denial notification reuses the `tasks.py`/`notifications.py` dispatch shape

A new `send_denial_notification` task, structurally identical to
`send_tracking_notification` (tenant-schema-scoped session, `request_id`
context binding, same `_RETRY_KWARGS`, same `_dispatch` helper routing on
`preferred_contact_method`) — the only difference is the subject/body text and
including the denial reason. No new dispatch infrastructure.

## Risks / Trade-offs

- **[Risk]** Flat status-transition columns on `Invitation` (Decision 1) don't
  capture a *history* of transitions if an invitation is somehow reopened.
  → **Mitigation**: `AuditLog` already captures every transition's actor/
  timestamp/entity; a history view can be built from that later without a
  schema change here.
- **[Risk]** `watchlist_flagged` has no setter in this change, so it can only
  be exercised in tests via direct repository/factory manipulation, not
  through any API call.
  → **Mitigation**: this is the deliberate scope boundary from proposal.md;
  the future watchlist-matching capability is expected to set it (e.g. at
  `create_invitation` time), and this change's tests construct flagged rows
  directly via the test factory per `testing-standards.md` §1.
- **[Risk]** Badge PNG rendering adds Pillow-level image-compositing code
  (font metrics, layout) that has no precedent in this codebase yet.
  → **Mitigation**: kept deliberately simple (fixed layout, one bundled
  font, no per-tenant branding) — a template/branding system is future work,
  not blocking this change's scope.

## Migration Plan

1. Alembic tenant migration adding the new `invitations` columns (nullable/
   defaulted, so it's backward compatible with existing rows — every existing
   invitation simply has `watchlist_flagged=false` and every new field `NULL`).
2. Add the 7 permission codes + role grants to `rbac_catalog.py`; existing
   tenants pick them up via `seed_default_roles`'s union-merge on next call
   (already how `invitations:create` was backfilled historically per that
   function's own docstring) — no separate backfill script needed.
3. Ship code + migration together; no phased rollout needed since every new
   endpoint is additive (no existing client can be calling them yet).
4. Rollback: revert the migration (`alembic downgrade`) and the code together
   — no data migration to reverse, since no existing column's meaning changed.
