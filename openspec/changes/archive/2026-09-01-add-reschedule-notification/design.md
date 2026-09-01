## Context

See `proposal.md` - Why for motivation. Current state, established by reading
the running code:

- `src/vmss_api/invitations/tasks.py` already has three notification tasks —
  `send_approval_notification`, `send_tracking_notification`,
  `send_denial_notification` — each following an identical shape: a thin
  Celery-bound wrapper (`request_id`/`tenant_schema` bound into `structlog`
  context, `_RETRY_KWARGS` retry policy, an `ERROR` log on retry exhaustion)
  around an inner `async def _send_*` that opens its own tenant-bound
  session (`tenant_session_scope`), loads the `Invitation` by id (returning
  early if it's gone — redelivery-safe per `background-jobs.md` §2), builds
  a subject/body, and calls the shared `_dispatch()` helper, which routes to
  `notifications.email_sender`/`notifications.sms_sender` based on
  `primary_contact_preferred_contact_method`. `send_denial_notification`'s
  own docstring already documents this as "structurally identical to
  `send_tracking_notification` ... only the subject/body differ" — the
  established pattern for adding a new notification type.
- `reschedule_invitation` (`invitations/service.py`) does not currently take
  a `tenant: Tenant` parameter, unlike `approve_invitation`/
  `deny_invitation`, which do (to resolve `tenant.schema_name` for the
  enqueue call). The router handler (`invitations/router.py`) already
  resolves `tenant` via `Depends(get_tenant)` for this route, so threading
  it through is a pure additive parameter — no new dependency needed.
- The user resolved, when this proposal was raised: only the primary
  contact is notified (never co-visitors, matching every existing
  notification), and the channel follows `preferredContactMethod` exactly
  like the existing three tasks (not an unconditional email).

## Goals / Non-Goals

**Goals:**
- Add `send_reschedule_notification`, structurally identical to the
  existing three tasks, enqueued once per successful reschedule.
- Thread `tenant` through `reschedule_invitation` so it can enqueue the
  task the same way `approve_invitation`/`deny_invitation` already do.

**Non-Goals:**
- No `Idempotency-Key` support added to `PATCH /invitations/{id}/reschedule`
  — flagged as an accepted, separately-scoped risk in proposal.md's Impact
  section, not solved here.
- No notification to co-visitors on a group registration — out of scope
  per the recipient decision above.
- No QR code on the reschedule notification — a reschedule doesn't
  re-approve the visit or invalidate an already-issued QR, so there's
  nothing new to encode.

## Decisions

**New task named `send_reschedule_notification`, copying
`send_denial_notification`'s shape exactly (subject/body differ only).**
Alternative considered: parameterizing one generic
`send_status_change_notification(kind, ...)` task instead of four separate
ones. Rejected — the existing three tasks are already separate functions
for exactly this reason (`add-invitation-approval-flow-and-role-resync/
design.md` Decision 2: "two distinct notifications, not one with a
conditional attachment"); a fourth follows the same precedent rather than
introducing a different shape for one notification type only.

**Body wording**: "Your visit has been rescheduled. New date: {date}, time:
{time}. Tracking ID: {tracking_id}." — no QR/attachment, matching the
`_dispatch()` call already used by `send_tracking_notification`/
`send_denial_notification` (both omit `attachment=`).

**`reschedule_invitation` gains a `tenant: Tenant` keyword parameter**,
matching `approve_invitation`/`deny_invitation`'s existing signature shape
exactly. The router call site adds `tenant=tenant` — `tenant` is already
resolved there via the existing `Depends(get_tenant)`.

**Enqueue timing**: after `await tenant_db.commit()`, in the same place the
existing `updated = await ...; await tenant_db.commit()` sequence already
returns from — mirroring every existing notification enqueue site (never
enqueued before commit, never inline in the request path).

## Risks / Trade-offs

- **[Risk] No `Idempotency-Key` on this endpoint.** A client retry (e.g. a
  mobile network timeout) can call reschedule more than once for what was
  meant as a single logical action, each success dispatching its own
  notification — a visitor could get two "rescheduled" messages for one
  actual change. → Not mitigated in this change; explicitly called out as
  an accepted, separately-scoped risk in the proposal. Adding
  `Idempotency-Key` to this endpoint, matching `api-conventions.md` §3, is
  a natural follow-up but changes this endpoint's request contract
  (a new optional header), which is outside what was asked here.
- **[Risk] SMS-preferring contacts get a text, not an email.** The original
  request's literal wording ("email should go to the visitor") could be
  read as "always email." → Deliberately resolved the other way when this
  proposal was drafted, for consistency with every other notification;
  documented here so the decision is traceable back to that resolution
  rather than looking like an oversight.

## Migration Plan

None. No schema change, no data migration — purely a new Celery task
function and one new call site in an existing service function's already-
committed code path. Safe to deploy and roll back independently of any
database state.
