"""
Asosiy menyu va umumiy buyruqlar.

Ushbu router birinchi bo'lib ro'yxatdan o'tkaziladi — shu sababli
«bekor qilish» va menyu tugmalari istalgan holatda ishlaydi.

Asosiy menyu to'liq inline: web ilova mavjud bo'lsa tugmalar ilovaning
tegishli ekranini Web App sifatida ochadi. Eski reply-klaviatura matnli
tugmalari orqaga moslik uchun saqlangan (eski foydalanuvchilarda
klaviatura hali ekranda turgan bo'lishi mumkin).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline
from bot.keyboards.factories import MenuCB
from bot.texts import common as TC

router = Router(name="menu")


async def send_main_menu(message: Message, is_admin: bool, *, text: str = "") -> None:
    """Asosiy inline menyuni yuboradi."""
    await message.answer(text or TC.MAIN_MENU, reply_markup=inline.main_menu(is_admin))


# ==========================================================================
#  Bekor qilish va asosiy menyu
# ==========================================================================


@router.message(StateFilter("*"), Command("menu"))
@router.message(StateFilter("*"), F.text == TC.BTN_MAIN_MENU)
async def open_main_menu(message: Message, state: FSMContext, is_admin: bool) -> None:
    """Asosiy menyuni ochadi va joriy dialogni tugatadi."""
    await _reset_state(state)
    await send_main_menu(message, is_admin)


@router.message(StateFilter("*"), Command("bekor", "cancel"))
@router.message(StateFilter("*"), F.text == TC.BTN_CANCEL)
async def cancel_action(message: Message, state: FSMContext, is_admin: bool) -> None:
    """Joriy amalni bekor qiladi."""
    await _reset_state(state)
    await send_main_menu(message, is_admin, text=TC.CANCELLED)


@router.callback_query(MenuCB.filter(F.action == "main"))
async def callback_main_menu(
    callback: CallbackQuery, state: FSMContext, is_admin: bool
) -> None:
    """Inline «Asosiy menyu» tugmasi."""
    await callback.answer()
    await _reset_state(state)
    await send_main_menu(callback.message, is_admin)


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
    await send_main_menu(callback.message, is_admin)


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
    await send_main_menu(message, is_admin, text=TC.HELP)


@router.callback_query(MenuCB.filter(F.action == "help"))
async def callback_help(callback: CallbackQuery, is_admin: bool) -> None:
    """Inline «Yordam» tugmasi."""
    await callback.answer()
    await send_main_menu(callback.message, is_admin, text=TC.HELP)


# ==========================================================================
#  Web ilova
# ==========================================================================


@router.message(StateFilter("*"), Command("ilova", "app", "webapp"))
async def open_web_app(message: Message, state: FSMContext, config, is_admin: bool) -> None:
    """Web ilovani ochish havolasi."""
    await _reset_state(state)
    if not config.miniapp_available:
        await send_main_menu(message, is_admin, text=TC.WEB_APP_UNAVAILABLE)
        return
    await message.answer(TC.WEB_APP_HINT, reply_markup=inline.open_app())


# ==========================================================================
#  Menyu bo'limlari — umumiy oqimlar
# ==========================================================================


async def _open_take(message: Message, state: FSMContext, user) -> None:
    from .taking.entry import open_take_menu

    await open_take_menu(message, state, user)


async def _open_create(message: Message, state: FSMContext, is_admin: bool) -> None:
    from .create.common import start_creation

    await start_creation(message, state, is_admin)


async def _open_results(message: Message, user) -> None:
    from .results import show_my_results

    await show_my_results(message, user)


async def _open_my_exams(message: Message, user) -> None:
    from .my_tests import show_my_exams

    await show_my_exams(message, user)


async def _open_certificates(message: Message, user) -> None:
    from .certificate import show_my_certificates

    await show_my_certificates(message, user)


async def _open_admin(message: Message, config) -> None:
    from .admin.panel import show_panel

    await show_panel(message, config)


# ==========================================================================
#  Asosiy menyu tugmalari (matnli — orqaga moslik uchun)
# ==========================================================================


@router.message(StateFilter("*"), F.text == TC.BTN_TAKE_EXAM)
async def press_take_exam(message: Message, state: FSMContext, user) -> None:
    """«Testda qatnashish»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)
    await _open_take(message, state, user)


@router.message(StateFilter("*"), F.text == TC.BTN_CREATE_EXAM)
async def press_create_exam(
    message: Message, state: FSMContext, user, is_admin: bool
) -> None:
    """«Test yaratish»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)
    await _open_create(message, state, is_admin)


@router.message(StateFilter("*"), F.text == TC.BTN_MY_RESULTS)
async def press_my_results(message: Message, state: FSMContext, user) -> None:
    """«Natijalarim»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)
    await _open_results(message, user)


@router.message(StateFilter("*"), F.text == TC.BTN_MY_EXAMS)
async def press_my_exams(message: Message, state: FSMContext, user) -> None:
    """«Testlarim»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)
    await _open_my_exams(message, user)


@router.message(StateFilter("*"), F.text == TC.BTN_CERTIFICATES)
async def press_certificates(message: Message, state: FSMContext, user) -> None:
    """«Sertifikatlar»."""
    if not await _require_registration(message, user):
        return
    await _reset_state(state)
    await _open_certificates(message, user)


@router.message(StateFilter("*"), F.text == TC.BTN_ADMIN)
async def press_admin(
    message: Message, state: FSMContext, user, config, is_admin: bool
) -> None:
    """«Admin panel»."""
    if not is_admin:
        await message.answer(TC.ADMIN_ONLY)
        return
    await _reset_state(state)
    await _open_admin(message, config)


# ==========================================================================
#  Asosiy menyu tugmalari (inline callback)
# ==========================================================================


@router.callback_query(MenuCB.filter(F.action == "take"))
async def cb_take_exam(callback: CallbackQuery, state: FSMContext, user) -> None:
    await callback.answer()
    if not await _require_registration_cb(callback, user):
        return
    await _reset_state(state)
    await _open_take(callback.message, state, user)


@router.callback_query(MenuCB.filter(F.action == "create"))
async def cb_create_exam(
    callback: CallbackQuery, state: FSMContext, user, is_admin: bool
) -> None:
    await callback.answer()
    if not await _require_registration_cb(callback, user):
        return
    await _reset_state(state)
    await _open_create(callback.message, state, is_admin)


@router.callback_query(MenuCB.filter(F.action == "results"))
async def cb_my_results(callback: CallbackQuery, state: FSMContext, user) -> None:
    await callback.answer()
    if not await _require_registration_cb(callback, user):
        return
    await _reset_state(state)
    await _open_results(callback.message, user)


@router.callback_query(MenuCB.filter(F.action == "certs"))
async def cb_certificates(callback: CallbackQuery, state: FSMContext, user) -> None:
    await callback.answer()
    if not await _require_registration_cb(callback, user):
        return
    await _reset_state(state)
    await _open_certificates(callback.message, user)


@router.callback_query(MenuCB.filter(F.action == "my_exams"))
async def cb_my_exams(callback: CallbackQuery, state: FSMContext, user) -> None:
    await callback.answer()
    if not await _require_registration_cb(callback, user):
        return
    await _reset_state(state)
    await _open_my_exams(callback.message, user)


@router.callback_query(MenuCB.filter(F.action == "admin"))
async def cb_admin(
    callback: CallbackQuery, state: FSMContext, user, config, is_admin: bool
) -> None:
    await callback.answer()
    if not is_admin:
        await callback.message.answer(TC.ADMIN_ONLY)
        return
    await _reset_state(state)
    await _open_admin(callback.message, config)


# ==========================================================================
#  Yordamchi
# ==========================================================================


async def _require_registration(message: Message, user) -> bool:
    """Foydalanuvchi ro'yxatdan o'tganini tekshiradi."""
    if user.is_registered:
        return True
    await message.answer(TC.NOT_REGISTERED)
    return False


async def _require_registration_cb(callback: CallbackQuery, user) -> bool:
    """Callback uchun ro'yxatdan o'tish tekshiruvi."""
    if user.is_registered:
        return True
    await callback.message.answer(TC.NOT_REGISTERED)
    return False


__all__ = ["router", "send_main_menu"]
