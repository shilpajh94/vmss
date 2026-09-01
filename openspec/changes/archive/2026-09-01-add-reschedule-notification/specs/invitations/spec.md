## ADDED Requirements

### Requirement: Reschedule Dispatches a Notification to the Primary Contact
WHEN a caller successfully reschedules an invitation via `PATCH
/invitations/{id}/reschedule`, the system SHALL dispatch a reschedule
notification to the primary contact, stating the invitation's tracking ID
and its new `preferredVisitDate`/`preferredVisitTime`. The notification
SHALL be sent via the primary contact's `preferredContactMethod` (`email`
sends an email, `sms` sends a text) — the same channel-routing rule the
creation, approval, and denial notifications already follow; group
registrations are notified the same way as individual ones, since only the
primary contact is ever notified for any invitation lifecycle event today.
The notification SHALL carry no QR code — a reschedule does not re-approve
the visit or invalidate a QR already issued. Dispatch SHALL happen
asynchronously (a background task), never inline in the request path, and
only after the reschedule is committed — a request rejected because the
invitation is not in a reschedulable status, or because the caller lacks
branch access, SHALL NOT dispatch any notification.

#### Scenario: Successful reschedule notifies the primary contact by email
- **WHEN** a caller with `invitations:reschedule` at the invitation's branch
  successfully reschedules an invitation whose primary contact's
  `preferredContactMethod` is `email`
- **THEN** an email is dispatched to the primary contact's email address,
  stating the tracking ID and the new `preferredVisitDate`/
  `preferredVisitTime`, with no QR code attached

#### Scenario: Successful reschedule notifies the primary contact by SMS when preferred
- **WHEN** a caller successfully reschedules an invitation whose primary
  contact's `preferredContactMethod` is `sms`
- **THEN** a text message is dispatched to the primary contact's phone
  number instead of an email, stating the same tracking ID and new
  date/time

#### Scenario: Rejected reschedule (ineligible status) dispatches no notification
- **WHEN** a caller attempts to reschedule an invitation that is not
  currently `submitted` or `approved` (e.g. already `checked_in`), and the
  request is rejected with 409
- **THEN** no reschedule notification is dispatched

#### Scenario: Rejected reschedule (no branch access) dispatches no notification
- **WHEN** a caller without branch access to the invitation attempts to
  reschedule it, and the request is rejected with 403
- **THEN** no reschedule notification is dispatched
