# Manual Web Verification Checklist — Role-Based Invitation Ownership

This closes `VMMS_WEB/openspec/changes/role-based-invitation-workflow/tasks.md`
task 7.2 (unperformed manual E2E pass), extended to cover all three invitation
channels rather than only the one already spot-checked. Run this against the
deployed `VMMS_WEB` app with a live backend once staff/admin users are
available. Check items off directly in the `VMMS_WEB` change's `tasks.md` —
this file lives in `VMSS_API`'s change and cannot edit that repo.

API-side regression evidence for every step below is already green (see this
change's `tasks.md`, groups 2–7): 830/830 tests passing, clean lint/type
checks. This checklist verifies the same behavior is reachable and correct
through the actual UI, which no automated test in either repo currently
exercises end to end.

## (a) Visitor Self-Service Wizard — Already Verified

- [x] Confirmed working by the user prior to this change. No further action.

## (b) Staff Pre-Registration Wizard

1. [ ] Log in as a staff user holding the tenant's default host role
   (`reception` unless reconfigured).
2. [ ] Create an invitation via the staff pre-registration wizard. Confirm no
   host field is shown anywhere in the form.
3. [ ] After submission, confirm the invitation appears on the staff/admin
   board as owned by **"Unassigned — Front Office"** (or equivalent
   role-owned label), not a named host.
4. [ ] Delegate the invitation to a specific person (the intended real host)
   via the delegate action.
5. [ ] Confirm the invitation card now shows the delegate as host, and that
   the notification center shows a delegation notification was sent to that
   person.
6. [ ] Open the invitation's Edit modal and change its date/time. Confirm
   the change saves and the card reflects the new date/time.
7. [ ] Confirm the delegate receives (or the notification center shows) the
   edit notification.

## (c) Walk-In Check-In Flow

1. [ ] From a walk-in kiosk/device-key-authenticated flow (or the
   equivalent walk-in UI), register a visitor with no host selection
   available.
2. [ ] Confirm the resulting invitation appears on the staff/admin board as
   role-owned ("Unassigned — Front Office"), the same as (b).
3. [ ] Delegate it to a specific host and confirm the card + notification
   center update the same way as (b).
4. [ ] Confirm the visitor's own tracking/confirmation email/SMS was sent
   (check the configured mail catcher or the visitor's inbox in a staging
   environment).

## After Completing All Three

- [ ] Mark `VMMS_WEB/openspec/changes/role-based-invitation-workflow/tasks.md`
  task 7.2 as done, referencing this checklist.
- [ ] Consider archiving `role-based-invitation-workflow` in `VMMS_WEB` once
  7.2 is checked off (its remaining 26 tasks are already done).
- [ ] Before archiving, do a quick pass over `VMMS_WEB`'s other open changes
  (`fix-invitation-contact-validation`, `fix-visitor-category-badgecolor-nullable`,
  `fix-visitor-category-invalid-id-fallback`, `fix-visitor-wizard-contact-method-default`,
  `fix-staff-dashboard-refresh-filters`, `integrate-audit-dashboard-apis`,
  `visit-card-schedule-actions`, `push-notifications`) for any overlap with
  the invitation-board/notification behavior this checklist exercises.
