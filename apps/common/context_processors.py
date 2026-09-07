"""Shablonlarga umumiy ma'lumot uzatuvchi kontekst protsessorlari."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

#: Panel uslubi va skriptlari — versiya belgisini shu fayllar bo'yicha olamiz.
_PANEL_STATIC = Path(__file__).resolve().parent.parent / "dashboard" / "static" / "dashboard"
_STATIC_ROOT = Path(__file__).resolve().parent.parent.parent / "static"
_KEYSHEET_STATIC = _STATIC_ROOT / "keysheet"
_PANEL_ASSETS = (
    _PANEL_STATIC / "css" / "dashboard.css",
    _PANEL_STATIC / "js" / "keysheet.js",
    _PANEL_STATIC / "js" / "broadcast.js",
    # Javoblar varaqasi — web ilova bilan umumiy.
    _KEYSHEET_STATIC / "keysheet.css",
    _KEYSHEET_STATIC / "keysheet.js",
)


def _css_version() -> str:
    """
    Panel uslubi va skriptlari uchun versiya belgisi (kesh buzish).

    Panel Telegram Web App sifatida ham ochiladi, webview esa fayllarni uzoq
    keshlaydi — ular o'zgarganda havolaga yangi `?v=...` qo'shiladi.
    """
    newest = 0
    for asset in _PANEL_ASSETS:
        try:
            newest = max(newest, int(asset.stat().st_mtime))
        except OSError:  # pragma: no cover - fayl yo'q bo'lishi mumkin
            continue
    return str(newest or 1)


def site_info(request) -> dict:  # noqa: ANN001
    """Sayt nomi, bot havolasi va shu kabi umumiy qiymatlar."""
    bot_username = getattr(settings, "BOT_USERNAME", "")
    return {
        "SITE_NAME": getattr(settings, "CERT_PLATFORM_NAME", "Ona tili RASH platformasi"),
        "ORGANIZATION": getattr(settings, "CERT_ORGANIZATION", ""),
        "BOT_USERNAME": bot_username,
        "BOT_URL": f"https://t.me/{bot_username}" if bot_username else "",
        "CHANNEL_URL": getattr(settings, "REQUIRED_CHANNEL_URL", ""),
        "PUBLIC_BASE_URL": getattr(settings, "PUBLIC_BASE_URL", ""),
        "PANEL_CSS_VERSION": _css_version(),
    }
