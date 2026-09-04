"""
Boshqaruv paneli view lari (SRS 9-bo'lim: administrator paneli).

Imkoniyatlar:
  * test va savollarni boshqarish;
  * javob kalitlarini kiritish;
  * Rasch parametrlarini tahrirlash;
  * natijalarni Excel/PDF eksport qilish;
  * ishtirokchilar statistikasini ko'rish;
  * ID kodlarni boshqarish va Excel ko'rinishida yuklab olish.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accesscodes.models import AccessCode, CodeBatch
from apps.accesscodes.services import code_statistics, create_codes
from apps.attempts import services as attempt_services
from apps.attempts.models import Attempt
from apps.broadcasts import formatting as tg_format
from apps.broadcasts import services as broadcast_services
from apps.broadcasts.models import Broadcast, BroadcastDelivery
from apps.certificates.models import Certificate
from apps.certificates.services import issue_certificate, issue_for_exam
from apps.common.mixins import staff_required
from apps.exams import keys as key_parser
from apps.exams import services as exam_services
from apps.exams.models import Exam, Question
from apps.exports import charts
from apps.exports import excel as excel_export
from apps.exports import pdf_report
from apps.rasch.services import calculate_exam, score_attempt_preliminary
from apps.users import services as user_services
from apps.users.models import BotUser, UserAction
from apps.users.services import user_statistics
from core import constants as C

from .forms import (
    BroadcastForm,
    CodeGenerationForm,
    ExamCreateForm,
    ExamDeleteForm,
    ExamSettingsForm,
    KeyImportForm,
    QuestionForm,
)

logger = logging.getLogger(__name__)


# ==========================================================================
#  Autentifikatsiya
# ==========================================================================


class LoginView(DjangoLoginView):
    """
    Panelga kirish sahifasi.

    Brute-force himoyasi: bitta IP dan 10 ta muvaffaqiyatsiz urinishdan
    so'ng kirish 10 daqiqaga vaqtincha yopiladi.
    """

    template_name = "dashboard/login.html"
    redirect_authenticated_user = True

    MAX_FAILURES = 10
    LOCKOUT_SECONDS = 600

    @staticmethod
    def _client_ip(request) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "") or "nomalum"

    def post(self, request, *args, **kwargs):
        from django.core.cache import cache

        key = f"panel-login-fail:{self._client_ip(request)}"
        if int(cache.get(key) or 0) >= self.MAX_FAILURES:
            messages.error(
                request,
                "Juda ko'p muvaffaqiyatsiz urinish. 10 daqiqadan so'ng qayta urinib ko'ring.",
            )
            return redirect("dashboard:login")

        response = super().post(request, *args, **kwargs)
        if response.status_code == 302:  # muvaffaqiyatli kirish
            cache.delete(key)
        else:
            cache.set(key, int(cache.get(key) or 0) + 1, self.LOCKOUT_SECONDS)
        return response


def logout_view(request):
    """Tizimdan chiqish."""
    logout(request)
    messages.info(request, "Tizimdan chiqdingiz.")
    return redirect("dashboard:login")


# ==========================================================================
#  Bosh sahifa
# ==========================================================================


@staff_required
def index(request):
    """Umumiy ko'rsatkichlar."""
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    exams = Exam.objects.all()
    context = {
        "section": "index",
        "users": user_statistics(),
        "exam_total": exams.count(),
        "exam_active": exams.filter(status=Exam.Status.ACTIVE).count(),
        "exam_published": exams.filter(status=Exam.Status.PUBLISHED).count(),
        "attempts_total": Attempt.objects.filter(status=Attempt.Status.SUBMITTED).count(),
        "attempts_today": Attempt.objects.filter(
            status=Attempt.Status.SUBMITTED, submitted_at__gte=today
        ).count(),
        "certificates": Certificate.objects.count(),
        "codes": {
            "total": AccessCode.objects.count(),
            "used": AccessCode.objects.filter(status=AccessCode.Status.USED).count(),
            "unused": AccessCode.objects.filter(status=AccessCode.Status.UNUSED).count(),
        },
        "recent_exams": exams.select_related("owner").order_by("-created_at")[:8],
        "recent_attempts": (
            Attempt.objects.filter(status=Attempt.Status.SUBMITTED)
            .select_related("exam", "user")
            .order_by("-submitted_at")[:10]
        ),
        "type_breakdown": [
            {
                "label": label,
                "count": exams.filter(exam_type=value).count(),
                "value": value,
            }
            for value, label in Exam.Type.choices
        ],
    }
    return render(request, "dashboard/index.html", context)


# ==========================================================================
#  Testlar
# ==========================================================================


#: Eskirgan testlarni tozalash shu oraliqda bir marta ishlaydi (sekund).
_PURGE_THROTTLE_SECONDS = 300


def _purge_stale_exams() -> None:
    """
    Faol bo'lmagan eskirgan testlarni tozalaydi.

    Asosiy tozalash bot fon vazifasida ketadi (`bot/tasks/scheduler.py`),
    lekin bot o'chirilgan bo'lsa ham panel ro'yxati toza qolishi kerak.
    Shuning uchun ro'yxat ochilganda ham tekshiriladi — ortiqcha yuk
    bo'lmasligi uchun besh daqiqada bir marta.
    """
    from django.core.cache import cache

    if not cache.add("dashboard-exam-purge", "1", _PURGE_THROTTLE_SECONDS):
        return
    try:
        exam_services.auto_purge_finished()
    except Exception:  # pragma: no cover - tozalash sahifani buzmasin
        logger.exception("Eskirgan testlarni tozalashda xato")


@staff_required
def exam_list(request):
    """Testlar ro'yxati."""
    _purge_stale_exams()

    queryset = (
        Exam.objects.select_related("owner")
        .annotate(
            participants=Count(
                "attempts", filter=Q(attempts__status="submitted"), distinct=True
            )
        )
        .order_by("-created_at")
    )

    exam_type = request.GET.get("turi", "")
    status = request.GET.get("holati", "")
    search = (request.GET.get("q") or "").strip()

    if exam_type:
        queryset = queryset.filter(exam_type=exam_type)
    # Holat ikkitagina: faol test va tugatilgan test. Eski bazadagi
    # «yopilgan», «hisoblangan» va «arxivlangan» yozuvlar ham tugatilgan
    # hisoblanadi — ular baribir 24 soat ichida o'chib ketadi.
    if status == Exam.Status.ACTIVE:
        queryset = queryset.filter(status=Exam.Status.ACTIVE)
    elif status:
        queryset = queryset.exclude(status=Exam.Status.ACTIVE)
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(code__icontains=search))

    context = {
        "section": "exams",
        "exams": queryset[:200],
        "type_choices": Exam.Type.choices,
        # Test yaratilishi bilan faollashadi, tugatilgach esa 24 soatdan
        # keyin o'chadi — shuning uchun ro'yxatda ikki holatgina uchraydi.
        "status_choices": [
            (Exam.Status.ACTIVE, "Faol"),
            (Exam.Status.PUBLISHED, "Tugatilgan"),
        ],
        "selected_type": exam_type,
        "selected_status": status,
        "search": search,
    }
    return render(request, "dashboard/exam_list.html", context)


@staff_required
def exam_create(request):
    """Yangi test yaratish."""
    form = ExamCreateForm(user=request.user)

    if request.method == "POST":
        form = ExamCreateForm(request.POST, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            owner = _dashboard_owner(request)

            hours = int(data.get("duration_hours") or 0)
            ends_at = timezone.now() + timedelta(hours=hours) if hours else None

            exam = exam_services.create_exam(
                owner=owner,
                title=data["title"],
                exam_type=data["exam_type"],
                question_count=int(data.get("question_count") or 0),
                national_template=bool(data.get("is_national")),
                description=data.get("description", ""),
                duration_minutes=hours * 60,
                ends_at=ends_at,
                show_results=bool(data.get("show_results")),
                show_correct_answers=bool(data.get("show_results")),
                certificate_enabled=bool(data.get("certificate"))
                and data["exam_type"] == Exam.Type.RASCH_PAID,
                organizer_name=owner.full_name or "",
            )

            if data.get("parsed_single"):
                exam_services.apply_single_keys(exam, data["parsed_single"])
            if data.get("parsed_multi"):
                exam_services.apply_multi_keys(exam, data["parsed_multi"])
            if data.get("parsed_open"):
                exam_services.apply_open_keys(exam, data["parsed_open"])

            messages.success(request, f"«{exam.title}» testi yaratildi (kod: {exam.code}).")

            # Test yaratilishi bilan faollashadi — qo'lda faollashtirish yo'q.
            ok, message = exam_services.activate_exam(exam)
            messages.success(request, message) if ok else messages.warning(request, message)

            return redirect("dashboard:exam_detail", pk=exam.pk)
        messages.error(request, "Formada xatolar bor — quyida ko'rsatilgan.")

    return render(
        request,
        "dashboard/exam_create.html",
        {"section": "exams", "form": form, "national_total": C.NATIONAL_TOTAL_QUESTIONS},
    )


def _dashboard_owner(request):
    """
    Web paneldan yaratilgan testning egasini aniqlaydi.

    Panel Django foydalanuvchisi bilan ishlaydi, testlar esa Telegram
    foydalanuvchisiga (`BotUser`) bog'lanadi. Bog'lanish quyidagicha:

      * Telegram orqali kirilgan bo'lsa, hisob nomi `tg_<telegram_id>` —
        o'sha `BotUser` egasi bo'ladi;
      * login-parol bilan kirilgan bo'lsa, shu Django hisobi uchun
        alohida `BotUser` yaratiladi. Uning `telegram_id` si manfiy,
        chunki haqiqiy Telegram ID lari doim musbat — to'qnashmaydi.

    Ilgari bu yerda **birinchi admin** qaytarilardi, shuning uchun
    paneldan yaratilgan har bir testda kim yaratganidan qat'i nazar
    o'sha odamning ismi «Yaratuvchi» bo'lib chiqardi.
    """
    account = getattr(request, "user", None)
    if account is None or not account.is_authenticated:
        return _panel_service_owner()

    # --- Telegram orqali kirgan admin ---
    username = account.get_username()
    if username.startswith("tg_"):
        raw = username[3:]
        if raw.lstrip("-").isdigit():
            owner = BotUser.objects.filter(telegram_id=int(raw)).first()
            if owner is not None:
                return owner

    # --- Login-parol bilan kirgan hisob ---
    display = (account.get_full_name() or "").strip() or username
    owner, created = BotUser.objects.get_or_create(
        telegram_id=-int(account.pk),
        defaults={
            "full_name": display[:120],
            "is_registered": True,
            "is_admin": True,
        },
    )
    if not created and owner.full_name != display[:120]:
        owner.full_name = display[:120]
        owner.save(update_fields=["full_name", "updated_at"])
    return owner


def _panel_service_owner():
    """Hisob aniqlanmagan holat uchun zaxira «Web panel» egasi."""
    owner, _ = BotUser.objects.get_or_create(
        telegram_id=0,
        defaults={
            "full_name": "Web panel",
            "is_registered": True,
            "is_admin": True,
        },
    )
    return owner


@staff_required
def exam_delete(request, pk: int):
    """Testni butunlay o'chirish (tasdiqlash bilan)."""
    exam = get_object_or_404(Exam, pk=pk)
    summary = exam_services.deletion_summary(exam)
    form = ExamDeleteForm(exam=exam)

    if request.method == "POST":
        form = ExamDeleteForm(request.POST, exam=exam)
        if form.is_valid():
            ok, message, _ = exam_services.delete_exam(exam, force=True)
            if ok:
                messages.success(request, message)
                return redirect("dashboard:exam_list")
            messages.error(request, message)

    return render(
        request,
        "dashboard/exam_delete.html",
        {"section": "exams", "exam": exam, "summary": summary, "form": form},
    )


@staff_required
def exam_detail(request, pk: int):
    """Test sozlamalari va boshqaruvi."""
    exam = get_object_or_404(Exam.objects.select_related("owner"), pk=pk)

    settings_form = ExamSettingsForm(instance=exam)
    key_form = KeyImportForm()

    if request.method == "POST":
        action = request.POST.get("form")
        if action == "settings":
            settings_form = ExamSettingsForm(request.POST, instance=exam)
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "Test sozlamalari saqlandi.")
                return redirect("dashboard:exam_detail", pk=exam.pk)
            messages.error(request, "Formada xatolar bor — quyida ko'rsatilgan.")
        elif action == "keys":
            key_form = KeyImportForm(request.POST)
            if key_form.is_valid():
                _apply_keys(request, exam, key_form.cleaned_data)
                return redirect("dashboard:exam_detail", pk=exam.pk)

    context = {
        "section": "exams",
        "exam": exam,
        "form": settings_form,
        "key_form": key_form,
        "summary": exam_services.exam_summary(exam),
        "missing_keys": exam_services.missing_keys(exam),
        "statistics": getattr(exam, "statistics", None),
        "code_stats": code_statistics(exam) if exam.requires_access_code else None,
    }
    return render(request, "dashboard/exam_detail.html", context)


def _apply_keys(request, exam: Exam, data: dict) -> None:
    """Kalitlarni tahlil qilib testga biriktiradi."""
    single_count = exam.questions.filter(kind=Question.Kind.SINGLE, is_active=True).count()
    multi_count = exam.questions.filter(kind=Question.Kind.MULTI, is_active=True).count()
    open_count = exam.questions.filter(kind=Question.Kind.OPEN, is_active=True).count()

    applied = 0
    errors: list[str] = []

    if data.get("single_keys") and single_count:
        result = key_parser.parse_single_key(data["single_keys"], single_count)
        errors.extend(result.errors)
        if result.ok:
            applied += exam_services.apply_single_keys(exam, result.keys)

    if data.get("multi_keys") and multi_count:
        result = key_parser.parse_multi_key(data["multi_keys"], multi_count)
        errors.extend(result.errors)
        if result.ok:
            applied += exam_services.apply_multi_keys(exam, result.keys)

    if data.get("open_keys") and open_count:
        result = key_parser.parse_open_key(data["open_keys"], open_count)
        errors.extend(result.errors)
        if result.ok:
            applied += exam_services.apply_open_keys(exam, result.keys)

    if applied:
        messages.success(request, f"{applied} ta savolga javob kaliti biriktirildi.")
    for error in errors[:12]:
        messages.error(request, error)
    if not applied and not errors:
        messages.warning(request, "Kalit kiritilmadi.")


@staff_required
def exam_questions(request, pk: int):
    """Savollar ro'yxati va tez tahrirlash."""
    exam = get_object_or_404(Exam, pk=pk)

    if request.method == "POST":
        updated = 0
        changed: list[Question] = []
        # Savollar bo'yicha yuramiz, POST kalitlari bo'yicha emas: ochiq
        # savolda ikkita maydon keladi (`key_<id>_a`, `key_<id>_b`), qolganida
        # bitta (`key_<id>`).
        for question in exam.questions.all().order_by("order"):
            if question.kind == Question.Kind.OPEN:
                first = request.POST.get(f"key_{question.id}_a")
                second = request.POST.get(f"key_{question.id}_b")
                if first is None and second is None:
                    continue
                question.answer_a = (first or "").strip()[:255]
                question.answer_b = (second or "").strip()[:255]
                question.parts = 2 if question.answer_b else 1
            else:
                value = request.POST.get(f"key_{question.id}")
                if value is None:
                    continue
                question.correct_key = "".join(
                    sorted({ch.upper() for ch in value if ch.isalpha()})
                )[:8]

            difficulty_raw = request.POST.get(f"diff_{question.id}")
            if difficulty_raw:
                try:
                    question.difficulty = float(difficulty_raw)
                except ValueError:
                    pass
            question.difficulty_locked = bool(request.POST.get(f"lock_{question.id}"))
            changed.append(question)
            updated += 1

        if changed:
            Question.objects.bulk_update(
                changed,
                ["correct_key", "answer_a", "answer_b", "parts",
                 "difficulty", "difficulty_locked", "updated_at"],
                batch_size=200,
            )
            messages.success(request, f"{updated} ta savol yangilandi.")
        return redirect("dashboard:exam_questions", pk=exam.pk)

    context = {
        "section": "exams",
        "exam": exam,
        "questions": exam.questions.order_by("order"),
        "kinds": Question.Kind,
    }
    return render(request, "dashboard/exam_questions.html", context)


@staff_required
def exam_results(request, pk: int):
    """
    Test natijalari va reyting.

    Savollarning qiyinchilik darajasi diagrammasi ham shu yerda ko'rsatiladi —
    sahifa `@staff_required` bilan himoyalangani uchun uni faqat adminlar
    ko'radi (talab: «FAQAT ADMINGA»).
    """
    exam = get_object_or_404(Exam, pk=pk)
    attempts = attempt_services.ranked_attempts(exam)
    summary = charts.build_summary(exam)
    context = {
        "section": "exams",
        "exam": exam,
        "attempts": attempts,
        "statistics": getattr(exam, "statistics", None),
        "certificates": Certificate.objects.filter(exam=exam).count(),
        "charts": summary,
        "difficulty_svg": mark_safe(charts.difficulty_svg(summary.rows)),
        "distribution_svg": mark_safe(charts.distribution_svg(summary.bins)),
    }
    return render(request, "dashboard/exam_results.html", context)


@staff_required
def exam_codes(request, pk: int):
    """ID kodlarni boshqarish."""
    exam = get_object_or_404(Exam, pk=pk)
    form = CodeGenerationForm()

    if request.method == "POST":
        form = CodeGenerationForm(request.POST)
        if form.is_valid():
            batch = create_codes(
                exam,
                form.cleaned_data["quantity"],
                created_by=exam.owner,
                note=form.cleaned_data.get("note", ""),
            )
            messages.success(
                request, f"{batch.quantity} ta ID kod yaratildi (partiya #{batch.id})."
            )
            return redirect("dashboard:exam_codes", pk=exam.pk)

    status_filter = request.GET.get("holati", "")
    codes = AccessCode.objects.filter(exam=exam).select_related("user").order_by("id")
    if status_filter:
        codes = codes.filter(status=status_filter)

    context = {
        "section": "exams",
        "exam": exam,
        "form": form,
        "batches": CodeBatch.objects.filter(exam=exam).order_by("-created_at"),
        "codes": codes[:500],
        "stats": code_statistics(exam),
        "status_choices": AccessCode.Status.choices,
        "selected_status": status_filter,
    }
    return render(request, "dashboard/exam_codes.html", context)


@staff_required
def exam_action(request, pk: int, action: str):
    """
    Test ustidagi amallar.

    Asosiysi — «tugatish»: test yopiladi, natijalar hisoblanadi va darhol
    e'lon qilinadi. Alohida «yopish / hisoblash / e'lon qilish» bosqichlari
    yo'q, chunki test yaratilishi bilan faol bo'ladi va bir bosishda
    yakunlanadi.
    """
    exam = get_object_or_404(Exam, pk=pk)

    if action == "tugatish":
        ok, message = exam_services.finish_exam(exam)
        if ok and exam.can_issue_certificate:
            exam.refresh_from_db()
            result = issue_for_exam(exam)
            message += (
                f" Sertifikatlar: {result['created']} ta yaratildi, "
                f"{result['skipped']} ta o'tkazib yuborildi."
            )
    elif action == "hisoblash":
        report = calculate_exam(exam)
        ok, message = True, (
            f"Hisoblandi: {report.participants} ta qatnashchi, "
            f"ishonchlilik {report.reliability:.3f}."
        )
    elif action == "sertifikatlar":
        if not exam.can_issue_certificate:
            ok, message = False, "Bu testda sertifikat berish yoqilmagan."
        elif exam.status != Exam.Status.PUBLISHED:
            ok, message = False, "Avval testni tugating."
        else:
            result = issue_for_exam(exam)
            ok, message = True, (
                f"{result['created']} ta sertifikat yaratildi, "
                f"{result['skipped']} ta o'tkazib yuborildi."
            )
    else:
        ok, message = False, "Noma'lum amal."

    messages.success(request, message) if ok else messages.error(request, message)
    return redirect(request.META.get("HTTP_REFERER") or f"/panel/testlar/{exam.pk}/")


# ==========================================================================
#  Eksport
# ==========================================================================


def _xlsx_response(payload: bytes, filename: str) -> HttpResponse:
    """Excel faylini javob sifatida qaytaradi."""
    response = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@staff_required
def export_results_excel(request, pk: int):
    """Natijalarni Excel ko'rinishida yuklab berish."""
    exam = get_object_or_404(Exam, pk=pk)
    payload = excel_export.results_workbook(exam)
    return _xlsx_response(payload, excel_export.default_filename("natijalar", exam))


@staff_required
def export_participants_excel(request, pk: int):
    """Ishtirokchilar ro'yxatini Excel ko'rinishida yuklab berish."""
    exam = get_object_or_404(Exam, pk=pk)
    payload = excel_export.participants_workbook(exam)
    return _xlsx_response(payload, excel_export.default_filename("ishtirokchilar", exam))


@staff_required
def export_codes_excel(request, pk: int):
    """ID kodlarni Excel ko'rinishida yuklab berish."""
    batch = get_object_or_404(CodeBatch.objects.select_related("exam"), pk=pk)
    payload = excel_export.codes_workbook(batch)
    return _xlsx_response(
        payload, excel_export.default_filename(f"idkodlar_{batch.id}", batch.exam)
    )


@staff_required
def export_results_pdf(request, pk: int):
    """Natijalar bo'yicha PDF hisobot."""
    exam = get_object_or_404(Exam, pk=pk)
    payload = pdf_report.results_report(exam)
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="natijalar_{exam.code}.pdf"'
    return response


# ==========================================================================
#  Sertifikatlar va foydalanuvchilar
# ==========================================================================


@staff_required
def certificate_list(request):
    """Berilgan sertifikatlar ro'yxati."""
    search = (request.GET.get("q") or "").strip()
    queryset = Certificate.objects.select_related("exam", "user").order_by("-issued_at")
    if search:
        queryset = queryset.filter(
            Q(number__icontains=search)
            | Q(full_name__icontains=search)
            | Q(exam__code__icontains=search)
        )
    return render(
        request,
        "dashboard/certificate_list.html",
        {"section": "certificates", "certificates": queryset[:300], "search": search},
    )


@staff_required
def user_list(request):
    """Foydalanuvchilar ro'yxati."""
    search = (request.GET.get("q") or "").strip()
    queryset = BotUser.objects.order_by("-created_at")
    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(username__icontains=search)
        )
    only = request.GET.get("faqat", "")
    if only == "admin":
        queryset = queryset.filter(is_admin=True)
    elif only == "royxatdan":
        queryset = queryset.filter(is_registered=True)
    elif only == "bloklangan":
        queryset = queryset.filter(is_blocked=True)

    return render(
        request,
        "dashboard/user_list.html",
        {
            "section": "users",
            "users": queryset[:300],
            "search": search,
            "only": only,
            "stats": user_statistics(),
        },
    )


@staff_required
def user_detail(request, pk: int):
    """Foydalanuvchi tafsiloti: natijalari, testlari va amallari."""
    bot_user = get_object_or_404(BotUser, pk=pk)

    attempts = (
        Attempt.objects.filter(user=bot_user, status=Attempt.Status.SUBMITTED)
        .select_related("exam")
        .order_by("-submitted_at")[:50]
    )
    owned = Exam.objects.filter(owner=bot_user).order_by("-created_at")[:50]
    actions = UserAction.objects.filter(user=bot_user).order_by("-created_at")[:50]
    certificates = Certificate.objects.filter(user=bot_user).order_by("-issued_at")[:50]
    codes = AccessCode.objects.filter(user=bot_user).select_related("exam").order_by("-used_at")[:50]

    return render(
        request,
        "dashboard/user_detail.html",
        {
            "section": "users",
            "bot_user": bot_user,
            "attempts": attempts,
            "owned": owned,
            "actions": actions,
            "certificates": certificates,
            "codes": codes,
        },
    )


@staff_required
def user_action(request, pk: int, action: str):
    """Foydalanuvchi ustidagi amallar."""
    bot_user = get_object_or_404(BotUser, pk=pk)

    if action == "bloklash":
        user_services.block_user(bot_user, "Panel orqali bloklandi")
        message = f"{bot_user.display_name} bloklandi."
    elif action == "blokdan-chiqarish":
        user_services.unblock_user(bot_user)
        message = f"{bot_user.display_name} blokdan chiqarildi."
    elif action == "admin":
        bot_user.is_admin = True
        bot_user.save(update_fields=["is_admin", "updated_at"])
        message = f"{bot_user.display_name} adminlar ro'yxatiga qo'shildi."
    elif action == "admin-emas":
        bot_user.is_admin = False
        bot_user.save(update_fields=["is_admin", "updated_at"])
        message = f"{bot_user.display_name} adminlikdan chiqarildi."
    else:
        messages.error(request, "Noma'lum amal.")
        return redirect("dashboard:user_detail", pk=pk)

    messages.success(request, message)
    return redirect("dashboard:user_detail", pk=pk)


# ==========================================================================
#  Savolni to'liq tahrirlash
# ==========================================================================


@staff_required
def question_edit(request, pk: int, question_id: int):
    """Bitta savolni to'liq tahrirlash."""
    exam = get_object_or_404(Exam, pk=pk)
    question = get_object_or_404(Question, pk=question_id, exam=exam)

    form = QuestionForm(instance=question)
    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, f"{question.order}-savol saqlandi.")
            next_question = (
                exam.questions.filter(order__gt=question.order).order_by("order").first()
            )
            if "save_next" in request.POST and next_question is not None:
                return redirect(
                    "dashboard:question_edit", pk=exam.pk, question_id=next_question.pk
                )
            return redirect("dashboard:exam_questions", pk=exam.pk)
        messages.error(request, "Formada xatolar bor.")

    ordered = list(exam.questions.order_by("order").values_list("id", "order"))
    position = next((i for i, (qid, _) in enumerate(ordered) if qid == question.id), 0)

    return render(
        request,
        "dashboard/question_edit.html",
        {
            "section": "exams",
            "exam": exam,
            "question": question,
            "form": form,
            "prev_id": ordered[position - 1][0] if position > 0 else None,
            "next_id": ordered[position + 1][0] if position + 1 < len(ordered) else None,
            "total": len(ordered),
            "position": position + 1,
        },
    )


# ==========================================================================
#  Urinishlar (natijalar)
# ==========================================================================


@staff_required
def attempt_list(request):
    """Barcha topshirilgan urinishlar."""
    queryset = (
        Attempt.objects.select_related("exam", "user")
        .order_by("-submitted_at", "-created_at")
    )

    search = (request.GET.get("q") or "").strip()
    status = request.GET.get("holati", "")
    exam_id = request.GET.get("test", "")

    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(user__telegram_id__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    if exam_id.isdigit():
        queryset = queryset.filter(exam_id=int(exam_id))

    return render(
        request,
        "dashboard/attempt_list.html",
        {
            "section": "attempts",
            "attempts": queryset[:300],
            "status_choices": Attempt.Status.choices,
            "exams": Exam.objects.order_by("-created_at")[:100],
            "search": search,
            "selected_status": status,
            "selected_exam": exam_id,
        },
    )


@staff_required
def attempt_detail(request, pk: int):
    """Bitta urinish: barcha javoblar va baholash."""
    attempt = get_object_or_404(
        Attempt.objects.select_related("exam", "user"), pk=pk
    )
    rows = attempt_services.answer_review(attempt)
    certificate = Certificate.objects.filter(attempt=attempt).first()
    code = AccessCode.objects.filter(attempt=attempt).first()

    return render(
        request,
        "dashboard/attempt_detail.html",
        {
            "section": "attempts",
            "attempt": attempt,
            "rows": rows,
            "certificate": certificate,
            "access_code": code,
        },
    )


@staff_required
def attempt_action(request, pk: int, action: str):
    """Urinish ustidagi amallar."""
    attempt = get_object_or_404(Attempt.objects.select_related("exam"), pk=pk)
    exam_pk = attempt.exam_id

    if action == "qayta-baholash":
        score_attempt_preliminary(attempt)
        messages.success(request, "Urinish qayta baholandi.")
        return redirect("dashboard:attempt_detail", pk=pk)

    if action == "bekor":
        attempt_services.cancel_attempt(attempt)
        messages.success(request, "Urinish bekor qilindi, ID kod bo'shatildi.")
        return redirect("dashboard:attempt_detail", pk=pk)

    if action == "ochirish":
        attempt.delete()
        messages.success(request, "Urinish o'chirildi.")
        return redirect("dashboard:exam_results", pk=exam_pk)

    if action == "sertifikat":
        certificate, message = issue_certificate(attempt)
        if certificate is None:
            messages.error(request, message)
        else:
            messages.success(request, f"Sertifikat tayyor: {certificate.number}")
        return redirect("dashboard:attempt_detail", pk=pk)

    messages.error(request, "Noma'lum amal.")
    return redirect("dashboard:attempt_detail", pk=pk)


# ==========================================================================
#  ID kodlar
# ==========================================================================


@staff_required
def code_action(request, pk: int, action: str):
    """Bitta ID kod ustidagi amallar."""
    code = get_object_or_404(AccessCode.objects.select_related("exam"), pk=pk)
    exam_pk = code.exam_id

    if action == "bekor":
        code.status = AccessCode.Status.REVOKED
        code.save(update_fields=["status", "updated_at"])
        messages.success(request, f"{code.code} bekor qilindi.")
    elif action == "tiklash":
        code.status = AccessCode.Status.UNUSED
        code.user = None
        code.telegram_id = None
        code.full_name = ""
        code.attempt = None
        code.activated_at = None
        code.used_at = None
        code.save()
        messages.success(request, f"{code.code} ishlatilmagan holatiga qaytarildi.")
    else:
        messages.error(request, "Noma'lum amal.")

    return redirect("dashboard:exam_codes", pk=exam_pk)


# ==========================================================================
#  Sertifikatlar
# ==========================================================================


@staff_required
def certificate_action(request, pk: int, action: str):
    """Sertifikat ustidagi amallar."""
    certificate = get_object_or_404(
        Certificate.objects.select_related("exam", "attempt"), pk=pk
    )

    if action == "bekor":
        certificate.is_revoked = True
        certificate.revoke_reason = "Panel orqali bekor qilindi"
        certificate.save(update_fields=["is_revoked", "revoke_reason", "updated_at"])
        messages.success(request, f"{certificate.number} bekor qilindi.")
    elif action == "tiklash":
        certificate.is_revoked = False
        certificate.revoke_reason = ""
        certificate.save(update_fields=["is_revoked", "revoke_reason", "updated_at"])
        messages.success(request, f"{certificate.number} tiklandi.")
    elif action == "qayta":
        issue_certificate(certificate.attempt, force=True)
        messages.success(request, f"{certificate.number} PDF qayta yaratildi.")
    elif action == "ochirish":
        number = certificate.number
        if certificate.file:
            try:
                certificate.file.delete(save=False)
            except Exception:  # pragma: no cover
                pass
        certificate.delete()
        messages.success(request, f"{number} o'chirildi.")
        return redirect("dashboard:certificate_list")
    else:
        messages.error(request, "Noma'lum amal.")

    return redirect("dashboard:certificate_list")


# ==========================================================================
#  Amallar tarixi (audit)
# ==========================================================================


@staff_required
def audit_list(request):
    """Foydalanuvchilarning muhim amallari tarixi."""
    queryset = UserAction.objects.select_related("user").order_by("-created_at")

    kind = request.GET.get("turi", "")
    search = (request.GET.get("q") or "").strip()
    if kind:
        queryset = queryset.filter(kind=kind)
    if search:
        queryset = queryset.filter(
            Q(description__icontains=search) | Q(user__full_name__icontains=search)
        )

    return render(
        request,
        "dashboard/audit_list.html",
        {
            "section": "audit",
            "actions": queryset[:300],
            "kind_choices": UserAction.Kind.choices,
            "selected_kind": kind,
            "search": search,
        },
    )


# ==========================================================================
#  Reklama (botdagi barcha foydalanuvchilarga ommaviy xabar)
# ==========================================================================


def _panel_telegram_id(user) -> int | None:
    """
    Panelga Telegram orqali kirgan adminning Telegram ID si.

    `telegram_login` shunday hisoblar uchun `tg_<id>` nomini beradi.
    Login/parol bilan kirilganda ID noma'lum bo'ladi.
    """
    username = getattr(user, "username", "") or ""
    if username.startswith("tg_") and username[3:].isdigit():
        return int(username[3:])
    return None


def _default_test_target(user) -> int | None:
    """Sinov xabari uchun taklif qilinadigan Telegram ID."""
    telegram_id = _panel_telegram_id(user)
    if telegram_id:
        return telegram_id
    admin = BotUser.objects.filter(is_admin=True).order_by("id").first()
    return admin.telegram_id if admin else None


def _parse_schedule(raw: str):
    """`datetime-local` maydonidan kelgan vaqtni o'qiydi."""
    from django.utils.dateparse import parse_datetime

    value = (raw or "").strip()
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@staff_required
def broadcast_list(request):
    """Reklama xabarlari ro'yxati."""
    queryset = Broadcast.objects.select_related("exam", "created_by").order_by(
        "-created_at"
    )
    status = request.GET.get("holati", "")
    if status:
        queryset = queryset.filter(status=status)

    return render(
        request,
        "dashboard/broadcast_list.html",
        {
            "section": "broadcasts",
            "broadcasts": queryset[:200],
            "status_choices": Broadcast.Status.choices,
            "selected_status": status,
            "stats": broadcast_services.broadcast_statistics(),
            "audience_counts": broadcast_services.audience_summary(),
        },
    )


def _broadcast_form_page(request, broadcast: Broadcast | None):
    """Yaratish va tahrirlash sahifasining umumiy qismi."""
    form = BroadcastForm(instance=broadcast)

    if request.method == "POST":
        form = BroadcastForm(request.POST, request.FILES, instance=broadcast)
        if form.is_valid():
            saved = form.save(commit=False)
            if saved.created_by_id is None and request.user.is_authenticated:
                saved.created_by = request.user
            saved.save()
            messages.success(
                request,
                "Reklama saqlandi. Yuborishdan oldin ko'rinishini tekshirib oling.",
            )
            return redirect("dashboard:broadcast_detail", pk=saved.pk)
        messages.error(request, "Formada xatolar bor.")

    return render(
        request,
        "dashboard/broadcast_form.html",
        {
            "section": "broadcasts",
            "broadcast": broadcast,
            "form": form,
            "audience_counts": broadcast_services.audience_summary(),
            "caption_limit": tg_format.CAPTION_LIMIT,
            "text_limit": tg_format.TEXT_LIMIT,
        },
    )


@staff_required
def broadcast_create(request):
    """Yangi reklama xabari."""
    return _broadcast_form_page(request, None)


@staff_required
def broadcast_edit(request, pk: int):
    """Qoralama holatidagi xabarni tahrirlash."""
    broadcast = get_object_or_404(Broadcast, pk=pk)
    if not broadcast.is_editable:
        messages.warning(
            request,
            "Yuborilgan xabarni tahrirlab bo'lmaydi — undan nusxa oling.",
        )
        return redirect("dashboard:broadcast_detail", pk=pk)
    return _broadcast_form_page(request, broadcast)


@staff_required
def broadcast_detail(request, pk: int):
    """Xabar ko'rinishi, auditoriya va yuborish holati."""
    broadcast = get_object_or_404(
        Broadcast.objects.select_related("exam", "created_by"), pk=pk
    )

    problems = (
        broadcast.deliveries.filter(
            status__in=[
                BroadcastDelivery.Status.FAILED,
                BroadcastDelivery.Status.BLOCKED,
            ]
        )
        .select_related("user")
        .order_by("-id")[:50]
    )

    return render(
        request,
        "dashboard/broadcast_detail.html",
        {
            "section": "broadcasts",
            "broadcast": broadcast,
            "recipients": broadcast_services.audience_count(
                broadcast.audience, broadcast.exam
            ),
            "problems": problems,
            "test_target": broadcast.test_target_id or _default_test_target(request.user),
        },
    )


@staff_required
@require_POST
def broadcast_action(request, pk: int, action: str):
    """Reklama ustidagi amallar (barchasi POST orqali)."""
    broadcast = get_object_or_404(Broadcast, pk=pk)

    if action == "yuborish":
        if broadcast.is_running:
            messages.info(request, "Bu xabar allaqachon navbatda.")
            return redirect("dashboard:broadcast_detail", pk=pk)
        scheduled_at = _parse_schedule(request.POST.get("vaqt", ""))
        total = broadcast_services.queue_broadcast(broadcast, scheduled_at=scheduled_at)
        if not total:
            broadcast_services.cancel_broadcast(broadcast)
            messages.warning(
                request, "Bu auditoriyada bironta ham foydalanuvchi topilmadi."
            )
        elif scheduled_at:
            messages.success(
                request,
                f"Reklama {total} ta foydalanuvchiga "
                f"{timezone.localtime(scheduled_at):%d.%m.%Y %H:%M} da yuboriladi.",
            )
        else:
            messages.success(
                request, f"Reklama {total} ta foydalanuvchiga yuborilmoqda."
            )

    elif action == "toxtatish":
        broadcast_services.cancel_broadcast(broadcast)
        messages.success(request, "Yuborish to'xtatildi.")

    elif action == "davom":
        total = broadcast_services.queue_broadcast(broadcast)
        messages.success(
            request,
            f"Yuborish davom ettirildi — {total - broadcast.processed} ta xabar qoldi.",
        )

    elif action == "qoralama":
        broadcast_services.reset_broadcast(broadcast)
        messages.success(request, "Xabar qoralama holatiga qaytarildi.")

    elif action == "nusxa":
        copy = broadcast_services.duplicate_broadcast(broadcast, request.user)
        messages.success(request, "Nusxa yaratildi.")
        return redirect("dashboard:broadcast_edit", pk=copy.pk)

    elif action == "sinov":
        raw_target = (request.POST.get("telegram_id") or "").strip()
        target = raw_target if raw_target.lstrip("-").isdigit() else None
        if target is None:
            messages.error(request, "Sinov uchun to'g'ri Telegram ID kiriting.")
        else:
            broadcast_services.request_test_send(broadcast, int(target))
            messages.success(
                request,
                "Sinov xabari navbatga qo'yildi — bir necha soniyada yetib boradi.",
            )

    elif action == "ochirish":
        if broadcast.is_running:
            messages.error(
                request, "Yuborilayotgan xabarni o'chirib bo'lmaydi — avval to'xtating."
            )
            return redirect("dashboard:broadcast_detail", pk=pk)
        broadcast.delete()
        messages.success(request, "Reklama o'chirildi.")
        return redirect("dashboard:broadcast_list")

    else:
        messages.error(request, "Noma'lum amal.")

    return redirect("dashboard:broadcast_detail", pk=pk)


@staff_required
def broadcast_progress(request, pk: int):
    """Yuborish holati (sahifa uni bir necha soniyada bir so'raydi)."""
    broadcast = get_object_or_404(Broadcast, pk=pk)
    return JsonResponse(
        {
            "status": broadcast.status,
            "status_label": broadcast.get_status_display(),
            "total": broadcast.total,
            "sent": broadcast.sent,
            "failed": broadcast.failed,
            "blocked": broadcast.blocked,
            "processed": broadcast.processed,
            "percent": broadcast.progress_percent,
            "finished": broadcast.is_finished,
            "test_sent": broadcast.test_sent_at is not None,
            "test_error": broadcast.test_error,
        }
    )


# ==========================================================================
#  Telegram orqali kirish (panel Web App sifatida)
# ==========================================================================


def telegram_entry(request):
    """
    Telegram Web App uchun kirish sahifasi.

    Sahifa `initData` ni serverga yuboradi; server imzoni tekshirib,
    admin huquqi bo'lsa sessiyaga kiritadi va panelga yo'naltiradi.
    """
    next_url = request.GET.get("next", "/panel/")
    if not next_url.startswith("/panel/"):
        next_url = "/panel/"
    return render(request, "dashboard/telegram_entry.html", {"next_url": next_url})


@csrf_exempt
@require_POST
def telegram_login(request):
    """`initData` imzosini tekshirib, panelga kiritadi."""
    from apps.miniapp.auth import MiniAppAuthError, resolve_user

    try:
        bot_user = resolve_user(request)
    except MiniAppAuthError as exc:
        return JsonResponse({"ok": False, "error": exc.reason}, status=401)

    if not bot_user.is_admin:
        return JsonResponse(
            {
                "ok": False,
                "error": "Boshqaruv paneliga faqat administratorlar kira oladi.",
            },
            status=403,
        )

    username = f"tg_{bot_user.telegram_id}"
    account, created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": (bot_user.full_name or bot_user.display_name)[:150],
            "is_staff": True,
            "is_active": True,
        },
    )
    changed = False
    if not account.is_staff:
        account.is_staff = True
        changed = True
    # Telegram orqali faqat bot adminlari kira oladi (yuqoridagi tekshiruv),
    # ular panelda to'liq huquqli: pullik test yaratish `is_superuser`
    # talab qiladi — aks holda formada «3-tur — Pullik RASH» ko'rinmaydi.
    if not account.is_superuser:
        account.is_superuser = True
        changed = True
    if not account.is_active:
        account.is_active = True
        changed = True
    if created:
        account.set_unusable_password()
        changed = True
    if changed:
        account.save()

    login(request, account, backend="django.contrib.auth.backends.ModelBackend")

    next_url = str((json.loads(request.body or b"{}") or {}).get("next", "/panel/"))
    if not next_url.startswith("/panel/"):
        next_url = "/panel/"

    return JsonResponse({"ok": True, "next": next_url, "user": account.username})
