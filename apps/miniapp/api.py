"""
Mini App uchun JSON API.

Barcha so'rovlar `X-Telegram-Init-Data` sarlavhasi orqali autentifikatsiya
qilinadi (Telegram imzosi tekshiriladi), shuning uchun sessiya va CSRF
tokeni kerak emas.

Javob formati:
    muvaffaqiyat -> {"ok": true, ...}
    xato         -> {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import logging
import re
from functools import wraps

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.accesscodes import services as code_services
from apps.attempts import services as attempt_services
from apps.attempts.models import Attempt
from apps.certificates import services as certificate_services
from apps.certificates.models import Certificate
from apps.exams import keys as key_parser
from apps.exams import services as exam_services
from apps.exams.models import Exam, Question
from apps.rasch.services import calculate_exam
from apps.users import services as user_services
from core import constants as C
from core.math_expr import MAX_INPUT_LENGTH, normalize_expression, parse_expression
from core.text_utils import is_valid_full_name, normalize_phone

from . import serializers as S
from core.db_retry import retry_on_lock

from .auth import MiniAppAuthError, resolve_user

logger = logging.getLogger(__name__)


# ==========================================================================
#  Yordamchi qatlam
# ==========================================================================


class ApiError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def api_view(*methods: str):
    """API endpointini o'raydigan dekorator."""

    allowed = set(methods or ("GET",))

    def decorator(func):
        @csrf_exempt
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if request.method not in allowed:
                return JsonResponse(
                    {"ok": False, "error": "So'rov usuli qo'llab-quvvatlanmaydi."},
                    status=405,
                )
            try:
                user = resolve_user(request)
            except MiniAppAuthError as exc:
                from bot.config import get_config

                config = get_config()
                return JsonResponse(
                    {
                        "ok": False,
                        "error": exc.reason,
                        "auth": False,
                        # Ilova shu kodga qarab kerakli tugmani chizadi.
                        "code": getattr(exc, "code", "invalid"),
                        "bot_url": config.bot_link(),
                        "channel_url": config.required_channel_url,
                    },
                    status=401,
                )

            try:
                # Imtihon paytida o'nlab qatnashchi bir vaqtda javob
                # saqlaydi — SQLite qulfida amal qayta bajariladi.
                payload = retry_on_lock(func)(request, user, *args, **kwargs)
            except ApiError as exc:
                return JsonResponse({"ok": False, "error": exc.message}, status=exc.status)
            except Exception:  # pragma: no cover - kutilmagan xato
                logger.exception("Mini App API xatosi: %s", request.path)
                return JsonResponse(
                    {"ok": False, "error": "Server xatosi. Qaytadan urinib ko'ring."},
                    status=500,
                )

            if isinstance(payload, HttpResponse):
                return payload
            data = {"ok": True}
            data.update(payload or {})
            return JsonResponse(data)

        return wrapper

    return decorator


def body(request) -> dict:
    """So'rov tanasini JSON sifatida o'qiydi."""
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError("So'rov formati noto'g'ri.") from None
    return data if isinstance(data, dict) else {}


def get_exam_or_404(code: str) -> Exam:
    """Kod bo'yicha testni oladi."""
    exam = exam_services.get_exam_by_code(code)
    if exam is None:
        raise ApiError("Test topilmadi.", status=404)
    return exam


def _bot_config():
    """Bot sozlamalari (havolalar uchun)."""
    from bot.config import get_config

    return get_config()


def get_owned_exam(code: str, user) -> Exam:
    """Testni oladi va boshqarish huquqini tekshiradi."""
    exam = get_exam_or_404(code)
    if not exam_services.can_manage(exam, user, is_admin=bool(user.is_admin)):
        raise ApiError("Bu testni boshqarish huquqingiz yo'q.", status=403)
    return exam


def get_own_attempt(attempt_id: int, user) -> Attempt:
    """Urinishni oladi va u foydalanuvchiga tegishliligini tekshiradi."""
    attempt = (
        Attempt.objects.select_related("exam", "user").filter(pk=attempt_id).first()
    )
    if attempt is None:
        raise ApiError("Urinish topilmadi.", status=404)
    if attempt.user_id != user.id and not user.is_admin:
        raise ApiError("Bu natija sizga tegishli emas.", status=403)
    return attempt


def require_registered(user) -> None:
    """Ro'yxatdan o'tganlikni talab qiladi."""
    if not user.is_registered:
        raise ApiError(
            "Avval botda ro'yxatdan o'ting: ism-familiya va telefon raqami.",
            status=403,
        )


# ==========================================================================
#  1. Boshlang'ich ma'lumotlar
# ==========================================================================


@api_view("GET")
def bootstrap(request, user):
    """Ilova ochilganda kerak bo'ladigan barcha ma'lumotlar."""
    # Testlar ro'yxati ishtirokchilarga ko'rsatilmaydi — ular testga faqat
    # tashkilotchi bergan kod orqali kiradi. Ro'yxatni faqat admin ko'radi.
    available = exam_services.list_available_exams(limit=20) if user.is_admin else []
    history = attempt_services.user_history(user, limit=20)
    certificates = Certificate.objects.filter(user=user, is_revoked=False).select_related(
        "exam"
    ).order_by("-issued_at")[:20]
    owned = exam_services.list_owned_exams(user, limit=30)

    drafts = list(
        Attempt.objects.filter(user=user, status=Attempt.Status.DRAFT)
        .select_related("exam")
        .order_by("-created_at")[:5]
    )

    return {
        "user": S.user_dict(user),
        "exams": [S.exam_dict(exam) for exam in available],
        "results": [
            S.attempt_dict(attempt) for attempt in history
        ],
        "certificates": [S.certificate_dict(item) for item in certificates],
        "my_exams": [
            S.exam_dict(exam, participants=getattr(exam, "participants", 0))
            for exam in owned
        ],
        "drafts": [
            {
                "attempt_id": attempt.id,
                "exam_code": attempt.exam.code,
                "exam_title": attempt.exam.title,
                "current_order": attempt.current_order,
                "question_count": attempt.exam.question_count,
            }
            for attempt in drafts
            if attempt.exam.accepts_answers
        ],
        "grade_table": [
            {"from": low, "to": high, "grade": grade} for low, high, grade in C.GRADE_TABLE
        ],
        "max_ball": C.MAX_BALL,
        # Ro'yxatdan o'tmagan foydalanuvchini botga yo'naltirish uchun.
        "bot_url": _bot_config().bot_link(),
    }


@api_view("POST")
def profile_update(request, user):
    """
    Ism-familiya va telefon raqamini tahrirlaydi.

    Tekshiruvlar botdagi ro'yxatdan o'tish bilan bir xil (`core.text_utils`),
    shunda bir xil ma'lumot ikki joyda turlicha qabul qilinmaydi.
    """
    data = body(request)
    raw_name = str(data.get("full_name") or "").strip()
    raw_phone = str(data.get("phone") or "").strip()

    errors: list[str] = []
    if not is_valid_full_name(raw_name):
        errors.append(
            "Ism-familiya kamida ikki so'zdan iborat bo'lsin (masalan: Alisher Rahimov)."
        )

    phone = normalize_phone(raw_phone)
    if len(re.sub(r"\D", "", phone)) < 9:
        errors.append("Telefon raqamini to'liq kiriting (masalan: +998901234567).")

    if errors:
        raise ApiError(" ".join(errors))

    saved = user_services.update_profile(user, raw_name, raw_phone)
    return {"user": S.user_dict(user), "saved": saved}


# ==========================================================================
#  2. Testlar
# ==========================================================================


@api_view("GET")
def exam_list(request, user):
    """
    Ishtirok etish mumkin bo'lgan testlar.

    Ishtirokchilarga bo'sh ro'yxat qaytariladi: testga kirish faqat test
    kodi orqali. Ro'yxatni ko'rish huquqi faqat adminda.
    """
    exams = exam_services.list_available_exams(limit=40) if user.is_admin else []
    return {"exams": [S.exam_dict(exam) for exam in exams], "list_visible": bool(user.is_admin)}


@api_view("GET")
def exam_detail(request, user, code: str):
    """Test haqidagi to'liq ma'lumot va ishtirok etish imkoniyati."""
    exam = get_exam_or_404(code)
    check = attempt_services.can_participate(user, exam)
    participants = attempt_services.participants_count(exam)
    my_attempt = attempt_services.get_result(exam, user)
    draft = attempt_services.get_draft_attempt(user, exam)

    return {
        "exam": S.exam_dict(exam, participants=participants, detailed=True),
        "can_participate": check.ok,
        "reason": check.message,
        "my_attempt_id": my_attempt.id if my_attempt else None,
        "draft_attempt_id": draft.id if draft else None,
        "can_manage": exam_services.can_manage(exam, user, is_admin=bool(user.is_admin)),
    }


@api_view("POST")
def exam_start(request, user, code: str):
    """Testni boshlaydi (pullik testda ID kod tekshiriladi)."""
    require_registered(user)
    exam = get_exam_or_404(code)

    check = attempt_services.can_participate(user, exam)
    if not check.ok:
        raise ApiError(check.message)

    access_code = None
    if exam.requires_access_code:
        raw_code = str(body(request).get("access_code", "")).strip()
        result = code_services.check_code(raw_code, exam)
        if not result.ok:
            raise ApiError(_strip_html(result.message))
        access_code = result.code

    attempt = attempt_services.start_attempt(user, exam, access_code)
    return {"attempt_id": attempt.id}


# ==========================================================================
#  3. Test topshirish
# ==========================================================================


@api_view("GET")
def attempt_detail(request, user, attempt_id: int):
    """Urinishdagi barcha savollar va saqlangan javoblar."""
    attempt = get_own_attempt(attempt_id, user)
    questions = list(attempt.exam.questions.filter(is_active=True).order_by("order"))
    answers = {answer.question_id: answer for answer in attempt.answers.all()}

    return {
        "attempt": S.attempt_dict(attempt),
        "exam": S.exam_dict(attempt.exam, detailed=True),
        "questions": [
            S.question_dict(question, answers.get(question.id)) for question in questions
        ],
        "editable": attempt.status == Attempt.Status.DRAFT and attempt.exam.accepts_answers,
    }


@api_view("POST")
def attempt_answer(request, user, attempt_id: int):
    """Bitta savolga javobni saqlaydi."""
    attempt = get_own_attempt(attempt_id, user)
    if attempt.status != Attempt.Status.DRAFT:
        raise ApiError("Javoblar allaqachon yuborilgan.")
    if not attempt.exam.accepts_answers:
        raise ApiError("Test yopilgan — javob qabul qilinmaydi.")

    data = body(request)
    try:
        order = int(data.get("order", 0))
    except (TypeError, ValueError):
        raise ApiError("Savol raqami noto'g'ri.") from None

    question = Question.objects.filter(
        exam=attempt.exam, order=order, is_active=True
    ).first()
    if question is None:
        raise ApiError("Savol topilmadi.", status=404)

    kwargs: dict = {}
    if question.kind in {Question.Kind.SINGLE, Question.Kind.MULTI}:
        selected = str(data.get("selected", ""))
        letters = {ch.upper() for ch in selected if ch.isalpha()}
        allowed = set(question.choice_letters)
        if not letters <= allowed:
            raise ApiError("Noto'g'ri variant tanlandi.")
        if len(letters) > 1:
            # Yopiq savollarda ham, moslashtirish (A–F) savollarida ham
            # faqat bitta variant belgilanadi.
            raise ApiError("Bu savolda faqat bitta variant tanlanadi.")
        kwargs["selected"] = "".join(sorted(letters))
    else:
        kwargs["text_a"] = str(data.get("text_a", ""))[:255]
        kwargs["text_b"] = str(data.get("text_b", ""))[:255]

    attempt_services.save_answer(attempt, question, **kwargs)
    attempt_services.set_current_order(attempt, order)

    answered, total = attempt_services.progress(attempt)
    return {"answered": answered, "total": total}


@api_view("POST")
def attempt_submit(request, user, attempt_id: int):
    """Javoblarni yakuniy yuboradi."""
    attempt = get_own_attempt(attempt_id, user)
    if attempt.status == Attempt.Status.SUBMITTED:
        return {"attempt": S.attempt_dict(attempt), "already": True}
    if not attempt.exam.accepts_answers:
        raise ApiError("Test yopilgan — javob qabul qilinmaydi.")

    attempt = attempt_services.submit_attempt(attempt)
    attempt.refresh_from_db()
    return {"attempt": S.attempt_dict(attempt)}


@api_view("POST")
def attempt_cancel(request, user, attempt_id: int):
    """Boshlangan urinishni bekor qiladi va ID kodni bo'shatadi."""
    attempt = get_own_attempt(attempt_id, user)
    if attempt.status != Attempt.Status.DRAFT:
        raise ApiError("Yuborilgan urinishni bekor qilib bo'lmaydi.")
    attempt_services.cancel_attempt(attempt)
    return {}


# ==========================================================================
#  4. Natijalar
# ==========================================================================


@api_view("GET")
def attempt_result(request, user, attempt_id: int):
    """Natija, javoblar tahlili va sertifikat holati."""
    attempt = get_own_attempt(attempt_id, user)
    exam = attempt.exam
    total = attempt_services.participants_count(exam)

    published = exam.results_available
    visible = exam.show_results_to_participants
    if exam.uses_rasch:
        visible = visible and published

    payload = {
        "attempt": S.attempt_dict(attempt, total_participants=total),
        "visible": bool(visible),
        "pending": bool(exam.uses_rasch and not published),
        "review": [],
        "certificate": None,
        "certificate_reason": "",
    }

    # `answer_review` o'zi `show_correct_answers` sozlamasini hisobga oladi:
    # kalit yopiq bo'lsa, to'g'ri javob o'rniga «—» qaytariladi.
    if visible:
        payload["review"] = S.review_dict(attempt_services.answer_review(attempt))

    if exam.can_issue_certificate and published:
        existing = certificate_services.get_certificate(attempt)
        if existing is not None:
            payload["certificate"] = S.certificate_dict(existing)
        else:
            check = certificate_services.check_eligibility(attempt)
            payload["certificate_reason"] = "" if check.ok else check.reason
            payload["certificate_available"] = bool(check)

    return payload


@api_view("POST")
def attempt_certificate(request, user, attempt_id: int):
    """Sertifikatni yaratadi (yoki mavjudini qaytaradi)."""
    attempt = get_own_attempt(attempt_id, user)
    certificate, message = certificate_services.issue_certificate(attempt)
    if certificate is None:
        raise ApiError(message)
    return {"certificate": S.certificate_dict(certificate)}


@api_view("GET")
def exam_rating(request, user, code: str):
    """Test reytingi."""
    exam = get_exam_or_404(code)
    is_owner = exam_services.can_manage(exam, user, is_admin=bool(user.is_admin))

    if not is_owner:
        if not exam.show_rating_to_participants:
            raise ApiError("Bu testda reyting yopiq.", status=403)
        if exam.uses_rasch and not exam.results_available:
            raise ApiError("Natijalar hali e'lon qilinmagan.", status=403)

    my_attempt = attempt_services.get_result(exam, user)
    limit = None if is_owner else 30
    attempts = attempt_services.rating(exam, limit=limit)

    return {
        "exam": S.exam_dict(exam),
        "rows": S.rating_dict(
            attempts,
            uses_rasch=exam.uses_rasch,
            me_id=my_attempt.id if my_attempt else None,
            # Nechta topgani faqat asosiy adminlarga ko'rinadi.
            show_raw=exam_services.is_main_admin(user),
        ),
        "my_place": my_attempt.rank if my_attempt else None,
        "total": attempt_services.participants_count(exam),
    }


@api_view("GET")
def certificate_list(request, user):
    """Foydalanuvchining sertifikatlari."""
    certificates = (
        Certificate.objects.filter(user=user, is_revoked=False)
        .select_related("exam")
        .order_by("-issued_at")[:50]
    )
    return {"certificates": [S.certificate_dict(item) for item in certificates]}


# ==========================================================================
#  5. Test yaratish va boshqarish
# ==========================================================================


@api_view("GET")
def my_exams(request, user):
    """Foydalanuvchi yaratgan testlar."""
    exams = exam_services.list_owned_exams(user, limit=50)
    return {
        "exams": [
            S.exam_dict(exam, participants=getattr(exam, "participants", 0))
            for exam in exams
        ]
    }


@api_view("POST")
def exam_create(request, user):
    """
    Yangi test yaratadi.

    Kutilayotgan maydonlar:
        title, type, national, question_count, duration_hours,
        show_results, certificate, single_keys, multi_keys, open_keys
    """
    require_registered(user)
    data = body(request)

    title = str(data.get("title", "")).strip()
    if len(title) < 3:
        raise ApiError("Test nomi kamida 3 ta belgidan iborat bo'lishi kerak.")

    exam_type = str(data.get("type", Exam.Type.SIMPLE))
    if exam_type not in dict(Exam.Type.choices):
        raise ApiError("Test turi noto'g'ri.")
    if exam_type == Exam.Type.RASCH_PAID and not user.is_admin:
        raise ApiError("Pullik testni faqat asosiy admin yaratishi mumkin.", status=403)

    national = bool(data.get("national")) and exam_type != Exam.Type.SIMPLE
    if national:
        question_count = C.NATIONAL_TOTAL_QUESTIONS
        single_count = C.NATIONAL_SINGLE_RANGE[1] - C.NATIONAL_SINGLE_RANGE[0] + 1
        multi_count = C.NATIONAL_MULTI_RANGE[1] - C.NATIONAL_MULTI_RANGE[0] + 1
        open_count = C.NATIONAL_OPEN_RANGE[1] - C.NATIONAL_OPEN_RANGE[0] + 1
    else:
        try:
            question_count = int(data.get("question_count", 0))
        except (TypeError, ValueError):
            raise ApiError("Savollar soni noto'g'ri.") from None
        if not (1 <= question_count <= 500):
            raise ApiError("Savollar soni 1 dan 500 gacha bo'lishi kerak.")
        single_count, multi_count, open_count = question_count, 0, 0

    # --- Javob kalitlarini oldindan tekshiramiz ---
    errors: list[str] = []
    single_keys = multi_keys = open_keys = None

    if single_count:
        parsed = key_parser.parse_single_key(str(data.get("single_keys", "")), single_count)
        errors.extend(parsed.errors)
        single_keys = parsed.keys
    if multi_count:
        parsed = key_parser.parse_multi_key(str(data.get("multi_keys", "")), multi_count)
        errors.extend(parsed.errors)
        multi_keys = parsed.keys
    if open_count:
        parsed = key_parser.parse_open_key(str(data.get("open_keys", "")), open_count)
        errors.extend(parsed.errors)
        open_keys = parsed.keys

    if errors:
        return JsonResponse(
            {"ok": False, "error": "Javob kalitida xatolar bor.", "errors": errors[:12]},
            status=400,
        )

    from datetime import timedelta

    from django.utils import timezone

    hours = max(0, int(data.get("duration_hours", 0) or 0))

    # Aniq sana-vaqt («2026-08-20T21:30») tayyor variantdan ustun turadi.
    ends_at = _parse_local_datetime(str(data.get("ends_at", "")))
    if ends_at is not None:
        if ends_at <= timezone.now():
            raise ApiError("Tugash vaqti kelajakda bo'lishi kerak.")
        hours = max(0, int((ends_at - timezone.now()).total_seconds() // 3600))
    elif hours:
        ends_at = timezone.now() + timedelta(hours=hours)

    exam = exam_services.create_exam(
        owner=user,
        title=title,
        exam_type=exam_type,
        question_count=question_count,
        national_template=national,
        description=str(data.get("description", ""))[:2000],
        duration_minutes=hours * 60,
        ends_at=ends_at,
        show_results=bool(data.get("show_results", True)),
        show_correct_answers=bool(data.get("show_results", True)),
        certificate_enabled=bool(data.get("certificate", False))
        and exam_type == Exam.Type.RASCH_PAID,
        organizer_name=user.full_name or "",
    )

    if single_keys:
        exam_services.apply_single_keys(exam, single_keys)
    if multi_keys:
        exam_services.apply_multi_keys(exam, multi_keys)
    if open_keys:
        exam_services.apply_open_keys(exam, open_keys)

    # Test saqlangan zahoti o'zi faollashadi — qo'lda faollashtirish yo'q.
    # Pullik test bundan mustasno: unda avval ID kodlar yaratilishi kerak.
    activated = False
    message = ""
    if exam_type != Exam.Type.RASCH_PAID:
        activated, message = exam_services.activate_exam(exam)
        exam.refresh_from_db()

    return {
        "exam": S.exam_dict(exam, participants=0, detailed=True),
        "activated": activated,
        "message": message,
    }


@api_view("POST")
def exam_delete(request, user, code: str):
    """Testni butunlay o'chiradi."""
    exam = get_owned_exam(code, user)
    data = body(request)
    summary = exam_services.deletion_summary(exam)

    if summary["needs_confirmation"] and not data.get("confirm"):
        return JsonResponse(
            {
                "ok": False,
                "error": "Tasdiqlash talab qilinadi.",
                "needs_confirmation": True,
                "summary": summary,
            },
            status=409,
        )

    ok, message, summary = exam_services.delete_exam(exam, force=True)
    if not ok:
        raise ApiError(message)
    return {"message": message, "summary": summary}


@api_view("GET")
def exam_delete_preview(request, user, code: str):
    """O'chirilganda nimalar yo'qolishini ko'rsatadi."""
    exam = get_owned_exam(code, user)
    return {"summary": exam_services.deletion_summary(exam), "exam": S.exam_dict(exam)}


@api_view("POST")
def exam_action(request, user, code: str):
    """
    Test ustidagi amallar.

    Asosiysi — «finish»: test yopiladi, natijalar hisoblanadi va darhol
    e'lon qilinadi. Alohida yopish / hisoblash / e'lon qilish bosqichlari
    yo'q, chunki test yaratilishi bilan faol bo'ladi.
    """
    exam = get_owned_exam(code, user)
    action = str(body(request).get("action", ""))

    if action == "finish":
        ok, message = exam_services.finish_exam(exam)
        if ok and exam.can_issue_certificate:
            exam.refresh_from_db()
            result = certificate_services.issue_for_exam(exam)
            message += f" Sertifikatlar: {result['created']} ta."
    elif action == "recalculate":
        report = calculate_exam(exam)
        ok = True
        message = (
            f"{report.participants} ta qatnashchi qayta hisoblandi. "
            f"Ishonchlilik: {report.reliability:.3f}"
        )
    elif action == "certificates":
        if not exam.can_issue_certificate:
            raise ApiError("Bu testda sertifikat berish yoqilmagan.")
        result = certificate_services.issue_for_exam(exam)
        ok = True
        message = (
            f"{result['created']} ta sertifikat yaratildi, "
            f"{result['skipped']} ta o'tkazib yuborildi."
        )
    else:
        raise ApiError("Noma'lum amal.")

    exam.refresh_from_db()
    if not ok:
        raise ApiError(message)
    return {
        "message": message,
        "exam": S.exam_dict(exam, detailed=True),
    }


@api_view("GET")
def exam_manage(request, user, code: str):
    """Boshqaruv ekrani uchun to'liq ma'lumot."""
    exam = get_owned_exam(code, user)
    statistics = getattr(exam, "statistics", None)
    participants = attempt_services.participants_count(exam)

    codes = None
    if exam.requires_access_code:
        codes = code_services.code_statistics(exam)

    return {
        "exam": S.exam_dict(exam, participants=participants, detailed=True),
        # O'rtacha to'g'ri javoblar soni — faqat asosiy adminlarga.
        "statistics": S.statistics_dict(
            statistics, show_raw=exam_services.is_main_admin(user)
        ),
        "codes": codes,
        "missing_keys": exam_services.missing_keys(exam)[:30],
        "certificates": Certificate.objects.filter(exam=exam).count(),
        "exports": {
            "results_xlsx": f"/panel/testlar/{exam.id}/eksport/natijalar.xlsx",
            "results_pdf": f"/panel/testlar/{exam.id}/eksport/natijalar.pdf",
        },
    }


@api_view("POST")
def exam_codes(request, user, code: str):
    """Pullik test uchun ID kodlar yaratadi."""
    exam = get_owned_exam(code, user)
    if not exam.requires_access_code:
        raise ApiError("ID kodlar faqat pullik testlarda ishlatiladi.")
    if not user.is_admin:
        raise ApiError("ID kodlarni faqat asosiy admin yaratadi.", status=403)

    try:
        quantity = int(body(request).get("quantity", 0))
    except (TypeError, ValueError):
        raise ApiError("Miqdor noto'g'ri.") from None
    if not (1 <= quantity <= C.CODE_BATCH_MAX):
        raise ApiError(f"Miqdor 1 dan {C.CODE_BATCH_MAX} gacha bo'lishi kerak.")

    batch = code_services.create_codes(exam, quantity, created_by=user)
    if exam.status == Exam.Status.DRAFT:
        exam_services.activate_exam(exam)

    return {
        "message": f"{batch.quantity} ta ID kod yaratildi.",
        "batch_id": batch.id,
        "download_url": f"/panel/partiya/{batch.id}/eksport/kodlar.xlsx",
        "codes": code_services.code_statistics(exam),
    }


# ==========================================================================
#  6. Matematik ifodani tekshirish
# ==========================================================================


@api_view("POST")
def check_expression(request, user):
    """Kiritilgan matematik ifodani tekshiradi (jonli tekshiruv)."""
    expression = str(body(request).get("expr", ""))[: MAX_INPUT_LENGTH + 20]
    if not expression.strip():
        raise ApiError("Ifoda bo'sh.")

    normalized = normalize_expression(expression)
    parsed = parse_expression(expression)
    if parsed is None:
        raise ApiError("Ifodani tahlil qilib bo'lmadi.")

    value = ""
    try:
        if not parsed.free_symbols:
            value = f"{float(parsed.evalf()):.6g}"
    except Exception:
        value = ""

    return {"normalized": normalized, "pretty": str(parsed), "value": value}


# ==========================================================================
#  Yordamchi
# ==========================================================================


def _strip_html(text: str) -> str:
    """Xabardan HTML teglarini olib tashlaydi."""
    import re

    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_local_datetime(value: str):
    """
    `datetime-local` maydonidan kelgan qiymatni vaqt zonasi bilan o'giradi.

    Ko'rinishi: ``2026-08-20T21:30``. Bo'sh yoki noto'g'ri bo'lsa — `None`.
    """
    from datetime import datetime

    from django.utils import timezone

    raw = (value or "").strip()
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, timezone.get_current_timezone())
    return moment


__all__ = [
    "ApiError",
    "bootstrap",
    "profile_update",
    "exam_list",
    "exam_detail",
    "exam_start",
    "attempt_detail",
    "attempt_answer",
    "attempt_submit",
    "attempt_cancel",
    "attempt_result",
    "attempt_certificate",
    "exam_rating",
    "certificate_list",
    "my_exams",
    "exam_create",
    "exam_delete",
    "exam_delete_preview",
    "exam_action",
    "exam_manage",
    "exam_codes",
    "check_expression",
]
