## Why

The user re-checked API-10 in Swagger UI and reported: "haven't seen the
payload same as the json given" for both the `group` and `individual`
example payloads they supplied, and asked directly: **"Does the api
supports image upload?"**

Re-reading the live route confirms two separate things:

**Image upload is genuinely supported — this part is not a gap.**
`POST /invitations/{tracking_token}/register`
(`src/vmss_api/invitations/router.py:186-196`) declares
`primary_contact_id_proof_file: Annotated[UploadFile, File()]` and
`visitor_id_proof_files: list[UploadFile] = _NO_VISITOR_FILES` as real file
parameters. Swagger UI renders these as file-picker widgets, and
`service.py`/`core/storage.py::validate_upload` genuinely validate and store
the uploaded bytes by real magic-byte content, not just filename/
`Content-Type` (`file-upload-handling.md` §2). Nothing to fix here.

**The reported symptom is real, and traced to a concrete cause.** The same
route declares `payload: Annotated[str, Form()]` — a bare string. FastAPI
has no schema/example attached to this field, so Swagger UI renders it as an
empty single-line text box with no hint of the nested JSON shape
(`registrationType`, `primaryContact`, `visitors[]`, `visitDetails`,
`carriedItems`, `vehicles[]`, `consents`) the caller must hand-encode into
it. That is exactly why the user's two JSON payloads didn't "look like" what
Swagger showed: Swagger was never given anything to show. This is the same
class of problem `api-documentation.md` describes for a missing
`response_model` — nothing breaks at runtime, but the endpoint is
indistinguishable in Swagger from one that takes an arbitrary string, and a
caller testing it interactively has no way to discover the real contract.

This is a **documentation/OpenAPI-schema gap, not a functional defect** —
the same conclusion already reached for API-09/API-10 in
`harden-invitation-tracking-fidelity` (still pending, unrelated fields). No
behavior of the endpoint changes; what changes is what Swagger UI shows for
it.

- **Verified, not assumed**: the obvious fix (`Form(openapi_examples=...)`
  on the `payload` param alone) was tested directly against this project's
  installed FastAPI 0.141.1 and confirmed to produce **no examples at all**
  in the generated schema, because this route has more than one `Form`/
  `File` parameter (`design.md` Decision 1 has the full trace). The
  corrected approach — `openapi_extra` on the route decorator — was tested
  the same way and confirmed to work.

## What Changes

- `submit_self_registration`'s route decorator gains an `openapi_extra`
  declaring two named examples — `individual` and `group` — for the
  multipart request body, built directly from the two JSON payloads the
  user supplied (converted to this endpoint's real camelCase wire shape),
  so Swagger UI's "Try it out" panel offers both as selectable, pre-filled
  forms (including the `payload` field's JSON) instead of an empty string
  box.
- `primary_contact_id_proof_file` and `visitor_id_proof_files` gain a
  `description` clarifying they are the primary contact's and each
  co-visitor's ID-proof image/PDF upload, matched to `payload.visitors` by
  order — so Swagger's parameter list makes the image-upload contract
  explicit instead of relying on the caller to infer it from the field name.
- A test asserting the generated OpenAPI schema for this route actually
  carries both named examples, so a future edit that drops them (e.g. a
  refactor of the route signature) fails CI instead of silently regressing
  Swagger back to an undocumented string box.
- **No changes** to request validation, file handling, or persistence —
  `SelfRegistrationSubmit` and `service.py::submit_self_registration` already
  accept and process exactly this shape (confirmed again in this audit).

## Capabilities

### New Capabilities
- `invitations`: this change's delta adds one requirement to the same
  not-yet-baselined `invitations` capability that
  `harden-invitation-tracking-fidelity` (still pending) is also
  establishing. Both changes' deltas will merge into one
  `openspec/specs/invitations/spec.md` when synced; each declares only the
  requirement it actually adds, matching this session's existing convention
  of one baseline capability accumulated across the changes that touch it.

### Modified Capabilities
- None.

## Impact

- **Code**: `src/vmss_api/invitations/router.py`
  (`submit_self_registration`'s parameter declarations only — no logic
  change).
- **Tests**: `src/vmss_api/invitations/tests.py` — one new test asserting
  `app.openapi()`'s schema for this route includes both named examples.
- **Docs**: `docs/features/invitations.md` gains a short note that the
  multipart `payload` field's Swagger examples show the exact JSON shape for
  both registration types, so a reader trying the endpoint from `/docs`
  isn't left guessing (`api-documentation.md` §1's spirit — a route's
  contract should be discoverable from Swagger, not just from source).
- **No breaking changes**: purely additive OpenAPI metadata; the wire
  contract and validation behavior are unchanged.
- **Out of scope**: the five tracking-response fields already being fixed in
  `harden-invitation-tracking-fidelity` — unrelated gap, separate change.
