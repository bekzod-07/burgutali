"""
Testga kirish.

Bosqichlar:
  1. test kodini kiritish yoki ochiq testlar ro'yxatidan tanlash;
  2. qatnashish huquqini tekshirish;
  3. pullik testda bir martalik ID kodni tekshirish va faollashtirish;
  4. urinishni ochish va birinchi savolni yuborish.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline, reply
from bot.keyboards.factories import ExamCB
from bot.services import attempts as attempt_service
from bot.services import codes as code_service
from bot.services import exams as exam_service
from bot.states import TakingStates
from bot.texts import exam as TE
from bot.utils.formatting import format_datetime
from core.text_utils import esc

logger = logging.getLogger(__name__)

router = Router(name="taking.entry")


# ==========================================================================
#  Testni tanlash
# ==========================================================================


async def open_take_menu(message: Message, state: FSMContext, user) -> None:
    """
    Test kodini so'raydi.

    Testlar ro'yxati ishtirokchilarga ko'rsatilmaydi — testga faqat
    tashkilotchi bergan kod orqali kiriladi.
    """
    await state.set_state(TakingStates.waiting_exam_code)
    await message.answer(TE.ASK_EXAM_CODE, reply_markup=reply.cancel_only())


@router.message(StateFilter(TakingStates.waiting_exam_code), F.text)
async def receive_exam_code(message: Message, state: FSMContext, user) -> None:
    """Kiritilgan test kodi."""
    await open_exam_by_code(message, state, user, message.text or "")


async def open_exam_by_code(
    message: Message, state: FSMContext, user, code: str
) -> None:
    """Kod bo'yicha testni topadi va ma'lumotini ko'rsatadi."""
    exam = await exam_service.get_exam_by_code(code)
    if exam is None:
        await message.answer(TE.EXAM_NOT_FOUND)
        return
    await show_exam_card(message, state, user, exam)


@router.callback_query(ExamCB.filter(F.action == "open"))
async def callback_open_exam(
    callback: CallbackQuery, callback_data: ExamCB, state: FSMContext, user
) -> None:
    """Ro'yxatdan test tanlandi."""
    await callback.answer()
    exam = await exam_service.get_exam(callback_data.exam_id)
    if exam is None:
        await callback.message.answer(TE.EXAM_NOT_FOUND)
        return
    await show_exam_card(callback.message, state, user, exam)


async def show_exam_card(message: Message, state: FSMContext, user, exam) -> None:
    """Test haqidagi ma'lumot va «Boshlash» tugmasi."""
    check = await attempt_service.can_participate(user, exam)
    participants = await attempt_service.participants_count(exam)
    summary = await exam_service.exam_summary(exam)

    extra = ""
    if exam.requires_access_code:
        extra += "Kirish uchun bir martalik ID kod talab qilinadi.\n"
    if exam.can_issue_certificate:
        extra += "Test yakunida sertifikat beriladi.\n"
    if not check.ok:
        extra += f"\n{esc(check.message)}"

    text = TE.EXAM_INFO.format(
        title=esc(exam.title),
        type=esc(exam.get_exam_type_display()),
        questions=exam.question_count,
        max_score=f"{summary['max_raw_score']:g}",
        ends_at=format_datetime(exam.ends_at),
        participants=participants,
        extra=extra,
    )

    if check.ok:
        await state.update_data(exam_id=exam.id)
        await message.answer(text, reply_markup=inline.exam_entry(exam))
    else:
        await message.answer(text, reply_markup=inline.back_to_menu())


# ==========================================================================
#  Testni boshlash
# ==========================================================================


@router.callback_query(ExamCB.filter(F.action == "take"))
async def callback_take_exam(
    callback: CallbackQuery, callback_data: ExamCB, state: FSMContext, user
) -> None:
    """«Testni boshlash» tugmasi."""
    await callback.answer()

    exam = await exam_service.get_exam(callback_data.exam_id)
    if exam is None:
        await callback.message.answer(TE.EXAM_NOT_FOUND)
        return

    check = await attempt_service.can_participate(user, exam)
    if not check.ok:
        await callback.message.answer(esc(check.message))
        return

    await state.update_data(exam_id=exam.id)

    if exam.requires_access_code:
        await state.set_state(TakingStates.waiting_access_code)
        await callback.message.answer(
            TE.ASK_ACCESS_CODE, reply_markup=reply.cancel_only()
        )
        return

    await begin_attempt(callback.message, state, user, exam, access_code=None)


# ==========================================================================
#  ID kod (pullik test)
# ==========================================================================


@router.message(StateFilter(TakingStates.waiting_access_code), F.text)
async def receive_access_code(message: Message, state: FSMContext, user) -> None:
    """Kiritilgan ID kodni tekshiradi."""
    data = await state.get_data()
    exam = await exam_service.get_exam(int(data.get("exam_id", 0) or 0))
    if exam is None:
        await message.answer(TE.EXAM_NOT_FOUND)
        await state.set_state(None)
        return

    result = await code_service.check_code(message.text or "", exam)
    if not result.ok:
        await message.answer(result.message)
        return

    await message.answer(TE.CODE_CONFIRMED)
    await begin_attempt(message, state, user, exam, access_code=result.code)


# ==========================================================================
#  Urinishni boshlash
# ==========================================================================


async def begin_attempt(
    message: Message, state: FSMContext, user, exam, access_code=None
) -> None:
    """Urinishni ochadi va birinchi savolni yuboradi."""
    attempt = await attempt_service.start_attempt(user, exam, access_code)

    duration = ""
    if exam.ends_at:
        duration = f"⏱ Tugash vaqti: {format_datetime(exam.ends_at)}\n"

    await state.set_state(TakingStates.answering)
    await state.update_data(
        attempt_id=attempt.id,
        exam_id=exam.id,
        total=exam.question_count,
        order=int(attempt.current_order or 1),
    )

    await message.answer(
        TE.EXAM_STARTED.format(questions=exam.question_count, duration=duration),
        reply_markup=reply.remove(),
    )

    from .flow import send_question

    await send_question(message, state, order=int(attempt.current_order or 1))


__all__ = ["router", "open_take_menu", "open_exam_by_code", "begin_attempt"]
