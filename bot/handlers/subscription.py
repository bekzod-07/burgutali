"""Majburiy obunani tekshirish tugmasi."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards import inline
from bot.keyboards.factories import SubscriptionCB
from bot.services import users as user_service
from bot.texts import start as TS
from bot.utils.subscription import is_subscribed

router = Router(name="subscription")


@router.callback_query(SubscriptionCB.filter(F.action == "check"))
async def check_subscription(
    callback: CallbackQuery, state: FSMContext, user, config, is_admin: bool
) -> None:
    """«A'zolikni tekshirish» tugmasi."""
    await callback.answer()

    subscribed = await is_subscribed(callback.bot, user.telegram_id)

    if subscribed is None:
        # Tekshirib bo'lmadi — kirish berilmaydi, tugma joyida qoladi.
        await callback.message.answer(
            TS.SUBSCRIPTION_CHECK_FAILED,
            reply_markup=inline.subscription(config.required_channel_url),
        )
        return

    await user_service.set_subscription(user, subscribed)
    user.is_subscribed = subscribed

    if not subscribed:
        await callback.message.answer(
            TS.SUBSCRIPTION_NOT_FOUND.format(channel=config.required_channel),
            reply_markup=inline.subscription(config.required_channel_url),
        )
        return

    await callback.message.answer(TS.SUBSCRIPTION_CONFIRMED)

    from .start import show_welcome

    await show_welcome(callback.message, state, user, is_admin)


__all__ = ["router"]
