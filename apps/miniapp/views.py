"""
Telegram Mini App sahifalari.

  * `app_shell` — bir sahifali web ilova (barcha ekranlar JS orqali
    chiziladi, ma'lumot `api.py` dan olinadi).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core import constants as C
from core.answer_check import (
    MAX_INPUT_LENGTH,
    alternatives,
    display_answer,
    normalize_answer,
)

from .auth import SESSION_KEY, validate_init_data, validate_login_widget


def asset_version() -> str:
    """
    Statik fayllar uchun versiya belgisi (kesh buzish).

    Telegram webview CSS va JS ni juda uzoq keshlaydi, shuning uchun
    fayl o'zgarganda havolaga yangi `?v=...` qo'shiladi va brauzer
    yangi nusxani oladi.
    """
    static_dir = Path(__file__).resolve().parent / "static" / "miniapp"
    shared_dir = Path(settings.BASE_DIR) / "static" / "keysheet"
    assets = [
        static_dir / "css/app.css",
        static_dir / "js/app.js",
        # Umumiy javoblar varaqasi ham shu versiya bilan yangilanadi.
        shared_dir / "keysheet.css",
        shared_dir / "keysheet.js",
    ]
    stamps: list[float] = []
    for path in assets:
        try:
            stamps.append(path.stat().st_mtime)
        except OSError:  # pragma: no cover - fayl yo'q bo'lishi mumkin
            continue
    if not stamps:
        return "1"
    return str(int(max(stamps)))


def app_shell(request):
    """Web ilovaning asosiy sahifasi."""
    context = {
        "initial_view": request.GET.get("view", "home"),
        "initial_code": request.GET.get("code", ""),
        "initial_attempt": request.GET.get("attempt", ""),
        "bot_username": getattr(settings, "BOT_USERNAME", ""),
        "max_ball": C.MAX_BALL,
        "grade_table": [
            {"from": low, "to": high, "grade": grade} for low, high, grade in C.GRADE_TABLE
        ],
        "debug_mode": bool(getattr(settings, "DEBUG", False)),
        "asset_version": asset_version(),
    }
    response = render(request, "miniapp/app.html", context)
    # Qobiq sahifasining o'zi keshlanmasin — aks holda yangi `?v=` ham yetib bormaydi.
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def login_page(request):
    """
    Ilova faqat Telegram ichida (Web App sifatida) ochiladi — brauzerdan
    kelgan har qanday so'rov to'g'ridan-to'g'ri botga yo'naltiriladi.
    """
    bot_username = getattr(settings, "BOT_USERNAME", "")
    return HttpResponseRedirect(f"https://t.me/{bot_username}")


def tg_login(request):
    """Telegram OAuth qaytish manzili — imzoni tekshirib sessiya ochadi."""
    from apps.users.models import BotUser

    def fail(reason: str):
        return HttpResponseRedirect(
            reverse("miniapp:login") + "?xato=" + quote(reason)
        )

    # Telegram natijani URL fragmentida (#tgAuthResult=...) qaytarishi mumkin —
    # fragment serverga yetib kelmaydi, uni JS query parametrlariga o'giradi.
    if "hash" not in request.GET:
        return render(request, "miniapp/tg_login_fragment.html")

    result = validate_login_widget(request.GET.dict())
    if not result.valid or result.telegram_id is None:
        return fail(result.reason or "Kirish ma'lumoti tasdiqlanmadi.")

    user = BotUser.objects.filter(telegram_id=result.telegram_id).first()
    if user is None:
        return fail("Siz botda ro'yxatdan o'tmagansiz. Avval botga /start yuboring.")
    if user.is_blocked:
        return fail("Hisobingiz bloklangan.")

    request.session[SESSION_KEY] = result.telegram_id
    request.session.set_expiry(30 * 24 * 3600)  # 30 kun
    return HttpResponseRedirect(reverse("miniapp:app"))


def logout_page(request):
    """Brauzer sessiyasini yopib, kirish sahifasiga qaytaradi."""
    request.session.pop(SESSION_KEY, None)
    return HttpResponseRedirect(reverse("miniapp:login"))


@csrf_exempt
@require_POST
def api_validate(request):
    """
    Kiritilgan javobni tekshiruvga tayyor ko'rinishda qaytaradi.

    Javoblar varaqasi maydonlari ostidagi izoh uchun ishlatiladi.
    So'rov tanasi: {"expr": "osmon; samo", "as_key": true, "initData": "..."}

    `as_key` — yozilayotgani **kalit** ekanini bildiradi: bunda sinonimlar
    ajratib ko'rsatiladi («osmon yoki samo»). Panelda kalit yoziladi,
    shuning uchun u doim shu bayroq bilan keladi.
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "So'rov formati noto'g'ri."}, status=400)

    expression = str(payload.get("expr", ""))[: MAX_INPUT_LENGTH + 20]

    init_data = payload.get("initData") or ""
    verified = bool(validate_init_data(init_data)) if init_data else False

    if not expression.strip():
        return JsonResponse({"ok": False, "error": "Javob bo'sh.", "verified": verified})

    if payload.get("as_key"):
        options = alternatives(expression)
        pretty = " yoki ".join(display_answer(item) for item in options)
    else:
        options = [expression]
        pretty = display_answer(expression)

    return JsonResponse(
        {
            "ok": True,
            "normalized": normalize_answer(expression),
            "pretty": pretty,
            "value": "",
            "variants": len(options),
            "verified": verified,
        }
    )
