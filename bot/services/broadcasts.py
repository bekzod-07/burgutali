"""
Reklama yuborish uchun baza amallari.

Panel xabarni bazaga yozadi, bot esa shu yerdagi funksiyalar orqali uni
o'qiydi va yuborilganini belgilaydi. Barcha amallar ORM ustida bo'lgani
uchun asinxron ko'rinishga o'ralgan (`sync_db_call` SQLite qulfida
qayta urinadi ham).
"""

from __future__ import annotations

import logging
import os

from asgiref.sync import sync_to_async
from django.utils import timezone

from apps.broadcasts.models import Broadcast, BroadcastDelivery
from apps.broadcasts.services import refresh_counters
from core.db_retry import retry_on_lock

logger = logging.getLogger(__name__)


def _payload(broadcast: Broadcast) -> dict:
    """Yuborish uchun kerakli ma'lumotlar (ORM obyektisiz)."""
    image_path = ""
    if broadcast.has_image:
        try:
            path = broadcast.image.path
        except (NotImplementedError, ValueError):  # pragma: no cover
            path = ""
        if path and os.path.exists(path):
            image_path = path
        else:
            logger.warning(
                "Reklama rasmi topilmadi: id=%s, fayl=%s",
                broadcast.pk,
                broadcast.image.name,
            )
    return {
        "id": broadcast.pk,
        "text": broadcast.text or "",
        "image_path": image_path,
        "image_file_id": broadcast.image_file_id or "",
        "buttons": broadcast.button_rows,
    }


# --------------------------------------------------------------------------
#  Navbat
# --------------------------------------------------------------------------


@retry_on_lock
def _claim_next() -> dict | None:
    """
    Yuborilishi kerak bo'lgan navbatdagi xabarni oladi.

    Avval yarim qolgan (bot qayta ishga tushgan) xabar davom ettiriladi,
    so'ng navbatdagilar vaqti kelganiga qarab olinadi.
    """
    now = timezone.now()

    broadcast = Broadcast.objects.filter(status=Broadcast.Status.SENDING).order_by(
        "created_at"
    ).first()

    if broadcast is None:
        broadcast = (
            Broadcast.objects.filter(status=Broadcast.Status.QUEUED)
            .filter(scheduled_at__isnull=True)
            .order_by("created_at")
            .first()
        )
    if broadcast is None:
        broadcast = (
            Broadcast.objects.filter(
                status=Broadcast.Status.QUEUED, scheduled_at__lte=now
            )
            .order_by("scheduled_at")
            .first()
        )
    if broadcast is None:
        return None

    if broadcast.status != Broadcast.Status.SENDING:
        broadcast.status = Broadcast.Status.SENDING
        broadcast.started_at = broadcast.started_at or now
        broadcast.error = ""
        broadcast.save(update_fields=["status", "started_at", "error", "updated_at"])

    return _payload(broadcast)


@retry_on_lock
def _next_deliveries(broadcast_id: int, limit: int) -> list[tuple[int, int]]:
    """Yuborilmagan qabul qiluvchilardan bir bo'lak."""
    rows = (
        BroadcastDelivery.objects.filter(
            broadcast_id=broadcast_id, status=BroadcastDelivery.Status.PENDING
        )
        .order_by("id")
        .values_list("id", "telegram_id")[:limit]
    )
    return list(rows)


@retry_on_lock
def _mark_delivery(delivery_id: int, status: str, error: str = "") -> None:
    """Bitta yuborishning natijasini yozadi."""
    BroadcastDelivery.objects.filter(pk=delivery_id).update(
        status=status, error=error[:200], sent_at=timezone.now()
    )


@retry_on_lock
def _mark_deliveries(results: list[tuple[int, str, str]]) -> None:
    """Bir bo'lakdagi natijalarni birdaniga yozadi."""
    now = timezone.now()
    for delivery_id, status, error in results:
        BroadcastDelivery.objects.filter(pk=delivery_id).update(
            status=status, error=(error or "")[:200], sent_at=now
        )


@retry_on_lock
def _current_status(broadcast_id: int) -> str:
    """Xabarning hozirgi holati — yuborish o'rtasida to'xtatilganini bilish uchun."""
    return (
        Broadcast.objects.filter(pk=broadcast_id)
        .values_list("status", flat=True)
        .first()
        or Broadcast.Status.CANCELLED
    )


@retry_on_lock
def _update_counters(broadcast_id: int) -> dict:
    """Hisoblagichlarni yangilaydi va qisqacha holatni qaytaradi."""
    broadcast = Broadcast.objects.filter(pk=broadcast_id).first()
    if broadcast is None:
        return {"status": Broadcast.Status.CANCELLED, "pending": 0}
    refresh_counters(broadcast)
    pending = BroadcastDelivery.objects.filter(
        broadcast_id=broadcast_id, status=BroadcastDelivery.Status.PENDING
    ).count()
    return {"status": broadcast.status, "pending": pending}


@retry_on_lock
def _finish(broadcast_id: int) -> dict | None:
    """Yuborish tugadi deb belgilaydi va yakuniy raqamlarni qaytaradi."""
    broadcast = Broadcast.objects.filter(pk=broadcast_id).first()
    if broadcast is None:
        return None
    refresh_counters(broadcast)
    if broadcast.status == Broadcast.Status.SENDING:
        broadcast.status = Broadcast.Status.DONE
        broadcast.finished_at = timezone.now()
        broadcast.save(update_fields=["status", "finished_at", "updated_at"])
    return {
        "id": broadcast.pk,
        "title": broadcast.display_title,
        "status": broadcast.status,
        "total": broadcast.total,
        "sent": broadcast.sent,
        "failed": broadcast.failed,
        "blocked": broadcast.blocked,
    }


@retry_on_lock
def _fail(broadcast_id: int, error: str) -> None:
    """Kutilmagan xatoda xabarni «xato» holatiga o'tkazadi."""
    Broadcast.objects.filter(pk=broadcast_id).update(
        status=Broadcast.Status.FAILED,
        error=error[:255],
        finished_at=timezone.now(),
    )


@retry_on_lock
def _save_file_id(broadcast_id: int, file_id: str) -> None:
    """Telegram qaytargan rasm belgisini saqlaydi (keyingi yuborishlar tez bo'ladi)."""
    Broadcast.objects.filter(pk=broadcast_id).update(image_file_id=file_id[:256])


# --------------------------------------------------------------------------
#  Sinov yuborish
# --------------------------------------------------------------------------


@retry_on_lock
def _pending_test() -> dict | None:
    """So'ralgan, lekin hali yuborilmagan sinov xabari."""
    broadcast = (
        Broadcast.objects.filter(
            test_requested_at__isnull=False,
            test_sent_at__isnull=True,
            test_target_id__isnull=False,
        )
        .exclude(test_error__gt="")
        .order_by("test_requested_at")
        .first()
    )
    if broadcast is None:
        return None
    payload = _payload(broadcast)
    payload["target"] = broadcast.test_target_id
    return payload


@retry_on_lock
def _mark_test(broadcast_id: int, error: str = "") -> None:
    """Sinov natijasini yozadi."""
    if error:
        Broadcast.objects.filter(pk=broadcast_id).update(test_error=error[:255])
    else:
        Broadcast.objects.filter(pk=broadcast_id).update(
            test_sent_at=timezone.now(), test_error=""
        )


@retry_on_lock
def _report_recipients() -> list[int]:
    """Yakuniy hisobot yuboriladigan adminlar."""
    from apps.users.models import BotUser

    return list(
        BotUser.objects.filter(is_admin=True, is_blocked=False).values_list(
            "telegram_id", flat=True
        )
    )


# --------------------------------------------------------------------------
#  Asinxron ko'rinishlar
# --------------------------------------------------------------------------

#: Funksiyalarning o'zi allaqachon `@retry_on_lock` bilan o'ralgan, shuning
#: uchun bu yerda faqat asinxron ko'rinishga o'tkaziladi.
claim_next = sync_to_async(_claim_next, thread_sensitive=True)
next_deliveries = sync_to_async(_next_deliveries, thread_sensitive=True)
mark_delivery = sync_to_async(_mark_delivery, thread_sensitive=True)
mark_deliveries = sync_to_async(_mark_deliveries, thread_sensitive=True)
current_status = sync_to_async(_current_status, thread_sensitive=True)
update_counters = sync_to_async(_update_counters, thread_sensitive=True)
finish = sync_to_async(_finish, thread_sensitive=True)
fail = sync_to_async(_fail, thread_sensitive=True)
save_file_id = sync_to_async(_save_file_id, thread_sensitive=True)
pending_test = sync_to_async(_pending_test, thread_sensitive=True)
mark_test = sync_to_async(_mark_test, thread_sensitive=True)
report_recipients = sync_to_async(_report_recipients, thread_sensitive=True)


__all__ = [
    "claim_next",
    "next_deliveries",
    "mark_delivery",
    "mark_deliveries",
    "current_status",
    "update_counters",
    "finish",
    "fail",
    "save_file_id",
    "pending_test",
    "mark_test",
    "report_recipients",
]
