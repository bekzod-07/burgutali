"""
Test topshirish (urinish) va javoblar modellari.

Muhim qoida (TZ): ID kod faqat yakuniy javoblar bazaga muvaffaqiyatli
saqlangandan keyin "Ishlatilgan" holatiga o'tadi. Shuning uchun urinish
avval DRAFT holatida bo'ladi va faqat `submit` bosqichida SUBMITTED bo'ladi.
"""

from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from core import constants as C


class AttemptQuerySet(models.QuerySet):
    """`Attempt` uchun qulay so'rovlar."""

    def submitted(self):
        return self.filter(status=Attempt.Status.SUBMITTED)

    def drafts(self):
        return self.filter(status=Attempt.Status.DRAFT)

    def scored(self):
        return self.filter(status=Attempt.Status.SUBMITTED, is_scored=True)

    def for_exam(self, exam):
        return self.filter(exam=exam)

    def ranked(self):
        """
        Reyting tartibida: ball -> to'g'ri javob -> topshirish vaqti.

        Ballari teng bo'lganda testni oldinroq topshirgan yuqorida turadi —
        o'rinlar aynan shu tartibda 1, 2, 3, ... bo'lib raqamlanadi
        (`apps.rasch.services._assign_ranks`).
        """
        return self.order_by(
            models.F("ball").desc(nulls_last=True),
            "-raw_score",
            models.F("submitted_at").asc(nulls_last=True),
            "id",
        )


class Attempt(TimeStampedModel):
    """Bitta foydalanuvchining bitta testdagi urinishi."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Jarayonda"
        SUBMITTED = "submitted", "Yuborilgan"
        CANCELLED = "cancelled", "Bekor qilingan"

    exam = models.ForeignKey(
        "exams.Exam", on_delete=models.CASCADE, related_name="attempts", verbose_name="Test"
    )
    user = models.ForeignKey(
        "users.BotUser", on_delete=models.CASCADE, related_name="attempts",
        verbose_name="Ishtirokchi",
    )

    # --- Ro'yxatdan o'tish ma'lumotlari (o'sha paytdagi nusxasi) ---
    full_name = models.CharField("Ism va familiya", max_length=120, blank=True, default="")
    phone = models.CharField("Telefon", max_length=20, blank=True, default="")

    status = models.CharField(
        "Holati", max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )

    started_at = models.DateTimeField("Boshlangan vaqt", default=timezone.now)
    submitted_at = models.DateTimeField("Yuborilgan vaqt", null=True, blank=True)
    duration_seconds = models.PositiveIntegerField("Sarflangan vaqt (sek)", default=0)

    # --- Joriy holat (uzilib qolganda davom ettirish uchun) ---
    current_order = models.PositiveIntegerField("Joriy savol raqami", default=1)

    # --- Natijalar ---
    raw_score = models.FloatField("Xom ball (to'g'ri qismlar)", default=0.0)
    max_raw_score = models.FloatField("Maksimal xom ball", default=0.0)
    percent = models.FloatField("Foiz", default=0.0)
    wrong_count = models.PositiveIntegerField("Xato javoblar", default=0)
    empty_count = models.PositiveIntegerField("Bo'sh javoblar", default=0)

    theta = models.FloatField("Rasch theta", null=True, blank=True)
    theta_se = models.FloatField("theta standart xatosi", null=True, blank=True)
    ball = models.FloatField("Standart ball", null=True, blank=True, db_index=True)
    grade = models.CharField("Daraja", max_length=16, blank=True, default="")
    rank = models.PositiveIntegerField("Reyting o'rni", null=True, blank=True)

    section_scores = models.JSONField("Bo'limlar bo'yicha natija", default=dict, blank=True)

    is_scored = models.BooleanField("Baholangan", default=False)
    scored_at = models.DateTimeField("Baholangan vaqt", null=True, blank=True)

    objects = AttemptQuerySet.as_manager()

    class Meta:
        verbose_name = "Urinish"
        verbose_name_plural = "Urinishlar"
        ordering = ("-created_at",)
        constraints = [
            # Bitta foydalanuvchi bitta testga faqat bitta yakuniy javob yuboradi.
            models.UniqueConstraint(
                fields=["exam", "user"],
                condition=models.Q(status="submitted"),
                name="uniq_submitted_attempt_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["exam", "status"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["exam", "-ball"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name or self.user_id} — {self.exam_id}"

    # ------------------------------------------------------------------
    @property
    def correct_count(self) -> int:
        """To'g'ri javoblar soni (qismlar bo'yicha)."""
        return int(self.raw_score)

    @property
    def is_submitted(self) -> bool:
        return self.status == self.Status.SUBMITTED

    @property
    def display_ball(self) -> str:
        """Ballning matnli ko'rinishi."""
        if self.ball is None:
            return "—"
        return f"{self.ball:.2f}"

    @property
    def display_percent(self) -> str:
        return f"{self.percent:.1f}%"

    @property
    def access_code_value(self) -> str:
        """Urinish ochilgan bir martalik ID kod (bo'lmasa — bo'sh satr)."""
        try:
            code = self.access_code
        except ObjectDoesNotExist:
            return ""
        return code.code if code else ""

    @property
    def public_label(self) -> str:
        """
        Umumiy natijalarda ko'rsatiladigan nom — har uchala turda ham
        ism-familiya.

        Ilgari pullik testda (3-tur) ism o'rniga bir martalik ID kod
        chiqardi; 2026-09-23 dan natijalar hamma joyda F.I.SH bilan
        e'lon qilinadi. ID raqami esa panelda alohida ustunda qoladi
        (`access_code_value`).
        """
        name = (self.full_name or "").strip()
        if name:
            return name
        if self.user_id:
            return self.user.display_name
        return self.access_code_value or f"ID-{self.id}"

    def mark_submitted(self) -> None:
        """Urinishni yakunlangan deb belgilaydi."""
        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        if self.started_at:
            delta = self.submitted_at - self.started_at
            self.duration_seconds = max(0, int(delta.total_seconds()))

    def reset_scores(self) -> None:
        """Baholash natijalarini tozalaydi (qayta hisoblashdan oldin)."""
        self.raw_score = 0.0
        self.percent = 0.0
        self.wrong_count = 0
        self.empty_count = 0
        self.theta = None
        self.theta_se = None
        self.ball = None
        self.grade = ""
        self.rank = None
        self.section_scores = {}
        self.is_scored = False


class Answer(TimeStampedModel):
    """Bitta savolga berilgan javob."""

    attempt = models.ForeignKey(
        Attempt, on_delete=models.CASCADE, related_name="answers", verbose_name="Urinish"
    )
    question = models.ForeignKey(
        "exams.Question", on_delete=models.CASCADE, related_name="answers",
        verbose_name="Savol",
    )
    order = models.PositiveIntegerField("Savol tartibi", default=0, db_index=True)

    # --- Variantli javoblar ---
    selected = models.CharField(
        "Tanlangan variant(lar)", max_length=8, blank=True, default="",
        help_text="SINGLE: A. MULTI: ABD ko'rinishida.",
    )

    # --- Ochiq javoblar ---
    text_a = models.CharField("a) javob", max_length=255, blank=True, default="")
    text_b = models.CharField("b) javob", max_length=255, blank=True, default="")

    # --- Baholash ---
    is_correct_a = models.BooleanField("1-qism to'g'ri", null=True, blank=True)
    is_correct_b = models.BooleanField("2-qism to'g'ri", null=True, blank=True)
    score = models.FloatField("Olingan ball", default=0.0)

    answered_at = models.DateTimeField("Javob vaqti", default=timezone.now)

    class Meta:
        verbose_name = "Javob"
        verbose_name_plural = "Javoblar"
        ordering = ("attempt_id", "order")
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"], name="uniq_answer_per_question"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.attempt_id}/{self.order}: {self.display_value}"

    # ------------------------------------------------------------------
    @property
    def display_value(self) -> str:
        """Javobning o'qishga qulay ko'rinishi."""
        if self.selected:
            return self.selected
        parts = []
        if self.text_a:
            parts.append(f"a) {self.text_a}")
        if self.text_b:
            parts.append(f"b) {self.text_b}")
        return "; ".join(parts) if parts else "—"

    @property
    def is_empty(self) -> bool:
        """Javob berilmaganmi."""
        return not (self.selected or self.text_a or self.text_b)

    @property
    def is_fully_correct(self) -> bool:
        """Barcha qismlar to'g'rimi."""
        flags = [f for f in (self.is_correct_a, self.is_correct_b) if f is not None]
        return bool(flags) and all(flags)

    @property
    def status_icon(self) -> str:
        """
        Natijalar ro'yxatida ko'rsatiladigan tipografik belgi.

        Emoji ishlatilmaydi: ✓ to'g'ri, ✗ xato, ± qisman, · javobsiz.
        """
        if self.is_empty:
            return "·"
        if self.is_fully_correct:
            return "✓"
        if self.score > 0:
            return "±"
        return "✗"

    @property
    def status_code(self) -> str:
        """Web ilova uchun mashina o'qiydigan holat: correct/partial/wrong/empty."""
        if self.is_empty:
            return "empty"
        if self.is_fully_correct:
            return "correct"
        if self.score > 0:
            return "partial"
        return "wrong"


class ExamStatistics(TimeStampedModel):
    """
    Test bo'yicha yig'ma statistika (TZ 9-bo'lim: "ishtirokchilar statistikasi").

    Har safar natijalar qayta hisoblanganda yangilanadi.
    """

    exam = models.OneToOneField(
        "exams.Exam", on_delete=models.CASCADE, related_name="statistics", verbose_name="Test"
    )
    participants = models.PositiveIntegerField("Qatnashchilar soni", default=0)
    avg_raw_score = models.FloatField("O'rtacha xom ball", default=0.0)
    avg_percent = models.FloatField("O'rtacha foiz", default=0.0)
    avg_ball = models.FloatField("O'rtacha standart ball", default=0.0)
    max_ball_achieved = models.FloatField("Eng yuqori ball", default=0.0)
    min_ball_achieved = models.FloatField("Eng past ball", default=0.0)
    std_ball = models.FloatField("Ballar standart og'ishi", default=0.0)
    reliability = models.FloatField("Ishonchlilik (KR-20 / Rasch)", default=0.0)
    grade_distribution = models.JSONField("Darajalar taqsimoti", default=dict, blank=True)
    item_statistics = models.JSONField("Savollar statistikasi", default=list, blank=True)

    class Meta:
        verbose_name = "Test statistikasi"
        verbose_name_plural = "Testlar statistikasi"

    def __str__(self) -> str:
        return f"Statistika: {self.exam_id}"

    @property
    def grade_rows(self) -> list[tuple[str, int]]:
        """Darajalar taqsimotini tartiblangan ro'yxat sifatida qaytaradi."""
        data = self.grade_distribution or {}
        return [(g, int(data.get(g, 0))) for g in reversed(C.GRADE_ORDER)]


class MockParticipant(TimeStampedModel):
    """
    E'lon uchun qo'shiladigan soxta qatnashchi.

    Mock imtihonni katta auditoriyada o'tkazilgandek ko'rsatish uchun
    natijalar ro'yxatiga o'ylab topilgan ism-familiyalar qo'shiladi:
    admin jami sonni (masalan 1000) va darajalar ulushini beradi, tizim
    esa har bir darajaga tegishli ballni o'sha daraja oralig'idan tasodifiy
    tanlaydi (`apps.attempts.mock`).

    Soxta qatnashchi **alohida jadvalda** saqlanadi va `Attempt` ga umuman
    tegmaydi: Rasch hisob-kitobi, statistika, savollar qiyinchiligi va
    sertifikatlar faqat haqiqiy javoblar bo'yicha qoladi. Soxta qatorlar
    faqat e'lon qilinadigan reytingda ko'rinadi.
    """

    exam = models.ForeignKey(
        "exams.Exam",
        on_delete=models.CASCADE,
        related_name="mock_participants",
        verbose_name="Test",
    )
    full_name = models.CharField("Ism va familiya", max_length=120)
    ball = models.FloatField("Standart ball")
    grade = models.CharField("Daraja", max_length=16, blank=True, default="")
    #: Yaratilish tartibi — ballari teng chiqqanda qatorlar joyini
    #: o'zgartirmasligi uchun.
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Soxta qatnashchi"
        verbose_name_plural = "Soxta qatnashchilar"
        ordering = ("-ball", "order")
        indexes = [models.Index(fields=["exam", "-ball"])]

    def __str__(self) -> str:
        return f"{self.full_name} — {self.ball:.2f}"

    @property
    def display_ball(self) -> str:
        """Ballning matnli ko'rinishi (haqiqiy urinishdagidek)."""
        return f"{self.ball:.2f}"
