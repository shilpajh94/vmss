from celery import Celery
from celery.schedules import crontab

from vmss_api.core.config import settings

celery_app = Celery(
    "vmss_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_default_queue = "vmss_api"

# CI-CD/k8s.yml runs two dedicated worker Deployments, each pinned to one
# queue via `-Q` (celery-worker-notifications -> "notifications",
# celery-worker-cron -> "cron_jobs") — neither consumes the default
# "vmss_api" queue. Without these routes, tasks enqueued via `.delay()` land
# in "vmss_api" and sit unconsumed in Redis forever on the deployed
# environment (no error, nothing in worker logs), even though the local
# ddev worker picks them up fine since it listens on every queue.
celery_app.conf.task_routes = {
    "vmss_api.invitations.tasks.*": {"queue": "notifications"},
    "vmss_api.reports.tasks.*": {"queue": "cron_jobs"},
}

# Feature task modules register themselves here as they're built.
celery_app.autodiscover_tasks(["vmss_api.invitations", "vmss_api.reports"])

# Recurring, time-triggered tasks (background-jobs.md, the `background-jobs`
# capability's "Scheduled Tasks Run Independently of Any Request"
# requirement). Requires the `vmss-api-celery-beat` daemon
# (`.ddev/config.yaml`) running alongside the worker — beat only enqueues on
# schedule, it never executes a task itself.
celery_app.conf.beat_schedule = {
    "dispatch-daily-rollup-snapshots": {
        "task": "vmss_api.reports.tasks.dispatch_daily_rollup_snapshots",
        "schedule": crontab(hour=2, minute=0),
    },
}
