"""`apps.rasch` ilovasining konfiguratsiyasi."""

from django.apps import AppConfig


class RaschConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rasch"
    verbose_name = "Rasch modeli"
