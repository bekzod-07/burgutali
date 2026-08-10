"""
Bot va Dispatcher obyektlarini yaratish.

Bu modul import qilinishi bilanoq Django muhiti ishga tushiriladi —
shundan keyingina `bot.services.*` modullari ORM bilan ishlay oladi.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from core.django_setup import setup_django

setup_django()

from .config import get_config  # noqa: E402


def create_bot() -> Bot:
    """Sozlangan `Bot` obyektini qaytaradi."""
    config = get_config()
    if not config.is_valid:
        raise RuntimeError(
            "BOT_TOKEN sozlanmagan yoki noto'g'ri. `.env` faylini tekshiring."
        )
    return Bot(
        token=config.token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )


def create_dispatcher() -> Dispatcher:
    """
    Sozlangan `Dispatcher` obyektini qaytaradi.

    Holat (FSM) xotirada saqlanadi — bot qayta ishga tushganda faqat
    tugallanmagan dialoglar qaytadan boshlanadi. Barcha muhim ma'lumotlar
    (urinishlar, javoblar, kodlar) bazada saqlanadi.
    """
    dispatcher = Dispatcher(storage=MemoryStorage())

    from .handlers import setup_routers
    from .middlewares import setup_middlewares

    setup_middlewares(dispatcher)
    setup_routers(dispatcher)
    return dispatcher


__all__ = ["create_bot", "create_dispatcher"]
