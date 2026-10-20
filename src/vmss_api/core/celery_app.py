import os

from celery import Celery
from celery.schedules import crontab

from vmss_api.core.config import settings

notification_queue = os.getenv(
    "CELERY_NOTIFICATION_QUEUE",
    "notifications",
)

cron_queue = os.getenv(
    "CELERY_CRON_QUEUE",
    "cron_jobs",
)

default_queue = f"{os.getenv('ENVIRONMENT', 'local')}_vmss_api"


celery_app = Celery(
    "vmss_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.task_default_queue = default_queue

celery_app.conf.task_routes = {
    # Exact names are matched before the glob below, so the visit-lifecycle
    # sweep runs on the cron queue while every other invitations task stays
    # on the notification queue (auto-checkout-and-archive-no-shows D1).
    "vmss_api.invitations.tasks.dispatch_visit_lifecycle_sweep": {
        "queue": cron_queue,
    },
    "vmss_api.invitations.tasks.sweep_tenant_visit_lifecycle": {
        "queue": cron_queue,
    },
    "vmss_api.invitations.tasks.dispatch_invitation_purge": {
        "queue": cron_queue,
    },
    "vmss_api.invitations.tasks.purge_tenant_invitations": {
        "queue": cron_queue,
    },
    "vmss_api.invitations.tasks.*": {
        "queue": notification_queue,
    },
    "vmss_api.notifications.tasks.*": {
        "queue": notification_queue,
    },
    "vmss_api.reports.tasks.*": {
        "queue": cron_queue,
    },
    "vmss_api.audit_trail.tasks.*": {
        "queue": cron_queue,
    },
}


celery_app.autodiscover_tasks(
    [
        "vmss_api.invitations",
        "vmss_api.notifications",
        "vmss_api.reports",
        "vmss_api.audit_trail",
    ]
)


celery_app.conf.beat_schedule = {
    "dispatch-daily-rollup-snapshots": {
        "task": "vmss_api.reports.tasks.dispatch_daily_rollup_snapshots",
        "schedule": crontab(hour=2, minute=0),
    },
    "visit-lifecycle-sweep": {
        "task": "vmss_api.invitations.tasks.dispatch_visit_lifecycle_sweep",
        "schedule": crontab(minute="*/15"),
    },
    "invitation-retention-purge": {
        "task": "vmss_api.invitations.tasks.dispatch_invitation_purge",
        "schedule": crontab(
            hour=settings.invitation_purge_hour, minute=settings.invitation_purge_minute
        ),
    },
}
