"""
Django ORM bilan ishlash uchun asinxron ko'prik.

Aiogram event loop ichida ORM ni to'g'ridan-to'g'ri chaqirib bo'lmaydi,
shuning uchun barcha ma'lumotlar bazasi amallari `sync_to_async` orqali
alohida oqimda bajariladi.
"""

from . import attempts, certificates, codes, exams, reports, stats, users  # noqa: F401

__all__ = ["users", "exams", "attempts", "codes", "certificates", "reports", "stats"]
