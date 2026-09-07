"""
Ochiq javoblarni tekshirish (ona tili fani).

36–45-savollarning javobi — so'z, so'z birikmasi yoki qisqa ibora. Shuning
uchun taqqoslash **matn** bo'yicha bajariladi: qatnashchi yozgani va kalit
bir xil ko'rinishga keltirilib solishtiriladi.

Nima e'tiborga olinmaydi:

  * katta-kichik harf — ``Ot`` = ``ot``;
  * apostrof ko'rinishi — ``o‘zbek`` = ``oʻzbek`` = ``o'zbek`` = ``o`zbek``;
  * apostrofning **umuman yo'qligi** — ``o‘rta`` = ``orta``, ``ma'no`` = ``mano``.
    Telefon klaviaturasida apostrof qiyin teriladi, shuning uchun uning
    bor-yo'qligi javobni xato qilmaydi;
  * ortiqcha probel va tinish belgilari — ``ot,`` = ``ot``;
  * bir necha probel — ``bosh  gap`` = ``bosh gap``;
  * chiziqcha turi — ``ko‘p–ma–ko‘p`` = ``ko‘p-ma-ko‘p``.

**Sinonimlar (muqobil javoblar).** Kalitda bir nechta to'g'ri javob
yozilishi mumkin — ular ``;``, ``,`` yoki ``/`` bilan ajratiladi va
har biri to'liq to'g'ri hisoblanadi:

    osmon; samo; fazo
    osmon, samo, fazo
    osmon / samo / fazo

Uchala yozuv ham bir xil ishlaydi: qatnashchi ``Samo.`` deb yozsa ham,
``FAZO`` deb yozsa ham javob to'g'ri hisoblanadi.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Kiritish uzunligi chegarasi.
MAX_INPUT_LENGTH = 255

#: Muqobil to'g'ri javoblarni ajratuvchi asosiy belgi — hujjatlarda va
#: interfeysda aynan shu ko'rsatiladi.
ALTERNATIVE_SEPARATOR = ";"

#: Kalitdagi sinonimlarni ajratuvchi barcha belgilar.
#:
#: Vergul ham ro'yxatda, chunki sinonimlar ro'yxatini odam odatda vergul
#: bilan yozadi («osmon, samo, fazo»). Bu javobning o'ziga zarar qilmaydi:
#: tinish belgilari taqqoslashda baribir hisobga olinmaydi.
ALTERNATIVE_SEPARATORS = ";,/"
_ALTERNATIVE_RE = re.compile(r"[;,/\n]+")

#: Barcha apostrof ko'rinishlari bitta belgiga keltiriladi.
_APOSTROPHES = "ʻʼ‘’‛`´ʹ′'"
_APOSTROPHE_RE = re.compile("[" + re.escape(_APOSTROPHES) + "]")

#: Tekshiruvda e'tiborga olinmaydigan tinish belgilari.
_PUNCTUATION_RE = re.compile(r"[.,!?:;\"«»„“”()\[\]{}…]+")

#: Chiziqchaning turli ko'rinishlari.
_DASH_RE = re.compile(r"[–—‒−]")

_SPACES_RE = re.compile(r"\s+")


def normalize_answer(raw: str) -> str:
    """Javobni taqqoslashga tayyor ko'rinishga keltiradi."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", str(raw))
    text = _APOSTROPHE_RE.sub("'", text)
    text = _DASH_RE.sub("-", text)
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text).strip().lower()
    return text


def fold_answer(raw: str) -> str:
    """
    Taqqoslashning eng erkin shakli: apostrof ham hisobga olinmaydi.

    ``o‘rta`` -> ``orta``, ``ma'no`` -> ``mano``, ``san’at`` -> ``sanat``.

    Telefonda ``oʻ`` va ``gʻ`` harflarini to'g'ri terish qiyin, ko'pchilik
    apostrofni umuman qo'ymaydi. Shu sababli javobning to'g'riligi
    apostrofga bog'lab qo'yilmaydi.
    """
    return normalize_answer(raw).replace("'", "")


def display_answer(raw: str) -> str:
    """Ekranda ko'rsatiladigan tozalangan ko'rinish (harflar saqlanadi)."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", str(raw))
    text = _APOSTROPHE_RE.sub("'", text)
    text = _DASH_RE.sub("-", text)
    return _SPACES_RE.sub(" ", text).strip()


def alternatives(correct_answer: str) -> list[str]:
    """
    Kalitdagi muqobil javoblar (sinonimlar) ro'yxati.

    Ajratkich sifatida ``;``, ``,`` va ``/`` qabul qilinadi, shuning uchun
    ``osmon; samo``, ``osmon, samo`` va ``osmon / samo`` bir xil natija
    beradi. Takrorlangan javoblar bir marta qoladi.
    """
    raw = (correct_answer or "").strip()
    if not raw:
        return []

    result: list[str] = []
    seen: set[str] = set()
    for piece in _ALTERNATIVE_RE.split(raw):
        piece = piece.strip()
        if not piece:
            continue
        marker = normalize_answer(piece)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(piece)
    return result or [raw]


@dataclass(frozen=True)
class ComparisonResult:
    """Taqqoslash natijasi va uning sababi."""

    equal: bool
    #: "text"       — javob kalitga aynan mos keldi;
    #: "apostrophe" — faqat apostrof farqi bilan mos keldi (u hisobga olinmadi);
    #: "empty"      — javob yoki kalit bo'sh.
    method: str

    def __bool__(self) -> bool:
        return self.equal


def compare_answer(
    user_answer: str,
    correct_answer: str,
    tolerance: float = 0.0,
) -> ComparisonResult:
    """
    Qatnashchi javobini kalit bilan solishtiradi.

    Kalitdagi har bir sinonim ikki bosqichda tekshiriladi: avval aynan
    moslik, so'ng apostrofsiz moslik (``orta`` = ``o‘rta``). Bittasi mos
    kelsa javob to'g'ri hisoblanadi.

    `tolerance` argumenti moslik uchun qabul qilinadi (ona tilida sonli
    xatolik tushunchasi yo'q), hisobga ta'sir qilmaydi.
    """
    user_answer = (user_answer or "").strip()[:MAX_INPUT_LENGTH]
    correct_answer = (correct_answer or "").strip()

    if not correct_answer or not user_answer:
        return ComparisonResult(False, "empty")

    given = normalize_answer(user_answer)
    if not given:
        return ComparisonResult(False, "empty")
    given_folded = fold_answer(user_answer)

    loose_match = False
    for alternative in alternatives(correct_answer):
        expected = normalize_answer(alternative)
        if not expected:
            continue
        if given == expected:
            return ComparisonResult(True, "text")
        expected_folded = fold_answer(alternative)
        if expected_folded and given_folded == expected_folded:
            loose_match = True

    if loose_match:
        return ComparisonResult(True, "apostrophe")
    return ComparisonResult(False, "text")


def is_equivalent(
    user_answer: str,
    correct_answer: str,
    tolerance: float = 0.0,
) -> bool:
    """`compare_answer` ning qisqa ko'rinishi."""
    return bool(compare_answer(user_answer, correct_answer, tolerance))


__all__ = [
    "MAX_INPUT_LENGTH",
    "ALTERNATIVE_SEPARATOR",
    "ALTERNATIVE_SEPARATORS",
    "ComparisonResult",
    "normalize_answer",
    "fold_answer",
    "display_answer",
    "alternatives",
    "compare_answer",
    "is_equivalent",
]
