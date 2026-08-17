"""
/start buyrug'i va deep-link larni qayta ishlash.

Oqim (TZ 2-bo'lim):
  /start -> majburiy obuna tekshiruvi -> «Boshlash» -> ro'yxatdan o'tish
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline, reply
from bot.keyboards.factories import MenuCB
from bot.texts import common as TC
from bot.texts import start as TS
from bot.utils.subscription import is_subscribed
from core.text_utils import esc

logger = logging.getLogger(__name__)

router = Router(name="start")


# ==========================================================================
#  /start
# ==========================================================================


@router.message(CommandStart(deep_link=True))
async def start_with_payload(
    message: Message, command: CommandObject, state: FSMContext, user, config, is_admin: bool
) -> None:
    """Deep-link bilan kelgan /start (masalan, `?start=exam_32`)."""
    payload = (command.args or "").strip()
    await state.clear()

    if payload.lower().startswith("exam_"):
        code = payload[5:].strip().upper()
        await state.update_data(pending_exam=code)

    await _start_flow(message, state, user, config, is_admin)


@router.message(CommandStart())
async def start_plain(
    message: Message, state: FSMContext, user, config, is_admin: bool
) -> None:
    """Oddiy /start."""
    await state.clear()
    await _start_flow(message, state, user, config, is_admin)


async def _start_flow(
    message: Message, state: FSMContext, user, config, is_admin: bool
) -> None:
    """
    Obunani tekshiradi va keyingi bosqichga o'tkazadi.

    A'zolik qat'iy shart: tasdiqlanmasa — tekshirib bo'lmagan holatda ham —
    foydalanuvchi menyuga o'tmaydi.
    """
    if config.subscription_required and not is_admin:
        subscribed = await is_subscribed(message.bot, user.telegram_id)
        if subscribed is not True:
            text = TS.SUBSCRIPTION_REQUIRED.format(channel=config.required_channel)
            if subscribed is None:
                logger.warning(
                    "Obunani tekshirib bo'lmadi (user=%s) — bot %s kanalida "
                    "administratormi?",
                    user.telegram_id, config.required_channel,
                )
                text += "\n\n" + TS.SUBSCRIPTION_CHECK_FAILED
            await message.answer(
                text,
                reply_markup=inline.subscription(config.required_channel_url),
            )
            return

    await show_welcome(message, state, user, is_admin)


async def show_welcome(
    message: Message, state: FSMContext, user, is_admin: bool
) -> None:
    """Xush kelibsiz xabari yoki asosiy menyu."""
    from .menu import send_main_menu

    if user.is_registered:
        # Eski reply-klaviaturani tozalab, inline menyu yuboramiz.
        await message.answer(
            TS.WELCOME_BACK.format(name=esc(user.display_name)),
            reply_markup=reply.remove(),
        )
        await send_main_menu(message, is_admin)
        await _open_pending_exam(message, state, user)
        return

    await message.answer(
        TS.WELCOME,
        reply_markup=reply.remove(),
    )
    await message.answer(
        "Ro'yxatdan o'tish uchun tugmani bosing.",
        reply_markup=inline.start_button(),
    )


# ==========================================================================
#  «Boshlash» tugmasi
# ==========================================================================


@router.callback_query(MenuCB.filter(F.action == "start"))
async def press_start(
    callback: CallbackQuery, state: FSMContext, user, config, is_admin: bool
) -> None:
    """«Boshlash» bosilganda ro'yxatdan o'tish boshlanadi."""
    await callback.answer()

    if config.subscription_required and not is_admin:
        subscribed = await is_subscribed(callback.bot, user.telegram_id)
        if subscribed is not True:
            text = TS.SUBSCRIPTION_REQUIRED.format(channel=config.required_channel)
            if subscribed is None:
                text += "\n\n" + TS.SUBSCRIPTION_CHECK_FAILED
            await callback.message.answer(
                text,
                reply_markup=inline.subscription(config.required_channel_url),
            )
            return

    if user.is_registered:
        from .menu import send_main_menu

        await send_main_menu(callback.message, is_admin)
        await _open_pending_exam(callback.message, state, user)
        return

    from .registration import ask_full_name

    await ask_full_name(callback.message, state)


# ==========================================================================
#  Deep-link orqali kelgan testni ochish
# ==========================================================================


async def _open_pending_exam(message: Message, state: FSMContext, user) -> None:
    """Deep-link da ko'rsatilgan testni ochadi (agar bo'lsa)."""
    data = await state.get_data()
    code = data.get("pending_exam")
    if not code:
        return
    await state.update_data(pending_exam=None)

    from .taking.entry import open_exam_by_code

    await open_exam_by_code(message, state, user, code)


__all__ = ["router", "show_welcome"]
