from django.apps import AppConfig


class OtzarConfig(AppConfig):
    name = "otzar"

    def ready(self):
        # Registers the system checks.
        from otzar import checks  # noqa: F401
