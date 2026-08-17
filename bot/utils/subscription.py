"""
Majburiy obunani tekshirish.

TZ talabi: botdan foydalanish uchun @Burgutali kanaliga a'zo bo'lish shart.
Bu qoida barcha foydalanuvchilarga tegishli — test ishlaydiganlarga ham,
test yaratadiganlarga ham. Asosiy adminlar bundan mustasno.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import get_config

logger = logging.getLogger(__name__)

#: Kanalda a'zo hisoblanadigan holatlar.
MEMBER_STATUSES = {"creator", "administrator", "member", "restricted"}


async def is_subscribed(bot: Bot, telegram_id: int) -> bool | None:
    """
    Foydalanuvchi majburiy kanalga a'zomi.

    Qaytaradi:
      * `True`  — a'zo;
      * `False` — a'zo emas;
      * `None`  — tekshirib bo'lmadi (bot kanalda admin emas va h.k.).
    """
    config = get_config()
    if not config.subscription_required or not config.required_channel:
        return True
    if config.is_admin(telegram_id):
        return True

    try:
        member = await bot.get_chat_member(config.required_channel, telegram_id)
    except TelegramAPIError as exc:
        logger.warning(
            "Obunani tekshirib bo'lmadi (kanal: %s, user: %s): %s",
            config.required_channel, telegram_id, exc,
        )
        return None

    status = getattr(member, "status", "")
    status_value = getattr(status, "value", status)
    return str(status_value) in MEMBER_STATUSES


async def check_bot_is_channel_admin(bot: Bot) -> bool:
    """
    Bot majburiy kanalda administrator ekanini tekshiradi.

    A'zolikni `getChatMember` orqali bilish uchun bot kanalda admin bo'lishi
    shart. Bo'lmasa har bir tekshiruv `None` qaytaradi va — qoida qat'iy
    bo'lgani uchun — hamma foydalanuvchi to'silib qoladi. Shuning uchun bu
    ishga tushishda bir marta tekshiriladi va logga aniq yoziladi.
    """
    config = get_config()
    if not config.subscription_required or not config.required_channel:
        return True

    try:
        member = await bot.get_chat_member(
            config.required_channel, (await bot.get_me()).id
        )
    except TelegramAPIError as exc:
        logger.error(
            "MAJBURIY OBUNA ISHLAMAYDI: %s kanaliga ulanib bo'lmadi (%s). "
            "Botni kanalga administrator qilib qo'shing.",
            config.required_channel, exc,
        )
        return False

    status = getattr(member, "status", "")
    status_value = str(getattr(status, "value", status))
    if status_value in {"creator", "administrator"}:
        logger.info(
            "Majburiy obuna yoqilgan: %s (bot kanalda administrator).",
            config.required_channel,
        )
        return True

    logger.error(
        "MAJBURIY OBUNA ISHLAMAYDI: bot %s kanalida administrator emas "
        "(holat: %s). A'zolikni tekshirib bo'lmaydi.",
        config.required_channel, status_value,
    )
    return False


async def ensure_subscription(bot: Bot, telegram_id: int) -> tuple[bool, str]:
    """
    Obunani tekshiradi va foydalanuvchiga ko'rsatiladigan xabarni qaytaradi.

    Qaytaradi: `(ruxsat berilsinmi, xabar)`.
    """
    from bot.texts import start as T

    config = get_config()
    result = await is_subscribed(bot, telegram_id)

    if result is True:
        return True, ""

    text = T.SUBSCRIPTION_REQUIRED.format(channel=config.required_channel)
    if result is None:
        # Tekshirib bo'lmadi. A'zolik qat'iy shart — kirish berilmaydi.
        text += "\n\n" + T.SUBSCRIPTION_CHECK_FAILED
    return False, text


__all__ = [
    "is_subscribed",
    "ensure_subscription",
    "check_bot_is_channel_admin",
    "MEMBER_STATUSES",
]
