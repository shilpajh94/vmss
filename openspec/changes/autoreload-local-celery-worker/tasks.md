## 1. Dependency

- [x] 1.1 `ddev exec uv add --dev watchfiles` and confirm `uv.lock` keeps watchfiles 1.2.x (no unrelated upgrades)

## 2. DDEV daemons

- [x] 2.1 In `.ddev/config.yaml`, change `vmss-api-celery-worker`'s command to `uv run watchfiles --sigint-timeout 10 'celery -A vmss_api.core.celery_app:celery_app worker --loglevel=info -Q vmss_api,notifications,cron_jobs' src`
- [x] 2.2 Change `vmss-api-celery-beat`'s command the same way (`'celery -A vmss_api.core.celery_app:celery_app beat --loglevel=info'`, watching `src`)
- [x] 2.3 Update the comments above both daemons: why they watch `src/` with the default filter (templates/assets, not just `.py`) and why not the repo root (beat schedule files)
- [x] 2.4 `ddev restart`, then confirm `supervisorctl status` shows all three daemons RUNNING and the worker log shows the `-Q` queues and the task list

## 3. Verify (design.md Decisions 1–4)

- [x] 3.1 Trigger a real worker-sent email (e.g. submit a visit request) and confirm in Mailpit: From `Guestify`, header `<img>` points at `guestify-logo.png`, no "Visimio" anywhere in the HTML/text parts
- [x] 3.2 Make a throwaway edit to `src/vmss_api/core/email_templates/base.html`, confirm the worker log shows a restart within a few seconds and the next email reflects the edit, then revert the edit
- [x] 3.3 Make a throwaway `.py` edit under `src/vmss_api/` and confirm beat restarts too, then revert
- [x] 3.4 Confirm editing a file outside `src/` (e.g. `tests/`) causes no restart, and that beat writing `celerybeat-schedule*` does not trigger a restart loop

## 4. Docs

- [x] 4.1 `docs/features/background-jobs.md`: update the daemon table's worker/beat commands and note they auto-restart locally
- [x] 4.2 `README.md` (Running the app section): note worker/beat auto-reload, keep `supervisorctl restart webextradaemons:vmss-api-celery-worker` only as the fallback

## 5. Checks

- [ ] 5.1 `ruff check`, `ruff format --check` clean; `ddev exec uv run pytest` shows no new failures compared with the pre-change baseline (no app code changed)
- [x] 5.2 Do not stage `.env` or `celerybeat-schedule-*` files (git-workflow.md §5)
