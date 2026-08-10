"""`apps.common` ilovasining konfiguratsiyasi."""

from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    verbose_name = "Umumiy"

    def ready(self) -> None:
        # SQLite uchun WAL rejimi va boshqa PRAGMA sozlamalarini ulaymiz.
        from . import db_pragmas  # noqa: F401
