## Context

See `proposal.md` for motivation. Relevant existing state:

- `invitations/notifications.py` and `invitations/tasks.py` dispatch
  visitor-facing email/SMS only, via `_dispatch()`'s
  `primary_contact_preferred_contact_method` branch. That module's own
  docstring already earmarks a standalone `notifications/` package as the
  next step "once a second feature needs it" — this change is that feature.
- `approvals/models.py::InvitationApprovalStep.approver_role_id` /
  `approver_user_id` is a CHECK-enforced XOR: a step is either host-identified
  (specific user) or role-identified (any holder of a role, scoped by branch
  via `UserBranchRole`). `approvals/service.py::_user_holds_role_at_branch`
  can check *one* user against a role, but nothing today lists *every* user
  holding a role at a branch — that's a new query this change needs.
- `approvals/service.py::approve_step` calls `_activate_next_step` when a
  next step exists, or `invitations_service.approve_invitation` when the
  step just approved was the last one. `reject_step` always calls
  `invitations_service.deny_invitation`. These are the two places a
  "step became current" push and an "invitation resolved" push are triggered
  from, respectively.
- No push infrastructure (device tokens, FCM client, dispatch task) exists
  anywhere in the codebase today.

## Goals / Non-Goals

**Goals:**
- Ship the general `notifications/` package (device registration + a
  role-or-user-addressed push primitive) so the *next* feature that needs
  push (not just invitations) has somewhere to plug in.
- Wire that primitive into every point in the invitation/approval lifecycle
  identified in the proposal, using FCM for both web and the Flutter app.
- Keep the existing visitor email/SMS path completely unchanged — this is an
  additive staff-facing channel, not a replacement.

**Non-Goals:**
- Client-side registration UI/service-worker code for the React portal or
  Flutter app (separate repos).
- Per-user notification preferences/opt-out, notification history/read
  receipts, or a generic in-app notification center — this change only
  builds device registration + dispatch.
- Extending push to any capability outside invitations/approvals (blacklist,
  admin config, login) — explicitly deferred per the proposal's scoping
  decision.

## Decisions

### Decision 1: `notifications/` owns device tokens; features never call FCM directly
A new tenant-scoped `DeviceToken` model (`user_id`, `platform` — `web`/
`android`/`ios`, `fcm_token`, `last_seen_at`) lives in
`notifications/models.py`. `invitations/service.py` and
`approvals/service.py` only ever call a dispatch function
(`notifications.service.notify_user(user_id, ...)` /
`notify_role_at_branch(role_id, branch_id, ...)`), never touch `DeviceToken`
or the FCM SDK themselves — same layering discipline
`fastapi-architecture.md` §2 already requires between features. This mirrors
how `invitations/notifications.py` wraps `core/emailing.py`'s SMTP primitive
today, just as its own package instead of a shared `core/` module, since push
recipients/targeting logic (role-at-branch resolution) is genuinely
notifications-domain logic, not a `core/` cross-cutting concern.

**Alternative considered**: put the FCM client directly in `core/` (like
`core/emailing.py`). Rejected — `core/emailing.py` is a stateless SMTP
sender with no domain model; push has a real owned table (`DeviceToken`) and
domain logic (role-at-branch resolution), which is what `project-rules.md`
says warrants a full feature package, not a `core/` utility module.

### Decision 2: One Celery task per dispatch call, addressed by resolved recipient — not resolved inside the task
`invitations/service.py`/`approvals/service.py` resolve *who* the recipient
is (host user id, or role id + branch id) synchronously, in the same
transaction as the state change, then enqueue
`notifications.tasks.send_push.delay(...)` with that resolved target — the
task itself only resolves *devices* for that target and calls FCM, it never
re-queries "what is this invitation's host" or "what step is current now"
(that state may have moved on by the time the task runs). This mirrors
`invitations/tasks.py`'s existing pattern of resolving all needed data
up front and passing plain ids as task arguments (`background-jobs.md` §2:
pass `tenant_id`/ids, resolve inside the task body only what's safe to
resolve fresh — devices, not workflow state).

**Alternative considered**: pass `invitation_id` + "notify current approver"
and let the task re-resolve the current step. Rejected — by the time a
retried task runs, a different step could be current (e.g. an admin
overrode and approved out of band), and the task would notify the wrong
person. Resolving the recipient synchronously, before enqueue, is correct by
construction: it captures "who needed to know about this specific event."

### Decision 3: Role-at-branch fan-out is a new `auth/repository.py` query, not duplicated in `approvals/`
`_user_holds_role_at_branch` (one user, one role) already lives in
`approvals/service.py`. The new "list every user holding role R at branch B"
query is added to `auth/repository.py::UserRepository` (it's fundamentally a
`User`/`UserBranchRole` join, same table family every other role-membership
query in that repository already covers), and `approvals/service.py` /
`invitations/service.py` call it rather than each writing their own query.

### Decision 4: FCM Admin SDK server-side; no separate Web Push/VAPID stack
Per the proposal's tech-stack answer, FCM's Web Push transport covers the
React portal (no separate VAPID keypair/library), and FCM covers the
Flutter app for both Android and iOS. `notifications/tasks.py` calls the
`firebase-admin` Python SDK's `messaging.send_each()` (batch send) with one
message per device token resolved for the target. A per-token "not
registered" error from that batch response is what triggers the token
deletion in `specs/notifications/spec.md`'s "invalid token" requirement.

### Decision 5: Push failures are logged, not surfaced — no user-visible retry/backoff signal
Consistent with `background-jobs.md` §3/§4: `send_push` declares
`autoretry_for`/`retry_backoff`/`max_retries` like every other task in
`invitations/tasks.py`, and logs `ERROR` with `tenant_id` + target +
exception on final exhaustion. There is no mechanism for a staff user to see
"this push failed" in the UI — same posture the existing email/SMS
notifications already have (§4 of `background-jobs.md` covers reprocessing
via logs, not a user-facing status).

## Risks / Trade-offs

- **[Risk]** A tenant with many users holding an Admin-equivalent role at a
  branch fans out to every one of them on every role-identified step
  activation — a busy tenant could generate a lot of push traffic to a large
  admin group. → **Mitigation**: out of scope to throttle in this change;
  flagged as a follow-up if it proves noisy in practice (e.g. a "notify only
  N random holders" or digest scheme), consistent with the proposal's
  explicit non-goal of notification preferences.
- **[Risk]** FCM Web Push requires the React portal to actually request
  browser notification permission and register a service worker — until
  that ships in the portal repo, staff on web get zero push despite the API
  being fully wired. → **Mitigation**: this is the proposal's stated
  out-of-scope client work; the API's device-registration endpoint is
  usable the moment the portal team implements their side, no API rework
  needed.
- **[Trade-off]** Resolving recipients synchronously in the request path
  (Decision 2) adds one extra query (role-holder lookup, or none for a
  host-identified step) to `create_invitation`/`approve_step` before the
  task enqueue. Accepted — it's a single indexed `UserBranchRole` join, and
  correctness (notifying the right person) matters more than shaving one
  query off an already multi-query request.

## Migration Plan

- New `DeviceToken` table via `alembic_tenant/` (per-tenant schema
  migration, applied to every tenant schema per `database-architecture.md`
  §5) — purely additive, no backfill needed (a staff user's first device
  registration populates their own row lazily).
- No changes to any existing table or endpoint's request/response contract —
  every wiring point in `invitations/service.py`/`approvals/service.py` adds
  a `.delay()` call after an existing commit, matching the existing
  dispatch-after-commit pattern; nothing about the HTTP contract changes, so
  no `api-conventions.md` §2 version bump is needed.
- Rollout order: land `notifications/` (table + registration endpoints +
  dispatch task) first, verified in isolation via its own `tests.py`, then
  wire the six invitation/approval call sites in a follow-up commit within
  the same change — if FCM credentials aren't yet available in an
  environment, `send_push` fails closed (logs `ERROR`, retries, eventually
  exhausts) the same way `UnconfiguredSmsSender` does today for SMS, rather
  than silently no-op.
- Rollback: dropping the new table/router is safe in isolation (nothing else
  depends on `notifications/` yet); reverting the six call-site wirings is a
  pure code revert with no data migration to undo.
