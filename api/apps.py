from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        # Connect the cache-invalidation signal handlers.
        from api import signals  # noqa: F401
