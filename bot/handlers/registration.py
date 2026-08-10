"""
Ro'yxatdan o'tish: ism-familiya va telefon raqami (TZ 3-bo'lim).

Telefon raqami imkon qadar Telegram kontakt tugmasi orqali olinadi.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards import reply
from bot.services import users as user_service
from bot.states import RegistrationStates
from bot.texts import start as TS
from core.text_utils import esc, is_valid_full_name, normalize_phone

router = Router(name="registration")


# ==========================================================================
#  1-bosqich: ism va familiya
# ==========================================================================


async def ask_full_name(message: Message, state: FSMContext) -> None:
    """Ism-familiyani so'raydi."""
    await state.set_state(RegistrationStates.waiting_full_name)
    await message.answer(TS.ASK_FULL_NAME, reply_markup=reply.remove())


@router.message(StateFilter(RegistrationStates.waiting_full_name), F.text)
async def receive_full_name(message: Message, state: FSMContext, user) -> None:
    """Kiritilgan ism-familiyani tekshiradi va saqlaydi."""
    raw = (message.text or "").strip()

    if not is_valid_full_name(raw):
        await message.answer(TS.INVALID_FULL_NAME)
        return

    full_name = await user_service.save_full_name(user, raw)
    user.full_name = full_name

    await state.set_state(RegistrationStates.waiting_phone)
    await message.answer(
        TS.ASK_PHONE.format(name=esc(full_name)),
        reply_markup=reply.phone_request(),
    )


@router.message(StateFilter(RegistrationStates.waiting_full_name))
async def full_name_wrong_type(message: Message) -> None:
    """Matn o'rniga boshqa narsa yuborilganda."""
    await message.answer(TS.INVALID_FULL_NAME)


# ==========================================================================
#  2-bosqich: telefon raqami
# ==========================================================================


@router.message(StateFilter(RegistrationStates.waiting_phone), F.contact)
async def receive_contact(message: Message, state: FSMContext, user, is_admin: bool) -> None:
    """Telegram kontakti orqali kelgan telefon raqami."""
    contact = message.contact

    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(TS.FOREIGN_CONTACT, reply_markup=reply.phone_request())
        return

    await _finish_registration(message, state, user, contact.phone_number, is_admin)


@router.message(StateFilter(RegistrationStates.waiting_phone), F.text)
async def receive_typed_phone(
    message: Message, state: FSMContext, user, is_admin: bool
) -> None:
    """Qo'lda yozilgan telefon raqami (zaxira variant)."""
    phone = normalize_phone(message.text or "")
    digits = "".join(ch for ch in phone if ch.isdigit())

    if len(digits) < 9:
        await message.answer(TS.INVALID_PHONE, reply_markup=reply.phone_request())
        return

    await _finish_registration(message, state, user, phone, is_admin)


@router.message(StateFilter(RegistrationStates.waiting_phone))
async def phone_wrong_type(message: Message) -> None:
    """Kontakt ham, matn ham emas."""
    await message.answer(TS.INVALID_PHONE, reply_markup=reply.phone_request())


async def _finish_registration(
    message: Message, state: FSMContext, user, raw_phone: str, is_admin: bool
) -> None:
    """Ro'yxatdan o'tishni yakunlaydi."""
    phone = await user_service.save_phone(user, raw_phone)
    user.phone = phone
    user.is_registered = True

    await state.set_state(None)
    # Telefon so'rash reply-klaviaturasini tozalab, inline menyu beramiz.
    await message.answer(
        TS.REGISTRATION_DONE.format(name=esc(user.full_name), phone=esc(phone)),
        reply_markup=reply.remove(),
    )
    from .menu import send_main_menu

    await send_main_menu(message, is_admin)

    # Deep-link orqali kelingan bo'lsa — testni ochamiz.
    data = await state.get_data()
    code = data.get("pending_exam")
    if code:
        await state.update_data(pending_exam=None)
        from .taking.entry import open_exam_by_code

        await open_exam_by_code(message, state, user, code)


__all__ = ["router", "ask_full_name"]
