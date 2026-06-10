from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "quotebot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_routes={
        "app.workers.tasks.process_item": {"queue": "items"},
        "app.workers.tasks.process_request": {"queue": "requests"},
        "app.workers.tasks.finalize_request": {"queue": "requests"},
        "app.workers.tasks.poll_email": {"queue": "email"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "poll-company-inbox": {
            "task": "app.workers.tasks.poll_email",
            "schedule": crontab(minute=f"*/{settings.poll_interval_minutes}"),
        },
    },
)
