"""
Middleware larni ro'yxatdan o'tkazish.

Tartib muhim:
  1. `ThrottlingMiddleware`   — juda tez-tez bosishdan himoya;
  2. `UserMiddleware`         — foydalanuvchini bazadan olish/yaratish;
  3. `SubscriptionMiddleware` — majburiy obunani tekshirish.
"""

from __future__ import annotations

from aiogram import Dispatcher

from .subscription_mw import SubscriptionMiddleware
from .throttling_mw import ThrottlingMiddleware
from .user_mw import UserMiddleware


def setup_middlewares(dispatcher: Dispatcher) -> None:
    """Barcha middleware larni Dispatcher ga ulaydi."""
    throttling = ThrottlingMiddleware()
    user = UserMiddleware()
    subscription = SubscriptionMiddleware()

    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(throttling)
        observer.outer_middleware(user)
        observer.outer_middleware(subscription)


__all__ = [
    "setup_middlewares",
    "ThrottlingMiddleware",
    "UserMiddleware",
    "SubscriptionMiddleware",
]
