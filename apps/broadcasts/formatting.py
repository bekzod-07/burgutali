"""
Reklama matni va tugmalarini tayyorlash.

Telegram xabar matnida HTML ning faqat kichik bir qismi qo'llanadi
(`<b>`, `<i>`, `<a href>` va h.k.). Administrator panelda erkin matn
yozadi, shuning uchun matn yuborishdan **oldin** tozalanadi:

  * ruxsat etilgan teglar o'z holicha qoladi;
  * qolgan barcha `<`, `>`, `&` belgilari ekranlanadi — aks holda
    Telegram butun xabarni rad etadi («can't parse entities»);
  * teglar juft emasligi formada xato sifatida ko'rsatiladi, ya'ni
    yuborish boshlanmasdan turib bilinadi.

Tugmalar oddiy matn ko'rinishida kiritiladi:

    Kanalga o'tish | https://t.me/Oybek_ustoz_MS
    Sayt | https://burgutali.uz || Bot | https://t.me/misol_bot

Har bir qator — klaviaturaning bir qatori; `||` bilan ajratilgan
tugmalar yonma-yon joylashadi.
"""

from __future__ import annotations

import re

#: Telegram qo'llaydigan teglar (Bot API, «HTML style» bo'limi).
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
        "code", "pre", "a", "tg-spoiler", "blockquote",
    }
)

#: Tugma havolasi uchun ruxsat etilgan sxemalar.
ALLOWED_SCHEMES: tuple[str, ...] = ("https://", "http://", "tg://")

#: Oddiy xabar va rasm izohi uchun belgilar chegarasi (Telegram limiti).
TEXT_LIMIT: int = 4096
CAPTION_LIMIT: int = 1024

#: Bitta klaviaturadagi chegaralar.
MAX_BUTTON_ROWS: int = 10
MAX_BUTTONS_PER_ROW: int = 3
MAX_BUTTON_TEXT: int = 64

_TAG_RE = re.compile(r"<\s*(/?)\s*([A-Za-z][A-Za-z0-9-]*)([^<>]*?)/?\s*>")
_HREF_RE = re.compile(
    r"""href\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+))""", re.IGNORECASE
)
_ENTITY_RE = re.compile(
    r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#\d{1,7}|#[xX][0-9A-Fa-f]{1,6});"
)


class FormatError(ValueError):
    """Matn yoki tugmalar noto'g'ri yozilgan."""


# --------------------------------------------------------------------------
#  Matn
# --------------------------------------------------------------------------


def _escape_text(chunk: str) -> str:
    """Teg bo'lmagan bo'lakni ekranlaydi (mavjud HTML-entity saqlanadi)."""
    result: list[str] = []
    position = 0
    for entity in _ENTITY_RE.finditer(chunk):
        result.append(chunk[position:entity.start()].replace("&", "&amp;"))
        result.append(entity.group(0))
        position = entity.end()
    result.append(chunk[position:].replace("&", "&amp;"))
    return "".join(result).replace("<", "&lt;").replace(">", "&gt;")


def sanitize_html(raw: str) -> str:
    """
    Matnni Telegram qabul qiladigan HTML ga aylantiradi.

    Teglar juft bo'lmasa `FormatError` chiqadi — shunda xato yuborishdan
    oldin, formaning o'zida ko'rinadi.
    """
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    output: list[str] = []
    stack: list[str] = []
    position = 0

    for match in _TAG_RE.finditer(text):
        output.append(_escape_text(text[position:match.start()]))
        position = match.end()

        closing = match.group(1) == "/"
        name = match.group(2).lower()
        attrs = match.group(3) or ""

        # `<br>` Telegram da qo'llanmaydi — qator uzilishiga aylantiramiz.
        if name == "br":
            if not closing:
                output.append("\n")
            continue

        if name not in ALLOWED_TAGS:
            output.append(_escape_text(match.group(0)))
            continue

        if closing:
            if not stack or stack[-1] != name:
                raise FormatError(
                    f"«{name}» tegi noto'g'ri yopilgan. Har bir ochilgan teg "
                    f"o'z tartibida yopilishi kerak."
                )
            stack.pop()
            output.append(f"</{name}>")
            continue

        if name == "a":
            href_match = _HREF_RE.search(attrs)
            href = ""
            if href_match:
                href = (
                    href_match.group(2)
                    or href_match.group(3)
                    or href_match.group(4)
                    or ""
                ).strip()
            if not href:
                raise FormatError("«a» tegida havola (href) ko'rsatilmagan.")
            if not href.lower().startswith(ALLOWED_SCHEMES):
                raise FormatError(
                    f"Havola https:// yoki tg:// bilan boshlanishi kerak: {href}"
                )
            stack.append(name)
            safe = href.replace("&", "&amp;").replace('"', "&quot;")
            output.append(f'<a href="{safe}">')
            continue

        stack.append(name)
        output.append(f"<{name}>")

    output.append(_escape_text(text[position:]))

    if stack:
        raise FormatError(
            "Quyidagi teglar yopilmagan: " + ", ".join(f"«{tag}»" for tag in stack)
        )

    return "".join(output)


def visible_length(html: str) -> int:
    """
    Xabarning ko'rinadigan uzunligi.

    Telegram chegarani teglarsiz matn bo'yicha hisoblaydi, shuning uchun
    formada ham aynan shu qiymat tekshiriladi.
    """
    return len(to_plain_text(html))


def to_plain_text(html: str) -> str:
    """HTML teglarsiz matn — xabar Telegram tomonidan rad etilsa ishlatiladi."""
    without_tags = _TAG_RE.sub("", html or "")
    return (
        without_tags.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )


# --------------------------------------------------------------------------
#  Tugmalar
# --------------------------------------------------------------------------


def parse_buttons(raw: str) -> list[list[dict[str, str]]]:
    """
    Matn ko'rinishidagi tugmalarni klaviatura tuzilmasiga aylantiradi.

    Natija — qatorlar ro'yxati, har bir qatorda `{"text": ..., "url": ...}`.
    """
    rows: list[list[dict[str, str]]] = []

    for number, line in enumerate((raw or "").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        row: list[dict[str, str]] = []
        for piece in line.split("||"):
            piece = piece.strip()
            if not piece:
                continue
            if "|" not in piece:
                raise FormatError(
                    f"{number}-qator: tugma «Matn | https://havola» ko'rinishida "
                    f"yozilishi kerak."
                )
            label, _, url = piece.partition("|")
            label = " ".join(label.split())
            url = url.strip()
            if not label:
                raise FormatError(f"{number}-qator: tugma matni bo'sh.")
            if len(label) > MAX_BUTTON_TEXT:
                raise FormatError(
                    f"{number}-qator: tugma matni {MAX_BUTTON_TEXT} belgidan uzun."
                )
            if not url:
                raise FormatError(f"{number}-qator: havola ko'rsatilmagan.")
            if not url.lower().startswith(ALLOWED_SCHEMES):
                raise FormatError(
                    f"{number}-qator: havola https:// yoki tg:// bilan "
                    f"boshlanishi kerak (hozir: {url})."
                )
            if any(ch.isspace() for ch in url):
                raise FormatError(f"{number}-qator: havolada bo'sh joy bo'lmaydi.")
            row.append({"text": label, "url": url})

        if not row:
            continue
        if len(row) > MAX_BUTTONS_PER_ROW:
            raise FormatError(
                f"{number}-qator: bir qatorda ko'pi bilan {MAX_BUTTONS_PER_ROW} ta "
                f"tugma bo'ladi."
            )
        rows.append(row)

    if len(rows) > MAX_BUTTON_ROWS:
        raise FormatError(f"Tugmalar ko'pi bilan {MAX_BUTTON_ROWS} qator bo'ladi.")

    return rows


def buttons_to_text(rows: list[list[dict[str, str]]] | None) -> str:
    """Klaviatura tuzilmasini formada qayta ko'rsatish uchun matnga o'giradi."""
    lines: list[str] = []
    for row in rows or []:
        parts = [
            f"{button.get('text', '')} | {button.get('url', '')}" for button in row
        ]
        lines.append(" || ".join(parts))
    return "\n".join(lines)


__all__ = [
    "ALLOWED_TAGS",
    "ALLOWED_SCHEMES",
    "TEXT_LIMIT",
    "CAPTION_LIMIT",
    "MAX_BUTTON_ROWS",
    "MAX_BUTTONS_PER_ROW",
    "MAX_BUTTON_TEXT",
    "FormatError",
    "sanitize_html",
    "visible_length",
    "to_plain_text",
    "parse_buttons",
    "buttons_to_text",
]
