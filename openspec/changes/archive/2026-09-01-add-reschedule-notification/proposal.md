## Why

`PATCH /invitations/{id}/reschedule` changes an invitation's visit date/time
but dispatches no notification at all today — the primary contact who
receives a confirmation on creation, approval, and denial gets nothing when
their visit is moved, and has no way to know the new date/time except by
checking back through the tracking lookup.

## What Changes

- Add a reschedule notification, dispatched (via the existing Celery
  pattern, never inline in the request path) after a successful reschedule,
  to the invitation's primary contact only — matching the existing
  create/approve/deny notifications, none of which reach co-visitors on a
  group registration either.
- The notification follows `primary_contact_preferred_contact_method`
  exactly like the existing notifications (`email` sends an email, `sms`
  sends a text) — not an unconditional email regardless of preference.
- Notification body states the new `preferredVisitDate`/`preferredVisitTime`
  and the tracking ID; no QR code (the visit isn't being re-approved, and
  the existing QR from creation/approval is still valid for check-in).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `invitations`: adds a requirement that a successful reschedule dispatches
  a notification to the primary contact, stating the new date/time.

## Impact

- **Code**: `src/vmss_api/invitations/tasks.py` (new
  `send_reschedule_notification` Celery task, following the existing
  `send_approval_notification`/`send_denial_notification` pattern),
  `src/vmss_api/invitations/service.py::reschedule_invitation` (enqueue the
  task after commit), `src/vmss_api/invitations/notifications.py` (new
  body-composition helper if the existing ones aren't directly reusable).
- **API contract**: no request/response shape change — `PATCH
  /invitations/{id}/reschedule`'s existing 200/409/403 behavior is
  unchanged; this only adds a side effect.
- **Out of scope**: this endpoint still has no `Idempotency-Key` handling
  (unlike approve/check-in/check-out/deny) — a client retry can call
  reschedule more than once for what was meant as one logical action, each
  one dispatching its own notification. Documented as an accepted risk in
  design.md; adding idempotency to this endpoint is a separate concern this
  change does not take on.
