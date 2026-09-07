# Invitations (Pre-Registration)

Lets an employee invite a visitor ahead of their visit by submitting the
visit's complete record — contact, co-visitors, visit info, items, vehicle,
consent — in one authenticated call, and lets anyone track that invitation's
status afterward via a public lookup. Covers API-09 and API-12 from the
product spec's Step 3 ("Pre-Registration"). `Invitation`, `InvitationVisitor`,
`InvitationVehicle` all live in each tenant's own Postgres schema (`Base`,
not `GlobalBase`) — see `database-architecture.md` §2.

See `openspec/changes/add-pre-registration/` for the original two-phase
proposal/spec/design this feature was first built from, and
`openspec/changes/merge-invitation-registration-into-creation/` for the
change that collapsed it into the single-call contract described below.

## Endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| POST | `/api/v1/invitations` | `invitations:create` at the resolved branch | — | An employee creates a fully completed single or group invitation in one call: `visitorCategoryId` (required — must resolve to an active `VisitorCategory` in the tenant), primary contact, co-visitors, visit details, carried items, vehicles, and consent, each visitor (including the primary contact) with their own ID-proof upload. Multipart: a JSON `payload` part (camelCased fields, matching `InvitationCreate`) plus `primary_contact_id_proof_file`/`primary_contact_photo_file` (both mandatory) and `visitor_id_proof_files` (mandatory per visitor)/`visitor_photo_files` (optional) — see "Primary contact profile photo" below — multipart field *names* are the literal Python parameter names, not camelCased, since they aren't part of a JSON body. Returns a tracking ID with the invitation's status resolved from `Company.autoApprovePreRegisteredVisitors` — `approved` immediately, or `submitted` (awaiting approval) — see "Auto-approve vs. manual approval" below. If the invitation submits `submitted` and its category has an active approval workflow, the response's `currentApprovalStep` shows the first step immediately — see "Per-category multi-step approval" below. Accepts an optional `Idempotency-Key` header (`api-conventions.md` §3) — a retried request with the same key and tenant returns the original response instead of creating a second invitation. **BREAKING**: `visitorCategoryId` is a new required field — existing callers must be updated to send it. **BREAKING**: `primary_contact_photo_file` is now mandatory (`require-primary-contact-photo`) — existing callers must be updated to send it. See "Finding the payload shape in Swagger" below for where to actually see the `individual`/`group` JSON examples in `/docs`. |
| POST | `/api/v1/invitations/{id}/approve` | `invitations:approve` at the invitation's branch | — | Transitions a `submitted` invitation to `approved` and dispatches the QR-bearing approval notification at that point. 409 if the invitation isn't currently `submitted`, **or if it still has a pending approval step** (a workflow-backed invitation must be approved through `POST /invitations/{id}/approval-steps/{stepId}/approve` instead — see "Per-category multi-step approval" below); 404 for an unknown id; 403 (not 404) if the caller lacks branch access to an invitation that does exist. |
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/approve` | `invitations:approve` at the invitation's branch, **and** the caller's assigned role must match the step's `approverRoleId` (or hold `invitations:approve-override`) | — | Approves the invitation's current pending step. The last step's approval flips the invitation to `approved` and fires the same QR/notification dispatch the blanket endpoint does; any earlier step unlocks the next one instead. 409 if `stepId` isn't the current pending step; 404 for an unknown invitation/step id (or a step belonging to a different invitation); 403 if the caller's role doesn't match and they lack the override permission. Registered by the `approvals` feature — see `docs/features/approvals.md`. |
| POST | `/api/v1/invitations/{id}/approval-steps/{stepId}/reject` | Same as the approve variant above | — | Rejects the current pending step (mandatory `reason`) — terminal: immediately denies the whole invitation (same `denied` state `POST /invitations/{id}/deny` produces) regardless of how many steps remain, which stay `pending`/unactioned. Same 409/404/403 conditions as the approve variant. |

The branch an invitation belongs to comes from either the optional
`X-Branch-ID` header or `branchId` in the `payload` JSON body — the header
takes precedence when both are supplied. Omitting both is rejected with a
handled `400` ("branch could not be determined") rather than FastAPI's
generic required-header `422`. This now matches
`docs/features/org_structure.md`'s creation endpoints, which resolve their
branch from the request body via the same `authorize_branch_id` helper.
| GET | `/api/v1/invitations` | `invitations:view`, branch-scoped | — | Paginated listing of invitations for triage/browsing — see "Listing invitations" below. |
| GET | `/api/v1/invitations/track?trackingId=` | None (public) | 20/minute per IP | Full status/visit-summary lookup by the human-readable tracking ID — returns `InvitationTrackingOut`, including every visit-detail and carried-item field captured at creation. |
| GET | `/api/v1/invitations/track?email=` | None (public) | 20/minute per IP | Minimal lookup (tracking ID + status only per matching invitation) by the primary contact's email — returns a `list[InvitationTrackingSummaryOut]`, a narrower shape than the tracking-ID lookup above; see "Minimal disclosure" below. Both shapes are declared on the endpoint's `response_model` as a union, so `/docs`/`/openapi.json` document the email-lookup branch's real (narrower, list) shape instead of the tracking-ID branch's. |
| GET | `/api/v1/invitations/{id}` | `invitations:view` at the invitation's branch | — | Authenticated, staff-facing single-invitation detail view (`InvitationDetailOut`) — branch/source/creator plus every lifecycle field below. Also includes resolved `branch`/`building`/`department` detail (alongside the existing raw `branchId`) and the primary contact's/each visitor's `idProofType`; `idProofUrl` (the raw document image) is included only when the caller additionally holds `documents:view` — see "Resolved location and permission-gated ID-proof documents" below. 404 unknown id, 403 (not 404) if the caller lacks branch access. See "Lifecycle actions" below. |
| PATCH | `/api/v1/invitations/{id}/deny` | `invitations:deny` at the invitation's branch | — | Transitions a `submitted` invitation to `denied`, with a mandatory `reason`, and dispatches a denial notification. 409 if not currently `submitted`. |
| PATCH | `/api/v2/invitations/{trackingId}/check-in` | None (public) | 20/minute per IP | **The single staff/desk-facing check-in endpoint** — the legacy `PATCH /api/v1/invitations/{id}/check-in` route has been removed outright (`checkin-approval-workflow-improvements`). Public, unauthenticated check-in by the invitation's `tracking_id` (`INV-XXXXXXXX`). Transitions an `approved` invitation to `checked_in`; 409 if not `approved`, or if `watchlistFlagged` is set and not yet overridden. Accepts `Idempotency-Key`. No branch-authorization check since there's no authenticated caller. Audit entries for this path use `actor_user_id = null` and `action = "invitation_checked_in_public"`. Success response (`InvitationCheckInOut`) matches the public tracking lookup's field set — primary contact name, host display name, purpose of visit, department, preferred visit date/time, expected duration, additional notes, carried items, co-visitors, and vehicles — alongside the id/trackingId/status fields it already carried. It does not carry `branchId`/`createdByUserId`/badge/watchlist-override internals, resolved branch/building/department, or any ID-proof field; those stay exclusive to `GET /invitations/{id}` (branch/building/department also on the QR endpoints below) — this endpoint has no authenticated caller to gate anything by, so it stays exactly as minimally-revealing as before. See "The tracking ID is a plain, human-readable identifier" below for how tenancy resolves with no bearer token. |
| PATCH | `/api/v2/invitations/qr/{token}/check-in` | None (public) | 20/minute per IP | Public, unauthenticated QR scan check-in — `token` is the encrypted, tamper-evident check-in token encoded in the invitation's QR image (see "QR check-in: encrypted token and the `checkInStatus` lifecycle" below), not the tracking ID. **No longer toggles** (`checkin-approval-workflow-improvements`): entry only, `unused`/`checked_out` → `checked_in`; 409 (not a silent toggle to checked-out) if already `checked_in` — use the check-out endpoint below instead. 400 for an invalid/tampered token or a not-yet-approved invitation, 409 for a watchlist block or already-checked-in, 425 if scanned before `preferredVisitDate` (`qr-checkin-scheduling-photo-email`), 410 if scanned after `expiresAt` has passed. Audit entries use `action = "invitation_qr_checked_in"`. Accepts `Idempotency-Key` — a scanning client must mint a fresh key per physical scan, not reuse one across scans. Also includes resolved `branch`/`building`/`department` detail and the primary contact's/each visitor's `idProofType` — but never an ID-proof document URL, since there's no authenticated caller to gate one by; see "Resolved location and permission-gated ID-proof documents" below. |
| PATCH | `/api/v2/invitations/qr/{token}/check-out` | None (public) | 20/minute per IP | Exit counterpart of the QR check-in route above, added by `checkin-approval-workflow-improvements` to replace its old check-in-URL toggle. `checked_in` → `checked_out`; 409 if not currently `checked_in`. Never expiry-blocked — a visit that legitimately continues past `expiresAt` can still be closed out. Audit entries use `action = "invitation_qr_checked_out"`. Accepts `Idempotency-Key`. Same resolved `branch`/`building`/`department`/`idProofType` fields as the check-in endpoint above. |
| PATCH | `/api/v1/invitations/{id}/check-out` | `invitations:checkout` at the invitation's branch | — | Transitions a `checked_in` invitation to `checked_out`, closing the visit. 409 if not `checked_in`. Accepts `Idempotency-Key`. |
| PATCH | `/api/v1/invitations/{id}/reschedule` | `invitations:reschedule` at the invitation's branch | — | Changes `preferredVisitDate`/`preferredVisitTime` while `submitted` or `approved`, and dispatches a reschedule notification to the primary contact. 409 once `checked_in`/`checked_out`/`denied`. |
| PATCH | `/api/v1/invitations/{id}/edit` | `invitations:edit` at the invitation's branch | — | (`role-based-invitation-workflow`) Edits any subset of `purposeOfVisit`/`purposeId`, `preferredVisitDate`, `preferredVisitTime`, `expectedDuration`/`durationId`, `departmentToVisit`/`departmentId`, `additionalNotes` while `submitted` or `approved` — the same eligible-status window as reschedule/extend, additive alongside them rather than replacing either. Never accepts the visitor's own personal fields, `visitorCategoryId`, or `hostId`/`hostNameOrEmail` — any of those in the request body is rejected with a validation error (`extra="forbid"`); host reassignment stays exclusively the delegation endpoint's job (see "Every invitation starts owned by a role" below). Dispatches an email to the primary contact describing what changed, and a push to the resolved host (if any). 409 once ineligible. |
| PATCH | `/api/v1/invitations/{id}/extend` | `invitations:extend` at the invitation's branch | — | Pushes `expiresAt` forward while `approved` or `checked_in`. 422 if the new expiry isn't strictly later than the current one; 409 if ineligible. |
| POST | `/api/v1/invitations/{id}/badge` | `invitations:badge` at the invitation's branch | — | Issues a printable badge (PNG) for an `approved`/`checked_in` invitation. 409 if ineligible or already issued (use reprint). Accepts `Idempotency-Key`. |
| POST | `/api/v1/invitations/{id}/badge/reprint` | `invitations:badge` at the invitation's branch | — | Re-renders an already-issued badge from current data and increments its reprint count. 409 if none issued yet. |
| POST | `/api/v1/invitations/{id}/watchlist-override` | `invitations:watchlist-override` (admin only by default) at the invitation's branch | — | Clears a `watchlistFlagged` invitation, with a mandatory `reason`, so check-in can proceed. 409 if not currently flagged. Does not itself check the invitation in. |

## Finding the payload shape in Swagger

`POST /invitations`'s `payload` field is a JSON-encoded string (multipart
form data has no native representation for nested objects/lists), so Swagger
UI shows it as a plain text box in the Parameters table with no expandable
schema tree. The route also declares `individual`/`group` examples via
`openapi_extra` (`invitations/router.py`'s `_INVITATION_PAYLOAD_EXAMPLES`) —
these are real, correct OpenAPI metadata (asserted by
`tests/test_api_documentation.py::test_invitation_multipart_payload_examples_documented`),
but Swagger UI does **not** apply `requestBody.examples` when populating a
"Try it out" form for a `multipart/form-data` body (it only does this for
JSON bodies), so this mechanism alone may not be visible depending on the
Swagger UI version rendering `/docs`.

The one place both example JSON payloads are guaranteed visible is the
`payload` field's own **description**, in the Parameters table — no "Try it
out" click required. It's built from the exact same example data as the
`openapi_extra` examples (`_INDIVIDUAL_PAYLOAD_EXAMPLE`/
`_GROUP_PAYLOAD_EXAMPLE` in `invitations/router.py`), so both channels stay
in sync, and is asserted by
`tests/test_api_documentation.py::test_invitation_payload_description_is_self_documenting`.

## One call creates a fully completed invitation

`POST /invitations` accepts the entire visit record up front — there is no
longer a separate public self-registration step for the visitor to complete
afterward (that flow, API-10, has been removed). The authenticated caller
(an employee/reception user) supplies every visitor's ID-proof upload and
affirms consent on the visitor's behalf; see
`openspec/changes/merge-invitation-registration-into-creation/design.md`
Decision 5 for why this trade-off was accepted. A created invitation is
always immediately in its final, fully detailed state — there is no
transient `pending`/shell state for a caller to observe.

### Optional catalog ids on visit details

`visitDetails` accepts *optional* fields alongside its existing free-text
ones: `purposeId`, `durationId`, `departmentId` — see
`docs/features/visit_info.md` for where those ids come from
(`GET /visit-info/departments`, `GET /visit-info/options`). When one is
supplied, the service resolves it against the corresponding catalog/
`Department` row (rejecting the request with `422` if it doesn't resolve to
an existing, active row in this tenant's schema) and overwrites the paired
free-text field (`purposeOfVisit`/`expectedDuration`/`departmentToVisit`)
with that row's canonical display value before persisting — the
client-supplied free-text value for that field, if any, is discarded in favor
of it. Omitting all three ids leaves every free-text field stored exactly as
submitted, byte-for-byte the pre-existing behavior — this was an additive
change, not a breaking one. `POST /registrations/walk-in` inherits the same
behavior automatically, since it submits the identical `VisitDetailsSubmit`
shape.

**`hostId`/`hostNameOrEmail` are no longer resolved at creation**
(`role-based-invitation-workflow`, **BREAKING**): a client may still send
either field on the wire (for backward compatibility with an un-updated
caller), but both are silently ignored — never validated, never used to set
the invitation's host. See "Every invitation starts owned by a role, not a
person" below for how the host is established instead.

**`departmentToVisit` is optional at creation**
(`allow-optional-department-at-creation`): a visitor or a staff member
creating an invitation on a visitor's behalf often doesn't know the
receiving organisation's internal department structure. Both
`departmentToVisit` and `departmentId` may be omitted entirely — the
invitation is created with `departmentToVisit` null rather than rejected —
and filled in later via `PATCH /invitations/{id}/edit` once someone (e.g.
reception, after triage) knows the actual answer. `purposeOfVisit` and
`expectedDuration` remain required free-text fields; only `departmentToVisit`
changed.

### Primary contact profile photo (`checkin-approval-workflow-improvements`, now mandatory per `require-primary-contact-photo`)

Alongside each visitor's required ID-proof upload, `POST /invitations`
accepts a profile photo: `primary_contact_photo_file` (single) for the
primary contact, and `visitor_photo_files` (list) for co-visitors,
order-matched to `payload.visitors` the same way `visitor_id_proof_files`
is. **`primary_contact_photo_file` is mandatory** — a request omitting it
is rejected with a validation error before any invitation record is
created, the same way an omitted `primary_contact_id_proof_file` already
is (`require-primary-contact-photo` — **BREAKING**, tightened in `v1`
directly rather than shipped as a new version; see that change's design.md
Decision 1 for why). Co-visitor photos remain optional: the
`visitor_photo_files` list may still be **shorter** than the visitor
list — a visitor beyond the supplied photo count simply has none; there is
no way to skip a photo for an early visitor while supplying one for a
later one in the same request, since multipart file lists have no concept
of a sparse/null entry.

Validated the same way ID-proof uploads are (real content/magic-byte
sniffing, never the client's declared content type or filename) but with a
narrower, **image-only** allow-list — JPEG/PNG, no PDF — and its own size
limit, `INVITATION_MAX_PHOTO_SIZE_BYTES` (default 2 MB, independent of
`INVITATION_MAX_UPLOAD_SIZE_BYTES`). The stored photo is surfaced back as
`photoUrl` on each visitor entry and `primaryContactPhotoUrl` on the
invitation, in every response that already carries visitor detail
(`GET /invitations/{id}`, the tracking lookup, the canonical check-in
response, and the QR check-in/check-out response — see "QR check-in"
below) — `primaryContactPhotoUrl` is always non-null for an invitation
created after this change shipped; a co-visitor's `photoUrl` is still null
when that visitor's photo wasn't captured. `POST /registrations/walk-in`
accepts the identical two file parts, with the same mandatory/optional
split.

## Auto-approve vs. manual approval

`Company.autoApprovePreRegisteredVisitors` (`org_structure/`'s tenant-wide
config) decides an invitation's fate at creation time
(`add-invitation-approval-flow-and-role-resync`):

- **Enabled**: the invitation is `approved` immediately (`approvedAt` set),
  and the primary contact gets the approval notification — tracking ID
  **and** a QR code.
- **Disabled**, or no `Company` profile configured yet for the tenant (the
  more conservative default): the invitation is `submitted` (awaiting
  approval), and the primary contact gets a tracking-only notification —
  **no QR code**. A caller holding the new `invitations:approve`
  permission (granted by default to `admin`/`reception`/`host`, not
  `security`) can later call `POST /invitations/{id}/approve`, which
  transitions it to `approved` and dispatches the QR-bearing notification
  at that point — the same content the auto-approved path sends
  immediately.

This is resolved once, at creation (or at manual approval), never
recomputed — flipping the Company setting later doesn't retroactively
change an already-created invitation's status. This flag decides only
*whether* a `submitted` invitation needs approval at all; if it does, and
either the invitation's `visitorCategoryId` has a configured approval
workflow or its host resolved to a user, snapshotted steps — not the
blanket approve endpoint — govern getting it to `approved`. See
"Per-category multi-step approval" below.

## Per-category multi-step approval

If `visitorCategoryId`'s category has one or more active
`ApprovalWorkflowRule` rows (`docs/features/visitors.md`) at the moment a
`submitted` invitation is created, the system snapshots them into ordered
`InvitationApprovalStep` rows on that invitation — a point-in-time copy, so
editing the category's workflow later never changes an invitation already
in flight.

**Every invitation starts owned by a role, not a person**
(`role-based-invitation-workflow`, **BREAKING** — replaces the old
"host resolves at creation, if a client supplied one" behavior).
Unconditionally — regardless of whether the category has any configured
rules, and regardless of anything the client submitted — `stepOrder` 0 is
role-identified for the tenant's *default host role* (the standard
`reception` role unless a tenant has reconfigured it via `Company.
defaultHostRoleId`), ahead of any role-based steps the category's own chain
configures. The blanket `POST /invitations/{id}/approve` endpoint is
therefore never reachable for a newly created invitation — every one now
has at least this one snapshotted step. The invitation's actual host is
established later, not at snapshot time: whoever holds the default host
role delegates `stepOrder` 0 to a specific person (see
`docs/features/approvals.md` "The ownership step (`stepOrder` 0)" for the
full delegation-eligibility rules), and that delegation is what sets
`hostId`/`hostNameOrEmail` — see "`hostId` reflects the resolved host, not
the original creator's input" below.

- **Approving/rejecting a step**: `POST /invitations/{id}/approval-steps
  /{stepId}/approve` and `.../reject` (see the endpoints table above) act
  on the invitation's *current pending step* — the lowest `stepOrder` still
  `pending`. Only that one step is ever actionable; naming any other step
  id is rejected with 409.
- **Approving the last step** finalizes the invitation exactly the way
  `POST /invitations/{id}/approve` already does — same `approved` status
  flip, same QR-bearing approval notification. Approving an earlier step
  just unlocks the next one; the invitation's own `status` stays
  `submitted` until the last step clears.
- **Rejecting any step is terminal.** It denies the whole invitation
  immediately (the same `denied` state and denial notification
  `POST /invitations/{id}/deny` produces), regardless of how many steps
  remain — those stay `pending` and are never evaluated. There is no
  resubmission path; a denied invitation is done.
- **Authorization** is tighter than the blanket endpoint's: the caller
  needs `invitations:approve` at the invitation's branch (same as today)
  **and** either their own branch-scoped role assignment must match the
  current step's `approverRoleId` (role-identified step), or their own user
  id must match the current step's `approverUserId` (host-identified step)
  — or they hold the `invitations:approve-override` permission (seeded to
  `admin` only), which bypasses either match entirely.
- **`currentApprovalStep`** (`{id, stepOrder, approverRoleId,
  approverUserId, totalSteps}`, exactly one of `approverRoleId`/
  `approverUserId` non-null) is included on `InvitationOut` (create/
  step-approve/reject responses), `InvitationTrackingOut` (the public
  tracking lookup), and `InvitationDetailOut` (the staff detail view)
  whenever the invitation is `submitted` and has a current pending step —
  `null` otherwise (no workflow, no host, or no longer `submitted`) — so a
  client can render "waiting on: Manager, step 2 of 3" without a second
  call, and call the approve/reject endpoints directly using `id` as
  `stepId`.
- **`hostId` reflects the resolved host, not the original creator's
  input** (the invitation's resolved host user id, or `null` before a
  delegation resolves one) — included on `InvitationOut` and
  `InvitationDetailOut` alongside the existing free-text
  `hostNameOrEmail`. Both stay `null` until `stepOrder` 0 is delegated to a
  specific person; nothing set at creation ever populates them anymore.
- **Escalation/auto-approve timestamps exist but aren't enforced yet.**
  Each step carries `escalatesAt`/`autoApprovesAt`, computed from the
  snapshotted rule's `escalationMinutes`/`autoApproveMinutes` relative to
  the moment that step becomes current (the invitation's submission time
  for the first step, or the moment the prior step is approved for every
  step after it). Nothing currently acts on either timestamp once it
  passes — no scheduled auto-approve, no escalation notification. That's
  deliberately out of scope for now; the fields exist for a UI countdown.

The engine itself lives in the `approvals` feature, not `invitations` —
see `docs/features/approvals.md` for its own model/endpoint reference.
`invitations` only owns the snapshot-at-submission step and the two status
outcomes (`approved` on the last step, `denied` on any rejection).

## Lifecycle actions: deny / check-in / check-out / reschedule / extend / badge / watchlist-override

`add-invitation-lifecycle-actions` adds `status` values `denied`,
`checked_in`, `checked_out` alongside the existing `submitted`/`approved`,
plus one atomic conditional `UPDATE`-based transition per action (same
concurrency-safe shape `POST /invitations/{id}/approve` already uses — a
losing concurrent request gets 409, never a corrupted double-transition):

```
submitted ──deny──> denied
submitted ──approve──> approved ──check-in──> checked_in ──check-out──> checked_out
```

- **`checkInStatus`** (`add-qr-checkin-security`) is a second, parallel
  lifecycle field — `unused` → `checked_in` → `checked_out` — driven only
  by the QR endpoint above. `status` keeps transitioning exactly as shown
  in the diagram for the `v1`/`v2` tracking-ID routes; the QR endpoint
  updates both fields together in the same transaction, so anything
  reading `status` (the "who's inside" emergency report, in particular)
  sees a QR-driven check-in exactly like any other. The two fields are
  deliberately not merged — see "QR check-in" below.
- **Reschedule** (`preferredVisitDate`/`preferredVisitTime`) and **extend**
  (`expiresAt`) operate on different status windows: reschedule only while
  `submitted`/`approved` (before check-in); extend only while
  `approved`/`checked_in` (an active visit). Extend also requires the new
  expiry be strictly later than the current one (422 otherwise).
- **Badge** issuance/reprint requires `approved`/`checked_in`. Issuance
  generates a `BDG-XXXXXXXX` number and a rendered PNG (visitor name,
  tracking ID, the expiry, and a QR code — `invitations/badge.py`, reusing
  `qr.py`'s QR generation, composited with Pillow, no new dependency),
  saved via `core/storage.py`'s existing save/`url_for` interface. The
  embedded QR encodes the same encrypted check-in token issued at approval
  (`_issue_qr_code` — see "QR check-in" below), not the tracking ID, so
  scanning the physical badge and scanning the emailed QR check in the
  invitation the same way. Reprint re-renders from the invitation's
  *current* data (so a reprint after a reschedule/extension reflects the
  new values) and increments `badgeReprintCount`; it keeps the same
  `badgeNumber` — that identifies the visit, not one physical printout.
- **Watchlist override**: `watchlistFlagged` is a new column, but **nothing
  in this codebase sets it to `true` yet** — there is no automatic
  watchlist/blacklist matching built. It exists so `POST
  /invitations/{id}/watchlist-override` and the check-in gate that reads it
  have a real contract to operate on ahead of that future capability. Until
  a future feature sets the flag (e.g. at creation time), `check-in` simply
  never hits the 409 this gate would otherwise produce.
- Denial dispatches `invitations/tasks.py::send_denial_notification`
  (tracking ID + reason, no QR) — structurally identical to
  `send_tracking_notification`, async/Celery, never inline.
- A successful reschedule dispatches
  `invitations/tasks.py::send_reschedule_notification` (tracking ID + the
  new `preferredVisitDate`/`preferredVisitTime`, no QR — the existing QR
  from creation/approval is still valid) — same structure and channel
  routing (`primaryContactPreferredContactMethod`) as the other three
  notifications, only to the primary contact (not co-visitors on a group
  registration, matching every other lifecycle notification). A request
  rejected with 409 (ineligible status) or 403 (no branch access) dispatches
  nothing. `add-reschedule-notification/design.md` flags one known gap:
  this endpoint still has no `Idempotency-Key` support, so a client retry
  can trigger more than one notification for what was meant as a single
  reschedule.

## Resolved location and permission-gated ID-proof documents

`enrich-invitation-checkin-and-detail-views` adds resolved facility detail
and ID-proof document access to three responses: `GET /invitations/{id}`
and both QR check-in/check-out responses. It deliberately does **not**
touch the tracking-ID check-in (`PATCH /api/v2/invitations/{trackingId}
/check-in`) or the public tracking/email lookups — see the table above.

- **Branch/building/department**: every one of the three responses gains
  a resolved `branch` object (`name`, `code`, `address`, `city` — the
  detail view keeps its existing raw `branchId` too, unchanged) plus
  `building`/`department` objects when resolvable. Resolution follows the
  invitation's optional `departmentId` (set only when the visit-info
  catalog lookup was used at creation — see "Visit details optionally
  accept catalog IDs" below) → `Department.floorId` → `Floor.buildingId`;
  either or both of `building`/`department` are `null` when that chain
  doesn't fully resolve (no `departmentId` on file, or a department with
  no `floorId`). The existing free-text `departmentToVisit` field is
  unaffected either way. `invitations/repository.py::get_location` does
  this as one explicit-join query (mirroring `auth/repository.py::
  list_employees_page`'s established cross-package join pattern —
  `invitations` has no ORM `relationship()` onto `org_structure` models),
  not a query per related entity.
- **ID-proof type vs. document**: `idProofType` (e.g. `"Passport"`) is
  always present for the primary contact and every visitor on all three
  responses — it was already stored, just never surfaced before. The raw
  document image (`idProofUrl`, a fetchable URL) is a different matter:
  per `security-architecture.md` §4 ("access to raw document images is
  itself a permission, not implied by can view visitor record"), it is
  included **only** on `GET /invitations/{id}`, and only when the caller
  additionally holds the new `documents:view` permission (checked after,
  and independent of, the endpoint's existing `invitations:view` check —
  lacking it doesn't 403 the request, it just leaves `idProofUrl` `null`).
  The QR check-in/check-out responses never carry `idProofUrl` at all
  (the field doesn't exist on their schema), since neither has an
  authenticated caller a permission could be checked against.
- **`documents:view`** ships granted to the Reception and Security
  standard roles (not Host) — see `docs/features/auth.md`'s "Resyncing
  stale roles against the catalog" for how an already-provisioned tenant
  picks up a newly-added catalog permission like this one.

## Listing invitations

`GET /invitations` gives an authenticated, `invitations:view`-gated caller a
paginated, filterable, sortable view of invitations — for browsing/triage
(e.g. "who's expected today at my branch"), not for looking up one
invitation's full detail (that's still `GET /invitations/track`'s job).
Branch scoping matches every other branch-scoped list endpoint
(`docs/features/org_structure.md`'s `GET /buildings`/`GET /floors`): supply
`X-Branch-ID` to narrow to one branch (rejected with 404/403 the same way an
unknown/unauthorized branch id is anywhere else), or omit it to list across
every branch the caller holds `invitations:view` at.

Query params:

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` / `pageSize` | int | `1` / `20` (max `100`) | Standard pagination (`api-conventions.md` §1). |
| `sortBy` | `submitted_at` \| `created_at` | `submitted_at` | Whitelisted — any other value is rejected with a validation error rather than passed to the database. |
| `sortOrder` | `asc` \| `desc` | `desc` | |
| `status` | string | unset | Exact match against the invitation's `status` column. |
| `registrationType` | `individual` \| `group` | unset | |
| `source` | `staff_pre_registration` \| `visitor_walk_in` | unset | |
| `relevantToMe` | bool | `false` | See "Relevant to me" below — a different filter mode entirely, not a narrower branch scope. |

Each row is an `InvitationListItemOut` — tracking ID, registration type,
source, status, `visitorCategoryId`, primary contact name,
`primaryContactPhotoUrl` (`qr-checkin-scheduling-photo-email` — null when no
photo was captured, resolved via the same storage-key-to-URL helper the
detail/tracking responses already use), purpose of visit, and
expiry/submission timestamps — deliberately narrower than
`InvitationTrackingOut`: it carries no per-visitor/vehicle detail, and no
`currentApprovalStep` either, so the underlying query never needs to
eager-load a child collection or run the extra current-step lookup for a
list view that doesn't render either (`query-performance.md` §1-2).

## Relevant to me

`GET /invitations?relevantToMe=true` is a personal worklist, not a narrower
branch scope: it returns invitations where the caller is either the
invitation's currently resolved host (`hostId` — set once `stepOrder` 0 has
been delegated to them, see `docs/features/approvals.md`), has been
delegated one of that invitation's approval steps (`docs/features/
approvals.md`'s "Delegation"), or currently holds the role that the
invitation's current pending, undelegated step names (e.g. every holder of
the default host role sees a freshly submitted invitation before anyone
delegates it) — regardless of that step's or the invitation's current
status for the first two clauses.

This deliberately **bypasses** `invitations:view` and `X-Branch-ID`
entirely — a host or delegate with no branch-level view permission still
needs to see and act on their own invitation, so this is a distinct query
path from the branch-scoped mode above, not a variant of it. `X-Branch-ID`
is ignored (not rejected, not narrowing) when `relevantToMe=true` is set.
It composes with `status`/`registrationType`/`source` and with
pagination/sorting exactly like the branch-scoped mode. A caller who is
neither host nor delegate on any invitation gets an empty, successfully
paginated result, not an error.

## The tracking ID is a plain, human-readable identifier

`GET /invitations/track` has no bearer token and no tenant identifier at all
to resolve from — a caller who lost their tracking ID is exactly who needs
it — so it resolves the single configured `settings.default_tenant_slug`
tenant via the shared `core.tenancy.resolve_default_tenant`
(`invitations/deps.py::track_default_tenant_db`). This is a known
limitation once a second tenant exists: a real multi-tenant deployment would
resolve this from the request's hostname/subdomain, which nothing in this
codebase does yet. The `GET /invitations/track` lookup itself carries no
token at all — a caller who lost their tracking ID is exactly who needs
this endpoint — and the manual check-in routes (`v1`/`v2`) are keyed by
this same plain `tracking_id`, not a token. The QR *scan* path is
different — see below.

If the default tenant doesn't exist or is inactive, this is a server-side
misconfiguration, not a caller error: it's logged at `ERROR` as
`invitations_track_default_tenant_unconfigured`, distinguishing "no such
tenant" from "tenant inactive" so an operator can tell the fix from the log
alone, consistent with `registrations`' equivalent fallback
(`docs/features/registrations.md`). The client-facing response is
unchanged — still 404 `"Tenant not found or inactive"`.

## QR check-in: encrypted token and the `checkInStatus` lifecycle

`add-qr-checkin-security` closes a gap the plain-tracking-ID QR had: a
photographed or forwarded code stayed valid indefinitely, and check-in
never checked `expiresAt`.

- **Token**: the QR image encodes a Fernet-encrypted token of the
  invitation's internal `id` — never the tracking ID, never the id in
  cleartext (`invitations/qr_token.py`, mirroring `core/encryption.py`'s
  own "encrypt now, decrypt later" pattern rather than a new crypto
  primitive, keyed by its own `QR_TOKEN_ENCRYPTION_KEY` setting —
  deliberately not shared with `SSO_ENCRYPTION_KEY`). A tampered or
  malformed token decrypts to nothing and is rejected 400, with no
  invitation detail disclosed either way.
- **Issued once, at approval**: `service.py::_issue_qr_code` runs inside
  the same transaction that transitions an invitation to `approved`
  (auto-approve at creation, or `POST /invitations/{id}/approve`),
  persisting the token and its rendered PNG (`invitation_qr_codes` table,
  via `core/storage.py`) rather than regenerating on every notification
  send the way the old plain-tracking-ID QR did. It's get-or-create, so a
  later badge issuance/reprint reuses the same token instead of minting a
  new one.
- **Lifecycle**: `checkInStatus` — `unused`/`checked_out` (currently
  outside) transitioning to `checked_in` (currently inside) and back — is a
  field parallel to (not merged with) `status`; see "Lifecycle actions"
  above for why. **Two explicit endpoints, not a toggle**
  (`checkin-approval-workflow-improvements`): the client calls
  `.../check-in` to enter and `.../check-out` to exit — the server no
  longer infers which one from current state, and calling the wrong one for
  the current state is rejected 409 rather than silently doing the other
  action. `checked_out` is **not** a dead end — a visitor may have multiple
  entry points during one visit (e.g. leaving for lunch and returning, or
  moving between buildings on a multi-building site), so calling check-in
  while `checked_out` re-admits exactly like calling it while `unused`.
  `unused` and `checked_out` are kept as distinct values only for what they
  record (never entered vs. entered-and-left at least once) — the gate
  treats them identically.
- **`Idempotency-Key` must be unique per physical scan** (`api-conventions.md`
  §3): both `.../check-in` and `.../check-out` cache their response per
  `(tenantId, idempotencyKey)` for 24h, so a retried request with the same
  key returns the original response instead of re-processing. If a
  client/test reuses one fixed key across multiple distinct scans (e.g.
  check-in, then check-out, then check-in again), every call after the
  first one replays that first response — this looks exactly like "the
  second check-in didn't register," but it's the cache doing its job, not
  a bug in the check-in/check-out cycle itself (which supports unlimited
  entry/exit — see above). Mint a fresh key per physical scan attempt.
- **Expiry**: checked on every transition *into* `checked_in` — the first
  entry from `unused` and any later re-entry from `checked_out` alike. A
  visit still `checked_in` past `expiresAt` can still be checked out — the
  expiry gates entry, not how long someone already inside can stay.
- **Scheduled visit date** (`qr-checkin-scheduling-photo-email`): entry is
  additionally gated on `preferredVisitDate`, the same date the visitor's
  registration/reschedule already captures — a scan attempted before that
  date is rejected `425 Too Early`, distinct from the `410 Gone` expiry
  rejection so a client can branch on status code alone. The comparison is
  date-only (tenant-local calendar day, via `Tenant.timezone`), so a scan
  succeeds at any time of day once the scheduled date arrives, up until
  `expiresAt`. An invitation with no `preferredVisitDate` set (still
  possible — the field is optional at registration) skips this check
  entirely and falls back to expiry-only gating, exactly as before. Like
  expiry, this only gates entry — check-out is never blocked by it.
- **Response** (`qr-checkin-full-registration-detail`, same shape for both
  check-in and check-out): a successful scan returns everything captured
  at registration — the same shape `GET /invitations/track?trackingId=`
  (`InvitationTrackingOut`) already returns, including
  `registrationType`/`source`, preferred visit date/time and expected
  duration, additional notes, carried items, the full co-visitor list
  (`visitors`), and the full vehicle list (`vehicles`) — plus the
  QR-specific fields that lookup doesn't carry (`id`, `checkInStatus`,
  `checkedInAt`/`checkedOutAt`, primary contact email/phone, `hostId`),
  and, for the primary contact and each visitor who has one on file, their
  captured profile photo (`primaryContactPhotoUrl`/`photoUrl` — the
  primary contact's is non-null for any invitation created after
  `require-primary-contact-photo`; a co-visitor's is still null when not
  captured; see "Primary contact profile photo" above). `currentApprovalStep` is
  deliberately omitted — a QR token only ever exists post-approval, so it
  would always be `null`. A rejected scan discloses none of this, only a
  generic failure message.
- No tenant claim in the token yet — this endpoint resolves tenancy the
  same way the tracking-ID `v2` route does (`track_default_tenant`, the
  single-configured-tenant shortcut described above). Revisit once a
  second tenant exists.

## Minimal disclosure on the email-based tracking lookup

`GET /invitations/track?email=` returns only a tracking ID and status per
matching invitation — never ID proof files, the visitor list, or vehicle/item
detail. Anyone who merely knows an email address can call this endpoint (it's
public and unauthenticated), so it exists only to help someone who lost
their tracking ID find it again; full detail requires the tracking ID itself
via the other lookup form.

## Async dispatch, not inline

Invitation creation (and manual approval) dispatches exactly one of two
notifications via Celery, never inline in the request path
(`background-jobs.md` §5): `invitations/tasks.py::send_approval_notification`
(tracking ID + QR code — sent for an `approved` invitation, taking the
already-issued `qr_token` as an explicit argument rather than deriving it
itself, since the token is generated and persisted by the service layer
at approval time — see "QR check-in" above) or
`send_tracking_notification` (tracking ID only, no QR — sent for a
`submitted` one). See "Auto-approve vs. manual approval" above for which
one a given creation/approval triggers. Denial (`send_denial_notification`)
and a successful reschedule (`send_reschedule_notification`) each dispatch
their own notification the same way — see "Lifecycle actions" above. Every
one of these four tasks resolves its own tenant-bound session from a
`tenant_schema` argument, skips if the invitation row is no longer found
(redelivery after removal), and declares
`autoretry_for`/`retry_backoff`/`max_retries`, logging at `ERROR` with full
context if retries are exhausted. Email goes out over SMTP
(`invitations/notifications.py::SmtpEmailSender`); SMS has no gateway wired up
yet (`UnconfiguredSmsSender` raises loudly rather than pretending to send —
this is a known open item, not an oversight).

**Every email is now a branded HTML template**
(`role-based-invitation-workflow`, `email-notifications` capability —
replaces the old plain-text `f-string` bodies): `core/email_rendering.py`
renders `core/email_templates/*.html` (one shared `base.html` layout — logo,
header/footer — plus one template per notification type) into a
`(subject, html_body)` pair, sent alongside the existing plain-text body as
a `multipart/alternative` message (`core/emailing.py::SmtpEmailSender`). A
template failing to render (logged at `ERROR`) falls back to the existing
plain-text body alone rather than failing the dispatch outright. The
approval email specifically now includes the full visit detail (date/time,
duration, department, purpose) plus the resolved host's name and a contact
channel — falling back to the tenant's own `Company.phone`/`Company.email`
when no host has been resolved by approval time.

Submission (every non-auto-approved invitation now snapshots at least the
ownership step), approval, denial, reschedule, edit, check-in, and check-out
each also dispatch a **staff-facing push notification** — additional to, and
dispatched independently from, the visitor email/SMS above. Submission
pushes every holder of the invitation's default host role at the branch
(role-based-invitation-workflow — previously the host, when one had been
supplied); the other actions push the invitation's resolved host, if one has
been delegated. See `docs/features/notifications.md` for the dispatch
primitive, the `assignedRoleId`/`assignedUserId`/`reason` addressing
metadata every payload now carries, and recipient-resolution rules.

**Owning-role email fan-out** (`role-based-invitation-workflow`, replaces
the old "host creation email"): submission also enqueues
`send_submission_role_email_notification`, emailing every active user
holding the default host role at the branch — the email counterpart of the
submission push above, additive to it, not a replacement. **Host-assignment
email**: `approvals`' `delegate_step`, when delegating `stepOrder` 0,
additionally enqueues `send_host_creation_notification` (same task as
before, repurposed — see `docs/features/approvals.md`) to the newly
resolved host, telling them they've been named host. Neither of these
existed before this change fired anything at creation for an un-resolved
host; both are asynchronous and never delay their triggering request.

**No Celery worker runs by default in this DDEV dev environment** — a
created invitation's notification task will sit queued in Redis until
something consumes it. To manually verify dispatch outside the automated
test suite (`invitations/tests.py::test_send_approval_notification_delivers_email_with_qr_via_mailpit`
already does this for you, against real SMTP), start one:

```
ddev exec uv run celery -A vmss_api.core.celery_app worker --loglevel=info
```

Then create an invitation and check DDEV's built-in Mailpit UI
(`ddev describe` prints its URL, or run `ddev mailpit`) for the confirmation
email and QR attachment.

## File uploads

ID proof files (one per visitor, including the primary contact) are validated
by real content — `core/storage.py::validate_upload` sniffs actual magic
bytes via `python-magic` against an image/PDF allow-list and enforces
`settings.invitation_max_upload_size_bytes` — never by the client-declared
`Content-Type` header or filename extension (`file-upload-handling.md` §2).
Accepted uploads are saved through `core/storage.py`'s minimal
save/`url_for` interface, local-disk-backed by default
(`settings.storage_backend = "local"`); an S3-compatible backend (API-14) is
implemented behind the same two functions and selected by setting
`storage_backend` to `"s3"` — see `docs/features/registrations.md`'s config
table for the S3 connection settings.

## Config knobs

| Setting | Default | Purpose |
|---|---|---|
| `INVITATION_TOKEN_TTL_HOURS` | `168` (7 days) | How long a created invitation's tracking record stays within its validity window. |
| `INVITATION_MAX_UPLOAD_SIZE_BYTES` | `5242880` (5 MB) | Max ID-proof file size. |
| `INVITATION_MAX_GROUP_VISITORS` | `20` | Cap on co-visitors in one group submission. |
| `INVITATION_MAX_PHOTO_SIZE_BYTES` | `2097152` (2 MB) | Max optional profile-photo file size — independent of the ID-proof limit above. |
| `STORAGE_ROOT` | `./var/storage` | Local-disk root for uploaded files in dev. |
| `QR_TOKEN_ENCRYPTION_KEY` | unset | Fernet key encrypting/decrypting QR check-in tokens. Fails loudly the first time a token is generated or scanned without it — never a silent no-op. Generate one the same way as `SSO_ENCRYPTION_KEY`; deliberately a separate key from it. |
| `MAIL_HOST`/`MAIL_PORT`/`MAIL_USERNAME`/`MAIL_PASSWORD`/`MAIL_USE_TLS`/`MAIL_FROM_ADDRESS` | local dev mail-catcher | Outbound email for visit confirmations. See `docs/features/configuration.md`. |
| `SMS_GATEWAY_BASE_URL`/`SMS_GATEWAY_API_KEY`/`SMS_FROM_NUMBER` | unset | Placeholders — no SMS gateway has been chosen yet. |

## Not yet built (flagged, not silently dropped)

- **Cancel an invitation.** `add-invitation-lifecycle-actions` added
  deny/check-in/check-out/reschedule/extend/badge/watchlist-override, but
  not cancel — `invitations:cancel` is still seeded into the permission
  catalog, unused, for when that lands. Deny (`submitted` → `denied`) is a
  distinct concept: a reviewer's rejection before approval, not a
  withdrawal of an already-approved/active invitation.
- **Recurring invitations.** One-off single/group invitations only.
- **Automatic watchlist/blacklist matching.** `watchlistFlagged` and
  `POST /invitations/{id}/watchlist-override` exist (see "Lifecycle
  actions" above), but nothing sets the flag yet — no matching logic runs
  at creation or anywhere else.
- **Hardware/printer integration for badges.** `POST /invitations/{id}/badge`
  renders and stores a badge image a reception device can retrieve and send
  to its own printer; there is no server-to-printer protocol.
- **Scheduled escalation/auto-approve enforcement.** Each approval step's
  `escalatesAt`/`autoApprovesAt` are computed and exposed (see "Per-category
  multi-step approval" above), but no Celery beat task acts on either yet —
  a step overdue for escalation or auto-approval just sits `pending` until a
  human acts on it.
- **Resubmission after a workflow rejection.** Rejecting any step denies the
  invitation outright; there is no path back to `submitted`.
- **SMS gateway integration.** See the config table above.

**Visitor-authored registration** — removed along with API-10 as a *remote*
self-service flow, but reintroduced as an *on-site* one: a visitor arriving
without a prior invitation now registers themselves via `POST
/registrations/walk-in` (API-13, `docs/features/registrations.md`),
authenticated by a branch's device credential rather than a staff bearer
token. It reuses this feature's exact `InvitationCreate` contract and writes
to the same `Invitation` table, tagged `source: "visitor_walk_in"` instead of
`"staff_pre_registration"`.
