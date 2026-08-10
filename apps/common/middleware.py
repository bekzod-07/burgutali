"""
Telegram Mini App uchun freym sozlamalari.

Telegram Web (web.telegram.org) Mini App larni `<iframe>` ichida ochadi.
Django ning standart `X-Frame-Options: SAMEORIGIN` sarlavhasi bunday
joylashtirishni bloklaydi, natijada ilova va boshqaruv paneli oq ekran
bo'lib qoladi.

Shuning uchun faqat Mini App yo'llari uchun `X-Frame-Options` olib
tashlanadi va uning o'rniga aniqroq `Content-Security-Policy:
frame-ancestors` qo'yiladi — sahifani faqat Telegram va o'z saytimiz
joylashtira oladi.
"""

from __future__ import annotations

#: Telegram webview ichida ochilishi mumkin bo'lgan yo'llar.
EMBEDDABLE_PREFIXES = ("/app/", "/panel/")

#: Sahifani joylashtirishga ruxsat berilgan manbalar.
FRAME_ANCESTORS = (
    "'self'",
    "https://web.telegram.org",
    "https://*.telegram.org",
    "https://telegram.org",
)


class TelegramFrameMiddleware:
    """Mini App sahifalarini Telegram iframe ichida ochishga ruxsat beradi."""

    def __init__(self, get_response) -> None:  # noqa: ANN001
        self.get_response = get_response

    def __call__(self, request):  # noqa: ANN001
        response = self.get_response(request)

        path = request.path or ""
        if not path.startswith(EMBEDDABLE_PREFIXES):
            return response

        # Django qo'ygan cheklovni olib tashlaymiz...
        response.headers.pop("X-Frame-Options", None)

        # ...va o'rniga aniq ro'yxatni qo'yamiz.
        policy = "frame-ancestors " + " ".join(FRAME_ANCESTORS)
        existing = response.headers.get("Content-Security-Policy")
        if existing and "frame-ancestors" not in existing:
            response.headers["Content-Security-Policy"] = f"{existing}; {policy}"
        elif not existing:
            response.headers["Content-Security-Policy"] = policy

        return response


__all__ = ["TelegramFrameMiddleware", "EMBEDDABLE_PREFIXES", "FRAME_ANCESTORS"]
