"""
Test natijalarini to'liq hisoblash xizmati.

Bosqichlar (TZ 7-bo'lim):
  1. Testdagi barcha yakunlangan urinishlar olinadi.
  2. Har bir javob qayta tekshiriladi (kalit yoki SymPy ekvivalentligi).
  3. Rasch testlarida savol qiyinliklari JMLE bilan kalibrlanadi
     (agar `Exam.auto_calibrate` yoqilgan bo'lsa).
  4. Har bir ishtirokchi uchun `theta` MLE orqali topiladi.
  5. `theta` standartlashtirilgan ballga (maksimum 90.14) aylantiriladi,
     daraja va reyting aniqlanadi.
  6. Test statistikasi yangilanadi.

Oddiy testda (1-tur) Rasch ishlatilmaydi — faqat to'g'ri javoblar soni,
foiz va reyting hisoblanadi.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
from django.db import models, transaction
from django.utils import timezone

from apps.attempts.grading import grade_attempt
from apps.attempts.models import Attempt, ExamStatistics
from apps.exams.models import Exam, Question
from core import constants as C

from . import estimator, scoring

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
#  Item (ballanadigan birlik) tavsifi
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """Rasch matritsasidagi bitta ustun."""

    question_id: int
    order: int
    part: int  # 0 -> a) qism / yagona qism, 1 -> b) qism
    difficulty: float
    locked: bool
    section: str


def build_items(exam: Exam) -> list[Item]:
    """Testdagi barcha ballanadigan birliklar ro'yxatini tuzadi."""
    items: list[Item] = []
    questions = exam.questions.filter(is_active=True).order_by("order")
    for question in questions:
        first, second = question.difficulty_for_part
        items.append(
            Item(
                question_id=question.id,
                order=question.order,
                part=0,
                difficulty=first,
                locked=bool(question.difficulty_locked),
                section=question.section or "",
            )
        )
        if int(question.parts or 1) >= 2:
            items.append(
                Item(
                    question_id=question.id,
                    order=question.order,
                    part=1,
                    difficulty=second,
                    locked=bool(question.difficulty_locked),
                    section=question.section or "",
                )
            )
    return items


# --------------------------------------------------------------------------
#  Asosiy hisoblash
# --------------------------------------------------------------------------


@dataclass
class CalculationReport:
    """Hisoblash yakuni bo'yicha qisqacha hisobot."""

    exam_id: int
    participants: int
    calibrated: bool
    converged: bool
    iterations: int
    reliability: float
    message: str = ""

    def as_text(self) -> str:
        lines = [
            f"Qatnashchilar: {self.participants}",
            f"Kalibrlash: {'ha' if self.calibrated else 'yo‘q'}",
            f"Yaqinlashdi: {'ha' if self.converged else 'yo‘q'} ({self.iterations} iteratsiya)",
            f"Ishonchlilik: {self.reliability:.3f}",
        ]
        if self.message:
            lines.append(self.message)
        return "\n".join(lines)


@transaction.atomic
def calculate_exam(exam: Exam, *, regrade: bool = True) -> CalculationReport:
    """
    Testning barcha natijalarini hisoblaydi va bazaga saqlaydi.

    `regrade=True` bo'lsa javoblar ham qaytadan tekshiriladi.
    """
    exam = Exam.objects.select_for_update().get(pk=exam.pk)
    attempts = list(
        Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED)
        .select_related("user")
        .order_by("id")
    )

    if not attempts:
        _reset_statistics(exam)
        exam.calculated_at = timezone.now()
        if exam.status in {Exam.Status.CLOSED, Exam.Status.ACTIVE}:
            exam.status = Exam.Status.CALCULATED
        exam.save(update_fields=["calculated_at", "status", "updated_at"])
        return CalculationReport(exam.id, 0, False, True, 0, 0.0, "Qatnashchi yo‘q.")

    items = build_items(exam)
    if not items:
        return CalculationReport(exam.id, len(attempts), False, True, 0, 0.0, "Savollar yo‘q.")

    # --- 1. Javoblarni tekshirish va matritsa yig'ish ---
    matrix_rows: list[list[int]] = []
    graded: list[dict] = []
    for attempt in attempts:
        result = grade_attempt(attempt, save=regrade)
        responses = result["responses"]
        # Uzunlikni item lar soniga moslashtiramiz (savol qo'shilgan/o'chirilgan holat)
        if len(responses) < len(items):
            responses = responses + [0] * (len(items) - len(responses))
        elif len(responses) > len(items):
            responses = responses[: len(items)]
        matrix_rows.append(responses)
        graded.append(result)

    matrix = np.asarray(matrix_rows, dtype=float)

    # --- 2. Rasch yoki oddiy baholash ---
    if exam.uses_rasch:
        report = _score_rasch(exam, attempts, graded, matrix, items)
    else:
        report = _score_simple(exam, attempts, graded)

    # --- 3. Reyting ---
    _assign_ranks(exam)

    # --- 4. Statistika ---
    _update_statistics(exam, matrix, items)

    # --- 5. Test holati ---
    exam.calculated_at = timezone.now()
    if exam.status in {Exam.Status.ACTIVE, Exam.Status.CLOSED}:
        exam.status = Exam.Status.CALCULATED
    exam.save(update_fields=["calculated_at", "status", "updated_at"])

    return report


def anchor_theta_min(
    exam: Exam,
    difficulties: np.ndarray,
    *,
    grade: str = C.SCALE_ANCHOR_GRADE,
    share: float = C.CERT_MIN_PERCENT,
) -> float | None:
    """
    Ball shkalasini daraja chegarasiga moslashtiruvchi `theta_min`.

    Savollarning `share` ulushini (55 dan 18 tasini) topgan qatnashchi
    aynan `grade` darajasining quyi chegarasini (46.00 ball) olishi kerak.
    Shkalaning yuqori uchi tegilmaydi: `theta_max` -> `max_ball`.

        ball = max_ball * (theta - theta_min) / (theta_max - theta_min)

    Tenglamani `theta_min` bo'yicha yechamiz. Hisoblab bo'lmasa (savol yo'q,
    chegara noto'g'ri yoki natija ma'nosiz) `None` qaytadi va shkala
    o'zgarishsiz qoladi.
    """
    total = int(np.asarray(difficulties).size)
    if total < 2:
        return None

    anchor_ball = C.grade_lower_bound(grade)
    max_ball = float(exam.max_ball or C.MAX_BALL)
    theta_max = float(exam.theta_max)
    if anchor_ball is None or max_ball <= 0:
        return None

    ratio = float(anchor_ball) / max_ball
    if not 0.0 < ratio < 1.0:
        return None

    # 55 ta birlikdan 32% -> 17.6 -> 18 ta.
    raw = int(math.ceil(total * float(share) / 100.0))
    raw = min(max(raw, 1), total - 1)

    theta_anchor = estimator.theta_for_raw_score(raw, difficulties)
    theta_min = (theta_anchor - ratio * theta_max) / (1.0 - ratio)

    # Shkala teskari yoki juda siqilib qolmasin.
    if not math.isfinite(theta_min) or theta_max - theta_min < 1.0:
        return None
    return round(float(theta_min), 4)


def _score_rasch(
    exam: Exam,
    attempts: list[Attempt],
    graded: list[dict],
    matrix: np.ndarray,
    items: list[Item],
) -> CalculationReport:
    """2- va 3-tur testlar uchun Rasch baholash."""
    anchors: dict[int, float] = {}
    for index, item in enumerate(items):
        if item.locked or not exam.auto_calibrate:
            anchors[index] = item.difficulty

    if exam.auto_calibrate and len(attempts) >= 3:
        calibration = estimator.calibrate(matrix, anchors=anchors or None)
        difficulties = calibration.difficulties
        _persist_difficulties(items, difficulties)
        calibrated = True
        converged = calibration.converged
        iterations = calibration.iterations
    else:
        difficulties = np.asarray([item.difficulty for item in items], dtype=float)
        calibrated = False
        converged = True
        iterations = 0

    # --- Shkalani daraja chegarasiga moslashtiramiz ---
    # Savollarning 32% ini topgan qatnashchi «C» ning quyi chegarasini
    # (46.00 ball) olsin; undan yuqorisi qiyinlikka qarab taqsimlanadi.
    if exam.anchor_scale:
        anchored = anchor_theta_min(exam, difficulties)
        if anchored is not None and abs(anchored - float(exam.theta_min)) > 1e-6:
            exam.theta_min = anchored
            exam.save(update_fields=["theta_min", "updated_at"])

    thetas: list[float] = []
    errors: list[float] = []
    updated: list[Attempt] = []

    for attempt, result, row in zip(attempts, graded, matrix):
        estimate = estimator.estimate_theta(row, difficulties)
        score = scoring.build_score(
            estimate.theta,
            result["raw_score"],
            result["max_raw_score"],
            max_ball=exam.max_ball,
            theta_min=exam.theta_min,
            theta_max=exam.theta_max,
        )
        attempt.raw_score = result["raw_score"]
        attempt.max_raw_score = result["max_raw_score"]
        attempt.percent = score.percent
        attempt.wrong_count = result["wrong"]
        attempt.empty_count = result["empty"]
        attempt.theta = score.theta
        attempt.theta_se = None if not np.isfinite(estimate.standard_error) else round(
            estimate.standard_error, 4
        )
        attempt.ball = score.ball
        attempt.grade = score.grade
        attempt.section_scores = result["sections"]
        attempt.is_scored = True
        attempt.scored_at = timezone.now()
        updated.append(attempt)
        thetas.append(estimate.theta)
        errors.append(estimate.standard_error)

    Attempt.objects.bulk_update(
        updated,
        [
            "raw_score", "max_raw_score", "percent", "wrong_count", "empty_count",
            "theta", "theta_se", "ball", "grade", "section_scores",
            "is_scored", "scored_at", "updated_at",
        ],
        batch_size=500,
    )

    reliability = estimator.person_separation_reliability(thetas, errors)
    return CalculationReport(
        exam_id=exam.id,
        participants=len(attempts),
        calibrated=calibrated,
        converged=converged,
        iterations=iterations,
        reliability=reliability,
    )


def _score_simple(
    exam: Exam, attempts: list[Attempt], graded: list[dict]
) -> CalculationReport:
    """1-tur (oddiy test) uchun baholash — Rasch ishlatilmaydi."""
    updated: list[Attempt] = []
    for attempt, result in zip(attempts, graded):
        percent, ball = scoring.simple_percent_score(
            result["raw_score"], result["max_raw_score"]
        )
        attempt.raw_score = result["raw_score"]
        attempt.max_raw_score = result["max_raw_score"]
        attempt.percent = percent
        attempt.wrong_count = result["wrong"]
        attempt.empty_count = result["empty"]
        attempt.theta = None
        attempt.theta_se = None
        attempt.ball = ball
        attempt.grade = ""
        attempt.section_scores = result["sections"]
        attempt.is_scored = True
        attempt.scored_at = timezone.now()
        updated.append(attempt)

    Attempt.objects.bulk_update(
        updated,
        [
            "raw_score", "max_raw_score", "percent", "wrong_count", "empty_count",
            "theta", "theta_se", "ball", "grade", "section_scores",
            "is_scored", "scored_at", "updated_at",
        ],
        batch_size=500,
    )
    return CalculationReport(
        exam_id=exam.id,
        participants=len(attempts),
        calibrated=False,
        converged=True,
        iterations=0,
        reliability=0.0,
    )


def _persist_difficulties(items: list[Item], difficulties: np.ndarray) -> None:
    """Kalibrlangan qiyinliklarni savollarga qaytarib yozadi."""
    by_question: dict[int, dict[int, float]] = {}
    for index, item in enumerate(items):
        if item.locked:
            continue
        by_question.setdefault(item.question_id, {})[item.part] = float(difficulties[index])

    if not by_question:
        return

    questions = list(Question.objects.filter(id__in=by_question.keys()))
    for question in questions:
        parts = by_question.get(question.id, {})
        if 0 in parts:
            question.difficulty = round(parts[0], 4)
        if 1 in parts:
            question.difficulty_b = round(parts[1], 4)
    Question.objects.bulk_update(questions, ["difficulty", "difficulty_b", "updated_at"])


def _assign_ranks(exam: Exam) -> None:
    """
    Reyting o'rinlarini belgilaydi — ketma-ket, takrorlanmaydigan raqamlar.

    O'rinlar 1, 2, 3, ... tartibida yuradi: bir xil o'rin ikki marta
    yozilmaydi. Ballari teng chiqqanda testni **oldinroq** topshirgan
    yuqoriroq o'rinni oladi, kechroq topshirgani esa keyingi o'ringa
    tushadi (masalan 10 va 11).
    """
    attempts = list(
        Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED)
        .order_by(
            models.F("ball").desc(nulls_last=True),
            "-raw_score",
            models.F("submitted_at").asc(nulls_last=True),
            "id",
        )
    )
    for index, attempt in enumerate(attempts, start=1):
        attempt.rank = index
    if attempts:
        Attempt.objects.bulk_update(attempts, ["rank"], batch_size=500)


def _update_statistics(exam: Exam, matrix: np.ndarray, items: list[Item]) -> None:
    """Test bo'yicha yig'ma statistikani yangilaydi."""
    attempts = list(Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED))
    stats, _ = ExamStatistics.objects.get_or_create(exam=exam)

    if not attempts:
        _reset_statistics(exam, stats)
        return

    balls = np.asarray([a.ball or 0.0 for a in attempts], dtype=float)
    percents = np.asarray([a.percent or 0.0 for a in attempts], dtype=float)
    raws = np.asarray([a.raw_score or 0.0 for a in attempts], dtype=float)

    distribution: dict[str, int] = {}
    for attempt in attempts:
        grade = attempt.grade or (C.NO_GRADE if exam.uses_rasch else "—")
        distribution[grade] = distribution.get(grade, 0) + 1

    item_stats: list[dict] = []
    if matrix.size and matrix.shape[1] == len(items):
        p_values = matrix.mean(axis=0)
        biserial = estimator._point_biserial(matrix)  # noqa: SLF001
        # Diagramma uchun odamlar soni ham saqlanadi: nechtasi savolni
        # topgan va nechtasi topa olmagan (`apps.exports.charts`).
        correct_counts = matrix.sum(axis=0)
        respondents = int(matrix.shape[0])
        for index, item in enumerate(items):
            item_stats.append(
                {
                    "order": item.order,
                    "part": "b" if item.part else "a",
                    "p_value": round(float(p_values[index]), 4),
                    "difficulty": round(float(item.difficulty), 4),
                    "point_biserial": round(float(biserial[index]), 4),
                    "correct": int(correct_counts[index]),
                    "total": respondents,
                }
            )

    stats.participants = len(attempts)
    stats.avg_raw_score = round(float(raws.mean()), 3)
    stats.avg_percent = round(float(percents.mean()), 2)
    stats.avg_ball = round(float(balls.mean()), 2)
    stats.max_ball_achieved = round(float(balls.max()), 2)
    stats.min_ball_achieved = round(float(balls.min()), 2)
    stats.std_ball = round(float(balls.std(ddof=1)) if len(balls) > 1 else 0.0, 3)
    stats.reliability = round(float(estimator.kr20(matrix)) if matrix.size else 0.0, 4)
    stats.grade_distribution = distribution
    stats.item_statistics = item_stats
    stats.save()


def _reset_statistics(exam: Exam, stats: ExamStatistics | None = None) -> None:
    """Statistikani nolga qaytaradi."""
    stats = stats or ExamStatistics.objects.get_or_create(exam=exam)[0]
    stats.participants = 0
    stats.avg_raw_score = 0.0
    stats.avg_percent = 0.0
    stats.avg_ball = 0.0
    stats.max_ball_achieved = 0.0
    stats.min_ball_achieved = 0.0
    stats.std_ball = 0.0
    stats.reliability = 0.0
    stats.grade_distribution = {}
    stats.item_statistics = []
    stats.save()


# --------------------------------------------------------------------------
#  Bitta urinishni tezkor baholash (test hali yopilmaganda ko'rsatish uchun)
# --------------------------------------------------------------------------


def score_attempt_preliminary(attempt: Attempt) -> dict:
    """
    Bitta urinishni joriy qiyinliklar asosida baholaydi.

    Bu — dastlabki natija: butun test bo'yicha kalibrlash o'tkazilmaydi.
    Oddiy testlarda (1-tur) natija shu yerda yakuniy hisoblanadi.
    """
    exam = attempt.exam
    result = grade_attempt(attempt, save=True)

    if exam.uses_rasch:
        items = build_items(exam)
        difficulties = [item.difficulty for item in items]
        responses = result["responses"]
        if len(responses) < len(items):
            responses = responses + [0] * (len(items) - len(responses))
        estimate = estimator.estimate_theta(responses[: len(items)], difficulties)
        score = scoring.build_score(
            estimate.theta,
            result["raw_score"],
            result["max_raw_score"],
            max_ball=exam.max_ball,
            theta_min=exam.theta_min,
            theta_max=exam.theta_max,
        )
        attempt.theta = score.theta
        attempt.theta_se = None if not np.isfinite(estimate.standard_error) else round(
            estimate.standard_error, 4
        )
        attempt.ball = score.ball
        attempt.grade = score.grade
        attempt.percent = score.percent
    else:
        percent, ball = scoring.simple_percent_score(
            result["raw_score"], result["max_raw_score"]
        )
        attempt.theta = None
        attempt.theta_se = None
        attempt.ball = ball
        attempt.grade = ""
        attempt.percent = percent

    attempt.raw_score = result["raw_score"]
    attempt.max_raw_score = result["max_raw_score"]
    attempt.wrong_count = result["wrong"]
    attempt.empty_count = result["empty"]
    attempt.section_scores = result["sections"]
    attempt.is_scored = True
    attempt.scored_at = timezone.now()
    attempt.save(
        update_fields=[
            "raw_score", "max_raw_score", "percent", "wrong_count", "empty_count",
            "theta", "theta_se", "ball", "grade", "section_scores",
            "is_scored", "scored_at", "updated_at",
        ]
    )
    return result


__all__ = [
    "Item",
    "CalculationReport",
    "build_items",
    "calculate_exam",
    "score_attempt_preliminary",
]
