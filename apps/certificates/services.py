"""
Sertifikat berish xizmatlari.

TZ talablari:
  * sertifikat faqat **3-tur (pullik RASH testi)** uchun beriladi;
  * sertifikat test yakunlangan zahoti emas, balki RASH hisoblanib,
    admin natijalarni **e'lon qilgandan keyin** ochiladi;
  * admin sertifikat kimlarga berilishini belgilaydi (hammaga yoki
    belgilangan ball/darajadan yuqori natija olganlarga);
  * bitta sertifikat raqami = bitta qatnashchi + bitta test natijasi.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.attempts.models import Attempt
from apps.exams.models import Exam
from apps.users.models import UserAction
from apps.users.services import log_action
from core import constants as C
from core.text_utils import slugify_filename

from .models import Certificate
from .pdf import CertificateData, render_pdf

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
#  Huquqni tekshirish
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EligibilityCheck:
    """Sertifikat olish huquqi tekshiruvining natijasi."""

    ok: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


def check_eligibility(attempt: Attempt) -> EligibilityCheck:
    """Ushbu urinish uchun sertifikat berilishi mumkinmi."""
    # Test holati boshqa joyda o'zgargan bo'lishi mumkin — yangilab olamiz.
    exam = Exam.objects.filter(pk=attempt.exam_id).first()
    if exam is None:
        return EligibilityCheck(False, "Test topilmadi.")

    if exam.exam_type != Exam.Type.RASCH_PAID:
        return EligibilityCheck(False, "Bu test turi uchun sertifikat berilmaydi.")
    if not exam.certificate_enabled:
        return EligibilityCheck(False, "Bu testda sertifikat berish o'chirilgan.")
    if exam.status != Exam.Status.PUBLISHED:
        return EligibilityCheck(False, "Natijalar hali e'lon qilinmagan.")
    if attempt.status != Attempt.Status.SUBMITTED or not attempt.is_scored:
        return EligibilityCheck(False, "Natijangiz hali hisoblanmagan.")
    if exam.essay_enabled and attempt.essay_ball is None:
        # Esse balli kiritilmagan bo'lsa yakuniy ball hali to'liq emas —
        # sertifikat noto'g'ri daraja bilan chiqib ketmasligi kerak.
        return EligibilityCheck(False, "Esse qismi hali baholanmagan.")

    # Shart bajarilmasa, sabab **umumiy** qoladi: chegara (daraja, ball yoki
    # foiz) qatnashchiga aytilmaydi, uni faqat admin ko'radi.
    not_enough = EligibilityCheck(False, "Natijangiz sertifikat berish uchun yetarli emas.")

    scope = exam.certificate_scope
    if scope == Exam.CertificateScope.MIN_PERCENT:
        minimum = exam.certificate_min_percent
        if minimum is not None and (attempt.percent or 0.0) < float(minimum):
            return not_enough
    elif scope == Exam.CertificateScope.MIN_BALL:
        minimum = exam.certificate_min_ball
        if minimum is not None and (attempt.result_ball or 0.0) < float(minimum):
            return not_enough
    elif scope == Exam.CertificateScope.MIN_GRADE:
        required = (exam.certificate_min_grade or "").strip()
        if required and C.grade_rank(attempt.grade) < C.grade_rank(required):
            return not_enough

    return EligibilityCheck(True)


# --------------------------------------------------------------------------
#  Sertifikat raqami
# --------------------------------------------------------------------------


def generate_number(exam: Exam) -> str:
    """
    Noyob sertifikat raqamini yaratadi.

    Ko'rinishi: ``RM-2026-000123``.
    """
    year = timezone.now().year
    prefix = f"{C.CERT_PREFIX}-{year}-"
    last = (
        Certificate.objects.filter(number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    sequence = 1
    if last:
        try:
            sequence = int(last.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            sequence = Certificate.objects.filter(number__startswith=prefix).count() + 1

    for _ in range(1000):
        number = f"{prefix}{sequence:06d}"
        if not Certificate.objects.filter(number=number).exists():
            return number
        sequence += 1
    return f"{prefix}{timezone.now().strftime('%H%M%S')}"


# --------------------------------------------------------------------------
#  Sertifikat yaratish
# --------------------------------------------------------------------------


@transaction.atomic
def issue_certificate(attempt: Attempt, *, force: bool = False) -> tuple[Certificate | None, str]:
    """
    Urinish uchun sertifikat yaratadi (yoki mavjudini qaytaradi).

    Qaytaradi: `(sertifikat, xabar)`.
    """
    existing = Certificate.objects.filter(attempt=attempt).first()
    if existing is not None and not force:
        if existing.file:
            return existing, "Sertifikat allaqachon mavjud."
        _render_and_attach(existing)
        return existing, "Sertifikat qayta yaratildi."

    check = check_eligibility(attempt)
    if not check and not force:
        return None, check.reason

    exam = attempt.exam
    from apps.attempts.services import participants_count

    total = participants_count(exam)
    from django.conf import settings

    certificate = existing or Certificate(attempt=attempt)
    certificate.exam = exam
    certificate.user = attempt.user
    certificate.full_name = attempt.full_name or attempt.user.display_name
    certificate.exam_title = exam.title
    certificate.exam_date = timezone.localtime(
        attempt.submitted_at or attempt.created_at
    ).date()
    # Sertifikatda **yakuniy** ball turadi: esse yoqilgan testda u test va
    # esse ballining o'rtachasi (`Attempt.result_ball`).
    certificate.ball = float(attempt.result_ball or 0.0)
    certificate.max_ball = float(exam.max_ball or C.MAX_BALL)
    certificate.percent = float(attempt.percent or 0.0)
    certificate.grade = attempt.grade or ""
    certificate.award_percent = C.certificate_percent(certificate.ball, certificate.grade)
    certificate.rank = attempt.rank
    certificate.total_participants = total
    certificate.section_scores = attempt.section_scores or {}
    certificate.organization = getattr(settings, "CERT_ORGANIZATION", "")
    certificate.organizer_name = (
        exam.organizer_name or getattr(settings, "CERT_ORGANIZER_NAME", "")
    )
    certificate.issued_at = timezone.now()
    if not certificate.number:
        certificate.number = generate_number(exam)
    certificate.save()

    _render_and_attach(certificate)

    log_action(
        attempt.user,
        UserAction.Kind.CERT_ISSUED,
        f"Sertifikat berildi: {certificate.number}",
        exam_id=exam.id,
        attempt_id=attempt.id,
        number=certificate.number,
    )
    return certificate, "Sertifikat tayyor."


def _render_and_attach(certificate: Certificate) -> None:
    """PDF ni yaratadi va sertifikatga biriktiradi."""
    from django.conf import settings

    data = CertificateData(
        number=certificate.number,
        full_name=certificate.full_name,
        exam_title=certificate.exam_title,
        exam_date=certificate.exam_date,
        ball=certificate.ball,
        max_ball=certificate.max_ball,
        grade=certificate.grade,
        percent=certificate.percent,
        award_percent=certificate.award_percent,
        rank=certificate.rank,
        total_participants=certificate.total_participants,
        sections=certificate.section_rows,
        organization=certificate.organization,
        organizer_name=certificate.organizer_name,
        platform_name=getattr(settings, "CERT_PLATFORM_NAME", "RASCH MATH PLATFORM"),
        issued_at=timezone.localtime(certificate.issued_at).date(),
        verify_url=certificate.verify_url,
    )
    payload = render_pdf(data)
    filename = f"sertifikat_{slugify_filename(certificate.number)}.pdf"
    certificate.file.save(filename, ContentFile(payload), save=True)


# --------------------------------------------------------------------------
#  Ommaviy berish
# --------------------------------------------------------------------------


def issue_for_exam(exam: Exam) -> dict:
    """
    Test bo'yicha barcha huquqli qatnashchilarga sertifikat yaratadi.

    Qaytaradi: {"created": n, "skipped": n, "errors": n}.
    """
    created = skipped = errors = 0
    attempts = Attempt.objects.filter(
        exam=exam, status=Attempt.Status.SUBMITTED, is_scored=True
    ).select_related("user", "exam")

    for attempt in attempts:
        try:
            certificate, _ = issue_certificate(attempt)
            if certificate is None:
                skipped += 1
            else:
                created += 1
        except Exception:  # pragma: no cover
            logger.exception("Sertifikat yaratishda xato: attempt_id=%s", attempt.id)
            errors += 1

    return {"created": created, "skipped": skipped, "errors": errors}


# --------------------------------------------------------------------------
#  Tekshirish
# --------------------------------------------------------------------------


def verify(number: str, token: str = "") -> Certificate | None:
    """Sertifikat raqami (va ixtiyoriy token) bo'yicha tekshiradi."""
    if not number:
        return None
    certificate = (
        Certificate.objects.select_related("exam", "user", "attempt")
        .filter(number__iexact=number.strip())
        .first()
    )
    if certificate is None:
        return None
    if token and certificate.verify_token != token:
        return None
    return certificate


def get_certificate(attempt: Attempt) -> Certificate | None:
    """Urinishga tegishli sertifikatni qaytaradi."""
    return Certificate.objects.filter(attempt=attempt).first()


def register_download(certificate: Certificate) -> None:
    """Yuklab olishlar hisoblagichini oshiradi."""
    Certificate.objects.filter(pk=certificate.pk).update(
        downloads=certificate.downloads + 1
    )


__all__ = [
    "EligibilityCheck",
    "check_eligibility",
    "generate_number",
    "issue_certificate",
    "issue_for_exam",
    "verify",
    "get_certificate",
    "register_download",
]
