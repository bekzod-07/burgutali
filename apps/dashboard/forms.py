"""Boshqaruv paneli formalari."""

from __future__ import annotations

from django import forms

from apps.exams import keys as key_parser
from apps.exams.models import Exam, Question
from core import constants as C


class ExamSettingsForm(forms.ModelForm):
    """Test sozlamalarini tahrirlash."""

    class Meta:
        model = Exam
        fields = [
            "title", "description", "status",
            "starts_at", "ends_at", "duration_minutes", "is_public",
            "show_results_to_participants", "show_correct_answers",
            "show_rating_to_participants",
            "max_ball", "theta_min", "theta_max", "auto_calibrate",
            "certificate_enabled", "certificate_scope", "certificate_min_percent",
            "certificate_min_ball", "certificate_min_grade", "organizer_name",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 3}),
            "status": forms.Select(attrs={"class": "input"}),
            "starts_at": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "duration_minutes": forms.NumberInput(attrs={"class": "input", "min": 0}),
            "max_ball": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "theta_min": forms.NumberInput(attrs={"class": "input", "step": "0.1"}),
            "theta_max": forms.NumberInput(attrs={"class": "input", "step": "0.1"}),
            "certificate_scope": forms.Select(attrs={"class": "input"}),
            "certificate_min_percent": forms.NumberInput(
                attrs={"class": "input", "step": "0.1", "min": 0, "max": 100}
            ),
            "certificate_min_ball": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "certificate_min_grade": forms.Select(attrs={"class": "input"}),
            "organizer_name": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificate_min_grade"].widget = forms.Select(
            attrs={"class": "input"},
            choices=[("", "— tanlanmagan —")] + [(g, g) for g in C.GRADE_ORDER[1:]],
        )
        self.fields["certificate_min_grade"].required = False
        self.fields["certificate_min_percent"].required = False
        for name in ("starts_at", "ends_at"):
            self.fields[name].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

    def clean(self):
        data = super().clean()
        theta_min = data.get("theta_min")
        theta_max = data.get("theta_max")
        if theta_min is not None and theta_max is not None and theta_min >= theta_max:
            self.add_error("theta_max", "theta yuqori chegarasi quyi chegaradan katta bo'lishi kerak.")
        starts_at = data.get("starts_at")
        ends_at = data.get("ends_at")
        if starts_at and ends_at and starts_at >= ends_at:
            self.add_error("ends_at", "Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak.")
        return data


class QuestionForm(forms.ModelForm):
    """Bitta savolni tahrirlash."""

    class Meta:
        model = Question
        fields = [
            "text", "section", "kind", "choices_count", "correct_key",
            "answer_a", "answer_b", "parts", "difficulty", "difficulty_b",
            "difficulty_locked", "numeric_tolerance", "is_active",
        ]
        widgets = {
            "text": forms.Textarea(attrs={"class": "input", "rows": 3}),
            "section": forms.TextInput(attrs={"class": "input"}),
            "kind": forms.Select(attrs={"class": "input"}),
            "choices_count": forms.NumberInput(attrs={"class": "input", "min": 2, "max": 6}),
            "parts": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 2}),
            "correct_key": forms.TextInput(attrs={"class": "input"}),
            "answer_a": forms.TextInput(attrs={"class": "input", "data-mathpad": "one"}),
            "answer_b": forms.TextInput(attrs={"class": "input", "data-mathpad": "one"}),
            "numeric_tolerance": forms.NumberInput(
                attrs={"class": "input", "step": "0.000001"}
            ),
            "difficulty": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "difficulty_b": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
        }
        labels = {
            "text": "Savol matni (ixtiyoriy)",
            "section": "Bo'lim nomi",
            "kind": "Savol turi",
            "choices_count": "Variantlar soni",
            "parts": "Ballanadigan qismlar (1 yoki 2)",
            "correct_key": "To'g'ri javob (bitta harf: A–F)",
            "answer_a": "a) javob",
            "answer_b": "b) javob",
            "numeric_tolerance": "Sonli xatolik chegarasi",
            "difficulty": "Qiyinlik b (1-qism)",
            "difficulty_b": "Qiyinlik b (2-qism)",
            "difficulty_locked": "Qiyinlik qulflangan (kalibrlashda o'zgarmasin)",
            "is_active": "Savol faol",
        }


class CodeGenerationForm(forms.Form):
    """ID kodlar yaratish formasi."""

    quantity = forms.IntegerField(
        label="Nechta ID kod yaratilsin?",
        min_value=1,
        max_value=C.CODE_BATCH_MAX,
        initial=1000,
        widget=forms.NumberInput(attrs={"class": "input", "step": 1}),
    )
    note = forms.CharField(
        label="Izoh",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "ixtiyoriy"}),
    )


class ExamCreateForm(forms.Form):
    """
    Yangi test yaratish formasi.

    Test turi, tuzilmasi, javob kalitlari va asosiy sozlamalar bir sahifada
    to'ldiriladi — shundan so'ng test darhol faollashtiriladi (pullik testdan
    tashqari: unda avval ID kodlar yaratilishi kerak).
    """

    STRUCTURE_CHOICES = [
        ("custom", "Savollar sonini o'zim belgilayman"),
        ("national", "Milliy sertifikat shabloni (45 ta savol)"),
    ]

    DURATION_CHOICES = [
        (0, "Cheklovsiz"),
        (1, "1 soat"),
        (3, "3 soat"),
        (24, "24 soat"),
        (72, "3 kun"),
        (168, "7 kun"),
    ]

    title = forms.CharField(
        label="Test nomi",
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "MILLIY SERTIFIKAT MOCK №7"}
        ),
    )
    exam_type = forms.ChoiceField(
        label="Test turi",
        choices=Exam.Type.choices,
        initial=Exam.Type.SIMPLE,
        widget=forms.Select(attrs={"class": "input"}),
    )
    structure = forms.ChoiceField(
        label="Tuzilma",
        choices=STRUCTURE_CHOICES,
        initial="custom",
        widget=forms.Select(attrs={"class": "input"}),
    )
    question_count = forms.IntegerField(
        label="Savollar soni",
        min_value=1,
        max_value=500,
        initial=20,
        required=False,
        widget=forms.NumberInput(attrs={"class": "input"}),
    )
    duration_hours = forms.TypedChoiceField(
        label="Tugash vaqti",
        choices=DURATION_CHOICES,
        coerce=int,
        initial=0,
        widget=forms.Select(attrs={"class": "input"}),
    )
    description = forms.CharField(
        label="Tavsif",
        required=False,
        widget=forms.Textarea(attrs={"class": "input", "rows": 2}),
    )

    single_keys = forms.CharField(
        label="Bitta javobli savollar kaliti (A–D)",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "input", "rows": 3, "placeholder": "ABCDABCD... yoki 1-A 2-B 3-C"}
        ),
    )
    multi_keys = forms.CharField(
        label="Moslashtirish savollari kaliti (A–F)",
        required=False,
        widget=forms.Textarea(attrs={"class": "input", "rows": 2, "placeholder": "A, C, E"}),
    )
    open_keys = forms.CharField(
        label="Ochiq javoblar kaliti (a ; b)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 6,
                "placeholder": "12 ; 3/4\nsqrt(2) ; pi/6",
                # Maydonga bosilganda matematik klaviatura ochiladi.
                "data-mathpad": "lines",
            }
        ),
    )

    show_results = forms.BooleanField(
        label="Natija qatnashchilarga ko'rinsin", required=False, initial=True
    )
    certificate = forms.BooleanField(
        label="Sertifikat berilsin (faqat pullik test)", required=False
    )
    activate = forms.BooleanField(
        label="Yaratilgach darhol faollashtirilsin", required=False, initial=True
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None and not user.is_superuser:
            self.fields["exam_type"].choices = [
                (value, label)
                for value, label in Exam.Type.choices
                if value != Exam.Type.RASCH_PAID
            ]

    # ------------------------------------------------------------------
    def clean(self):
        data = super().clean()
        exam_type = data.get("exam_type")
        structure = data.get("structure")

        national = structure == "national" and exam_type != Exam.Type.SIMPLE
        data["is_national"] = national

        if national:
            data["question_count"] = C.NATIONAL_TOTAL_QUESTIONS
            single_count = C.NATIONAL_SINGLE_RANGE[1] - C.NATIONAL_SINGLE_RANGE[0] + 1
            multi_count = C.NATIONAL_MULTI_RANGE[1] - C.NATIONAL_MULTI_RANGE[0] + 1
            open_count = C.NATIONAL_OPEN_RANGE[1] - C.NATIONAL_OPEN_RANGE[0] + 1
        else:
            count = data.get("question_count")
            if not count:
                self.add_error("question_count", "Savollar sonini kiriting.")
                return data
            single_count, multi_count, open_count = count, 0, 0

        # --- Javob kalitlarini tekshiramiz ---
        if single_count:
            parsed = key_parser.parse_single_key(data.get("single_keys", ""), single_count)
            if not parsed.ok:
                self.add_error("single_keys", " ".join(parsed.errors[:5]))
            data["parsed_single"] = parsed.keys
        if multi_count:
            parsed = key_parser.parse_multi_key(data.get("multi_keys", ""), multi_count)
            if not parsed.ok:
                self.add_error("multi_keys", " ".join(parsed.errors[:5]))
            data["parsed_multi"] = parsed.keys
        if open_count:
            parsed = key_parser.parse_open_key(data.get("open_keys", ""), open_count)
            if not parsed.ok:
                self.add_error("open_keys", " ".join(parsed.errors[:5]))
            data["parsed_open"] = parsed.keys

        return data


class ExamDeleteForm(forms.Form):
    """Testni o'chirishni tasdiqlash."""

    confirm_code = forms.CharField(
        label="Tasdiqlash uchun test kodini kiriting",
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "32", "autocomplete": "off"}),
    )

    def __init__(self, *args, exam=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.exam = exam

    def clean_confirm_code(self):
        value = (self.cleaned_data.get("confirm_code") or "").strip().upper()
        if self.exam is not None and value != self.exam.code.upper():
            raise forms.ValidationError(
                "Kod mos kelmadi. O'chirish uchun test kodini aynan kiriting."
            )
        return value


class KeyImportForm(forms.Form):
    """Javob kalitlarini matn ko'rinishida import qilish."""

    single_keys = forms.CharField(
        label="Bitta javobli savollar kaliti (A–D)",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "input", "rows": 3, "placeholder": "ABCDABCD... yoki 1-A 2-B ..."}
        ),
    )
    multi_keys = forms.CharField(
        label="Moslashtirish savollari kaliti (A–F)",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "input", "rows": 2, "placeholder": "A, C, E"}
        ),
    )
    open_keys = forms.CharField(
        label="Ochiq javoblar kaliti (har bir qatorda: a ; b)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 5,
                "placeholder": "12 ; 3/4\nsqrt(2) ; pi/6",
                "data-mathpad": "lines",
            }
        ),
    )
