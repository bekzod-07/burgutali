"""Foydalanuvchilar bilan ishlash xizmatlari."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from core.text_utils import clean_full_name, normalize_phone

from .models import BotUser, UserAction

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
#  Ro'yxatga olish va yangilash
# --------------------------------------------------------------------------


@transaction.atomic
def get_or_create_user(
    telegram_id: int,
    *,
    username: str = "",
    first_name: str = "",
    last_name: str = "",
    admin_ids: set[int] | None = None,
) -> tuple[BotUser, bool]:
    """Telegram ID bo'yicha foydalanuvchini topadi yoki yaratadi."""
    admin_ids = admin_ids or set()
    user, created = BotUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            "username": (username or "").lstrip("@")[:64],
            "tg_first_name": (first_name or "")[:128],
            "tg_last_name": (last_name or "")[:128],
            "is_admin": telegram_id in admin_ids,
        },
    )

    changed: list[str] = []
    new_username = (username or "").lstrip("@")[:64]
    if new_username != user.username:
        user.username = new_username
        changed.append("username")
    if (first_name or "")[:128] != user.tg_first_name:
        user.tg_first_name = (first_name or "")[:128]
        changed.append("tg_first_name")
    if (last_name or "")[:128] != user.tg_last_name:
        user.tg_last_name = (last_name or "")[:128]
        changed.append("tg_last_name")
    if telegram_id in admin_ids and not user.is_admin:
        user.is_admin = True
        changed.append("is_admin")

    user.last_seen_at = timezone.now()
    changed.append("last_seen_at")

    if changed and not created:
        user.save(update_fields=list(set(changed)) + ["updated_at"])
    elif created:
        log_action(user, UserAction.Kind.OTHER, "Botga birinchi marta kirdi")

    return user, created


def save_full_name(user: BotUser, raw_name: str) -> str:
    """Ism-familiyani tozalab saqlaydi va tozalangan ko'rinishini qaytaradi."""
    cleaned = clean_full_name(raw_name)
    user.full_name = cleaned[:120]
    user.save(update_fields=["full_name", "updated_at"])
    return user.full_name


def save_phone(user: BotUser, raw_phone: str) -> str:
    """Telefon raqamini normallashtirib saqlaydi va ro'yxatni yakunlaydi."""
    phone = normalize_phone(raw_phone)
    user.phone = phone[:20]
    user.mark_registered()
    user.save(update_fields=["phone", "is_registered", "registered_at", "updated_at"])
    log_action(user, UserAction.Kind.REGISTER, "Ro'yxatdan o'tishni yakunladi")
    return user.phone


def set_subscription(user: BotUser, subscribed: bool) -> None:
    """Majburiy obuna holatini keshda saqlaydi."""
    user.is_subscribed = bool(subscribed)
    user.subscription_checked_at = timezone.now()
    user.save(update_fields=["is_subscribed", "subscription_checked_at", "updated_at"])


def block_user(user: BotUser, reason: str = "") -> None:
    """Foydalanuvchini bloklaydi."""
    user.is_blocked = True
    user.block_reason = (reason or "")[:255]
    user.save(update_fields=["is_blocked", "block_reason", "updated_at"])


def unblock_user(user: BotUser) -> None:
    """Blokni olib tashlaydi."""
    user.is_blocked = False
    user.block_reason = ""
    user.save(update_fields=["is_blocked", "block_reason", "updated_at"])


def sync_admins(admin_ids: set[int]) -> int:
    """
    `.env` dagi ADMIN_IDS ro'yxatini baza bilan moslashtiradi.

    Bot ishga tushganda bir marta chaqiriladi.
    """
    if not admin_ids:
        return 0
    updated = BotUser.objects.filter(telegram_id__in=admin_ids, is_admin=False).update(
        is_admin=True
    )
    BotUser.objects.filter(is_admin=True).exclude(telegram_id__in=admin_ids).update(
        is_admin=False
    )
    return updated


# --------------------------------------------------------------------------
#  Audit
# --------------------------------------------------------------------------


def log_action(
    user: BotUser | None,
    kind: str,
    description: str = "",
    **payload,
) -> UserAction:
    """Amal tarixiga yozuv qo'shadi."""
    return UserAction.objects.create(
        user=user,
        kind=kind,
        description=(description or "")[:255],
        payload=payload or {},
    )


# --------------------------------------------------------------------------
#  Statistika
# --------------------------------------------------------------------------


def user_statistics() -> dict:
    """Foydalanuvchilar bo'yicha umumiy statistika."""
    total = BotUser.objects.count()
    registered = BotUser.objects.registered().count()
    admins = BotUser.objects.admins().count()
    blocked = BotUser.objects.filter(is_blocked=True).count()
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = BotUser.objects.filter(created_at__gte=today).count()
    active_today = BotUser.objects.filter(last_seen_at__gte=today).count()
    return {
        "total": total,
        "registered": registered,
        "admins": admins,
        "blocked": blocked,
        "new_today": new_today,
        "active_today": active_today,
    }


__all__ = [
    "get_or_create_user",
    "save_full_name",
    "save_phone",
    "set_subscription",
    "block_user",
    "unblock_user",
    "sync_admins",
    "log_action",
    "user_statistics",
]
