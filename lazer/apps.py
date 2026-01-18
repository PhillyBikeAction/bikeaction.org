from django.apps import AppConfig


class LazerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lazer"

    def ready(self):
        import lazer.signals  # noqa: F401
        from lazer.utils import _get_yolo_model

        _get_yolo_model()
