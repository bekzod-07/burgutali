"""
Matematik ifodalarni tahlil qilish va ekvivalentlikka tekshirish.

TZ 4-bo'lim: 36–45-savollarning javoblari SymPy yordamida *matematik
ekvivalentlik* bo'yicha tekshiriladi. Ya'ni `1/2`, `0.5` va `2^-1` bir xil
javob hisoblanadi; `sin(pi/6)` esa `0.5` ga teng.

Modul Django ga bog'liq emas — uni Mini App validatsiyasida ham,
bot baholashida ham ishlatish mumkin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# --------------------------------------------------------------------------
#  Sozlamalar
# --------------------------------------------------------------------------

#: Kiritish uzunligi chegarasi (SymPy ni juda og'ir ifodalardan himoya qiladi).
MAX_INPUT_LENGTH = 256

#: Muqobil to'g'ri javoblarni ajratuvchi belgi (kalit ichida).
ALTERNATIVE_SEPARATOR = ";"

#: Standart sonli xatolik chegarasi.
DEFAULT_TOLERANCE = 1e-6


# --------------------------------------------------------------------------
#  Normalizatsiya
# --------------------------------------------------------------------------

#: Bitta belgini bevosita almashtirish jadvali.
_CHAR_MAP = {
    "×": "*", "·": "*", "∙": "*", "⋅": "*", "х": "*",
    "÷": "/", ":": "/", "∶": "/",
    "−": "-", "–": "-", "—": "-", "‒": "-",
    "π": "pi", "𝜋": "pi",
    "∞": "oo",
    "≤": "<=", "≥": ">=", "≠": "!=",
    "≡": "=",
    "，": ",", "。": ".",
    "＝": "=",
    "’": "", "‘": "", "ʻ": "",
    " ": " ",  # bo'linmas probel
    "°": "*pi/180",
    "%": "/100",
    "√": "sqrt",
    "∛": "cbrt",
}

#: Yuqori indekslar (daraja).
_SUPERSCRIPTS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁺": "+", "⁻": "-", "ⁿ": "n",
}

#: Funksiya nomlarini SymPy nomlariga moslashtirish (o'zbek/rus yozuvi).
_FUNCTION_ALIASES = (
    (r"\barcctg\b", "acot"),
    (r"\barctg\b", "atan"),
    (r"\barcsin\b", "asin"),
    (r"\barccos\b", "acos"),
    (r"\barctan\b", "atan"),
    (r"\bctg\b", "cot"),
    (r"\btg\b", "tan"),
    (r"\bln\b", "log"),
    (r"\blg\b", "log10"),
    (r"\bmod\b", "%"),
)


def _replace_superscripts(text: str) -> str:
    """`x²` -> `x**2` ko'rinishiga o'tkazadi."""
    out: list[str] = []
    buffer: list[str] = []
    for ch in text:
        if ch in _SUPERSCRIPTS:
            buffer.append(_SUPERSCRIPTS[ch])
            continue
        if buffer:
            out.append("**(" + "".join(buffer) + ")")
            buffer = []
        out.append(ch)
    if buffer:
        out.append("**(" + "".join(buffer) + ")")
    return "".join(out)


def _expand_radicals(text: str) -> str:
    """`sqrt2`, `sqrt(3)`, `sqrt 5` ko'rinishlarini `sqrt(...)` ga keltiradi."""
    # sqrt dan keyin qavs bo'lmasa — keyingi son yoki o'zgaruvchini qavsga olamiz.
    pattern = re.compile(r"\b(sqrt|cbrt)\s*(?!\()([A-Za-z0-9_.]+)")
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(lambda m: f"{m.group(1)}({m.group(2)})", text)
    return text


def _expand_abs(text: str) -> str:
    """`|x|` -> `Abs(x)`."""
    pattern = re.compile(r"\|([^|]+)\|")
    prev = None
    while prev != text and "|" in text:
        prev = text
        text = pattern.sub(lambda m: f"Abs({m.group(1)})", text)
    return text.replace("|", "")


#: Vergul argument ajratuvchi bo'lib keladigan funksiyalar: `root(8,3)`,
#: `log(100,10)` — bu yerdagi vergulni kasr nuqtasiga aylantirib bo'lmaydi.
_TWO_ARG_FUNCTIONS = frozenset(
    {"root", "log", "gcd", "lcm", "binomial", "rational", "atan2"}
)


def _fix_decimal_commas(text: str) -> str:
    """
    Raqamlar orasidagi vergulni nuqtaga o'zgartiradi (0,5 -> 0.5).

    Istisno: ikki argumentli funksiya qavslari ichida vergul argument
    ajratuvchi hisoblanadi — `root(8,3)` va `log(100,10)` o'zgarmaydi
    (aks holda `root(8.3)` tahlil qilinmay, `log(100.10)` esa noto'g'ri
    natija berar edi).
    """
    result: list[str] = []
    stack: list[bool] = []  # har bir ochiq qavs: 2 argumentli funksiya qavsimi
    for index, char in enumerate(text):
        if char == "(":
            j = index - 1
            while j >= 0 and (text[j].isalnum() or text[j] == "_"):
                j -= 1
            name = text[j + 1 : index].lower()
            stack.append(name in _TWO_ARG_FUNCTIONS)
        elif char == ")":
            if stack:
                stack.pop()
        elif char == ",":
            separator_context = stack[-1] if stack else False
            prev_digit = index > 0 and text[index - 1].isdigit()
            next_digit = index + 1 < len(text) and text[index + 1].isdigit()
            if prev_digit and next_digit and not separator_context:
                result.append(".")
                continue
        result.append(char)
    return "".join(result)


def normalize_expression(raw: str) -> str:
    """Foydalanuvchi kiritgan ifodani SymPy tushunadigan ko'rinishga keltiradi."""
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""

    # 1. Vergul -> nuqta (faqat sonlar orasida)
    text = _fix_decimal_commas(text)

    # 2. Yuqori indekslar
    text = _replace_superscripts(text)

    # 3. Belgilarni almashtirish
    for src, dst in _CHAR_MAP.items():
        if src in text:
            text = text.replace(src, dst)

    # 4. Modul belgisi
    text = _expand_abs(text)

    # 5. Funksiya nomlari
    for pattern, replacement in _FUNCTION_ALIASES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 6. Ildizlarni qavslash
    text = _expand_radicals(text)

    # 7. Daraja belgisi
    text = text.replace("^", "**")

    # 8. Ortiqcha probellar
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --------------------------------------------------------------------------
#  SymPy bilan ishlash
# --------------------------------------------------------------------------

_SYMPY_NAMESPACE: dict[str, Any] | None = None

#: Kiritishda umuman uchramasligi kerak bo'lgan naqshlar.
#: SymPy `parse_expr` ichida `eval` ishlatadi, shuning uchun Python
#: identifikatorlariga yo'l ochib beradigan har qanday belgi bloklanadi.
_FORBIDDEN_RE = re.compile(
    r"(__|\bimport\b|\bexec\b|\beval\b|\bopen\b|\bcompile\b|\bglobals\b|"
    r"\blocals\b|\bgetattr\b|\bsetattr\b|\blambda\b|\bclass\b|"
    r"[\[\]{}@#$~?\\\"']|:=)",
    re.IGNORECASE,
)


def is_safe_input(text: str) -> bool:
    """Kiritilgan matn xavfsizmi (kod bajarishga urinish yo'qmi)."""
    return not bool(_FORBIDDEN_RE.search(text or ""))


def _build_namespace() -> dict[str, Any]:
    """SymPy uchun ruxsat etilgan nomlar lug'ati (xavfsizlik uchun cheklangan)."""
    global _SYMPY_NAMESPACE
    if _SYMPY_NAMESPACE is not None:
        return _SYMPY_NAMESPACE

    import sympy as sp

    namespace: dict[str, Any] = {
        # Konstantalar
        "pi": sp.pi,
        "E": sp.E,
        "e": sp.E,
        "oo": sp.oo,
        "I": sp.I,
        # Asosiy funksiyalar
        "sqrt": sp.sqrt,
        "cbrt": sp.cbrt,
        "root": sp.root,
        "exp": sp.exp,
        "log": sp.log,
        "log10": lambda x: sp.log(x, 10),
        "log2": lambda x: sp.log(x, 2),
        "Abs": sp.Abs,
        "abs": sp.Abs,
        "sign": sp.sign,
        "factorial": sp.factorial,
        "floor": sp.floor,
        "ceiling": sp.ceiling,
        "Rational": sp.Rational,
        "Integer": sp.Integer,
        "Float": sp.Float,
        "gcd": sp.gcd,
        "lcm": sp.lcm,
        "binomial": sp.binomial,
        # Trigonometriya
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot,
        "sec": sp.sec, "csc": sp.csc,
        "asin": sp.asin, "acos": sp.acos, "atan": sp.atan, "acot": sp.acot,
        "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
        # Ko'p ishlatiladigan o'zgaruvchilar
        "x": sp.Symbol("x"), "y": sp.Symbol("y"), "z": sp.Symbol("z"),
        "a": sp.Symbol("a"), "b": sp.Symbol("b"), "c": sp.Symbol("c"),
        "n": sp.Symbol("n"), "m": sp.Symbol("m"), "k": sp.Symbol("k"),
        "t": sp.Symbol("t"),
        # `parse_expr` transformatsiyalari ishlatadigan ichki nomlar
        "Symbol": sp.Symbol,
        "Function": sp.Function,
        "Pow": sp.Pow,
        "Mul": sp.Mul,
        "Add": sp.Add,
        # Python ning o'rnatilgan funksiyalariga yo'l yopiladi:
        # `eval` globals ichida `__builtins__` mavjud bo'lgani uchun
        # uni bo'sh lug'at bilan almashtiramiz.
        "__builtins__": {},
    }
    _SYMPY_NAMESPACE = namespace
    return namespace


def parse_expression(raw: str):
    """
    Matnni SymPy ifodasiga aylantiradi.

    Muvaffaqiyatsiz bo'lsa `None` qaytaradi (istisno chiqarmaydi).

    Xavfsizlik: SymPy ning `parse_expr` funksiyasi ichida `eval` ishlatadi,
    shuning uchun ikki qatlamli himoya qo'llaniladi:
      1. shubhali belgilar va kalit so'zlar bo'lgan matn umuman qabul
         qilinmaydi (`is_safe_input`);
      2. `eval` uchun berilgan global lug'atda `__builtins__` bo'sh qilinadi —
         `__import__`, `open`, `eval` kabi funksiyalarga yo'l yo'q.
    """
    text = normalize_expression(raw)
    if not text or len(text) > MAX_INPUT_LENGTH:
        return None
    if not is_safe_input(text) or not is_safe_input(str(raw)):
        return None

    try:
        from sympy.parsing.sympy_parser import (
            convert_xor,
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )
    except Exception:  # pragma: no cover - sympy o'rnatilmagan
        return None

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )
    namespace = _build_namespace()
    try:
        return parse_expr(
            text,
            local_dict=dict(namespace),
            global_dict=dict(namespace),
            transformations=transformations,
            evaluate=True,
        )
    except Exception:
        return None


# --------------------------------------------------------------------------
#  Taqqoslash
# --------------------------------------------------------------------------

_RELATION_RE = re.compile(r"(<=|>=|!=|<|>|=)")


@dataclass(frozen=True)
class ComparisonResult:
    """Taqqoslash natijasi va uning sababi."""

    equal: bool
    method: str  # "sympy" | "numeric" | "text" | "empty"

    def __bool__(self) -> bool:
        return self.equal


def _numeric_value(expr) -> complex | None:
    """Ifodani songa aylantiradi (agar erkin o'zgaruvchi bo'lmasa)."""
    try:
        if expr.free_symbols:
            return None
        return complex(expr.evalf(20))
    except Exception:
        return None


def _compare_expressions(left, right, tolerance: float) -> bool:
    """Ikkita SymPy ifodasini ekvivalentlikka tekshiradi."""
    import sympy as sp

    if left is None or right is None:
        return False

    # 1. To'g'ridan-to'g'ri tenglik
    try:
        if left == right:
            return True
    except Exception:
        pass

    # 2. Sonli qiymatlar
    lv, rv = _numeric_value(left), _numeric_value(right)
    if lv is not None and rv is not None:
        return abs(lv - rv) <= max(tolerance, abs(rv) * tolerance)

    # 3. Erkin o'zgaruvchilar mos kelmasa — teng emas
    try:
        if left.free_symbols != right.free_symbols:
            return False
    except Exception:
        return False

    # 4. Simvolik ekvivalentlik
    try:
        verdict = left.equals(right)
        if verdict is True:
            return True
        if verdict is False:
            return False
    except Exception:
        pass

    try:
        diff = sp.simplify(sp.expand(left - right))
        return bool(diff == 0)
    except Exception:
        return False


def _split_relation(text: str) -> tuple[str, str, str] | None:
    """`x >= 2` kabi munosabatni (chap, belgi, o'ng) ko'rinishida qaytaradi."""
    normalized = normalize_expression(text)
    match = _RELATION_RE.search(normalized)
    if not match:
        return None
    op = match.group(1)
    left = normalized[: match.start()].strip()
    right = normalized[match.end():].strip()
    if not left or not right:
        return None
    return left, op, right


def _compare_relations(user_text: str, key_text: str, tolerance: float) -> bool | None:
    """Munosabatli (tenglik/tengsizlik) javoblarni taqqoslaydi."""
    user_rel = _split_relation(user_text)
    key_rel = _split_relation(key_text)
    if key_rel is None and user_rel is None:
        return None  # munosabat yo'q — oddiy taqqoslashga o'tiladi
    if key_rel is None or user_rel is None:
        return False

    u_left, u_op, u_right = user_rel
    k_left, k_op, k_right = key_rel
    if u_op != k_op:
        return False
    return _compare_expressions(
        parse_expression(u_left), parse_expression(k_left), tolerance
    ) and _compare_expressions(
        parse_expression(u_right), parse_expression(k_right), tolerance
    )


def _text_equal(user: str, key: str) -> bool:
    """Oxirgi chora: matnlarni normallashtirib solishtirish."""
    def clean(value: str) -> str:
        return re.sub(r"\s+", "", normalize_expression(value)).lower()

    return bool(user) and clean(user) == clean(key)


def compare_answer(
    user_answer: str,
    correct_answer: str,
    tolerance: float = DEFAULT_TOLERANCE,
) -> ComparisonResult:
    """
    Foydalanuvchi javobini kalit bilan taqqoslaydi.

    Kalitda `;` orqali bir nechta muqobil to'g'ri javob berilishi mumkin
    (masalan: ``0.5;1/2``).
    """
    user_answer = (user_answer or "").strip()
    correct_answer = (correct_answer or "").strip()

    if not correct_answer:
        return ComparisonResult(False, "empty")
    if not user_answer:
        return ComparisonResult(False, "empty")

    alternatives = [
        alt.strip()
        for alt in correct_answer.split(ALTERNATIVE_SEPARATOR)
        if alt.strip()
    ] or [correct_answer]

    for alternative in alternatives:
        # 1. Munosabatli javoblar (tengsizlik/tenglik)
        relation_verdict = _compare_relations(user_answer, alternative, tolerance)
        if relation_verdict is True:
            return ComparisonResult(True, "sympy")
        if relation_verdict is False and _split_relation(alternative) is not None:
            continue

        # 2. Oddiy ifodalar
        user_expr = parse_expression(user_answer)
        key_expr = parse_expression(alternative)
        if user_expr is not None and key_expr is not None:
            if _compare_expressions(user_expr, key_expr, tolerance):
                return ComparisonResult(True, "sympy")
            continue

        # 3. Matn sifatida solishtirish (ifoda tahlil qilinmaganda)
        if _text_equal(user_answer, alternative):
            return ComparisonResult(True, "text")

    return ComparisonResult(False, "sympy")


def is_equivalent(
    user_answer: str,
    correct_answer: str,
    tolerance: float = DEFAULT_TOLERANCE,
) -> bool:
    """`compare_answer` ning qisqa ko'rinishi."""
    return bool(compare_answer(user_answer, correct_answer, tolerance))


def pretty_expression(raw: str) -> str:
    """Ifodani o'qishga qulay ko'rinishda qaytaradi (ekranda ko'rsatish uchun)."""
    expr = parse_expression(raw)
    if expr is None:
        return (raw or "").strip()
    try:
        import sympy as sp

        return str(sp.nsimplify(expr, rational=False))
    except Exception:
        return str(expr)


__all__ = [
    "MAX_INPUT_LENGTH",
    "ALTERNATIVE_SEPARATOR",
    "DEFAULT_TOLERANCE",
    "ComparisonResult",
    "is_safe_input",
    "normalize_expression",
    "parse_expression",
    "compare_answer",
    "is_equivalent",
    "pretty_expression",
]
