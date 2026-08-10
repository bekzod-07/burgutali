"""
Test yaratish: javob kalitlarini kiritish.

Uch xil kalit ketma-ket so'raladi (agar tegishli savollar mavjud bo'lsa):
  1. bitta javobli savollar (A–D);
  2. ko'p javobli savollar (A–F);
  3. ochiq javobli savollar (a va b).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards import inline
from bot.services import exams as exam_service
from bot.states import CreateExamStates
from bot.texts import exam as TE
from core.text_utils import esc

router = Router(name="create.keys")


# ==========================================================================
#  Keyingi bosqichni aniqlash
# ==========================================================================


async def ask_next_key_step(message: Message, state: FSMContext) -> None:
    """Qaysi kalit hali kiritilmaganini aniqlab, mos savolni beradi."""
    data = await state.get_data()

    if data.get("single_count", 0) and data.get("single_keys") is None:
        await state.set_state(CreateExamStates.waiting_single_keys)
        await message.answer(
            TE.ASK_SINGLE_KEYS.format(count=data["single_count"]),
            reply_markup=inline.cancel(),
        )
        return

    if data.get("multi_count", 0) and data.get("multi_keys") is None:
        await state.set_state(CreateExamStates.waiting_multi_keys)
        await message.answer(
            TE.ASK_MULTI_KEYS.format(count=data["multi_count"]),
            reply_markup=inline.cancel(),
        )
        return

    if data.get("open_count", 0) and data.get("open_keys") is None:
        await state.set_state(CreateExamStates.waiting_open_keys)
        await message.answer(
            TE.ASK_OPEN_KEYS.format(count=data["open_count"]),
            reply_markup=inline.cancel(),
        )
        return

    from .settings import ask_duration

    await ask_duration(message, state)


# ==========================================================================
#  Bitta javobli savollar (A–D)
# ==========================================================================


@router.message(StateFilter(CreateExamStates.waiting_single_keys), F.text)
async def receive_single_keys(message: Message, state: FSMContext) -> None:
    """A–D kalitini qabul qiladi."""
    data = await state.get_data()
    count = int(data.get("single_count", 0))

    result = exam_service.parse_single_key(message.text or "", count)
    if not result.ok:
        await message.answer(TE.KEY_ERRORS.format(errors=_format_errors(result.errors)))
        return

    await state.update_data(single_keys=result.keys)
    await message.answer(TE.KEYS_SAVED)
    await ask_next_key_step(message, state)


# ==========================================================================
#  Ko'p javobli savollar (A–F)
# ==========================================================================


@router.message(StateFilter(CreateExamStates.waiting_multi_keys), F.text)
async def receive_multi_keys(message: Message, state: FSMContext) -> None:
    """A–F ko'p javobli kalitni qabul qiladi."""
    data = await state.get_data()
    count = int(data.get("multi_count", 0))

    result = exam_service.parse_multi_key(message.text or "", count)
    if not result.ok:
        await message.answer(TE.KEY_ERRORS.format(errors=_format_errors(result.errors)))
        return

    await state.update_data(multi_keys=result.keys)
    await message.answer(TE.KEYS_SAVED)
    await ask_next_key_step(message, state)


# ==========================================================================
#  Ochiq javobli savollar
# ==========================================================================


@router.message(StateFilter(CreateExamStates.waiting_open_keys), F.text)
async def receive_open_keys(message: Message, state: FSMContext) -> None:
    """Ochiq javoblar kalitini qabul qiladi."""
    data = await state.get_data()
    count = int(data.get("open_count", 0))

    result = exam_service.parse_open_key(message.text or "", count)
    if not result.ok:
        await message.answer(TE.KEY_ERRORS.format(errors=_format_errors(result.errors)))
        return

    await state.update_data(open_keys=result.keys)
    await message.answer(TE.KEYS_SAVED)
    await ask_next_key_step(message, state)


# ==========================================================================
#  Yordamchi
# ==========================================================================


def _format_errors(errors: list[str], limit: int = 8) -> str:
    """Xatolar ro'yxatini matnga aylantiradi."""
    shown = [f"• {esc(error)}" for error in errors[:limit]]
    if len(errors) > limit:
        shown.append(f"• ... yana {len(errors) - limit} ta xato")
    return "\n".join(shown)


__all__ = ["router", "ask_next_key_step"]
