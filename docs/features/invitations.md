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
| GET | `/api/v1/invitations` | `invitations:view-all`, branch-scoped (or none with `relevantToMe=true`) | — | Paginated listing of invitations for triage/browsing — see "Listing invitations" below. |
| GET | `/api/v1/invitations/export` | `invitations:export`, branch-scoped | — | Downloads the matching invitations as CSV or XLSX, one row per visitor, filtered by status and date range — see "Exporting invitations" below. |
| GET | `/api/v1/invitations/lookup-by-email?email=` | `invitations:create`, branch-scoped | — | Staff-authenticated prefill lookup for the create-invitation wizard's Primary Contact fields: returns `fullName`, `phone`, `preferredContactMethod`, `visitorCategoryId`, `idProofType`, `photoUrl`, `idProofUrl` from the most recent non-deleted invitation, among the caller's authorized branches, whose primary contact email matches case-insensitively. `data: null` (not 404) when no match — same "no match is not an error" convention `GET /api/v1/visitor-portal/me` uses. Gated by `invitations:create` rather than `invitations:view` since it only exists to prefill that create flow. `photoUrl` is always resolved when captured (same as every other invitation response); `idProofUrl` is `null` unless the caller additionally holds `documents:view` at the matched invitation's branch — `invitations:create` alone does not grant identity-document visibility, matching `GET /invitations/{id}`'s existing gating. See `openspec/changes/add-invitation-lookup-by-email/`. |
| GET | `/api/v1/invitations/track?trackingId=` | None (public) | 20/minute per IP | Full status/visit-summary lookup by the human-readable tracking ID — returns `InvitationTrackingOut`, including every visit-detail and carried-item field captured at creation. |
| GET | `/api/v1/invitations/track?email=` | None (public) | 20/minute per IP | Minimal lookup (tracking ID + status only per matching invitation) by the primary contact's email — returns a `list[InvitationTrackingSummaryOut]`, a narrower shape than the tracking-ID lookup above; see "Minimal disclosure" below. Both shapes are declared on the endpoint's `response_model` as a union, so `/docs`/`/openapi.json` document the email-lookup branch's real (narrower, list) shape instead of the tracking-ID branch's. |
| GET | `/api/v1/invitations/{id}` | `invitations:view-all` at the invitation's branch, **or** being a participant (same rule as `relevantToMe`) | — | Authenticated, staff-facing single-invitation detail view (`InvitationDetailOut`) — branch/source/creator plus every lifecycle field below. Also includes resolved `branch`/`building`/`department` detail (alongside the existing raw `branchId`) and the primary contact's/each visitor's `idProofType`; `idProofUrl` (the raw document image) is included only when the caller additionally holds `documents:view` — see "Resolved location and permission-gated ID-proof documents" below. 404 unknown id; 404 also for a non-participant who holds only `invitations:view` there (e.g. an uninvolved host — existence is not disclosed); 403 if the caller holds no invitation-viewing grant there at all. See "Who can see an invitation" and "Lifecycle actions" below. |
| PATCH | `/api/v1/invitations/{id}/deny` | `invitations:deny` at the invitation's branch | — | Transitions a `submitted` invitation to `denied`, with a mandatory `reason`, and dispatches a denial notification. 409 if not currently `submitted`. |
| PATCH | `/api/v1/invitations/{id}/revert-approval` | `invitations:revert-approval` at the invitation's branch | — | Sends an `approved` invitation whose visitor has never checked in back to `submitted`, with a mandatory `reason` (1–500 chars, trimmed). Resets and restarts its approval workflow from step 1. See [Reverting an approval](#reverting-an-approval). 409 if not `approved` or already checked in. |
| PATCH | `/api/v2/invitations/{trackingId}/check-in` | None (public) | 20/minute per IP | **The single staff/desk-facing check-in endpoint** — the legacy `PATCH /api/v1/invitations/{id}/check-in` route has been removed outright (`checkin-approval-workflow-improvements`). Public, unauthenticated check-in by the invitation's `tracking_id` (`INV-XXXXXXXX`). Transitions an invitation whose `checkInStatus` is `unused` or `checked_out` to `checked_in` (`allow-multiple-checkins` — `checked_out` is not terminal, mirroring the QR endpoint's cycling rule below); `status` must also show the invitation was validly approved at some point (`approved`, `checked_in`, or `checked_out` — never `submitted`/`denied`). A call while already `checked_in` is a **200 idempotent no-op** (unchanged data, no re-stamped `checkedInAt`) rather than an error — this holds even if the invitation was checked in via the *other* check-in endpoint (QR), since both read/write the same `checkInStatus` column. 409 if never approved ("Invitation is not approved") or if `watchlistFlagged` is set and not yet overridden. Accepts `Idempotency-Key` (optional — the already-checked-in case is idempotent on its own; the header only dedupes two distinct concurrent requests). No branch-authorization check since there's no authenticated caller. Audit entries for this path use `actor_user_id = null` and `action = "invitation_checked_in_public"`. Success response (`InvitationCheckInOut`) matches the public tracking lookup's field set — primary contact name, host display name, purpose of visit, department, preferred visit date/time, expected duration, additional notes, carried items, co-visitors, and vehicles — alongside the id/trackingId/status fields it already carried. It does not carry `branchId`/`createdByUserId`/badge/watchlist-override internals, resolved branch/building/department, or any ID-proof field; those stay exclusive to `GET /invitations/{id}` (branch/building/department also on the QR endpoints below) — this endpoint has no authenticated caller to gate anything by, so it stays exactly as minimally-revealing as before. See "The tracking ID is a plain, human-readable identifier" below for how tenancy resolves with no bearer token. |
| PATCH | `/api/v2/invitations/qr/{token}/check-in` | None (public) | 20/minute per IP | Public, unauthenticated QR scan check-in — `token` is the encrypted, tamper-evident check-in token encoded in the invitation's QR image (see "QR check-in: encrypted token and the `checkInStatus` lifecycle" below), not the tracking ID. **No longer toggles** (`checkin-approval-workflow-improvements`): entry only, `unused`/`checked_out` → `checked_in`. Scanning while already `checked_in` is a **200 idempotent no-op** (not a silent toggle to checked-out, and not an error) — same "Verification passed" message, unchanged data; use the check-out endpoint below to actually exit. 400 for an invalid/tampered token or a not-yet-approved invitation, 409 for a watchlist block, 425 if scanned before `preferredVisitDate` (`qr-checkin-scheduling-photo-email`), 410 if scanned after `expiresAt` has passed. Audit entries use `action = "invitation_qr_checked_in"`. Accepts `Idempotency-Key` — a scanning client must mint a fresh key per physical scan, not reuse one across scans. Also includes resolved `branch`/`building`/`department` detail and the primary contact's/each visitor's `idProofType` — but never an ID-proof document URL, since there's no authenticated caller to gate one by; see "Resolved location and permission-gated ID-proof documents" below. |
| PATCH | `/api/v2/invitations/qr/{token}/check-out` | None (public) | 20/minute per IP | Exit counterpart of the QR check-in route above, added by `checkin-approval-workflow-improvements` to replace its old check-in-URL toggle. `checked_in` → `checked_out`; 409 if not currently `checked_in`. Never expiry-blocked — a visit that legitimately continues past `expiresAt` can still be closed out. Audit entries use `action = "invitation_qr_checked_out"`. Accepts `Idempotency-Key`. Same resolved `branch`/`building`/`department`/`idProofType` fields as the check-in endpoint above. |
| GET | `/api/v1/public/email-assets/{tenantId}/qr/{invitationId}.png?exp=&sig=` | None (public; HMAC-signed URL) | 60/minute per IP | (`serve-email-images-by-url-and-complete-contact`) The check-in QR image that confirmation and approved-reschedule emails reference by URL instead of embedding it. Returns `image/png`, regenerated from the token persisted at approval. The signature covers tenant id, invitation id and `exp` (the invitation's `expiresAt` + 7 days at send time): 403 on a mismatch — including a swapped tenant or invitation id — 410 once expired, 404 for an unknown tenant/invitation/QR row. See `docs/features/notifications.md` "Images load by URL". |
| PATCH | `/api/v1/invitations/{id}/check-out` | `invitations:checkout` at the invitation's branch | — | Transitions a `checked_in` invitation to `checked_out`, closing the visit. 409 if not `checked_in`. Accepts `Idempotency-Key`. Standard roles holding `invitations:checkout`: Admin, Security, and Reception (`grant-reception-checkout-permission` — backs the web board's manual Check Out button; existing tenants are backfilled by tenant migration `bff38dfa42e7`). Host does not. |
| PATCH | `/api/v1/invitations/{id}/reschedule` | `invitations:reschedule` at the invitation's branch | — | Changes `preferredVisitDate`/`preferredVisitTime` while `submitted` or `approved`, and dispatches a reschedule notification to the primary contact. 409 once `checked_in`/`checked_out`/`denied`. |
| PATCH | `/api/v1/invitations/{id}/edit` | `invitations:edit` at the invitation's branch (**and** `invitations:approve` when `pocUserId`/`pocRoleId` is supplied) | — | (`role-based-invitation-workflow`) Edits any subset of `purposeOfVisit`/`purposeId`, `preferredVisitDate`, `preferredVisitTime`, `expectedDuration`/`durationId`, `departmentToVisit`/`departmentId`, `additionalNotes` while `submitted` or `approved` — the same eligible-status window as reschedule/extend, additive alongside them rather than replacing either. Never accepts the visitor's own personal fields, `visitorCategoryId`, or `hostId`/`hostNameOrEmail` — any of those in the request body is rejected with a validation error (`extra="forbid"`); host reassignment stays exclusively the delegation endpoint's job (see "Every invitation starts owned by a role" below). Also accepts `pocUserId`/`pocRoleId` (`add-invitation-point-of-contact`, see "Point of contact" below) — at most one of the two, never both (422 otherwise). Dispatches an email to the primary contact describing what changed (reflecting the current `pocName`, whether or not it was the field that changed), a push to the resolved host (if any), and — when the point of contact was just (re)set — a push to the new point of contact (a specific user, or every holder of a role at the branch) plus an email when it's a specific user. 409 once ineligible. |
| PATCH | `/api/v1/invitations/{id}/extend` | `invitations:extend` at the invitation's branch | — | Pushes `expiresAt` forward while `approved` or `checked_in`. 422 if the new expiry isn't strictly later than the current one; 409 if ineligible. |
| POST | `/api/v1/invitations/{id}/badge` | `invitations:badge` at the invitation's branch | — | Issues a printable badge (PNG) for an `approved`/`checked_in` invitation. 409 if ineligible or already issued (use reprint). Accepts `Idempotency-Key`. |
| POST | `/api/v1/invitations/{id}/badge/reprint` | `invitations:badge` at the invitation's branch | — | Re-renders an already-issued badge from current data and increments its reprint count. 409 if none issued yet. |
| POST | `/api/v1/invitations/{id}/watchlist-override` | `invitations:watchlist-override` (admin only by default) at the invitation's branch | — | Clears a `watchlistFlagged` invitation, with a mandatory `reason`, so check-in can proceed. 409 if not currently flagged. Does not itself check the invitation in. |

## Links in invitation emails

Every visitor- and staff-facing invitation email (received, confirmed,
rescheduled, edited, denied, submission triage, host assigned, POC
assigned) carries a button into the web portal when `STAFF_PORTAL_URL` is
set. Visitor emails link to `/visitor/track` (denials link to
`/visitor/request` instead), and staff emails link to `/staff/login`. See
`docs/features/notifications.md` "Portal links" for the full table.

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

### Admin-authored answers are referenced by field/group id, never by key (`restructure-walkin-payload-by-field-id`, **BREAKING**)

`consents`, `customFields` (at every scope), and `groups` all reference a
`FormField`/`FormFieldGroup` by its `id` (a UUID), never by its `key`/label
— see "Consents", "Admin-defined custom fields", and "Admin-defined
repeatable groups" below for each shape. A caller resolves the current
`fieldId`/`groupId` values from the branch's currently published form
(`GET /form-builder/effective`), the same read it already uses to render
the form and its labels/options — never hardcoded. This applies uniformly
whether the caller submitted the old key-keyed shape or not; there is no
transitional dual-accept — see "Finding the payload shape in Swagger" for
how to discover the exact current request/response shape.

### ID proof type and vehicle type are branch-configured, not fixed (`make-id-proof-and-vehicle-type-configurable`, **BREAKING**)

`idProofType` (`primaryContact`/each `visitors[]` entry) and `vehicleType`
(each `vehicles[]` entry) are plain strings, not a fixed server-side enum —
a valid value is whatever the calling branch's currently published Form
Builder "ID Proof Type"/"Vehicle Type" options declare
(`GET /form-builder/effective`'s Visitor Info/Vehicle Info steps), the same
"branch's currently configured options" contract `carriedItems.items` uses.
Submitting a value outside the branch's current
options is rejected with `422`. A branch that has never customized either
field accepts the original four ID proof types
(`Aadhaar Card`/`Passport`/`Driving License`/`Other`) and three vehicle
types (`2_wheeler`/`4_wheeler`/`heavy`) unchanged — those are the seeded
defaults, not special-cased in code. See `docs/features/form_builder.md`
for how an admin edits these two fields' options.

### Vehicle count and admin-defined repeatable groups (`add-repeatable-field-groups`)

The number of `vehicles[]` entries a request may declare is now checked
against the branch's currently published Vehicle Info field-group instance
range (`GET /form-builder/effective`'s Vehicle Info step, `groups[].key ==
"vehicles"`) instead of being unconditionally unlimited — a branch that
has never configured a minimum/maximum still accepts any number of
vehicles, including zero, unchanged from before this change.

The number of `visitors[]` entries a `group` registration may declare is
similarly checked against Visitor Info's field group's `maxInstances`
(`groups[].key == "visitors"`) — this **replaces** the previous
`INVITATION_MAX_GROUP_VISITORS` settings-based rejection (still 20 by
default, seeded into that group at migration time), so a client that was
relying on the old 422 message text should expect the same status code
via a different underlying check. Unlike Vehicle Info's group, Visitor
Info's isn't admin-editable through the Form Builder API — see
`docs/features/form_builder.md`'s "Field groups" for why.

An admin can also define a **repeatable field group** on any other step
(e.g. a "Parcels" group on Carried Items), optionally made **conditional**
on another field's value, through Form Builder — see
`docs/features/form_builder.md` "Field groups"/"Conditional groups".
`POST /invitations` (and `POST /registrations/walk-in`) accepts that
group's answers as an optional top-level `groups: {groupId, instances}[]`
array, each entry's `groupId` referencing the group's live id (never its
key/label) and `instances` an ordered array of that group's per-instance
answer sets — each instance itself a `customFields`-shaped
`{fieldId, value}[]` array, one instance per visitor-filled repetition. A
submission naming a `groupId` the branch's active form doesn't define (or
that belongs to a different branch/tenant), or supplying more instances
than that group's currently published `maxInstances`, is rejected with
`422` before any invitation is created — the same "validate everything,
then persist" ordering ID-proof file validation already uses, so one
invalid instance never leaves a partially-created invitation behind. Every
response that already returns `customFields` (`GET /invitations/{id}`, the
tracking lookup, the canonical check-in response, and the QR check-in/
check-out response) now also returns `groups` in the same
`{groupId, instances}[]` shape, alongside it.

**When a group is hidden** by its `visibilityCondition` (evaluated against
the same request's own submitted values), the request is accepted even if
that group's fields would otherwise be required, and even if fewer
instances are submitted than the group's configured minimum — a visitor
who was never shown the group can't be expected to have filled it in. Its
maximum still applies if instances are submitted anyway, and any value
that is supplied for a hidden group's field is still validated against
that field's own type/options/length rules.

### Repeatable group file uploads (`add-group-field-file-upload`)

If a repeatable field group has its own `file_upload`-typed field (Form
Builder field type `file_upload`), that field's answer can only come from a
multipart file — never a JSON value in `groups`. Only a group's
**first** `file_upload` field is read; a group with more than one is
supported for definition but only the first is ever populated this way.

The client sends one multipart **list** part named
`groupFieldFiles[<groupId>]`, **order-matched** to that same group's
`payload.groups` entry's `instances` — the same "list, order-matched
to instances" convention `visitorIdProofFiles`/`visitor_id_proof_files`
already uses for the fixed `visitors` list. There is no `instanceIndex` or
field id encoded in the part name: file *n* in the list pairs with
instance *n* of the `groups` entry whose `groupId` matches `<groupId>`.

- The instance's `customFields` array must **omit** that field id (or
  send `null` for its value) — supplying any other value for it is
  rejected with `422` (`"'<fieldId>' in '<groupName>' instance <n> must
  be uploaded as a file, not supplied as a value"`), never silently
  overwritten.
- If the field is required (and the group is visible), every instance must
  have a matching file — a count mismatch is rejected with `422`
  (`"Field group '<groupName>' requires an uploaded file for every
  instance"`). More files than instances is also rejected (`422`, `"More
  files were uploaded than instances of '<groupName>'"`).
- Accepted files are validated the same way a top-level ID-proof upload is
  (`_validate_id_proof`), stored via the same `core/storage.py::save`
  interface under the `invitations/group-files` category, and the
  resulting storage key is written back into that instance's field
  (keyed by `fieldId`) in the persisted `groups` — never a client-supplied
  value.

`POST /registrations/walk-in` accepts the identical `groupFieldFiles[...]`
contract — see `docs/features/registrations.md`.

### Inline (non-grouped) custom-field file uploads (`add-inline-custom-field-file-upload`)

An admin-authored `file_upload`-typed field that is *not* assigned to a
repeatable field group (e.g. an "additional document" field added directly
on Visitor Info, not one of its groups) — the standalone counterpart of the
repeatable-group case above. Unlike a group (whose multipart part is keyed
by group id alone, so only the group's *first* `file_upload` field is
read), each of these fields has its own multipart part keyed by field id,
so every `file_upload` field at a scope is supported, not just one.

Four scopes, one multipart convention each:

| Scope | Multipart part | Shape |
|---|---|---|
| Primary contact (Visitor Info) | `primaryContactCustomFieldFiles[<fieldId>]` | At most one file. |
| Each co-visitor (Visitor Info) | `visitorCustomFieldFiles[<fieldId>]` | Order-matched list, same convention as `visitor_id_proof_files`. |
| Each vehicle (Vehicle Info) | `vehicleCustomFieldFiles[<fieldId>]` | Order-matched list, same convention as the visitor case. |
| Invitation-level (Visit Details/Carried Items/a custom step) | `customFieldFiles[<fieldId>]` | At most one file. |

**The primary contact's plain-JSON (non-file) custom-field answers are
submitted through the top-level `customFields` array**, not a nested
`primaryContact.customFields` — there is exactly one primary contact per
invitation, so a Visitor Info-step field id in the invitation-level
`customFields` array is understood as the primary contact's answer for it.
`primaryContact.customFields` still exists on the wire but is accepted and
silently ignored (kept only so an already-deployed client sending it
doesn't get a hard validation error). Each co-visitor's and each vehicle's
own answers are unaffected — they still use `visitors[i].customFields`/
`vehicles[i].customFields` respectively, since a group registration has
more than one such answer set and a flat map can't tell whose is whose.
The `primaryContactCustomFieldFiles[<fieldId>]` multipart part name above is
unchanged — file uploads are a separate channel from the plain-JSON one.

- The field's id must be **omitted** from the corresponding `customFields`
  array (the invitation-level one, for the primary contact) — supplying
  any other value for it is rejected with `422`
  (`"'<fieldId>' for <scope> must be uploaded as a file, not supplied as a
  value"`), never silently overwritten, same rule as the repeatable-group
  case.
- If the field is required, every applicable instance (the primary contact;
  each visitor; each vehicle; the invitation itself) must have a matching
  file — a count mismatch is rejected with `422`. More files than instances
  (or more than one file for a single-instance scope) is also rejected.
- Accepted files are validated and stored the same way a group's own
  `file_upload` field is (`_validate_id_proof`, `core/storage.py::save`,
  category `invitations/custom-fields`), and the resulting storage key is
  written back into the persisted `customFields`/
  `primaryContactCustomFields`/a vehicle's own `customFields` array (keyed
  internally by `fieldId`) — never a client-supplied value. Every reader
  (`router.py::_resolve_custom_field_file_values`/`_resolve_group_field_
  values`, applied to the invitation, primary contact, every visitor, every
  vehicle, and every `groups` instance alike) resolves that
  storage key to a signed, time-boxed URL (`core/storage.py::url_for`)
  before it reaches a response — gated by the caller's `documents:view`
  grant for the invitation's branch the same way `photoUrl`/`idProofUrl`
  already are: a caller without that permission gets `null` for the field
  instead of either the raw key or a usable URL, never a fallback that
  leaks the key.
- The file-field ids resolved this way are always the branch's *current*
  effective form. If a field's type is changed after invitations already
  hold data under its id, an older instance's value may not be a storage
  key at all — that's resolved to `null` too, rather than passed to
  `core/storage.py::url_for`, which can only sign an actual string key.

`POST /registrations/walk-in` accepts the identical
`primaryContactCustomFieldFiles[...]`/`visitorCustomFieldFiles[...]`/
`vehicleCustomFieldFiles[...]`/`customFieldFiles[...]` contract — see
`docs/features/registrations.md`.

### Retyped system fields and submission validation (`make-system-field-types-editable`)

`fullName` (`primaryContact`/each `visitors[]` entry), `purposeOfVisit`,
`expectedDuration`, `additionalNotes` (`visitDetails`), and
`licensePlate` (each `vehicles[]` entry) can now also be retyped through
Form Builder (see `docs/features/form_builder.md` "Changing an existing
field's type"), extending the same dynamic validation
`idProofType`/`vehicleType` already use: when a field's *currently
configured* type is `dropdown_select`/`checkbox_list`, a submitted value
must match one of the branch's currently published options for that
field, rejected with `422` otherwise. When it's still its default
(non-option-bearing) type, the submitted value is validated as ordinary
free text, unchanged from before this change. `hostNameOrEmail` and
`departmentToVisit` are not covered by this — neither is a Form Builder
field any more (`remove-dead-host-department-system-fields`): `host`'s
submitted value is always discarded (see "`hostId`/`hostNameOrEmail` are
no longer resolved at creation" above), and `departmentToVisit` is always
validated as ordinary free text (or resolved from the `departmentId`
catalog — see "Optional catalog ids on visit details" above), never
gated by a Form Builder option list.

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

### A returning primary contact's name (and email, if omitted) is locked to their prior visit (`dedupe-repeat-visitor-registrations`)

Before writing a new invitation, `create_invitation` checks whether the
*primary contact* has visited before — a new row is always created for this
visit either way (visit history/audit is completely unaffected), but the
identity fields it's created with may be overridden:

- **Email match**: when the request's `primaryContact.email` is non-null and
  matches the email on a prior invitation (any status — `approved`,
  `submitted`, `denied`, `checked_in`, `checked_out`, or expired; if more
  than one matches, the most recently created one wins), the new
  invitation's `primaryContactFullName` is silently overridden with that
  prior invitation's value, **regardless of what the request submits**. A
  visitor who wants to register under a different name does so by
  registering under a different email — there is no "edit my name" path
  through creation.
- **Phone fallback**: when the request omits `primaryContact.email`
  entirely (only `phone` supplied — requires `preferredContactMethod:
  "sms"`, see `InvitationPrimaryContactCreate._check_contact`) and that
  phone matches a prior invitation's phone, the new invitation's
  `primaryContactFullName` **and** `primaryContactEmail` are both carried
  forward from that prior invitation, rather than leaving email null.
- **A non-matching email always wins over a matching phone.** If the
  request supplies an email that doesn't match anything on file, it is
  always treated as a first-time contact — even if its phone happens to
  match a *different* prior invitation's phone. Email is the sole
  authoritative identity key; phone is only ever a fallback for when no
  email is given at all. This is deliberate, not a gap: it's how the
  system avoids ever silently merging two people who happen to share a
  phone (e.g. a shared reception/family line) under one identity.

Every other primary-contact field (`phone` in the email-match case,
`preferredContactMethod`, ID proof, photo, `customFieldValues`) and
everything inherently per-visit (`visitorCategoryId`, visit details,
carried items, vehicles, consents, co-visitors) is taken from the new
request exactly as submitted — untouched by this lookup. **Co-visitors are
completely out of scope**: `invitation_visitors` rows are never matched,
locked, or carried forward, even if a co-visitor's email matches someone
listed as a co-visitor on an earlier invitation.

**BREAKING**: a caller submitting a different `fullName` for an
already-seen email/phone no longer gets that name recorded — the response
echoes back the *stored* name (and, for a phone-fallback match, the
*stored* email), not what was submitted. `POST /registrations/walk-in`
inherits this behavior automatically, with no code of its own, since it
calls straight into `create_invitation`. See
`openspec/changes/dedupe-repeat-visitor-registrations/design.md` for the
full rationale and alternatives considered.

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
"host resolves at creation, if a client supplied one" behavior). The
invitation's *first* snapshotted step — whichever role the category's own
workflow configures for its lowest `stepOrder`, or, only when the category
has no configured rules at all, a synthetic `stepOrder` 0 step role-identified
for the tenant's *default host role* (the standard `reception` role unless a
tenant has reconfigured it via `Company.defaultHostRoleId`) — doubles as the
invitation's host-nomination step (**revised**: an earlier version of this
feature always added that default-host-role step unconditionally, ahead of
the category's own rules, producing an extra step whenever the category's
own first level was already configured as that same role; see
`docs/features/approvals.md` "The host-nomination step" for the full
history). The blanket `POST /invitations/{id}/approve` endpoint is never
reachable for a newly created invitation regardless — every one still has
at least one snapshotted step. The invitation's actual host is established
later, not at snapshot time: whoever holds that first step's role delegates
it to a specific person (see `docs/features/approvals.md` "The
host-nomination step" for the full delegation-eligibility rules), and that
delegation is what sets `hostId`/`hostNameOrEmail` — see "`hostId` reflects
the resolved host, not the original creator's input" below.

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
  `stepId`. **`totalSteps` counts this invitation's own snapshotted steps**
  (a point-in-time copy taken at submission — see
  `docs/features/approvals.md` "The host-nomination step" — never re-read
  from the category's live rules afterward), which is the category's active
  rule count *at submission time*, or `1` when the category had none (the
  one case a synthetic step still gets added). This now matches the row
  count from `GET /approval-workflow-rules?visitorCategoryId=...` exactly
  (or `1` if that returns no rows) — there is no longer a built-in
  off-by-one between the two. If you need to confirm a specific invitation's
  snapshot against what was active when it was submitted, compare its
  steps' `approverRoleId`s and timestamps against the `AuditLog` rows for
  that category's `ApprovalWorkflowRule` changes, not against the rule
  count alone.
- **`hostId` reflects the resolved host, not the original creator's
  input** (the invitation's resolved host user id, or `null` before a
  delegation resolves one) — included on `InvitationOut` and
  `InvitationDetailOut` alongside the existing free-text
  `hostNameOrEmail`. Both stay `null` until any step is delegated to a
  specific person, and update again to that delegate on every subsequent
  delegation at any `stepOrder` — not just the host-nomination step — so
  `hostId` always tracks the most recently delegated step. Nothing set at
  creation ever populates them. **Exception**: for a **single-step
  (reception-only) workflow** — the category has no active
  `ApprovalWorkflowRule`, so the invitation snapshots only the one
  synthetic host-nomination step — there is no later step to delegate
  through, so directly *approving* that one step also resolves `hostId`/
  `hostNameOrEmail` to the approving user, the same as a delegation would
  (see `docs/features/approvals.md` "The host-nomination step" for the
  full rule). This does not apply once a category has any configured
  rules: approving a multi-step workflow's host-nomination step directly
  still leaves `hostId` unresolved.
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

## Point of contact (`add-invitation-point-of-contact`)

Distinct from `hostId`/`hostNameOrEmail` above, which is who the visitor is
meeting and only ever resolves through the approval workflow (delegation, or
directly approving a single-step workflow's only step — see "`hostId`
reflects the resolved host" above). `pocUserId`/`pocRoleId` name who to
actually reach about the visit's logistics, and are set directly, at any
time, via `PATCH /invitations/{id}/edit` — not gated by the invitation's
current approval step/level the way host resolution is:

- At most one of `pocUserId`/`pocRoleId` may be supplied on an edit — never
  both (422 otherwise). An unknown id for either is also 422. Omitting both
  leaves whatever point of contact is already resolved unchanged (same
  "omitted, not reset to null" convention every other edit field already
  follows).
- Setting either requires the caller to additionally hold
  `invitations:approve` at the invitation's branch, checked in
  `invitations/service.py::edit_invitation` on top of this endpoint's own
  `invitations:edit` gate — naming who visitors are routed to is closer to
  an approval action than a visit-detail edit, so not every
  `invitations:edit` holder should be able to set it.
- `pocName` snapshots the resolved display name (the user's `full_name` or
  the role's `name`) at the moment it was set — same convention as
  `hostNameOrEmail` — so rendering it never needs an extra join. All three
  fields (`pocUserId`, `pocRoleId`, `pocName`) are included on `InvitationOut`
  and `InvitationDetailOut`.
- Setting the point of contact notifies the newly-named party: a push to the
  specific user, or to every holder of the role at the invitation's branch
  (the same user-XOR-role routing `notify_step_approver` already does for
  approval steps — `docs/features/approvals.md`), plus an email
  (`poc_assigned.html`) when a specific person was named — mirroring
  `delegate_step`'s host-assigned notification, no email counterpart for a
  role-identified point of contact. Independently, the visitor's own
  edit-notification email (`edit.html`, fired unconditionally on any
  successful edit) includes a "Point of contact" row whenever `pocName` is
  resolved, reflecting its current value regardless of which field the edit
  actually changed — same posture the email already has for purpose/date/
  duration/department.

## Lifecycle actions: deny / check-in / check-out / reschedule / extend / badge / watchlist-override

`add-invitation-lifecycle-actions` adds `status` values `denied`,
`checked_in`, `checked_out` alongside the existing `submitted`/`approved`,
plus one atomic conditional `UPDATE`-based transition per action (same
concurrency-safe shape `POST /invitations/{id}/approve` already uses — a
losing concurrent request gets 409, never a corrupted double-transition):

```
submitted ──deny──> denied
submitted ──approve──> approved ──check-in──> checked_in ──check-out──> checked_out
                                       ▲                                      │
                                       └──────────────check-in────────────────┘
```

- **`checkInStatus`** (`add-qr-checkin-security`) is a second, parallel
  lifecycle field — `unused`/`checked_out` → `checked_in` → `checked_out`,
  cycling indefinitely with no terminal state. It is the actual re-entry
  gate for **both** the tracking-ID/staff check-in endpoint and the QR
  check-in endpoint (`allow-multiple-checkins`) — `check_in_status`, not
  `status`, decides entry-vs-exit eligibility on every check-in path, and
  every check-in/check-out transition on every path writes both columns
  together in the same atomic `UPDATE`, so they can never disagree within
  one request. `status` keeps transitioning exactly as shown in the
  diagram above for both the tracking-ID and QR routes, so anything reading
  `status` (the "who's inside" emergency report, in particular) sees a
  check-in the same way regardless of which endpoint drove it. `checked_out`
  is **not** terminal on either endpoint — a visitor who steps out (lunch, a
  second delivery drop-off, moving between buildings) can be checked back in
  through either endpoint as many times as their invitation stays `approved`
  and unexpired. Calling a check-in endpoint while `checkInStatus` is
  already `checked_in` is a **200 idempotent no-op** (unchanged data, no
  re-stamped `checkedInAt`, no duplicate host notification/audit entry) —
  not an error — whichever endpoint originally checked them in; the caller
  still has to use a check-out endpoint to actually exit. Because both
  check-in endpoints share the one `check_in_status` column, this
  already-checked-in recognition works across endpoints too — checking in
  via tracking-ID then "checking in" again via QR (or vice versa) is
  recognized as the same already-checked-in visitor, not treated as two
  separate entries.
- **Reschedule** (`preferredVisitDate`/`preferredVisitTime`) and **extend**
  (`expiresAt`) operate on different status windows: reschedule only while
  `submitted`/`approved` (before check-in); extend only while
  `approved`/`checked_in` (an active visit). Extend also requires the new
  expiry be strictly later than the current one (422 otherwise).
- **Expiry is the end of the visit day**
  (`expire-invitation-at-end-of-visit-day`): `expiresAt` is 23:59:59 on
  `preferredVisitDate` in the **visit timezone**, regardless of when the
  invitation was submitted (e.g. scheduled 2026-10-02 11:00 IST → expires
  2026-10-02 23:59:59 IST). The visit timezone is the company's
  `defaultTimezone`, else the tenant's `timezone`, else UTC; an invalid IANA
  name is skipped with a `WARNING` (`invitations_invalid_timezone`). It is
  set at creation and approval, and recalculated whenever the visit date
  changes — reschedule (`submitted` or `approved`) or an edit that sets a
  *different* `preferredVisitDate`. Resubmitting the same date on edit does
  not touch `expiresAt`, so a staff extension survives an unrelated edit.
  The QR scheduled-date gate uses the same timezone, so the two always
  agree on which day is "the visit day". Rows created under the old fixed
  7-day TTL were realigned by tenant migration `a7c3e9f1b2d4`.
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

## Reverting an approval

`add-invitation-approval-revert`. An approval made by mistake can be undone
until the visitor first enters:

```
approved ──revert-approval──> submitted   (only while checkInStatus = unused)
```

- **Request**: `PATCH /api/v1/invitations/{id}/revert-approval` with body
  `{"reason": "..."}`. A reason that is missing, empty or whitespace-only,
  or longer than 500 characters, returns 422.
- **Eligibility**: `status = approved` **and** `checkInStatus = unused`,
  checked in one atomic `UPDATE`. Anything else returns 409, and of two
  concurrent reverts only one succeeds. A caller without the permission at
  the invitation's branch gets 403, and an unknown id gets 404.
- **Effect**:
  - `status` becomes `submitted` and `approvedAt` is cleared.
  - `approvalRevertedAt`, `approvalRevertedByUserId` and
    `approvalRevertReason` record the latest revert. They're on
    `InvitationOut` and the detail view, and every revert is also
    audit-logged as `invitation_approval_reverted` with the reason in the
    diff.
  - `expiresAt`, the host, the visit details and the issued QR row are
    left unchanged.
- **Workflow**: every `InvitationApprovalStep` goes back to `pending`, with
  its actor, delegation and clock cleared. The lowest `stepOrder` step
  becomes current again (its clock restarts from now) and its approver gets
  the usual "awaiting approval" push. The step snapshot taken at submission
  is reused, not re-read from the category's current rules. An
  auto-approved invitation has no steps, so it goes back to `submitted` and
  can be approved with `POST /invitations/{id}/approve`.
- **The pass while reverted**: every check-in path (QR, staff, public
  tracking ID) refuses a `submitted` invitation, so the visitor's existing
  QR doesn't admit them. Re-approval re-sends the **same** QR, which then
  works again.
- **Notifications**:
  - The primary contact gets the `approval_reverted` email and SMS
    (`send_approval_revert_notification`). They are told their approval
    was withdrawn and the pass is on hold; the reason is not included,
    since it's an internal note. The task skips sending if the invitation
    has already been re-approved by the time it runs.
  - The host gets a push (`action: approval_reverted`).
  - The host and point of contact also get the staff lifecycle email,
    which does include the reason. See "Notifying the responsible staff"
    below.
- **Permission**: `invitations:revert-approval` is separate from
  `invitations:approve`. It is granted by default to `admin`, `reception`
  and `host`, but not `security`. Tenant migration `6054f5200ed1` backfills
  it to those standard roles in existing tenants.

## Notifying the responsible staff

`staff-lifecycle-emails-and-dashboard-landing`. A denial (direct, or via a
rejected approval step), an approval revert, or a reschedule (including
one out of `archived`) also tells the staff who own the visit, not just
the visitor:

| Who | Email | Push |
|---|---|---|
| Visitor (primary contact) | Existing denial / withdrawal / reschedule email or SMS | — |
| Resolved host (`hostId`) | Staff lifecycle email | Existing host push |
| Point-of-contact user (`pocUserId`) | Staff lifecycle email | Push, unless they're also the host |
| Point-of-contact role (`pocRoleId`) | None, because a role POC is push-only | Push to every holder at the branch or company-wide, with `reason: "lifecycle_update"` |

- **Recipients**: the person who performed the action is never emailed or
  POC-pushed. Someone who is both host and point of contact gets one email
  and one push. Deactivated users are skipped with a `WARNING`. The
  existing host push is unchanged, even when the host is the actor.
- **Email**: `send_staff_lifecycle_notification` sends one Celery task per
  recipient, so a retry never re-sends to someone already emailed. The
  template is `staff_lifecycle_update`, and its tone and pill vary by
  event: red for denied, amber for approval withdrawn, blue for
  rescheduled. It names the actor (or "A staff member" if that account is
  gone) and includes the denial or revert reason. It never includes the QR
  pass.
- **Redelivery**: the task skips the send once the invitation no longer
  reflects the event. A denial must still be `denied`. A revert must still
  be `submitted` with `approvalRevertedAt` set. A reschedule is skipped
  once the invitation is `denied`, `checked_in` or `checked_out`.
- **Extend**: `PATCH …/extend` now pushes the host (`action: extended`,
  plus `expiresAt` in the payload, with the new expiry in the body). It
  sends no email.
- **Not covered**: check-in and check-out stay push-only, and the
  automatic check-out and archive sweep stays silent.

## Staff push coverage

`complete-staff-push-coverage`. Every lifecycle event that pushes the host
also pushes the point of contact. The POC rules are the same for every
event: the actor and the host are never POC-pushed (the host already gets
the host push), a role POC fans out to every holder at the branch or
company-wide with `reason: "lifecycle_update"`, and an invitation with no
POC skips the push. QR and kiosk check-in/check-out have no human actor, so
only the host is excluded there. Staff email is unchanged: only deny,
revert and reschedule email staff.

| Event (`action`) | Host | Point of contact | Approver(s) |
|---|---|---|---|
| Submitted (`step_awaiting_approval`) | — | — | Push to the first step's user or role (not Admin or `host` role) |
| Next step activated (`step_awaiting_approval`) | — | — | Push to that step's user or role |
| Host named by delegation (`host_assigned`) | Push + email to the new host | — | — |
| POC named by edit (`poc_assigned`) | — | Push to the new POC (+ email for a user POC) | — |
| Approved (`approved`) | Push | Push | — |
| Denied / reverted / rescheduled | Push + email | Push (+ email for a user POC) | — |
| Checked in / out (`checked_in`, `checked_out`) | Push | Push | — |
| Pass extended (`extended`) | Push | Push | — |
| Details edited (`edited`) | Push | Push to a POC already in place; a POC named by this same edit gets only `poc_assigned` | — |

Not pushed to any staff: auto-approved creation (no host or POC exists yet),
the visit-lifecycle sweep's auto check-out and no-show archive, watchlist
flags and kiosk device registrations (no recipient role is defined for
either).

## Automatic check-out and archived no-shows

`auto-checkout-and-archive-no-shows`. A visit nobody closes by hand is
closed by the visit-lifecycle sweep. That is a Celery beat task running
every 15 minutes per tenant; see `docs/features/background-jobs.md`.

```
checked_in ──expiresAt passes──> checked_out   (checkedOutAutomatically = true)
approved (checkInStatus unused) ──expiresAt passes──> archived
archived ──reschedule / edit date──> submitted ──approve──> approved
```

- **Trigger**: the invitation's live `expiresAt`, which is the end of the
  visit day in the visit timezone. An extension via `PATCH …/extend`
  postpones both transitions. No timezone logic lives in the sweep itself.
- **Auto check-out**:
  - It applies to any row where `status` or `checkInStatus` is
    `checked_in`. Both columns become `checked_out`.
  - `checkedOutAt` is set to the invitation's `expiresAt`, not the sweep
    time.
  - `checkedOutByUserId` stays null and `checkedOutAutomatically` is
    `true`.
  - Any later manual check-out (staff or QR) writes the flag back to
    `false`.
  - A QR check-out of a visit the sweep already closed returns 409.
- **Archive**:
  - Only `approved` rows whose `checkInStatus` is still `unused` are
    archived. `status` becomes `archived` and `archivedAt` is set.
  - A `submitted` row whose date passed is left alone.
  - `expiresAt`, the visit details, the approval steps and the QR row are
    unchanged.
- **Silent and audited**:
  - No email, SMS or push is sent for either transition.
  - Each changed invitation gets one audit row with no actor
    (`invitation_auto_checked_out` / `invitation_archived`), written in the
    same transaction as the change.
  - Re-running the sweep changes nothing.
- **An archived pass is inert**:
  - Every check-in path (QR, staff, public tracking ID) returns 409 with
    "Invitation is archived; reschedule it to admit the visitor".
  - Extend, badge, revert, approve and deny also return 409.
- **Leaving `archived`**:
  - `PATCH …/reschedule` accepts an archived invitation, with a new date
    of today or later in the visit timezone (otherwise 422). It returns to
    `submitted`: `approvedAt` is cleared, `expiresAt` is realigned to the
    new day, and the reschedule history columns are filled as usual.
  - Every approval step resets and the first is re-activated, with the
    approver pushed, exactly like a revert.
  - The Company auto-approve setting does **not** apply, so someone must
    approve it again. Re-approval re-sends the original QR.
  - `archivedAt` is kept as history.
  - The response includes `currentApprovalStep`.
- **Editing an archived invitation**: `PATCH …/edit` is allowed. If the
  edit doesn't change `preferredVisitDate`, the invitation stays
  `archived`. A date change behaves like the reschedule above (past date →
  422).
- **Response fields**: `archivedAt` and `checkedOutAutomatically` are on
  `InvitationOut`, the list row, the detail view, the tracking lookup and
  both check-in responses. `GET /invitations?status=archived` filters on
  the new status.
- **Export**: status label `Archived`, with an `Archived At` column
  (column 32). `status=archived` keeps Requested At / Approved At /
  Archived At, and its date range applies to `archivedAt`. Checked Out By
  reads `System (auto check-out)` for an automatic check-out.
- **Deploy note**: the first sweep after release processes the backlog.
  Every old approved no-show is archived, and every stuck check-in is
  closed with `checkedOutAt` = its old `expiresAt`. Tenant migration
  `ee5f27776d94` adds the two columns. Its downgrade returns `archived`
  rows to `approved` first.

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

`GET /invitations` gives an authenticated, `invitations:view-all`-gated caller a
paginated, filterable, sortable view of invitations — for browsing/triage
(e.g. "who's expected today at my branch"), not for looking up one
invitation's full detail (that's still `GET /invitations/track`'s job).
Branch scoping matches every other branch-scoped list endpoint
(`docs/features/org_structure.md`'s `GET /buildings`/`GET /floors`): supply
`X-Branch-ID` to narrow to one branch (rejected with 404/403 the same way an
unknown/unauthorized branch id is anywhere else), or omit it to list across
every branch the caller holds `invitations:view-all` at. A `host` holds only
`invitations:view` and gets 403 here — hosts use `relevantToMe=true`.

Query params:

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` / `pageSize` | int | `1` / `20` (max `100`) | Standard pagination (`api-conventions.md` §1). |
| `sortBy` | `submitted_at` \| `created_at` | `submitted_at` | Whitelisted — any other value is rejected with a validation error rather than passed to the database. |
| `sortOrder` | `asc` \| `desc` | `desc` | |
| `status` | string | unset | Exact match against the invitation's `status` column. |
| `registrationType` | `individual` \| `group` | unset | |
| `source` | `staff_pre_registration` \| `visitor_walk_in` | unset | |
| `search` | string (max 255) | unset | Case-insensitive substring match against primary contact name **or** tracking ID. |
| `purposeOfVisit` | string (max 255) | unset | Exact (case-sensitive) match against the invitation's purpose of visit. Used by the paged web board's purpose dropdown so filtering — and `pagination.total` — happens server-side (`add-invitation-purpose-filter`). |
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

## Exporting invitations

`GET /invitations/export` (`add-invitation-export`) returns the invitations
that match the filters as a file download, so staff can take a gate list,
a security handover or a compliance extract offline — for example "everyone
who checked in today" or "all approved visitors next week". It is a raw file
response, not the JSON envelope; every error (403, 404, 422) still uses the
standard JSON error envelope.

**Permission.** `invitations:export`, branch-scoped exactly like the
branch-wide listing: `X-Branch-ID` narrows to one branch, and omitting it
exports across every branch where the caller holds `invitations:export`.
The standard `admin`, `reception` and `security` roles hold it; `host` does
not. Existing tenants receive the grant from tenant migration
`4ea4f6ccffbd`. Custom roles must be granted it by an admin.
`relevantToMe=true` *narrows* the export to invitations relevant to the
caller — unlike the list, it never replaces the permission check.

Query params — every filter of [Listing invitations](#listing-invitations)
with the same meaning (`status`, `registrationType`, `source`, `search`,
`purposeOfVisit`, `relevantToMe`), plus:

| Param | Type | Default | Notes |
|---|---|---|---|
| `format` | `csv` \| `xlsx` | `csv` | Any other value is a 422. |
| `dateFrom` / `dateTo` | date (`YYYY-MM-DD`) | unset | Inclusive calendar dates in the visit timezone (`Company.defaultTimezone`, then `Tenant.timezone`, then UTC). `dateFrom` later than `dateTo` is a 422. |

**Which date the range applies to.** It follows `status`: `submitted` →
submitted-at, `approved` → approved-at, `denied` → denied-at, `checked_in`
→ checked-in-at, `checked_out` → checked-out-at. With no `status`, it
applies to the invitation's creation time. Rows are sorted by that same
timestamp, newest first. `status` matches the *current* status, the same as
the list: `status=approved` does not include visitors who have since checked
in. To get everyone approved in a period regardless of what happened next,
export without `status`.

**One row per visitor.** Each invitation produces one row for its primary
contact, plus one row per co-visitor for a group invitation. All rows of an
invitation are adjacent, primary contact first, and each repeats the
invitation's visit-level fields (badge, vehicles, notes, lifecycle times and
so on).

**Columns** (`improve-invitation-export-readability`), in order: Tracking
ID, Status, Visitor Name, Visitor Role, Email, Phone Number, ID Proof Type,
Visitor Category, Registration Type, Source, Branch, Building, Department,
Host, Point of Contact, Purpose of Visit, Visit Date, Visit Time, Expected
Duration, Badge Number, Vehicle Number(s) (license plates joined with
`, `), Carried Items (items joined with `, `, then ` — ` and the
description if one was given), Additional Notes, Requested At, Approved At,
Denied At, Denial Reason, Checked In At, Checked In By, Checked Out At,
Checked Out By. A value that is not recorded is an empty cell. Custom
form-builder fields are not exported.

**Lifecycle columns follow `status`.** With a `status` filter, only the
lifecycle columns that can hold a value for it are included. With no
`status`, all of them are included. Scripts reading the file should look
columns up by header, not by position.

| `status` | Lifecycle columns included |
|---|---|
| `submitted` | Requested At |
| `approved` | Requested At, Approved At |
| `denied` | Requested At, Denied At, Denial Reason |
| `checked_in` | Requested At, Approved At, Checked In At, Checked In By |
| `checked_out` | Requested At, Approved At, Checked In At, Checked In By, Checked Out At, Checked Out By |

**Labels, not codes.** Status, Source, Registration Type and Visitor Role
use the same wording as the web invitation board:

- Status: `submitted` → Requested, `approved` → Approved, `denied` →
  Denied, `checked_in` → Checked-in, `checked_out` → Checked-out.
- Source: `staff_pre_registration` → Staff Pre-Registration,
  `visitor_walk_in` → Visitor Walk-in.
- Registration Type: Individual / Group.
- Visitor Role: Primary Contact / Co-Visitor.

A code with no label is written in Title Case with spaces, never raw.

**Dates and times.** Timestamps are in the visit timezone. The zone is
named once, in each timestamp header, for example
`Checked In At (Asia/Kolkata)`, not in every cell.

- In CSV, timestamps are `YYYY-MM-DD HH:MM` (24-hour), the visit date is
  `YYYY-MM-DD`, and the visit time is `HH:MM`.
- In XLSX, the same values are real date/time cells shown in those
  formats, so they sort and filter as dates.

**Filename.** `invitations-<status|all>-<YYYY-MM-DD>.<csv|xlsx>`, where the
status uses hyphens (`invitations-checked-in-2026-10-14.xlsx`) and the date
is in the visit timezone. Browsers on the web portal cannot read this
header across origins, so the portal names the download itself.

**XLSX layout.** The header row is bold, frozen and auto-filtered, and every
column has a preset width.

**What is never exported.** ID-proof documents, photos, storage keys and
signed URLs — whatever the caller's `documents:view` grant. Only the
ID-proof *type* is included.

**Formula-injection guard.**

- **CSV:** any value starting with `=`, `+`, `-`, `@`, a tab or a carriage
  return is prefixed with `'`, so a spreadsheet shows it as text instead of
  evaluating it. Phone numbers stored as `+91…` therefore appear as
  `'+91…` in CSV.
- **XLSX:** every text value is stored as a text cell, which is never
  evaluated, so values keep their original form, for example `+91…`. Use
  XLSX when the file is for reading in a spreadsheet.

**Size cap.** An export larger than `INVITATION_EXPORT_MAX_ROWS` visitor
rows (default 10,000) is rejected with 422 and a message to narrow the
filters. The file is never silently truncated.

**Auditing.** Every successful export writes an `invitations_exported`
audit entry with the actor, the filters, the format and the row count — no
visitor data. Rejected exports are not audited as exports.

## Relevant to me

`GET /invitations?relevantToMe=true` is a personal worklist, not a narrower
branch scope: it returns invitations where the caller is either the
invitation's currently resolved host (`hostId` — set once any step has
been delegated to them, see `docs/features/approvals.md`), has been
delegated one of that invitation's approval steps (`docs/features/
approvals.md`'s "Delegation"), currently holds the role that the
invitation's current pending step names *and that step has no delegate
assigned yet*, has personally approved/rejected any of that invitation's
steps, or currently holds the tenant's default host role (e.g. Reception) —
regardless of that step's or the invitation's current status for all but
the plain role clause.

**BREAKING (harden-approval-gate-and-narrow-delegate-visibility)**: the
plain role clause used to deliberately *not* require the step to be
undelegated — every holder of the role kept seeing the invitation even
after it was delegated to someone else. That is reversed: once a
role-identified step (at any `stepOrder`) is delegated to a specific
person, every other holder of that role stops seeing the invitation via
this clause — only the delegate, the resolved host, or someone who
personally acted on a step still sees it. The one exception is the
tenant's default host role (Reception): every holder of that role keeps
*permanent* visibility into every invitation regardless of delegation or
status, via its own clause, since that role owns front-office intake for
an invitation's entire lifecycle. The person who actually acted on a step
also keeps seeing the invitation forever, via the "personally
approved/rejected" clause: e.g. an individual Reception user who approved
the ownership step keeps it in their list through every later step and
past final approval/denial — and that same "I acted on the step before
this one" fact also lets them delegate the *next* step straight to whoever
the workflow configures for it, without needing to hold that step's role
themselves (see `docs/features/approvals.md`'s "Delegation").

This deliberately **bypasses** `invitations:view` and `X-Branch-ID`
entirely — a host or delegate with no branch-level view permission still
needs to see and act on their own invitation, so this is a distinct query
path from the branch-scoped mode above, not a variant of it. `X-Branch-ID`
is ignored (not rejected, not narrowing) when `relevantToMe=true` is set.
It composes with `status`/`registrationType`/`source` and with
pagination/sorting exactly like the branch-scoped mode. A caller who is
neither host nor delegate on any invitation gets an empty, successfully
paginated result, not an error.

## Who can see an invitation

**BREAKING (restrict-delegated-invitation-visibility)**: once Reception
delegates a request to one person, only Reception and that person (plus
anyone who already acted on it) should see it and its details.

- **`invitations:view-all`** — "see every invitation at this branch". Seeded
  for `admin`, `reception` and `security`; **not** `host`. Gates the
  branch-scoped `GET /invitations`, the non-participant path of
  `GET /invitations/{id}`, and `/admin/dashboard/*`.
- **`invitations:view`** — kept by `host`; on its own it no longer grants any
  branch-wide read. It only decides 404 vs 403 for a non-participant on the
  detail endpoint.
- **Participant** — the `relevantToMe` rule above. `GET /invitations/{id}`
  serves the detail to a participant even with no permission at all (e.g. a
  delegate).
- **Delegation-only roles** (`auth/rbac_catalog.py::DELEGATION_ONLY_ROLE_NAMES`,
  i.e. `host`): the "holds the current step's role" clause never matches
  their steps. An unassigned `host` step — e.g. after Reception's delegate
  approves step 0, or between the two calls behind the portal's "Approve &
  Delegate" — is no longer shown to every host, matching the existing rule
  that no host can act on or be notified about it until it's delegated.

**Deploy:** existing tenants need `scripts/upgrade_all_tenants.py` (tenant
migration `d4e6f8a0b2c3` grants `invitations:view-all` to every role that
held `invitations:view` except `host`, including custom roles; then
`seed_default_roles`). Until it runs, Reception/Security/Admin get 403 on the
branch listing and dashboard; the prestart drift check warns about the
lagging tenant.

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
  date-only (calendar day in the visit timezone — see "Expiry is the end of
  the visit day" below), so a scan
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

**Every email is a branded Visimio HTML template**
(`role-based-invitation-workflow`, restyled by
`redesign-notification-email-templates` and
`refine-email-templates-and-visimio-brand`). `core/email_rendering.py::render_email`
renders a pair of templates per notification type from
`core/email_templates/`. `<type>.html` extends `base.html`, and `<type>.txt`
extends `base.txt`. The result is a `RenderedEmail(subject, html, text)`,
sent as a `multipart/alternative` message
(`core/emailing.py::SmtpEmailSender`). The subject is always the template's
`heading` block. If a template fails to render for any reason, including a
filter receiving an unexpected value type, the failure is logged at
`ERROR` and the task sends a minimal plain-text email (tracking ID plus
"look it up") instead of failing the dispatch. The SMS path sends its own
short one-line `sms_body`, never the email text. See
`docs/features/notifications.md` "Notification emails" for the layout,
the per-type content, and the name and date rules.

The approval email includes the full visit detail: date/time, **place of
visit** (building · branch · address, resolved through
`InvitationRepository.get_location`), department, duration and purpose. It
always shows a point-of-contact block, filled in this order: the
invitation's POC, the resolved host, the branch's contact person, the front
desk (branch contact, falling back to the Company contact), then "Reception
at {branch}" (`serve-email-images-by-url-and-complete-contact`).

**The check-in QR is loaded by URL, never attached.** It appears in a "Your
check-in pass" block whose image is the signed
`/api/v1/public/email-assets/{tenantId}/qr/{invitationId}.png` URL (see the
endpoint table), so the message carries no image part at all. Only when
`EMAIL_ASSET_BASE_URL` is unset does it fall back to an inline
`cid:visit-qr@vmss` part. A **reschedule of an approved invitation** shows
the same QR, reading the persisted token through
`InvitationRepository.get_qr_code`, with a fresh `exp` for the new expiry.
A reschedule of a still-`submitted` invitation, and every edit email,
carries no QR. The edit email says the existing pass is still valid when
approved, and says a pass will follow on approval otherwise.

Submission (every non-auto-approved invitation now snapshots at least one
step) approval, denial, reschedule, edit, check-in, and check-out each also
dispatch a **staff-facing push notification** — additional to, and
dispatched independently from, the visitor email/SMS above. Submission reads
back the invitation's own just-created current step
(`InvitationApprovalStepRepository.get_current_pending`) and pushes every
holder of *that step's* `approverRoleId` at the branch
(role-based-invitation-workflow — previously the host, when one had been
supplied) — this is the category's own configured first-level role when the
category has active rules, or the tenant's default host role only when it
doesn't (see `docs/features/approvals.md` "The host-nomination step"); the
other actions push the invitation's resolved host, if one has been
delegated. See `docs/features/notifications.md` for the dispatch primitive,
the `assignedRoleId`/`assignedUserId`/`reason` addressing metadata every
payload now carries, and recipient-resolution rules.

**Current-step-role email fan-out** (`role-based-invitation-workflow`,
replaces the old "host creation email"): submission also enqueues
`send_submission_role_email_notification` with that same current step's
`approverRoleId`, emailing every active user holding that role at the
branch — the email counterpart of the submission push above, additive to
it, not a replacement. **Host-assignment email**: `approvals`'
`delegate_step`, when delegating the host-nomination step, additionally
enqueues `send_host_creation_notification` (same task as before, repurposed
— see `docs/features/approvals.md`) to the newly resolved host, telling
them they've been named host. Neither of these existed before this change
fired anything at creation for an un-resolved host; both are asynchronous
and never delay their triggering request.

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
| `INVITATION_MAX_UPLOAD_SIZE_BYTES` | `5242880` (5 MB) | Max ID-proof file size. |
| `INVITATION_MAX_GROUP_VISITORS` | `20` | Cap on co-visitors in one group submission. |
| `INVITATION_MAX_PHOTO_SIZE_BYTES` | `2097152` (2 MB) | Max optional profile-photo file size — independent of the ID-proof limit above. |
| `INVITATION_EXPORT_MAX_ROWS` | `10000` | Max visitor rows per `GET /invitations/export`; an over-cap export is rejected with 422, never truncated. |
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
