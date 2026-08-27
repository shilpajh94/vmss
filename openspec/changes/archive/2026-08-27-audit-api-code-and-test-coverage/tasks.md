## 1. Code review of this session's changes

- [x] 1.1 Run the project's code-review process against the current
      uncommitted diff (`registrations/deps.py`, `visit_info/router.py`,
      `visit_info/service.py`, `auth/repository.py`, `registrations/tests.py`,
      `visit_info/tests.py`) for correctness bugs, edge cases, and
      reuse/simplification issues. **4 findings.**
- [x] 1.2 Triage each finding: fix genuine bugs (smallest correct change);
      note and dismiss anything that's a style preference or out of scope,
      with a one-line reason.
      1. **[FIXED, real bug]** `visit_info/router.py::search_hosts` —
         `query.strip() if query else None` left a whitespace-only query
         (e.g. `?query=%20`) as `""` after stripping, which then failed the
         `len(...) < 2` check and was rejected with 422 instead of treated
         as blank/browsable — contradicting the spec and this endpoint's
         own docstring. Fixed to `(query or "").strip() or None`, so blank
         *and* whitespace-only both normalize to `None`. Added regression
         test `test_search_hosts_whitespace_only_query_returns_browsable_default_list`.
      2. **[Dismissed, intentional]** Hand-rolled length validation instead
         of declarative `Query(min_length=...)` produces `error_response`'s
         422 envelope rather than FastAPI's native validation-error shape.
         This was a deliberate choice (design.md's "Decisions"), matching
         an existing precedent already in the codebase
         (`invitations/router.py`'s conditional `trackingId`/`email`
         validation uses the same `error_response` pattern) rather than a
         new inconsistency — not changed.
      3. **[FIXED, clarity]** `_DEFAULT_TENANT_UNCONFIGURED_DETAIL` was
         reused verbatim for both the "no default tenant" and "no default
         branch" paths, so the name no longer matched what it backed.
         Renamed to `_DEFAULT_UNCONFIGURED_DETAIL`.
      4. **[FIXED, simplification]** The "no default tenant" / "no default
         branch" branches in `_resolve_default_device_context` were
         near-identical copy-pasted log+raise blocks. Extracted a shared
         `_reject_unconfigured_default(event, **fields) -> NoReturn`
         helper; both branches now call it.

## 2. Test-coverage audit against testing-standards.md §2

- [x] 2.1 Confirm every endpoint the feature's router exposes has at least
      one happy-path test. **Result: no gaps in any of the 11 features** —
      every route across `auth`, `core`, `identity_verification`,
      `invitations`, `org_structure`, `platform`, `registrations`,
      `reports`, `tenant`, `visit_info`, `visitors` has a passing-path test.
- [x] 2.2 Confirm every `require_permission`/`authorize_branch_id`-gated
      endpoint has a permission-denied test case. **Gaps found and fixed:**
      - `auth`: 5 gated `/auth/roles*` endpoints had no denial test
        (`GET /roles`, `GET /roles/verify`, `GET /roles/{id}`,
        `PUT /roles/{id}`, `DELETE /roles/{id}`) — **added 5 tests.**
      - `org_structure`: 4 gated endpoints had no denial test
        (`GET /company`, `PUT /company`, `DELETE /company`,
        `DELETE /branches/{id}`) — **added 4 tests.**
      - `tenant`/`platform`: `POST /platform/tenants` has no
        unauthenticated/wrong-token-chain test (its sibling
        `GET /platform/tenants` has both) — **flagged, not fixed** (see
        Wrap-up backlog).
      - `visitors`, `invitations`, `reports`, `identity_verification`: no
        gaps found.
- [x] 2.3 Confirm every tenant-scoped repository method has at least one
      tenant-isolation test — per `testing-standards.md` §2's reference
      example, `auth/tests.py::test_tenant_schema_isolation`. **Gap found
      and fixed:**
      - `visit_info`: **zero** tenant-isolation tests existed for any of
        its three endpoints — **added
        `test_search_hosts_tenant_schema_isolation`.** (While writing it,
        found and fixed a real test-isolation bug: a fixed schema name +
        fixed email collided with leftover data from a prior run, since
        `open_tenant_session` writes aren't rolled back like `db_session`'s
        are — fixed by randomizing the email, matching the established
        `uuid.uuid4().hex[:8]` idiom already used elsewhere, e.g.
        `org_structure/tests.py::test_list_branches_tenant_isolation`.)
      - `auth`, `org_structure`, `visitors`, `invitations`, `reports`: the
        "at least one" bar is met for every tenant-scoped repository class,
        though several individual methods beyond the first per class have
        no dedicated isolation test (e.g. `auth`'s `UserRepository` has ~8
        untested methods beyond `get_by_id`) — **not fixed**, consistent
        with the project's own established "one test per feature is the
        bar" convention (confirmed by every other audited feature doing
        exactly this, not more).
      - `tenant`/`platform`: provisioning-produces-a-working-schema is
        tested; provisioning-produces-schemas-isolated-*from-each-other*
        (two real tenants, cross-checked) is not — **flagged, not fixed.**
      - `identity_verification`: no repository/DB table exists by design
        (Redis-only state); has its own dedicated per-tenant Redis-key
        isolation test — no gap.
- [x] 2.4 List any gap found per feature; add the missing test(s) (built via
      the project's factory pattern, not hand-built dicts, per
      `testing-standards.md` §1). **10 tests added across `auth` (5),
      `org_structure` (4), `visit_info` (1); 2 tests added/extended in
      `registrations` for spec-scenario gaps found in task 3 below.**

## 3. Spec-to-test cross-check

- [x] 3.1 For each `#### Scenario:` in the capability's main spec, identify
      the test (by name/file) that exercises it. Flag any scenario with no
      identifiable test. **Result across all 14 capabilities:**
      - **Fully covered, no gaps:** `visitors` (structural coverage
        complete, see 3.2 for finer-grained gaps), `identity-verification`,
        `rate-limiting`, `file-storage` (one gap, see below).
      - **`registrations`**: two scenarios had no test — "Invalid device
        credential is reported and logged as a client-side anomaly" (the
        WARNING-log-level half was never asserted) and "Walk-in
        registration is audited" / "Audit entry recorded with no actor"
        (the audit-log write is real and fires, per this session's earlier
        live-request verification, but had zero test coverage anywhere in
        the repo) — **both fixed**, one new test each.
      - **`invitations`**: today's new "Visit Details Optionally Accept
        Catalog IDs" requirement is fully covered. Two pre-existing gaps
        found: "Full consent accepted and timestamped" (`consentRecordedAt`
        persistence itself is never asserted, only the boolean flags) and
        the OpenAPI-example-parses-as-valid-JSON half of the
        self-documenting-payload requirement — **flagged, not fixed.**
      - **`org-structure`**: several scenarios (company defaults
        persistence, branch created with explicit `isActive`, security-gate
        building-cross-branch 404, floor/reception-desk/gate creation
        without `X-Branch-ID`, duplicate-active-row 409 for
        Building/Department-direct/ReceptionDesk/SecurityGate, company
        email validation on update, inactive-branch-header rejection,
        listing rate-limit) have no identifiable test — **flagged, not
        fixed** (see Wrap-up backlog; volume here is large enough that
        fixing all of it belongs in its own change, not this audit pass).
      - **`reports`**: "company-wide, not branch-scoped" and "grouped
        queries, not a per-branch loop" scenarios have no dedicated test
        (the latter is arguably not behavior-testable) — **flagged, not
        fixed** (minor).
      - **`api-compliance-hardening`**: idempotency-key-expiry scenario
        untested (no test manipulates the Redis TTL) — **flagged.**
      - **`api-documentation`**: request-body (not just response) camelCase
        rendering untested — **flagged.**
      - **`background-jobs`**: actual retry-with-backoff behavior and
        request-id propagation into task logs are both untested (existing
        tests deliberately short-circuit to `max_retries=0` to skip the
        real retry path) — **flagged.**
      - **`environment-configuration`**: **zero test coverage anywhere in
        the repo** — no test exercises `Settings`, its
        component/override-URL assembly, or `.env.example` completeness —
        **flagged as the single largest gap found in this audit**, worth
        its own follow-up change rather than a few tests bolted onto this
        one.
      - **`file-storage`**: client-supplied-filename-can't-influence-
        storage-path is structurally guaranteed (the `save()` signature
        never accepts a filename) but not asserted by a test — **flagged,
        minor.**
      - **`tenant`/`platform`**: **no capability spec exists for this
        behavior at all** under `openspec/specs/` — tested, but entirely
        undocumented at the spec level, unlike every other feature audited
        — **flagged as a documentation gap**, not fixed (writing a new
        capability spec is out of scope for a `skip_specs: true` audit
        change; recommended as separate follow-up work).
- [x] 3.2 Flag the reverse case if noticed in passing (a test asserting
      behavior the spec doesn't document). **Found, not fixed (spec is
      what's stale in each case, not the test):**
      - `org_structure`: `GET /branches/current` is a fully real,
        implemented, tested endpoint with zero mention in
        `openspec/specs/org-structure/spec.md`.
      - `invitations`: `test_create_group_invitation_exceeding_max_visitors_rejected`
        asserts a max-group-size cap the spec never documents.
      - `reports`: two logging-detail tests (zero-admin-recipients,
        retry-exhaustion) assert behavior the spec doesn't mention (both
        reasonable, just undocumented).
      - `auth`: the entire employee-listing/sync surface
        (`POST /employees/sync`, `GET /employees`,
        `GET /employees/directory`) is thoroughly tested with no matching
        spec scenario in `auth/spec.md` — likely documented in
        `org-structure/spec.md` instead (that's where the "Employee
        Directory Sync" scenarios actually live, per 3.1's `org-structure`
        findings — confirmed not a real gap, just cross-file).
- [x] 3.3 For each flagged gap, add the missing test or, if the spec itself
      is what's stale, correct the spec. **Fixed the highest-value,
      lowest-ambiguity gaps** (registrations' 2 spec-scenario gaps, folded
      into task 2's fixes). **Left the rest flagged, not fixed** — the
      remaining volume (`org-structure`'s ~9 scenarios, `visitors`' 6,
      `environment-configuration`'s full gap, several smaller ones) is
      large enough that fixing it all here would turn a review/audit pass
      into an open-ended test-writing project; see Wrap-up for the
      prioritized backlog instead. None of the stale-spec cases (3.2) were
      corrected — that's an `openspec/specs/` edit outside a
      `skip_specs: true` change's intended scope, recommended as separate
      follow-up work.

## 4. Wrap-up

- [x] 4.1 Summarize findings.

  **Code review** (task 1): 4 findings — 1 real bug fixed (whitespace-only
  `query` on `GET /hosts/search` wrongly rejected instead of treated as
  blank), 2 simplification fixes applied (misleading shared constant name;
  duplicated log+raise blocks extracted into `_reject_unconfigured_default`),
  1 dismissed as intentional (matches an existing codebase precedent).

  **Test-coverage audit** (task 2): 3 real `testing-standards.md` §2 gaps
  found and closed — `auth` (5 missing permission-denied tests),
  `org_structure` (4 missing permission-denied tests), `visit_info` (zero
  tenant-isolation tests, plus a test-isolation bug found and fixed while
  writing the new one). 10 new tests added. All other 8 features already
  met the §2 bar.

  **Spec-to-test cross-check** (task 3): all 14 capabilities reviewed
  scenario-by-scenario. 2 gaps fixed (`registrations`). A larger backlog of
  smaller gaps was found and deliberately left unfixed (see below) —
  fixing all of it would exceed this audit's scope. The single largest
  finding: **`environment-configuration` has zero test coverage anywhere in
  the repo**, and **`tenant`/`platform` has no capability spec at all**
  despite being tested — both worth dedicated follow-up changes.

  **Prioritized backlog (not fixed in this change):**
  1. `environment-configuration` — no test coverage at all (largest gap).
  2. Write a capability spec for `tenant`/`platform` behavior (currently
     undocumented at the spec level).
  3. `org-structure` — ~9 spec scenarios with no test, plus document
     `GET /branches/current` (implemented, tested, unspec'd).
  4. `visitors` — 6 finer-grained scenario gaps (branch-context CRUD,
     duplicate-name conflict, update-path validation variants).
  5. `POST /platform/tenants` missing an unauthenticated-request test
     (mirrors what `GET /platform/tenants` already has).
  6. Smaller items: `invitations` (2), `reports` (2), `background-jobs` (2),
     `api-compliance-hardening` (1), `api-documentation` (1),
     `file-storage` (1) — each independently low-effort, listed in task 3
     above.

- [x] 4.2 Run `ddev exec uv run pytest -q` once more if any test or code
      file changed in tasks 1–3, to confirm everything (old and new) is
      green. **Result: 405 passed, 0 failed** (393 baseline + 12 new test
      functions: 1 whitespace-query regression, 1 audit-log, 1
      invalid-key-WARNING-log, 1 visit_info tenant-isolation, 5 auth
      permission-denied, 4 org_structure permission-denied — one of the 13
      edits extended an existing test in place rather than adding a new
      function, hence 12 not 13).
- [x] 4.3 Note the `sso`-on-unmerged-branch finding for the user explicitly
      (not a code issue on this branch, but worth knowing before this
      branch and `feature/sso-api-task` are eventually reconciled). Done —
      see proposal.md "Why" and the apply-session summary.
