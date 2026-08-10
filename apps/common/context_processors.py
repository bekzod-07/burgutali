"""Shablonlarga umumiy ma'lumot uzatuvchi kontekst protsessorlari."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

#: Panel uslubi — versiya belgisini shu fayl bo'yicha hisoblaymiz.
_PANEL_CSS = (
    Path(__file__).resolve().parent.parent
    / "dashboard"
    / "static"
    / "dashboard"
    / "css"
    / "dashboard.css"
)


def _css_version() -> str:
    """
    Panel uslubi uchun versiya belgisi (kesh buzish).

    Panel Telegram Web App sifatida ham ochiladi, webview esa CSS ni uzoq
    keshlaydi — fayl o'zgarganda havolaga yangi `?v=...` qo'shiladi.
    """
    try:
        return str(int(_PANEL_CSS.stat().st_mtime))
    except OSError:  # pragma: no cover - fayl yo'q bo'lishi mumkin
        return "1"


def site_info(request) -> dict:  # noqa: ANN001
    """Sayt nomi, bot havolasi va shu kabi umumiy qiymatlar."""
    bot_username = getattr(settings, "BOT_USERNAME", "")
    return {
        "SITE_NAME": getattr(settings, "CERT_PLATFORM_NAME", "Rasch Math Platform"),
        "ORGANIZATION": getattr(settings, "CERT_ORGANIZATION", ""),
        "BOT_USERNAME": bot_username,
        "BOT_URL": f"https://t.me/{bot_username}" if bot_username else "",
        "CHANNEL_URL": getattr(settings, "REQUIRED_CHANNEL_URL", ""),
        "PUBLIC_BASE_URL": getattr(settings, "PUBLIC_BASE_URL", ""),
        "PANEL_CSS_VERSION": _css_version(),
    }
