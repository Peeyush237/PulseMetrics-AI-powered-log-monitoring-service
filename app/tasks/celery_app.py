from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "pulsemetrics",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ingestion_tasks",
        "app.tasks.rule_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.maintenance_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

celery_app.conf.beat_schedule = {
    "evaluate-rules-every-30s": {
        "task": "app.tasks.rule_tasks.evaluate_all_rules",
        "schedule": 30.0,
    },
    "maintain-partitions-daily": {
        "task": "app.tasks.maintenance_tasks.maintain_partitions",
        "schedule": crontab(hour=2, minute=0),
    },
    "drop-expired-logs-daily": {
        "task": "app.tasks.maintenance_tasks.drop_expired_logs",
        "schedule": crontab(hour=3, minute=0),
    },
}
