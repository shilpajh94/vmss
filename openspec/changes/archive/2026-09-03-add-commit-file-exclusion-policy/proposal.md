## Why

The dev server injects real secrets into `.env` at deploy time (the file is
checked out with `_PLACEHOLDER_` values and the real values are supplied by
the environment/library at runtime), so a local `.env` edit should never be
staged for commit — only mirrored into `.env.example` as a placeholder.
Similarly, `.gitignore` and Celery beat's runtime scheduler shadow files
(`celerybeat-schedule-shm`, `celerybeat-schedule-wal`) currently show up as
tracked-and-modified in `git status`, which means past commits (including
automated ones) have staged files that should never have been committed in
the first place, or committed at all. There is currently no documented rule
governing which files an automated commit (Claude Code or a contributor
running a broad `git add`) must exclude, so this keeps recurring.

## What Changes

- Add a new rule to `.claude/rules/git-workflow.md` defining a **commit
  exclusion list** — files that must never be staged by an automated/broad
  `git add`, and instead require an explicit, deliberate manual commit:
  - `.env` (and any other local dotenv override file, e.g. `.env.local`)
  - `.gitignore`
  - `celerybeat-schedule-shm`, `celerybeat-schedule-wal` (Celery beat SQLite
    scheduler shadow files — runtime-generated, not source)
- Add a **`.env` → `.env.example` sync rule**: when a commit would include a
  new or changed key in `.env`, the corresponding key is instead added/updated
  in `.env.example` with a safe placeholder value (`_PLACEHOLDER_` or an
  equivalent non-functional example), and `.env.example` is staged in place
  of `.env`.
- Untrack `celerybeat-schedule-shm` and `celerybeat-schedule-wal` from git
  (`git rm --cached`) — they are already listed in `.gitignore` but remain
  tracked from before that entry was added, so `.gitignore` alone doesn't
  stop them showing up as modified.
- Document that `.gitignore` changes are made manually by the developer when
  needed, never as a side effect of an unrelated commit.

This is a documentation/process and repo-hygiene change — it does not modify
any application runtime behavior, so no capability spec changes.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — this change is process/tooling only; see `skip_specs: true` in
`.openspec.yaml`)

## Impact

- `.claude/rules/git-workflow.md` — new "Commit Exclusion List" and "`.env` →
  `.env.example` Sync" sections.
- Git index — `git rm --cached celerybeat-schedule-shm celerybeat-schedule-wal`
  (files remain on disk, only untracked; already covered by `.gitignore`).
- No application code, API, or schema changes.
