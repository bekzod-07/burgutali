"""
Callback ma'lumotlari fabrikalari (aiogram 3 `CallbackData`).

Har bir inline tugma o'zining tuzilgan (typed) callback ma'lumotiga ega —
bu satrlarni qo'lda tahlil qilishdan qutqaradi va xatolarni kamaytiradi.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    """Umumiy menyu harakatlari."""

    action: str  # start, main, help, cancel, noop


class SubscriptionCB(CallbackData, prefix="sub"):
    """Majburiy obuna tekshiruvi."""

    action: str  # check


class CreateCB(CallbackData, prefix="crt"):
    """Test yaratish sehrgari."""

    action: str  # type, structure, count, duration, visibility, certificate, keys_skip
    value: str = ""


class ExamCB(CallbackData, prefix="exam"):
    """Test ustidagi amallar."""

    action: str  # open, take, manage, activate, close, calc, publish,
                 # rating, xlsx, pdf, codes, certs, archive, results
    exam_id: int


class QuestionCB(CallbackData, prefix="q"):
    """Test topshirishdagi savol tugmalari."""

    action: str  # pick, toggle, confirm, prev, next, jump, review, finish, clear
    order: int = 0
    value: str = ""


class AttemptCB(CallbackData, prefix="att"):
    """Natijalar bilan bog'liq amallar."""

    action: str  # open, answers, rating, certificate
    attempt_id: int


class CodesCB(CallbackData, prefix="code"):
    """ID kodlar yaratish."""

    action: str  # exam, quantity, custom
    exam_id: int = 0
    quantity: int = 0


class CalendarCB(CallbackData, prefix="cal"):
    """
    Sana va vaqtni tanlash (test tugash vaqti uchun).

    Bosqichlar: oy varaqlash -> kun -> soat -> daqiqa.
    """

    action: str  # nav, day, hour, minute, back_days, back_hours, noop
    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0


class PageCB(CallbackData, prefix="pg"):
    """Ro'yxatlarda sahifalash."""

    scope: str  # exams, my_exams, results, certificates
    page: int = 1


__all__ = [
    "MenuCB",
    "SubscriptionCB",
    "CreateCB",
    "ExamCB",
    "QuestionCB",
    "AttemptCB",
    "CodesCB",
    "CalendarCB",
    "PageCB",
]
