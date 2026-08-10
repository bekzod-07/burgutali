"""
Test topshirish bo'limi.

Fayllar:
  * `entry.py`  — testga kirish (kod, ID kod, tekshiruvlar);
  * `flow.py`   — savollarga javob berish;
  * `finish.py` — yakuniy yuborish.
"""

from __future__ import annotations

from aiogram import Router

from . import entry, finish, flow

router = Router(name="taking")
router.include_router(entry.router)
router.include_router(flow.router)
router.include_router(finish.router)

__all__ = ["router"]
