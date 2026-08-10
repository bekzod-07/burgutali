#!/usr/bin/env python
"""
Telegram botni ishga tushirish uchun qulay kirish nuqtasi.

    python run_bot.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def main() -> None:
    from bot.main import main as run_bot

    run_bot()


if __name__ == "__main__":
    main()
