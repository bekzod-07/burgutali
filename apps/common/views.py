"""Ommaviy sahifalar: bosh sahifa, xatolik sahifalari, healthcheck."""

from __future__ import annotations

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


def home(request):
    """Platformaning ommaviy bosh sahifasi."""
    from apps.exams.models import Exam
    from apps.attempts.models import Attempt
    from apps.certificates.models import Certificate

    stats = {
        "exams": Exam.objects.count(),
        "attempts": Attempt.objects.filter(status=Attempt.Status.SUBMITTED).count(),
        "certificates": Certificate.objects.count(),
    }
    return render(request, "common/home.html", {"stats": stats})


def healthcheck(request):
    """Oddiy holat tekshiruvi (monitoring uchun)."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_ok = True
    except Exception:  # pragma: no cover
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "error", "database": db_ok})


def error_404(request, exception=None):  # noqa: ANN001
    """404 — sahifa topilmadi."""
    return render(request, "common/404.html", status=404)


def error_500(request):  # noqa: ANN001
    """500 — server xatosi."""
    try:
        return render(request, "common/500.html", status=500)
    except Exception:  # pragma: no cover
        return HttpResponse("Server xatosi", status=500)
