## Why

Front-end and operational feedback surfaced four gaps in the invitation/check-in
flow: QR check-in only enforces the invitation's expiry, letting a visitor scan in
before their scheduled visit date; the invitation list endpoint doesn't surface the
profile photo the detail endpoint already returns, forcing an extra lookup per row;
and a host currently has no email trail that an invitation naming them was created
(only an in-app push, which is easy to miss). A fourth reported issue — QR check-in
toggling to check-out on a repeat scan — was investigated and found to already be
correctly implemented (see Impact); no change is needed there, but it's called out
explicitly so the reporter's concern is addressed in this proposal.

## What Changes

- QR check-in (`PATCH /api/v2/invitations/qr/{token}/check-in`) additionally
  rejects a scan attempted before the invitation's scheduled visit date
  (`preferredVisitDate`), using a date-only comparison in the tenant's local
  calendar day. An invitation with no `preferredVisitDate` set skips this check
  and falls back to today's expiry-only gating. The existing expiry check
  (`expiresAt`) is unchanged, and check-out remains exempt from both checks.
- `GET /invitations` (the branch-scoped list endpoint) adds the primary contact's
  profile photo URL to each row, matching what the tracking/detail responses
  already return.
- New: on invitation creation, when the invitation has a resolved host
  (`hostId` present), the system dispatches an informational email to that host's
  address stating an invitation naming them was received — asynchronously, via the
  same Celery dispatch pattern already used for visitor confirmation/approval
  email, and without delaying the creation response. An invitation with no
  resolved host skips this dispatch without failing creation.
- No code change for QR check-in-vs-check-out toggling: `check_in_by_qr_token`
  already rejects a repeat entry scan on an already-`checked_in` invitation with
  409 rather than toggling it to `checked_out` (`invitations/service.py:715-759`).
  This proposal formalizes that as an explicit regression-guarded expectation
  (task to confirm/add a test) rather than introducing new behavior.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: three requirement changes —
  1. "QR Check-In Endpoint Transitions an Eligible Visitor to Checked-In" gains a
     scheduled-date gate (new scenario), in addition to the existing expiry gate.
  2. "Employee Lists Invitations at Their Authorized Branches" gains a profile
     photo field on each list row.
  3. New requirement: invitation creation dispatches an email to the resolved
     host, alongside the existing push-notification requirement for other host
     events.

## Impact

- **Affected code**:
  - `src/vmss_api/invitations/service.py` — `check_in_by_qr_token` (new
    scheduled-date check, mirroring the existing `expires_at` check at
    lines 747-750); `create_invitation` (new host-email task enqueue, following
    the existing `tasks.send_approval_notification.delay(...)` pattern at
    lines 505-510).
  - `src/vmss_api/invitations/repository.py` — `check_in_by_qr_if_eligible`
    (extend the atomic `WHERE` clause with the scheduled-date condition, same
    approach as the existing `expires_at > now()` clause).
  - `src/vmss_api/invitations/schemas.py` — add a photo URL field to the list
    response schema (the field/URL-resolution logic already exists for detail
    schemas via `_resolve_photo_url()` in `router.py`).
  - `src/vmss_api/invitations/router.py` — wire the photo URL into the list
    endpoint's row construction.
  - `src/vmss_api/invitations/tasks.py` — new Celery task
    `send_host_creation_notification` (or similar), following the existing
    `_RETRY_KWARGS` / `tenant_session_scope` / idempotent-lookup pattern used by
    `send_approval_notification` et al.; resolves the host's email via
    `UserRepository(tenant_db).get_active(invitation.host_id)`.
  - `src/vmss_api/invitations/tests.py` — new/updated tests for all three
    behavior changes, plus an explicit regression test for the no-toggle
    check-in behavior (item 4).
- **No new dependencies, no DB migration** (reuses the existing
  `preferred_visit_date` column and existing email-sending infrastructure).
- **No breaking change**: all three changes are additive to existing endpoints'
  behavior/response shape; no field is removed or renamed, no status code for an
  existing success case changes.
