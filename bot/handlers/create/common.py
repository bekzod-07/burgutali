"""
Test yaratish: tur, nom va tuzilmani tanlash.

TZ bo'yicha oddiy va bepul RASH testini har qanday ro'yxatdan o'tgan
foydalanuvchi yaratishi mumkin; pullik RASH testini esa faqat asosiy admin.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline, reply
from bot.keyboards.factories import CreateCB
from bot.states import CreateExamStates
from bot.texts import exam as TE
from core import constants as C

router = Router(name="create.common")


# ==========================================================================
#  1-bosqich: test turini tanlash
# ==========================================================================


async def start_creation(message: Message, state: FSMContext, is_admin: bool) -> None:
    """Sehrgarni boshlaydi."""
    await state.set_state(CreateExamStates.choosing_type)
    await message.answer(
        TE.CHOOSE_TYPE,
        reply_markup=inline.exam_types(is_admin),
    )


@router.callback_query(
    StateFilter(CreateExamStates.choosing_type), CreateCB.filter(F.action == "type")
)
async def choose_type(
    callback: CallbackQuery,
    callback_data: CreateCB,
    state: FSMContext,
    is_admin: bool,
) -> None:
    """Test turi tanlandi."""
    exam_type = callback_data.value

    if exam_type == "rasch_paid" and not is_admin:
        await callback.answer()
        await callback.message.answer(TE.PAID_ADMIN_ONLY)
        return

    await callback.answer()
    await state.update_data(exam_type=exam_type)
    await state.set_state(CreateExamStates.waiting_title)
    await callback.message.answer(TE.ASK_TITLE, reply_markup=reply.cancel_only())


# ==========================================================================
#  2-bosqich: test nomi
# ==========================================================================


@router.message(StateFilter(CreateExamStates.waiting_title), F.text)
async def receive_title(message: Message, state: FSMContext) -> None:
    """Test nomini qabul qiladi."""
    title = (message.text or "").strip()
    if len(title) < 3:
        await message.answer(TE.INVALID_TITLE)
        return

    await state.update_data(title=title[:150])
    data = await state.get_data()

    if data.get("exam_type") == "simple":
        # Oddiy testda tuzilma doim bir xil: A/B/C/D savollari.
        await state.update_data(national=False)
        await _ask_question_count(message, state)
        return

    await state.set_state(CreateExamStates.choosing_structure)
    await message.answer(TE.ASK_STRUCTURE, reply_markup=inline.exam_structure())


# ==========================================================================
#  3-bosqich: tuzilma
# ==========================================================================


@router.callback_query(
    StateFilter(CreateExamStates.choosing_structure),
    CreateCB.filter(F.action == "structure"),
)
async def choose_structure(
    callback: CallbackQuery, callback_data: CreateCB, state: FSMContext
) -> None:
    """Tuzilma tanlandi: milliy shablon yoki o'zi belgilaydi."""
    await callback.answer()

    if callback_data.value == "national":
        single = C.NATIONAL_SINGLE_RANGE[1] - C.NATIONAL_SINGLE_RANGE[0] + 1
        multi = C.NATIONAL_MULTI_RANGE[1] - C.NATIONAL_MULTI_RANGE[0] + 1
        open_count = C.NATIONAL_OPEN_RANGE[1] - C.NATIONAL_OPEN_RANGE[0] + 1
        await state.update_data(
            national=True,
            question_count=C.NATIONAL_TOTAL_QUESTIONS,
            single_count=single,
            multi_count=multi,
            open_count=open_count,
        )
        from .keys import ask_next_key_step

        await ask_next_key_step(callback.message, state)
        return

    await state.update_data(national=False)
    await _ask_question_count(callback.message, state)


async def _ask_question_count(message: Message, state: FSMContext) -> None:
    """Savollar sonini so'raydi."""
    await state.set_state(CreateExamStates.waiting_question_count)
    await message.answer(TE.ASK_QUESTION_COUNT, reply_markup=inline.question_counts())


@router.callback_query(
    StateFilter(CreateExamStates.waiting_question_count),
    CreateCB.filter(F.action == "count"),
)
async def choose_count_button(
    callback: CallbackQuery, callback_data: CreateCB, state: FSMContext
) -> None:
    """Tayyor variantlardan savollar soni tanlandi."""
    await callback.answer()
    try:
        count = int(callback_data.value)
    except ValueError:
        await callback.message.answer(TE.INVALID_QUESTION_COUNT)
        return
    await _save_count(callback.message, state, count)


@router.message(StateFilter(CreateExamStates.waiting_question_count), F.text)
async def receive_count(message: Message, state: FSMContext) -> None:
    """Qo'lda yozilgan savollar soni."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(TE.INVALID_QUESTION_COUNT)
        return
    count = int(raw)
    if not (1 <= count <= 500):
        await message.answer(TE.INVALID_QUESTION_COUNT)
        return
    await _save_count(message, state, count)


async def _save_count(message: Message, state: FSMContext, count: int) -> None:
    """Savollar sonini saqlaydi va kalitlar bosqichiga o'tadi."""
    await state.update_data(
        question_count=count,
        single_count=count,
        multi_count=0,
        open_count=0,
    )
    from .keys import ask_next_key_step

    await ask_next_key_step(message, state)


__all__ = ["router", "start_creation"]
