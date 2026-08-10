"""
Spam va tez-tez bosishdan himoya.

Har bir foydalanuvchi uchun oxirgi so'rov vaqti eslab qolinadi. Belgilangan
oraliqdan tez yuborilgan so'rovlar e'tiborsiz qoldiriladi.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import get_config
from bot.texts import common as T

#: Bir vaqtda kuzatiladigan foydalanuvchilar soni.
MAX_TRACKED_USERS = 10_000


class ThrottlingMiddleware(BaseMiddleware):
    """So'rovlar chastotasini cheklaydi."""

    def __init__(self, rate: float | None = None) -> None:
        super().__init__()
        self.rate = rate if rate is not None else get_config().throttle_rate
        self._last_seen: OrderedDict[int, float] = OrderedDict()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        previous = self._last_seen.get(user.id)
        self._last_seen[user.id] = now
        self._last_seen.move_to_end(user.id)
        if len(self._last_seen) > MAX_TRACKED_USERS:
            self._last_seen.popitem(last=False)

        if previous is not None and (now - previous) < self.rate:
            if isinstance(event, CallbackQuery):
                await event.answer(T.TOO_FAST, show_alert=False)
            elif isinstance(event, Message) and event.text and event.text.startswith("/"):
                # Buyruqlarni bo'g'ib qo'ymaymiz
                return await handler(event, data)
            return None

        return await handler(event, data)
