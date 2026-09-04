"""
Mini App API uchun ma'lumotlarni JSON ko'rinishiga o'girish.

Bu yerda hech qanday biznes-mantiq yo'q — faqat modellarni ilova
tushunadigan lug'atlarga aylantirish.
"""

from __future__ import annotations

from django.utils import timezone

from apps.attempts.models import Attempt
from apps.exams.models import Exam, Question
from core import constants as C


# --------------------------------------------------------------------------
#  Yordamchilar
# --------------------------------------------------------------------------


def iso(value) -> str | None:
    """Sana-vaqtni ISO formatida qaytaradi (mahalliy vaqt zonasida)."""
    if value is None:
        return None
    return timezone.localtime(value).isoformat()


def human_datetime(value) -> str:
    """Sana-vaqtning o'qishga qulay ko'rinishi."""
    if value is None:
        return "cheklanmagan"
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")


# --------------------------------------------------------------------------
#  Foydalanuvchi
# --------------------------------------------------------------------------


def user_dict(user) -> dict:
    """Foydalanuvchi haqidagi asosiy ma'lumot."""
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "full_name": user.full_name or user.display_name,
        "phone": user.phone,
        "username": user.username,
        "is_admin": bool(user.is_admin),
        "is_registered": bool(user.is_registered),
    }


# --------------------------------------------------------------------------
#  Testlar
# --------------------------------------------------------------------------


def exam_dict(exam: Exam, *, participants: int | None = None, detailed: bool = False) -> dict:
    """Test haqidagi ma'lumot."""
    data = {
        "id": exam.id,
        "code": exam.code,
        "title": exam.title,
        "description": exam.description,
        "type": exam.exam_type,
        "type_label": exam.get_exam_type_display(),
        "type_short": {"simple": "1-tur", "rasch_free": "2-tur", "rasch_paid": "3-tur"}.get(
            exam.exam_type, ""
        ),
        "status": exam.status,
        "status_label": exam.get_status_display(),
        "question_count": exam.question_count,
        "uses_rasch": exam.uses_rasch,
        "requires_code": exam.requires_access_code,
        "certificate": exam.can_issue_certificate,
        "ends_at": iso(exam.ends_at),
        "ends_at_human": human_datetime(exam.ends_at),
        "starts_at": iso(exam.starts_at),
        "is_open": exam.accepts_answers,
        "results_published": exam.results_available,
        "participants": participants,
        "owner": exam.owner.full_name or exam.owner.display_name if exam.owner_id else "",
    }
    if detailed:
        data.update(
            {
                "max_raw_score": exam.max_raw_score,
                "max_ball": exam.max_ball,
                "is_national": exam.is_national_template,
                "show_results": exam.show_results_to_participants,
                "show_answers": exam.show_correct_answers,
                "show_rating": exam.show_rating_to_participants,
                "duration_minutes": exam.duration_minutes,
                "created_at": iso(exam.created_at),
                "deep_link": exam.deep_link,
            }
        )
    return data


def question_dict(question: Question, answer=None) -> dict:
    """Savol va unga berilgan javob."""
    return {
        "id": question.id,
        "order": question.order,
        "kind": question.kind,
        "text": question.text,
        "section": question.section,
        "parts": int(question.parts or 1),
        "choices": list(question.choice_letters),
        "answer": {
            "selected": answer.selected if answer else "",
            "text_a": answer.text_a if answer else "",
            "text_b": answer.text_b if answer else "",
        },
        "answered": bool(
            answer and (answer.selected or answer.text_a or answer.text_b)
        ),
    }


# --------------------------------------------------------------------------
#  Urinishlar va natijalar
# --------------------------------------------------------------------------


def attempt_dict(attempt: Attempt, *, total_participants: int = 0) -> dict:
    """Urinish va uning natijasi."""
    exam = attempt.exam
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "exam_code": exam.code,
        "exam_title": exam.title,
        "uses_rasch": exam.uses_rasch,
        "exam_status": exam.status,
        "results_published": exam.results_available,
        "show_results": exam.show_results_to_participants,
        "show_answers": exam.show_correct_answers,
        "show_rating": exam.show_rating_to_participants,
        "certificate_enabled": exam.can_issue_certificate,
        "status": attempt.status,
        "current_order": attempt.current_order,
        "raw_score": attempt.raw_score,
        "max_raw_score": attempt.max_raw_score,
        "correct": int(attempt.raw_score),
        "wrong": attempt.wrong_count,
        "empty": attempt.empty_count,
        "percent": round(attempt.percent, 1),
        # RASH testida qatnashchiga shu foiz ko'rsatiladi (`ball * 100 / 65`).
        "award_percent": C.certificate_percent(attempt.ball, attempt.grade),
        # Fan ballari: asosiy fanlar foizga proporsional (100% -> 93 va 63),
        # majburiy fan esa sertifikat olganlarning hammasiga to'liq (11 ball).
        "subjects": [
            {"name": name, "value": value}
            for name, value in zip(
                C.subject_names(), C.subject_scores(attempt.ball, attempt.grade)
            )
        ],
        "theta": attempt.theta,
        "ball": attempt.display_ball,
        "grade": attempt.grade or "",
        "rank": attempt.rank,
        "total_participants": total_participants,
        "is_scored": attempt.is_scored,
        "submitted_at": iso(attempt.submitted_at),
        "submitted_at_human": human_datetime(attempt.submitted_at),
        "duration_seconds": attempt.duration_seconds,
        "sections": attempt.section_scores or {},
    }


def review_dict(rows: list[dict]) -> list[dict]:
    """Javoblarni ko'rib chiqish jadvali."""
    mapping = {"✓": "correct", "✗": "wrong", "±": "partial", "·": "empty"}
    result = []
    for row in rows:
        result.append(
            {
                "order": row["order"],
                "kind": row["kind"],
                "given": row["given"],
                "correct": row["correct"],
                "score": row["score"],
                "max_score": row["max_score"],
                "state": mapping.get(row["icon"], "empty"),
            }
        )
    return result


def rating_dict(attempts, *, uses_rasch: bool, me_id: int | None = None) -> list[dict]:
    """
    Reyting jadvali.

    Nom `Attempt.public_label` dan olinadi: pullik RASH testida ism o'rniga
    ishtirokchining ID raqami ko'rsatiladi.
    """
    rows = []
    for index, attempt in enumerate(attempts, start=1):
        rows.append(
            {
                "place": attempt.rank or index,
                "name": attempt.public_label,
                "ball": attempt.display_ball if uses_rasch else None,
                "grade": attempt.grade or "",
                "raw_score": attempt.raw_score,
                "max_raw_score": attempt.max_raw_score,
                "percent": round(attempt.percent, 1),
                "is_me": attempt.id == me_id,
            }
        )
    return rows


# --------------------------------------------------------------------------
#  Sertifikatlar
# --------------------------------------------------------------------------


def certificate_dict(certificate) -> dict:
    """Sertifikat ma'lumoti va yuklab olish havolasi."""
    return {
        "id": certificate.id,
        "number": certificate.number,
        "attempt_id": certificate.attempt_id,
        "exam_title": certificate.exam_title,
        "exam_date": certificate.exam_date.strftime("%d.%m.%Y"),
        "ball": certificate.display_ball,
        "grade": certificate.grade or "",
        "rank": certificate.display_rank,
        "percent": certificate.percent,
        "award_percent": certificate.award_percent,
        "issued_at": certificate.issued_at.strftime("%d.%m.%Y")
        if certificate.issued_at
        else "",
        "download_url": (
            f"/verify/{certificate.number}/yuklab-olish/?t={certificate.verify_token}"
        ),
        "verify_url": f"/verify/{certificate.number}/?t={certificate.verify_token}",
        "is_valid": certificate.is_valid,
    }


# --------------------------------------------------------------------------
#  Statistika
# --------------------------------------------------------------------------


def statistics_dict(statistics) -> dict | None:
    """Test statistikasi."""
    if statistics is None or not statistics.participants:
        return None
    return {
        "participants": statistics.participants,
        "avg_raw_score": round(statistics.avg_raw_score, 2),
        "avg_percent": round(statistics.avg_percent, 1),
        "avg_ball": round(statistics.avg_ball, 2),
        "max_ball": round(statistics.max_ball_achieved, 2),
        "min_ball": round(statistics.min_ball_achieved, 2),
        "std_ball": round(statistics.std_ball, 2),
        "reliability": round(statistics.reliability, 3),
        "grades": [
            {"grade": grade, "count": count}
            for grade, count in statistics.grade_rows
            if count
        ],
    }


__all__ = [
    "iso",
    "human_datetime",
    "user_dict",
    "exam_dict",
    "question_dict",
    "attempt_dict",
    "review_dict",
    "rating_dict",
    "certificate_dict",
    "statistics_dict",
]
