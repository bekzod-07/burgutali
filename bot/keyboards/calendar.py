"""
Inline kalendar — sana, soat va daqiqani tanlash.

Test tugash vaqtini belgilashda ishlatiladi: foydalanuvchi oyni varaqlaydi,
kunni bosadi, so'ng soat va daqiqani tanlaydi (masalan, 21:30).

Uch bosqich, uchtasi ham bitta xabar ichida almashadi:

    oy jadvali  ->  soatlar jadvali  ->  daqiqalar jadvali

Emoji ishlatilmaydi — faqat matn va tipografik belgilar.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from django.utils import timezone

from bot.keyboards.factories import CalendarCB, CreateCB, MenuCB
from bot.texts import common as TC

#: Oy nomlari (1 dan boshlab indekslanadi).
MONTHS: tuple[str, ...] = (
    "",
    "Yanvar",
    "Fevral",
    "Mart",
    "Aprel",
    "May",
    "Iyun",
    "Iyul",
    "Avgust",
    "Sentabr",
    "Oktabr",
    "Noyabr",
    "Dekabr",
)

#: Hafta kunlari — dushanbadan boshlab.
WEEKDAYS: tuple[str, ...] = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")

#: Daqiqa qadami (00, 05, 10 ... 55).
MINUTE_STEP: int = 5


def _noop() -> str:
    """Hech narsa qilmaydigan tugma uchun callback."""
    return CalendarCB(action="noop").pack()


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Oyni `delta` ga suradi va (yil, oy) qaytaradi."""
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def today_local() -> date:
    """Mahalliy vaqt zonasidagi bugungi sana."""
    return timezone.localtime().date()


# ==========================================================================
#  1-bosqich: oy jadvali
# ==========================================================================


def month_keyboard(year: int = 0, month: int = 0) -> InlineKeyboardMarkup:
    """Kun tanlash jadvali. O'tib ketgan kunlar bosilmaydi."""
    today = today_local()
    year = year or today.year
    month = month or today.month

    builder = InlineKeyboardBuilder()

    # --- Sarlavha: ‹  Avgust 2026  › ---
    previous_year, previous_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, +1)
    first_of_month = date(year, month, 1)
    can_go_back = first_of_month > date(today.year, today.month, 1)

    builder.row(
        InlineKeyboardButton(
            text="‹" if can_go_back else " ",
            callback_data=(
                CalendarCB(action="nav", year=previous_year, month=previous_month).pack()
                if can_go_back
                else _noop()
            ),
        ),
        InlineKeyboardButton(text=f"{MONTHS[month]} {year}", callback_data=_noop()),
        InlineKeyboardButton(
            text="›",
            callback_data=CalendarCB(action="nav", year=next_year, month=next_month).pack(),
        ),
    )

    # --- Hafta kunlari ---
    builder.row(
        *[InlineKeyboardButton(text=name, callback_data=_noop()) for name in WEEKDAYS]
    )

    # --- Kunlar ---
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data=_noop()))
                continue
            current = date(year, month, day)
            if current < today:
                # O'tib ketgan kun — tanlanmaydi.
                row.append(InlineKeyboardButton(text="·", callback_data=_noop()))
                continue
            label = f"[{day}]" if current == today else str(day)
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=CalendarCB(
                        action="day", year=year, month=month, day=day
                    ).pack(),
                )
            )
        builder.row(*row)

    # --- Tez tanlovlar ---
    builder.row(
        InlineKeyboardButton(
            text="Cheklovsiz", callback_data=CreateCB(action="duration", value="0").pack()
        ),
        InlineKeyboardButton(
            text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel").pack()
        ),
    )
    return builder.as_markup()


# ==========================================================================
#  2-bosqich: soat
# ==========================================================================


def hours_keyboard(year: int, month: int, day: int) -> InlineKeyboardMarkup:
    """Soat tanlash jadvali (00–23)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"{day:02d}.{month:02d}.{year} — soatni tanlang",
            callback_data=_noop(),
        )
    )

    row: list[InlineKeyboardButton] = []
    for hour in range(24):
        row.append(
            InlineKeyboardButton(
                text=f"{hour:02d}",
                callback_data=CalendarCB(
                    action="hour", year=year, month=month, day=day, hour=hour
                ).pack(),
            )
        )
        if len(row) == 6:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    builder.row(
        InlineKeyboardButton(
            text="‹ Sana",
            callback_data=CalendarCB(action="nav", year=year, month=month).pack(),
        ),
        InlineKeyboardButton(
            text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel").pack()
        ),
    )
    return builder.as_markup()


# ==========================================================================
#  3-bosqich: daqiqa
# ==========================================================================


def minutes_keyboard(year: int, month: int, day: int, hour: int) -> InlineKeyboardMarkup:
    """Daqiqa tanlash jadvali (00, 05, ... 55)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"{day:02d}.{month:02d}.{year} {hour:02d}:__ — daqiqani tanlang",
            callback_data=_noop(),
        )
    )

    row: list[InlineKeyboardButton] = []
    for minute in range(0, 60, MINUTE_STEP):
        row.append(
            InlineKeyboardButton(
                text=f"{hour:02d}:{minute:02d}",
                callback_data=CalendarCB(
                    action="minute",
                    year=year,
                    month=month,
                    day=day,
                    hour=hour,
                    minute=minute,
                ).pack(),
            )
        )
        if len(row) == 4:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    builder.row(
        InlineKeyboardButton(
            text="‹ Soat",
            callback_data=CalendarCB(
                action="back_hours", year=year, month=month, day=day
            ).pack(),
        ),
        InlineKeyboardButton(
            text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel").pack()
        ),
    )
    return builder.as_markup()


# ==========================================================================
#  Yordamchi
# ==========================================================================


def build_datetime(year: int, month: int, day: int, hour: int, minute: int):
    """
    Tanlangan sana-vaqtdan vaqt zonasi bilan `datetime` yasaydi.

    Noto'g'ri sana berilsa (masalan, 31-fevral) `None` qaytaradi.
    """
    try:
        naive = datetime(year, month, day, hour, minute)
    except ValueError:
        return None
    current_zone = timezone.get_current_timezone()
    try:
        return timezone.make_aware(naive, current_zone)
    except Exception:  # pragma: no cover - DST o'tish oralig'i
        return timezone.make_aware(naive + timedelta(hours=1), current_zone)


__all__ = [
    "MONTHS",
    "WEEKDAYS",
    "MINUTE_STEP",
    "month_keyboard",
    "hours_keyboard",
    "minutes_keyboard",
    "build_datetime",
    "today_local",
]
