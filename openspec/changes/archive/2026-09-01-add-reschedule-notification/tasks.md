## 1. Notification task

- [x] 1.1 Add `send_reschedule_notification` to
      `src/vmss_api/invitations/tasks.py`, structurally identical to
      `send_denial_notification` (Celery-bound wrapper with
      `_RETRY_KWARGS`, `structlog` context binding, `ERROR` log on retry
      exhaustion, an `engine.dispose()` in a `finally`) — only the
      subject/body and log-event name differ.
- [x] 1.2 Inner `_send_reschedule_notification(tenant_schema, invitation_id)`:
      load the invitation (return early if missing, matching the other
      three tasks' redelivery-safe pattern), build the subject/body
      ("Your visit has been rescheduled. New date: {preferredVisitDate},
      time: {preferredVisitTime}. Tracking ID: {tracking_id}."), call
      `_dispatch(invitation, subject=..., body=...)` with no `attachment`.

## 2. Service wiring

- [x] 2.1 Add `tenant: Tenant` keyword parameter to
      `reschedule_invitation` (`invitations/service.py`), matching
      `approve_invitation`/`deny_invitation`'s existing signature shape.
- [x] 2.2 After `await tenant_db.commit()`, enqueue
      `tasks.send_reschedule_notification.delay(request_id=_current_request_id(),
      tenant_schema=tenant.schema_name, invitation_id=str(updated.id))` —
      same call shape as the existing three enqueue sites.

## 3. Router wiring

- [x] 3.1 `invitations/router.py`'s `reschedule_invitation` handler: pass
      `tenant=tenant` at the `service.reschedule_invitation(...)` call site
      (`tenant` is already resolved there via `Depends(get_tenant)`).

## 4. Tests (per `testing-standards.md`)

- [x] 4.1 Endpoint-level: a successful reschedule enqueues
      `send_reschedule_notification.delay` with the correct
      `request_id`/`tenant_schema`/`invitation_id` kwargs — mirror
      `test_approve_invitation_success`'s `monkeypatch.setattr(tasks.send_*
      .delay, ...)` pattern.
- [x] 4.2 Extend the existing `test_reschedule_invitation_after_check_in_
      rejected` (409 case) to also assert no notification task is enqueued.
- [x] 4.3 Extend the existing `test_reschedule_invitation_requires_
      permission` (403 case) to also assert no notification task is
      enqueued.
- [x] 4.4 A reschedule for a primary contact whose `preferredContactMethod`
      is `sms` dispatches via `notifications.sms_sender`, not
      `email_sender` — monkeypatch both senders and assert only the SMS
      one was called.

## 5. Documentation

- [x] 5.1 Update `docs/features/invitations.md`'s notification summary to
      mention the reschedule notification alongside the existing
      creation/approval/denial ones.
