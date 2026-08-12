"""Test yaratish va topshirish bilan bog'liq matnlar (emojisiz)."""

from __future__ import annotations

# ==========================================================================
#  Test turini tanlash
# ==========================================================================

CHOOSE_TYPE = (
    "<b>Yangi test yaratish</b>\n\n"
    "Qaysi turdagi testni yaratmoqchisiz?\n\n"
    "<b>1-tur. Oddiy test</b>\n"
    "A/B/C/D variantli, natija to‘g‘ri javoblar soni bo‘yicha hisoblanadi. "
    "RASH modeli ishlatilmaydi.\n\n"
    "<b>2-tur. Bepul RASH testi</b>\n"
    "Natija Rasch (IRT-1PL) modeli asosida hisoblanadi, reyting tuziladi. "
    "Sertifikat berilmaydi.\n\n"
    "<b>3-tur. Pullik RASH testi</b>\n"
    "Faqat asosiy admin uchun. Kirish bir martalik ID kodlar orqali, "
    "sertifikat beriladi."
)

BTN_TYPE_SIMPLE = "1-tur. Oddiy test"
BTN_TYPE_RASCH_FREE = "2-tur. Bepul RASH testi"
BTN_TYPE_RASCH_PAID = "3-tur. Pullik RASH testi"

PAID_ADMIN_ONLY = (
    "Pullik RASH testini faqat asosiy admin yaratishi mumkin.\n\n"
    "Siz bepul testlarni yaratishingiz mumkin."
)

# ==========================================================================
#  Test yaratish bosqichlari
# ==========================================================================

ASK_TITLE = (
    "Test nomini kiriting.\n\n"
    "Masalan: <i>MILLIY SERTIFIKAT MOCK №7</i>"
)

INVALID_TITLE = "Test nomi kamida 3 ta belgidan iborat bo‘lishi kerak."

ASK_STRUCTURE = (
    "<b>Test tuzilmasini tanlang</b>\n\n"
    "<b>Milliy sertifikat shabloni</b> — 45 ta savol:\n"
    "• 1–32 — A, B, C, D (bitta javob)\n"
    "• 33–35 — A, B, C, D, E, F (moslashtirish, bitta javob)\n"
    "• 36–45 — variantsiz, a) va b) javob maydonlari\n\n"
    "Yoki oddiy tuzilmani tanlab, savollar sonini o‘zingiz belgilang."
)

BTN_NATIONAL_TEMPLATE = "Milliy sertifikat shabloni (45 ta)"
BTN_CUSTOM_STRUCTURE = "Savollar sonini o‘zim belgilayman"

ASK_QUESTION_COUNT = (
    "Test nechta savoldan iborat bo‘lsin?\n\n"
    "Tayyor variantlardan birini tanlang yoki sonni yozib yuboring "
    "(1 dan 500 gacha)."
)

INVALID_QUESTION_COUNT = "1 dan 500 gacha bo‘lgan son kiriting."

# --- Javob kalitlari ---

ASK_SINGLE_KEYS = (
    "<b>Javob kalitini kiriting</b> ({count} ta savol, A–D)\n\n"
    "Quyidagi ko‘rinishlardan istalganini ishlatishingiz mumkin:\n"
    "• <code>ABCDABCD...</code>\n"
    "• <code>A B C D A B</code>\n"
    "• <code>1-A 2-B 3-C</code>"
)

ASK_MULTI_KEYS = (
    "<b>Moslashtirish savollari kaliti</b> ({count} ta savol, A–F)\n\n"
    "Har bir savolga <b>bitta</b> harf to‘g‘ri keladi. Javoblarni vergul "
    "bilan ajratib yozing:\n"
    "<code>A, C, E</code>"
)

ASK_OPEN_KEYS = (
    "<b>Ochiq javobli savollar kaliti</b> ({count} ta savol)\n\n"
    "Har bir savol uchun alohida qator yozing, a) va b) javoblarni "
    "<code>;</code> bilan ajrating:\n\n"
    "<code>12 ; 3/4\n"
    "sqrt(2) ; pi/6\n"
    "0.5 ; -2</code>\n\n"
    "Javoblar matematik ekvivalentlik bo‘yicha tekshiriladi: "
    "<code>1/2</code> va <code>0.5</code> bir xil hisoblanadi."
)

KEYS_SAVED = "Javob kaliti saqlandi."

KEY_ERRORS = "Kalitda xatolar bor:\n\n{errors}\n\nQaytadan kiriting."

# --- Sozlamalar ---

ASK_DURATION = (
    "Test qachon tugasin?\n\n"
    "Tayyor variantni tanlang, <b>«Sana va vaqtni tanlash»</b> orqali "
    "kalendardan aniq kun va soatni belgilang yoki soatlar sonini yozing "
    "(masalan: <code>48</code>)."
)

BTN_NO_LIMIT = "Cheklovsiz"
BTN_1_HOUR = "1 soat"
BTN_3_HOURS = "3 soat"
BTN_24_HOURS = "24 soat"
BTN_7_DAYS = "7 kun"
BTN_PICK_DATETIME = "Sana va vaqtni tanlash"

ASK_END_DATE = (
    "<b>Test tugash sanasi</b>\n\n"
    "Kalendardan kunni tanlang. Keyingi qadamda soat va daqiqani "
    "belgilaysiz (masalan, <code>21:30</code>)."
)

ASK_END_HOUR = (
    "<b>{date}</b>\n\n"
    "Test soat nechada tugasin? Soatni tanlang."
)

ASK_END_MINUTE = (
    "<b>{date}, soat {hour}</b>\n\n"
    "Daqiqani tanlang."
)

END_TIME_SET = "Tugash vaqti belgilandi: <b>{moment}</b>"

END_TIME_IN_PAST = (
    "Bu vaqt allaqachon o‘tib ketgan. Iltimos, kelajakdagi sana va vaqtni tanlang."
)

ASK_VISIBILITY = (
    "Natijalar qatnashchilarga ko‘rinsinmi?\n\n"
    "Agar «Ha» bo‘lsa, test yakunlangach ishtirokchi o‘z natijasini va "
    "qaysi savollarda xato qilganini ko‘ra oladi."
)

ASK_CERTIFICATE = (
    "Sertifikat berilsinmi?\n\n"
    "Sertifikat natijalar e’lon qilingandan keyin, PDF ko‘rinishida "
    "QR-kod bilan beriladi."
)

BTN_YES = "Ha"
BTN_NO = "Yo‘q"

EXAM_CREATED = (
    "<b>Test yaratildi</b>\n\n"
    "Nomi: <b>{title}</b>\n"
    "Test kodi: <code>{code}</code>\n"
    "Savollar: <b>{questions}</b> ta\n"
    "Turi: {type}\n"
    "Tugash vaqti: {ends_at}\n\n"
    "Test faollashtirildi — endi ishtirokchilar javob yuborishi mumkin.\n\n"
    "Ishtirokchilarga quyidagi kodni yoki havolani yuboring:\n"
    "<code>{code}</code>\n{link}"
)

EXAM_CREATED_PAID = (
    "<b>Pullik test yaratildi</b>\n\n"
    "Nomi: <b>{title}</b>\n"
    "Test kodi: <code>{code}</code>\n"
    "Savollar: <b>{questions}</b> ta\n\n"
    "Endi ishtirokchilar uchun ID kodlar yarating."
)

# ==========================================================================
#  Testga kirish
# ==========================================================================

ASK_EXAM_CODE = (
    "Test kodini kiriting.\n\n"
    "Kod — oddiy son, masalan: <code>32</code>\n\n"
    "Kodni testni o‘tkazayotgan tashkilotchidan oling."
)

EXAM_NOT_FOUND = (
    "Bunday kodli test topilmadi.\n\n"
    "Kodni to‘g‘ri kiritganingizni tekshiring."
)

NO_OPEN_EXAMS = "Hozircha ochiq testlar yo‘q."

EXAM_INFO = (
    "<b>{title}</b>\n\n"
    "Turi: {type}\n"
    "Savollar soni: <b>{questions}</b> ta\n"
    "Maksimal ball: <b>{max_score}</b>\n"
    "Tugash vaqti: {ends_at}\n"
    "Qatnashganlar: {participants} ta\n"
    "{extra}"
)

ALREADY_PARTICIPATED = "Siz bu testda allaqachon qatnashgansiz."

# --- ID kod ---

ASK_ACCESS_CODE = "Testda qatnashish uchun ID kodingizni kiriting:"

CODE_CONFIRMED = "ID tasdiqlandi. Testda qatnashishingiz mumkin."

# ==========================================================================
#  Test topshirish
# ==========================================================================

EXAM_STARTED = (
    "<b>Test boshlandi</b>\n\n"
    "Savollar: {questions} ta\n"
    "{duration}"
    "\nJavoblaringiz avtomatik saqlanadi — internet uzilsa ham "
    "qoldirgan joyingizdan davom ettirasiz.\n\n"
    "Yakuniy javobni faqat bir marta yuborish mumkin."
)

QUESTION_SINGLE = (
    "<b>{order}-savol</b>  ({order}/{total})\n"
    "{progress}\n"
    "{text}"
    "\nTo‘g‘ri javobni tanlang."
)

QUESTION_MULTI = (
    "<b>{order}-savol</b>  ({order}/{total})\n"
    "{progress}\n"
    "{text}"
    "\nA–F variantlardan <b>mos bittasini</b> belgilang, so‘ng «Tasdiqlash» ni bosing."
)

QUESTION_OPEN = (
    "<b>{order}-savol</b>  ({order}/{total})\n"
    "{progress}\n"
    "{text}"
    "\n<b>a)</b> va <b>b)</b> javoblarni bitta xabarda, <code>;</code> bilan "
    "ajratib yuboring.\n\n"
    "Masalan: <code>12 ; 3/4</code>\n\n"
    "<code>1/2</code>, <code>0.5</code>, <code>sqrt(2)</code>, "
    "<code>pi/6</code> kabi ko‘rinishlar qabul qilinadi."
)

QUESTION_OPEN_SINGLE_PART = (
    "<b>{order}-savol</b>  ({order}/{total})\n"
    "{progress}\n"
    "{text}"
    "\nJavobingizni yuboring.\n\n"
    "Masalan: <code>12</code> yoki <code>sqrt(3)/2</code>"
)

ANSWER_SAVED = "Javob saqlandi: <b>{value}</b>"

ANSWER_EMPTY = "Javob bo‘sh. Iltimos, javobingizni yozing."

NAV_HINT = "Savollar orasida harakatlanish uchun tugmalardan foydalaning."

REVIEW_TITLE = (
    "<b>Javoblaringiz</b>\n\n"
    "Javob berilgan: <b>{answered}/{total}</b>\n\n"
    "{rows}"
)

CONFIRM_SUBMIT = (
    "<b>Javoblarni yakuniy yuborishni tasdiqlaysizmi?</b>\n\n"
    "Javob berilgan: <b>{answered}/{total}</b>\n"
    "{unanswered}\n"
    "Yuborilgandan keyin javoblarni o‘zgartirib bo‘lmaydi."
)

UNANSWERED_WARNING = "Javobsiz savollar: {orders}\n"

SUBMITTED = "Javoblaringiz qabul qilindi."

SUBMITTED_WITH_RESULT = (
    "<b>Javoblaringiz qabul qilindi</b>\n\n"
    "To‘g‘ri javoblar: <b>{correct}/{total}</b>\n"
    "Xato javoblar: <b>{wrong}</b>\n"
    "Javobsiz: <b>{empty}</b>\n"
    "Foiz: <b>{percent}%</b>"
)

RESULTS_LATER = (
    "\n\nYakuniy natija test yakunlangach, tashkilotchi natijalarni "
    "e’lon qilgandan so‘ng ma’lum bo‘ladi."
)

# ==========================================================================
#  Natijalar
# ==========================================================================

NO_RESULTS = "Sizda hali natijalar yo‘q.\n\nBiror testda qatnashib ko‘ring."

RESULT_READY = (
    "<b>Natijangiz tayyor</b>\n\n"
    "Test: <b>{title}</b>\n"
    "RASH ballingiz: <b>{ball}</b>\n"
    "Daraja: <b>{grade}</b>\n"
    "Reyting: <b>{rank}</b>"
)

RESULT_SIMPLE = (
    "<b>Natijangiz</b>\n\n"
    "Test: <b>{title}</b>\n"
    "To‘g‘ri javoblar: <b>{correct}/{total}</b>\n"
    "Xato: <b>{wrong}</b>\n"
    "Javobsiz: <b>{empty}</b>\n"
    "Foiz: <b>{percent}%</b>\n"
    "Reyting: <b>{rank}</b>"
)

RESULT_HIDDEN = (
    "Bu testda natijalar qatnashchilarga ko‘rsatilmaydi.\n\n"
    "Natijalarni tashkilotchi e’lon qilganda ko‘rishingiz mumkin."
)

RESULT_PENDING = (
    "Natijalar hali e’lon qilinmagan.\n\n"
    "Tashkilotchi natijalarni tasdiqlagandan so‘ng xabar beramiz."
)

RATING_TITLE = "<b>{title}</b> — reyting\n\n{rows}"

REVIEW_ANSWERS_TITLE = "<b>{title}</b> — javoblaringiz\n\n{rows}"

BTN_SHOW_ANSWERS = "Javoblarimni ko‘rish"
BTN_SHOW_RATING = "Reyting"
BTN_GET_CERTIFICATE = "Sertifikatni olish"

# ==========================================================================
#  Sertifikat
# ==========================================================================

CERTIFICATE_READY = (
    "<b>Sertifikatingiz tayyor</b>\n\n"
    "Raqami: <code>{number}</code>\n"
    "Ball: <b>{ball}</b>\n"
    "Daraja: <b>{grade}</b>\n\n"
    "QR-kod orqali sertifikatning haqiqiyligini istalgan vaqtda "
    "tekshirish mumkin."
)

NO_CERTIFICATES = "Sizda hali sertifikatlar yo‘q."

CERTIFICATE_NOT_AVAILABLE = "{reason}"


__all__ = [name for name in dir() if not name.startswith("_")]
