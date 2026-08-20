## Why

The user re-tested `POST /api/v1/invitations` in Swagger UI (`/docs`) and reported
it's "showing only this much" — a screenshot of the `payload`/
`primary_contact_id_proof_file`/`visitor_id_proof_files` parameter list with no
visible trace of the nested `registrationType`, `primaryContact`, `visitors`,
`visitDetails`, `carriedItems`, `vehicles`, `consents` shape their own
`register-type-group.txt`/`register-type-individual.txt` payloads use — even
though `service.py`/`schemas.py` already accept exactly that shape (confirmed
again in this session's earlier work: 174/174 tests pass, and `app.openapi()`
already carries `individual`/`group` examples for this exact route).

The previous fix for this class of problem (the now-archived
`document-self-registration-multipart-payload` change, built for the earlier
`/register` endpoint and carried over onto `/invitations` by this session's
`merge-invitation-registration-into-creation`) added the examples via
`openapi_extra` on the route decorator and proved them with a schema-level
test (`app.openapi()` contains the `examples` map). That test still passes
today — but it only proves the *raw OpenAPI document* carries the examples,
not that Swagger UI's rendered page does anything with them. Swagger UI
(`swagger-ui-dist@5`, loaded from the CDN in `fastapi/openapi/docs.py`, this
project's default per `api-documentation.md` §3) is well known to only apply
`requestBody.content[...].examples` to pre-fill the "Try it out" form for
JSON-typed bodies; for `multipart/form-data` it renders one input widget per
schema property from the combined body model and does not consult the
operation-level `examples` map at all. That is exactly the gap between "the
schema test passes" and "the user still can't find it in Swagger" — the fix
shipped real OpenAPI metadata that most tooling other than a browser-rendered
Swagger UI can read, but not something the specific rendering surface the
user is actually looking at displays.

`payload`'s own `Form(description=...)` text, by contrast, is a plain string
the parameter table already renders correctly (confirmed working in the
earlier change's task 2.2) — regardless of content type, regardless of
"Try it out" being open. That is the one place in Swagger's UI this
information can reliably reach a human without depending on multipart-example
rendering support that may not exist.

## What Changes

- `payload`'s `Form(...)` `description` on `POST /invitations` gains the full
  `individual` and `group` example JSON (camelCase, matching this project's
  wire convention) as literal, formatted text — visible in Swagger's
  Parameters table without opening "Try it out" or depending on multipart
  example-selection support.
- `primary_contact_id_proof_file`/`visitor_id_proof_files` descriptions gain
  an explicit cross-reference to the visitor-list ordering rule already
  stated on `visitor_id_proof_files`, so both file fields are self-explanatory
  from the same table row a reader is already looking at.
- The existing `openapi_extra` `individual`/`group` examples and their
  regression test are kept as-is (not removed) — they're correct, harmless,
  and useful to any tool that *does* render multipart examples (Redoc, a
  future Swagger UI version, non-browser OpenAPI consumers); they're just not
  sufficient on their own for this project's actual `/docs` rendering surface.
- **No behavior change**: request validation, multipart parsing, and
  persistence are untouched — this is OpenAPI/description metadata only, the
  same posture as the change it follows on from.

## Capabilities

### New Capabilities
- `invitations`: adds one requirement to the same not-yet-baselined
  `invitations` capability that `add-pre-registration` and
  `harden-invitation-tracking-fidelity` (both still unarchived) are also
  building toward — this delta, theirs, and the now-archived
  `merge-invitation-registration-into-creation`/
  `document-self-registration-multipart-payload` deltas all merge into one
  `openspec/specs/invitations/spec.md` once reconciled and synced.

### Modified Capabilities
(none — this only adds a requirement; it doesn't change how any existing
requirement is satisfied)

## Impact

- **Code**: `src/vmss_api/invitations/router.py` — `create_invitation`'s
  `payload`/`primary_contact_id_proof_file`/`visitor_id_proof_files`
  parameter `description=` text only. No signature, validation, or logic
  change.
- **Tests**: `tests/test_api_documentation.py` — a new assertion that the
  generated OpenAPI schema's `payload` parameter description contains both
  registration types' example JSON (by parsing the embedded JSON back out
  and validating it against `InvitationCreate`), so a future edit that
  strips or breaks the embedded example fails CI instead of silently
  regressing Swagger back to an unexplained string box.
- **Docs**: `docs/features/invitations.md` gains a short note that the
  `payload` field's Swagger description (not just "Try it out") is where the
  full JSON shape is discoverable, and why (`api-documentation.md` §1's
  spirit: a route's contract should be discoverable from Swagger, not just
  from source or from a rendering path that may not be supported).
- **No breaking changes.** No new dependencies. No `.env`/settings changes.
- **Out of scope**: reconciling the four overlapping `invitations` spec
  deltas into one main `openspec/specs/invitations/spec.md` — flagged at the
  end of this session's cleanup as separate, deliberate work; this change
  adds one more delta to that same pile rather than resolving it.
