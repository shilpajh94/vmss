## 1. Data Model & Migration

- [x] 1.1 Add the new columns to `invitations/models.py::Invitation`
      (denial, check-in/out, badge, watchlist-override — design.md Decision 1).
- [x] 1.2 Author the Alembic tenant migration
      (`alembic_tenant/versions/`) adding those columns; verify it applies
      cleanly to an existing tenant schema with data in it.

## 2. RBAC Catalog

- [x] 2.1 Add the 7 new permission codes to
      `auth/rbac_catalog.py::PERMISSION_CODES`.
- [x] 2.2 Add the role grants from design.md Decision 5's table to
      `ROLE_PERMISSIONS` (`reception`, `security`, `host`); confirm
      `seed_default_roles`'s union-merge backfill picks them up for an
      already-provisioned tenant without a separate script.

## 3. Schemas

- [x] 3.1 Add `InvitationDetailOut` (design.md Decision 2) to
      `invitations/schemas.py`.
- [x] 3.2 Add request schemas: `InvitationDenyRequest` (mandatory reason),
      `InvitationRescheduleRequest` (new date/time), `InvitationExtendRequest`
      (new expiry), `WatchlistOverrideRequest` (mandatory reason).
- [x] 3.3 Add response schemas: `BadgeOut` (badge number, issued-at, retrieval
      URL, reprint count).

## 4. Repository

- [x] 4.1 Add atomic conditional-`UPDATE` methods to
      `InvitationRepository`, mirroring `approve_if_submitted`: `deny_if_submitted`,
      `check_in_if_eligible` (also checking `watchlist_flagged` is false),
      `check_out_if_checked_in`.
- [x] 4.2 Add plain conditional-status-guarded update methods for
      `reschedule`, `extend`, badge issuance/reprint, and
      `override_watchlist_if_flagged`.

## 5. Badge Rendering

- [x] 5.1 Create `invitations/badge.py`: `_render_png` (Pillow compositing of
      QR + tracking ID + primary contact name + expiry) wrapped in
      `anyio.to_thread.run_sync`, reusing `qr.py::generate_qr_png` for the QR
      portion (design.md Decision 3).
- [x] 5.2 Add badge-number generation (`BDG-XXXXXXXX`, retry-loop-against-
      uniqueness, mirroring `_generate_unique_tracking_id`).

## 6. Notifications

- [x] 6.1 Add `send_denial_notification` to `invitations/tasks.py`
      (design.md Decision 7), structurally mirroring
      `send_tracking_notification`.

## 7. Service Layer

- [x] 7.1 Implement `deny_invitation`, `check_in_invitation`,
      `check_out_invitation`, `reschedule_invitation`, `extend_invitation`,
      `issue_badge`, `reprint_badge`, `override_watchlist` in
      `invitations/service.py`, each following the fetch → authorize →
      conditional-update → commit → (audit task, notification task) shape
      `approve_invitation` already establishes.

## 8. Router

- [x] 8.1 Add `GET /invitations/{id}` (branch-scoped detail lookup).
- [x] 8.2 Add `PATCH /invitations/{id}/deny`.
- [x] 8.3 Add `PATCH /invitations/{id}/check-in` (with `Idempotency-Key`
      support, reusing the existing `_cached_response`/`_cache_response`
      helpers).
- [x] 8.4 Add `PATCH /invitations/{id}/check-out` (with `Idempotency-Key`).
- [x] 8.5 Add `PATCH /invitations/{id}/reschedule`.
- [x] 8.6 Add `PATCH /invitations/{id}/extend`.
- [x] 8.7 Add `POST /invitations/{id}/badge` (with `Idempotency-Key`) and
      `POST /invitations/{id}/badge/reprint`.
- [x] 8.8 Add `POST /invitations/{id}/watchlist-override`.
- [x] 8.9 Set `response_model=Envelope[...]` on every new route
      (api-documentation.md §1) and confirm each renders camelCase in
      `/docs` (api-documentation.md §5).

## 9. Tests (`invitations/tests.py`)

- [x] 9.1 Happy-path test for each of the 8 endpoints.
- [x] 9.2 Permission-denied (403) test for each endpoint
      (testing-standards.md §2).
- [x] 9.3 Tenant-isolation test covering at least one of the new endpoints
      (testing-standards.md §2) — e.g. check-in against a different
      tenant's schema-bound session must not see the row.
- [x] 9.4 State-conflict (409) tests: deny/check-in/check-out/reschedule/
      extend/badge-issuance each from an ineligible status; badge reprint
      with none issued yet; watchlist-override on a non-flagged invitation.
- [x] 9.5 Idempotency-Key retry tests for check-in, check-out, and badge
      issuance (single side effect, identical response body on retry).
- [x] 9.6 Watchlist gate test: flag an invitation directly via the test
      factory, confirm check-in is blocked with 409, override it, confirm
      check-in then succeeds.
- [x] 9.7 Badge reprint reflects updated data: issue a badge, extend or
      reschedule the invitation, reprint, and confirm the re-rendered badge
      (or the data it was rendered from) reflects the new value.

## 10. Documentation

- [x] 10.1 Add the 8 new endpoints to `docs/features/invitations.md`
      (purpose, permission required, request/response shape, status
      preconditions).
