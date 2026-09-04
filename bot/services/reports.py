"""
Umumiy natijalar hisoboti (adminga avtomatik yuboriladigan PDF).

Bu modul ORM ustidagi amallarni asinxron ko'rinishga o'raydi — fon vazifasi
(`bot/tasks/scheduler.py`) shu funksiyalar orqali ishlaydi.
"""

from __future__ import annotations

from asgiref.sync import sync_to_async

from apps.exams import services as exam_services
from core.db_retry import retry_on_lock, sync_db_call

exams_awaiting_report = sync_to_async(
    exam_services.exams_awaiting_report, thread_sensitive=True
)
mark_report_sent = sync_db_call(exam_services.mark_report_sent)
report_recipients = sync_to_async(exam_services.report_recipients, thread_sensitive=True)


@sync_to_async(thread_sensitive=True)
@retry_on_lock
def prepare_report(exam_id: int, reason: str) -> dict | None:
    """
    Hisobotni tayyorlaydi: kerak bo'lsa natijalarni hisoblaydi va PDF yasaydi.

    Ikkita PDF yasaladi:

      * `pdf` — **e'lon uchun**: `№ · F.I.SH · Ball · Foiz · Daraja` va
        fan ballari. Nechta savolni to'g'ri topgani ko'rinmaydi, shuning
        uchun uni kanalga qo'yish mumkin — testni yaratgan foydalanuvchi
        aynan shu faylni oladi.
      * `admin_pdf` — **faqat `.env` dagi asosiy adminlar uchun**:
        yuqoridagilarga qo'shimcha to'g'ri javoblar soni, ularning foizi,
        umumiy statistika va savollar qiyinchiligi.

    Qaytaradi: `{"exam", "title", "code", "type", "participants", "pdf",
    "admin_pdf", "recipients"}` yoki test topilmasa `None`.
    """
    from apps.attempts.models import Attempt
    from apps.exams.models import Exam
    from apps.exports import charts
    from apps.exports.pdf_report import overall_results_report, results_report
    from apps.rasch.services import calculate_exam

    exam = Exam.objects.select_related("owner").filter(pk=exam_id).first()
    if exam is None:
        return None

    participants = Attempt.objects.filter(
        exam=exam, status=Attempt.Status.SUBMITTED
    ).count()

    pdf = b""
    admin_pdf = b""
    images: list[tuple[str, bytes]] = []
    if participants:
        # Test yopilgan, lekin hali hisoblanmagan bo'lsa — avval hisoblaymiz,
        # aks holda hisobotda ball va daraja bo'sh chiqadi.
        if reason == "closed" and exam.status == Exam.Status.CLOSED:
            calculate_exam(exam)
            exam.refresh_from_db()
        pdf = overall_results_report(exam)
        admin_pdf = results_report(exam)

        # Savollar qiyinchiligi diagrammasi — faqat adminlarga.
        summary = charts.build_summary(exam)
        difficulty = charts.difficulty_png(exam, summary.rows)
        if difficulty:
            images.append(("qiyinchilik", difficulty))
        distribution = charts.distribution_png(exam, summary.bins)
        if distribution:
            images.append(("ballar-taqsimoti", distribution))

    return {
        "exam_id": exam.id,
        "title": exam.title,
        "code": exam.code,
        "type": exam.get_exam_type_display(),
        "status": exam.get_status_display(),
        "participants": participants,
        "pdf": pdf,
        "admin_pdf": admin_pdf,
        "images": images,
        # Umumiy natijalar (nechta topgani ko'rinmaydi) — egasi va adminlarga.
        "recipients": exam_services.report_recipients(exam),
        # To'liq hisobot, Excel va diagrammalar — faqat asosiy adminlarga.
        "admin_recipients": exam_services.main_admin_ids(),
    }


@sync_to_async(thread_sensitive=True)
@retry_on_lock
def mark_report_sent_by_id(exam_id: int, reason: str) -> None:
    """Hisobot yuborilganini test ID si bo'yicha belgilaydi."""
    from apps.exams.models import Exam

    exam = Exam.objects.filter(pk=exam_id).first()
    if exam is not None:
        exam_services.mark_report_sent(exam, reason)


@sync_to_async(thread_sensitive=True)
def build_overall_pdf(exam) -> bytes:
    """Umumiy natijalar PDF hisobotini qaytaradi (qo'lda so'ralganda)."""
    from apps.exports.pdf_report import overall_results_report

    return overall_results_report(exam)


__all__ = [
    "exams_awaiting_report",
    "mark_report_sent",
    "mark_report_sent_by_id",
    "report_recipients",
    "prepare_report",
    "build_overall_pdf",
]
