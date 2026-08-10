"""
Test yaratish: tugash vaqti, natijalar ko'rinishi va sertifikat sozlamalari.

TZ (1-tur): "Test yaratuvchi natijani qatnashchilarga ko'rinadigan yoki
ko'rinmaydigan qilib belgilashi, testning tugash vaqtini belgilay olishi
mumkin".

Tugash vaqtini uch xil usulda berish mumkin:
  * tayyor variant (1 soat, 24 soat, 7 kun ...);
  * qo'lda yozilgan soatlar soni;
  * kalendardan aniq sana, soat va daqiqa (masalan, 21:30).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from django.utils import timezone

from bot.keyboards import calendar as cal
from bot.keyboards import inline
from bot.keyboards.factories import CalendarCB, CreateCB
from bot.states import CreateExamStates
from bot.texts import exam as TE
from bot.utils.formatting import format_datetime

router = Router(name="create.settings")


# ==========================================================================
#  Tugash vaqti
# ==========================================================================


async def ask_duration(message: Message, state: FSMContext) -> None:
    """Test tugash vaqtini so'raydi."""
    await state.set_state(CreateExamStates.choosing_duration)
    await message.answer(TE.ASK_DURATION, reply_markup=inline.durations())


@router.callback_query(
    StateFilter(CreateExamStates.choosing_duration),
    CreateCB.filter(F.action == "duration"),
)
async def choose_duration(
    callback: CallbackQuery, callback_data: CreateCB, state: FSMContext
) -> None:
    """Tayyor variantlardan davomiylik tanlandi."""
    await callback.answer()
    try:
        hours = int(callback_data.value)
    except ValueError:
        hours = 0
    await state.update_data(duration_hours=hours, ends_at_iso="")
    await _ask_visibility(callback.message, state)


@router.message(StateFilter(CreateExamStates.choosing_duration), F.text)
async def receive_custom_duration(message: Message, state: FSMContext) -> None:
    """Qo'lda yozilgan soatlar soni."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Soatlar sonini raqam bilan yozing (masalan: 48).")
        return
    hours = min(int(raw), 24 * 365)
    await state.update_data(duration_hours=hours, ends_at_iso="")
    await _ask_visibility(message, state)


# ==========================================================================
#  Kalendar: sana -> soat -> daqiqa
# ==========================================================================


@router.callback_query(
    StateFilter(CreateExamStates.choosing_duration),
    CreateCB.filter(F.action == "calendar"),
)
async def open_calendar(callback: CallbackQuery, state: FSMContext) -> None:
    """«Sana va vaqtni tanlash» — kalendarni ochadi."""
    await callback.answer()
    await _edit(callback, TE.ASK_END_DATE, cal.month_keyboard())


@router.callback_query(CalendarCB.filter(F.action == "noop"))
async def calendar_noop(callback: CallbackQuery) -> None:
    """Bo'sh katak yoki sarlavha bosildi."""
    await callback.answer()


@router.callback_query(
    StateFilter(CreateExamStates.choosing_duration),
    CalendarCB.filter(F.action == "nav"),
)
async def calendar_navigate(
    callback: CallbackQuery, callback_data: CalendarCB, state: FSMContext
) -> None:
    """Oyni varaqlash (yoki soatlar jadvalidan sanaga qaytish)."""
    await callback.answer()
    await _edit(
        callback,
        TE.ASK_END_DATE,
        cal.month_keyboard(callback_data.year, callback_data.month),
    )


@router.callback_query(
    StateFilter(CreateExamStates.choosing_duration),
    CalendarCB.filter(F.action.in_({"day", "back_hours"})),
)
async def calendar_pick_day(
    callback: CallbackQuery, callback_data: CalendarCB, state: FSMContext
) -> None:
    """Kun tanlandi — soatlar jadvali ko'rsatiladi."""
    await callback.answer()
    label = f"{callback_data.day:02d}.{callback_data.month:02d}.{callback_data.year}"
    await _edit(
        callback,
        TE.ASK_END_HOUR.format(date=label),
        cal.hours_keyboard(callback_data.year, callback_data.month, callback_data.day),
    )


@router.callback_query(
    StateFilter(CreateExamStates.choosing_duration),
    CalendarCB.filter(F.action == "hour"),
)
async def calendar_pick_hour(
    callback: CallbackQuery, callback_data: CalendarCB, state: FSMContext
) -> None:
    """Soat tanlandi — daqiqalar jadvali ko'rsatiladi."""
    await callback.answer()
    label = f"{callback_data.day:02d}.{callback_data.month:02d}.{callback_data.year}"
    await _edit(
        callback,
        TE.ASK_END_MINUTE.format(date=label, hour=f"{callback_data.hour:02d}"),
        cal.minutes_keyboard(
            callback_data.year, callback_data.month, callback_data.day, callback_data.hour
        ),
    )


@router.callback_query(
    StateFilter(CreateExamStates.choosing_duration),
    CalendarCB.filter(F.action == "minute"),
)
async def calendar_pick_minute(
    callback: CallbackQuery, callback_data: CalendarCB, state: FSMContext
) -> None:
    """Daqiqa tanlandi — tugash vaqti to'liq belgilandi."""
    await callback.answer()

    moment = cal.build_datetime(
        callback_data.year,
        callback_data.month,
        callback_data.day,
        callback_data.hour,
        callback_data.minute,
    )
    if moment is None or moment <= timezone.now():
        await callback.message.answer(TE.END_TIME_IN_PAST)
        await _edit(
            callback,
            TE.ASK_END_DATE,
            cal.month_keyboard(callback_data.year, callback_data.month),
        )
        return

    hours = max(0, int((moment - timezone.now()).total_seconds() // 3600))
    await state.update_data(ends_at_iso=moment.isoformat(), duration_hours=hours)

    await callback.message.answer(
        TE.END_TIME_SET.format(moment=format_datetime(moment))
    )
    await _ask_visibility(callback.message, state)


async def _edit(callback: CallbackQuery, text: str, markup) -> None:
    """Kalendar xabarini o'rnida yangilaydi (imkoni bo'lmasa — yangisini yuboradi)."""
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:  # pragma: no cover - xabar o'zgarmagan bo'lishi mumkin
        await callback.message.answer(text, reply_markup=markup)


# ==========================================================================
#  Natijalar ko'rinishi
# ==========================================================================


async def _ask_visibility(message: Message, state: FSMContext) -> None:
    """Natijalar qatnashchilarga ko'rinishini so'raydi."""
    await state.set_state(CreateExamStates.choosing_visibility)
    await message.answer(
        TE.ASK_VISIBILITY,
        reply_markup=inline.yes_no("visibility"),
    )


@router.callback_query(
    StateFilter(CreateExamStates.choosing_visibility),
    CreateCB.filter(F.action == "visibility"),
)
async def choose_visibility(
    callback: CallbackQuery, callback_data: CreateCB, state: FSMContext, user
) -> None:
    """Natijalar ko'rinishi tanlandi."""
    await callback.answer()
    show_results = callback_data.value == "1"
    await state.update_data(show_results=show_results)

    data = await state.get_data()
    if data.get("exam_type") == "rasch_paid":
        await state.set_state(CreateExamStates.choosing_certificate)
        await callback.message.answer(
            TE.ASK_CERTIFICATE, reply_markup=inline.yes_no("certificate")
        )
        return

    from .finalize import finish_creation

    await finish_creation(callback.message, state, user)


# ==========================================================================
#  Sertifikat
# ==========================================================================


@router.callback_query(
    StateFilter(CreateExamStates.choosing_certificate),
    CreateCB.filter(F.action == "certificate"),
)
async def choose_certificate(
    callback: CallbackQuery, callback_data: CreateCB, state: FSMContext, user
) -> None:
    """Sertifikat berish yoki bermaslik tanlandi."""
    await callback.answer()
    await state.update_data(certificate=callback_data.value == "1")

    from .finalize import finish_creation

    await finish_creation(callback.message, state, user)


__all__ = ["router", "ask_duration"]
