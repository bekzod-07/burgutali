"""
Savollar qiyinligi va ballar taqsimoti diagrammalari.

Talab (2026-08-09): RASH testlarida savollarning qiyinchilik darajasi
ustunli diagramma ko'rinishida ko'rsatilsin va u **faqat adminlarga**
ochiq bo'lsin. Shu sababli bu modul faqat ikki joyda ishlatiladi:

  * boshqaruv panelining natijalar sahifasi (`@staff_required`) — SVG;
  * test yakunlangach adminlarga yuboriladigan hisobot — PNG.

Diagramma har bir savol uchun bitta ustun chizadi va ustun ikkiga
bo'linadi:

  * pastki **ko'k** qism — savolni to'g'ri topgan ishtirokchilar soni;
  * yuqoridagi **qizil** qism — topa olmaganlar soni.

Ustunning to'liq balandligi — qatnashchilar soni, shuning uchun savollarni
bir qarashda solishtirish mumkin. Har bir qismning ichiga odamlar soni
yoziladi. Qiyinlik foizi (noto'g'ri javob bergalar ulushi) va Rasch `b`
qiymati diagramma yonidagi jadvalda ko'rsatiladi.

Diagrammalar tashqi kutubxonasiz chiziladi: panel uchun — qo'lda
yig'ilgan SVG, bot uchun — Pillow. Emoji ishlatilmaydi.
"""

from __future__ import annotations

import io
import logging
import math
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
#  Ranglar va qiyinlik darajalari
# --------------------------------------------------------------------------

GREEN = "#1f9d55"
GOLD = "#d9a908"
ORANGE = "#e08e0b"
RED = "#d9534f"
NAVY = "#0f2b46"
GRID = "#dfe6ee"
MUTED = "#64758c"
BLUE = "#2f7fd0"
BLUE_SOFT = "#cfe3f6"

#: Ustunli diagramma ranglari: topganlar — ko'k, topmaganlar — qizil.
CORRECT_COLOR = "#2f7fd0"
WRONG_COLOR = "#e2523f"

#: (yuqori chegara, nomi, rangi) — chegara **ichiga olinmaydi**.
DIFFICULTY_LEVELS: tuple[tuple[float, str, str], ...] = (
    (30.0, "Oson", GREEN),
    (60.0, "O'rtacha", GOLD),
    (80.0, "Qiyin", ORANGE),
    (float("inf"), "Juda qiyin", RED),
)

#: Ballar taqsimotidagi oraliq kengligi (ball).
BALL_BIN_STEP: float = 2.0

#: Taqsimotdagi ustunlar sonining yuqori chegarasi.
MAX_BINS: int = 60


def difficulty_level(percent: float) -> tuple[str, str]:
    """Foiz bo'yicha qiyinlik darajasi nomi va rangini qaytaradi."""
    for limit, name, color in DIFFICULTY_LEVELS:
        if percent < limit:
            return name, color
    return DIFFICULTY_LEVELS[-1][1], DIFFICULTY_LEVELS[-1][2]


# --------------------------------------------------------------------------
#  Ma'lumot
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DifficultyRow:
    """Diagrammadagi bitta ustun (bitta ballanadigan birlik)."""

    label: str
    order: int
    part: str
    percent: float
    level: str
    color: str
    difficulty: float
    point_biserial: float
    #: Savolni to'g'ri topganlar soni (ustunning ko'k qismi).
    correct_count: int = 0
    #: Topa olmaganlar soni (ustunning qizil qismi).
    wrong_count: int = 0

    @property
    def total_count(self) -> int:
        """Savolga javob bergan ishtirokchilar soni."""
        return int(self.correct_count) + int(self.wrong_count)


@dataclass(frozen=True)
class DistributionBin:
    """Ballar taqsimotidagi bitta oraliq."""

    label: str
    low: float
    high: float
    count: int


@dataclass
class DifficultySummary:
    """Diagramma uchun tayyorlangan to'plam."""

    rows: list[DifficultyRow] = field(default_factory=list)
    bins: list[DistributionBin] = field(default_factory=list)
    participants: int = 0

    @property
    def has_data(self) -> bool:
        return bool(self.rows)

    @property
    def level_counts(self) -> list[tuple[str, str, int]]:
        """Har bir daraja bo'yicha savollar soni: `(nom, rang, soni)`."""
        counter = Counter(row.level for row in self.rows)
        result: list[tuple[str, str, int]] = []
        for _, name, color in DIFFICULTY_LEVELS:
            result.append((name, color, counter.get(name, 0)))
        return result

    @property
    def answer_counts(self) -> list[tuple[str, str, int]]:
        """Diagramma izohi: `(nom, rang, jami odam)`."""
        correct = sum(row.correct_count for row in self.rows)
        wrong = sum(row.wrong_count for row in self.rows)
        return [
            ("Topganlar", CORRECT_COLOR, correct),
            ("Topa olmaganlar", WRONG_COLOR, wrong),
        ]

    @property
    def hardest(self) -> list[DifficultyRow]:
        return sorted(self.rows, key=lambda row: row.percent, reverse=True)[:5]

    @property
    def easiest(self) -> list[DifficultyRow]:
        return sorted(self.rows, key=lambda row: row.percent)[:5]


def difficulty_rows(exam) -> list[DifficultyRow]:
    """
    Test savollarining qiyinlik ko'rsatkichlari.

    Ma'lumot `ExamStatistics.item_statistics` dan olinadi — u natijalar
    hisoblangandan keyin to'ldiriladi. Hisoblanmagan testda bo'sh ro'yxat
    qaytadi.
    """
    statistics = getattr(exam, "statistics", None)
    raw = list(getattr(statistics, "item_statistics", None) or [])
    if not raw:
        return []

    participants = int(getattr(statistics, "participants", 0) or 0)
    counts = Counter(int(item.get("order") or 0) for item in raw)
    rows: list[DifficultyRow] = []
    for item in raw:
        order = int(item.get("order") or 0)
        part = str(item.get("part") or "a")
        # Ikki qismli (ochiq) savol ustunlari «36(a)», «36(b)» deb belgilanadi.
        label = f"{order}({part})" if counts[order] > 1 else str(order)
        p_value = float(item.get("p_value") or 0.0)
        percent = max(0.0, min(100.0, (1.0 - p_value) * 100.0))
        level, color = difficulty_level(percent)

        # Yangi hisob-kitobda odamlar soni bevosita saqlanadi; eski
        # ma'lumotlarda esa faqat `p_value` bor — u qatnashchilar soniga
        # ko'paytiriladi.
        total = int(item.get("total") or participants or 0)
        if item.get("correct") is None:
            correct = int(round(p_value * total))
        else:
            correct = int(item.get("correct") or 0)
        correct = max(0, min(total, correct))

        rows.append(
            DifficultyRow(
                label=label,
                order=order,
                part=part,
                percent=round(percent, 1),
                level=level,
                color=color,
                difficulty=float(item.get("difficulty") or 0.0),
                point_biserial=float(item.get("point_biserial") or 0.0),
                correct_count=correct,
                wrong_count=total - correct,
            )
        )
    return rows


def ball_distribution(exam, step: float = BALL_BIN_STEP) -> list[DistributionBin]:
    """Ishtirokchilar ballarining oraliqlar bo'yicha taqsimoti."""
    from apps.attempts.models import Attempt

    values = [
        float(ball)
        for ball in Attempt.objects.filter(
            exam=exam, status=Attempt.Status.SUBMITTED
        ).values_list("ball", flat=True)
        if ball is not None
    ]
    if not values:
        return []

    step = max(0.5, float(step))
    low = math.floor(min(values) / step) * step
    high = math.ceil(max(values) / step) * step
    if high <= low:
        high = low + step

    # Juda ko'p ustun chiqmasligi uchun oraliq kengaytiriladi.
    while (high - low) / step > MAX_BINS:
        step *= 2
        low = math.floor(min(values) / step) * step
        high = math.ceil(max(values) / step) * step

    edges: list[float] = []
    current = low
    while current < high - 1e-9:
        edges.append(current)
        current += step

    bins: list[DistributionBin] = []
    for edge in edges:
        upper = edge + step
        count = sum(
            1
            for value in values
            if edge <= value < upper or (abs(upper - high) < 1e-9 and value == high)
        )
        bins.append(
            DistributionBin(
                label=f"{edge:g}–{upper:g}", low=edge, high=upper, count=count
            )
        )
    return bins


def build_summary(exam) -> DifficultySummary:
    """Panel va hisobot uchun barcha diagramma ma'lumotlarini yig'adi."""
    statistics = getattr(exam, "statistics", None)
    return DifficultySummary(
        rows=difficulty_rows(exam),
        bins=ball_distribution(exam),
        participants=int(getattr(statistics, "participants", 0) or 0),
    )


# --------------------------------------------------------------------------
#  SVG (boshqaruv paneli)
# --------------------------------------------------------------------------

_BAR_WIDTH = 20
_BAR_GAP = 6
_PAD_LEFT = 42
_PAD_RIGHT = 12
_PAD_TOP = 12
_PLOT_HEIGHT = 260
_LABEL_HEIGHT = 46

#: Ustun ichidagi son shu balandlikdan boshlab sig'adi (piksel).
_INNER_LABEL_MIN = 26


def _escape(value: object) -> str:
    """SVG matni uchun xavfsiz ko'rinish."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


#: O'q qadamini tanlashda sinab ko'riladigan ko'paytuvchilar.
_AXIS_MULTIPLIERS: tuple[float, ...] = (1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10)


def _nice_top(value: int, steps: int = 6) -> tuple[int, int]:
    """
    O'q uchun qulay yuqori chegara va qadamni tanlaydi.

    Qadam o'qishga qulay son bo'ladi, yuqori chegara esa ma'lumotdan
    ortiqcha uzoqlashmaydi: 18 ta qatnashchi uchun `(18, 3)`, 1713 ta
    uchun `(1800, 300)`.
    """
    value = max(1, int(value))
    rough = value / max(1, steps)
    magnitude = 10 ** max(0, len(str(int(rough))) - 1)
    for multiplier in _AXIS_MULTIPLIERS:
        step = max(1, int(math.ceil(magnitude * multiplier)))
        if step * steps >= value:
            return step * int(math.ceil(value / step)), step
    step = max(1, int(magnitude * 10))
    return step * int(math.ceil(value / step)), step


def _svg_frame(bars: int, y_labels: list[str]) -> tuple[int, int, list[str]]:
    """Diagramma ramkasi: o'lchamlar va gorizontal chiziqlar."""
    width = _PAD_LEFT + bars * (_BAR_WIDTH + _BAR_GAP) + _PAD_RIGHT
    height = _PAD_TOP + _PLOT_HEIGHT + _LABEL_HEIGHT
    parts: list[str] = []
    steps = len(y_labels) - 1
    for index, label in enumerate(y_labels):
        y = _PAD_TOP + _PLOT_HEIGHT - (_PLOT_HEIGHT * index / max(1, steps))
        parts.append(
            f'<line x1="{_PAD_LEFT}" y1="{y:.1f}" x2="{width - _PAD_RIGHT}" '
            f'y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{_PAD_LEFT - 6}" y="{y + 3.5:.1f}" text-anchor="end" '
            f'font-size="9" fill="{MUTED}">{_escape(label)}</text>'
        )
    return width, height, parts


def _inner_value(x: float, top: float, height: float, value: int) -> str:
    """Ustun qismining ichiga odamlar sonini tik holda yozadi."""
    if height < _INNER_LABEL_MIN or not value:
        return ""
    center_x = x + _BAR_WIDTH / 2
    center_y = top + height / 2
    return (
        f'<text x="{center_x:.1f}" y="{center_y:.1f}" font-size="10" '
        f'fill="#ffffff" text-anchor="middle" dominant-baseline="middle" '
        f'transform="rotate(-90 {center_x:.1f} {center_y:.1f})">{value}</text>'
    )


def difficulty_svg(rows: list[DifficultyRow]) -> str:
    """
    Savollar qiyinligi diagrammasi (SVG matni).

    Har bir savol bitta ustun: pastdagi ko'k qism — savolni topganlar,
    ustidagi qizil qism — topa olmaganlar. Ustunning to'liq balandligi
    qatnashchilar soniga teng, shuning uchun savollar bir-biri bilan
    bemalol solishtiriladi.
    """
    if not rows:
        return ""

    people = max((row.total_count for row in rows), default=0)
    if people <= 0:
        return ""

    axis_top, tick = _nice_top(people)
    y_labels = [str(value) for value in range(0, axis_top + 1, tick)]
    width, height, parts = _svg_frame(len(rows), y_labels)

    for index, row in enumerate(rows):
        x = _PAD_LEFT + index * (_BAR_WIDTH + _BAR_GAP)
        correct_height = _PLOT_HEIGHT * row.correct_count / axis_top
        wrong_height = _PLOT_HEIGHT * row.wrong_count / axis_top
        base = _PAD_TOP + _PLOT_HEIGHT
        correct_top = base - correct_height
        wrong_top = correct_top - wrong_height

        title = (
            f"{row.label}-savol · topgan {row.correct_count} ta · "
            f"topmagan {row.wrong_count} ta ({row.percent:g}% noto‘g‘ri) · "
            f"b = {row.difficulty:.2f}"
        )
        parts.append(
            f'<g><title>{_escape(title)}</title>'
            f'<rect x="{x}" y="{correct_top:.1f}" width="{_BAR_WIDTH}" '
            f'height="{max(0.0, correct_height):.1f}" fill="{CORRECT_COLOR}"/>'
            f'<rect x="{x}" y="{wrong_top:.1f}" width="{_BAR_WIDTH}" '
            f'height="{max(0.0, wrong_height):.1f}" fill="{WRONG_COLOR}"/>'
            f"</g>"
        )
        parts.append(_inner_value(x, correct_top, correct_height, row.correct_count))
        parts.append(_inner_value(x, wrong_top, wrong_height, row.wrong_count))

        label_x = x + _BAR_WIDTH / 2
        label_y = _PAD_TOP + _PLOT_HEIGHT + 10
        parts.append(
            f'<text x="{label_x:.1f}" y="{label_y}" font-size="9" '
            f'fill="{MUTED}" text-anchor="end" '
            f'transform="rotate(-60 {label_x:.1f} {label_y})">'
            f"{_escape(row.label)}</text>"
        )

    parts.append(
        f'<text x="{_PAD_LEFT}" y="{height - 6}" font-size="9.5" fill="{MUTED}">'
        "Ko‘k — savolni topganlar, qizil — topa olmaganlar "
        f"(jami {people} ta ishtirokchi)</text>"
    )
    return _wrap_svg(width, height, parts)


def distribution_svg(bins: list[DistributionBin]) -> str:
    """Ballar taqsimoti diagrammasi (SVG matni)."""
    if not bins:
        return ""

    peak = max(item.count for item in bins) or 1
    tick = max(1, math.ceil(peak / 5))
    y_values = list(range(0, tick * 5 + 1, tick))
    width, height, parts = _svg_frame(len(bins), [str(value) for value in y_values])
    top = y_values[-1] or 1

    step = 1 if len(bins) <= 24 else 2
    for index, item in enumerate(bins):
        x = _PAD_LEFT + index * (_BAR_WIDTH + _BAR_GAP)
        bar_height = _PLOT_HEIGHT * item.count / top
        y = _PAD_TOP + _PLOT_HEIGHT - bar_height
        parts.append(
            f'<rect x="{x}" y="{y:.1f}" width="{_BAR_WIDTH}" '
            f'height="{max(0.0, bar_height):.1f}" rx="2" fill="{BLUE}">'
            f"<title>{_escape(item.label)} ball · {item.count} ta</title></rect>"
        )
        if index % step == 0:
            label_x = x + _BAR_WIDTH / 2
            label_y = _PAD_TOP + _PLOT_HEIGHT + 10
            parts.append(
                f'<text x="{label_x:.1f}" y="{label_y}" font-size="9" '
                f'fill="{MUTED}" text-anchor="end" '
                f'transform="rotate(-60 {label_x:.1f} {label_y})">'
                f"{_escape(item.label)}</text>"
            )

    parts.append(
        f'<text x="{_PAD_LEFT}" y="{height - 6}" font-size="9.5" fill="{MUTED}">'
        "Gorizontal o‘q — ball oralig‘i, vertikal o‘q — "
        "ishtirokchilar soni</text>"
    )
    return _wrap_svg(width, height, parts)


def _wrap_svg(width: int, height: int, parts: list[str]) -> str:
    """SVG ramkasiga o'raydi."""
    return (
        f'<svg class="chart-svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img">{"".join(parts)}</svg>'
    )


# --------------------------------------------------------------------------
#  PNG (Telegram bot — adminlarga yuboriladigan hisobot)
# --------------------------------------------------------------------------

_PNG_WIDTH_MIN = 900
_PNG_HEIGHT = 660
_PNG_PLOT = 420
_PNG_LEFT = 70
_PNG_TOP = 90
_PNG_BOTTOM_LABELS = 70


def _pillow():
    """Pillow modullarini qaytaradi (o'rnatilmagan bo'lsa `None`)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # pragma: no cover - Pillow ixtiyoriy
        logger.warning("Pillow topilmadi — diagramma rasmi yaratilmaydi.")
        return None
    return Image, ImageDraw, ImageFont


def _png_fonts(ImageFont):
    """Diagramma uchun shriftlar (topilmasa — Pillow ning standarti)."""
    from apps.certificates.fonts import font_files

    regular, bold = font_files()
    try:
        if regular is None:
            raise OSError("shrift yo'q")
        return (
            ImageFont.truetype(str(regular), 15),
            ImageFont.truetype(str(bold or regular), 24),
            ImageFont.truetype(str(regular), 13),
        )
    except Exception:  # pragma: no cover - shrift o'qilmasa
        default = ImageFont.load_default()
        return default, default, default


def _png_vertical_number(
    Image, ImageDraw, canvas, font, center_x, center_y, segment_height, value
) -> None:
    """
    Ustun qismining o'rtasiga oq rangda tik son yozadi.

    Ustunlar ingichka bo'lgani uchun son 90 gradusga buriladi. Qism
    balandligi yetmasa, son butunlay yozilmaydi.
    """
    text = str(value)
    box = ImageDraw.Draw(canvas).textbbox((0, 0), text, font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    if width + 6 > segment_height:
        return
    patch = Image.new("RGBA", (width + 4, height + 4), (0, 0, 0, 0))
    ImageDraw.Draw(patch).text((2 - box[0], 2 - box[1]), text, font=font, fill="#ffffff")
    patch = patch.rotate(90, expand=True)
    canvas.paste(
        patch,
        (int(center_x - patch.width / 2), int(center_y - patch.height / 2)),
        patch,
    )


def difficulty_png(exam, rows: list[DifficultyRow] | None = None) -> bytes:
    """
    Savollar qiyinligi diagrammasini PNG ko'rinishida qaytaradi.

    Ko'rinishi panel bilan bir xil: ustunning ko'k qismi — savolni
    topganlar, qizil qismi — topa olmaganlar soni.

    Diagramma yaratib bo'lmasa (Pillow yo'q yoki ma'lumot yetarli emas)
    bo'sh `bytes` qaytadi — chaqiruvchi uni jimgina o'tkazib yuboradi.
    """
    rows = difficulty_rows(exam) if rows is None else rows
    if not rows:
        return b""

    people = max((row.total_count for row in rows), default=0)
    if people <= 0:
        return b""

    modules = _pillow()
    if modules is None:
        return b""
    Image, ImageDraw, ImageFont = modules

    bar_gap = 4
    bar_width = max(6, min(22, (_PNG_WIDTH_MIN - _PNG_LEFT - 30) // len(rows) - bar_gap))
    width = max(_PNG_WIDTH_MIN, _PNG_LEFT + len(rows) * (bar_width + bar_gap) + 30)

    image = Image.new("RGB", (width, _PNG_HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)
    regular, title_font, small = _png_fonts(ImageFont)

    draw.text(
        (_PNG_LEFT, 28), "Savollar qiyinchilik darajasi", font=title_font, fill=NAVY
    )
    draw.text(
        (_PNG_LEFT, 62),
        f"{exam.title} · test kodi {exam.code} · faqat admin uchun",
        font=small,
        fill=MUTED,
    )

    # --- To'r va o'q (odamlar soni bo'yicha) ---
    axis_top, tick = _nice_top(people)
    for value in range(0, axis_top + 1, tick):
        y = _PNG_TOP + _PNG_PLOT - _PNG_PLOT * value / axis_top
        draw.line([(_PNG_LEFT, y), (width - 24, y)], fill=GRID, width=1)
        draw.text((_PNG_LEFT - 40, y - 8), f"{value}", font=small, fill=MUTED)

    # --- Ustunlar: ko'k (topgan) + qizil (topmagan) ---
    base = _PNG_TOP + _PNG_PLOT
    labels: list[tuple[float, float, float, int]] = []
    for index, row in enumerate(rows):
        x = _PNG_LEFT + index * (bar_width + bar_gap)
        correct_height = _PNG_PLOT * row.correct_count / axis_top
        wrong_height = _PNG_PLOT * row.wrong_count / axis_top
        correct_top = base - correct_height
        wrong_top = correct_top - wrong_height
        if correct_height > 0:
            draw.rectangle(
                [(x, correct_top), (x + bar_width, base)], fill=CORRECT_COLOR
            )
            labels.append(
                (x, correct_top + correct_height / 2, correct_height, row.correct_count)
            )
        if wrong_height > 0:
            draw.rectangle(
                [(x, wrong_top), (x + bar_width, correct_top)], fill=WRONG_COLOR
            )
            labels.append(
                (x, wrong_top + wrong_height / 2, wrong_height, row.wrong_count)
            )

    # Sonlar ustun ichiga tik yoziladi — ustunlar ingichka bo'lgani uchun.
    if bar_width >= 10:
        for x, center_y, segment_height, value in labels:
            _png_vertical_number(
                Image, ImageDraw, image, small,
                x + bar_width / 2, center_y, segment_height, value,
            )

    # --- Yorliqlar (sig'gani qadar) ---
    step = max(1, math.ceil(26 / (bar_width + bar_gap)))
    for index, row in enumerate(rows):
        if index % step:
            continue
        x = _PNG_LEFT + index * (bar_width + bar_gap)
        draw.text(
            (x, _PNG_TOP + _PNG_PLOT + 8), row.label, font=small, fill=MUTED
        )

    # --- Izoh ---
    legend_y = _PNG_TOP + _PNG_PLOT + _PNG_BOTTOM_LABELS
    x = _PNG_LEFT
    for name, color, count in (
        ("Topganlar", CORRECT_COLOR, sum(row.correct_count for row in rows)),
        ("Topa olmaganlar", WRONG_COLOR, sum(row.wrong_count for row in rows)),
    ):
        draw.rectangle([(x, legend_y), (x + 16, legend_y + 16)], fill=color)
        text = f"{name} — {count} ta javob"
        draw.text((x + 22, legend_y), text, font=regular, fill=NAVY)
        x += 26 + int(draw.textlength(text, font=regular))

    draw.text(
        (_PNG_LEFT, legend_y + 34),
        f"Ustun balandligi — {people} ta ishtirokchi. Ko‘k qism savolni "
        "topganlar, qizil qism topa olmaganlar soni.",
        font=small,
        fill=MUTED,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def distribution_png(exam, bins: list[DistributionBin] | None = None) -> bytes:
    """Ballar taqsimoti diagrammasi (PNG)."""
    bins = ball_distribution(exam) if bins is None else bins
    if not bins:
        return b""

    modules = _pillow()
    if modules is None:
        return b""
    Image, ImageDraw, ImageFont = modules

    bar_gap = 6
    bar_width = max(8, min(30, (_PNG_WIDTH_MIN - _PNG_LEFT - 30) // len(bins) - bar_gap))
    width = max(_PNG_WIDTH_MIN, _PNG_LEFT + len(bins) * (bar_width + bar_gap) + 30)

    image = Image.new("RGB", (width, _PNG_HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)
    regular, title_font, small = _png_fonts(ImageFont)

    draw.text((_PNG_LEFT, 28), "Ballar taqsimoti", font=title_font, fill=NAVY)
    draw.text(
        (_PNG_LEFT, 62),
        f"{exam.title} · test kodi {exam.code} · faqat admin uchun",
        font=small,
        fill=MUTED,
    )

    peak = max(item.count for item in bins) or 1
    tick = max(1, math.ceil(peak / 5))
    top_value = tick * 5
    for index in range(6):
        value = tick * index
        y = _PNG_TOP + _PNG_PLOT - _PNG_PLOT * value / top_value
        draw.line([(_PNG_LEFT, y), (width - 24, y)], fill=GRID, width=1)
        draw.text((_PNG_LEFT - 34, y - 8), f"{value}", font=small, fill=MUTED)

    for index, item in enumerate(bins):
        x = _PNG_LEFT + index * (bar_width + bar_gap)
        bar_height = _PNG_PLOT * item.count / top_value
        top = _PNG_TOP + _PNG_PLOT - bar_height
        draw.rectangle(
            [(x, top), (x + bar_width, _PNG_TOP + _PNG_PLOT)],
            fill=BLUE,
            outline=BLUE_SOFT,
        )

    step = max(1, math.ceil(52 / (bar_width + bar_gap)))
    for index, item in enumerate(bins):
        if index % step:
            continue
        x = _PNG_LEFT + index * (bar_width + bar_gap)
        draw.text((x, _PNG_TOP + _PNG_PLOT + 8), item.label, font=small, fill=MUTED)

    draw.text(
        (_PNG_LEFT, _PNG_TOP + _PNG_PLOT + _PNG_BOTTOM_LABELS),
        "Gorizontal o‘q — ball oralig‘i, vertikal o‘q — "
        "ishtirokchilar soni.",
        font=small,
        fill=MUTED,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


__all__ = [
    "DIFFICULTY_LEVELS",
    "CORRECT_COLOR",
    "WRONG_COLOR",
    "DifficultyRow",
    "DistributionBin",
    "DifficultySummary",
    "difficulty_level",
    "difficulty_rows",
    "ball_distribution",
    "build_summary",
    "difficulty_svg",
    "distribution_svg",
    "difficulty_png",
    "distribution_png",
]
