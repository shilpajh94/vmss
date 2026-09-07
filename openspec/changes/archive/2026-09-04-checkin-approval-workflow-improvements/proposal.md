## Why

The frontend team (React portal + Flutter app) surfaced nine integration
issues after building against the current check-in, invitation-approval, and
registration APIs. Investigation against the current code confirms seven are
real gaps and two are duplicate framings of the same root cause:

1. **Check-in has 5 endpoints, not 1** (`PATCH /api/v1/invitations/{id}/check-in`
   — deprecated, `PATCH /api/v2/invitations/{trackingId}/check-in` — canonical,
   `PATCH /api/v2/invitations/qr/{token}/check-in`, `PATCH
   /admin/dashboard/upcoming-visitors`, plus a separate check-out endpoint).
   Confirmed: this matches the frontend's "3 or 4 endpoints" complaint.
2. **QR check-in/check-out share one toggling endpoint** — confirmed, but only
   for the QR flow; the tracking-ID/desk flow already has separate check-in
   and check-out endpoints.
3+5. **Invitation routing "sent to all hosts" bug** — confirmed, but more
   precise than reported: a visitor-selected host (`hostId`) already gets an
   exclusive, person-scoped approval step. The actual bug is that a
   *role-identified* workflow step (e.g. "any Reception staff") correctly
   notifies every role-holder at the branch, but the `relevantToMe` personal
   worklist filter doesn't recognize a role-holder as having a relevant
   pending item unless they've been explicitly delegated — forcing them onto
   the branch-wide list (which shows every invitation, looking like "sent to
   everyone").
4/6-7. **Multi-level delegation** — a working delegation mechanism already
   exists, but is hard-restricted to "the host delegates only the single
   step immediately after their own, one time, to one person." There is no
   support for delegating any other step, delegating by a non-host approver,
   or re-delegating (chaining) an already-delegated step — which is what
   "multi-level workflow" delegation actually requires.
8-9. **No visitor photo capture or display anywhere** — confirmed. Neither
   the shared invitation/walk-in payload nor any response schema (including
   the QR check-in response) has a photo field; there is nothing to add to
   the shared visitor schema, but the underlying storage-and-content-
   validation pattern used for ID-proof uploads (`file-upload-handling.md`)
   already exists to build on.

This change consolidates the check-in surface, splits QR check-in/check-out
into explicit actions, fixes the approval-routing visibility gap, generalizes
delegation into genuine multi-level reassignment, and adds photo capture to
registration plus photo display to the QR check-in/check-out response.

## What Changes

- **BREAKING**: Remove the legacy `PATCH /api/v1/invitations/{id}/check-in`
  endpoint. `PATCH /api/v2/invitations/{trackingId}/check-in` becomes the
  single staff/desk-facing check-in endpoint (it already exists and is
  already the most-used path in tests).
- **BREAKING**: Remove `PATCH /admin/dashboard/upcoming-visitors`'s
  check-in mutation. The dashboard's upcoming-visitors preview rows gain a
  `trackingId` field (if not already present) so the admin portal calls the
  canonical v2 endpoint directly instead of a dashboard-specific wrapper.
- The desk check-out endpoint (`PATCH /api/v1/invitations/{id}/check-out`)
  is unaffected — it is already separate from check-in.
- **BREAKING**: Split the QR flow's toggling behavior into two explicit
  actions: `PATCH /api/v2/invitations/qr/{token}/check-in` (entry only —
  rejects if already `checked_in`) and a new `PATCH
  /api/v2/invitations/qr/{token}/check-out` (exit only — rejects if not
  currently `checked_in`). The QR check-in URL keeps working for entries;
  only the "scan again to check out" behavior moves to the new checkout URL.
- Extend `GET /invitations?relevantToMe=true` to also include an invitation
  when the caller currently holds (via branch-scoped role) the role
  required by that invitation's current pending step and no delegate has
  been assigned to that step yet — closing the gap where a valid
  role-based approver couldn't find their pending work except through the
  branch-wide list.
- Generalize approval-step delegation: the requirement restricting
  delegation to "host only, delegating only the step right after their own"
  is replaced by "whoever is currently authorized to act on the current
  pending step (by role, by being the named host, by an existing delegate
  assignment, or by override permission) may delegate that step to another
  qualifying person, at any step position" — including re-delegating an
  already-delegated step (chaining), which is what makes this a genuine
  multi-level capability instead of one hop.
- Add an optional profile-photo upload for the primary contact and each
  visitor to the shared invitation/walk-in payload contract (`POST
  /invitations` and, since it reuses the identical contract, `POST
  /registrations/walk-in` automatically inherits it), validated the same
  way ID-proof uploads are (real content/magic-byte check, size limit).
- Add the captured photo (when present) to the QR check-in and check-out
  response payloads, so a security/reception scanning app can render it
  next to the visitor's name during verification.

## Capabilities

### Modified Capabilities
- `invitations`: consolidate check-in to one canonical endpoint, split QR
  check-in/check-out into explicit actions, extend `relevantToMe` to
  role-based current-step approvers, add optional photo capture at
  registration, add photo to the QR check-in/check-out response.
- `approvals`: generalize step delegation from "host-only, next-step-only,
  one-shot" to "current step's authorized approver, any step, re-delegable."
- `dashboard`: remove the upcoming-visitors check-in mutation; ensure
  preview rows carry `trackingId` so the canonical check-in endpoint can be
  called directly from that view.

## Impact

- **Code**: `src/vmss_api/invitations/{router,service,schemas,models,repository}.py`,
  `src/vmss_api/approvals/{router,service,repository}.py`,
  `src/vmss_api/dashboard/{router,service,schemas}.py`,
  `src/vmss_api/registrations/schemas.py` (inherits invitation schema
  changes with no code change of its own, per the existing re-export
  pattern), file-storage integration for photo uploads
  (`database-architecture.md` §1 / `file-upload-handling.md`).
- **API contract**: two endpoint removals (v1 UUID check-in, dashboard
  check-in mutation) and one endpoint addition (QR check-out) — all
  **BREAKING** for the React portal and Flutter app; both client teams need
  a coordinated release, not an in-place swap, since the removed routes
  return 404 rather than being deprecated in place.
- **Notifications**: no change to `notify_step_approver`'s fan-out logic
  itself (role-identified steps still correctly notify every role-holder —
  that part was never the bug); only the `relevantToMe` read-side filter and
  the delegation write-side eligibility change.
- **Assumption to flag**: the photo field is added to the payload/schema
  shared by both `POST /invitations` (staff pre-registration) and `POST
  /registrations/walk-in`, since the two already reuse one Pydantic
  contract verbatim (`registrations/schemas.py`) — there is no way to add it
  to walk-in alone without forking that shared schema, and forking it would
  contradict the existing "walk-in reuses the exact same payload contract"
  design decision. The field is optional on both flows.
