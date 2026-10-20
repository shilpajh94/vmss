## Context

`.ddev/config.yaml`'s `web_extra_daemons` run three processes under supervisor:
`vmss-api` (`uvicorn ... --reload`), `vmss-api-celery-worker` and `vmss-api-celery-beat`
(plain `celery ... worker|beat`). Only uvicorn reloads. Every email is rendered and sent
inside a worker task (`invitations/tasks.py`, `reports/tasks.py`,
`identity_verification/senders.py`, ...). A worker started before a pull therefore keeps
rendering pre-pull templates, settings defaults (`BRAND_NAME`) and logo URLs. This is
the cause of the stale Visimio branding (see proposal.md, Why).

Celery removed its own `--autoreload` in 4.0. `watchfiles` 1.2.0 is already installed
(through `uvicorn[standard]`) and has a CLI that runs a command and restarts it on change.

## Goals / Non-Goals

**Goals:**
- Worker and beat restart on any source change under `src/`, including non-Python
  files (Jinja templates, PNG email assets).
- No new third-party package beyond declaring the one already installed.

**Non-Goals:**
- Production or staging worker supervision. The deployment target is still undecided,
  and those workers must never watch files.
- Replacing a cached `visimio-logo.png` in mail clients. That URL already serves the
  new bytes, and the `immutable` cache trade-off was accepted in `rebrand-to-guestify`
  design.md Decision 5.
- Any change to the email rendering code.

## Decisions

1. **Wrap the existing celery commands with the `watchfiles` CLI.**
   `uv run watchfiles --sigint-timeout 10 '<existing celery command>' src`.
   - Alternative: `watchmedo auto-restart` (watchdog). Rejected because it adds a new
     dependency, while watchfiles is already installed and is what uvicorn's reload uses,
     so we know file events reach this container.
   - Alternative: a git `post-merge` hook that runs `supervisorctl restart`. Rejected
     because it misses uncommitted edits and branch switches, and hooks are per-clone and
     easy to skip.
   - Alternative: keep documenting a manual restart. Rejected because it has already
     failed twice.

2. **Default filter, not `--filter python`.** The stale-branding bug came from `.html`/`.txt`
   templates and a `.png` asset as much as from `.py`. watchfiles' default filter already
   ignores `__pycache__`, `.git`, editor swap files and similar noise.

3. **Watch `src/` only.** Not the repo root: `alembic*/`, `tests/`, `openspec/` and the
   celery beat schedule files (`celerybeat-schedule*`, written at the repo root by beat
   itself) would cause spurious restarts or a restart loop.

4. **`--sigint-timeout 10`.** watchfiles stops the child with SIGINT, which Celery treats
   as a warm shutdown (finish in-flight tasks). After the timeout it sends SIGKILL. 10 s
   covers a normal email send. A task killed mid-run is redelivered, and task bodies are
   idempotent by the existing `background-jobs` requirement.

5. **Declare `watchfiles` as a dev dependency** (`uv add --dev watchfiles`). This keeps
   the local daemon working if uvicorn's extras ever change. Not a runtime dependency,
   since deployed workers don't use it.

## Risks / Trade-offs

- [Burst of saves or a `git pull` touching many files triggers several restarts] →
  watchfiles debounces changes (default 1.6 s step) into one restart.
- [Restart while a long task such as a report export runs] → the task is SIGKILLed after
  10 s and redelivered. Acceptable locally, and tasks are idempotent.
- [Two worker generations briefly overlap] → watchfiles waits for the old child to exit
  before starting the new one, so they don't overlap.
- [Container file events not delivered (e.g. a Windows-filesystem mount)] → the repo
  lives on the WSL Linux filesystem, where uvicorn `--reload` already works. If events
  ever stop, the manual `supervisorctl restart` still works as a fallback.

## Migration Plan

1. Edit `.ddev/config.yaml`, then run `ddev restart`. Supervisor config is generated at
   container start, so a plain daemon restart won't pick up the new command.
2. Rollback: revert the two `command:` lines and run `ddev restart`.
