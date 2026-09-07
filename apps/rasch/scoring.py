"""
Rasch `theta` qiymatini standartlashtirilgan ballga aylantirish.

SRS 8-bo'limi maksimal standartlashtirilgan ball sifatida **90.14** ni
belgilaydi va darajalarni shu ball asosida beradi. Shuning uchun logit
shkalasidagi `theta` chiziqli ravishda [0; 90.14] oralig'iga o'tkaziladi:

        ball = max_ball * (theta - theta_min) / (theta_max - theta_min)

Standart chegaralar: theta_min = -4.0, theta_max = +4.0. Bu chegaralar
har bir test uchun alohida sozlanishi mumkin (`Exam.theta_min/theta_max`).

Natijada:
  theta = +0.0826  ->  46.00  (C darajasining quyi chegarasi)
  theta =  0.0000  ->  45.07  (o'rtacha qobiliyat — daraja olinmaydi)
  theta = +2.2126  ->  70.00  (A+ darajasining quyi chegarasi)
  theta = +4.0000  ->  90.14  (maksimal ball)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core import constants as C

from .estimator import probability


@dataclass(frozen=True)
class ScoreResult:
    """Yakuniy ball va daraja."""

    theta: float
    ball: float
    grade: str
    percent: float
    raw_score: float
    max_raw_score: float

    @property
    def display_ball(self) -> str:
        return f"{self.ball:.2f}"


def theta_to_ball(
    theta: float,
    *,
    max_ball: float = C.MAX_BALL,
    theta_min: float = C.THETA_MIN,
    theta_max: float = C.THETA_MAX,
) -> float:
    """`theta` ni standartlashtirilgan ballga aylantiradi."""
    if theta is None:
        return 0.0
    span = float(theta_max) - float(theta_min)
    if span <= 0:
        return 0.0
    normalized = (float(theta) - float(theta_min)) / span
    ball = float(max_ball) * normalized
    return round(float(np.clip(ball, 0.0, float(max_ball))), 2)


def ball_to_theta(
    ball: float,
    *,
    max_ball: float = C.MAX_BALL,
    theta_min: float = C.THETA_MIN,
    theta_max: float = C.THETA_MAX,
) -> float:
    """Teskari almashtirish: balldan `theta` ni topadi."""
    if max_ball <= 0:
        return float(theta_min)
    span = float(theta_max) - float(theta_min)
    return float(theta_min) + span * (float(ball) / float(max_ball))


def grade_for(ball: float) -> str:
    """Ball uchun darajani qaytaradi (SRS 8-bo'limdagi jadval)."""
    return C.grade_for_ball(ball)


def build_score(
    theta: float,
    raw_score: float,
    max_raw_score: float,
    *,
    max_ball: float = C.MAX_BALL,
    theta_min: float = C.THETA_MIN,
    theta_max: float = C.THETA_MAX,
) -> ScoreResult:
    """Yakuniy natija obyektini yig'adi."""
    ball = theta_to_ball(theta, max_ball=max_ball, theta_min=theta_min, theta_max=theta_max)
    percent = round(raw_score / max_raw_score * 100.0, 2) if max_raw_score else 0.0
    return ScoreResult(
        theta=round(float(theta), 4),
        ball=ball,
        grade=grade_for(ball),
        percent=percent,
        raw_score=float(raw_score),
        max_raw_score=float(max_raw_score),
    )


def expected_score(theta: float, difficulties) -> float:
    """Berilgan `theta` da kutilayotgan xom ball."""
    b = np.asarray(list(difficulties), dtype=float)
    if b.size == 0:
        return 0.0
    return float(probability(theta, b).sum())


def test_information(theta: float, difficulties) -> float:
    """Testning berilgan `theta` nuqtasidagi informatsiyasi."""
    b = np.asarray(list(difficulties), dtype=float)
    if b.size == 0:
        return 0.0
    p = probability(theta, b)
    return float((p * (1.0 - p)).sum())


def combine_with_essay(
    test_ball: float | None,
    essay_ball: float | None,
    *,
    max_ball: float = C.MAX_BALL,
    essay_max_ball: float | None = None,
) -> float | None:
    """
    Test balli va esse ballini birlashtiradi: ``(test + esse) / 2``.

    Esse boshqa shkalada baholangan bo'lsa (`essay_max_ball`), u avval
    test shkalasiga keltiriladi, shundan keyin o'rtacha olinadi::

        esse_moslangan = esse * max_ball / essay_max_ball
        yakuniy        = (test + esse_moslangan) / 2

    Standart holatda ikkala shkala ham 90.14 ga teng, shuning uchun
    hisob aynan «qo'shib ikkiga bo'lish» bo'lib qoladi.

    Esse balli kiritilmagan bo'lsa (`None`) — test ballining o'zi
    qaytariladi: qatnashchi esse baholanmagani uchun jazolanmaydi.
    """
    if test_ball is None:
        return None
    test_ball = float(test_ball)
    if essay_ball is None:
        return round(test_ball, 2)

    scale = float(essay_max_ball or max_ball)
    if scale <= 0:
        scale = float(max_ball)
    scaled = float(essay_ball) * float(max_ball) / scale
    scaled = float(np.clip(scaled, 0.0, float(max_ball)))

    combined = (test_ball + scaled) / 2.0
    return round(float(np.clip(combined, 0.0, float(max_ball))), 2)


def simple_percent_score(raw_score: float, max_raw_score: float) -> tuple[float, float]:
    """
    1-tur (oddiy test) uchun natija: (foiz, 100 ballik shkaladagi ball).

    Rasch modeli ishlatilmaydi — faqat to'g'ri javoblar soni va foiz.
    """
    if max_raw_score <= 0:
        return 0.0, 0.0
    percent = round(raw_score / max_raw_score * 100.0, 2)
    return percent, percent


__all__ = [
    "ScoreResult",
    "theta_to_ball",
    "ball_to_theta",
    "grade_for",
    "build_score",
    "expected_score",
    "test_information",
    "combine_with_essay",
    "simple_percent_score",
]
