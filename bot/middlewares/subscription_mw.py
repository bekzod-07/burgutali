"""
Majburiy obunani tekshiruvchi middleware.

TZ talabi: botdan foydalanish uchun kanalga a'zo bo'lish shart. Bu qoida
barcha foydalanuvchilarga tegishli — test ishlaydiganlarga ham, bepul test
yaratib o'tkazadiganlarga ham. Asosiy adminlar bundan mustasno.

Obuna holati bazada keshlanadi va har safar Telegram API ga murojaat
qilinmaydi — faqat kesh eskirganda yoki foydalanuvchi hali a'zo bo'lmaganda.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from django.utils import timezone

from bot.keyboards import inline
from bot.services import users as user_service
from bot.utils.subscription import is_subscribed

logger = logging.getLogger(__name__)

#: Obuna holati keshda shu muddat davomida yangi hisoblanadi.
CACHE_TTL = timedelta(minutes=30)

#: Tekshiruvdan ozod qilingan buyruqlar.
EXEMPT_COMMANDS = {"/start", "/help", "/yordam", "/bekor", "/cancel"}

#: Tekshiruvdan ozod qilingan callback prefikslari.
EXEMPT_CALLBACK_PREFIXES = ("sub:", "menu:start")


class SubscriptionMiddleware(BaseMiddleware):
    """Kanalga a'zolikni talab qiladi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        config = data.get("config")
        if user is None or config is None:
            return await handler(event, data)

        if not config.subscription_required or data.get("is_admin"):
            return await handler(event, data)

        if self._is_exempt(event):
            return await handler(event, data)

        if user.is_subscribed and self._cache_is_fresh(user):
            return await handler(event, data)

        bot = data.get("bot")
        subscribed = await is_subscribed(bot, user.telegram_id)

        if subscribed is None:
            # Tekshirib bo'lmadi — foydalanuvchini to'smaymiz.
            return await handler(event, data)

        await user_service.set_subscription(user, subscribed)
        if subscribed:
            user.is_subscribed = True
            return await handler(event, data)

        await self._ask_to_subscribe(event, config)
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _is_exempt(event: TelegramObject) -> bool:
        """Ushbu hodisa tekshiruvdan ozodmi."""
        if isinstance(event, Message):
            text = (event.text or "").strip().split()[0].lower() if event.text else ""
            return text in EXEMPT_COMMANDS
        if isinstance(event, CallbackQuery):
            payload = event.data or ""
            return any(payload.startswith(prefix) for prefix in EXEMPT_CALLBACK_PREFIXES)
        return False

    @staticmethod
    def _cache_is_fresh(user) -> bool:
        """Obuna keshi hali eskirmaganmi."""
        checked_at = getattr(user, "subscription_checked_at", None)
        if checked_at is None:
            return False
        return (timezone.now() - checked_at) < CACHE_TTL

    @staticmethod
    async def _ask_to_subscribe(event: TelegramObject, config) -> None:
        """A'zo bo'lishni so'raydi."""
        from bot.texts import start as T

        text = T.SUBSCRIPTION_REQUIRED.format(channel=config.required_channel)
        markup = inline.subscription(config.required_channel_url)

        if isinstance(event, CallbackQuery):
            await event.answer()
            if event.message is not None:
                await event.message.answer(text, reply_markup=markup)
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=markup)
