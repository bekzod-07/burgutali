"""
Sertifikatlarni berish va yuborish (TZ 31-bo'lim).

Sertifikat faqat pullik RASH testida, natijalar e'lon qilingandan keyin
va admin belgilagan shartlarga javob bergan qatnashchilarga beriladi.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards import inline
from bot.keyboards.factories import AttemptCB
from bot.services import attempts as attempt_service
from bot.services import certificates as certificate_service
from bot.texts import common as TC
from bot.texts import exam as TE
from bot.utils.files import document
from core.text_utils import esc

logger = logging.getLogger(__name__)

router = Router(name="certificate")


# ==========================================================================
#  Sertifikatlar ro'yxati
# ==========================================================================


async def show_my_certificates(message: Message, user) -> None:
    """Foydalanuvchining sertifikatlari."""
    certificates = await certificate_service.user_certificates(user)
    if not certificates:
        await message.answer(TE.NO_CERTIFICATES)
        return

    builder = InlineKeyboardBuilder()
    lines = ["<b>Sizning sertifikatlaringiz</b>\n"]
    for certificate in certificates:
        lines.append(
            f"• <code>{certificate.number}</code> — {esc(certificate.exam_title)}\n"
            f"  Ball: <b>{certificate.display_ball}</b> · Daraja: <b>{certificate.grade or '—'}</b>"
        )
        builder.button(
            text=f"Yuklab olish — {certificate.number}",
            callback_data=AttemptCB(action="certificate", attempt_id=certificate.attempt_id),
        )
    builder.adjust(1)

    await message.answer("\n".join(lines), reply_markup=builder.as_markup())


# ==========================================================================
#  Sertifikatni olish
# ==========================================================================


@router.callback_query(AttemptCB.filter(F.action == "certificate"))
async def get_certificate(
    callback: CallbackQuery, callback_data: AttemptCB, user
) -> None:
    """«Sertifikatni olish» tugmasi."""
    await callback.answer()

    attempt = await attempt_service.get_attempt(callback_data.attempt_id)
    if attempt is None or attempt.user_id != user.id:
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    check = await certificate_service.check_eligibility(attempt)
    if not check:
        existing = await certificate_service.get_certificate(attempt)
        if existing is None:
            await callback.message.answer(
                TE.CERTIFICATE_NOT_AVAILABLE.format(reason=esc(check.reason))
            )
            return

    await callback.message.answer("⏳ Sertifikat tayyorlanmoqda...")

    try:
        certificate, message_text = await certificate_service.issue_certificate(attempt)
    except Exception:
        logger.exception("Sertifikat yaratishda xato: attempt_id=%s", attempt.id)
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    if certificate is None:
        await callback.message.answer(
            TE.CERTIFICATE_NOT_AVAILABLE.format(reason=esc(message_text))
        )
        return

    payload = await certificate_service.certificate_payload(certificate.id)
    if payload is None:
        await callback.message.answer(TC.ERROR_GENERIC)
        return

    content, filename, info = payload
    caption = TE.CERTIFICATE_READY.format(
        number=info["number"], ball=info["ball"], grade=info["grade"]
    )

    markup = None
    if info.get("verify_url"):
        markup = inline.url_button("Haqiqiyligini tekshirish", info["verify_url"])

    await callback.message.answer_document(
        document(content, filename), caption=caption, reply_markup=markup
    )


__all__ = ["router", "show_my_certificates"]
