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
| POST | `/api/v1/invitations` | `invitations:create` at `X-Branch-ID` | — | An employee creates a fully completed single or group invitation in one call: primary contact, co-visitors, visit details, carried items, vehicles, and consent, each visitor (including the primary contact) with their own ID-proof upload. Multipart: a JSON `payload` part (camelCased fields, matching `InvitationCreate`) plus `primary_contact_id_proof_file`/`visitor_id_proof_files` file parts — multipart field *names* are the literal Python parameter names, not camelCased, since they aren't part of a JSON body. Returns a tracking ID with the invitation already `status: submitted` — there is no follow-up step. Accepts an optional `Idempotency-Key` header (`api-conventions.md` §3) — a retried request with the same key and tenant returns the original response instead of creating a second invitation. See "Finding the payload shape in Swagger" below for where to actually see the `individual`/`group` JSON examples in `/docs`. |
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

Invitation creation dispatches a single visit-confirmation notification
(email/SMS + QR code) via Celery (`invitations/tasks.py::send_visit_confirmation`),
never inline in the request path (`background-jobs.md` §5). The task
resolves its own tenant-bound session from a `tenant_schema` argument, skips
if the invitation row is no longer found (redelivery after removal), and
declares `autoretry_for`/`retry_backoff`/`max_retries`, logging at `ERROR`
with full context if retries are exhausted. Email goes out over SMTP
(`invitations/notifications.py::SmtpEmailSender`); SMS has no gateway wired up
yet (`UnconfiguredSmsSender` raises loudly rather than pretending to send —
this is a known open item, not an oversight).

**No Celery worker runs by default in this DDEV dev environment** — a
created invitation's confirmation task will sit queued in Redis until
something consumes it. To manually verify dispatch outside the automated
test suite (`invitations/tests.py::test_send_visit_confirmation_delivers_email_with_qr_via_mailpit`
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
save/`url_for` interface, local-disk-backed in dev; swapping to S3-compatible
object storage in prod is a new implementation behind the same two functions.

## Config knobs

| Setting | Default | Purpose |
|---|---|---|
| `INVITATION_TOKEN_TTL_HOURS` | `168` (7 days) | How long a created invitation's tracking record stays within its validity window. |
| `INVITATION_MAX_UPLOAD_SIZE_BYTES` | `5242880` (5 MB) | Max ID-proof file size. |
| `INVITATION_MAX_GROUP_VISITORS` | `20` | Cap on co-visitors in one group submission. |
| `STORAGE_ROOT` | `./var/storage` | Local-disk root for uploaded files in dev. |
| `SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_USE_TLS`/`SMTP_FROM_ADDRESS` | local dev mail-catcher | Outbound email for visit confirmations. |
| `SMS_GATEWAY_BASE_URL`/`SMS_GATEWAY_API_KEY`/`SMS_FROM_NUMBER` | unset | Placeholders — no SMS gateway has been chosen yet. |

## Not yet built (flagged, not silently dropped)

- **Cancel/reschedule an invitation.** The product spec's Employee Features
  list these, but they weren't part of this feature's scope — meaningful
  cancel/reschedule needs a check-in state machine to interact with, which
  doesn't exist yet. `invitations:cancel` is already seeded into the
  permission catalog for when that lands.
- **Recurring invitations.** One-off single/group invitations only.
- **Approval workflow evaluation.** A submitted invitation is stored as
  `submitted`; nothing here evaluates `ApprovalWorkflowRule`s against it —
  that's the not-yet-built `approvals` feature's job.
- **SMS gateway integration.** See the config table above.
- **Visitor-authored consent/self-service upload.** Removed along with API-10;
  a future requirement for the visitor to supply their own ID proof remotely
  is a new change, not a variant of this one.
