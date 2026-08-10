"""
Tushunilmagan xabarlarni qayta ishlash.

Ushbu router eng oxirida ro'yxatdan o'tkaziladi — boshqa hech bir handler
mos kelmagan xabarlar shu yerga tushadi.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.texts import common as TC

from .menu import send_main_menu

router = Router(name="fallback")


@router.message(F.text)
async def unknown_text(message: Message, state: FSMContext, user, is_admin: bool) -> None:
    """Noma'lum matnli xabar."""
    if not user.is_registered:
        await message.answer(TC.NOT_REGISTERED)
        return
    await send_main_menu(message, is_admin, text=TC.UNKNOWN_COMMAND)


@router.message()
async def unknown_content(message: Message, user, is_admin: bool) -> None:
    """Matn bo'lmagan noma'lum xabar (rasm, stiker va h.k.)."""
    if not user.is_registered:
        await message.answer(TC.NOT_REGISTERED)
        return
    await send_main_menu(message, is_admin, text=TC.UNKNOWN_COMMAND)


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    """Eskirgan yoki noma'lum inline tugma."""
    await callback.answer(
        "Bu tugma eskirgan. Iltimos, /start ni bosing.", show_alert=True
    )


__all__ = ["router"]
