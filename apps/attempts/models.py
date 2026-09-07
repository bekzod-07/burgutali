"""
Test topshirish (urinish) va javoblar modellari.

Muhim qoida (TZ): ID kod faqat yakuniy javoblar bazaga muvaffaqiyatli
saqlangandan keyin "Ishlatilgan" holatiga o'tadi. Shuning uchun urinish
avval DRAFT holatida bo'ladi va faqat `submit` bosqichida SUBMITTED bo'ladi.
"""

from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.functions import Coalesce
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
        Reyting tartibida (yakuniy ball -> to'g'ri javob -> topshirish vaqti).

        Tartib `final_ball` bo'yicha: esse yoqilgan testda u test balli va
        esse ballining o'rtachasi, aks holda test ballining o'zi.
        `final_ball` hali hisoblanmagan eski yozuvlar uchun `ball` ga
        tushiladi.
        """
        return self.annotate(
            _rank_ball=Coalesce("final_ball", "ball")
        ).order_by("-_rank_ball", "-raw_score", "submitted_at")


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
    ball = models.FloatField("Test balli", null=True, blank=True, db_index=True)

    # --- Esse (yozma qism) ---
    #: Esse balli — admin panelda qo'lda kiritiladi (`Exam.essay_max_ball`
    #: shkalasida). Kiritilmagan bo'lsa `None`.
    essay_ball = models.FloatField("Esse balli", null=True, blank=True)
    #: Yakuniy ball: esse yoqilgan va kiritilgan bo'lsa
    #: `(test balli + esse balli) / 2`, aks holda test ballining o'zi.
    #: Daraja, reyting va sertifikat aynan shu ball bo'yicha aniqlanadi.
    final_ball = models.FloatField(
        "Yakuniy ball", null=True, blank=True, db_index=True
    )

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
            models.Index(fields=["exam", "-final_ball"]),
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
    def result_ball(self) -> float | None:
        """
        Natija sifatida qaraladigan ball.

        Esse yoqilgan testda bu `(test balli + esse balli) / 2`, aks holda
        test ballining o'zi. Daraja, reyting, sertifikat va barcha
        ko'rsatkichlar shu qiymatga tayanadi.
        """
        return self.final_ball if self.final_ball is not None else self.ball

    @property
    def display_ball(self) -> str:
        """Yakuniy ballning matnli ko'rinishi."""
        value = self.result_ball
        if value is None:
            return "—"
        return f"{value:.2f}"

    @property
    def display_test_ball(self) -> str:
        """Faqat test qismidan olingan ball (esse hisobga olinmagan)."""
        if self.ball is None:
            return "—"
        return f"{self.ball:.2f}"

    @property
    def display_essay_ball(self) -> str:
        """Esse balli (kiritilmagan bo'lsa «—»)."""
        if self.essay_ball is None:
            return "—"
        return f"{self.essay_ball:.2f}"

    @property
    def essay_pending(self) -> bool:
        """Esse yoqilgan, lekin balli hali kiritilmaganmi."""
        return bool(self.exam.essay_enabled) and self.essay_ball is None

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
        Umumiy natijalarda ko'rsatiladigan nom.

        Talab: 1- va 2-turda ism-familiya, 3-turda (pullik RASH testi) esa
        ishtirokchining ID raqami e'lon qilinadi. Sertifikatga esa doim
        ism-familiya yoziladi.
        """
        if self.exam.exam_type == self.exam.Type.RASCH_PAID:
            return self.access_code_value or f"ID-{self.id}"
        return self.full_name or (self.user.display_name if self.user_id else "Ishtirokchi")

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
        # `essay_ball` ataylab tozalanmaydi — u qo'lda kiritilgan ma'lumot.
        self.final_ball = None
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


class PhantomParticipant(TimeStampedModel):
    """
    E'lon uchun qo'shiladigan **soxta** qatnashchi qatori.

    Natijalar e'lon qilinayotganda administrator ro'yxatga qo'shimcha
    qatorlar qo'shishi mumkin: tasodifiy ism-familiya va real natijalar
    orasiga tabiiy joylashadigan ball.

    Bu qatorlar **hech qanday haqiqiy ma'lumot emas** va shu sababli
    qat'iy chegaralangan:

      * ular faqat e'lon qilinadigan ro'yxatda (umumiy natijalar PDF si,
        ilova va botdagi reyting) ko'rinadi;
      * statistikaga, Rasch kalibrlashiga va qatnashchilar soniga
        **kirmaydi** — barcha ilmiy hisob-kitob faqat haqiqiy urinishlar
        ustida bajariladi;
      * ularga sertifikat **berilmaydi** (sertifikat `Attempt` ga
        bog'langan, soxta qatorda esa urinish yo'q);
      * boshqaruv panelida alohida belgi bilan ko'rsatiladi, shunda admin
        ularni haqiqiy natijadan doim ajrata oladi.

    Test qayta e'lon qilinsa, avvalgi qatorlar o'chib, yangisi yaratiladi.
    """

    exam = models.ForeignKey(
        "exams.Exam", on_delete=models.CASCADE, related_name="phantoms",
        verbose_name="Test",
    )
    full_name = models.CharField("Ism va familiya", max_length=120)
    raw_score = models.FloatField("Xom ball", default=0.0)
    max_raw_score = models.FloatField("Maksimal xom ball", default=0.0)
    percent = models.FloatField("Foiz", default=0.0)
    ball = models.FloatField("Yakuniy ball", null=True, blank=True)
    grade = models.CharField("Daraja", max_length=16, blank=True, default="")

    class Meta:
        verbose_name = "Soxta qatnashchi (e'lon uchun)"
        verbose_name_plural = "Soxta qatnashchilar (e'lon uchun)"
        ordering = ("-ball", "-raw_score", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "full_name"], name="uniq_phantom_name_per_exam"
            ),
        ]
        indexes = [models.Index(fields=["exam", "-ball"])]

    def __str__(self) -> str:
        return f"{self.full_name} (soxta)"

    # ------------------------------------------------------------------
    @property
    def public_label(self) -> str:
        """E'lon qilinadigan ro'yxatdagi nom."""
        return self.full_name

    @property
    def display_ball(self) -> str:
        if self.ball is None:
            return "—"
        return f"{self.ball:.2f}"
