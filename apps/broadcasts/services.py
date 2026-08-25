"""
Reklama xizmatlari — auditoriyani aniqlash, navbatga qo'yish va hisob.

Bu qatlam faqat baza bilan ishlaydi: Telegramga xabar yuborish botning
fon vazifasida (`bot/tasks/broadcast.py`) bajariladi. Shunday ajratish
tufayli panel javobni kutib qolmaydi — «Yuborish» bosilishi bilan
sahifa darhol ochiladi, jarayon esa fonda davom etadi.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.users.models import BotUser
from core.db_retry import retry_on_lock

from .models import Broadcast, BroadcastDelivery

logger = logging.getLogger(__name__)

#: Yuborish ro'yxati shuncha qatordan iborat bo'laklarda yoziladi.
CHUNK_SIZE: int = 500


# --------------------------------------------------------------------------
#  Auditoriya
# --------------------------------------------------------------------------


def audience_queryset(audience: str, exam=None):
    """
    Tanlangan auditoriya bo'yicha foydalanuvchilar so'rovi.

    Bloklangan foydalanuvchilarga reklama yuborilmaydi.
    """
    queryset = BotUser.objects.filter(is_blocked=False)

    if audience == Broadcast.Audience.REGISTERED:
        queryset = queryset.filter(is_registered=True)
    elif audience == Broadcast.Audience.ACTIVE:
        since = timezone.now() - timedelta(days=Broadcast.ACTIVE_DAYS)
        queryset = queryset.filter(last_seen_at__gte=since)
    elif audience == Broadcast.Audience.ADMINS:
        queryset = queryset.filter(is_admin=True)
    elif audience == Broadcast.Audience.EXAM:
        if exam is None:
            return queryset.none()
        queryset = queryset.filter(attempts__exam=exam).distinct()

    return queryset.order_by("id")


def audience_count(audience: str, exam=None) -> int:
    """Auditoriyadagi foydalanuvchilar soni."""
    return audience_queryset(audience, exam).count()


def audience_summary() -> dict[str, int]:
    """Barcha auditoriyalar bo'yicha sonlar — formada ko'rsatish uchun."""
    return {
        value: audience_count(value)
        for value, _ in Broadcast.Audience.choices
        if value != Broadcast.Audience.EXAM
    }


# --------------------------------------------------------------------------
#  Navbat
# --------------------------------------------------------------------------


@retry_on_lock
def queue_broadcast(broadcast: Broadcast, *, scheduled_at=None) -> int:
    """
    Xabarni yuborish navbatiga qo'yadi va qabul qiluvchilar ro'yxatini yozadi.

    Ro'yxat aynan shu payt tuziladi, ya'ni keyin qo'shilgan foydalanuvchilar
    eski reklamani olmaydi. Qayta navbatga qo'yilganda (masalan to'xtatilgan
    xabar davom ettirilsa) allaqachon yuborilganlar takrorlanmaydi.
    """
    with transaction.atomic():
        users = list(
            audience_queryset(broadcast.audience, broadcast.exam).values_list(
                "id", "telegram_id"
            )
        )
        existing = set(
            BroadcastDelivery.objects.filter(broadcast=broadcast).values_list(
                "user_id", flat=True
            )
        )

        new_rows = [
            BroadcastDelivery(
                broadcast=broadcast,
                user_id=user_id,
                telegram_id=telegram_id,
                status=BroadcastDelivery.Status.PENDING,
            )
            for user_id, telegram_id in users
            if user_id not in existing
        ]
        for start in range(0, len(new_rows), CHUNK_SIZE):
            BroadcastDelivery.objects.bulk_create(new_rows[start:start + CHUNK_SIZE])

        broadcast.status = Broadcast.Status.QUEUED
        broadcast.scheduled_at = scheduled_at
        broadcast.error = ""
        broadcast.finished_at = None
        _apply_counters(broadcast)
        broadcast.save(
            update_fields=[
                "status", "scheduled_at", "error", "finished_at",
                "total", "sent", "failed", "blocked", "updated_at",
            ]
        )

    logger.info(
        "Reklama navbatga qo'yildi: id=%s, qabul qiluvchilar=%s",
        broadcast.pk,
        broadcast.total,
    )
    return broadcast.total


@retry_on_lock
def cancel_broadcast(broadcast: Broadcast) -> None:
    """Yuborishni to'xtatadi — yuborilmagan qatorlar navbatda qoladi."""
    broadcast.status = Broadcast.Status.CANCELLED
    broadcast.finished_at = timezone.now()
    broadcast.save(update_fields=["status", "finished_at", "updated_at"])
    logger.info("Reklama to'xtatildi: id=%s", broadcast.pk)


@retry_on_lock
def reset_broadcast(broadcast: Broadcast) -> None:
    """Xabarni qoralama holatiga qaytaradi (yuborish ro'yxati o'chiriladi)."""
    with transaction.atomic():
        BroadcastDelivery.objects.filter(broadcast=broadcast).delete()
        broadcast.status = Broadcast.Status.DRAFT
        broadcast.total = broadcast.sent = broadcast.failed = broadcast.blocked = 0
        broadcast.started_at = None
        broadcast.finished_at = None
        broadcast.error = ""
        broadcast.save(
            update_fields=[
                "status", "total", "sent", "failed", "blocked",
                "started_at", "finished_at", "error", "updated_at",
            ]
        )


@retry_on_lock
def request_test_send(broadcast: Broadcast, telegram_id: int) -> None:
    """Sinov xabarini bitta odamga yuborishni so'raydi (botni uyg'otadi)."""
    broadcast.test_target_id = int(telegram_id)
    broadcast.test_requested_at = timezone.now()
    broadcast.test_sent_at = None
    broadcast.test_error = ""
    broadcast.save(
        update_fields=[
            "test_target_id", "test_requested_at", "test_sent_at",
            "test_error", "updated_at",
        ]
    )


@retry_on_lock
def duplicate_broadcast(broadcast: Broadcast, user=None) -> Broadcast:
    """Xabardan yangi qoralama nusxa yaratadi."""
    copy = Broadcast.objects.create(
        title=(broadcast.title or broadcast.display_title)[:140] + " (nusxa)",
        text=broadcast.text,
        image=broadcast.image,
        image_file_id=broadcast.image_file_id,
        buttons=broadcast.buttons,
        audience=broadcast.audience,
        exam=broadcast.exam,
        status=Broadcast.Status.DRAFT,
        created_by=user if (user is not None and user.is_authenticated) else None,
    )
    return copy


# --------------------------------------------------------------------------
#  Hisoblagichlar
# --------------------------------------------------------------------------


def _apply_counters(broadcast: Broadcast) -> None:
    """Hisoblagichlarni yuborishlar jadvalidan qayta hisoblaydi (saqlamaydi)."""
    stats = BroadcastDelivery.objects.filter(broadcast=broadcast).aggregate(
        total=Count("id"),
        sent=Count("id", filter=Q(status=BroadcastDelivery.Status.SENT)),
        failed=Count("id", filter=Q(status=BroadcastDelivery.Status.FAILED)),
        blocked=Count("id", filter=Q(status=BroadcastDelivery.Status.BLOCKED)),
    )
    broadcast.total = stats["total"] or 0
    broadcast.sent = stats["sent"] or 0
    broadcast.failed = stats["failed"] or 0
    broadcast.blocked = stats["blocked"] or 0


@retry_on_lock
def refresh_counters(broadcast: Broadcast) -> Broadcast:
    """Hisoblagichlarni qayta hisoblab saqlaydi."""
    _apply_counters(broadcast)
    broadcast.save(
        update_fields=["total", "sent", "failed", "blocked", "updated_at"]
    )
    return broadcast


def broadcast_statistics() -> dict[str, int]:
    """Ro'yxat sahifasidagi umumiy raqamlar."""
    rows = Broadcast.objects.aggregate(
        total=Count("id"),
        running=Count(
            "id",
            filter=Q(status__in=[Broadcast.Status.QUEUED, Broadcast.Status.SENDING]),
        ),
        done=Count("id", filter=Q(status=Broadcast.Status.DONE)),
    )
    return {
        "total": rows["total"] or 0,
        "running": rows["running"] or 0,
        "done": rows["done"] or 0,
        "sent": BroadcastDelivery.objects.filter(
            status=BroadcastDelivery.Status.SENT
        ).count(),
    }


__all__ = [
    "audience_queryset",
    "audience_count",
    "audience_summary",
    "queue_broadcast",
    "cancel_broadcast",
    "reset_broadcast",
    "request_test_send",
    "duplicate_broadcast",
    "refresh_counters",
    "broadcast_statistics",
    "CHUNK_SIZE",
]
