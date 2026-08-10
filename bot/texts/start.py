"""
/start, majburiy obuna va ro'yxatdan o'tish matnlari.

Matnlar texnik topshiriqdagi mazmunga muvofiq, emojisiz shaklda.
"""

from __future__ import annotations

# ==========================================================================
#  /start
# ==========================================================================

WELCOME = (
    "Assalomu alaykum!\n"
    "Matematika testlarini o‘tkazish va tekshirish platformasiga xush kelibsiz.\n\n"
    "Bu bot orqali siz:\n"
    "• testlarda qatnashishingiz;\n"
    "• natijalaringizni bilishingiz;\n"
    "• reytingni kuzatishingiz;\n"
    "• o‘z testingizni yaratib, boshqalar uchun test o‘tkazishingiz mumkin.\n\n"
    "Davom etish uchun quyidagi tugmani bosing."
)

WELCOME_BACK = (
    "Assalomu alaykum, <b>{name}</b>!\n\n"
    "Yana ko‘rishganimizdan xursandmiz. Quyidagi menyudan foydalaning."
)

# ==========================================================================
#  Majburiy obuna
# ==========================================================================

SUBSCRIPTION_REQUIRED = (
    "<b>Botdan foydalanish uchun kanalimizga a’zo bo‘ling</b>\n\n"
    "{channel} kanaliga a’zo bo‘ling va «A’zolikni tekshirish» tugmasini bosing."
)

SUBSCRIPTION_CONFIRMED = "A’zolik tasdiqlandi. Davom etishingiz mumkin."

SUBSCRIPTION_NOT_FOUND = (
    "Siz hali kanalga a’zo bo‘lmagansiz.\n\n"
    "Iltimos, {channel} kanaliga a’zo bo‘ling va qaytadan tekshiring."
)

SUBSCRIPTION_CHECK_FAILED = (
    "A’zolikni tekshirib bo‘lmadi.\n\n"
    "Bot kanalda administrator sifatida qo‘shilganini tekshiring yoki "
    "birozdan so‘ng qayta urinib ko‘ring."
)

BTN_JOIN_CHANNEL = "Kanalga a’zo bo‘lish"
BTN_CHECK_SUBSCRIPTION = "A’zolikni tekshirish"

# ==========================================================================
#  Ro'yxatdan o'tish
# ==========================================================================

ASK_FULL_NAME = (
    "<b>Ro‘yxatdan o‘tish</b>\n\n"
    "Ism va familiyangizni kiriting.\n"
    "Masalan: <i>Burgutali Eshquvvatov</i>"
)

INVALID_FULL_NAME = (
    "Ism va familiyani to‘liq kiriting.\n\n"
    "Kamida ikkita so‘z bo‘lishi kerak. Masalan: <i>Burgutali Eshquvvatov</i>"
)

ASK_PHONE = (
    "Ism va familiyangiz saqlandi: <b>{name}</b>\n\n"
    "Endi telefon raqamingizni yuboring.\n"
    "Pastdagi <b>«Telefon raqamni yuborish»</b> tugmasidan foydalaning."
)

INVALID_PHONE = (
    "Telefon raqami noto‘g‘ri.\n\n"
    "Iltimos, pastdagi tugma orqali kontaktingizni yuboring."
)

FOREIGN_CONTACT = (
    "Iltimos, <b>o‘zingizning</b> telefon raqamingizni yuboring.\n"
    "Buning uchun pastdagi tugmadan foydalaning."
)

REGISTRATION_DONE = (
    "<b>Ro‘yxatdan o‘tdingiz</b>\n\n"
    "Ism-familiya: <b>{name}</b>\n"
    "Telefon: <b>{phone}</b>\n\n"
    "Endi testlarda qatnashishingiz yoki o‘z testingizni yaratishingiz mumkin."
)

ALREADY_REGISTERED = "Siz allaqachon ro‘yxatdan o‘tgansiz."


__all__ = [name for name in dir() if not name.startswith("_")]
