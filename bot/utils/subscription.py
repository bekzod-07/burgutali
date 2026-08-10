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
    if result is None:
        # Tekshirib bo'lmasa foydalanuvchini to'sib qo'ymaymiz —
        # bu bot sozlamasidagi muammo, foydalanuvchining aybi emas.
        return True, T.SUBSCRIPTION_CHECK_FAILED
    return False, T.SUBSCRIPTION_REQUIRED.format(channel=config.required_channel)


__all__ = ["is_subscribed", "ensure_subscription", "MEMBER_STATUSES"]
