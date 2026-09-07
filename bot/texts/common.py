"""
Umumiy matnlar va tugma yozuvlari.

Botda emoji ishlatilmaydi. Vizual ajratish uchun faqat tipografik
belgilar qo'llaniladi: ✓ (to'g'ri), ✗ (xato), · (bo'sh), • (ro'yxat),
— (ajratkich). Bular emoji emas, oddiy matn belgilari — barcha
qurilmalarda bir xil ko'rinadi.
"""

from __future__ import annotations

# ==========================================================================
#  Tipografik belgilar (emoji o'rniga)
# ==========================================================================

MARK_CORRECT = "✓"
MARK_WRONG = "✗"
MARK_EMPTY = "·"
MARK_PARTIAL = "±"
BULLET = "•"
DASH = "—"
ARROW = "›"

# ==========================================================================
#  Asosiy menyu tugmalari (reply keyboard)
# ==========================================================================

BTN_WEB_APP = "Ilovani ochish"
BTN_TAKE_EXAM = "Testda qatnashish"
BTN_CREATE_EXAM = "Test yaratish"
BTN_MY_RESULTS = "Natijalarim"
BTN_MY_EXAMS = "Testlarim"
BTN_CERTIFICATES = "Sertifikatlar"
BTN_HELP = "Yordam"
BTN_ADMIN = "Admin panel"

# ==========================================================================
#  Umumiy tugmalar
# ==========================================================================

BTN_START = "Boshlash"
BTN_BACK = "Orqaga"
BTN_CANCEL = "Bekor qilish"
BTN_SKIP = "O'tkazib yuborish"
BTN_MAIN_MENU = "Asosiy menyu"
BTN_CONFIRM = "Tasdiqlash"
BTN_SHARE_PHONE = "Telefon raqamni yuborish"
BTN_OPEN_APP = "Web ilovada ochish"

# ==========================================================================
#  Umumiy xabarlar
# ==========================================================================

CANCELLED = "Amal bekor qilindi."

MAIN_MENU = "Asosiy menyu. Kerakli bo'limni tanlang."

NOT_REGISTERED = (
    "Avval ro'yxatdan o'tishingiz kerak.\n\n"
    "Buning uchun /start buyrug'ini yuboring."
)

BLOCKED = (
    "Hisobingiz bloklangan.\n\n"
    "Savollaringiz bo'lsa, administrator bilan bog'laning."
)

ADMIN_ONLY = "Bu bo'lim faqat administratorlar uchun."

UNKNOWN_COMMAND = (
    "Bu buyruqni tushunmadim.\n\n"
    "Quyidagi menyudan foydalaning yoki /start ni bosing."
)

ERROR_GENERIC = (
    "Kutilmagan xatolik yuz berdi.\n\n"
    "Iltimos, qaytadan urinib ko'ring. Muammo takrorlansa /start ni bosing."
)

TOO_FAST = "Biroz sekinroq, iltimos."

LOADING = "Bajarilmoqda..."

WEB_APP_HINT = (
    "<b>Web ilova</b>\n\n"
    "Testlarni topshirish, javoblarni tekshirish, natijalarni ko'rish va "
    "sertifikat yuklab olish — barchasi qulay ilovada.\n\n"
    "Quyidagi tugmani bosing."
)

WEB_APP_UNAVAILABLE = (
    "Web ilova hozircha mavjud emas.\n\n"
    "Barcha amallarni bot orqali bajarishingiz mumkin."
)

HELP = (
    "<b>Yordam</b>\n\n"
    "<b>Botdan qanday foydalanish kerak?</b>\n\n"
    "{bullet} <b>Ilovani ochish</b> — testlarni topshirish, natijalarni va "
    "javoblarni ko'rish, sertifikat yuklab olish uchun qulay web ilova.\n\n"
    "{bullet} <b>Testda qatnashish</b> — test kodini kiriting yoki ochiq "
    "testlar ro'yxatidan tanlang. Pullik testda ID kod so'raladi.\n\n"
    "{bullet} <b>Test yaratish</b> — o'z testingizni yarating: savollar "
    "sonini belgilang, javob kalitini kiriting va testni faollashtiring. "
    "Test kodini ishtirokchilarga tarqating.\n\n"
    "{bullet} <b>Natijalarim</b> — topshirgan testlaringiz natijasi.\n\n"
    "{bullet} <b>Testlarim</b> — siz yaratgan testlarni boshqarish: "
    "natijalarni hisoblash, e'lon qilish, o'chirish.\n\n"
    "{bullet} <b>Sertifikatlar</b> — pullik RASH testlari uchun berilgan "
    "sertifikatlar.\n\n"
    "<b>Buyruqlar:</b>\n"
    "/start — botni qayta ishga tushirish\n"
    "/menu — asosiy menyu\n"
    "/ilova — web ilovani ochish\n"
    "/bekor — joriy amalni bekor qilish\n"
    "/yordam — ushbu yo'riqnoma"
).format(bullet=BULLET)

BOT_DESCRIPTION = (
    "Assalomu alaykum! Ona tili testlarini tez va qulay tekshiruvchi "
    "botga xush kelibsiz.\n"
    "Test javoblaringizni yuboring va natijangizni bilib oling.\n"
    "Telegram kanalimiz: @Oybek_ustoz_MS"
)


def progress_bar(current: int, total: int, width: int = 10) -> str:
    """Matnli progress-bar yasaydi."""
    if total <= 0:
        return "▱" * width
    filled = max(0, min(width, round(current / total * width)))
    return "▰" * filled + "▱" * (width - filled)


def answer_mark(*, is_empty: bool, is_full: bool, has_partial: bool = False) -> str:
    """Javob holatini bildiruvchi tipografik belgi."""
    if is_empty:
        return MARK_EMPTY
    if is_full:
        return MARK_CORRECT
    if has_partial:
        return MARK_PARTIAL
    return MARK_WRONG


__all__ = [name for name in dir() if not name.startswith("_")]
