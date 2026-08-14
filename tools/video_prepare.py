#!/usr/bin/env python
"""
Video dars uchun tayyorgarlik.

Videoda ochiq savollar va matematik klaviaturani ko'rsatish uchun **faol**
milliy shablon testi kerak — demo ma'lumotdagi testlar esa allaqachon
yakunlangan va natijalari e'lon qilingan. Shu skript video uchun bitta
yangi, hech kim topshirmagan faol test yaratadi.

Test nomi «DEMO» bilan boshlanadi, shuning uchun uni
`python tools/demo_data.py --clean` o'chirib tashlaydi.

Ishga tushirish:

    python tools\\video_prepare.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.django_setup import setup_django  # noqa: E402

setup_django()

from apps.exams.models import Exam  # noqa: E402
from apps.exams.services import (  # noqa: E402
    activate_exam,
    apply_multi_keys,
    apply_open_keys,
    apply_single_keys,
    create_exam,
)
from apps.users.models import BotUser  # noqa: E402

TITLE = "DEMO — MILLIY SERTIFIKAT MOCK (jonli)"

# Video davomida web ilovaga aynan shu foydalanuvchi nomidan kiramiz.
VIDEO_USER_ID = 900000001


def reset_video_attempts() -> None:
    """Video foydalanuvchisining faol testlardagi urinishlarini tozalaydi.

    Videoni qayta yozganda test «allaqachon topshirilgan» holatda
    qolmasligi uchun kerak. Yakunlangan demo testlardagi natijalar
    tegilmaydi — ular ilovada ko'rinib turishi kerak.
    """
    from apps.attempts.models import Attempt

    stale = Attempt.objects.filter(
        user__telegram_id=VIDEO_USER_ID, exam__status=Exam.Status.ACTIVE
    )
    count = stale.count()
    if count:
        stale.delete()
        print(f"  video foydalanuvchisining {count} ta urinishi tozalandi")


def main() -> int:
    owner = BotUser.objects.filter(is_admin=True).order_by("id").first()
    if owner is None:
        print("[XATO] Admin foydalanuvchi topilmadi. Avval demo_data.py --reset")
        return 1

    # Oldingi yozuvdan qolgan nusxani olib tashlaymiz
    old = Exam.objects.filter(title=TITLE)
    if old.exists():
        count = old.count()
        old.delete()
        print(f"  eski nusxa o'chirildi ({count} ta)")

    exam = create_exam(
        owner=owner,
        title=TITLE,
        exam_type=Exam.Type.RASCH_FREE,
        national_template=True,
        description="45 ta savol: 1–32 (A–D), 33–35 (A–F), 36–45 (ochiq javob).",
        show_results=True,
    )
    apply_single_keys(exam, ["ABCD"[i % 4] for i in range(32)])
    apply_multi_keys(exam, ["A", "C", "E"])
    apply_open_keys(
        exam,
        [
            "12||3/4", "1/2||0.25", "sqrt(2)||pi/6", "5||-3", "0||1",
            "2^3||9", "sin(pi/2)||cos(0)", "10||100", "1/3||2/3", "7||8",
        ],
    )
    ok, message = activate_exam(exam)

    exam.refresh_from_db()
    print(f"Tayyor: {exam.code} — {exam.questions.count()} ta savol, holati: {exam.status}")
    if not ok:
        print(f"  [!] {message}")

    reset_video_attempts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
