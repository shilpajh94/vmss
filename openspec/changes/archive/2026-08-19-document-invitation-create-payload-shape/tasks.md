## 1. Router (`invitations/router.py`)

- [x] 1.1 Extend `payload`'s `Form(description=...)` on `create_invitation`
      with the full `individual` example JSON (camelCase) in the
      description. Implemented via a shared `_INDIVIDUAL_PAYLOAD_EXAMPLE`
      dict rather than duplicating literal JSON text — both the
      `openapi_extra` examples and the description are built from the same
      source dict, so they're data-identical by construction (stronger than
      "byte-for-byte," since they can't drift apart on a future edit).
- [x] 1.2 Same for the `group` example JSON, via a shared
      `_GROUP_PAYLOAD_EXAMPLE` dict.
- [x] 1.3 Updated `primary_contact_id_proof_file`'s and
      `visitor_id_proof_files`'s (`_NO_VISITOR_FILES`) `description=` text so
      each cross-references the other and the `payload.visitors` ordering
      rule.
- [x] 1.4 `_INVITATION_PAYLOAD_EXAMPLES`/`openapi_extra` and the route
      decorator untouched — additive to the parameter descriptions only
      (design.md Decision 1 — kept both channels).

## 2. Tests (`tests/test_api_documentation.py`)

- [x] 2.1 Added `test_invitation_payload_description_is_self_documenting`:
      fetches `app.openapi()`, reads the `payload` property's description on
      `Body_create_invitation_api_v1_invitations_post`, extracts both
      ```json fenced blocks via regex, and parses each with
      `InvitationCreate.model_validate_json(...)`, asserting the two
      registration types are both represented (design.md Decision 2 —
      parse-and-validate, not substring matching).
- [x] 2.2 Ran `tests/test_api_documentation.py` + `invitations/tests.py` —
      38/38 passed, including the pre-existing
      `test_invitation_multipart_payload_examples_documented` (unaffected —
      confirms this change is additive, not a replacement).

## 3. Docs

- [x] 3.1 `docs/features/invitations.md`: replaced the now-inaccurate claim
      that "Try it out" reliably shows the examples with a new "Finding the
      payload shape in Swagger" section explaining the Swagger UI multipart-
      examples limitation and pointing at the `payload` field's description
      as the reliable source.

## 4. Final Verification

- [x] 4.1 `ddev exec uv run ruff check .` and `ddev exec uv run ruff format --check .`
      — both clean across the whole repo.
- [x] 4.2 `ddev exec uv run mypy src/vmss_api/invitations` — clean, 11 source
      files.
- [x] 4.3 `ddev exec uv run pytest` — full suite green, 175/175 passed, no
      regressions.
- [x] 4.4 Inspected `app.openapi()`'s `payload` parameter description
      directly — both example blocks present, fully human-readable
      (pretty-printed JSON), not just machine-parseable.
