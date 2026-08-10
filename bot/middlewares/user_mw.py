"""
Foydalanuvchini bazadan olish yoki yaratish.

Har bir handler `user` (BotUser) va `config` (BotConfig) argumentlarini
tayyor holda oladi.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import get_config
from bot.services import users as user_service
from bot.texts import common as T

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """`user` va `config` ni handler ma'lumotlariga qo'shadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = getattr(event, "from_user", None)
        if telegram_user is None or telegram_user.is_bot:
            return await handler(event, data)

        config = get_config()
        try:
            user, _ = await user_service.get_or_create_user(
                telegram_user.id,
                username=telegram_user.username or "",
                first_name=telegram_user.first_name or "",
                last_name=telegram_user.last_name or "",
                admin_ids=set(config.admin_ids),
            )
        except Exception:  # pragma: no cover - baza vaqtincha ishlamasligi mumkin
            logger.exception("Foydalanuvchini yuklashda xato: %s", telegram_user.id)
            return None

        if user.is_blocked:
            if isinstance(event, CallbackQuery):
                await event.answer(T.BLOCKED, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(T.BLOCKED)
            return None

        data["user"] = user
        data["config"] = config
        data["is_admin"] = bool(user.is_admin or config.is_admin(telegram_user.id))
        return await handler(event, data)
