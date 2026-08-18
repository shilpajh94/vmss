## Context

See `proposal.md` - Why for the full trace: `POST /invitations`'s `payload`
form field already has correct `openapi_extra`-based `examples` (moved onto
this route by `merge-invitation-registration-into-creation`, originally built
by the now-archived `document-self-registration-multipart-payload` for the
earlier `/register` endpoint), proven by a schema-level test. The user is
still reporting they can't find the shape in Swagger UI. This design exists
to resolve that apparent contradiction and land a fix that's actually visible
on this project's real `/docs` page, not just in `app.openapi()`'s output.

## Goals / Non-Goals

**Goals:**
- Make the `individual`/`group` JSON shape for `POST /invitations`'s
  `payload` field readable directly from Swagger's Parameters table, with no
  dependency on whether the rendering surface applies multipart
  `requestBody.examples`.
- Keep the fix provable by an automated schema assertion, consistent with
  this project's established pattern for this class of gap
  (`api-documentation.md` §1).

**Non-Goals:**
- Removing or replacing the existing `openapi_extra` examples — they're
  correct OpenAPI metadata, useful to tools that do support multipart
  examples (Redoc, non-Swagger-UI consumers, a future Swagger UI release).
  This design adds a second, more reliable channel; it doesn't replace the
  first.
- Redesigning the endpoint to avoid a JSON-encoded `payload` string entirely
  (e.g. flattening every nested field into its own `Form()` parameter).
  Multipart/form-data has no native representation for a list of nested
  objects (`visitors[]`, `vehicles[]`) without either this JSON-string
  encoding or a much more invasive per-index-flattened field scheme; the
  JSON-string shape was already deliberately chosen and re-confirmed correct
  twice over in this session's prior work. Not reopened here.
- Verifying this in an actual rendered browser session — no browser
  automation tool is available in this environment. The fix is designed
  around a rendering behavior (Form/File parameter descriptions render;
  operation-level multipart examples are the specific piece in question)
  that this session's earlier change already confirmed renders correctly
  (task 2.2), so it does not depend on the uncertain part.

## Decisions

### Decision 1: Put the example JSON in the field's own `description`, not (only) in `openapi_extra`

**Root cause of the reported symptom**: Swagger UI (`swagger-ui-dist@5`,
loaded via CDN in `fastapi/openapi/docs.py` — this project's default,
`api-documentation.md` §3) builds its "Try it out" form for a
`multipart/form-data` request body by rendering one input widget per property
in the body's combined schema (`payload`: a text box, `primary_contact_id_
proof_file`: a file picker, etc.). This per-property rendering path does not
consult `requestBody.content['multipart/form-data'].examples` at all — that
map is Swagger UI's mechanism for *whole-body* examples on JSON-typed
content, where the UI can just paste one example object into a single JSON
textarea. There's no equivalent "paste this whole example into these five
separate widgets" behavior for multipart bodies. This is a form-data-specific
gap in Swagger UI itself, not a bug in this project's OpenAPI output — the
raw schema is correct (confirmed by the existing regression test), and a
tool that reads the schema directly (or a future Swagger UI version that
adds multipart-example support) would already show it correctly today.

Since this project cannot change what Swagger UI supports, the fix has to
route the information through a channel Swagger UI *does* render for a
multipart body: each Form/File parameter's own `description` text, which
renders in the Parameters table unconditionally — no "Try it out" click
required, no dependency on content-type-specific example handling. This was
already confirmed working for this exact field's shorter description in the
prior change (task 2.2), so extending that same description with the full
example JSON (fenced/formatted as literal text) is the one option verified
not to depend on the part of Swagger UI's behavior in question.

**Alternative considered**: OpenAPI 3.1's `contentSchema`/`contentMediaType`
vocabulary (FastAPI 0.141 emits OpenAPI 3.1 by default), which is the
"correct," schema-native way to say "this string field contains JSON matching
this schema." Rejected as the primary fix, not as wrong — `swagger-ui-dist@5`
support for rendering `contentSchema` on a multipart string property is
inconsistent across UI versions and not something this project pins or
controls (the CDN URL floats on `@5`), so relying on it alone would leave the
same "works in the raw schema, unverified whether it renders" gap this change
exists to close. Not added alongside the description fix either — two
overlapping documentation mechanisms for the same field raises the
maintenance surface (two places to keep in sync with any future field change)
for a benefit this project has no way to confirm it gets today.

**Alternative considered**: drop the `openapi_extra` examples entirely and
replace them with the description-embedded JSON. Rejected — they're correct,
already tested, and free to keep; removing correct metadata to work around a
renderer's limitation would be over-correcting, not fixing the actual gap.

### Decision 2: Prove it by parsing the embedded JSON back out of the schema, not by asserting exact text

The new test extracts the `individual`/`group` JSON blocks embedded in the
`payload` parameter's `description` string and parses each with
`InvitationCreate.model_validate_json(...)`, asserting `registration_type`
matches. This mirrors the existing `openapi_extra` example test's approach
(parse-and-validate, not string-equality) so the test survives cosmetic
rewording of the surrounding description prose and only fails on an actual
content/shape regression — consistent with this project's established
pattern for this exact kind of assertion.

**Alternative considered**: assert the description contains specific
substrings (e.g. `"registrationType"`). Rejected — a substring check can't
catch a malformed or stale JSON example the way parsing it as
`InvitationCreate` can.

## Risks / Trade-offs

- **[Risk]** This design's root-cause diagnosis (Swagger UI not applying
  multipart examples) is based on this project's/Swagger UI's documented
  architecture, not a live browser reproduction in this environment (no
  browser automation tool available here). → **Mitigation**: the fix does
  not depend on this diagnosis being the *only* cause — embedding the
  example in `description` is a strict improvement over the current state
  regardless of why the previous fix wasn't visible, since `description`
  text is confirmed to render unconditionally. If the user's environment
  turns out to have a different underlying issue (e.g. a cached `/docs`
  page, a different pinned Swagger UI version), this change still makes the
  information visible without depending on that other issue being found.
- **[Trade-off]** The `payload` parameter's description becomes
  significantly longer (two full JSON examples inline). Accepted — a longer,
  actually-useful description is a better trade than a short one a caller
  can't act on; this mirrors the same trade-off already accepted for
  `openapi_extra`'s examples, just moved to a channel that reliably renders.

## Migration Plan

- No schema/migration change — this is OpenAPI parameter-description text
  only, no DB or Pydantic validation change.
- No `.env`/settings changes. No new dependencies.
- Deploy is a plain code change to `router.py`'s parameter declarations plus
  a new test and a docs note — nothing else to sequence.
