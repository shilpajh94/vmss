## Why

Staff never learn about invitation events except by refreshing the portal: a
host or an Admin-role approver has no signal that a visitor submitted a
registration awaiting their action, that a prior step in a multi-step
workflow just cleared and now waits on them, or that their visitor has been
denied, rescheduled, or has checked in/out. The visitor already gets an
email/SMS at each of these points (`invitations/notifications.py`); staff get
nothing. Push notifications on the web portal and the Flutter app close that
gap for the people who act on or care about an invitation, without changing
the visitor-facing channel at all.

## What Changes

- Add a general-purpose `notifications` capability: staff register a device
  (web push subscription or FCM token) against their user account, and a new
  push-dispatch primitive sends a notification to one or more users by id or
  to every user holding a given role at a branch. Built as the standalone
  `notifications/` package `project-rules.md` and `invitations/notifications.py`
  already flagged as coming "once a second feature needs it" — this is that
  feature.
- Firebase Cloud Messaging (FCM) is the push provider for both channels: FCM
  Web Push for the React portal, FCM for the Flutter app (Android + iOS). One
  provider, one token type, one Celery dispatch path.
- Wire push notifications into the existing invitation/approval lifecycle,
  targeted at staff only (never the visitor, whose email/SMS notifications
  are unchanged):
  - **Invitation submitted** (leaves `create_invitation` as `submitted`, not
    auto-approved): push the current pending approval step's approver(s) —
    the resolved host if the step is host-identified, or every user holding
    the step's role at the invitation's branch.
  - **A step is approved and a next step becomes current**
    (`approvals.service.approve_step` → `_activate_next_step`): push the new
    current step's approver(s), same resolution as above.
  - **Invitation approved** (last step cleared, or a workflow-free invitation
    approved directly): push the invitation's host, if one resolved.
  - **Invitation denied** (`deny_invitation`, including via
    `approvals.service.reject_step`): push the invitation's host, if one
    resolved.
  - **Invitation rescheduled**: push the invitation's host, if one resolved.
  - **Invitation checked in / checked out**: push the invitation's host, if
    one resolved.
  - An invitation with no resolved host and no pending step's role holders
    has no push recipient — that action logs at `WARNING` and is otherwise a
    no-op (a "which visitors are hostless" gap is out of scope for this
    change).
- Auto-approved invitations (company-level `auto_approve_pre_registered_visitors`)
  never create approval steps, so this change never enqueues a "submitted,
  needs your action" push for them — only the existing visitor email fires.

## Capabilities

### New Capabilities
- `notifications`: device registration (web push / FCM token per user) and a
  push-dispatch primitive addressed by user id(s) or by role-at-branch,
  built on Firebase Cloud Messaging.

### Modified Capabilities
- `invitations`: submission, approval, denial, reschedule, check-in, and
  check-out each additionally dispatch a staff-facing push notification
  (recipients as described above); the existing visitor email/SMS
  notifications are unchanged.
- `approvals`: activating a step (at submission, and when a prior step's
  approval advances the workflow) dispatches a push notification to that
  step's approver(s).

## Impact

- **New code**: `src/vmss_api/notifications/` (`models.py` — a
  `DeviceToken` table; `repository.py`; `service.py`; `schemas.py`;
  `router.py` — `POST`/`DELETE /notifications/devices`; `tasks.py` — the
  Celery push-dispatch task calling the FCM Admin SDK; `tests.py`).
- **Changed code**: `src/vmss_api/invitations/service.py` (enqueue a push
  after each of the six actions listed above),
  `src/vmss_api/approvals/service.py::_activate_next_step` and `approve_step`
  (enqueue a push when a step becomes current),
  `src/vmss_api/auth/repository.py` (new "list users holding role X at
  branch Y" query — `approvals/service.py` today only checks one specific
  user, never lists holders), `src/vmss_api/core/celery_app.py` (register
  `vmss_api.notifications` for autodiscovery and queue routing),
  `src/vmss_api/api.py` / `main.py` (register the new router + OpenAPI tag
  per `api-documentation.md` §2), `.env.example` (new `FCM_*` settings).
- **Dependencies**: adds the Firebase Admin SDK (`firebase-admin`) via
  `uv add`.
- **Out of scope**: the React portal's and Flutter app's own client-side
  push registration/permission-prompt UI and service-worker code — those are
  separate repos; this change only builds the API side (registration
  endpoint + dispatch). Notification preferences/opt-out per staff user are
  also out of scope; every user with a registered device receives every push
  their role/host relationship entitles them to.
