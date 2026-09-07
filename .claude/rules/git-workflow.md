---
trigger: model_decision
description: Apply when writing a commit message, opening or describing a pull request, or discussing the merge/CI gate process.
---

# Git Workflow & CI Gate — VMSS_API

Nothing in the other rule files covers commit/branch/PR conventions or what must
pass before merge; this fills that gap.

## 1. Commit Messages

Conventional Commits style: `<type>: <summary>`, types limited to `feat`, `fix`,
`refactor`, `test`, `docs`, `chore`, `perf`. Body explains *why* when the diff
alone doesn't make it obvious (same bar as code comments — don't restate the diff).
This keeps `git log` scannable for "what changed and why" without opening every
commit, and is a prerequisite if changelog generation is ever automated later.

## 2. Branch Naming

`<type>/<short-description>`, e.g. `feat/visitor-checkin-otp`,
`fix/tenant-leak-in-reports`. Matches the commit `type` vocabulary in §1.

## 3. PR Checklist

Before requesting review, confirm:
- `ruff check` and `ruff format --check` clean.
- `mypy` clean on any module touched under `core/`, `auth/`, or anything handling
  money/PII (`project-rules.md`'s strict-typing scope).
- `pytest` green, including the permission-denied and tenant-isolation cases
  required by `testing-standards.md` §2 for any new/changed endpoint.
- New or changed endpoints have a corresponding update in `docs/features/` and, if
  the change is breaking, follows the versioning/deprecation rule in
  `api-conventions.md` §2.

## 4. CI Gate

Merge to main requires, at minimum: lint (`ruff check`), format check
(`ruff format --check`), type check (scoped per §3), and the full `pytest` suite —
all green. No merging on red CI, no `--no-verify`/skipped hooks to force a merge
through. If CI itself is broken (not the change under review), fix or roll back
the pipeline rather than bypassing it for one PR.

## 5. Commit Exclusion List

A broad/automated `git add` (including one Claude Code runs as part of the
commit workflow) must **never** stage these files. They require an explicit,
deliberate manual commit instead:

- `.env`, `.env.local`, and any other local dotenv override file — the dev
  server checks these out as `_PLACEHOLDER_` and injects real values at
  runtime, so a local edit to one is dev-machine state, not something to ship.
- `.gitignore` — changed only when a developer deliberately decides to change
  what git ignores, never as a side effect of staging an unrelated change.
- `celerybeat-schedule-shm`, `celerybeat-schedule-wal` — Celery beat's SQLite
  scheduler shadow files. Runtime-generated on the local machine, not source.

If one of these files shows as modified in `git status` during a commit, leave
it unstaged (per §6 below for `.env` specifically) and mention it to the user
rather than including it.

## 6. `.env` → `.env.example` Sync

When a commit would otherwise include a new or changed key in `.env`, do not
stage `.env`. Instead, add or update that key in `.env.example` with a
`_PLACEHOLDER_` (or equivalent safe, non-functional example) value, and stage
`.env.example` in its place. This keeps `.env.example` — the file that's
actually committed and reviewed — in sync with every setting the application
reads, per `database-architecture.md` §8 and `project-rules.md`'s Secret
Management section, without ever exposing a real local value.
