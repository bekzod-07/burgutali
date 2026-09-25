"""
E'lon uchun soxta (mock) qatnashchilar.

Mock imtihon natijalarini katta auditoriyada o'tkazilgandek ko'rsatish
kerak bo'ladi: admin jami sonni (masalan 1000 ta) va darajalar ulushini
beradi — tizim esa o'ylab topilgan ism-familiyalar bilan shuncha qator
yaratadi.

Ulushlar foizda beriladi, masalan standart taqsimot:

    A+ 2%, A 4%, B+ 6%, B 8%, C+ 18%, C 22%

Qolgani (bu misolda 40%) — daraja olmaganlar. 1000 ta qatnashchida bu
20 ta A+, 40 ta A, 60 ta B+, 80 ta B, 180 ta C+, 220 ta C va 400 ta
darajasiz natija degani.

Ball har bir daraja oralig'idan tasodifiy tanlanadi (`C.GRADE_TABLE`),
shuning uchun daraja ham, foiz ham, fan ballari ham haqiqiy natijadagi
kabi hisoblanadi.

**Muhim:** soxta qatorlar `MockParticipant` jadvalida saqlanadi va
`Attempt` ga umuman tegmaydi. Rasch hisob-kitobi, savollar qiyinchiligi,
statistika va sertifikatlar faqat haqiqiy javoblar bo'yicha qoladi —
haqiqiy o'quvchilarning balli, darajasi va foizi o'zgarmaydi.
"""

from __future__ import annotations

import logging
import math
import random

from django.db import transaction
from django.db.models import Avg

from core import constants as C

from .models import MockParticipant

logger = logging.getLogger(__name__)

#: Standart taqsimot: `(daraja, foiz)`. Yig'indisi 100 dan kam bo'lsa,
#: qolgani daraja olmaganlarga to'g'ri keladi.
DEFAULT_SHARES: tuple[tuple[str, float], ...] = (
    ("A+", 2.0),
    ("A", 4.0),
    ("B+", 6.0),
    ("B", 8.0),
    ("C+", 18.0),
    ("C", 22.0),
)

#: Bir marta yaratiladigan soxta qatnashchilar soni chegarasi.
MAX_MOCK_PARTICIPANTS: int = 20000

#: Daraja olinmagan natijalar shu ball oralig'idan olinadi.
_NO_GRADE_RANGE: tuple[float, float] = (18.0, 45.9)

FIRST_NAMES: tuple[str, ...] = (
    "Abdulaziz", "Abdulloh", "Adham", "Akbar", "Akmal", "Alisher", "Anvar",
    "Asadbek", "Aziz", "Azizbek", "Bahrom", "Behruz", "Bekzod", "Bobur",
    "Davron", "Diyor", "Doston", "Eldor", "Elyor", "Farrux", "Farhod",
    "Fazliddin", "Firdavs", "G'ayrat", "Hasan", "Husan", "Ibrohim", "Ilhom",
    "Islom", "Jahongir", "Jasur", "Javohir", "Kamron", "Kamoliddin",
    "Laziz", "Lutfulla", "Mansur", "Mirjalol", "Muhammad", "Muhammadali",
    "Mustafo", "Nodir", "Nodirbek", "Nurbek", "Oybek", "Otabek", "Ozodbek",
    "Qodirjon", "Ravshan", "Rustam", "Sanjar", "Sardor", "Shahzod",
    "Shohruh", "Sherzod", "Sirojiddin", "Temur", "Tohir", "Ulug'bek",
    "Umid", "Xurshid", "Yusuf", "Zafar", "Zohid",
    "Aziza", "Barno", "Charos", "Dilafruz", "Dildora", "Dilnoza", "Durdona",
    "Farida", "Feruza", "Gulbahor", "Gulnora", "Hilola", "Husniya",
    "Iroda", "Kamola", "Lobar", "Madina", "Malika", "Maftuna", "Mohira",
    "Muattar", "Muslima", "Nargiza", "Nilufar", "Nodira", "Odina",
    "Oydina", "Ozoda", "Rayhona", "Ruxshona", "Sabina", "Sarvinoz",
    "Sevara", "Shahnoza", "Sitora", "Umida", "Xadicha", "Yulduz",
    "Zarina", "Zebo", "Zilola", "Zuhra",
)

LAST_NAMES: tuple[str, ...] = (
    "Abdullayev", "Abdurahmonov", "Ahmedov", "Akbarov", "Alimov", "Aliyev",
    "Anvarov", "Artikov", "Ashurov", "Azizov", "Bekmurodov", "Boboyev",
    "Choriyev", "Davronov", "Ergashev", "Eshonqulov", "Fayzullayev",
    "G'aniyev", "Hakimov", "Hamidov", "Hasanov", "Ibrohimov", "Ismoilov",
    "Jo'rayev", "Jumayev", "Kamolov", "Karimov", "Kholmatov", "Qodirov",
    "Qosimov", "Mahmudov", "Mamatov", "Mirzayev", "Muhammadiyev",
    "Murodov", "Nazarov", "Niyozov", "Normatov", "Nurmatov", "Olimov",
    "Ortiqov", "Otajonov", "Rahimov", "Rahmonov", "Rasulov", "Ravshanov",
    "Sadullayev", "Safarov", "Salimov", "Sattorov", "Shodmonov",
    "Sobirov", "Sultonov", "Tashmatov", "To'rayev", "Tursunov", "Umarov",
    "Usmonov", "Xolmirzayev", "Xudoyberdiyev", "Yo'ldoshev", "Yusupov",
    "Zoirov", "Zokirov",
)

#: Ayol ismlari ro'yxatning shu indeksidan boshlanadi — familiyaga «a»
#: qo'shish uchun kerak (Karimov -> Karimova).
_FEMALE_FROM = FIRST_NAMES.index("Aziza")


def _full_name(rng: random.Random) -> str:
    """Tasodifiy ism va familiya (ayol ismiga familiya moslashtiriladi)."""
    index = rng.randrange(len(FIRST_NAMES))
    first = FIRST_NAMES[index]
    last = LAST_NAMES[rng.randrange(len(LAST_NAMES))]
    if index >= _FEMALE_FROM:
        last = f"{last}a"
    return f"{first} {last}"


#: Ulushlar shu tartibda so'raladi va shu tartibda hisoblanadi —
#: yuqori darajadan pastga, oxirida daraja olmaganlar.
GRADE_SEQUENCE: tuple[str, ...] = tuple(reversed(C.GRADE_ORDER))


def normalize_shares(shares) -> list[tuple[str, float]]:
    """
    Foizlarni tekshiradi va tartibga soladi.

    Qabul qiladi `{daraja: foiz}` lug'atini yoki `(daraja, foiz)`
    juftliklari ro'yxatini. Har qanday daraja, shu jumladan «Daraja
    olinmadi» ham beriladi — ya'ni taqsimotni to'liq qo'lda belgilash
    mumkin.

    Noma'lum darajalar va manfiy qiymatlar tashlab yuboriladi. Yig'indi
    100 dan oshsa mutanosib kamaytiriladi: bu oxirgi himoya, chunki
    panel formasi bunday qiymatni umuman qabul qilmaydi.
    """
    if hasattr(shares, "items"):
        pairs = list(shares.items())
    else:
        pairs = list(shares or [])

    cleaned: list[tuple[str, float]] = []
    for grade, percent in pairs:
        name = str(grade).strip()
        if name not in C.GRADE_ORDER:
            continue
        try:
            value = float(percent)
        except (TypeError, ValueError):
            continue
        if value > 0:
            cleaned.append((name, value))

    total = sum(value for _grade, value in cleaned)
    if total > 100.0:
        cleaned = [(grade, value * 100.0 / total) for grade, value in cleaned]

    # Hisob doim yuqori darajadan boshlanadi, darajasizlar esa oxirida —
    # yaxlitlash qoldig'i o'shalarga qo'shiladi.
    order = {grade: index for index, grade in enumerate(GRADE_SEQUENCE)}
    cleaned.sort(key=lambda item: order.get(item[0], len(order)))
    return cleaned


def plan_counts(total: int, shares=None) -> list[tuple[str, int]]:
    """
    Har bir darajaga nechta qatnashchi to'g'ri kelishini hisoblaydi.

    Qaytaradi `(daraja, soni)` juftliklari. Yaxlitlash tufayli yoki
    foizlar yig'indisi 100 dan kam bo'lgani uchun ortib qolgan qatorlar
    daraja olmaganlarga qo'shiladi, shuning uchun yig'indi doim `total`
    ga teng bo'ladi.
    """
    total = max(0, int(total))
    if not total:
        return []

    cleaned = normalize_shares(DEFAULT_SHARES if shares is None else shares)
    plan: list[tuple[str, int]] = []
    assigned = 0
    for grade, percent in cleaned:
        count = int(round(total * percent / 100.0))
        count = min(count, total - assigned)
        if count > 0:
            plan.append((grade, count))
            assigned += count

    rest = total - assigned
    if rest > 0:
        for index, (grade, count) in enumerate(plan):
            if grade == C.NO_GRADE:
                plan[index] = (grade, count + rest)
                break
        else:
            plan.append((C.NO_GRADE, rest))
    return plan


def _ball_range(grade: str, max_ball: float) -> tuple[float, float]:
    """Daraja uchun ball oralig'i (yuqori daraja test maksimumi bilan cheklanadi)."""
    if grade == C.NO_GRADE:
        low, high = _NO_GRADE_RANGE
        return low, min(high, max_ball)

    for low, high, name in C.GRADE_TABLE:
        if name != grade:
            continue
        upper = max_ball if high is None else min(float(high), max_ball)
        return float(low), max(float(low), upper)
    return 0.0, max_ball


@transaction.atomic
def generate(exam, total: int, shares=None, *, replace: bool = True, seed=None) -> dict:
    """
    Testga soxta qatnashchilar qo'shadi.

    `replace=True` bo'lsa avvalgi soxta qatorlar o'chiriladi — shuning
    uchun funksiyani qayta chaqirish ro'yxatni ikkilantirmaydi.

    Qaytaradi: `{"created", "removed", "plan"}`.
    """
    total = max(0, int(total))
    if total > MAX_MOCK_PARTICIPANTS:
        raise ValueError(
            f"Soxta qatnashchilar soni {MAX_MOCK_PARTICIPANTS} dan oshmasligi kerak."
        )

    removed = 0
    if replace:
        # O'rinlar oxirida bir marta qayta hisoblanadi.
        removed = clear(exam, resync=False)

    plan = plan_counts(total, shares)
    if not plan:
        # Soni 0 berilgan — ro'yxat tozalandi, o'rinlar tiklanadi.
        _resync_ranks(exam)
        return {"created": 0, "removed": removed, "plan": []}

    rng = random.Random(seed)
    max_ball = float(getattr(exam, "max_ball", None) or C.MAX_BALL)

    # Ismlar takrorlanmasligi uchun ko'rilganlari eslab qolinadi; ro'yxat
    # tugab qolsa (juda ko'p qatnashchi) takror ham ruxsat etiladi.
    seen: set[str] = set()
    unique_limit = len(FIRST_NAMES) * len(LAST_NAMES)

    rows: list[MockParticipant] = []
    order = 0
    for grade, count in plan:
        low, high = _ball_range(grade, max_ball)
        for _ in range(count):
            name = _full_name(rng)
            if len(seen) < unique_limit:
                attempts = 0
                while name in seen and attempts < 40:
                    name = _full_name(rng)
                    attempts += 1
            seen.add(name)

            ball = round(rng.uniform(low, high), 2)
            order += 1
            rows.append(
                MockParticipant(
                    exam=exam,
                    full_name=name,
                    ball=ball,
                    # Darajani balldan qayta aniqlaymiz: yaxlitlashdan keyin
                    # ham jadval bilan mos bo'lishi kerak.
                    grade=C.grade_for_ball(ball),
                    order=order,
                )
            )

    MockParticipant.objects.bulk_create(rows, batch_size=500)
    _resync_ranks(exam)
    logger.info(
        "Soxta qatnashchilar yaratildi: exam_id=%s, soni=%s", exam.id, len(rows)
    )
    return {"created": len(rows), "removed": removed, "plan": plan}


def clear(exam, *, resync: bool = True) -> int:
    """Testdagi barcha soxta qatnashchilarni o'chiradi."""
    removed, _ = MockParticipant.objects.filter(exam=exam).delete()
    if resync:
        _resync_ranks(exam)
    return int(removed)


def _resync_ranks(exam) -> None:
    """
    Haqiqiy qatnashchilarning reyting o'rnini qayta hisoblaydi.

    Soxta qatorlar qo'shilgach yoki o'chirilgach o'rinlar siljiydi, ball
    va daraja esa o'z joyida qoladi.
    """
    from apps.attempts.services import assign_ranks

    assign_ranks(exam)


def count(exam) -> int:
    """Testdagi soxta qatnashchilar soni."""
    return MockParticipant.objects.filter(exam=exam).count()


def participants(exam):
    """Soxta qatnashchilar (ball bo'yicha kamayish tartibida)."""
    return MockParticipant.objects.filter(exam=exam).order_by("-ball", "order")


def balls(exam) -> list[float]:
    """Soxta qatnashchilarning ballari (ballar taqsimoti diagrammasi uchun)."""
    return [
        float(ball)
        for ball in MockParticipant.objects.filter(exam=exam).values_list(
            "ball", flat=True
        )
        if ball is not None
    ]


def _logit(value: float) -> float:
    """`ln(p / (1 - p))` — chekka qiymatlar biroz ichkariga suriladi."""
    value = min(max(float(value), 0.02), 0.98)
    return math.log(value / (1.0 - value))


def theta_for_ball(exam, ball: float) -> float:
    """
    Balldan qobiliyatni (`theta`) tiklaydi.

    Ball shkalasi chiziqli (`apps.rasch.scoring.theta_to_ball`), shuning
    uchun teskari hisob ham chiziqli.
    """
    theta_min = float(getattr(exam, "theta_min", None) or C.THETA_MIN)
    theta_max = float(getattr(exam, "theta_max", None) or C.THETA_MAX)
    max_ball = float(getattr(exam, "max_ball", None) or C.MAX_BALL)
    if max_ball <= 0:
        return theta_min
    return theta_min + float(ball or 0.0) * (theta_max - theta_min) / max_ball


def item_hit_counts(exam, item_statistics) -> list[int]:
    """
    Soxta qatnashchilardan har bir savolni nechtasi «topgani».

    Soxta qatnashchida javoblar yo'q — faqat ball bor. Shuning uchun
    javoblar Rasch modeli bo'yicha tiklanadi: savolning qiyinligi haqiqiy
    qatnashchilarning natijasidan (`p_value`) chiqariladi, soxta
    qatnashchining qobiliyati esa ballidan. So'ng har bir savol uchun
    `P = 1 / (1 + exp(-(theta - b)))` ehtimoli bilan tanlov qilinadi.

    Natija **barqaror**: tasodifiy sonlar generatori har bir qatnashchining
    `id` si bilan urug'lantiriladi, shuning uchun diagramma har safar
    bir xil chiqadi. Haqiqiy javoblarga, Rasch kalibrlashga va
    qatnashchilarning balliga bu hisob umuman ta'sir qilmaydi.
    """
    from apps.attempts.models import Attempt

    items = list(item_statistics or [])
    if not items:
        return []

    rows = list(
        MockParticipant.objects.filter(exam=exam).values_list("id", "ball")
    )
    if not rows:
        return [0] * len(items)

    # Savol qiyinligi: o'rtacha qobiliyatli haqiqiy qatnashchi uchun
    # ehtimol aynan `p_value` chiqadigan qilib tanlanadi.
    mean_theta = Attempt.objects.filter(
        exam=exam, status=Attempt.Status.SUBMITTED, theta__isnull=False
    ).aggregate(value=Avg("theta"))["value"]
    mean_theta = float(mean_theta) if mean_theta is not None else 0.0

    difficulties = [
        mean_theta - _logit(float(item.get("p_value") or 0.0)) for item in items
    ]

    counts = [0] * len(items)
    for mock_id, ball in rows:
        theta = theta_for_ball(exam, ball)
        rng = random.Random(mock_id)
        for index, difficulty in enumerate(difficulties):
            probability = 1.0 / (1.0 + math.exp(-(theta - difficulty)))
            if rng.random() < probability:
                counts[index] += 1
    return counts


__all__ = [
    "DEFAULT_SHARES",
    "GRADE_SEQUENCE",
    "MAX_MOCK_PARTICIPANTS",
    "FIRST_NAMES",
    "LAST_NAMES",
    "normalize_shares",
    "plan_counts",
    "generate",
    "clear",
    "count",
    "participants",
    "balls",
    "theta_for_ball",
    "item_hit_counts",
]
