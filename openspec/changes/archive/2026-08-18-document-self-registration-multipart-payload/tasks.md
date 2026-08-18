## 1. Re-Confirm the Reported Symptom (no code change)

- [x] 1.1 Confirmed `primary_contact_id_proof_file`/`visitor_id_proof_files`
      are real `UploadFile` parameters (`router.py:193-194`) — image upload
      is already supported and already renders as file pickers in Swagger.
      Not a gap.
- [x] 1.2 Confirmed `payload: Annotated[str, Form()]` (`router.py:192`) has
      no `openapi_examples`/`description` — Swagger renders it as an empty
      string box, which is the actual cause of "haven't seen the payload
      same as the json given."

## 2. Add Swagger Examples via `openapi_extra` (design.md Decision 1 — verified)

- [x] 2.0 Confirmed by direct reproduction against this project's installed
      FastAPI 0.141.1 that `Form(openapi_examples=...)` on `payload` alone
      produces **no examples** in the generated schema, because this route
      combines three `Form`/`File` params into one synthesized body field —
      the mechanism only reads the combined field's own `field_info`, not
      any individual param's. `openapi_extra` on the route decorator was
      confirmed to work instead (see design.md Decision 1 for the traced
      cause and the verified reproduction).
- [x] 2.1 `invitations/router.py`: added `_SELF_REGISTRATION_PAYLOAD_EXAMPLES`
      declaring `requestBody.content['multipart/form-data'].examples` with
      `individual` and `group` keys, each `value` a `{"payload": "<json
      string>"}` map built from the user's two supplied JSON payloads
      translated to camelCase field names; passed via `openapi_extra` to
      `@router.post("/{tracking_token}/register", ...)`.
- [x] 2.2 `invitations/router.py`: added `description` to `payload`'s
      `Form(...)`, `primary_contact_id_proof_file`'s `File(...)`, and the
      `_NO_VISITOR_FILES` `File(...)` singleton backing
      `visitor_id_proof_files` — confirmed these per-field `description`s DO
      render correctly even though per-field `openapi_examples` don't.

## 3. Prove It via the Generated OpenAPI Schema (design.md Decision 2 — verified path)

- [x] 3.1 `tests/test_api_documentation.py`: added
      `test_self_registration_multipart_payload_examples_documented`
      asserting both `individual` and `group` keys exist at
      `schema["paths"]["/api/v1/invitations/{tracking_token}/register"]`
      `["post"]["requestBody"]["content"]["multipart/form-data"]["examples"]`
      — added here rather than `invitations/tests.py` since this file is
      this project's established home for OpenAPI-schema regression
      assertions (`api-documentation.md`), confirmed by its existing
      camelCase/tag/security schema tests.
- [x] 3.2 Same test asserts each example's `value["payload"]` parses via
      `SelfRegistrationSubmit.model_validate_json(...)` and that
      `registration_type` matches the example's own key — so a schema drift
      (e.g. a renamed field) that would break real Swagger-driven testing
      fails this test too.

## 4. Docs

- [x] 4.1 `docs/features/invitations.md`: added a note that `/docs`'s "Try
      it out" for self-registration offers pre-filled `individual`/`group`
      examples for the `payload` field, via `openapi_extra` (not
      `Form(openapi_examples=...)`, which doesn't work for this
      multi-Form/File-param route).

## 5. Final Verification

- [x] 5.1 `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`
      clean on `src/vmss_api/invitations/router.py` and
      `tests/test_api_documentation.py`.
- [x] 5.2 `ddev exec uv run mypy src/vmss_api/invitations` — clean.
- [x] 5.3 `ddev exec uv run pytest src/vmss_api/invitations/tests.py` — all
      26 existing cases green (no regressions from the route signature
      change); `ddev exec uv run pytest tests/test_api_documentation.py` —
      all 12 cases green including the new schema-example test.
- [x] 5.4 Confirmed via a direct `app.openapi()` inspection (equivalent to
      what `/docs` renders) that both examples appear under the route's
      `multipart/form-data` request body and each `payload` value is the
      exact camelCase JSON the user supplied. Full suite
      (`ddev exec uv run pytest`) — 175 passed, no regressions.
