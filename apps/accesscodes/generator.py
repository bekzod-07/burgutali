"""
Bir martalik ID kodlarni generatsiya qilish.

TZ dagi format: ``R7K4-8251`` — ya'ni

    <harf><raqam><harf><raqam> - <4 ta raqam>

Chalkashtirmaslik uchun harflar orasidan ``I`` va ``O`` chiqarib tashlangan
(ular ``1`` va ``0`` ga o'xshaydi).

Kodlar kriptografik jihatdan xavfsiz `secrets` moduli orqali yaratiladi va
bazadagi mavjud kodlar bilan taqqoslab, takrorlanmasligi kafolatlanadi.
"""

from __future__ import annotations

import secrets
import string

from core import constants as C

#: Kodning harfiy pozitsiyalarida ishlatiladigan belgilar.
LETTERS = C.CODE_LETTERS

#: Kodning raqamli pozitsiyalarida ishlatiladigan belgilar.
DIGITS = string.digits


def make_code() -> str:
    """Bitta tasodifiy ID kod yaratadi (bazani tekshirmasdan)."""
    head = "".join(
        (
            secrets.choice(LETTERS),
            secrets.choice(DIGITS),
            secrets.choice(LETTERS),
            secrets.choice(DIGITS),
        )
    )
    tail = "".join(secrets.choice(DIGITS) for _ in range(4))
    return f"{head}-{tail}"


def normalize_code(raw: str) -> str:
    """
    Foydalanuvchi kiritgan kodni standart ko'rinishga keltiradi.

    ``r7k4 8251``, ``R7K48251``, ``r7k4-8251`` -> ``R7K4-8251``
    """
    if not raw:
        return ""
    cleaned = "".join(ch for ch in str(raw).upper() if ch.isalnum())
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:]}"
    return cleaned


def is_valid_format(code: str) -> bool:
    """Kod formati to'g'rimi (``XNXN-NNNN``)."""
    code = normalize_code(code)
    if len(code) != 9 or code[4] != "-":
        return False
    head, tail = code[:4], code[5:]
    if not (head[0].isalpha() and head[1].isdigit() and head[2].isalpha() and head[3].isdigit()):
        return False
    return tail.isdigit()


def generate_unique_codes(quantity: int, existing: set[str] | None = None) -> list[str]:
    """
    `quantity` ta noyob kod yaratadi.

    `existing` — allaqachon band bo'lgan kodlar to'plami (bazadan olinadi).
    """
    quantity = max(0, min(int(quantity), C.CODE_BATCH_MAX))
    if quantity == 0:
        return []

    taken: set[str] = set(existing or set())
    result: list[str] = []

    # Xavfsizlik chegarasi: cheksiz siklga tushib qolmaslik uchun
    attempts = 0
    max_attempts = quantity * 50 + 1000

    while len(result) < quantity and attempts < max_attempts:
        attempts += 1
        code = make_code()
        if code in taken:
            continue
        taken.add(code)
        result.append(code)

    return result


__all__ = [
    "LETTERS",
    "DIGITS",
    "make_code",
    "normalize_code",
    "is_valid_format",
    "generate_unique_codes",
]
