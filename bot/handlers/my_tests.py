"""
«Testlarim» — yaratilgan testlarni boshqarish.

Test yaratilishi bilan faollashadi, shuning uchun boshqaruvda yagona
yakunlovchi amal bor — «Testni tugatish»: u testni yopadi, natijalarni
Rasch modeli bo'yicha hisoblaydi va darhol e'lon qiladi.

Imkoniyatlar (TZ 9-bo'lim):
  * testni tugatish (yopish + hisoblash + e'lon qilish bir amalda);
  * reyting va statistikani ko'rish;
  * natijalarni Excel/PDF ko'rinishida eksport qilish;
  * pullik testda ID kodlarni boshqarish va sertifikatlarni yaratish.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from bot.keyboards import inline
from bot.keyboards.factories import ExamCB
from bot.services import attempts as attempt_service
from bot.services import certificates as certificate_service
from bot.services import codes as code_service
from bot.services import exams as exam_service
from bot.texts import admin as TA
from bot.texts import common as TC
from bot.texts import exam as TE
from bot.utils.files import document, timestamped_name
from bot.utils.formatting import rating_rows
from core.text_utils import esc

logger = logging.getLogger(__name__)

router = Router(name="my_tests")


# ==========================================================================
#  Testlar ro'yxati
# ==========================================================================


async def show_my_exams(message: Message, user) -> None:
    """Foydalanuvchi yaratgan testlar ro'yxati."""
    exams = await exam_service.list_owned_exams(user, limit=20)
    if not exams:
        await message.answer(TA.NO_EXAMS)
        return

    await message.answer(
        TA.EXAM_LIST_TITLE,
        reply_markup=inline.exam_list(exams, action="manage"),
    )


@router.callback_query(ExamCB.filter(F.action == "manage"))
async def manage_exam(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """Test boshqaruvi kartochkasi."""
    await callback.answer()
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return
    await _send_manage_card(callback.message, exam)


async def _send_manage_card(message: Message, exam) -> None:
    """Boshqaruv kartochkasini yuboradi."""
    participants = await attempt_service.participants_count(exam)

    codes_info = ""
    if exam.requires_access_code:
        stats = await code_service.code_statistics(exam)
        codes_info = (
            f"ID kodlar: {stats['total']} ta "
            f"(ishlatilgan: {stats['used']}, bo‘sh: {stats['unused']})\n"
        )

    await message.answer(
        TA.EXAM_MANAGE.format(
            title=esc(exam.title),
            code=exam.code,
            type=esc(exam.get_exam_type_display()),
            status=esc(exam.get_status_display()),
            questions=exam.question_count,
            participants=participants,
            codes_info=codes_info,
        ),
        reply_markup=inline.exam_manage(exam),
    )


# ==========================================================================
#  Holat bilan ishlash
# ==========================================================================


@router.callback_query(ExamCB.filter(F.action == "finish"))
async def finish(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool, bot: Bot
) -> None:
    """
    Testni tugatish — yagona yakunlovchi amal.

    Javob qabul qilish to'xtaydi, natijalar Rasch modeli bo'yicha
    hisoblanadi va darhol e'lon qilinadi; sertifikat yoqilgan bo'lsa
    sertifikatlar ham shu yerda yaratiladi.
    """
    await callback.answer()
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    await callback.message.answer(TA.CALCULATING)
    try:
        ok, message_text = await exam_service.finish_exam(exam)
    except Exception:
        logger.exception("Testni tugatishda xato: exam_id=%s", exam.id)
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    if not ok:
        await callback.message.answer(esc(message_text))
        return

    exam = await exam_service.get_exam(exam.id)

    certificates_note = ""
    if exam.can_issue_certificate:
        result = await certificate_service.issue_for_exam(exam)
        certificates_note = (
            f"Sertifikatlar: {result['created']} ta yaratildi, "
            f"{result['skipped']} ta o‘tkazib yuborildi."
        )

    await callback.message.answer(TA.PUBLISHED.format(certificates=certificates_note))
    asyncio.create_task(_notify_participants(bot, exam.id))
    await _send_manage_card(callback.message, exam)


async def _notify_participants(bot: Bot, exam_id: int) -> None:
    """
    Barcha qatnashchilarga natija tayyorligini bildiradi.

    RASH testlarida (2- va 3-tur) qatnashchiga o'z natijasidan tashqari
    **umumiy natijalar** ham PDF ko'rinishida yuboriladi. Ro'yxatdagi nom
    test turiga bog'liq: 1- va 2-turda ism-familiya, 3-turda ID raqami
    (`Attempt.public_label`).
    """
    exam = await exam_service.get_exam(exam_id)
    if exam is None:
        return

    overall_pdf = b""
    overall_name = ""
    if exam.uses_rasch and exam.show_rating_to_participants:
        try:
            from bot.services import reports as report_service

            overall_pdf = await report_service.build_overall_pdf(exam)
            overall_name = timestamped_name("umumiy-natijalar", "pdf", exam.code)
        except Exception:  # pragma: no cover - hisobotsiz ham xabar ketaveradi
            logger.exception("Umumiy natijalar PDF yasalmadi: exam_id=%s", exam_id)

    participants = await attempt_service.submitted_participants(exam_id)
    for telegram_id, attempt_id in participants:
        try:
            snapshot = await attempt_service.result_snapshot(attempt_id)
            # RASH testida nechta savolni to'g'ri topgani ko'rsatilmaydi —
            # u faqat adminlar hisobotida bo'ladi.
            if exam.uses_rasch:
                from bot.handlers.results import subjects_block

                result = (
                    f"RASH ballingiz: <b>{snapshot['ball']}</b>\n"
                    f"Foiz: <b>{snapshot['award_percent']:.2f}%</b>\n"
                    f"Daraja: <b>{snapshot['grade']}</b>\n"
                    f"Reyting: <b>{snapshot['rank']}</b>"
                    f"{subjects_block(snapshot)}"
                )
            else:
                result = (
                    f"To‘g‘ri javoblar: <b>{snapshot['correct']}</b>\n"
                    f"Foiz: <b>{snapshot['percent']}%</b>\n"
                    f"Reyting: <b>{snapshot['rank']}</b>"
                )

            from bot.keyboards.factories import AttemptCB
            from aiogram.utils.keyboard import InlineKeyboardBuilder

            builder = InlineKeyboardBuilder()
            builder.button(
                text="Batafsil", callback_data=AttemptCB(action="open", attempt_id=attempt_id)
            )
            if exam.can_issue_certificate:
                builder.button(
                    text=TE.BTN_GET_CERTIFICATE,
                    callback_data=AttemptCB(action="certificate", attempt_id=attempt_id),
                )
            builder.adjust(1)

            await bot.send_message(
                telegram_id,
                TA.PUBLISH_NOTIFICATION.format(title=esc(exam.title), result=result),
                reply_markup=builder.as_markup(),
            )
            if overall_pdf:
                await bot.send_document(
                    telegram_id,
                    document(overall_pdf, overall_name),
                    caption=TA.OVERALL_RESULTS_CAPTION.format(title=esc(exam.title)),
                )
        except TelegramAPIError:
            continue
        except Exception:  # pragma: no cover
            logger.exception("Xabar yuborishda xato: %s", telegram_id)
        await asyncio.sleep(0.05)


# ==========================================================================
#  Reyting va eksport
# ==========================================================================


@router.callback_query(ExamCB.filter(F.action == "rating"))
async def show_rating(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """Test reytingi."""
    await callback.answer()
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    top = await attempt_service.rating(exam, limit=25)
    body = rating_rows(top, uses_rasch=exam.uses_rasch)
    await callback.message.answer(
        TE.RATING_TITLE.format(title=esc(exam.title), rows=body),
        reply_markup=inline.back_to_menu(),
    )


@router.callback_query(ExamCB.filter(F.action == "xlsx"))
async def export_excel(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """Natijalarni Excel ko'rinishida yuborish."""
    await callback.answer("⏳ Fayl tayyorlanmoqda...")
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    try:
        payload = await exam_service.export_results_excel(exam)
    except Exception:
        logger.exception("Excel eksportida xato: exam_id=%s", exam.id)
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    await callback.message.answer_document(
        document(payload, timestamped_name("natijalar", "xlsx", exam.code)),
        caption=f"<b>{esc(exam.title)}</b> — natijalar",
    )


@router.callback_query(ExamCB.filter(F.action == "pdf"))
async def export_pdf(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """Natijalarni PDF hisobot ko'rinishida yuborish."""
    await callback.answer("⏳ Hisobot tayyorlanmoqda...")
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    try:
        payload = await exam_service.export_results_pdf(exam)
    except Exception:
        logger.exception("PDF eksportida xato: exam_id=%s", exam.id)
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    await callback.message.answer_document(
        document(payload, timestamped_name("natijalar", "pdf", exam.code)),
        caption=f"<b>{esc(exam.title)}</b> — hisobot",
    )


@router.callback_query(ExamCB.filter(F.action == "charts"))
async def export_charts(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """
    Savollar qiyinchiligi va ballar taqsimoti diagrammalarini yuboradi.

    Diagramma faqat test egasi va adminlar uchun — `_get_owned_exam`
    huquqni tekshiradi, ishtirokchilar bu tugmani umuman ko'rmaydi.
    """
    await callback.answer("⏳ Diagramma tayyorlanmoqda...")
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    try:
        images = await exam_service.difficulty_charts(exam)
    except Exception:
        logger.exception("Diagramma yasashda xato: exam_id=%s", exam.id)
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    if not images:
        await callback.message.answer(TA.CHARTS_EMPTY)
        return

    captions = {
        "qiyinchilik": TA.REPORT_CHART_DIFFICULTY,
        "ballar-taqsimoti": TA.REPORT_CHART_DISTRIBUTION,
    }
    for kind, image in images:
        await callback.message.answer_photo(
            document(image, timestamped_name(kind, "png", exam.code)),
            caption=captions.get(kind, ""),
        )


# ==========================================================================
#  Pullik testga oid amallar
# ==========================================================================


@router.callback_query(ExamCB.filter(F.action == "codes"))
async def open_codes(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """ID kodlar yaratish oynasi."""
    await callback.answer()
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return
    if not exam.requires_access_code:
        await callback.message.answer("ID kodlar faqat pullik testlarda ishlatiladi.")
        return

    await callback.message.answer(
        TA.ASK_CODE_QUANTITY.format(title=esc(exam.title)),
        reply_markup=inline.code_quantities(exam.id),
    )


@router.callback_query(ExamCB.filter(F.action == "certs"))
async def make_certificates(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """Barcha huquqli qatnashchilarga sertifikat yaratish."""
    await callback.answer("⏳ Sertifikatlar yaratilmoqda...")
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    if not exam.can_issue_certificate:
        await callback.message.answer("Bu testda sertifikat berish yoqilmagan.")
        return
    if exam.status != "published":
        await callback.message.answer("Avval natijalarni e'lon qiling.")
        return

    result = await certificate_service.issue_for_exam(exam)
    await callback.message.answer(
        f"<b>Sertifikatlar</b>\n\n"
        f"Yaratildi: <b>{result['created']}</b>\n"
        f"⏭ O‘tkazib yuborildi: <b>{result['skipped']}</b>\n"
        f"Xatolar: <b>{result['errors']}</b>"
    )


# ==========================================================================
#  O'chirish
# ==========================================================================


@router.callback_query(ExamCB.filter(F.action == "delete"))
async def ask_delete(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """Testni o'chirishdan oldin tasdiqlash so'raydi."""
    await callback.answer()
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    summary = await exam_service.deletion_summary(exam)
    await callback.message.answer(
        TA.CONFIRM_DELETE.format(
            title=esc(exam.title),
            code=exam.code,
            questions=summary["questions"],
            attempts=summary["attempts"],
            submitted=summary["submitted"],
            codes=summary["codes"],
            used_codes=summary["used_codes"],
            certificates=summary["certificates"],
        ),
        reply_markup=inline.confirm_delete(exam),
    )


@router.callback_query(ExamCB.filter(F.action == "delete_yes"))
async def confirm_delete(
    callback: CallbackQuery, callback_data: ExamCB, user, is_admin: bool
) -> None:
    """Testni butunlay o'chiradi."""
    await callback.answer("O'chirilmoqda...")
    exam = await _get_owned_exam(callback, callback_data.exam_id, user, is_admin)
    if exam is None:
        return

    try:
        ok, message_text, _ = await exam_service.delete_exam(exam, force=True)
    except Exception:
        logger.exception("Testni o'chirishda xato: exam_id=%s", exam.id)
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # pragma: no cover
        pass

    await callback.message.answer(
        esc(message_text), reply_markup=inline.back_to_menu()
    )


# ==========================================================================
#  Yordamchi
# ==========================================================================


async def _get_owned_exam(callback: CallbackQuery, exam_id: int, user, is_admin: bool):
    """Testni oladi va foydalanuvchining huquqini tekshiradi."""
    exam = await exam_service.get_exam(exam_id)
    if exam is None:
        await callback.message.answer(TE.EXAM_NOT_FOUND)
        return None
    if exam.owner_id != user.id and not is_admin:
        await callback.message.answer(TC.ADMIN_ONLY)
        return None
    return exam


__all__ = ["router", "show_my_exams"]
