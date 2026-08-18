## Context

See `proposal.md` - Why for motivation. This design covers a first-commit audit
across every feature package (`auth`, `invitations`, `org_structure`, `platform`,
`reports`, `tenant`, `visitors`) plus repo-root hygiene. The audit (already run,
findings summarized below) found the codebase largely compliant already — no
missing dependencies, no camelCase leakage, no missing `response_model`, no
`print()`/ad-hoc logging, every feature has tests. The remaining findings are
narrow and mechanical:

- `platform/` and `reports/` are missing `__init__.py`.
- `var/` (local upload storage, 439 files) is untracked and unmatched by
  `.gitignore` — would be staged into the first commit as-is.
- The product-config PDF and two `register-type-*.txt` sample payloads sit at
  repo root with no `.gitignore` coverage.
- `service.py` imports/uses `AsyncSession` directly in 6 of 7 feature packages
  (`invitations` is the one exception — it stays fully behind its repository).
- Those same 6 `repository.py` files have zero `selectinload`/`joinedload`
  calls across 38 combined `select()` statements — a potential N+1/`MissingGreenlet`
  risk *only* where the returned model has a relationship a service or response
  schema actually touches.
- `invitations/notifications.py` has three `Protocol`s (`EmailSender`,
  `SmsSender`, `Attachment`) each with exactly one concrete implementation today.
- `.env` (local, gitignored) has a stale key name and is missing several
  settings that `.env.example` already documents correctly.

## Goals / Non-Goals

**Goals:**
- Make the first commit clean: nothing untracked-but-unwanted gets staged, no
  packaging gap, no documented-standard violation introduced at the start.
- Fix the `AsyncSession`-in-service and missing-eager-load findings **only**
  where they're real — i.e., verify each repository method's returned model
  actually has a relationship touched downstream before adding
  `selectinload`/`joinedload`, and verify each `service.py` `AsyncSession` usage
  is actually a query (not, say, a type-only import or a `Depends` annotation
  passed straight through to a repository constructor) before moving code.
- Keep every change behavior-preserving: same request/response contracts, same
  query results, same status codes. The full `pytest` suite is the acceptance
  gate, not new test cases (no behavior is being added).

**Non-Goals:**
- Not rewriting or renaming anything beyond what the findings above name.
  No speculative refactors "while we're in there."
- Not resolving the `notifications.py` `Protocol` question by deleting the
  abstraction outright — see Decisions below, it's a judgment call with a
  cheap default, not a forced removal.
- Not touching `pyproject.toml`/`uv.lock` — the dependency audit found no gap.
- Not adding new tests for the AsyncSession/eager-load refactors — they're
  required to be behavior-preserving under the *existing* suite, which already
  covers each feature's endpoints (`testing-standards.md` §2's happy-path,
  permission-denied, and tenant-isolation cases are already present per-feature).

## Decisions

**1. Fix `.gitignore` before the first `git add`, not after.**
Add `var/` as its own top-level entry (matches the existing style of other
storage/artifact ignores already in the file) rather than a narrower pattern
like `var/storage/*/invitations/id-proof/` — the whole `var/` tree is local
runtime state (uploads, generated files), not something any tenant/environment
should ever commit, so a broad ignore is correct here, not over-scoped.
Move the PDF and two `.txt` sample-payload files out of repo root into
`docs/` (the PDF is product reference material — closest existing home is
`docs/`) and delete the two `.txt` files if they're scratch payloads no longer
needed for reference, or move them under `docs/features/` if they document a
real request shape worth keeping. Confirm which with a quick content check
during implementation rather than guessing.

**2. `AsyncSession`-in-`service.py`: move only where it's a real query, not every match.**
Alternative considered: blanket-move every `AsyncSession`-typed parameter out of
every `service.py` regardless of what it's used for. Rejected — some of those
12 matches may just be a type import for a `Depends()`-annotated parameter that
the service immediately hands to its repository's constructor, which is the
correct pattern (`repository.py` still does the actual querying) and not a
violation. The real violation is a `service.py` calling `session.execute(...)`
or `select(...)` directly. Each of the 6 flagged files needs a quick read to
classify before touching anything — expected outcome is that most or all
*are* real violations given `database-architecture.md` §3 is unambiguous, but
verify rather than assume for all 6.

**3. Eager-loading: add only where a relationship is actually accessed downstream.**
Alternative considered: add `selectinload`/`joinedload` defensively to every
`select()` in the 6 flagged repositories. Rejected as over-engineering in the
other direction — `query-performance.md` §1's own rule is conditional ("if a
repository method returns a model whose relationship the service or response
schema will touch"), not universal. A `select()` against a model with no
relationships, or one where only scalar columns are read downstream, needs no
change. Implementation must check each model's relationship attributes
(`models.py`) against what the corresponding service method and response
schema actually access before adding an eager-load clause — this also
determines `selectinload` (one-to-many/many-to-many) vs. `joinedload`
(many-to-one/one-to-one) per query, per the same rule.

**4. `notifications.py` Protocols: keep, don't collapse — but flag as a
watch item, not a fix.**
Alternative considered: collapse `EmailSender`/`SmsSender`/`Attachment` into
plain concrete classes since each has one implementation today. Rejected as
the action for *this* change — `SmsSender` exists specifically because a real
second implementation (an actual SMS gateway, currently
`UnconfiguredSmsSender` which just raises) is a known near-term addition per
`security-architecture.md` §2's SMS/OTP requirements and the referenced
`add-pre-registration` change's own open questions. Collapsing it now would
mean re-introducing the abstraction within one or two changes. This is
recorded as a design note, not a task — no code change here.

**5. `.env` fix is out-of-band from the commit-readiness goal but cheap to
include.**
`.env` is gitignored and was never going to be committed either way, so this
finding doesn't block "make the first commit clean." It's included as a task
anyway since it's a one-file, low-risk fix already surfaced by the same audit
pass, and leaving a known-stale local config lying around is exactly the kind
of thing that's cheap to fix now and easy to forget later.

## Risks / Trade-offs

- [Risk] Moving `AsyncSession` usage from `service.py` into `repository.py`
  changes call signatures between the two layers → Mitigation: change the
  repository's public method signature to accept the same business-level
  arguments it does today (no session parameter added to its public API,
  since the repository already holds `self.session` from construction per
  `database-architecture.md` §3) — the service call site simplifies to calling
  the repository method directly instead of building a query itself. Run the
  full per-feature test file after each feature's refactor before moving to
  the next, so a regression is caught against one feature, not discovered
  after all six are touched.
- [Risk] Adding eager-loading to a query that's called from a hot path (e.g. a
  paginated list endpoint) could increase query cost if applied too broadly
  (e.g. `joinedload` on a one-to-many by mistake, causing row fan-out) →
  Mitigation: Decision 3's per-model relationship check, and matching
  `selectinload` to one-to-many/many-to-many vs. `joinedload` to
  many-to-one/one-to-one per `query-performance.md` §1's explicit rule.
- [Risk] Relocating the root-level PDF/`.txt` files could break a link or
  reference elsewhere (docs, README) that points at the old root path →
  Mitigation: grep for references to the three filenames across `docs/`,
  `README.md`, and any `.md` file before moving, and update any hit.
- [Risk] `var/` being newly gitignored doesn't retroactively untrack it if any
  of those 439 files were already `git add`ed in a prior local experiment →
  Mitigation: confirm via `git status`/`git ls-files` that nothing under `var/`
  is currently staged or tracked before relying on `.gitignore` alone; if
  something is already staged, `git restore --staged` it first.

## Migration Plan

Sequential, each step independently verifiable, no step requires the others to
be in-flight simultaneously:

1. `.gitignore` fix (`var/`) + root-file relocation — verify with `git status`.
2. `.env` local fix — verify the app still boots locally (`ddev exec uv run
   uvicorn ...` or the project's existing dev-run command) — no test coverage
   needed since it's a local-only, gitignored file.
3. Add the two missing `__init__.py` files — verify with `ddev exec uv run
   pytest` (import resolution regressions would surface immediately).
4. Per feature (auth → invitations-skip-already-clean → org_structure →
   platform → reports → tenant → visitors), in any order since they're
   independent: classify `AsyncSession` usage (Decision 2), move real
   violations into `repository.py`, add eager-loading only where Decision 3's
   check confirms it's needed, run that feature's `tests.py` before moving to
   the next feature.
5. Full `ddev exec uv run pytest` + `ruff check` + `ruff format --check` +
   scoped `mypy` (per `project-rules.md`'s strict-typing scope) as the final
   gate before the first commit.

**Rollback**: every step is a local, uncommitted working-tree change up until
the first commit is actually made — rollback is `git diff`/`git checkout` on
the specific file if a step causes a test regression, no deployment or data
migration involved.

## Open Questions

None — the two judgment calls in this audit (the `.txt` files' fate, and
whether all 6 `AsyncSession` matches are real violations) are resolved by a
quick content/read check during implementation (Decisions 1 and 2), not
left open; they don't change the specs, approach, or task breakdown itself.
