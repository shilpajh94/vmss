## Why

`role-based-invitation-workflow` (the change that made every new invitation
default to role-owned "reception/front-office" ownership instead of a
client-picked host, added `PATCH /invitations/{id}/edit`, and replaced plain
f-string emails with branded Jinja2 templates) is **archived and done on the
API side** — `openspec/changes/archive/2026-09-07-role-based-invitation-workflow/`,
26 tasks, all checked. Its `VMMS_WEB` companion change is **26 of 27 tasks
done but still open** (`VMMS_WEB/openspec/changes/role-based-invitation-workflow/`):
every field/UI/notification task is checked, `tsc`/`lint`/`build` are clean,
but task 7.2 — an actual manual walk-through of create → role-owned →
delegate → edit → notify, against a real backend — was never performed, since
that session had no browser tooling and no way to drive a live reception-role
staff member and a real delegation.

The user has now checked the **visitor** portal's invitation flow by hand and
confirmed it works. What's asked next is to do the same verification for
**every other invitation area** — the staff-assisted pre-registration wizard,
the unauthenticated walk-in channel, and the staff/admin invitation board
(approve, deny, delegate, edit, reschedule, extend, badge issue/reprint,
check-in/out) — on both web and API, to close out task 7.2's gap across all
of them rather than just the one channel already spot-checked, to confirm SSO
login (staff/admin sign-in, a prerequisite for reaching any of the above)
still works end to end after this rollout, and to confirm nothing else in the
API broke along the way. This is a verification and regression-closing pass,
not new product behavior — the same kind of change as the archived
`verify-full-api-test-and-validation-coverage` audit, which likewise closed
gaps against already-established rules without introducing new requirements.

## What Changes

- **Regression-verify the invitation-ownership rollout across every channel**,
  on the API: re-run and, where a gap is found, add the missing coverage for
  — role-owned `stepOrder=0` creation, delegation resolving `hostId` and
  notifying the new host, `PATCH /invitations/{id}/edit`'s field/status/
  permission rules, and the branded-email rendering path — exercised through
  `POST /invitations` (visitor self-service and staff pre-registration both
  use this endpoint) **and** `POST /registrations/walk-in`, not only the
  channel already manually checked.
- **Regression-verify the staff/admin invitation board's full action set**
  still behaves correctly post-rollout: approve/deny/delegate (`approvals`
  capability), reschedule, extend, badge issue/reprint, and QR + staff
  check-in/out — since `role-based-invitation-workflow` touched
  `approvals/service.py`'s delegation-eligibility check and
  `notifications/service.py`'s push-payload shape, both shared by this board.
- **Regression-verify SSO end to end**: provider-config resolution, OIDC
  `start_login` → `handle_callback` → `redeem_exchange_code`, user
  provisioning/role-mapping, confirming the archived change's file
  touches (only new test additions, per current diff) didn't regress any
  existing SSO test or behavior.
- **Full-suite regression pass**: run the complete `pytest` suite plus
  `ruff check`/`ruff format --check`/`mypy` (scoped per
  `project-rules.md`) to confirm nothing outside invitations/approvals/
  notifications/SSO broke as a side effect.
- **Coordinate closing `VMMS_WEB`'s open task 7.2** — that repo has its own
  `openspec/` root and is out of this change's edit scope, but this change's
  tasks record exactly what that manual walk-through must cover for each of
  the three invitation channels (not just the one visitor-portal pass already
  done), so the web-side change can be closed out and archived once run.
- No new API contract, schema, or requirement is introduced — this closes
  verification/coverage gaps against behavior the archived change already
  specified.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — this change closes test-coverage and regression-verification gaps
against requirements `invitations`, `approvals`, `notifications`, and the
(currently spec-less) `sso` feature already implement; it does not change
what any of them are required to do. Per the proposal instructions, no
delta spec is warranted, so `skip_specs: true` is set in this change's
`.openspec.yaml`, consistent with the precedent
`verify-full-api-test-and-validation-coverage` audit.)

## Impact

- **Code (this repo, may change if a gap is found)**:
  `src/vmss_api/invitations/{service,tasks,tests}.py`,
  `src/vmss_api/approvals/{service,tests}.py`,
  `src/vmss_api/notifications/{service,tests}.py`,
  `src/vmss_api/sso/tests.py`, `src/vmss_api/registrations/tests.py`.
- **Out of this repo's edit scope, tracked as a coordination item**:
  `VMMS_WEB/openspec/changes/role-based-invitation-workflow/tasks.md` task
  7.2, and that repo's other currently-open changes
  (`fix-invitation-contact-validation`, `fix-visitor-category-badgecolor-nullable`,
  `fix-visitor-category-invalid-id-fallback`,
  `fix-visitor-wizard-contact-method-default`,
  `fix-staff-dashboard-refresh-filters`, `integrate-audit-dashboard-apis`,
  `visit-card-schedule-actions`, `push-notifications`) — worth a quick check
  for overlap with the invitation board/notification behavior this change
  regression-tests, but not modified here.
- **No breaking change, no migration, no new dependency.**
