"""Inline klaviaturalar — emojisiz, matnli tugmalar."""

from __future__ import annotations

from urllib.parse import urlencode

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import get_config
from bot.texts import admin as TA
from bot.texts import common as TC
from bot.texts import exam as TE
from bot.texts import start as TS
from core import constants as C

from .factories import (
    AttemptCB,
    CodesCB,
    CreateCB,
    ExamCB,
    MenuCB,
    QuestionCB,
    SubscriptionCB,
)


# ==========================================================================
#  Web ilova tugmalari
# ==========================================================================


def webapp_url(**params) -> str:
    """Mini App ning ma'lum bir ekraniga havola yasaydi."""
    config = get_config()
    if not config.miniapp_available:
        return ""
    base = config.miniapp_url
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def webapp_button(text: str, **params) -> InlineKeyboardButton | None:
    """Mini App ni ochuvchi inline tugma (mavjud bo'lmasa `None`)."""
    url = webapp_url(**params)
    if not url:
        return None
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))


def _attach_webapp(builder: InlineKeyboardBuilder, text: str, **params) -> bool:
    """Builder ga Mini App tugmasini qo'shadi (imkoni bo'lsa)."""
    button = webapp_button(text, **params)
    if button is None:
        return False
    builder.row(button)
    return True


# ==========================================================================
#  Asosiy menyu (to'liq inline)
# ==========================================================================


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Asosiy menyu — to'liq inline tugmalar.

    Web ilova mavjud bo'lsa (HTTPS), har bir bo'lim ilovaning tegishli
    ekranini to'g'ridan-to'g'ri Web App sifatida ochadi. Aks holda
    bot ichidagi oqimlarga yo'naltiruvchi callback tugmalar beriladi.
    """
    config = get_config()
    builder = InlineKeyboardBuilder()

    if config.miniapp_available:
        builder.row(
            InlineKeyboardButton(
                text=TC.BTN_WEB_APP, web_app=WebAppInfo(url=config.miniapp_url)
            )
        )
        grid = InlineKeyboardBuilder()
        for text, view in (
            (TC.BTN_TAKE_EXAM, "exams"),
            (TC.BTN_CREATE_EXAM, "create"),
            (TC.BTN_MY_RESULTS, "results"),
            (TC.BTN_CERTIFICATES, "certificates"),
            (TC.BTN_MY_EXAMS, "my-exams"),
        ):
            grid.button(text=text, web_app=WebAppInfo(url=webapp_url(view=view)))
        grid.button(text=TC.BTN_HELP, callback_data=MenuCB(action="help"))
        grid.adjust(2)
        builder.attach(grid)
    else:
        grid = InlineKeyboardBuilder()
        grid.button(text=TC.BTN_TAKE_EXAM, callback_data=MenuCB(action="take"))
        grid.button(text=TC.BTN_CREATE_EXAM, callback_data=MenuCB(action="create"))
        grid.button(text=TC.BTN_MY_RESULTS, callback_data=MenuCB(action="results"))
        grid.button(text=TC.BTN_CERTIFICATES, callback_data=MenuCB(action="certs"))
        grid.button(text=TC.BTN_MY_EXAMS, callback_data=MenuCB(action="my_exams"))
        grid.button(text=TC.BTN_HELP, callback_data=MenuCB(action="help"))
        grid.adjust(2)
        builder.attach(grid)

    if is_admin:
        builder.row(
            InlineKeyboardButton(
                text=TC.BTN_ADMIN, callback_data=MenuCB(action="admin").pack()
            )
        )
    return builder.as_markup()


# ==========================================================================
#  Boshlanish va obuna
# ==========================================================================


def start_button() -> InlineKeyboardMarkup:
    """«Boshlash» tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.button(text=TC.BTN_START, callback_data=MenuCB(action="start"))
    return builder.as_markup()


def subscription(channel_url: str) -> InlineKeyboardMarkup:
    """Majburiy obuna tugmalari."""
    builder = InlineKeyboardBuilder()
    if channel_url:
        builder.button(text=TS.BTN_JOIN_CHANNEL, url=channel_url)
    builder.button(
        text=TS.BTN_CHECK_SUBSCRIPTION, callback_data=SubscriptionCB(action="check")
    )
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    """«Asosiy menyu» tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.button(text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main"))
    return builder.as_markup()


def cancel() -> InlineKeyboardMarkup:
    """«Bekor qilish» tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.button(text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel"))
    return builder.as_markup()


def open_app(view: str = "", **params) -> InlineKeyboardMarkup:
    """Faqat «Web ilovada ochish» tugmasidan iborat klaviatura."""
    builder = InlineKeyboardBuilder()
    if view:
        params["view"] = view
    _attach_webapp(builder, TC.BTN_OPEN_APP, **params)
    builder.row(
        InlineKeyboardButton(
            text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main").pack()
        )
    )
    return builder.as_markup()


# ==========================================================================
#  Test yaratish sehrgari
# ==========================================================================


def exam_types(is_admin: bool) -> InlineKeyboardMarkup:
    """Test turini tanlash."""
    builder = InlineKeyboardBuilder()
    builder.button(text=TE.BTN_TYPE_SIMPLE, callback_data=CreateCB(action="type", value="simple"))
    builder.button(
        text=TE.BTN_TYPE_RASCH_FREE, callback_data=CreateCB(action="type", value="rasch_free")
    )
    if is_admin:
        builder.button(
            text=TE.BTN_TYPE_RASCH_PAID, callback_data=CreateCB(action="type", value="rasch_paid")
        )
    builder.button(text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def exam_structure() -> InlineKeyboardMarkup:
    """Test tuzilmasini tanlash."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TE.BTN_NATIONAL_TEMPLATE, callback_data=CreateCB(action="structure", value="national")
    )
    builder.button(
        text=TE.BTN_CUSTOM_STRUCTURE, callback_data=CreateCB(action="structure", value="custom")
    )
    builder.button(text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def question_counts() -> InlineKeyboardMarkup:
    """Savollar sonini tanlash."""
    builder = InlineKeyboardBuilder()
    for size in C.SIMPLE_TEST_SIZES:
        builder.button(text=f"{size} ta", callback_data=CreateCB(action="count", value=str(size)))
    builder.button(text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel"))
    builder.adjust(3, 3, 1)
    return builder.as_markup()


def durations() -> InlineKeyboardMarkup:
    """Test davomiyligini tanlash (yoki kalendarni ochish)."""
    builder = InlineKeyboardBuilder()
    options = [
        (TE.BTN_NO_LIMIT, "0"),
        (TE.BTN_1_HOUR, "1"),
        (TE.BTN_3_HOURS, "3"),
        (TE.BTN_24_HOURS, "24"),
        (TE.BTN_7_DAYS, "168"),
    ]
    for label, value in options:
        builder.button(text=label, callback_data=CreateCB(action="duration", value=value))
    builder.button(
        text=TE.BTN_PICK_DATETIME, callback_data=CreateCB(action="calendar", value="open")
    )
    builder.button(text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel"))
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


def yes_no(action: str) -> InlineKeyboardMarkup:
    """«Ha / Yo'q» tanlovi."""
    builder = InlineKeyboardBuilder()
    builder.button(text=TE.BTN_YES, callback_data=CreateCB(action=action, value="1"))
    builder.button(text=TE.BTN_NO, callback_data=CreateCB(action=action, value="0"))
    builder.adjust(2)
    return builder.as_markup()


# ==========================================================================
#  Testlar ro'yxati
# ==========================================================================


def exam_list(exams, action: str = "open") -> InlineKeyboardMarkup:
    """Testlar ro'yxati tugmalari."""
    builder = InlineKeyboardBuilder()
    for exam in exams:
        builder.button(
            text=f"{exam.title} [{exam.code}]",
            callback_data=ExamCB(action=action, exam_id=exam.id),
        )
    builder.adjust(1)
    view = "my-exams" if action == "manage" else "exams"
    _attach_webapp(builder, TC.BTN_OPEN_APP, view=view)
    builder.row(
        InlineKeyboardButton(
            text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main").pack()
        )
    )
    return builder.as_markup()


def exam_entry(exam) -> InlineKeyboardMarkup:
    """Testni boshlash tugmalari."""
    builder = InlineKeyboardBuilder()
    has_app = _attach_webapp(builder, "Ilovada topshirish", view="exam", code=exam.code)
    builder.row(
        InlineKeyboardButton(
            text="Botda topshirish" if has_app else "Testni boshlash",
            callback_data=ExamCB(action="take", exam_id=exam.id).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main").pack()
        )
    )
    return builder.as_markup()


def exam_manage(exam, *, is_owner: bool = True) -> InlineKeyboardMarkup:
    """Test boshqaruvi tugmalari."""
    builder = InlineKeyboardBuilder()
    status = exam.status

    if status in {"draft", "closed"}:
        builder.button(text=TA.BTN_ACTIVATE, callback_data=ExamCB(action="activate", exam_id=exam.id))
    if status == "active":
        builder.button(text=TA.BTN_CLOSE, callback_data=ExamCB(action="close", exam_id=exam.id))
    if status in {"active", "closed", "calculated", "published"}:
        builder.button(text=TA.BTN_CALCULATE, callback_data=ExamCB(action="calc", exam_id=exam.id))
    if status in {"calculated", "published"}:
        builder.button(text=TA.BTN_PUBLISH, callback_data=ExamCB(action="publish", exam_id=exam.id))

    builder.button(text=TA.BTN_RATING, callback_data=ExamCB(action="rating", exam_id=exam.id))
    builder.button(text=TA.BTN_EXPORT_RESULTS, callback_data=ExamCB(action="xlsx", exam_id=exam.id))
    builder.button(text=TA.BTN_EXPORT_PDF, callback_data=ExamCB(action="pdf", exam_id=exam.id))
    # Savollar qiyinchiligi diagrammasi — faqat test egasi va adminlar uchun.
    builder.button(text=TA.BTN_CHARTS, callback_data=ExamCB(action="charts", exam_id=exam.id))

    if exam.exam_type == "rasch_paid":
        builder.button(text=TA.BTN_MAKE_CODES, callback_data=ExamCB(action="codes", exam_id=exam.id))
        if exam.certificate_enabled:
            builder.button(
                text=TA.BTN_CERTIFICATES, callback_data=ExamCB(action="certs", exam_id=exam.id)
            )

    builder.button(text=TA.BTN_DUPLICATE, callback_data=ExamCB(action="copy", exam_id=exam.id))
    builder.button(text=TA.BTN_ARCHIVE, callback_data=ExamCB(action="archive", exam_id=exam.id))
    builder.button(text=TA.BTN_DELETE, callback_data=ExamCB(action="delete", exam_id=exam.id))
    builder.adjust(1)

    _attach_webapp(builder, TC.BTN_OPEN_APP, view="exam-manage", code=exam.code)
    builder.row(
        InlineKeyboardButton(
            text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main").pack()
        )
    )
    return builder.as_markup()


def confirm_delete(exam) -> InlineKeyboardMarkup:
    """Testni o'chirishni tasdiqlash."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TA.BTN_CONFIRM_DELETE,
        callback_data=ExamCB(action="delete_yes", exam_id=exam.id),
    )
    builder.button(
        text=TA.BTN_CANCEL_DELETE,
        callback_data=ExamCB(action="manage", exam_id=exam.id),
    )
    builder.adjust(1)
    return builder.as_markup()


# ==========================================================================
#  Test topshirish
# ==========================================================================


def question_single(question, selected: str, total: int) -> InlineKeyboardMarkup:
    """Bitta javobli savol uchun tugmalar."""
    builder = InlineKeyboardBuilder()
    for letter in question.choice_letters:
        prefix = "● " if letter == selected else "○ "
        builder.button(
            text=f"{prefix}{letter}",
            callback_data=QuestionCB(action="pick", order=question.order, value=letter),
        )
    builder.adjust(4)
    _add_navigation(builder, question.order, total)
    return builder.as_markup()


def question_multi(question, selected: str, total: int) -> InlineKeyboardMarkup:
    """Moslashtirish savoli (A–F) uchun tugmalar — bitta variant tanlanadi."""
    builder = InlineKeyboardBuilder()
    chosen = set(selected or "")
    for letter in question.choice_letters:
        prefix = "● " if letter in chosen else "○ "
        builder.button(
            text=f"{prefix}{letter}",
            callback_data=QuestionCB(action="toggle", order=question.order, value=letter),
        )
    builder.adjust(3)

    confirm = InlineKeyboardBuilder()
    confirm.button(
        text=TC.BTN_CONFIRM, callback_data=QuestionCB(action="confirm", order=question.order)
    )
    confirm.button(
        text="Tozalash", callback_data=QuestionCB(action="clear", order=question.order)
    )
    confirm.adjust(2)
    builder.attach(confirm)

    _add_navigation(builder, question.order, total)
    return builder.as_markup()


def question_open(question, total: int) -> InlineKeyboardMarkup:
    """Ochiq javobli savol uchun tugmalar."""
    builder = InlineKeyboardBuilder()
    _add_navigation(builder, question.order, total)
    return builder.as_markup()


def _add_navigation(builder: InlineKeyboardBuilder, order: int, total: int) -> None:
    """Savollar orasida harakatlanish tugmalarini qo'shadi."""
    nav = InlineKeyboardBuilder()
    if order > 1:
        nav.button(text="‹ Oldingi", callback_data=QuestionCB(action="prev", order=order))
    nav.button(text=f"{order} / {total}", callback_data=QuestionCB(action="review", order=order))
    if order < total:
        nav.button(text="Keyingi ›", callback_data=QuestionCB(action="next", order=order))
    nav.adjust(3)
    builder.attach(nav)

    finish = InlineKeyboardBuilder()
    finish.button(text="Ko'rib chiqish", callback_data=QuestionCB(action="review", order=order))
    finish.button(text="Yakunlash", callback_data=QuestionCB(action="finish", order=order))
    finish.adjust(2)
    builder.attach(finish)


def review_navigation(total: int, unanswered: list[int]) -> InlineKeyboardMarkup:
    """Ko'rib chiqish sahifasi tugmalari."""
    builder = InlineKeyboardBuilder()
    for order in unanswered[:12]:
        builder.button(
            text=f"{order}", callback_data=QuestionCB(action="jump", order=order)
        )
    builder.adjust(6)

    actions = InlineKeyboardBuilder()
    actions.button(text="Testga qaytish", callback_data=QuestionCB(action="jump", order=1))
    actions.button(text="Yakunlash", callback_data=QuestionCB(action="finish", order=0))
    actions.adjust(1)
    builder.attach(actions)
    return builder.as_markup()


def confirm_submit() -> InlineKeyboardMarkup:
    """Yakuniy yuborishni tasdiqlash."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Ha, yuborilsin", callback_data=QuestionCB(action="submit", order=0)
    )
    builder.button(
        text="Yo'q, davom etaman", callback_data=QuestionCB(action="jump", order=0)
    )
    builder.adjust(1)
    return builder.as_markup()


# ==========================================================================
#  Natijalar
# ==========================================================================


def result_actions(
    attempt, *, show_answers: bool, show_rating: bool, certificate: bool, exam_code: str = ""
) -> InlineKeyboardMarkup:
    """Natija sahifasidagi tugmalar."""
    builder = InlineKeyboardBuilder()
    if show_answers:
        builder.button(
            text=TE.BTN_SHOW_ANSWERS, callback_data=AttemptCB(action="answers", attempt_id=attempt.id)
        )
    if show_rating:
        builder.button(
            text=TE.BTN_SHOW_RATING, callback_data=AttemptCB(action="rating", attempt_id=attempt.id)
        )
    if certificate:
        builder.button(
            text=TE.BTN_GET_CERTIFICATE,
            callback_data=AttemptCB(action="certificate", attempt_id=attempt.id),
        )
    builder.adjust(1)

    _attach_webapp(builder, TC.BTN_OPEN_APP, view="result", attempt=attempt.id)
    builder.row(
        InlineKeyboardButton(
            text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main").pack()
        )
    )
    return builder.as_markup()


def attempt_list(attempts) -> InlineKeyboardMarkup:
    """Natijalar ro'yxati."""
    builder = InlineKeyboardBuilder()
    for attempt in attempts:
        label = f"{attempt.exam.title} — {attempt.display_ball}"
        builder.button(text=label, callback_data=AttemptCB(action="open", attempt_id=attempt.id))
    builder.adjust(1)
    _attach_webapp(builder, TC.BTN_OPEN_APP, view="results")
    builder.row(
        InlineKeyboardButton(
            text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main").pack()
        )
    )
    return builder.as_markup()


# ==========================================================================
#  Admin
# ==========================================================================


def admin_panel(web_url: str = "") -> InlineKeyboardMarkup:
    """
    Administrator paneli tugmalari.

    Web panel Telegram Web App sifatida ochiladi — login va parol kerak
    emas, kirish `initData` imzosi orqali amalga oshadi.
    """
    config = get_config()
    builder = InlineKeyboardBuilder()

    if config.panel_available:
        builder.row(
            InlineKeyboardButton(
                text=TA.BTN_WEB_PANEL, web_app=WebAppInfo(url=config.panel_url)
            )
        )
    elif web_url:
        builder.row(InlineKeyboardButton(text=TA.BTN_WEB_PANEL, url=web_url))

    actions = InlineKeyboardBuilder()
    actions.button(text=TA.BTN_STATS, callback_data=MenuCB(action="admin_stats"))
    actions.button(text=TA.BTN_ALL_EXAMS, callback_data=MenuCB(action="admin_exams"))
    actions.button(text=TA.BTN_CODES, callback_data=MenuCB(action="admin_codes"))
    actions.button(text=TA.BTN_EXPORT_USERS, callback_data=MenuCB(action="admin_users"))
    actions.adjust(1)
    builder.attach(actions)

    builder.row(
        InlineKeyboardButton(
            text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main").pack()
        )
    )
    return builder.as_markup()


def code_exam_list(exams) -> InlineKeyboardMarkup:
    """ID kod yaratish uchun test tanlash."""
    builder = InlineKeyboardBuilder()
    for exam in exams:
        builder.button(
            text=f"{exam.title} [{exam.code}]",
            callback_data=CodesCB(action="exam", exam_id=exam.id),
        )
    builder.button(text=TC.BTN_MAIN_MENU, callback_data=MenuCB(action="main"))
    builder.adjust(1)
    return builder.as_markup()


def code_quantities(exam_id: int) -> InlineKeyboardMarkup:
    """ID kodlar miqdorini tanlash."""
    builder = InlineKeyboardBuilder()
    for quantity in C.CODE_BATCH_CHOICES:
        builder.button(
            text=f"{quantity} ta",
            callback_data=CodesCB(action="quantity", exam_id=exam_id, quantity=quantity),
        )
    builder.button(
        text=f"{C.DEFAULT_CODE_BATCH} ta",
        callback_data=CodesCB(action="quantity", exam_id=exam_id, quantity=C.DEFAULT_CODE_BATCH),
    )
    builder.button(
        text=TA.BTN_CUSTOM_QUANTITY, callback_data=CodesCB(action="custom", exam_id=exam_id)
    )
    builder.button(text=TC.BTN_CANCEL, callback_data=MenuCB(action="cancel"))
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


def url_button(text: str, url: str) -> InlineKeyboardMarkup:
    """Bitta havola tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]]
    )


__all__ = [
    "webapp_url",
    "webapp_button",
    "main_menu",
    "start_button",
    "subscription",
    "back_to_menu",
    "cancel",
    "open_app",
    "exam_types",
    "exam_structure",
    "question_counts",
    "durations",
    "yes_no",
    "exam_list",
    "exam_entry",
    "exam_manage",
    "confirm_delete",
    "question_single",
    "question_multi",
    "question_open",
    "review_navigation",
    "confirm_submit",
    "result_actions",
    "attempt_list",
    "admin_panel",
    "code_exam_list",
    "code_quantities",
    "url_button",
]
