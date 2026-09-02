## 1. Dependencies & Configuration

- [x] 1.1 `uv add firebase-admin`; add `FCM_CREDENTIALS_JSON` (or path) and
      any other required FCM settings to `core/config.py::Settings` and
      `.env.example`.
- [x] 1.2 Add a thin FCM client wrapper (init from settings, exposes a
      `send_each(messages)` call) that `notifications/tasks.py` calls — keep
      this isolated so it can be mocked in tests.

## 2. `notifications` Package Scaffolding

- [x] 2.1 Create `src/vmss_api/notifications/__init__.py`,
      `models.py` (`DeviceToken`: `id`, `user_id` FK, `platform`
      enum/string, `fcm_token` unique, `last_seen_at`, `TimestampMixin`),
      `repository.py`, `service.py`, `schemas.py` (`CamelModel` subclasses),
      `router.py`, `tasks.py`, `tests.py`.
- [x] 2.2 Alembic tenant migration (`alembic_tenant/versions/`) creating
      `device_tokens` with a unique index on `fcm_token`.
- [x] 2.3 Register `notifications` router in `api.py`
      (`api_router.include_router(notifications.router.router)`) and add its
      tag + description to `main.py`'s `_TAGS_METADATA`
      (`api-documentation.md` §2).
- [x] 2.4 Register `vmss_api.notifications` in `core/celery_app.py`'s
      `autodiscover_tasks` list and add a `task_routes` entry (route to the
      existing `notifications` queue, matching `invitations.tasks`'
      routing).

## 3. Device Registration Endpoints

- [x] 3.1 `POST /notifications/devices` — registers/updates a device token
      for the calling user (reassigns ownership if the token belonged to
      someone else, per spec).
- [x] 3.2 `DELETE /notifications/devices/{token}` — removes a device token
      owned by the calling user; no-op (not an error) if not found or owned
      by someone else.
- [x] 3.3 `response_model=Envelope[...]` on both routes
      (`api-documentation.md` §1); request schemas validate `platform`
      against an explicit enum (`web`/`android`/`ios`).
- [x] 3.4 Repository methods: `upsert_by_token`, `delete_owned_by_user`,
      `list_tokens_for_users(user_ids)`.

## 4. Push Dispatch Primitive

- [x] 4.1 `auth/repository.py::UserRepository` — add
      `list_user_ids_holding_role_at_branch(role_id, branch_id)` (mirrors
      `approvals/service.py::_user_holds_role_at_branch`'s branch-or-
      company-wide `UserBranchRole` match, but returns every matching user
      id instead of checking one).
- [x] 4.2 `notifications/service.py` — `notify_user(user_id, *, title, body,
      data)` and `notify_role_at_branch(role_id, branch_id, *, title, body,
      data)`; both resolve device tokens via the repository and enqueue
      `notifications.tasks.send_push.delay(...)` with the resolved token
      list (or resolved user ids — see design.md Decision 2 on resolving the
      *target*, not re-deriving it, inside the task).
- [x] 4.3 `notifications/tasks.py::send_push` — Celery task with
      `autoretry_for`/`retry_backoff`/`max_retries` (`background-jobs.md`
      §3), binds `request_id` into `structlog` context, calls the FCM
      wrapper's batch send, deletes any device token FCM reports as
      not-registered, logs `ERROR` with enough context on retry exhaustion.
- [x] 4.4 Enforce the payload content rule (tracking id + visitor display
      name + action type only, no ID-proof/identity-document data) in one
      shared payload-building helper other call sites use, so it can't be
      bypassed per call site.

## 5. Wire Into Invitation Creation & Terminal Actions

- [x] 5.1 `invitations/service.py::create_invitation` — after commit, if the
      invitation is `submitted` (not auto-approved) and at least one
      approval step was created, resolve step 0's approver (host user id, or
      role id + branch id) and call the matching `notify_*` function.
- [x] 5.2 `invitations/service.py::approve_invitation` — after commit, if
      `invitation.host_id` resolves, `notify_user` the host that the
      invitation was approved.
- [x] 5.3 `invitations/service.py::deny_invitation` — after commit, if
      `invitation.host_id` resolves, `notify_user` the host that the
      invitation was denied.
- [x] 5.4 `invitations/service.py::reschedule_invitation` — after commit, if
      `invitation.host_id` resolves, `notify_user` the host with the new
      date/time.
- [x] 5.5 `invitations/service.py::check_in_invitation` and
      `check_out_invitation` — after commit, if `invitation.host_id`
      resolves, `notify_user` the host for each event.

## 6. Wire Into Step Activation

- [x] 6.1 `approvals/service.py::_activate_next_step` — after the next
      step's clock fields are set, resolve its approver (host or role +
      invitation's branch) and call the matching `notify_*` function; verify
      this fires from `approve_step`'s call site (not the final-step branch,
      which instead goes through `invitations_service.approve_invitation`'s
      own push per task 5.2).

## 7. Tests (`testing-standards.md` §2)

- [x] 7.1 `notifications/tests.py` — happy path for register/unregister
      endpoints; permission-denied case (unauthenticated caller rejected);
      tenant-isolation case (a device token registered under one tenant's
      schema is invisible to a dispatch resolved against another tenant's
      schema); token-reassignment scenario; invalid-token cleanup on a
      mocked FCM "not registered" response.
- [x] 7.2 `invitations/tests.py` additions — for each of the five wired
      actions (submission, approve, deny, reschedule, check-in/out), assert
      the correct `notify_*` call is made (mocked) with the correct
      recipient, and that a hostless/stepless invitation skips the call
      without failing the request.
- [x] 7.3 `approvals/tests.py` addition — approving a non-final step in a
      multi-step workflow triggers a push to the next step's resolved
      approver; approving the final step does not double-fire (only
      `approve_invitation`'s push fires).
- [x] 7.4 `auth/tests.py` addition — new
      `list_user_ids_holding_role_at_branch` repository method: branch-scoped
      match, company-wide (`branch_id IS NULL`) match, and tenant-isolation
      case.

## 8. Documentation

- [x] 8.1 Add `docs/features/notifications.md` (purpose, endpoints, FCM
      config knobs) per `project-rules.md`'s "New Features" documentation
      requirement.
- [x] 8.2 Update `docs/features/invitations.md` and
      `docs/features/approvals.md` (if present) to mention the new push
      touchpoints alongside the existing email/SMS ones.
