#!/usr/bin/env python
"""
Video dars uchun bot suhbatini yozib olish.

Skript Telegram serveriga murojaat qilmaydi: `Bot.session` soxta sessiya
bilan almashtiriladi va botning **haqiqiy** handler'lari chaqiriladi.
Natijada suhbat tarixi (foydalanuvchi xabarlari + botning javoblari va
tugmalari) `data/video/bot_dialog.json` fayliga yoziladi — video darsning
Telegram sahnalari aynan shu ma'lumotdan quriladi.

Ishga tushirish:

    python tools\\video_bot_dialog.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Throttling middleware simulyatsiyani bloklamasligi uchun.
os.environ["BOT_THROTTLE_RATE"] = "0"

from core.django_setup import setup_django  # noqa: E402

setup_django()

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.methods import (  # noqa: E402
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    GetChatMember,
    GetMe,
    SendDocument,
    SendMessage,
)
from aiogram.types import (  # noqa: E402
    CallbackQuery,
    Chat,
    ChatMemberLeft,
    ChatMemberMember,
    Contact,
    Message,
    Update,
    User,
)

OUT_PATH = BASE_DIR / "data" / "video" / "bot_dialog.json"

TEACHER_ID = 900000801
STUDENT_ID = 900000802


# ==========================================================================
#  Soxta sessiya — yuborilgan hamma narsani yozib boradi
# ==========================================================================


class RecordingSession:
    """Telegram API o'rniga ishlaydigan, suhbatni yozib boruvchi sessiya."""

    def __init__(self) -> None:
        self.log: list[dict] = []
        self.subscribed: set[int] = set()
        self.current_chat: int | None = None
        self._message_id = 1000

    # ----------------------------------------------------------------
    async def __call__(self, bot: Bot, method, timeout=None):  # noqa: ANN001
        name = type(method).__name__

        if isinstance(method, SendMessage):
            self._record(method.chat_id, method.text or "", method.reply_markup)
            return self._make_message(bot, method.chat_id, method.text or "")

        if isinstance(method, SendDocument):
            filename = getattr(method.document, "filename", "fayl")
            data = getattr(method.document, "data", b"") or b""
            self._record(
                method.chat_id,
                method.caption or "",
                method.reply_markup,
                document={"filename": filename, "size": len(data)},
            )
            return self._make_message(bot, method.chat_id, method.caption or "")

        if isinstance(method, EditMessageText):
            self._record(
                method.chat_id or 0, method.text or "", method.reply_markup, edited=True
            )
            return self._make_message(bot, method.chat_id or 0, method.text or "")

        if isinstance(method, EditMessageReplyMarkup):
            return self._make_message(bot, method.chat_id or 0, "")

        if isinstance(method, AnswerCallbackQuery):
            if method.text:
                self.log.append(
                    {"side": "alert", "chat_id": self.current_chat, "text": method.text}
                )
            return True

        if isinstance(method, GetChatMember):
            user = User(id=method.user_id, is_bot=False, first_name="Video")
            if method.user_id in self.subscribed:
                return ChatMemberMember(status="member", user=user)
            return ChatMemberLeft(status="left", user=user)

        if isinstance(method, GetMe):
            return User(
                id=123456789,
                is_bot=True,
                first_name="Rasch Math Bot",
                username="rashonatilibot",
            )

        if name.startswith(("Set", "Delete", "Close", "Log", "Pin", "Unpin")):
            return True
        return True

    async def close(self) -> None:
        return None

    # ----------------------------------------------------------------
    def _record(self, chat_id, text, markup, *, edited=False, document=None) -> None:
        entry: dict = {
            "side": "bot",
            "chat_id": chat_id,
            "text": text or "",
            "edited": edited,
        }
        if document:
            entry["document"] = document

        inline = getattr(markup, "inline_keyboard", None)
        if inline:
            entry["inline"] = [
                [{"text": b.text, "web_app": bool(b.web_app)} for b in row]
                for row in inline
            ]
        keyboard = getattr(markup, "keyboard", None)
        if keyboard:
            entry["reply"] = [
                [
                    {
                        "text": b.text,
                        "contact": bool(getattr(b, "request_contact", False)),
                        "web_app": bool(getattr(b, "web_app", None)),
                    }
                    for b in row
                ]
                for row in keyboard
            ]
        self.log.append(entry)

    def _make_message(self, bot: Bot, chat_id: int, text: str) -> Message:
        self._message_id += 1
        message = Message(
            message_id=self._message_id,
            date=datetime.now(dt_timezone.utc),
            chat=Chat(id=chat_id, type="private"),
            from_user=User(id=123456789, is_bot=True, first_name="Rasch Math Bot"),
            text=text or None,
        )
        return message.as_(bot)

    # ----------------------------------------------------------------
    def mark(self) -> int:
        return len(self.log)

    def markups_since(self, index: int) -> list[dict]:
        return [item for item in self.log[index:] if item.get("inline")]


# ==========================================================================
#  Foydalanuvchi nomidan harakat qiluvchi yordamchi
# ==========================================================================


class Driver:
    def __init__(self) -> None:
        from bot.handlers import setup_routers
        from bot.middlewares import setup_middlewares

        self.session = RecordingSession()
        self.bot = Bot(
            token=os.environ.get("BOT_TOKEN", "1:VIDEO-PLACEHOLDER"),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=self.session,
        )
        self.dispatcher = Dispatcher()
        setup_middlewares(self.dispatcher)
        setup_routers(self.dispatcher)
        self._update_id = 0

    # ----------------------------------------------------------------
    async def send(self, user_id: int, text: str, *, name: str = "Video") -> int:
        """Foydalanuvchi matnli xabar yuboradi."""
        self.session.current_chat = user_id
        self.session.log.append({"side": "user", "chat_id": user_id, "text": text})
        index = self.session.mark()
        self._update_id += 1
        message = Message(
            message_id=self._update_id,
            date=datetime.now(dt_timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name=name),
            text=text,
        )
        await self.dispatcher.feed_update(
            self.bot, Update(update_id=self._update_id, message=message)
        )
        return index

    async def send_contact(self, user_id: int, phone: str) -> int:
        """Foydalanuvchi telefon raqamini tugma orqali yuboradi."""
        self.session.current_chat = user_id
        self.session.log.append(
            {"side": "user", "chat_id": user_id, "text": phone, "kind": "contact"}
        )
        index = self.session.mark()
        self._update_id += 1
        message = Message(
            message_id=self._update_id,
            date=datetime.now(dt_timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Video"),
            contact=Contact(phone_number=phone, first_name="Video", user_id=user_id),
        )
        await self.dispatcher.feed_update(
            self.bot, Update(update_id=self._update_id, message=message)
        )
        return index

    async def click(self, user_id: int, data: str, *, label: str = "") -> int:
        """Foydalanuvchi inline tugmani bosadi."""
        self.session.current_chat = user_id
        self.session.log.append(
            {
                "side": "user",
                "chat_id": user_id,
                "text": label or data,
                "kind": "tap",
            }
        )
        index = self.session.mark()
        self._update_id += 1
        message = Message(
            message_id=self._update_id,
            date=datetime.now(dt_timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=123456789, is_bot=True, first_name="Rasch Math Bot"),
            text="—",
        ).as_(self.bot)
        callback = CallbackQuery(
            id=str(self._update_id),
            from_user=User(id=user_id, is_bot=False, first_name="Video"),
            chat_instance="video",
            message=message,
            data=data,
        )
        await self.dispatcher.feed_update(
            self.bot, Update(update_id=self._update_id, callback_query=callback)
        )
        return index


# --------------------------------------------------------------------------
#  Callback ma'lumotini topish uchun log'ga qo'shimcha yozuv
# --------------------------------------------------------------------------
#  RecordingSession faqat tugma matnini saqlaydi, lekin bosish uchun
#  `callback_data` kerak. Shu sababli markup obyektlari alohida ro'yxatda
#  ham saqlanadi.


class MarkupKeeper:
    """Yuborilgan inline klaviaturalarni obyekt ko'rinishida saqlaydi."""

    def __init__(self) -> None:
        self.items: list = []

    def add(self, markup) -> None:  # noqa: ANN001
        if getattr(markup, "inline_keyboard", None):
            self.items.append(markup)

    def mark(self) -> int:
        return len(self.items)

    def find(self, index: int, predicate):
        for markup in self.items[index:]:
            for row in markup.inline_keyboard:
                for button in row:
                    if button.callback_data and predicate(button.text):
                        return button.callback_data, button.text
        return None, None


KEEPER = MarkupKeeper()

_original_record = RecordingSession._record


def _record_with_keeper(self, chat_id, text, markup, *, edited=False, document=None):
    KEEPER.add(markup)
    _original_record(self, chat_id, text, markup, edited=edited, document=document)


RecordingSession._record = _record_with_keeper


# ==========================================================================
#  Sahnalar
# ==========================================================================


async def tap_last(drv: Driver, user_id: int, predicate, *, back: int = 1) -> bool:
    """Oxirgi yuborilgan inline klaviaturadan mos tugmani topib bosadi."""
    start = max(KEEPER.mark() - back, 0)
    data, label = KEEPER.find(start, predicate)
    if data is None:
        return False
    await drv.click(user_id, data, label=label)
    return True


async def scene_registration(drv: Driver) -> None:
    """1-sahna: /start, majburiy obuna, ro'yxatdan o'tish."""
    print("[1] Ro'yxatdan o'tish...")

    await drv.send(STUDENT_ID, "/start")

    # Hali kanalga a'zo emas — bot rad javobini beradi
    await tap_last(drv, STUDENT_ID, lambda t: "tekshir" in t.lower())
    # Kanalga a'zo bo'lgach, tekshiruv o'tadi
    drv.session.subscribed.add(STUDENT_ID)
    await tap_last(drv, STUDENT_ID, lambda t: "tekshir" in t.lower())

    await tap_last(drv, STUDENT_ID, lambda t: "boshla" in t.lower())

    # Bitta so'z — bot qabul qilmaydi
    await drv.send(STUDENT_ID, "Sardor")
    # To'liq ism
    await drv.send(STUDENT_ID, "Sardor Aliyev")
    # Telefon
    await drv.send_contact(STUDENT_ID, "+998901112233")


async def scene_teacher_creates(drv: Driver) -> str:
    """2-sahna: o'qituvchi botda test yaratadi."""
    print("[2] Test yaratish...")

    drv.session.subscribed.add(TEACHER_ID)
    await drv.send(TEACHER_ID, "/start", name="Nodira")
    if await tap_last(drv, TEACHER_ID, lambda t: "boshla" in t.lower()):
        await drv.send(TEACHER_ID, "Nodira Qodirova")
        await drv.send_contact(TEACHER_ID, "+998903334455")

    await drv.send(TEACHER_ID, "Test yaratish")
    await tap_last(drv, TEACHER_ID, lambda t: "oddiy" in t.lower())

    await drv.send(TEACHER_ID, "Kvadrat tenglamalar — nazorat ishi")
    await tap_last(drv, TEACHER_ID, lambda t: t.strip().startswith("10"))

    await drv.send(TEACHER_ID, "ABCDABCDAB")
    await tap_last(drv, TEACHER_ID, lambda t: "24 soat" in t.lower())

    # Ko'rinish: ochiq test (kod bilan hamma kira oladi)
    await tap_last(drv, TEACHER_ID, lambda t: "bekor" not in t.lower())

    # Yaratilgan testning kodini bazadan olamiz
    from apps.exams.models import Exam

    exam = (
        Exam.objects.filter(owner__telegram_id=TEACHER_ID)
        .order_by("-id")
        .first()
    )
    code = exam.code if exam else ""
    print(f"    yaratildi: {code}")
    return code


async def scene_student_takes(drv: Driver, code: str) -> None:
    """3-sahna: o'quvchi testni topshiradi."""
    print("[3] Testni topshirish...")

    await drv.send(STUDENT_ID, "Testda qatnashish")
    await drv.send(STUDENT_ID, "T-YOQ000")  # noto'g'ri kod — bot xato beradi
    await drv.send(STUDENT_ID, code)
    await tap_last(drv, STUDENT_ID, lambda t: "botda topshirish" in t.lower())

    from apps.exams.models import Exam

    exam = Exam.objects.filter(code=code).first()
    if exam is None:
        return

    key = "ABCDABCDAB"
    questions = list(exam.questions.order_by("order"))
    for i, question in enumerate(questions):
        # Aksariyat savolga to'g'ri, ba'zisiga xato javob beriladi
        correct = key[i] if i < len(key) else "A"
        answer = correct if i not in (3, 7) else ("A" if correct != "A" else "B")
        await drv.click(
            STUDENT_ID, f"q:pick:{question.order}:{answer}", label=answer
        )

    await tap_last(drv, STUDENT_ID, lambda t: "yakun" in t.lower())
    await tap_last(
        drv, STUDENT_ID, lambda t: "yubor" in t.lower() or "tasdiq" in t.lower()
    )


async def scene_results(drv: Driver) -> None:
    """4-sahna: natijalar va sertifikatlar bo'limi."""
    print("[4] Natijalar...")

    await drv.send(STUDENT_ID, "Natijalarim")
    await tap_last(drv, STUDENT_ID, lambda t: "kvadrat" in t.lower(), back=2)
    await tap_last(drv, STUDENT_ID, lambda t: "javob" in t.lower(), back=2)

    await drv.send(STUDENT_ID, "Sertifikatlar")
    await drv.send(STUDENT_ID, "/ilova")


# ==========================================================================
#  Ishga tushirish
# ==========================================================================


async def main() -> int:
    from asgiref.sync import sync_to_async
    from apps.users.models import BotUser
    from apps.exams.models import Exam

    # Oldingi yozuvdan qolgan ma'lumotlarni tozalaymiz
    @sync_to_async(thread_sensitive=True)
    def cleanup() -> None:
        Exam.objects.filter(owner__telegram_id__in=[TEACHER_ID, STUDENT_ID]).delete()
        BotUser.objects.filter(telegram_id__in=[TEACHER_ID, STUDENT_ID]).delete()

    await cleanup()

    drv = Driver()
    try:
        await scene_registration(drv)
        code = await scene_teacher_creates(drv)
        if code:
            await scene_student_takes(drv, code)
            await scene_results(drv)
    finally:
        await drv.bot.session.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "teacher_id": TEACHER_ID,
        "student_id": STUDENT_ID,
        "log": drv.session.log,
    }
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    bot_messages = sum(1 for item in drv.session.log if item["side"] == "bot")
    user_messages = sum(1 for item in drv.session.log if item["side"] == "user")
    print()
    print(f"Yozib olindi: {user_messages} ta foydalanuvchi xabari, "
          f"{bot_messages} ta bot javobi")
    print(f"Fayl: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
