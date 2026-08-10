"""Ishlab chiqish (development) rejimi sozlamalari."""

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, get_bool

DEBUG = get_bool("DJANGO_DEBUG", True)

# Lokal ishlab chiqishda ngrok/cloudflared domenlari ham ruxsat etiladi.
if DEBUG and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS = ALLOWED_HOSTS + [
        ".ngrok-free.app",
        ".ngrok-free.dev",
        ".ngrok.io",
        ".ngrok.app",
        ".trycloudflare.com",
        ".loca.lt",
        "testserver",
    ]

CSRF_TRUSTED_ORIGINS = list(globals().get("CSRF_TRUSTED_ORIGINS", [])) + [
    "https://*.ngrok-free.app",
    "https://*.ngrok-free.dev",
    "https://*.ngrok.io",
    "https://*.ngrok.app",
    "https://*.trycloudflare.com",
]

# Mini App Telegram webview ichida iframe sifatida ochilishi mumkin.
X_FRAME_OPTIONS = "SAMEORIGIN"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
