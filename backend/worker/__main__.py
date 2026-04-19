#!/usr/bin/env python
"""Celery worker entrypoint.

Usage:
    python -m worker

Or from backend directory:
    cd backend && python -m worker
"""

import sys
from pathlib import Path

# Add backend to path if running from backend/worker directly
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from celery_app import celery_app
import worker.celery_tasks  # noqa: F401

if __name__ == "__main__":
    celery_app.worker_main(
        argv=[
            "worker",
            "--loglevel=info",
            "--concurrency=4",
            "--max-tasks-per-child=100",
            "--queues=analyze,generate,upscale,vectorize,mockup,export,default",
        ]
    )
