"""
Telegram foydalanuvchilari modeli.

TZ 2-bo'lim: tizimda ikkita asosiy rol bor —
  * Administrator — testlarni yaratadi, ID kodlarni boshqaradi, natijalarni ko'radi;
  * Ishtirokchi   — ism, familiya (va pullik testda ID) orqali test topshiradi.

Har qanday foydalanuvchi bepul testlarni yaratishi mumkin (TZ, 1- va 2-tur),
pullik RASH testini esa faqat asosiy admin yaratadi.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class BotUserQuerySet(models.QuerySet):
    """`BotUser` uchun qulay so'rovlar."""

    def registered(self):
        return self.filter(is_registered=True)

    def admins(self):
        return self.filter(is_admin=True)

    def active(self):
        return self.filter(is_blocked=False)


class BotUser(TimeStampedModel):
    """Telegram orqali botdan foydalanuvchi."""

    telegram_id = models.BigIntegerField("Telegram ID", unique=True, db_index=True)
    username = models.CharField("Telegram username", max_length=64, blank=True, default="")
    tg_first_name = models.CharField("Telegram ismi", max_length=128, blank=True, default="")
    tg_last_name = models.CharField("Telegram familiyasi", max_length=128, blank=True, default="")

    # --- Ro'yxatdan o'tish ma'lumotlari (TZ 3-bo'lim) ---
    full_name = models.CharField("Ism va familiya", max_length=120, blank=True, default="")
    phone = models.CharField("Telefon raqami", max_length=20, blank=True, default="")
    is_registered = models.BooleanField("Ro'yxatdan o'tgan", default=False)
    registered_at = models.DateTimeField("Ro'yxatdan o'tgan vaqt", null=True, blank=True)

    # --- Rollar va holat ---
    is_admin = models.BooleanField("Asosiy admin", default=False)
    is_blocked = models.BooleanField("Bloklangan", default=False)
    block_reason = models.CharField("Bloklash sababi", max_length=255, blank=True, default="")

    # --- Majburiy obuna keshi ---
    is_subscribed = models.BooleanField("Kanalga a'zo", default=False)
    subscription_checked_at = models.DateTimeField(
        "Obuna tekshirilgan vaqt", null=True, blank=True
    )

    last_seen_at = models.DateTimeField("Oxirgi faollik", null=True, blank=True)

    objects = BotUserQuerySet.as_manager()

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["is_registered"]),
            models.Index(fields=["is_admin"]),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.telegram_id})"

    # ------------------------------------------------------------------
    #  Yordamchi xossalar
    # ------------------------------------------------------------------
    @property
    def display_name(self) -> str:
        """Ekranda ko'rsatiladigan nom."""
        if self.full_name:
            return self.full_name
        parts = [self.tg_first_name, self.tg_last_name]
        name = " ".join(p for p in parts if p).strip()
        if name:
            return name
        if self.username:
            return f"@{self.username}"
        return f"ID {self.telegram_id}"

    @property
    def username_link(self) -> str:
        """Telegram profiliga havola."""
        if self.username:
            return f"https://t.me/{self.username}"
        return f"tg://user?id={self.telegram_id}"

    def mark_registered(self) -> None:
        """Ro'yxatdan o'tganini belgilaydi."""
        self.is_registered = True
        if self.registered_at is None:
            self.registered_at = timezone.now()

    def touch(self) -> None:
        """Oxirgi faollik vaqtini yangilaydi."""
        self.last_seen_at = timezone.now()


class UserAction(models.Model):
    """
    Audit jurnali — muhim harakatlar tarixi.

    TZ 11-bo'lim: "xavfsizlik va ma'lumotlarni zaxiralash mexanizmlari".
    Kim, qachon, qaysi amalni bajarganini kuzatish imkonini beradi.
    """

    class Kind(models.TextChoices):
        REGISTER = "register", "Ro'yxatdan o'tdi"
        EXAM_CREATED = "exam_created", "Test yaratdi"
        EXAM_PUBLISHED = "exam_published", "Natijalarni e'lon qildi"
        ATTEMPT_STARTED = "attempt_started", "Testni boshladi"
        ATTEMPT_SUBMITTED = "attempt_submitted", "Javoblarni yubordi"
        CODE_ACTIVATED = "code_activated", "ID kodni faollashtirdi"
        CODE_USED = "code_used", "ID kodni ishlatdi"
        CODES_GENERATED = "codes_generated", "ID kodlar yaratdi"
        CERT_ISSUED = "cert_issued", "Sertifikat oldi"
        OTHER = "other", "Boshqa"

    user = models.ForeignKey(
        BotUser, on_delete=models.CASCADE, related_name="actions",
        verbose_name="Foydalanuvchi", null=True, blank=True,
    )
    kind = models.CharField("Amal", max_length=32, choices=Kind.choices, default=Kind.OTHER)
    description = models.CharField("Tavsif", max_length=255, blank=True, default="")
    payload = models.JSONField("Qo'shimcha ma'lumot", default=dict, blank=True)
    created_at = models.DateTimeField("Vaqt", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Amal tarixi"
        verbose_name_plural = "Amallar tarixi"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["kind", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.user_id}"
