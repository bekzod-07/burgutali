#!/usr/bin/env python
"""
`.env` faylidagi `PUBLIC_BASE_URL` (va unga bog'liq sozlamalar) ni yangilaydi.

Tunnel manzili har safar o'zgargani uchun ishga tushirish skripti shu
yordamchini chaqiradi:

    python tools/set_public_url.py https://xxxx.trycloudflare.com

Faylning qolgan qatorlariga tegilmaydi.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


def set_key(lines: list[str], key: str, value: str) -> list[str]:
    """`.env` dagi kalitni yangilaydi yoki oxiriga qo'shadi."""
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=", re.IGNORECASE)
    result: list[str] = []
    replaced = False
    for line in lines:
        if pattern.match(line):
            if not replaced:
                result.append(f"{key}={value}")
                replaced = True
            continue
        result.append(line)
    if not replaced:
        result.append(f"{key}={value}")
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("Foydalanish: python tools/set_public_url.py <https://...>")
        return 1

    url = sys.argv[1].strip().rstrip("/")
    if not url.startswith("https://"):
        print(f"Ogohlantirish: manzil HTTPS emas — Mini App ishlamaydi ({url})")

    if not ENV_PATH.exists():
        print(f"XATO: {ENV_PATH} topilmadi. Avval .env.example dan nusxa oling.")
        return 1

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    host = url.replace("https://", "").replace("http://", "")
    lines = set_key(lines, "PUBLIC_BASE_URL", url)
    lines = set_key(
        lines,
        "DJANGO_ALLOWED_HOSTS",
        f"localhost,127.0.0.1,{host}",
    )
    lines = set_key(
        lines,
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        f"http://localhost:8000,http://127.0.0.1:8000,{url}",
    )

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PUBLIC_BASE_URL yangilandi: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
