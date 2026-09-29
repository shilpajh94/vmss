## 1. Schema

- [x] 1.1 Add `visitor_category_id: uuid.UUID | None` to `ReturningVisitorPrefill`
      (`src/vmss_api/visitor_return_visit/schemas.py`), placed alongside the
      other prefill fields, with a docstring note following the file's
      existing id-only-convention pattern (see `id_proof_url`/`photo_url`'s
      docstring for the established style).

## 2. Service Layer

- [x] 2.1 Update `_to_prefill` (`src/vmss_api/visitor_return_visit/service.py`)
      to pass `visitor_category_id=invitation.visitor_category_id` — a plain
      column already present on the `Invitation` row the function receives,
      no new query or eager-load needed.

## 3. Tests

- [x] 3.1 Extend
      `test_returning_visitor_sees_history_and_prefill_from_most_recent_visit`
      (`src/vmss_api/visitor_return_visit/tests.py`) to set a
      `visitor_category_id` on the seeded invitation and assert
      `prefill["visitorCategoryId"]` matches it.
- [x] 3.2 Add a test asserting `prefill["visitorCategoryId"]` is present and
      `null` when the most recent invitation has no `visitor_category_id` set
      (same pattern as the existing
      `test_prefill_missing_photo_and_id_proof_are_null_not_omitted` test).

## 4. Documentation

- [x] 4.1 Update the `GET /api/v1/visitor-portal/me` row/description in
      `docs/features/visitor_return_visit.md` to list `visitorCategoryId` in
      the prefill field set.

## 5. Verification

- [x] 5.1 `ddev exec uv run pytest src/vmss_api/visitor_return_visit/tests.py`
      passes.
- [x] 5.2 `ddev exec uv run ruff check` and
      `ddev exec uv run ruff format --check` clean on changed files.
- [x] 5.3 Confirm `tests/test_api_documentation.py::test_response_schemas_render_camel_case`
      still passes (new field renders as `visitorCategoryId`, automatic via
      `CamelModel` — `api-documentation.md` §5).
