"""
Javoblarni yakuniy yuborish.

Muhim (TZ): ID kod faqat shu bosqichda — javoblar bazaga muvaffaqiyatli
saqlangandan keyin — "Ishlatilgan" holatiga o'tadi.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline, reply
from bot.keyboards.factories import QuestionCB
from bot.services import attempts as attempt_service
from bot.states import TakingStates
from bot.texts import common as TC
from bot.texts import exam as TE

logger = logging.getLogger(__name__)

router = Router(name="taking.finish")


# ==========================================================================
#  Tasdiqlash
# ==========================================================================


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "finish")
)
async def ask_confirmation(callback: CallbackQuery, state: FSMContext) -> None:
    """Yakuniy yuborishni tasdiqlashni so'raydi."""
    await callback.answer()

    data = await state.get_data()
    attempt_id = int(data.get("attempt_id", 0) or 0)
    exam_id = int(data.get("exam_id", 0) or 0)
    total = int(data.get("total", 0) or 0)

    from bot.services import exams as exam_service

    orders = await exam_service.question_orders(exam_id)
    answered = await attempt_service.answered_orders(attempt_id)
    unanswered = [order for order in orders if order not in answered]

    warning = ""
    if unanswered:
        warning = TE.UNANSWERED_WARNING.format(
            orders=", ".join(str(order) for order in unanswered[:30])
        )

    await state.set_state(TakingStates.confirming)
    await callback.message.answer(
        TE.CONFIRM_SUBMIT.format(
            answered=len(answered), total=total, unanswered=warning
        ),
        reply_markup=inline.confirm_submit(),
    )


@router.callback_query(
    StateFilter(TakingStates.confirming), QuestionCB.filter(F.action == "jump")
)
async def back_to_questions(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Testga qaytish."""
    await callback.answer()
    await state.set_state(TakingStates.answering)

    data = await state.get_data()
    order = callback_data.order or int(data.get("order", 1) or 1)

    from .flow import send_question

    await send_question(callback.message, state, order)


# ==========================================================================
#  Yuborish
# ==========================================================================


@router.callback_query(
    StateFilter(TakingStates.confirming), QuestionCB.filter(F.action == "submit")
)
async def submit(callback: CallbackQuery, state: FSMContext, user, is_admin: bool) -> None:
    """Javoblarni yakuniy yuboradi."""
    await callback.answer()

    data = await state.get_data()
    attempt = await attempt_service.get_attempt(int(data.get("attempt_id", 0) or 0))
    if attempt is None:
        await state.clear()
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    try:
        attempt = await attempt_service.submit_attempt(attempt)
    except Exception:
        logger.exception("Javoblarni yuborishda xato: attempt_id=%s", attempt.id)
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    await state.clear()
    await _show_submission_result(callback.message, attempt, is_admin)


async def _show_submission_result(message: Message, attempt, is_admin: bool) -> None:
    """Yuborishdan keyingi xabarni ko'rsatadi."""
    snapshot = await attempt_service.result_snapshot(attempt.id)

    # Klaviaturani asosiy menyuga qaytaramiz.
    await message.answer(TE.SUBMITTED, reply_markup=reply.main_menu(is_admin))

    if not snapshot["show_results"]:
        await message.answer(TE.RESULT_HIDDEN, reply_markup=inline.back_to_menu())
        return

    if snapshot["uses_rasch"]:
        # RASH natijasi faqat admin natijalarni e'lon qilgandan keyin ma'lum bo'ladi.
        await message.answer(
            TE.SUBMITTED_WITH_RESULT.format(
                correct=snapshot["correct"],
                total=f"{snapshot['max_raw_score']:g}",
                wrong=snapshot["wrong"],
                empty=snapshot["empty"],
                percent=snapshot["percent"],
            )
            + TE.RESULTS_LATER,
            reply_markup=inline.back_to_menu(),
        )
        return

    text = TE.SUBMITTED_WITH_RESULT.format(
        correct=snapshot["correct"],
        total=f"{snapshot['max_raw_score']:g}",
        wrong=snapshot["wrong"],
        empty=snapshot["empty"],
        percent=snapshot["percent"],
    )
    await message.answer(
        text,
        reply_markup=inline.result_actions(
            attempt,
            show_answers=snapshot["show_answers"],
            show_rating=snapshot["show_rating"],
            certificate=False,
        ),
    )


__all__ = ["router"]
