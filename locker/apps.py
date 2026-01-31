from django.apps import AppConfig


class LockerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "locker"

    # necessary for django to recognize organizer_admin
    def ready(self):
        import locker.organizer_admin # noqa: F401
