"""
Fon vazifalari.

Ikkita vazifa bajariladi:

  1. **Testlarni avtomatik tugatish va tozalash** — tugash vaqti o'tgan
     faol testlar tugatiladi (javob qabul qilish to'xtaydi, natijalar
     hisoblanib e'lon qilinadi). Faol bo'lmagan testlar esa 24 soatdan
     keyin bazadan butunlay o'chiriladi — ro'yxatda faqat faol testlar
     qoladi.

  2. **Adminga umumiy natijalar hisobotini yuborish** — 2- va 3-tur (RASH)
     testlari yopilganda va natijalar e'lon qilinganda umumiy natijalar
     PDF ko'rinishida test egasiga va asosiy adminlarga yuboriladi.
     Hisobot testning qayerda yopilganidan (bot, web ilova yoki panel)
     qat'i nazar yuboriladi — vazifa bazadagi belgilarga qarab ishlaydi.

  3. **Reklama xabarlarini yuborish** — panelda tayyorlangan ommaviy
     xabar (matn, rasm, tugmalar) foydalanuvchilarga yetkaziladi
     (`bot/tasks/broadcast.py`).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import get_config
from bot.texts import admin as TA
from bot.utils.files import document, timestamped_name
from core.text_utils import esc

logger = logging.getLogger(__name__)

#: Hisobotlarni tekshirish oralig'i (sekund).
REPORT_INTERVAL: int = 60


async def auto_close_loop(interval: int) -> None:
    """
    Vaqti tugagan testlarni tugatadi va eskirganlarini tozalaydi.

    Ikkita ish bir oraliqda bajariladi:
      * tugash vaqti o'tgan faol test tugatiladi — natijalari hisoblanib
        e'lon qilinadi;
      * faol bo'lmagan test 24 soatdan keyin bazadan o'chiriladi.
    """
    from bot.services import exams as exam_service

    while True:
        try:
            closed = await exam_service.auto_close_expired()
            if closed:
                logger.info("Vaqti tugagan %s ta test avtomatik tugatildi.", closed)
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception:  # pragma: no cover - fon vazifasi to'xtamasin
            logger.exception("Testlarni avtomatik tugatishda xato")

        try:
            purged = await exam_service.auto_purge_finished()
            if purged:
                logger.info("%s ta eskirgan test avtomatik o'chirildi.", purged)
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception:  # pragma: no cover - fon vazifasi to'xtamasin
            logger.exception("Eskirgan testlarni tozalashda xato")

        await asyncio.sleep(max(15, interval))


async def results_report_loop(bot: Bot, interval: int) -> None:
    """Yopilgan va e'lon qilingan testlar bo'yicha adminga PDF yuboradi."""
    from bot.services import reports as report_service

    while True:
        try:
            pending = await report_service.exams_awaiting_report()
            for exam_id, reason in pending:
                await _send_report(bot, exam_id, reason)
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception:  # pragma: no cover - fon vazifasi to'xtamasin
            logger.exception("Natijalar hisobotini yuborishda xato")
        await asyncio.sleep(max(30, interval))


async def _send_report(bot: Bot, exam_id: int, reason: str) -> None:
    """Bitta test bo'yicha hisobotni tayyorlaydi va yuboradi."""
    from bot.services import reports as report_service

    try:
        payload = await report_service.prepare_report(exam_id, reason)
    except Exception:
        logger.exception("Hisobotni tayyorlashda xato: exam_id=%s", exam_id)
        return

    if payload is None:
        # Test o'chirilgan — qayta urinishning hojati yo'q.
        return

    recipients = payload["recipients"]
    if not recipients:
        logger.warning(
            "Hisobotni yuborish uchun admin topilmadi: exam_id=%s", exam_id
        )
        await report_service.mark_report_sent_by_id(exam_id, reason)
        return

    if not payload["participants"]:
        text = TA.REPORT_NO_PARTICIPANTS.format(
            title=esc(payload["title"]), code=esc(payload["code"])
        )
        await _broadcast(bot, recipients, text, None, "")
        await report_service.mark_report_sent_by_id(exam_id, reason)
        return

    template = TA.REPORT_PUBLISHED if reason == "published" else TA.REPORT_CLOSED
    caption = template.format(
        title=esc(payload["title"]),
        code=esc(payload["code"]),
        type=esc(payload["type"]),
        participants=payload["participants"],
    )
    # 1-fayl — e'lon uchun: nechta to'g'ri topgani ko'rinmaydi, uni
    # kanalga qo'yish mumkin.
    filename = timestamped_name("umumiy-natijalar", "pdf", payload["code"])
    await _broadcast(bot, recipients, caption, payload["pdf"], filename)

    # 2-fayl — faqat adminlar uchun: to'g'ri javoblar soni bilan to'liq
    # hisobot. Kanalga qo'yiladigan faylda bu ma'lumot bo'lmasligi kerak.
    if payload.get("admin_pdf"):
        admin_caption = TA.REPORT_ADMIN_COPY.format(
            title=esc(payload["title"]), code=esc(payload["code"])
        )
        admin_name = timestamped_name("admin-hisobot", "pdf", payload["code"])
        await _broadcast(
            bot, recipients, admin_caption, payload["admin_pdf"], admin_name
        )

    # Savollar qiyinchiligi va ballar taqsimoti — faqat adminlarga.
    await _broadcast_charts(bot, recipients, payload)

    await report_service.mark_report_sent_by_id(exam_id, reason)
    logger.info(
        "Natijalar hisoboti yuborildi: exam_id=%s, sabab=%s, qabul qiluvchilar=%s",
        exam_id,
        reason,
        len(recipients),
    )


async def _broadcast_charts(bot: Bot, recipients: list[int], payload: dict) -> None:
    """
    Diagrammalarni adminlarga rasm ko'rinishida yuboradi.

    Talab: savollarning qiyinchilik darajasi RASH testlarida ustunli
    diagramma ko'rinishida va **faqat adminga** ko'rsatiladi.
    """
    images = payload.get("images") or []
    if not images:
        return

    captions = {
        "qiyinchilik": TA.REPORT_CHART_DIFFICULTY,
        "ballar-taqsimoti": TA.REPORT_CHART_DISTRIBUTION,
    }
    for telegram_id in recipients:
        for kind, image in images:
            name = timestamped_name(kind, "png", payload["code"])
            try:
                await bot.send_photo(
                    telegram_id,
                    document(image, name),
                    caption=captions.get(kind, ""),
                )
            except TelegramAPIError as error:
                logger.warning(
                    "Diagrammani yuborib bo'lmadi (%s): %s", telegram_id, error
                )
            except Exception:  # pragma: no cover
                logger.exception("Diagrammani yuborishda kutilmagan xato: %s", telegram_id)
            await asyncio.sleep(0.05)


async def _broadcast(
    bot: Bot, recipients: list[int], caption: str, pdf: bytes | None, filename: str
) -> None:
    """Hisobotni barcha adminlarga yuboradi (xatoliklar yig'ilib qolmaydi)."""
    for telegram_id in recipients:
        try:
            if pdf:
                await bot.send_document(
                    telegram_id, document(pdf, filename), caption=caption
                )
            else:
                await bot.send_message(telegram_id, caption)
        except TelegramAPIError as error:
            logger.warning("Hisobotni yuborib bo'lmadi (%s): %s", telegram_id, error)
        except Exception:  # pragma: no cover
            logger.exception("Hisobotni yuborishda kutilmagan xato: %s", telegram_id)
        await asyncio.sleep(0.05)


def start_scheduler(bot: Bot | None = None) -> list[asyncio.Task]:
    """Fon vazifalarini ishga tushiradi va ularning ro'yxatini qaytaradi."""
    from bot.tasks.broadcast import QUEUE_INTERVAL, broadcast_loop

    config = get_config()
    tasks = [asyncio.create_task(auto_close_loop(config.auto_close_interval))]
    if bot is not None:
        tasks.append(asyncio.create_task(results_report_loop(bot, REPORT_INTERVAL)))
        tasks.append(asyncio.create_task(broadcast_loop(bot, QUEUE_INTERVAL)))
    logger.info("Fon vazifalari ishga tushdi (%s ta).", len(tasks))
    return tasks


__all__ = [
    "start_scheduler",
    "auto_close_loop",
    "results_report_loop",
    "REPORT_INTERVAL",
]
