## 1. Repo Hygiene (gitignore, root files)

- [x] 1.1 Add `var/` to `.gitignore` as a top-level entry.
- [x] 1.2 Run `git status`/`git ls-files` to confirm nothing under `var/` is
      currently tracked or staged; if anything is, `git restore --staged` it.
- [x] 1.3 Grep `docs/`, `README.md`, and any tracked `.md` file for references
      to `Visitor Management System Product Configuration.pdf`,
      `register-type-group.txt`, and `register-type-individual.txt`.
- [x] 1.4 Move the PDF into `docs/`; for each `.txt` file, either move it under
      `docs/features/` if it documents a real request shape worth keeping, or
      delete it if it's disposable scratch payload data — update any
      references found in 1.3.
- [x] 1.5 Re-run `git status` to confirm repo root now only has expected,
      trackable files.

## 2. Local Dev Config Fix

- [x] 2.1 In the local `.env` (gitignored, not committed), rename
      `DEFAULT_ORGANIZATION_SLUG` to `DEFAULT_TENANT_SLUG`.
- [x] 2.2 Add the settings missing from `.env` that `.env.example` already
      documents: `GLOBAL_SCHEMA_NAME`, `TENANT_SCHEMA_PREFIX`, `STORAGE_ROOT`,
      `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
      `SMTP_USE_TLS`, `SMTP_FROM_ADDRESS`, `SMS_GATEWAY_BASE_URL`,
      `SMS_GATEWAY_API_KEY`, `SMS_FROM_NUMBER`, `INVITATION_TOKEN_TTL_HOURS`,
      `INVITATION_MAX_UPLOAD_SIZE_BYTES`, `INVITATION_MAX_GROUP_VISITORS`.
- [x] 2.3 Confirm the app still boots locally against the corrected `.env`.

## 3. Missing Package Markers

- [x] 3.1 ~~Add `src/vmss_api/platform/__init__.py`~~ — already exists
      (0-byte marker, same as every other feature). Original audit finding
      was a false positive; no change made.
- [x] 3.2 ~~Add `src/vmss_api/reports/__init__.py`~~ — already exists, same
      as above.
- [x] 3.3 Confirmed via the pre-change baseline `pytest` run (186 passed) —
      import resolution was never actually broken.

## 4. `AsyncSession` Layering — auth

- [x] 4.1 Read `auth/service.py`'s `AsyncSession` usage; classify each as
      either a real query (violation) or a pass-through `Depends()` type only
      (not a violation, per design.md Decision 2). **Result: every usage is a
      pass-through to a `Repository(tenant_db)` constructor, or
      `add()`/`flush()`/`commit()`/`rollback()` for cross-repository
      transaction control. Zero raw `select()`/`.execute()` calls. No
      violation.**
- [x] 4.2 N/A — no real violation found; no code moved.
- [x] 4.3 No code changed; covered by the pre-change baseline `pytest` run
      (186 passed, `auth/tests.py`'s 20 included).

## 5. `AsyncSession` Layering — org_structure

- [x] 5.1 Repeat 4.1's classification for `org_structure/service.py`. **Same
      result: extensive `add()`/`flush()`/`commit()` for building
      multi-row entity trees (branch → building → floor → department/desk/gate),
      zero raw `select()`/`.execute()`. No violation.**
- [x] 5.2 N/A — no real violation found.
- [x] 5.3 No code changed; covered by baseline (78 tests).

## 6. `AsyncSession` Layering — platform

- [x] 6.1 Repeat 4.1's classification for `platform/service.py`. Confirmed
      the one `execute()` at line 41 (`_create_schema`) is the documented
      DDL-provisioning exception, not a domain-table query. Every other usage
      is pass-through/transaction-control. No violation.
- [x] 6.2 N/A — no real violation found (the documented exception is
      intentionally left as-is).
- [x] 6.3 No code changed; covered by baseline (8 tests).

## 7. `AsyncSession` Layering — reports

- [x] 7.1 Repeat 4.1's classification for `reports/service.py`. **Single
      function, passes `tenant_db` straight into `BranchRollupRepository`,
      never queries directly. No violation.**
- [x] 7.2 N/A — no real violation found.
- [x] 7.3 No code changed; covered by baseline (3 tests).

## 8. `AsyncSession` Layering — tenant

- [x] 8.1 Repeat 4.1's classification for `tenant/service.py`. **`tenant/service.py`
      does not import or use `AsyncSession` at all** — the original audit's
      inclusion of `tenant` in this finding was inaccurate.
- [x] 8.2 N/A — nothing to move.
- [x] 8.3 No code changed; covered by baseline (3 tests).

## 9. `AsyncSession` Layering — visitors

- [x] 9.1 Repeat 4.1's classification for `visitors/service.py`. **Same
      add/flush/commit-only pattern as auth/org_structure. No violation.**
- [x] 9.2 N/A — no real violation found.
- [x] 9.3 No code changed; covered by baseline (25 tests).

## 10. Eager-Loading / N+1 Fixes

- [x] 10.1 For each of `auth/repository.py`, `org_structure/repository.py`,
      `platform/repository.py`, `reports/repository.py`,
      `tenant/repository.py`, `visitors/repository.py`: cross-reference each
      `select()` statement's model against that model's relationships
      (`models.py`) and what the corresponding service method or response
      schema actually accesses. **Findings:**
      - `org_structure`, `platform`, `tenant`, `visitors` models declare
        **zero** `relationship()` attributes — every cross-entity link is a
        plain FK column, joined explicitly in SQL. Nothing to eager-load.
      - `reports/repository.py` returns either plain aggregate `dict`s or
        `Branch` rows accessed only for scalar columns. Nothing to
        eager-load.
      - `auth/models.py` does declare real relationships genuinely accessed
        downstream (`router.py:65-73`, `134` → `user.branch_roles`,
        `assignment.role.name`), but they're already covered by
        **mapper-level `lazy="selectin"`** on `Role.permissions`
        (`models.py:65-66`), `User.branch_roles` (`models.py:93`), and
        `UserBranchRole.role` (`models.py:135`) — confirmed by direct read.
        This eager-loads on every query against those mappers regardless of
        the `select()` shape, so no query-level `selectinload()` is needed.
- [x] 10.2 No `selectinload`/`joinedload` calls added — none of the 6
      repository files have a genuine gap. Adding one anywhere would be the
      defensive over-eager-loading the design explicitly ruled out (Decision 3).
- [x] 10.3 No code changed here; the pre-change baseline `pytest` run
      (186 passed, zero `MissingGreenlet` errors) already confirms current
      behavior is correct.

## 11. Final Gate

- [x] 11.1 `ruff check .` — all checks passed.
- [x] 11.2 `ruff format --check .` — 173 files already formatted.
- [x] 11.3 `mypy src/vmss_api/core src/vmss_api/auth` — success, no issues
      (under the mypy config that actually exists in `pyproject.toml` today;
      see note below — that config doesn't yet turn on `strict = true` for
      these packages despite `project-rules.md` documenting that it should).
- [x] 11.4 Full `ddev exec uv run pytest` — **186 passed.** One regression
      was caught and fixed here: task 2.2's `.env` edit initially set
      `SMTP_USERNAME=`/`SMTP_PASSWORD=` to empty strings, which
      `pydantic-settings` parses as `""` rather than falling back to the
      `None` default — `invitations/notifications.py`'s `SmtpEmailSender`
      then attempted an authenticated SMTP login with blank credentials,
      which mailpit rejects (`test_send_visit_confirmation_delivers_email_with_qr_via_mailpit`
      failed). Fixed by leaving those two keys unset in `.env` instead of
      empty; suite is back to green.
- [x] 11.5 Final `git status`/`git add -A --dry-run` review — confirmed no
      `.env`, `__pycache__`, or `var/` content appears in staged output.

**Discovered, out-of-scope findings** (not fixed here — beyond this change's
approved scope, flagged for a follow-up decision):
- `pyproject.toml`'s `[tool.mypy]` has no `strict = true` override for
  `core`/`auth` as `project-rules.md` documents policy-wise; running
  `mypy --strict` on those two packages surfaces 9 real errors (mostly
  missing return-type annotations in `core/middleware.py`, `core/tenancy.py`,
  and two test helpers in `auth/tests.py`, plus one in root `factories.py`).
- `.env.example` has the same latent `SMTP_USERNAME=`/`SMTP_PASSWORD=`
  empty-string landmine this task just fixed locally — anyone who
  `cp .env.example .env` for onboarding will hit the same SMTP AUTH failure
  the moment they exercise the email-notification path against a
  non-AUTH mail catcher.
