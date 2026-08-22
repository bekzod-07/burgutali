"""
SQLite yozuv qulfida amalni qayta urinish.

Bot va web-server bitta SQLite fayliga yozadi, imtihon paytida esa o'nlab
qatnashchi bir vaqtda javob saqlaydi. WAL rejimi o'qish va yozishni
ajratadi, lekin bitta holatda `busy_timeout` yordam bermaydi:

    ulanish avval **o'qish** tranzaksiyasini boshlaydi (masalan
    `get_or_create` ning SELECT qismi), so'ng **yozmoqchi** bo'ladi —
    oradagi vaqtda boshqa ulanish yozib ulgurgan bo'lsa, SQLite
    o'lik qulfning oldini olish uchun `SQLITE_BUSY` ni **darhol**
    qaytaradi va kutmaydi.

Amalda bu «database is locked» degan 500 xato bo'lib chiqadi va
qatnashchining javobi saqlanmay qoladi. Bu yerdagi dekorator shunday
holatda amalni boshidan qayta bajaradi: tranzaksiya to'liq yopilib,
yangisi ochiladi, shuning uchun ikkinchi urinish deyarli doim o'tadi.

PostgreSQL da bu muammo yo'q — dekorator u yerda ham xalaqit bermaydi,
chunki xato matni mos kelmaydi va amal birinchi urinishdayoq o'tadi.
"""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Callable, TypeVar

from django.db import OperationalError, close_old_connections

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Nechta qayta urinish (birinchisidan tashqari).
MAX_RETRIES: int = 4

#: Urinishlar orasidagi boshlang'ich kutish (soniya). Har safar ikkilanadi.
BASE_DELAY: float = 0.08

#: Qaysi xato matnlari qayta urinishga arziydi.
_LOCK_MARKERS = ("database is locked", "database table is locked")


def is_lock_error(error: BaseException) -> bool:
    """Xato SQLite qulfi tufayli yuz berganmi."""
    return any(marker in str(error).lower() for marker in _LOCK_MARKERS)


def retry_on_lock(func: Callable[..., T]) -> Callable[..., T]:
    """
    Amalni SQLite qulfida qayta bajaradi.

    Kutish vaqti har urinishda ikkilanadi va ustiga kichik tasodifiy
    qo'shimcha beriladi — bir vaqtda qulfga urilgan so'rovlar keyingi
    urinishda ham to'qnashmasligi uchun.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        delay = BASE_DELAY
        for attempt in range(MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except OperationalError as error:
                if attempt >= MAX_RETRIES or not is_lock_error(error):
                    raise
                logger.warning(
                    "Baza qulflangan (%s-urinish), %.0f ms dan keyin qayta urinamiz: %s",
                    attempt + 1,
                    delay * 1000,
                    func.__name__,
                )
                # Ochiq tranzaksiya qolib ketmasin — keyingi urinish toza
                # ulanishdan boshlanadi.
                close_old_connections()
                time.sleep(delay + random.uniform(0, BASE_DELAY))
                delay *= 2
        raise AssertionError("yetib bo'lmaydigan holat")  # pragma: no cover

    return wrapper


def sync_db_call(func: Callable[..., T]):
    """
    Bazaga **yozadigan** amalni bot uchun asinxron ko'rinishga o'raydi.

    `sync_to_async(retry_on_lock(func), thread_sensitive=True)` bilan bir
    xil, lekin qisqa va bir joyda: yangi yozuvchi amal qo'shilganda uni
    shu funksiya bilan o'rash yetarli.
    """
    from asgiref.sync import sync_to_async

    return sync_to_async(retry_on_lock(func), thread_sensitive=True)


__all__ = [
    "retry_on_lock",
    "sync_db_call",
    "is_lock_error",
    "MAX_RETRIES",
    "BASE_DELAY",
]
