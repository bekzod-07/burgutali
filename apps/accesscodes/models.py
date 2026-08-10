"""
Bir martalik ID kodlar modeli.

TZ talablari:
  * Admin testga tegishli N ta noyob ID kod yaratadi (500 / 1000 / 1500 / 2000
    yoki boshqa miqdor). SRS 5-bo'limida esa standart hajm — 3000 ta.
  * Kodlar tasodifiy va takrorlanmaydigan bo'lishi kerak (R7K4-8251 formati).
  * Kod holatlari: Ishlatilmagan -> Faollashtirilgan -> Ishlatilgan.
  * Kod foydalanuvchi uni kiritgan zahoti "ishlatilgan" bo'lib qolmasligi kerak;
    faqat yakuniy javob bazaga saqlangandan keyin USED holatiga o'tadi.
  * Qaysi ID orqali qaysi Telegram ID, ism-familiya, qachon va qaysi testga
    javob yuborilgani saqlanadi.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class CodeBatch(TimeStampedModel):
    """Bir marta yaratilgan ID kodlar to'plami (partiya)."""

    exam = models.ForeignKey(
        "exams.Exam", on_delete=models.CASCADE, related_name="code_batches",
        verbose_name="Test",
    )
    quantity = models.PositiveIntegerField("Kodlar soni", default=0)
    created_by = models.ForeignKey(
        "users.BotUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="code_batches", verbose_name="Yaratuvchi",
    )
    note = models.CharField("Izoh", max_length=255, blank=True, default="")
    file = models.FileField(
        "Excel fayl", upload_to="exports/codes/", null=True, blank=True
    )

    class Meta:
        verbose_name = "ID kodlar partiyasi"
        verbose_name_plural = "ID kodlar partiyalari"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.exam_id} — {self.quantity} ta kod"

    @property
    def used_count(self) -> int:
        return self.codes.filter(status=AccessCode.Status.USED).count()

    @property
    def unused_count(self) -> int:
        return self.codes.filter(status=AccessCode.Status.UNUSED).count()


class AccessCodeQuerySet(models.QuerySet):
    """`AccessCode` uchun qulay so'rovlar."""

    def unused(self):
        return self.filter(status=AccessCode.Status.UNUSED)

    def activated(self):
        return self.filter(status=AccessCode.Status.ACTIVATED)

    def used(self):
        return self.filter(status=AccessCode.Status.USED)

    def available(self):
        """Ishlatishga yaroqli kodlar (hali yakuniy javob yuborilmagan)."""
        return self.filter(
            status__in=[AccessCode.Status.UNUSED, AccessCode.Status.ACTIVATED]
        )


class AccessCode(TimeStampedModel):
    """Pullik testga kirish uchun bir martalik ID kod."""

    class Status(models.TextChoices):
        UNUSED = "unused", "Ishlatilmagan"
        ACTIVATED = "activated", "Faollashtirilgan"
        USED = "used", "Ishlatilgan"
        REVOKED = "revoked", "Bekor qilingan"

    exam = models.ForeignKey(
        "exams.Exam", on_delete=models.CASCADE, related_name="access_codes",
        verbose_name="Test",
    )
    batch = models.ForeignKey(
        CodeBatch, on_delete=models.CASCADE, related_name="codes",
        verbose_name="Partiya", null=True, blank=True,
    )
    code = models.CharField("ID kod", max_length=16, unique=True, db_index=True)
    status = models.CharField(
        "Holati", max_length=12, choices=Status.choices,
        default=Status.UNUSED, db_index=True,
    )

    # --- Kim ishlatgani (TZ: "qaysi ID orqali qaysi Telegram ID ...") ---
    user = models.ForeignKey(
        "users.BotUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="access_codes", verbose_name="Foydalanuvchi",
    )
    telegram_id = models.BigIntegerField("Telegram ID", null=True, blank=True)
    full_name = models.CharField("Ism va familiya", max_length=120, blank=True, default="")
    attempt = models.OneToOneField(
        "attempts.Attempt", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="access_code", verbose_name="Urinish",
    )

    activated_at = models.DateTimeField("Faollashtirilgan vaqt", null=True, blank=True)
    used_at = models.DateTimeField("Ishlatilgan vaqt", null=True, blank=True)

    objects = AccessCodeQuerySet.as_manager()

    class Meta:
        verbose_name = "ID kod"
        verbose_name_plural = "ID kodlar"
        ordering = ("exam_id", "id")
        indexes = [
            models.Index(fields=["exam", "status"]),
            models.Index(fields=["telegram_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_status_display()})"

    # ------------------------------------------------------------------
    @property
    def is_available(self) -> bool:
        """Kod hali yakuniy javob uchun ishlatilmaganmi."""
        return self.status in {self.Status.UNUSED, self.Status.ACTIVATED}

    def activate(self, user, full_name: str = "") -> None:
        """
        Kodni faollashtiradi (test boshlanganda).

        Bu bosqichda kod hali "ishlatilgan" hisoblanmaydi — foydalanuvchining
        interneti uzilsa ham kod kuyib ketmaydi.
        """
        self.status = self.Status.ACTIVATED
        self.user = user
        self.telegram_id = getattr(user, "telegram_id", None)
        self.full_name = full_name or getattr(user, "full_name", "") or ""
        if self.activated_at is None:
            self.activated_at = timezone.now()

    def consume(self, attempt) -> None:
        """Yakuniy javob saqlangandan keyin kodni ishlatilgan deb belgilaydi."""
        self.status = self.Status.USED
        self.attempt = attempt
        self.used_at = timezone.now()
        if attempt is not None:
            self.user = attempt.user
            self.telegram_id = attempt.user.telegram_id
            self.full_name = attempt.full_name or self.full_name

    def release(self) -> None:
        """Faollashtirilgan kodni bo'shatadi (foydalanuvchi testdan chiqsa)."""
        if self.status == self.Status.ACTIVATED:
            self.status = self.Status.UNUSED
            self.user = None
            self.telegram_id = None
            self.full_name = ""
            self.activated_at = None
