"""Umumiy statistika bo'limi."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline
from bot.keyboards.factories import MenuCB
from bot.services import stats as stats_service
from bot.texts import admin as TA
from bot.texts import common as TC

router = Router(name="admin.stats")


@router.callback_query(MenuCB.filter(F.action == "admin_stats"))
async def show_stats(callback: CallbackQuery, is_admin: bool) -> None:
    """Statistikani ko'rsatadi."""
    if not is_admin:
        await callback.answer(TC.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()
    data = await stats_service.overview()
    await callback.message.answer(
        TA.STATS.format(**data), reply_markup=inline.back_to_menu()
    )


@router.message(Command("stat", "statistika"))
async def command_stats(message: Message, is_admin: bool) -> None:
    """/statistika buyrug'i."""
    if not is_admin:
        await message.answer(TC.ADMIN_ONLY)
        return
    data = await stats_service.overview()
    await message.answer(TA.STATS.format(**data))


__all__ = ["router"]
