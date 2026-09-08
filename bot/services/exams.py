"""Testlar bilan ishlash (asinxron)."""

from __future__ import annotations

from asgiref.sync import sync_to_async

from apps.exams import keys as key_parser
from apps.exams import services as exam_services
from apps.exams.models import Exam, Question
from core.db_retry import sync_db_call

# --------------------------------------------------------------------------
#  To'g'ridan-to'g'ri o'raladigan funksiyalar
# --------------------------------------------------------------------------

create_exam = sync_db_call(exam_services.create_exam)
apply_single_keys = sync_db_call(exam_services.apply_single_keys)
apply_multi_keys = sync_db_call(exam_services.apply_multi_keys)
apply_open_keys = sync_db_call(exam_services.apply_open_keys)
activate_exam = sync_db_call(exam_services.activate_exam)
close_exam = sync_db_call(exam_services.close_exam)
publish_results = sync_db_call(exam_services.publish_results)
archive_exam = sync_db_call(exam_services.archive_exam)
duplicate_exam = sync_db_call(exam_services.duplicate_exam)
deletion_summary = sync_to_async(exam_services.deletion_summary, thread_sensitive=True)
delete_exam = sync_db_call(exam_services.delete_exam)
auto_close_expired = sync_db_call(exam_services.auto_close_expired)
#: Muddati o'tgan testlarni butunlay o'chiradi (48 soat).
delete_stale_exams = sync_db_call(exam_services.delete_stale_exams)
get_exam_by_code = sync_to_async(exam_services.get_exam_by_code, thread_sensitive=True)
list_available_exams = sync_to_async(exam_services.list_available_exams, thread_sensitive=True)
list_owned_exams = sync_to_async(exam_services.list_owned_exams, thread_sensitive=True)
exam_summary = sync_to_async(exam_services.exam_summary, thread_sensitive=True)
missing_keys = sync_to_async(exam_services.missing_keys, thread_sensitive=True)

#: Kalitlarni tahlil qilish ORM ga bog'liq emas — to'g'ridan-to'g'ri ishlatiladi.
parse_single_key = key_parser.parse_single_key
parse_multi_key = key_parser.parse_multi_key
parse_open_key = key_parser.parse_open_key


# --------------------------------------------------------------------------
#  Qo'shimcha so'rovlar
# --------------------------------------------------------------------------


@sync_to_async(thread_sensitive=True)
def get_exam(exam_id: int) -> Exam | None:
    """ID bo'yicha testni qaytaradi."""
    return Exam.objects.select_related("owner").filter(pk=exam_id).first()


@sync_to_async(thread_sensitive=True)
def count_questions(exam_id: int, kind: str) -> int:
    """Berilgan turdagi savollar soni."""
    return Question.objects.filter(exam_id=exam_id, kind=kind, is_active=True).count()


@sync_to_async(thread_sensitive=True)
def structure_counts(exam_id: int) -> dict[str, int]:
    """Test tuzilmasi: har bir savol turidan nechtadan bor."""
    result: dict[str, int] = {}
    for kind, _ in Question.Kind.choices:
        result[kind] = Question.objects.filter(
            exam_id=exam_id, kind=kind, is_active=True
        ).count()
    return result


@sync_to_async(thread_sensitive=True)
def get_question(exam_id: int, order: int) -> Question | None:
    """Test ichidagi tartib raqami bo'yicha savolni qaytaradi."""
    return Question.objects.filter(exam_id=exam_id, order=order, is_active=True).first()


@sync_to_async(thread_sensitive=True)
def question_orders(exam_id: int) -> list[int]:
    """Testdagi barcha savollar tartib raqamlari."""
    return list(
        Question.objects.filter(exam_id=exam_id, is_active=True)
        .order_by("order")
        .values_list("order", flat=True)
    )


@sync_to_async(thread_sensitive=True)
def paid_exams() -> list[Exam]:
    """Pullik RASH testlari ro'yxati."""
    return list(
        Exam.objects.filter(exam_type=Exam.Type.RASCH_PAID)
        .exclude(status=Exam.Status.ARCHIVED)
        .order_by("-created_at")[:30]
    )


@sync_to_async(thread_sensitive=True)
def all_exams(limit: int = 30) -> list[Exam]:
    """Barcha testlar (admin uchun)."""
    return list(
        Exam.objects.select_related("owner")
        .exclude(status=Exam.Status.ARCHIVED)
        .order_by("-created_at")[:limit]
    )


@sync_to_async(thread_sensitive=True)
def calculate(exam: Exam):
    """Rasch hisob-kitobini bajaradi."""
    from apps.rasch.services import calculate_exam

    return calculate_exam(exam)


@sync_to_async(thread_sensitive=True)
def export_results_excel(exam: Exam) -> bytes:
    """Natijalarni Excel ko'rinishida qaytaradi."""
    from apps.exports.excel import results_workbook

    return results_workbook(exam)


@sync_to_async(thread_sensitive=True)
def export_results_pdf(exam: Exam) -> bytes:
    """Natijalarni PDF hisobot ko'rinishida qaytaradi."""
    from apps.exports.pdf_report import results_report

    return results_report(exam)


@sync_to_async(thread_sensitive=True)
def difficulty_charts(exam: Exam) -> list[tuple[str, bytes]]:
    """
    Savollar qiyinchiligi va ballar taqsimoti diagrammalari.

    Qaytaradi `(nom, PNG)` juftliklari. Diagramma yasab bo'lmasa (natijalar
    hali hisoblanmagan yoki Pillow yo'q) — bo'sh ro'yxat. Bu ma'lumot faqat
    adminlarga ko'rsatiladi.
    """
    from apps.exports import charts

    summary = charts.build_summary(exam)
    result: list[tuple[str, bytes]] = []

    difficulty = charts.difficulty_png(exam, summary.rows)
    if difficulty:
        result.append(("qiyinchilik", difficulty))

    distribution = charts.distribution_png(exam, summary.bins)
    if distribution:
        result.append(("ballar-taqsimoti", distribution))

    return result


__all__ = [name for name in dir() if not name.startswith("_")]
