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

#: Rasm kamida shuncha keng bo'ladi (savol kam bo'lsa ustunlar kengayadi).
_PNG_MIN_WIDTH = 1240

#: Bitta ustunga ajratiladigan joy (ustun + oraliq) chegaralari.
_PNG_SLOT_MIN = 48
_PNG_SLOT_MAX = 96

#: Ustun eni — unga ajratilgan joyning shuncha ulushi.
_PNG_BAR_RATIO = 0.78

_PNG_LEFT = 128
_PNG_RIGHT = 56
_PNG_TOP = 178
_PNG_PLOT = 820
_PNG_XLABELS = 150
_PNG_LEGEND = 132

#: Ustun ichidagi son shu balandlikdan boshlab sig'adi (piksel).
_PNG_INNER_MIN = 46


def _pillow():
    """Pillow modullarini qaytaradi (o'rnatilmagan bo'lsa `None`)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # pragma: no cover - Pillow ixtiyoriy
        logger.warning("Pillow topilmadi — diagramma rasmi yaratilmaydi.")
        return None
    return Image, ImageDraw, ImageFont


def _png_font_factory(ImageFont):
    """
    Kerakli o'lchamdagi shriftni qaytaruvchi funksiya.

    Diagramma katta chizilgani uchun sarlavha, o'q va ustun ichidagi
    sonlar turli o'lchamda bo'ladi. Shrift topilmasa Pillow ning
    standart shrifti ishlatiladi (o'lcham o'zgarmaydi).
    """
    from apps.certificates.fonts import font_files

    regular, bold = font_files()

    def font(size: int, *, bold_face: bool = False):
        try:
            if regular is None:
                raise OSError("shrift yo'q")
            path = (bold or regular) if bold_face else regular
            return ImageFont.truetype(str(path), size)
        except Exception:  # pragma: no cover - shrift o'qilmasa
            return ImageFont.load_default()

    return font


def _png_layout(count: int) -> tuple[int, int, int, int]:
    """
    Diagramma o'lchamlarini savollar soniga qarab hisoblaydi.

    Qaytaradi: `(rasm eni, rasm bo'yi, ustun eni, ustunga ajratilgan joy)`.
    Savollar ko'p bo'lsa rasm kengayadi — ustunlar siqilib, yorliqlar
    ustma-ust tushib qolmaydi.
    """
    count = max(1, int(count))
    plot_min = _PNG_MIN_WIDTH - _PNG_LEFT - _PNG_RIGHT
    slot = int(min(_PNG_SLOT_MAX, max(_PNG_SLOT_MIN, plot_min / count)))
    bar_width = max(10, int(slot * _PNG_BAR_RATIO))
    width = max(_PNG_MIN_WIDTH, _PNG_LEFT + count * slot + _PNG_RIGHT)
    height = _PNG_TOP + _PNG_PLOT + _PNG_XLABELS + _PNG_LEGEND
    return width, height, bar_width, slot


def _png_rotated_text(
    Image, ImageDraw, canvas, font, text: str, color: str, angle: int
):
    """Burilgan matnni alohida qatlamda tayyorlaydi (Pillow matnni burmaydi)."""
    box = ImageDraw.Draw(canvas).textbbox((0, 0), text, font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    patch = Image.new("RGBA", (width + 6, height + 6), (0, 0, 0, 0))
    ImageDraw.Draw(patch).text((3 - box[0], 3 - box[1]), text, font=font, fill=color)
    return patch.rotate(angle, expand=True, resample=Image.BICUBIC)


def _png_vertical_number(
    Image, ImageDraw, canvas, font, center_x, center_y, segment_height, value
) -> None:
    """
    Ustun qismining o'rtasiga oq rangda tik son yozadi.

    Ustunlar ingichka bo'lgani uchun son 90 gradusga buriladi. Qism
    balandligi yetmasa, son butunlay yozilmaydi.
    """
    text = str(value)
    patch = _png_rotated_text(Image, ImageDraw, canvas, font, text, "#ffffff", 90)
    if patch.height > segment_height - 6:
        return
    canvas.paste(
        patch,
        (int(center_x - patch.width / 2), int(center_y - patch.height / 2)),
        patch,
    )


def _png_axis_label(
    Image, ImageDraw, canvas, font, center_x, top_y, text: str
) -> None:
    """Gorizontal o'qdagi savol raqamini yozadi (kerak bo'lsa buriladi)."""
    box = ImageDraw.Draw(canvas).textbbox((0, 0), text, font=font)
    patch = _png_rotated_text(Image, ImageDraw, canvas, font, text, MUTED, 60)
    canvas.paste(patch, (int(center_x - patch.width + 8), int(top_y)), patch)
    del box


def difficulty_png(exam, rows: list[DifficultyRow] | None = None) -> bytes:
    """
    Savollar qiyinligi diagrammasini PNG ko'rinishida qaytaradi.

    Ko'rinishi panel bilan bir xil: ustunning ko'k qismi — savolni
    topganlar, qizil qismi — topa olmaganlar soni. Rasm savollar soniga
    qarab kengayadi, shuning uchun 55 ta birlikda ham ustunlar va
    yorliqlar bemalol o'qiladi.

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

    width, height, bar_width, slot = _png_layout(len(rows))
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)

    font = _png_font_factory(ImageFont)
    title_font = font(42, bold_face=True)
    subtitle_font = font(24)
    axis_font = font(24)
    legend_font = font(26)
    note_font = font(22)
    label_font = font(24)
    value_font = font(22)

    draw.text((_PNG_LEFT, 44), "Savollar qiyinchilik darajasi",
              font=title_font, fill=NAVY)
    draw.text(
        (_PNG_LEFT, 106),
        f"{exam.title} · test kodi {exam.code} · faqat admin uchun",
        font=subtitle_font, fill=MUTED,
    )

    # --- To'r va o'q (odamlar soni bo'yicha) ---
    axis_top, tick = _nice_top(people)
    base = _PNG_TOP + _PNG_PLOT
    for value in range(0, axis_top + 1, tick):
        y = base - _PNG_PLOT * value / axis_top
        draw.line([(_PNG_LEFT, y), (width - _PNG_RIGHT, y)], fill=GRID, width=2)
        text = str(value)
        text_width = draw.textlength(text, font=axis_font)
        draw.text((_PNG_LEFT - 18 - text_width, y - 15), text,
                  font=axis_font, fill=MUTED)

    # --- Ustunlar: ko'k (topgan) + qizil (topmagan) ---
    labels: list[tuple[float, float, float, int]] = []
    for index, row in enumerate(rows):
        x = _PNG_LEFT + index * slot + (slot - bar_width) / 2
        correct_height = _PNG_PLOT * row.correct_count / axis_top
        wrong_height = _PNG_PLOT * row.wrong_count / axis_top
        correct_top = base - correct_height
        wrong_top = correct_top - wrong_height
        if correct_height > 0:
            draw.rectangle([(x, correct_top), (x + bar_width, base)],
                           fill=CORRECT_COLOR)
            labels.append(
                (x, correct_top + correct_height / 2, correct_height, row.correct_count)
            )
        if wrong_height > 0:
            draw.rectangle([(x, wrong_top), (x + bar_width, correct_top)],
                           fill=WRONG_COLOR)
            labels.append(
                (x, wrong_top + wrong_height / 2, wrong_height, row.wrong_count)
            )

        # Savol raqami — har bir ustun ostida, burilgan holda.
        _png_axis_label(
            Image, ImageDraw, image, label_font,
            x + bar_width / 2 + 10, base + 16, row.label,
        )

    # Sonlar ustun ichiga tik yoziladi.
    for x, center_y, segment_height, value in labels:
        if segment_height < _PNG_INNER_MIN:
            continue
        _png_vertical_number(
            Image, ImageDraw, image, value_font,
            x + bar_width / 2, center_y, segment_height, value,
        )

    # --- Izoh ---
    legend_y = base + _PNG_XLABELS
    x = _PNG_LEFT
    for name, color, count in (
        ("Topganlar", CORRECT_COLOR, sum(row.correct_count for row in rows)),
        ("Topa olmaganlar", WRONG_COLOR, sum(row.wrong_count for row in rows)),
    ):
        draw.rectangle([(x, legend_y), (x + 28, legend_y + 28)], fill=color)
        text = f"{name} — {count} ta javob"
        draw.text((x + 40, legend_y), text, font=legend_font, fill=NAVY)
        x += 74 + int(draw.textlength(text, font=legend_font))

    draw.text(
        (_PNG_LEFT, legend_y + 58),
        f"Ustun balandligi — {people} ta ishtirokchi. Ko‘k qism savolni "
        "topganlar, qizil qism topa olmaganlar soni.",
        font=note_font, fill=MUTED,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def distribution_png(exam, bins: list[DistributionBin] | None = None) -> bytes:
    """
    Ballar taqsimoti diagrammasi (PNG).

    Qiyinchilik diagrammasi bilan bir xil o'lchamda chiziladi — oraliqlar
    ko'p bo'lsa rasm kengayadi va yorliqlar ustma-ust tushmaydi.
    """
    bins = ball_distribution(exam) if bins is None else bins
    if not bins:
        return b""

    modules = _pillow()
    if modules is None:
        return b""
    Image, ImageDraw, ImageFont = modules

    width, height, bar_width, slot = _png_layout(len(bins))
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)

    font = _png_font_factory(ImageFont)
    title_font = font(42, bold_face=True)
    subtitle_font = font(24)
    axis_font = font(24)
    note_font = font(22)
    label_font = font(22)
    value_font = font(22)

    draw.text((_PNG_LEFT, 44), "Ballar taqsimoti", font=title_font, fill=NAVY)
    draw.text(
        (_PNG_LEFT, 106),
        f"{exam.title} · test kodi {exam.code} · faqat admin uchun",
        font=subtitle_font, fill=MUTED,
    )

    peak = max(item.count for item in bins) or 1
    axis_top, tick = _nice_top(peak)
    base = _PNG_TOP + _PNG_PLOT
    for value in range(0, axis_top + 1, tick):
        y = base - _PNG_PLOT * value / axis_top
        draw.line([(_PNG_LEFT, y), (width - _PNG_RIGHT, y)], fill=GRID, width=2)
        text = str(value)
        text_width = draw.textlength(text, font=axis_font)
        draw.text((_PNG_LEFT - 18 - text_width, y - 15), text,
                  font=axis_font, fill=MUTED)

    for index, item in enumerate(bins):
        x = _PNG_LEFT + index * slot + (slot - bar_width) / 2
        bar_height = _PNG_PLOT * item.count / axis_top
        top = base - bar_height
        if bar_height > 0:
            draw.rectangle([(x, top), (x + bar_width, base)], fill=BLUE)
            # Ishtirokchilar soni kichik son — ustun ustiga to'g'ri yoziladi.
            text = str(item.count)
            text_width = draw.textlength(text, font=value_font)
            draw.text(
                (x + bar_width / 2 - text_width / 2, top - 34),
                text, font=value_font, fill=NAVY,
            )
        _png_axis_label(
            Image, ImageDraw, image, label_font,
            x + bar_width / 2 + 10, base + 16, item.label,
        )

    draw.text(
        (_PNG_LEFT, base + _PNG_XLABELS),
        "Gorizontal o‘q — ball oralig‘i, vertikal o‘q — "
        "ishtirokchilar soni.",
        font=note_font, fill=MUTED,
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
