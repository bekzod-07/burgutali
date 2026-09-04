"""Administrator paneli matnlari (emojisiz)."""

from __future__ import annotations

PANEL_TITLE = (
    "<b>Administrator paneli</b>\n\n"
    "Kerakli bo‘limni tanlang."
)

BTN_STATS = "Umumiy statistika"
BTN_ALL_EXAMS = "Barcha testlar"
BTN_CODES = "ID kodlar yaratish"
BTN_EXPORT_USERS = "Foydalanuvchilar (Excel)"
BTN_WEB_PANEL = "Web panel"

STATS = (
    "<b>Umumiy statistika</b>\n\n"
    "<b>Foydalanuvchilar</b>\n"
    "• Jami: <b>{users_total}</b>\n"
    "• Ro‘yxatdan o‘tgan: <b>{users_registered}</b>\n"
    "• Bugun qo‘shilgan: <b>{users_new}</b>\n"
    "• Bugun faol: <b>{users_active}</b>\n\n"
    "<b>Testlar</b>\n"
    "• Jami: <b>{exams_total}</b>\n"
    "• Faol: <b>{exams_active}</b>\n"
    "• E’lon qilingan: <b>{exams_published}</b>\n\n"
    "<b>Javoblar</b>\n"
    "• Jami topshirilgan: <b>{attempts_total}</b>\n"
    "• Bugun: <b>{attempts_today}</b>\n\n"
    "<b>ID kodlar</b>\n"
    "• Jami: <b>{codes_total}</b>\n"
    "• Ishlatilgan: <b>{codes_used}</b>\n"
    "• Ishlatilmagan: <b>{codes_unused}</b>\n\n"
    "<b>Sertifikatlar</b>: <b>{certificates}</b> ta"
)

# ==========================================================================
#  ID kodlar
# ==========================================================================

CHOOSE_EXAM_FOR_CODES = (
    "<b>ID kodlar yaratish</b>\n\n"
    "Qaysi test uchun ID kod yaratilsin?"
)

NO_PAID_EXAMS = (
    "Pullik RASH testlari topilmadi.\n\n"
    "Avval pullik test yarating."
)

ASK_CODE_QUANTITY = (
    "<b>{title}</b>\n\n"
    "Nechta ID kod yaratilsin?"
)

BTN_CUSTOM_QUANTITY = "Boshqa miqdor"

ASK_CUSTOM_QUANTITY = (
    "Nechta ID kod kerakligini yozing (1 dan {maximum} gacha):"
)

INVALID_QUANTITY = "1 dan {maximum} gacha bo‘lgan son kiriting."

CODES_GENERATING = "ID kodlar yaratilmoqda... Bu bir necha soniya olishi mumkin."

CODES_READY = (
    "<b>{quantity} ta ID kod yaratildi</b>\n\n"
    "Test: <b>{title}</b>\n"
    "Test kodi: <code>{code}</code>\n\n"
    "Kodlar ro‘yxati Excel fayl ko‘rinishida yuborildi.\n"
    "To‘lov qilgan har bir qatnashchiga bittadan ID kod bering.\n\n"
    "Har bir ID kod faqat <b>bitta yakuniy javob</b> uchun ishlaydi."
)

CODES_SAMPLE = "Namuna:\n<code>{sample}</code>"

# ==========================================================================
#  Test boshqaruvi
# ==========================================================================

EXAM_MANAGE = (
    "<b>{title}</b>\n\n"
    "Kod: <code>{code}</code>\n"
    "Turi: {type}\n"
    "Holati: <b>{status}</b>\n"
    "Savollar: {questions} ta\n"
    "Qatnashganlar: {participants} ta\n"
    "{codes_info}"
    "\nQuyidagi amallardan birini tanlang."
)

#: Yagona yakunlovchi amal — yopish, hisoblash va e’lon qilish bir tugmada.
BTN_FINISH = "Testni tugatish"
BTN_RATING = "Reyting"
BTN_EXPORT_RESULTS = "Natijalar (Excel)"
BTN_EXPORT_PDF = "Natijalar (PDF)"
BTN_MAKE_CODES = "ID kodlar yaratish"
BTN_CERTIFICATES = "Sertifikatlarni yaratish"
BTN_DELETE = "Testni o‘chirish"

CALCULATING = "Test tugatilmoqda: natijalar hisoblanib e’lon qilinmoqda..."

PUBLISHED = (
    "<b>Test tugatildi — natijalar e’lon qilindi</b>\n\n"
    "Barcha qatnashchilarga xabar yuborilmoqda...\n"
    "{certificates}"
)

PUBLISH_NOTIFICATION = (
    "<b>Natijangiz tayyor</b>\n\n"
    "Test: <b>{title}</b>\n"
    "{result}"
)

NO_EXAMS = "Sizda hali testlar yo‘q.\n\n«Test yaratish» tugmasi orqali yarating."

EXAM_LIST_TITLE = "<b>Sizning testlaringiz</b>\n\nBoshqarish uchun testni tanlang."

ALL_EXAMS_TITLE = "<b>Barcha testlar</b>\n\nBoshqarish uchun testni tanlang."

# ==========================================================================
#  O'chirish
# ==========================================================================

CONFIRM_DELETE = (
    "<b>Testni butunlay o‘chirish</b>\n\n"
    "Test: <b>{title}</b> (<code>{code}</code>)\n\n"
    "Quyidagilar ham birga o‘chadi:\n"
    "• savollar: <b>{questions}</b> ta\n"
    "• urinishlar: <b>{attempts}</b> ta (topshirilgan: <b>{submitted}</b>)\n"
    "• ID kodlar: <b>{codes}</b> ta (ishlatilgan: <b>{used_codes}</b>)\n"
    "• sertifikatlar: <b>{certificates}</b> ta\n\n"
    "<b>Bu amalni ortga qaytarib bo‘lmaydi.</b>\n"
    "Ma’lumotlarni saqlab qolish uchun avval natijalarni Excel/PDF "
    "ko‘rinishida yuklab oling."
)

BTN_CONFIRM_DELETE = "Ha, butunlay o‘chirilsin"
BTN_CANCEL_DELETE = "Yo‘q, bekor qilish"

DELETED = "{message}"

# ==========================================================================
#  Avtomatik natijalar hisoboti
# ==========================================================================

REPORT_CLOSED = (
    "<b>Test yakunlandi</b>\n\n"
    "Test: <b>{title}</b>\n"
    "Kod: <code>{code}</code>\n"
    "Turi: {type}\n"
    "Qatnashchilar: <b>{participants}</b> ta\n\n"
    "Umumiy natijalar quyidagi faylda — <b>kanalga qo’yish uchun</b>. "
    "Unda nechta savolni to’g’ri topgani ko’rsatilmaydi."
)

REPORT_PUBLISHED = (
    "<b>Natijalar e’lon qilindi</b>\n\n"
    "Test: <b>{title}</b>\n"
    "Kod: <code>{code}</code>\n"
    "Qatnashchilar: <b>{participants}</b> ta\n\n"
    "E’lon qilingan umumiy natijalar quyidagi faylda — "
    "<b>kanalga qo’yish uchun</b>. Unda nechta savolni to’g’ri "
    "topgani ko’rsatilmaydi."
)

#: Ikkinchi PDF — to'liq hisobot, faqat adminlarga.
REPORT_ADMIN_COPY = (
    "<b>Faqat admin uchun</b>\n\n"
    "Test: <b>{title}</b> (<code>{code}</code>)\n\n"
    "To‘liq hisobot: umumiy statistika, darajalar taqsimoti, savollar "
    "qiyinchiligi va reyting — to‘g‘ri javoblar soni bilan.\n"
    "<b>Bu faylni kanalga qo‘ymang.</b>"
)

REPORT_NO_PARTICIPANTS = (
    "<b>Test yakunlandi</b>\n\n"
    "Test: <b>{title}</b> (<code>{code}</code>)\n\n"
    "Bu testda qatnashchi bo‘lmadi — hisobot yaratilmadi."
)

# Diagrammalar faqat adminlarga yuboriladi.
REPORT_CHART_DIFFICULTY = (
    "Savollarning qiyinchilik darajasi. "
    "Ustun balandligi — savolga noto‘g‘ri javob berganlar ulushi."
)

REPORT_CHART_DISTRIBUTION = (
    "Ishtirokchilar ballarining taqsimoti."
)

BTN_CHARTS = "Savollar qiyinchiligi"

# Qatnashchilarga e'lon qilinadigan umumiy natijalar (2- va 3-tur).
OVERALL_RESULTS_CAPTION = (
    "<b>{title}</b> — umumiy natijalar"
)

#: Diagramma nechta odam savolni topganini ko'rsatadi — u faqat
#: `.env` dagi asosiy adminlarga ochiq.
CHARTS_ADMIN_ONLY = (
    "Savollar qiyinchiligi diagrammasi faqat asosiy adminlar uchun."
)

CHARTS_EMPTY = (
    "Diagramma uchun ma’lumot yo‘q.\n\n"
    "Avval «Testni tugatish» tugmasini bosing."
)


# --------------------------------------------------------------------------
#  Reklama (ommaviy xabar)
# --------------------------------------------------------------------------

#: Yuborish yakunlanganda adminlarga boradigan qisqa hisobot.
BROADCAST_DONE = (
    "<b>Reklama yuborildi</b>\n\n"
    "Xabar: <b>{title}</b>\n"
    "Qabul qiluvchilar: <b>{total}</b> ta\n"
    "Yetkazildi: <b>{sent}</b> ta\n"
    "Botni bloklaganlar: <b>{blocked}</b> ta\n"
    "Yetkazilmadi: <b>{failed}</b> ta"
)

#: Sinov xabaridan oldin yuboriladigan izoh.
BROADCAST_TEST_NOTE = (
    "<b>Sinov xabari</b> — quyida reklama qanday ko‘rinishi ko‘rsatiladi. "
    "Bu xabar boshqa foydalanuvchilarga yuborilmadi."
)


__all__ = [name for name in dir() if not name.startswith("_")]
