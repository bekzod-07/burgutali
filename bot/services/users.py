"""Foydalanuvchilar bilan ishlash (asinxron)."""

from __future__ import annotations

from asgiref.sync import sync_to_async

from apps.users import services as user_services
from apps.users.models import BotUser

# --------------------------------------------------------------------------
#  Asosiy amallar
# --------------------------------------------------------------------------

get_or_create_user = sync_to_async(user_services.get_or_create_user, thread_sensitive=True)
save_full_name = sync_to_async(user_services.save_full_name, thread_sensitive=True)
save_phone = sync_to_async(user_services.save_phone, thread_sensitive=True)
set_subscription = sync_to_async(user_services.set_subscription, thread_sensitive=True)
sync_admins = sync_to_async(user_services.sync_admins, thread_sensitive=True)
log_action = sync_to_async(user_services.log_action, thread_sensitive=True)
user_statistics = sync_to_async(user_services.user_statistics, thread_sensitive=True)


@sync_to_async(thread_sensitive=True)
def get_user(telegram_id: int) -> BotUser | None:
    """Telegram ID bo'yicha foydalanuvchini qaytaradi."""
    return BotUser.objects.filter(telegram_id=telegram_id).first()


@sync_to_async(thread_sensitive=True)
def refresh(user: BotUser) -> BotUser:
    """Foydalanuvchi ma'lumotlarini bazadan qayta o'qiydi."""
    return BotUser.objects.get(pk=user.pk)


@sync_to_async(thread_sensitive=True)
def all_registered_ids() -> list[int]:
    """Barcha ro'yxatdan o'tgan foydalanuvchilarning Telegram ID lari."""
    return list(
        BotUser.objects.registered().active().values_list("telegram_id", flat=True)
    )


@sync_to_async(thread_sensitive=True)
def export_users_excel() -> bytes:
    """Foydalanuvchilar ro'yxatini Excel ko'rinishida qaytaradi."""
    from apps.exports.excel import participants_workbook

    return participants_workbook(None)


__all__ = [
    "get_or_create_user",
    "save_full_name",
    "save_phone",
    "set_subscription",
    "sync_admins",
    "log_action",
    "user_statistics",
    "get_user",
    "refresh",
    "all_registered_ids",
    "export_users_excel",
]
