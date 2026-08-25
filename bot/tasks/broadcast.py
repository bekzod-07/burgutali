"""
Reklama xabarlarini yuborish (fon vazifasi).

Panelda tayyorlangan xabar bazaga tushadi, bu yerdagi tsikl esa uni
navbatdan olib, foydalanuvchilarga birma-bir yuboradi. Shu tariqa:

  * panel javob kutib qolmaydi — «Yuborish» bosilishi bilan sahifa ochiladi;
  * bot qayta ishga tushsa, yuborish qolgan joyidan davom etadi;
  * har bir qabul qiluvchi alohida belgilanadi, ya'ni xabar ikki marta
    yuborilmaydi.

Tezlik ataylab cheklangan: Telegram ommaviy yuborishda sekundiga ~30 ta
xabarga ruxsat beradi, biz 20 ta bilan cheklanamiz. Agar shunda ham
cheklovga urilsa (`TelegramRetryAfter`), server aytgan vaqt kutiladi.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

#: Navbatni tekshirish oralig'i (sekund).
QUEUE_INTERVAL: int = 5

#: Sekundiga nechta xabar yuboriladi.
MESSAGES_PER_SECOND: float = 20.0

#: Ikki xabar orasidagi tanaffus.
SEND_PAUSE: float = 1.0 / MESSAGES_PER_SECOND

#: Bir bo'lakdagi xabarlar soni — har bo'lakdan keyin xabar to'xtatilgan
#: yoki to'xtatilmaganligi qayta tekshiriladi.
BATCH_SIZE: int = 50

#: Bitta odamga necha marta urinib ko'riladi (tarmoq uzilishlari uchun).
MAX_ATTEMPTS: int = 3


# --------------------------------------------------------------------------
#  Yordamchilar
# --------------------------------------------------------------------------


def build_keyboard(rows) -> InlineKeyboardMarkup | None:
    """Saqlangan tugmalardan inline klaviatura yasaydi."""
    keyboard = [
        [
            InlineKeyboardButton(text=button["text"], url=button["url"])
            for button in row
            if button.get("text") and button.get("url")
        ]
        for row in (rows or [])
    ]
    keyboard = [row for row in keyboard if row]
    if not keyboard:
        return None
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _photo(payload: dict):
    """Yuboriladigan rasm: avval Telegram belgisi, bo'lmasa fayl."""
    file_id = payload.get("image_file_id")
    if file_id:
        return file_id
    path = payload.get("image_path")
    if path:
        return FSInputFile(path)
    return None


async def _deliver(
    bot: Bot, chat_id: int, payload: dict, keyboard: InlineKeyboardMarkup | None
) -> tuple[str, str]:
    """
    Xabarni bitta odamga yuboradi.

    Qaytaradi: `(holat, xato)` — holat `BroadcastDelivery.Status` qiymati.
    """
    from apps.broadcasts.formatting import to_plain_text
    from apps.broadcasts.models import BroadcastDelivery
    from bot.services import broadcasts as service

    status = BroadcastDelivery.Status
    last_error = ""

    for _ in range(MAX_ATTEMPTS):
        # Matn Telegram tomonidan rad etilgan bo'lsa, teglarsiz yuboriladi.
        parse_mode = None if payload.get("plain") else "HTML"
        text = payload.get("text") or ""

        try:
            photo = _photo(payload)
            if photo is not None:
                message = await bot.send_photo(
                    chat_id,
                    photo,
                    caption=text or None,
                    parse_mode=parse_mode,
                    reply_markup=keyboard,
                )
                # Birinchi muvaffaqiyatli yuborishdan keyin rasm qaytadan
                # yuklanmaydi — Telegram bergan belgidan foydalanamiz.
                if not payload.get("image_file_id") and message.photo:
                    file_id = message.photo[-1].file_id
                    payload["image_file_id"] = file_id
                    if payload.get("id"):
                        await service.save_file_id(payload["id"], file_id)
            else:
                await bot.send_message(
                    chat_id, text, parse_mode=parse_mode, reply_markup=keyboard
                )
            return status.SENT, ""

        except TelegramRetryAfter as error:
            wait = min(120, int(getattr(error, "retry_after", 5)) + 1)
            logger.warning(
                "Telegram tezlikni chekladi — %s soniya kutamiz (chat=%s).",
                wait,
                chat_id,
            )
            await asyncio.sleep(wait)
            last_error = str(error)[:200]
            continue

        except TelegramForbiddenError as error:
            # Foydalanuvchi botni bloklagan yoki hisobi o'chirilgan.
            return status.BLOCKED, str(error)[:200]

        except TelegramBadRequest as error:
            reason = str(error).lower()
            if "parse entities" in reason and not payload.get("plain"):
                logger.warning(
                    "Reklama matnini Telegram o'qiy olmadi — teglarsiz yuboramiz "
                    "(id=%s).",
                    payload.get("id"),
                )
                payload["plain"] = True
                payload["text"] = to_plain_text(text)
                continue
            if (
                "file identifier" in reason or "wrong file" in reason
            ) and payload.get("image_file_id"):
                # Saqlangan rasm belgisi eskirgan — faylni qaytadan yuklaymiz.
                payload["image_file_id"] = ""
                continue
            return status.FAILED, str(error)[:200]

        except TelegramNetworkError as error:
            last_error = str(error)[:200]
            await asyncio.sleep(2)
            continue

        except TelegramAPIError as error:
            return status.FAILED, str(error)[:200]

    return status.FAILED, last_error or "Bir necha urinishdan keyin ham yuborilmadi"


# --------------------------------------------------------------------------
#  Sinov xabari
# --------------------------------------------------------------------------


async def process_test_sends(bot: Bot) -> bool:
    """Panelda so'ralgan sinov xabarlarini yuboradi."""
    from apps.broadcasts.models import BroadcastDelivery
    from bot.services import broadcasts as service
    from bot.texts import admin as TA

    payload = await service.pending_test()
    if payload is None:
        return False

    target = payload.get("target")
    logger.info("Reklama sinov xabari: id=%s, kimga=%s", payload["id"], target)

    try:
        await bot.send_message(target, TA.BROADCAST_TEST_NOTE)
    except TelegramAPIError as error:
        await service.mark_test(payload["id"], str(error)[:200])
        return True

    state, error = await _deliver(
        bot, target, payload, build_keyboard(payload["buttons"])
    )
    if state == BroadcastDelivery.Status.SENT:
        await service.mark_test(payload["id"], "")
    else:
        await service.mark_test(
            payload["id"], error or "Sinov xabari yuborilmadi"
        )
    return True


# --------------------------------------------------------------------------
#  Asosiy yuborish
# --------------------------------------------------------------------------


async def process_queue(bot: Bot) -> bool:
    """Navbatdagi bitta reklamani oxirigacha yuboradi."""
    from apps.broadcasts.models import Broadcast
    from bot.services import broadcasts as service

    payload = await service.claim_next()
    if payload is None:
        return False

    broadcast_id = payload["id"]
    keyboard = build_keyboard(payload["buttons"])
    logger.info("Reklama yuborish boshlandi: id=%s", broadcast_id)

    try:
        while True:
            status = await service.current_status(broadcast_id)
            if status != Broadcast.Status.SENDING:
                logger.info(
                    "Reklama yuborish to'xtatildi: id=%s, holat=%s",
                    broadcast_id,
                    status,
                )
                return True

            rows = await service.next_deliveries(broadcast_id, BATCH_SIZE)
            if not rows:
                break

            results: list[tuple[int, str, str]] = []
            for delivery_id, telegram_id in rows:
                state, error = await _deliver(bot, telegram_id, payload, keyboard)
                results.append((delivery_id, state, error))
                await asyncio.sleep(SEND_PAUSE)

            await service.mark_deliveries(results)
            await service.update_counters(broadcast_id)

    except asyncio.CancelledError:
        raise
    except Exception as error:  # pragma: no cover - fon vazifasi to'xtamasin
        logger.exception("Reklama yuborishda kutilmagan xato: id=%s", broadcast_id)
        await service.fail(broadcast_id, str(error))
        return True

    summary = await service.finish(broadcast_id)
    if summary:
        logger.info(
            "Reklama yakunlandi: id=%s, yetkazildi=%s/%s",
            broadcast_id,
            summary["sent"],
            summary["total"],
        )
        await _notify_admins(bot, summary)
    return True


async def _notify_admins(bot: Bot, summary: dict) -> None:
    """Yuborish yakunlangani haqida adminlarga qisqa hisobot."""
    from bot.services import broadcasts as service
    from bot.texts import admin as TA
    from core.text_utils import esc

    recipients = await service.report_recipients()
    if not recipients:
        return

    text = TA.BROADCAST_DONE.format(
        title=esc(summary["title"]),
        total=summary["total"],
        sent=summary["sent"],
        blocked=summary["blocked"],
        failed=summary["failed"],
    )
    for telegram_id in recipients:
        try:
            await bot.send_message(telegram_id, text)
        except TelegramAPIError as error:
            logger.warning(
                "Reklama hisobotini yuborib bo'lmadi (%s): %s", telegram_id, error
            )
        await asyncio.sleep(0.05)


async def broadcast_loop(bot: Bot, interval: int = QUEUE_INTERVAL) -> None:
    """Navbatni doimiy kuzatib turadigan tsikl."""
    while True:
        worked = False
        try:
            worked = await process_test_sends(bot)
            worked = await process_queue(bot) or worked
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception:  # pragma: no cover - fon vazifasi to'xtamasin
            logger.exception("Reklama navbatini tekshirishda xato")

        # Ish bo'lsa darhol keyingisiga o'tamiz, bo'lmasa biroz kutamiz.
        await asyncio.sleep(0.5 if worked else max(2, interval))


__all__ = [
    "broadcast_loop",
    "process_queue",
    "process_test_sends",
    "build_keyboard",
    "QUEUE_INTERVAL",
    "MESSAGES_PER_SECOND",
    "BATCH_SIZE",
]
