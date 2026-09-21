"""
Natijalarni ko'rsatish.

  * javoblar tahlili — nechta to'g'ri/xato, har bir savolda qatnashchi
    javobi va to'g'ri javob — test topshirilishi bilan doim ko'rinadi;
  * ball: oddiy testda «Natija ko'rinsin» sozlamasiga qarab darhol, RASH
    testida esa natijalar e'lon qilingach (butun test bo'yicha hisoblanadi).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline
from bot.keyboards.factories import AttemptCB
from bot.services import attempts as attempt_service
from bot.services import exams as exam_service
from bot.texts import common as TC
from bot.texts import exam as TE
from bot.utils.formatting import rating_rows, review_rows
from core import constants as C
from core.text_utils import chunk_text, esc

router = Router(name="results")


# ==========================================================================
#  Natijalar ro'yxati
# ==========================================================================


async def show_my_results(message: Message, user) -> None:
    """Foydalanuvchining barcha natijalari."""
    attempts = await attempt_service.user_history(user, limit=15)
    if not attempts:
        await message.answer(TE.NO_RESULTS)
        return

    await message.answer(
        "<b>Sizning natijalaringiz</b>\n\nBatafsil ko‘rish uchun tanlang.",
        reply_markup=inline.attempt_list(attempts),
    )


@router.callback_query(AttemptCB.filter(F.action == "open"))
async def open_result(
    callback: CallbackQuery, callback_data: AttemptCB, user
) -> None:
    """Bitta natijaning tafsilotlari."""
    await callback.answer()
    await _send_result(callback.message, callback_data.attempt_id, user)


async def send_answer_review(message: Message, attempt, title: str) -> None:
    """
    Javoblar tahlilini yuboradi: qisqa hisob va har bir savol bo'yicha
    qatnashchi javobi hamda (xato bo'lsa) to'g'ri javob.
    """
    rows = await attempt_service.answer_review(attempt)
    summary = attempt_service.review_summary(rows)
    await message.answer(summary_text(title, summary))

    body = review_rows(rows, show_correct=True)
    text = TE.REVIEW_ANSWERS_TITLE.format(title=esc(title), rows=body)
    for chunk in chunk_text(text, C.TELEGRAM_MESSAGE_LIMIT - 100):
        await message.answer(chunk)


def summary_text(title: str, summary: dict) -> str:
    """Qisqa hisob matni: to'g'ri, xato, javobsiz va xato qilingan savollar."""
    partial = (
        TE.REVIEW_PARTIAL_LINE.format(count=summary["partial"]) if summary["partial"] else ""
    )
    text = TE.REVIEW_SUMMARY.format(
        title=esc(title),
        correct=summary["correct"],
        wrong=summary["wrong"],
        partial=partial,
        empty=summary["empty"],
        total=summary["total"],
    )
    if summary["wrong_orders"]:
        text += TE.REVIEW_WRONG_ORDERS.format(
            orders=", ".join(str(order) for order in summary["wrong_orders"])
        )
    elif summary["total"] and summary["correct"] == summary["total"]:
        text += TE.REVIEW_ALL_CORRECT
    return text


async def _send_result(message: Message, attempt_id: int, user) -> None:
    """Natija kartochkasini yuboradi."""
    attempt = await attempt_service.get_attempt(attempt_id)
    if attempt is None or attempt.user_id != user.id:
        await message.answer(TC.ERROR_GENERIC)
        return

    snapshot = await attempt_service.result_snapshot(attempt.id)

    if not snapshot["score_visible"]:
        # Ball hali yo'q (RASH natijasi e'lon qilinmagan yoki oddiy testda
        # yashirilgan), lekin to'g'ri/xato hisobi va javoblar tahlili ochiq.
        rows = await attempt_service.answer_review(attempt)
        text = summary_text(snapshot["title"], attempt_service.review_summary(rows))
        text += TE.RESULT_SCORE_LATER if snapshot["pending"] else TE.RESULT_SCORE_HIDDEN
        await message.answer(
            text,
            reply_markup=inline.result_actions(
                attempt,
                show_answers=snapshot["show_answers"],
                show_rating=False,
                certificate=False,
            ),
        )
        return

    if snapshot["uses_rasch"] and snapshot["essay_enabled"]:
        text = TE.RESULT_READY_ESSAY.format(
            title=esc(snapshot["title"]),
            test_ball=snapshot["test_ball"],
            essay_ball=snapshot["essay_ball"],
            ball=snapshot["ball"],
            percent=f"{snapshot['award_percent']:g}",
            grade=snapshot["grade"],
            rank=snapshot["rank"],
        )
    elif snapshot["uses_rasch"]:
        text = TE.RESULT_READY.format(
            title=esc(snapshot["title"]),
            ball=snapshot["ball"],
            percent=f"{snapshot['award_percent']:g}",
            grade=snapshot["grade"],
            rank=snapshot["rank"],
        )
    else:
        text = TE.RESULT_SIMPLE.format(
            title=esc(snapshot["title"]),
            correct=snapshot["correct"],
            total=f"{snapshot['max_raw_score']:g}",
            wrong=snapshot["wrong"],
            empty=snapshot["empty"],
            percent=snapshot["percent"],
            rank=snapshot["rank"],
        )

    certificate_available = False
    if snapshot["certificate"] and snapshot["status"] == "published":
        from bot.services import certificates as certificate_service

        check = await certificate_service.check_eligibility(attempt)
        certificate_available = bool(check)

    await message.answer(
        text,
        reply_markup=inline.result_actions(
            attempt,
            show_answers=snapshot["show_answers"],
            show_rating=snapshot["show_rating"],
            certificate=certificate_available,
        ),
    )


# ==========================================================================
#  Javoblarni ko'rish
# ==========================================================================


@router.callback_query(AttemptCB.filter(F.action == "answers"))
async def show_answers(
    callback: CallbackQuery, callback_data: AttemptCB, user
) -> None:
    """To'g'ri va xato javoblar ro'yxati."""
    await callback.answer()

    attempt = await attempt_service.get_attempt(callback_data.attempt_id)
    if attempt is None or attempt.user_id != user.id:
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    snapshot = await attempt_service.result_snapshot(attempt.id)
    # Tugallanmagan urinishda tahlil yopiq — aks holda to'g'ri javoblar
    # test paytida ochilib qolardi.
    if not snapshot["show_answers"]:
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    await send_answer_review(callback.message, attempt, snapshot["title"])


# ==========================================================================
#  Reyting
# ==========================================================================


@router.callback_query(AttemptCB.filter(F.action == "rating"))
async def show_rating(
    callback: CallbackQuery, callback_data: AttemptCB, user
) -> None:
    """Test bo'yicha reyting."""
    await callback.answer()

    attempt = await attempt_service.get_attempt(callback_data.attempt_id)
    if attempt is None:
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    exam = await exam_service.get_exam(attempt.exam_id)
    snapshot = await attempt_service.result_snapshot(attempt.id)

    if not snapshot["show_rating"]:
        await callback.message.answer("Bu testda reyting yopiq.")
        return
    if snapshot["uses_rasch"] and snapshot["status"] != "published":
        await callback.message.answer(TE.RESULT_PENDING)
        return

    top = await attempt_service.public_ranking(exam, limit=C.TOP_RATING_LIMIT)
    body = rating_rows(top, uses_rasch=exam.uses_rasch, highlight_id=attempt.id)

    text = TE.RATING_TITLE.format(title=esc(exam.title), rows=body)
    if attempt.rank and attempt.rank > C.TOP_RATING_LIMIT:
        text += f"\n\nSizning o‘rningiz: <b>{snapshot['rank']}</b>"

    await callback.message.answer(text, reply_markup=inline.back_to_menu())


__all__ = ["router", "show_my_results", "send_answer_review"]
