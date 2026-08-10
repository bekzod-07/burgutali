#!/usr/bin/env python
"""
Video dars yozib olish uchun namoyish (demo) ma'lumotlarini tayyorlaydi.

Yozuvda ekran bo'sh turmasligi uchun uchta tayyor test, ishtirokchilar,
natijalar, ID kodlar va sertifikatlar yaratiladi.

Foydalanish:

    python tools/demo_data.py            # demo ma'lumotlarni qo'shadi
    python tools/demo_data.py --reset    # avval eskisini o'chirib, qaytadan
    python tools/demo_data.py --clean    # faqat o'chiradi

Xavfsizlik: barcha demo yozuvlar alohida belgilanadi —
  * foydalanuvchilar: Telegram ID 900000000 dan boshlanadi;
  * testlar: nomi "DEMO" bilan boshlanadi.
`--clean` faqat shu yozuvlarni o'chiradi, haqiqiy ma'lumotlarga tegmaydi.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.accesscodes.models import AccessCode  # noqa: E402
from apps.accesscodes.services import activate_code, create_codes  # noqa: E402
from apps.attempts.models import Attempt  # noqa: E402
from apps.attempts.services import save_answer, start_attempt, submit_attempt  # noqa: E402
from apps.certificates.services import issue_for_exam  # noqa: E402
from apps.exams.models import Exam, Question  # noqa: E402
from apps.exams.services import (  # noqa: E402
    activate_exam,
    apply_multi_keys,
    apply_open_keys,
    apply_single_keys,
    close_exam,
    create_exam,
    delete_exam,
    publish_results,
)
from apps.rasch.services import calculate_exam  # noqa: E402
from apps.users.models import BotUser  # noqa: E402

# --------------------------------------------------------------------------
#  Sozlamalar
# --------------------------------------------------------------------------

DEMO_ID_START = 900_000_000
DEMO_PREFIX = "DEMO"

NAMES = [
    "Aziza Karimova", "Bekzod Rahimov", "Dilnoza Yusupova", "Elyor Tashmatov",
    "Farida Nazarova", "G'ayrat Sobirov", "Hilola Umarova", "Islom Qodirov",
    "Jasur Ergashev", "Kamola Sharipova", "Laziz Tursunov", "Madina Alimova",
    "Nodir Xolmatov", "Ozoda Yo'ldosheva", "Pulat Aliyev", "Ruxshona Sattorova",
    "Sardor Ismoilov", "Tohir Bekmurodov", "Umida Rasulova", "Vohid Nematov",
    "Xurshid Jo'rayev", "Yulduz Abdullayeva", "Zafar Mirzayev", "Aziz Norqulov",
    "Barno Xasanova", "Doniyor Salimov", "Feruza Qosimova", "Gulnora Ahmedova",
]


def log(message: str) -> None:
    print(f"  {message}")


# --------------------------------------------------------------------------
#  Tozalash
# --------------------------------------------------------------------------


def clean() -> None:
    """Faqat demo yozuvlarni o'chiradi."""
    print("\nDemo ma'lumotlar o'chirilmoqda...")

    exams = list(Exam.objects.filter(title__startswith=DEMO_PREFIX))
    for exam in exams:
        delete_exam(exam, force=True)
        log(f"test o'chirildi: {exam.title}")

    removed, _ = BotUser.objects.filter(telegram_id__gte=DEMO_ID_START).delete()
    log(f"{removed} ta demo yozuv o'chirildi")
    print("Tayyor.\n")


# --------------------------------------------------------------------------
#  Foydalanuvchilar
# --------------------------------------------------------------------------


def make_users(count: int) -> list[BotUser]:
    """Demo ishtirokchilarni yaratadi."""
    users: list[BotUser] = []
    for index in range(count):
        name = NAMES[index % len(NAMES)]
        telegram_id = DEMO_ID_START + index + 1
        user, _ = BotUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                "full_name": name,
                "phone": f"+9989{random.randint(10000000, 99999999)}",
                "is_registered": True,
                "is_subscribed": True,
                "registered_at": timezone.now(),
                "last_seen_at": timezone.now(),
            },
        )
        users.append(user)
    log(f"{len(users)} ta demo ishtirokchi tayyor")
    return users


def demo_owner() -> BotUser:
    """Demo testlarning egasi — mavjud admin yoki yangi demo admin."""
    owner = BotUser.objects.filter(is_admin=True).order_by("id").first()
    if owner is not None:
        return owner
    owner, _ = BotUser.objects.get_or_create(
        telegram_id=DEMO_ID_START,
        defaults={
            "full_name": "Demo Administrator",
            "phone": "+998901234567",
            "is_registered": True,
            "is_admin": True,
            "is_subscribed": True,
            "registered_at": timezone.now(),
        },
    )
    return owner


# --------------------------------------------------------------------------
#  Javob berish
# --------------------------------------------------------------------------


def answer_exam(user: BotUser, exam: Exam, ability: float, rng: random.Random) -> Attempt:
    """
    Ishtirokchi nomidan testni to'ldiradi.

    `ability` — 0 dan 1 gacha: qanchalik kuchli ishtirokchi.
    """
    attempt = start_attempt(user, exam)
    for question in exam.questions.order_by("order"):
        success = max(0.05, min(0.97, ability - question.difficulty * 0.12))
        correct = rng.random() < success

        if question.kind == Question.Kind.OPEN:
            save_answer(
                attempt,
                question,
                text_a=question.answer_a if correct else "0",
                text_b=question.answer_b if (correct and question.parts > 1) else (
                    "0" if question.parts > 1 else ""
                ),
            )
        else:
            if correct:
                value = question.correct_key
            else:
                letters = [x for x in question.choice_letters if x not in question.correct_set]
                value = rng.choice(letters) if letters else "A"
            save_answer(attempt, question, selected=value)

    return submit_attempt(attempt)


# --------------------------------------------------------------------------
#  1-tur: oddiy test
# --------------------------------------------------------------------------


def build_simple(owner: BotUser, users: list[BotUser], rng: random.Random) -> Exam:
    print("\n[1/3] Oddiy test (1-tur)")
    exam = create_exam(
        owner=owner,
        title=f"{DEMO_PREFIX} — Algebra: kvadrat tenglamalar",
        exam_type=Exam.Type.SIMPLE,
        question_count=20,
        description="20 ta savol, A/B/C/D. Natija to'g'ri javoblar soni bo'yicha.",
        show_results=True,
    )
    apply_single_keys(exam, ["ABCD"[i % 4] for i in range(20)])
    activate_exam(exam)
    log(f"yaratildi: {exam.code} — 20 ta savol, faol")

    for index, user in enumerate(users[:14]):
        answer_exam(user, exam, 0.45 + index * 0.035, rng)
    calculate_exam(exam)
    log("14 ta ishtirokchi javob berdi, natijalar hisoblandi")
    return exam


# --------------------------------------------------------------------------
#  2-tur: bepul RASH testi
# --------------------------------------------------------------------------


def build_rasch_free(owner: BotUser, users: list[BotUser], rng: random.Random) -> Exam:
    print("\n[2/3] Bepul RASH testi (2-tur) — milliy shablon")
    exam = create_exam(
        owner=owner,
        title=f"{DEMO_PREFIX} — MILLIY SERTIFIKAT MOCK №1",
        exam_type=Exam.Type.RASCH_FREE,
        national_template=True,
        description="45 ta savol: 1–32 (A–D), 33–35 (A–F), 36–45 (ochiq javob).",
        show_results=True,
    )
    apply_single_keys(exam, ["ABCD"[i % 4] for i in range(32)])
    apply_multi_keys(exam, ["AB", "ACD", "BF"])
    apply_open_keys(
        exam,
        [
            "12||3/4", "1/2||0.25", "sqrt(2)||pi/6", "5||-3", "0||1",
            "2^3||9", "sin(pi/2)||cos(0)", "10||100", "1/3||2/3", "7||8",
        ],
    )
    activate_exam(exam)
    log(f"yaratildi: {exam.code} — 45 ta savol (55 ta ballanadigan birlik)")

    for index, user in enumerate(users[:24]):
        answer_exam(user, exam, 0.30 + index * 0.028, rng)

    close_exam(exam)
    report = calculate_exam(exam)
    publish_results(exam)
    log(
        f"24 ta ishtirokchi, RASH hisoblandi "
        f"(ishonchlilik {report.reliability:.3f}), natijalar e'lon qilindi"
    )
    return exam


# --------------------------------------------------------------------------
#  3-tur: pullik RASH testi + sertifikatlar
# --------------------------------------------------------------------------


def build_rasch_paid(owner: BotUser, users: list[BotUser], rng: random.Random) -> Exam:
    print("\n[3/3] Pullik RASH testi (3-tur) — ID kodlar va sertifikatlar")
    exam = create_exam(
        owner=owner,
        title=f"{DEMO_PREFIX} — MILLIY SERTIFIKAT MOCK №2 (pullik)",
        exam_type=Exam.Type.RASCH_PAID,
        question_count=30,
        description="Kirish bir martalik ID kod orqali. Sertifikat beriladi.",
        show_results=True,
        certificate_enabled=True,
        organizer_name=owner.full_name or "Tashkilotchi",
    )
    apply_single_keys(exam, ["ABCD"[i % 4] for i in range(30)])

    batch = create_codes(exam, 500, created_by=owner, note="Video dars uchun demo")
    log(f"{batch.quantity} ta ID kod yaratildi (partiya #{batch.id})")

    activate_exam(exam)
    log(f"yaratildi: {exam.code} — 30 ta savol, faol")

    codes = list(AccessCode.objects.filter(exam=exam).order_by("id")[:18])
    for index, user in enumerate(users[:18]):
        activate_code(codes[index], user, user.full_name)
        answer_exam(user, exam, 0.35 + index * 0.033, rng)

    close_exam(exam)
    calculate_exam(exam)
    publish_results(exam)
    result = issue_for_exam(exam)
    log(
        f"18 ta ishtirokchi, natijalar e'lon qilindi, "
        f"{result['created']} ta sertifikat berildi"
    )
    return exam


# --------------------------------------------------------------------------
#  Bo'sh test (video darsda "noldan yaratish" uchun joy qoldiriladi)
# --------------------------------------------------------------------------


def summary(exams: list[Exam]) -> None:
    print("\n" + "=" * 62)
    print("  DEMO MA'LUMOTLAR TAYYOR")
    print("=" * 62)
    for exam in exams:
        exam.refresh_from_db()
        participants = Attempt.objects.filter(
            exam=exam, status=Attempt.Status.SUBMITTED
        ).count()
        print(f"\n  {exam.title}")
        print(f"    kod          : {exam.code}")
        print(f"    turi         : {exam.get_exam_type_display()}")
        print(f"    holati       : {exam.get_status_display()}")
        print(f"    savollar     : {exam.question_count}")
        print(f"    qatnashchilar: {participants}")
        if exam.requires_access_code:
            free = AccessCode.objects.filter(
                exam=exam, status=AccessCode.Status.UNUSED
            ).first()
            if free:
                print(f"    bo'sh ID kod : {free.code}   <- videoda shuni kiriting")

    print("\n  Foydalanuvchilar: Telegram ID {}+".format(DEMO_ID_START))
    print("  O'chirish       : python tools/demo_data.py --clean")
    print("=" * 62 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Video dars uchun demo ma'lumotlar")
    parser.add_argument("--reset", action="store_true", help="avval eskisini o'chirish")
    parser.add_argument("--clean", action="store_true", help="faqat o'chirish")
    parser.add_argument("--seed", type=int, default=2026, help="tasodifiylik urug'i")
    args = parser.parse_args()

    if args.clean:
        clean()
        return 0
    if args.reset:
        clean()

    rng = random.Random(args.seed)
    print("\nDemo ma'lumotlar tayyorlanmoqda...")

    owner = demo_owner()
    log(f"testlar egasi: {owner.display_name}")
    users = make_users(28)

    exams = [
        build_simple(owner, users, rng),
        build_rasch_free(owner, users, rng),
        build_rasch_paid(owner, users, rng),
    ]

    summary(exams)
    return 0


if __name__ == "__main__":
    sys.exit(main())
