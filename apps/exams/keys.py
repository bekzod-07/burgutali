"""
Javob kalitlarini tahlil qilish (parsing).

Test yaratuvchi kalitni turli ko'rinishda kiritishi mumkin:

  * ketma-ket:      ``ABCDABCD...``
  * probel bilan:   ``A B C D A B``
  * raqamlangan:    ``1-A 2-B 3-C`` yoki ``1) A  2) B``
  * qatorlar bilan: har bir qatorda bitta javob.

Moslashtirish savollari (33–35) uchun ham har bir savolga **bitta** harf
kiritiladi (A–F): ``A, C, E`` yoki ``33-A 34-C 35-E``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core import constants as C


@dataclass
class KeyParseResult:
    """Kalitni tahlil qilish natijasi."""

    keys: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def count(self) -> int:
        return len(self.keys)


_NUMBERED_RE = re.compile(r"(\d{1,3})\s*[\).\-:=]?\s*([A-Za-z]+)")
_SPLIT_RE = re.compile(r"[\s,;|/]+")

#: Ochiq javob qatori boshidagi savol raqami: «36) », «36. », «36: », «36- ».
#: Nuqta va chiziqdan keyin probel talab qilinadi — aks holda «0.5» kabi
#: o'nlik kasr yoki «12-3» kabi ifodaning boshi kesilib qolar edi.
_LEADING_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*(?:[\):=]|[.\-](?=\s))\s*")


def _clean(raw: str) -> str:
    """Kalitni tozalaydi."""
    return (raw or "").strip()


def _is_numbered(raw: str) -> bool:
    """Kalit raqamlangan ko'rinishdami (1-A 2-B ...)."""
    return bool(re.search(r"\d\s*[\).\-:=]\s*[A-Za-z]", raw))


def parse_single_key(raw: str, count: int, allowed: tuple[str, ...] = C.SINGLE_CHOICES) -> KeyParseResult:
    """
    Bitta javobli savollar uchun kalitni tahlil qiladi.

    `count` — kutilayotgan javoblar soni.
    """
    raw = _clean(raw)
    result = KeyParseResult()
    if not raw:
        result.errors.append("Kalit bo'sh.")
        return result

    allowed_set = {ch.upper() for ch in allowed}

    if _is_numbered(raw):
        mapping: dict[int, str] = {}
        for number, letters in _NUMBERED_RE.findall(raw):
            index = int(number)
            letter = letters.strip().upper()
            if len(letter) != 1:
                result.errors.append(f"{index}-savol uchun bitta harf kutilgan: «{letters}».")
                continue
            if letter not in allowed_set:
                result.errors.append(
                    f"{index}-savolda noto'g'ri variant: «{letter}». "
                    f"Ruxsat etilgan: {', '.join(sorted(allowed_set))}."
                )
                continue
            mapping[index] = letter
        keys = []
        for order in range(1, count + 1):
            if order not in mapping:
                result.errors.append(f"{order}-savol uchun javob kiritilmagan.")
                keys.append("")
            else:
                keys.append(mapping[order])
        result.keys = keys
        return result

    # Ketma-ket harflar
    letters = [ch.upper() for ch in raw if ch.isalpha()]
    if len(letters) != count:
        result.errors.append(
            f"{count} ta javob kutilgan, {len(letters)} ta topildi."
        )
    for index, letter in enumerate(letters, start=1):
        if letter not in allowed_set:
            result.errors.append(
                f"{index}-javobda noto'g'ri variant: «{letter}». "
                f"Ruxsat etilgan: {', '.join(sorted(allowed_set))}."
            )
    result.keys = letters[:count] if len(letters) >= count else letters
    return result


def parse_multi_key(raw: str, count: int, allowed: tuple[str, ...] = C.MULTI_CHOICES) -> KeyParseResult:
    """
    Moslashtirish savollari (A–F) uchun kalitni tahlil qiladi.

    Har bir savolga **faqat bitta** variant to'g'ri keladi. Javoblar probel,
    vergul, nuqta-vergul yoki yangi qator bilan ajratiladi: ``A, C, E``.
    """
    raw = _clean(raw)
    result = KeyParseResult()
    if not raw:
        result.errors.append("Kalit bo'sh.")
        return result

    allowed_set = {ch.upper() for ch in allowed}

    groups: list[str]
    if _is_numbered(raw):
        mapping: dict[int, str] = {}
        for number, letters in _NUMBERED_RE.findall(raw):
            mapping[int(number)] = letters.upper()
        groups = [mapping.get(order, "") for order in range(1, count + 1)]
    else:
        groups = [g for g in _SPLIT_RE.split(raw) if g]
        # Ajratkichsiz ketma-ket yozilgan bo'lsa («ACE») — har bir harf alohida javob.
        if len(groups) == 1 and len(groups[0]) == count:
            groups = list(groups[0])

    if len(groups) != count:
        result.errors.append(
            f"{count} ta javob kutilgan, {len(groups)} ta topildi. "
            "Har bir savol uchun bitta harf yozing (masalan: A, C, E)."
        )

    keys: list[str] = []
    for index, group in enumerate(groups[:count], start=1):
        letters = sorted({ch.upper() for ch in group if ch.isalpha()})
        if not letters:
            result.errors.append(f"{index}-savol uchun javob kiritilmagan.")
            keys.append("")
            continue
        invalid = [ch for ch in letters if ch not in allowed_set]
        if invalid:
            result.errors.append(
                f"{index}-savolda noto'g'ri variant: {', '.join(invalid)}. "
                f"Ruxsat etilgan: {', '.join(sorted(allowed_set))}."
            )
        elif len(letters) > 1:
            # 33–35 — moslashtirish savollari: faqat bitta variant belgilanadi.
            result.errors.append(
                f"{index}-savolda faqat bitta variant belgilanadi, "
                f"«{''.join(letters)}» emas."
            )
        keys.append("".join(letters))

    while len(keys) < count:
        keys.append("")
    result.keys = keys
    return result


def parse_open_key(raw: str, count: int, parts: int = 2) -> KeyParseResult:
    """
    Ochiq javobli savollar (36–45) uchun kalitni tahlil qiladi.

    Har bir qatorda bitta savolning javoblari bo'ladi:
        ``36) 12 ; 3/4``   yoki   ``12 | 3/4``   yoki   ``12; 3/4``

    a) va b) javoblari ``;`` yoki ``|`` belgisi bilan ajratiladi.
    Natija ``["12||3/4", ...]`` ko'rinishida saqlanadi (ichki ajratkich ``||``).
    """
    raw = _clean(raw)
    result = KeyParseResult()
    if not raw:
        result.errors.append("Kalit bo'sh.")
        return result

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) != count:
        result.errors.append(
            f"{count} ta qator kutilgan, {len(lines)} ta topildi. "
            "Har bir savol uchun alohida qator yozing."
        )

    keys: list[str] = []
    for index, line in enumerate(lines[:count], start=1):
        # Boshidagi savol raqamini olib tashlaymiz («36) 12 ; 3/4»).
        line = _LEADING_NUMBER_RE.sub("", line)
        pieces = [p.strip() for p in re.split(r"[;|]", line) if p.strip()]
        if not pieces:
            result.errors.append(f"{index}-qatorda javob topilmadi.")
            keys.append("")
            continue
        if parts >= 2 and len(pieces) < 2:
            result.errors.append(
                f"{index}-qatorda ikkita javob kutilgan (a va b). "
                "Ularni «;» bilan ajrating."
            )
        keys.append("||".join(pieces[:parts]))

    while len(keys) < count:
        keys.append("")
    result.keys = keys
    return result


def split_open_key(value: str) -> tuple[str, str]:
    """`"12||3/4"` -> `("12", "3/4")`."""
    if not value:
        return "", ""
    pieces = value.split("||")
    first = pieces[0].strip() if pieces else ""
    second = pieces[1].strip() if len(pieces) > 1 else ""
    return first, second


def format_key_preview(keys: list[str], per_line: int = 10) -> str:
    """Kalitni ko'rib chiqish uchun chiroyli ko'rinishda formatlaydi."""
    lines: list[str] = []
    buffer: list[str] = []
    for index, key in enumerate(keys, start=1):
        buffer.append(f"{index}-{key or '—'}")
        if len(buffer) >= per_line:
            lines.append("  ".join(buffer))
            buffer = []
    if buffer:
        lines.append("  ".join(buffer))
    return "\n".join(lines)


__all__ = [
    "KeyParseResult",
    "parse_single_key",
    "parse_multi_key",
    "parse_open_key",
    "split_open_key",
    "format_key_preview",
]
