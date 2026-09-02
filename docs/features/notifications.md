# Notifications (Push)

Staff device registration and a push-notification dispatch primitive, built
on Firebase Cloud Messaging (FCM), for the React portal and the Flutter
app. Wired into the invitation/approval lifecycle so a host or approver
learns of an action awaiting or affecting them without refreshing the
portal — never the visitor, whose email/SMS notifications
(`docs/features/invitations.md`) are unchanged. See
`openspec/changes/add-invitation-push-notifications/` for the
proposal/design this feature was built from.

`notifications` is the general-purpose package `project-rules.md` and
`invitations/notifications.py`'s own docstring flagged as coming "once a
second feature needs it" — this is that feature. Other capabilities never
touch its `DeviceToken` table or the FCM SDK directly; they call
`notifications.service.notify_user`/`notify_role_at_branch`/
`notify_step_approver`.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/notifications/devices` | Any authenticated staff user (self-service, like `GET /auth/me` — no permission check) | Registers/updates a device token (`fcmToken`, `platform`: `web`/`android`/`ios`) against the caller's own account. Re-registering an already-known token updates it in place; a token previously owned by a *different* user is reassigned to the caller (a device is physically one browser/app install). |
| DELETE | `/api/v1/notifications/devices/{fcmToken}` | Any authenticated staff user | Removes one of the caller's own device tokens. A no-op (still 200), not an error, if the token was never registered or belongs to someone else. |

## Dispatch primitive

`notifications/service.py` exposes three functions other features call:

- `notify_user(*, tenant_schema, user_id, title, body, data)` — pushes to
  every device registered to one specific user.
- `notify_role_at_branch(tenant_db, *, tenant_schema, role_id, branch_id,
  title, body, data)` — resolves every user holding `role_id` via a
  `UserBranchRole` scoped to `branch_id`, or company-wide (`branch_id IS
  NULL`), then pushes to all of them. Zero holders logs `WARNING`
  (`push_notify_role_no_holders`) and is otherwise a no-op — not an error
  for the calling action.
- `notify_step_approver(tenant_db, *, tenant_schema, approver_user_id,
  approver_role_id, branch_id, title, body, data)` — the shared entry point
  `invitations`/`approvals` call with an `InvitationApprovalStep`'s own
  `approver_user_id`/`approver_role_id` XOR, routing to whichever of the two
  functions above applies.

A recipient resolved this way is never re-derived inside the Celery task —
`notifications/tasks.py::send_push` takes the already-resolved `user_ids`
and only resolves *devices* for them fresh at send time (which devices a
user has can change between enqueue and execution; who the recipient is
should not).

## Recipient resolution used by `invitations`/`approvals`

| Event | Recipient |
|---|---|
| Invitation submitted (workflow-backed, not auto-approved) | The newly-created first approval step's approver — host if host-identified, else every holder of the step's role at the invitation's branch, unless that role is the tenant's standard `admin` role. |
| A step is approved, activating the next step | The newly-current step's approver, same resolution as above. |
| Invitation approved / denied / rescheduled / checked in / checked out | The invitation's own host (`hostId`), if one resolved. No host means no push — not an error. |

A role-identified step pushes to every holder of that role, **except** the
tenant's standard `admin` role, which never receives push
(`exclude-admin-role-only-from-push`). `admin` is matched by name,
case-insensitively — it's seeded non-renameable/non-deletable per
`auth/rbac_catalog.py`, so it's a reliable identifier across every tenant. A
role id that can't be resolved to a row dispatches normally (fails open)
rather than silently dropping the push.

An auto-approved invitation never has approval steps, so its creation never
fires a "submitted, awaiting your approval" push — only the visitor's
existing auto-approval email fires. A `submitted` invitation with no
resolved host and no active workflow rules has no approval step at all;
that logs `WARNING` (`push_notify_no_approval_step`) rather than silently
doing nothing.

## Payload content

Every push payload is built by `invitations/push_notifications.py` from
`primary_contact_full_name`/`tracking_id`/`id` only — the one place
enforcing that a payload never carries identity-document data, raw OTP
codes, or other data `security-architecture.md` §2/§4 classifies as
sensitive, so it can't be bypassed per call site.

## Failure handling

- Push dispatch always runs as a Celery task enqueued after the triggering
  action's own commit, never inline in the request path — a push failure
  (including full retry exhaustion) never surfaces on the triggering
  action's HTTP response.
- `send_push` declares `autoretry_for`/`retry_backoff`/`max_retries` like
  every task in `invitations/tasks.py`, and logs `ERROR`
  (`push_dispatch_exhausted`) with `tenant_schema`/`user_ids` on final
  exhaustion.
- A token FCM reports as "not registered" (app uninstalled, browser data
  cleared) is deleted from `device_tokens` so future dispatches stop
  attempting delivery to it — a transient send failure is left for the
  task's own retry instead.

## Config knobs

| Setting | Default | Purpose |
|---|---|---|
| `FCM_CREDENTIALS_PATH` | unset | Path to a Firebase service-account key JSON file. Left unset by default; `notifications/fcm.py` fails loudly (`FcmNotConfiguredError`) the first time a push is actually attempted, rather than silently no-op'ing — same posture `TWILIO_*`/`SMS_GATEWAY_*` already have. |

## Not yet built (flagged, not silently dropped)

- **Client-side registration UI.** The React portal's and Flutter app's own
  push-permission prompts and service-worker/FCM-token wiring are separate
  repos; this feature only builds the API side (registration endpoint +
  dispatch). The endpoint is usable the moment either client implements
  its side.
- **Notification preferences/opt-out.** Every user with a registered
  device receives every push their role/host relationship entitles them
  to; there's no per-user mute/preference setting.
- **Push beyond `invitations`/`approvals`.** Blacklist changes, admin
  config changes, and login are not wired to push yet — deliberately
  scoped out of this change (see the proposal), left for a later change to
  pick up using the same `notify_user`/`notify_role_at_branch` primitives.
