from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookstore.settings")

app = Celery("bookstore")

# Using a string here means the worker does not have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):  # type: ignore[override]
    print(f"Request: {self.request!r}")
