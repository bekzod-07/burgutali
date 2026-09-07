"""
E'lon uchun qo'shiladigan soxta qatnashchi qatorlarini yaratish.

Administrator natijalarni e'lon qilayotganda ro'yxatga qo'shimcha qatorlar
qo'shishi mumkin. Bu modul ular uchun ikkita narsani beradi:

  1. **Ism-familiya** — o'zbekcha ismlar va familiyalar ro'yxatidan
     tasodifiy juftlik. Bir testda bir xil ism ikki marta chiqmaydi va
     haqiqiy qatnashchining ismi bilan ham to'qnashmaydi.

  2. **Ball** — haqiqiy natijalar orasiga tabiiy joylashadigan qiymat.
     Ball haqiqiy natijalarning o'rtachasi va tarqoqligiga qarab
     tanlanadi, shuning uchun ro'yxatning boshida ham, oxirida ham
     g'alati sakrashlar bo'lmaydi.

Diqqat: bu yerda yaratilgan qatorlar hech qanday hisob-kitobga (Rasch
kalibrlash, statistika, sertifikat) qo'shilmaydi — ular faqat e'lon
qilinadigan ro'yxatda ko'rinadi. `apps.attempts.models.PhantomParticipant`
izohiga qarang.
"""

from __future__ import annotations

import random
import unicodedata

from core import constants as C

# --------------------------------------------------------------------------
#  Ismlar
# --------------------------------------------------------------------------

#: O'g'il bolalar ismlari.
MALE_NAMES: tuple[str, ...] = (
    "Abdulaziz", "Abdulloh", "Akmal", "Alisher", "Amirbek", "Asadbek",
    "Aziz", "Azizbek", "Bahodir", "Behruz", "Bekzod", "Bobur",
    "Davron", "Diyorbek", "Doston", "Elyor", "Eldor", "Farrux",
    "Firdavs", "G‘ayrat", "Habibullo", "Hasanboy", "Humoyun", "Ibrohim",
    "Islom", "Ja’far", "Javohir", "Jasur", "Kamron", "Muhammadali",
    "Muhammadyusuf", "Mustafo", "Nodirbek", "Nuriddin", "Otabek",
    "Ozodbek", "Rustam", "Sanjar", "Sardor", "Shahriyor", "Shohjahon",
    "Sirojiddin", "Temurbek", "Ulug‘bek", "Umarbek", "Xurshid",
    "Yusufbek", "Zafarbek", "Zohidjon", "Zuhriddin",
)

#: Qiz bolalar ismlari.
FEMALE_NAMES: tuple[str, ...] = (
    "Aziza", "Barno", "Charos", "Dildora", "Dilnoza", "Durdona",
    "Farangiz", "Fotima", "Gulbahor", "Gulnoza", "Hilola", "Iroda",
    "Kamola", "Laylo", "Madina", "Mahliyo", "Malika", "Marjona",
    "Marhabo", "Maftuna", "Mohira", "Muslima", "Nafisa", "Nargiza",
    "Nilufar", "Nodira", "Oysha", "Ozoda", "Robiya", "Ruxshona",
    "Sabina", "Sarvinoz", "Sevara", "Shahnoza", "Shahzoda", "Sitora",
    "Umida", "Xadicha", "Xurshida", "Yulduz", "Zarina", "Zebo",
    "Zilola", "Zuhra", "Zulfiya",
)

#: Familiyalar (o'zak — qo'shimchasi quyida qo'shiladi).
SURNAME_STEMS: tuple[str, ...] = (
    "Abdullay", "Ahmad", "Aliy", "Artiq", "Bozor", "Ergash",
    "Hakim", "Holmat", "Ibrohim", "Ismoil", "Jo‘ra", "Karim",
    "Mahmud", "Mamat", "Mirza", "Muhammad", "Murod", "Nazar",
    "Normat", "Nurmat", "Odil", "Olim", "Ostonaqul", "Po‘lat",
    "Qodir", "Qosim", "Rahim", "Rashid", "Rasul", "Ravshan",
    "Sa’dull", "Safar", "Salim", "Sattor", "Sobir", "Sulaymon",
    "Tosh", "To‘lqin", "Turg‘un", "Umar", "Usmon", "Xolmuhammad",
    "Yo‘ldosh", "Yusup", "Zaripboy",
)


def _surname(stem: str, female: bool) -> str:
    """Familiya o'zagiga jinsga mos qo'shimcha qo'shadi."""
    return f"{stem}ova" if female else f"{stem}ov"


def random_full_name(rng: random.Random, *, female: bool | None = None) -> str:
    """Bitta tasodifiy ism-familiya («Familiya Ism» tartibida)."""
    if female is None:
        female = rng.random() < 0.5
    given = rng.choice(FEMALE_NAMES if female else MALE_NAMES)
    family = _surname(rng.choice(SURNAME_STEMS), female)
    return f"{family} {given}"


def _name_key(value: str) -> str:
    """Ismlarni taqqoslash uchun sodda kalit (apostrof va registrga befarq)."""
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()


def unique_names(
    count: int,
    taken: set[str] | None = None,
    *,
    rng: random.Random | None = None,
) -> list[str]:
    """
    `count` ta takrorlanmaydigan ism-familiya qaytaradi.

    `taken` — band nomlar (haqiqiy qatnashchilar va avval yaratilgan
    qatorlar). Taqqoslash registr va apostrofga befarq bajariladi.
    """
    rng = rng or random.Random()
    used = {_name_key(name) for name in (taken or set())}
    result: list[str] = []

    # Kombinatsiyalar soni cheklangan (~4000), shuning uchun urinishlar
    # soni ham cheklanadi — zaxira sifatida otasining ismi qo'shiladi.
    attempts = 0
    limit = max(count * 60, 400)
    while len(result) < count and attempts < limit:
        attempts += 1
        name = random_full_name(rng)
        key = _name_key(name)
        if key in used:
            continue
        used.add(key)
        result.append(name)

    while len(result) < count:
        # Zaxira: «Familiya Ism O.» ko'rinishi — takrorlanish ehtimoli yo'q.
        base = random_full_name(rng)
        initial = rng.choice(MALE_NAMES + FEMALE_NAMES)[0]
        name = f"{base} {initial}."
        key = _name_key(name)
        if key in used:
            continue
        used.add(key)
        result.append(name)

    return result


# --------------------------------------------------------------------------
#  Ballar
# --------------------------------------------------------------------------

#: Haqiqiy natija bo'lmaganda ballar tanlanadigan oraliq (RASH shkalasi).
DEFAULT_BALL_RANGE: tuple[float, float] = (46.0, 72.0)


def blended_balls(
    count: int,
    real_balls: list[float],
    *,
    max_ball: float = C.MAX_BALL,
    rng: random.Random | None = None,
) -> list[float]:
    """
    Haqiqiy natijalar orasiga tabiiy joylashadigan `count` ta ball.

    Ballar haqiqiy natijalarning o'rtachasi va standart og'ishi bo'yicha
    normal taqsimotdan olinadi, so'ng haqiqiy natijalarning eng past va
    eng yuqori qiymatlari orasiga qisiladi. Shu sababli soxta qatorlar
    ro'yxatning o'rtasiga tushadi: birinchi o'rinni ham, oxirgi o'rinni
    ham egallab olmaydi.

    Haqiqiy natija bo'lmasa (yoki bittagina bo'lsa) `DEFAULT_BALL_RANGE`
    oralig'idan tanlanadi.
    """
    rng = rng or random.Random()
    if count <= 0:
        return []

    values = [float(b) for b in real_balls if b is not None]

    if len(values) >= 2:
        low, high = min(values), max(values)
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        spread = variance ** 0.5
        # Tarqoqlik juda kichik bo'lsa ham qatorlar bir-biriga yopishmasin.
        spread = max(spread, max(1.5, (high - low) / 6.0 or 1.5))
    elif len(values) == 1:
        only = values[0]
        low, high = max(0.0, only - 8.0), min(float(max_ball), only + 8.0)
        mean, spread = only, 4.0
    else:
        low, high = DEFAULT_BALL_RANGE
        high = min(high, float(max_ball))
        mean, spread = (low + high) / 2.0, max(1.5, (high - low) / 5.0)

    low = max(0.0, min(low, float(max_ball)))
    high = max(low, min(high, float(max_ball)))

    result: list[float] = []
    for _ in range(count):
        value = rng.gauss(mean, spread)
        value = min(max(value, low), high)
        result.append(round(value, 2))
    result.sort(reverse=True)
    return result


__all__ = [
    "MALE_NAMES",
    "FEMALE_NAMES",
    "SURNAME_STEMS",
    "DEFAULT_BALL_RANGE",
    "random_full_name",
    "unique_names",
    "blended_balls",
]
