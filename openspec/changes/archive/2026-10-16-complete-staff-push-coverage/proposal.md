## Why

Staff should get a push for every invitation lifecycle event they're
responsible for, without having to check their inbox. An audit of every
dispatch site shows the **host** is already pushed for every event. The
**point of contact (POC)** is not. `staff-lifecycle-emails-and-dashboard-landing`
(2026-10-15) pushed the POC only on deny, revert and reschedule. So the POC
gets nothing when the visit they coordinate is approved, when the visitor
arrives or leaves, when the pass is extended, or when the visit details
change. Arrival is the moment a POC needs to know about most.

## Gap Analysis

Each row is one staff-facing event. "Host" means the resolved `host_id`;
"POC" means `poc_user_id` or every holder of `poc_role_id` at the branch.

| Event | Host push today | POC push today | This change |
|---|---|---|---|
| Submitted → first approver(s) | n/a (step push) | n/a | unchanged |
| Next step activated | n/a (step push) | n/a | unchanged |
| Delegated / host named | ✓ `host_assigned` | n/a | unchanged |
| POC named (edit) | n/a | ✓ `poc_assigned` | unchanged |
| **Approved** | ✓ | ✗ | **POC pushed** |
| Denied | ✓ | ✓ | unchanged |
| Approval reverted | ✓ | ✓ | unchanged |
| Rescheduled | ✓ | ✓ | unchanged |
| **Checked in** (staff, tracking id, QR, kiosk) | ✓ | ✗ | **POC pushed** |
| **Checked out** (staff, QR) | ✓ | ✗ | **POC pushed** |
| **Pass extended** | ✓ | ✗ | **POC pushed** |
| **Details edited** | ✓ | ✗ | **POC pushed** |

Reviewed and deliberately left unchanged. Each of these is an existing
decision, or has no staff recipient to push:

- **Admin- and `host`-role triage push.** On submission, these roles get
  the triage email but no push. That is the
  `exclude-admin-role-only-from-push` decision and the delegation-only role
  rule. Lifting it would broadcast "act on this now" company-wide.
- **Auto-approved creation.** `host_id` is never set at creation, and the
  POC can only be named by an edit. An auto-approved invitation has no
  resolved staff recipient, and the spec "Auto-Approved Invitations Do Not
  Trigger a Submission Push" stands.
- **Visit-lifecycle sweep** (auto check-out, no-show archive). This stays
  silent, per the `visit-lifecycle-sweep` spec. The sweep runs every 15
  minutes, so a push from it would arrive out of hours.
- **Watchlist-flagged invitations and kiosk devices awaiting approval.** No
  recipient role is defined for either, so they're recorded as open
  questions in design.md and not built here.
- **Staff emails.** No staff email is added or removed. Push is added
  alongside the existing emails.

## What Changes

- **POC push on approve, check-in, check-out, extend and edit.** These are
  the same five events that already push the host. A POC user gets a push.
  For a POC role, every holder at the invitation's branch or company-wide
  gets one. The rules match the deny/revert/reschedule POC push:
  - the actor and the host are excluded, because the host already gets
    `_notify_host`'s push;
  - a role fan-out carries `reason: "lifecycle_update"`;
  - payloads exclude sensitive visitor data;
  - an invitation with no POC skips the push without failing the request.
- **An edit that names a new POC sends that POC only `poc_assigned`.** The
  `edited` push goes only to a POC that was already in place before the
  edit, so the new POC isn't pushed twice for one edit.
- **The actor is threaded through approve and extend.** These two paths
  need it to exclude the acting staff member.
  `invitations.service.approve_invitation` (called from
  `POST /invitations/{id}/approve` and from `approvals.service.approve_step`)
  and `extend_invitation` gain an optional `actor_user_id`. QR and kiosk
  check-in and check-out have no human actor, so `None` excludes no one.
- **One POC-push helper.** The POC half of `_notify_responsible_staff` is
  extracted so all eight lifecycle events share it, rather than copying
  the exclusion rules five more times.

Nothing here is **BREAKING**. No endpoint, request or response shape
changes. The push payload keeps its existing keys and `action` values. The
web client (VMMS_WEB `PushNotificationsProvider`) routes every push by
`invitationId`, so it needs no change.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: "Denial, Approval Revert, and Reschedule Push the Point of
  Contact" widens to cover every lifecycle event that pushes the host:
  approval, check-in, check-out, pass extension and detail edits.

## Impact

- **API code**: `invitations/service.py`. That means `_notify_responsible_staff`
  and a new POC-push helper, plus `approve_invitation`, `_perform_check_in`,
  `check_in_by_qr_token`, `check_out_by_qr_token`, `check_out_invitation`,
  `edit_invitation` and `extend_invitation`. Also `invitations/router.py`
  (the approve and extend routes pass the caller's id) and
  `approvals/service.py::approve_step` (passes the approver's id).
- **Tests**: `invitations` tests, and an `approvals` test for the
  final-step path.
- **DB / migrations / RBAC / settings**: none.
- **Web / mobile clients**: none required.
- **Docs**: `docs/features/invitations.md`, notifications section.
