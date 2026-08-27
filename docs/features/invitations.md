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
| POST | `/api/v1/invitations` | `invitations:create` at the resolved branch | — | An employee creates a fully completed single or group invitation in one call: primary contact, co-visitors, visit details, carried items, vehicles, and consent, each visitor (including the primary contact) with their own ID-proof upload. Multipart: a JSON `payload` part (camelCased fields, matching `InvitationCreate`) plus `primary_contact_id_proof_file`/`visitor_id_proof_files` file parts — multipart field *names* are the literal Python parameter names, not camelCased, since they aren't part of a JSON body. Returns a tracking ID with the invitation's status resolved from `Company.autoApprovePreRegisteredVisitors` — `approved` immediately, or `submitted` (awaiting approval) — see "Auto-approve vs. manual approval" below. Accepts an optional `Idempotency-Key` header (`api-conventions.md` §3) — a retried request with the same key and tenant returns the original response instead of creating a second invitation. See "Finding the payload shape in Swagger" below for where to actually see the `individual`/`group` JSON examples in `/docs`. |
| POST | `/api/v1/invitations/{id}/approve` | `invitations:approve` at the invitation's branch | — | Transitions a `submitted` invitation to `approved` and dispatches the QR-bearing approval notification at that point. 409 if the invitation isn't currently `submitted`; 404 for an unknown id; 403 (not 404) if the caller lacks branch access to an invitation that does exist — see "Auto-approve vs. manual approval" below. |

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
change an already-created invitation's status. Only the per-visitor-category
`ApprovalWorkflowRule` multi-step engine (`visitors/` — config CRUD only,
no runtime evaluation yet) is unaffected; this flow uses only the
company-wide flag.

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

Each row is an `InvitationListItemOut` — tracking ID, registration type,
source, status, primary contact name, purpose of visit, and expiry/submission
timestamps — deliberately narrower than `InvitationTrackingOut`: it carries
no per-visitor/vehicle detail, so the underlying query never needs to
eager-load either child collection for a list view that doesn't render them
(`query-performance.md` §1).

## The tracking ID is a plain, human-readable identifier

`GET /invitations/track` has no bearer token and no tenant identifier at all
to resolve from — a caller who lost their tracking ID is exactly who needs
it — so it resolves the single configured `settings.default_tenant_slug`
tenant (`invitations/deps.py::track_default_tenant_db`). This is a known
limitation once a second tenant exists: a real multi-tenant deployment would
resolve this from the request's hostname/subdomain, which nothing in this
codebase does yet. There is no signed token anywhere in this feature
anymore — the confirmation QR code encodes the plain `tracking_id`, since
there is no unauthenticated write endpoint left that needed a signed token
to resolve tenancy.

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
(tracking ID + QR code — sent for an `approved` invitation) or
`send_tracking_notification` (tracking ID only, no QR — sent for a
`submitted` one). See "Auto-approve vs. manual approval" above for which
one a given creation/approval triggers. Both tasks resolve their own
tenant-bound session from a `tenant_schema` argument, skip if the
invitation row is no longer found (redelivery after removal), and declare
`autoretry_for`/`retry_backoff`/`max_retries`, logging at `ERROR` with full
context if retries are exhausted. Email goes out over SMTP
(`invitations/notifications.py::SmtpEmailSender`); SMS has no gateway wired up
yet (`UnconfiguredSmsSender` raises loudly rather than pretending to send —
this is a known open item, not an oversight).

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
| `MAIL_HOST`/`MAIL_PORT`/`MAIL_USERNAME`/`MAIL_PASSWORD`/`MAIL_USE_TLS`/`MAIL_FROM_ADDRESS` | local dev mail-catcher | Outbound email for visit confirmations. See `docs/features/configuration.md`. |
| `SMS_GATEWAY_BASE_URL`/`SMS_GATEWAY_API_KEY`/`SMS_FROM_NUMBER` | unset | Placeholders — no SMS gateway has been chosen yet. |

## Not yet built (flagged, not silently dropped)

- **Cancel/reschedule an invitation.** The product spec's Employee Features
  list these, but they weren't part of this feature's scope — meaningful
  cancel/reschedule needs a check-in state machine to interact with, which
  doesn't exist yet. `invitations:cancel` is already seeded into the
  permission catalog for when that lands.
- **Recurring invitations.** One-off single/group invitations only.
- **Reject/decline a submitted invitation.** `POST /invitations/{id}/approve`
  exists; there is no corresponding reject action yet — explicitly out of
  scope for `add-invitation-approval-flow-and-role-resync`.
- **Per-visitor-category, multi-step approval workflow evaluation.**
  `ApprovalWorkflowRule` (`visitors/`) is still config CRUD only — nothing
  evaluates it against an invitation. The auto-approve/manual-approve flow
  above uses only the tenant-wide `Company.autoApprovePreRegisteredVisitors`
  flag, not this per-category rule chain; wiring the two together is a
  separate, larger effort.
- **SMS gateway integration.** See the config table above.

**Visitor-authored registration** — removed along with API-10 as a *remote*
self-service flow, but reintroduced as an *on-site* one: a visitor arriving
without a prior invitation now registers themselves via `POST
/registrations/walk-in` (API-13, `docs/features/registrations.md`),
authenticated by a branch's device credential rather than a staff bearer
token. It reuses this feature's exact `InvitationCreate` contract and writes
to the same `Invitation` table, tagged `source: "visitor_walk_in"` instead of
`"staff_pre_registration"`.
