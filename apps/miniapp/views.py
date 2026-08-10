"""
Telegram Mini App sahifalari.

  * `app_shell` — bir sahifali web ilova (barcha ekranlar JS orqali
    chiziladi, ma'lumot `api.py` dan olinadi);
  * `keyboard`  — faqat matematik klaviatura (bot reply-klaviaturasidan
    ochilganda ishlatiladi va javobni `sendData()` orqali qaytaradi).
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core import constants as C
from core.math_expr import MAX_INPUT_LENGTH, normalize_expression, parse_expression

from .auth import validate_init_data


def asset_version() -> str:
    """
    Statik fayllar uchun versiya belgisi (kesh buzish).

    Telegram webview CSS va JS ni juda uzoq keshlaydi, shuning uchun
    fayl o'zgarganda havolaga yangi `?v=...` qo'shiladi va brauzer
    yangi nusxani oladi.
    """
    static_dir = Path(__file__).resolve().parent / "static" / "miniapp"
    stamps: list[float] = []
    for relative in ("css/app.css", "js/app.js"):
        path = static_dir / relative
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


def keyboard(request):
    """Matematik klaviatura sahifasi (bot uchun alohida ko'rinish)."""
    context = {
        "question_order": request.GET.get("q", ""),
        "exam_code": request.GET.get("exam", ""),
        "parts": request.GET.get("parts", "2"),
        "prefill_a": request.GET.get("a", ""),
        "prefill_b": request.GET.get("b", ""),
        "question_text": request.GET.get("text", ""),
    }
    return render(request, "miniapp/keyboard.html", context)


@csrf_exempt
@require_POST
def api_validate(request):
    """
    Kiritilgan ifodani tekshiradi (klaviatura sahifasi uchun).

    So'rov tanasi: {"expr": "1/2 + sqrt(3)", "initData": "..."}
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "So'rov formati noto'g'ri."}, status=400)

    expression = str(payload.get("expr", ""))[: MAX_INPUT_LENGTH + 20]

    init_data = payload.get("initData") or ""
    verified = bool(validate_init_data(init_data)) if init_data else False

    if not expression.strip():
        return JsonResponse({"ok": False, "error": "Ifoda bo'sh.", "verified": verified})

    normalized = normalize_expression(expression)
    parsed = parse_expression(expression)
    if parsed is None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Ifodani tahlil qilib bo'lmadi.",
                "normalized": normalized,
                "verified": verified,
            }
        )

    value = ""
    try:
        if not parsed.free_symbols:
            value = f"{float(parsed.evalf()):.6g}"
    except Exception:
        value = ""

    return JsonResponse(
        {
            "ok": True,
            "normalized": normalized,
            "pretty": str(parsed),
            "value": value,
            "verified": verified,
        }
    )
