from __future__ import annotations

from celery import shared_task

from .engine import generate_recommendations


@shared_task
def update_all_recommendations() -> None:
    """Celery task wrapper to recompute recommendations for all users."""

    generate_recommendations()
