"""
Test yaratish: yakuniy bosqich.

Bu yerda test bazada yaratiladi, javob kalitlari biriktiriladi va
(pullik testdan tashqari) test darhol faollashtiriladi.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils import timezone

from bot.config import get_config
from bot.keyboards import inline, reply
from bot.services import exams as exam_service
from bot.texts import exam as TE
from bot.utils.formatting import format_datetime
from core.text_utils import esc

logger = logging.getLogger(__name__)

router = Router(name="create.finalize")


async def finish_creation(message: Message, state: FSMContext, user) -> None:
    """Testni yaratadi va natijani foydalanuvchiga ko'rsatadi."""
    data = await state.get_data()
    config = get_config()

    exam_type = data.get("exam_type", "simple")
    hours = int(data.get("duration_hours", 0) or 0)

    # Kalendardan aniq sana-vaqt tanlangan bo'lsa — u ustunlik qiladi.
    ends_at = _parse_iso(data.get("ends_at_iso", ""))
    if ends_at is None:
        ends_at = timezone.now() + timedelta(hours=hours) if hours else None

    try:
        exam = await exam_service.create_exam(
            owner=user,
            title=data.get("title", "Nomsiz test"),
            exam_type=exam_type,
            question_count=int(data.get("question_count", 0) or 0),
            national_template=bool(data.get("national")),
            duration_minutes=hours * 60,
            ends_at=ends_at,
            show_results=bool(data.get("show_results", True)),
            show_correct_answers=bool(data.get("show_results", True)),
            certificate_enabled=bool(data.get("certificate", False)),
            organizer_name=user.full_name or "",
        )
    except Exception:
        logger.exception("Test yaratishda xato")
        await state.clear()
        await message.answer(
            "Testni yaratib bo'lmadi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=reply.main_menu(bool(user.is_admin)),
        )
        return

    # --- Javob kalitlarini biriktirish ---
    if data.get("single_keys"):
        await exam_service.apply_single_keys(exam, data["single_keys"])
    if data.get("multi_keys"):
        await exam_service.apply_multi_keys(exam, data["multi_keys"])
    if data.get("open_keys"):
        await exam_service.apply_open_keys(exam, data["open_keys"])

    await state.clear()

    # --- Pullik test: avval ID kodlar kerak ---
    if exam_type == "rasch_paid":
        await message.answer(
            TE.EXAM_CREATED_PAID.format(
                title=esc(exam.title),
                code=exam.code,
                questions=exam.question_count,
            ),
            reply_markup=reply.main_menu(True),
        )
        await message.answer(
            "Nechta ID kod yaratilsin?",
            reply_markup=inline.code_quantities(exam.id),
        )
        return

    # --- Bepul testlar darhol faollashtiriladi ---
    activated, activation_message = await exam_service.activate_exam(exam)
    exam = await exam_service.get_exam(exam.id)

    link = ""
    deep_link = config.exam_deep_link(exam.code)
    if deep_link:
        link = f"Havola: {deep_link}"

    await message.answer(
        TE.EXAM_CREATED.format(
            title=esc(exam.title),
            code=exam.code,
            questions=exam.question_count,
            type=exam.get_exam_type_display(),
            ends_at=format_datetime(exam.ends_at),
            link=link,
        ),
        reply_markup=reply.main_menu(bool(user.is_admin)),
    )

    if not activated:
        await message.answer(activation_message)


def _parse_iso(value: str):
    """FSM da saqlangan ISO sana-vaqtni `datetime` ga aylantiradi."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


__all__ = ["router", "finish_creation"]
