## Context

See `proposal.md` - Why for motivation. Relevant existing pieces this design
changes or removes:

- `add-pre-registration/design.md` Decision 1 (two-phase split), Decision 5
  (QR encodes the tracking token), and Decision 9 (signed JWT tracking token,
  needed specifically to resolve tenancy on an unauthenticated write endpoint
  with no bearer token) — all three are specific to the two-phase flow this
  change removes.
- `invitations/models.py::Invitation` already carries every field this change
  needs (`primary_contact_*`, visit-detail columns, `carried_items`,
  consent columns) — they were previously nullable-until-registration and
  filled by a second `UPDATE` from `submit_self_registration`. No column is
  added or removed; only when they get filled changes (all at `INSERT` time
  now).
- `core/storage.py::validate_upload`/`save` (`file-upload-handling.md`) is
  reused as-is — file validation and storage-key generation don't change,
  only which route calls them.
- `invitations/qr.py::generate_qr_png` is reused as-is — only the string it
  encodes changes (tracking id instead of a signed token).

## Goals / Non-Goals

**Goals:**
- One authenticated call creates a fully populated invitation, matching the
  full JSON/multipart shape previously only accepted by API-10.
- No new Alembic migration — the existing `invitations` schema already
  supports this.
- Remove the JWT tracking-token machinery cleanly (no dead code left behind)
  now that nothing decodes it.

**Non-Goals:**
- Re-introducing any form of visitor self-service registration. If a future
  requirement needs the visitor to supply their own ID proof remotely, that
  is a new change, not a variant of this one.
- Changing `GET /invitations/track`'s response schemas
  (`InvitationTrackingOut`/`InvitationTrackingSummaryOut`) — only the
  guarantee about *when* that data is complete changes (spec.md).
- Reworking the `checkin` feature's future QR-scan flow. This change only
  ensures the QR payload (plain `tracking_id`) is something a future
  `checkin` endpoint can look up via the same `InvitationRepository` method
  `GET /invitations/track` already uses — designing that endpoint is out of
  scope here.

## Decisions

### 1. `POST /invitations` becomes multipart, absorbing API-10's entire body shape
`InvitationCreate` gains everything `SelfRegistrationSubmit` had:
`primary_contact.id_proof_type`, `visitors[]` (each with `id_proof_type`),
`visit_details`, `carried_items`, `vehicles`, `consents`. The route signature
changes from a single JSON body param to the same
`Form(payload) + File(primary_contact_id_proof_file) + File(visitor_id_proof_files)`
shape `submit_self_registration` already uses — no new multipart-handling
pattern is introduced, this is a straight move of an existing pattern to a
different route.
**Why**: reusing the exact shape means `schemas.py`'s existing validators
(`_require_reachable_contact`, `_require_contact_for_method`, the
individual/group visitor-count checks, `ConsentsSubmit`'s
all-must-be-true check) transfer unchanged — only `SelfRegistrationSubmit`
itself is deleted, its fields folding into `InvitationCreate`.
**Alternative considered**: keep two endpoints, make API-10's fields optional
on API-09 (the rejected "optional pre-fill" option from the initial scoping
conversation) — rejected per the explicit choice to collapse the flow, not
extend it.

### 2. Invitation is created already `submitted`; the `pending` status becomes unused
`create_invitation` builds one `Invitation` row with every field set and
`status="submitted"`, `submitted_at=now`, in a single `INSERT` — no
intermediate row, no follow-up `UPDATE`. `service.py::submit_self_registration`
is deleted outright rather than kept as dead code.
**Why**: there is no longer a window between "shell exists" and "visit record
complete" for `pending` to describe. The `status` column itself stays (a
future `cancelled`/`expired` state will need it), only the `pending` value
becomes unreachable in new code paths.

### 3. QR payload switches from a signed JWT to the plain `tracking_id`
`core/security.py::create_invitation_token`/`decode_invitation_token` are
deleted. `invitations/deps.py::get_invitation_claims`/`get_invitation_tenant`/
`get_invitation_tenant_db` are deleted (their sole caller, the API-10 route,
is gone). `tasks.py`'s confirmation task now generates the QR from
`invitation.tracking_id` directly (already loaded in the task), so no token
string needs to be threaded from `service.py` through to `tasks.py` at all.
**Why**: the JWT existed to solve exactly one problem — resolving which
tenant schema to query on an unauthenticated write request carrying no bearer
token (`add-pre-registration/design.md` Decision 9). That problem no longer
exists once there is no unauthenticated write endpoint. Keeping the JWT
machinery around unused would violate this project's "don't keep unused code"
convention for no benefit — `GET /invitations/track` already resolves tenancy
via `track_default_tenant_db` (the configured default tenant slug), completely
independent of any per-invitation token, and needs no signature to look up a
tracking id that's already meant to be human-readable and shared (`INV-XXXXXXXX`).
**Alternative considered**: keep minting a signed token nobody verifies yet, in
anticipation of the not-yet-built `checkin` feature scanning it. Rejected —
that feature doesn't exist, and its own design step is better placed to decide
whether it needs a signed token or can reuse the plain tracking id the way
`GET /invitations/track` already does; speculative unused code isn't a
substitute for that decision.

### 4. Two dispatch tasks collapse into one, fired at creation
`send_invitation_link` (the "please register" email/SMS) and
`send_registration_confirmation` (the "you're confirmed" email/SMS with QR)
collapse into a single `send_visit_confirmation` task, enqueued once from
`create_invitation` instead of twice across two requests. The new task's
idempotency check (`background-jobs.md` §2) becomes "has this invitation
already had its confirmation sent" — tracked via the existing `status`
column reaching `submitted` being sufficient, since that now happens exactly
once, at creation, atomically with the row's insert.
**Why**: with only one request in the lifecycle, there is only one point at
which a notification is ever due; keeping two tasks would leave
`send_invitation_link` permanently dead code.

### 5. Consent and ID-proof capture move to the authenticated caller, by design, not by oversight
`ConsentsSubmit`'s all-three-accepted validation still runs, but is now
satisfied by whoever calls `POST /invitations` (an employee/reception user),
not by the visitor in a dedicated step. Same for every visitor's ID-proof
file — the caller uploads it on the visitor's behalf.
**Why**: this is the direct, necessary consequence of collapsing the two-phase
flow the way it was asked for (proposal.md - Why) — there is no design
alternative that preserves visitor-authored consent/upload without keeping a
second request in the flow, which is exactly what this change removes.
Flagged explicitly below as an accepted trade-off rather than glossed over,
since `security-architecture.md` §4's "Consent Capture" requirement is still
satisfied mechanically (a timestamped consent record still exists) but its
original premise — that the visitor is the one affirming it — no longer
holds.

### 6. Breaking change ships immediately, not behind a deprecation window
`api-conventions.md` §2 calls for a `Deprecation` header and a migration
window before removing an existing endpoint. This change removes API-10 (and
changes API-09's contract) immediately instead.
**Why**: `project-rules.md` states the deployment target is "not yet
decided" and no deploy pipeline exists yet — there is no deployed environment
with real external clients depending on the current contract to give a
migration window to. Standard practice on a still-pre-production API is to
land the corrected contract directly rather than run a deprecation cycle for
clients that don't yet exist in production.
**Alternative considered**: deprecate API-10 first (keep it functioning,
mark it `Deprecation`-flagged) and remove it in a follow-up change — rejected
as unnecessary process overhead given the above, but flagged here so this
deviation from `api-conventions.md` §2 is visible rather than silent.

## Risks / Trade-offs

- **[Risk]** Consent and ID-proof upload are no longer visitor-authored
  (Decision 5) — a compliance-relevant change in who is attesting to what.
  → **Mitigation**: none within this change's scope; flagged here for the
  security-architecture.md owner to confirm this still satisfies the
  product's actual compliance requirement before this ships. If it doesn't,
  the fix is a product-level decision (e.g. requiring a witnessed/counter-signed
  consent flow), not a re-litigation of this change's endpoint shape.
- **[Risk]** Removing API-10 without a deprecation window (Decision 6) will
  break any client already integrated against the two-phase flow.
  → **Mitigation**: accepted given no production deployment exists yet
  (see Decision 6); revisit if that assumption turns out to be wrong before
  this ships.
- **[Trade-off]** An employee must now have every visitor's ID-proof file in
  hand at creation time (e.g. scanned in advance, or the visitor physically
  present), rather than each visitor uploading their own remotely.
  → Accepted as the direct, intended consequence of the requested merge.

## Migration Plan

- No Alembic migration — `invitations`/`invitation_visitors`/
  `invitation_vehicles` tables are unchanged; only the write pattern
  (one `INSERT` instead of `INSERT` + `UPDATE`) changes.
- No data backfill — any existing `pending` (never-completed) invitation rows
  in a running environment stay as historical rows; nothing in this change
  reads or migrates them, since there is no dev/staging data to preserve yet
  (`project-rules.md`: deployment not yet decided).
- Deploy is a plain code/schema-less release: update `router.py`,
  `service.py`, `schemas.py`, `deps.py`, `tasks.py`, `core/security.py`, then
  `docs/features/invitations.md`. No environment variable or settings key
  changes (`settings.invitation_token_ttl_hours` is reused as-is for the
  tracking record's validity window).

## Open Questions

- Whether the not-yet-built `checkin` feature will want a signed,
  tamper-evident QR payload instead of the plain tracking id this change
  switches to — doesn't change this change's specs, approach, or task
  breakdown; that feature's own design step can reintroduce a signed token
  scheme if it needs one, independent of this change.
