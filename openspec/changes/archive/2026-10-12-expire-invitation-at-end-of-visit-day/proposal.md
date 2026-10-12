## Why

Staff see `Expires` values that don't line up with the visit. For example,
`INV-D127D29A` is scheduled for 2026-10-02 11:00 but expires
"Oct 2, 2026, 2:53 PM", which is exactly 7 days after it was submitted.
`INV-2015854C` is scheduled for 2026-10-20 but expires on 2026-10-02, so its
QR pass would die before the visit. A visitor's pass should be valid through
the end of the scheduled visit day (e.g. `2026-10-02 23:59:59` local time),
whatever time it was submitted, approved, rescheduled or edited.

Commit `9478fc5` (2026-09-28) already moved creation, approval and
approved-reschedule to an end-of-visit-day rule. It left four gaps:

1. **Old rows.** Every invitation created before 2026-09-28 still has
   `created_at + 168h` (`settings.invitation_token_ttl_hours`). Nothing
   backfilled them, and the screenshot shows one of these rows.
2. **Wrong timezone.** The end-of-day calculation uses only `Tenant.timezone`
   (`UTC` in dev). The company's own `default_timezone` (`Asia/Kolkata` in
   dev) is ignored, so a newly created Oct 2 visit would show as
   "Oct 3, 5:29 AM" to IST staff.
3. **Rescheduling a `submitted` invitation** changes the visit date but keeps
   the old expiry.
4. **Editing `preferredVisitDate`** through `PATCH /invitations/{id}` changes
   the date but never recalculates `expires_at`.

## What Changes

- Add one helper that picks the visit timezone: `Company.default_timezone`,
  then `Tenant.timezone`, then `UTC`. Invalid IANA names fall through to the
  next option with a `WARNING` log. Both the end-of-visit-day expiry and the
  QR check-in "not before the visit date" check use it, so the two always
  agree on what "the visit day" means.
- Whenever an invitation's visit date is set or changed, set `expires_at` to
  23:59:59 of that date in the visit timezone, stored as UTC. That covers
  creation (staff, walk-in, return visit), approval, reschedule (now
  **including `submitted`** invitations) and an edit that changes
  `preferredVisitDate`.
- Add a one-off tenant Alembic data migration that recalculates `expires_at`
  for open invitations (`status` in `submitted`/`approved` and
  `check_in_status` ≠ `checked_out`) that have a `preferred_visit_date`.
  Terminal rows (denied, cancelled, checked out) keep their history.
- Leave the manual extend-expiry endpoint (`PATCH …/expiry`) as it is. It can
  still push `expires_at` past the end of the day.
- Remove the unused `invitation_token_ttl_hours` setting from `config.py` and
  `.env.example`. Nothing reads it since `9478fc5`.
- No API contract change. `expiresAt` keeps its type and shape; only its
  value is corrected. No web change is needed, because `VisitorInfoModal`
  already shows `expiresAt` in the viewer's local time.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `invitations`: "Invitation Has an Expiry-Bound Tracking Identity" now
  defines expiry as the end of the visit day in the visit timezone, and
  requires reschedule/edit to recalculate it. "QR Check-In Endpoint
  Transitions an Eligible Visitor to Checked-In" defines its "tenant-local
  calendar day" using the same visit timezone.

## Impact

- **Code**: `src/vmss_api/invitations/service.py` (timezone resolver,
  `_end_of_visit_day_utc`, `create_invitation`, `approve_invitation`,
  `reschedule_invitation`, `edit_invitation`, `check_in_by_qr_token`),
  `src/vmss_api/invitations/repository.py` (edit-update path accepts
  `expires_at`), `src/vmss_api/core/config.py`, `.env.example`.
- **Migration**: new `alembic_tenant/versions/<rev>_realign_invitation_expiry_to_visit_day.py`
  (data only, no DDL), chained off the current single head `e5f7a9b1c3d4`.
- **Side effects**: signed QR image URLs embed `expires_at + 7d` when they are
  generated. Links in emails already sent keep their old `exp`, but each
  check-in still validates against the live `expires_at`, so nothing breaks.
  The dashboard's "upcoming" list (filters on `expires_at > now`) will now
  show the corrected rows.
- **Out of scope**: the dashboard's own "today" bounds
  (`dashboard/service.py`) still use `Tenant.timezone` only. Per-branch
  timezones would need a new `branches` column; that's a separate change if
  it's ever needed.
