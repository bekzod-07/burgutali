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
    R.equal("40.0 -> C (sertifikat chegarasi)", C.grade_for_ball(40.0), "C")
    R.equal("45.9 -> C", C.grade_for_ball(45.9), "C")
    R.equal("49.9 -> C", C.grade_for_ball(49.9), "C")
    R.equal("50.0 -> C+", C.grade_for_ball(50.0), "C+")
    R.equal("55.0 -> B", C.grade_for_ball(55.0), "B")
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
#  3. Matematik ekvivalentlik (SymPy)
# ==========================================================================


def test_math_expr() -> None:
    from core.math_expr import is_equivalent, normalize_expression, parse_expression

    R.head("3. Matematik ekvivalentlik (SRS 4-bo'lim)")

    cases_true = [
        ("1/2", "0.5"),
        ("0,5", "1/2"),
        ("2^-1", "0.5"),
        ("sin(pi/6)", "0.5"),
        ("√2", "sqrt(2)"),
        ("2^3", "8"),
        ("x²+2x", "x**2+2*x"),
        ("|-5|", "5"),
        ("tg(pi/4)", "1"),
        ("ctg(pi/4)", "1"),
        ("ln(e)", "1"),
        ("log(100)/log(10)", "2"),
        ("30°", "pi/6"),
        ("3/4", "0.75"),
        ("2x", "x*2"),
        ("0.5", "1/2;0.5"),
        ("(1+2)*3", "9"),
        ("sqrt(9)", "3"),
    ]
    for user, key in cases_true:
        R.check(f"«{user}» = «{key}»", is_equivalent(user, key))

    cases_false = [
        ("1/3", "0.33"),
        ("4", "5"),
        ("x+1", "x+2"),
        ("sin(pi/3)", "0.5"),
        ("", "5"),
    ]
    for user, key in cases_false:
        R.check(f"«{user}» ≠ «{key}»", not is_equivalent(user, key))

    R.check("Tengsizlik taqqoslanadi", is_equivalent("x>=2", "x >= 2"))
    R.check("Normalizatsiya ishlaydi", "**" in normalize_expression("2^3"))
    R.check("Juda uzun ifoda rad etiladi", parse_expression("1+" * 300 + "1") is None)

    # --- Xavfsizlik: SymPy `parse_expr` ichida `eval` ishlatadi ---
    attacks = [
        "__import__('os')",
        '__import__("os").system("calc")',
        "open('x')",
        "exit()",
        "eval('1+1')",
        "().__class__",
        "().__class__.__bases__",
        "globals()",
        "lambda: 1",
        "[1,2,3]",
        "{1:2}",
    ]
    for attack in attacks:
        R.check(f"Hujum bloklandi: {attack[:26]}", parse_expression(attack) is None)


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
    R.close("theta=-0.4500 -> 40.00 (C chegarasi)", scoring.theta_to_ball(-0.45), 40.0, 0.02)
    R.equal("C chegarasi — sertifikat 40 balldan", scoring.grade_for(40.0), "C")
    R.equal("39.99 ball — sertifikat yo'q", scoring.grade_for(39.99), C.NO_GRADE)

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

    result = keys.parse_open_key("12 ; 3/4\nsqrt(2) ; pi/6", 2)
    R.check("Ochiq kalit o'qiladi", result.ok)
    R.equal("Ochiq kalit ajratiladi", keys.split_open_key(result.keys[0]), ("12", "3/4"))
    R.equal("Ikkinchi qator", keys.split_open_key(result.keys[1]), ("sqrt(2)", "pi/6"))

    result = keys.parse_open_key("12 ; 3/4", 3)
    R.check("Qator soni mos kelmasa xato", not result.ok)

    # O'nlik kasr savol raqami deb kesilmasligi kerak: «0.5» -> «5» emas.
    result = keys.parse_open_key("0.5 ; -2\n12-3 ; 1.25", 2)
    R.check("O'nlik kasrli kalit o'qiladi", result.ok)
    R.equal("O'nlik kasr butunligicha qoladi", keys.split_open_key(result.keys[0]), ("0.5", "-2"))
    R.equal("Ayirma ifodasi kesilmaydi", keys.split_open_key(result.keys[1]), ("12-3", "1.25"))

    result = keys.parse_open_key("36) 12 ; 3/4\n37. 5 ; 6", 2)
    R.check("Raqamlangan ochiq kalit o'qiladi", result.ok)
    R.equal("Savol raqami olib tashlanadi", keys.split_open_key(result.keys[0]), ("12", "3/4"))
    R.equal("Nuqtali raqam ham olib tashlanadi", keys.split_open_key(result.keys[1]), ("5", "6"))

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
    from apps.rasch.services import calculate_exam
    from apps.users.models import BotUser

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
    R.equal("Maksimal xom ball 55", exam.max_raw_score, 55.0)
    # Kod ishtirokchi uchun qulay bo'lishi kerak — oddiy 2–3 xonali son.
    R.check(
        f"Test kodi oddiy son ({exam.code})",
        bool(exam.code) and exam.code.isdigit() and len(exam.code) <= 3,
    )

    # --- Javob kalitlari ---
    single_keys = ["ABCD"[i % 4] for i in range(32)]
    apply_single_keys(exam, single_keys)
    apply_multi_keys(exam, ["A", "C", "E"])
    open_keys = [
        "12||3/4", "1/2||0.25", "sqrt(2)||pi/6", "5||-3", "0||1",
        "2^3||9", "sin(pi/2)||cos(0)", "10||100", "1/3||2/3", "7||8",
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
                    text_a=question.answer_a if good_a else "999",
                    text_b=question.answer_b if good_b else "888",
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

    # --- Baholash aniqligi: to'liq to'g'ri javob bergan ishtirokchi ---
    perfect_user, _ = BotUser.objects.get_or_create(
        telegram_id=9999, defaults={"full_name": "Mukammal Ishtirokchi", "is_registered": True}
    )
    perfect = start_attempt(perfect_user, exam)
    for question in questions:
        if question.kind == Question.Kind.OPEN:
            save_answer(perfect, question, text_a=question.answer_a, text_b=question.answer_b)
        else:
            save_answer(perfect, question, selected=question.correct_key)
    submit_attempt(perfect)
    perfect.refresh_from_db()
    R.equal("To'liq to'g'ri javob = 55 ball", perfect.raw_score, 55.0)
    R.close("Foiz = 100", perfect.percent, 100.0, 0.01)

    # --- Matematik ekvivalentlik amalda ---
    equiv_user, _ = BotUser.objects.get_or_create(
        telegram_id=9998, defaults={"full_name": "Ekvivalent Ishtirokchi", "is_registered": True}
    )
    equiv = start_attempt(equiv_user, exam)
    open_question = exam.questions.filter(kind="open", order=37).first()
    save_answer(equiv, open_question, text_a="0.5", text_b="1/4")
    submit_attempt(equiv)
    equiv_answer = equiv.answers.get(question=open_question)
    R.check("«0.5» = «1/2» deb qabul qilindi", equiv_answer.is_correct_a is True)
    R.check("«1/4» = «0.25» deb qabul qilindi", equiv_answer.is_correct_b is True)

    # --- Statistika ---
    calculate_exam(exam)
    exam.refresh_from_db()
    statistics = exam.statistics
    R.check("Statistika yaratildi", statistics.participants > 0)
    R.check("Darajalar taqsimoti to'ldirildi", bool(statistics.grade_distribution))
    R.check("Savollar statistikasi to'ldirildi", len(statistics.item_statistics) == 55)

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


# ==========================================================================
#  11. Eksport (Excel / PDF)
# ==========================================================================


def test_exports() -> None:
    from apps.accesscodes.models import CodeBatch
    from apps.exams.models import Exam
    from apps.exports.excel import codes_workbook, participants_workbook, results_workbook
    from apps.exports.pdf_report import certificate_list_report, results_report

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
    R.check(
        "Daraja ustuni uchun uslub buyruqlari yasaldi",
        len(commands) == 6
        and all(cmd[1][0] == 2 and cmd[2][0] == 2 for cmd in commands),
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

    response = client.get("/app/klaviatura/?q=36&parts=2")
    R.equal("Matematik klaviatura sahifasi ochiladi", response.status_code, 200)
    R.check("Klaviatura tugmalari bor", b"keyboard" in response.content)

    response = client.post(
        "/app/api/tekshir/", data='{"expr": "1/2 + 1/2"}', content_type="application/json"
    )
    R.equal("Mini App API javob beradi", response.status_code, 200)
    R.check("Ifoda to'g'ri tahlil qilindi", response.json().get("ok") is True)

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
    R.check("Mini App tugmasi web_app bilan",
            reply.math_keyboard("https://example.test/app/").keyboard[0][0].web_app is not None)

    R.check("Obuna klaviaturasi 2 ta tugma",
            len(inline.subscription("https://t.me/Burgutali").inline_keyboard) == 2)

    # --- Majburiy obuna: @Burgutali, qat'iy rejim ---
    R.check("Majburiy obuna yoqilgan", config.subscription_required is True)
    R.equal("Majburiy kanal — @Burgutali", config.required_channel, "@Burgutali")
    R.equal("Kanal havolasi to'g'ri",
            config.required_channel_url, "https://t.me/Burgutali")

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
    R.check("Nusxa boshqa kodga ega", copy_code != exam_code)
    R.equal("Nusxa qoralama holatida", response.json()["exam"]["status"], "draft")

    # --- Ifodani tekshirish ---
    response = call("/app/api/ifoda/", {"expr": "1/2 + 1/2"}, who=participant)
    R.equal("Ifoda tekshirildi", response.status_code, 200)
    R.equal("Natija 1", response.json()["value"], "1")

    response = call("/app/api/ifoda/", {"expr": "__import__('os')"}, who=participant)
    R.equal("Xavfli ifoda rad etiladi", response.status_code, 400)

    # --- O'chirish ---
    response = call(f"/app/api/test/{copy_code}/ochirish-tekshiruv/", who=admin)
    R.equal("O'chirish hisoboti olindi", response.status_code, 200)

    response = call(f"/app/api/test/{copy_code}/ochirish/", {"confirm": True}, who=admin)
    R.equal("Nusxa o'chirildi", response.status_code, 200)
    R.check("Baza tozalandi", not Exam.objects.filter(code=copy_code).exists())

    # --- Tasdiqsiz o'chirish (javoblari bor test) ---
    response = call(f"/app/api/test/{exam_code}/ochirish/", {}, who=admin)
    R.equal("Tasdiqsiz o'chirish rad etiladi", response.status_code, 409)
    R.check("Tasdiq talab qilinadi", response.json().get("needs_confirmation"))

    response = call(f"/app/api/test/{exam_code}/ochirish/", {"confirm": True}, who=admin)
    R.equal("Tasdiq bilan o'chirildi", response.status_code, 200)
    R.check("Test o'chdi", not Exam.objects.filter(code=exam_code).exists())

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
#  21. Matematik klaviatura (uchala joyda bir xil)
# ==========================================================================


def test_mathpad() -> None:
    from django.test import Client

    from core.math_expr import parse_expression

    R.head("21. Matematik klaviatura (umumiy modul)")

    shared = BASE_DIR / "static" / "mathpad"
    css = shared / "mathpad.css"
    js = shared / "mathpad.js"
    field_js = shared / "mathfield.js"

    R.check("Umumiy uslub fayli bor", css.is_file())
    R.check("Umumiy modul fayli bor", js.is_file())
    R.check("Formula maydoni fayli bor", field_js.is_file())
    if not (css.is_file() and js.is_file() and field_js.is_file()):
        return

    source = js.read_text(encoding="utf-8")

    # --- Tugmalar to'plami (rasmda ko'rsatilgan tartib) ---
    rows = {
        "raqamlar": [str(digit) for digit in range(10)],
        "belgilar": ["pi", "e", "a", "b", "c", "x", "y", "z", "."],
        "amallar": ["(", ")", "/", "sqrt()", "^()", "^(2)", "^(3)", "cbrt()", "root(,)"],
        "trigonometriya": ["+", "-", "sin()", "cos()", "tan()", "cot()"],
        "teskari trigonometriya": ["arcsin()", "arccos()", "arctan()", "arcctg()"],
        "logarifmlar": ["ln()", "log10()", "log(,)", "exp()"],
    }
    for name, keys in rows.items():
        missing = [key for key in keys if '"%s"' % key not in source]
        R.check(f"Qator to'liq: {name} ({len(keys)} ta)", not missing, ", ".join(missing))

    # --- Har bir funksiya SymPy da haqiqatan hisoblanadi ---
    functions = [
        ("sqrt(4)", 2), ("cbrt(8)", 2), ("root(8,3)", 2),
        ("sin(0)", 0), ("cos(0)", 1), ("tan(0)", 0),
        ("arcsin(0)", 0), ("arccos(1)", 0), ("arctan(0)", 0),
        ("ln(1)", 0), ("log10(100)", 2), ("log(100,10)", 2), ("exp(0)", 1),
        ("2^3", 8), ("cot(pi/4)", 1), ("arcctg(1)", None),
        # Daraja qavs bilan yoziladi — keyingi son ko'rsatkichga qo'shilmaydi.
        ("2^(3)", 8), ("2^(2)", 4), ("2^(3)4", 32), ("2^(2)5", 20), ("2^(-1)", 0.5),
        # Ildiz darajasi — ixtiyoriy butun son.
        ("root(32,5)", 2), ("root(16,4)", 2),
        # Tayyor kasrdan keyin qo'yilgan yangi kasr — alohida ko'paytuvchi.
        ("455/3*(2/5)", None), ("1/2*(3/4)", 0.375),
        # Maxrajdan chiqqandan keyin davom ettirilgan ifoda.
        ("5/(2)", 2.5), ("5/(2)3", 7.5), ("5/(2)+3", 5.5), ("2^(3)/(4)", 2),
    ]
    for expression, expected in functions:
        parsed = parse_expression(expression)
        ok = parsed is not None
        if ok and expected is not None:
            ok = abs(float(parsed) - expected) < 1e-9
        R.check(f"Tugma ishlaydi: {expression}", ok, repr(parsed))

    # --- Boshqaruv amallari ---
    for action in ("undo", "redo", "paste", "left", "right", "enter", "del", "close"):
        R.check(f"Amal mavjud: {action}", 'data-mp="%s"' % action in source)

    # --- Klaviatura uchala joyda bir xil manbadan keladi ---
    pages = {
        "Web ilova": BASE_DIR / "apps/miniapp/templates/miniapp/app.html",
        "Klaviatura sahifasi": BASE_DIR / "apps/miniapp/templates/miniapp/keyboard.html",
        "Boshqaruv paneli": BASE_DIR / "apps/dashboard/templates/dashboard/base.html",
    }
    for name, path in pages.items():
        markup = path.read_text(encoding="utf-8")
        R.check(
            f"{name} umumiy klaviaturani ulaydi",
            "mathpad/mathpad.css" in markup and "mathpad/mathpad.js" in markup,
        )
        R.check(
            f"{name} formula maydonini ulaydi",
            "mathpad/mathfield.js" in markup,
        )

    # --- Javob chizilgan formula ko'rinishida ko'rsatiladi ---
    field_source = field_js.read_text(encoding="utf-8")
    for part, marker in (
        ("kasr", "mf-frac"),
        ("daraja", "mf-sup"),
        ("ildiz", "mf-root"),
        ("indeks", "mf-sub"),
        ("kursor", "mf-caret"),
        ("bo'sh joy belgisi", "mf-box"),
    ):
        R.check(f"Formula qismi chiziladi: {part}", marker in field_source)

    for name in ("sqrt", "cbrt", "root", "abs", "log10", "log"):
        R.check(f"Funksiya chizilishi tavsiflangan: {name}",
                '"%s"' % name in field_source)

    R.check("Formula maydonida emoji yo'q", not _has_emoji(field_source))

    styles = css.read_text(encoding="utf-8")
    R.check("Formula uslublari umumiy faylda", ".mf-frac" in styles)

    # --- To'ldirilmagan joy bo'sh to'rtburchak bo'lib chiziladi ---
    R.check("Bo'sh joy to'rtburchagi tavsiflangan", "function slot(" in field_source)
    R.check("Bo'sh joyda kursor ko'rinadi", 'classList.contains("mf-box")' in field_source)
    R.check("Bo'sh to'rtburchak uslubi bor", ".mf-box.is-active" in styles)
    R.check(
        "Tugallanmagan formulada xato ko'rsatilmaydi",
        "incomplete" in field_source,
    )
    R.check(
        "Kasr tugmasi bo'sh kasr chizadi",
        'data-mp="frac"' in source or '"frac"' in source,
    )
    R.check("Bo'sh kasr uchun maxsus amal bor", "function insertFraction(" in source)

    # --- Darajadan chiqish: kursor pastga tushadi ---
    R.check(
        "Ko'rsatkich alohida o'qiladi (keyingi son darajaga qo'shilmaydi)",
        "function parseExponent(" in field_source,
    )
    R.check("Tuzilma oxiri belgilanadi", "mf-tail" in field_source)
    R.check("Tuzilma oxiri uslubi bor", ".mf-tail" in styles)
    R.check(
        "Bo'sh tuzilma butunlay o'chadi",
        "function emptyShell(" in source,
    )

    # --- Yangi kasr eskisining suratiga ko'tarilmaydi ---
    R.check(
        "Tayyor kasr ustiga yangi kasr chiqmaydi",
        "function endsWithFraction(" in source,
    )
    R.check(
        "Ko'paytmadagi ortiqcha qavslar chizilmaydi",
        "function factor(" in field_source,
    )
    R.check(
        "Ildiz darajasi bo'sh to'rtburchak bo'lib chiziladi",
        '"root(,)"' in source and ".mf-deg.is-empty" in styles,
    )
    R.check(
        "Maxrajdan chiqib yozishni davom ettirish mumkin",
        "function openDenominator(" in source,
    )
    R.check(
        "Tuzilma qavslari ustida kursor to'xtamaydi",
        "function hiddenParen(" in source,
    )
    R.check(
        "«Bo'sh joy» joriy bo'lakni tugatadi",
        "function leaveSlot(" in source and "function slotEnd(" in source,
    )
    R.check(
        "Matn ko'rinishidagi maydonlarda bo'sh joy odatdagidek yoziladi",
        'input.dataset.mpadRaw === "1"' in source,
    )

    # --- Kursor tugmalari yuqorida (telefon navigatsiyasi to'sib qo'ymasin) ---
    R.check(
        "Kursor tugmalari yuqori qismda quriladi",
        "mpad-head" in source
        and source.index("mpad-navwrap") < source.index("ROWS.forEach"),
    )
    pad_css = (BASE_DIR / "static/mathpad/mathpad.css").read_text(encoding="utf-8")
    R.check("Yuqori qism uchun uslub bor", ".mpad-head {" in pad_css)
    R.check(
        "Yuqori qism aylantirilganda ham ko'rinadi",
        "position: sticky" in pad_css,
    )
    R.check(
        "Panel pastida telefon uchun bo'sh joy qoldiriladi",
        "max(6px, env(safe-area-inset-bottom" in pad_css,
    )

    # --- Eski (ikki sahifali) klaviaturadan iz qolmagan ---
    for path in (
        BASE_DIR / "apps/miniapp/static/miniapp/js/app.js",
        BASE_DIR / "apps/miniapp/static/miniapp/js/keyboard.js",
        BASE_DIR / "apps/dashboard/static/dashboard/js/mathpad.js",
    ):
        text = path.read_text(encoding="utf-8")
        R.check(
            f"Eski klaviatura qoldig'i yo'q: {path.name}",
            "mpage-num" not in text and "renderMathPad" not in text,
        )

    R.check("Klaviaturada emoji yo'q", not _has_emoji(source))

    # --- Sahifa haqiqatan ochiladi ---
    client = Client()
    response = client.get("/app/klaviatura/?q=36&parts=2")
    R.equal("Klaviatura sahifasi ochiladi", response.status_code, 200)
    body = response.content.decode("utf-8", "replace")
    R.check("Sahifada umumiy modul ulangan", "mathpad/mathpad.js" in body)
    R.check("Javob maydonlari bor", 'id="answer-a"' in body and 'id="answer-b"' in body)


# ==========================================================================
#  Asosiy oqim
# ==========================================================================


def main() -> int:
    print("\033[1m" + "═" * 60)
    print("  RASCH TELEGRAM BOT — O'Z-O'ZINI TEKSHIRUV")
    print("═" * 60 + "\033[0m")
    print(f"Sinov bazasi: {SELFTEST_DB}")

    steps = [
        test_constants,
        test_text_utils,
        test_math_expr,
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
        test_mathpad,
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
