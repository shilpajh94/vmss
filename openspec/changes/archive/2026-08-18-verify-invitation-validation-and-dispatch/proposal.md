## Why

The user asked for "proper validation checks" on the pre-registration API,
mandatory fields to be clearly marked, and confirmation — proven by test
cases, not manual inspection — that invitation-confirmation email actually
reaches Mailpit and that a QR code is actually generated on submission.

Three concrete things were confirmed by direct investigation, not assumed:

1. **`InvitationCreate`'s JSON schema is completely absent from the OpenAPI
   document.** `payload` is a bare `Form(str)` (multipart has no native way
   to carry a nested object), so FastAPI never registers `InvitationCreate`
   or any of its nested schemas (`VisitorSubmit`, `VisitDetailsSubmit`, etc.)
   in `components.schemas` — confirmed by listing every schema FastAPI
   actually emits. There is nothing there for a "mandatory fields" list to
   come from, for any OpenAPI-reading tool, today. Separately,
   `InvitationCreate.model_json_schema()` (Pydantic, not exposed via
   OpenAPI) already gets required-vs-optional exactly right — e.g.
   `InvitationPrimaryContactCreate` requires `fullName`/`idProofType`;
   `email`/`phone` are correctly optional at the schema level, since "at
   least one of the two" is a cross-field business rule a JSON Schema
   `required` list can't express, and is already enforced by a
   `model_validator`. So this is a **documentation gap**, not a validation
   gap — the validation is already correct.
2. **No Celery worker is running in this dev environment.** Checked running
   processes directly — none. `send_visit_confirmation.delay(...)` queues
   into Redis exactly as designed, but nothing consumes it. A manual
   "create an invitation and watch Mailpit" check would see nothing arrive
   today, for an environment reason unrelated to the dispatch code's
   correctness.
3. **Mailpit is live and reachable.** DDEV's built-in mail catcher is
   running and its HTTP API (`http://localhost:8025/api/v1/messages`,
   reachable from inside the `web` container) responds. This makes a real,
   non-mocked integration test — send through actual SMTP, then query
   Mailpit's API for the message — genuinely possible here, consistent with
   this project's existing "real Postgres, no mocks" testing philosophy
   (`testing-standards.md`).

## What Changes

- Extend the `payload` Form field's description (already fixed for example
  visibility by `document-invitation-create-payload-shape`) with an explicit
  required/optional field summary per nested object, generated from each
  schema's own `model_json_schema()["required"]` rather than hand-typed, so
  it can't silently drift from the actual validators as fields change.
- Add the validation-completeness tests this capability doesn't have yet:
  a request missing `registrationType`/`primaryContact`/`visitDetails`/
  `consents` entirely is rejected with 422; an invalid enum value for
  `idProofType`/`vehicleType`/a carried-item category is rejected with 422;
  a vehicle missing `licensePlate` or a visitor missing `fullName` is
  rejected with 422. Plus one test asserting each nested schema's own
  `required` list matches what the description text claims, so a future
  field addition that updates one but not the other fails CI.
- Add a real (non-mocked) test that runs `send_visit_confirmation` via
  Celery's eager `.apply()` (same mechanism the existing task tests already
  use) with the actual `SmtpEmailSender`, sends through real SMTP to this
  project's dev Mailpit instance, then queries Mailpit's HTTP API to confirm
  a message arrived addressed to the invitation's primary contact with the
  expected subject and a PNG attachment — proving the email-to-Mailpit path
  end to end instead of only asserting a fake sender was called.
- The same test verifies the attachment is a valid PNG (opens and verifies
  via Pillow, confirms format `"PNG"`) — proving a real QR image was
  generated and actually attached. Decoding the QR's payload back to the
  tracking ID is **out of scope** (would need a new dependency this project
  doesn't currently have; a valid, correctly-typed image is proportionate
  evidence "a QR was generated" for what was asked).
- `docs/features/invitations.md` gains a short note on how to start a local
  Celery worker for manual end-to-end testing (`ddev exec uv run celery -A
  vmss_api.core.celery_app worker`) and where Mailpit's UI lives — since one
  isn't running by default today, and there's currently no documented way to
  start one.
- **No behavior change to request validation, dispatch logic, or QR
  generation** — everything audited here was already correct; this closes
  documentation and test-coverage gaps around it.

## Capabilities

### New Capabilities
- `invitations`: adds requirements to the same not-yet-baselined
  `invitations` capability this session's other invitations changes have
  been building toward (see the still-open spec-reconciliation note from
  earlier in this session) — one requirement about the payload's
  self-documented required/optional fields, one about dispatch being
  verified against a real mail catcher.

### Modified Capabilities
(none — no existing requirement's behavior changes)

## Impact

- **Code**: `src/vmss_api/invitations/router.py` (`_PAYLOAD_DESCRIPTION`
  only — no signature/logic change).
- **Tests**: `src/vmss_api/invitations/tests.py` — new validation-gap tests,
  a schema-vs-description consistency test, and a new real-Mailpit
  integration test for `send_visit_confirmation`.
- **Docs**: `docs/features/invitations.md` — a short "running the worker
  locally" note.
- **No breaking changes.** No new dependencies. No `.env`/settings changes.
- **Out of scope**: exposing `InvitationCreate`'s JSON Schema to OpenAPI
  tooling itself (e.g. via OpenAPI 3.1 `contentSchema`) — investigated as an
  alternative to the description-text approach and set aside; see design.md
  Decision 1 for why. Also out of scope: a new ddev command to launch the
  Celery worker (a doc note covers the immediate "how do I check this"
  need; a dedicated command is a separate, smaller follow-up if wanted).
