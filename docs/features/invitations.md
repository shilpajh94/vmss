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
| POST | `/api/v1/invitations` | `invitations:create` at the resolved branch | — | An employee creates a fully completed single or group invitation in one call: `visitorCategoryId` (required — must resolve to an active `VisitorCategory` in the tenant), primary contact, co-visitors, visit details, carried items, vehicles, and consent, each visitor (including the primary contact) with their own ID-proof upload. Multipart: a JSON `payload` part (camelCased fields, matching `InvitationCreate`) plus `primary_contact_id_proof_file`/`visitor_id_proof_files` file parts — multipart field *names* are the literal Python parameter names, not camelCased, since they aren't part of a JSON body. Returns a tracking ID with the invitation's status resolved from `Company.autoApprovePreRegisteredVisitors` — `approved` immediately, or `submitted` (awaiting approval) — see "Auto-approve vs. manual approval" below. If the invitation submits `submitted` and its category has an active approval workflow, the response's `currentApprovalStep` shows the first step immediately — see "Per-category multi-step approval" below. Accepts an optional `Idempotency-Key` header (`api-conventions.md` §3) — a retried request with the same key and tenant returns the original response instead of creating a second invitation. **BREAKING**: `visitorCategoryId` is a new required field — existing callers must be updated to send it. See "Finding the payload shape in Swagger" below for where to actually see the `individual`/`group` JSON examples in `/docs`. |
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
| GET | `/api/v1/invitations/{id}` | `invitations:view` at the invitation's branch | — | Authenticated, staff-facing single-invitation detail view (`InvitationDetailOut`) — branch/source/creator plus every lifecycle field below. 404 unknown id, 403 (not 404) if the caller lacks branch access. See "Lifecycle actions" below. |
| PATCH | `/api/v1/invitations/{id}/deny` | `invitations:deny` at the invitation's branch | — | Transitions a `submitted` invitation to `denied`, with a mandatory `reason`, and dispatches a denial notification. 409 if not currently `submitted`. |
| PATCH | `/api/v1/invitations/{id}/check-in` | `invitations:checkin` at the invitation's branch | — | **Deprecated** — see the public `/api/v2` route below. Transitions an `approved` invitation to `checked_in`. 409 if not `approved`, or if `watchlistFlagged` is set and not yet overridden. Accepts `Idempotency-Key`. Response carries a `Deprecation: true` header. Target removal date: TBD (see `openspec/changes/add-public-checkin-endpoint/design.md` Open Questions) — not yet removed, still fully functional. |
| PATCH | `/api/v2/invitations/{trackingId}/check-in` | None (public) | 20/minute per IP | Public, unauthenticated check-in by the invitation's `tracking_id` (`INV-XXXXXXXX`) — the manual desk fallback for when a camera isn't available. Same transition/409/404 rules as the `v1` route; no branch-authorization check since there's no authenticated caller. Audit entries for this path use `actor_user_id = null` and `action = "invitation_checked_in_public"`. Accepts `Idempotency-Key`. See "The tracking ID is a plain, human-readable identifier" below for how tenancy resolves with no bearer token. |
| PATCH | `/api/v2/invitations/qr/{token}/check-in` | None (public) | 20/minute per IP | Public, unauthenticated QR scan check-in (`add-qr-checkin-security`) — `token` is the encrypted, tamper-evident check-in token encoded in the invitation's QR image (see "QR check-in: encrypted token and the `checkInStatus` lifecycle" below), not the tracking ID. The same token drives every direction, cycling for as many entry/exit round trips as the visitor makes: a scan while outside (`unused`/`checked_out`) checks the visitor in, a scan while `checked_in` checks them out — `checked_out` is never a dead end. 400 for an invalid/tampered token or a not-yet-approved invitation, 409 for a watchlist block, 410 if scanned for entry (first or repeat) after `expiresAt` has passed (the exit scan is never expiry-blocked). Audit entries use `action = "invitation_qr_checked_in"`/`"invitation_qr_checked_out"`, one per scan. Accepts `Idempotency-Key` — a scanning client must mint a fresh key per physical scan, not reuse one across scans. |
| PATCH | `/api/v1/invitations/{id}/check-out` | `invitations:checkout` at the invitation's branch | — | Transitions a `checked_in` invitation to `checked_out`, closing the visit. 409 if not `checked_in`. Accepts `Idempotency-Key`. |
| PATCH | `/api/v1/invitations/{id}/reschedule` | `invitations:reschedule` at the invitation's branch | — | Changes `preferredVisitDate`/`preferredVisitTime` while `submitted` or `approved`, and dispatches a reschedule notification to the primary contact. 409 once `checked_in`/`checked_out`/`denied`. |
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

`visitDetails` accepts four new *optional* fields alongside its existing
free-text ones: `purposeId`, `hostId`, `durationId`, `departmentId` — see
`docs/features/visit_info.md` for where those ids come from
(`GET /hosts/search`, `GET /visit-info/departments`,
`GET /visit-info/options`). When one is supplied, the service resolves it
against the corresponding catalog/`Department`/`User` row (rejecting the
request with `422` if it doesn't resolve to an existing, active row in this
tenant's schema) and overwrites the paired free-text field
(`purposeOfVisit`/`hostNameOrEmail`/`expectedDuration`/`departmentToVisit`)
with that row's canonical display value before persisting — the
client-supplied free-text value for that field, if any, is discarded in favor
of it. Omitting all four ids leaves every free-text field stored exactly as
submitted, byte-for-byte the pre-existing behavior — this was an additive
change, not a breaking one. `POST /registrations/walk-in` inherits the same
behavior automatically, since it submits the identical `VisitDetailsSubmit`
shape.

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
in flight. A category with no active rules, and no resolved host (see
below), gets no steps, and that invitation keeps exactly the single-approve
behavior described above.

**The invitation's own host is always the first approver, when resolved.**
Whenever `hostId` resolves to an active user at submission (see "Optional
catalog ids on visit details" above), an additional step is prepended at
`stepOrder` 0, ahead of any role-based steps — unconditionally, whether or
not the category has any configured rules. See `docs/features/approvals.md`
"Host as step 0" for the full composition rules and authorization details;
in short: this step is authorized for that specific person (or
`invitations:approve-override`), not by role match.

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
- **`hostId`** (the invitation's resolved host user id, or `null`) is
  included on `InvitationOut` and `InvitationDetailOut` alongside the
  existing free-text `hostNameOrEmail`.
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
source, status, `visitorCategoryId`, primary contact name, purpose of visit,
and expiry/submission timestamps — deliberately narrower than
`InvitationTrackingOut`: it carries no per-visitor/vehicle detail, and no
`currentApprovalStep` either, so the underlying query never needs to
eager-load a child collection or run the extra current-step lookup for a
list view that doesn't render either (`query-performance.md` §1-2).

## Relevant to me

`GET /invitations?relevantToMe=true` is a personal worklist, not a narrower
branch scope: it returns invitations where the caller is either the
snapshotted host (the `stepOrder` 0 `InvitationApprovalStep`'s
`approverUserId` — see `docs/features/approvals.md`) or has been delegated
one of that invitation's approval steps (`docs/features/approvals.md`'s
"Host delegation"), regardless of that step's or the invitation's current
status.

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
  outside) toggling with `checked_in` (currently inside) — is a field
  parallel to (not merged with) `status`; see "Lifecycle actions" above
  for why. Scanning drives the transition directly: no separate
  preview/confirm step. `checked_out` is **not** a dead end — a visitor
  may have multiple entry points during one visit (e.g. leaving for lunch
  and returning, or moving between buildings on a multi-building site),
  so a scan while `checked_out` re-admits exactly like a scan while
  `unused`. `unused` and `checked_out` are kept as distinct values only
  for what they record (never entered vs. entered-and-left at least
  once) — the gate treats them identically.
- **Expiry**: checked on every transition *into* `checked_in` — the first
  entry from `unused` and any later re-entry from `checked_out` alike. A
  visit still `checked_in` past `expiresAt` can still be checked out — the
  expiry gates entry, not how long someone already inside can stay.
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

Submission (if it snapshots at least one approval step), approval, denial,
reschedule, check-in, and check-out each also dispatch a **staff-facing
push notification** — additional to, and dispatched independently from, the
visitor email/SMS above. Submission pushes the current approval step's
approver(s) (host or role-at-branch); the other five push the invitation's
host, if one resolved. See `docs/features/notifications.md` for the
dispatch primitive and recipient-resolution rules.

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
