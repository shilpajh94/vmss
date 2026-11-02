## Why

Implementing a change request or a small suggestion currently ends with a full
`pytest` run (about 9 minutes) or a full e2e run. Those runs often fail on known,
unrelated flakes, so the extra time tells us little about the change itself. The
user asked for a standing rule: test what the change touched, plus any area that
depends on it, and leave the full run to the CI gate.

## What Changes

- Add a written rule for verifying a change request or suggestion task. It
  replaces the full suite with **targeted tests**:
  - the test modules for each feature package the change edits;
  - the test modules for any other area that imports, calls, or consumes the
    changed code (shared `core/` helpers, schemas, tasks, migrations, response
    shapes the web client reads);
  - `tests/test_api_documentation.py` when the change adds, removes, or registers
    a route or a response schema.
- Say what to do when a `tasks.md` step asks for a "full suite": run the targeted
  set and record in the task note that this was done instead.
- Keep the full suite where it already applies: the CI merge gate
  (`git-workflow.md` §4), and any time the user asks for a full run.
- Put the rule where it is always read: `.claude/rules/testing-standards.md` (new
  §5), the Testing section of `.claude/rules/project-rules.md`, and
  `operations.apply.guidance` in `openspec/config.yaml` so `/opsx:apply` sees it.
- Reword `project-rules.md`'s line "All tests must pass before proposing
  significant changes" so it no longer conflicts with the new rule.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `quality-assurance`: adds a requirement that limits verification of a change
  request or suggestion to targeted and dependent tests. The full suite is kept
  for the CI gate and for runs the user asks for.

## Impact

- **Files**: `.claude/rules/testing-standards.md`, `.claude/rules/project-rules.md`,
  `openspec/config.yaml`. No application code, API, database, or dependency
  changes.
- **CI**: no change. The merge gate still runs the full `pytest` suite.
- **Out of scope**: VMMS_WEB. The rule applies there too in practice, but this
  change can only edit VMSS_API. Adding the same guidance to
  `VMMS_WEB/openspec/config.yaml` is a separate follow-up.
