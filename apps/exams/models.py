"""
Test (imtihon) va savollar modellari.

TZ bo'yicha uchta test turi mavjud:

  1-tur  SIMPLE      — Oddiy test. Har qanday ro'yxatdan o'tgan foydalanuvchi
                       yaratadi. A/B/C/D variantlari. Natija — to'g'ri javoblar
                       soni va foiz. RASH ishlatilmaydi. Sertifikat yo'q.

  2-tur  RASCH_FREE  — Bepul RASH testi. Har qanday foydalanuvchi yaratadi.
                       Natija Rasch (IRT-1PL) modeli asosida hisoblanadi.
                       Sertifikat yo'q.

  3-tur  RASCH_PAID  — Pullik RASH testi. Faqat asosiy admin yaratadi.
                       Kirish bir martalik ID kod orqali. Sertifikat beriladi.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from core import constants as C


class ReservedExamCode(models.Model):
    """
    Ayni damda band bo'lgan test kodi.

    Test kodi ishtirokchi uchun qulay bo'lishi kerak — shuning uchun u oddiy
    ikki yoki uch xonali son (``32``, ``145``). Bunday kodlar soni cheklangan,
    shuning uchun ular **qayta ishlatiladi**: test yakunlangach (yopilganda,
    arxivlanganda yoki o'chirilganda) kod «kuyadi» — `released_at` belgilanadi
    va bot uni yangi testga bemalol bera oladi.

    Jadval ikkita vazifani bajaradi:

      * test yaratilayotgan paytda kodni band qilib turadi (bir vaqtda ikkita
        test yaratilsa ham bitta kod ikki marta berilmaydi);
      * qaysi kod hozir kimda ekanini ko'rsatadi.
    """

    code = models.CharField("Test kodi", max_length=20, unique=True, db_index=True)
    exam_title = models.CharField("Qaysi test uchun", max_length=150, blank=True, default="")
    created_at = models.DateTimeField("Berilgan vaqt", auto_now_add=True)
    released_at = models.DateTimeField("Bo'shatilgan vaqt", null=True, blank=True)

    class Meta:
        verbose_name = "Band qilingan test kodi"
        verbose_name_plural = "Band qilingan test kodlari"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.code

    @property
    def is_free(self) -> bool:
        """Kod boshqa testga berilishi mumkinmi."""
        return self.released_at is not None


class ExamQuerySet(models.QuerySet):
    """`Exam` uchun qulay so'rovlar."""

    def active(self):
        return self.filter(status=Exam.Status.ACTIVE)

    def rasch(self):
        return self.filter(exam_type__in=[Exam.Type.RASCH_FREE, Exam.Type.RASCH_PAID])

    def paid(self):
        return self.filter(exam_type=Exam.Type.RASCH_PAID)

    def public_active(self):
        return self.filter(status=Exam.Status.ACTIVE, is_public=True)

    def owned_by(self, user):
        return self.filter(owner=user)


class Exam(TimeStampedModel):
    """Bitta test (imtihon)."""

    class Type(models.TextChoices):
        SIMPLE = "simple", "1-tur — Oddiy test"
        RASCH_FREE = "rasch_free", "2-tur — Bepul RASH testi"
        RASCH_PAID = "rasch_paid", "3-tur — Pullik RASH testi"

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        ACTIVE = "active", "Faol (javoblar qabul qilinmoqda)"
        CLOSED = "closed", "Yopilgan"
        CALCULATED = "calculated", "Natijalar hisoblangan"
        PUBLISHED = "published", "Natijalar e'lon qilingan"
        ARCHIVED = "archived", "Arxivlangan"

    class CertificateScope(models.TextChoices):
        ALL = "all", "Barcha qatnashchilarga"
        MIN_BALL = "min_ball", "Belgilangan balldan yuqori bo'lganlarga"
        MIN_GRADE = "min_grade", "Belgilangan darajadan yuqori bo'lganlarga"

    #: Kod band hisoblanadigan holatlar — test hali yakunlanmagan.
    #: Test bu holatlardan chiqishi bilan kodi bo'shaydi va boshqa testga
    #: berilishi mumkin (`ReservedExamCode` ga qarang).
    LIVE_STATUSES: tuple[str, ...] = ("draft", "active")

    # --- Asosiy ---
    title = models.CharField("Test nomi", max_length=150)
    # Kod faqat **yakunlanmagan** testlar orasida takrorlanmasligi kerak:
    # yopilgan testning kodi yangi testga qayta beriladi. Shu sababli
    # `unique=True` o'rniga shartli cheklov ishlatiladi (Meta.constraints).
    code = models.CharField("Test kodi", max_length=20, db_index=True)
    exam_type = models.CharField(
        "Test turi", max_length=16, choices=Type.choices, default=Type.SIMPLE, db_index=True
    )
    status = models.CharField(
        "Holati", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    owner = models.ForeignKey(
        "users.BotUser", on_delete=models.CASCADE, related_name="exams",
        verbose_name="Yaratuvchi",
    )
    description = models.TextField("Tavsif", blank=True, default="")

    # --- Tuzilma ---
    question_count = models.PositiveIntegerField(
        "Savollar soni", default=0, validators=[MaxValueValidator(500)]
    )
    is_national_template = models.BooleanField(
        "Milliy sertifikat shabloni (45 ta savol)", default=False
    )

    # --- Vaqt va kirish ---
    starts_at = models.DateTimeField("Boshlanish vaqti", null=True, blank=True)
    ends_at = models.DateTimeField("Tugash vaqti", null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(
        "Davomiyligi (daqiqa, 0 = cheklanmagan)", default=0
    )
    is_public = models.BooleanField("Ommaviy ro'yxatda ko'rinsin", default=True)

    # --- Natijalarni ko'rsatish (TZ, 1-tur talablari) ---
    show_results_to_participants = models.BooleanField(
        "Natija qatnashchilarga ko'rinsin", default=True
    )
    show_correct_answers = models.BooleanField(
        "To'g'ri/xato javoblar ko'rsatilsin", default=True
    )
    show_rating_to_participants = models.BooleanField(
        "Reyting qatnashchilarga ko'rinsin", default=True
    )

    # --- Rasch sozlamalari (TZ 7-bo'lim) ---
    max_ball = models.FloatField("Maksimal standart ball", default=C.MAX_BALL)
    theta_min = models.FloatField("theta quyi chegara", default=C.THETA_MIN)
    theta_max = models.FloatField("theta yuqori chegara", default=C.THETA_MAX)
    auto_calibrate = models.BooleanField(
        "Savol qiyinligi ma'lumotlardan hisoblansin (JMLE)", default=True
    )

    # --- Sertifikat sozlamalari (TZ 31-bo'lim) ---
    certificate_enabled = models.BooleanField("Sertifikat berilsinmi", default=False)
    certificate_scope = models.CharField(
        "Sertifikat kimlarga", max_length=16,
        choices=CertificateScope.choices, default=CertificateScope.ALL,
    )
    certificate_min_ball = models.FloatField(
        "Minimal ball", null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1000.0)],
    )
    certificate_min_grade = models.CharField(
        "Minimal daraja", max_length=8, blank=True, default=""
    )
    organizer_name = models.CharField(
        "Tashkilotchi / o'qituvchi", max_length=120, blank=True, default=""
    )

    # --- Hisoblash holati ---
    calculated_at = models.DateTimeField("Hisoblangan vaqt", null=True, blank=True)
    published_at = models.DateTimeField("E'lon qilingan vaqt", null=True, blank=True)
    closed_at = models.DateTimeField("Yopilgan vaqt", null=True, blank=True)

    # --- Adminga yuborilgan avtomatik hisobotlar ---
    # Test yopilganda va natijalar e'lon qilinganda umumiy natijalar PDF
    # ko'rinishida adminlarga yuboriladi. Ikki marta yubormaslik uchun
    # yuborilgan vaqt shu yerda belgilanadi.
    closed_report_sent_at = models.DateTimeField(
        "Yopilish hisoboti yuborilgan vaqt", null=True, blank=True
    )
    published_report_sent_at = models.DateTimeField(
        "E'lon hisoboti yuborilgan vaqt", null=True, blank=True
    )

    objects = ExamQuerySet.as_manager()

    class Meta:
        verbose_name = "Test"
        verbose_name_plural = "Testlar"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["exam_type", "status"]),
            models.Index(fields=["owner", "-created_at"]),
        ]
        constraints = [
            # Bitta kod bir vaqtning o'zida faqat bitta yakunlanmagan
            # testda bo'lishi mumkin. Yopilgan testlar kodni ushlab
            # turmaydi — shu sababli kod qayta ishlatiladi.
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(status__in=("draft", "active")),
                name="uniq_live_exam_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.code}]"

    # ------------------------------------------------------------------
    #  Turga oid xossalar
    # ------------------------------------------------------------------
    @property
    def uses_rasch(self) -> bool:
        """Natija Rasch modeli orqali hisoblanadimi."""
        return self.exam_type in {self.Type.RASCH_FREE, self.Type.RASCH_PAID}

    @property
    def requires_access_code(self) -> bool:
        """Testga kirish uchun bir martalik ID kod talab qilinadimi."""
        return self.exam_type == self.Type.RASCH_PAID

    @property
    def can_issue_certificate(self) -> bool:
        """Sertifikat berish mumkinmi (TZ: faqat 3-tur)."""
        return self.exam_type == self.Type.RASCH_PAID and self.certificate_enabled

    @property
    def is_admin_only(self) -> bool:
        """Testni faqat asosiy admin yaratishi mumkinmi."""
        return self.exam_type == self.Type.RASCH_PAID

    # ------------------------------------------------------------------
    #  Holat bilan ishlash
    # ------------------------------------------------------------------
    @property
    def is_time_over(self) -> bool:
        """Belgilangan tugash vaqti o'tganmi."""
        return bool(self.ends_at and timezone.now() >= self.ends_at)

    @property
    def is_not_started(self) -> bool:
        """Boshlanish vaqti hali kelmaganmi."""
        return bool(self.starts_at and timezone.now() < self.starts_at)

    @property
    def accepts_answers(self) -> bool:
        """Ayni damda javob qabul qilinadimi."""
        if self.status != self.Status.ACTIVE:
            return False
        if self.is_not_started or self.is_time_over:
            return False
        return self.question_count > 0

    @property
    def results_available(self) -> bool:
        """Natijalar e'lon qilinganmi."""
        return self.status == self.Status.PUBLISHED

    @property
    def deep_link(self) -> str:
        """Botga to'g'ridan-to'g'ri kirish havolasi."""
        from django.conf import settings

        username = getattr(settings, "BOT_USERNAME", "")
        if not username:
            return ""
        return f"https://t.me/{username}?start=exam_{self.code}"

    # ------------------------------------------------------------------
    #  Maksimal xom ball
    # ------------------------------------------------------------------
    @property
    def max_raw_score(self) -> float:
        """Testdagi barcha ballanadigan birliklar (item) soni."""
        agg = self.questions.filter(is_active=True).aggregate(total=models.Sum("parts"))
        return float(agg["total"] or 0)


class QuestionQuerySet(models.QuerySet):
    """`Question` uchun qulay so'rovlar."""

    def active(self):
        return self.filter(is_active=True)

    def ordered(self):
        return self.order_by("order")


class Question(TimeStampedModel):
    """
    Testdagi bitta savol.

    TZ 3-bo'lim (Milliy sertifikat shabloni):
      * 1–32  — SINGLE: A, B, C, D (bitta to'g'ri javob);
      * 33–35 — MULTI : A, B, C, D, E, F (moslashtirish, bitta to'g'ri javob);
      * 36–45 — OPEN  : variantsiz, a) va b) javob maydonlari.
    """

    class Kind(models.TextChoices):
        SINGLE = "single", "Bitta javobli (A–D)"
        MULTI = "multi", "Moslashtirish (A–F)"
        OPEN = "open", "Ochiq javob (a, b)"

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name="questions", verbose_name="Test"
    )
    order = models.PositiveIntegerField("Tartib raqami", db_index=True)
    kind = models.CharField("Turi", max_length=8, choices=Kind.choices, default=Kind.SINGLE)
    text = models.TextField("Savol matni", blank=True, default="")
    section = models.CharField("Bo'lim", max_length=64, blank=True, default="")

    # --- Variantlar ---
    choices_count = models.PositiveSmallIntegerField(
        "Variantlar soni", default=4,
        validators=[MinValueValidator(2), MaxValueValidator(6)],
    )
    correct_key = models.CharField(
        "To'g'ri javob kaliti", max_length=8, blank=True, default="",
        help_text="Bitta harf: A. Moslashtirish savollarida ham bitta harf (A–F).",
    )

    # --- Ochiq javoblar (36–45) ---
    answer_a = models.CharField(
        "a) javob", max_length=255, blank=True, default="",
        help_text="Matematik ifoda; SymPy orqali ekvivalentlikka tekshiriladi.",
    )
    answer_b = models.CharField("b) javob", max_length=255, blank=True, default="")
    numeric_tolerance = models.FloatField(
        "Sonli xatolik chegarasi", default=1e-6,
        help_text="Sonli javoblarni taqqoslashda ruxsat etilgan farq.",
    )

    # --- Rasch parametrlari (TZ 7- va 9-bo'limlar) ---
    parts = models.PositiveSmallIntegerField(
        "Ballanadigan qismlar soni", default=1,
        validators=[MinValueValidator(1), MaxValueValidator(2)],
    )
    difficulty = models.FloatField(
        "Qiyinlik b (1-qism)", default=0.0,
        validators=[MinValueValidator(C.DIFFICULTY_MIN), MaxValueValidator(C.DIFFICULTY_MAX)],
    )
    difficulty_b = models.FloatField(
        "Qiyinlik b (2-qism)", null=True, blank=True,
        validators=[MinValueValidator(C.DIFFICULTY_MIN), MaxValueValidator(C.DIFFICULTY_MAX)],
    )
    difficulty_locked = models.BooleanField(
        "Qiyinlik qo'lda kiritilgan (avtomatik o'zgartirilmasin)", default=False
    )

    is_active = models.BooleanField("Faol", default=True)

    objects = QuestionQuerySet.as_manager()

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ("exam_id", "order")
        constraints = [
            models.UniqueConstraint(fields=["exam", "order"], name="uniq_exam_question_order"),
        ]

    def __str__(self) -> str:
        return f"{self.exam_id}/{self.order} ({self.get_kind_display()})"

    # ------------------------------------------------------------------
    @property
    def choice_letters(self) -> tuple[str, ...]:
        """Ushbu savol uchun variant harflari."""
        if self.kind == self.Kind.MULTI:
            return C.MULTI_CHOICES[: self.choices_count]
        if self.kind == self.Kind.SINGLE:
            return C.SINGLE_CHOICES[: self.choices_count]
        return ()

    @property
    def correct_set(self) -> set[str]:
        """To'g'ri javob harflari to'plami."""
        return {ch for ch in (self.correct_key or "").upper() if ch.isalpha()}

    @property
    def max_score(self) -> int:
        """Savoldan olish mumkin bo'lgan maksimal ball (qismlar soni)."""
        return int(self.parts)

    @property
    def difficulty_for_part(self) -> tuple[float, float]:
        """(1-qism qiyinligi, 2-qism qiyinligi)."""
        first = float(self.difficulty)
        second = float(self.difficulty_b) if self.difficulty_b is not None else first
        return first, second

    @property
    def has_key(self) -> bool:
        """Javob kaliti kiritilganmi."""
        if self.kind == self.Kind.OPEN:
            if self.parts >= 2:
                return bool(self.answer_a.strip()) and bool(self.answer_b.strip())
            return bool(self.answer_a.strip())
        return bool(self.correct_set)

    def label(self) -> str:
        """Botda ko'rsatiladigan qisqa sarlavha."""
        return f"{self.order}-savol"
