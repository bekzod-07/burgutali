"""
Natijalarni PDF hisobot ko'rinishida eksport qilish (SRS 9-bo'lim).

Hisobot tarkibi:
  * test haqida qisqacha ma'lumot;
  * umumiy statistika (o'rtacha ball, ishonchlilik, darajalar taqsimoti);
  * reyting jadvali.
"""

from __future__ import annotations

import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.attempts.services import ranked_attempts
from apps.certificates.fonts import register_fonts, safe_text
from apps.exams.models import Exam

NAVY = colors.HexColor("#0F2B46")
GOLD = colors.HexColor("#C9A227")
LIGHT = colors.HexColor("#EEF2F6")
GRAY = colors.HexColor("#5B6B7B")


def participant_column(exam: Exam) -> str:
    """
    Ishtirokchi ustunining sarlavhasi.

    1- va 2-turda natijalar ism-familiya bilan, 3-turda (pullik RASH testi)
    esa ID raqami bilan e'lon qilinadi.
    """
    if exam.exam_type == Exam.Type.RASCH_PAID:
        return "ID raqami"
    return "F.I.SH"


def _styles():
    """Hisobot uchun matn uslublari."""
    fonts = register_fonts()
    return {
        "title": ParagraphStyle(
            "title", fontName=fonts.bold, fontSize=16, leading=20,
            textColor=NAVY, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=fonts.regular, fontSize=9, leading=12,
            textColor=GRAY, spaceAfter=10,
        ),
        "heading": ParagraphStyle(
            "heading", fontName=fonts.bold, fontSize=11, leading=14,
            textColor=NAVY, spaceBefore=8, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", fontName=fonts.regular, fontSize=9, leading=12,
        ),
        "fonts": fonts,
    }


def _table_style(columns: int) -> TableStyle:
    """Jadval uslubi."""
    fonts = register_fonts()
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), fonts.bold),
            ("FONTNAME", (0, 1), (-1, -1), fonts.regular),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (1, 1), (1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C6D0DA")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def _append_difficulty_chart(story: list, exam: Exam, styles: dict) -> None:
    """
    Hisobotga savollar qiyinchiligi diagrammasini qo'shadi.

    Bu hisobot faqat adminlar uchun eksport qilinadi, shuning uchun
    diagramma ham shu yerda beriladi. Diagramma yasab bo'lmasa (natijalar
    hisoblanmagan yoki Pillow yo'q) bo'lim tushirib qoldiriladi.
    """
    from apps.exports import charts

    fonts = styles["fonts"]
    rows = charts.difficulty_rows(exam)
    if not rows:
        return

    image = charts.difficulty_png(exam, rows)
    if not image:
        return

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(safe_text("Savollar qiyinchiliklari", fonts), styles["heading"])
    )

    width_px, height_px = ImageReader(io.BytesIO(image)).getSize()
    width = 180 * mm
    story.append(
        Image(
            io.BytesIO(image),
            width=width,
            height=width * height_px / max(1, width_px),
        )
    )

    legend = "   ".join(
        f"{name}: {count} ta"
        for name, _, count in charts.DifficultySummary(rows=rows).level_counts
    )
    story.append(Paragraph(safe_text(legend, fonts), styles["subtitle"]))


def results_report(exam: Exam) -> bytes:
    """Test natijalari bo'yicha PDF hisobot yaratadi."""
    styles = _styles()
    fonts = styles["fonts"]
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Natijalar — {exam.title}",
    )

    story: list = []

    # --- Sarlavha ---
    story.append(Paragraph(safe_text(exam.title, fonts), styles["title"]))
    story.append(
        Paragraph(
            safe_text(
                f"Test kodi: {exam.code}  •  Turi: {exam.get_exam_type_display()}  •  "
                f"Holati: {exam.get_status_display()}  •  "
                f"Hisobot: {timezone.localtime().strftime('%d.%m.%Y %H:%M')}",
                fonts,
            ),
            styles["subtitle"],
        )
    )

    # --- Statistika ---
    statistics = getattr(exam, "statistics", None)
    if statistics is not None and statistics.participants:
        story.append(Paragraph(safe_text("Umumiy statistika", fonts), styles["heading"]))
        rows = [
            ["Ko‘rsatkich", "Qiymat"],
            ["Qatnashchilar soni", str(statistics.participants)],
            ["O‘rtacha xom ball", f"{statistics.avg_raw_score:.2f}"],
            ["O‘rtacha foiz", f"{statistics.avg_percent:.2f}%"],
        ]
        if exam.uses_rasch:
            rows += [
                ["O‘rtacha standart ball", f"{statistics.avg_ball:.2f}"],
                ["Eng yuqori ball", f"{statistics.max_ball_achieved:.2f}"],
                ["Eng past ball", f"{statistics.min_ball_achieved:.2f}"],
                ["Standart og‘ish", f"{statistics.std_ball:.2f}"],
                ["Ishonchlilik (KR-20)", f"{statistics.reliability:.3f}"],
            ]
        table = Table(
            [[safe_text(cell, fonts) for cell in row] for row in rows],
            colWidths=[70 * mm, 40 * mm],
        )
        table.setStyle(_table_style(2))
        story.append(table)

        # --- Darajalar taqsimoti ---
        if statistics.grade_distribution:
            story.append(
                Paragraph(safe_text("Darajalar taqsimoti", fonts), styles["heading"])
            )
            grade_rows = [["Daraja", "Soni", "Ulushi"]]
            total = max(1, statistics.participants)
            for grade, count in statistics.grade_rows:
                if not count:
                    continue
                grade_rows.append([grade, str(count), f"{count / total * 100:.1f}%"])
            if len(grade_rows) > 1:
                grade_table = Table(
                    [[safe_text(cell, fonts) for cell in row] for row in grade_rows],
                    colWidths=[45 * mm, 30 * mm, 30 * mm],
                )
                grade_table.setStyle(_table_style(3))
                story.append(grade_table)

    # --- Savollar qiyinchiligi (faqat admin hisobotida) ---
    _append_difficulty_chart(story, exam, styles)

    # --- Reyting ---
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(safe_text("Reyting", fonts), styles["heading"]))

    uses_rasch = exam.uses_rasch
    header = ["O‘rin", participant_column(exam), "To‘g‘ri", "Foiz"]
    widths = [14 * mm, 62 * mm, 18 * mm, 18 * mm]
    if uses_rasch:
        header += ["Ball", "Daraja"]
        widths += [20 * mm, 22 * mm]
    header += ["Sana"]
    widths += [28 * mm]

    data = [header]
    attempts = ranked_attempts(exam)
    for index, attempt in enumerate(attempts, start=1):
        row = [
            str(attempt.rank or index),
            attempt.public_label,
            f"{attempt.raw_score:g}",
            f"{attempt.percent:.1f}%",
        ]
        if uses_rasch:
            row += [
                f"{attempt.ball:.2f}" if attempt.ball is not None else "—",
                attempt.grade or "—",
            ]
        row.append(
            timezone.localtime(attempt.submitted_at).strftime("%d.%m.%Y")
            if attempt.submitted_at
            else "—"
        )
        data.append(row)

    if len(data) == 1:
        story.append(Paragraph(safe_text("Qatnashchilar yo‘q.", fonts), styles["body"]))
    else:
        table = Table(
            [[safe_text(cell, fonts) for cell in row] for row in data],
            colWidths=widths,
            repeatRows=1,
        )
        table.setStyle(_table_style(len(header)))
        story.append(table)

    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            safe_text(
                "Natijalar Rasch (IRT-1PL) modeli asosida hisoblangan."
                if uses_rasch
                else "Natijalar to‘g‘ri javoblar soni bo‘yicha hisoblangan.",
                fonts,
            ),
            styles["subtitle"],
        )
    )

    document.build(story)
    return buffer.getvalue()


def overall_results_report(exam: Exam) -> bytes:
    """
    Umumiy natijalar e'loni — soddalashtirilgan jadval.

    Ustunlar: ``№ · F.I.SH (yoki ID raqami) · BALL · FOIZ · DARAJA``.
    Aynan shu ko'rinish test yakunlangach adminga yuboriladi va
    ishtirokchilarga e'lon qilinadi.
    """
    styles = _styles()
    fonts = styles["fonts"]
    buffer = io.BytesIO()

    moment = exam.closed_at or exam.published_at or timezone.now()
    day = timezone.localtime(moment).strftime("%Y-%m-%d")

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"{day} imtihon natijalari",
    )

    story: list = [
        Paragraph(safe_text(f"{day} imtihon natijalari", fonts), styles["title"]),
        Paragraph(
            safe_text(
                f"{exam.title}  •  Test kodi: {exam.code}  •  "
                f"{exam.get_exam_type_display()}",
                fonts,
            ),
            styles["subtitle"],
        ),
    ]

    header = ["№", participant_column(exam), "BALL", "FOIZ", "DARAJA"]
    data = [header]
    for index, attempt in enumerate(ranked_attempts(exam), start=1):
        data.append(
            [
                str(attempt.rank or index),
                attempt.public_label,
                attempt.display_ball if exam.uses_rasch else f"{attempt.raw_score:g}",
                f"{attempt.percent:.0f}%",
                attempt.grade or "—",
            ]
        )

    if len(data) == 1:
        story.append(Paragraph(safe_text("Qatnashchilar yo‘q.", fonts), styles["body"]))
    else:
        table = Table(
            [[safe_text(cell, fonts) for cell in row] for row in data],
            colWidths=[14 * mm, 92 * mm, 24 * mm, 20 * mm, 28 * mm],
            repeatRows=1,
        )
        table.setStyle(_table_style(len(header)))
        story.append(table)

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            safe_text(
                "Natijalar Rasch (IRT-1PL) modeli asosida hisoblangan."
                if exam.uses_rasch
                else "Natijalar to‘g‘ri javoblar soni bo‘yicha hisoblangan.",
                fonts,
            ),
            styles["subtitle"],
        )
    )

    document.build(story)
    return buffer.getvalue()


def certificate_list_report(exam: Exam) -> bytes:
    """Berilgan sertifikatlar ro'yxatini PDF ko'rinishida qaytaradi."""
    from apps.certificates.models import Certificate

    styles = _styles()
    fonts = styles["fonts"]
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, title="Sertifikatlar")

    story = [
        Paragraph(safe_text(f"{exam.title} — sertifikatlar", fonts), styles["title"]),
        Paragraph(
            safe_text(f"Test kodi: {exam.code}", fonts), styles["subtitle"]
        ),
    ]

    data = [["№", "Sertifikat raqami", "Ism-familiya", "Ball", "Daraja", "Sana"]]
    certificates = Certificate.objects.filter(exam=exam).order_by("-ball")
    for index, certificate in enumerate(certificates, start=1):
        data.append(
            [
                str(index),
                certificate.number,
                certificate.full_name,
                f"{certificate.ball:.2f}",
                certificate.grade or "—",
                certificate.exam_date.strftime("%d.%m.%Y"),
            ]
        )

    if len(data) == 1:
        story.append(Paragraph(safe_text("Sertifikatlar yo‘q.", fonts), styles["body"]))
    else:
        table = Table(
            [[safe_text(cell, fonts) for cell in row] for row in data],
            colWidths=[12 * mm, 40 * mm, 60 * mm, 20 * mm, 20 * mm, 26 * mm],
            repeatRows=1,
        )
        table.setStyle(_table_style(6))
        story.append(KeepTogether(table))

    document.build(story)
    return buffer.getvalue()


__all__ = [
    "participant_column",
    "results_report",
    "overall_results_report",
    "certificate_list_report",
]
