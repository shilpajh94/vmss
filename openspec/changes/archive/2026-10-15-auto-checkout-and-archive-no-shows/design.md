## Context

See proposal.md for the motivation. Behavior is specified in
`specs/visit-lifecycle-sweep/spec.md`, `specs/invitations/spec.md` and
`specs/invitation-export/spec.md`.

Current state that shapes the approach:

- **`expires_at` and the visit timezone.** `Invitation.expires_at` is
  already 23:59:59 of `preferred_visit_date` in the visit timezone, stored
  as UTC. Creation, approval, reschedule and date-changing edits set it
  (`expire-invitation-at-end-of-visit-day`). Staff can push it later with
  `PATCH …/expiry`.
- **Two status columns.** `status` and `check_in_status` are both written
  on every check-in and check-out path:
  - `check_out_if_checked_in` gates on `status`.
  - `check_out_by_qr_if_eligible` gates on `check_in_status`.
  - Every check-in path admits only `approved`/`checked_in`/`checked_out`.
- **Status-gated actions.** Reschedule and edit use
  `_RESCHEDULABLE_STATUSES = ("submitted", "approved")`. Extend and badge
  use `_ACTIVE_STATUSES = ("approved", "checked_in")`. Revert, approve and
  deny gate on a single status.
- **Approval revert.** It already does "send back to `submitted` and
  restart the workflow" with
  `InvitationApprovalStepRepository.reset_all_for_invitation` and
  `activate_current_pending`. It keeps the QR row, and re-approval re-sends
  the same pass.
- **Celery.** Beat runs one task, `reports.tasks.dispatch_daily_rollup_snapshots`.
  It lists active tenants and enqueues one per-tenant task, so one tenant's
  failure can't block another. `vmss_api.invitations.tasks.*` is routed to
  the notifications queue, and `reports`/`audit_trail` go to the cron
  queue.
- **Web portal.** VMMS_WEB parses `status` as `z.string()`, so a new value
  doesn't break parsing. Its board maps one column to one API status, and
  `VisitRequestCard` gates Reschedule/Edit on
  `RESCHEDULABLE_STATUSES = {'submitted', 'approved'}`.

## Goals / Non-Goals

**Goals:**
- Run one sweep per tenant that does both transitions in a single
  transaction, together with their audit rows.
- Make the sweep safe under redelivery and under concurrent runs without a
  Redis marker.
- Make an archived invitation inert on every existing status-gated path
  without touching each gate.

**Non-Goals:**
- Archiving `submitted` invitations whose date passed (user decision).
- Notifying anyone about an automatic check-out or an archive (user
  decision).
- Auto check-out based on `expected_duration`. Expiry is the only trigger.
- A per-tenant setting for the sweep interval or the archive delay.
- Changing reschedule rules for `submitted`/`approved`. For example, they
  still accept a past date as they do today. The not-in-the-past check
  applies only when leaving `archived`.
- An "un-archive without rescheduling" action.

## Decisions

### D1. One beat-driven sweep with a per-tenant fan-out, every 15 minutes
`dispatch_visit_lifecycle_sweep` (beat, `crontab(minute="*/15")`) lists
active tenants and enqueues `sweep_tenant_visit_lifecycle(tenant_id,
tenant_schema)` for each. This copies `reports.tasks` exactly, including
`engine.dispose()` and the per-tenant enqueue `try/except`. The per-tenant
task opens `tenant_session_scope` and runs both transitions and their
audit inserts, then commits once. It has `_RETRY_KWARGS`-style retries and
logs `ERROR` on exhaustion.

- *Why 15 minutes:* the end of the visit day is the boundary, and 15
  minutes of lag after midnight is invisible to staff. The query is a
  cheap indexed predicate.
- *Alternatives:* a once-a-day 00:05 run (rejected: tenants span
  timezones, so "after midnight" differs per tenant, and an extended
  expiry mid-day would wait up to 24h); checking lazily on read (rejected:
  the emergency/dashboard counts would still be wrong until someone opened
  the row).
- Both tasks live in `invitations/tasks.py`, per background-jobs.md §1.
  They get **exact-name** entries in `task_routes` pointing at the cron
  queue. Celery's map router checks exact names before glob patterns, so
  the existing `vmss_api.invitations.tasks.*` → notifications rule stays
  for everything else.

### D2. Idempotency comes from conditional bulk `UPDATE … RETURNING`, not a Redis marker
Each transition is one statement:

- **Auto check-out:** `UPDATE invitations SET … WHERE (status =
  'checked_in' OR check_in_status = 'checked_in') AND expires_at <= now()
  AND deleted_at IS NULL RETURNING id`
- **Archive:** `… WHERE status = 'approved' AND check_in_status = 'unused'
  AND expires_at <= now() …`

The returned ids feed one bulk `INSERT` into `audit_logs` in the same
transaction. A redelivered or repeated run matches zero rows and so writes
zero audit rows. Under READ COMMITTED, a concurrent second `UPDATE` blocks
on the locked rows and re-evaluates its `WHERE` once the first commits, so
each row is transitioned and audited exactly once. This is the same
guarantee the existing `*_if_eligible` methods rely on.

- *Alternative:* the rollup task's Redis `SET NX` run-marker (rejected:
  that suits a once-per-day send, but here a marker would suppress a
  legitimate later run in the same window).
- The `OR` on both status columns catches legacy rows where only one
  column says `checked_in` (from before `allow-multiple-checkins` aligned
  them). Both columns are written to `checked_out`.
- Audit rows are written inline, not via `BackgroundTasks`/Celery. The
  "audit writes must not block the request path" rule doesn't apply
  because there is no request, and writing them in the same transaction is
  what makes "transitioned without audit" impossible.

### D3. `checked_out_at = expires_at`, plus a `checked_out_automatically` flag
The real departure time is unknown. `expires_at` is the latest moment the
visit was valid, and it doesn't depend on sweep lag. A new boolean column
`checked_out_automatically` (server default `false`) records that no
person did the check-out, while `checked_out_by_user_id` stays null.

- Every manual check-out `UPDATE` (staff and QR) explicitly sets it back
  to `false`. A visit that was auto-checked-out, then extended, re-entered
  and manually checked out must not stay flagged.
- *Alternatives:* `now()` (rejected: it lands just after midnight, inflates
  durations and implies an observed exit); a `checkout_method` enum column
  (`staff`/`qr`/`auto`) (rejected for now: the QR path has no actor anyway,
  so only "auto or not" is needed today. A later change can widen the
  boolean if reporting needs it).

### D4. `archived` is a new `status` value, not a flag on `approved`
Making it a status keeps an archived row out of every existing gate with
no gate edits: check-in eligibility, `_ACTIVE_STATUSES`, revert/approve/
deny single-status checks, and the dashboard's `status = 'approved'`
upcoming count. It fits the existing plain-string column, needing no enum
migration, and gives the board a clean one-status column.

`archived_at` (nullable timestamp) records when the archive happened. It
is kept after a reschedule as history and overwritten if the invitation is
archived again.

- *Alternative:* `is_archived` on an `approved` row (rejected: every gate
  that admits `approved` would need an extra condition, and missing one is
  a silent pass that still admits the visitor).
- `InvitationStatus` gains `archived`, so `?status=archived` validates.
  `_EXPORT_DATE_COLUMNS` and the export label/column map gain an entry.
- Only the check-in pre-checks (`_perform_check_in`,
  `check_in_by_qr_token`) get an explicit `status == "archived"` branch,
  and only to give a clearer 409 detail ("Invitation is archived;
  reschedule it to admit the visitor"). The repository `WHERE` clauses
  already exclude it.

### D5. Archive is triggered by `expires_at`, not by `preferred_visit_date + 1 day`
`expires_at` already is "end of visit day in the visit timezone",
including the Company → Tenant → UTC fallback. It respects a staff
extension, and it exists on rows without a `preferred_visit_date`. Reusing
it means the sweep needs no timezone logic and can't disagree with check-in
about when the pass died.

### D6. Leaving `archived`: a dedicated repository transition plus the revert's step reset
`reschedule_invitation` branches on `invitation.status == "archived"`:

1. It validates `preferred_visit_date >= today` in the visit timezone
   (`_resolve_visit_timezone`), returning 422 otherwise.
2. It calls a new `InvitationRepository.reschedule_archived_if_eligible`.
   This is the same history-capturing `SET` list as
   `reschedule_if_eligible`, plus `status='submitted'` and
   `approved_at=NULL`, under `WHERE status = 'archived'`. Two concurrent
   calls give one winner, and the loser gets 409.
3. It calls `reset_all_for_invitation` and `activate_current_pending`, as
   `revert_invitation_approval` does, in the same transaction. Then it
   commits.
4. It sends the existing reschedule email, which already renders the
   "pass comes after approval" variant for `submitted`. It sends the host
   push, and the approver push for the activated step, using the same
   block as revert.

Only the service-side eligibility check admits `archived`. The
repository's `_RESCHEDULABLE_STATUSES` and `reschedule_if_eligible` keep
`("submitted", "approved")`, so an archived row can only leave `archived`
through the new method.

- The Company auto-approve flag is deliberately ignored here (user
  decision). The original approval was for a specific day, so a new day
  is re-reviewed. Auto-approve stays a creation-time rule.
- The QR row is kept, the same reasoning as approval revert D3: every
  check-in path refuses `submitted`, and re-approval re-sends the same
  token.

### D7. Edit on `archived`: keep archived unless the date actually changes
`edit_invitation` admits `archived`, so `allowed_statuses` includes it.
If `changes` contains a `preferred_visit_date` different from the current
one, it does the following:

- applies the D6 not-in-the-past check;
- adds `status="submitted"`, `approved_at=None` and the realigned
  `expires_at` to `changes`;
- runs the step reset and activation after the `UPDATE`, inside the same
  transaction.

Otherwise the edit leaves the status alone. Notifications are the existing
edit email and host push, plus the approver push when a step was
activated. Edit does not populate the `previous_preferred_visit_*`
history, which matches today's edit behavior; only reschedule does.

The point-of-contact gate is unchanged, so `_poc_eligible` still applies.
- *Alternative:* reject date changes on archived edits and force the
  Reschedule action (rejected: the web edit modal resubmits the whole
  form, and a user who picks a new date there would hit a confusing 409).

### D8. Web: one more board column and widened action gates
- `BoardStatus`/`API_STATUS_BY_BOARD_STATUS` gain `archived`. The column
  sits after Denied and is a non-drag target. That adds one more
  `GET /invitations?status=archived` query per board load, which is cheap.
- `STATUS_OPTIONS` and `EXPORT_DATE_LABELS` gain `archived`.
- `VisitRequestCard`'s Reschedule/Edit gate includes `archived`.
- The reschedule modal's minimum date is today when the card is archived.
  The server's 422 is still the authority.
- `VisitorInfoModal` gets a badge style for `archived`, an "Archived on …"
  line, and a "Checked out automatically" note when
  `checkedOutAutomatically` is set.
- The success toast after rescheduling an archived card says the visit is
  awaiting re-approval.

## Risks / Trade-offs

- **First run after deploy processes the whole backlog.** Every old
  approved no-show is archived and every stuck check-in is closed in one
  go, with `checked_out_at` possibly weeks in the past. → This is the
  intended cleanup. Two bulk statements per tenant handle it, and the
  audit rows are bulk-inserted. Tell staff before release that old
  no-shows will appear under Archived.
- **Beat or cron worker not running in an environment** → no sweep, so
  behavior is the same as today. → Add the beat entry to the deployment
  checklist, and log an `INFO` per tenant with the counts so a silent
  absence is noticeable.
- **`checked_out_at = expires_at` overstates visit duration** for a
  visitor who really left at noon. → `checked_out_automatically` lets
  reports exclude or flag these. Real departure time can't be known
  without a check-out.
- **A staff member mid-way through a manual check-out at the moment the
  sweep fires** → one of the two conditional `UPDATE`s wins, and the other
  gets 409 or matches zero rows. The visit is closed exactly once either
  way.
- **Browser date vs. visit timezone on the reschedule picker** → the
  client minimum is a convenience only. The server checks against the
  visit timezone.
- **Rollback.** Downgrading drops the two columns, but `archived` rows
  would keep a status older code doesn't know. → The migration's
  `downgrade()` first runs `UPDATE invitations SET status='approved'
  WHERE status='archived'`. That returns no-shows to the pre-change state;
  they're already expired, so they're inert.

## Migration Plan

1. Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and confirm
   a single head.
2. Add a tenant migration that adds `archived_at TIMESTAMPTZ NULL` and
   `checked_out_automatically BOOLEAN NOT NULL DEFAULT false`. Pass
   `schema=` explicitly to `op.add_column` / `op.drop_column`, because
   they ignore `schema_translate_map`. Generate the revision id rather than
   typing it by hand.
3. Upgrade all tenants locally (the default tenant only, per local
   policy), then drop `vmss_test` so conftest's `create_all` picks up the
   new columns.
4. Deploy the API, the cron-queue worker and beat together. The first beat
   tick does the backlog cleanup.
5. Deploy the VMMS_WEB change. It is safe in either order: the API change
   is additive, and the web only reads the new fields when present.
