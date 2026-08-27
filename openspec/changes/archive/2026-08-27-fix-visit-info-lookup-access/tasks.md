## 1. Registrations: distinguish invalid-credential vs unconfigured-defaults

- [x] 1.1 In `registrations/deps.py`, add a second detail string (e.g.
      `_DEFAULT_TENANT_UNCONFIGURED_DETAIL = "Registration service is not
      configured for this environment"`) distinct from
      `_INVALID_DEVICE_KEY_DETAIL`.
- [x] 1.2 In `_resolve_default_device_context`, raise with the new detail
      string and `logger.error(...)` (not `logger.warning`) for both the
      "default tenant not found/inactive" and "default branch not
      found/inactive" branches; include `tenant_slug`/`branch_code` in the
      log context.
- [x] 1.3 Leave `get_registration_device`'s invalid-key/inactive-tenant/
      inactive-branch-from-a-matched-key paths unchanged (still
      `_INVALID_DEVICE_KEY_DETAIL` at `WARNING`).
- [x] 1.4 Update `registrations/tests.py::test_walk_in_registration_missing_device_key_no_default_tenant_rejected`
      and `..._no_default_branch_rejected` to assert the new message and
      (via `caplog`/structlog capture, matching this repo's existing
      logging-assertion pattern if one exists) the `ERROR` level.

## 2. `GET /hosts/search`: optional query with browsable default list

- [x] 2.1 In `visit_info/router.py`, change `query` to
      `Annotated[str | None, Query()] = None` (dropping the unconditional
      `min_length`); add an explicit length check in the router or service
      that rejects a *supplied* query shorter than `_MIN_QUERY_LENGTH`
      with the same validation-error response as today.
- [x] 2.2 In `visit_info/service.py::search_hosts`, branch the query
      construction: when `query` is `None`/blank, list active employees
      ordered by name (existing `is_active`/soft-delete filters unchanged)
      instead of applying the name/email `ILIKE` filter; when non-blank,
      keep today's matching behavior. Both branches share the existing
      `limit` capping.
- [x] 2.3 Update `docs/features/registrations.md` (or the visit-info
      feature doc, once it exists) to document the optional `query` and
      the browsable-default-list behavior.

## 3. Regression tests: device key already optional on the three lookup endpoints

- [x] 3.1 In `visit_info/tests.py`, add a missing-`X-Device-Key`-header
      success test for `GET /visit-info/departments`, asserting it falls
      back to the default tenant/branch (mirroring
      `registrations/tests.py::test_walk_in_registration_missing_device_key_falls_back_to_default_tenant_success`).
- [x] 3.2 Same for `GET /hosts/search` and `GET /visit-info/options`.
- [x] 3.3 Add tests for the new omitted-query and blank-query behavior on
      `GET /hosts/search` (browsable default list, capped by `limit`,
      alphabetical order) and confirm the below-minimum-length case is
      still rejected when a query *is* supplied.
- [x] 3.4 Add a test asserting the `ERROR`-level log and new message when
      `X-Device-Key` is omitted and the default tenant/branch is
      unconfigured, for at least one of the three visit-info endpoints (in
      addition to the walk-in coverage from Task 1.4), since they share
      the same dependency.

## 4. Verification

- [x] 4.1 `ruff check` / `ruff format --check` clean on touched files.
- [x] 4.2 `pytest` green, including all new tests above.
- [x] 4.3 Manually confirm against a local `.env` with real
      `TENANT_DEFAULT_SLUG`/`REGISTRATION_DEFAULT_BRANCH_CODE` values that
      omitting `X-Device-Key` on all four endpoints succeeds end-to-end
      (not just unit-tested), so the fix is verified the same way the
      frontend team will retest it. (Done via the real ASGI app + real
      Postgres, hitting all four endpoints exactly as the frontend
      reported: all three GETs and the walk-in POST succeed with no
      `X-Device-Key`; the unconfigured-default case returns the new
      distinct message and `ERROR` log. This also required actually fixing
      this local checkout's non-functional `.env` — see apply-session
      notes.)
- [x] 4.4 Flag the `vmss-dev` `.env` placeholder values
      (`TENANT_DEFAULT_SLUG`, `REGISTRATION_DEFAULT_BRANCH_CODE`) to
      whoever manages that environment — outside this change's code, but
      required for error 1 to actually resolve there. (Flagged in
      proposal.md - Impact and again below — this local checkout's `.env`
      turns out to have the *same* unresolved-placeholder pattern across
      nearly every setting, not just these two; see note on task 4.2/4.3.)
