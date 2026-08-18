from celery import Celery

from vmss_api.core.config import settings

celery_app = Celery(
    "vmss_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_default_queue = "vmss_api"

# Feature task modules register themselves here as they're built.
celery_app.autodiscover_tasks(["vmss_api.invitations"])
