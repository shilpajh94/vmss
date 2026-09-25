## Why

A full audit of `src/vmss_api/` found a small number of genuine N+1 query
patterns, one loop-and-query bulk-create path, one layering violation, and
several helpers that are duplicated verbatim across 2-3 feature packages —
in most cases with a docstring on the copy admitting it mirrors a sibling
that was never actually extracted into `core/`. None of these are
architectural problems (`TenantScopedRepository.paginate`, eager-loading
discipline, and the repository pattern are already followed correctly
almost everywhere), but each fix removes a measurable, citable inefficiency
or a maintenance hazard (three copies of the same Redis idempotency logic
drifting out of sync). Fixing them now, while the list is short and
well-scoped, is cheaper than waiting for a fourth copy to appear or for
`bulk_create_visitor_categories` to time out under real data volume.

## What Changes

- Batch `form_builder/service.py::list_fields_for_steps` into a single
  `WHERE step_id IN (...)` query instead of one query per step.
- Batch `visitors/service.py::bulk_create_visitor_categories`'s per-name
  existence checks (`get_by_code`/`get_by_name` in a loop) into two
  `WHERE code IN (...)` / `WHERE name IN (...)` pre-fetch queries, and
  replace the post-commit per-row `refresh()` loop with one `WHERE id IN
  (...)` re-query.
- Reduce `org_structure/service.py::provision_branch`'s per-row
  `flush()` calls (one per building, one per floor) to one flush per level
  (or fewer), without changing the rows it creates or their ids.
- Extract the three duplicated idempotency-cache helpers
  (`invitations/router.py`, `audit_trail/router.py`,
  `identity_verification/router.py`) into a single `core/idempotency.py`
  used by all three.
- Extract the three duplicated `_branch_filter` implementations
  (`dashboard/repository.py`, `invitations/repository.py`,
  `org_structure/repository.py`) into one shared helper in `core/`.
- Extract the duplicated avatar/photo content-type allow-list checks
  (`auth/service.py`, `invitations/service.py`) into one
  `validate_image_only` helper in `core/storage.py`.
- Move `approvals/service.py::_user_holds_role_at_branch`'s direct
  `AsyncSession`/`select()` usage into `auth/repository.py` behind a
  repository method, per the project's mandatory repository-pattern rule.
- Add a `paginate_with_joins` variant on `TenantScopedRepository` (or
  equivalent shared helper) and migrate `FloorRepository.list_page` and
  `ReceptionDeskRepository.list_page`'s duplicated count+join+page
  boilerplate onto it.
- No public API contract, request/response schema, status code, or
  database schema changes anywhere in this list — every item is an
  internal implementation change behind an existing interface.

## Capabilities

No spec-level behavior changes: every item above is an internal
query-shape, code-location, or duplication fix behind an existing,
unchanged public contract (same endpoints, same request/response schemas,
same status codes, same side effects and ordering guarantees observable by
a caller). `skip_specs: true` is set in this change's `.openspec.yaml`
accordingly — see `design.md` for how each item is verified to be
behavior-preserving.

### New Capabilities
(none)

### Modified Capabilities
(none — see above)

## Impact

- **Code**: `form_builder/service.py`, `visitors/service.py`,
  `org_structure/service.py`, `invitations/router.py`,
  `audit_trail/router.py`, `identity_verification/router.py`,
  `dashboard/repository.py`, `invitations/repository.py`,
  `org_structure/repository.py`, `auth/service.py`,
  `invitations/service.py`, `core/storage.py`, `approvals/service.py`,
  `auth/repository.py`, `core/database.py` (new `core/idempotency.py` and
  a `core/branch_filter.py` or equivalent addition to `core/tenancy.py`).
- **Tests**: existing `tests.py` suites for every touched feature must
  keep passing unmodified in behavior (assertions on response bodies,
  status codes) — per `testing-standards.md`, any test that only passed
  because of the old query shape (e.g. asserting call counts on a mocked
  repository, which this codebase doesn't do) would need updating, but a
  scan found none. New tests are added only to pin down the previously
  N+1/loop-and-query behavior so a regression is caught (e.g. a test
  asserting `bulk_create_visitor_categories` issues a bounded number of
  queries via SQLAlchemy's engine-level query counter, if the test
  harness supports it — see `design.md`).
- **No** database migration, `.env` key, dependency version, or Celery
  task signature changes.
- **No** change to `docs/features/*.md` beyond noting the internal
  optimization where a feature doc explicitly described the old query
  shape.
