"""Administrator panelining asosiy menyusi."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline
from bot.keyboards.factories import MenuCB
from bot.services import exams as exam_service
from bot.services import users as user_service
from bot.texts import admin as TA
from bot.texts import common as TC
from bot.utils.files import document, timestamped_name

logger = logging.getLogger(__name__)

router = Router(name="admin.panel")


# ==========================================================================
#  Panelni ochish
# ==========================================================================


async def show_panel(message: Message, config) -> None:
    """Administrator panelini ko'rsatadi."""
    web_url = f"{config.public_base_url}/panel/" if config.public_base_url else ""
    await message.answer(TA.PANEL_TITLE, reply_markup=inline.admin_panel(web_url))


@router.message(Command("admin"))
async def command_admin(message: Message, config, is_admin: bool) -> None:
    """/admin buyrug'i."""
    if not is_admin:
        await message.answer(TC.ADMIN_ONLY)
        return
    await show_panel(message, config)


# ==========================================================================
#  Barcha testlar
# ==========================================================================


@router.callback_query(MenuCB.filter(F.action == "admin_exams"))
async def all_exams(callback: CallbackQuery, is_admin: bool) -> None:
    """Barcha testlar ro'yxati."""
    if not is_admin:
        await callback.answer(TC.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()

    exams = await exam_service.all_exams(limit=25)
    if not exams:
        await callback.message.answer(TA.NO_EXAMS)
        return

    await callback.message.answer(
        TA.ALL_EXAMS_TITLE,
        reply_markup=inline.exam_list(exams, action="manage"),
    )


# ==========================================================================
#  Foydalanuvchilarni eksport qilish
# ==========================================================================


@router.callback_query(MenuCB.filter(F.action == "admin_users"))
async def export_users(callback: CallbackQuery, is_admin: bool) -> None:
    """Foydalanuvchilar ro'yxatini Excel ko'rinishida yuboradi."""
    if not is_admin:
        await callback.answer(TC.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer("⏳ Fayl tayyorlanmoqda...")

    try:
        payload = await user_service.export_users_excel()
    except Exception:
        logger.exception("Foydalanuvchilarni eksport qilishda xato")
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    await callback.message.answer_document(
        document(payload, timestamped_name("foydalanuvchilar", "xlsx")),
        caption="Barcha ro‘yxatdan o‘tgan foydalanuvchilar",
    )


__all__ = ["router", "show_panel"]
