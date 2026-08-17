"""
Telegram Mini App `initData` imzosini tekshirish.

Telegram Mini App ochilganda `window.Telegram.WebApp.initData` orqali
imzolangan ma'lumot uzatiladi. Uning haqiqiyligi bot tokeni yordamida
HMAC-SHA256 imzosi bo'yicha tekshiriladi:

    secret_key = HMAC_SHA256(key="WebAppData", msg=<bot_token>)
    hash       = HMAC_SHA256(key=secret_key, msg=<data_check_string>)

Manba: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl

from django.conf import settings


@dataclass
class InitDataResult:
    """`initData` ni tekshirish natijasi."""

    valid: bool
    reason: str = ""
    user: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @property
    def telegram_id(self) -> int | None:
        value = self.user.get("id")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def __bool__(self) -> bool:
        return self.valid


def validate_init_data(
    init_data: str,
    *,
    bot_token: str | None = None,
    max_age: int | None = None,
) -> InitDataResult:
    """`initData` satrini tekshiradi va foydalanuvchi ma'lumotini qaytaradi."""
    if not init_data:
        return InitDataResult(False, "initData bo'sh.")

    token = bot_token or getattr(settings, "BOT_TOKEN", "")
    if not token:
        return InitDataResult(False, "Bot tokeni sozlanmagan.")

    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return InitDataResult(False, "initData formati noto'g'ri.")

    received_hash = pairs.pop("hash", "")
    if not received_hash:
        return InitDataResult(False, "Imzo (hash) topilmadi.")

    data_check_string = "\n".join(
        f"{key}={pairs[key]}" for key in sorted(pairs)
    )
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    computed = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return InitDataResult(False, "Imzo mos kelmadi.")

    ttl = max_age if max_age is not None else getattr(settings, "MINIAPP_INITDATA_TTL", 86400)
    if ttl:
        try:
            auth_date = int(pairs.get("auth_date", "0"))
        except ValueError:
            auth_date = 0
        if auth_date and (time.time() - auth_date) > ttl:
            return InitDataResult(False, "initData muddati o'tgan.")

    user: dict = {}
    if "user" in pairs:
        try:
            user = json.loads(pairs["user"])
        except json.JSONDecodeError:
            user = {}

    return InitDataResult(True, "", user, pairs)


# --------------------------------------------------------------------------
#  Telegram Login Widget (brauzerdan kirish)
# --------------------------------------------------------------------------

#: Brauzer sessiyasida Telegram ID saqlanadigan kalit.
SESSION_KEY = "miniapp_tg_id"


def validate_login_widget(
    params: dict,
    *,
    bot_token: str | None = None,
    max_age: int = 86400,
) -> InitDataResult:
    """
    Telegram Login Widget qaytargan ma'lumot imzosini tekshiradi.

    Mini App `initData` dan farqi — kalit sifatida bot token xeshi
    to'g'ridan-to'g'ri ishlatiladi:

        secret_key = SHA256(<bot_token>)
        hash       = HMAC_SHA256(key=secret_key, msg=<data_check_string>)

    Manba: https://core.telegram.org/widgets/login#checking-authorization
    """
    token = bot_token or getattr(settings, "BOT_TOKEN", "")
    if not token:
        return InitDataResult(False, "Bot tokeni sozlanmagan.")

    data = {k: v for k, v in params.items() if k != "hash"}
    received_hash = params.get("hash", "")
    if not received_hash or "id" not in data:
        return InitDataResult(False, "Kirish ma'lumoti to'liq emas.")

    data_check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret_key = hashlib.sha256(token.encode()).digest()
    computed = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return InitDataResult(False, "Imzo mos kelmadi.")

    if max_age:
        try:
            auth_date = int(data.get("auth_date", "0"))
        except ValueError:
            auth_date = 0
        if not auth_date or (time.time() - auth_date) > max_age:
            return InitDataResult(False, "Kirish ma'lumoti muddati o'tgan.")

    return InitDataResult(True, "", dict(data), dict(data))


# --------------------------------------------------------------------------
#  So'rovdan foydalanuvchini aniqlash
# --------------------------------------------------------------------------

#: `initData` uzatiladigan HTTP sarlavha nomi.
INIT_DATA_HEADER = "HTTP_X_TELEGRAM_INIT_DATA"


class MiniAppAuthError(Exception):
    """Mini App autentifikatsiyasi muvaffaqiyatsiz tugadi."""

    def __init__(self, reason: str = "Autentifikatsiya talab qilinadi") -> None:
        super().__init__(reason)
        self.reason = reason


def _require_subscription(user) -> None:
    """
    Majburiy obunani tekshiradi (Mini App tomonida).

    Telegram API bu yerda so'ralmaydi — holat bazadagi keshdan o'qiladi.
    Keshni bot yangilab turadi: foydalanuvchi botga har murojaat qilganda
    `SubscriptionMiddleware` a'zolikni tekshiradi va natijani yozadi.
    Shu sababli ilovaga faqat botda a'zoligi tasdiqlangan odam kiradi.
    """
    from bot.config import get_config

    config = get_config()
    if not config.subscription_required:
        return
    if user.is_admin or config.is_admin(user.telegram_id):
        return
    if user.is_subscribed:
        return

    raise MiniAppAuthError(
        f"Ilovadan foydalanish uchun {config.required_channel} kanaliga "
        "a'zo bo'ling, so'ng botga qaytib «A'zolikni tekshirish» tugmasini bosing."
    )


def resolve_user(request):
    """
    So'rov sarlavhasidagi `initData` bo'yicha `BotUser` ni topadi.

    Ishlab chiqish rejimida (`DEBUG=True`) `X-Debug-User` sarlavhasi orqali
    Telegram ID ni to'g'ridan-to'g'ri berish mumkin — bu avtotestlar va
    brauzerda tekshirish uchun kerak. Ishlab chiqarishda bu yo'l yopiq.
    """
    from apps.users.models import BotUser

    init_data = request.META.get(INIT_DATA_HEADER, "")
    if init_data:
        result = validate_init_data(init_data)
        if not result.valid:
            raise MiniAppAuthError(result.reason)
        telegram_id = result.telegram_id
        if telegram_id is None:
            raise MiniAppAuthError("Foydalanuvchi ma'lumoti topilmadi.")
        user = BotUser.objects.filter(telegram_id=telegram_id).first()
        if user is None:
            raise MiniAppAuthError(
                "Siz botda ro'yxatdan o'tmagansiz. Avval botga /start yuboring."
            )
        if user.is_blocked:
            raise MiniAppAuthError("Hisobingiz bloklangan.")
        _require_subscription(user)
        return user

    # Brauzer sessiyasi (Telegram Login Widget orqali kirilgan bo'lsa).
    session_tg_id = request.session.get(SESSION_KEY) if hasattr(request, "session") else None
    if session_tg_id:
        # API'lar CSRF'dan ozod, shuning uchun sessiyali o'zgartiruvchi
        # so'rovlar faqat ilova JS'i qo'yadigan maxsus sarlavha bilan qabul
        # qilinadi — begona sayt formasi bunday sarlavha yubora olmaydi.
        if request.method not in ("GET", "HEAD", "OPTIONS") and (
            request.META.get("HTTP_X_REQUESTED_WITH") != "XMLHttpRequest"
        ):
            raise MiniAppAuthError("So'rov manbai tasdiqlanmadi.")
        user = BotUser.objects.filter(telegram_id=session_tg_id).first()
        if user is None:
            request.session.pop(SESSION_KEY, None)
            raise MiniAppAuthError(
                "Siz botda ro'yxatdan o'tmagansiz. Avval botga /start yuboring."
            )
        if user.is_blocked:
            raise MiniAppAuthError("Hisobingiz bloklangan.")
        _require_subscription(user)
        return user

    if getattr(settings, "DEBUG", False) or getattr(settings, "MINIAPP_ALLOW_DEBUG_USER", False):
        raw = request.META.get("HTTP_X_DEBUG_USER", "")
        if raw:
            try:
                telegram_id = int(raw)
            except ValueError:
                raise MiniAppAuthError("X-Debug-User noto'g'ri.") from None
            user = BotUser.objects.filter(telegram_id=telegram_id).first()
            if user is None:
                raise MiniAppAuthError("Bunday foydalanuvchi topilmadi.")
            return user

    raise MiniAppAuthError(
        "Ilovani Telegram orqali oching — autentifikatsiya ma'lumoti topilmadi."
    )


__all__ = [
    "InitDataResult",
    "MiniAppAuthError",
    "INIT_DATA_HEADER",
    "SESSION_KEY",
    "validate_init_data",
    "validate_login_widget",
    "resolve_user",
]
