#!/usr/bin/env python
"""
Loyihaning o'z-o'zini tekshiruvi (selftest).

Ushbu skript butun tizimni alohida vaqtinchalik ma'lumotlar bazasida
uchdan-uchgacha sinovdan o'tkazadi:

  * yordamchi modullar (konstantalar, matn, matematik ekvivalentlik);
  * Rasch (IRT-1PL) baholash algoritmi;
  * javob kalitlarini tahlil qilish;
  * ID kodlar hayotiy sikli;
  * test yaratish -> javob berish -> hisoblash -> e'lon qilish -> sertifikat;
  * Excel/PDF eksport;
  * sertifikatni QR orqali tekshirish;
  * Django web sahifalarining ochilishi.

Ishga tushirish:

    python selftest.py

Asosiy (ishchi) baza umuman o'zgartirilmaydi.
"""

from __future__ import annotations

import os
import shutil
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# --------------------------------------------------------------------------
#  Alohida sinov bazasi (ishchi bazaga tegilmaydi)
# --------------------------------------------------------------------------
SELFTEST_DIR = BASE_DIR / "data" / "selftest"
SELFTEST_DB = SELFTEST_DIR / "selftest.sqlite3"
SELFTEST_MEDIA = SELFTEST_DIR / "media"

SELFTEST_DIR.mkdir(parents=True, exist_ok=True)
for stale in SELFTEST_DIR.glob("selftest.sqlite3*"):
    stale.unlink(missing_ok=True)
if SELFTEST_MEDIA.exists():
    shutil.rmtree(SELFTEST_MEDIA, ignore_errors=True)
SELFTEST_MEDIA.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = "sqlite:///" + SELFTEST_DB.as_posix()
os.environ["DJANGO_ENV"] = "dev"
os.environ["DJANGO_DEBUG"] = "1"
os.environ.setdefault("BOT_TOKEN", "123456789:selftest-token-placeholder")
os.environ.setdefault("PUBLIC_BASE_URL", "https://example.test")

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402

settings.MEDIA_ROOT = SELFTEST_MEDIA


# ==========================================================================
#  Kichik test-harness
# ==========================================================================


class Runner:
    """Oddiy tekshiruv hisoblagichi."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []
        self.section = ""

    def head(self, title: str) -> None:
        self.section = title
        print(f"\n\033[1m{title}\033[0m")
        print("─" * max(30, len(title)))

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        if condition:
            self.passed += 1
            print(f"  \033[92m✓\033[0m {name}")
        else:
            self.failed += 1
            message = f"[{self.section}] {name}" + (f" — {detail}" if detail else "")
            self.errors.append(message)
            print(f"  \033[91m✗\033[0m {name}" + (f"  ({detail})" if detail else ""))
        return condition

    def equal(self, name: str, actual, expected) -> bool:
        return self.check(name, actual == expected, f"kutilgan {expected!r}, olindi {actual!r}")

    def close(self, name: str, actual: float, expected: float, tolerance: float = 1e-6) -> bool:
        ok = abs(float(actual) - float(expected)) <= tolerance
        return self.check(name, ok, f"kutilgan ≈{expected}, olindi {actual}")

    def raises(self, name: str, func, exception=Exception) -> bool:
        try:
            func()
        except exception:
            return self.check(name, True)
        except Exception as exc:  # noqa: BLE001
            return self.check(name, False, f"boshqa istisno: {exc!r}")
        return self.check(name, False, "istisno chiqmadi")

    def summary(self) -> int:
        total = self.passed + self.failed
        print("\n" + "═" * 60)
        if self.failed == 0:
            print(f"\033[92m✅ BARCHA TEKSHIRUVLAR MUVAFFAQIYATLI: {self.passed}/{total}\033[0m")
        else:
            print(f"\033[91m❌ XATOLAR: {self.failed} / {total}\033[0m\n")
            for error in self.errors:
                print(f"   • {error}")
        print("═" * 60)
        return 0 if self.failed == 0 else 1


R = Runner()


# --------------------------------------------------------------------------
#  Emoji aniqlagich (loyihada emoji ishlatilmasligi kerak)
# --------------------------------------------------------------------------

import re as _re  # noqa: E402

_EMOJI_RE = _re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U0001F1E6-\U0001F1FF"
    "\U0000FE0F"
    "]"
)

#: Loyihada ataylab ishlatiladigan tipografik belgilar (emoji emas).
_ALLOWED_MARKS = "✓✗±·•—–…›‹«»●○■□▰▱°≤≥≠√π∛×÷−⁄"


def _has_emoji(text: str) -> bool:
    """Matnda emoji bor-yo'qligini tekshiradi (tipografik belgilar hisobga olinmaydi)."""
    cleaned = "".join(ch for ch in (text or "") if ch not in _ALLOWED_MARKS)
    return bool(_EMOJI_RE.search(cleaned))


# ==========================================================================
#  1. Konstantalar va daraja jadvali
# ==========================================================================


def test_constants() -> None:
    from core import constants as C

    R.head("1. Konstantalar va daraja jadvali (SRS 8-bo'lim)")

    R.equal("Maksimal ball 90.14", C.MAX_BALL, 90.14)
    R.equal("0 ball -> daraja yo'q", C.grade_for_ball(0), "Daraja olinmadi")
    R.equal("39.9 -> daraja yo'q", C.grade_for_ball(39.9), "Daraja olinmadi")
    R.equal("45.9 -> daraja yo'q", C.grade_for_ball(45.9), "Daraja olinmadi")
    R.equal("46.0 -> C (TZ 8-bo'lim)", C.grade_for_ball(46.0), "C")
    R.equal("49.9 -> C", C.grade_for_ball(49.9), "C")
    R.equal("50.0 -> C+", C.grade_for_ball(50.0), "C+")
    R.equal("55.0 -> B", C.grade_for_ball(55.0), "B")

    # --- Foiz: ball * 100 / 65, 100% dan oshmaydi ---
    R.equal("Foiz asosi 65", C.CERT_PERCENT_BASE, 65.0)
    R.close("46.0 -> 70.77% (C boshi)", C.certificate_percent(46.0), 70.77, 0.01)
    R.close("50.0 -> 76.92%", C.certificate_percent(50.0), 76.92, 0.01)
    R.close("55.0 -> 84.62%", C.certificate_percent(55.0), 84.62, 0.01)
    R.close("60.0 -> 92.31%", C.certificate_percent(60.0), 92.31, 0.01)
    R.close("64.9 -> 99.85%", C.certificate_percent(64.9), 99.85, 0.01)
    R.close("65.0 -> 100% (A boshi)", C.certificate_percent(65.0), 100.0, 0.01)
    R.close("A+ darajaga ham 100%", C.certificate_percent(70.0), 100.0, 0.01)
    R.close("Maksimal ballda ham 100%", C.certificate_percent(C.MAX_BALL), 100.0, 0.01)
    R.equal("Ball yo'q -> 0%", C.certificate_percent(None), 0.0)

    # --- Sertifikat: 0-45.9 ball (darajasiz) uchun berilmaydi ---
    R.equal("Sertifikat eng past darajasi C", C.CERT_MIN_GRADE, "C")
    R.equal("45.9 ball — daraja yo'q", C.grade_for_ball(45.9), C.NO_GRADE)
    R.check("C darajasi chegaradan past emas",
            C.grade_rank("C") >= C.grade_rank(C.CERT_MIN_GRADE))
    R.check("Darajasiz natija chegaradan past",
            C.grade_rank(C.NO_GRADE) < C.grade_rank(C.CERT_MIN_GRADE))
    R.equal("60.0 -> B+", C.grade_for_ball(60.0), "B+")
    R.equal("65.0 -> A", C.grade_for_ball(65.0), "A")
    R.equal("70.0 -> A+", C.grade_for_ball(70.0), "A+")
    R.equal("90.14 -> A+", C.grade_for_ball(90.14), "A+")
    R.check("A+ darajasi C dan kuchli", C.grade_rank("A+") > C.grade_rank("C"))
    R.equal("Milliy shablon 45 ta savol", C.NATIONAL_TOTAL_QUESTIONS, 45)
    R.equal("1–32 bitta javobli", C.NATIONAL_SINGLE_RANGE, (1, 32))
    R.equal("33–35 ko'p javobli", C.NATIONAL_MULTI_RANGE, (33, 35))
    R.equal("36–45 ochiq javobli", C.NATIONAL_OPEN_RANGE, (36, 45))
    R.equal("Ko'p javobli variantlar A–F", C.MULTI_CHOICES, ("A", "B", "C", "D", "E", "F"))


# ==========================================================================
#  2. Matn yordamchilari
# ==========================================================================


def test_text_utils() -> None:
    from core.text_utils import (
        chunk_text,
        clean_full_name,
        esc,
        is_valid_full_name,
        normalize_phone,
        shorten,
        slugify_filename,
    )

    R.head("2. Matn yordamchilari")

    R.equal("Ism-familiya tozalanadi", clean_full_name("  burgutali   ESHQUVVATOV "),
            "Burgutali Eshquvvatov")
    R.check("To'liq ism qabul qilinadi", is_valid_full_name("Burgutali Eshquvvatov"))
    R.check("Bitta so'z rad etiladi", not is_valid_full_name("Burgutali"))
    R.check("Bo'sh matn rad etiladi", not is_valid_full_name("   "))
    R.equal("Telefon +998 bilan", normalize_phone("901234567"), "+998901234567")
    R.equal("Telefon formatlanadi", normalize_phone("+998 (90) 123-45-67"), "+998901234567")
    R.equal("HTML ekranlanadi", esc("<b>&"), "&lt;b&gt;&amp;")
    R.equal("Qisqartirish ishlaydi", shorten("abcdefghij", 5), "abcd…")
    R.check("Uzun matn bo'linadi", len(chunk_text("a\n" * 3000, 4000)) > 1)
    R.check("Fayl nomi xavfsiz", slugify_filename("Milliy sertifikat №7").isascii())


# ==========================================================================
#  3. Ochiq javob normalizatsiyasi (ona tili)
# ==========================================================================


def test_answer_check() -> None:
    from core.answer_check import (
        alternatives,
        compare_answer,
        display_answer,
        fold_answer,
        normalize_answer,
    )

    R.head("3. Ochiq javoblarni tekshirish")

    # --- Normalizatsiya ---
    R.equal("Katta harf pastga tushadi", normalize_answer("EGA"), "ega")
    R.equal("Ortiqcha probel yig'iladi", normalize_answer("  bosh   gap "), "bosh gap")
    R.equal("Nuqta olib tashlanadi", normalize_answer("kesim."), "kesim")
    R.equal("Vergul olib tashlanadi", normalize_answer("kesim,"), "kesim")
    R.equal("Qo'shtirnoq olib tashlanadi", normalize_answer('"ot"'), "ot")
    R.equal(
        "Apostroflar bir xillashadi",
        normalize_answer("o‘zbek tili"),
        normalize_answer("oʻzbek tili"),
    )
    R.equal("Bo'sh qiymat bo'sh qoladi", normalize_answer("   "), "")
    R.equal("None bo'sh qoladi", normalize_answer(None), "")

    # --- Taqqoslash ---
    for given, key, expected in [
        ("ega", "ega", True),
        ("Ega.", "ega", True),
        ("  EGA  ", "ega", True),
        ("o‘zak", "oʻzak", True),
        ("kesim", "ega", False),
        ("egalik", "ega", False),
        ("", "ega", False),
        ("ega", "", False),
    ]:
        R.equal(
            f"Taqqoslash: {given!r} ~ {key!r}",
            bool(compare_answer(given, key)),
            expected,
        )

    # --- Muqobil javoblar ---
    R.equal("Muqobillar ajratiladi", alternatives("ot; ism"), ["ot", "ism"])
    R.equal("Ajratkichsiz kalit bitta muqobil", alternatives("ot"), ["ot"])
    R.check("Birinchi muqobil to'g'ri", bool(compare_answer("ot", "ot; ism")))
    R.check("Ikkinchi muqobil to'g'ri", bool(compare_answer("ISM.", "ot; ism")))
    R.check("Ro'yxatdan tashqarisi rad etiladi",
            not compare_answer("fe’l", "ot; ism"))

    # --- Sinonimlar: «,», «;» va «/» bir xil ajratkich ---
    R.equal(
        "Vergulli sinonimlar ajratiladi",
        alternatives("osmon, samo, fazo"),
        ["osmon", "samo", "fazo"],
    )
    R.equal(
        "«/» bilan yozilgan sinonimlar ajratiladi",
        alternatives("osmon / samo"),
        ["osmon", "samo"],
    )
    R.equal(
        "Aralash ajratkich ham ishlaydi",
        alternatives("osmon; samo, fazo"),
        ["osmon", "samo", "fazo"],
    )
    R.equal(
        "Takrorlangan sinonim bir marta qoladi",
        alternatives("osmon, Osmon., osmon"),
        ["osmon"],
    )
    for given in ("osmon", "Samo.", "  FAZO  ", "fazo"):
        R.check(
            f"Sinonim qabul qilinadi: {given!r}",
            bool(compare_answer(given, "osmon, samo, fazo")),
        )
    R.check(
        "Sinonimlar ro'yxatida yo'q javob rad etiladi",
        not compare_answer("yer", "osmon, samo, fazo"),
    )

    # --- Apostrofning bor-yo'qligi javobni xato qilmaydi ---
    R.equal("Apostrofsiz shakl", fold_answer("oʻrta"), "orta")
    R.equal("Tutuq belgisi ham tushadi", fold_answer("ma’no"), "mano")
    for given in ("O‘rta", "O`rta", "oʻrta", "o’rta", "o'rta", "Orta", "orta", "O‘RTA"):
        R.check(
            f"Apostrofga befarq: {given!r}",
            bool(compare_answer(given, "o‘rta")),
        )
    R.check(
        "Kalit apostrofsiz bo'lsa ham mos keladi",
        bool(compare_answer("o‘rta", "orta")),
    )
    R.check("Boshqa so'z baribir rad etiladi", not compare_answer("orqa", "o‘rta"))
    R.equal(
        "Aynan moslik «text» deb belgilanadi",
        compare_answer("o‘rta", "oʻrta").method,
        "text",
    )
    R.equal(
        "Apostrofsiz moslik alohida belgilanadi",
        compare_answer("orta", "o‘rta").method,
        "apostrophe",
    )

    # --- Ko'rsatish ---
    R.equal("Ko'rsatishda harflar saqlanadi", display_answer(" Bosh  Gap "), "Bosh Gap")

    # --- Matematik ekvivalentlik endi qo'llanmaydi ---
    R.check("«0.5» va «1/2» boshqa javob", not compare_answer("0.5", "1/2"))

    # --- Uzun javob kesiladi, xato bermaydi ---
    R.check("Juda uzun javob rad etiladi", not compare_answer("a" * 5000, "ega"))


# ==========================================================================
#  4. Rasch modeli
# ==========================================================================


def test_rasch() -> None:
    import numpy as np

    from apps.rasch import estimator, scoring
    from core import constants as C

    R.head("4. Rasch (IRT-1PL) modeli (SRS 7-bo'lim)")

    # --- Ehtimollik formulasi ---
    R.close("P(theta=b) = 0.5", float(estimator.probability(0.0, 0.0)), 0.5)
    R.close("P(theta-b=1) ≈ 0.7311", float(estimator.probability(1.0, 0.0)), 0.7310586, 1e-6)
    R.check("P o'sib boradi", float(estimator.probability(2.0, 0.0)) > float(estimator.probability(1.0, 0.0)))
    R.close("Informatsiya maksimumi 0.25", float(estimator.information(0.0, 0.0)), 0.25)

    # --- Sun'iy ma'lumotlar ustida kalibrlash ---
    rng = np.random.default_rng(42)
    n_persons, n_items = 300, 40
    true_theta = rng.normal(0, 1.2, n_persons)
    true_b = np.linspace(-2.0, 2.0, n_items)
    probabilities = estimator.probability(true_theta[:, None], true_b[None, :])
    matrix = (rng.random((n_persons, n_items)) < probabilities).astype(float)

    calibration = estimator.calibrate(matrix)
    R.equal("Kalibrlash qiyinliklar sonini qaytaradi", len(calibration.difficulties), n_items)
    correlation = float(np.corrcoef(calibration.difficulties, true_b)[0, 1])
    R.check(f"Qiyinliklar korrelyatsiyasi > 0.95 ({correlation:.3f})", correlation > 0.95)

    estimates = estimator.estimate_thetas(matrix, calibration.difficulties)
    theta_hat = np.array([e.theta for e in estimates])
    theta_corr = float(np.corrcoef(theta_hat, true_theta)[0, 1])
    R.check(f"theta korrelyatsiyasi > 0.90 ({theta_corr:.3f})", theta_corr > 0.90)

    # --- Ekstremal natijalar ---
    all_correct = estimator.estimate_theta([1] * 10, [0.0] * 10)
    all_wrong = estimator.estimate_theta([0] * 10, [0.0] * 10)
    R.check("To'liq to'g'ri javob ekstremal deb belgilanadi", all_correct.extreme)
    R.check("To'liq to'g'ri theta musbat", all_correct.theta > 0)
    R.check("To'liq xato theta manfiy", all_wrong.theta < 0)
    R.check("theta chegaradan chiqmaydi",
            C.THETA_MIN <= all_wrong.theta <= C.THETA_MAX
            and C.THETA_MIN <= all_correct.theta <= C.THETA_MAX)
    R.check("Ko'proq to'g'ri javob -> kattaroq theta",
            estimator.estimate_theta([1] * 8 + [0] * 2, [0.0] * 10).theta
            > estimator.estimate_theta([1] * 3 + [0] * 7, [0.0] * 10).theta)

    # --- Xom balldan theta (shkalani moslashtirish uchun) ---
    b = [0.0] * 10
    R.close("Xom ball 7 -> naqsh bilan bir xil theta",
            estimator.theta_for_raw_score(7, b),
            estimator.estimate_theta([1] * 7 + [0] * 3, b).theta, 0.01)
    R.check("Xom ball ortsa theta ham ortadi",
            estimator.theta_for_raw_score(8, b) > estimator.theta_for_raw_score(3, b))

    # --- Ball shkalasini «C» darajasiga moslashtirish ---
    from apps.exams.models import Exam as _Exam
    from apps.rasch.services import anchor_theta_min

    R.equal("C darajasi 46 balldan", C.grade_lower_bound("C"), 46.0)
    R.equal("A+ darajasi 70 balldan", C.grade_lower_bound("A+"), 70.0)
    R.check("Tanilmagan daraja chegarasi yo'q", C.grade_lower_bound("Z") is None)

    import numpy as _np

    probe = _Exam(max_ball=C.MAX_BALL, theta_min=C.THETA_MIN, theta_max=C.THETA_MAX)
    diffs = _np.linspace(-2.0, 2.0, 55)
    anchored = anchor_theta_min(probe, diffs)
    R.check("Shkala uchun theta_min hisoblandi", anchored is not None)
    if anchored is not None:
        # 55 birlikdan 32% -> 18 ta. Aynan shu ball 46.00 chiqishi kerak.
        theta18 = estimator.theta_for_raw_score(18, diffs)
        ball18 = scoring.theta_to_ball(
            theta18, max_ball=C.MAX_BALL, theta_min=anchored, theta_max=C.THETA_MAX
        )
        R.close("18 ta to'g'ri javob -> 46.00 ball", ball18, 46.0, 0.02)
        R.equal("18 ta to'g'ri javob -> C", C.grade_for_ball(ball18), "C")

        theta17 = estimator.theta_for_raw_score(17, diffs)
        ball17 = scoring.theta_to_ball(
            theta17, max_ball=C.MAX_BALL, theta_min=anchored, theta_max=C.THETA_MAX
        )
        R.check("17 ta to'g'ri javob -> daraja yo'q",
                C.grade_for_ball(ball17) == C.NO_GRADE, f"{ball17:.2f} ball")
        R.check("Shkalaning yuqori uchi tegilmaydi",
                abs(scoring.theta_to_ball(C.THETA_MAX, max_ball=C.MAX_BALL,
                                          theta_min=anchored, theta_max=C.THETA_MAX)
                    - C.MAX_BALL) < 0.01)

    R.check("Savol yo'q bo'lsa moslash bekor qilinadi",
            anchor_theta_min(probe, _np.asarray([])) is None)

    # --- Ishonchlilik ---
    reliability = estimator.kr20(matrix)
    R.check(f"KR-20 oralig'ida ({reliability:.3f})", 0.0 <= reliability <= 1.0)
    R.check("KR-20 yetarlicha yuqori", reliability > 0.6)

    # --- Ballga o'tkazish ---
    R.close("theta=+4 -> 90.14", scoring.theta_to_ball(4.0), 90.14, 0.01)
    R.close("theta=-4 -> 0", scoring.theta_to_ball(-4.0), 0.0, 0.01)
    R.close("theta=0 -> 45.07", scoring.theta_to_ball(0.0), 45.07, 0.01)
    R.check("Ball monoton o'sadi",
            scoring.theta_to_ball(1.0) < scoring.theta_to_ball(2.0))
    R.check("Ball chegaradan oshmaydi", scoring.theta_to_ball(99.0) <= C.MAX_BALL)
    R.equal("A+ chegarasi", scoring.grade_for(70.0), "A+")

    R.close("theta=+2.2125 -> 70.00 (A+ chegarasi)", scoring.theta_to_ball(2.2125), 70.0, 0.02)
    R.close("theta=+0.0826 -> 46.00 (C chegarasi)", scoring.theta_to_ball(0.0826), 46.0, 0.02)
    R.equal("C chegarasi 46 balldan (TZ)", scoring.grade_for(46.0), "C")
    R.equal("45.99 ball — daraja yo'q", scoring.grade_for(45.99), C.NO_GRADE)

    result = scoring.build_score(2.25, 40, 55)
    R.check(f"theta=2.25 -> A+ ({result.ball})", result.grade == "A+")
    R.equal("theta=2.0 -> A", scoring.build_score(2.0, 40, 55).grade, "A")
    R.close("Foiz to'g'ri hisoblanadi", result.percent, round(40 / 55 * 100, 2), 0.01)


# ==========================================================================
#  5. Javob kalitlarini tahlil qilish
# ==========================================================================


def test_keys() -> None:
    from apps.exams import keys

    R.head("5. Javob kalitlarini tahlil qilish")

    result = keys.parse_single_key("ABCDABCDAB", 10)
    R.check("Ketma-ket kalit o'qiladi", result.ok)
    R.equal("Kalit uzunligi", len(result.keys), 10)
    R.equal("Birinchi javob", result.keys[0], "A")

    result = keys.parse_single_key("A B C D", 4)
    R.check("Probelli kalit o'qiladi", result.ok)

    result = keys.parse_single_key("1-A 2-B 3-C", 3)
    R.check("Raqamlangan kalit o'qiladi", result.ok)
    R.equal("Raqamlangan kalit qiymati", result.keys, ["A", "B", "C"])

    result = keys.parse_single_key("ABC", 5)
    R.check("Kam javob xato beradi", not result.ok)

    result = keys.parse_single_key("ABZ", 3)
    R.check("Noto'g'ri variant aniqlanadi", not result.ok)

    result = keys.parse_multi_key("A, C, E", 3)
    R.check("Moslashtirish kaliti o'qiladi", result.ok)
    R.equal("Moslashtirish javoblari", result.keys, ["A", "C", "E"])

    result = keys.parse_multi_key("ACE", 3)
    R.check("Ajratkichsiz kalit ham o'qiladi", result.ok)
    R.equal("Ajratkichsiz kalit qiymati", result.keys, ["A", "C", "E"])

    result = keys.parse_multi_key("AB, C, D", 3)
    R.check("33–35 da bir nechta harf xato beradi", not result.ok)

    result = keys.parse_multi_key("A C", 3)
    R.check("Javob soni mos kelmasa xato", not result.ok)

    result = keys.parse_open_key("ot | fe’l\nega | kesim", 2)
    R.check("Ochiq kalit o'qiladi", result.ok)
    R.equal("Ochiq kalit ajratiladi", keys.split_open_key(result.keys[0]), ("ot", "fe’l"))
    R.equal("Ikkinchi qator", keys.split_open_key(result.keys[1]), ("ega", "kesim"))

    result = keys.parse_open_key("ot | fe’l", 3)
    R.check("Qator soni mos kelmasa xato", not result.ok)

    # Muqobil javoblar «;» bilan beriladi va bir bo'lak bo'lib qoladi.
    result = keys.parse_open_key("ot; ism | fe’l\nsifat | son; miqdor", 2)
    R.check("Muqobil javobli kalit o'qiladi", result.ok)
    R.equal("Muqobillar a) qismida qoladi",
            keys.split_open_key(result.keys[0]), ("ot; ism", "fe’l"))
    R.equal("Muqobillar b) qismida qoladi",
            keys.split_open_key(result.keys[1]), ("sifat", "son; miqdor"))

    result = keys.parse_open_key("36) ot | fe’l\n37. ega | kesim", 2)
    R.check("Raqamlangan ochiq kalit o'qiladi", result.ok)
    R.equal("Savol raqami olib tashlanadi",
            keys.split_open_key(result.keys[0]), ("ot", "fe’l"))
    R.equal("Nuqtali raqam ham olib tashlanadi",
            keys.split_open_key(result.keys[1]), ("ega", "kesim"))

    R.check("Kalit ko'rinishi shakllanadi", "1-A" in keys.format_key_preview(["A", "B"]))


# ==========================================================================
#  6. ID kodlar generatori
# ==========================================================================


def test_code_generator() -> None:
    from apps.accesscodes.generator import (
        generate_unique_codes,
        is_valid_format,
        make_code,
        normalize_code,
    )

    R.head("6. ID kodlar generatori (TZ: R7K4-8251 formati)")

    code = make_code()
    R.equal("Kod uzunligi 9", len(code), 9)
    R.equal("5-belgi chiziqcha", code[4], "-")
    R.check("Format to'g'ri", is_valid_format(code))
    R.check("Namuna kod to'g'ri formatda", is_valid_format("R7K4-8251"))
    R.check("Noto'g'ri format aniqlanadi", not is_valid_format("ABCD-EFGH"))
    R.equal("Kod normallashadi", normalize_code("r7k4 8251"), "R7K4-8251")
    R.equal("Chiziqchasiz kod normallashadi", normalize_code("R7K48251"), "R7K4-8251")

    codes = generate_unique_codes(2000)
    R.equal("2000 ta kod yaratildi", len(codes), 2000)
    R.equal("Barchasi noyob", len(set(codes)), 2000)
    R.check("Barchasi to'g'ri formatda", all(is_valid_format(c) for c in codes))
    R.check("I va O harflari ishlatilmaydi",
            all("I" not in c[:4] and "O" not in c[:4] for c in codes))


# ==========================================================================
#  7. Baza: migratsiyalar
# ==========================================================================


def test_migrations() -> None:
    from django.core.management import call_command

    R.head("7. Ma'lumotlar bazasi va migratsiyalar")

    try:
        call_command("migrate", verbosity=0, interactive=False)
        R.check("Migratsiyalar qo'llandi", True)
    except Exception as exc:  # noqa: BLE001
        R.check("Migratsiyalar qo'llandi", False, str(exc))
        raise

    try:
        call_command("makemigrations", "--check", "--dry-run", verbosity=0)
        R.check("Yetishmayotgan migratsiya yo'q", True)
    except SystemExit:
        R.check("Yetishmayotgan migratsiya yo'q", False, "makemigrations kerak")
    except Exception as exc:  # noqa: BLE001
        R.check("Yetishmayotgan migratsiya yo'q", False, str(exc))


# ==========================================================================
#  8. To'liq oqim: bepul RASH testi
# ==========================================================================


def test_rasch_free_flow() -> dict:
    import numpy as np

    from apps.attempts.models import Attempt
    from apps.attempts.services import (
        can_participate,
        save_answer,
        start_attempt,
        submit_attempt,
    )
    from apps.exams.models import Exam, Question
    from apps.exams.services import activate_exam, apply_multi_keys, apply_open_keys, apply_single_keys, create_exam, keys_ready, publish_results
    from apps.rasch import scoring
    from apps.rasch.services import calculate_exam
    from apps.users.models import BotUser
    from core import constants as C
    from core.answer_check import alternatives

    def correct_text(key: str) -> str:
        """Kalitdagi birinchi sinonim — «to'g'ri javob» sifatida yoziladi."""
        options = alternatives(key)
        return options[0] if options else ""

    R.head("8. To'liq oqim: milliy shablon (45 savol) + RASH")

    owner, _ = BotUser.objects.get_or_create(
        telegram_id=1000, defaults={"full_name": "Test Yaratuvchi", "is_registered": True}
    )

    exam = create_exam(
        owner=owner,
        title="MILLIY SERTIFIKAT MOCK №7",
        exam_type=Exam.Type.RASCH_FREE,
        national_template=True,
        show_results=True,
    )
    R.equal("45 ta savol yaratildi", exam.question_count, 45)
    R.equal("Bitta javobli savollar", exam.questions.filter(kind="single").count(), 32)
    R.equal("Ko'p javobli savollar", exam.questions.filter(kind="multi").count(), 3)
    R.equal("Ochiq savollar", exam.questions.filter(kind="open").count(), 10)
    # 36–39 bitta javobdan, 40–45 esa a) va b) dan iborat.
    R.equal(
        "36–39 bitta javobli",
        list(
            exam.questions.filter(kind="open", order__lte=39)
            .order_by("order")
            .values_list("parts", flat=True)
        ),
        [1, 1, 1, 1],
    )
    R.equal(
        "40–45 ikkita javobli",
        list(
            exam.questions.filter(kind="open", order__gte=40)
            .order_by("order")
            .values_list("parts", flat=True)
        ),
        [2, 2, 2, 2, 2, 2],
    )
    R.equal("Maksimal xom ball 51", exam.max_raw_score, float(C.NATIONAL_MAX_RAW_SCORE))
    # Kod ishtirokchi uchun qulay bo'lishi kerak — oddiy 2–3 xonali son.
    R.check(
        f"Test kodi oddiy son ({exam.code})",
        bool(exam.code) and exam.code.isdigit() and len(exam.code) <= 3,
    )

    # --- Javob kalitlari ---
    single_keys = ["ABCD"[i % 4] for i in range(32)]
    apply_single_keys(exam, single_keys)
    apply_multi_keys(exam, ["A", "C", "E"])
    # 36–39 — bitta javobdan, 40–45 — a) va b) dan.
    # 45-savol kaliti ataylab sinonimlar bilan yozilgan — qatnashchi
    # «o‘zak» ham, «negiz» ham yozsa to'g'ri hisoblanishi kerak.
    open_keys = [
        "ot", "ega", "sifat", "olmosh",
        "bosh kelishik||qaratqich kelishik", "undosh||unli",
        "sodda gap||qo‘shma gap", "ko‘chma ma’no||o‘z ma’nosi",
        "sinonim||antonim", "o‘zak, negiz||qo‘shimcha, affiks",
    ]
    apply_open_keys(exam, open_keys)

    R.check("Barcha kalitlar kiritildi", keys_ready(exam))

    ok, message = activate_exam(exam)
    R.check(f"Test faollashtirildi ({message})", ok)
    exam.refresh_from_db()
    R.equal("Holat = faol", exam.status, Exam.Status.ACTIVE)

    # --- 40 ta ishtirokchi ---
    questions = list(exam.questions.order_by("order"))
    rng = np.random.default_rng(7)
    participants = 40
    abilities = np.linspace(-1.5, 2.5, participants)

    for index in range(participants):
        user, _ = BotUser.objects.get_or_create(
            telegram_id=2000 + index,
            defaults={
                "full_name": f"Ishtirokchi {index + 1}",
                "phone": f"+99890000{index:04d}",
                "is_registered": True,
            },
        )
        check = can_participate(user, exam)
        if index == 0:
            R.check("Ishtirok etish mumkin", check.ok, check.message)

        attempt = start_attempt(user, exam)
        theta = abilities[index]

        for question in questions:
            success = float(1.0 / (1.0 + np.exp(-(theta - question.difficulty))))
            if question.kind == Question.Kind.SINGLE:
                value = question.correct_key if rng.random() < success else "A" if question.correct_key != "A" else "B"
                save_answer(attempt, question, selected=value)
            elif question.kind == Question.Kind.MULTI:
                value = question.correct_key if rng.random() < success else "A" if question.correct_key != "A" else "B"
                save_answer(attempt, question, selected=value)
            else:
                good_a = rng.random() < success
                good_b = rng.random() < success
                save_answer(
                    attempt,
                    question,
                    text_a=correct_text(question.answer_a) if good_a else "noto‘g‘ri javob",
                    text_b=correct_text(question.answer_b) if good_b else "boshqa javob",
                )
        submit_attempt(attempt)

    submitted = Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED).count()
    R.equal(f"{participants} ta javob yuborildi", submitted, participants)

    # --- Ikkinchi marta yuborish taqiqlangan ---
    repeat_user = BotUser.objects.get(telegram_id=2000)
    repeat_check = can_participate(repeat_user, exam)
    R.check("Takroriy qatnashish taqiqlanadi", not repeat_check.ok)

    # --- Hisoblash ---
    report = calculate_exam(exam)
    R.equal("Hisoblangan qatnashchilar", report.participants, participants)
    R.check("Kalibrlash bajarildi", report.calibrated)
    R.check(f"Ishonchlilik oralig'ida ({report.reliability:.3f})",
            0.0 <= report.reliability <= 1.0)

    attempts = list(Attempt.objects.filter(exam=exam, status="submitted").ranked())
    R.check("Barcha urinishlar baholandi", all(a.is_scored for a in attempts))
    R.check("Ballar oralig'ida", all(0 <= (a.ball or 0) <= exam.max_ball for a in attempts))
    R.check("Reyting o'rinlari berildi", all(a.rank for a in attempts))
    R.equal("Birinchi o'rin = 1", attempts[0].rank, 1)
    R.check("Reyting ball bo'yicha kamayadi",
            all(attempts[i].ball >= attempts[i + 1].ball for i in range(len(attempts) - 1)))
    R.check("Yuqori qobiliyat -> yuqori ball",
            attempts[0].raw_score >= attempts[-1].raw_score)
    R.check("Darajalar belgilandi", all(a.grade for a in attempts))

    # --- Shkala «C» darajasiga moslashgan: 32% (51 dan 17 ta) -> 46.00 ball ---
    exam.refresh_from_db()
    R.check("Shkala moslashtirildi", exam.theta_min < C.THETA_MIN,
            f"theta_min = {exam.theta_min}")

    from apps.rasch import estimator as _est
    from apps.rasch.services import build_items as _items

    diffs = [i.difficulty for i in _items(exam)]
    R.equal("51 ta ballanadigan birlik", len(diffs), C.NATIONAL_MAX_RAW_SCORE)
    ball17 = scoring.theta_to_ball(
        _est.theta_for_raw_score(17, diffs),
        max_ball=exam.max_ball, theta_min=exam.theta_min, theta_max=exam.theta_max,
    )
    ball16 = scoring.theta_to_ball(
        _est.theta_for_raw_score(16, diffs),
        max_ball=exam.max_ball, theta_min=exam.theta_min, theta_max=exam.theta_max,
    )
    R.close("17 ta to'g'ri javob -> 46.00 ball", ball17, 46.0, 0.05)
    R.equal("17 ta to'g'ri javob -> C darajasi", C.grade_for_ball(ball17), "C")
    R.check("16 ta to'g'ri javob -> daraja yo'q",
            C.grade_for_ball(ball16) == C.NO_GRADE, f"{ball16:.2f} ball")

    # --- Baholash aniqligi: to'liq to'g'ri javob bergan ishtirokchi ---
    perfect_user, _ = BotUser.objects.get_or_create(
        telegram_id=9999, defaults={"full_name": "Mukammal Ishtirokchi", "is_registered": True}
    )
    perfect = start_attempt(perfect_user, exam)
    for question in questions:
        if question.kind == Question.Kind.OPEN:
            save_answer(
                perfect,
                question,
                text_a=correct_text(question.answer_a),
                text_b=correct_text(question.answer_b),
            )
        else:
            save_answer(perfect, question, selected=question.correct_key)
    submit_attempt(perfect)
    perfect.refresh_from_db()
    R.equal(
        "To'liq to'g'ri javob = 51 ball",
        perfect.raw_score,
        float(C.NATIONAL_MAX_RAW_SCORE),
    )
    R.close("Foiz = 100", perfect.percent, 100.0, 0.01)

    # --- Matn normalizatsiyasi amalda ---
    # 37-savol (bitta javobli) kaliti «ega», 41-savol (a va b) kaliti
    # «undosh | unli». Katta-kichik harf, ortiqcha probel va tinish
    # belgilari e'tiborga olinmasligi kerak.
    equiv_user, _ = BotUser.objects.get_or_create(
        telegram_id=9998, defaults={"full_name": "Ekvivalent Ishtirokchi", "is_registered": True}
    )
    equiv = start_attempt(equiv_user, exam)
    single_open = exam.questions.filter(kind="open", order=37).first()
    double_open = exam.questions.filter(kind="open", order=41).first()
    save_answer(equiv, single_open, text_a="  EGA. ")
    save_answer(equiv, double_open, text_a="Undosh.", text_b="  unli,")
    submit_attempt(equiv)

    single_answer = equiv.answers.get(question=single_open)
    double_answer = equiv.answers.get(question=double_open)
    R.check("«EGA.» = «ega» deb qabul qilindi", single_answer.is_correct_a is True)
    R.check("Bitta javobli savolda b) baholanmaydi",
            single_answer.is_correct_b is None)
    R.equal("Bitta javobli savol = 1 ball", single_answer.score, 1.0)
    R.check("«Undosh.» = «undosh» deb qabul qilindi", double_answer.is_correct_a is True)
    R.check("«  unli,» = «unli» deb qabul qilindi", double_answer.is_correct_b is True)
    R.equal("a) va b) li savol = 2 ball", double_answer.score, 2.0)

    # --- Sinonim va apostrofsiz javob amalda ---
    # 45-savol kaliti: a) «o‘zak, negiz», b) «qo‘shimcha, affiks».
    # Qatnashchi ikkinchi sinonimni yozsa ham, apostrofni tushirib
    # qoldirsa ham javob to'g'ri hisoblanishi kerak.
    synonym_user, _ = BotUser.objects.get_or_create(
        telegram_id=9997, defaults={"full_name": "Sinonim Ishtirokchi", "is_registered": True}
    )
    synonym = start_attempt(synonym_user, exam)
    synonym_question = exam.questions.filter(kind="open", order=45).first()
    save_answer(synonym, synonym_question, text_a="Negiz", text_b="affiks")
    submit_attempt(synonym)
    synonym_answer = synonym.answers.get(question=synonym_question)
    R.check("«Negiz» sinonimi qabul qilindi", synonym_answer.is_correct_a is True)
    R.check("«affiks» sinonimi qabul qilindi", synonym_answer.is_correct_b is True)

    loose_user, _ = BotUser.objects.get_or_create(
        telegram_id=9996, defaults={"full_name": "Apostrofsiz Ishtirokchi", "is_registered": True}
    )
    loose = start_attempt(loose_user, exam)
    save_answer(loose, synonym_question, text_a="ozak", text_b="qoshimcha")
    submit_attempt(loose)
    loose_answer = loose.answers.get(question=synonym_question)
    R.check("«ozak» = «o‘zak» deb qabul qilindi", loose_answer.is_correct_a is True)
    R.check("«qoshimcha» = «qo‘shimcha» deb qabul qilindi",
            loose_answer.is_correct_b is True)

    # --- Statistika ---
    calculate_exam(exam)
    exam.refresh_from_db()
    statistics = exam.statistics
    R.check("Statistika yaratildi", statistics.participants > 0)
    R.check("Darajalar taqsimoti to'ldirildi", bool(statistics.grade_distribution))
    R.check(
        "Savollar statistikasi to'ldirildi",
        len(statistics.item_statistics) == C.NATIONAL_MAX_RAW_SCORE,
    )

    # --- Natijalarni e'lon qilish ---
    ok, message = publish_results(exam)
    R.check(f"Natijalar e'lon qilindi ({message})", ok)
    exam.refresh_from_db()
    R.equal("Holat = e'lon qilingan", exam.status, Exam.Status.PUBLISHED)

    return {"exam": exam, "owner": owner}


# ==========================================================================
#  9. Oddiy test (1-tur)
# ==========================================================================


def test_simple_flow() -> None:
    from apps.attempts.models import Attempt
    from apps.attempts.services import answer_review, save_answer, start_attempt, submit_attempt
    from apps.exams.models import Exam
    from apps.exams.services import activate_exam, apply_single_keys, create_exam
    from apps.users.models import BotUser

    R.head("9. Oddiy test (1-tur) — RASH ishlatilmaydi")

    owner = BotUser.objects.get(telegram_id=1000)
    exam = create_exam(
        owner=owner,
        title="Algebra — 20 savol",
        exam_type=Exam.Type.SIMPLE,
        question_count=20,
        show_results=True,
    )
    R.equal("20 ta savol yaratildi", exam.question_count, 20)
    R.check("Rasch ishlatilmaydi", not exam.uses_rasch)
    R.check("ID kod talab qilinmaydi", not exam.requires_access_code)
    R.check("Sertifikat berilmaydi", not exam.can_issue_certificate)

    apply_single_keys(exam, ["ABCD"[i % 4] for i in range(20)])
    ok, _ = activate_exam(exam)
    R.check("Oddiy test faollashtirildi", ok)

    questions = list(exam.questions.order_by("order"))
    user, _ = BotUser.objects.get_or_create(
        telegram_id=3001, defaults={"full_name": "Oddiy Ishtirokchi", "is_registered": True}
    )
    attempt = start_attempt(user, exam)
    for index, question in enumerate(questions):
        if index < 15:
            save_answer(attempt, question, selected=question.correct_key)
        elif index < 18:
            wrong = "A" if question.correct_key != "A" else "B"
            save_answer(attempt, question, selected=wrong)
        # oxirgi 2 tasi javobsiz qoladi

    submit_attempt(attempt)
    attempt.refresh_from_db()

    R.equal("15 ta to'g'ri javob", attempt.raw_score, 15.0)
    R.equal("3 ta xato javob", attempt.wrong_count, 3)
    R.equal("2 ta javobsiz", attempt.empty_count, 2)
    R.close("Foiz 75%", attempt.percent, 75.0, 0.01)
    R.check("Rasch theta hisoblanmadi", attempt.theta is None)

    review = answer_review(attempt)
    R.equal("Ko'rib chiqishda 20 ta qator", len(review), 20)
    R.equal("Birinchi javob to'g'ri", review[0]["icon"], "✓")
    R.equal("16-javob xato", review[15]["icon"], "✗")
    R.equal("19-javob bo'sh", review[18]["icon"], "·")

    from apps.rasch.services import calculate_exam

    calculate_exam(exam)
    attempt.refresh_from_db()
    R.equal("Reyting o'rni berildi", attempt.rank, 1)
    R.check("Oddiy testda daraja yo'q", attempt.grade == "")
    R.equal("Yuborilgan urinishlar", Attempt.objects.filter(exam=exam, status="submitted").count(), 1)


# ==========================================================================
#  10. Pullik RASH testi + ID kodlar + sertifikat
# ==========================================================================


def test_paid_flow() -> None:
    from apps.accesscodes.models import AccessCode
    from apps.accesscodes.services import (
        activate_code,
        check_code,
        code_statistics,
        create_codes,
        find_active_code,
    )
    from apps.attempts.services import save_answer, start_attempt, submit_attempt
    from apps.certificates.models import Certificate
    from apps.certificates.services import check_eligibility, issue_certificate, issue_for_exam, verify
    from apps.exams.models import Exam
    from apps.exams.services import activate_exam, apply_single_keys, create_exam, publish_results
    from apps.rasch.services import calculate_exam
    from apps.users.models import BotUser
    from core import constants as C

    R.head("10. Pullik RASH testi: ID kodlar va sertifikat")

    owner = BotUser.objects.get(telegram_id=1000)
    exam = create_exam(
        owner=owner,
        title="MILLIY SERTIFIKAT MOCK №8 (pullik)",
        exam_type=Exam.Type.RASCH_PAID,
        question_count=30,
        certificate_enabled=True,
        organizer_name="Burgutali Eshquvvatov",
    )
    apply_single_keys(exam, ["ABCD"[i % 4] for i in range(30)])

    R.check("ID kod talab qilinadi", exam.requires_access_code)
    R.check("Sertifikat yoqilgan", exam.can_issue_certificate)

    ok, message = activate_exam(exam)
    R.check("Kodsiz faollashmaydi", not ok, message)

    # --- ID kodlar yaratish ---
    batch = create_codes(exam, 500, created_by=owner)
    R.equal("500 ta kod yaratildi", batch.quantity, 500)
    R.equal("Bazada 500 ta kod", AccessCode.objects.filter(exam=exam).count(), 500)
    stats = code_statistics(exam)
    R.equal("Barchasi ishlatilmagan", stats["unused"], 500)

    ok, _ = activate_exam(exam)
    R.check("Kodlar bilan faollashtirildi", ok)
    exam.refresh_from_db()

    codes = list(AccessCode.objects.filter(exam=exam).order_by("id")[:5])

    # --- Kodni tekshirish ---
    result = check_code(codes[0].code, exam)
    R.check("To'g'ri kod qabul qilinadi", result.ok)
    R.check("Noto'g'ri format rad etiladi", not check_code("XXXX", exam).ok)
    R.check("Mavjud bo'lmagan kod rad etiladi", not check_code("Z9Z9-0000", exam).ok)

    # --- Kod hayotiy sikli ---
    user, _ = BotUser.objects.get_or_create(
        telegram_id=4001,
        defaults={"full_name": "Pullik Ishtirokchi", "phone": "+998901112233", "is_registered": True},
    )
    code = codes[0]
    activate_code(code, user, user.full_name)
    code.refresh_from_db()
    R.equal("Kod faollashtirildi", code.status, AccessCode.Status.ACTIVATED)
    R.check("Kod hali ishlatilmagan", code.is_available)
    R.equal("Telegram ID saqlandi", code.telegram_id, 4001)

    active = find_active_code(user, exam)
    R.check("Faol kod topildi", active is not None and active.id == code.id)

    attempt = start_attempt(user, exam)
    questions = list(exam.questions.order_by("order"))
    for index, question in enumerate(questions):
        if index < 26:
            save_answer(attempt, question, selected=question.correct_key)
        else:
            save_answer(attempt, question, selected="A" if question.correct_key != "A" else "B")
    submit_attempt(attempt)

    code.refresh_from_db()
    R.equal("Javobdan keyin kod ishlatilgan", code.status, AccessCode.Status.USED)
    R.check("Kod urinishga bog'landi", code.attempt_id == attempt.id)
    R.check("Ishlatilgan vaqt saqlandi", code.used_at is not None)

    reuse = check_code(code.code, exam)
    R.check("Ishlatilgan kod qayta ishlamaydi", not reuse.ok)
    R.check("Xabar tushunarli", "avval yuborilgan" in reuse.message)

    # --- Boshqa testga tegishli kod ---
    other_exam = create_exam(
        owner=owner, title="Boshqa pullik test", exam_type=Exam.Type.RASCH_PAID, question_count=5
    )
    cross = check_code(codes[1].code, other_exam)
    R.check("Boshqa testning kodi rad etiladi", not cross.ok)

    # --- Yana ishtirokchilar ---
    for index in range(1, 12):
        participant, _ = BotUser.objects.get_or_create(
            telegram_id=4100 + index,
            defaults={"full_name": f"Pullik {index}", "is_registered": True},
        )
        participant_code = codes[1] if index == 1 else AccessCode.objects.filter(
            exam=exam, status=AccessCode.Status.UNUSED
        ).first()
        activate_code(participant_code, participant, participant.full_name)
        participant_attempt = start_attempt(participant, exam)
        correct_count = max(5, 26 - index)
        for position, question in enumerate(questions):
            if position < correct_count:
                save_answer(participant_attempt, question, selected=question.correct_key)
            else:
                save_answer(
                    participant_attempt, question,
                    selected="A" if question.correct_key != "A" else "B",
                )
        submit_attempt(participant_attempt)

    # --- Sertifikat: e'lon qilinmagan bo'lsa berilmaydi ---
    eligibility = check_eligibility(attempt)
    R.check("E'lon qilinmagan natijaga sertifikat yo'q", not eligibility.ok)

    report = calculate_exam(exam)
    R.equal("Pullik testda qatnashchilar", report.participants, 12)

    exam.refresh_from_db()
    attempt.refresh_from_db()
    R.check("Ball hisoblandi", attempt.ball is not None and attempt.ball > 0)
    R.check("Daraja belgilandi", bool(attempt.grade))

    ok, _ = publish_results(exam)
    R.check("Natijalar e'lon qilindi", ok)
    exam.refresh_from_db()

    eligibility = check_eligibility(attempt)
    R.check("E'londan keyin sertifikat mumkin", eligibility.ok, eligibility.reason)

    certificate, message = issue_certificate(attempt)
    R.check("Sertifikat yaratildi", certificate is not None, message)
    R.check("Sertifikat raqami noyob", certificate.number.startswith("RM-"))
    R.check("PDF fayl biriktirildi", bool(certificate.file))
    R.check("PDF hajmi ma'noli", certificate.file.size > 1000)
    R.check("QR havolasi shakllandi", certificate.verify_url.startswith("http"))
    R.check("Tekshiruv tokeni bor", len(certificate.verify_token) > 10)
    R.equal("Sertifikatdagi ism", certificate.full_name, "Pullik Ishtirokchi")
    R.check("Sertifikatda ball bor", certificate.ball == attempt.ball)

    # --- Takroriy berish yangi raqam yaratmaydi ---
    second, _ = issue_certificate(attempt)
    R.equal("Sertifikat raqami o'zgarmaydi", second.number, certificate.number)
    R.equal("Bitta urinish -> bitta sertifikat",
            Certificate.objects.filter(attempt=attempt).count(), 1)

    # --- Tekshiruv ---
    found = verify(certificate.number, certificate.verify_token)
    R.check("Sertifikat raqam bo'yicha topiladi", found is not None)
    R.check("Noto'g'ri token rad etiladi", verify(certificate.number, "yolgon") is None)
    R.check("Mavjud bo'lmagan raqam topilmaydi", verify("RM-1900-000001") is None)

    # --- Ommaviy berish ---
    bulk = issue_for_exam(exam)
    R.check("Ommaviy sertifikat berildi", bulk["created"] >= 1)
    R.check("Sertifikatlar soni ortdi", Certificate.objects.filter(exam=exam).count() >= 1)

    # --- Minimal ball sharti ---
    exam.certificate_scope = Exam.CertificateScope.MIN_BALL
    exam.certificate_min_ball = 999.0
    exam.save(update_fields=["certificate_scope", "certificate_min_ball"])
    strict = check_eligibility(attempt)
    R.check("Minimal ball sharti ishlaydi", not strict.ok)
    exam.certificate_scope = Exam.CertificateScope.ALL
    exam.certificate_min_ball = None
    exam.save(update_fields=["certificate_scope", "certificate_min_ball"])

    # --- Minimal foiz sharti (standart) ---
    fresh = create_exam(
        owner=owner,
        title="Foiz sharti uchun namuna",
        exam_type=Exam.Type.RASCH_PAID,
        question_count=10,
        certificate_enabled=True,
    )
    R.equal("Yangi testda standart shart — daraja",
            fresh.certificate_scope, Exam.CertificateScope.MIN_GRADE)
    R.equal("Standart daraja C", fresh.certificate_min_grade, "C")

    exam.certificate_scope = Exam.CertificateScope.MIN_GRADE
    exam.certificate_min_grade = C.CERT_MIN_GRADE
    exam.save(update_fields=["certificate_scope", "certificate_min_grade"])

    saved_ball, saved_grade = attempt.ball, attempt.grade

    def _set(ball):
        attempt.ball = ball
        attempt.grade = C.grade_for_ball(ball)
        attempt.save(update_fields=["ball", "grade"])
        return check_eligibility(attempt)

    low = _set(45.9)
    R.check("45.9 ball — sertifikat yo'q", not low.ok, low.reason)
    R.check("Sabab chegarani oshkor qilmaydi",
            "C" not in low.reason.replace("Natijangiz", "") and "46" not in low.reason,
            low.reason)
    R.check("0 ball — sertifikat yo'q", not _set(0.0).ok)
    R.check("46.0 ball (C) — sertifikat bor", _set(46.0).ok)
    R.check("50.0 ball (C+) — sertifikat bor", _set(50.0).ok)
    R.check("90.14 ball (A+) — sertifikat bor", _set(C.MAX_BALL).ok)

    # Daraja bo'sh qoldirilsa shart qo'llanmaydi.
    exam.certificate_min_grade = ""
    exam.save(update_fields=["certificate_min_grade"])
    R.check("Daraja bo'sh — shart qo'llanmaydi", _set(10.0).ok)

    attempt.ball, attempt.grade = saved_ball, saved_grade
    attempt.save(update_fields=["ball", "grade"])
    exam.certificate_scope = Exam.CertificateScope.ALL
    exam.certificate_min_grade = C.CERT_MIN_GRADE
    exam.save(update_fields=["certificate_scope", "certificate_min_grade"])

    # --- Hisobotdagi daraja yorlig'i ---
    from apps.exports.pdf_report import grade_label

    R.equal("Daraja olinmagan qator qisqartiriladi",
            grade_label(C.NO_GRADE), "—")
    R.equal("Bo'sh daraja ham qisqartiriladi", grade_label(""), "—")
    R.equal("Oddiy daraja o'zgarmaydi", grade_label("B+"), "B+")


# ==========================================================================
#  11. Eksport (Excel / PDF)
# ==========================================================================


def test_exports() -> None:
    from apps.accesscodes.models import CodeBatch
    from apps.exams.models import Exam
    from apps.exports.excel import codes_workbook, participants_workbook, results_workbook
    from apps.exports.pdf_report import certificate_list_report, results_report
    from core import constants as C

    R.head("11. Eksport: Excel va PDF")

    exam = Exam.objects.filter(exam_type=Exam.Type.RASCH_FREE).first()
    paid = Exam.objects.filter(exam_type=Exam.Type.RASCH_PAID).first()
    batch = CodeBatch.objects.first()

    results = results_workbook(exam)
    R.check("Natijalar Excel yaratildi", len(results) > 5000)
    R.check("Excel formati (ZIP sarlavhasi)", results[:2] == b"PK")

    participants = participants_workbook(exam)
    R.check("Ishtirokchilar Excel yaratildi", len(participants) > 3000)

    codes = codes_workbook(batch)
    R.check("ID kodlar Excel yaratildi", len(codes) > 5000)

    report = results_report(exam)
    R.check("Natijalar PDF yaratildi", len(report) > 3000)
    R.check("PDF formati", report[:4] == b"%PDF")

    certificates = certificate_list_report(paid)
    R.check("Sertifikatlar PDF yaratildi", certificates[:4] == b"%PDF")

    # --- E'lon qilinadigan jadval: ball, foiz, daraja (to'g'ri javob yo'q) ---
    from apps.exports.pdf_report import overall_results_report, results_report as full_report

    announce = overall_results_report(exam)
    R.check("Umumiy natijalar PDF yaratildi", announce[:4] == b"%PDF")

    from apps.attempts.services import ranked_attempts as _ranked

    # --- Belgi (favicon): logda 404 qolmasin ---
    from django.test import Client as _Client

    client = _Client()
    R.check("Belgi fayli bor", (BASE_DIR / "static/favicon.svg").is_file())
    fav = client.get("/favicon.ico")
    R.check("favicon.ico yo'naltiriladi", fav.status_code in (301, 302),
            str(fav.status_code))
    for name, url in (("bosh sahifa", "/"), ("panel", "/panel/kirish/")):
        page = client.get(url).content.decode("utf-8", "replace")
        R.check(f"Belgi ulangan: {name}", "favicon.svg" in page)

    # --- Kartalar sarlavhasi chapda turadi ---
    dash_css_head = (
        BASE_DIR / "apps/dashboard/static/dashboard/css/dashboard.css"
    ).read_text(encoding="utf-8")
    head_rule = dash_css_head.split(".card-head {", 1)[1].split("}", 1)[0]
    R.check("Sarlavha o'ng chetga uchmaydi",
            "space-between" not in head_rule, head_rule.strip())
    R.check("Izoh o'ng chetga suriladi",
            ".card-head .sub { font-size: 12.5px; color: var(--muted); margin-left: auto; }"
            in dash_css_head)

    # --- Test egasi: paneldan kim yaratsa, o'sha ko'rinadi ---
    from django.contrib.auth.models import User as _DjangoUser

    from apps.dashboard.views import _dashboard_owner
    from apps.users.models import BotUser as _BotUser

    class _Req:
        def __init__(self, user):
            self.user = user

    tg_admin, _ = _BotUser.objects.get_or_create(
        telegram_id=770001,
        defaults={"full_name": "Telegramdan Kirgan", "is_admin": True,
                  "is_registered": True},
    )
    _DjangoUser.objects.filter(username="tg_770001").delete()
    tg_account = _DjangoUser.objects.create(username="tg_770001", is_staff=True)
    R.equal("Telegram orqali kirgan admin o'zi egasi",
            _dashboard_owner(_Req(tg_account)).pk, tg_admin.pk)

    _DjangoUser.objects.filter(username="panel_xodim").delete()
    plain = _DjangoUser.objects.create(
        username="panel_xodim", first_name="Panel", last_name="Xodimi", is_staff=True
    )
    owner_a = _dashboard_owner(_Req(plain))
    R.equal("Login bilan kirganga alohida egalik",
            owner_a.full_name, "Panel Xodimi")
    R.check("Egalik boshqa adminga tegishli emas", owner_a.pk != tg_admin.pk)
    R.check("Telegram ID manfiy (to'qnashmaydi)", owner_a.telegram_id < 0)
    R.equal("Ikkinchi chaqiruvda o'sha egalik",
            _dashboard_owner(_Req(plain)).pk, owner_a.pk)

    # --- «Testni yaratish» tugmasi doim ko'rinadi ---
    create_html = (
        BASE_DIR / "apps/dashboard/templates/dashboard/exam_create.html"
    ).read_text(encoding="utf-8")
    R.check("Panelda yopishqoq amal paneli", 'class="action-bar"' in create_html)
    dash_css = (
        BASE_DIR / "apps/dashboard/static/dashboard/css/dashboard.css"
    ).read_text(encoding="utf-8")
    R.check("Amal paneli uslubi bor", ".action-bar {" in dash_css
            and "position: sticky" in dash_css)

    app_js_create = (BASE_DIR / "apps/miniapp/static/miniapp/js/app.js").read_text(
        encoding="utf-8"
    )
    R.check("Ilovada ham yopishqoq panel",
            '<div class="finish-bar">' in app_js_create)
    R.check("Yaratish ekranida panel yoqiladi",
            'view === "attempt" || view === "create"' in app_js_create)
    R.check("Ro'yxatdan o'tmaganga darhol aytiladi",
            "Avval ro" in app_js_create and "is_registered" in app_js_create)

    # --- SQLite qulfida amal qayta bajariladi ---
    from django.db import OperationalError

    from core.db_retry import is_lock_error, retry_on_lock

    R.check("Qulf xatosi tanildi",
            is_lock_error(OperationalError("database is locked")))
    R.check("Boshqa xato tanilmaydi",
            not is_lock_error(OperationalError("no such table: x")))

    calls = {"n": 0}

    @retry_on_lock
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OperationalError("database is locked")
        return "ok"

    R.equal("Qulfdan keyin amal bajariladi", flaky(), "ok")
    R.equal("Uchinchi urinishda o'tdi", calls["n"], 3)

    other = {"n": 0}

    @retry_on_lock
    def broken():
        other["n"] += 1
        raise OperationalError("no such column: zzz")

    try:
        broken()
        R.check("Boshqa xato qayta urinilmaydi", False)
    except OperationalError:
        R.equal("Boshqa xato darhol chiqadi", other["n"], 1)

    api_src = (BASE_DIR / "apps/miniapp/api.py").read_text(encoding="utf-8")
    R.check("Web API qulfda qayta uriniladi", "retry_on_lock(func)" in api_src)

    # Botdagi yozuvchi amallar ham himoyalangan bo'lishi kerak — ular
    # himoyasiz qolsa, foydalanuvchi umuman javob olmaydi.
    protected = {
        "attempts": ["start_attempt", "save_answer", "submit_attempt",
                     "toggle_multi_choice", "set_current_order"],
        "users": ["get_or_create_user", "save_full_name", "save_phone",
                  "set_subscription"],
        "exams": ["create_exam", "activate_exam", "close_exam",
                  "publish_results", "delete_exam"],
        "certificates": ["issue_certificate", "issue_for_exam"],
        "codes": ["create_codes", "activate_code", "consume_code"],
    }
    for module, names in protected.items():
        src = (BASE_DIR / f"bot/services/{module}.py").read_text(encoding="utf-8")
        missing = [n for n in names if f"{n} = sync_db_call(" not in src]
        R.check(f"Qulf himoyasi: {module}", not missing, ", ".join(missing))

    reports_src = (BASE_DIR / "bot/services/reports.py").read_text(encoding="utf-8")
    R.check("Hisobot tayyorlashda ham himoya", "@retry_on_lock" in reports_src)

    # --- Ilovaga botsiz kirganda yo'l ko'rsatiladi (Main Mini App) ---
    from apps.miniapp.auth import MiniAppAuthError

    err = MiniAppAuthError("x", code="not_registered")
    R.equal("Xato sababi kodlanadi", err.code, "not_registered")
    R.equal("Standart kod", MiniAppAuthError("x").code, "invalid")

    api_py = (BASE_DIR / "apps/miniapp/api.py").read_text(encoding="utf-8")
    R.check("401 javobida kod bor", '"code": getattr(exc, "code"' in api_py)
    R.check("401 javobida bot havolasi bor", '"bot_url"' in api_py)
    R.check("401 javobida kanal havolasi bor", '"channel_url"' in api_py)

    app_js_auth = (BASE_DIR / "apps/miniapp/static/miniapp/js/app.js").read_text(
        encoding="utf-8"
    )
    R.check("Ro'yxatdan o'tmaganga «Botni ochish»",
            'payload.code === "not_registered"' in app_js_auth
            and "Botni ochish" in app_js_auth)
    R.check("A'zo bo'lmaganga «Kanalga o'tish»",
            'payload.code === "not_subscribed"' in app_js_auth
            and "Kanalga o" in app_js_auth)
    R.check("Havola Telegram ichida ochiladi",
            "openTelegramLink" in app_js_auth)

    # --- Ikkita hisobot: e'lon uchun va faqat admin uchun ---
    from bot.texts import admin as _TA

    reports_py = (BASE_DIR / "bot/services/reports.py").read_text(encoding="utf-8")
    sched_py = (BASE_DIR / "bot/tasks/scheduler.py").read_text(encoding="utf-8")

    R.check("E'lon PDF si tayyorlanadi", "overall_results_report(exam)" in reports_py)
    R.check("Admin PDF si tayyorlanadi", "results_report(exam)" in reports_py)
    R.check("Ikkalasi ham yuboriladi",
            'payload["pdf"]' in sched_py and 'payload["admin_pdf"]' in sched_py)
    R.check("Admin fayli alohida nom bilan",
            '"admin-hisobot"' in sched_py and '"umumiy-natijalar"' in sched_py)
    R.check("Admin nusxasi ogohlantiriladi",
            "kanalga qo" in _TA.REPORT_ADMIN_COPY)
    R.check("E'lon fayli kanalga mo'ljallangani aytiladi",
            "kanalga" in _TA.REPORT_PUBLISHED and "kanalga" in _TA.REPORT_CLOSED)

    # Qatnashchiga yuboriladigan xabarda to'g'ri javoblar soni yo'q.
    my_tests_py = (BASE_DIR / "bot/handlers/my_tests.py").read_text(encoding="utf-8")
    rasch_block = my_tests_py.split("if exam.uses_rasch:", 1)[1].split("else:", 1)[0]
    R.check("Qatnashchi xabarida to'g'ri javoblar soni yo'q",
            "correct" not in rasch_block)
    R.check("Qatnashchi xabarida foiz bor", "award_percent" in rasch_block)

    # E'lon qilinadigan jadvaldagi foiz — `ball * 100 / 65`, to'g'ri
    # javoblar ulushi emas. Har bir qatnashchi uchun tekshiramiz.
    for item in _ranked(exam)[:5]:
        expected = min(100.0, round(item.ball * 100.0 / 65.0, 2))
        R.close(f"{item.ball:.2f} ball -> {expected:.2f}%",
                C.certificate_percent(item.ball, item.grade), expected, 0.01)

    low = _ranked(exam).last()
    if low is not None and (low.ball or 0) < 65:
        R.check("Past ballda foiz 100% dan kam",
                C.certificate_percent(low.ball) < 100.0)

    # --- Darajalar PDF da rang bilan ajratiladi ---
    from apps.exports import pdf_report as PR
    from core import constants as C

    R.check(
        "Har bir daraja uchun rang bor",
        all(grade in PR.GRADE_COLORS for grade in ("A+", "A", "B+", "B", "C+", "C")),
    )
    R.check(
        "A+ eng to'q yashil, A ochroq",
        PR.GRADE_COLORS["A+"][0] != PR.GRADE_COLORS["A"][0],
    )
    R.equal(
        "Daraja olinmaganda betaraf rang",
        PR.grade_colors(C.NO_GRADE), PR.NO_GRADE_COLOR,
    )
    R.equal("Bo'sh daraja ham bo'yaladi", PR.grade_colors("—"), PR.NO_GRADE_COLOR)
    R.check("Tanilmagan daraja bo'yalmaydi", PR.grade_colors("Z") is None)

    rows = [["№", "Ism", "Daraja"], ["1", "A. A.", "A+"], ["2", "B. B.", "C"]]
    commands = PR._grade_column_style(rows, 2)

    # Har bir qator uchun uchta buyruq: butun qator foni, daraja katagining
    # matn rangi va qalin shrifti.
    R.equal("Ikkita qator uchun 6 ta buyruq", len(commands), 6)

    backgrounds = [c for c in commands if c[0] == "BACKGROUND"]
    R.equal("Har bir qatorga bitta fon", len(backgrounds), 2)
    R.check(
        "Fon butun qatorni egallaydi",
        all(c[1][0] == 0 and c[2][0] == len(rows[0]) - 1 for c in backgrounds),
    )
    R.check(
        "Matn rangi faqat daraja katagida",
        all(c[1][0] == 2 and c[2][0] == 2 for c in commands if c[0] != "BACKGROUND"),
    )
    R.check(
        "Sarlavha qatori bo'yalmaydi",
        all(cmd[1][1] >= 1 for cmd in commands),
    )


# ==========================================================================
#  12. Mini App autentifikatsiyasi
# ==========================================================================


def test_miniapp_auth() -> None:
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode

    from apps.miniapp.auth import validate_init_data

    R.head("12. Mini App initData imzosi")

    token = "123456789:TESTTOKEN"
    user_payload = json.dumps({"id": 555, "first_name": "Test"}, separators=(",", ":"))
    fields = {"auth_date": str(int(time.time())), "query_id": "AAA", "user": user_payload}

    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()

    valid = urlencode({**fields, "hash": signature})
    result = validate_init_data(valid, bot_token=token)
    R.check("To'g'ri imzo qabul qilinadi", result.valid, result.reason)
    R.equal("Foydalanuvchi ID o'qiladi", result.telegram_id, 555)

    tampered = urlencode({**fields, "hash": "0" * 64})
    R.check("Soxta imzo rad etiladi", not validate_init_data(tampered, bot_token=token).valid)
    R.check("Bo'sh initData rad etiladi", not validate_init_data("", bot_token=token).valid)

    old_fields = {**fields, "auth_date": str(int(time.time()) - 100000)}
    old_check = "\n".join(f"{key}={old_fields[key]}" for key in sorted(old_fields))
    old_signature = hmac.new(secret, old_check.encode(), hashlib.sha256).hexdigest()
    old = urlencode({**old_fields, "hash": old_signature})
    R.check("Eskirgan initData rad etiladi",
            not validate_init_data(old, bot_token=token, max_age=3600).valid)


# ==========================================================================
#  13. Web sahifalar
# ==========================================================================


def test_web_pages() -> None:
    from django.test import Client

    from apps.certificates.models import Certificate

    R.head("13. Django web sahifalari")

    client = Client()

    response = client.get("/")
    R.equal("Bosh sahifa ochiladi", response.status_code, 200)
    R.check("Bosh sahifada platforma nomi bor", b"RASCH" in response.content.upper())

    response = client.get("/sog/")
    R.equal("Healthcheck ishlaydi", response.status_code, 200)

    response = client.get("/verify/")
    R.equal("Tekshiruv formasi ochiladi", response.status_code, 200)

    certificate = Certificate.objects.first()
    if certificate:
        response = client.get(f"/verify/{certificate.number}/?t={certificate.verify_token}")
        R.equal("Sertifikat sahifasi ochiladi", response.status_code, 200)
        R.check("Sahifada ism ko'rsatiladi",
                certificate.full_name.encode() in response.content)
        R.check("Haqiqiylik tasdiqlanadi", "haqiqiy".encode() in response.content.lower())

        response = client.get(f"/verify/{certificate.number}/yuklab-olish/?t={certificate.verify_token}")
        R.equal("PDF yuklab olinadi", response.status_code, 200)
    else:
        R.check("Sertifikat mavjud", False, "sertifikat topilmadi")

    response = client.get("/verify/RM-1900-000001/")
    R.equal("Mavjud bo'lmagan sertifikat -> 404", response.status_code, 404)

    response = client.get("/app/")
    R.equal("Web ilova ochiladi", response.status_code, 200)
    R.check("Ilova skripti ulangan", b"app.js" in response.content)

    response = client.get("/app/klaviatura/")
    R.equal("Matematik klaviatura sahifasi olib tashlandi", response.status_code, 404)

    response = client.post(
        "/app/api/tekshir/", data='{"expr": "  Bosh  Gap. "}',
        content_type="application/json",
    )
    R.equal("Mini App API javob beradi", response.status_code, 200)
    payload = response.json()
    R.check("Javob tekshiruvga tayyorlandi", payload.get("ok") is True)
    R.equal("Tekshiruv ko'rinishi", payload.get("normalized"), "bosh gap")

    response = client.post(
        "/app/api/tekshir/", data='{"expr": "osmon, samo, fazo", "as_key": true}',
        content_type="application/json",
    )
    payload = response.json()
    R.equal("Panelda sinonimlar sanaladi", payload.get("variants"), 3)
    R.equal(
        "Panelda sinonimlar ko'rsatiladi",
        payload.get("pretty"),
        "osmon yoki samo yoki fazo",
    )

    response = client.get("/panel/")
    R.check("Panel himoyalangan (login talab qilinadi)",
            response.status_code in (302, 301))

    response = client.get("/panel/kirish/")
    R.equal("Panel login sahifasi ochiladi", response.status_code, 200)

    response = client.get("/admin/")
    R.equal("Django admin olib tashlangan", response.status_code, 404)

    # --- Ikonkalar butunligi (emoji o'rniga SVG) ---
    sprite = (BASE_DIR / "templates" / "partials" / "icons.html").read_text(encoding="utf-8")
    defined = set(_re.findall(r'<symbol id="i-([a-z0-9-]+)"', sprite))
    R.check(f"Ikonkalar to'plami yaratilgan ({len(defined)} ta)", len(defined) >= 40)

    used: dict[str, set[str]] = {}
    for pattern in ("**/*.html", "**/*.js"):
        for path in BASE_DIR.glob(pattern):
            if any(part in {"env", "data", "staticfiles", ".venv"} for part in path.parts):
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for name in _re.findall(r"#i-([a-z0-9-]+)", content):
                used.setdefault(name, set()).add(path.name)
            for name in _re.findall(r'\bic\("([a-z0-9-]+)"', content):
                used.setdefault(name, set()).add(path.name)

    missing = sorted(name for name in used if name not in defined)
    R.check(
        f"Barcha ishlatilgan ikonkalar mavjud ({len(used)} ta)",
        not missing,
        ", ".join(missing[:6]),
    )

    R.check("Bosh sahifada emoji yo'q",
            not _has_emoji(client.get("/").content.decode("utf-8", "ignore")))

    # --- `hidden` atributi CSS bilan bosib ketilmasligi ---
    # `.modal-backdrop { display: flex }` kabi qoidalar brauzerning standart
    # `[hidden] { display: none }` qoidasidan kuchli. Shu sababli har bir
    # uslub faylida `!important` bilan qayta e'lon qilingan bo'lishi shart —
    # aks holda modal oynasi va yashirin tugmalar ekranda qolib ketadi.
    hidden_rule = _re.compile(r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important")
    for css_path in (
        BASE_DIR / "apps" / "miniapp" / "static" / "miniapp" / "css" / "app.css",
        BASE_DIR / "static" / "css" / "site.css",
        BASE_DIR / "apps" / "dashboard" / "static" / "dashboard" / "css" / "dashboard.css",
    ):
        content = css_path.read_text(encoding="utf-8")
        R.check(
            f"`[hidden]` qoidasi mavjud: {css_path.name}",
            bool(hidden_rule.search(content)),
        )

    # Mini App qobig'idagi yashirin elementlar haqiqatan `hidden` bilan chiqadi
    app_html = client.get("/app/").content.decode("utf-8", "ignore")
    for marker in ('id="modal" hidden', 'id="toast" hidden', 'id="btn-back" hidden'):
        R.check(f"Yashirin element to'g'ri belgilangan: {marker}", marker in app_html)


# ==========================================================================
#  14. Web panel (autentifikatsiyadan keyin)
# ==========================================================================


def test_dashboard() -> None:
    from django.contrib.auth.models import User
    from django.test import Client

    from apps.accesscodes.models import CodeBatch
    from apps.exams.models import Exam

    R.head("14. Boshqaruv paneli")

    User.objects.filter(username="selftest_admin").delete()
    User.objects.create_superuser("selftest_admin", "admin@test.local", "SelfTest12345!")

    client = Client()
    logged = client.login(username="selftest_admin", password="SelfTest12345!")
    R.check("Admin tizimga kirdi", logged)

    exam = Exam.objects.filter(exam_type=Exam.Type.RASCH_PAID).first()
    batch = CodeBatch.objects.first()

    pages = [
        ("/panel/", "Umumiy ko'rinish"),
        ("/panel/testlar/", "Testlar ro'yxati"),
        (f"/panel/testlar/{exam.pk}/", "Test tafsilotlari"),
        (f"/panel/testlar/{exam.pk}/savollar/", "Savollar sahifasi"),
        (f"/panel/testlar/{exam.pk}/natijalar/", "Natijalar sahifasi"),
        (f"/panel/testlar/{exam.pk}/kodlar/", "ID kodlar sahifasi"),
        ("/panel/sertifikatlar/", "Sertifikatlar ro'yxati"),
        ("/panel/foydalanuvchilar/", "Foydalanuvchilar ro'yxati"),
    ]
    for url, label in pages:
        response = client.get(url)
        R.equal(f"{label} ochiladi", response.status_code, 200)

    # --- Savollar qiyinchiligi diagrammasi faqat panelda (adminda) ---
    scored = next(
        (
            item
            for item in Exam.objects.filter(statistics__isnull=False).order_by("-id")
            if item.statistics.item_statistics
        ),
        None,
    )
    R.check("Hisoblangan test topildi", scored is not None)
    if scored is not None:
        results_url = f"/panel/testlar/{scored.pk}/natijalar/"
        body = client.get(results_url).content.decode("utf-8", "replace")
        R.check("Natijalar sahifasida qiyinchilik diagrammasi bor",
                "Savollar qiyinchiliklari" in body and 'class="chart-svg"' in body)
        R.check("Diagramma «faqat admin uchun» deb belgilangan",
                "Faqat admin uchun" in body)

        anonymous = Client()
        R.check("Diagramma sahifasi anonim foydalanuvchiga berilmaydi",
                anonymous.get(results_url).status_code in {302, 403})

    downloads = [
        (f"/panel/testlar/{exam.pk}/eksport/natijalar.xlsx", "Natijalar (Excel)"),
        (f"/panel/testlar/{exam.pk}/eksport/natijalar.pdf", "Natijalar (PDF)"),
        (f"/panel/testlar/{exam.pk}/eksport/ishtirokchilar.xlsx", "Ishtirokchilar (Excel)"),
        (f"/panel/partiya/{batch.pk}/eksport/kodlar.xlsx", "ID kodlar (Excel)"),
    ]
    for url, label in downloads:
        response = client.get(url)
        R.equal(f"{label} yuklab olinadi", response.status_code, 200)
        R.check(f"{label} bo'sh emas", len(response.content) > 1000)

    # ------------------------------------------------------------------
    #  Django admin o'rniga qo'shilgan sahifalar
    # ------------------------------------------------------------------
    from apps.attempts.models import Attempt
    from apps.certificates.models import Certificate
    from apps.exams.models import Question
    from apps.users.models import BotUser

    attempt = (
        Attempt.objects.filter(status=Attempt.Status.SUBMITTED)
        .select_related("exam")
        .order_by("id")
        .first()
    )
    R.check("Sinov uchun urinish topildi", attempt is not None)
    target_exam = attempt.exam
    question = Question.objects.filter(exam=target_exam).order_by("order").first()
    bot_user = BotUser.objects.filter(telegram_id=1000).first()
    certificate = Certificate.objects.order_by("id").first()

    extra_pages = [
        ("/panel/testlar/yangi/", "Yangi test formasi"),
        (f"/panel/testlar/{exam.pk}/ochirish/", "O'chirish tasdiqlash sahifasi"),
        (f"/panel/testlar/{target_exam.pk}/savollar/{question.pk}/", "Savolni tahrirlash"),
        ("/panel/urinishlar/", "Urinishlar ro'yxati"),
        (f"/panel/urinish/{attempt.pk}/", "Urinish tafsiloti"),
        (f"/panel/foydalanuvchi/{bot_user.pk}/", "Foydalanuvchi tafsiloti"),
        ("/panel/tarix/", "Amallar tarixi"),
        ("/panel/tg/", "Telegram kirish sahifasi"),
    ]
    for url, label in extra_pages:
        response = client.get(url)
        R.equal(f"{label} ochiladi", response.status_code, 200)

    # --- Savolni tahrirlash haqiqatan saqlaydimi ---
    response = client.post(
        f"/panel/testlar/{target_exam.pk}/savollar/{question.pk}/",
        {
            "text": "Sinov savoli matni",
            "section": "1-qism",
            "kind": question.kind,
            "choices_count": question.choices_count,
            "parts": question.parts,
            "correct_key": "B",
            "answer_a": "",
            "answer_b": "",
            "numeric_tolerance": "0.000001",
            "difficulty": "0.75",
            "difficulty_b": "",
            "difficulty_locked": "on",
            "is_active": "on",
        },
    )
    R.check("Savol saqlandi (redirect)", response.status_code in (302, 301))
    question.refresh_from_db()
    R.equal("Savol matni saqlandi", question.text, "Sinov savoli matni")
    R.equal("Kalit saqlandi", question.correct_key, "B")
    R.close("Qiyinlik saqlandi", question.difficulty, 0.75, 0.001)
    R.check("Qulflash saqlandi", question.difficulty_locked)

    # --- Foydalanuvchini bloklash / blokdan chiqarish ---
    client.get(f"/panel/foydalanuvchi/{bot_user.pk}/amal/bloklash/")
    bot_user.refresh_from_db()
    R.check("Foydalanuvchi bloklandi", bot_user.is_blocked)
    client.get(f"/panel/foydalanuvchi/{bot_user.pk}/amal/blokdan-chiqarish/")
    bot_user.refresh_from_db()
    R.check("Foydalanuvchi blokdan chiqarildi", not bot_user.is_blocked)

    # --- Urinishni qayta baholash ---
    response = client.get(f"/panel/urinish/{attempt.pk}/amal/qayta-baholash/")
    R.check("Urinish qayta baholandi", response.status_code in (302, 301))

    # --- Sertifikatni bekor qilish / tiklash ---
    if certificate is not None:
        client.get(f"/panel/sertifikat/{certificate.pk}/amal/bekor/")
        certificate.refresh_from_db()
        R.check("Sertifikat bekor qilindi", certificate.is_revoked)
        client.get(f"/panel/sertifikat/{certificate.pk}/amal/tiklash/")
        certificate.refresh_from_db()
        R.check("Sertifikat tiklandi", not certificate.is_revoked)

    # --- ID kodni bekor qilish / tiklash ---
    from apps.accesscodes.models import AccessCode

    code = AccessCode.objects.order_by("id").first()
    if code is not None:
        client.get(f"/panel/kod/{code.pk}/amal/bekor/")
        code.refresh_from_db()
        R.equal("ID kod bekor qilindi", code.status, AccessCode.Status.REVOKED)
        client.get(f"/panel/kod/{code.pk}/amal/tiklash/")
        code.refresh_from_db()
        R.equal("ID kod tiklandi", code.status, AccessCode.Status.UNUSED)

    # --- Foydalanuvchini admin qilish ---
    client.get(f"/panel/foydalanuvchi/{bot_user.pk}/amal/admin/")
    bot_user.refresh_from_db()
    R.check("Foydalanuvchi admin qilindi", bot_user.is_admin)

    # --- Telegram orqali kirish ---
    fresh = Client()
    response = fresh.post("/panel/tg-kirish/", data="{}", content_type="application/json")
    R.equal("initData'siz kirish rad etiladi", response.status_code, 401)

    response = fresh.post(
        "/panel/tg-kirish/", data="{}", content_type="application/json",
        HTTP_X_DEBUG_USER="2000",
    )
    R.equal("Oddiy foydalanuvchi panelga kira olmaydi", response.status_code, 403)

    response = fresh.post(
        "/panel/tg-kirish/", data="{}", content_type="application/json",
        HTTP_X_DEBUG_USER=str(bot_user.telegram_id),
    )
    R.equal("Admin Telegram orqali kirdi", response.status_code, 200)
    R.check("Kirish javobi to'g'ri", response.json().get("ok") is True)

    response = fresh.get("/panel/")
    R.equal("Telegram sessiyasi bilan panel ochiladi", response.status_code, 200)

    # --- Telegram iframe uchun sarlavhalar ---
    response = client.get("/app/")
    R.check("Mini App iframe'da ochiladi (X-Frame-Options yo'q)",
            "X-Frame-Options" not in response.headers)
    R.check("frame-ancestors siyosati qo'yilgan",
            "frame-ancestors" in response.headers.get("Content-Security-Policy", ""))
    R.check("Telegram domeni ruxsat etilgan",
            "telegram.org" in response.headers.get("Content-Security-Policy", ""))


# ==========================================================================
#  15. Bot modullari
# ==========================================================================


def test_bot() -> None:
    R.head("15. Telegram bot (aiogram 3)")

    from bot.config import get_config
    from bot.keyboards import inline, reply
    from bot.texts import admin as TA
    from bot.texts import common as TC
    from bot.texts import exam as TE
    from bot.texts import start as TS

    config = get_config()
    R.check("Konfiguratsiya o'qildi", config.token != "")
    R.check("Mini App manzili shakllandi", config.miniapp_url.endswith("/app/"))

    R.check("Boshlash matni mavjud", "xush kelibsiz" in TS.WELCOME.lower())
    R.check("Obuna matni kanalni ko'rsatadi", "{channel}" in TS.SUBSCRIPTION_REQUIRED)
    R.check("Ro'yxatdan o'tish matni", "Ism va familiyangizni kiriting" in TS.ASK_FULL_NAME)
    R.check("«Javoblaringiz qabul qilindi» matni bor",
            "Javoblaringiz qabul qilindi" in TE.SUBMITTED)
    R.check("Botda emoji yo'q (matnlar)", not _has_emoji(
        "".join(str(getattr(module, name)) for module in (TC, TS, TE, TA)
               for name in dir(module) if name.isupper() and isinstance(getattr(module, name), str))
    ))
    R.check("Natija matni RASH ballini ko'rsatadi", "RASH ballingiz" in TE.RESULT_READY)
    R.check("Sertifikat tugmasi matni", "Sertifikatni olish" in TE.BTN_GET_CERTIFICATE)
    R.check("ID kod so'rovi matni", "ID kodingizni kiriting" in TE.ASK_ACCESS_CODE)
    R.check("Admin panel matni", "Administrator paneli" in TA.PANEL_TITLE)
    R.check("Progress-bar ishlaydi", TC.progress_bar(5, 10).count("▰") == 5)

    menu = reply.main_menu(is_admin=True)
    R.check("Asosiy menyuda web ilova tugmasi", menu.keyboard[0][0].web_app is not None)
    R.check("Asosiy menyu tugmalari", len(menu.keyboard) == 5)
    R.check("Admin tugmasi bor", any(
        TC.BTN_ADMIN in [button.text for button in row] for row in menu.keyboard
    ))
    R.check("Telefon tugmasi kontakt so'raydi",
            reply.phone_request().keyboard[0][0].request_contact is True)

    R.check("Obuna klaviaturasi 2 ta tugma",
            len(inline.subscription("https://t.me/Burgutali").inline_keyboard) == 2)

    # --- Majburiy obuna ---
    # Kanal `.env` da beriladi va o'chirilgan bo'lishi ham mumkin, shuning
    # uchun bu yerda sozlamaning **izchilligi** tekshiriladi: obuna yoqilgan
    # bo'lsa kanal ham, havolasi ham ko'rsatilgan bo'lishi shart.
    if config.subscription_required:
        R.check("Majburiy obuna yoqilgan — kanal ko'rsatilgan",
                bool(config.required_channel))
        R.check("Majburiy obuna yoqilgan — kanal havolasi bor",
                config.required_channel_url.startswith("https://t.me/"))
    else:
        R.check("Majburiy obuna o'chirilgan (sozlamada shunday)",
                config.subscription_required is False)

    from bot.middlewares.subscription_mw import EXEMPT_COMMANDS
    from bot.utils import subscription as sub_utils

    R.check("Obunadan ozod buyruq — faqat /start", EXEMPT_COMMANDS == {"/start"})
    R.check("Bot kanalda admin ekani tekshiriladi",
            hasattr(sub_utils, "check_bot_is_channel_admin"))

    mw_source = (BASE_DIR / "bot/middlewares/subscription_mw.py").read_text(
        encoding="utf-8"
    )
    R.check(
        "Tekshirib bo'lmasa ham kirish berilmaydi",
        "check_failed=True" in mw_source
        and "return await handler(event, data)" not in mw_source.split(
            "if subscribed is None:", 1
        )[1].split("await user_service.set_subscription", 1)[0],
    )
    R.check("Test turlari klaviaturasi (admin)",
            len(inline.exam_types(True).inline_keyboard) == 4)
    R.check("Test turlari klaviaturasi (oddiy foydalanuvchi)",
            len(inline.exam_types(False).inline_keyboard) == 3)
    R.check("ID kod miqdorlari klaviaturasi",
            len(inline.code_quantities(1).inline_keyboard) >= 4)

    from bot.loader import create_dispatcher

    dispatcher = create_dispatcher()
    R.check("Dispatcher yig'ildi", dispatcher is not None)
    R.equal("Routerlar soni", len(dispatcher.sub_routers), 11)

    used = dispatcher.resolve_used_update_types()
    R.check("message yangilanishi kuzatiladi", "message" in used)
    R.check("callback_query kuzatiladi", "callback_query" in used)

    from bot.utils.formatting import format_duration, rating_rows, status_label

    R.equal("Davomiylik formati", format_duration(3665), "1 soat 1 daq 5 s")
    R.check("Holat yozuvi", "Faol" in status_label("active"))
    R.check("Bo'sh reyting xabari", "yo'q" in rating_rows([], uses_rasch=True))


# ==========================================================================
#  16. Mini App API (web ilova)
# ==========================================================================


def test_miniapp_api() -> None:
    import json

    from django.test import Client

    from apps.exams import services as exam_services
    from apps.exams.models import Exam
    from apps.users.models import BotUser

    R.head("16. Mini App API (web ilova)")

    client = Client()
    user = BotUser.objects.get(telegram_id=2000)
    admin = BotUser.objects.get(telegram_id=1000)

    def call(path, payload=None, who=None, method=None):
        headers = {"HTTP_X_DEBUG_USER": str((who or user).telegram_id)}
        if payload is not None or method == "POST":
            return client.post(
                path, data=json.dumps(payload or {}),
                content_type="application/json", **headers
            )
        return client.get(path, **headers)

    # --- Autentifikatsiya ---
    response = client.get("/app/api/boshlash/")
    R.equal("Autentifikatsiyasiz so'rov rad etiladi", response.status_code, 401)
    R.check("Xato javobida sabab bor", "error" in response.json())

    response = client.get("/app/api/boshlash/", HTTP_X_DEBUG_USER="99999999")
    R.equal("Mavjud bo'lmagan foydalanuvchi rad etiladi", response.status_code, 401)

    # --- Boshlang'ich ma'lumot ---
    response = call("/app/api/boshlash/")
    R.equal("bootstrap ishlaydi", response.status_code, 200)
    data = response.json()
    R.check("Foydalanuvchi qaytadi", data["user"]["telegram_id"] == 2000)
    R.check("Testlar ro'yxati bor", isinstance(data["exams"], list))
    R.check("Natijalar ro'yxati bor", isinstance(data["results"], list))
    R.check("Daraja jadvali uzatiladi", len(data["grade_table"]) == 7)
    R.equal("Maksimal ball uzatiladi", data["max_ball"], 90.14)

    # --- Profilni tahrirlash ---
    was = (user.full_name, user.phone)

    response = call("/app/api/profil/", {"full_name": "Alisher", "phone": "+998901234567"})
    R.equal("Bir so'zli ism rad etiladi", response.status_code, 400)

    response = call("/app/api/profil/", {"full_name": "Alisher Rahimov", "phone": "123"})
    R.equal("Qisqa telefon rad etiladi", response.status_code, 400)

    response = call("/app/api/profil/", {"full_name": "", "phone": ""})
    R.equal("Bo'sh profil rad etiladi", response.status_code, 400)

    response = call(
        "/app/api/profil/", {"full_name": "  alisher   RAHIMOV ", "phone": "901234567"}
    )
    R.equal("Profil saqlandi", response.status_code, 200)
    saved = response.json()["saved"]
    R.equal("Ism tozalanadi va bosh harfga keltiriladi", saved["full_name"], "Alisher Rahimov")
    R.equal("Telefon +998 bilan saqlanadi", saved["phone"], "+998901234567")

    user.refresh_from_db()
    R.equal("Bazada yangilandi", user.full_name, "Alisher Rahimov")
    R.check("Profil tahriri tarixga yozildi", user.actions.filter(
        description="Profilni tahrirladi"
    ).exists())

    response = call("/app/api/profil/", method="GET")
    R.equal("Profil faqat POST bilan o'zgaradi", response.status_code, 405)

    user.full_name, user.phone = was
    user.save(update_fields=["full_name", "phone"])

    # --- Yangi test yaratish ---
    response = call("/app/api/test-yaratish/", {
        "title": "Mini App orqali test",
        "type": "simple",
        "question_count": 5,
        "single_keys": "ABCDA",
        "show_results": True,
        "duration_hours": 0,
    }, who=admin)
    R.equal("API orqali test yaratildi", response.status_code, 200)
    created = response.json()["exam"]
    R.equal("5 ta savol", created["question_count"], 5)
    R.check("Test faollashtirildi", response.json()["activated"])
    exam_code = created["code"]
    # Kodlar qayta ishlatiladi, shuning uchun testni `id` bo'yicha kuzatamiz.
    exam_id = exam_services.get_exam_by_code(exam_code).pk

    # --- Noto'g'ri kalit rad etiladi ---
    response = call("/app/api/test-yaratish/", {
        "title": "Xato kalitli test", "type": "simple",
        "question_count": 5, "single_keys": "AB",
    }, who=admin)
    R.equal("Noto'g'ri kalit rad etiladi", response.status_code, 400)
    R.check("Xatolar ro'yxati qaytadi", bool(response.json().get("errors")))

    # --- Testni ko'rish va boshlash ---
    participant, _ = BotUser.objects.get_or_create(
        telegram_id=8801,
        defaults={"full_name": "Mini App Ishtirokchi", "is_registered": True},
    )
    response = call(f"/app/api/test/{exam_code}/", who=participant)
    R.equal("Test tafsilotlari ochiladi", response.status_code, 200)
    R.check("Qatnashish mumkin", response.json()["can_participate"])

    response = call(f"/app/api/test/{exam_code}/boshlash/", {}, who=participant)
    R.equal("Test boshlandi", response.status_code, 200)
    attempt_id = response.json()["attempt_id"]

    response = call(f"/app/api/urinish/{attempt_id}/", who=participant)
    R.equal("Savollar olindi", response.status_code, 200)
    questions = response.json()["questions"]
    R.equal("5 ta savol qaytdi", len(questions), 5)
    R.check("Javob maydonlari bo'sh", not questions[0]["answered"])

    # --- Javob saqlash ---
    for index, question in enumerate(questions):
        letter = "ABCDA"[index] if index < 4 else "B"  # oxirgisi xato
        response = call(
            f"/app/api/urinish/{attempt_id}/javob/",
            {"order": question["order"], "selected": letter},
            who=participant,
        )
        if index == 0:
            R.equal("Javob saqlandi", response.status_code, 200)
    R.equal("Javoblar hisoblandi", response.json()["answered"], 5)

    # --- Noto'g'ri variant rad etiladi ---
    response = call(
        f"/app/api/urinish/{attempt_id}/javob/",
        {"order": 1, "selected": "Z"}, who=participant,
    )
    R.equal("Noto'g'ri variant rad etiladi", response.status_code, 400)

    # --- Begona urinishga kirish taqiqlanadi ---
    response = call(f"/app/api/urinish/{attempt_id}/", who=user)
    R.equal("Begona urinish rad etiladi", response.status_code, 403)

    # --- Yuborish ---
    response = call(f"/app/api/urinish/{attempt_id}/yuborish/", {}, who=participant)
    R.equal("Javoblar yuborildi", response.status_code, 200)
    attempt = response.json()["attempt"]
    R.equal("4 ta to'g'ri javob", attempt["correct"], 4)
    R.equal("Urinish yuborilgan", attempt["status"], "submitted")

    # --- Natija ---
    response = call(f"/app/api/urinish/{attempt_id}/natija/", who=participant)
    R.equal("Natija olindi", response.status_code, 200)
    result = response.json()
    R.check("Natija ko'rinadi", result["visible"])
    R.equal("Javoblar tahlili 5 ta qator", len(result["review"]), 5)
    R.equal("Birinchi javob to'g'ri", result["review"][0]["state"], "correct")
    R.equal("Oxirgi javob xato", result["review"][4]["state"], "wrong")

    # --- Reyting ---
    response = call(f"/app/api/test/{exam_code}/reyting/", who=participant)
    R.equal("Reyting olindi", response.status_code, 200)
    R.check("Reytingda qatnashchi bor", len(response.json()["rows"]) >= 1)

    # --- Boshqaruv ---
    response = call(f"/app/api/test/{exam_code}/boshqaruv/", who=admin)
    R.equal("Boshqaruv ma'lumoti olindi", response.status_code, 200)
    R.check("Eksport havolalari bor", "results_xlsx" in response.json()["exports"])

    response = call(f"/app/api/test/{exam_code}/boshqaruv/", who=participant)
    R.equal("Begona foydalanuvchi boshqara olmaydi", response.status_code, 403)

    # --- Amallar ---
    response = call(f"/app/api/test/{exam_code}/amal/", {"action": "close"}, who=admin)
    R.equal("Test yopildi", response.status_code, 200)
    response = call(f"/app/api/test/{exam_code}/amal/", {"action": "calculate"}, who=admin)
    R.equal("Natijalar hisoblandi", response.status_code, 200)
    response = call(f"/app/api/test/{exam_code}/amal/", {"action": "publish"}, who=admin)
    R.equal("Natijalar e'lon qilindi", response.status_code, 200)

    response = call(f"/app/api/test/{exam_code}/amal/", {"action": "yoq"}, who=admin)
    R.equal("Noma'lum amal rad etiladi", response.status_code, 400)

    # --- Nusxalash ---
    response = call(f"/app/api/test/{exam_code}/amal/", {"action": "duplicate"}, who=admin)
    R.equal("Nusxa yaratildi", response.status_code, 200)
    copy_code = response.json()["exam"]["code"]
    # Kod noyob emas: test yakunlangach u bo'shab, boshqa testga berilishi
    # mumkin (`release_code`). Shuning uchun nusxani kod bo'yicha emas,
    # `id` bo'yicha kuzatamiz.
    copy_id = Exam.objects.filter(code=copy_code, status="draft").order_by("-id").first().pk
    R.check("Nusxa — alohida test", copy_id != exam_id)
    R.equal("Nusxa qoralama holatida", response.json()["exam"]["status"], "draft")
    R.check("Nusxa kod bo'yicha topiladi",
            exam_services.get_exam_by_code(copy_code).pk == copy_id)

    # --- Ochiq javobni tekshiruvga tayyorlash ---
    response = call("/app/api/ifoda/", {"expr": "  Bosh  Gap. "}, who=participant)
    R.equal("Javob tekshirildi", response.status_code, 200)
    R.equal("Tekshiruv ko'rinishi", response.json()["normalized"], "bosh gap")
    R.equal("Ekranda harflar saqlanadi", response.json()["pretty"], "Bosh Gap.")

    # Kalit yozilayotganda sinonimlar ajratib ko'rsatiladi...
    response = call(
        "/app/api/ifoda/", {"expr": "osmon, samo", "as_key": True}, who=participant
    )
    R.equal("Kalitdagi sinonimlar sanaladi", response.json()["variants"], 2)
    R.equal("Sinonimlar ko'rsatiladi", response.json()["pretty"], "osmon yoki samo")

    # ...qatnashchining javobi esa bitta butun javob bo'lib qoladi.
    response = call("/app/api/ifoda/", {"expr": "osmon, samo"}, who=participant)
    R.equal("Qatnashchi javobi bo'linmaydi", response.json()["variants"], 1)

    response = call("/app/api/ifoda/", {"expr": "   "}, who=participant)
    R.equal("Bo'sh javob rad etiladi", response.status_code, 400)

    # --- O'chirish ---
    response = call(f"/app/api/test/{copy_code}/ochirish-tekshiruv/", who=admin)
    R.equal("O'chirish hisoboti olindi", response.status_code, 200)

    response = call(f"/app/api/test/{copy_code}/ochirish/", {"confirm": True}, who=admin)
    R.equal("Nusxa o'chirildi", response.status_code, 200)
    R.check("Baza tozalandi", not Exam.objects.filter(pk=copy_id).exists())

    # --- Tasdiqsiz o'chirish (javoblari bor test) ---
    response = call(f"/app/api/test/{exam_code}/ochirish/", {}, who=admin)
    R.equal("Tasdiqsiz o'chirish rad etiladi", response.status_code, 409)
    R.check("Tasdiq talab qilinadi", response.json().get("needs_confirmation"))

    response = call(f"/app/api/test/{exam_code}/ochirish/", {"confirm": True}, who=admin)
    R.equal("Tasdiq bilan o'chirildi", response.status_code, 200)
    R.check("Test o'chdi", not Exam.objects.filter(pk=exam_id).exists())

    # --- Sahifa ochiladi ---
    response = client.get("/app/?view=exams")
    R.equal("Web ilova sahifasi ochiladi", response.status_code, 200)
    R.check("SPA skripti ulangan", b"app.js" in response.content)
    R.check("Ikonkalar to'plami ulangan", b"i-award" in response.content)


# ==========================================================================
#  17. Test o'chirish va nusxalash (xizmat darajasida)
# ==========================================================================


def test_delete_duplicate() -> None:
    from apps.accesscodes.models import AccessCode
    from apps.attempts.models import Attempt
    from apps.certificates.models import Certificate
    from apps.exams.models import Exam, Question
    from apps.exams.services import (
        activate_exam,
        apply_single_keys,
        can_manage,
        create_exam,
        delete_exam,
        deletion_summary,
        duplicate_exam,
    )
    from apps.users.models import BotUser

    R.head("17. Testni nusxalash va o'chirish")

    owner = BotUser.objects.get(telegram_id=1000)
    stranger = BotUser.objects.get(telegram_id=2001)

    exam = create_exam(
        owner=owner, title="O'chiriladigan test",
        exam_type=Exam.Type.SIMPLE, question_count=6,
    )
    apply_single_keys(exam, ["A", "B", "C", "D", "A", "B"])
    activate_exam(exam)

    # --- Huquqlar ---
    R.check("Egasi boshqara oladi", can_manage(exam, owner))
    R.check("Begona boshqara olmaydi", not can_manage(exam, stranger))
    R.check("Admin boshqara oladi", can_manage(exam, stranger, is_admin=True))

    # --- Nusxalash ---
    copy = duplicate_exam(exam, owner)
    R.check("Nusxa yaratildi", copy.id != exam.id)
    R.equal("Nusxadagi savollar soni", copy.questions.count(), 6)
    R.equal("Kalitlar ko'chirildi", copy.questions.order_by("order").first().correct_key, "A")
    R.equal("Nusxa qoralama", copy.status, Exam.Status.DRAFT)
    R.check("Kod noyob", copy.code != exam.code)
    R.check("Nomida «nusxa» bor", "nusxa" in copy.title)

    # --- Bo'sh testni o'chirish ---
    ok, message, summary = delete_exam(copy)
    R.check("Javobsiz test tasdiqsiz o'chadi", ok, message)
    R.check("Savollar ham o'chdi", not Question.objects.filter(exam_id=copy.id).exists())

    # --- Javoblari bor test ---
    from apps.attempts.services import save_answer, start_attempt, submit_attempt

    participant, _ = BotUser.objects.get_or_create(
        telegram_id=8802, defaults={"full_name": "O'chirish Testi", "is_registered": True}
    )
    attempt = start_attempt(participant, exam)
    for question in exam.questions.order_by("order"):
        save_answer(attempt, question, selected=question.correct_key)
    submit_attempt(attempt)

    summary = deletion_summary(exam)
    R.equal("Hisobotda 1 ta topshirilgan javob", summary["submitted"], 1)
    R.check("Tasdiq talab qilinadi", summary["needs_confirmation"])

    ok, message, _ = delete_exam(exam)
    R.check("Tasdiqsiz o'chirilmaydi", not ok)
    R.check("Xabar tushunarli", "tasdiqlanishi" in message.lower())

    exam_id = exam.id
    ok, message, _ = delete_exam(exam, force=True)
    R.check("Tasdiq bilan o'chirildi", ok)
    R.check("Urinishlar ham o'chdi", not Attempt.objects.filter(exam_id=exam_id).exists())
    R.check("Test bazada yo'q", not Exam.objects.filter(id=exam_id).exists())

    # --- Pullik test: kodlar va sertifikatlar bilan ---
    paid = (
        Exam.objects.filter(exam_type=Exam.Type.RASCH_PAID, access_codes__isnull=False)
        .distinct()
        .first()
    )
    if paid is not None:
        paid_id = paid.id
        summary = deletion_summary(paid)
        R.check("Pullik testda kodlar bor", summary["codes"] > 0)
        ok, _, _ = delete_exam(paid, force=True)
        R.check("Pullik test o'chirildi", ok)
        R.check("ID kodlar ham o'chdi", not AccessCode.objects.filter(exam_id=paid_id).exists())
        R.check("Sertifikatlar ham o'chdi",
                not Certificate.objects.filter(exam_id=paid_id).exists())


# ==========================================================================
#  18. Chegaraviy holatlar
# ==========================================================================


def test_edge_cases() -> None:
    from apps.attempts.services import can_participate
    from apps.exams.models import Exam
    from apps.exams.services import activate_exam, close_exam, create_exam, get_exam_by_code, publish_results
    from apps.rasch.services import calculate_exam
    from apps.users.models import BotUser

    R.head("18. Chegaraviy holatlar")

    owner = BotUser.objects.get(telegram_id=1000)

    # --- Kalitsiz test faollashmaydi ---
    empty = create_exam(
        owner=owner, title="Kalitsiz test", exam_type=Exam.Type.SIMPLE, question_count=5
    )
    ok, message = activate_exam(empty)
    R.check("Kalitsiz test faollashmaydi", not ok)
    R.check("Xabar savollarni ko'rsatadi", "kalit" in message.lower())

    # --- Savolsiz test ---
    zero = create_exam(
        owner=owner, title="Savolsiz test", exam_type=Exam.Type.SIMPLE, question_count=0
    )
    ok, _ = activate_exam(zero)
    R.check("Savolsiz test faollashmaydi", not ok)

    # --- Qatnashchisiz hisoblash ---
    report = calculate_exam(zero)
    R.equal("Qatnashchisiz hisoblash xato bermaydi", report.participants, 0)

    # --- Hisoblanmagan natijani e'lon qilib bo'lmaydi ---
    fresh = create_exam(
        owner=owner, title="Yangi test", exam_type=Exam.Type.RASCH_FREE, question_count=5
    )
    ok, _ = publish_results(fresh)
    R.check("Hisoblanmagan natija e'lon qilinmaydi", not ok)

    # --- Ro'yxatdan o'tmagan foydalanuvchi ---
    guest, _ = BotUser.objects.get_or_create(
        telegram_id=7777, defaults={"full_name": "", "is_registered": False}
    )
    active_exam = Exam.objects.filter(status=Exam.Status.ACTIVE).first()
    check = can_participate(guest, active_exam)
    R.check("Ro'yxatdan o'tmaganlar qatnasha olmaydi", not check.ok)

    # --- Bloklangan foydalanuvchi ---
    blocked, _ = BotUser.objects.get_or_create(
        telegram_id=7778,
        defaults={"full_name": "Bloklangan", "is_registered": True, "is_blocked": True},
    )
    check = can_participate(blocked, active_exam)
    R.check("Bloklanganlar qatnasha olmaydi", not check.ok)

    # --- Yopilgan testga javob berib bo'lmaydi ---
    closed = create_exam(
        owner=owner, title="Yopilgan test", exam_type=Exam.Type.SIMPLE, question_count=3
    )
    from apps.exams.services import apply_single_keys

    apply_single_keys(closed, ["A", "B", "C"])
    activate_exam(closed)
    close_exam(closed)
    closed.refresh_from_db()
    normal, _ = BotUser.objects.get_or_create(
        telegram_id=7779, defaults={"full_name": "Oddiy Foydalanuvchi", "is_registered": True}
    )
    check = can_participate(normal, closed)
    R.check("Yopilgan testga javob berib bo'lmaydi", not check.ok)

    # --- Test kodi bo'yicha qidiruv ---
    found = get_exam_by_code(closed.code.lower())
    R.check("Kod registrga befarq topiladi", found is not None and found.id == closed.id)
    R.check("Bo'sh kod None qaytaradi", get_exam_by_code("") is None)
    R.check("Noto'g'ri kod None qaytaradi", get_exam_by_code("YOQ-XXXXXX") is None)

    # --- Bo'sh javoblar bilan yuborish ---
    from apps.attempts.services import start_attempt, submit_attempt

    empty_exam = create_exam(
        owner=owner, title="Bo'sh javoblar", exam_type=Exam.Type.SIMPLE, question_count=4
    )
    apply_single_keys(empty_exam, ["A", "B", "C", "D"])
    activate_exam(empty_exam)
    lazy, _ = BotUser.objects.get_or_create(
        telegram_id=7780, defaults={"full_name": "Bo'sh Javob", "is_registered": True}
    )
    lazy_attempt = start_attempt(lazy, empty_exam)
    submit_attempt(lazy_attempt)
    lazy_attempt.refresh_from_db()
    R.equal("Bo'sh javoblar 0 ball", lazy_attempt.raw_score, 0.0)
    R.equal("4 ta javobsiz savol", lazy_attempt.empty_count, 4)
    R.close("Foiz 0", lazy_attempt.percent, 0.0, 0.01)


# ==========================================================================
#  19. Test kodi: oddiy son va qayta ishlatilishi
# ==========================================================================


def test_exam_codes() -> None:
    from apps.exams.models import Exam, ReservedExamCode
    from apps.exams.services import (
        activate_exam,
        apply_single_keys,
        archive_exam,
        close_exam,
        create_exam,
        _reserve_code,
        delete_exam,
        generate_exam_code,
        get_exam_by_code,
        release_code,
    )
    from apps.users.models import BotUser

    R.head("19. Test kodi: oddiy son va qayta ishlatilishi")

    owner, _ = BotUser.objects.get_or_create(
        telegram_id=8801,
        defaults={"full_name": "Kod Egasi", "is_registered": True},
    )

    def new_exam(title: str) -> Exam:
        exam = create_exam(
            owner=owner, title=title, exam_type=Exam.Type.SIMPLE, question_count=2
        )
        apply_single_keys(exam, ["A", "B"])
        return exam

    # --- Ko'rinishi: oddiy 2–3 xonali son ---
    codes = [generate_exam_code(f"Kod sinovi {index}") for index in range(12)]
    R.check("Kodlar faqat raqamdan iborat", all(code.isdigit() for code in codes))
    R.check("Kodlar 2–3 xonali", all(2 <= len(code) <= 3 for code in codes))
    R.equal("Kodlar takrorlanmaydi", len(set(codes)), len(codes))

    # --- Yangi band qilingan kod eski test tufayli bo'shab ketmasin ---
    # Kodlar 2-3 xonali, shuning uchun yangi kod ilgari ishlatilib
    # yakunlangan testnikiga tushib qolishi odatiy hol. Shunda bandlik
    # yozuvi (hali yaratilmagan test uchun) bo'shatilmasligi kerak.
    finished = new_exam("Yakunlangan test")
    finished_code = finished.code
    finished.status = Exam.Status.PUBLISHED
    finished.save(update_fields=["status"])
    release_code(finished_code)

    R.check("Yakunlangan testning kodi bo'shaydi",
            generate_exam_code("Yangi egasi") is not None)
    ReservedExamCode.objects.filter(code=finished_code).delete()

    # Kodni qo'lda band qilamiz — test hali yaratilmagan.
    R.check("Kod band qilindi", _reserve_code(finished_code, "Hali yaratilmagan"))
    R.check("Band kod ikkinchi marta berilmaydi",
            not _reserve_code(finished_code, "Boshqa test"))
    ReservedExamCode.objects.filter(code=finished_code).delete()

    # --- Faol testda kod band ---
    first = new_exam("Kod sinovi — birinchi")
    activate_exam(first)
    first.refresh_from_db()
    R.check("Kod bo'yicha faol test topiladi", get_exam_by_code(first.code) == first)
    R.check(
        "Faol testning kodi band",
        ReservedExamCode.objects.filter(
            code=first.code, released_at__isnull=True
        ).exists(),
    )

    # --- Yopilgach kod «kuyadi» ---
    close_exam(first)
    R.check(
        "Yopilgandan keyin kod bo'shaydi",
        ReservedExamCode.objects.filter(
            code=first.code, released_at__isnull=False
        ).exists(),
    )

    # --- Bo'shagan kod yangi testga beriladi ---
    freed = first.code
    second = new_exam("Kod sinovi — ikkinchi")
    second.code = freed
    second.save(update_fields=["code"])
    activate_exam(second)
    second.refresh_from_db()
    R.equal("Bo'shagan kod yangi testga berildi", second.code, freed)
    R.check(
        "Kod bo'yicha yangi (faol) test topiladi",
        get_exam_by_code(freed) == second,
    )
    R.check("Eski test o'z kodini saqlab qoladi", Exam.objects.get(pk=first.pk).code == freed)

    # --- Kod boshqa testda bo'lsa, qayta faollashtirishda yangisi beriladi ---
    ok, message = activate_exam(first)
    first.refresh_from_db()
    R.check(f"Eski test yangi kod oldi ({first.code})", ok and first.code != freed)
    R.check("Xabar yangi kodni ko'rsatadi", first.code in message)

    # --- Arxivlash va o'chirish ham kodni bo'shatadi ---
    archive_exam(first)
    R.check(
        "Arxivlash kodni bo'shatadi",
        ReservedExamCode.objects.filter(
            code=first.code, released_at__isnull=False
        ).exists(),
    )

    third = new_exam("Kod sinovi — uchinchi")
    third_code = third.code
    delete_exam(third, force=True)
    R.check(
        "O'chirish kodni bo'shatadi",
        ReservedExamCode.objects.filter(
            code=third_code, released_at__isnull=False
        ).exists(),
    )

    # --- release_code idempotent ---
    R.check("Bo'shatilgan kodni qayta bo'shatish xato bermaydi", not release_code(third_code))
    R.check("Bo'sh kodni bo'shatish xato bermaydi", not release_code(""))


# ==========================================================================
#  20. Savollar qiyinchiligi diagrammasi (faqat adminga)
# ==========================================================================


def test_charts() -> None:
    from apps.attempts.models import Attempt
    from apps.exams.models import Exam
    from apps.exports import charts

    R.head("20. Savollar qiyinchiligi diagrammasi (faqat adminga)")

    # --- Daraja chegaralari ---
    R.equal("0% — oson", charts.difficulty_level(0.0)[0], "Oson")
    R.equal("29.9% — oson", charts.difficulty_level(29.9)[0], "Oson")
    R.equal("30% — o'rtacha", charts.difficulty_level(30.0)[0], "O'rtacha")
    R.equal("60% — qiyin", charts.difficulty_level(60.0)[0], "Qiyin")
    R.equal("80% — juda qiyin", charts.difficulty_level(80.0)[0], "Juda qiyin")
    R.equal("100% — juda qiyin", charts.difficulty_level(100.0)[0], "Juda qiyin")

    exam = (
        Exam.objects.filter(
            statistics__isnull=False, attempts__status=Attempt.Status.SUBMITTED
        )
        .distinct()
        .order_by("-id")
        .first()
    )
    if exam is None:
        R.check("Diagramma uchun test topildi", False, "hisoblangan test yo'q")
        return

    summary = charts.build_summary(exam)
    R.check("Qiyinlik ma'lumotlari yig'ildi", summary.has_data)
    R.check(
        "Foizlar 0–100 oralig'ida",
        all(0.0 <= row.percent <= 100.0 for row in summary.rows),
    )
    R.check("Har bir ustunda rang bor", all(row.color for row in summary.rows))
    R.equal(
        "Darajalar bo'yicha jami savollar soni",
        sum(count for _, _, count in summary.level_counts),
        len(summary.rows),
    )
    R.check("Eng qiyin ro'yxati tartiblangan", summary.hardest == sorted(
        summary.hardest, key=lambda row: row.percent, reverse=True
    ))

    # --- SVG (boshqaruv paneli) ---
    svg = charts.difficulty_svg(summary.rows)
    R.check("SVG yaratildi", svg.startswith("<svg") and svg.endswith("</svg>"))
    R.check("SVG da ustunlar bor", svg.count("<rect") >= len(summary.rows))
    R.equal("Bo'sh ma'lumotda SVG bo'sh", charts.difficulty_svg([]), "")

    # --- PNG (bot orqali adminga) ---
    png = charts.difficulty_png(exam, summary.rows)
    R.check("PNG yaratildi", png.startswith(b"\x89PNG"))
    R.equal("Bo'sh ma'lumotda PNG bo'sh", charts.difficulty_png(exam, []), b"")

    if summary.bins:
        distribution = charts.distribution_svg(summary.bins)
        R.check("Ballar taqsimoti SVG yaratildi", distribution.startswith("<svg"))
        R.check(
            "Taqsimotdagi jami ishtirokchilar soni to'g'ri",
            sum(item.count for item in summary.bins)
            == Attempt.objects.filter(
                exam=exam, status=Attempt.Status.SUBMITTED, ball__isnull=False
            ).count(),
        )
        R.check(
            "Ballar taqsimoti PNG yaratildi",
            charts.distribution_png(exam, summary.bins).startswith(b"\x89PNG"),
        )

    # --- Ishtirokchiga ko'rinmasligi: Mini App javobida yo'q ---
    import json as _json

    from apps.miniapp import serializers

    payload = _json.dumps(
        serializers.statistics_dict(exam.statistics), default=str, ensure_ascii=False
    )
    R.check(
        "Mini App statistikasida savol qiyinliklari yo'q",
        "item_statistics" not in payload and "point_biserial" not in payload,
    )


# ==========================================================================
#  21. Ochiq javoblar (36-45) — matn sifatida tekshiriladi
# ==========================================================================


def test_open_answers() -> None:
    """
    Ona tilida ochiq javob so'z yoki qisqa ibora bo'ladi.

    Tekshiruv `core.answer_check` orqali matn bo'yicha bajariladi va
    matematik klaviatura umuman ishlatilmaydi — shu ikkalasi tekshiriladi.
    """
    from django.test import Client

    from core.answer_check import (
        alternatives,
        compare_answer,
        display_answer,
        normalize_answer,
    )

    R.head("21. Ochiq javoblar (matn tekshiruvi)")

    # --- Normalizatsiya qoidalari ---
    R.equal("Katta harf pastga tushadi", normalize_answer("EGA"), "ega")
    R.equal("Ortiqcha probel yig'iladi", normalize_answer("  bosh   gap "), "bosh gap")
    R.equal("Tinish belgilari olib tashlanadi", normalize_answer("kesim,"), "kesim")
    R.equal(
        "Apostroflar bir xillashadi",
        normalize_answer("o‘zbek"),
        normalize_answer("oʻzbek"),
    )
    R.equal("Chiziqcha bir xillashadi", normalize_answer("ko‘p–ma–ko‘p"),
            normalize_answer("ko‘p-ma-ko‘p"))

    # --- Taqqoslash ---
    R.check("Bir xil javob qabul qilinadi", bool(compare_answer("Ega.", "ega")))
    R.check("Apostrof ko'rinishi to'sqinlik qilmaydi",
            bool(compare_answer("o‘zak", "oʻzak")))
    R.check("Boshqa so'z rad etiladi", not compare_answer("kesim", "ega"))
    R.check("Bo'sh javob rad etiladi", not compare_answer("", "ega"))
    R.check("Bo'sh kalit rad etiladi", not compare_answer("ega", ""))

    # --- Muqobil javoblar ---
    R.equal("Muqobillar ajratiladi", alternatives("ot; ism"), ["ot", "ism"])
    R.check("Birinchi muqobil to'g'ri", bool(compare_answer("ot", "ot; ism")))
    R.check("Ikkinchi muqobil ham to'g'ri", bool(compare_answer("ISM", "ot; ism")))
    R.check("Ro'yxatdan tashqarisi rad etiladi",
            not compare_answer("fe’l", "ot; ism"))

    # --- Sinonimlar vergul bilan sanaladi ---
    R.equal(
        "Vergulli sinonimlar ajratiladi",
        alternatives("osmon, samo, fazo"),
        ["osmon", "samo", "fazo"],
    )
    for given in ("Osmon", "samo", "FAZO."):
        R.check(
            f"Sinonim to'g'ri hisoblanadi: {given!r}",
            bool(compare_answer(given, "osmon, samo, fazo")),
        )
    R.check(
        "Sinonim bo'lmagan javob rad etiladi",
        not compare_answer("bulut", "osmon, samo, fazo"),
    )

    # --- Apostrof bor-yo'qligi javobni xato qilmaydi ---
    for given in ("O‘rta", "O`rta", "Orta", "orta"):
        R.check(
            f"Apostrofga befarq: {given!r}",
            bool(compare_answer(given, "o‘rta")),
        )
    R.check("Tutuq belgisiz javob ham to'g'ri", bool(compare_answer("mano", "ma’no")))

    # --- Baholash zanjiri: kalitdagi sinonim va apostrof (grading.py) ---
    from apps.attempts.grading import grade_open
    from apps.exams.models import Question

    sample = Question(
        kind=Question.Kind.OPEN,
        parts=2,
        answer_a="osmon, samo, fazo",
        answer_b="o‘rta",
    )
    for text_a, text_b, first, second in (
        ("osmon", "o‘rta", True, True),
        ("Samo.", "orta", True, True),   # sinonim + apostrofsiz
        ("FAZO", "O`rta", True, True),
        ("bulut", "orta", False, True),
        ("fazo", "orqa", True, False),
    ):
        score = grade_open(text_a, text_b, sample)
        R.equal(
            f"Baholash: a={text_a!r} b={text_b!r}",
            (score.is_correct_a, score.is_correct_b),
            (first, second),
        )
    R.equal(
        "Ikkala qism to'g'ri bo'lsa 2 ball",
        grade_open("samo", "orta", sample).score,
        2.0,
    )

    # --- Ko'rinish (varaqa ostidagi izoh uchun) ---
    R.equal("Ko'rsatishda harflar saqlanadi", display_answer("  Bosh  Gap "), "Bosh Gap")

    # --- Sonli javob ham matn: «0.5» va «1/2» endi bir xil emas ---
    R.check("Matematik ekvivalentlik qo'llanmaydi",
            not compare_answer("0.5", "1/2"))

    # --- Klaviatura sahifasi olib tashlangan ---
    client = Client()
    R.equal(
        "Matematik klaviatura sahifasi yo'q",
        client.get("/app/klaviatura/").status_code,
        404,
    )

    # --- Kodda va sahifalarda klaviaturadan iz qolmagan ---
    R.check(
        "Umumiy klaviatura fayllari o'chirilgan",
        not (BASE_DIR / "static" / "mathpad").exists(),
    )
    for path in (
        BASE_DIR / "apps/miniapp/static/miniapp/js/app.js",
        BASE_DIR / "apps/dashboard/static/dashboard/js/keysheet.js",
        BASE_DIR / "static/keysheet/keysheet.js",
    ):
        text = path.read_text(encoding="utf-8")
        R.check(
            f"Klaviaturaga murojaat yo'q: {path.name}",
            "MathPad." not in text and "MathField." not in text,
        )

    for name, path in (
        ("Web ilova", BASE_DIR / "apps/miniapp/templates/miniapp/app.html"),
        ("Boshqaruv paneli", BASE_DIR / "apps/dashboard/templates/dashboard/base.html"),
    ):
        markup = path.read_text(encoding="utf-8")
        R.check(f"{name} klaviaturani ulamaydi", "mathpad/" not in markup)

    # --- Javob maydoni oddiy matn kiritishga ochiq ---
    for name, path in (
        ("varaqa", BASE_DIR / "static/keysheet/keysheet.js"),
        ("web ilova", BASE_DIR / "apps/miniapp/static/miniapp/js/app.js"),
        (
            "panel — savollar",
            BASE_DIR / "apps/dashboard/templates/dashboard/exam_questions.html",
        ),
        (
            "panel — savolni tahrirlash",
            BASE_DIR / "apps/dashboard/templates/dashboard/question_edit.html",
        ),
    ):
        text = path.read_text(encoding="utf-8")
        R.check(
            f"Maydon telefon klaviaturasini ochadi: {name}",
            'inputmode="none"' not in text,
        )

    # --- Pastdagi bo'sh joy (telefon: panel kontentni yopib qo'ymasin) ---
    app_css = (BASE_DIR / "apps/miniapp/static/miniapp/css/app.css").read_text(
        encoding="utf-8"
    )
    app_js = (BASE_DIR / "apps/miniapp/static/miniapp/js/app.js").read_text(
        encoding="utf-8"
    )

    R.check("Pastki chekka o'zgaruvchisi bor", "--safe-bot:" in app_css)
    R.check(
        "Telegram bergan chekka hisobga olinadi",
        "--tg-safe-area-inset-bottom" in app_css
        and "--tg-content-safe-area-inset-bottom" in app_css,
    )
    R.check(
        "Faqat `env()` ga tayanmaydi",
        "env(safe-area-inset-bottom, 0px));" not in app_css
        and "+ env(safe-area-inset-bottom, 0px))" not in app_css,
    )
    for name, rule in (
        ("varaq", "padding-bottom: calc(var(--tab-h) + var(--safe-bot))"),
        ("pastki menyu", "padding-bottom: var(--safe-bot)"),
        ("«Yakunlash» paneli", "calc(10px + var(--safe-bot))"),
        ("xabar", "calc(var(--tab-h) + 16px + var(--safe-bot))"),
    ):
        R.check(f"Umumiy chekka ishlatiladi: {name}", rule in app_css)

    R.check(
        "«Yakunlash» ostidagi joy panel balandligidan olinadi",
        "var(--finish-h, 72px)" in app_css,
    )
    R.check("Chekka mijozdan o'qiladi", "function syncSafeArea" in app_js)
    R.check("Panel balandligi o'lchanadi", "function syncFinishBar" in app_js)
    R.check(
        "Telegram hodisalariga ulangan",
        '"safeAreaChanged"' in app_js and '"viewportChanged"' in app_js,
    )


# ==========================================================================
#  22. Javoblar varaqasi (umumiy modul)
# ==========================================================================


def test_keysheet() -> None:
    """Web ilova va panel bitta varaqani ishlatishini tekshiradi."""
    from django.contrib.auth.models import User
    from django.test import Client

    from apps.exams.models import Exam, Question
    from apps.exams.services import create_exam
    from apps.users.models import BotUser

    R.head("22. Javoblar varaqasi (umumiy modul)")

    shared = BASE_DIR / "static" / "keysheet"
    css = shared / "keysheet.css"
    js = shared / "keysheet.js"

    R.check("Umumiy uslub fayli bor", css.is_file())
    R.check("Umumiy modul fayli bor", js.is_file())

    css_text = css.read_text(encoding="utf-8")
    js_text = js.read_text(encoding="utf-8")

    R.check("Varaqada emoji yo'q", not _has_emoji(css_text) and not _has_emoji(js_text))
    R.check("Uslub qobiq palitrasiga moslashadi", "--ks-accent" in css_text)
    R.check("A-D va A-F uslublari bor", ".choices.cols-6" in css_text)
    R.check("Tashqi interfeys ochilgan", "global.KeySheet" in js_text)

    # --- Reja: milliy shablon va oddiy test ---
    R.check("Milliy reja 33-35 ni ajratadi",
            '"33"' not in js_text and "multi: { from: 33, to: 35 }" in js_text)
    R.check("Ochiq savollar 36-45", "open: { from: 36, to: 45 }" in js_text)
    R.check(
        "36-39 bitta javobli deb belgilangan",
        "openSingle: { from: 36, to: 39 }" in js_text,
    )
    R.check("Varaqa qismlar sonini hisobga oladi", "function openParts" in js_text)

    # --- Ikkala qobiq ham shu modulni ulaydi ---
    app_html = (BASE_DIR / "apps/miniapp/templates/miniapp/app.html").read_text(encoding="utf-8")
    panel_html = (
        BASE_DIR / "apps/dashboard/templates/dashboard/base.html"
    ).read_text(encoding="utf-8")
    for name, text in (("web ilova", app_html), ("panel", panel_html)):
        R.check(f"Varaqa uslubi ulangan: {name}", "keysheet/keysheet.css" in text)
        R.check(f"Varaqa moduli ulangan: {name}", "keysheet/keysheet.js" in text)

    # --- Web ilovada eski nusxa qolmagan ---
    app_js = (BASE_DIR / "apps/miniapp/static/miniapp/js/app.js").read_text(encoding="utf-8")
    R.check("Web ilova umumiy varaqani ishlatadi", "KeySheet.mount(" in app_js)
    R.check(
        "Web ilovada eski varaqa kodi qolmagan",
        "renderKeySheet" not in app_js and "collectSheetKeys" not in app_js,
    )

    # --- Panel sahifalari ---
    User.objects.filter(username="keysheet_admin").delete()
    User.objects.create_superuser("keysheet_admin", "ks@test.local", "KeySheet12345!")
    client = Client()
    R.check("Admin tizimga kirdi",
            client.login(username="keysheet_admin", password="KeySheet12345!"))

    page = client.get("/panel/testlar/yangi/").content.decode("utf-8", "replace")
    R.check("Yangi test sahifasida varaqa bor", 'id="key-sheet"' in page)
    R.check("Rejim tugmalari bor", 'data-keymode="sheet"' in page)
    R.check("Matn rejimi ham qoldi", 'id="key-text"' in page)
    R.check("To'ldirilganlik hisoblagichi bor", 'id="key-progress"' in page)

    owner = BotUser.objects.get(telegram_id=1000)
    national = create_exam(
        owner=owner,
        title="Varaqa uchun milliy namuna",
        exam_type=Exam.Type.RASCH_FREE,
        national_template=True,
    )
    single = national.questions.filter(kind=Question.Kind.SINGLE).first()
    multi = national.questions.filter(kind=Question.Kind.MULTI).first()
    # 36 — bitta javobli, 40 — a) va b) li ochiq savol.
    open_q = national.questions.filter(kind=Question.Kind.OPEN, order=40).first()
    open_single = national.questions.filter(kind=Question.Kind.OPEN, order=36).first()
    R.check("Milliy shablonda uchala tur bor",
            bool(single) and bool(multi) and bool(open_q))

    rows = client.get(f"/panel/testlar/{national.pk}/savollar/").content.decode(
        "utf-8", "replace"
    )
    R.check("Jadvalda A-D tugmalari", 'data-letters="ABCD"' in rows)
    R.check("Jadvalda A-F tugmalari", 'data-letters="ABCDEF"' in rows)
    R.check("40–45 da ikkita maydon",
            f'name="key_{open_q.id}_a"' in rows and f'name="key_{open_q.id}_b"' in rows)
    R.check(
        "36–39 da faqat bitta maydon",
        f'name="key_{open_single.id}_a"' in rows
        and f'name="key_{open_single.id}_b"' not in rows,
    )

    edit_multi = client.get(
        f"/panel/testlar/{national.pk}/savollar/{multi.pk}/"
    ).content.decode("utf-8", "replace")
    R.check("33-35 tahririda A-F tugmalari", 'data-letters="ABCDEF"' in edit_multi)

    edit_open = client.get(
        f"/panel/testlar/{national.pk}/savollar/{open_q.pk}/"
    ).content.decode("utf-8", "replace")
    R.check("Ochiq savol tahririda varaqa maydonlari",
            'class="answer-field"' in edit_open and "data-ks-check" in edit_open)

    # --- Kalitlarni saqlash: harf va ikkita ochiq maydon ---
    response = client.post(
        f"/panel/testlar/{national.pk}/savollar/",
        {
            f"key_{single.id}": "C",
            f"key_{multi.id}": "E",
            f"key_{open_q.id}_a": "sqrt(2)",
            f"key_{open_q.id}_b": "pi/6",
            f"diff_{single.id}": "0.55",
        },
    )
    R.check("Kalitlar saqlandi", response.status_code in (200, 302))
    single.refresh_from_db()
    multi.refresh_from_db()
    open_q.refresh_from_db()
    R.equal("A-D kaliti yozildi", single.correct_key, "C")
    R.equal("A-F kaliti yozildi", multi.correct_key, "E")
    R.equal("Ochiq a) yozildi", open_q.answer_a, "sqrt(2)")
    R.equal("Ochiq b) yozildi", open_q.answer_b, "pi/6")
    R.equal("Ikki qismli deb belgilandi", open_q.parts, 2)
    R.equal("Qiyinlik ham saqlandi", round(single.difficulty, 2), 0.55)

    national.delete()


# ==========================================================================
#  23. Reklama (ommaviy xabar): matn + rasm + tugmalar
# ==========================================================================


class _FakePhoto:
    """Telegram qaytaradigan rasm haqidagi ma'lumot."""

    def __init__(self, file_id: str) -> None:
        self.file_id = file_id


class _FakeSentMessage:
    """`send_photo` javobining soddalashtirilgan ko'rinishi."""

    def __init__(self, photo=None) -> None:
        self.photo = photo


class _FakeBot:
    """
    Telegram o'rniga ishlaydigan soxta bot.

    Reklama yuborishda faqat `send_message` va `send_photo` chaqiriladi,
    shuning uchun shu ikkitasi yetarli.
    """

    FILE_ID = "SINOV_FILE_ID_123"

    def __init__(self, blocked=(), broken=()) -> None:
        self.messages: list[dict] = []
        self.photos: list[dict] = []
        self.blocked = set(blocked)
        self.broken = set(broken)
        self.count = 0

    # ----------------------------------------------------------------
    def _guard(self, chat_id: int) -> None:
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

        self.count += 1
        self.on_send(chat_id)
        if chat_id in self.blocked:
            raise TelegramForbiddenError(None, "bot was blocked by the user")
        if chat_id in self.broken:
            raise TelegramBadRequest(None, "chat not found")

    def on_send(self, chat_id: int) -> None:
        """Merosxo'r sinflar uchun ilgak."""

    # ----------------------------------------------------------------
    async def send_message(
        self, chat_id, text=None, parse_mode="HTML", reply_markup=None, **kwargs
    ):
        self._guard(chat_id)
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text or "",
                "parse_mode": parse_mode,
                "markup": reply_markup,
            }
        )
        return _FakeSentMessage()

    async def send_photo(
        self, chat_id, photo, caption=None, parse_mode="HTML", reply_markup=None, **kwargs
    ):
        self._guard(chat_id)
        self.photos.append(
            {
                "chat_id": chat_id,
                "photo": photo,
                "caption": caption or "",
                "parse_mode": parse_mode,
                "markup": reply_markup,
            }
        )
        return _FakeSentMessage([_FakePhoto(self.FILE_ID)])


def test_broadcast() -> None:
    import asyncio

    from io import BytesIO

    from django.contrib.auth.models import User
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.test import Client
    from django.utils import timezone as dj_timezone

    from apps.broadcasts import formatting as fmt
    from apps.broadcasts import services as broadcast_services
    from apps.broadcasts.models import Broadcast, BroadcastDelivery
    from apps.dashboard.forms import BroadcastForm
    from apps.users.models import BotUser
    from bot.tasks import broadcast as worker

    R.head("23. Reklama: matn, rasm va tugmali xabar")

    # ------------------------------------------------------------------
    #  Matnni tayyorlash
    # ------------------------------------------------------------------
    R.equal(
        "Ruxsat etilgan teglar saqlanadi",
        fmt.sanitize_html("Salom <b>dunyo</b>"),
        "Salom <b>dunyo</b>",
    )
    R.equal(
        "Ruxsatsiz teg oddiy matnga aylanadi",
        fmt.sanitize_html("<script>alert(1)</script>"),
        "&lt;script&gt;alert(1)&lt;/script&gt;",
    )
    R.equal(
        "Yolg'iz «<» ekranlanadi",
        fmt.sanitize_html("5 < 7 & 8"),
        "5 &lt; 7 &amp; 8",
    )
    R.equal(
        "Tozalash takrorlanganda o'zgarmaydi",
        fmt.sanitize_html(fmt.sanitize_html("5 < 7 & 8")),
        "5 &lt; 7 &amp; 8",
    )
    R.equal(
        "Havola tegi saqlanadi",
        fmt.sanitize_html('<a href="https://t.me/x">bu yerda</a>'),
        '<a href="https://t.me/x">bu yerda</a>',
    )
    R.equal("«br» qator uzilishiga aylanadi", fmt.sanitize_html("a<br>b"), "a\nb")
    R.raises(
        "Yopilmagan teg xato beradi",
        lambda: fmt.sanitize_html("<b>ochiq qoldi"),
        fmt.FormatError,
    )
    R.raises(
        "Noto'g'ri tartibda yopilgan teg xato beradi",
        lambda: fmt.sanitize_html("<b><i>matn</b></i>"),
        fmt.FormatError,
    )
    R.raises(
        "Xavfli havola rad etiladi",
        lambda: fmt.sanitize_html('<a href="javascript:alert(1)">x</a>'),
        fmt.FormatError,
    )
    R.equal(
        "Uzunlik teglarsiz hisoblanadi",
        fmt.visible_length("<b>Salom</b>"),
        5,
    )
    R.equal("Xabar chegarasi 4096", fmt.TEXT_LIMIT, 4096)
    R.equal("Rasm izohi chegarasi 1024", fmt.CAPTION_LIMIT, 1024)

    # ------------------------------------------------------------------
    #  Tugmalar
    # ------------------------------------------------------------------
    rows = fmt.parse_buttons(
        "Kanal | https://t.me/Burgutali\n"
        "Sayt | https://burgutali.uz || Bot | https://t.me/sinov_bot"
    )
    R.equal("Tugmalar ikki qatorga bo'lindi", len(rows), 2)
    R.equal("Ikkinchi qatorda ikkita tugma", len(rows[1]), 2)
    R.equal("Tugma matni o'qildi", rows[0][0]["text"], "Kanal")
    R.equal("Tugma havolasi o'qildi", rows[0][0]["url"], "https://t.me/Burgutali")
    R.equal(
        "Tugmalar matnga qaytariladi",
        fmt.buttons_to_text(rows).splitlines()[0],
        "Kanal | https://t.me/Burgutali",
    )
    R.raises(
        "Havolasiz tugma rad etiladi",
        lambda: fmt.parse_buttons("Kanal - https://t.me/x"),
        fmt.FormatError,
    )
    R.raises(
        "Noto'g'ri sxemali havola rad etiladi",
        lambda: fmt.parse_buttons("Kanal | ftp://fayl.uz"),
        fmt.FormatError,
    )
    R.raises(
        "Bir qatorda to'rtta tugma rad etiladi",
        lambda: fmt.parse_buttons(
            "a | https://a.uz || b | https://b.uz || c | https://c.uz || d | https://d.uz"
        ),
        fmt.FormatError,
    )

    # ------------------------------------------------------------------
    #  Sinov foydalanuvchilari
    # ------------------------------------------------------------------
    BotUser.objects.filter(telegram_id__in=[900001, 900002, 900003]).delete()
    BotUser.objects.create(
        telegram_id=900001, tg_first_name="Reklama qabul qiluvchi",
        is_registered=True, last_seen_at=dj_timezone.now(),
    )
    blocker = BotUser.objects.create(
        telegram_id=900002, tg_first_name="Botni bloklagan", is_registered=True
    )
    banned = BotUser.objects.create(
        telegram_id=900003, tg_first_name="Panelda bloklangan", is_blocked=True
    )

    reachable = BotUser.objects.filter(is_blocked=False).count()
    R.equal(
        "Auditoriya bloklanganlarni hisobga olmaydi",
        broadcast_services.audience_count(Broadcast.Audience.ALL),
        reachable,
    )
    R.check(
        "Bloklangan foydalanuvchi auditoriyaga tushmaydi",
        not broadcast_services.audience_queryset(Broadcast.Audience.ALL)
        .filter(pk=banned.pk)
        .exists(),
    )
    R.check(
        "«Ro'yxatdan o'tganlar» auditoriyasi kichikroq yoki teng",
        broadcast_services.audience_count(Broadcast.Audience.REGISTERED) <= reachable,
    )

    # ------------------------------------------------------------------
    #  Panel orqali yaratish
    # ------------------------------------------------------------------
    User.objects.filter(username="selftest_admin").delete()
    User.objects.create_superuser("selftest_admin", "admin@test.local", "SelfTest12345!")
    client = Client()
    R.check(
        "Admin panelga kirdi",
        client.login(username="selftest_admin", password="SelfTest12345!"),
    )

    R.equal(
        "Reklama ro'yxati ochiladi", client.get("/panel/reklama/").status_code, 200
    )
    R.equal(
        "Yangi reklama formasi ochiladi",
        client.get("/panel/reklama/yangi/").status_code,
        200,
    )
    R.check(
        "Panel menyusida «Reklama» bo'limi bor",
        "Reklama" in client.get("/panel/").content.decode("utf-8", "replace"),
    )

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (600, 400), (29, 78, 126)).save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    response = client.post(
        "/panel/reklama/yangi/",
        {
            "title": "Sinov reklamasi",
            "text": "Salom <b>do'stlar</b>! 5 < 7 <script>x</script>",
            "buttons_raw": (
                "Kanalga o'tish | https://t.me/Burgutali\n"
                "Sayt | https://burgutali.uz || Bot | https://t.me/sinov_bot"
            ),
            "audience": Broadcast.Audience.ALL,
            "exam": "",
            "image": SimpleUploadedFile("reklama.png", image_bytes, content_type="image/png"),
        },
    )
    R.check("Reklama saqlandi (redirect)", response.status_code in (301, 302))

    broadcast = Broadcast.objects.order_by("-id").first()
    R.check("Reklama bazaga yozildi", broadcast is not None)
    R.check("Qalin teg saqlandi", "<b>do'stlar</b>" in broadcast.text)
    R.check("Ruxsatsiz teg ekranlandi", "&lt;script&gt;" in broadcast.text)
    R.equal("Uchta tugma saqlandi", broadcast.button_count, 3)
    R.equal("Tugmalar ikki qatorda", len(broadcast.button_rows), 2)
    R.check("Rasm biriktirildi", broadcast.has_image)
    R.equal("Yangi xabar qoralama holatida", broadcast.status, Broadcast.Status.DRAFT)
    R.check("Xabar tahrirlash uchun ochiq", broadcast.is_editable)

    detail = client.get(f"/panel/reklama/{broadcast.pk}/")
    R.equal("Reklama tafsiloti ochiladi", detail.status_code, 200)
    detail_html = detail.content.decode("utf-8", "replace")
    R.check(
        "Tafsilotda tugma havolasi ko'rinadi",
        "https://t.me/Burgutali" in detail_html,
    )
    R.check("Tafsilotda rasm ko'rinadi", "/media/broadcasts/" in detail_html)
    R.check(
        "Ruxsatsiz teg sahifada matn bo'lib qoladi",
        "<script>x</script>" not in detail_html,
    )
    R.equal(
        "Tahrirlash sahifasi ochiladi",
        client.get(f"/panel/reklama/{broadcast.pk}/tahrir/").status_code,
        200,
    )

    # --- Forma tekshiruvlari ---
    empty_form = BroadcastForm(data={"text": "", "audience": Broadcast.Audience.ALL})
    R.check("Bo'sh xabar qabul qilinmaydi", not empty_form.is_valid())

    long_form = BroadcastForm(
        data={
            "text": "a" * (fmt.CAPTION_LIMIT + 10),
            "audience": Broadcast.Audience.ALL,
            "buttons_raw": "",
        },
        files={
            "image": SimpleUploadedFile("katta.png", image_bytes, content_type="image/png")
        },
    )
    R.check(
        "Rasm izohi 1024 belgidan oshsa xato beriladi",
        not long_form.is_valid() and "text" in long_form.errors,
    )

    bad_buttons = BroadcastForm(
        data={
            "text": "Matn",
            "audience": Broadcast.Audience.ALL,
            "buttons_raw": "Kanal | havola-emas",
        }
    )
    R.check(
        "Noto'g'ri tugma formada ushlanadi",
        not bad_buttons.is_valid() and "buttons_raw" in bad_buttons.errors,
    )

    no_exam = BroadcastForm(
        data={"text": "Matn", "audience": Broadcast.Audience.EXAM, "buttons_raw": ""}
    )
    R.check(
        "«Test ishtirokchilari» uchun test ko'rsatilishi shart",
        not no_exam.is_valid() and "exam" in no_exam.errors,
    )

    # ------------------------------------------------------------------
    #  Navbatga qo'yish
    # ------------------------------------------------------------------
    response = client.post(f"/panel/reklama/{broadcast.pk}/amal/yuborish/")
    R.check("Yuborish buyrug'i qabul qilindi", response.status_code in (301, 302))
    broadcast.refresh_from_db()
    R.equal("Reklama navbatga tushdi", broadcast.status, Broadcast.Status.QUEUED)
    R.equal("Yuborish ro'yxati tuzildi", broadcast.total, reachable)
    R.check(
        "Bloklangan foydalanuvchi ro'yxatga kirmadi",
        not BroadcastDelivery.objects.filter(
            broadcast=broadcast, telegram_id=banned.telegram_id
        ).exists(),
    )
    R.check(
        "Yuborish holati JSON ko'rinishida beriladi",
        client.get(f"/panel/reklama/{broadcast.pk}/holat/").json()["total"] == reachable,
    )

    # ------------------------------------------------------------------
    #  Bot yuboradi
    # ------------------------------------------------------------------
    R.close("Tezlik sekundiga 20 ta xabar", worker.MESSAGES_PER_SECOND, 20.0, 0.001)
    R.equal("Bir bo'lakda 50 ta xabar", worker.BATCH_SIZE, 50)
    worker.SEND_PAUSE = 0.0  # sinovda kutib o'tirmaymiz

    bot = _FakeBot(blocked={blocker.telegram_id})
    R.check("Bot navbatdagi reklamani oldi", asyncio.run(worker.process_queue(bot)))

    broadcast.refresh_from_db()
    R.equal("Yuborish yakunlandi", broadcast.status, Broadcast.Status.DONE)
    R.equal("Yetkazilganlar soni", broadcast.sent, reachable - 1)
    R.equal("Botni bloklaganlar soni", broadcast.blocked, 1)
    R.equal("Yuborilmaganlar yo'q", broadcast.failed, 0)
    R.equal("Jarayon 100 foiz", broadcast.progress_percent, 100)
    R.equal("Barcha xabar rasm bilan ketdi", len(bot.photos), reachable - 1)
    R.check(
        "Yakunda adminlarga hisobot yuborildi",
        any("Reklama yuborildi" in item["text"] for item in bot.messages),
    )

    first_photo = bot.photos[0]
    R.check(
        "Birinchi xabarda rasm faylini yuklandi",
        not isinstance(first_photo["photo"], str),
    )
    R.check(
        "Keyingi xabarlarda Telegram fayl belgisi ishlatildi",
        isinstance(bot.photos[-1]["photo"], str),
    )
    R.equal("Fayl belgisi saqlandi", broadcast.image_file_id, _FakeBot.FILE_ID)
    R.check("Izoh xabar matni bilan bir xil", first_photo["caption"] == broadcast.text)
    R.check("Tugmalar biriktirildi", first_photo["markup"] is not None)
    R.equal(
        "Klaviatura ikki qatorli", len(first_photo["markup"].inline_keyboard), 2
    )
    R.equal(
        "Ikkinchi qatorda ikkita tugma",
        len(first_photo["markup"].inline_keyboard[1]),
        2,
    )
    R.equal(
        "Tugma havolasi to'g'ri",
        first_photo["markup"].inline_keyboard[0][0].url,
        "https://t.me/Burgutali",
    )

    R.check(
        "Bloklagan foydalanuvchi alohida belgilandi",
        BroadcastDelivery.objects.filter(
            broadcast=broadcast,
            telegram_id=blocker.telegram_id,
            status=BroadcastDelivery.Status.BLOCKED,
        ).exists(),
    )
    R.check(
        "Navbat bo'shadi",
        not asyncio.run(worker.process_queue(_FakeBot())),
    )

    # ------------------------------------------------------------------
    #  To'xtatish va davom ettirish
    # ------------------------------------------------------------------
    second = Broadcast.objects.create(
        title="To'xtatiladigan xabar",
        text="Ikkinchi xabar",
        audience=Broadcast.Audience.ALL,
        status=Broadcast.Status.DRAFT,
    )
    broadcast_services.queue_broadcast(second)
    worker.BATCH_SIZE = 2

    class _CancellingBot(_FakeBot):
        """Ikkinchi xabardan keyin yuborishni to'xtatadi."""

        def on_send(self, chat_id: int) -> None:
            if self.count == 2:
                Broadcast.objects.filter(pk=second.pk).update(
                    status=Broadcast.Status.CANCELLED
                )

    asyncio.run(worker.process_queue(_CancellingBot()))
    second.refresh_from_db()
    R.equal("Xabar to'xtatilgan holatda", second.status, Broadcast.Status.CANCELLED)
    R.equal("Ikkita xabar yuborilib ulgurdi", second.sent, 2)
    R.check(
        "Qolganlari navbatda qoldi",
        BroadcastDelivery.objects.filter(
            broadcast=second, status=BroadcastDelivery.Status.PENDING
        ).count()
        == second.total - 2,
    )

    resumed = _FakeBot()
    broadcast_services.queue_broadcast(second)
    asyncio.run(worker.process_queue(resumed))
    second.refresh_from_db()
    R.equal("Davom ettirilgach yakunlandi", second.status, Broadcast.Status.DONE)
    R.equal("Hammaga yetib bordi", second.sent, second.total)
    delivered_again = [
        item for item in resumed.messages if item["text"] == "Ikkinchi xabar"
    ]
    R.equal(
        "Avval olganlarga takror yuborilmadi", len(delivered_again), second.total - 2
    )
    worker.BATCH_SIZE = 50

    # ------------------------------------------------------------------
    #  Matn Telegram tomonidan rad etilsa — teglarsiz yuboriladi
    # ------------------------------------------------------------------
    class _PickyBot(_FakeBot):
        """HTML matnni qabul qilmaydigan Telegram."""

        async def send_message(
            self, chat_id, text=None, parse_mode="HTML", reply_markup=None, **kwargs
        ):
            from aiogram.exceptions import TelegramBadRequest

            if parse_mode == "HTML":
                raise TelegramBadRequest(None, "can't parse entities: unexpected tag")
            return await super().send_message(
                chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup
            )

    picky_target = BotUser.objects.get(telegram_id=900001)
    third = Broadcast.objects.create(
        title="Teglar bilan xabar",
        text="<b>Qalin</b> matn",
        audience=Broadcast.Audience.ADMINS,
        status=Broadcast.Status.DRAFT,
    )
    BroadcastDelivery.objects.create(
        broadcast=third, user=picky_target, telegram_id=picky_target.telegram_id
    )
    Broadcast.objects.filter(pk=third.pk).update(
        status=Broadcast.Status.QUEUED, total=1
    )

    picky = _PickyBot()
    asyncio.run(worker.process_queue(picky))
    third.refresh_from_db()
    R.equal("Teglarsiz bo'lsa ham yetkazildi", third.sent, 1)
    R.equal("Ikkinchi urinish teglarsiz ketdi", picky.messages[0]["parse_mode"], None)
    R.equal("Matn teglarsiz yuborildi", picky.messages[0]["text"], "Qalin matn")

    # ------------------------------------------------------------------
    #  Sinov yuborish
    # ------------------------------------------------------------------
    broadcast_services.request_test_send(broadcast, 900001)
    test_bot = _FakeBot()
    R.check("Sinov xabari yuborildi", asyncio.run(worker.process_test_sends(test_bot)))
    broadcast.refresh_from_db()
    R.check("Sinov vaqti belgilandi", broadcast.test_sent_at is not None)
    R.equal("Sinov xatosi yo'q", broadcast.test_error, "")
    targets = {item["chat_id"] for item in test_bot.messages + test_bot.photos}
    R.equal("Sinov faqat bitta odamga ketdi", targets, {900001})
    R.equal("Sinovda ham rasm yuborildi", len(test_bot.photos), 1)
    R.check(
        "Sinov ikkinchi marta takrorlanmaydi",
        not asyncio.run(worker.process_test_sends(_FakeBot())),
    )

    # ------------------------------------------------------------------
    #  Qoralamaga qaytarish va o'chirish
    # ------------------------------------------------------------------
    client.post(f"/panel/reklama/{second.pk}/amal/qoralama/")
    second.refresh_from_db()
    R.equal("Qoralamaga qaytdi", second.status, Broadcast.Status.DRAFT)
    R.equal("Yuborish tarixi tozalandi", second.total, 0)
    R.check(
        "Yuborish ro'yxati o'chirildi",
        not BroadcastDelivery.objects.filter(broadcast=second).exists(),
    )

    client.post(f"/panel/reklama/{second.pk}/amal/nusxa/")
    R.check(
        "Nusxa yaratildi",
        Broadcast.objects.filter(title__endswith="(nusxa)").exists(),
    )

    client.post(f"/panel/reklama/{third.pk}/amal/ochirish/")
    R.check(
        "Reklama o'chirildi", not Broadcast.objects.filter(pk=third.pk).exists()
    )
    R.check(
        "O'chirilgan reklamaning yuborishlari ham ketdi",
        not BroadcastDelivery.objects.filter(broadcast_id=third.pk).exists(),
    )

    # --- Yuborilayotgan xabarni o'chirib bo'lmaydi ---
    Broadcast.objects.filter(pk=broadcast.pk).update(status=Broadcast.Status.SENDING)
    client.post(f"/panel/reklama/{broadcast.pk}/amal/ochirish/")
    R.check(
        "Yuborilayotgan xabar o'chirilmaydi",
        Broadcast.objects.filter(pk=broadcast.pk).exists(),
    )
    Broadcast.objects.filter(pk=broadcast.pk).update(status=Broadcast.Status.DONE)

    # --- Anonim foydalanuvchi kira olmaydi ---
    anonymous = Client()
    R.check(
        "Reklama bo'limi anonim foydalanuvchiga berilmaydi",
        anonymous.get("/panel/reklama/").status_code in {302, 403},
    )
    R.check(
        "Reklama yuborishni anonim foydalanuvchi boshlay olmaydi",
        anonymous.post(f"/panel/reklama/{broadcast.pk}/amal/yuborish/").status_code
        in {302, 403},
    )


# ==========================================================================
#  Asosiy oqim
# ==========================================================================


# ==========================================================================
#  24. Esse balli va e'lon uchun qo'shimcha qatorlar
# ==========================================================================


def test_essay_and_phantoms() -> None:
    from django.contrib.auth.models import User
    from django.test import Client

    from apps.attempts import services as attempt_services
    from apps.attempts.models import Attempt, PhantomParticipant
    from apps.attempts.services import (
        EssayError,
        create_phantoms,
        parse_essay_ball,
        public_ranking,
        save_answer,
        set_essay_ball,
        start_attempt,
        submit_attempt,
    )
    from apps.certificates.services import check_eligibility
    from apps.exams.models import Exam
    from apps.exams.services import (
        activate_exam,
        apply_single_keys,
        close_exam,
        create_exam,
        publish_results,
        report_recipients,
    )
    from apps.rasch.scoring import combine_with_essay
    from apps.rasch.services import calculate_exam
    from apps.users.models import BotUser
    from core import constants as C

    R.head("24. Esse balli va e'lon uchun qo'shimcha qatorlar")

    # ------------------------------------------------------------------
    #  24.1. Qo'shish formulasi
    # ------------------------------------------------------------------
    R.close(
        "(60 + 80) / 2 = 70",
        combine_with_essay(60.0, 80.0, max_ball=C.MAX_BALL, essay_max_ball=C.MAX_BALL),
        70.0,
        0.01,
    )
    R.equal(
        "Esse kiritilmasa test balli qoladi",
        combine_with_essay(63.25, None, max_ball=C.MAX_BALL),
        63.25,
    )
    R.equal(
        "Test balli yo'q bo'lsa natija ham yo'q",
        combine_with_essay(None, 50.0, max_ball=C.MAX_BALL),
        None,
    )
    # Esse 100 ballik shkalada: 50 -> 45.07 -> (60 + 45.07) / 2
    R.close(
        "Boshqa shkaladagi esse moslashtiriladi",
        combine_with_essay(60.0, 50.0, max_ball=C.MAX_BALL, essay_max_ball=100.0),
        (60.0 + C.MAX_BALL / 2) / 2,
        0.02,
    )
    R.equal(
        "Esse maksimal balldan oshsa shkala chetiga qisiladi",
        combine_with_essay(90.14, 500.0, max_ball=C.MAX_BALL, essay_max_ball=C.MAX_BALL),
        90.14,
    )

    # ------------------------------------------------------------------
    #  24.2. Kiritilgan qiymatni tekshirish
    # ------------------------------------------------------------------
    owner, _ = BotUser.objects.get_or_create(
        telegram_id=4100, defaults={"full_name": "Esse Yaratuvchi", "is_registered": True}
    )
    exam = create_exam(
        owner=owner,
        title="ESSE VA REYTING SINOVI",
        exam_type=Exam.Type.RASCH_FREE,
        question_count=10,
        show_results=True,
    )
    apply_single_keys(exam, ["A"] * 10)
    exam.essay_enabled = True
    exam.essay_max_ball = C.MAX_BALL
    exam.save(update_fields=["essay_enabled", "essay_max_ball"])
    activate_exam(exam)
    exam.refresh_from_db()

    R.equal("Bo'sh qiymat — baholanmagan", parse_essay_ball("", exam), None)
    R.equal("Vergul o'nlik ajratkichi", parse_essay_ball("7,5", exam), 7.5)
    R.raises("Harf qabul qilinmaydi", lambda: parse_essay_ball("abc", exam), EssayError)
    R.raises("Manfiy ball rad etiladi", lambda: parse_essay_ball("-1", exam), EssayError)
    R.raises(
        "Maksimaldan katta ball rad etiladi",
        lambda: parse_essay_ball("999", exam),
        EssayError,
    )

    # ------------------------------------------------------------------
    #  24.3. Qatnashchilar va yakuniy ball
    # ------------------------------------------------------------------
    questions = list(exam.questions.order_by("order"))
    attempts: list[Attempt] = []
    for index in range(6):
        user, _ = BotUser.objects.get_or_create(
            telegram_id=4200 + index,
            defaults={
                "full_name": f"Esse Qatnashchi {index + 1}",
                "phone": "+998900000000",
                "is_registered": True,
            },
        )
        attempt = start_attempt(user, exam)
        # Har xil natija: birinchi qatnashchi ko'proq topadi.
        correct = 9 - index
        for position, question in enumerate(questions):
            save_answer(attempt, question, selected="A" if position < correct else "B")
        attempts.append(submit_attempt(attempt))

    close_exam(exam)
    calculate_exam(exam)
    exam.refresh_from_db()

    first = Attempt.objects.get(pk=attempts[0].pk)
    R.check("Test balli hisoblandi", first.ball is not None)
    R.equal(
        "Esse kiritilmaguncha yakuniy ball test balliga teng",
        first.final_ball,
        first.ball,
    )
    R.check("Esse hali baholanmagan deb belgilanadi", first.essay_pending)

    # --- Esse ballini kiritamiz ---
    test_ball = float(first.ball)
    set_essay_ball(first, 90.14)
    first.refresh_from_db()
    R.close(
        "Yakuniy ball = (test + esse) / 2",
        first.final_ball,
        round((test_ball + 90.14) / 2, 2),
        0.01,
    )
    R.equal(
        "Daraja yakuniy ball bo'yicha",
        first.grade,
        C.grade_for_ball(first.final_ball),
    )
    R.check("Esse baholandi deb belgilandi", not first.essay_pending)
    R.equal("display_ball yakuniy ballni ko'rsatadi", first.display_ball, f"{first.final_ball:.2f}")

    # --- Eng past natijali qatnashchiga yuqori esse: reyting o'zgaradi ---
    last = Attempt.objects.get(pk=attempts[-1].pk)
    R.check("Oxirgi qatnashchi quyi o'rinda edi", (last.rank or 0) > 1)
    set_essay_ball(last, 90.14)
    last.refresh_from_db()
    R.check(
        "Esse balli reytingni qayta chiqaradi",
        (last.rank or 99) < (Attempt.objects.get(pk=attempts[2].pk).rank or 0),
    )

    # --- Esse balli o'chirilsa yakuniy ball test balliga qaytadi ---
    set_essay_ball(last, None)
    last.refresh_from_db()
    R.equal("Esse o'chirilsa yakuniy ball test balli", last.final_ball, last.ball)

    # --- To'plam bo'lib kiritish ---
    changed = attempt_services.set_essay_balls(
        exam, {attempts[i].pk: 45.0 for i in range(1, 4)}
    )
    R.equal("Uchta esse balli birdaniga saqlandi", changed, 3)
    done, total = attempt_services.essay_progress(exam)
    R.equal("Baholanganlar soni", done, 4)
    R.equal("Jami topshirganlar", total, 6)

    # ------------------------------------------------------------------
    #  24.4. Esse baholanmaguncha sertifikat berilmaydi
    # ------------------------------------------------------------------
    pending = Attempt.objects.get(pk=attempts[4].pk)
    paid = create_exam(
        owner=owner,
        title="ESSE SERTIFIKAT SINOVI",
        exam_type=Exam.Type.RASCH_PAID,
        question_count=5,
        certificate_enabled=True,
    )
    paid.essay_enabled = True
    paid.status = Exam.Status.PUBLISHED
    paid.certificate_scope = Exam.CertificateScope.ALL
    paid.save(update_fields=["essay_enabled", "status", "certificate_scope"])
    pending.exam = paid
    check = check_eligibility(pending)
    R.check("Esse baholanmagan bo'lsa sertifikat berilmaydi", not check.ok)
    R.check("Sabab esse haqida", "sse" in check.reason)

    # ------------------------------------------------------------------
    #  24.5. E'lon uchun qo'shimcha (soxta) qatorlar
    # ------------------------------------------------------------------
    exam.refresh_from_db()
    real_total = attempt_services.participants_count(exam)
    real_names = set(
        Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED)
        .values_list("full_name", flat=True)
    )
    real_balls = [
        a.result_ball
        for a in Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED)
        if a.result_ball is not None
    ]

    created = create_phantoms(exam, 10, seed=42)
    R.equal("10 ta soxta qator yaratildi", created, 10)

    phantoms = list(PhantomParticipant.objects.filter(exam=exam))
    names = [p.full_name for p in phantoms]
    R.equal("Ismlar takrorlanmaydi", len(set(names)), 10)
    R.check(
        "Ismlar haqiqiy qatnashchilarniki bilan to'qnashmaydi",
        not (set(names) & real_names),
    )
    R.check("Ismlar ikki so'zdan iborat", all(len(n.split()) >= 2 for n in names))
    R.check(
        "Ballar haqiqiy natijalar oralig'ida",
        all(min(real_balls) - 0.01 <= p.ball <= max(real_balls) + 0.01 for p in phantoms),
    )
    R.check("Daraja ball bo'yicha to'g'ri", all(
        p.grade == C.grade_for_ball(p.ball) for p in phantoms
    ))

    # --- Hisob-kitobga ta'sir qilmaydi ---
    R.equal(
        "Qatnashchilar soni o'zgarmaydi",
        attempt_services.participants_count(exam),
        real_total,
    )
    calculate_exam(exam)
    exam.refresh_from_db()
    R.equal(
        "Statistikaga kirmaydi",
        exam.statistics.participants,
        real_total,
    )
    R.equal(
        "Soxta qatorda urinish yo'q (sertifikat berilmaydi)",
        Attempt.objects.filter(exam=exam).exclude(full_name__in=real_names).count(),
        0,
    )

    # --- Umumiy ro'yxat ---
    rows = public_ranking(exam)
    R.equal("E'lon ro'yxatida hamma qatorlar bor", len(rows), real_total + 10)
    R.equal("Birinchi o'rin 1 dan boshlanadi", rows[0].rank, 1)
    R.check(
        "Ro'yxat ball bo'yicha kamayib boradi",
        all(
            (rows[i].ball or 0) >= (rows[i + 1].ball or 0)
            for i in range(len(rows) - 1)
        ),
    )
    R.equal(
        "Soxta qatorlar belgilangan",
        sum(1 for row in rows if row.is_phantom),
        10,
    )
    R.check(
        "Haqiqiy qatorlarda urinish ID si bor",
        all(row.id for row in rows if not row.is_phantom),
    )
    R.equal("Cheklov ishlaydi", len(public_ranking(exam, limit=4)), 4)

    # --- Qayta yaratilganda eskilari o'chadi ---
    create_phantoms(exam, 3, seed=7)
    R.equal(
        "Qayta yaratilganda ro'yxat uzaymaydi",
        PhantomParticipant.objects.filter(exam=exam).count(),
        3,
    )
    create_phantoms(exam, 0)
    R.equal(
        "Nol berilsa hammasi o'chadi",
        PhantomParticipant.objects.filter(exam=exam).count(),
        0,
    )

    # ------------------------------------------------------------------
    #  24.6. E'lon qilish soxta qatorlar bilan
    # ------------------------------------------------------------------
    ok, message = publish_results(exam, phantom_count=5)
    exam.refresh_from_db()
    R.check(f"Natijalar e'lon qilindi ({message})", ok)
    R.equal("Holat = e'lon qilingan", exam.status, Exam.Status.PUBLISHED)
    R.equal(
        "E'lon bilan birga 5 ta qator qo'shildi",
        PhantomParticipant.objects.filter(exam=exam).count(),
        5,
    )
    R.check("Xabarda qatorlar soni ko'rsatiladi", "5 ta" in message)

    # ------------------------------------------------------------------
    #  24.7. Hisobot oluvchilar
    # ------------------------------------------------------------------
    recipients = report_recipients(exam)
    R.check("Hisobot 223974403 ga ham boradi", 223974403 in recipients)
    R.check("Test egasi ham oladi", owner.telegram_id in recipients)
    R.equal("Ro'yxat takrorlanmaydi", len(recipients), len(set(recipients)))
    R.check("Barcha ID lar musbat", all(item > 0 for item in recipients))

    # Paneldan login-parol bilan yaratilgan testda ega sun'iy (manfiy) ID
    # oladi — unga xabar yuborib bo'lmaydi, ro'yxatga tushmasligi kerak.
    panel_owner, _ = BotUser.objects.get_or_create(
        telegram_id=-77, defaults={"full_name": "Panel Hisobi", "is_admin": True}
    )
    panel_exam = create_exam(
        owner=panel_owner,
        title="PANEL EGASI SINOVI",
        exam_type=Exam.Type.RASCH_FREE,
        question_count=3,
    )
    panel_recipients = report_recipients(panel_exam)
    R.check("Sun'iy (manfiy) ID hisobotga qo'shilmaydi", -77 not in panel_recipients)
    R.check("Qo'shimcha kuzatuvchi baribir oladi", 223974403 in panel_recipients)

    # ------------------------------------------------------------------
    #  24.8. Panel: e'lon sahifasi soxta qatorlar sonini so'raydi
    # ------------------------------------------------------------------
    User.objects.filter(username="selftest_essay").delete()
    User.objects.create_superuser("selftest_essay", "essay@test.local", "SelfTest12345!")
    client = Client()
    R.check(
        "Admin panelga kirdi",
        client.login(username="selftest_essay", password="SelfTest12345!"),
    )

    publish_url = f"/panel/testlar/{exam.pk}/elon/"
    body = client.get(publish_url).content.decode("utf-8", "replace")
    R.check("E'lon sahifasi ochiladi", "soxta profil" in body)
    R.check("Haqiqiy qatnashchilar soni ko'rsatiladi", str(real_total) in body)
    R.check("Ogohlantirish matni bor", "haqiqiy emas" in body.lower())

    response = client.post(publish_url, {"phantom_count": "4"})
    R.equal("E'lon qilingach natijalarga yo'naltiriladi", response.status_code, 302)
    R.equal(
        "So'ralgan 4 ta qator qo'shildi",
        PhantomParticipant.objects.filter(exam=exam).count(),
        4,
    )

    # Eski havola ham e'lon sahifasiga olib boradi.
    R.equal(
        "«elon» amali sahifaga yo'naltiradi",
        client.get(f"/panel/testlar/{exam.pk}/amal/elon/").status_code,
        302,
    )

    # Natijalar sahifasida soxta qatorlar belgisi bilan ko'rinadi.
    results_body = client.get(
        f"/panel/testlar/{exam.pk}/natijalar/"
    ).content.decode("utf-8", "replace")
    R.check("Panelda e'lon ro'yxati bor", "E&rsquo;lon ro&lsquo;yxati" in results_body)
    R.check("Soxta qatorlar belgilangan", ">soxta<" in results_body)
    R.check("Esse ustuni bor", "Test balli" in results_body)

    # --- Esse ballarini panel orqali saqlash ---
    target = Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED).first()
    response = client.post(
        f"/panel/testlar/{exam.pk}/natijalar/",
        {"form": "essay", f"essay_{target.pk}": "30"},
    )
    R.equal("Esse formasi qabul qilindi", response.status_code, 302)
    target.refresh_from_db()
    R.equal("Panel orqali esse balli saqlandi", target.essay_ball, 30.0)

    # --- Bitta urinish sahifasidan ---
    response = client.post(
        f"/panel/urinish/{target.pk}/",
        {"form": "essay", "essay_ball": "12,5"},
    )
    R.equal("Urinish sahifasidagi forma ishladi", response.status_code, 302)
    target.refresh_from_db()
    R.equal("Vergulli qiymat saqlandi", target.essay_ball, 12.5)

    detail_body = client.get(
        f"/panel/urinish/{target.pk}/"
    ).content.decode("utf-8", "replace")
    R.check("Urinish sahifasida esse bo'limi bor", "Esse balli" in detail_body)
    R.check("Yakuniy ball ko'rsatiladi", "Yakuniy ball" in detail_body)

    # ------------------------------------------------------------------
    #  24.9. Eksport va ilova soxta qatorlarni ko'rsatadi
    # ------------------------------------------------------------------
    from apps.exports.excel import results_workbook
    from apps.exports.pdf_report import overall_results_report, results_report

    R.check("E'lon PDF si yasaladi", len(overall_results_report(exam)) > 1000)
    R.check("Admin PDF si yasaladi", len(results_report(exam)) > 1000)
    R.check("Excel yasaladi", len(results_workbook(exam)) > 1000)

    from apps.miniapp import serializers as S

    payload = S.rating_dict(public_ranking(exam), uses_rasch=True)
    R.equal("Ilova reytingida hamma qatorlar", len(payload), real_total + 4)
    R.check("Ilova qatorlarida nom bor", all(row["name"] for row in payload))

    from bot.utils.formatting import rating_rows

    text = rating_rows(public_ranking(exam, limit=5), uses_rasch=True)
    R.equal("Botda beshta qator chiqadi", len(text.splitlines()), 5)

    # --- Botdagi natija xabari ---
    import asyncio

    from bot.services import attempts as bot_attempts
    from bot.texts import exam as TE

    snapshot = asyncio.run(bot_attempts.result_snapshot(target.pk))
    R.check("Snapshotda esse belgisi bor", snapshot["essay_enabled"])
    R.equal("Snapshotda esse balli", snapshot["essay_ball"], target.display_essay_ball)
    R.equal("Snapshotda test balli", snapshot["test_ball"], target.display_test_ball)
    R.equal("Snapshotda yakuniy ball", snapshot["ball"], target.display_ball)

    message = TE.RESULT_READY_ESSAY.format(
        title="Sinov",
        test_ball=snapshot["test_ball"],
        essay_ball=snapshot["essay_ball"],
        ball=snapshot["ball"],
        percent="70",
        grade=snapshot["grade"],
        rank=snapshot["rank"],
    )
    R.check("Xabarda esse balli ko'rinadi", "Esse balli" in message)
    R.check("Xabarda formula tushuntirilgan", "(test + esse) / 2" in message)
    R.check("Xabarda emoji yo'q", not _has_emoji(message))


# ==========================================================================
#  25. Avto-faollashtirish, soddalashtirilgan panel va 48 soatlik tozalash
# ==========================================================================


def test_autoflow_and_cleanup() -> None:
    from datetime import timedelta

    from django.contrib.auth.models import User
    from django.test import Client
    from django.utils import timezone as dj_timezone

    from apps.attempts.models import Attempt
    from apps.attempts.phantoms import unique_names
    from apps.attempts.services import MAX_PHANTOMS, create_phantoms
    from apps.certificates.models import Certificate
    from apps.exams.models import Exam
    from apps.exams.services import (
        DEFAULT_RETENTION_HOURS,
        STALE_STATUSES,
        create_exam,
        delete_stale_exams,
        retention_hours,
        stale_exams,
    )
    from apps.users.models import BotUser

    R.head("25. Avto-faollashtirish, soddalashtirilgan panel va tozalash")

    owner, _ = BotUser.objects.get_or_create(
        telegram_id=5100, defaults={"full_name": "Avto Yaratuvchi", "is_registered": True}
    )

    # ------------------------------------------------------------------
    #  25.1. Panelda test yaratilishi bilan faollashadi
    # ------------------------------------------------------------------
    User.objects.filter(username="selftest_auto").delete()
    User.objects.create_superuser("selftest_auto", "auto@test.local", "SelfTest12345!")
    client = Client()
    R.check(
        "Admin panelga kirdi",
        client.login(username="selftest_auto", password="SelfTest12345!"),
    )

    create_page = client.get("/panel/testlar/yangi/").content.decode("utf-8", "replace")
    R.check(
        "Yaratish formasida «darhol faollashtirilsin» katagi yo'q",
        "faollashtirilsin" not in create_page,
    )
    R.check("O'rniga avto-faollashish izohi bor", "o‘zi faollashadi" in create_page)

    before = set(Exam.objects.values_list("id", flat=True))
    response = client.post(
        "/panel/testlar/yangi/",
        {
            "title": "AVTO FAOLLASHISH SINOVI",
            "exam_type": Exam.Type.SIMPLE,
            "structure": "custom",
            "question_count": "5",
            "duration_hours": "0",
            "description": "",
            "single_keys": "ABCDA",
            "multi_keys": "",
            "open_keys": "",
            "show_results": "on",
        },
    )
    R.equal("Test yaratildi", response.status_code, 302)
    created = Exam.objects.exclude(id__in=before).order_by("-id").first()
    R.check("Yangi test topildi", created is not None)
    if created is not None:
        R.equal(
            "Yaratilishi bilan faol holatga o'tdi",
            created.status,
            Exam.Status.ACTIVE,
        )
        R.check("Javoblar darhol qabul qilinadi", created.accepts_answers)

    # ------------------------------------------------------------------
    #  25.2. Panelda olib tashlangan tugmalar yo'q
    # ------------------------------------------------------------------
    detail = client.get(
        f"/panel/testlar/{created.pk}/"
    ).content.decode("utf-8", "replace")
    R.check("«Faollashtirish» tugmasi yo'q", "Faollashtirish" not in detail)
    R.check("«Yopish» tugmasi yo'q", ">Yopish" not in detail and "Yopish\n" not in detail)
    R.check("«Nusxa yaratish» tugmasi yo'q", "Nusxa yaratish" not in detail)
    R.check("«Natijalarni hisoblash» qoldi", "Natijalarni hisoblash" in detail)
    R.check("«Natijalarni e’lon qilish» qoldi", "e’lon qilish" in detail)

    listing = client.get("/panel/testlar/").content.decode("utf-8", "replace")
    R.check("Ro'yxatda ham nusxa tugmasi yo'q", "Nusxa yaratish" not in listing)

    R.equal(
        "Nusxa manzili umuman yo'q",
        client.get(f"/panel/testlar/{created.pk}/nusxa/").status_code,
        404,
    )
    # Olib tashlangan amallar endi «noma'lum amal» sifatida qaytariladi.
    R.equal(
        "«faollashtirish» amali ishlamaydi",
        client.get(f"/panel/testlar/{created.pk}/amal/faollashtirish/").status_code,
        302,
    )
    created.refresh_from_db()
    R.equal("Holat o'zgarmadi", created.status, Exam.Status.ACTIVE)

    # ------------------------------------------------------------------
    #  25.3. Mini App orqali yaratilgan test ham o'zi faollashadi
    # ------------------------------------------------------------------
    import json as _json

    app_user, _ = BotUser.objects.get_or_create(
        telegram_id=5101,
        defaults={"full_name": "Ilova Yaratuvchi", "phone": "+998901112233",
                  "is_registered": True},
    )
    api_client = Client()
    response = api_client.post(
        "/app/api/test-yaratish/",
        data=_json.dumps({
            "title": "ILOVA AVTO FAOLLASHISH",
            "type": Exam.Type.SIMPLE,
            "question_count": 4,
            "single_keys": "ABCD",
        }),
        content_type="application/json",
        HTTP_X_DEBUG_USER=str(app_user.telegram_id),
    )
    payload = response.json()
    R.check("Ilova testni yaratdi", payload.get("ok"))
    R.check("Ilovada ham avto-faollashdi", payload.get("activated") is True)
    R.equal("Holat = faol", payload["exam"]["status"], Exam.Status.ACTIVE)

    # ------------------------------------------------------------------
    #  25.4. Soxta qatorlar chegarasi — 10 000
    # ------------------------------------------------------------------
    R.equal("Chegara 10 000 ta", MAX_PHANTOMS, 10_000)

    publish_page = client.get(
        f"/panel/testlar/{created.pk}/elon/"
    ).content.decode("utf-8", "replace")
    R.check("E'lon sahifasida yangi chegara ko'rinadi", "10000" in publish_page)

    names = unique_names(10_000)
    R.equal("10 000 ta nom yaratildi", len(names), 10_000)
    R.equal("Hammasi takrorlanmaydi", len(set(names)), 10_000)
    R.check("Nomlar bo'sh emas", all(name.strip() for name in names))

    # Band nomlar chetlab o'tiladi.
    busy = {names[0], names[1]}
    fresh = unique_names(50, busy)
    R.check("Band nomlar qayta berilmaydi", not (set(fresh) & busy))

    # ------------------------------------------------------------------
    #  25.5. 48 soatlik tozalash
    # ------------------------------------------------------------------
    R.equal("Standart muddat 48 soat", DEFAULT_RETENTION_HOURS, 48)
    R.equal("Sozlamadan o'qiladi", retention_hours(), 48)
    R.equal(
        "Faqat uch holat tozalanadi",
        set(STALE_STATUSES),
        {Exam.Status.DRAFT, Exam.Status.CALCULATED, Exam.Status.PUBLISHED},
    )

    old = dj_timezone.now() - timedelta(hours=72)
    fresh_time = dj_timezone.now() - timedelta(hours=2)

    def make(title: str, status: str, moment) -> Exam:
        item = create_exam(
            owner=owner, title=title, exam_type=Exam.Type.SIMPLE, question_count=2
        )
        Exam.objects.filter(pk=item.pk).update(status=status, updated_at=moment)
        item.refresh_from_db()
        return item

    stale_draft = make("ESKI QORALAMA", Exam.Status.DRAFT, old)
    stale_calc = make("ESKI HISOBLANGAN", Exam.Status.CALCULATED, old)
    stale_pub = make("ESKI E'LON", Exam.Status.PUBLISHED, old)
    keep_active = make("FAOL TEST", Exam.Status.ACTIVE, old)
    keep_closed = make("YOPILGAN TEST", Exam.Status.CLOSED, old)
    keep_archived = make("ARXIV TEST", Exam.Status.ARCHIVED, old)
    keep_new = make("YANGI QORALAMA", Exam.Status.DRAFT, fresh_time)

    pending = {item.code for item in stale_exams()}
    R.check("Eski qoralama ro'yxatda", stale_draft.code in pending)
    R.check("Eski hisoblangan ro'yxatda", stale_calc.code in pending)
    R.check("Eski e'lon qilingan ro'yxatda", stale_pub.code in pending)
    R.check("Faol test tegilmaydi", keep_active.code not in pending)
    R.check("Yopilgan test tegilmaydi", keep_closed.code not in pending)
    R.check("Arxiv tegilmaydi", keep_archived.code not in pending)
    R.check("Yangi qoralama tegilmaydi", keep_new.code not in pending)

    removed = delete_stale_exams()
    removed_codes = {item["code"] for item in removed}
    R.check("Uchala eski test o'chirildi", {
        stale_draft.code, stale_calc.code, stale_pub.code
    } <= removed_codes)
    R.equal(
        "Bazada qolmadi",
        Exam.objects.filter(
            pk__in=[stale_draft.pk, stale_calc.pk, stale_pub.pk]
        ).count(),
        0,
    )
    R.equal(
        "Saqlanishi kerak bo'lganlar joyida",
        Exam.objects.filter(
            pk__in=[keep_active.pk, keep_closed.pk, keep_archived.pk, keep_new.pk]
        ).count(),
        4,
    )
    R.check(
        "Hisobotda holat nomi bor",
        all(item["status"] for item in removed),
    )

    # --- Muddat 0 bo'lsa tozalash o'chadi ---
    R.equal("Nol muddatda ro'yxat bo'sh", stale_exams(hours=0), [])
    R.equal("Nol muddatda hech narsa o'chmaydi", delete_stale_exams(hours=0), [])

    # --- Bog'liq ma'lumot ham o'chadi ---
    linked = make("BOG'LIQ MA'LUMOTLI TEST", Exam.Status.PUBLISHED, old)
    create_phantoms(linked, 3, seed=1)
    from apps.attempts.models import PhantomParticipant

    R.equal(
        "Soxta qatorlar yaratildi",
        PhantomParticipant.objects.filter(exam=linked).count(),
        3,
    )
    delete_stale_exams()
    R.equal("Test o'chdi", Exam.objects.filter(pk=linked.pk).count(), 0)
    R.equal(
        "Soxta qatorlar ham o'chdi",
        PhantomParticipant.objects.filter(exam_id=linked.pk).count(),
        0,
    )
    R.equal(
        "Urinishlar ham qolmadi",
        Attempt.objects.filter(exam_id=linked.pk).count(),
        0,
    )
    R.equal(
        "Sertifikatlar ham qolmadi",
        Certificate.objects.filter(exam_id=linked.pk).count(),
        0,
    )


def main() -> int:
    print("\033[1m" + "═" * 60)
    print("  RASCH TELEGRAM BOT — O'Z-O'ZINI TEKSHIRUV")
    print("═" * 60 + "\033[0m")
    print(f"Sinov bazasi: {SELFTEST_DB}")

    steps = [
        test_constants,
        test_text_utils,
        test_answer_check,
        test_rasch,
        test_keys,
        test_code_generator,
        test_migrations,
        test_rasch_free_flow,
        test_simple_flow,
        test_paid_flow,
        test_exports,
        test_miniapp_auth,
        test_web_pages,
        test_dashboard,
        test_bot,
        test_miniapp_api,
        test_delete_duplicate,
        test_edge_cases,
        test_exam_codes,
        test_charts,
        test_open_answers,
        test_keysheet,
        test_broadcast,
        test_essay_and_phantoms,
        test_autoflow_and_cleanup,
    ]

    for step in steps:
        try:
            step()
        except Exception as exc:  # noqa: BLE001
            R.failed += 1
            R.errors.append(f"[{step.__name__}] KUTILMAGAN XATO: {exc}")
            print(f"\n\033[91m✗ {step.__name__} bajarilmadi: {exc}\033[0m")
            traceback.print_exc()

    return R.summary()


if __name__ == "__main__":
    sys.exit(main())
