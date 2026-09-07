"""Ommaviy sahifalar: bosh sahifa, xatolik sahifalari, healthcheck."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render


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


def favicon(request):
    """
    Brauzer so'raydigan `/favicon.ico` ni statik belgiga yo'naltiradi.

    Manzil **so'rov paytida** hisoblanadi: production da
    `ManifestStaticFilesStorage` ishlatiladi va u `collectstatic` dan
    oldin manifestni topa olmaydi — bu esa `manage.py migrate` ni ham
    to'xtatib qo'yardi.
    """
    from django.templatetags.static import static

    try:
        url = static("favicon.svg")
    except ValueError:  # manifest hali yig'ilmagan
        url = f"{settings.STATIC_URL}favicon.svg"
    return redirect(url, permanent=True)


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
