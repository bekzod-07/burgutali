"""
Yakunlanmagan testlarning eski, murakkab kodlarini oddiy songa o'tkazadi.

Eski kodlar `T-4C6VV3` ko'rinishida edi — ishtirokchi uchun uni og'zaki
aytish ham, kiritish ham noqulay. Yangi kod oddiy ikki yoki uch xonali
son (`32`, `145`).

Faqat **yakunlanmagan** (qoralama va faol) testlar o'zgartiriladi:
yopilgan testlarning kodi tarixiy hisobotlarda uchraydi, shuning uchun
ularga tegilmaydi — ular baribir yangi testga to'sqinlik qilmaydi.
"""

from __future__ import annotations

import re

from django.db import migrations

#: Kod band hisoblanadigan holatlar.
LIVE_STATUSES = ("draft", "active")

#: Oddiy kod namunasi — 2 dan 6 xonagacha son.
SIMPLE_CODE = re.compile(r"^\d{2,6}$")

#: Kod uzunliklari — avval qisqasi beriladi.
LENGTHS = (2, 3, 4, 5, 6)


def simplify_codes(apps, schema_editor):
    """Eski formatdagi kodlarni oddiy sonlarga almashtiradi."""
    Exam = apps.get_model("exams", "Exam")
    ReservedExamCode = apps.get_model("exams", "ReservedExamCode")

    exams = [
        exam
        for exam in Exam.objects.filter(status__in=LIVE_STATUSES).order_by("id")
        if not SIMPLE_CODE.match(exam.code or "")
    ]
    if not exams:
        return

    taken = set(
        Exam.objects.filter(status__in=LIVE_STATUSES).values_list("code", flat=True)
    )
    taken |= set(
        ReservedExamCode.objects.filter(released_at__isnull=True).values_list(
            "code", flat=True
        )
    )

    def next_free() -> str | None:
        for length in LENGTHS:
            for number in range(10 ** (length - 1), 10**length):
                candidate = str(number)
                if candidate not in taken:
                    return candidate
        return None

    for exam in exams:
        candidate = next_free()
        if candidate is None:  # pragma: no cover - amalda yetib bo'lmaydi
            return
        taken.add(candidate)

        old_code = exam.code
        exam.code = candidate
        exam.save(update_fields=["code"])

        # Eski kodning bandligini bo'shatamiz, yangisini band qilamiz.
        ReservedExamCode.objects.filter(code=old_code).delete()
        ReservedExamCode.objects.update_or_create(
            code=candidate,
            defaults={"exam_title": (exam.title or "")[:150], "released_at": None},
        )


def noop(apps, schema_editor):
    """Ortga qaytarish: kodlarni tiklab bo'lmaydi (eski qiymat saqlanmagan)."""


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0004_reservedexamcode_released_at_alter_exam_code_and_more"),
    ]

    operations = [
        migrations.RunPython(simplify_codes, noop),
    ]
