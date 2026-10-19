## Why

Today nothing ever closes out a visit on its own. A visitor who checks in
and leaves without checking out stays `checked_in` indefinitely if staff
don't check them out manually. Celery beat only runs the daily report
rollup, and the QR check-out deliberately skips the expiry check. That
visitor keeps counting as "inside" in the dashboard's checked-in count and
in the "who's inside" emergency data, days after the pass expired.

The opposite case has a similar gap. An approved visitor who never turns
up stays `approved` after their visit day ends. Check-in already rejects
them as expired, but the row still looks like an active upcoming visit.
Staff can't tell no-shows apart from real upcoming visits, and the only way
to bring the visitor back is to reschedule a row that still claims to be
approved for a day that has passed.

## What Changes

- **Auto check-out.** A scheduled sweep (Celery beat, every 15 minutes,
  run per tenant) checks out every invitation that is still checked in
  once its `expires_at` has passed. That is the end of the visit day in
  the visit timezone, or a later time if staff extended it.
  - It sets `status` and `checkInStatus` to `checked_out`.
  - `checkedOutAt` is set to the invitation's `expiresAt`.
  - `checkedOutByUserId` stays null, and a new `checkedOutAutomatically`
    flag is set to `true`.
  - Each invitation gets an `invitation_auto_checked_out` audit entry with
    no actor.
  - No notification is sent.
- **Archive approved no-shows.** The same sweep moves every `approved`
  invitation that was never checked in (`checkInStatus` = `unused`) to a
  new **`archived`** status once its `expires_at` has passed. In practice
  that happens just after midnight at the start of the day after the
  scheduled visit.
  - It records `archivedAt` and writes an `invitation_archived` audit
    entry.
  - No notification is sent.
  - `submitted` invitations whose visit date has passed are **not**
    archived. They stay as they are.
- **Reschedule from archived.** `PATCH /invitations/{id}/reschedule` also
  accepts an `archived` invitation. The new date must be today or later in
  the visit timezone. Rescheduling sends the invitation back to
  **`submitted`** for re-approval:
  - `approvedAt` is cleared.
  - Approval steps are reset and the first step is re-activated, the same
    way an approval revert does.
  - `expiresAt` is set to the end of the new visit day.
  - The existing QR pass is kept but won't admit the visitor until the
    invitation is approved again.
  - The existing reschedule notifications are sent as they are for any
    `submitted` reschedule.
- **Edit from archived.** `PATCH /invitations/{id}/edit` also accepts an
  `archived` invitation. An edit that leaves the date unchanged keeps it
  `archived`. An edit that changes `preferredVisitDate` behaves like a
  reschedule: the date must not be in the past, and the invitation goes
  back to `submitted` with its approval steps reset.
- **Archived is not a usable pass.** Every check-in path (QR, staff,
  public tracking ID) rejects an `archived` invitation with a 409 that says
  it must be rescheduled first. Extending expiry, issuing a badge,
  reverting approval and denying are all rejected for `archived`.
- **Listing and export.** `GET /invitations?status=archived` filters on the
  new status, and responses expose `archivedAt` and
  `checkedOutAutomatically` as new fields.
  - The export labels the status `Archived` and adds an `Archived At`
    column.
  - Its date range for `status=archived` uses `archivedAt`.
  - Checked Out By reads `System (auto check-out)` for auto-checked-out
    rows.
- **Web portal (VMMS_WEB).**
  - Add an `Archived` status option to the filter and export, and an
    Archived board column.
  - Style the Archived badge in the detail modal and show when the
    invitation was archived.
  - Show a "Checked out automatically" note.
  - Allow Reschedule and Edit on archived cards. The reschedule date
    picker's minimum is today, and the success message says the visit is
    awaiting re-approval.
- **Migration.** A new tenant migration adds `archived_at` (nullable) and
  `checked_out_automatically` (boolean, default `false`). There is no data
  backfill. The first sweep after deploy closes out existing stale rows.

## Capabilities

### New Capabilities

- `visit-lifecycle-sweep`: the scheduled per-tenant job that auto-checks-out
  expired check-ins and archives approved no-shows. It covers timing,
  eligibility, idempotency, audit trail and the no-notification rule.

### Modified Capabilities

- `invitations`:
  - "QR Check-Out Endpoint Transitions a Checked-In Visitor to Checked-Out"
    now notes that an expired check-in is closed by the sweep if nobody
    checks it out.
  - "Reschedule Dispatches a Notification to the Primary Contact" adds
    `archived` as a reschedulable status.
  - "Authorized Caller Edits Non-Personal Invitation Details" allows
    `archived`, with a date change re-entering approval.
  - New requirements:
    - "An Archived Invitation Is Rescheduled Back Into Approval"
    - "An Archived Invitation Does Not Admit the Visitor"
    - "Invitation List Filters and Surfaces Archived and Auto Check-Out State"
- `invitation-export`:
  - "Exported Values Are Human-Readable Labels" gains `archived` →
    `Archived`.
  - "Exported Columns Exclude Documents and Signed URLs" gains the
    `Archived At` column and the auto check-out value for Checked Out By.
  - "Date Columns Follow the Status Filter" gains an `archived` row.

## Impact

- **API code**:
  - `src/vmss_api/invitations/models.py`: two columns.
  - `schemas.py`: `InvitationStatus.archived` and the new output fields.
  - `repository.py`: bulk sweep `UPDATE`s, archived in the reschedule and
    edit gates, and the export date column.
  - `service.py`: reschedule and edit from archived, plus check-in
    rejection messages.
  - `tasks.py`: dispatcher and per-tenant sweep tasks.
  - `export.py`: label, column, and Checked Out By value.
  - `src/vmss_api/core/celery_app.py`: beat entry and a cron-queue route.
- **Migration**: a new `alembic_tenant/versions/<rev>_invitation_archive_and_auto_checkout.py`.
  Pass `schema=` explicitly to `op.add_column`. Run
  `alembic -c alembic_tenant.ini heads` first to confirm a single head.
- **API contract**: additive only. There is a new `status` value
  (`archived`) and two new response fields. Clients that parse `status` as
  a free string are unaffected; the web portal's zod schemas use
  `z.string()`. The `PATCH …/reschedule` and `…/edit` endpoints now accept a
  status they used to reject with 409.
- **Dashboard and emergency data**: "checked-in" counts drop to visitors
  who are actually on site. "Upcoming" already filters
  `status = approved AND expires_at > now`, so it is unaffected.
- **Web (VMMS_WEB)**:
  - `filter-options.ts`
  - `use-paged-board-columns.ts`, `use-invitations-board.ts` and
    `KanbanColumn.tsx`
  - `VisitRequestCard.tsx`
  - `VisitorInfoModal.tsx`
  - the reschedule modal's minimum date
- **Ops**: the Celery beat and worker processes for the cron queue must be
  running for the sweep to happen. Without them, behavior is the same as
  today: no auto check-out and no archiving.
