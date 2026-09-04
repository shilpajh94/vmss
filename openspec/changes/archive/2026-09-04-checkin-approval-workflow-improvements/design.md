## Context

See `proposal.md` - Why/What Changes for motivation. This covers the "how"
for five independent pieces of work that happen to land in one change
because they were reported together: endpoint consolidation, QR
check-in/check-out split, `relevantToMe` extension, delegation
generalization, and photo capture/display. They touch three feature
packages (`invitations`, `approvals`, `dashboard`) and can be implemented
and reviewed as largely independent units of work — see `tasks.md` for the
grouping.

Current relevant code (confirmed by direct inspection, not the spec text
alone):
- `invitations/router.py`: 5 check-in-capable routes (v1 UUID at line ~721,
  v2 tracking-ID at ~785, QR-token toggle at ~837, check-out at ~897) plus
  `dashboard/router.py:92`'s body-keyed wrapper.
- `invitations/service.py::check_in_by_qr_token` (~652-720) holds the
  if/else toggle between check-in and check-out branches.
- `invitations/repository.py::_relevant_to_me_filter` (~27-46) is the
  `relevantToMe` query — currently only checks `stepOrder == 0 AND
  approver_user_id == user_id` OR `delegated_to_user_id == user_id`.
- `approvals/service.py::delegate_step` (~215-277) hard-codes: caller must
  be the `stepOrder` 0 host, target step must be `host_step.step_order + 1`,
  host's own step must be `approved`.
- `approvals/service.py::_authorize_step_action` (~63-68 area) already
  implements the general "is this caller allowed to act on the current
  step" check (role match / host match / delegate match / override) that
  the generalized delegation rule reuses.
- ID-proof upload path: `_validate_id_proof(content, max_size)`
  (`invitations/service.py:126`) plus `storage_save(tenant_id, prefix,
  content, content_type)` — this is the pattern the new photo upload
  reuses, not a new upload pipeline.
- Storage key naming convention already in use:
  `primary_contact_id_proof_storage_key` (Invitation),
  `id_proof_storage_key` (InvitationVisitor) — the photo columns mirror
  this naming.

## Goals / Non-Goals

**Goals:**
- Remove two redundant check-in surfaces without losing any check-in
  business rule they enforced.
- Make the QR flow's two actions independently callable and independently
  testable.
- Fix `relevantToMe` so a role-based approver can find their pending work
  without falling back to the unfiltered branch-wide list.
- Reuse the existing step-authorization predicate for delegation instead of
  writing a second, parallel eligibility check.
- Reuse the existing upload-validation/storage pattern for photos instead
  of introducing a new file-handling path.

**Non-Goals:**
- Building the escalation/auto-approve enforcement that `escalatesAt`/
  `autoApprovesAt` already compute but nothing acts on (`approvals/spec.md`
  "Escalation and Auto-Approve Timestamps Are Computed but Not Enforced")
  — untouched, out of scope for this change.
- Malware/content scanning for uploaded photos (`file-upload-handling.md`
  §4 already flags this as an open pre-production item for all uploads,
  ID-proof included) — the photo upload gets the same content-type/
  magic-byte validation ID-proof already gets, no more, no less.
- Changing how role-identified steps fan out notifications
  (`notify_step_approver`) — that logic is already correct; only the
  read-side `relevantToMe` filter was wrong.
- A generic "reassign any step to anyone regardless of eligibility" escape
  hatch — the delegate must still meet the step's own role/permission
  requirement; only *who may initiate* a delegation and *which step* is
  delegable are generalized.

## Decisions

### 1. Remove routes outright rather than soft-deprecate further
`PATCH /api/v1/invitations/{id}/check-in` already carries a `Deprecation`
header (`mark_deprecated()`); it has had its migration window. Given the
frontend team is asking for exactly this cleanup now, and
`api-conventions.md` §2's deprecation window exists to protect clients that
haven't migrated yet, removing it in this change is proceeding at the
requesting team's pace, not skipping the process — the two client teams
(React portal, Flutter) are the ones asking. Same reasoning for the
dashboard's `PATCH /admin/dashboard/upcoming-visitors` mutation: it has no
independent business rule (docstring already says it delegates to the same
service call as v1 check-in), so removing it is deleting a wrapper, not a
capability.

**Alternative considered**: keep the dashboard wrapper and just have it
call the v2 service function internally. Rejected — it still leaves two
routes for one action, which is exactly what "keep one endpoint" asks to
stop.

### 2. QR check-in keeps its URL; only check-out gets a new one
Reusing the existing `PATCH /api/v2/invitations/qr/{token}/check-in` URL for
the entry action (rather than minting two new URLs) minimizes the surface
the QR-scanning client must change — it already only needs a new call for
the exit case it previously reached by calling the same URL twice. The
service function `check_in_by_qr_token` loses its `if/else` toggle body:
the check-in branch becomes the whole function, and the check-out branch
moves to a new `check_out_by_qr_token` function backing the new route,
reusing `InvitationRepository.check_out_by_qr_if_eligible` (already exists,
used from the else-branch today).

### 3. `relevantToMe`'s new clause (c) is a second `EXISTS` branch, not a join rewrite
`_relevant_to_me_filter` adds a third `or_()` branch: the invitation has a
current pending `InvitationApprovalStep` (`status == 'pending'` and, per
existing "current step" semantics, the lowest `stepOrder` among pending
steps) whose `approverRoleId` matches one of the caller's roles at that
step's branch (via `UserBranchRole`, the same table
`_authorize_step_action`/`_user_holds_role_at_branch` already query), and
`delegated_to_user_id IS NULL` on that step. This is expressed as a
correlated `EXISTS` subquery mirroring the shape of the existing two
branches, not a new join on the outer query — keeps the query plan close to
today's and avoids row duplication from a join fan-out.

**Alternative considered**: compute "my relevant invitations" in the service
layer by loading the caller's roles once and filtering in Python. Rejected
per `query-performance.md` §2 — this is a list endpoint; the filter belongs
in the query, not a post-fetch loop.

### 4. Delegation eligibility is "the host, OR whoever can act on the step, OR override" — not a bare reuse of the acting predicate
`approvals/service.py::_authorize_step_action` already answers "can this
caller act on this step" (role/host/delegate/override); its role/host/
delegate half is extracted into a shared `_caller_matches_step(tenant_db,
user, invitation, step) -> bool` helper. **This alone is not sufficient for
delegation eligibility**, and reusing it verbatim was an early mistake
caught during implementation: the *existing* capability's whole reason to
exist is that the invitation's host can hand off a role-identified step to
someone else precisely *because* the host doesn't hold that role — if
delegation eligibility required the same match as acting, the host would
lose the ability to delegate a step they were never authorized to act on in
the first place, which is a regression, not a generalization.

`delegate_step` therefore checks three independent conditions, not one
predicate: (1) the caller is the invitation's host (`stepOrder` 0's
`approver_user_id`) — a blanket privilege independent of the current step's
own kind, generalized from "only the step right after the host's own" to
"any step"; (2) `_caller_matches_step` against the *current* step (covers a
role-holder delegating their own pending step, and a delegate
re-delegating); (3) `invitations:approve-override`. This keeps the
refactor-and-reuse benefit for (2) — no duplicate role/delegate-matching
logic — while preserving the host's original blanket privilege as its own
explicit clause.

Re-delegation (`_caller_matches_step`'s delegate-match branch) is new to
`_authorize_step_action`'s use for delegation, but not new to the function
itself — the existing "delegate match" branch already exists per
`approvals/spec.md` "Acting on a Step Requires the Caller's Matching Role,
or an Explicit Override" clause (a), so no new branch was needed there.

### 5. Photo storage mirrors the ID-proof pattern exactly
New columns: `Invitation.primary_contact_photo_storage_key: str | None`,
`InvitationVisitor.photo_storage_key: str | None` — both nullable (photo is
optional), same `String(500)` shape as their ID-proof counterparts. Upload
path: a new `visitor_photo_files` (list, order-matched, optional — may be
shorter than the visitor list) and a single optional
`primary_contact_photo_file` form part, alongside the existing ID-proof
file parts in the same multipart request. Validation reuses
`_validate_id_proof`'s content-sniffing approach but against an
image-only allow-list (JPEG/PNG, no PDF) via a new `_validate_photo`
sharing its implementation shape. Response schemas
(`InvitationVisitorOut`, `InvitationQrCheckInOut`) gain `photoUrl` /
`primaryContactPhotoUrl` resolved from the storage key the same way any
other storage-backed URL is resolved today (existing storage interface,
not a new one).

**Alternative considered**: a single generic "attachments" list instead of
named photo columns. Rejected — over-engineering for one well-known
attachment kind; `database-architecture.md`'s modeling standards favor
explicit typed columns over a generic bag for a known, singular field, and
mirrors the existing ID-proof precedent exactly.

### 6. Photo field lands on the shared schema, not a walk-in-only fork
Per proposal.md's flagged assumption: `VisitorSubmit` and
`InvitationPrimaryContactCreate` (in `invitations/schemas.py`) gain the
optional photo file handling; `registrations/schemas.py` needs no change at
all since it already re-exports these types verbatim. This is the same
precedent `VisitDetailsSubmit`'s `purposeId`/`hostId`/etc. fields already
followed (`invitations/spec.md` "Visit Details Optionally Accept Catalog
IDs Alongside Free Text").

## Risks / Trade-offs

- **[Risk]** Removing `PATCH /api/v1/invitations/{id}/check-in` and the
  dashboard wrapper breaks any in-flight client build still calling them →
  **Mitigation**: both client teams (React, Flutter) raised these issues
  themselves, so this is a coordinated, requested removal; confirm exact
  release timing with both teams before merging so the API change and
  client changes ship together, not API-first-and-wait.
- **[Risk]** Splitting the QR toggle changes exit behavior for any device
  in the field that scans the same QR check-in URL twice to check a visitor
  out → **Mitigation**: check-in URL is preserved for entry; only exit
  moves. Document the new check-out URL prominently in the migration note
  each client team needs, and keep the check-in endpoint's 409-on-
  already-checked-in response message explicit ("call check-out instead")
  so a client that hasn't migrated yet gets an actionable error rather than
  a silent toggle.
- **[Risk]** The `relevantToMe` `EXISTS` subquery is evaluated per row in
  the outer `Invitation` query — a branch with many concurrently-submitted,
  workflow-backed invitations could add query cost → **Mitigation**: the
  subquery is index-supported (`InvitationApprovalStep` is already indexed
  by `invitation_id`; `UserBranchRole` is already indexed by `user_id` +
  `branch_id` for the existing role-match authorization check this reuses)
  and bounded by the same pagination as the rest of the endpoint; no new
  index is anticipated but confirm with `EXPLAIN` during implementation if
  a tenant's invitation volume is large enough to matter (`query-
  performance.md` §1's spirit, applied to a subquery rather than a join).
- **[Risk]** Delegation chains (re-delegation) could in principle be passed
  back and forth indefinitely → **Mitigation**: not defending against
  deliberate misuse in this change (both parties are already
  role-authorized/permissioned staff); each delegation still requires the
  *current* delegate (or an override holder) to act, so a chain only grows
  through legitimate, authorized hand-offs. Flag as an open item if abuse
  is observed in practice.
- **[Trade-off]** Photo upload gets no malware/content scanning, same as
  ID-proof today — accepted per `file-upload-handling.md` §4's existing
  "confirm with security-architecture owner before launch" carve-out; not
  a new gap introduced by this change.

## Migration Plan

1. Land the additive pieces first (photo columns/upload/response fields,
   `relevantToMe` new clause, generalized delegation, new QR check-out
   route) — none of these break an existing caller.
2. Coordinate a release window with the React portal and Flutter teams for
   the two removals (v1 check-in, dashboard check-in mutation) and the QR
   check-in behavior change (409 instead of toggling to checked-out).
3. Remove the v1 route, the dashboard mutation, and the QR toggle branch in
   the same deploy the client teams ship their updated calls in — per
   `api-conventions.md` §2, a breaking change ships as a coordinated cutover
   for these internal-client-only routes, not a silent `/v1`→`/v2`
   redirect (there is no `/v3` here since the canonical route already
   exists at `/v2`).
4. **Rollback**: each of the four pieces (endpoint consolidation, QR split,
   `relevantToMe`, delegation) is an independent code path and can be
   reverted independently if one surfaces a regression; the photo columns
   are additive/nullable so no data migration needs reverting even if the
   upload code path is rolled back.

## Open Questions

- Exact max file size and allowed dimensions for the visitor photo (the
  spec only requires "a maximum upload size" and "image-only allow-list")
  — a specific number (e.g. 2 MB, matching a typical selfie/webcam capture)
  can be set during implementation without changing the spec or the task
  breakdown.
- Whether `GET /invitations/track` (the public tracking lookup) should also
  surface the photo, alongside the QR check-in/check-out response — the
  proposal scoped this to the QR response only per the frontend's explicit
  ask (issue 9 names "checkin api while scanning the qr" specifically);
  extending it to the tracking lookup is a small additive follow-up if
  requested later, not a blocker for this change.
