"""Reply (pastki) klaviaturalar — emojisiz, matnli tugmalar."""

from __future__ import annotations

from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from bot.config import get_config
from bot.texts import common as T


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Asosiy menyu.

    Web ilova mavjud bo'lsa (PUBLIC_BASE_URL HTTPS), birinchi qatorda
    ilovani ochuvchi tugma turadi.
    """
    config = get_config()
    rows: list[list[KeyboardButton]] = []

    if config.miniapp_available:
        rows.append(
            [
                KeyboardButton(
                    text=T.BTN_WEB_APP,
                    web_app=WebAppInfo(url=config.miniapp_url),
                )
            ]
        )

    rows += [
        [KeyboardButton(text=T.BTN_TAKE_EXAM), KeyboardButton(text=T.BTN_CREATE_EXAM)],
        [KeyboardButton(text=T.BTN_MY_RESULTS), KeyboardButton(text=T.BTN_MY_EXAMS)],
        [KeyboardButton(text=T.BTN_CERTIFICATES), KeyboardButton(text=T.BTN_HELP)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=T.BTN_ADMIN)])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Bo'limni tanlang...",
    )


def phone_request() -> ReplyKeyboardMarkup:
    """Telefon raqamini so'rash klaviaturasi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=T.BTN_SHARE_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Telefon raqamingizni yuboring",
    )


def cancel_only() -> ReplyKeyboardMarkup:
    """Faqat «Bekor qilish» tugmasi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=T.BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder="Yozing yoki bekor qiling...",
    )


def remove() -> ReplyKeyboardRemove:
    """Klaviaturani olib tashlaydi."""
    return ReplyKeyboardRemove()


__all__ = ["main_menu", "phone_request", "cancel_only", "remove"]
