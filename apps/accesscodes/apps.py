"""`apps.accesscodes` ilovasining konfiguratsiyasi."""

from django.apps import AppConfig


class AccessCodesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accesscodes"
    verbose_name = "ID kodlar"
