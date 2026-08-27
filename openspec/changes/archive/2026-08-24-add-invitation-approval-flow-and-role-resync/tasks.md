## 1. Schema: `approved_at` column

- [x] 1.1 Add `approved_at: Mapped[datetime | None]` to
      `invitations/models.py::Invitation`.
- [x] 1.2 Author an `alembic_tenant/versions/` migration (down-revision
      `39c3f5112585`, current head) adding the nullable `approved_at`
      column to `invitations`, passing `schema=op.get_context()
      .version_table_schema` explicitly on `op.add_column`/`op.drop_column`
      (per `50d2e145f79f`'s documented `schema_translate_map` landmine).
      Purely additive — no backfill.

## 2. RBAC catalog: `invitations:approve`

- [x] 2.1 Add `"invitations:approve"` to
      `auth/rbac_catalog.py::PERMISSION_CODES`.
- [x] 2.2 Add `"invitations:approve"` to `ROLE_PERMISSIONS["admin"]`
      (already inherits the full list), `["reception"]`, and `["host"]`.
      Leave `["security"]` and `["visitor"]` unchanged.

## 3. Auto-approve on creation (`invitations`)

- [x] 3.1 In `invitations/service.py::create_invitation`, look up
      `CompanyRepository(tenant_db).get_singleton()` before constructing
      the `Invitation` row. Resolve `status = "approved"` and
      `approved_at = now` if the company exists and
      `auto_approve_pre_registered_visitors` is `True`; otherwise
      `status = "submitted"` and `approved_at = None`.
- [x] 3.2 Replace the single `tasks.send_visit_confirmation.delay(...)` call
      with a branch on the resolved status: enqueue
      `tasks.send_approval_notification.delay(...)` when `approved`, or
      `tasks.send_tracking_notification.delay(...)` when `submitted`. Same
      `request_id`/`tenant_schema`/`invitation_id` argument shape as today.

## 4. Split the notification task (`invitations/tasks.py`)

- [x] 4.1 Rename `send_visit_confirmation`/`_send_visit_confirmation` to
      `send_approval_notification`/`_send_approval_notification` — same
      body (QR PNG attachment, "Your visit is confirmed" subject), no
      behavior change beyond the name.
- [x] 4.2 Add `send_tracking_notification`/`_send_tracking_notification` —
      same idempotent-against-redelivery/retry-with-backoff structure and
      `_dispatch` call, but with a tracking-only subject/body (tracking ID
      and current status) and no attachment.
- [x] 4.3 Confirm both tasks still dispose the module-level `engine` in a
      `finally` block (per the existing comment on event-loop reuse across
      Celery task invocations).

## 5. Manual approval endpoint (`invitations`)

- [x] 5.1 In `invitations/service.py`, add `approve_invitation(tenant_db,
      invitation_id) -> Invitation`: fetch via `InvitationRepository.get`,
      404 if missing; 409 if `status != "submitted"`; otherwise set
      `status = "approved"`, `approved_at = now`, commit, return the
      updated row. (Implemented as two functions — `get_invitation`
      (404-fetch, called by the router before `authorize_branch_id` so it
      has a `branch_id` to check) and `approve_invitation(tenant_db,
      invitation, *, tenant)` which does the 409 check, transition,
      commit, and enqueues `send_approval_notification` itself — mirrors
      `create_invitation`'s own dispatch-after-commit pattern instead of
      pushing the enqueue call into the router.)
- [x] 5.2 In `invitations/router.py`, add
      `POST /invitations/{invitation_id}/approve`: fetch the invitation
      first (404 if missing), `authorize_branch_id(tenant_db, user,
      "invitations:approve", invitation.branch_id)` (403/404 per the
      existing pattern), call `service.approve_invitation`, and
      `background_tasks.add_task(record_audit_log, ..., action=
      "invitation_approved", entity_type="Invitation", entity_id=
      invitation.id)`. Response: `InvitationOut`.
- [x] 5.3 Add `approved_at: datetime | None` to `InvitationOut`,
      `InvitationListItemOut`, and `InvitationTrackingOut` in
      `invitations/schemas.py` (not `InvitationTrackingSummaryOut`, which
      stays intentionally minimal), and to the router's `_to_invitation_out`/
      `_to_list_item_out`/`_to_tracking_out` builders.

## 6. Auth: resync standard roles against the catalog

- [x] 6.1 In `auth/service.py`, add `resync_role_permissions(tenant_db) ->
      dict[str, list[str]]`: for each name in
      `rbac_catalog.STANDARD_ROLE_NAMES` present in the tenant's `roles`
      table, snapshot its current permission codes; call
      `rbac_catalog.seed_default_roles(tenant_db)`; re-read each role and
      diff against its snapshot; return `{role_name: [newly_granted_codes]}`
      (omit roles with an empty diff, or include them with an empty list —
      pick one and keep it consistent with the response schema below).
      (Excludes `visitor` — always empty, per design.md's Non-Goals.
      Included roles always appear, with an empty list when nothing was
      missing — `sorted(granted.items())` in the router keeps the response
      order stable.)
- [x] 6.2 In `auth/schemas.py`, add a response schema for the resync result
      (e.g. `RolePermissionResyncOut` — a mapping or list of
      `{roleName, grantedPermissionCodes}`). (Named
      `RolePermissionResyncEntryOut`.)
- [x] 6.3 In `auth/router.py`, add `POST /auth/roles/resync-permissions`,
      gated by `Depends(require_permission("roles:manage"))`, calling
      `service.resync_role_permissions` and returning the result via
      `success_response`.

## 7. Tests (`invitations/tests.py`)

- [x] 7.1 Test: auto-approve enabled → creation returns `status: approved`,
      `approvedAt` set, and the dispatched notification (assert via a
      recording sender fixture, mirroring `identity_verification/tests.py`'s
      `_RecordingSender` pattern) carries the QR attachment. (Verified at
      the endpoint level by asserting `send_approval_notification.delay`
      — not `send_tracking_notification.delay` — was called, matching the
      existing `test_create_invitation_idempotency_key_replay` convention
      of mocking `.delay` rather than letting Celery actually run in an
      HTTP test; the QR-attachment content itself is verified once, at the
      task level, by `test_send_approval_notification_delivers_email_with_qr_via_mailpit`.)
- [x] 7.2 Test: auto-approve disabled (or no `Company` profile configured)
      → creation returns `status: submitted`, `approvedAt` unset, and the
      dispatched notification carries no attachment. (Same verification
      approach as 7.1, plus a third test for the no-Company-profile-at-all
      case.)
- [x] 7.3 Test: `POST /invitations/{id}/approve` happy path — a `submitted`
      invitation transitions to `approved`, `approvedAt` is set, and the
      QR-bearing notification is dispatched.
- [x] 7.4 Test: approving an already-`approved` invitation returns 409 and
      leaves it unchanged.
- [x] 7.5 Test: a caller without `invitations:approve` gets 403; the
      invitation and its notifications are unaffected.
- [x] 7.6 Test: a nonexistent invitation id gets 404; a caller with
      `invitations:approve` only at a different branch gets 403, not 404
      — `authorize_branch_id` (the same dependency `POST /invitations`
      uses) 403s on no-branch-access and only 404s when the branch itself
      doesn't exist. Corrected from this task's original 404-for-both
      wording after implementation showed the real dependency behavior
      (see design.md Decision 3's note).

## 8. Tests (`auth/tests.py`)

- [x] 8.1 Test: a role missing a catalog permission (simulate by removing
      it from the role's grants directly in the test, mirroring a
      pre-catalog-update tenant) gets it back after
      `POST /auth/roles/resync-permissions`.
- [x] 8.2 Test: running the resync twice in a row reports no newly granted
      permissions on the second call, and no role's permission set changes
      (idempotency).
- [x] 8.3 Test: a permission manually granted to a standard role beyond its
      catalog default survives the resync.
- [x] 8.4 Test: a caller without `roles:manage` gets 403 from the resync
      endpoint.

## 9. Docs

- [x] 9.1 Update `docs/features/invitations.md` (or equivalent): document
      the auto-approve-driven status/notification split and the new
      approve endpoint.
- [x] 9.2 Update `docs/features/auth.md`: document the new resync endpoint
      and when to use it (a tenant whose standard roles predate a catalog
      permission).

## 10. Verification

- [x] 10.1 `ruff check` and `ruff format --check` clean on every changed
      file (repo-wide: both pass).
- [x] 10.2 `mypy` clean on `auth/` (in the mandatory strict-typing scope)
      and on every other touched signature. (`registrations/tests.py:246`
      has one pre-existing, unrelated error predating this change —
      confirmed via `git diff` before touching that file — left as-is.)
- [x] 10.3 `ddev exec uv run alembic -c alembic_tenant.ini upgrade head`
      applies cleanly against the dev tenant schema. (The actual dev
      tenant schema's `alembic_version` is already stamped at a revision
      absent from this repo's history entirely — a pre-existing
      environment drift, not caused by this change. Verified instead
      against a fresh throwaway schema: the full migration chain from
      `<base>` through this change's new revision applies cleanly, and the
      resulting `invitations.approved_at` column is nullable
      `timestamp with time zone` as designed.)
- [x] 10.4 `ddev exec uv run pytest` green, including the new tests in
      §7-§8. (341 passed, full suite — after also clearing several
      pre-existing ad-hoc test schemas whose `invitations` table predated
      this change's new column, an unrelated stale-fixture issue this
      change's own test run surfaced.)
