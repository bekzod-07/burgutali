"""
Test yaratish sehrgari.

Bosqichlar alohida fayllarga ajratilgan:
  * `common.py`   — test turi, nomi va tuzilmasi;
  * `keys.py`     — javob kalitlarini kiritish;
  * `settings.py` — tugash vaqti, natija ko'rinishi, sertifikat;
  * `finalize.py` — testni yaratish va faollashtirish.
"""

from __future__ import annotations

from aiogram import Router

from . import common, finalize, keys, settings

router = Router(name="create")
router.include_router(common.router)
router.include_router(keys.router)
router.include_router(settings.router)
router.include_router(finalize.router)

__all__ = ["router"]
