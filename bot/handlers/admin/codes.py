"""
Bir martalik ID kodlarni yaratish (TZ: "Pullik RASH testi").

Oqim:
  1. admin testni tanlaydi;
  2. kodlar miqdorini tanlaydi (500 / 1000 / 1500 / 2000 / 3000 / boshqa);
  3. bot noyob kodlarni yaratadi va Excel fayl ko'rinishida yuboradi.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline
from bot.keyboards.factories import CodesCB, MenuCB
from bot.services import codes as code_service
from bot.services import exams as exam_service
from bot.states import AdminStates
from bot.texts import admin as TA
from bot.texts import common as TC
from bot.utils.files import document, timestamped_name
from core import constants as C
from core.text_utils import esc

logger = logging.getLogger(__name__)

router = Router(name="admin.codes")


# ==========================================================================
#  1-bosqich: testni tanlash
# ==========================================================================


@router.callback_query(MenuCB.filter(F.action == "admin_codes"))
async def choose_exam(callback: CallbackQuery, is_admin: bool) -> None:
    """ID kod yaratish uchun testni tanlash."""
    if not is_admin:
        await callback.answer(TC.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()

    exams = await exam_service.paid_exams()
    if not exams:
        await callback.message.answer(TA.NO_PAID_EXAMS)
        return

    await callback.message.answer(
        TA.CHOOSE_EXAM_FOR_CODES, reply_markup=inline.code_exam_list(exams)
    )


@router.callback_query(CodesCB.filter(F.action == "exam"))
async def ask_quantity(
    callback: CallbackQuery, callback_data: CodesCB, is_admin: bool
) -> None:
    """Kodlar miqdorini so'raydi."""
    if not is_admin:
        await callback.answer(TC.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()

    exam = await exam_service.get_exam(callback_data.exam_id)
    if exam is None:
        await callback.message.answer("Test topilmadi.")
        return

    await callback.message.answer(
        TA.ASK_CODE_QUANTITY.format(title=esc(exam.title)),
        reply_markup=inline.code_quantities(exam.id),
    )


# ==========================================================================
#  2-bosqich: miqdorni tanlash
# ==========================================================================


@router.callback_query(CodesCB.filter(F.action == "quantity"))
async def generate_from_button(
    callback: CallbackQuery, callback_data: CodesCB, state: FSMContext, user, is_admin: bool
) -> None:
    """Tayyor variantlardan miqdor tanlandi."""
    if not is_admin:
        await callback.answer(TC.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()
    await _generate(callback.message, state, user, callback_data.exam_id, callback_data.quantity)


@router.callback_query(CodesCB.filter(F.action == "custom"))
async def ask_custom_quantity(
    callback: CallbackQuery, callback_data: CodesCB, state: FSMContext, is_admin: bool
) -> None:
    """«Boshqa miqdor» tanlandi."""
    if not is_admin:
        await callback.answer(TC.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()

    await state.set_state(AdminStates.waiting_code_quantity)
    await state.update_data(codes_exam_id=callback_data.exam_id)
    await callback.message.answer(
        TA.ASK_CUSTOM_QUANTITY.format(maximum=C.CODE_BATCH_MAX),
        reply_markup=inline.cancel(),
    )


@router.message(StateFilter(AdminStates.waiting_code_quantity), F.text)
async def receive_custom_quantity(
    message: Message, state: FSMContext, user, is_admin: bool
) -> None:
    """Qo'lda kiritilgan miqdor."""
    if not is_admin:
        await message.answer(TC.ADMIN_ONLY)
        await state.clear()
        return

    raw = (message.text or "").strip().replace(" ", "")
    if not raw.isdigit():
        await message.answer(TA.INVALID_QUANTITY.format(maximum=C.CODE_BATCH_MAX))
        return

    quantity = int(raw)
    if not (1 <= quantity <= C.CODE_BATCH_MAX):
        await message.answer(TA.INVALID_QUANTITY.format(maximum=C.CODE_BATCH_MAX))
        return

    data = await state.get_data()
    exam_id = int(data.get("codes_exam_id", 0) or 0)
    await state.clear()
    await _generate(message, state, user, exam_id, quantity)


# ==========================================================================
#  3-bosqich: kodlarni yaratish
# ==========================================================================


async def _generate(
    message: Message, state: FSMContext, user, exam_id: int, quantity: int
) -> None:
    """Kodlarni yaratadi va Excel fayl sifatida yuboradi."""
    exam = await exam_service.get_exam(exam_id)
    if exam is None:
        await message.answer("Test topilmadi.")
        return

    quantity = max(1, min(int(quantity or 0), C.CODE_BATCH_MAX))
    await message.answer(TA.CODES_GENERATING)

    try:
        batch = await code_service.create_codes(exam, quantity, created_by=user)
    except Exception:
        logger.exception("ID kodlarni yaratishda xato: exam_id=%s", exam_id)
        await message.answer(TC.ERROR_GENERIC)
        return

    try:
        payload = await code_service.export_codes_excel(batch)
    except Exception:
        logger.exception("ID kodlarni eksport qilishda xato: batch_id=%s", batch.id)
        await message.answer(
            f"{batch.quantity} ta kod yaratildi, lekin Excel faylini "
            "tayyorlab bo'lmadi. Web paneldan yuklab oling."
        )
        return

    sample = await code_service.sample_codes(batch, limit=3)

    await message.answer_document(
        document(payload, timestamped_name("idkodlar", "xlsx", exam.code)),
        caption=TA.CODES_READY.format(
            quantity=batch.quantity, title=esc(exam.title), code=exam.code
        ),
    )
    if sample:
        await message.answer(TA.CODES_SAMPLE.format(sample="\n".join(sample)))

    # Pullik test ID kodlarsiz faollashmaydi — endi faollashtirish mumkin.
    if exam.status == "draft":
        ok, activation_message = await exam_service.activate_exam(exam)
        await message.answer(esc(activation_message))


__all__ = ["router"]
