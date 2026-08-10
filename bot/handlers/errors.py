"""
Xatoliklarni markazlashgan holda ushlash.

Har qanday handler ichida yuzaga kelgan kutilmagan xato jurnalga yoziladi
va foydalanuvchiga tushunarli xabar ko'rsatiladi.
"""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ErrorEvent

from bot.texts import common as TC

logger = logging.getLogger(__name__)


async def handle_error(event: ErrorEvent) -> bool:
    """Barcha ushlanmagan xatoliklarni qayta ishlaydi."""
    exception = event.exception

    # Foydalanuvchi botni bloklagan bo'lsa — jim o'tamiz.
    if isinstance(exception, TelegramForbiddenError):
        logger.info("Foydalanuvchi botni bloklagan: %s", exception)
        return True

    # "message is not modified" kabi zararsiz xatolar.
    if isinstance(exception, TelegramBadRequest):
        text = str(exception).lower()
        if "message is not modified" in text or "query is too old" in text:
            return True

    logger.exception("Handler xatosi: %s", exception, exc_info=exception)

    update = event.update
    message = getattr(update, "message", None)
    callback = getattr(update, "callback_query", None)

    try:
        if callback is not None:
            await callback.answer(TC.ERROR_GENERIC, show_alert=True)
        elif message is not None:
            await message.answer(TC.ERROR_GENERIC)
    except Exception:  # pragma: no cover - javob berib bo'lmasa
        pass

    return True


def setup(dispatcher: Dispatcher) -> None:
    """Xatolik handlerini ro'yxatdan o'tkazadi."""
    dispatcher.errors.register(handle_error)


__all__ = ["setup", "handle_error"]
