"""
Sertifikat modeli.

TZ 31-bo'lim talablari:
  * sertifikat raqami — noyob;
  * ism-familiya, test nomi, test sanasi, RASH balli, foiz, daraja;
  * bo'limlar bo'yicha natija (agar mavjud bo'lsa);
  * berilgan sana va tashkilotchi nomi;
  * har bir sertifikatda unikal QR-kod va tekshiruv sahifasi;
  * bitta sertifikat raqami = bitta qatnashchi + bitta test natijasi.
"""

from __future__ import annotations

import secrets

from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from core import constants as C


def _make_verify_token() -> str:
    """QR havolasi uchun taxmin qilib bo'lmaydigan token."""
    return secrets.token_urlsafe(16)


class CertificateQuerySet(models.QuerySet):
    """`Certificate` uchun qulay so'rovlar."""

    def valid(self):
        return self.filter(is_revoked=False)

    def for_exam(self, exam):
        return self.filter(exam=exam)


class Certificate(TimeStampedModel):
    """Bitta qatnashchi uchun bitta test bo'yicha elektron sertifikat."""

    number = models.CharField("Sertifikat raqami", max_length=32, unique=True, db_index=True)
    verify_token = models.CharField(
        "Tekshiruv tokeni", max_length=64, unique=True, default=_make_verify_token
    )

    exam = models.ForeignKey(
        "exams.Exam", on_delete=models.CASCADE, related_name="certificates",
        verbose_name="Test",
    )
    attempt = models.OneToOneField(
        "attempts.Attempt", on_delete=models.CASCADE, related_name="certificate",
        verbose_name="Urinish",
    )
    user = models.ForeignKey(
        "users.BotUser", on_delete=models.CASCADE, related_name="certificates",
        verbose_name="Qatnashchi",
    )

    # --- Sertifikat matnidagi ma'lumotlar (o'zgarmas nusxa) ---
    full_name = models.CharField("Ism va familiya", max_length=120)
    exam_title = models.CharField("Test nomi", max_length=150)
    exam_date = models.DateField("Test sanasi")
    ball = models.FloatField("RASH balli", default=0.0)
    max_ball = models.FloatField("Maksimal ball", default=C.MAX_BALL)
    percent = models.FloatField("To'g'ri javob foizi", null=True, blank=True)
    grade = models.CharField("Daraja", max_length=16, blank=True, default="")
    # Sertifikatda ko'rsatiladigan foiz: A+ va A uchun 100%, qolganida
    # `ball * 100 / 75` (`core.constants.certificate_percent`).
    award_percent = models.FloatField("Sertifikat foizi", null=True, blank=True)
    rank = models.PositiveIntegerField("Reyting o'rni", null=True, blank=True)
    total_participants = models.PositiveIntegerField("Jami qatnashchilar", default=0)
    section_scores = models.JSONField("Bo'limlar natijasi", default=dict, blank=True)

    organization = models.CharField("Tashkilot", max_length=150, blank=True, default="")
    organizer_name = models.CharField("Tashkilotchi", max_length=120, blank=True, default="")

    issued_at = models.DateTimeField("Berilgan sana", default=timezone.now)
    file = models.FileField("PDF fayl", upload_to="certificates/%Y/%m/", null=True, blank=True)

    is_revoked = models.BooleanField("Bekor qilingan", default=False)
    revoke_reason = models.CharField("Bekor qilish sababi", max_length=255, blank=True, default="")

    downloads = models.PositiveIntegerField("Yuklab olishlar soni", default=0)

    objects = CertificateQuerySet.as_manager()

    class Meta:
        verbose_name = "Sertifikat"
        verbose_name_plural = "Sertifikatlar"
        ordering = ("-issued_at",)
        indexes = [models.Index(fields=["exam", "-ball"])]

    def __str__(self) -> str:
        return f"{self.number} — {self.full_name}"

    # ------------------------------------------------------------------
    @property
    def verify_url(self) -> str:
        """QR-kod ichiga joylanadigan to'liq havola."""
        from django.conf import settings

        base = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
        return f"{base}{C.CERT_VERIFY_PATH}{self.number}/?t={self.verify_token}"

    @property
    def is_valid(self) -> bool:
        return not self.is_revoked

    @property
    def display_ball(self) -> str:
        return f"{self.ball:.2f}"

    @property
    def display_rank(self) -> str:
        if not self.rank or not self.total_participants:
            return "—"
        return f"{self.rank} / {self.total_participants}"

    @property
    def section_rows(self) -> list[tuple[str, str]]:
        """Bo'limlar natijasini ko'rsatish uchun ro'yxat."""
        rows: list[tuple[str, str]] = []
        for name, value in (self.section_scores or {}).items():
            if isinstance(value, dict):
                correct = value.get("correct", 0)
                total = value.get("total", 0)
                rows.append((str(name), f"{correct}/{total}"))
            else:
                rows.append((str(name), str(value)))
        return rows
