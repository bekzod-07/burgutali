"""Fayllarni Telegram orqali yuborish uchun yordamchilar."""

from __future__ import annotations

from datetime import datetime

from aiogram.types import BufferedInputFile

from core.text_utils import slugify_filename


def document(payload: bytes, filename: str) -> BufferedInputFile:
    """Bayt massividan Telegram hujjatini yasaydi."""
    return BufferedInputFile(payload, filename=filename)


def timestamped_name(prefix: str, extension: str, code: str = "") -> str:
    """`natijalar_32_20260806_1530.xlsx` ko'rinishidagi nom yasaydi."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    parts = [slugify_filename(prefix)]
    if code:
        parts.append(slugify_filename(code))
    parts.append(stamp)
    return "_".join(parts) + "." + extension.lstrip(".")


__all__ = ["document", "timestamped_name"]
