"""Umumiy statistika (asinxron)."""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.utils import timezone


@sync_to_async(thread_sensitive=True)
def overview() -> dict:
    """Administrator paneli uchun umumiy ko'rsatkichlar."""
    from apps.accesscodes.models import AccessCode
    from apps.attempts.models import Attempt
    from apps.certificates.models import Certificate
    from apps.exams.models import Exam
    from apps.users.models import BotUser

    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        "users_total": BotUser.objects.count(),
        "users_registered": BotUser.objects.registered().count(),
        "users_new": BotUser.objects.filter(created_at__gte=today).count(),
        "users_active": BotUser.objects.filter(last_seen_at__gte=today).count(),
        "exams_total": Exam.objects.count(),
        "exams_active": Exam.objects.filter(status=Exam.Status.ACTIVE).count(),
        "exams_published": Exam.objects.filter(status=Exam.Status.PUBLISHED).count(),
        "attempts_total": Attempt.objects.filter(status=Attempt.Status.SUBMITTED).count(),
        "attempts_today": Attempt.objects.filter(
            status=Attempt.Status.SUBMITTED, submitted_at__gte=today
        ).count(),
        "codes_total": AccessCode.objects.count(),
        "codes_used": AccessCode.objects.filter(status=AccessCode.Status.USED).count(),
        "codes_unused": AccessCode.objects.filter(status=AccessCode.Status.UNUSED).count(),
        "certificates": Certificate.objects.count(),
    }


__all__ = ["overview"]
