## Why

Today a visitor (self-service pre-registration or walk-in) must pick a specific
named host, and the resulting invitation is fixed once created except for a
handful of narrow fields (date/time via reschedule, expiry via extend). Neither
matches how front-office actually works: a visitor rarely knows who their real
point of contact should be, and reception staff routinely need to correct
misrouted or unavailable-slot invitations after the fact. Email is currently
one-line plain-text f-strings with no branding and no point-of-contact detail,
which undermines the "who's inside" / visitor-confidence story the product
depends on. This change makes the front-office role the default owner of every
new invitation, lets that role delegate to the real host, opens up editing of
everything except the visitor's own personal details, and replaces ad hoc
notification/email bodies with a proper templated, branded system.

Companion change: `VMMS_WEB` change `role-based-invitation-workflow` implements
the corresponding UI (hiding the host field, an Edit Invitation action, and
notification-center changes) against the contract this change defines.

## What Changes

- **BREAKING**: `POST /invitations` and `POST /registrations/walk-in` no
  longer accept `hostId`/`hostNameOrEmail` in the request body. The host is
  never client-supplied at creation, in either the visitor self-service
  channel or the staff-assisted registration channel — both are treated the
  same way.
- Every new invitation's initial approval step (`stepOrder=0`) is
  **role-identified for the tenant's `reception` role** instead of
  host-identified. `reception` already carries `invitations:approve`/`deny`/
  etc., so no new role or permission-catalog entry is introduced.
- Every active holder of the `reception` role at the invitation's branch is
  notified (push + email) when a new invitation is submitted to them, the
  same role-fan-out primitive already used elsewhere
  (`notify_role_at_branch`).
- Reception delegates the invitation's `stepOrder=0` step to the actual
  intended host via the **existing** `delegate_step` mechanism. **BREAKING**
  (behavior change): for this specific step, the delegate is no longer
  required to hold the step's `approver_role_id` (`reception`) — any active
  user with `invitations:approve` visibility at the branch may be nominated
  as host, since the real host is normally not a front-office employee. Later
  approval-workflow steps (level 2+, configured per visitor category) keep
  today's rule unchanged: a delegate for those must hold that step's role.
- Once delegated, the resolved host is echoed back onto the invitation
  (`hostId`/`hostNameOrEmail` on the `Invitation` row, `InvitationOut`)
  exactly as it is today when a host resolves — no API shape change on read,
  only on how the value gets set.
- **New**: `PATCH /invitations/{id}/edit` (new permission `invitations:edit`)
  lets an authorized caller change preferred visit date/time, expected
  duration, location/building/department to visit, purpose, and additional
  notes — every visit-detail field except the visitor/co-visitor personal
  fields (name, email, phone, ID proof, photo), `visitorCategoryId` (locked
  after creation), and the host. **Host reassignment stays exclusively on
  the existing delegation mechanism** (`delegate_step`, see below) rather
  than becoming a second field this endpoint can also set — one code path
  for "who is the host," not two. Eligible while status is `submitted` or
  `approved` (not `denied`/`checked_in`/`checked_out`), following the same
  atomic-conditional-UPDATE pattern as `reschedule`/`extend`. This is
  additive alongside the existing narrow `reschedule`/`extend` endpoints,
  which are unchanged.
- **New capability `email-notifications`**: a Jinja2-based HTML email
  template system (base layout with the VMSS logo + brand color, one
  template per notification type) replacing today's plain-text f-string
  bodies. The "invitation approved" email is rewritten to include the full
  invitation details a visitor needs for their visit: tracking ID, visit
  date/time, location/building/department, purpose, and the resolved host's
  name plus a point-of-contact channel (host's phone/email if resolved,
  otherwise the branch's front-office contact) — closing the current gap
  where the approval email carries none of this.
- Notification push payloads gain addressing metadata (`assignedRoleId` vs
  `assignedUserId`, and a `reason` of `role_assigned` | `delegated`) so a
  client can distinguish "sent to your role" from "delegated to you
  personally" — today's payload has neither.
- A VMSS/VMMS product logo asset is produced (see companion `VMMS_WEB` change
  for placement) and referenced from the new email base template.

## Capabilities

### New Capabilities
- `email-notifications`: Jinja2 HTML template engine for outbound email
  (base branded layout + per-notification-type templates), replacing plain
  f-string bodies; provider-swap point stays the existing `EmailSender`
  interface.

### Modified Capabilities
- `invitations`: host is never client-supplied at creation; `stepOrder=0`
  defaults to the `reception` role; new `PATCH /invitations/{id}/edit`
  endpoint and its field/status eligibility rules; approval-email content
  requirements now specify host/point-of-contact and visit-detail fields.
- `approvals`: delegation eligibility for the invitation-ownership step
  (`stepOrder=0` when role-identified for the tenant's default host role) no
  longer requires the delegate to hold that role; delegation dispatches a
  notification (push + email) to the new delegate, which it does not do
  today.
- `notifications`: push payload gains `assignedRoleId`/`assignedUserId`/
  `reason` addressing metadata for invitation-related pushes.

## Impact

- **Code**: `src/vmss_api/invitations/{models,schemas,service,router,tasks}.py`,
  `src/vmss_api/approvals/service.py`, `src/vmss_api/notifications/service.py`,
  `src/vmss_api/auth/rbac_catalog.py` (no new role, but confirm `reception`'s
  permission set covers the ownership step), `src/vmss_api/core/emailing.py`
  (template rendering), new `src/vmss_api/core/email_templates/` (or similar)
  package.
- **API contract (breaking)**: `hostId`/`hostNameOrEmail` removed from
  `POST /invitations` / `POST /registrations/walk-in` request bodies. Both
  the React portal and Flutter app must stop sending them before/alongside
  this deploying, per `api-conventions.md` §2's client-coordination rule
  since this tightens an existing request contract.
- **Data**: no new tables. `InvitationApprovalStep.approver_role_id` for
  `stepOrder=0` now always resolves to the `reception` role's id at
  creation time instead of sometimes being host-identified.
- **Migration**: existing in-flight invitations created before this change
  (host-identified `stepOrder=0`) keep working under today's delegation
  rules — this change only affects newly created invitations.
- **Dependencies**: adds `jinja2` (not currently a dependency — confirmed via
  `pyproject.toml` grep) for the new `email-notifications` capability.
