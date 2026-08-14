#!/usr/bin/env python
"""
Video darsning ovozli variantini tayyorlaydi.

`tools/video_lesson.py` yozib bergan diktor yo'lagidan (`dars_ovoz.wav`)
uchta narsa chiqariladi:

  * `dars_ovoz.ogg`  — Telegramda **ovozli xabar** ko'rinishida
    yuboriladigan format (OGG/Opus, mono);
  * `dars_ovoz.mp3`  — oddiy audio fayl;
  * `ovoz/NN-bob.ogg` — har bir bob alohida ovozli xabar
    (taymkodlar `boblar.txt` dan olinadi).

Ishga tushirish:

    python tools\\video_audio.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.video_voice import _ffmpeg, media_duration  # noqa: E402

OUT_DIR = BASE_DIR / "data" / "video"
TRACK = OUT_DIR / "dars_ovoz.wav"
PARTS_DIR = OUT_DIR / "ovoz"

# Telegram ovozli xabari: OGG/Opus, mono. 40 kbit/s nutq uchun yetarli.
OPUS_ARGS = ["-c:a", "libopus", "-b:a", "40k", "-ac", "1", "-ar", "48000",
             "-application", "voip", "-vbr", "on"]
MP3_ARGS = ["-c:a", "libmp3lame", "-q:a", "5", "-ac", "1", "-ar", "44100"]


def run(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("  [!] xato:", (result.stderr or "")[-300:])
        return False
    return True


def stamp_to_seconds(text: str) -> float:
    parts = [int(p) for p in text.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def read_chapters() -> list[tuple[float, str]]:
    path = OUT_DIR / "boblar.txt"
    if not path.exists():
        return []
    out: list[tuple[float, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(\d+:\d+(?::\d+)?)\s+(.+)$", line.strip())
        if match:
            out.append((stamp_to_seconds(match.group(1)), match.group(2)))
    return out


def slug(name: str) -> str:
    table = str.maketrans("‘’ʻʼ", "''''")
    text = name.translate(table).lower()
    text = (text.replace("‘", "'").replace("o'", "o").replace("g'", "g")
                .replace("’", ""))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "bob"


def main() -> int:
    exe = _ffmpeg()
    if not exe:
        print("[XATO] ffmpeg topilmadi.")
        return 1
    if not TRACK.exists():
        print(f"[XATO] {TRACK} topilmadi — avval: python tools\\video_lesson.py")
        return 1

    total = media_duration(TRACK)
    print(f"Diktor yo'lagi: {total / 60:.1f} daqiqa")

    ogg = OUT_DIR / "dars_ovoz.ogg"
    mp3 = OUT_DIR / "dars_ovoz.mp3"

    print("Ovozli xabar (OGG/Opus)...")
    if run([exe, "-y", "-i", str(TRACK), *OPUS_ARGS, str(ogg)]):
        print(f"  {ogg}  ({ogg.stat().st_size / 1024 / 1024:.1f} MB)")

    print("Audio fayl (MP3)...")
    if run([exe, "-y", "-i", str(TRACK), *MP3_ARGS, str(mp3)]):
        print(f"  {mp3}  ({mp3.stat().st_size / 1024 / 1024:.1f} MB)")

    chapters = read_chapters()
    if not chapters:
        print("[i] boblar.txt topilmadi — bo'limlarga bo'linmadi.")
        return 0

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    for old in PARTS_DIR.glob("*.ogg"):
        old.unlink()

    print(f"Boblar bo'yicha bo'lish ({len(chapters)} ta)...")
    for i, (start, name) in enumerate(chapters, start=1):
        end = chapters[i][0] if i < len(chapters) else total
        part = PARTS_DIR / f"{i:02d}-{slug(name)}.ogg"
        cmd = [exe, "-y", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}",
               "-i", str(TRACK), *OPUS_ARGS, str(part)]
        if run(cmd):
            print(f"  {part.name}  ({(end - start) / 60:.1f} daq, "
                  f"{part.stat().st_size / 1024:.0f} KB)")

    print(f"\nBo'limlar: {PARTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
