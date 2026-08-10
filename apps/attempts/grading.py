"""
Javoblarni tekshirish (baholash) mantiqi.

Uchta savol turi qo'llab-quvvatlanadi:

  * SINGLE — A/B/C/D dan bittasi. Tanlangan harf kalitga to'liq mos kelsa 1 ball.
  * MULTI  — A..F dan bir yoki bir nechtasi. To'plam kalitga **aynan** mos
             kelgandagina 1 ball (qisman ball berilmaydi).
  * OPEN   — a) va b) javob maydonlari. Har biri SymPy orqali matematik
             ekvivalentlikka tekshiriladi va har biri 1 balldan.

Baholash natijasi `Answer` obyektiga yoziladi, urinishning umumiy xom balli
esa `Attempt` ga.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.math_expr import compare_answer

from apps.exams.models import Question


@dataclass
class AnswerScore:
    """Bitta javobning baholash natijasi."""

    is_correct_a: bool | None
    is_correct_b: bool | None
    score: float
    max_score: float
    is_empty: bool

    @property
    def is_full(self) -> bool:
        return self.max_score > 0 and self.score >= self.max_score


# --------------------------------------------------------------------------
#  Alohida savol turlarini baholash
# --------------------------------------------------------------------------


def _normalize_selection(value: str) -> set[str]:
    """Tanlangan variantlarni to'plamga aylantiradi."""
    return {ch for ch in (value or "").upper() if ch.isalpha()}


def grade_single(selected: str, question: Question) -> AnswerScore:
    """Bitta javobli savolni baholaydi."""
    chosen = _normalize_selection(selected)
    key = question.correct_set
    if not chosen:
        return AnswerScore(None, None, 0.0, 1.0, True)
    correct = bool(key) and chosen == key
    return AnswerScore(correct, None, 1.0 if correct else 0.0, 1.0, False)


def grade_multi(selected: str, question: Question) -> AnswerScore:
    """
    Ko'p javobli savolni baholaydi.

    To'plam kalitga aynan mos kelishi shart — ortiqcha yoki kam tanlov
    xato hisoblanadi.
    """
    chosen = _normalize_selection(selected)
    key = question.correct_set
    if not chosen:
        return AnswerScore(None, None, 0.0, 1.0, True)
    correct = bool(key) and chosen == key
    return AnswerScore(correct, None, 1.0 if correct else 0.0, 1.0, False)


def grade_open(text_a: str, text_b: str, question: Question) -> AnswerScore:
    """
    Ochiq javobli savolni (36–45) baholaydi.

    Har bir qism (a va b) alohida 1 balldan baholanadi.
    """
    tolerance = float(question.numeric_tolerance or 1e-6)
    parts = int(question.parts or 1)

    text_a = (text_a or "").strip()
    text_b = (text_b or "").strip()

    correct_a: bool | None = None
    correct_b: bool | None = None
    score = 0.0

    if question.answer_a:
        if text_a:
            correct_a = bool(compare_answer(text_a, question.answer_a, tolerance))
            score += 1.0 if correct_a else 0.0
        else:
            correct_a = False

    if parts >= 2 and question.answer_b:
        if text_b:
            correct_b = bool(compare_answer(text_b, question.answer_b, tolerance))
            score += 1.0 if correct_b else 0.0
        else:
            correct_b = False

    max_score = float(parts)
    is_empty = not text_a and not text_b
    return AnswerScore(correct_a, correct_b, score, max_score, is_empty)


# --------------------------------------------------------------------------
#  Umumiy kirish nuqtasi
# --------------------------------------------------------------------------


def grade_answer(answer, question: Question | None = None) -> AnswerScore:
    """
    `Answer` obyektini baholaydi va natijani unga yozadi (saqlamaydi).

    Qaytariladigan qiymat — `AnswerScore`.
    """
    question = question or answer.question

    if question.kind == Question.Kind.SINGLE:
        result = grade_single(answer.selected, question)
    elif question.kind == Question.Kind.MULTI:
        result = grade_multi(answer.selected, question)
    else:
        result = grade_open(answer.text_a, answer.text_b, question)

    answer.is_correct_a = result.is_correct_a
    answer.is_correct_b = result.is_correct_b
    answer.score = result.score
    return result


def grade_attempt(attempt, *, save: bool = True) -> dict:
    """
    Urinishdagi barcha javoblarni qayta baholaydi.

    Qaytaradi: {"raw_score", "max_raw_score", "correct", "wrong", "empty",
                "sections", "responses"}.

    `responses` — Rasch matritsasi uchun 0/1 qiymatlar ro'yxati
    (ochiq savollarda har bir qism alohida element bo'ladi).
    """
    questions = list(
        attempt.exam.questions.filter(is_active=True).order_by("order")
    )
    answers_by_question = {a.question_id: a for a in attempt.answers.all()}

    raw_score = 0.0
    max_raw_score = 0.0
    wrong = 0
    empty = 0
    responses: list[int] = []
    sections: dict[str, dict[str, float]] = {}
    updated: list = []

    for question in questions:
        answer = answers_by_question.get(question.id)
        parts = int(question.parts or 1)
        max_raw_score += parts

        if answer is None:
            empty += 1
            responses.extend([0] * parts)
            _add_section(sections, question, 0.0, parts)
            continue

        result = grade_answer(answer, question)
        raw_score += result.score
        updated.append(answer)

        if result.is_empty:
            empty += 1
        elif result.score <= 0:
            wrong += 1

        if question.kind == Question.Kind.OPEN and parts >= 2:
            responses.append(1 if result.is_correct_a else 0)
            responses.append(1 if result.is_correct_b else 0)
        else:
            responses.extend([1 if result.score > 0 else 0] * parts)

        _add_section(sections, question, result.score, parts)

    if save and updated:
        from apps.attempts.models import Answer as AnswerModel

        AnswerModel.objects.bulk_update(
            updated, ["is_correct_a", "is_correct_b", "score"]
        )

    return {
        "raw_score": round(raw_score, 4),
        "max_raw_score": round(max_raw_score, 4),
        "correct": int(raw_score),
        "wrong": wrong,
        "empty": empty,
        "sections": sections,
        "responses": responses,
    }


def _add_section(sections: dict, question: Question, score: float, parts: int) -> None:
    """Bo'limlar bo'yicha natijani yig'adi (sertifikat uchun)."""
    name = (question.section or "").strip()
    if not name:
        return
    bucket = sections.setdefault(name, {"correct": 0.0, "total": 0.0})
    bucket["correct"] += float(score)
    bucket["total"] += float(parts)


__all__ = [
    "AnswerScore",
    "grade_single",
    "grade_multi",
    "grade_open",
    "grade_answer",
    "grade_attempt",
]
