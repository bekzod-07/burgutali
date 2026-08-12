"""
Test topshirish jarayonini boshqarish xizmatlari.

Oqim:
  1. `can_participate` — foydalanuvchi testga kira oladimi?
  2. `start_attempt`   — DRAFT urinish ochiladi (ID kod faollashtiriladi).
  3. `save_answer`     — har bir javob darhol bazaga saqlanadi.
  4. `submit_attempt`  — yakuniy yuborish; shundan keyingina ID kod
                         "Ishlatilgan" holatiga o'tadi.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.exams.models import Exam, Question
from apps.users.models import UserAction
from apps.users.services import log_action

from .models import Answer, Attempt

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
#  Kirish huquqini tekshirish
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ParticipationCheck:
    """Testga kirish imkoniyati tekshiruvining natijasi."""

    ok: bool
    message: str = ""

    def __bool__(self) -> bool:
        return self.ok


def can_participate(user, exam: Exam) -> ParticipationCheck:
    """Foydalanuvchi ushbu testda qatnasha oladimi."""
    if not user.is_registered:
        return ParticipationCheck(False, "Avval ro'yxatdan o'tishingiz kerak.")
    if user.is_blocked:
        return ParticipationCheck(False, "Hisobingiz bloklangan.")

    if exam.status == Exam.Status.DRAFT:
        return ParticipationCheck(False, "Bu test hali faollashtirilmagan.")
    if exam.status in {Exam.Status.CLOSED, Exam.Status.CALCULATED, Exam.Status.PUBLISHED}:
        return ParticipationCheck(False, "Bu test yakunlangan — javoblar qabul qilinmaydi.")
    if exam.status == Exam.Status.ARCHIVED:
        return ParticipationCheck(False, "Bu test arxivlangan.")
    if exam.is_not_started:
        moment = timezone.localtime(exam.starts_at).strftime("%d.%m.%Y %H:%M")
        return ParticipationCheck(False, f"Test {moment} da boshlanadi.")
    if exam.is_time_over:
        return ParticipationCheck(False, "Testni topshirish vaqti tugagan.")
    if exam.question_count <= 0:
        return ParticipationCheck(False, "Testda savollar yo'q.")

    if Attempt.objects.filter(
        exam=exam, user=user, status=Attempt.Status.SUBMITTED
    ).exists():
        return ParticipationCheck(False, "Siz bu testda allaqachon qatnashgansiz.")

    return ParticipationCheck(True)


# --------------------------------------------------------------------------
#  Urinishni boshlash
# --------------------------------------------------------------------------


@transaction.atomic
def start_attempt(user, exam: Exam, access_code=None) -> Attempt:
    """
    Yangi urinish ochadi yoki tugallanmagan urinishni davom ettiradi.

    Pullik testda `access_code` berilishi shart — u faollashtiriladi.
    """
    attempt = (
        Attempt.objects.filter(exam=exam, user=user, status=Attempt.Status.DRAFT)
        .order_by("-created_at")
        .first()
    )
    if attempt is None:
        attempt = Attempt.objects.create(
            exam=exam,
            user=user,
            full_name=user.full_name or user.display_name,
            phone=user.phone,
            status=Attempt.Status.DRAFT,
            started_at=timezone.now(),
            current_order=1,
            max_raw_score=exam.max_raw_score,
        )
        log_action(
            user,
            UserAction.Kind.ATTEMPT_STARTED,
            f"«{exam.title}» testini boshladi",
            exam_id=exam.id,
            attempt_id=attempt.id,
        )

    if access_code is not None:
        from apps.accesscodes.services import activate_code

        activate_code(access_code, user, attempt.full_name)

    return attempt


def get_draft_attempt(user, exam: Exam) -> Attempt | None:
    """Foydalanuvchining ushbu testdagi tugallanmagan urinishi."""
    return (
        Attempt.objects.filter(exam=exam, user=user, status=Attempt.Status.DRAFT)
        .order_by("-created_at")
        .first()
    )


def cancel_attempt(attempt: Attempt) -> None:
    """Urinishni bekor qiladi va ID kodni bo'shatadi."""
    from apps.accesscodes.services import find_active_code, release_code

    attempt.status = Attempt.Status.CANCELLED
    attempt.save(update_fields=["status", "updated_at"])

    code = find_active_code(attempt.user, attempt.exam)
    if code is not None:
        release_code(code)


# --------------------------------------------------------------------------
#  Javoblarni saqlash
# --------------------------------------------------------------------------


@transaction.atomic
def save_answer(
    attempt: Attempt,
    question: Question,
    *,
    selected: str | None = None,
    text_a: str | None = None,
    text_b: str | None = None,
) -> Answer:
    """Bitta savolga berilgan javobni saqlaydi (mavjud bo'lsa yangilaydi)."""
    answer, _ = Answer.objects.get_or_create(
        attempt=attempt,
        question=question,
        defaults={"order": question.order},
    )
    answer.order = question.order

    if selected is not None:
        answer.selected = "".join(
            sorted({ch.upper() for ch in selected if ch.isalpha()})
        )[:8]
    if text_a is not None:
        answer.text_a = str(text_a).strip()[:255]
    if text_b is not None:
        answer.text_b = str(text_b).strip()[:255]

    answer.answered_at = timezone.now()
    answer.save(
        update_fields=["order", "selected", "text_a", "text_b", "answered_at", "updated_at"]
    )
    return answer


def toggle_multi_choice(attempt: Attempt, question: Question, letter: str) -> str:
    """
    Moslashtirish savolida (33–35, A–F) variantni belgilaydi.

    Faqat **bitta** variant belgilanadi: yangi harf oldingisini almashtiradi,
    o'sha harf qayta bosilsa esa belgi olib tashlanadi.

    Qaytaradi: yangilangan tanlov satri (masalan, "C").
    """
    answer = Answer.objects.filter(attempt=attempt, question=question).first()
    current = (answer.selected if answer and answer.selected else "").upper()
    letter = (letter or "").upper()[:1]
    value = "" if letter and letter == current else letter
    save_answer(attempt, question, selected=value)
    return value


def set_current_order(attempt: Attempt, order: int) -> None:
    """Joriy savol raqamini yangilaydi (uzilishdan keyin davom ettirish uchun)."""
    attempt.current_order = max(1, int(order))
    attempt.save(update_fields=["current_order", "updated_at"])


def answered_map(attempt: Attempt) -> dict[int, Answer]:
    """`{savol_tartibi: Answer}` lug'ati."""
    return {answer.order: answer for answer in attempt.answers.all()}


def progress(attempt: Attempt) -> tuple[int, int]:
    """(javob berilgan savollar soni, jami savollar soni)."""
    total = attempt.exam.question_count
    answered = (
        attempt.answers.exclude(selected="", text_a="", text_b="").count()
    )
    return answered, total


def unanswered_orders(attempt: Attempt) -> list[int]:
    """Javob berilmagan savollar tartib raqamlari."""
    answers = {
        answer.order
        for answer in attempt.answers.all()
        if answer.selected or answer.text_a or answer.text_b
    }
    all_orders = list(
        attempt.exam.questions.filter(is_active=True)
        .order_by("order")
        .values_list("order", flat=True)
    )
    return [order for order in all_orders if order not in answers]


# --------------------------------------------------------------------------
#  Yakuniy yuborish
# --------------------------------------------------------------------------


@transaction.atomic
def submit_attempt(attempt: Attempt) -> Attempt:
    """
    Urinishni yakunlaydi.

    Tartib muhim: avval urinish SUBMITTED holatida saqlanadi, keyin
    ID kod "Ishlatilgan" deb belgilanadi (TZ talabi).
    """
    from apps.accesscodes.services import consume_code, find_active_code
    from apps.rasch.services import score_attempt_preliminary

    attempt = Attempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.status == Attempt.Status.SUBMITTED:
        return attempt

    attempt.max_raw_score = attempt.exam.max_raw_score
    attempt.mark_submitted()
    attempt.save(
        update_fields=[
            "status", "submitted_at", "duration_seconds", "max_raw_score", "updated_at"
        ]
    )

    # Javoblar saqlangandan keyingina ID kod ishlatilgan hisoblanadi.
    code = find_active_code(attempt.user, attempt.exam)
    if code is not None:
        consume_code(code, attempt)

    # Dastlabki natija (oddiy testda — yakuniy natija).
    try:
        score_attempt_preliminary(attempt)
    except Exception:  # pragma: no cover - baholash xatosi javobni yo'qotmasin
        logger.exception("Urinishni baholashda xato: attempt_id=%s", attempt.id)

    log_action(
        attempt.user,
        UserAction.Kind.ATTEMPT_SUBMITTED,
        f"«{attempt.exam.title}» testiga javob yubordi",
        exam_id=attempt.exam_id,
        attempt_id=attempt.id,
    )
    return attempt


# --------------------------------------------------------------------------
#  Natijalar va reyting
# --------------------------------------------------------------------------


def get_result(exam: Exam, user) -> Attempt | None:
    """Foydalanuvchining ushbu testdagi yakuniy natijasi."""
    return (
        Attempt.objects.filter(exam=exam, user=user, status=Attempt.Status.SUBMITTED)
        .select_related("exam")
        .first()
    )


def ranked_attempts(exam: Exam):
    """
    Test bo'yicha tartiblangan urinishlar so'rovi.

    `access_code` ham birga olinadi — pullik testda natijalar ism o'rniga
    ID raqami bilan e'lon qilinadi (`Attempt.public_label`).
    """
    return (
        Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED)
        .select_related("user", "exam", "access_code")
        .ranked()
    )


def rating(exam: Exam, limit: int | None = None) -> list[Attempt]:
    """Test bo'yicha reyting ro'yxati."""
    queryset = ranked_attempts(exam)
    if limit:
        queryset = queryset[:limit]
    return list(queryset)


def participants_count(exam: Exam) -> int:
    """Testni topshirganlar soni."""
    return Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED).count()


def answer_review(attempt: Attempt) -> list[dict]:
    """
    Har bir savol bo'yicha to'g'ri/xato ma'lumoti.

    TZ (1-tur): "Test tugagandan keyin ... to'g'ri va xato qilgan savollarini
    ham bilishi imkoniyati bo'lishi kerak".
    """
    questions = list(attempt.exam.questions.filter(is_active=True).order_by("order"))
    answers = {answer.question_id: answer for answer in attempt.answers.all()}
    rows: list[dict] = []
    show_key = attempt.exam.show_correct_answers

    for question in questions:
        answer = answers.get(question.id)
        if question.kind == Question.Kind.OPEN:
            correct_value = "; ".join(
                value for value in (question.answer_a, question.answer_b) if value
            )
        else:
            correct_value = question.correct_key

        rows.append(
            {
                "order": question.order,
                "kind": question.kind,
                "given": answer.display_value if answer else "—",
                "correct": correct_value if show_key else "—",
                "score": answer.score if answer else 0.0,
                "max_score": question.max_score,
                "icon": answer.status_icon if answer else "·",
            }
        )
    return rows


def user_history(user, limit: int = 20) -> list[Attempt]:
    """Foydalanuvchining oxirgi natijalari."""
    return list(
        Attempt.objects.filter(user=user, status=Attempt.Status.SUBMITTED)
        .select_related("exam")
        .order_by("-submitted_at")[:limit]
    )


__all__ = [
    "ParticipationCheck",
    "can_participate",
    "start_attempt",
    "get_draft_attempt",
    "cancel_attempt",
    "save_answer",
    "toggle_multi_choice",
    "set_current_order",
    "answered_map",
    "progress",
    "unanswered_orders",
    "submit_attempt",
    "get_result",
    "ranked_attempts",
    "rating",
    "participants_count",
    "answer_review",
    "user_history",
]
