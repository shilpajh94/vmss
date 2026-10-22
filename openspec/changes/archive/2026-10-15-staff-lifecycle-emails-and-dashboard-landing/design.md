## Context

See proposal.md for the gap analysis. The current-state facts that shape
the approach:

- **Notification fan-out.** Every lifecycle action follows the same shape:
  fetch, authorize, conditional `UPDATE`, commit, and then three outputs
  (an audit row from the router's background task, a visitor
  `send_*_notification.delay(...)`, and a host push through
  `invitations/service.py::_notify_host`).
- **Staff email precedent.** `send_host_creation_notification` and
  `send_poc_creation_notification` each send one Celery task per
  recipient. The caller passes the recipient id explicitly, so an
  exhausted-retries log names who went unnotified. Each task re-checks
  that the recipient is still active. A role-identified POC never gets
  email (`edit_invitation` pushes the role instead).
- **Missing actor.** `deny_invitation(tenant_db, invitation, *, reason,
  tenant)` has no actor parameter, and `approvals/service.py::reject_step`
  calls it directly. `reschedule_invitation` and `_reschedule_archived`
  also lack an actor. There are no `denied_by_user_id` or
  `rescheduled_by_user_id` columns. `revert_invitation_approval` already
  takes `user`.
- **Role push.** `notifications_service.notify_role_at_branch` resolves the
  holders of a role at a branch or company-wide. It has no exclusion list,
  and it always stamps `reason: "role_assigned"` on the payload.
- **Dashboard scope.** All three dashboard endpoints use
  `resolve_dashboard_branch_scope("invitations:view-all")`, so a host gets
  403. `relevantToMe` lives in
  `invitations/repository.py::_relevant_to_me_filter(user_id,
  default_host_role_id)`, and `GET /invitations` uses it with no branch
  gate at all.
- **Web.** The web app sends a user to a landing page from two places that
  disagree. `use-staff-login-page.ts` handles admin, reception and staff,
  but `use-staff-sso-login-page.ts` handles only admin and staff, so
  reception users who sign in through SSO land on the board.
  `/staff/dashboard` renders `StaffDashboardPage`, which is the kanban
  board. `isReception` comes from `branchRoles` on the client.

## Goals / Non-Goals

**Goals:**
- One place decides who counts as responsible staff, so deny, revert and
  reschedule cannot drift apart.
- Staff email retries are isolated per recipient, so a retry does not
  re-send email to someone who already received it.
- The personal dashboard and the `relevantToMe` board are guaranteed to
  agree, because both use the same predicate rather than a copy of it.

**Non-Goals:**
- **Changing the sweep.** The two earlier user decisions stand: no
  notification on auto check-out or archive, and no archiving of stale
  `submitted` requests (`visit-lifecycle-sweep` spec). The sweep interval
  stays at 15 minutes.
- **Staff email on check-in, check-out or extend.** These stay push only,
  because they are frequent and real-time.
- **A visitor notification on extend.** The QR pass and the visit date do
  not change.
- **POC push on check-in or check-out.** It would double the push volume
  for a busy reception desk. If wanted, it belongs in a separate change.
- **Reminders for pending approvals** (`database-architecture.md` §6 lists
  them as a future Celery job). They need their own cadence and an opt-out
  design.
- **Changing the host push.** Existing host pushes do not change, including
  the case where the host is the actor.
- **Redirecting a signed-in user away from the login pages.**

## Decisions

### D1. A single responsible-staff resolver, called from each action
Add `_responsible_staff(invitation, *, actor_user_id) -> ResponsibleStaff`
in `invitations/service.py`. It returns:

- `email_user_ids`: `host_id` and `poc_user_id`, de-duplicated, with the
  actor removed;
- `push_poc_user_id`: `poc_user_id`, unless it equals the actor or the
  host. The host already receives the host push;
- `push_poc_role_id`: `poc_role_id`, when set.

Add `_notify_responsible_staff(tenant_db, tenant, invitation, *, event,
actor_user_id)`. It enqueues one email task per entry in `email_user_ids`
and sends the POC push. The three actions call it right after their
existing visitor dispatch and `_notify_host`:

- `deny_invitation`;
- `revert_invitation_approval`;
- `reschedule_invitation` and `_reschedule_archived`.

*Alternative considered:* resolve the recipients inside the Celery task
from the invitation's current `host_id` and `poc_user_id`. This was
rejected because it breaks the explicit-recipient precedent, and a host
change between enqueue and send would email someone who was never
responsible at the time of the action.

### D2. Thread an `actor_user_id` through deny and reschedule
`deny_invitation` gains a required keyword argument `actor_user_id:
uuid.UUID`. The router passes `user.id`. `approvals.reject_step` passes the
rejecting `user.id`. `reschedule_invitation` and `_reschedule_archived` gain
the same argument. `revert_invitation_approval` already has `user`.

The actor is passed to the email task too (`actor_user_id`), so the email
can name who acted. It is not persisted, and no column is added. The audit
log already records the actor for every one of these actions, and the
email only needs the name at send time.

*Alternative considered:* add `denied_by_user_id` and
`rescheduled_by_user_id` columns. This was rejected because it needs a
migration for data the audit trail already holds.

### D3. One email task with an `event` argument, one template
`send_staff_lifecycle_notification(self, *, request_id, tenant_schema,
invitation_id, recipient_user_id, actor_user_id, event)` takes `event` in
`{"denied", "approval_reverted", "rescheduled"}`. The task:

1. Binds `request_id` (`logging-observability.md` §1).
2. Loads the invitation and returns if it is missing.
3. Checks the redelivery guard for the event, as listed in the invitations
   spec. Revert uses the same guard as
   `_send_approval_revert_notification`.
4. Loads the recipient with `UserRepository.get_active`. If the recipient
   is missing, it logs `WARNING` and returns.
5. Resolves the actor's name, falling back to "a staff member".
6. Renders `staff_lifecycle_update` through `_render_or_fallback`, reusing
   `_invitation_email_context` plus `event`, `actor_name`, `reason`
   (`denial_reason` or `approval_revert_reason`), `visitor_phone` and
   `visitor_email`.
7. Sends the email through `notifications.email_sender`.

It uses the standard `_RETRY_KWARGS` and logs `ERROR` when retries are
exhausted (`background-jobs.md` §3–4).

One template with an `event` switch matches how the spec presents this
type: one row group with tone, pill, heading and lead varying by event,
over a shared body (Visit details, visitor contact, portal step). Three
near-identical templates would drift apart.

*Alternative considered:* reuse `host_assigned.html` with an extra
heading. This was rejected because tone, pill and the reason callout all
differ.

### D4. POC push uses a role fan-out that can exclude users
Generalize `notify_role_at_branch` with two optional keyword arguments:

- `exclude_user_ids: Collection[uuid.UUID] = ()`, which removes the actor
  and the host from the resolved holders;
- `reason: str = "role_assigned"`.

The POC push passes `reason="lifecycle_update"`. Existing callers are
unaffected. A POC user is pushed with the existing `notify_user`. The push
builders `push_notifications.denied`, `approval_reverted` and
`rescheduled` are reused as they are. They are already addressed to "the
visit", not to the host personally, and they already exclude PII.

*Alternative considered:* a new `notify_poc` helper in invitations. This
was rejected because it would duplicate the holder lookup that
`notify_role_at_branch` owns.

### D5. Extend reuses `_notify_host`
Add `push_notifications.extended(invitation)` with the title "Visit pass
extended" and the new `expires_at` in the visit timezone. Call
`_notify_host(tenant, updated, push_notifications.extended)` after commit
in `extend_invitation`, which therefore gains a `tenant` keyword argument.
Its router already resolves the tenant.

### D6. `my-overview` lives in the dashboard feature and reuses the invitations predicate
Expose the predicate as a public function,
`invitations.repository.relevant_to_me_clause(user_id,
default_host_role_id)`, a thin wrapper over `_relevant_to_me_filter`. Add
`DashboardRepository.personal_overview_counts(...)` and
`personal_upcoming_preview(...)`, which apply that clause plus the status
filters from the dashboard spec in a single `COUNT ... FILTER (WHERE ...)`
query and one bounded `SELECT`.

The service resolves `default_host_role_id` with
`org_structure.service.get_default_host_role`, the same way the
`relevantToMe` list does. The route sits on the existing dashboard
`router` as `GET /my-overview`, with only `get_current_user`. There is no
branch-scope dependency, so `X-Branch-ID` is never read.

The route stays under the `/admin/dashboard` prefix. That prefix already
serves reception and security, who are not admins. Adding a second
`APIRouter` in the same module would sidestep the "every feature exposes
one `router`" contract that `tests/test_api_documentation.py` checks.

*Alternative considered:* `GET /admin/dashboard/overview?scope=mine`. This
was rejected because a single endpoint whose permission gate depends on a
query parameter is harder to reason about and to test.

*Alternative considered:* loosen the `view-all` gate on the existing
overview. This was rejected because it is a privacy regression that the
dashboard spec explicitly forbids.

### D7. Web: one landing helper and a route split
- `src/presentation/utils/landing-path.ts` exports `landingPathFor(user:
  StaffUser)`: `isAdmin` → `/admin/dashboard`, `isReception` →
  `/reception/dashboard`, otherwise → `/staff/dashboard`. Both login hooks
  call it.
- Rename the current `staff-dashboard` page to `staff-invitations`
  (component `StaffInvitationsPage`, route `/staff/invitations`), with no
  behavior change. Create a new `staff-dashboard` page that reuses
  `KpiRow` and the upcoming-visitors list pattern from `admin-dashboard`.
  It is backed by a new `getMyDashboardOverviewUseCase` and a repository
  method calling `GET /admin/dashboard/my-overview`. A preview row links
  to `/staff/invitations` with the existing deep-link query that opens the
  visitor-info modal.
- Point every board link at `/staff/invitations`:
  - `DashboardSidebar`: a new "Dashboard" item →
    `/staff/dashboard`, and "All visitors" → `/staff/invitations`;
  - `ReceptionSidebar` "visits";
  - `PushNotificationsProvider` `basePath`;
  - the redirect after staff visitor registration;
  - the `use-admin-audit-trail` and `use-reception-dashboard` bounces,
    which go to `landingPathFor(user)` where a user is available and to
    `/staff/dashboard` otherwise.

## Risks / Trade-offs

- **[Risk] More email for staff.** A host who is not the actor now gets an
  email and a push for each of the three events. → These events change
  whether or when a visit happens, which is the reason for this change.
  Check-in and check-out stay push only (Non-Goals).
- **[Risk] Different visibility rules.** A POC role with many holders
  pushes all of them, but none of them is emailed. → This is consistent
  with the existing role-identified POC rule. It is documented in the
  spec.
- **[Risk] The `relevantToMe` clause (e) is broad.** Holders of the
  default host role see every invitation. Their "personal" dashboard
  therefore shows branch-wide numbers. → This is intended: it mirrors
  exactly what their board already shows, and the spec's "counts agree"
  scenario locks that in.
- **[Risk] Missing beat in production.** The sweep silently never runs if
  production deploys no beat process, or deploys two. → Add a "Deployment
  requirements" note to `docs/features/background-jobs.md`: exactly one
  `celery beat` per environment, alongside the workers. The deployment
  target is still undecided (`project-rules.md`).
- **[Risk] Lost web bookmarks.** A bookmarked `/staff/dashboard` now shows
  KPIs instead of the board. → The board is one click away in the sidebar.
  Push deep links are updated in the same change, so no notification opens
  the wrong page.
- **[Trade-off] Missing actor in the reject-step path.** `deny_invitation`'s
  new required argument has to be threaded through
  `approvals.reject_step`. A missed call site is a type error that mypy
  catches in the `invitations` scope, not a silent gap.

## Migration Plan

No DB migration or RBAC change is needed. Deploy the API first: the new
endpoint is additive, and the extra notifications are server-side only.
Then deploy the web app. Rollback is a plain revert of either repository.
The old web app keeps working against the new API.
