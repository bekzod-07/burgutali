"""Test topshirish bilan ishlash (asinxron)."""

from __future__ import annotations

from asgiref.sync import sync_to_async

from apps.attempts import services as attempt_services
from apps.attempts.models import Attempt
from core import constants as C
from core.db_retry import sync_db_call

# --------------------------------------------------------------------------
#  Yozuvchi amallar SQLite qulfida qayta bajariladi: bot va web-server
#  bitta faylga yozadi, imtihon paytida esa yozuvlar bir-biriga urilishi
#  mumkin (`core/db_retry.py` ga qarang).
# --------------------------------------------------------------------------

can_participate = sync_to_async(attempt_services.can_participate, thread_sensitive=True)
start_attempt = sync_db_call(attempt_services.start_attempt)
get_draft_attempt = sync_to_async(attempt_services.get_draft_attempt, thread_sensitive=True)
cancel_attempt = sync_db_call(attempt_services.cancel_attempt)
save_answer = sync_db_call(attempt_services.save_answer)
toggle_multi_choice = sync_db_call(attempt_services.toggle_multi_choice)
set_current_order = sync_db_call(attempt_services.set_current_order)
progress = sync_to_async(attempt_services.progress, thread_sensitive=True)
unanswered_orders = sync_to_async(attempt_services.unanswered_orders, thread_sensitive=True)
submit_attempt = sync_db_call(attempt_services.submit_attempt)
get_result = sync_to_async(attempt_services.get_result, thread_sensitive=True)
rating = sync_to_async(attempt_services.rating, thread_sensitive=True)
#: E'lon qilinadigan reyting — haqiqiy natijalar va administrator
#: qo'shgan qatorlar birga (`apps.attempts.services.public_ranking`).
public_ranking = sync_to_async(
    attempt_services.public_ranking, thread_sensitive=True
)
participants_count = sync_to_async(attempt_services.participants_count, thread_sensitive=True)
answer_review = sync_to_async(attempt_services.answer_review, thread_sensitive=True)
user_history = sync_to_async(attempt_services.user_history, thread_sensitive=True)


@sync_to_async(thread_sensitive=True)
def get_attempt(attempt_id: int) -> Attempt | None:
    """ID bo'yicha urinishni qaytaradi."""
    return (
        Attempt.objects.select_related("exam", "user")
        .filter(pk=attempt_id)
        .first()
    )


@sync_to_async(thread_sensitive=True)
def selected_value(attempt_id: int, order: int) -> str:
    """Savolga tanlangan variant(lar)ni qaytaradi."""
    answer = Attempt.objects.get(pk=attempt_id).answers.filter(order=order).first()
    return answer.selected if answer else ""


@sync_to_async(thread_sensitive=True)
def answer_values(attempt_id: int, order: int) -> tuple[str, str, str]:
    """(tanlangan, a-javob, b-javob) qiymatlarini qaytaradi."""
    answer = Attempt.objects.get(pk=attempt_id).answers.filter(order=order).first()
    if answer is None:
        return "", "", ""
    return answer.selected, answer.text_a, answer.text_b


@sync_to_async(thread_sensitive=True)
def answered_orders(attempt_id: int) -> set[int]:
    """Javob berilgan savollar tartib raqamlari."""
    answers = Attempt.objects.get(pk=attempt_id).answers.all()
    return {
        answer.order
        for answer in answers
        if answer.selected or answer.text_a or answer.text_b
    }


@sync_to_async(thread_sensitive=True)
def result_snapshot(attempt_id: int) -> dict:
    """Natija haqidagi asosiy ma'lumotlar."""
    attempt = Attempt.objects.select_related("exam").get(pk=attempt_id)
    total = Attempt.objects.filter(
        exam=attempt.exam, status=Attempt.Status.SUBMITTED
    ).count()
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "title": attempt.exam.title,
        "uses_rasch": attempt.exam.uses_rasch,
        "status": attempt.exam.status,
        "show_results": attempt.exam.show_results_to_participants,
        "show_answers": attempt.exam.show_correct_answers,
        "show_rating": attempt.exam.show_rating_to_participants,
        "certificate": attempt.exam.can_issue_certificate,
        "raw_score": attempt.raw_score,
        "max_raw_score": attempt.max_raw_score,
        "correct": int(attempt.raw_score),
        "wrong": attempt.wrong_count,
        "empty": attempt.empty_count,
        "percent": round(attempt.percent, 1),
        # RASH testida qatnashchiga shu foiz ko'rsatiladi (`ball * 100 / 65`),
        # to'g'ri javoblar ulushi emas.
        "award_percent": C.certificate_percent(attempt.result_ball, attempt.grade),
        "ball": attempt.display_ball,
        # --- Esse (yozma qism) ---
        "essay_enabled": bool(attempt.exam.essay_enabled),
        "test_ball": attempt.display_test_ball,
        "essay_ball": (
            "baholanmoqda" if attempt.essay_pending else attempt.display_essay_ball
        ),
        "grade": attempt.grade or "—",
        "rank": f"{attempt.rank} / {total}" if attempt.rank else "—",
        "is_scored": attempt.is_scored,
    }


@sync_to_async(thread_sensitive=True)
def submitted_participants(exam_id: int) -> list[tuple[int, int]]:
    """(telegram_id, attempt_id) juftliklari — natijalarni tarqatish uchun."""
    return list(
        Attempt.objects.filter(exam_id=exam_id, status=Attempt.Status.SUBMITTED)
        .select_related("user")
        .values_list("user__telegram_id", "id")
    )


__all__ = [name for name in dir() if not name.startswith("_")]
