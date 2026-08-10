"""
Matn bilan ishlash yordamchilari.

Asosiy vazifalar:
  * o'zbek lotin alifbosidagi turli apostroflarni bir xillashtirish;
  * HTML uchun xavfsiz matn tayyorlash (Telegram parse_mode=HTML);
  * ism-familiya va telefon raqamini normallashtirish.
"""

from __future__ import annotations

import html
import re
import unicodedata

# --- Apostroflar -----------------------------------------------------------
# O'zbek lotin yozuvida o' va g' harflari uchun turli belgilar ishlatiladi.
# Barchasini yagona ko'rinishga keltiramiz.
_APOSTROPHES = "ʻʼ‘’‛`´ʹ′'"
_APOSTROPHE_RE = re.compile("[" + re.escape(_APOSTROPHES) + "]")

#: Ekranda ko'rsatiladigan standart apostrof.
CANONICAL_APOSTROPHE = "‘"


def normalize_apostrophes(text: str, replacement: str = CANONICAL_APOSTROPHE) -> str:
    """Barcha apostrof ko'rinishlarini bitta belgiga almashtiradi."""
    if not text:
        return ""
    return _APOSTROPHE_RE.sub(replacement, text)


def to_ascii_apostrophes(text: str) -> str:
    """Apostroflarni oddiy ASCII belgisiga almashtiradi (fayl nomlari uchun)."""
    return normalize_apostrophes(text, "'")


# --- HTML ------------------------------------------------------------------

def esc(text: object) -> str:
    """Telegram HTML uchun matnni xavfsiz holatga keltiradi."""
    if text is None:
        return ""
    return html.escape(str(text), quote=False)


# --- Ism-familiya ----------------------------------------------------------

_NAME_ALLOWED_RE = re.compile(r"[^\w\s'‘ʻ’.\-]", re.UNICODE)
_SPACES_RE = re.compile(r"\s+")


def clean_full_name(raw: str) -> str:
    """Ism-familiyani tozalaydi va har bir so'zni bosh harf bilan yozadi."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw)
    text = _NAME_ALLOWED_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text).strip()
    if not text:
        return ""
    text = normalize_apostrophes(text)
    parts = []
    for word in text.split(" "):
        if not word:
            continue
        parts.append(word[:1].upper() + word[1:].lower() if word.isalpha() else _titlecase_mixed(word))
    return " ".join(parts)


def _titlecase_mixed(word: str) -> str:
    """Apostrof yoki chiziqcha bo'lgan so'zni to'g'ri bosh harflaydi."""
    result = []
    capitalize_next = True
    for ch in word:
        if capitalize_next and ch.isalpha():
            result.append(ch.upper())
            capitalize_next = False
        else:
            result.append(ch.lower() if ch.isalpha() else ch)
            if ch in "-":
                capitalize_next = True
    return "".join(result)


def is_valid_full_name(raw: str) -> bool:
    """Ism-familiya kamida 2 ta so'zdan va 3 ta harfdan iborat ekanini tekshiradi."""
    cleaned = clean_full_name(raw)
    if len(cleaned) < 3 or len(cleaned) > 120:
        return False
    words = [w for w in cleaned.split(" ") if len(w) >= 2]
    if len(words) < 2:
        return False
    return sum(ch.isalpha() for ch in cleaned) >= 3


# --- Telefon ---------------------------------------------------------------

_PHONE_CLEAN_RE = re.compile(r"[^\d+]")


def normalize_phone(raw: str) -> str:
    """Telefon raqamini +998XXXXXXXXX ko'rinishiga keltiradi (imkon qadar)."""
    if not raw:
        return ""
    text = _PHONE_CLEAN_RE.sub("", str(raw))
    if not text:
        return ""
    if text.startswith("+"):
        digits = text[1:]
    else:
        digits = text
    digits = re.sub(r"\D", "", digits)
    if not digits:
        return ""
    if len(digits) == 9:  # 901234567
        digits = "998" + digits
    elif len(digits) == 12 and digits.startswith("998"):
        pass
    return "+" + digits


# --- Kesish ----------------------------------------------------------------

def shorten(text: str, limit: int, suffix: str = "…") -> str:
    """Matnni belgilangan uzunlikkacha qisqartiradi."""
    if text is None:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    if limit <= len(suffix):
        return text[:limit]
    return text[: limit - len(suffix)].rstrip() + suffix


def chunk_text(text: str, limit: int) -> list[str]:
    """Uzun matnni qator chegarasini buzmagan holda bo'laklarga ajratadi."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def slugify_filename(text: str, default: str = "fayl") -> str:
    """Fayl nomi uchun xavfsiz satr yasaydi."""
    text = to_ascii_apostrophes(text or "")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return text[:60] or default


__all__ = [
    "CANONICAL_APOSTROPHE",
    "normalize_apostrophes",
    "to_ascii_apostrophes",
    "esc",
    "clean_full_name",
    "is_valid_full_name",
    "normalize_phone",
    "shorten",
    "chunk_text",
    "slugify_filename",
]
