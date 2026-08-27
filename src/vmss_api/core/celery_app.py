from celery import Celery
from celery.schedules import crontab

from vmss_api.core.config import settings

celery_app = Celery(
    "vmss_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_default_queue = "vmss_api"

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
