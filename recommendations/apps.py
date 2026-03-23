from django.apps import AppConfig


class RecommendationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recommendations"

    def ready(self) -> None:  # type: ignore[override]
        # Import signal handlers
        from . import signals  # noqa: F401
        return super().ready()
