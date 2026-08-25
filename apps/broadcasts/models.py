"""
Reklama (ommaviy xabar) modellari.

Panelda tayyorlangan xabar bazaga yoziladi, bot esa uni fon vazifasi
sifatida yuboradi. Shuning uchun ikkita jadval bor:

  * `Broadcast` — xabarning o'zi (matn, rasm, tugmalar, kimga, holati);
  * `BroadcastDelivery` — har bir qabul qiluvchi uchun alohida qator.

Har bir qabul qiluvchi alohida yozilishi ikkita muhim narsani beradi:
bot qayta ishga tushsa xabar **ikki marta** yuborilmaydi va yuborish
qayerda to'xtagani aniq ko'rinadi.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


def broadcast_image_path(instance: "Broadcast", filename: str) -> str:
    """Rasm `media/broadcasts/YYYY/MM/` ichiga saqlanadi."""
    now = timezone.now()
    return f"broadcasts/{now:%Y/%m}/{filename}"


class Broadcast(TimeStampedModel):
    """Botdagi foydalanuvchilarga yuboriladigan bitta reklama xabari."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        QUEUED = "queued", "Navbatda"
        SENDING = "sending", "Yuborilmoqda"
        DONE = "done", "Yakunlandi"
        CANCELLED = "cancelled", "To'xtatildi"
        FAILED = "failed", "Xato"

    class Audience(models.TextChoices):
        ALL = "all", "Barcha foydalanuvchilar"
        REGISTERED = "registered", "Ro'yxatdan o'tganlar"
        ACTIVE = "active", "Oxirgi 30 kunda faol bo'lganlar"
        ADMINS = "admins", "Faqat adminlar"
        EXAM = "exam", "Tanlangan test ishtirokchilari"

    #: `ACTIVE` auditoriyasi uchun faollik oynasi (kun).
    ACTIVE_DAYS: int = 30

    title = models.CharField(
        "Sarlavha (faqat panel uchun)", max_length=150, blank=True, default=""
    )
    text = models.TextField("Xabar matni", blank=True, default="")
    image = models.ImageField(
        "Rasm", upload_to=broadcast_image_path, blank=True, null=True
    )
    #: Telegram birinchi yuborishdan keyin qaytargan `file_id`. Keyingi
    #: yuborishlarda rasm qaytadan yuklanmaydi — bu ming kishilik
    #: reklamada trafikni ham, vaqtni ham bir necha barobar tejaydi.
    image_file_id = models.CharField(
        "Telegram fayl belgisi", max_length=256, blank=True, default=""
    )
    buttons = models.JSONField("Tugmalar", default=list, blank=True)

    audience = models.CharField(
        "Kimga", max_length=16, choices=Audience.choices, default=Audience.ALL
    )
    exam = models.ForeignKey(
        "exams.Exam",
        verbose_name="Test",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="broadcasts",
    )

    status = models.CharField(
        "Holati", max_length=12, choices=Status.choices,
        default=Status.DRAFT, db_index=True,
    )
    scheduled_at = models.DateTimeField(
        "Rejalashtirilgan vaqt", null=True, blank=True,
        help_text="Bo'sh bo'lsa darhol yuboriladi.",
    )

    total = models.PositiveIntegerField("Qabul qiluvchilar", default=0)
    sent = models.PositiveIntegerField("Yuborildi", default=0)
    failed = models.PositiveIntegerField("Yuborilmadi", default=0)
    blocked = models.PositiveIntegerField("Botni bloklaganlar", default=0)

    started_at = models.DateTimeField("Boshlangan vaqt", null=True, blank=True)
    finished_at = models.DateTimeField("Tugagan vaqt", null=True, blank=True)
    error = models.CharField("Xato", max_length=255, blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Kim yaratdi",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="broadcasts",
    )

    # --- Sinov yuborish (bitta odamga, yuborishdan oldin ko'rish uchun) ---
    test_target_id = models.BigIntegerField(
        "Sinov uchun Telegram ID", null=True, blank=True
    )
    test_requested_at = models.DateTimeField(
        "Sinov so'ralgan vaqt", null=True, blank=True
    )
    test_sent_at = models.DateTimeField("Sinov yuborilgan vaqt", null=True, blank=True)
    test_error = models.CharField("Sinov xatosi", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Reklama xabari"
        verbose_name_plural = "Reklama xabarlari"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "scheduled_at"]),
        ]

    def __str__(self) -> str:
        return self.display_title

    # ------------------------------------------------------------------
    #  Yordamchi xossalar
    # ------------------------------------------------------------------
    @property
    def display_title(self) -> str:
        """Ro'yxatda ko'rinadigan nom."""
        if self.title:
            return self.title
        from apps.broadcasts.formatting import to_plain_text

        plain = " ".join(to_plain_text(self.text).split())
        if plain:
            return plain[:60] + ("…" if len(plain) > 60 else "")
        return f"№{self.pk} reklama"

    @property
    def is_editable(self) -> bool:
        """Xabarni tahrirlash mumkinmi (yuborish boshlanmaganda)."""
        return self.status in {self.Status.DRAFT, self.Status.FAILED}

    @property
    def is_running(self) -> bool:
        """Hozir navbatda yoki yuborilmoqdami."""
        return self.status in {self.Status.QUEUED, self.Status.SENDING}

    @property
    def is_finished(self) -> bool:
        return self.status in {
            self.Status.DONE,
            self.Status.CANCELLED,
            self.Status.FAILED,
        }

    @property
    def processed(self) -> int:
        """Ishlangan qabul qiluvchilar soni."""
        return self.sent + self.failed + self.blocked

    @property
    def progress_percent(self) -> int:
        """Yuborish jarayoni foizda (0–100)."""
        if not self.total:
            return 100 if self.is_finished else 0
        return min(100, round(self.processed * 100 / self.total))

    @property
    def has_image(self) -> bool:
        return bool(self.image and self.image.name)

    @property
    def button_rows(self) -> list[list[dict[str, str]]]:
        """Tugmalar — har doim qatorlar ro'yxati ko'rinishida."""
        rows = self.buttons or []
        if not isinstance(rows, list):
            return []
        result: list[list[dict[str, str]]] = []
        for row in rows:
            if isinstance(row, dict):  # eski format: bitta tugma
                row = [row]
            if isinstance(row, list):
                buttons = [
                    button for button in row
                    if isinstance(button, dict) and button.get("text") and button.get("url")
                ]
                if buttons:
                    result.append(buttons)
        return result

    @property
    def button_count(self) -> int:
        return sum(len(row) for row in self.button_rows)

    @property
    def audience_label(self) -> str:
        """Auditoriya nomi (test tanlangan bo'lsa test kodi bilan)."""
        label = self.get_audience_display()
        if self.audience == self.Audience.EXAM and self.exam_id and self.exam:
            return f"{label} — {self.exam.code}"
        return label


class BroadcastDelivery(models.Model):
    """Bitta foydalanuvchiga yuborilgan (yoki yuborilishi kerak) xabar."""

    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Yuborilmadi"
        BLOCKED = "blocked", "Botni bloklagan"

    broadcast = models.ForeignKey(
        Broadcast, on_delete=models.CASCADE, related_name="deliveries",
        verbose_name="Reklama",
    )
    user = models.ForeignKey(
        "users.BotUser", on_delete=models.CASCADE, related_name="broadcast_deliveries",
        verbose_name="Foydalanuvchi",
    )
    #: Foydalanuvchi o'chirilsa ham kimga yuborilgani ko'rinib tursin.
    telegram_id = models.BigIntegerField("Telegram ID")
    status = models.CharField(
        "Holati", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    error = models.CharField("Xato", max_length=200, blank=True, default="")
    sent_at = models.DateTimeField("Yuborilgan vaqt", null=True, blank=True)

    class Meta:
        verbose_name = "Yuborish"
        verbose_name_plural = "Yuborishlar"
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=["broadcast", "user"], name="broadcast_user_unique"
            )
        ]
        indexes = [
            models.Index(fields=["broadcast", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.telegram_id} — {self.get_status_display()}"


__all__ = ["Broadcast", "BroadcastDelivery", "broadcast_image_path"]
