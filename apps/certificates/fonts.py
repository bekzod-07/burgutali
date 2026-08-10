"""
Sertifikat PDF fayli uchun shriftlarni tayyorlash.

O'zbek lotin alifbosida `oʻ`, `gʻ` kabi maxsus belgilar ishlatiladi.
ReportLab ning standart (Type-1) shriftlari bu belgilarni qo'llab-quvvatlamaydi,
shuning uchun tizimda mavjud Unicode TTF shrifti izlanadi va ro'yxatdan
o'tkaziladi.

Izlash tartibi:
  1. `assets/fonts/` katalogi (loyiha bilan birga keladigan shriftlar);
  2. operatsion tizimning standart shriftlari;
  3. hech nima topilmasa — `Helvetica` va matnni transliteratsiya qilish.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from core.env import BASE_DIR

logger = logging.getLogger(__name__)

#: Loyiha bilan birga keladigan shriftlar katalogi.
ASSETS_FONTS_DIR = BASE_DIR / "assets" / "fonts"

#: (oddiy, qalin) juftliklari — birinchi topilgani ishlatiladi.
FONT_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
    ("Roboto-Regular.ttf", "Roboto-Bold.ttf"),
    ("arial.ttf", "arialbd.ttf"),
    ("Arial.ttf", "Arial Bold.ttf"),
    ("segoeui.ttf", "segoeuib.ttf"),
    ("tahoma.ttf", "tahomabd.ttf"),
    ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
    ("FreeSans.ttf", "FreeSansBold.ttf"),
    ("Helvetica.ttc", "Helvetica.ttc"),
)

#: Shriftlar izlanadigan kataloglar.
SEARCH_DIRS: tuple[Path, ...] = (
    ASSETS_FONTS_DIR,
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/freefont"),
    Path("/usr/share/fonts/TTF"),
    Path("/usr/share/fonts"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
)


@dataclass(frozen=True)
class FontPair:
    """Sertifikatda ishlatiladigan shrift nomlari."""

    regular: str
    bold: str
    unicode_ready: bool

    @property
    def needs_transliteration(self) -> bool:
        return not self.unicode_ready


_CACHED: FontPair | None = None


def _find_font(filename: str) -> Path | None:
    """Berilgan nomdagi shrift faylini izlaydi."""
    for directory in SEARCH_DIRS:
        try:
            if not directory.exists():
                continue
            candidate = directory / filename
            if candidate.is_file():
                return candidate
        except OSError:  # pragma: no cover - ruxsat yo'q bo'lishi mumkin
            continue
    return None


def font_files() -> tuple[Path | None, Path | None]:
    """
    Birinchi topilgan Unicode TTF juftligining fayl yo'llarini qaytaradi.

    ReportLab dan tashqari kutubxonalar (masalan, diagramma chizadigan
    Pillow) uchun kerak — ular shrift nomi emas, fayl yo'lini kutadi.
    Hech nima topilmasa `(None, None)` qaytadi.
    """
    for regular_name, bold_name in FONT_CANDIDATES:
        regular_path = _find_font(regular_name)
        if regular_path is None:
            continue
        return regular_path, _find_font(bold_name) or regular_path
    return None, None


def register_fonts() -> FontPair:
    """
    Unicode shriftni ro'yxatdan o'tkazadi va nomlarini qaytaradi.

    Natija keshlanadi — takroriy chaqiruvlar tez ishlaydi.
    """
    global _CACHED
    if _CACHED is not None:
        return _CACHED

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:  # pragma: no cover - reportlab o'rnatilmagan
        _CACHED = FontPair("Helvetica", "Helvetica-Bold", False)
        return _CACHED

    for regular_name, bold_name in FONT_CANDIDATES:
        regular_path = _find_font(regular_name)
        if regular_path is None:
            continue
        bold_path = _find_font(bold_name) or regular_path
        try:
            pdfmetrics.registerFont(TTFont("CertFont", str(regular_path)))
            pdfmetrics.registerFont(TTFont("CertFont-Bold", str(bold_path)))
            try:
                from reportlab.pdfbase.pdfmetrics import registerFontFamily

                registerFontFamily(
                    "CertFont", normal="CertFont", bold="CertFont-Bold",
                    italic="CertFont", boldItalic="CertFont-Bold",
                )
            except Exception:  # pragma: no cover
                pass
            logger.info("Sertifikat shrifti: %s", regular_path)
            _CACHED = FontPair("CertFont", "CertFont-Bold", True)
            return _CACHED
        except Exception as exc:  # pragma: no cover
            logger.debug("Shrift yuklanmadi (%s): %s", regular_path, exc)
            continue

    logger.warning(
        "Unicode shrift topilmadi — Helvetica ishlatiladi. "
        "Yaxshiroq natija uchun assets/fonts/ ga DejaVuSans.ttf ni joylang."
    )
    _CACHED = FontPair("Helvetica", "Helvetica-Bold", False)
    return _CACHED


# --------------------------------------------------------------------------
#  Transliteratsiya (shrift topilmagan holat uchun)
# --------------------------------------------------------------------------

_TRANSLIT_MAP = {
    "ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "`": "'",
    "“": '"', "”": '"', "«": '"', "»": '"',
    "–": "-", "—": "-", "−": "-",
    "…": "...",
    "№": "No.",
    "•": "-", "·": "-",
    "✅": "", "❌": "", "🏅": "", "🎉": "", "📊": "", "🏆": "",
}


def safe_text(value: object, font: FontPair | None = None) -> str:
    """
    Matnni tanlangan shriftda chizishga tayyorlaydi.

    Unicode shrift mavjud bo'lsa matn o'zgarmaydi; aks holda
    maxsus belgilar Latin-1 ga mos ko'rinishga almashtiriladi.
    """
    text = "" if value is None else str(value)
    font = font or register_fonts()
    if font.unicode_ready:
        return text
    for src, dst in _TRANSLIT_MAP.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


__all__ = [
    "FontPair",
    "register_fonts",
    "font_files",
    "safe_text",
    "ASSETS_FONTS_DIR",
]
