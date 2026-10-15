## 1. Actor threading

- [x] 1.1 Add a required `actor_user_id: uuid.UUID` keyword argument to `invitations/service.py::deny_invitation`. Pass `user.id` from the deny route in `invitations/router.py` and from `approvals/service.py::reject_step`.
- [x] 1.2 Add the same argument to `reschedule_invitation` and `_reschedule_archived`, and pass `user.id` from the reschedule route.
- [x] 1.3 Run `ddev exec uv run mypy src/vmss_api/invitations src/vmss_api/approvals` and confirm no call site was missed.

## 2. Role push with exclusions

- [x] 2.1 Extend `notifications/service.py::notify_role_at_branch` with optional `exclude_user_ids: Collection[uuid.UUID] = ()` and `reason: str = "role_assigned"`. Filter the resolved holders, and treat an empty set after filtering as the existing zero-holders `WARNING` no-op.
- [x] 2.2 Add a test in `notifications/tests.py`: excluded users are not addressed, and the default `reason` is unchanged for existing callers.

## 3. Responsible-staff resolution and dispatch

- [x] 3.1 Add `_responsible_staff(invitation, *, actor_user_id)` to `invitations/service.py`, following design.md D1. It returns the email user ids (host plus POC user, de-duplicated, minus the actor), the POC push user (minus the actor and the host) and the POC role id.
- [x] 3.2 Add `_notify_responsible_staff(tenant_db, tenant, invitation, *, event, actor_user_id)`:
  - enqueue one `send_staff_lifecycle_notification.delay(...)` per email recipient;
  - push the POC user with `notify_user`, using the event's existing push builder;
  - push the POC role with `notify_role_at_branch(..., exclude_user_ids={actor, host}, reason="lifecycle_update")`.
- [x] 3.3 Call it after commit in `deny_invitation`, `revert_invitation_approval`, `reschedule_invitation` and `_reschedule_archived`, after the existing visitor dispatch and `_notify_host`. Confirm none of the 409/403/404/422 paths reach it.

## 4. Staff lifecycle email task and template

- [x] 4.1 Add `core/email_templates/staff_lifecycle_update.html`, extending `base.html` and using `_macros.html`. It switches tone, pill, heading, lead and reason callout on `event`, and has a shared Visit details block, visitor name, phone and email rows, and a portal step quoting the tracking ID. It has no QR block (email-notifications spec).
- [x] 4.2 Add a `_cta` entry for `staff_lifecycle_update`, pointing at the staff portal link, consistent with `host_assigned` and `poc_assigned`.
- [x] 4.3 Add `send_staff_lifecycle_notification(self, *, request_id, tenant_schema, invitation_id, recipient_user_id, actor_user_id, event)` to `invitations/tasks.py`, following design.md D3:
  - bind `request_id`;
  - apply the redelivery guard for each event;
  - skip an inactive recipient with a `WARNING`;
  - fall back to "a staff member" for the actor's name;
  - use `_render_or_fallback` with a fallback subject equal to the heading;
  - use `_RETRY_KWARGS`, with an `ERROR` log on exhaustion;
  - call `engine.dispose()` in `finally`.

## 5. Extend pushes the host

- [x] 5.1 Add `push_notifications.extended(invitation)` with the title "Visit pass extended" and an action `extended`. The body names the visitor, the tracking ID and the new expiry in the visit timezone, with no PII beyond what `_build` already sends.
- [x] 5.2 Give `extend_invitation` a `tenant` keyword argument, and call `_notify_host(tenant, updated, push_notifications.extended)` after commit. Update the extend route to pass `tenant`.

## 6. Personal dashboard endpoint

- [x] 6.1 Expose `relevant_to_me_clause(user_id, default_host_role_id)` in `invitations/repository.py` as a public wrapper over `_relevant_to_me_filter`.
- [x] 6.2 Add `DashboardRepository.personal_overview_counts(...)`, a single query using `COUNT(*) FILTER (WHERE …)` for `visitsToday`, `insideNow`, `awaitingApproval` and `upcoming`, with today's bounds in the tenant timezone. Also add `personal_upcoming_preview(..., limit=5)`, which orders by scheduled visit date and time and excludes `archived`, `denied` and soft-deleted rows.
- [x] 6.3 Add the `MyDashboardOverviewOut` and `MyUpcomingVisitorOut` schemas (`CamelModel`) to `dashboard/schemas.py`.
- [x] 6.4 Add `dashboard/service.py::get_my_overview(tenant_db, tenant, user)`. It resolves the default host role with `org_structure.service.get_default_host_role`, reuses `_today_bounds_utc`, and makes no branch-scope call.
- [x] 6.5 Add `GET /my-overview` to `dashboard/router.py`, with `response_model=Envelope[MyDashboardOverviewOut]` and only `get_current_user`, `get_tenant` and `get_tenant_db`. Note in the docstring that the `/admin/dashboard` prefix is historical (design.md D6).

## 7. API tests

- [x] 7.1 `invitations/tests.py`, covering each scenario in the invitations spec:
  - revert, deny (direct and through `reject_step`) and reschedule (including out of `archived`) each enqueue one staff email per recipient;
  - the actor is excluded, and a host who is also the POC is de-duplicated;
  - a role POC gets a push but no email;
  - rejected actions enqueue nothing.

  Build invitations with the existing factories, with `host_id` and `poc_user_id` set.
- [x] 7.2 Task-level tests that call `_send_staff_lifecycle_notification` directly against the real test DB:
  - the redelivery guard skips the send for each event;
  - an inactive recipient is skipped;
  - the rendered email contains the reason and the actor's name, has no QR, and its subject equals its heading.
- [x] 7.3 Extend tests: a successful extend pushes the host, a 422 sends no push, and an extend with no host still succeeds.
- [x] 7.4 `dashboard/tests.py` for `my-overview`, covering each scenario in the dashboard spec:
  - a host gets 200 with only their own invitations;
  - `awaitingApproval` equals the `relevantToMe&status=submitted` list total;
  - archived and denied invitations are excluded;
  - a request without a token gets 401;
  - `X-Branch-ID` is ignored;
  - the preview is capped at 5 and ordered.

  Add a tenant-isolation case using `make_tenant_schema` and `open_tenant_session` (`testing-standards.md` §2).
- [x] 7.5 Extend `tests/test_api_documentation.py::test_response_schemas_render_camel_case` to assert `visitsToday` and `upcomingPreview`.
- [x] 7.6 Run `ddev exec uv run pytest src/vmss_api/invitations src/vmss_api/dashboard src/vmss_api/approvals src/vmss_api/notifications tests/test_api_documentation.py`, then the full suite. Never run two pytest processes at once. Compare any unrelated failures against a stashed baseline before calling them regressions.

## 8. Web portal (VMMS_WEB)

- [x] 8.1 Add `src/presentation/utils/landing-path.ts` exporting `landingPathFor(user)` (design.md D7). *Deviation:* VMMS_WEB has no test runner (no vitest/jest, no test files), so there is no unit test; adding a framework was out of scope. The three branches are covered by the browser QA in 8.9.
- [x] 8.2 Use it in `use-staff-login-page.ts` and `use-staff-sso-login-page.ts`. This fixes SSO reception users landing on the board.
- [x] 8.3 Rename `pages/staff-dashboard` to `pages/staff-invitations` (`StaffInvitationsPage`, `useStaffInvitations`), with no behavior change, and route it at `/staff/invitations` in `App.tsx`.
- [x] 8.4 Add the domain entity and Zod schema for the personal overview, a repository method calling `GET /admin/dashboard/my-overview`, and `getMyDashboardOverviewUseCase`, registered in `AppDependenciesProvider`.
- [x] 8.5 Build a new `pages/staff-dashboard` page and hook. It reuses `KpiRow` (Visits today, Inside now, Awaiting approval, Upcoming) and an upcoming-visitors list in which each row links to `/staff/invitations?invitationId=…`. It has loading, error and empty states, and a 401 bounce to `/staff/login`. Route it at `/staff/dashboard` under `StaffLayout`.
- [x] 8.6 Repoint the board links to `/staff/invitations`:
  - `DashboardSidebar`: add a "Dashboard" item and repoint "All visitors";
  - `ReceptionSidebar` "visits";
  - the `basePath` in `PushNotificationsProvider.buildInvitationPath`;
  - the redirect in `staff-visitor-registration.tsx`;
  - the bounces in `use-admin-audit-trail` and `use-reception-dashboard`, which use `landingPathFor` where a user is loaded.
- [x] 8.7 Confirm that the push title mapping falls back to the default title for `reason: "lifecycle_update"`, rather than showing "New invitation for …".
- [x] 8.8 Run the web lint and type check, without prettier (VMMS_WEB has none). `tsc -b` is clean and `npm run lint` shows only 2 pre-existing warnings in an untouched file. There are no web tests to update (see 8.1).
- [x] 8.9 Browser QA on the local default tenant:
  - an admin, a reception user (password and SSO) and a host each land on their dashboard after login;
  - the host's KPIs match their board;
  - a push deep link opens the board with the visitor modal.

## 9. Docs

- [x] 9.1 `docs/features/invitations.md`: add a responsible-staff notification table (event × visitor, host, POC user and POC role × email and push), plus the extend host push.
- [x] 9.2 `docs/features/dashboard.md`: document `GET /admin/dashboard/my-overview`, its `relevantToMe` scope and why it has no branch gate.
- [x] 9.3 `docs/features/background-jobs.md`: add "Deployment requirements": exactly one `celery beat` per environment, which the visit-lifecycle sweep and the daily rollups depend on. Also note that the sweep is deliberately silent and leaves `submitted` requests alone.
- [x] 9.4 Run `openspec validate staff-lifecycle-emails-and-dashboard-landing --strict`.
