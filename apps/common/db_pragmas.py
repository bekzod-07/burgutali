"""
SQLite uchun PRAGMA sozlamalari.

Telegram bot va Django web-server bitta SQLite fayliga bir vaqtda murojaat
qilishi mumkin. WAL (Write-Ahead Logging) rejimi bir vaqtda o'qish va yozishga
imkon beradi va "database is locked" xatosini deyarli yo'q qiladi.

PostgreSQL ishlatilganda bu modul hech narsa qilmaydi.
"""

from __future__ import annotations

import logging

from django.db.backends.signals import connection_created
from django.dispatch import receiver

logger = logging.getLogger(__name__)

#: Har bir yangi SQLite ulanishida bajariladigan buyruqlar.
SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA busy_timeout=30000;",
    "PRAGMA temp_store=MEMORY;",
)


@receiver(connection_created)
def configure_sqlite(sender, connection, **kwargs) -> None:  # noqa: ANN001
    """Yangi ulanish yaratilganda SQLite PRAGMA larini qo'llaydi."""
    if connection.vendor != "sqlite":
        return
    try:
        cursor = connection.cursor()
        for pragma in SQLITE_PRAGMAS:
            cursor.execute(pragma)
    except Exception as exc:  # pragma: no cover - himoya
        logger.warning("SQLite PRAGMA sozlanmadi: %s", exc)
