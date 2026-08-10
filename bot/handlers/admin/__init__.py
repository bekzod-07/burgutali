"""
Administrator paneli.

Fayllar:
  * `panel.py` — panel menyusi va testlar ro'yxati;
  * `stats.py` — umumiy statistika;
  * `codes.py` — bir martalik ID kodlarni yaratish va Excel eksporti.
"""

from __future__ import annotations

from aiogram import Router

from . import codes, panel, stats

router = Router(name="admin")
router.include_router(panel.router)
router.include_router(stats.router)
router.include_router(codes.router)

__all__ = ["router"]
