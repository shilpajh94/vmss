## Context

The guidance on testing is spread across files that load at different times:

- `.claude/rules/testing-standards.md` has `trigger: glob` on test files. It loads
  only when a test file is being edited, not when the agent decides what to run.
- `.claude/rules/project-rules.md` has `trigger: always_on`. Its Testing section
  says "All tests must pass before proposing significant changes", which reads as
  "run the full suite".
- `openspec/config.yaml` has no `operations.apply.guidance`. `/opsx:apply` gets no
  project-specific guidance on testing.
- `.claude/rules/git-workflow.md` §3 and §4 cover the PR checklist and the CI
  gate. Both are about merging, not about implementing a change.

## Goals / Non-Goals

**Goals:**
- The rule is in context at the moment of choosing which tests to run, whichever
  way the change is being implemented (`/opsx:apply` or a plain request).
- One full statement of the rule, with short pointers to it from the other places.
  This avoids three copies drifting apart.

**Non-Goals:**
- No change to the CI gate, the PR checklist, or what a feature's tests must cover
  (`testing-standards.md` §2).
- No script that works out the dependent test set automatically. Choosing it
  stays a judgment call, made by tracing imports and consumers.

## Decisions

1. **The full rule goes in `testing-standards.md` as new §5, "Test scope while
   implementing a change".** That file already owns "what tests to run and
   why". Because it is glob-triggered, the always-loaded places point to it:
   - `project-rules.md` Testing: replace "All tests must pass before proposing
     significant changes" with a short summary of the rule and a link to
     `testing-standards.md` §5. State that the full suite is the CI gate's job.
   - `openspec/config.yaml`: add `operations.apply.guidance` entries that state
     the rule in brief, so `/opsx:apply` sees it without loading a rules file.

   *Considered:* a new always-on rules file. Rejected because it would split
   testing guidance across two files for one paragraph of content.
   *Considered:* changing `testing-standards.md` to `trigger: always_on`.
   Rejected because that loads factory and coverage guidance into every session.

2. **How to find dependent areas.** Search for imports of the changed module or
   symbol (`grep -rn "from vmss_api.<feature>"` and similar) and follow the
   consumers: Celery tasks, schemas reused by other features, tenant migrations,
   response shapes the web client reads. If no other area depends on the changed
   code, run only the change's own feature tests.

3. **Targeted runs stay sequential.** One `ddev exec uv run pytest <paths>`
   invocation, never parallel processes, because they race on the shared test DB.

## Risks / Trade-offs

- [A regression in an area nobody traced is missed locally] → The CI gate still
  runs the full suite before merge. The verification report names the dependent
  areas that were included, so a reviewer can spot one that is missing.
- [Older `tasks.md` files still say "run the full suite"] → The rule says how to
  handle that: run the targeted set and note the substitution. Existing change
  files are not rewritten.
