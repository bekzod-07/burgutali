"""
Bot konfiguratsiyasi.

Barcha qiymatlar `.env` faylidan o'qiladi (`core.env` orqali) —
Django sozlamalari bilan bir xil manbadan foydalaniladi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from core.env import get_bool, get_int, get_int_list, get_str, load_env


#: Natijalar hisobotini standart holatda oladigan qo'shimcha kuzatuvchilar.
#: `.env` da `REPORT_EXTRA_IDS` berilsa, o'sha ro'yxat ishlatiladi.
DEFAULT_REPORT_EXTRA_IDS: tuple[int, ...] = (223974403,)


@dataclass(frozen=True)
class BotConfig:
    """Botning ishga tushish sozlamalari."""

    token: str
    username: str
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    #: Natijalar hisobotini qo'shimcha oladigan Telegram ID lar.
    #: Bular admin emas — faqat yopilgan/e'lon qilingan testlar bo'yicha
    #: umumiy natijalar PDF sini oladi (`REPORT_EXTRA_IDS`).
    report_extra_ids: frozenset[int] = field(default_factory=frozenset)
    required_channel: str = ""
    required_channel_url: str = ""
    subscription_required: bool = True
    public_base_url: str = ""
    throttle_rate: float = 0.4
    auto_close_interval: int = 60

    # ------------------------------------------------------------------
    @property
    def is_valid(self) -> bool:
        """Token to'g'ri ko'rinishdami."""
        return bool(self.token) and ":" in self.token

    @property
    def miniapp_url(self) -> str:
        """Web ilova manzili (faqat HTTPS bo'lsa ishlaydi)."""
        if not self.public_base_url:
            return ""
        return f"{self.public_base_url.rstrip('/')}/app/"

    @property
    def panel_url(self) -> str:
        """
        Boshqaruv panelining Telegram kirish manzili.

        Bu manzil `initData` imzosini tekshiradi va admin huquqi bo'lsa
        panelga kiritadi — login/parol kerak emas.
        """
        if not self.public_base_url:
            return ""
        return f"{self.public_base_url.rstrip('/')}/panel/tg/"

    @property
    def panel_available(self) -> bool:
        """Panelni Web App sifatida ochish mumkinmi (HTTPS talab qilinadi)."""
        return self.panel_url.startswith("https://")

    @property
    def miniapp_available(self) -> bool:
        """Telegram Mini App ni ochish mumkinmi (HTTPS talab qilinadi)."""
        return self.miniapp_url.startswith("https://")

    def is_admin(self, telegram_id: int | None) -> bool:
        """Berilgan foydalanuvchi `.env` dagi asosiy adminmi."""
        return telegram_id is not None and int(telegram_id) in self.admin_ids

    def bot_link(self) -> str:
        return f"https://t.me/{self.username}" if self.username else ""

    def exam_deep_link(self, code: str) -> str:
        """Testga to'g'ridan-to'g'ri kirish havolasi."""
        if not self.username:
            return ""
        return f"https://t.me/{self.username}?start=exam_{code}"


@lru_cache(maxsize=1)
def get_config() -> BotConfig:
    """Konfiguratsiyani bir marta o'qib keshlaydi."""
    load_env()
    return BotConfig(
        token=get_str("BOT_TOKEN", ""),
        username=get_str("BOT_USERNAME", "").lstrip("@"),
        admin_ids=frozenset(get_int_list("ADMIN_IDS", [])),
        report_extra_ids=frozenset(
            get_int_list("REPORT_EXTRA_IDS", DEFAULT_REPORT_EXTRA_IDS)
        ),
        required_channel=get_str("REQUIRED_CHANNEL", "@Oybek_ustoz_MS"),
        required_channel_url=get_str("REQUIRED_CHANNEL_URL", "https://t.me/Oybek_ustoz_MS"),
        subscription_required=get_bool("SUBSCRIPTION_REQUIRED", True),
        public_base_url=get_str("PUBLIC_BASE_URL", "").rstrip("/"),
        throttle_rate=float(get_str("BOT_THROTTLE_RATE", "0.4") or 0.4),
        auto_close_interval=get_int("BOT_AUTO_CLOSE_INTERVAL", 60),
    )


__all__ = ["BotConfig", "get_config", "DEFAULT_REPORT_EXTRA_IDS"]
