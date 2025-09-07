from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "campaigns"

    def ready(self):
        # Import Wagtail models to ensure they're registered
        from . import wagtail_models  # noqa: F401
