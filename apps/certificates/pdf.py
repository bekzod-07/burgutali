"""
Sertifikatni PDF ko'rinishida chizish.

Dizayn Milliy sertifikat uslubiga yaqin, biroq rasmiy davlat hujjatining
nusxasi emas — platformaning o'z nomi, ranglari va emblemasidan foydalaniladi
(TZ 31-bo'lim talabi).

Chizish `reportlab.pdfgen.canvas` orqali bajariladi: bu bizga har bir element
joylashuvini aniq boshqarish imkonini beradi va tashqi bog'liqlik talab qilmaydi.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import date

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas

from .fonts import register_fonts, safe_text
from .qr import make_qr_reader

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
#  Rang palitrasi
# --------------------------------------------------------------------------

NAVY = HexColor("#0F2B46")
NAVY_LIGHT = HexColor("#1D4E7E")
GOLD = HexColor("#C9A227")
GOLD_LIGHT = HexColor("#E4C766")
CREAM = HexColor("#FBF9F4")
GRAY = HexColor("#5B6B7B")
GRAY_LIGHT = HexColor("#A9B6C2")
WHITE = HexColor("#FFFFFF")

PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE


# --------------------------------------------------------------------------
#  Ma'lumot konteyneri
# --------------------------------------------------------------------------


@dataclass
class CertificateData:
    """Sertifikatga chiqariladigan barcha ma'lumotlar."""

    number: str
    full_name: str
    exam_title: str
    exam_date: date
    ball: float
    max_ball: float
    grade: str = ""
    percent: float | None = None
    award_percent: float | None = None
    rank: int | None = None
    total_participants: int | None = None
    sections: list[tuple[str, str]] = field(default_factory=list)
    organization: str = ""
    organizer_name: str = ""
    platform_name: str = "RASCH MATH PLATFORM"
    issued_at: date | None = None
    verify_url: str = ""

    @property
    def rank_text(self) -> str:
        if not self.rank or not self.total_participants:
            return "—"
        return f"{self.rank} / {self.total_participants}"


# --------------------------------------------------------------------------
#  Yordamchi chizish funksiyalari
# --------------------------------------------------------------------------


def _fit_font_size(
    canvas: pdf_canvas.Canvas,
    text: str,
    font_name: str,
    max_width: float,
    start_size: float,
    min_size: float = 8.0,
) -> float:
    """Matn belgilangan kenglikka sig'adigan shrift o'lchamini topadi."""
    size = start_size
    while size > min_size:
        if canvas.stringWidth(text, font_name, size) <= max_width:
            return size
        size -= 0.5
    return min_size


def _draw_corner(canvas: pdf_canvas.Canvas, x: float, y: float, dx: float, dy: float) -> None:
    """Burchak bezagi (ikkita chiziqdan iborat)."""
    length = 18 * mm
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(2.2)
    canvas.line(x, y, x + dx * length, y)
    canvas.line(x, y, x, y + dy * length)
    canvas.setLineWidth(0.9)
    inner = 3.2 * mm
    canvas.line(x + dx * inner, y + dy * inner, x + dx * (length * 0.72), y + dy * inner)
    canvas.line(x + dx * inner, y + dy * inner, x + dx * inner, y + dy * (length * 0.72))


def _draw_emblem(canvas: pdf_canvas.Canvas, cx: float, cy: float, radius: float, fonts) -> None:
    """Platforma emblemasi — oltin halqa ichida "R" harfi."""
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(2.0)
    canvas.circle(cx, cy, radius, stroke=1, fill=0)
    canvas.setLineWidth(0.8)
    canvas.circle(cx, cy, radius - 1.6 * mm, stroke=1, fill=0)
    canvas.setFillColor(NAVY)
    canvas.setFont(fonts.bold, radius * 1.15)
    canvas.drawCentredString(cx, cy - radius * 0.42, "R")


def _draw_ribbon(canvas: pdf_canvas.Canvas, cx: float, cy: float) -> None:
    """Medal lentasi ko'rinishidagi kichik bezak."""
    canvas.setFillColor(GOLD_LIGHT)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.6)
    path = canvas.beginPath()
    path.moveTo(cx - 6 * mm, cy)
    path.lineTo(cx - 2 * mm, cy - 10 * mm)
    path.lineTo(cx, cy - 6.5 * mm)
    path.lineTo(cx + 2 * mm, cy - 10 * mm)
    path.lineTo(cx + 6 * mm, cy)
    path.close()
    canvas.drawPath(path, stroke=1, fill=1)


def _draw_stat_box(
    canvas: pdf_canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    label: str,
    value: str,
    fonts,
    *,
    accent: Color = NAVY,
    highlight: bool = False,
) -> None:
    """Natija ko'rsatkichi uchun quti."""
    canvas.setFillColor(WHITE if not highlight else CREAM)
    canvas.setStrokeColor(GOLD if highlight else GRAY_LIGHT)
    canvas.setLineWidth(1.4 if highlight else 0.8)
    canvas.roundRect(x, y, width, height, 3 * mm, stroke=1, fill=1)

    canvas.setFillColor(GRAY)
    canvas.setFont(fonts.regular, 8)
    canvas.drawCentredString(x + width / 2, y + height - 7 * mm, safe_text(label, fonts))

    value_text = safe_text(value, fonts)
    size = _fit_font_size(canvas, value_text, fonts.bold, width - 6 * mm, 20, 9)
    canvas.setFillColor(accent)
    canvas.setFont(fonts.bold, size)
    canvas.drawCentredString(x + width / 2, y + height / 2 - size * 0.42, value_text)


# --------------------------------------------------------------------------
#  Asosiy chizish
# --------------------------------------------------------------------------


def draw_certificate(canvas: pdf_canvas.Canvas, data: CertificateData) -> None:
    """Bitta sahifaga sertifikatni chizadi."""
    fonts = register_fonts()
    width, height = PAGE_SIZE

    # --- Fon ---
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, width, height, stroke=0, fill=1)

    # --- Tashqi ramka ---
    margin = 10 * mm
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(3)
    canvas.rect(margin, margin, width - 2 * margin, height - 2 * margin, stroke=1, fill=0)

    inner_margin = margin + 3.5 * mm
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1)
    canvas.rect(
        inner_margin, inner_margin,
        width - 2 * inner_margin, height - 2 * inner_margin,
        stroke=1, fill=0,
    )

    # --- Burchak bezaklari ---
    offset = inner_margin + 4 * mm
    _draw_corner(canvas, offset, offset, 1, 1)
    _draw_corner(canvas, width - offset, offset, -1, 1)
    _draw_corner(canvas, offset, height - offset, 1, -1)
    _draw_corner(canvas, width - offset, height - offset, -1, -1)

    # --- Yuqori qism: platforma nomi ---
    top = height - inner_margin
    _draw_emblem(canvas, width / 2, top - 17 * mm, 9 * mm, fonts)

    canvas.setFillColor(NAVY)
    canvas.setFont(fonts.bold, 13)
    canvas.drawCentredString(
        width / 2, top - 33 * mm, safe_text(data.platform_name.upper(), fonts)
    )
    if data.organization:
        canvas.setFillColor(GRAY)
        canvas.setFont(fonts.regular, 9)
        canvas.drawCentredString(
            width / 2, top - 39 * mm, safe_text(data.organization, fonts)
        )

    # --- Sarlavha ---
    canvas.setFillColor(NAVY)
    canvas.setFont(fonts.bold, 40)
    canvas.drawCentredString(width / 2, top - 58 * mm, safe_text("SERTIFIKAT", fonts))

    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1.6)
    canvas.line(width / 2 - 42 * mm, top - 63 * mm, width / 2 + 42 * mm, top - 63 * mm)

    canvas.setFillColor(GRAY)
    canvas.setFont(fonts.regular, 9.5)
    canvas.drawCentredString(
        width / 2, top - 70 * mm,
        safe_text("Ushbu sertifikat quyidagi shaxsga berildi", fonts),
    )

    # --- Ism-familiya ---
    name_text = safe_text(data.full_name.upper(), fonts)
    name_size = _fit_font_size(canvas, name_text, fonts.bold, width - 90 * mm, 28, 12)
    canvas.setFillColor(NAVY_LIGHT)
    canvas.setFont(fonts.bold, name_size)
    canvas.drawCentredString(width / 2, top - 84 * mm, name_text)

    name_width = canvas.stringWidth(name_text, fonts.bold, name_size)
    underline = max(name_width + 16 * mm, 70 * mm)
    canvas.setStrokeColor(GOLD_LIGHT)
    canvas.setLineWidth(0.9)
    canvas.line(
        width / 2 - underline / 2, top - 88 * mm,
        width / 2 + underline / 2, top - 88 * mm,
    )

    # --- Test nomi va sanasi ---
    canvas.setFillColor(GRAY)
    canvas.setFont(fonts.regular, 9.5)
    canvas.drawCentredString(
        width / 2, top - 96 * mm,
        safe_text("quyidagi testda ishtirok etgani va natija ko‘rsatgani uchun", fonts),
    )

    exam_text = safe_text(data.exam_title, fonts)
    exam_size = _fit_font_size(canvas, exam_text, fonts.bold, width - 100 * mm, 15, 9)
    canvas.setFillColor(NAVY)
    canvas.setFont(fonts.bold, exam_size)
    canvas.drawCentredString(width / 2, top - 104 * mm, exam_text)

    canvas.setFillColor(GRAY)
    canvas.setFont(fonts.regular, 9)
    canvas.drawCentredString(
        width / 2, top - 110 * mm,
        safe_text(f"Test sanasi: {data.exam_date.strftime('%d.%m.%Y')}", fonts),
    )

    # --- Natija qutilari ---
    boxes: list[tuple[str, str, bool]] = [
        ("RASCH BALLI", f"{data.ball:.2f}", True),
    ]
    # Nechta to'g'ri javob berilgani sertifikatda ko'rsatilmaydi — faqat
    # ball, foiz (`ball * 100 / 65`) va daraja.
    if data.award_percent is not None:
        boxes.append(("FOIZ", f"{data.award_percent:.0f}%", False))
    if data.grade:
        boxes.append(("DARAJA", data.grade, False))
    if data.rank and data.total_participants:
        boxes.append(("REYTING", data.rank_text, False))

    box_height = 20 * mm
    box_width = 42 * mm
    gap = 5 * mm
    total_width = len(boxes) * box_width + (len(boxes) - 1) * gap
    start_x = (width - total_width) / 2
    box_y = inner_margin + 40 * mm

    for index, (label, value, highlight) in enumerate(boxes):
        _draw_stat_box(
            canvas,
            start_x + index * (box_width + gap),
            box_y,
            box_width,
            box_height,
            label,
            value,
            fonts,
            accent=GOLD if highlight else NAVY,
            highlight=highlight,
        )

    # --- Bo'limlar bo'yicha natija ---
    if data.sections:
        canvas.setFillColor(GRAY)
        canvas.setFont(fonts.regular, 8)
        pieces = [f"{name}: {value}" for name, value in data.sections[:6]]
        canvas.drawCentredString(
            width / 2, box_y - 6 * mm,
            safe_text("Bo‘limlar bo‘yicha: " + "   |   ".join(pieces), fonts),
        )

    # --- Pastki qism: imzo, raqam, QR ---
    bottom = inner_margin + 12 * mm

    # Imzo (chapda)
    signature_x = inner_margin + 22 * mm
    canvas.setStrokeColor(GRAY_LIGHT)
    canvas.setLineWidth(0.8)
    canvas.line(signature_x, bottom + 9 * mm, signature_x + 52 * mm, bottom + 9 * mm)
    canvas.setFillColor(NAVY)
    canvas.setFont(fonts.bold, 9)
    canvas.drawString(
        signature_x, bottom + 4.5 * mm,
        safe_text(data.organizer_name or data.organization or "Tashkilotchi", fonts),
    )
    canvas.setFillColor(GRAY)
    canvas.setFont(fonts.regular, 7.5)
    canvas.drawString(signature_x, bottom + 0.5 * mm, safe_text("Tashkilotchi / o‘qituvchi", fonts))

    # Sertifikat raqami (markazda)
    canvas.setFillColor(NAVY)
    canvas.setFont(fonts.bold, 10)
    canvas.drawCentredString(
        width / 2, bottom + 6 * mm,
        safe_text(f"Sertifikat raqami: {data.number}", fonts),
    )
    issued = data.issued_at or date.today()
    canvas.setFillColor(GRAY)
    canvas.setFont(fonts.regular, 7.5)
    canvas.drawCentredString(
        width / 2, bottom + 1.5 * mm,
        safe_text(f"Berilgan sana: {issued.strftime('%d.%m.%Y')}", fonts),
    )

    # QR-kod (o'ngda)
    if data.verify_url:
        qr_size = 26 * mm
        qr_x = width - inner_margin - qr_size - 8 * mm
        qr_y = bottom - 1 * mm
        reader = make_qr_reader(data.verify_url, box_size=6, border=1)
        if reader is not None:
            canvas.drawImage(
                reader, qr_x, qr_y, qr_size, qr_size,
                preserveAspectRatio=True, mask="auto",
            )
            canvas.setFillColor(GRAY)
            canvas.setFont(fonts.regular, 6.5)
            canvas.drawCentredString(
                qr_x + qr_size / 2, qr_y - 3.5 * mm,
                safe_text("QR orqali tekshiring", fonts),
            )

    # Medal bezagi
    _draw_ribbon(canvas, width - inner_margin - 20 * mm, top - 20 * mm)

    canvas.showPage()


def render_pdf(data: CertificateData) -> bytes:
    """Sertifikatni PDF bayt massivi ko'rinishida qaytaradi."""
    buffer = io.BytesIO()
    canvas = pdf_canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    canvas.setTitle(f"Sertifikat {data.number}")
    canvas.setAuthor(data.organization or data.platform_name)
    canvas.setSubject(data.exam_title)
    draw_certificate(canvas, data)
    canvas.save()
    return buffer.getvalue()


__all__ = ["CertificateData", "draw_certificate", "render_pdf", "PAGE_SIZE"]
