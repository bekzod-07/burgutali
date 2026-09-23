"""Matnlarni chiroyli ko'rinishda shakllantirish."""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from core.text_utils import esc, shorten

# ==========================================================================
#  Vaqt
# ==========================================================================


def format_datetime(value: datetime | None, default: str = "cheklanmagan") -> str:
    """Sana va vaqtni mahalliy vaqt zonasida formatlaydi."""
    if value is None:
        return default
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")


def format_duration(seconds: int) -> str:
    """Sekundlarni «12 daq 30 s» ko'rinishiga o'giradi."""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} soat")
    if minutes:
        parts.append(f"{minutes} daq")
    if secs or not parts:
        parts.append(f"{secs} s")
    return " ".join(parts)


def format_remaining(ends_at: datetime | None) -> str:
    """Test tugashiga qolgan vaqtni qaytaradi."""
    if ends_at is None:
        return "cheklanmagan"
    delta = ends_at - timezone.now()
    if delta.total_seconds() <= 0:
        return "vaqt tugagan"
    return format_duration(int(delta.total_seconds()))


# ==========================================================================
#  Test
# ==========================================================================


def exam_type_label(exam_type: str) -> str:
    """Test turining qisqa yozuvi."""
    return {
        "simple": "1-tur",
        "rasch_free": "2-tur",
        "rasch_paid": "3-tur",
    }.get(exam_type, "Test")


def status_label(status: str) -> str:
    """Test holatining qisqa yozuvi."""
    return {
        "draft": "Qoralama",
        "active": "Faol",
        "closed": "Yopilgan",
        "calculated": "Hisoblangan",
        "published": "E'lon qilingan",
        "archived": "Arxivlangan",
    }.get(status, status)


# ==========================================================================
#  Reyting va javoblar
# ==========================================================================


def rating_rows(rows, *, uses_rasch: bool, highlight_id: int | None = None) -> str:
    """
    Reyting jadvalini matn ko'rinishida yig'adi.

    `rows` — `apps.attempts.services.result_rows()` qatorlari: haqiqiy
    qatnashchilar va e'lon uchun qo'shilgan soxta qatnashchilar birga.
    Nom har uchala test turida ham ism-familiya.
    """
    if not rows:
        return "Hozircha qatnashchilar yo'q."

    lines: list[str] = []
    for item in rows:
        name = esc(shorten(item.label or "Ishtirokchi", 26))
        if uses_rasch:
            grade = f" · {item.grade}" if item.grade else ""
            row = f"{item.place}. <b>{name}</b> — {item.display_ball}{grade}"
        else:
            row = f"{item.place}. <b>{name}</b> — {item.percent:.0f}%"
        attempt = item.attempt
        if highlight_id and attempt is not None and attempt.id == highlight_id:
            row = f"<b>›</b> {row}"
        lines.append(row)
    return "\n".join(lines)


def review_rows(rows: list[dict], *, show_correct: bool) -> str:
    """Javoblarni ko'rib chiqish jadvali."""
    if not rows:
        return "Javoblar yo'q."

    lines: list[str] = []
    for row in rows:
        given = esc(shorten(str(row["given"]), 24))
        if show_correct and row["correct"] and row["correct"] != "—":
            correct = esc(shorten(str(row["correct"]), 24))
            lines.append(
                f"{row['icon']} <b>{row['order']}.</b> {given}  "
                f"<i>(to‘g‘ri: {correct})</i>"
            )
        else:
            lines.append(f"{row['icon']} <b>{row['order']}.</b> {given}")
    return "\n".join(lines)


def answers_overview(orders: list[int], answered: set[int], per_line: int = 10) -> str:
    """
    Savollar bo'yicha javob berilgan/berilmagan holatini ko'rsatadi.

    Javob berilgan savol qalin, berilmagani oddiy shriftda yoziladi.
    """
    lines: list[str] = []
    buffer: list[str] = []
    for order in orders:
        buffer.append(f"<b>{order}</b>" if order in answered else f"<code>{order}</code>")
        if len(buffer) >= per_line:
            lines.append(" ".join(buffer))
            buffer = []
    if buffer:
        lines.append(" ".join(buffer))
    lines.append("")
    lines.append("<b>qalin</b> — javob berilgan, <code>oddiy</code> — javobsiz")
    return "\n".join(lines)


def exam_card(summary: dict, *, extra: str = "") -> str:
    """Test haqidagi qisqa ma'lumot kartochkasi."""
    return (
        f"<b>{esc(summary['title'])}</b>\n\n"
        f"Kod: <code>{summary['code']}</code>\n"
        f"Turi: {esc(summary['type'])}\n"
        f"Savollar: {summary['questions']} ta\n"
        f"Qatnashganlar: {summary['participants']} ta\n"
        f"Tugash vaqti: {format_datetime(summary.get('ends_at'))}\n"
        f"{extra}"
    )


__all__ = [
    "format_datetime",
    "format_duration",
    "format_remaining",
    "exam_type_label",
    "status_label",
    "rating_rows",
    "review_rows",
    "answers_overview",
    "exam_card",
]
