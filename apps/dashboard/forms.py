"""Boshqaruv paneli formalari."""

from __future__ import annotations

from django import forms

from apps.broadcasts import formatting as tg_format
from apps.broadcasts.models import Broadcast
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
            "max_ball", "theta_min", "theta_max", "auto_calibrate", "anchor_scale",
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
            "difficulty_locked", "is_active",
        ]
        widgets = {
            "text": forms.Textarea(attrs={"class": "input", "rows": 3}),
            "section": forms.TextInput(attrs={"class": "input"}),
            "kind": forms.Select(attrs={"class": "input"}),
            "choices_count": forms.NumberInput(attrs={"class": "input", "min": 2, "max": 6}),
            "parts": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 2}),
            "correct_key": forms.TextInput(attrs={"class": "input"}),
            # Ochiq javob maydonlari varaqadagidek ko'rinadi; javob matn
            # sifatida tekshiriladi (`dashboard/js/keysheet.js`).
            "answer_a": forms.TextInput(
                attrs={"placeholder": "masalan: osmon, samo, fazo",
                       "autocapitalize": "off",
                       "data-ks-check": "a) to‘g‘ri javob"}
            ),
            "answer_b": forms.TextInput(
                attrs={"placeholder": "masalan: fe’l, harakat",
                       "autocapitalize": "off",
                       "data-ks-check": "b) to‘g‘ri javob"}
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
            "correct_key": "To'g'ri javob",
            "answer_a": "a) javob",
            "answer_b": "b) javob",
            "difficulty": "Qiyinlik b (1-qism)",
            "difficulty_b": "Qiyinlik b (2-qism)",
            "difficulty_locked": "Qiyinlik qulflangan (kalibrlashda o'zgarmasin)",
            "is_active": "Savol faol",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        question = self.instance

        # Harfli kalit matn maydoni emas, varaqadagidek tugmalar bilan
        # tanlanadi (`dashboard/js/keysheet.js`). Maydonning o'zi formada
        # yashirin qoladi, shuning uchun server tomoni o'zgarmaydi.
        letters = "".join(question.choice_letters) if question and question.pk else ""
        if letters:
            self.fields["correct_key"].widget.attrs.update({
                "data-letters": letters,
                "data-kind": question.kind,
            })


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
        label="Ochiq javoblar kaliti (a | b)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 6,
                "placeholder": "osmon, samo, fazo | fe’l, harakat\nsifat, belgi | son",
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

    @property
    def key_errors(self) -> bool:
        """Javob kalitlari maydonlarida xato bormi.

        Xato bo'lsa sahifa «Matn ko'rinishida» rejimida ochiladi — foydalanuvchi
        xato xabarini va o'zi kiritgan matnni ko'rib turadi.
        """
        return any(
            self[name].errors for name in ("single_keys", "multi_keys", "open_keys")
        )

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
            # 36–39 bitta javobdan, 40–45 esa a) va b) dan iborat.
            parsed = key_parser.parse_open_key(
                data.get("open_keys", ""), open_count, C.national_open_parts()
            )
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
        label="Ochiq javoblar kaliti (har bir qatorda: a | b)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 5,
                "placeholder": "osmon, samo, fazo | fe’l, harakat\nsifat, belgi | son",
            }
        ),
    )


class BroadcastForm(forms.ModelForm):
    """
    Reklama xabarini tayyorlash: matn, rasm va tugmalar.

    Matn Telegram HTML uslubida bo'ladi (`<b>`, `<i>`, `<a href>`), lekin
    ruxsatsiz teglar avtomatik ekranlanadi — yuborishda «can't parse
    entities» xatosi chiqmaydi. Tugmalar har bir qatorda
    «Matn | https://havola» ko'rinishida yoziladi.
    """

    #: Rasm hajmi chegarasi (Telegram 10 MB gacha qabul qiladi).
    MAX_IMAGE_BYTES: int = 8 * 1024 * 1024

    buttons_raw = forms.CharField(
        label="Tugmalar",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 4,
                "placeholder": (
                    "Kanalga o'tish | https://t.me/Oybek_ustoz_MS\n"
                    "Sayt | https://burgutali.uz || Bot | https://t.me/bot"
                ),
            }
        ),
        help_text=(
            "Har bir qator — bitta tugma qatori. Bitta qatorga ikki tugma "
            "qo'yish uchun ularni «||» bilan ajrating."
        ),
    )
    remove_image = forms.BooleanField(label="Rasmni olib tashlash", required=False)

    class Meta:
        model = Broadcast
        fields = ["title", "text", "image", "audience", "exam"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "input", "placeholder": "Masalan: Yangi mock test e'loni"}
            ),
            "text": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 8,
                    "placeholder": "Xabar matni. Qalin uchun <b>matn</b>, qiya uchun <i>matn</i>.",
                }
            ),
            "audience": forms.Select(attrs={"class": "input"}),
            "exam": forms.Select(attrs={"class": "input"}),
        }
        labels = {
            "title": "Sarlavha (faqat panelda ko'rinadi)",
            "text": "Xabar matni",
            "image": "Rasm (ixtiyoriy)",
            "audience": "Kimga yuborilsin",
            "exam": "Test (faqat «test ishtirokchilari» uchun)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["text"].required = False
        self.fields["exam"].required = False
        self.fields["exam"].queryset = Exam.objects.order_by("-created_at")
        self.fields["exam"].empty_label = "— tanlanmagan —"
        # Standart `ClearableFileInput` inglizcha «Currently / Change / Clear»
        # yozuvlarini chiqaradi — panel esa butunlay o'zbekcha. Shuning uchun
        # oddiy fayl maydoni ishlatiladi, rasmni olib tashlash uchun esa
        # quyidagi `remove_image` katagi bor.
        self.fields["image"].widget = forms.FileInput(
            attrs={"class": "input", "accept": "image/*"}
        )
        if self.instance and self.instance.pk:
            self.fields["buttons_raw"].initial = tg_format.buttons_to_text(
                self.instance.button_rows
            )
        if not (self.instance and self.instance.pk and self.instance.has_image):
            self.fields.pop("remove_image", None)

    # ------------------------------------------------------------------
    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image or not hasattr(image, "size"):
            return image
        if image.size > self.MAX_IMAGE_BYTES:
            raise forms.ValidationError(
                f"Rasm hajmi {self.MAX_IMAGE_BYTES // (1024 * 1024)} MB dan oshmasligi kerak."
            )
        # Django yangi yuklangan faylga tekshirilgan `PIL.Image` ni biriktiradi.
        opened = getattr(image, "image", None)
        if opened is not None and opened.width + opened.height > 10000:
            raise forms.ValidationError(
                "Rasm juda katta: eni va bo'yi yig'indisi 10000 nuqtadan oshmasin."
            )
        return image

    def clean_buttons_raw(self):
        raw = self.cleaned_data.get("buttons_raw", "")
        try:
            self._button_rows = tg_format.parse_buttons(raw)
        except tg_format.FormatError as error:
            raise forms.ValidationError(str(error)) from error
        return raw

    def clean(self):
        data = super().clean()

        # --- Matn: ruxsat etilgan teglargina qoladi ---
        text_html = ""
        if not self.has_error("text"):
            try:
                text_html = tg_format.sanitize_html(data.get("text", ""))
            except tg_format.FormatError as error:
                self.add_error("text", str(error))
        self._text_html = text_html

        # --- Rasm bormi (yangi yuklangan yoki avval saqlangan) ---
        has_image = bool(data.get("image"))
        if not has_image and self.instance and self.instance.pk:
            has_image = self.instance.has_image and not data.get("remove_image")

        if not text_html.strip() and not has_image:
            self.add_error(
                "text", "Xabar bo'sh bo'lmasligi kerak: matn yoki rasm qo'shing."
            )

        limit = tg_format.CAPTION_LIMIT if has_image else tg_format.TEXT_LIMIT
        length = tg_format.visible_length(text_html)
        if length > limit:
            where = "rasm izohi" if has_image else "xabar"
            self.add_error(
                "text",
                f"Matn juda uzun: {length} belgi. Telegram {where}i uchun "
                f"chegara — {limit} belgi.",
            )

        # --- Test ishtirokchilari tanlansa, test ko'rsatilishi shart ---
        if data.get("audience") == Broadcast.Audience.EXAM and not data.get("exam"):
            self.add_error("exam", "Auditoriya sifatida test tanlangan — testni ko'rsating.")

        return data

    # ------------------------------------------------------------------
    def save(self, commit: bool = True) -> Broadcast:
        broadcast = super().save(commit=False)
        # Bazada tozalangan HTML saqlanadi — bot aynan shu matnni yuboradi,
        # panel ko'rinishi esa yuboriladigan xabar bilan bir xil bo'ladi.
        broadcast.text = getattr(self, "_text_html", broadcast.text)
        broadcast.buttons = getattr(self, "_button_rows", [])
        if self.cleaned_data.get("remove_image"):
            broadcast.image = None
            broadcast.image_file_id = ""
        elif self.cleaned_data.get("image"):
            # Yangi rasm — eski `file_id` endi mos kelmaydi.
            broadcast.image_file_id = ""
        if broadcast.audience != Broadcast.Audience.EXAM:
            broadcast.exam = None
        if commit:
            broadcast.save()
        return broadcast
