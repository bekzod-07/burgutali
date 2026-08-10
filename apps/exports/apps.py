"""`apps.exports` ilovasining konfiguratsiyasi."""

from django.apps import AppConfig


class ExportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.exports"
    verbose_name = "Eksport"
