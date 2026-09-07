"""
Savollarga javob berish oqimi.

Har bir javob darhol bazaga saqlanadi — internet uzilsa ham foydalanuvchi
qoldirgan joyidan davom ettiradi (urinish DRAFT holatida saqlanib turadi).
"""

from __future__ import annotations

import json
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import get_config
from bot.keyboards import inline, reply
from bot.keyboards.factories import QuestionCB
from bot.services import attempts as attempt_service
from bot.services import exams as exam_service
from bot.states import TakingStates
from bot.texts import common as TC
from bot.texts import exam as TE
from bot.utils.formatting import answers_overview
from core.text_utils import esc, shorten

logger = logging.getLogger(__name__)

router = Router(name="taking.flow")


# ==========================================================================
#  Savolni ko'rsatish
# ==========================================================================


async def send_question(
    message: Message,
    state: FSMContext,
    order: int,
    *,
    edit: bool = False,
) -> None:
    """Berilgan tartib raqamli savolni yuboradi (yoki xabarni tahrirlaydi)."""
    data = await state.get_data()
    attempt_id = int(data.get("attempt_id", 0) or 0)
    exam_id = int(data.get("exam_id", 0) or 0)
    total = int(data.get("total", 0) or 0)

    if not attempt_id or not exam_id:
        await message.answer(TC.ERROR_GENERIC)
        return

    order = max(1, min(int(order or 1), max(total, 1)))
    question = await exam_service.get_question(exam_id, order)
    if question is None:
        await message.answer("Savol topilmadi.")
        return

    selected, text_a, text_b = await attempt_service.answer_values(attempt_id, order)

    await state.update_data(order=order)
    attempt = await attempt_service.get_attempt(attempt_id)
    if attempt is not None:
        await attempt_service.set_current_order(attempt, order)

    text = _question_text(question, order, total, selected, text_a, text_b)
    markup = _question_markup(question, selected, total)

    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except Exception:  # pragma: no cover - xabar o'zgarmagan bo'lishi mumkin
            pass

    await message.answer(text, reply_markup=markup)


def _question_text(
    question, order: int, total: int, selected: str, text_a: str, text_b: str
) -> str:
    """Savol matnini shakllantiradi."""
    progress = TC.progress_bar(order, total)
    body = f"\n{esc(question.text)}\n" if question.text else "\n"

    if question.kind == "single":
        text = TE.QUESTION_SINGLE.format(
            order=order, total=total, progress=progress, text=body
        )
    elif question.kind == "multi":
        text = TE.QUESTION_MULTI.format(
            order=order, total=total, progress=progress, text=body
        )
    elif int(question.parts or 1) >= 2:
        text = TE.QUESTION_OPEN.format(
            order=order, total=total, progress=progress, text=body
        )
    else:
        text = TE.QUESTION_OPEN_SINGLE_PART.format(
            order=order, total=total, progress=progress, text=body
        )

    current = _current_answer_label(question, selected, text_a, text_b)
    if current:
        text += f"\n\nJoriy javobingiz: <b>{esc(current)}</b>"
    return text


def _current_answer_label(question, selected: str, text_a: str, text_b: str) -> str:
    """Saqlangan javobning qisqa ko'rinishi."""
    if question.kind in {"single", "multi"}:
        return selected or ""
    parts = []
    if text_a:
        parts.append(f"a) {text_a}")
    if text_b:
        parts.append(f"b) {text_b}")
    return "; ".join(parts)


def _question_markup(question, selected: str, total: int):
    """Savol turiga mos inline klaviatura."""
    if question.kind == "single":
        return inline.question_single(question, selected, total)
    if question.kind == "multi":
        return inline.question_multi(question, selected, total)
    return inline.question_open(question, total)


# ==========================================================================
#  Variantli javoblar
# ==========================================================================


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "pick")
)
async def pick_single(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Bitta javobli savolda variant tanlandi."""
    data = await state.get_data()
    attempt = await attempt_service.get_attempt(int(data.get("attempt_id", 0) or 0))
    question = await exam_service.get_question(
        int(data.get("exam_id", 0) or 0), callback_data.order
    )
    if attempt is None or question is None:
        await callback.answer(TC.ERROR_GENERIC, show_alert=True)
        return

    await attempt_service.save_answer(attempt, question, selected=callback_data.value or "")
    await callback.answer(callback_data.value or "")

    total = int(data.get("total", 0) or 0)
    next_order = callback_data.order + 1
    if next_order > total:
        await _show_review(callback.message, state)
        return
    await send_question(callback.message, state, next_order)


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "toggle")
)
async def toggle_multi(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Ko'p javobli savolda variantni belgilash/olib tashlash."""
    data = await state.get_data()
    attempt = await attempt_service.get_attempt(int(data.get("attempt_id", 0) or 0))
    question = await exam_service.get_question(
        int(data.get("exam_id", 0) or 0), callback_data.order
    )
    if attempt is None or question is None:
        await callback.answer(TC.ERROR_GENERIC, show_alert=True)
        return

    value = await attempt_service.toggle_multi_choice(
        attempt, question, callback_data.value or ""
    )
    await callback.answer(value or "—")
    await send_question(callback.message, state, callback_data.order, edit=True)


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "clear")
)
async def clear_multi(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Ko'p javobli savolda tanlovni tozalash."""
    data = await state.get_data()
    attempt = await attempt_service.get_attempt(int(data.get("attempt_id", 0) or 0))
    question = await exam_service.get_question(
        int(data.get("exam_id", 0) or 0), callback_data.order
    )
    if attempt is None or question is None:
        await callback.answer(TC.ERROR_GENERIC, show_alert=True)
        return

    await attempt_service.save_answer(attempt, question, selected="")
    await callback.answer("Tozalandi")
    await send_question(callback.message, state, callback_data.order, edit=True)


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "confirm")
)
async def confirm_multi(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Ko'p javobli savol javobini tasdiqlash."""
    await callback.answer("Saqlandi")
    data = await state.get_data()
    total = int(data.get("total", 0) or 0)
    next_order = callback_data.order + 1
    if next_order > total:
        await _show_review(callback.message, state)
        return
    await send_question(callback.message, state, next_order)


# ==========================================================================
#  Ochiq javoblar
# ==========================================================================


@router.message(StateFilter(TakingStates.answering), F.web_app_data)
async def receive_web_app_answer(message: Message, state: FSMContext) -> None:
    """Web ilova yuborgan javob."""
    raw = message.web_app_data.data if message.web_app_data else ""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        await message.answer(TE.ANSWER_EMPTY)
        return

    text_a = str(payload.get("a", "")).strip()
    text_b = str(payload.get("b", "")).strip()
    data = await state.get_data()
    order = int(payload.get("q") or data.get("order") or 1)
    await _store_open_answer(message, state, order, text_a, text_b)


@router.message(StateFilter(TakingStates.answering), F.text)
async def receive_text_answer(message: Message, state: FSMContext) -> None:
    """Ochiq savolga matn ko'rinishida berilgan javob."""
    data = await state.get_data()
    order = int(data.get("order", 1) or 1)
    exam_id = int(data.get("exam_id", 0) or 0)

    question = await exam_service.get_question(exam_id, order)
    if question is None:
        await message.answer(TC.ERROR_GENERIC)
        return

    raw = (message.text or "").strip()
    if not raw:
        await message.answer(TE.ANSWER_EMPTY)
        return

    if question.kind in {"single", "multi"}:
        letters = "".join(
            sorted({ch.upper() for ch in raw if ch.isalpha()})
        )
        allowed = set(question.choice_letters)
        if letters and set(letters) <= allowed:
            if question.kind == "single" and len(letters) > 1:
                await message.answer("Bu savolda faqat bitta variant tanlanadi.")
                return
            attempt = await attempt_service.get_attempt(int(data.get("attempt_id", 0) or 0))
            await attempt_service.save_answer(attempt, question, selected=letters)
            await message.answer(TE.ANSWER_SAVED.format(value=esc(letters)))
            await _advance(message, state, order)
            return
        await message.answer(
            "Javobni tugmalar orqali tanlang yoki variant harfini yozing "
            f"({', '.join(question.choice_letters)})."
        )
        return

    parts = [piece.strip() for piece in raw.replace("|", ";").split(";")]
    text_a = parts[0] if parts else ""
    text_b = parts[1] if len(parts) > 1 else ""
    await _store_open_answer(message, state, order, text_a, text_b)


async def _store_open_answer(
    message: Message, state: FSMContext, order: int, text_a: str, text_b: str
) -> None:
    """Ochiq javobni saqlaydi va keyingi savolga o'tadi."""
    data = await state.get_data()
    attempt = await attempt_service.get_attempt(int(data.get("attempt_id", 0) or 0))
    question = await exam_service.get_question(int(data.get("exam_id", 0) or 0), order)

    if attempt is None or question is None:
        await message.answer(TC.ERROR_GENERIC)
        return
    if not text_a and not text_b:
        await message.answer(TE.ANSWER_EMPTY)
        return

    await attempt_service.save_answer(
        attempt, question, text_a=text_a, text_b=text_b
    )
    label = "; ".join(
        piece for piece in (f"a) {text_a}" if text_a else "", f"b) {text_b}" if text_b else "")
        if piece
    )
    await message.answer(TE.ANSWER_SAVED.format(value=esc(shorten(label, 80))))
    await _advance(message, state, order)


async def _advance(message: Message, state: FSMContext, order: int) -> None:
    """Keyingi savolga o'tadi yoki ko'rib chiqish sahifasini ochadi."""
    data = await state.get_data()
    total = int(data.get("total", 0) or 0)
    if order + 1 > total:
        await _show_review(message, state)
        return
    await send_question(message, state, order + 1)


# ==========================================================================
#  Navigatsiya
# ==========================================================================


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "prev")
)
async def go_previous(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Oldingi savol."""
    await callback.answer()
    await send_question(callback.message, state, max(1, callback_data.order - 1))


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "next")
)
async def go_next(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Keyingi savol."""
    await callback.answer()
    data = await state.get_data()
    total = int(data.get("total", 0) or 0)
    await send_question(callback.message, state, min(total, callback_data.order + 1))


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "jump")
)
async def jump_to(
    callback: CallbackQuery, callback_data: QuestionCB, state: FSMContext
) -> None:
    """Belgilangan savolga o'tish."""
    await callback.answer()
    data = await state.get_data()
    order = callback_data.order or int(data.get("order", 1) or 1)
    await send_question(callback.message, state, order)


@router.callback_query(
    StateFilter(TakingStates.answering), QuestionCB.filter(F.action == "review")
)
async def review(callback: CallbackQuery, state: FSMContext) -> None:
    """Javoblarni ko'rib chiqish."""
    await callback.answer()
    await _show_review(callback.message, state)


async def _show_review(message: Message, state: FSMContext) -> None:
    """Javoblar holatini ko'rsatadi."""
    data = await state.get_data()
    attempt_id = int(data.get("attempt_id", 0) or 0)
    exam_id = int(data.get("exam_id", 0) or 0)
    total = int(data.get("total", 0) or 0)

    orders = await exam_service.question_orders(exam_id)
    answered = await attempt_service.answered_orders(attempt_id)
    unanswered = [order for order in orders if order not in answered]

    text = TE.REVIEW_TITLE.format(
        answered=len(answered),
        total=total,
        rows=answers_overview(orders, answered),
    )
    if unanswered:
        text += "\n\n" + TE.UNANSWERED_WARNING.format(
            orders=", ".join(str(order) for order in unanswered[:30])
        )

    await message.answer(
        text, reply_markup=inline.review_navigation(total, unanswered)
    )


__all__ = ["router", "send_question"]
