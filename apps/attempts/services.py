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
from dataclasses import dataclass, replace

from django.db import transaction
from django.utils import timezone

from apps.exams.models import Exam, Question
from apps.users.models import UserAction
from core import constants as C
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


# --------------------------------------------------------------------------
#  Esse balli (qo'lda baholanadigan yozma qism)
# --------------------------------------------------------------------------


class EssayError(ValueError):
    """Esse balli noto'g'ri kiritildi."""


def parse_essay_ball(raw, exam: Exam) -> float | None:
    """
    Kiritilgan esse ballini tekshiradi.

    Bo'sh qiymat `None` qaytaradi — bu «hali baholanmagan» degani.
    Vergul o'nlik ajratkichi sifatida qabul qilinadi («7,5» = 7.5).
    """
    text = str(raw if raw is not None else "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        raise EssayError("Esse balli son bo'lishi kerak.") from None

    maximum = float(exam.essay_max_ball or 0) or 0.0
    if value < 0 or (maximum and value > maximum):
        raise EssayError(
            f"Esse balli 0 dan {maximum:g} gacha bo'lishi kerak."
        )
    return round(value, 2)


@transaction.atomic
def set_essay_ball(attempt: Attempt, value: float | None, *, reassign: bool = True) -> Attempt:
    """
    Bitta urinishga esse ballini yozadi va yakuniy ballni qayta hisoblaydi.

    Yakuniy ball — `(test balli + esse balli) / 2`, daraja esa aynan shu
    ball bo'yicha. Reyting ham o'zgargani uchun o'rinlar qaytadan
    taqsimlanadi (`reassign=False` bilan buni to'plam oxiriga qoldirish
    mumkin).
    """
    from apps.rasch.services import apply_final_ball, assign_ranks

    attempt.essay_ball = None if value is None else round(float(value), 2)
    apply_final_ball(attempt, attempt.exam)
    attempt.save(update_fields=["essay_ball", "final_ball", "grade", "updated_at"])

    if reassign:
        assign_ranks(attempt.exam)
    return attempt


@transaction.atomic
def set_essay_balls(exam: Exam, values: dict[int, float | None]) -> int:
    """
    Bir nechta urinishga esse ballini birdaniga yozadi.

    `values` — `{urinish_id: ball}`. Natijada reyting bir marta qayta
    taqsimlanadi. Qaytaradi: o'zgartirilgan urinishlar soni.
    """
    from apps.rasch.services import apply_final_ball, assign_ranks

    if not values:
        return 0

    attempts = list(
        Attempt.objects.filter(exam=exam, id__in=list(values))
        .select_related("exam")
    )
    changed: list[Attempt] = []
    for attempt in attempts:
        new_value = values.get(attempt.id)
        new_value = None if new_value is None else round(float(new_value), 2)
        if attempt.essay_ball == new_value:
            continue
        attempt.essay_ball = new_value
        apply_final_ball(attempt, exam)
        changed.append(attempt)

    if changed:
        Attempt.objects.bulk_update(
            changed, ["essay_ball", "final_ball", "grade", "updated_at"], batch_size=200
        )
        assign_ranks(exam)
    return len(changed)


def essay_progress(exam: Exam) -> tuple[int, int]:
    """(esse balli kiritilganlar soni, jami topshirganlar soni)."""
    submitted = Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED)
    return submitted.exclude(essay_ball__isnull=True).count(), submitted.count()


# --------------------------------------------------------------------------
#  E'lon qilinadigan umumiy ro'yxat (haqiqiy + soxta qatorlar)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RankRow:
    """
    Reyting jadvalining bitta qatori.

    Haqiqiy urinish ham, e'lon uchun qo'shilgan soxta qator ham shu
    ko'rinishga keltiriladi — shuning uchun PDF, ilova va bot bir xil
    ma'lumot bilan ishlaydi. `is_phantom` bayrog'i faqat boshqaruv
    panelida ko'rsatiladi.
    """

    rank: int
    public_label: str
    ball: float | None
    grade: str
    raw_score: float
    max_raw_score: float
    percent: float
    id: int | None = None
    is_phantom: bool = False
    test_ball: float | None = None
    essay_ball: float | None = None
    attempt: Attempt | None = None

    @property
    def display_ball(self) -> str:
        return "—" if self.ball is None else f"{self.ball:.2f}"

    @property
    def submitted_at(self):
        return self.attempt.submitted_at if self.attempt is not None else None


def _row_from_attempt(attempt: Attempt) -> RankRow:
    """Haqiqiy urinishni jadval qatoriga aylantiradi."""
    return RankRow(
        rank=0,
        public_label=attempt.public_label,
        ball=attempt.result_ball,
        grade=attempt.grade or "",
        raw_score=attempt.raw_score or 0.0,
        max_raw_score=attempt.max_raw_score or 0.0,
        percent=attempt.percent or 0.0,
        id=attempt.id,
        is_phantom=False,
        test_ball=attempt.ball,
        essay_ball=attempt.essay_ball,
        attempt=attempt,
    )


def _row_from_phantom(phantom) -> RankRow:
    """Soxta qatorni jadval qatoriga aylantiradi."""
    return RankRow(
        rank=0,
        public_label=phantom.full_name,
        ball=phantom.ball,
        grade=phantom.grade or "",
        raw_score=phantom.raw_score or 0.0,
        max_raw_score=phantom.max_raw_score or 0.0,
        percent=phantom.percent or 0.0,
        id=None,
        is_phantom=True,
    )


#: Bir marta qo'shish mumkin bo'lgan soxta qatorlarning eng ko'p soni.
MAX_PHANTOMS: int = 10_000


def phantom_count(exam: Exam) -> int:
    """Testga qo'shilgan soxta qatorlar soni."""
    from .models import PhantomParticipant

    return PhantomParticipant.objects.filter(exam=exam).count()


@transaction.atomic
def create_phantoms(exam: Exam, count: int, *, seed: int | None = None) -> int:
    """
    E'lon uchun `count` ta soxta qatnashchi qatorini yaratadi.

    Avvalgi qatorlar o'chiriladi, ya'ni test qayta e'lon qilinsa ro'yxat
    ikki barobar uzayib ketmaydi. `count=0` — barcha soxta qatorlarni
    o'chiradi.

    Ballar haqiqiy natijalar orasiga tabiiy joylashadi
    (`apps.attempts.phantoms.blended_balls`), ismlar esa haqiqiy
    qatnashchilarniki bilan to'qnashmaydi.

    Qaytaradi: yaratilgan qatorlar soni.
    """
    import random

    from apps.rasch.services import ball_scale

    from . import phantoms as phantom_utils
    from .models import PhantomParticipant

    PhantomParticipant.objects.filter(exam=exam).delete()

    count = max(0, min(int(count or 0), MAX_PHANTOMS))
    if count == 0:
        return 0

    rng = random.Random(seed)
    real = list(
        Attempt.objects.filter(exam=exam, status=Attempt.Status.SUBMITTED)
        .select_related("exam")
        .order_by("-final_ball", "-ball")
    )

    taken = {a.full_name for a in real if a.full_name}
    names = phantom_utils.unique_names(count, taken, rng=rng)

    scale = ball_scale(exam)
    balls = phantom_utils.blended_balls(
        count,
        [a.result_ball for a in real if a.result_ball is not None],
        max_ball=scale,
        rng=rng,
    )

    # Xom ballni haqiqiy natijalardan interpolyatsiya qilamiz — shunda
    # «to'g'ri javoblar soni» ustuni ham ishonarli chiqadi.
    reference = sorted(
        ((a.result_ball, a.raw_score) for a in real if a.result_ball is not None),
        key=lambda pair: pair[0],
    )
    max_raw = float(exam.max_raw_score or 0.0)

    def raw_for(ball: float) -> float:
        if reference:
            nearest = min(reference, key=lambda pair: abs(pair[0] - ball))
            return float(nearest[1])
        if max_raw and scale:
            return round(max_raw * ball / scale)
        return 0.0

    rows: list[PhantomParticipant] = []
    for name, ball in zip(names, balls):
        raw = raw_for(ball)
        if exam.uses_rasch:
            percent = C.certificate_percent(ball)
            grade = C.grade_for_ball(ball)
        else:
            percent = float(ball)
            grade = ""
        rows.append(
            PhantomParticipant(
                exam=exam,
                full_name=name,
                raw_score=raw,
                max_raw_score=max_raw,
                percent=round(percent, 2),
                ball=ball,
                grade=grade,
            )
        )

    PhantomParticipant.objects.bulk_create(rows, batch_size=200)
    logger.info("«%s» testiga %s ta soxta qator qo'shildi.", exam.code, len(rows))
    return len(rows)


def public_ranking(exam: Exam, limit: int | None = None) -> list[RankRow]:
    """
    E'lon qilinadigan reyting: haqiqiy natijalar + soxta qatorlar birga.

    O'rinlar ikkala turdagi qator ustida birgalikda qayta taqsimlanadi,
    shuning uchun ro'yxat uzluksiz chiqadi (1, 2, 3, ...). Soxta qatorlar
    bo'lmasa natija oddiy reyting bilan bir xil.
    """
    from .models import PhantomParticipant

    rows = [_row_from_attempt(a) for a in ranked_attempts(exam)]
    rows += [
        _row_from_phantom(p)
        for p in PhantomParticipant.objects.filter(exam=exam)
    ]

    rows.sort(
        key=lambda row: (-(row.ball or 0.0), -(row.raw_score or 0.0), row.public_label)
    )

    result: list[RankRow] = []
    previous_key = None
    previous_rank = 0
    for index, row in enumerate(rows, start=1):
        key = (round(row.ball or 0.0, 4), round(row.raw_score or 0.0, 4))
        if key == previous_key:
            place = previous_rank
        else:
            place = index
            previous_rank = index
            previous_key = key
        result.append(replace(row, rank=place))

    return result[:limit] if limit else result


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
    "EssayError",
    "parse_essay_ball",
    "set_essay_ball",
    "set_essay_balls",
    "essay_progress",
    "RankRow",
    "public_ranking",
    "MAX_PHANTOMS",
    "phantom_count",
    "create_phantoms",
]
