"""
Sertifikat uchun QR-kod yaratish.

Har bir sertifikatda unikal QR-kod bo'ladi. QR skanerlanganda sertifikatni
tekshirish sahifasi ochiladi va u yerda quyidagilar ko'rsatiladi:
sertifikat haqiqiyligi, ism-familiya, test nomi, natija, test sanasi va
sertifikat raqami.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def make_qr_image(data: str, *, box_size: int = 10, border: int = 2):
    """
    Berilgan matn (odatda havola) uchun QR-kod rasmini qaytaradi.

    Qaytaradi: PIL `Image` obyekti yoki `None` (kutubxona yo'q bo'lsa).
    """
    if not data:
        return None
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except Exception:  # pragma: no cover - qrcode o'rnatilmagan
        logger.warning("`qrcode` kutubxonasi topilmadi — QR yaratilmadi.")
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0f2b46", back_color="white")
    try:
        return image.get_image()
    except AttributeError:
        return image


def make_qr_bytes(data: str, *, box_size: int = 10, border: int = 2) -> bytes | None:
    """QR-kodni PNG bayt massivi ko'rinishida qaytaradi."""
    image = make_qr_image(data, box_size=box_size, border=border)
    if image is None:
        return None
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_qr_reader(data: str, *, box_size: int = 10, border: int = 2):
    """
    ReportLab uchun `ImageReader` qaytaradi.

    Bu funksiya PDF ga QR-kodni bevosita joylash uchun ishlatiladi.
    """
    payload = make_qr_bytes(data, box_size=box_size, border=border)
    if payload is None:
        return None
    try:
        from reportlab.lib.utils import ImageReader
    except Exception:  # pragma: no cover
        return None
    return ImageReader(io.BytesIO(payload))


__all__ = ["make_qr_image", "make_qr_bytes", "make_qr_reader"]
