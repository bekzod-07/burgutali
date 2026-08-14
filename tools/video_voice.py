#!/usr/bin/env python
"""
Video dars uchun o'zbekcha diktor ovozi.

Modul uchta ishni bajaradi:

  1. matnni o'zbek tilidagi neyron ovoz bilan o'qib beradi (Microsoft Edge
     TTS, `uz-UZ-SardorNeural`) va natijani keshlaydi;
  2. har bir gapning videodagi boshlanish vaqtini yozib boradi;
  3. yozuv tugagach barcha gaplarni bitta tovush yo'lagiga terib, videoga
     qo'shadi hamda subtitr (`.srt`) faylini yozadi.

Internet bo'lmasa yoki `edge-tts` o'rnatilmagan bo'lsa modul jimgina
o'chadi — video baribir yoziladi, faqat ovozsiz.

O'rnatish:

    pip install edge-tts
"""

from __future__ import annotations

import hashlib
import html as html_mod
import os
import re
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "video" / "voice"

VOICE = os.environ.get("VIDEO_VOICE", "uz-UZ-SardorNeural")
RATE = os.environ.get("VIDEO_VOICE_RATE", "+6%")

# Gaplar orasidagi tabiiy tanaffus (soniya).
GAP = 0.42

SAMPLE_RATE = 48000
BYTES_PER_SAMPLE = 2


# ==========================================================================
#  Matnni ovoz uchun tayyorlash
# ==========================================================================

# Diktor to'g'ri o'qishi uchun almashtiriladigan belgi va qisqartmalar.
REPLACEMENTS: list[tuple[str, str]] = [
    ("Rasch", "Rash"),
    ("RASH", "Rash"),
    ("IRT-1PL", "I-R-T bir P-L"),
    ("KR-20", "Ka-Er yigirma"),
    ("SymPy", "SimPay"),
    ("QR", "Kyu-Ar"),
    ("ID", "Ay-Di"),
    ("PDF", "Pe-De-Ef"),
    ("initData", "init-data"),
    ("θ", "teta"),
    ("π", "pi"),
    ("√", "kvadrat ildiz"),
    ("∛", "kub ildiz"),
    ("≤", "kichik yoki teng"),
    ("≥", "katta yoki teng"),
    ("≠", "teng emas"),
    ("⁻¹", " minus birinchi darajada"),
    ("²", " kvadrat"),
    ("|x|", "modul iks"),
    ("A+", "A plyus"),
    ("B+", "B plyus"),
    ("C+", "C plyus"),
    ("→", ", so'ng "),
    ("·", ", "),
    ("«", ""),
    ("»", ""),
    ("✓", "to'g'ri belgisi"),
    ("✗", "xato belgisi"),
    ("●", "belgi"),
    ("%", " foiz"),
    ("№", "raqam "),
    ("&", " va "),
]


def speech_text(text: str) -> str:
    """Ekrandagi izohni diktor o'qiy oladigan ko'rinishga keltiradi."""
    out = re.sub(r"<[^>]+>", " ", text or "")
    out = html_mod.unescape(out)

    for src, dst in REPLACEMENTS:
        out = out.replace(src, dst)

    # «1–32» -> «1 dan 32 gacha» (savol oraliqlari)
    out = re.sub(r"(\d+)\s*[–—]\s*(\d+)", r"\1 dan \2 gacha", out)
    # «A–F» -> «A dan F gacha» (variant oraliqlari)
    out = re.sub(r"\b([A-F])\s*[–—]\s*([A-F])\b", r"\1 dan \2 gacha", out)
    # «90.14» -> «90 butun 14»
    out = re.sub(r"(\d+)[.,](\d+)", r"\1 butun \2", out)
    # «A/B/C/D» -> «A, B, C, D»
    out = re.sub(r"\b([A-F])/(?=[A-F]\b)", r"\1, ", out)
    # «1/2» -> «bir bo'lingan ikki», «sin(» -> «sinus»
    out = re.sub(r"(\d+)\s*/\s*(\d+)", r"\1 bo‘lingan \2", out)
    out = re.sub(r"\bsin\s*\(", "sinus (", out)
    out = re.sub(r"\bcos\s*\(", "kosinus (", out)
    out = out.replace("=", " teng ")
    # Tire — gap ichida qisqa tanaffus
    out = out.replace("—", ", ").replace("–", ", ")

    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    out = re.sub(r"(,\s*){2,}", ", ", out)
    return out


# ==========================================================================
#  Ovoz sintezi
# ==========================================================================


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil

        return shutil.which("ffmpeg")


def media_duration(path: Path) -> float:
    """Fayl davomiyligi (soniya). ffmpeg chiqishidan o'qiladi."""
    exe = _ffmpeg()
    if not exe:
        return 0.0
    result = subprocess.run(
        [exe, "-i", str(path)], capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr or "")
    if not match:
        return 0.0
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


@dataclass
class Clip:
    """Videoning ma'lum bir soniyasida yangraydigan gap."""

    start: float          # yozuv boshidan hisoblangan vaqt (soniya)
    duration: float
    path: Path
    text: str             # subtitr uchun (asl, belgilangan ko'rinishda)


class Narrator:
    """Matnni ovozga aylantiradi va vaqt jadvalini yuritadi."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.clips: list[Clip] = []
        self.free_at = 0.0          # navbatdagi gap eng erta qachon boshlanadi
        self.enabled = enabled
        self.failed = False
        self._misses = 0
        if enabled:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def synth(self, text: str) -> tuple[Path, float] | None:
        """Matnni ovozga aylantiradi (keshdan oladi). None — ovoz yo'q."""
        if not self.enabled or self.failed:
            return None

        spoken = speech_text(text)
        if not spoken:
            return None

        key = hashlib.sha1(f"{VOICE}|{RATE}|{spoken}".encode("utf-8")).hexdigest()[:16]
        path = CACHE_DIR / f"{key}.mp3"

        if not path.exists():
            self._misses += 1
            try:
                self._download(spoken, path)
            except Exception as exc:  # tarmoq yo'q, paket yo'q va h.k.
                print(f"  [!] ovoz olinmadi ({exc.__class__.__name__}: "
                      f"{str(exc)[:120]}) — video ovozsiz davom etadi")
                self.failed = True
                if path.exists():
                    path.unlink(missing_ok=True)
                return None

        duration = media_duration(path)
        if duration <= 0:
            path.unlink(missing_ok=True)
            return None
        return path, duration

    @staticmethod
    def _download(spoken: str, path: Path) -> None:
        """Ovozni Edge TTS dan oladi.

        Sintez alohida oqimda bajariladi: Playwright ning sinxron API si
        shu oqimda o'z asyncio siklini yuritadi va `asyncio.run()` u yerda
        ishlamaydi.
        """
        import asyncio
        import threading

        import edge_tts

        tmp = path.with_suffix(".part")
        box: dict[str, BaseException] = {}

        async def run() -> None:
            speech = edge_tts.Communicate(spoken, VOICE, rate=RATE)
            await speech.save(str(tmp))

        def worker() -> None:
            try:
                asyncio.run(run())
            except BaseException as exc:      # noqa: BLE001 - oqimdan uzatamiz
                box["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=90)
        if "error" in box:
            raise box["error"]
        if thread.is_alive() or not tmp.exists() or tmp.stat().st_size < 400:
            raise RuntimeError("ovoz olinmadi")
        tmp.replace(path)

    # ------------------------------------------------------------------
    def queue(self, text: str, at: float) -> float:
        """Gapni jadvalga qo'yadi. Qaytaradi: gap tugaydigan vaqt."""
        made = self.synth(text)
        if made is None:
            return at

        path, duration = made
        start = max(at, self.free_at)
        self.clips.append(Clip(start=start, duration=duration, path=path, text=text))
        self.free_at = start + duration + GAP
        return self.free_at

    # ------------------------------------------------------------------
    @property
    def prefetched(self) -> bool:
        """Barcha gaplar keshdan olindimi (yozuv silliq ketadimi)."""
        return self._misses == 0


# ==========================================================================
#  Tovush yo'lagini yig'ish va videoga qo'shish
# ==========================================================================


def _pcm(path: Path) -> bytes:
    exe = _ffmpeg()
    if not exe:
        return b""
    result = subprocess.run(
        [exe, "-v", "error", "-i", str(path), "-f", "s16le",
         "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True,
    )
    return result.stdout or b""


def build_track(clips: list[Clip], total_seconds: float, out: Path,
                *, scale: float = 1.0) -> Path | None:
    """Barcha gaplarni bitta WAV yo'lagiga teradi."""
    if not clips:
        return None

    length = int((total_seconds + 1.0) * SAMPLE_RATE) * BYTES_PER_SAMPLE
    track = bytearray(length)

    for clip in clips:
        data = _pcm(clip.path)
        if not data:
            continue
        offset = int(clip.start * scale * SAMPLE_RATE) * BYTES_PER_SAMPLE
        if offset + len(data) > len(track):
            track.extend(b"\x00" * (offset + len(data) - len(track)))
        track[offset:offset + len(data)] = data

    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(BYTES_PER_SAMPLE)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(track))
    return out


def _stamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def write_srt(clips: list[Clip], out: Path, *, scale: float = 1.0) -> Path | None:
    """Subtitr fayli — YouTube va Telegram uchun."""
    if not clips:
        return None

    lines: list[str] = []
    for i, clip in enumerate(clips, start=1):
        text = re.sub(r"<[^>]+>", "", clip.text)
        text = html_mod.unescape(text).strip()
        start = clip.start * scale
        end = start + clip.duration * scale
        lines.append(str(i))
        lines.append(f"{_stamp(start)} --> {_stamp(end)}")
        lines.append(text)
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def mux(video: Path, audio: Path | None, mp4: Path) -> Path | None:
    """Videoni mp4 ga o'giradi va tovush yo'lagini qo'shadi."""
    exe = _ffmpeg()
    if not exe:
        print("  [i] ffmpeg topilmadi — video faqat webm formatida qoldi.")
        return None

    cmd = [exe, "-y", "-i", str(video)]
    if audio is not None:
        cmd += ["-i", str(audio)]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if audio is not None:
        cmd += ["-c:a", "aac", "-b:a", "160k", "-ac", "2",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    cmd.append(str(mp4))

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    if result.returncode != 0:
        print("  [!] mp4 ga o'girish bajarilmadi:")
        print("     ", (result.stderr or "")[-500:])
        return None
    return mp4
