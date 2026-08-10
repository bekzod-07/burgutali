"""
Muhit o'zgaruvchilari bilan ishlash.

Ushbu modul Django sozlamalari va Telegram bot konfiguratsiyasi uchun
yagona manba bo'lib xizmat qiladi — `.env` fayli faqat bir marta o'qiladi.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

# Loyihaning ildiz katalogi: <root>/core/env.py -> <root>
BASE_DIR: Path = Path(__file__).resolve().parent.parent

_DOTENV_LOADED = False


def load_env(*, override: bool = False) -> None:
    """`.env` faylini yuklaydi (faqat bir marta)."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED and not override:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - python-dotenv ixtiyoriy
        _DOTENV_LOADED = True
        return
    load_dotenv(BASE_DIR / ".env", override=override)
    _DOTENV_LOADED = True


def get_str(key: str, default: str = "") -> str:
    """Matnli qiymat qaytaradi."""
    load_env()
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip()


def get_bool(key: str, default: bool = False) -> bool:
    """Mantiqiy qiymat qaytaradi (1/true/yes/on -> True)."""
    raw = get_str(key, "").lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on", "ha"}


def get_int(key: str, default: int = 0) -> int:
    """Butun son qaytaradi; noto'g'ri qiymatda `default` qaytadi."""
    raw = get_str(key, "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_float(key: str, default: float = 0.0) -> float:
    """Haqiqiy son qaytaradi; noto'g'ri qiymatda `default` qaytadi."""
    raw = get_str(key, "")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def get_list(key: str, default: Iterable[str] = ()) -> list[str]:
    """Vergul bilan ajratilgan ro'yxatni qaytaradi."""
    raw = get_str(key, "")
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_int_list(key: str, default: Iterable[int] = ()) -> list[int]:
    """Vergul bilan ajratilgan butun sonlar ro'yxatini qaytaradi."""
    result: list[int] = []
    for item in get_list(key):
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result or list(default)


__all__ = [
    "BASE_DIR",
    "load_env",
    "get_str",
    "get_bool",
    "get_int",
    "get_float",
    "get_list",
    "get_int_list",
]
