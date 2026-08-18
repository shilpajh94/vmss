## Context

See `proposal.md` - Why for the full trace of the reported symptom to its
cause: `payload: Annotated[str, Form()]` on
`POST /invitations/{tracking_token}/register`
(`src/vmss_api/invitations/router.py:186-196`) has no schema/example
attached, so Swagger UI shows an empty string box instead of the nested JSON
shape the user expected to see and test against. Image upload itself
(`primary_contact_id_proof_file`, `visitor_id_proof_files`) already works
and already renders as file pickers — confirmed again while investigating
this, not assumed from the earlier audit.

## Goals / Non-Goals

**Goals:**
- Make Swagger UI's "Try it out" panel for this route show a pre-filled,
  selectable example of the `payload` JSON for both `individual` and
  `group` registration types, matching the two payloads the user supplied.
- Make the file-upload parameters' purpose explicit in Swagger's parameter
  descriptions.
- Prove the fix with a test against the generated OpenAPI schema, not just a
  manual Swagger UI check — manual checks aren't repeatable in CI.

**Non-Goals:**
- Changing `SelfRegistrationSubmit` or any validation rule — already correct
  (confirmed in `harden-invitation-tracking-fidelity` and re-confirmed here).
- Changing the tracking-response field gap — that's
  `harden-invitation-tracking-fidelity`'s own, unrelated scope.
- Building a Swagger-only alternate JSON-body endpoint. The multipart
  contract (JSON `payload` part + separate file parts) is the correct shape
  for a request that must carry both structured data and file uploads
  together (`api-conventions.md` has no lighter-weight alternative for this
  case); the fix here is making that existing, correct contract
  discoverable, not replacing it.

## Decisions

### Decision 1: Attach examples via `openapi_extra` on the route, not `Form(openapi_examples=...)`

**Verified against the actual installed FastAPI 0.141.1** before committing
to this, since the obvious-looking approach turns out not to work here.
`Form()`/`Body()` accept an `openapi_examples` argument, but tracing
`fastapi/openapi/utils.py::get_openapi_operation_request_body` shows it only
reads `field_info.openapi_examples` off the route's single synthesized
**body field** — the one `ModelField` FastAPI builds to represent the whole
request body. When a route has more than one `Form`/`File` parameter (this
route has three: `payload`, `primary_contact_id_proof_file`,
`visitor_id_proof_files`), FastAPI combines them into one generated
`Body_submit_self_registration_...` model and that combined field's
`field_info` is a fresh `Body(...)` FastAPI creates internally — not any of
the three params' own `FieldInfo` objects. Put `openapi_examples` on
`payload`'s `Form(...)` and it is silently discarded: reproduced this
exactly — a scratch route matching this endpoint's real signature produced
zero `examples` anywhere in `app.openapi()`'s output. This is exactly the
kind of documentation regression this change exists to catch, and it would
have shipped invisibly if task 3.1's schema assertion hadn't been checked
against a real run first.

The mechanism that does work for a multi-field multipart body is the route
decorator's own `openapi_extra`, which FastAPI deep-merges into the
generated operation object *after* auto-generation — confirmed by the same
scratch reproduction, this time asserting the resulting schema:

```python
_SELF_REGISTRATION_EXAMPLES = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "examples": {
                    "individual": {
                        "summary": "Individual registration, no co-visitors or vehicles",
                        "value": {"payload": json.dumps({...})},  # from the user's individual payload, camelCase keys
                    },
                    "group": {
                        "summary": "Group registration with co-visitors and vehicles",
                        "value": {"payload": json.dumps({...})},  # from the user's group payload, camelCase keys
                    },
                }
            }
        }
    }
}


@router.post(
    "/{tracking_token}/register",
    response_model=Envelope[SelfRegistrationOut],
    openapi_extra=_SELF_REGISTRATION_EXAMPLES,
)
async def submit_self_registration(...):
```

Confirmed via the scratch reproduction that this lands at exactly
`schema["paths"]["/invitations/{tracking_token}/register"]["post"]`
`["requestBody"]["content"]["multipart/form-data"]["examples"]`, each
example's `value` being the full form field map (`{"payload": "<json
string>"}`) Swagger UI pre-fills into the "Try it out" form — including the
`payload` textbox. `payload`/the file params keep their own `Form(...)`/
`File(...)` `description=` (that part of the original design was correct and
independently confirmed to render).

Both `payload` example values are built directly from the two payloads the
user supplied, translated to this endpoint's actual camelCase field names
(`registrationType`, `primaryContact.fullName`, `visitDetails.purposeOfVisit`,
`carriedItems.itemDescription`, `vehicles[].vehicleType`, etc.) so what
Swagger shows is byte-for-byte what the caller already validated by hand
against the schemas, not a paraphrase.

**Alternative considered**: switch the endpoint to accept a single JSON body
with base64-encoded file content instead of multipart file parts (which
would let `Form(openapi_examples=...)` work directly, since there'd be only
one body field). Rejected — base64 inflates payload size ~33% for what are
meant to be photo/PDF ID scans, and multipart file upload is the standard,
more efficient shape for this; the reported problem is documentation, not
the transport shape.

### Decision 2: Verify via the generated OpenAPI schema, not a Swagger UI screenshot

Add a test that constructs the app's OpenAPI schema (`app.openapi()`) and
asserts both `individual` and `group` keys are present at the confirmed
path:
`schema["paths"]["/api/v1/invitations/{tracking_token}/register"]["post"]`
`["requestBody"]["content"]["multipart/form-data"]["examples"]` (path
verified against this project's actual mounted prefix,
`fastapi-architecture.md` §7 — the scratch reproduction above used an
unmounted route, so the real path carries the `/api/v1` prefix this app
mounts `api_router` under). This is the only way this fix stays proven once
merged — a manual "I checked Swagger and it looked right" doesn't survive
the next refactor, and per Decision 1's finding, the "obvious" fix silently
produces nothing without this kind of check.

**Alternative considered**: rely on manual QA of `/docs` only. Rejected —
consistent with `testing-standards.md`'s general bias against
"looked right once" verification; a schema assertion is cheap and exact.

## Risks / Trade-offs

- [Trade-off] The two example JSON strings duplicate literal data already
  present in `invitations/tests.py`'s `_individual_submission()`/
  `_group_submission()` fixtures (as dicts, not JSON strings meant for
  Swagger). Accepted: fixtures exist to drive test requests
  programmatically; these examples exist to be read and pasted by a human in
  Swagger UI. Keeping them as literal, readable JSON in the route decorator
  (rather than deriving one from the other via `json.dumps(fixture)`) keeps
  the Swagger-facing example stable and independent of internal test-fixture
  refactors.

## Migration Plan

- No schema/migration change — this is OpenAPI metadata only, no DB or
  Pydantic validation change.
- No `.env`/`settings` changes. No new dependencies.
