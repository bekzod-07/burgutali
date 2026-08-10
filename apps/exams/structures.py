"""
Test tuzilmasini (savollar to'plamini) yaratish.

Ikki xil tuzilma qo'llab-quvvatlanadi:

  1. **Oddiy tuzilma** — barcha savollar bir xil turdagi (odatda A/B/C/D).
     Savollar sonini test yaratuvchi belgilaydi (10, 20, 30, 45, 50, 100 ...).

  2. **Milliy sertifikat shabloni** (SRS 3-bo'lim) — 45 ta savol:
       * 1–32  — A, B, C, D (bitta javob);
       * 33–35 — A, B, C, D, E, F (bir yoki bir nechta javob);
       * 36–45 — variantsiz, a) va b) javob maydonlari.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import constants as C

from .models import Exam, Question


@dataclass(frozen=True)
class QuestionSpec:
    """Yaratilishi kerak bo'lgan savolning tavsifi."""

    order: int
    kind: str
    choices_count: int
    parts: int
    section: str = ""

    @property
    def is_open(self) -> bool:
        return self.kind == Question.Kind.OPEN


def national_specs() -> list[QuestionSpec]:
    """Milliy sertifikat formatidagi 45 ta savol tavsifi."""
    specs: list[QuestionSpec] = []

    single_start, single_end = C.NATIONAL_SINGLE_RANGE
    multi_start, multi_end = C.NATIONAL_MULTI_RANGE
    open_start, open_end = C.NATIONAL_OPEN_RANGE

    for order in range(single_start, single_end + 1):
        specs.append(
            QuestionSpec(order, Question.Kind.SINGLE, len(C.SINGLE_CHOICES), 1, "1-qism")
        )
    for order in range(multi_start, multi_end + 1):
        specs.append(
            QuestionSpec(order, Question.Kind.MULTI, len(C.MULTI_CHOICES), 1, "2-qism")
        )
    for order in range(open_start, open_end + 1):
        specs.append(QuestionSpec(order, Question.Kind.OPEN, 0, 2, "3-qism"))
    return specs


def simple_specs(count: int, choices_count: int = 4) -> list[QuestionSpec]:
    """Bir xil turdagi `count` ta savol tavsifi (A/B/C/D)."""
    count = max(1, min(int(count), 500))
    choices_count = max(2, min(int(choices_count), len(C.SINGLE_CHOICES)))
    return [
        QuestionSpec(order, Question.Kind.SINGLE, choices_count, 1)
        for order in range(1, count + 1)
    ]


def build_questions(exam: Exam, specs: list[QuestionSpec]) -> list[Question]:
    """
    Test uchun savollarni yaratadi (mavjudlarini almashtiradi).

    Javob kalitlari keyinroq `apply_keys` orqali kiritiladi.
    """
    exam.questions.all().delete()
    questions = [
        Question(
            exam=exam,
            order=spec.order,
            kind=spec.kind,
            choices_count=spec.choices_count or 4,
            parts=spec.parts,
            section=spec.section,
        )
        for spec in specs
    ]
    created = Question.objects.bulk_create(questions)
    exam.question_count = len(created)
    exam.save(update_fields=["question_count", "updated_at"])
    return created


def describe_structure(exam: Exam) -> str:
    """Test tuzilmasini matn ko'rinishida tavsiflaydi."""
    counts: dict[str, int] = {}
    for question in exam.questions.filter(is_active=True):
        counts[question.kind] = counts.get(question.kind, 0) + 1

    parts: list[str] = []
    labels = {
        Question.Kind.SINGLE: "bitta javobli (A–D)",
        Question.Kind.MULTI: "ko'p javobli (A–F)",
        Question.Kind.OPEN: "ochiq javobli (a, b)",
    }
    for kind, label in labels.items():
        if counts.get(kind):
            parts.append(f"{counts[kind]} ta {label}")
    return ", ".join(parts) if parts else "savollar kiritilmagan"


__all__ = [
    "QuestionSpec",
    "national_specs",
    "simple_specs",
    "build_questions",
    "describe_structure",
]
