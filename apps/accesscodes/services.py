"""
ID kodlar bilan ishlash xizmatlari.

Kodning hayotiy sikli (TZ talabi):

    Ishlatilmagan  ->  Faollashtirilgan  ->  Ishlatilgan
      (unused)          (activated)           (used)

Kod foydalanuvchi uni kiritgan zahoti "ishlatilgan" bo'lib qolmaydi —
faqat yakuniy javob bazaga muvaffaqiyatli saqlangandan keyin USED holatiga
o'tadi. Bu internet uzilishi kabi holatlarda kodning "kuyib ketishi"ning
oldini oladi.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction

from apps.exams.models import Exam
from apps.users.models import UserAction
from apps.users.services import log_action
from core import constants as C

from .generator import generate_unique_codes, is_valid_format, normalize_code
from .models import AccessCode, CodeBatch

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
#  Kodlarni yaratish
# --------------------------------------------------------------------------


@transaction.atomic
def create_codes(exam: Exam, quantity: int, created_by=None, note: str = "") -> CodeBatch:
    """
    Test uchun `quantity` ta noyob ID kod yaratadi.

    Kodlar aynan shu testga bog'lanadi — boshqa testda ishlatib bo'lmaydi.
    """
    quantity = max(1, min(int(quantity), C.CODE_BATCH_MAX))

    existing = set(AccessCode.objects.values_list("code", flat=True))
    codes = generate_unique_codes(quantity, existing)

    batch = CodeBatch.objects.create(
        exam=exam,
        quantity=len(codes),
        created_by=created_by,
        note=(note or "")[:255],
    )

    AccessCode.objects.bulk_create(
        [
            AccessCode(exam=exam, batch=batch, code=code, status=AccessCode.Status.UNUSED)
            for code in codes
        ],
        batch_size=1000,
    )

    log_action(
        created_by,
        UserAction.Kind.CODES_GENERATED,
        f"{len(codes)} ta ID kod yaratildi",
        exam_id=exam.id,
        exam_code=exam.code,
        quantity=len(codes),
        batch_id=batch.id,
    )
    logger.info("Test %s uchun %s ta ID kod yaratildi", exam.code, len(codes))
    return batch


# --------------------------------------------------------------------------
#  Kodni tekshirish
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeCheck:
    """ID kodni tekshirish natijasi."""

    ok: bool
    message: str
    code: AccessCode | None = None

    def __bool__(self) -> bool:
        return self.ok


def check_code(raw_code: str, exam: Exam | None = None) -> CodeCheck:
    """
    Kiritilgan ID kodni tekshiradi.

    Tekshiriladi (TZ tartibida):
      1. Bunday ID mavjudmi?
      2. ID aynan shu testga tegishlimi?
      3. ID avval ishlatilganmi?
    """
    normalized = normalize_code(raw_code)
    if not normalized:
        return CodeCheck(False, "ID kod kiritilmadi.")
    if not is_valid_format(normalized):
        return CodeCheck(
            False,
            "ID kod formati noto‘g‘ri.\n\nTo‘g‘ri ko‘rinish: <code>R7K4-8251</code>",
        )

    code = AccessCode.objects.select_related("exam").filter(code=normalized).first()
    if code is None:
        return CodeCheck(False, "Bunday ID kod topilmadi.")

    if exam is not None and code.exam_id != exam.id:
        return CodeCheck(
            False,
            "Bu ID kod boshqa testga tegishli.\n\n"
            f"Kod tegishli test: <b>{code.exam.title}</b>",
        )

    if code.status == AccessCode.Status.REVOKED:
        return CodeCheck(False, "Bu ID kod bekor qilingan.")

    if code.status == AccessCode.Status.USED:
        return CodeCheck(
            False,
            "Bu ID kod orqali javob avval yuborilgan.\n\n"
            "Har bir ID kod faqat bir marta ishlatilishi mumkin.",
        )

    return CodeCheck(True, "ID tasdiqlandi.", code)


# --------------------------------------------------------------------------
#  Holatni o'zgartirish
# --------------------------------------------------------------------------


@transaction.atomic
def activate_code(code: AccessCode, user, full_name: str = "") -> AccessCode:
    """
    Kodni faollashtiradi (test boshlanishida).

    Kod hali "ishlatilgan" hisoblanmaydi.
    """
    code = AccessCode.objects.select_for_update().get(pk=code.pk)
    if code.status == AccessCode.Status.USED:
        return code
    code.activate(user, full_name)
    code.save(
        update_fields=[
            "status", "user", "telegram_id", "full_name", "activated_at", "updated_at"
        ]
    )
    log_action(
        user,
        UserAction.Kind.CODE_ACTIVATED,
        f"ID kod faollashtirildi: {code.code}",
        code=code.code,
        exam_id=code.exam_id,
    )
    return code


@transaction.atomic
def consume_code(code: AccessCode, attempt) -> AccessCode:
    """Yakuniy javob saqlangandan keyin kodni "Ishlatilgan" holatiga o'tkazadi."""
    code = AccessCode.objects.select_for_update().get(pk=code.pk)
    code.consume(attempt)
    code.save(
        update_fields=[
            "status", "attempt", "used_at", "user", "telegram_id", "full_name", "updated_at"
        ]
    )
    log_action(
        attempt.user,
        UserAction.Kind.CODE_USED,
        f"ID kod ishlatildi: {code.code}",
        code=code.code,
        exam_id=code.exam_id,
        attempt_id=attempt.id,
    )
    return code


@transaction.atomic
def release_code(code: AccessCode) -> AccessCode:
    """Faollashtirilgan kodni bo'shatadi (foydalanuvchi testni tark etsa)."""
    code = AccessCode.objects.select_for_update().get(pk=code.pk)
    code.release()
    code.save(
        update_fields=[
            "status", "user", "telegram_id", "full_name", "activated_at", "updated_at"
        ]
    )
    return code


@transaction.atomic
def revoke_code(code: AccessCode, reason: str = "") -> AccessCode:
    """Kodni bekor qiladi (admin tomonidan)."""
    code = AccessCode.objects.select_for_update().get(pk=code.pk)
    code.status = AccessCode.Status.REVOKED
    code.save(update_fields=["status", "updated_at"])
    return code


def find_active_code(user, exam: Exam) -> AccessCode | None:
    """Foydalanuvchi ushbu test uchun faollashtirgan kodni topadi."""
    return (
        AccessCode.objects.filter(
            exam=exam, user=user, status=AccessCode.Status.ACTIVATED
        )
        .order_by("-activated_at")
        .first()
    )


# --------------------------------------------------------------------------
#  Statistika
# --------------------------------------------------------------------------


def code_statistics(exam: Exam) -> dict:
    """Test bo'yicha ID kodlar statistikasi."""
    queryset = AccessCode.objects.filter(exam=exam)
    return {
        "total": queryset.count(),
        "unused": queryset.filter(status=AccessCode.Status.UNUSED).count(),
        "activated": queryset.filter(status=AccessCode.Status.ACTIVATED).count(),
        "used": queryset.filter(status=AccessCode.Status.USED).count(),
        "revoked": queryset.filter(status=AccessCode.Status.REVOKED).count(),
    }


__all__ = [
    "CodeCheck",
    "create_codes",
    "check_code",
    "activate_code",
    "consume_code",
    "release_code",
    "revoke_code",
    "find_active_code",
    "code_statistics",
]
