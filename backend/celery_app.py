"""Celery application configuration."""

import os

from celery import Celery

redis_url = os.getenv("REDIS_QUEUE_URL") or os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "clothes_design",
    broker=redis_url,
    backend=redis_url,
    include=[
        "worker.celery_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    result_expires=3600,
    result_extended=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.task_routes = {
    "worker.tasks.analyze": {"queue": "analyze"},
    "worker.tasks.generate": {"queue": "generate"},
    "worker.tasks.upscale": {"queue": "upscale"},
    "worker.tasks.vectorize": {"queue": "vectorize"},
    "worker.tasks.mockup": {"queue": "mockup"},
    "worker.tasks.export_pattern": {"queue": "export"},
}

celery_app.conf.task_default_queue = "default"
