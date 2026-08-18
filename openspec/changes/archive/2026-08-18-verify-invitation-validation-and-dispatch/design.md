## Context

See `proposal.md` - Why for the three investigated findings this design
responds to. Relevant existing pieces:

- `invitations/router.py::_PAYLOAD_DESCRIPTION` (built by
  `document-invitation-create-payload-shape`) already embeds both example
  payloads in the `payload` Form field's description — the one channel
  confirmed to render in Swagger's Parameters table regardless of content
  type. This design extends that same string, not a new mechanism.
- `invitations/tasks.py::send_visit_confirmation`/`_send_visit_confirmation`
  already generates a QR (`qr.py::generate_qr_png`) and calls
  `notifications.email_sender.send(...)` with the attachment. The existing
  tests (`test_send_visit_confirmation_skips_when_invitation_missing`,
  `..._exhausted_retries_logs_error`) stub `email_sender` with recording/
  failing fakes — neither exercises the real `SmtpEmailSender` or checks an
  attachment actually arrives anywhere.
- `core/config.py`'s `smtp_host`/`smtp_port` default to `"localhost"`/`1025`
  — DDEV's built-in mail interception captures outbound SMTP on that port
  from inside the `web` container regardless of destination, redirecting it
  to Mailpit. Confirmed reachable at `http://localhost:8025/api/v1/messages`
  from inside the container during this session's investigation.

## Goals / Non-Goals

**Goals:**
- Make mandatory-vs-optional fields for `POST /invitations`'s payload
  discoverable from Swagger without depending on OpenAPI machinery this
  session already found isn't exposed for this endpoint.
- Close the validation-completeness test gaps identified by comparing
  existing tests against every validator in `schemas.py`.
- Prove, with a real test (not a mock), that a confirmation email with a
  valid QR attachment is actually deliverable — using infrastructure
  (Mailpit) already running in this environment.

**Non-Goals:**
- Changing any validation rule — every gap found is a missing *test*, not
  missing *validation*. `schemas.py` already rejects everything the new
  tests assert; see proposal.md's investigation.
- Exposing `InvitationCreate`'s JSON Schema to OpenAPI tooling via
  `contentSchema`/`contentMediaType` (Decision 1 below) — considered and set
  aside for this change.
- Decoding the generated QR code back to its payload text (proposal.md
  Impact — no QR-decode dependency exists in this project, and a valid PNG
  is proportionate evidence for what was asked).
- Adding a ddev command or Procfile entry to launch a Celery worker
  automatically — a docs note that one isn't running by default and how to
  start one manually covers the immediate need without adding new
  developer-experience surface nobody asked for yet.

## Decisions

### Decision 1: Document required fields as generated text in `description`, not via OpenAPI `contentSchema`

**Considered**: OpenAPI 3.1's `contentSchema`/`contentMediaType` vocabulary
(FastAPI 0.141 emits OpenAPI 3.1) is the schema-native way to say "this
string property contains JSON matching this schema," and would make
`InvitationCreate` appear in `components.schemas` for any tool that reads
it. Implementing it means either post-processing `app.openapi_schema` after
generation (no existing `custom_openapi` override in `main.py` to hang this
off of yet) or getting `openapi_extra` to deep-merge a `contentSchema` onto
the auto-generated `Body_create_invitation_...` `$ref`'d schema — untested
against this project's installed FastAPI/Pydantic versions the way the
`examples` mechanism was verified in the earlier change's design.md, and
carrying real risk of silently breaking the existing (working, tested)
`primary_contact_id_proof_file`/`visitor_id_proof_files` properties if the
merge doesn't behave as expected.

**Chosen instead**: build the required/optional summary as plain text,
generated from `InvitationCreate.model_json_schema()["required"]` and each
nested model's own `required` list (not hand-typed, so it can't silently
drift — Decision 2 below is the test that enforces this), and append it to
the already-proven-reliable `_PAYLOAD_DESCRIPTION` string. Lower-risk,
reuses a mechanism this session already verified renders, and doesn't touch
the working multipart schema generation at all.

**Alternative not pursued further**: the `contentSchema` approach remains
available as a follow-up if a future need (e.g. client code generation from
`/openapi.json`) specifically requires machine-readable typing for this
field — flagged as an Open Question below rather than silently dropped.

### Decision 2: Generate the description's required-field text from the schemas, assert it in a test — don't hand-type it twice

`invitations/router.py` builds the required/optional summary by calling
`.model_json_schema()["required"]` on each relevant model at import time
(same place `_PAYLOAD_DESCRIPTION` is already built), so the text is always
in sync with the actual validators. The new test
(`test_invitation_payload_description_matches_schema_requirements`)
independently recomputes the same `required` lists and asserts the
description contains every one of them — this is a second, redundant check
by design: if a future refactor changes how the description is built
without also changing what it lists, this test still catches drift because
it doesn't trust the same code path that builds the string.

**Alternative considered**: hand-write the required-field list as prose and
trust a human to keep it updated. Rejected — this is exactly the kind of
"looked right once" documentation this project's `testing-standards.md`
already pushes back on elsewhere.

### Decision 3: Prove email+QR delivery through Mailpit's own HTTP API, not by asserting the fake sender was called

The new test calls `tasks.send_visit_confirmation.apply(...)` (Celery eager
mode, same pattern as the existing task tests) with `notifications.
email_sender` left as the real `SmtpEmailSender` (not monkeypatched), so a
real `aiosmtplib.send(...)` call goes out over the loopback SMTP port DDEV
intercepts. The test then polls `GET http://localhost:8025/api/v1/messages`
(Mailpit's API, confirmed reachable from inside the `web` container this
session) for a message matching the invitation's `tracking_id` in the
subject/body, and asserts it has exactly one attachment with
`Content-Type: image/png` that Pillow can open and verify as a real PNG.

**Why this, not a mocked assertion**: the existing tests already prove the
task *calls* the sender correctly in isolation; they don't prove the
message is actually deliverable end-to-end (the exact gap the user pointed
at — "check whether the email has been sent to mailpit"). This mirrors
`testing-standards.md`'s existing bias toward real infrastructure over
mocks (real Postgres, not SQLite) applied to the one other piece of
real infrastructure this feature depends on.

**Risk accepted**: this test depends on Mailpit being reachable at a fixed
local URL, which is true in this DDEV-based dev/CI setup but would need
adjusting if the project's test environment changes (e.g. a different mail
catcher, a different port). Scoped as a plain module-level constant
(`_MAILPIT_API_URL`) in the test file specifically so that one line is the
only thing to change if this environment assumption is ever wrong, rather
than embedding the URL inline at each use site.

**Alternative considered**: skip this test with a `pytest.mark.skipif` when
Mailpit isn't reachable (e.g. in a CI environment without DDEV). Deferred as
an implementation-time decision — `project-rules.md` mandates `ddev exec uv
run pytest` as the one documented way to run this suite, and DDEV always
provides Mailpit, so a skip guard may prove unnecessary; add one only if
running the suite without DDEV turns out to be a real, supported path.

## Risks / Trade-offs

- **[Risk]** The Mailpit-backed test is slower and has more moving parts
  (real network I/O to a sibling container) than the rest of this file's
  otherwise-fast Celery-eager tests. → **Mitigation**: accepted — one test,
  proportionate to directly verifying the exact thing that was asked about,
  consistent with this project's existing tolerance for real-Postgres test
  latency over mocked speed.
- **[Trade-off]** `contentSchema`-based OpenAPI exposure (Decision 1) is not
  delivered by this change, so a non-Swagger OpenAPI consumer (a code
  generator, a contract-testing tool) still can't see `InvitationCreate`'s
  shape structurally. → Accepted per Decision 1's risk/reward reasoning;
  flagged as an Open Question, not silently dropped.

## Migration Plan

- No schema/migration change. No new dependencies. No `.env`/settings
  changes.
- Deploy is a plain code/test/docs change: `router.py`'s description string,
  new tests in `tests.py`, a docs note.

## Open Questions

- Whether `InvitationCreate` should eventually be exposed to OpenAPI
  tooling via `contentSchema` (Decision 1) — doesn't change this change's
  specs, approach, or task breakdown; a future change can revisit this
  independently if a concrete consumer needs it (e.g. a generated API
  client).
- Whether the Mailpit-backed test needs a `skipif` guard for a future
  non-DDEV test environment (Decision 3) — resolve at implementation time
  if that environment turns out to exist; today's only documented test
  command already guarantees DDEV/Mailpit are present.
