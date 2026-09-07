## Context

See `proposal.md` - Why/What Changes for motivation. Three independent, low-risk
changes to the existing `invitations` feature; no new tables, no new external
dependency. Key existing pieces this design builds on (from codebase research):

- `Invitation.expires_at` is the only field gating QR check-in today, checked
  both in `service.py::check_in_by_qr_token` (returns `HTTP_410_GONE`) and
  redundantly in the atomic `repository.py::check_in_by_qr_if_eligible`
  `WHERE` clause (race-safe against concurrent scans).
- `Invitation.preferred_visit_date: date | None` already exists, is captured at
  creation/reschedule, but is not currently enforced anywhere.
- `Tenant.timezone: str` (default `"UTC"`) already exists; `dashboard/service.py`
  already has a `_resolve_tenant_timezone(tenant) -> ZoneInfo` helper (falls back
  to UTC + logs `WARNING` on an invalid stored value) — the only existing
  precedent in the codebase for turning a UTC timestamp into a tenant-local
  calendar day.
- The list endpoint's row schema and the detail schemas are separate Pydantic
  models; the photo URL resolution logic (`_resolve_photo_url()` in
  `router.py`) already exists and is reused, not rebuilt.
- `invitations/tasks.py` has an established Celery task shape (`_RETRY_KWARGS`,
  `tenant_session_scope`, idempotent DB lookup, `_dispatch()` for
  email/SMS) used by `send_approval_notification`, `send_denial_notification`,
  etc. — the new host-email task follows this shape exactly rather than
  introducing a new pattern.

## Goals / Non-Goals

**Goals:**
- Make the scheduled-date gate race-safe the same way the expiry gate already
  is (atomic repository-level check, not just a service-level pre-check).
- Give the frontend a way to distinguish "too early" from "expired" and other
  rejection reasons without parsing the error message string.
- Reuse the existing tenant-timezone-resolution and Celery-task-dispatch
  patterns rather than inventing new ones.

**Non-Goals:**
- Not adding a new, separate "scheduled date" column — `preferred_visit_date`
  is repurposed as the enforced value per the confirmed decision in this
  change (see proposal.md).
- Not changing check-out behavior — it remains exempt from both the expiry and
  the new scheduled-date check, per the existing spec and explicit design
  intent (a visit that starts before/spans the scheduled date can still be
  closed out).
- Not touching `dashboard/service.py`'s existing timezone helper — see
  Decisions below for why a small amount of local duplication is preferred
  here over a cross-feature extraction.
- Not building a general-purpose multi-channel notification abstraction — the
  host-creation email follows `invitations/tasks.py`'s existing feature-local
  pattern, consistent with `background-jobs.md` §1's guidance that a shared
  `notifications/` abstraction gets built once a second feature actually needs
  one (it doesn't yet).

## Decisions

### 1. Scheduled-date comparison uses tenant-local calendar day via `Tenant.timezone`
Alternative considered: compare in UTC (matching how `expires_at` is compared
today). Rejected because `expires_at` is a precise instant where UTC-vs-local
rarely matters at day granularity, but "the scheduled date" is inherently a
tenant-local concept (a receptionist in Mumbai thinks in IST calendar days, not
UTC ones) — comparing in UTC could reject a valid same-day scan or accept one a
day early/late near midnight in the tenant's zone. Reuses the same
`ZoneInfo(tenant.timezone)` + `UTC` fallback-with-`WARNING`-log approach
`dashboard/service.py::_resolve_tenant_timezone` already established, added as
a small local helper in `invitations/service.py` rather than importing across
feature packages (`fastapi-architecture.md` §1's feature-based modularity — no
cross-feature import already exists between `invitations` and `dashboard`, and
one two-line helper doesn't justify introducing one). If a third feature needs
this later, extracting it into `core/` becomes the obvious move; not done
preemptively here per `project-rules.md`'s no-premature-abstraction guidance.

### 2. New rejection uses `HTTP_425_TOO_EARLY`, not `410 Gone` or a generic `400`
Alternative considered: reuse `410 Gone` (the expiry status) or a generic `400`
matching the invalid-token/not-approved cases. Rejected: `410 Gone` means "this
resource is permanently gone," which is wrong for a QR that will become valid
later; a generic `400` would be indistinguishable from unrelated validation
failures without parsing the `detail` string, which the spec's "distinguishable
from the expiry-rejection case" scenario explicitly requires. `425 Too Early`
(RFC 8470, already available as `starlette.status.HTTP_425_TOO_EARLY`) is an
exact semantic match and lets the frontend branch on status code alone.

### 3. Scheduled-date check is enforced in two places, mirroring the existing expiry check
Service-layer check (clear, logged rejection before touching the DB) plus an
added condition in `repository.py::check_in_by_qr_if_eligible`'s atomic
`UPDATE ... WHERE` (closes the same race window the existing `expires_at >
now()` clause closes: two concurrent scans of a not-yet-eligible invitation
must not both fall through a check-then-act gap). This duplicates the
existing structure exactly rather than introducing a new validation layer.

### 4. Photo URL added to the list row schema is nullable, no new query
`GET /invitations`'s repository query already loads
`primary_contact_photo_storage_key` as part of the `Invitation` row (it's a
plain column, not a relationship needing `selectinload`); the change only adds
the field to the list output schema and resolves it through the existing
`_resolve_photo_url()` helper in the row-construction step — no N+1 risk
(`query-performance.md` §1 doesn't apply here since no new relationship is
being traversed).

### 5. Host-creation email is a distinct Celery task, not folded into the existing confirmation dispatch
Alternative considered: extend the existing visitor confirmation
email/SMS task to also email the host. Rejected: the visitor confirmation task
is keyed to `primary_contact_preferred_contact_method` (email or SMS) and
recipient-resolution logic that's specific to the primary contact, not the
host; folding host-notification in would couple two independent recipients
and delivery-failure domains into one task, complicating the
exhausted-retries `ERROR` log (`logging-observability.md` §3) that needs to
say clearly *who* didn't get notified. A separate task
(`send_host_creation_notification` or similar name, finalized during
implementation) keeps the existing tasks' contracts unchanged and follows the
established one-task-per-notification-purpose pattern already used for
approval/denial/reschedule/tracking notifications.

## Risks / Trade-offs

- **[Risk]** A tenant with `preferred_visit_date` already populated on
  existing, currently-scannable invitations could see previously-valid QR
  codes start being rejected the moment this ships, if today's date happens to
  be before that stored date for some in-flight invitation. → **Mitigation**:
  this is very unlikely in practice (an invitation whose visit date hasn't
  arrived yet wouldn't normally be scanned before that date under intended
  usage), and it's the entire point of the requested change; call it out in
  the PR description so support is aware of the day-one behavior shift. No
  backfill/migration needed since the field already holds real data.
- **[Risk]** An invalid/misconfigured `tenant.timezone` value silently falls
  back to UTC (matching existing `dashboard/service.py` behavior), which could
  make the scheduled-date boundary off by the tenant's real UTC offset for
  that tenant only. → **Mitigation**: this mirrors an already-accepted
  trade-off elsewhere in the codebase (logged at `WARNING`, not silently
  swallowed); not introducing new risk, just extending existing behavior to a
  second call site.
- **[Trade-off]** Duplicating a small timezone-resolution helper into
  `invitations/service.py` instead of extracting a shared one now is
  deliberate scope discipline, at the cost of ~10 duplicated lines. Revisit if
  a third call site appears.

## Migration Plan

No schema migration. Deploy is a single code release:
1. Ship the `invitations` service/repository/schema/task changes together
   (all three behavior changes are independent of each other and could ship
   separately, but there's no reason to split the PR).
2. No feature flag — all three changes are corrective/additive per the
   proposal's Impact section (no breaking response-shape or status-code
   change to an existing success path).
3. Rollback is a plain revert; no data migration to undo.
