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
from core import constants as C

NAVY = colors.HexColor("#0F2B46")
GOLD = colors.HexColor("#C9A227")
LIGHT = colors.HexColor("#EEF2F6")
GRAY = colors.HexColor("#5B6B7B")

# ==========================================================================
#  Daraja ranglari
# ==========================================================================

#: Har bir daraja uchun (fon, matn) rangi.
#:
#: Yuqori daraja — to'q yashil, pastga tushgan sari och yashil, sariq va
#: apelsin ranglarga o'tadi. Fon och, matn to'q — jadval oq-qora printerda
#: ham o'qiladi va ranglar bir-biridan yorqinligi bilan ajralib turadi.
GRADE_COLORS: dict[str, tuple[str, str]] = {
    "A+": ("#A5D6A7", "#1B5E20"),   # to'q yashil
    "A":  ("#C8E6C9", "#2E7D32"),   # yashil
    "B+": ("#DCEDC8", "#33691E"),   # och yashil
    "B":  ("#F0F4C3", "#827717"),   # limon
    "C+": ("#FFECB3", "#E65100"),   # sariq
    "C":  ("#FFE0B2", "#BF360C"),   # apelsin
}

#: Daraja olinmagan qatorlar uchun betaraf rang.
NO_GRADE_COLOR: tuple[str, str] = ("#ECEFF1", "#546E7A")


def grade_colors(grade: str) -> tuple[str, str] | None:
    """
    Daraja uchun (fon, matn) rangini qaytaradi.

    Daraja tanilmasa (bo'sh, «—» yoki «Daraja olinmadi») betaraf kulrang
    beriladi; umuman mos kelmasa `None` — katak bo'yalmaydi.
    """
    name = (grade or "").strip()
    if name in GRADE_COLORS:
        return GRADE_COLORS[name]
    if not name or name == "—" or name == C.NO_GRADE:
        return NO_GRADE_COLOR
    return None


def grade_label(grade: str) -> str:
    """
    Daraja ustunida ko'rsatiladigan qisqa yorliq.

    «Daraja olinmadi» reyting jadvalining tor ustuniga sig'maydi va qo'shni
    ustun ustiga chiqib ketadi, shuning uchun u «—» bilan almashtiriladi.
    Ma'nosi jadval ostidagi izoh qatorida tushuntiriladi.
    """
    name = (grade or "").strip()
    return "—" if not name or name == C.NO_GRADE else name


def _grade_column_style(rows: list[list], column: int) -> list[tuple]:
    """
    Daraja bo'yicha **butun qatorni** bo'yaydigan uslub buyruqlari.

    `rows` — jadvalning barcha qatorlari (0-qator sarlavha), `column` —
    daraja ustunining tartib raqami. Buyruqlar asosiy uslubdan **keyin**
    qo'llanadi, shuning uchun ular qator fonini (`ROWBACKGROUNDS`) bosadi.

    Fon och, matn to'q — jadval oq-qora bosmada ham o'qiladi. Daraja
    katagi qo'shimcha ravishda qalin va o'z rangida yoziladi.
    """
    commands: list[tuple] = []
    fonts = register_fonts()
    for index, row in enumerate(rows[1:], start=1):
        if column >= len(row):
            continue
        pair = grade_colors(str(row[column]))
        if pair is None:
            continue
        background, ink = pair
        last = len(row) - 1
        commands.append(
            ("BACKGROUND", (0, index), (last, index), colors.HexColor(background))
        )
        cell = (column, index)
        commands.append(("TEXTCOLOR", cell, cell, colors.HexColor(ink)))
        commands.append(("FONTNAME", cell, cell, fonts.bold))
    return commands


def _grade_legend(styles: dict) -> Paragraph:
    """Ranglar nimani bildirishini tushuntiruvchi qator."""
    fonts = styles["fonts"]
    parts = " · ".join(
        f'<font color="{ink}">{name}</font>' for name, (_, ink) in GRADE_COLORS.items()
    )
    neutral = NO_GRADE_COLOR[1]
    return Paragraph(
        f"Qatorlar daraja rangida: {parts} · "
        f'<font color="{neutral}">— daraja olinmadi</font>',
        styles["subtitle"],
    )


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
                grade_table.setStyle(TableStyle(_grade_column_style(grade_rows, 0)))
                story.append(grade_table)

    # --- Savollar qiyinchiligi (faqat admin hisobotida) ---
    _append_difficulty_chart(story, exam, styles)

    # --- Reyting ---
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(safe_text("Reyting", fonts), styles["heading"]))

    # Bu hisobot faqat adminlar uchun, shuning uchun nechta to'g'ri javob
    # borligi ham ko'rsatiladi. Qatnashchilarga e'lon qilinadigan jadvalda
    # (`overall_results_report`) bu ustunlar yo'q.
    uses_rasch = exam.uses_rasch
    header = ["O‘rin", participant_column(exam), "To‘g‘ri", "Foiz"]
    widths = [13 * mm, 44 * mm, 16 * mm, 16 * mm]
    if uses_rasch:
        header += ["Ball", "Sert. %", "Daraja"]
        widths += [18 * mm, 18 * mm, 20 * mm]
    header += ["Sana"]
    widths += [26 * mm]

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
                f"{C.certificate_percent(attempt.ball, attempt.grade):.2f}%"
                if attempt.ball is not None else "—",
                grade_label(attempt.grade),
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
        if uses_rasch:
            # «Daraja» — «Ball» dan keyingi ustun.
            column = header.index("Daraja")
            table.setStyle(TableStyle(_grade_column_style(data, column)))
        story.append(table)
        if uses_rasch:
            story.append(Spacer(1, 2 * mm))
            story.append(_grade_legend(styles))

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

    Ustunlar: ``№ · F.I.SH (yoki ID raqami) · BALL · FOIZ · DARAJA`` va
    RASH testlarida yana uchta fan balli: ``ASOSIY 1-FAN · ASOSIY 2-FAN ·
    MAJBURIY FAN``. Aynan shu ko'rinish test yakunlangach adminga yuboriladi
    va ishtirokchilarga e'lon qilinadi.
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

    # RASH testlarida foiz `ball * 100 / 65` formulasi bo'yicha ko'rsatiladi
    # (`core.constants.certificate_percent`), oddiy testda esa to'g'ri
    # javoblarning ulushi. Nechta to'g'ri topgani e'londa ko'rsatilmaydi —
    # u faqat adminlar hisobotida bo'ladi.
    header = ["№", participant_column(exam), "BALL", "FOIZ", "DARAJA"]
    widths = [9 * mm, 45 * mm, 20 * mm, 22 * mm, 24 * mm]
    if exam.uses_rasch:
        # Sertifikat foizi asosiy fanlarga ko'chiriladi (100% -> 93 va 63),
        # majburiy fan esa sertifikat olganlarning hammasiga to'liq: 11 ball.
        # Sarlavha ikki qatorga bo'linadi, aks holda ustunga sig'maydi.
        header += [
            name.upper().replace(" ", "\n", 1) for name in C.subject_names()
        ]
        widths += [21 * mm, 21 * mm, 20 * mm]
    else:
        widths = [12 * mm, 92 * mm, 24 * mm, 22 * mm, 28 * mm]

    data = [header]
    for index, attempt in enumerate(ranked_attempts(exam), start=1):
        if exam.uses_rasch:
            percent = C.certificate_percent(attempt.ball, attempt.grade)
        else:
            percent = attempt.percent or 0.0
        row = [
            str(attempt.rank or index),
            attempt.public_label,
            attempt.display_ball if exam.uses_rasch else f"{attempt.raw_score:g}",
            f"{percent:.2f}%",
            grade_label(attempt.grade),
        ]
        if exam.uses_rasch:
            row += [
                f"{value:.2f}"
                for value in C.subject_scores(attempt.ball, attempt.grade)
            ]
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
        if exam.uses_rasch:
            table.setStyle(TableStyle(_grade_column_style(data, header.index("DARAJA"))))
        story.append(table)
        if exam.uses_rasch:
            story.append(Spacer(1, 2 * mm))
            story.append(_grade_legend(styles))

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

    header = ["№", "Sertifikat raqami", "Ism-familiya", "Ball", "Daraja", "Sana"]
    data = [header]
    certificates = Certificate.objects.filter(exam=exam).order_by("-ball")
    for index, certificate in enumerate(certificates, start=1):
        data.append(
            [
                str(index),
                certificate.number,
                certificate.full_name,
                f"{certificate.ball:.2f}",
                grade_label(certificate.grade),
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
        table.setStyle(TableStyle(_grade_column_style(data, header.index("Daraja"))))
        story.append(KeepTogether(table))
        story.append(Spacer(1, 2 * mm))
        story.append(_grade_legend(styles))

    document.build(story)
    return buffer.getvalue()


__all__ = [
    "participant_column",
    "results_report",
    "overall_results_report",
    "certificate_list_report",
]
