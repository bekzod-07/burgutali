"""
Asosiy menyu va umumiy buyruqlar.

Ushbu router birinchi bo'lib ro'yxatdan o'tkaziladi — shu sababli
«bekor qilish» va menyu tugmalari istalgan holatda ishlaydi.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import reply
from bot.keyboards.factories import MenuCB
from bot.texts import common as TC

router = Router(name="menu")


# ==========================================================================
#  Bekor qilish va asosiy menyu
# ==========================================================================


@router.message(StateFilter("*"), Command("menu"))
@router.message(StateFilter("*"), F.text == TC.BTN_MAIN_MENU)
async def open_main_menu(message: Message, state: FSMContext, is_admin: bool) -> None:
    """Asosiy menyuni ochadi va joriy dialogni tugatadi."""
    await _reset_state(state)
    await message.answer(TC.MAIN_MENU, reply_markup=reply.main_menu(is_admin))


@router.message(StateFilter("*"), Command("bekor", "cancel"))
@router.message(StateFilter("*"), F.text == TC.BTN_CANCEL)
async def cancel_action(message: Message, state: FSMContext, is_admin: bool) -> None:
    """Joriy amalni bekor qiladi."""
    await _reset_state(state)
    await message.answer(TC.CANCELLED, reply_markup=reply.main_menu(is_admin))


@router.callback_query(MenuCB.filter(F.action == "main"))
async def callback_main_menu(
    callback: CallbackQuery, state: FSMContext, is_admin: bool
) -> None:
    """Inline «Asosiy menyu» tugmasi."""
    await callback.answer()
    await _reset_state(state)
    await callback.message.answer(TC.MAIN_MENU, reply_markup=reply.main_menu(is_admin))


@router.callback_query(MenuCB.filter(F.action == "cancel"))
async def callback_cancel(
    callback: CallbackQuery, state: FSMContext, is_admin: bool
) -> None:
    """Inline «Bekor qilish» tugmasi."""
    await callback.answer(TC.CANCELLED)
    await _reset_state(state)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # pragma: no cover - xabar allaqachon o'zgargan bo'lishi mumkin
        pass
    await callback.message.answer(TC.MAIN_MENU, reply_markup=reply.main_menu(is_admin))


@router.callback_query(MenuCB.filter(F.action == "noop"))
async def callback_noop(callback: CallbackQuery) -> None:
    """Hech narsa qilmaydigan tugma."""
    await callback.answer()


async def _reset_state(state: FSMContext) -> None:
    """Holatni tozalaydi, lekin kutilayotgan test kodini saqlab qoladi."""
    data = await state.get_data()
    pending = data.get("pending_exam")
    await state.clear()
    if pending:
        await state.update_data(pending_exam=pending)


# ==========================================================================
#  Yordam
# ==========================================================================


@router.message(StateFilter("*"), Command("yordam", "help"))
@router.message(StateFilter("*"), F.text == TC.BTN_HELP)
async def show_help(message: Message, is_admin: bool) -> None:
    """Yordam bo'limi."""
    await message.answer(TC.HELP, reply_markup=reply.main_menu(is_admin))


# ==========================================================================
#  Web ilova
# ==========================================================================


@router.message(StateFilter("*"), Command("ilova", "app", "webapp"))
async def open_web_app(message: Message, state: FSMContext, config, is_admin: bool) -> None:
    """Web ilovani ochish havolasi."""
    from bot.keyboards import inline

    await _reset_state(state)
    if not config.miniapp_available:
        await message.answer(
            TC.WEB_APP_UNAVAILABLE, reply_markup=reply.main_menu(is_admin)
        )
        return
    await message.answer(TC.WEB_APP_HINT, reply_markup=inline.open_app())


# ==========================================================================
#  Asosiy menyu tugmalari
# ==========================================================================


@router.message(StateFilter("*"), F.text == TC.BTN_TAKE_EXAM)
async def press_take_exam(message: Message, state: FSMContext, user) -> None:
    """«Testda qatnashish»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)

    from .taking.entry import open_take_menu

    await open_take_menu(message, state, user)


@router.message(StateFilter("*"), F.text == TC.BTN_CREATE_EXAM)
async def press_create_exam(
    message: Message, state: FSMContext, user, is_admin: bool
) -> None:
    """«Test yaratish»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)

    from .create.common import start_creation

    await start_creation(message, state, is_admin)


@router.message(StateFilter("*"), F.text == TC.BTN_MY_RESULTS)
async def press_my_results(message: Message, state: FSMContext, user) -> None:
    """«Natijalarim»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)

    from .results import show_my_results

    await show_my_results(message, user)


@router.message(StateFilter("*"), F.text == TC.BTN_MY_EXAMS)
async def press_my_exams(message: Message, state: FSMContext, user) -> None:
    """«Testlarim»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)

    from .my_tests import show_my_exams

    await show_my_exams(message, user)


@router.message(StateFilter("*"), F.text == TC.BTN_CERTIFICATES)
async def press_certificates(message: Message, state: FSMContext, user) -> None:
    """«Sertifikatlar»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)

    from .certificate import show_my_certificates

    await show_my_certificates(message, user)


@router.message(StateFilter("*"), F.text == TC.BTN_ADMIN)
async def press_admin(
    message: Message, state: FSMContext, user, config, is_admin: bool
) -> None:
    """«Admin panel»."""
    if not is_admin:
        await message.answer(TC.ADMIN_ONLY)
        return
    await _reset_state(state)

    from .admin.panel import show_panel

    await show_panel(message, config)


# ==========================================================================
#  Yordamchi
# ==========================================================================


async def _require_registration(message: Message, user) -> bool:
    """Foydalanuvchi ro'yxatdan o'tganini tekshiradi."""
    if user.is_registered:
        return True
    await message.answer(TC.NOT_REGISTERED)
    return False


__all__ = ["router"]
