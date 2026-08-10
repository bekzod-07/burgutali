"""
Botni ishga tushirish.

Ishga tushirish:
    python run_bot.py
yoki
    python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault

from core.env import BASE_DIR

logger = logging.getLogger("bot")

#: Telegram menyusida ko'rinadigan buyruqlar.
BOT_COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish"),
    BotCommand(command="menu", description="Asosiy menyu"),
    BotCommand(command="ilova", description="Web ilovani ochish"),
    BotCommand(command="yordam", description="Yordam"),
    BotCommand(command="bekor", description="Joriy amalni bekor qilish"),
]


def setup_logging(level: str = "INFO") -> None:
    """Konsol va faylga log yozishni sozlaydi."""
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        logs_dir / "bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)

    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


async def on_startup(bot: Bot) -> None:
    """Bot ishga tushganda bajariladigan amallar."""
    from bot.config import get_config
    from bot.services import users as user_service
    from bot.texts.common import BOT_DESCRIPTION

    config = get_config()

    try:
        me = await bot.get_me()
        logger.info("Bot ishga tushdi: @%s (id=%s)", me.username, me.id)
    except Exception:
        logger.exception("Bot ma'lumotlarini olishda xato")

    # `.env` dagi adminlarni baza bilan moslashtiramiz.
    if config.admin_ids:
        try:
            await user_service.sync_admins(set(config.admin_ids))
            logger.info("Adminlar sinxronlandi: %s", sorted(config.admin_ids))
        except Exception:
            logger.exception("Adminlarni sinxronlashda xato")

    try:
        await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())
    except Exception:
        logger.warning("Bot buyruqlarini o'rnatib bo'lmadi", exc_info=True)

    try:
        await bot.set_my_short_description(
            short_description=BOT_DESCRIPTION[:120]
        )
        await bot.set_my_description(description=BOT_DESCRIPTION[:512])
    except Exception:
        logger.debug("Bot tavsifini o'rnatib bo'lmadi", exc_info=True)

    # Suhbat oynasidagi doimiy «menyu» tugmasini Web ilovaga bog'laymiz.
    if config.miniapp_available:
        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo

            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Ilova", web_app=WebAppInfo(url=config.miniapp_url)
                )
            )
            logger.info("Web ilova menyu tugmasi o'rnatildi: %s", config.miniapp_url)
        except Exception:
            logger.warning("Menyu tugmasini o'rnatib bo'lmadi", exc_info=True)
    else:
        logger.warning(
            "Mini App o'chirilgan: PUBLIC_BASE_URL HTTPS bo'lishi kerak "
            "(hozirgi qiymat: %s). Testlar bot orqali topshiriladi.",
            config.public_base_url or "—",
        )


async def on_shutdown(bot: Bot) -> None:
    """Bot to'xtaganda resurslarni bo'shatadi."""
    logger.info("Bot to'xtatilmoqda...")
    try:
        await bot.session.close()
    except Exception:  # pragma: no cover
        pass


async def run() -> None:
    """Asosiy asinxron kirish nuqtasi."""
    from bot.loader import create_bot, create_dispatcher
    from bot.tasks import start_scheduler

    bot: Bot = create_bot()
    dispatcher: Dispatcher = create_dispatcher()

    await on_startup(bot)
    tasks = start_scheduler(bot)

    try:
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    finally:
        for task in tasks:
            task.cancel()
        await on_shutdown(bot)


def main() -> None:
    """Sinxron kirish nuqtasi."""
    setup_logging()

    from aiogram.exceptions import (
        TelegramConflictError,
        TelegramNetworkError,
        TelegramUnauthorizedError,
    )

    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi.")
    except TelegramUnauthorizedError:
        logger.error(
            "BOT_TOKEN noto'g'ri yoki bekor qilingan. "
            "`.env` faylidagi BOT_TOKEN ni @BotFather dan olingan token bilan almashtiring."
        )
        sys.exit(1)
    except TelegramConflictError:
        logger.error(
            "Bot allaqachon ishlamoqda (boshqa nusxa getUpdates so'rovini yuboryapti). "
            "Avvalgi nusxani to'xtating — bir vaqtda faqat bitta nusxa ishlashi mumkin."
        )
        sys.exit(1)
    except TelegramNetworkError as exc:
        logger.error("Telegram bilan aloqa yo'q: %s", exc)
        sys.exit(1)
    except RuntimeError as exc:
        logger.error("Botni ishga tushirib bo'lmadi: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
