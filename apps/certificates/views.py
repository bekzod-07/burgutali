"""
Sertifikatni tekshirish sahifalari.

QR-kod skanerlanganda `/verify/<raqam>/?t=<token>` manzili ochiladi va
sertifikat haqiqiyligi, ism-familiya, test nomi, natija, test sanasi hamda
sertifikat raqami ko'rsatiladi (TZ 31-bo'lim).
"""

from __future__ import annotations

from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from . import services


def verify_form(request):
    """Sertifikat raqamini kiritish sahifasi."""
    number = (request.GET.get("number") or request.POST.get("number") or "").strip()
    if number:
        return redirect("certificates:detail", number=number)
    return render(request, "certificates/verify_form.html")


def verify_detail(request, number: str):
    """Sertifikat tafsilotlari va haqiqiyligi."""
    token = request.GET.get("t", "")
    certificate = services.verify(number, token)

    context = {
        "number": number,
        "certificate": certificate,
        "is_valid": bool(certificate and certificate.is_valid),
        "token": token,
    }
    status = 200 if certificate else 404
    return render(request, "certificates/verify_detail.html", context, status=status)


def download(request, number: str):
    """Sertifikat PDF faylini yuklab berish."""
    token = request.GET.get("t", "")
    certificate = services.verify(number, token)
    if certificate is None or not certificate.file:
        raise Http404("Sertifikat topilmadi.")
    if certificate.is_revoked:
        raise Http404("Sertifikat bekor qilingan.")

    services.register_download(certificate)
    return FileResponse(
        certificate.file.open("rb"),
        as_attachment=True,
        filename=f"sertifikat_{certificate.number}.pdf",
        content_type="application/pdf",
    )
