## Context

The task list is the parent "Badge Printing Flow" with 15 subtasks across four iterations. Findings from the codebase that shape the design:

- A "visit" is an `Invitation` row. There is no separate visits table, so `{visit_id}` in the new routes is an invitation id.
- `invitations/` already has a PNG badge (`badge.py`, `POST /invitations/{id}/badge`, `invitations:badge`), an encrypted invitation QR token (`qr_token.py`, Fernet, `QR_TOKEN_ENCRYPTION_KEY`), check-in/out by token and by SMS check-in code, and an `Idempotency` dependency (`core/idempotency.py`). All of it stays untouched.
- `Tenant` is a global-schema row (`tenants`). It has a read-only `GET /tenants/me` and no write path or settings.
- There is no "ID verified" signal on an invitation; there is an ID-proof type/document and a photo storage key.
- Permissions live in `auth/rbac_catalog.py` and earlier changes granted new codes to existing roles through migrations.
- Rate limiting is slowapi (`core/rate_limit.py`); audit writes use `record_audit_log` from a `BackgroundTasks` task.

## Goals / Non-Goals

**Goals:**
- Ship the whole flow dark behind two flags, with zero behavior change when off.
- A badge QR that is generated at reception, day-bound, signed, and revocable.
- New code lives in `checkin/`; edits to existing modules are limited to flag wiring, permission catalog, and one notification branch.

**Non-Goals:**
- No change to the existing PNG badge, invitation QR token, or existing check-in/out endpoints.
- No physical print-spooler integration; the API returns a PDF and the client prints it.
- No per-tenant badge branding or templates.
- No kiosk self-service printing.

## Decisions

**1. Two flags, AND-ed.** `BADGE_PRINT_FLOW_ENABLED` is the deploy-level kill switch (default off); `tenants.badge_print_flow_enabled` is the rollout toggle. A dependency `require_badge_print_flow` (in `core/deps.py`, resolved after `get_tenant`) raises `404` unless both are true. `404`, not `403`, so a disabled flow is indistinguishable from a route that does not exist. Alternative of tenant-only rejected: no way to disable everywhere in an incident.

**2. Tenant toggle on the global `tenants` table, not a tenant-schema settings table.** The flag is read before a tenant session exists (`get_tenant` is step 2 of the resolution chain), and `Tenant` is already the one place per-tenant config lives. Needs a **global** Alembic migration (`alembic/`), default `false`, `server_default` set so existing rows backfill. Edit via new `PATCH /tenants/me/settings` guarded by new `tenants:update` (Admin). Tenant is resolved from the token. Audited to the platform/tenant audit path already used by tenant admin changes.

**3. Package `checkin/`.** `router.py`, `service.py`, `schemas.py`, `models.py` (`BadgePrint`), `repository.py`, `badge_pdf.py`, `badge_token.py`, `tasks.py` only if a Celery task is needed (a FastAPI `BackgroundTasks` audit write is the project norm, so likely none). It reads `Invitation` through its own repository queries; it does not import invitation services. Search reuses the existing query building by calling the invitation repository's read-only search helper where one fits (`repository.py` around the `search` filter), otherwise a new read-only query in `checkin/repository.py`. Exact-match fields (`tracking_id`, `checkin_code`) never use `LIKE`. Phone matching uses the same digits-only normalizer the phone lookup uses.

**4. "OTP" in search means the numeric check-in code** (`Invitation.checkin_code`, sent by SMS), not the identity-verification OTP, which is Redis-only and single-use. Assumption recorded; confirm with product.

**5. ID verification is an explicit reception act.** New nullable `id_verified_at` and `id_verified_by_user_id` on `invitations` (tenant migration, additive), set by `POST /checkin/{visit_id}/verify-id`. Chosen over deriving it from "ID document uploaded", because uploading is not the same as a human checking the physical ID.

**6. PDF via Pillow, no new dependency.** The renderer composes the badge as an image (reusing `invitations/qr.py::generate_qr_png` read-only for the QR) and saves it as PDF with `Image.save(format="PDF")`, executed with `anyio.to_thread.run_sync`. Alternative `reportlab` gives vector text but adds a dependency; revisit if print quality is poor. The photo is fetched from object storage through the existing storage interface, never written to local disk.

**7. Badge token: signed, day-bound, with `jti`.** A new module `checkin/badge_token.py` issues a PyJWT token (HS256) signed with a new `BADGE_TOKEN_SECRET` setting (separate from `QR_TOKEN_ENCRYPTION_KEY`, so rotating one does not invalidate the other). Claims: `sub` (visit id), `tid` (tenant id), `day` (visit local date in tenant timezone, ISO), `jti`, `exp` (end of that local day plus a small grace), `typ="badge"`. Verification checks signature, `typ`, `tid` equals the resolved tenant, `day` equals today in the tenant timezone, and that a `badge_prints` row with that `jti` is active. Every failure returns the same generic invalid-token error (matches `decrypt_invitation_token`'s contract). The scan endpoints are unauthenticated-by-JWT but the tenant is taken from the token's `tid` claim after signature verification, never from a request field (`security-architecture.md` §1). New setting goes in `config.py`, `.env.example` and docs.

**8. `badge_prints` is append-only.** Columns: `id`, `visit_id` (FK `invitations.id`), `printed_by_user_id`, `printed_at`, `jti` (unique), `active`, `reprint_reason`, `created_at`. No `deleted_at` (append-only, `database-architecture.md` §4). The one allowed mutation is `active: true -> false`, done by a guarded `UPDATE ... WHERE jti = :jti AND active`. A partial unique index on `(visit_id) WHERE active` guarantees at most one active badge per visit, which also makes concurrent double-print fail cleanly.

**9. Print is POST, reprint is GET as specified.** `POST /checkin/{visit_id}/badge` is the first print. `GET /checkin/{visit_id}/badge?reason=...` is the reprint, as written in the task list. Because a GET that deactivates a token is unsafe under prefetch, caches and retries, the response sets `Cache-Control: no-store`, `reason` is mandatory, and the deactivate-and-insert runs in one transaction. See Risks.

**10. Reprint policy (confirmed with user):** reason required, no cap, previous `jti` deactivated, new `jti` issued, both rows kept.

**11. Idempotency.** Print uses the existing `idempotency` dependency, keyed `(tenant, key, caller)`. The cached response for a PDF must store the bytes; if the existing store only caches JSON, the print route instead caches `(key -> badge_prints.id)` and re-renders the PDF from the stored row. Decided at implementation after reading `core/idempotency.py`. Either way a retry never creates a second row.

**12. Scan endpoints.** `POST /checkin/badge/check-out` and `POST /checkin/badge/re-enter` take the token in the JSON body (not the URL, so it stays out of access logs). Rate-limited with slowapi per IP, audited, and checkout deactivates the `jti`. Checkout reuses the existing invitation checkout transition function rather than duplicating state logic, keeping `status` and `check_in_status` in step. Re-entry is allowed only on the token's `day` and only while the `jti` is active.

**13. Notification branch (email only, approved).** The visitor approval email is rendered in `invitations/tasks.py` from `visit_confirmation.html/.txt`, not `invitations/notifications.py`. The task adds `badge_flow_enabled` to the render context only when the global and tenant flags are both on, and both templates render a "Please bring your ID" callout behind it, so flag-off output is byte-identical. SMS/WhatsApp are untouched (SMS templates are DLT-registered). Tests assert the callout appears only when the flow is on.

**14. Permission naming.** `visitors:print_badge` as specified, even though the catalog's other invitation codes are `invitations:*`. Added to `PERMISSION_CODES`, granted to `admin` and `reception`, and applied to existing roles by a tenant migration modelled on the earlier `grant_*` migrations.

## Risks / Trade-offs

- [Reprint is a state-changing GET] → `no-store`, mandatory `reason`, single transaction. Recommend changing to `POST /checkin/{visit_id}/badge/reprint` before the frontend integrates; a one-line router change plus the doc. Left as specified pending product confirmation.
- [Two badges for one visit: the old invitation QR and the new badge QR both exist] → They are different tokens on different endpoints; the old QR path is untouched and keeps working when the flow is on. Whether to disable it for flow-on tenants is a product question, not decided here.
- [Day boundary and timezones] → Day is computed in `tenant.timezone`; tests cover a scan at 23:59 and 00:01 local, plus a tenant not in UTC.
- [Token secret rotation invalidates every printed badge] → Acceptable, since badges are one-day.
- [Staff enumerate PII via search] → Branch-scoped, requires `visitors:print_badge`, `idProofUrl` and document URLs are not returned by search, query text is never logged in full, phones are masked in logs.
- [Photo or ID missing at print time causes reception friction] → `409` lists every unmet condition at once.
- [Flag lookup adds a read per request] → `Tenant` is already loaded by `get_tenant`, so no extra query.
- [Tenant migration across all schemas] → standard `alembic_tenant` rollout; new columns are nullable and the table is new, so it is safe to apply before the code ships.

## Migration Plan

1. Deploy migrations (global `tenants` column, tenant `badge_prints` + `invitations` columns + permission grants) with the flag off. Nothing user-visible changes.
2. Deploy code with `BADGE_PRINT_FLOW_ENABLED=false`.
3. Set `BADGE_TOKEN_SECRET`, then enable the global flag in a staging environment and toggle one tenant.
4. Rollback: turn the global flag off (instant, endpoints return 404). Migrations are additive; downgrades drop the new table and columns.

## Open Questions

- Confirm "OTP" in search means the SMS check-in code (Decision 4).
- Confirm whether the reprint endpoint stays `GET` (Decision 9).
- Should the old invitation QR stop working for flow-on tenants once a badge is printed?
