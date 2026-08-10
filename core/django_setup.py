"""
Django muhitini bot jarayoni ichida ishga tushirish.

Telegram bot va Django web-panel bitta ma'lumotlar bazasi va bitta ORM
bilan ishlaydi. Shu sababli bot ishga tushishidan oldin `django.setup()`
chaqirilishi shart — barcha `bot.services.*` modullari shu orqali Django
modellaridan foydalanadi.
"""

from __future__ import annotations

import os
import sys

from core.env import BASE_DIR

_INITIALIZED = False


def setup_django() -> None:
    """Django muhitini bir marta ishga tushiradi (idempotent)."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    root = str(BASE_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Bot jarayonida ORM ni sync_to_async orqali chaqiramiz, shuning uchun
    # Django ning "async-unsafe" tekshiruvini o'chirish shart emas, lekin
    # ba'zi kutubxonalar event loop ichida lazy chaqiruv qilishi mumkin.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "false")

    import django

    django.setup()
    _INITIALIZED = True


__all__ = ["setup_django"]
