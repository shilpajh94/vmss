## 1. Tenant resolution & deprecation plumbing

- [x] 1.1 Add `track_default_tenant` dependency to `invitations/deps.py`
      (returns the resolved `Tenant`, same `resolve_default_tenant` +
      404/logging behavior as `track_default_tenant_db`, without binding a
      session).
- [x] 1.2 Add `mark_deprecated(response: JSONResponse) -> JSONResponse` to
      `core/responses.py`, setting the `Deprecation` response header.

## 2. Service layer

- [x] 2.1 Extract the shared 409-not-approved / 409-watchlist-flagged /
      status-transition logic out of `service.check_in_invitation` into a
      private `_perform_check_in(invitation, *, actor_user_id)` helper.
- [x] 2.2 Update `service.check_in_invitation` to call `_perform_check_in`
      with `actor_user_id=user_id`, preserving its existing behavior and
      signature.
- [x] 2.3 Add `service.check_in_invitation_by_tracking_id(tenant_db,
      tracking_id, tenant)`: looks up the invitation via
      `InvitationRepository.get_by_tracking_id` (404 if not found), then
      calls `_perform_check_in(invitation, actor_user_id=None)`.

## 3. Public v2 route

- [x] 3.1 Add `router_v2 = APIRouter(prefix="/invitations",
      tags=["invitations"])` in `invitations/router.py`.
- [x] 3.2 Implement `PATCH /{trackingId}/check-in` on `router_v2`:
      `@limiter.limit("20/minute")`, `Depends(track_default_tenant_db)` for
      the session, `Depends(track_default_tenant)` for the `Tenant`, optional
      `Idempotency-Key` header reusing the existing `_cached_response`/
      `_cache_response` helpers keyed by `tenant.id`.
- [x] 3.3 In the same handler, call
      `service.check_in_invitation_by_tracking_id`, then
      `background_tasks.add_task(record_audit_log, tenant.schema_name,
      actor_user_id=None, action="invitation_checked_in_public",
      entity_type="Invitation", entity_id=invitation.id)`.
- [x] 3.4 Register the new response schema/model on the route
      (`response_model=Envelope[InvitationOut]`, matching the `v1` route)
      per `api-documentation.md` §1.

## 4. v1 deprecation

- [x] 4.1 Wrap the existing `v1` check-in route's return with
      `mark_deprecated(...)`.

## 5. App wiring

- [x] 5.1 Add `api_router_v2 = APIRouter()` in `api.py`, including only
      `invitations.router.router_v2`.
- [x] 5.2 Mount `app.include_router(api_router_v2, prefix="/api/v2")` in
      `main.py`, alongside the existing `/api/v1` mount.

## 6. Documentation

- [x] 6.1 Add the new `PATCH /api/v2/invitations/{trackingId}/check-in` route
      to `docs/features/invitations.md`'s endpoint table.
- [x] 6.2 Add a deprecation note (with target removal date, once decided —
      see design.md Open Questions) for `PATCH
      /api/v1/invitations/{id}/check-in` in the same file.
- [x] 6.3 Update `.env.example` if the rate limit or default-tenant slug
      settings gain any new knobs (none expected — reusing existing
      `track_default_tenant_db`/`limiter` config). Verified: no new settings
      introduced, `.env.example` unchanged.

## 7. Tests

- [x] 7.1 Happy path: public check-in by `tracking_id` with no
      `Authorization` header transitions `approved` → `checked_in`.
- [x] 7.2 409 when invitation is not `approved`.
- [x] 7.3 409 when `watchlistFlagged` and not overridden.
- [x] 7.4 404 for an unknown `tracking_id`.
- [x] 7.5 Retried request with the same `Idempotency-Key` is not duplicated.
- [x] 7.6 Rate limit trips after the configured threshold (mirrors the
      existing `GET /invitations/track` throttling test).
- [x] 7.7 Audit log row for a public check-in has `actor_user_id IS NULL`
      and `action = "invitation_checked_in_public"`.
- [x] 7.8 `v1` check-in response includes the `Deprecation` header; existing
      `v1` happy-path/403/409 tests still pass unchanged. All 144
      invitations tests pass (`ddev exec uv run pytest
      src/vmss_api/invitations/tests.py`).
