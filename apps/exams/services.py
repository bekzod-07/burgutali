"""
Testlar bilan ishlash xizmatlari (biznes-mantiq).

Bu modul Django ORM ustidagi barcha amallarni jamlaydi: test yaratish,
javob kalitlarini biriktirish, holatni o'zgartirish va natijalarni e'lon qilish.
Telegram bot ham, web panel ham aynan shu funksiyalardan foydalanadi.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.db import models, transaction
from django.db.models import Count, Q
from django.utils import timezone

from core import constants as C
from core.text_utils import shorten

from .keys import split_open_key
from .models import Exam, Question, ReservedExamCode
from .structures import QuestionSpec, build_questions, national_specs, simple_specs

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
#  Test kodi
# --------------------------------------------------------------------------


#: Kod band hisoblanadigan test holatlari (test hali yakunlanmagan).
LIVE_STATUSES: tuple[str, ...] = tuple(Exam.LIVE_STATUSES)


def release_code(code: str) -> bool:
    """
    Kodni umumiy fondga qaytaradi («kod kuyadi»).

    Test yopilganda, arxivlanganda yoki o'chirilganda chaqiriladi — shundan
    keyin bot shu kodni yangi testga bemalol bera oladi.
    """
    if not code:
        return False
    updated = ReservedExamCode.objects.filter(
        code=code, released_at__isnull=True
    ).update(released_at=timezone.now())
    return bool(updated)


def _is_code_free(code: str) -> bool:
    """
    Kod yangi testga berilishi mumkinmi.

    Bandlik yozuvi bo'lsa-yu, unga tegishli test allaqachon yakunlangan
    bo'lsa (holat bazada belgilanmay qolgan bo'lishi mumkin) — kod
    o'sha yerda bo'shatiladi.
    """
    reservation = ReservedExamCode.objects.filter(code=code).first()
    if reservation is None:
        return True
    if reservation.released_at is not None:
        return True

    exam = Exam.objects.filter(code=code).order_by("-id").first()
    if exam is None:
        # Kod band qilingan, lekin test hali yaratilmagan — tegmaymiz.
        return False

    # Bandlik yozuvi shu testdan **keyin** yaratilgan bo'lsa, u boshqa
    # (hali yaratilib ulgurmagan) testga tegishli. Kodni eski, yakunlangan
    # testga qarab bo'shatib yuborsak, bitta kod ikkita testga berilib
    # qolardi — kodlar 2-3 xonali bo'lgani uchun bu tez-tez uchraydi.
    if exam.created_at and reservation.created_at and exam.created_at < reservation.created_at:
        return False

    if exam.status in LIVE_STATUSES:
        return False

    release_code(code)
    return True


def _reserve_code(code: str, title: str = "") -> bool:
    """
    Kodni band qiladi. Kod hozir ishlatilayotgan bo'lsa `False` qaytaradi.

    Bir vaqtning o'zida ikkita test yaratilsa ham bitta kod ikki marta
    berilmasligi uchun bandlik bazadagi `unique` cheklov orqali hal qilinadi.
    """
    from django.db import IntegrityError

    if Exam.objects.filter(code=code, status__in=LIVE_STATUSES).exists():
        return False

    try:
        with transaction.atomic():
            ReservedExamCode.objects.create(code=code, exam_title=shorten(title, 150))
        return True
    except IntegrityError:
        pass

    # Kod ilgari berilgan — bo'shaganini tekshiramiz.
    if not _is_code_free(code):
        return False

    # `released_at__isnull=False` sharti poyga holatida bitta kodning
    # ikkita testga berilishining oldini oladi: yangilash bitta yozuvni
    # faqat bir marta «band» holatiga o'tkazadi.
    updated = ReservedExamCode.objects.filter(
        code=code, released_at__isnull=False
    ).update(
        released_at=None,
        exam_title=shorten(title, 150),
        created_at=timezone.now(),
    )
    return bool(updated)


def claim_code(exam: Exam) -> str:
    """
    Testni faollashtirishdan oldin kodni qayta band qiladi.

    Yopilgan test kodini bo'shatgani uchun uni qayta faollashtirishda kod
    boshqa testga berilgan bo'lishi mumkin. Bunday holatda yangi kod
    beriladi. Qaytadigan qiymat — testning yangi (yoki o'sha eski) kodi.
    """
    taken = (
        Exam.objects.filter(code=exam.code, status__in=LIVE_STATUSES)
        .exclude(pk=exam.pk)
        .exists()
    )
    if taken:
        return generate_exam_code(exam.title)

    reservation, created = ReservedExamCode.objects.get_or_create(
        code=exam.code, defaults={"exam_title": shorten(exam.title, 150)}
    )
    if not created and reservation.released_at is not None:
        reservation.released_at = None
        reservation.exam_title = shorten(exam.title, 150)
        reservation.save(update_fields=["released_at", "exam_title"])
    return exam.code


def generate_exam_code(title: str = "") -> str:
    """
    Ishtirokchi uchun qulay test kodini yaratadi.

    Ko'rinishi — oddiy son: ``32``, ``145``. Avval ikki xonali kodlar
    beriladi, ular tugagach uch xonali va h.k. Yakunlangan testlarning
    kodlari qayta ishlatiladi (`release_code` ga qarang).
    """
    for length in C.EXAM_CODE_LENGTHS:
        low = 10 ** (length - 1)
        high = 10**length - 1

        for _ in range(C.EXAM_CODE_RANDOM_TRIES):
            candidate = str(secrets.randbelow(high - low + 1) + low)
            if _reserve_code(candidate, title):
                return candidate

        if length > C.EXAM_CODE_SCAN_MAX_LENGTH:
            continue

        # Tasodifiy urinishlar band kodlarga tushib qoldi — bo'sh kodni
        # ketma-ket qidiramiz. Bu uzunlik butunlay to'lgan bo'lsa,
        # keyingi uzunlikka o'tiladi.
        pattern = rf"^\d{{{length}}}$"
        taken = set(
            ReservedExamCode.objects.filter(
                code__regex=pattern, released_at__isnull=True
            ).values_list("code", flat=True)
        )
        taken |= set(
            Exam.objects.filter(
                code__regex=pattern, status__in=LIVE_STATUSES
            ).values_list("code", flat=True)
        )
        for number in range(low, high + 1):
            candidate = str(number)
            if candidate in taken:
                continue
            if _reserve_code(candidate, title):
                return candidate

    # Amalda yetib bo'lmaydigan holat — vaqt tamg'asiga asoslangan kod.
    fallback = str(int(timezone.now().timestamp()))[-9:]
    _reserve_code(fallback, title)
    return fallback


# --------------------------------------------------------------------------
#  Test yaratish
# --------------------------------------------------------------------------


@transaction.atomic
def create_exam(
    *,
    owner,
    title: str,
    exam_type: str,
    question_count: int = 0,
    national_template: bool = False,
    description: str = "",
    duration_minutes: int = 0,
    ends_at=None,
    show_results: bool = True,
    show_correct_answers: bool = True,
    certificate_enabled: bool = False,
    organizer_name: str = "",
) -> Exam:
    """
    Yangi test yaratadi va savollar tuzilmasini shakllantiradi.

    `national_template=True` bo'lsa — SRS 3-bo'limidagi 45 ta savol tuzilmasi
    yaratiladi, aks holda `question_count` ta A/B/C/D savol.
    """
    exam = Exam.objects.create(
        title=shorten(title.strip(), 150) or "Nomsiz test",
        code=generate_exam_code(title),
        exam_type=exam_type,
        status=Exam.Status.DRAFT,
        owner=owner,
        description=shorten(description or "", 2000),
        duration_minutes=max(0, int(duration_minutes or 0)),
        ends_at=ends_at,
        is_national_template=bool(national_template),
        show_results_to_participants=bool(show_results),
        show_correct_answers=bool(show_correct_answers),
        certificate_enabled=bool(certificate_enabled),
        organizer_name=organizer_name or "",
    )

    specs: list[QuestionSpec]
    if national_template:
        specs = national_specs()
    else:
        specs = simple_specs(question_count)
    build_questions(exam, specs)

    logger.info("Yangi test yaratildi: %s (%s)", exam.code, exam.get_exam_type_display())
    return exam


# --------------------------------------------------------------------------
#  Javob kalitlari
# --------------------------------------------------------------------------


@transaction.atomic
def apply_single_keys(exam: Exam, keys: list[str]) -> int:
    """Bitta javobli savollarga kalitlarni biriktiradi (tartib bo'yicha)."""
    questions = list(
        exam.questions.filter(kind=Question.Kind.SINGLE, is_active=True).order_by("order")
    )
    return _apply_letter_keys(questions, keys)


@transaction.atomic
def apply_multi_keys(exam: Exam, keys: list[str]) -> int:
    """Ko'p javobli savollarga kalitlarni biriktiradi."""
    questions = list(
        exam.questions.filter(kind=Question.Kind.MULTI, is_active=True).order_by("order")
    )
    return _apply_letter_keys(questions, keys)


def _apply_letter_keys(questions: list[Question], keys: list[str]) -> int:
    """Harfli kalitlarni savollarga yozadi."""
    updated: list[Question] = []
    for question, key in zip(questions, keys):
        question.correct_key = "".join(sorted({ch.upper() for ch in (key or "") if ch.isalpha()}))
        updated.append(question)
    if updated:
        Question.objects.bulk_update(updated, ["correct_key", "updated_at"])
    return len(updated)


@transaction.atomic
def apply_open_keys(exam: Exam, keys: list[str]) -> int:
    """Ochiq javobli savollarga kalitlarni biriktiradi."""
    questions = list(
        exam.questions.filter(kind=Question.Kind.OPEN, is_active=True).order_by("order")
    )
    updated: list[Question] = []
    for question, key in zip(questions, keys):
        first, second = split_open_key(key)
        question.answer_a = first
        question.answer_b = second
        question.parts = 2 if second else 1
        updated.append(question)
    if updated:
        Question.objects.bulk_update(
            updated, ["answer_a", "answer_b", "parts", "updated_at"]
        )
    return len(updated)


def missing_keys(exam: Exam) -> list[int]:
    """Kaliti kiritilmagan savollar tartib raqamlari."""
    missing: list[int] = []
    for question in exam.questions.filter(is_active=True).order_by("order"):
        if not question.has_key:
            missing.append(question.order)
    return missing


def keys_ready(exam: Exam) -> bool:
    """Barcha savollarning kaliti kiritilganmi."""
    return not missing_keys(exam)


# --------------------------------------------------------------------------
#  Holat bilan ishlash
# --------------------------------------------------------------------------


def _reload(exam: Exam) -> Exam:
    """
    Test holatini bazadan qayta o'qiydi.

    Bot va web panel obyektlarni uzoq vaqt xotirada saqlashi mumkin, shuning
    uchun holatni o'zgartiruvchi amallar doim yangi ma'lumot bilan ishlaydi.
    """
    try:
        exam.refresh_from_db()
    except Exception:  # pragma: no cover - obyekt o'chirilgan bo'lishi mumkin
        pass
    return exam


def activate_exam(exam: Exam) -> tuple[bool, str]:
    """Testni faollashtiradi (javob qabul qilishni boshlaydi)."""
    _reload(exam)
    if exam.question_count <= 0:
        return False, "Testda savollar yo'q."
    missing = missing_keys(exam)
    if missing:
        preview = ", ".join(str(order) for order in missing[:10])
        more = " ..." if len(missing) > 10 else ""
        return False, f"Javob kaliti kiritilmagan savollar: {preview}{more}"
    if exam.exam_type == Exam.Type.RASCH_PAID and not exam.access_codes.exists():
        return False, "Pullik test uchun avval ID kodlar yaratilishi kerak."

    # Yopilgan test kodini bo'shatgani uchun uni qayta band qilamiz.
    # Kod boshqa testga berilib ketgan bo'lsa — yangisi olinadi.
    old_code = exam.code
    exam.code = claim_code(exam)

    exam.status = Exam.Status.ACTIVE
    exam.closed_at = None
    exam.save(update_fields=["code", "status", "closed_at", "updated_at"])

    if exam.code != old_code:
        return True, (
            f"Test faollashtirildi. Eski kod ({old_code}) boshqa testga "
            f"berilgani uchun yangi kod: {exam.code}"
        )
    return True, "Test faollashtirildi."


def close_exam(exam: Exam) -> tuple[bool, str]:
    """
    Testni yopadi — yangi javoblar qabul qilinmaydi.

    Shu payt test kodi ham bo'shaydi: u yangi testga berilishi mumkin.
    """
    _reload(exam)
    if exam.status not in {Exam.Status.ACTIVE, Exam.Status.DRAFT}:
        return False, "Test allaqachon yopilgan."
    exam.status = Exam.Status.CLOSED
    exam.closed_at = timezone.now()
    exam.save(update_fields=["status", "closed_at", "updated_at"])
    release_code(exam.code)
    return True, "Test yopildi."


def publish_results(exam: Exam, *, phantom_count: int | None = None) -> tuple[bool, str]:
    """
    Natijalarni e'lon qiladi.

    TZ talabi: sertifikat test yakunlangan zahoti emas, balki admin
    natijalarni tasdiqlagandan keyingina ochiladi.

    `phantom_count` berilsa, e'lon qilinadigan ro'yxatga shuncha **soxta**
    qatnashchi qatori qo'shiladi (`apps.attempts.services.create_phantoms`).
    Ular hisob-kitobga kirmaydi va sertifikat olmaydi — faqat e'lon
    ro'yxatida ko'rinadi. `None` bo'lsa mavjud qatorlar o'zgarishsiz
    qoladi, `0` esa ularni butunlay o'chiradi.
    """
    _reload(exam)
    if exam.status not in {Exam.Status.CALCULATED, Exam.Status.PUBLISHED}:
        return False, "Avval natijalarni hisoblang."
    exam.status = Exam.Status.PUBLISHED
    exam.published_at = timezone.now()
    exam.save(update_fields=["status", "published_at", "updated_at"])
    # Test to'liq yakunlandi — kodi ham bo'shaydi (yopilmagan bo'lsa ham).
    release_code(exam.code)

    message = "Natijalar e'lon qilindi."
    if phantom_count is not None:
        from apps.attempts.services import create_phantoms

        created = create_phantoms(exam, phantom_count)
        if created:
            message += f" Ro'yxatga {created} ta soxta qator qo'shildi."
        elif phantom_count == 0:
            message += " Soxta qatorlar o'chirildi."

    # Natijalar o'zgardi — hisobot qaytadan yuborilsin.
    if exam.published_report_sent_at is not None:
        exam.published_report_sent_at = None
        exam.save(update_fields=["published_report_sent_at", "updated_at"])

    return True, message


def archive_exam(exam: Exam) -> tuple[bool, str]:
    """Testni arxivlaydi (kodi bo'shaydi)."""
    _reload(exam)
    exam.status = Exam.Status.ARCHIVED
    exam.save(update_fields=["status", "updated_at"])
    release_code(exam.code)
    return True, "Test arxivlandi."


@transaction.atomic
def duplicate_exam(exam: Exam, owner=None) -> Exam:
    """
    Testning to'liq nusxasini yaratadi (savollar va kalitlar bilan).

    Natijalar, ID kodlar va sertifikatlar ko'chirilmaydi — yangi test
    qoralama holatida ochiladi.
    """
    _reload(exam)
    copy = Exam.objects.create(
        title=shorten(f"{exam.title} (nusxa)", 150),
        code=generate_exam_code(f"{exam.title} (nusxa)"),
        exam_type=exam.exam_type,
        status=Exam.Status.DRAFT,
        owner=owner or exam.owner,
        description=exam.description,
        question_count=exam.question_count,
        is_national_template=exam.is_national_template,
        duration_minutes=exam.duration_minutes,
        is_public=exam.is_public,
        show_results_to_participants=exam.show_results_to_participants,
        show_correct_answers=exam.show_correct_answers,
        show_rating_to_participants=exam.show_rating_to_participants,
        max_ball=exam.max_ball,
        theta_min=exam.theta_min,
        theta_max=exam.theta_max,
        auto_calibrate=exam.auto_calibrate,
        certificate_enabled=exam.certificate_enabled,
        certificate_scope=exam.certificate_scope,
        certificate_min_percent=exam.certificate_min_percent,
        certificate_min_ball=exam.certificate_min_ball,
        certificate_min_grade=exam.certificate_min_grade,
        organizer_name=exam.organizer_name,
    )

    Question.objects.bulk_create(
        [
            Question(
                exam=copy,
                order=question.order,
                kind=question.kind,
                text=question.text,
                section=question.section,
                choices_count=question.choices_count,
                correct_key=question.correct_key,
                answer_a=question.answer_a,
                answer_b=question.answer_b,
                numeric_tolerance=question.numeric_tolerance,
                parts=question.parts,
                difficulty=question.difficulty,
                difficulty_b=question.difficulty_b,
                difficulty_locked=question.difficulty_locked,
                is_active=question.is_active,
            )
            for question in exam.questions.order_by("order")
        ],
        batch_size=200,
    )
    logger.info("Test nusxalandi: %s -> %s", exam.code, copy.code)
    return copy


def deletion_summary(exam: Exam) -> dict:
    """
    Test o'chirilganda birga yo'q bo'ladigan ma'lumotlar hisobi.

    O'chirishdan oldin foydalanuvchiga ko'rsatiladi.
    """
    from apps.accesscodes.models import AccessCode
    from apps.attempts.models import Attempt
    from apps.certificates.models import Certificate

    submitted = Attempt.objects.filter(
        exam=exam, status=Attempt.Status.SUBMITTED
    ).count()
    return {
        "questions": exam.questions.count(),
        "attempts": Attempt.objects.filter(exam=exam).count(),
        "submitted": submitted,
        "codes": AccessCode.objects.filter(exam=exam).count(),
        "used_codes": AccessCode.objects.filter(
            exam=exam, status=AccessCode.Status.USED
        ).count(),
        "certificates": Certificate.objects.filter(exam=exam).count(),
        "needs_confirmation": submitted > 0,
    }


@transaction.atomic
def delete_exam(exam: Exam, *, force: bool = False) -> tuple[bool, str, dict]:
    """
    Testni butunlay o'chiradi.

    Test bilan birga uning savollari, urinishlari, javoblari, ID kodlari,
    statistikasi va sertifikatlari ham o'chadi. Shu sababli topshirilgan
    javoblar mavjud bo'lsa, `force=True` talab qilinadi.

    Qaytaradi: `(muvaffaqiyat, xabar, hisobot)`.
    """
    _reload(exam)
    summary = deletion_summary(exam)

    if summary["needs_confirmation"] and not force:
        return (
            False,
            f"Bu testda {summary['submitted']} ta topshirilgan javob bor. "
            "O'chirish tasdiqlanishi kerak.",
            summary,
        )

    # Sertifikat PDF fayllarini diskdan ham tozalaymiz.
    from apps.certificates.models import Certificate

    for certificate in Certificate.objects.filter(exam=exam):
        if certificate.file:
            try:
                certificate.file.delete(save=False)
            except Exception:  # pragma: no cover - fayl allaqachon yo'q bo'lishi mumkin
                logger.warning("Sertifikat faylini o'chirib bo'lmadi: %s", certificate.number)

    from apps.accesscodes.models import CodeBatch

    for batch in CodeBatch.objects.filter(exam=exam):
        if batch.file:
            try:
                batch.file.delete(save=False)
            except Exception:  # pragma: no cover
                pass

    code = exam.code
    title = exam.title
    exam.delete()
    # Test o'chirildi — kod boshqa testga berilishi mumkin.
    release_code(code)
    logger.info("Test o'chirildi: %s (%s)", code, title)
    return True, f"«{title}» testi butunlay o‘chirildi.", summary


def can_manage(exam: Exam, user, *, is_admin: bool = False) -> bool:
    """Foydalanuvchi ushbu testni boshqara oladimi."""
    if exam is None or user is None:
        return False
    return bool(is_admin or getattr(user, "is_admin", False) or exam.owner_id == user.id)


def auto_close_expired() -> int:
    """
    Tugash vaqti o'tgan faol testlarni avtomatik yopadi.

    Bot fon vazifasi (`bot/tasks/scheduler.py`) tomonidan chaqiriladi.
    Yopilgan testning kodi bo'shaydi va yangi testga berilishi mumkin.
    """
    now = timezone.now()
    expired = Exam.objects.filter(
        status=Exam.Status.ACTIVE, ends_at__isnull=False, ends_at__lte=now
    )
    count = 0
    for exam in expired:
        exam.status = Exam.Status.CLOSED
        exam.closed_at = now
        exam.save(update_fields=["status", "closed_at", "updated_at"])
        release_code(exam.code)
        count += 1
    return count


# --------------------------------------------------------------------------
#  Eskirgan testlarni avtomatik o'chirish
# --------------------------------------------------------------------------

#: Shu holatlardagi test belgilangan muddat o'tgach butunlay o'chiriladi.
#:
#: `active` va `closed` ro'yxatda yo'q — test hali jarayonda yoki natijasi
#: hisoblanmagan. `archived` ham yo'q: arxiv ataylab saqlanadi.
STALE_STATUSES: tuple[str, ...] = (
    Exam.Status.DRAFT,
    Exam.Status.CALCULATED,
    Exam.Status.PUBLISHED,
)

#: Standart saqlash muddati (soat). `.env` da `EXAM_RETENTION_HOURS` bilan
#: o'zgartiriladi; 0 yoki manfiy qiymat tozalashni butunlay o'chiradi.
DEFAULT_RETENTION_HOURS: int = 48


def retention_hours() -> int:
    """Test shu holatlarda necha soat saqlanadi (0 — o'chirilmaydi)."""
    from core.env import get_int

    return get_int("EXAM_RETENTION_HOURS", DEFAULT_RETENTION_HOURS)


def stale_exams(hours: int | None = None, limit: int = 50) -> list[Exam]:
    """
    Muddati o'tgan testlar ro'yxati.

    Hisob `updated_at` bo'yicha: test holatga o'tganda ham, keyin
    tahrirlanganda ham bu vaqt yangilanadi. Shuning uchun ustida ish
    ketayotgan qoralama o'chib ketmaydi — soat oxirgi o'zgarishdan
    boshlab sanaladi.
    """
    window = retention_hours() if hours is None else int(hours)
    if window <= 0:
        return []
    cutoff = timezone.now() - timedelta(hours=window)
    return list(
        Exam.objects.filter(status__in=STALE_STATUSES, updated_at__lte=cutoff)
        .order_by("id")[:limit]
    )


def delete_stale_exams(hours: int | None = None, limit: int = 50) -> list[dict]:
    """
    Muddati o'tgan testlarni butunlay o'chiradi.

    Test bilan birga uning savollari, urinishlari, javoblari, ID kodlari,
    statistikasi va **sertifikatlari** ham o'chadi (`delete_exam`).
    Shu sababli o'chirilgan har bir test logga yoziladi.

    Bot fon vazifasi (`bot/tasks/scheduler.py`) tomonidan chaqiriladi.
    Qaytaradi: o'chirilgan testlar haqidagi qisqa ma'lumot ro'yxati.
    """
    removed: list[dict] = []
    for exam in stale_exams(hours, limit):
        summary = deletion_summary(exam)
        record = {
            "code": exam.code,
            "title": exam.title,
            "status": exam.get_status_display(),
            "participants": summary["submitted"],
            "certificates": summary["certificates"],
        }
        ok, _message, _summary = delete_exam(exam, force=True)
        if not ok:  # pragma: no cover - `force=True` da yuz bermaydi
            continue
        removed.append(record)
        logger.info(
            "Muddati o'tgan test o'chirildi: %s «%s» (%s) — "
            "%s ta natija, %s ta sertifikat bilan birga.",
            record["code"], record["title"], record["status"],
            record["participants"], record["certificates"],
        )
    return removed


# --------------------------------------------------------------------------
#  Avtomatik hisobotlar (adminga PDF yuborish)
# --------------------------------------------------------------------------

#: Umumiy natijalar hisoboti yuboriladigan test turlari (2- va 3-tur).
REPORT_EXAM_TYPES: tuple[str, ...] = (Exam.Type.RASCH_FREE, Exam.Type.RASCH_PAID)


def exams_awaiting_report(limit: int = 20) -> list[tuple[int, str]]:
    """
    Adminga hisobot yuborilishi kerak bo'lgan testlar.

    Qaytaradi `(test_id, sabab)` juftliklari. Sabab ikki xil:
      * ``closed``    — test yopildi (vaqti tugadi yoki qo'lda yopildi);
      * ``published`` — natijalar e'lon qilindi.

    Hisobot bot fon vazifasi orqali yuboriladi, shuning uchun test qayerda
    yopilganidan (bot, web ilova yoki panel) qat'i nazar ishlaydi.
    """
    pending: list[tuple[int, str]] = []

    closed = Exam.objects.filter(
        exam_type__in=REPORT_EXAM_TYPES,
        status__in=[Exam.Status.CLOSED, Exam.Status.CALCULATED, Exam.Status.PUBLISHED],
        closed_report_sent_at__isnull=True,
    ).order_by("id")[:limit]
    pending.extend((exam.id, "closed") for exam in closed)

    published = Exam.objects.filter(
        exam_type__in=REPORT_EXAM_TYPES,
        status=Exam.Status.PUBLISHED,
        published_report_sent_at__isnull=True,
    ).order_by("id")[:limit]
    pending.extend((exam.id, "published") for exam in published)

    return pending


def mark_report_sent(exam: Exam, reason: str) -> None:
    """Hisobot yuborilganini belgilaydi (qayta yuborilmasligi uchun)."""
    field = "closed_report_sent_at" if reason == "closed" else "published_report_sent_at"
    setattr(exam, field, timezone.now())
    exam.save(update_fields=[field, "updated_at"])


def report_recipients(exam: Exam) -> list[int]:
    """
    Hisobotni kim olishi kerak.

    Uch manba qo'shiladi:

      * test egasi;
      * `.env` dagi asosiy adminlar (`ADMIN_IDS`);
      * `.env` dagi qo'shimcha kuzatuvchilar (`REPORT_EXTRA_IDS`) — ular
        faqat hisobotni oladi, botda admin huquqiga ega bo'lmaydi.

    Bir xil odam ikki marta olmasligi uchun ro'yxat takrorlanmaydi.
    """
    from bot.config import get_config

    config = get_config()
    recipients: list[int] = []

    def add(value) -> None:
        """Ro'yxatga haqiqiy Telegram ID ni qo'shadi."""
        try:
            number = int(value)
        except (TypeError, ValueError):
            return
        # Paneldan login-parol bilan kirgan hisob uchun `BotUser.telegram_id`
        # sun'iy va manfiy bo'ladi (`dashboard.views._dashboard_owner`),
        # «Web panel» egasida esa 0. Bunday ID ga xabar yuborib bo'lmaydi.
        if number <= 0 or number in recipients:
            return
        recipients.append(number)

    if exam.owner_id:
        add(getattr(exam.owner, "telegram_id", None))
    for admin_id in sorted(config.admin_ids):
        add(admin_id)
    for extra_id in sorted(config.report_extra_ids):
        add(extra_id)
    return recipients


# --------------------------------------------------------------------------
#  Qidiruv va ma'lumot
# --------------------------------------------------------------------------


def _pick_exam(queryset) -> Exam | None:
    """
    Bir xil kodli testlardan keraklisini tanlaydi.

    Kod qayta ishlatilgani uchun bitta kod bir nechta testda uchrashi
    mumkin: bittasi hozir faol, qolganlari yakunlangan. Ishtirokchiga
    doim **yakunlanmagan** test kerak, shuning uchun avval shular, so'ng
    eng yangi test qaytariladi.
    """
    return (
        queryset.annotate(
            _live=models.Case(
                models.When(status__in=LIVE_STATUSES, then=models.Value(0)),
                default=models.Value(1),
                output_field=models.IntegerField(),
            )
        )
        .order_by("_live", "-created_at")
        .first()
    )


def get_exam_by_code(code: str) -> Exam | None:
    """
    Kod bo'yicha testni topadi (registr, probel va ortiqcha belgilarga befarq).

    Kodlar oddiy son ko'rinishida (``32``), lekin eski testlarda ``T-4C6VV3``
    ko'rinishi ham uchraydi — ikkalasi ham topiladi.
    """
    if not code:
        return None
    normalized = code.strip().upper().replace(" ", "").lstrip("#")
    if not normalized:
        return None

    exam = _pick_exam(Exam.objects.filter(code__iexact=normalized))
    if exam:
        return exam

    # «032» kabi yozuvni «32» ga keltiramiz.
    if normalized.isdigit():
        trimmed = str(int(normalized))
        if trimmed != normalized:
            exam = _pick_exam(Exam.objects.filter(code__iexact=trimmed))
            if exam:
                return exam

    # Eski format: foydalanuvchi prefiksni yozmagan bo'lishi mumkin.
    return _pick_exam(Exam.objects.filter(code__iendswith=f"-{normalized}"))


def list_available_exams(limit: int = 20) -> list[Exam]:
    """Ishtirok etish mumkin bo'lgan ommaviy testlar."""
    exams = (
        Exam.objects.public_active()
        .exclude(exam_type=Exam.Type.RASCH_PAID)
        .order_by("-created_at")[: limit * 2]
    )
    return [exam for exam in exams if exam.accepts_answers][:limit]


def list_owned_exams(owner, limit: int = 50) -> list[Exam]:
    """Foydalanuvchi yaratgan testlar."""
    return list(
        Exam.objects.filter(owner=owner)
        .annotate(
            participants=Count(
                "attempts", filter=Q(attempts__status="submitted"), distinct=True
            )
        )
        .order_by("-created_at")[:limit]
    )


def exam_summary(exam: Exam) -> dict:
    """Test haqida qisqacha ma'lumot (botda ko'rsatish uchun)."""
    from apps.attempts.models import Attempt

    from apps.attempts.models import PhantomParticipant

    participants = Attempt.objects.filter(
        exam=exam, status=Attempt.Status.SUBMITTED
    ).count()
    # E'lon ro'yxatiga qo'shilgan soxta qatorlar — alohida son. Ular
    # `participants` ga qo'shilmaydi: bu ko'rsatkich hisob-kitobda ham
    # ishlatiladi va faqat haqiqiy natijalarni bildirishi kerak.
    phantoms = PhantomParticipant.objects.filter(exam=exam).count()
    return {
        "id": exam.id,
        "title": exam.title,
        "code": exam.code,
        "phantoms": phantoms,
        "published_rows": participants + phantoms,
        "type": exam.get_exam_type_display(),
        "status": exam.get_status_display(),
        "questions": exam.question_count,
        "participants": participants,
        "max_raw_score": exam.max_raw_score,
        "ends_at": exam.ends_at,
        "certificate": exam.can_issue_certificate,
        "deep_link": exam.deep_link,
    }


__all__ = [
    "LIVE_STATUSES",
    "generate_exam_code",
    "release_code",
    "claim_code",
    "ReservedExamCode",
    "create_exam",
    "apply_single_keys",
    "apply_multi_keys",
    "apply_open_keys",
    "missing_keys",
    "keys_ready",
    "activate_exam",
    "close_exam",
    "publish_results",
    "archive_exam",
    "duplicate_exam",
    "deletion_summary",
    "delete_exam",
    "can_manage",
    "auto_close_expired",
    "STALE_STATUSES",
    "DEFAULT_RETENTION_HOURS",
    "retention_hours",
    "stale_exams",
    "delete_stale_exams",
    "REPORT_EXAM_TYPES",
    "exams_awaiting_report",
    "mark_report_sent",
    "report_recipients",
    "get_exam_by_code",
    "list_available_exams",
    "list_owned_exams",
    "exam_summary",
]
