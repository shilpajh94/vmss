## 1. Document the commit exclusion policy

- [x] 1.1 In `.claude/rules/git-workflow.md`, add a "Commit Exclusion List"
      section listing files that must never be staged by a broad/automated
      `git add` and instead require an explicit, deliberate manual commit:
      `.env`, `.env.local` (and any other local dotenv override file),
      `.gitignore`, `celerybeat-schedule-shm`, `celerybeat-schedule-wal`.
- [x] 1.2 In the same file, add an "`.env` → `.env.example` Sync" section:
      when a commit would otherwise include a new or changed key in `.env`,
      add/update that key in `.env.example` with a `_PLACEHOLDER_` (or
      equivalent safe, non-functional) value instead, and stage
      `.env.example` in place of `.env`.
- [x] 1.3 State explicitly that `.gitignore` changes are committed manually
      by the developer when needed, never as a side effect of staging an
      unrelated change.

## 2. Untrack Celery beat scheduler shadow files

- [x] 2.1 Confirm `celerybeat-schedule-shm` and `celerybeat-schedule-wal`
      are listed in `.gitignore` (already present) — no `.gitignore` edit
      needed.
- [x] 2.2 Run `git rm --cached celerybeat-schedule-shm celerybeat-schedule-wal`
      so they stop showing as tracked/modified, while leaving the local
      files on disk untouched.

## 3. Reconcile the currently pending working tree

- [x] 3.1 Diff the current `.env` against `.env.example`; for any key present
      or changed in `.env` but missing/stale in `.env.example`, add it there
      with a placeholder value per task 1.2's rule. Result: every key in
      `.env` already exists in `.env.example` — no keys to add.
- [x] 3.2 Leave `.env`, `.env.local`, and `.gitignore` unstaged per the new
      policy (commit them manually only if the developer decides to). All
      three were already unstaged; confirmed none were added.
- [x] 3.3 Verify `git status` after tasks 2.2–3.2: only `.env.example`,
      `.claude/rules/git-workflow.md`, and any other genuinely
      source-relevant changes remain staged/pending — `.env`, `.gitignore`,
      and the celerybeat shadow files are no longer offered for commit.
      Confirmed: `git status` shows the two celerybeat files staged for
      deletion (untracking), and `.env`/`.gitignore`/`.env.local` are
      unstaged/untracked, not offered for commit.
