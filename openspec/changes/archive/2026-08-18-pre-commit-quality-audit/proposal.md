## Why

The git repository was just initialized and nothing has been committed yet. Before
the first commit, the project needs a full audit against its own documented
standards (`project-rules.md`, `database-architecture.md`, `fastapi-architecture.md`,
`query-performance.md`, `testing-standards.md`, `logging-observability.md`,
`api-documentation.md`) so the first commit is a clean baseline — not one that
immediately needs a follow-up cleanup commit for gitignore gaps, stray files, or
rule violations that were easy to catch before anything was locked in.

## What Changes

- Add `var/` (439 files of local upload storage, including test `id-proof` images)
  to `.gitignore` — currently untracked and unmatched, so a plain `git add .` would
  stage it into the first commit.
- Move `Visitor Management System Product Configuration.pdf`,
  `register-type-group.txt`, and `register-type-individual.txt` out of the repo
  root (or gitignore them) — root-level scratch/reference files with no place in
  version control.
- Fix the local, gitignored `.env` (not `.env.example` — that file is already
  correct and complete against `core/config.py`'s `Settings`): rename its stale
  `DEFAULT_ORGANIZATION_SLUG` key to `DEFAULT_TENANT_SLUG` (the real field is
  `settings.default_tenant_slug`, confirmed in `core/config.py:26` and consumed
  in `invitations/deps.py:33`) and add the settings `.env` is missing
  (`GLOBAL_SCHEMA_NAME`, `TENANT_SCHEMA_PREFIX`, `STORAGE_ROOT`, the `SMTP_*`
  group, `SMS_GATEWAY_BASE_URL`/`SMS_GATEWAY_API_KEY`/`SMS_FROM_NUMBER`,
  `INVITATION_TOKEN_TTL_HOURS`, `INVITATION_MAX_UPLOAD_SIZE_BYTES`,
  `INVITATION_MAX_GROUP_VISITORS`). This is a local dev-environment correctness
  fix, not a commit-readiness item (`.env` is gitignored and untracked either
  way) — every field has a code-level default so nothing is currently broken,
  but the stale key is worth fixing while already in the file.
- Add missing `__init__.py` to `src/vmss_api/platform/` and
  `src/vmss_api/reports/` — every other feature package has one; these two
  currently resolve only as implicit namespace packages.
- Move direct `AsyncSession` usage out of `service.py` in the six features where
  it's imported/used there (auth, invitations, org_structure, platform, reports,
  tenant/visitors — confirm exact list during implementation) — into the
  corresponding `repository.py`, per `database-architecture.md` §3's "repository
  is the only layer allowed to import `AsyncSession`."
- Add `selectinload`/`joinedload` to `repository.py` queries in auth,
  org_structure, platform, reports, tenant, and visitors wherever the returned
  model has a relationship the service/response schema touches — currently zero
  eager-load calls across those six files, vs. `invitations/repository.py` which
  already does this correctly (`query-performance.md` §1).
- Evaluate the single-implementation `Protocol`s in
  `src/vmss_api/invitations/notifications.py` (`EmailSender`, `SmsSender`,
  `Attachment`) — keep if there's a concrete near-term second implementation
  (e.g. a real SMS gateway is planned), simplify to a plain class otherwise.
- No change to `.gitignore`/`.aiignore` entries that are already correct; no
  change to `pyproject.toml` dependencies (audit confirmed the full required
  stack is present at the correct versions with no unused additions).

## Capabilities

### New Capabilities

None — this change fixes internal compliance with already-documented standards
and repo hygiene. No new user-facing or API-observable capability is introduced.

### Modified Capabilities

None — no endpoint's request/response contract, status codes, or externally
observable behavior changes. The `AsyncSession`-placement and eager-loading fixes
are internal refactors (same query results, fewer round trips); the
gitignore/env/`__init__.py`/file-location fixes are repo hygiene. Per this
schema's own guidance, a spec describes behavior — since no behavior changes here,
no spec should change either. This change sets `skip_specs: true` in
`.openspec.yaml` accordingly.

## Impact

- **Affected code**: `service.py`/`repository.py` pairs in `auth`, `org_structure`,
  `platform`, `reports`, `tenant`, `visitors`; `src/vmss_api/platform/__init__.py`
  and `src/vmss_api/reports/__init__.py` (new files); `src/vmss_api/invitations/notifications.py`
  (possible simplification only, not required).
- **Affected config**: `.gitignore`, `.env.example`.
- **Affected files at repo root**: relocation of the product-config PDF and the
  two `register-type-*.txt` sample payload files.
- **No dependency changes**: `pyproject.toml`/`uv.lock` already match the
  required stack; no package additions or removals.
- **No test-visible behavior change**: existing `pytest` suite (auth 20,
  invitations 31, org_structure 78, platform 8, reports 3, tenant 3, visitors 25
  tests) must stay green throughout; the eager-loading and session-placement
  refactors are required to be behavior-preserving, verified by the existing
  suite rather than new test cases.
