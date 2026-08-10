"""`apps.miniapp` ilovasining konfiguratsiyasi."""

from django.apps import AppConfig


class MiniAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.miniapp"
    verbose_name = "Mini App"
