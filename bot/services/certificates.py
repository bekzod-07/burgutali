"""Sertifikatlar bilan ishlash (asinxron)."""

from __future__ import annotations

from asgiref.sync import sync_to_async

from apps.certificates import services as certificate_services
from apps.certificates.models import Certificate

# --------------------------------------------------------------------------

check_eligibility = sync_to_async(certificate_services.check_eligibility, thread_sensitive=True)
issue_certificate = sync_to_async(certificate_services.issue_certificate, thread_sensitive=True)
issue_for_exam = sync_to_async(certificate_services.issue_for_exam, thread_sensitive=True)
get_certificate = sync_to_async(certificate_services.get_certificate, thread_sensitive=True)


@sync_to_async(thread_sensitive=True)
def user_certificates(user, limit: int = 20) -> list[Certificate]:
    """Foydalanuvchining sertifikatlari."""
    return list(
        Certificate.objects.filter(user=user, is_revoked=False)
        .select_related("exam")
        .order_by("-issued_at")[:limit]
    )


@sync_to_async(thread_sensitive=True)
def certificate_payload(certificate_id: int) -> tuple[bytes, str, dict] | None:
    """
    Sertifikat PDF faylini va uning ma'lumotlarini qaytaradi.

    Qaytaradi: `(bayt massivi, fayl nomi, ma'lumotlar)` yoki `None`.
    """
    certificate = Certificate.objects.select_related("exam").filter(pk=certificate_id).first()
    if certificate is None or not certificate.file:
        return None
    try:
        with certificate.file.open("rb") as handle:
            payload = handle.read()
    except (FileNotFoundError, OSError):
        return None

    info = {
        "number": certificate.number,
        "ball": certificate.display_ball,
        "grade": certificate.grade or "—",
        "rank": certificate.display_rank,
        "title": certificate.exam_title,
        "verify_url": certificate.verify_url,
    }
    filename = f"sertifikat_{certificate.number}.pdf"
    Certificate.objects.filter(pk=certificate.pk).update(
        downloads=certificate.downloads + 1
    )
    return payload, filename, info


__all__ = [
    "check_eligibility",
    "issue_certificate",
    "issue_for_exam",
    "get_certificate",
    "user_certificates",
    "certificate_payload",
]
