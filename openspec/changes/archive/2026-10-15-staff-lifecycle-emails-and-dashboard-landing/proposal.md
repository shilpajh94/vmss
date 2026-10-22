## Why

The recent lifecycle work (deny, revert-approval, reschedule, archive,
auto check-out) tells the **visitor** by email, but the **staff** who own the
visit only get a push. A push is easy to miss and leaves no record in an
inbox. Also, the point of contact (POC) gets nothing at all when a visit is
denied, withdrawn or moved. Separately, staff users do not land on a
dashboard after login. They land on the invitations board, because hosts are
not allowed to read the branch-wide dashboard.

## Gap Analysis

What was asked, and what the code does today:

| Question | Today | This change |
|---|---|---|
| Daily cron to auto check-out and archive? | **Already built** (`auto-checkout-and-archive-no-shows`, 2026-10-15). A Celery beat sweep runs every 15 minutes for each active tenant. It checks out expired check-ins and archives approved no-shows the day after their visit. The `vmss-api-celery-beat` DDEV daemon runs it locally. | Nothing to build. The sweep stays as it is, including its two earlier decisions: it sends no notifications, and it does not archive `submitted` requests whose date has passed. Production must run exactly one beat process. That is recorded as a deployment requirement because the deployment target is still open. |
| On revoke, do the visitor and the responsible staff get notified? | The visitor gets an email or SMS (`send_approval_revert_notification`). The host gets a **push only**. The POC gets nothing. | The host and the POC user also get an **email**. The POC also gets a **push**. |
| Same for other lifecycle actions | Deny and reschedule behave like revoke: the visitor gets email or SMS, the host gets a push only, the POC gets nothing. Extend notifies **no one**, even though every other lifecycle action pushes the host. | Deny and reschedule get the same staff email and POC push as revoke. Extend gains the missing host push. |
| Login landing page is the dashboard | Admin → `/admin/dashboard` ✓. Reception (password login) → `/reception/dashboard` ✓. Reception (**SSO**) → staff board ✗. Host and other staff → `/staff/dashboard`, which is actually the invitations **board** ✗. | Add a personal staff dashboard backed by a new endpoint scoped to "my visits". Move the board to `/staff/invitations`. Use one shared landing rule for both login paths. |

Reviewed and left out of scope (see design.md Non-Goals): staff email on
check-in, check-out and extend (these stay push only); a visitor email on
extend; reminders for pending approvals; archiving stale `submitted`
requests.

## What Changes

- **Staff lifecycle email.** When an invitation is **denied**, has its
  **approval reverted**, or is **rescheduled**, the system emails the
  invitation's responsible staff. These are the resolved host (`host_id`) and
  the named POC user (`poc_user_id`). Inactive users are skipped. A person who
  holds both roles gets one email. The staff member who performed the action
  gets none. Staff emails include the deny or revert reason. The visitor
  email still leaves the revert reason out. This change adds one new Celery
  task, sent once per recipient, and one new branded template,
  `staff_lifecycle_update`.
- **POC push on the same three events.** A POC user gets a push. If the POC
  is a role, every holder of that role at the invitation's branch gets a
  push. This follows the existing rule that a role-identified POC gets push
  only, never email. The host's existing push does not change.
- **Extend pushes the host.** `PATCH /invitations/{id}/extend` sends the
  resolved host a push with the new expiry. This is the one lifecycle action
  that currently notifies no one.
- **Personal staff dashboard API.** Adds
  `GET /api/v1/admin/dashboard/my-overview`, available to any authenticated
  tenant user. It returns counts over the caller's `relevantToMe` invitation
  set: visits today, inside now, awaiting approval and upcoming. It also
  returns a bounded preview of upcoming visitors. It uses the same
  relevance rule as `GET /invitations?relevantToMe=true`, so the dashboard
  and the board always agree. The existing branch-wide dashboard endpoints
  and their `invitations:view-all` gate do not change.
- **Web (VMMS_WEB) landing.** `/staff/dashboard` becomes a KPI dashboard
  page built on the new endpoint. The current board moves to
  `/staff/invitations`, and every link to it is updated: sidebars, push
  deep links, the post-registration redirect and the audit-trail bounce.
  Both login hooks (password and SSO) share one `landingPathFor(user)`
  helper: admin → `/admin/dashboard`, reception → `/reception/dashboard`,
  everyone else → `/staff/dashboard`.

None of this is **BREAKING** at the API level. Every API change is a new
endpoint, a new notification or a new template. The `/staff/dashboard` web
URL changes what it shows. A bookmark to it now opens the dashboard, and the
board is one click away in the sidebar.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: deny, revert-approval and reschedule also email the host
  and POC user and push the POC. Extend pushes the host.
- `email-notifications`: a new "Staff lifecycle update" notification type,
  with tone, pill, heading and sections for each event.
- `dashboard`: a new personal `my-overview` endpoint scoped by
  `relevantToMe`.

## Impact

- **API code**: `invitations/{service,tasks,push_notifications}.py`, a new
  template `core/email_templates/staff_lifecycle_update.html`,
  `dashboard/{router,service,repository,schemas}.py`. The new dashboard
  query reuses `invitations/repository.py::_relevant_to_me_filter`, which
  needs a small public wrapper.
- **DB**: none. There is no migration.
- **RBAC**: none. `my-overview` follows the `relevantToMe` gate (any
  authenticated user).
- **Web code (VMMS_WEB)**: `App.tsx` routes, a new staff dashboard page and
  hook, the renamed board page, `DashboardSidebar`, `ReceptionSidebar`,
  `PushNotificationsProvider`, both login hooks, the staff registration
  page, the audit-trail hook, a new dashboard use case and repository
  method.
- **Docs**: `docs/features/{invitations,dashboard,background-jobs}.md`.
- **Dependencies**: none.
