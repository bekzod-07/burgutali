"""
Loyiha bo'ylab ishlatiladigan o'zgarmas qiymatlar.

Bu yerda TZ (SRS) da keltirilgan barcha raqamli talablar jamlangan:
maksimal standartlashtirilgan ball, daraja jadvali, savol turlari,
variant harflari va h.k.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

# ==========================================================================
#  1. Ball va darajalar (SRS 8-bo'lim)
# ==========================================================================

#: Maksimal standartlashtirilgan ball.
MAX_BALL: Final[float] = 90.14

#: Daraja jadvali: (quyi chegara, yuqori chegara, daraja nomi).
#: Yuqori chegara `None` bo'lsa — cheksiz.
GRADE_TABLE: Final[tuple[tuple[float, float | None, str], ...]] = (
    (0.0, 45.9, "Daraja olinmadi"),
    (46.0, 49.9, "C"),
    (50.0, 54.9, "C+"),
    (55.0, 59.9, "B"),
    (60.0, 64.9, "B+"),
    (65.0, 69.9, "A"),
    (70.0, None, "A+"),
)

#: Daraja olinmaganini bildiruvchi matn.
NO_GRADE: Final[str] = "Daraja olinmadi"

#: Ball shkalasi shu darajaga «anchor» qilinadi: savollarning
#: `CERT_MIN_PERCENT` ulushini topgan qatnashchi aynan shu darajaning quyi
#: chegarasini oladi. 55 ballik shablonda 18 ta to'g'ri javob -> 46.0 ball
#: -> «C». Undan yuqorisi savollar qiyinligiga qarab taqsimlanadi.
SCALE_ANCHOR_GRADE: Final[str] = "C"

#: Sertifikat beriladigan eng past daraja. Undan pastda (0-45.9 ball)
#: daraja umuman olinmaydi, shuning uchun sertifikat ham berilmaydi.
CERT_MIN_GRADE: Final[str] = "C"

#: Sertifikat uchun talab qilinadigan standart foiz — to'g'ri javoblarning
#: ulushi. 55 ballik milliy shablonda 18 ta to'g'ri javob shu chegaraga
#: to'g'ri keladi (18/55 = 32.7%). Yangi testlar shu chegara bilan
#: yaratiladi, admin uni har bir test uchun alohida o'zgartirishi mumkin
#: (`Exam.certificate_min_percent`). Chegara qatnashchiga ko'rsatilmaydi.
CERT_MIN_PERCENT: Final[float] = 32.0

#: Darajalarni kuchi bo'yicha tartiblangan ro'yxati (pastdan yuqoriga).
GRADE_ORDER: Final[tuple[str, ...]] = (NO_GRADE, "C", "C+", "B", "B+", "A", "A+")


def grade_for_ball(ball: float | Decimal | None) -> str:
    """Berilgan ball uchun darajani qaytaradi (SRS 8-bo'lim jadvali)."""
    if ball is None:
        return NO_GRADE
    value = float(ball)
    for low, high, name in GRADE_TABLE:
        if value < low:
            continue
        if high is None or value <= high:
            return name
    # 45.9 < ball < 46.0 kabi oraliqlar uchun himoya
    for low, high, name in reversed(GRADE_TABLE):
        if value >= low:
            return name
    return NO_GRADE


def grade_lower_bound(grade: str) -> float | None:
    """Daraja boshlanadigan ball. Daraja tanilmasa — `None`."""
    name = (grade or "").strip()
    for low, _high, item in GRADE_TABLE:
        if item == name:
            return low
    return None


def grade_rank(grade: str) -> int:
    """Daraja kuchini son ko'rinishida qaytaradi (taqqoslash uchun)."""
    try:
        return GRADE_ORDER.index(grade)
    except ValueError:
        return 0


#: Sertifikat foizi hisoblanadigan asos: shu ball 100% ga to'g'ri keladi.
#: 65 — «A» darajasining quyi chegarasi, shuning uchun A va A+ o'z-o'zidan
#: 100% oladi.
CERT_PERCENT_BASE: Final[float] = 65.0


def certificate_percent(ball: float | Decimal | None, grade: str | None = None) -> float:
    """Sertifikat va natijalarda ko'rsatiladigan foiz.

    `foiz = ball * 100 / 65`, lekin 100% dan oshmaydi. Asos «A» darajasining
    quyi chegarasiga teng, shuning uchun:

      * 46.00 ball (C darajasining boshi) ->  70.77%;
      * 65.00 ball (A darajasining boshi) -> 100%;
      * undan yuqori ball ham -> 100%.

    `grade` argumenti moslik uchun qabul qilinadi, hisobga ta'sir qilmaydi.
    """
    if ball is None:
        return 0.0
    return round(min(100.0, float(ball) * 100.0 / CERT_PERCENT_BASE), 2)


# ==========================================================================
#  2. Rasch modeli (SRS 7-bo'lim)
# ==========================================================================

#: theta (qobiliyat) qiymati cheklanadigan oraliq — logit shkalasi.
THETA_MIN: Final[float] = -4.0
THETA_MAX: Final[float] = 4.0

#: Savol qiyinligi (b) uchun ruxsat etilgan oraliq.
DIFFICULTY_MIN: Final[float] = -5.0
DIFFICULTY_MAX: Final[float] = 5.0

#: MLE (Newton-Raphson) iteratsiya sozlamalari.
MLE_MAX_ITER: Final[int] = 100
MLE_TOLERANCE: Final[float] = 1e-6

#: To'liq to'g'ri / to'liq noto'g'ri natijalar uchun ekstrapolyatsiya tuzatmasi.
#: (Wright & Stone: 0.3 logit qadam)
EXTREME_SCORE_ADJUSTMENT: Final[float] = 0.3


# ==========================================================================
#  3. Test tuzilmasi (SRS 3-bo'lim) — "Milliy sertifikat" shabloni
# ==========================================================================

#: Milliy sertifikat formatidagi standart test — jami savollar soni.
NATIONAL_TOTAL_QUESTIONS: Final[int] = 45

#: 1–32-savollar: A, B, C, D — bitta to'g'ri javob.
NATIONAL_SINGLE_RANGE: Final[tuple[int, int]] = (1, 32)

#: 33–35-savollar (moslashtirish): A, B, C, D, E, F — faqat bitta to'g'ri javob.
NATIONAL_MULTI_RANGE: Final[tuple[int, int]] = (33, 35)

#: 36–45-savollar: variantsiz, har birida a) va b) javob maydoni.
NATIONAL_OPEN_RANGE: Final[tuple[int, int]] = (36, 45)

#: Bitta javobli savollar uchun variant harflari.
SINGLE_CHOICES: Final[tuple[str, ...]] = ("A", "B", "C", "D")

#: Moslashtirish savollari (33–35) uchun variant harflari — bittasi tanlanadi.
MULTI_CHOICES: Final[tuple[str, ...]] = ("A", "B", "C", "D", "E", "F")

#: Ochiq savollarning qismlari.
OPEN_PARTS: Final[tuple[str, ...]] = ("a", "b")

#: Oddiy test yaratishda taklif qilinadigan savollar soni.
SIMPLE_TEST_SIZES: Final[tuple[int, ...]] = (10, 20, 30, 45, 50, 100)


# ==========================================================================
#  4. ID kodlar (SRS 5-bo'lim va TZ "Pullik RASH testi")
# ==========================================================================

#: Administrator uchun bir marta yaratiladigan standart ID kodlar soni.
DEFAULT_CODE_BATCH: Final[int] = 3000

#: Botda taklif qilinadigan ID kod miqdorlari.
CODE_BATCH_CHOICES: Final[tuple[int, ...]] = (500, 1000, 1500, 2000)

#: Bir marta yaratish mumkin bo'lgan maksimal kodlar soni.
CODE_BATCH_MAX: Final[int] = 20000

#: ID kod formati: 4 belgi + "-" + 4 raqam (masalan, R7K4-8251).
CODE_LETTERS: Final[str] = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # I va O chiqarib tashlandi
CODE_DIGITS: Final[str] = "23456789"  # 0 va 1 chiqarib tashlandi


# ==========================================================================
#  5. Test kodi (ishtirokchi testga kirishi uchun)
# ==========================================================================

#: Test kodi — faqat raqamlardan iborat oddiy son (masalan, ``32``).
#: Avval ikki xonali, ular tugagach uch xonali kodlar beriladi.
#: Kod bir marta berilgach **hech qachon** boshqa testga qaytarilmaydi.
EXAM_CODE_LENGTHS: Final[tuple[int, ...]] = (2, 3, 4, 5, 6)

#: Kod tanlashda tasodifiy urinishlar soni (keyin ketma-ket qidiriladi).
EXAM_CODE_RANDOM_TRIES: Final[int] = 40

#: Ketma-ket qidiruv qo'llaniladigan eng katta uzunlik (undan kattasi — tasodifiy).
EXAM_CODE_SCAN_MAX_LENGTH: Final[int] = 4


# ==========================================================================
#  6. Sertifikat
# ==========================================================================

#: Sertifikat raqami prefiksi.
CERT_PREFIX: Final[str] = "RM"

#: Sertifikat tekshiruv sahifasining yo'li.
CERT_VERIFY_PATH: Final[str] = "/verify/"


# ==========================================================================
#  7. Interfeys cheklovlari
# ==========================================================================

#: Telegram xabari uzunligi chegarasi.
TELEGRAM_MESSAGE_LIMIT: Final[int] = 4096

#: Ro'yxatlarda bir sahifada ko'rsatiladigan elementlar soni.
PAGE_SIZE: Final[int] = 8

#: Reytingda botda ko'rsatiladigan eng yaxshi natijalar soni.
TOP_RATING_LIMIT: Final[int] = 10


__all__ = [
    "MAX_BALL",
    "GRADE_TABLE",
    "NO_GRADE",
    "GRADE_ORDER",
    "grade_for_ball",
    "grade_rank",
    "THETA_MIN",
    "THETA_MAX",
    "DIFFICULTY_MIN",
    "DIFFICULTY_MAX",
    "MLE_MAX_ITER",
    "MLE_TOLERANCE",
    "EXTREME_SCORE_ADJUSTMENT",
    "NATIONAL_TOTAL_QUESTIONS",
    "NATIONAL_SINGLE_RANGE",
    "NATIONAL_MULTI_RANGE",
    "NATIONAL_OPEN_RANGE",
    "SINGLE_CHOICES",
    "MULTI_CHOICES",
    "OPEN_PARTS",
    "SIMPLE_TEST_SIZES",
    "DEFAULT_CODE_BATCH",
    "CODE_BATCH_CHOICES",
    "CODE_BATCH_MAX",
    "CODE_LETTERS",
    "CODE_DIGITS",
    "EXAM_CODE_LENGTHS",
    "EXAM_CODE_RANDOM_TRIES",
    "EXAM_CODE_SCAN_MAX_LENGTH",
    "CERT_PREFIX",
    "CERT_VERIFY_PATH",
    "TELEGRAM_MESSAGE_LIMIT",
    "PAGE_SIZE",
    "TOP_RATING_LIMIT",
]
