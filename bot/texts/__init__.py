"""
Botning barcha matnlari.

Matnlar bo'limlarga ajratilgan:
  * `common` — tugma yozuvlari va umumiy xabarlar;
  * `start`  — /start, majburiy obuna, ro'yxatdan o'tish;
  * `exam`   — test yaratish va topshirish;
  * `admin`  — administrator paneli.
"""

from . import admin, common, exam, start  # noqa: F401

__all__ = ["common", "start", "exam", "admin"]
