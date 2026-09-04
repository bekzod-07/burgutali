#!/usr/bin/env python
"""
Botning to'liq foydalanuvchi oqimini simulyatsiya qilish.

Skript Telegram serveriga umuman murojaat qilmaydi: `Bot.session` soxta
sessiya bilan almashtiriladi va barcha so'rovlar xotirada qayta ishlanadi.
Shu yo'l bilan quyidagilar tekshiriladi:

  * middleware zanjiri (throttling -> foydalanuvchi -> majburiy obuna);
  * /start, majburiy obuna va ro'yxatdan o'tish dialogi;
  * test yaratish sehrgari (tur -> nom -> savollar -> kalit -> sozlamalar);
  * testga kirish, savollarga javob berish va yakuniy yuborish;
  * natijalar, reyting va javoblarni ko'rish;
  * pullik test: ID kod, sertifikat va admin paneli.

Ishga tushirish:

    python simulate.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# --------------------------------------------------------------------------
#  Alohida simulyatsiya bazasi
# --------------------------------------------------------------------------
SIM_DIR = BASE_DIR / "data" / "simulate"
SIM_DB = SIM_DIR / "simulate.sqlite3"
SIM_MEDIA = SIM_DIR / "media"

SIM_DIR.mkdir(parents=True, exist_ok=True)
for stale in SIM_DIR.glob("simulate.sqlite3*"):
    stale.unlink(missing_ok=True)
if SIM_MEDIA.exists():
    shutil.rmtree(SIM_MEDIA, ignore_errors=True)
SIM_MEDIA.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = "sqlite:///" + SIM_DB.as_posix()
os.environ["DJANGO_ENV"] = "dev"
os.environ["BOT_TOKEN"] = "123456789:SIMULATION-TOKEN-PLACEHOLDER-000"
os.environ["BOT_USERNAME"] = "rasch_sim_bot"
os.environ["ADMIN_IDS"] = "500001"
os.environ["REQUIRED_CHANNEL"] = "@Burgutali"
os.environ["SUBSCRIPTION_REQUIRED"] = "1"
os.environ["BOT_THROTTLE_RATE"] = "0"
os.environ["PUBLIC_BASE_URL"] = "https://example.test"

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402

settings.MEDIA_ROOT = SIM_MEDIA

from django.core.management import call_command  # noqa: E402

call_command("migrate", verbosity=0, interactive=False)

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
    SendPhoto,
)
from aiogram.types import (  # noqa: E402
    CallbackQuery,
    Chat,
    ChatMemberMember,
    Contact,
    Message,
    Update,
    User,
)


# ==========================================================================
#  Soxta sessiya
# ==========================================================================


class FakeSession:
    """Telegram API o'rniga ishlaydigan xotiradagi sessiya."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.documents: list[dict] = []
        self.photos: list[dict] = []
        self.alerts: list[str] = []
        self.subscribed: set[int] = set()
        self._message_id = 1000

    # ----------------------------------------------------------------
    async def __call__(self, bot: Bot, method, timeout=None):  # noqa: ANN001
        name = type(method).__name__

        if isinstance(method, SendMessage):
            self._message_id += 1
            self.sent.append(
                {
                    "chat_id": method.chat_id,
                    "text": method.text or "",
                    "markup": method.reply_markup,
                }
            )
            return self._make_message(bot, method.chat_id, method.text or "")

        if isinstance(method, SendDocument):
            self._message_id += 1
            filename = getattr(method.document, "filename", "fayl")
            size = len(getattr(method.document, "data", b"") or b"")
            self.documents.append(
                {"chat_id": method.chat_id, "filename": filename,
                 "size": size, "caption": method.caption or ""}
            )
            self.sent.append({"chat_id": method.chat_id, "text": method.caption or "",
                              "markup": method.reply_markup})
            message = self._make_message(bot, method.chat_id, method.caption or "")
            return message

        if isinstance(method, SendPhoto):
            self._message_id += 1
            filename = getattr(method.photo, "filename", "rasm")
            size = len(getattr(method.photo, "data", b"") or b"")
            self.photos.append(
                {"chat_id": method.chat_id, "filename": filename,
                 "size": size, "caption": method.caption or ""}
            )
            self.sent.append({"chat_id": method.chat_id, "text": method.caption or "",
                              "markup": method.reply_markup})
            return self._make_message(bot, method.chat_id, method.caption or "")

        if isinstance(method, (EditMessageText,)):
            self.sent.append(
                {"chat_id": method.chat_id, "text": method.text or "",
                 "markup": method.reply_markup, "edited": True}
            )
            return self._make_message(bot, method.chat_id or 0, method.text or "")

        if isinstance(method, EditMessageReplyMarkup):
            return self._make_message(bot, method.chat_id or 0, "")

        if isinstance(method, AnswerCallbackQuery):
            if method.text:
                self.alerts.append(method.text)
            return True

        if isinstance(method, GetChatMember):
            user = User(id=method.user_id, is_bot=False, first_name="Sim")
            status = "member" if method.user_id in self.subscribed else "left"
            if status == "member":
                return ChatMemberMember(status="member", user=user)
            from aiogram.types import ChatMemberLeft

            return ChatMemberLeft(status="left", user=user)

        if isinstance(method, GetMe):
            return User(id=123456789, is_bot=True, first_name="Rasch Bot",
                        username="rasch_sim_bot")

        # Qolgan barcha metodlar (SetMyCommands, DeleteWebhook, ...) -> True
        if name.startswith(("Set", "Delete", "Close", "Log", "Pin", "Unpin")):
            return True
        return True

    async def close(self) -> None:
        return None

    # ----------------------------------------------------------------
    def _make_message(self, bot: Bot, chat_id: int, text: str) -> Message:
        self._message_id += 1
        message = Message(
            message_id=self._message_id,
            date=datetime.now(dt_timezone.utc),
            chat=Chat(id=chat_id, type="private"),
            from_user=User(id=123456789, is_bot=True, first_name="Rasch Bot"),
            text=text or None,
        )
        return message.as_(bot)

    # ----------------------------------------------------------------
    def last_text(self) -> str:
        return self.sent[-1]["text"] if self.sent else ""

    def texts_since(self, index: int) -> list[str]:
        return [item["text"] for item in self.sent[index:]]

    def markup_since(self, index: int):
        for item in reversed(self.sent[index:]):
            if item.get("markup") is not None:
                return item["markup"]
        return None

    def all_markups_since(self, index: int) -> list:
        return [item["markup"] for item in self.sent[index:] if item.get("markup")]


# ==========================================================================
#  Simulyatsiya muhiti
# ==========================================================================


class Simulator:
    """Foydalanuvchi nomidan xabar va tugmalarni yuboradi."""

    def __init__(self) -> None:
        from bot.handlers import setup_routers
        from bot.middlewares import setup_middlewares

        self.session = FakeSession()
        self.bot = Bot(
            token=os.environ["BOT_TOKEN"],
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=self.session,
        )
        self.dispatcher = Dispatcher()
        setup_middlewares(self.dispatcher)
        setup_routers(self.dispatcher)
        self._update_id = 0

    # ----------------------------------------------------------------
    def mark(self) -> int:
        """Joriy xabarlar sonini qaytaradi (keyinchalik solishtirish uchun)."""
        return len(self.session.sent)

    async def send(self, user_id: int, text: str, *, name: str = "Sim Foydalanuvchi") -> int:
        """Matnli xabar yuboradi."""
        index = self.mark()
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
        """Kontakt yuboradi."""
        index = self.mark()
        self._update_id += 1
        message = Message(
            message_id=self._update_id,
            date=datetime.now(dt_timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Sim"),
            contact=Contact(phone_number=phone, first_name="Sim", user_id=user_id),
        )
        await self.dispatcher.feed_update(
            self.bot, Update(update_id=self._update_id, message=message)
        )
        return index

    async def click(self, user_id: int, data: str) -> int:
        """Inline tugmani bosadi."""
        index = self.mark()
        self._update_id += 1
        message = Message(
            message_id=self._update_id,
            date=datetime.now(dt_timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=123456789, is_bot=True, first_name="Rasch Bot"),
            text="—",
        ).as_(self.bot)
        callback = CallbackQuery(
            id=str(self._update_id),
            from_user=User(id=user_id, is_bot=False, first_name="Sim"),
            chat_instance="sim",
            message=message,
            data=data,
        )
        await self.dispatcher.feed_update(
            self.bot, Update(update_id=self._update_id, callback_query=callback)
        )
        return index

    # ----------------------------------------------------------------
    def find_callback(self, index: int, predicate) -> str | None:
        """Yuborilgan klaviaturalardan mos callback ma'lumotini topadi."""
        for markup in self.session.all_markups_since(index):
            rows = getattr(markup, "inline_keyboard", None)
            if not rows:
                continue
            for row in rows:
                for button in row:
                    if button.callback_data and predicate(button):
                        return button.callback_data
        return None

    def joined_texts(self, index: int) -> str:
        return "\n".join(self.session.texts_since(index))


# ==========================================================================
#  Tekshiruv hisoblagichi
# ==========================================================================


class Runner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []
        self.section = ""

    def head(self, title: str) -> None:
        self.section = title
        print(f"\n\033[1m{title}\033[0m")
        print("─" * max(30, len(title)))

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        if condition:
            self.passed += 1
            print(f"  \033[92m✓\033[0m {name}")
        else:
            self.failed += 1
            self.errors.append(f"[{self.section}] {name}" + (f" — {detail}" if detail else ""))
            print(f"  \033[91m✗\033[0m {name}" + (f"  ({detail})" if detail else ""))
        return condition

    def equal(self, name: str, actual, expected) -> bool:
        return self.check(name, actual == expected, f"kutilgan {expected!r}, olindi {actual!r}")

    def summary(self) -> int:
        total = self.passed + self.failed
        print("\n" + "═" * 60)
        if self.failed == 0:
            print(f"\033[92m✅ SIMULYATSIYA MUVAFFAQIYATLI: {self.passed}/{total}\033[0m")
        else:
            print(f"\033[91m❌ XATOLAR: {self.failed} / {total}\033[0m\n")
            for error in self.errors:
                print(f"   • {error}")
        print("═" * 60)
        return 0 if self.failed == 0 else 1


R = Runner()

USER_ID = 700001
ADMIN_ID = 500001
SECOND_ID = 700002


async def q(func):
    """
    ORM so'rovini asinxron kontekstda xavfsiz bajaradi.

    Foydalanish: `user = await q(lambda: BotUser.objects.get(pk=1))`
    """
    from asgiref.sync import sync_to_async

    return await sync_to_async(func, thread_sensitive=True)()


# ==========================================================================
#  1. /start, majburiy obuna va ro'yxatdan o'tish
# ==========================================================================


async def scenario_registration(sim: Simulator) -> None:
    from apps.users.models import BotUser

    R.head("1. /start, majburiy obuna va ro'yxatdan o'tish")

    # --- Obunasiz /start ---
    index = await sim.send(USER_ID, "/start")
    text = sim.joined_texts(index)
    R.check("Obunasiz foydalanuvchiga a'zolik so'raladi", "a’zo bo‘ling" in text)
    R.check("Kanal nomi ko'rsatiladi", "@Burgutali" in text)

    check_cb = sim.find_callback(index, lambda b: b.callback_data.startswith("sub:"))
    R.check("«A'zolikni tekshirish» tugmasi bor", check_cb is not None)

    # --- Hali obuna bo'lmagan holda tekshirish ---
    index = await sim.click(USER_ID, check_cb)
    R.check("A'zo emasligi aniqlanadi", "hali kanalga a’zo bo‘lmagansiz" in sim.joined_texts(index))

    # --- Kanalga a'zo bo'ladi ---
    sim.session.subscribed.add(USER_ID)
    index = await sim.click(USER_ID, check_cb)
    text = sim.joined_texts(index)
    R.check("A'zolik tasdiqlandi", "A’zolik tasdiqlandi" in text)
    R.check("Xush kelibsiz xabari keldi", "xush kelibsiz" in text.lower())

    start_cb = sim.find_callback(index, lambda b: b.callback_data == "menu:start")
    R.check("«Boshlash» tugmasi bor", start_cb is not None)

    # --- Ro'yxatdan o'tish ---
    index = await sim.click(USER_ID, start_cb)
    R.check("Ism-familiya so'raldi", "Ism va familiyangizni kiriting" in sim.joined_texts(index))

    index = await sim.send(USER_ID, "Ali")
    R.check("Bitta so'z rad etiladi", "to‘liq kiriting" in sim.joined_texts(index))

    index = await sim.send(USER_ID, "burgutali eshquvvatov")
    text = sim.joined_texts(index)
    R.check("Ism saqlandi va tozalandi", "Burgutali Eshquvvatov" in text)
    R.check("Telefon so'raldi", "telefon raqamingizni yuboring" in text.lower())

    index = await sim.send_contact(USER_ID, "+998901234567")
    text = sim.joined_texts(index)
    R.check("Ro'yxatdan o'tish yakunlandi", "Ro‘yxatdan o‘tdingiz" in text)
    R.check("Telefon ko'rsatiladi", "+998901234567" in text)

    user = await q(lambda: BotUser.objects.get(telegram_id=USER_ID))
    R.check("Bazada ro'yxatdan o'tgan", user.is_registered)
    R.equal("Ism bazada", user.full_name, "Burgutali Eshquvvatov")
    R.equal("Telefon bazada", user.phone, "+998901234567")

    # --- Asosiy menyu (inline) ---
    index = await sim.send(USER_ID, "/menu")
    markup = sim.session.markup_since(index)
    labels = [
        button.text
        for row in (
            getattr(markup, "keyboard", None)
            or getattr(markup, "inline_keyboard", None)
            or []
        )
        for button in row
    ]
    R.check("Asosiy menyuda «Testda qatnashish»", any("qatnashish" in x for x in labels))
    R.check("Asosiy menyuda «Test yaratish»", any("yaratish" in x for x in labels))
    R.check("Oddiy foydalanuvchida admin tugmasi yo'q", not any("Admin" in x for x in labels))


# ==========================================================================
#  2. Test yaratish sehrgari
# ==========================================================================


async def scenario_create_exam(sim: Simulator) -> str:
    from apps.exams.models import Exam

    R.head("2. Test yaratish sehrgari (oddiy test)")

    index = await sim.send(USER_ID, "Test yaratish")
    text = sim.joined_texts(index)
    R.check("Test turlari ko'rsatildi", "Oddiy test" in text)

    paid_cb = sim.find_callback(index, lambda b: "rasch_paid" in (b.callback_data or ""))
    R.check("Oddiy foydalanuvchida pullik test yo'q", paid_cb is None)

    simple_cb = sim.find_callback(index, lambda b: b.callback_data.endswith("simple"))
    index = await sim.click(USER_ID, simple_cb)
    R.check("Test nomi so'raldi", "Test nomini kiriting" in sim.joined_texts(index))

    index = await sim.send(USER_ID, "ab")
    R.check("Qisqa nom rad etiladi", "kamida 3 ta belgi" in sim.joined_texts(index))

    index = await sim.send(USER_ID, "Algebra sinovi")
    R.check("Savollar soni so'raldi", "nechta savoldan" in sim.joined_texts(index))

    count_cb = sim.find_callback(index, lambda b: b.callback_data.endswith(":10"))
    index = await sim.click(USER_ID, count_cb)
    R.check("Javob kaliti so'raldi", "Javob kalitini kiriting" in sim.joined_texts(index))

    index = await sim.send(USER_ID, "ABCD")
    R.check("Kalit uzunligi tekshiriladi", "kutilgan" in sim.joined_texts(index).lower())

    index = await sim.send(USER_ID, "ABCDABCDAB")
    text = sim.joined_texts(index)
    R.check("Kalit saqlandi", "Javob kaliti saqlandi" in text)
    R.check("Tugash vaqti so'raldi", "Test qachon tugasin" in text)

    duration_cb = sim.find_callback(index, lambda b: b.callback_data.endswith("duration:0"))
    index = await sim.click(USER_ID, duration_cb)
    R.check("Natija ko'rinishi so'raldi", "qatnashchilarga ko‘rinsinmi" in sim.joined_texts(index))

    yes_cb = sim.find_callback(index, lambda b: b.callback_data.endswith("visibility:1"))
    index = await sim.click(USER_ID, yes_cb)
    text = sim.joined_texts(index)
    R.check("Test yaratildi", "Test yaratildi" in text)

    exam = await q(lambda: Exam.objects.filter(title="Algebra sinovi").first())
    R.check("Test bazada mavjud", exam is not None)
    # Kod ishtirokchi uchun qulay bo'lishi kerak — oddiy 2–3 xonali son.
    R.check(
        "Test kodi oddiy son ko'rinishida berildi",
        exam is not None and exam.code.isdigit() and len(exam.code) <= 3
        and exam.code in text,
    )
    R.equal("10 ta savol", exam.question_count, 10)
    R.equal("Holat faol", exam.status, Exam.Status.ACTIVE)
    keys = await q(lambda: list(exam.questions.values_list("correct_key", flat=True)))
    R.check("Barcha kalitlar kiritildi", all(keys) and len(keys) == 10)
    R.check("Natijalar ko'rinadi", exam.show_results_to_participants)

    return exam.code


# ==========================================================================
#  3. Testda qatnashish
# ==========================================================================


async def scenario_take_exam(sim: Simulator, exam_code: str) -> None:
    from apps.attempts.models import Attempt
    from apps.exams.models import Exam
    from apps.users.models import BotUser

    R.head("3. Testda qatnashish va javob yuborish")

    # --- Ikkinchi foydalanuvchi ro'yxatdan o'tadi ---
    sim.session.subscribed.add(SECOND_ID)
    await sim.send(SECOND_ID, "/start")
    index = await sim.send(SECOND_ID, "/start")
    start_cb = sim.find_callback(index, lambda b: b.callback_data == "menu:start")
    await sim.click(SECOND_ID, start_cb)
    await sim.send(SECOND_ID, "Sardor Aliyev")
    await sim.send_contact(SECOND_ID, "+998907654321")

    user = await q(lambda: BotUser.objects.get(telegram_id=SECOND_ID))
    R.check("Ikkinchi foydalanuvchi ro'yxatdan o'tdi", user.is_registered)

    # --- Test kodini kiritish ---
    index = await sim.send(SECOND_ID, "Testda qatnashish")
    R.check("Test kodi so'raldi", "Test kodini kiriting" in sim.joined_texts(index))

    index = await sim.send(SECOND_ID, "T-YOQ123")
    R.check("Noto'g'ri kod rad etiladi", "test topilmadi" in sim.joined_texts(index).lower())

    index = await sim.send(SECOND_ID, exam_code.lower())
    text = sim.joined_texts(index)
    R.check("Test topildi", "Algebra sinovi" in text)
    R.check("Savollar soni ko'rsatildi", "10" in text)

    take_cb = sim.find_callback(index, lambda b: b.callback_data.startswith("exam:take"))
    R.check("«Testni boshlash» tugmasi bor", take_cb is not None)

    index = await sim.click(SECOND_ID, take_cb)
    text = sim.joined_texts(index)
    R.check("Test boshlandi", "Test boshlandi" in text)
    R.check("Birinchi savol yuborildi", "1-savol" in text)

    attempt = await q(lambda: Attempt.objects.filter(user=user).first())
    R.check("Urinish yaratildi", attempt is not None)
    R.equal("Urinish qoralama holatida", attempt.status, Attempt.Status.DRAFT)

    # --- Savollarga javob berish ---
    exam = await q(lambda: Exam.objects.get(code=exam_code))
    questions = await q(lambda: list(exam.questions.order_by("order")))

    for position, question in enumerate(questions):
        if position < 7:
            value = question.correct_key
        else:
            value = "A" if question.correct_key != "A" else "B"
        index = await sim.click(SECOND_ID, f"q:pick:{question.order}:{value}")

    text = sim.joined_texts(index)
    R.check("Oxirgi javobdan keyin ko'rib chiqish ochildi", "Javoblaringiz" in text)
    R.check("10/10 javob berilgan", "10/10" in text)

    answers_count = await q(lambda: attempt.answers.count())
    R.equal("10 ta javob saqlandi", answers_count, 10)

    # --- Yakunlash ---
    finish_cb = sim.find_callback(index, lambda b: b.callback_data.startswith("q:finish"))
    index = await sim.click(SECOND_ID, finish_cb)
    R.check("Tasdiqlash so'raldi", "yakuniy yuborishni tasdiqlaysizmi" in sim.joined_texts(index).lower())

    submit_cb = sim.find_callback(index, lambda b: b.callback_data.startswith("q:submit"))
    index = await sim.click(SECOND_ID, submit_cb)
    text = sim.joined_texts(index)
    R.check("«Javoblaringiz qabul qilindi» xabari", "Javoblaringiz qabul qilindi" in text)
    R.check("Natija ko'rsatildi", "To‘g‘ri javoblar" in text)
    R.check("7 ta to'g'ri javob", "7/10" in text or "7" in text)

    saved = await q(lambda: Attempt.objects.get(pk=attempt.pk))
    R.equal("Urinish yuborildi", saved.status, Attempt.Status.SUBMITTED)
    R.equal("7 ball", saved.raw_score, 7.0)
    R.equal("3 ta xato", saved.wrong_count, 3)

    # --- Takroriy urinish ---
    index = await sim.send(SECOND_ID, "Testda qatnashish")
    index = await sim.send(SECOND_ID, exam_code)
    R.check("Takroriy qatnashish taqiqlanadi",
            "allaqachon qatnashgansiz" in sim.joined_texts(index))

    # --- Natijalar bo'limi ---
    index = await sim.send(SECOND_ID, "Natijalarim")
    R.check("Natijalar ro'yxati ko'rsatildi", "natijalaringiz" in sim.joined_texts(index).lower())

    open_cb = sim.find_callback(index, lambda b: b.callback_data.startswith("att:open"))
    index = await sim.click(SECOND_ID, open_cb)
    text = sim.joined_texts(index)
    R.check("Natija tafsiloti ochildi", "Algebra sinovi" in text)
    R.check("Foiz ko'rsatildi", "70" in text)

    answers_cb = sim.find_callback(index, lambda b: b.callback_data.startswith("att:answers"))
    index = await sim.click(SECOND_ID, answers_cb)
    text = sim.joined_texts(index)
    R.check("Javoblar ro'yxati ko'rsatildi", "✓" in text and "✗" in text)


# ==========================================================================
#  4. Pullik test: admin oqimi
# ==========================================================================


async def scenario_admin(sim: Simulator) -> None:
    from apps.accesscodes.models import AccessCode
    from apps.attempts.models import Attempt
    from apps.certificates.models import Certificate
    from apps.exams.models import Exam
    from apps.users.models import BotUser

    R.head("4. Admin oqimi: pullik test, ID kodlar va sertifikat")

    sim.session.subscribed.add(ADMIN_ID)
    index = await sim.send(ADMIN_ID, "/start")
    start_cb = sim.find_callback(index, lambda b: b.callback_data == "menu:start")
    if start_cb:
        await sim.click(ADMIN_ID, start_cb)
        await sim.send(ADMIN_ID, "Bosh Administrator")
        await sim.send_contact(ADMIN_ID, "+998900000001")

    admin_user = await q(lambda: BotUser.objects.get(telegram_id=ADMIN_ID))
    R.check("Admin huquqi berildi", admin_user.is_admin)

    index = await sim.send(ADMIN_ID, "/menu")
    markup = sim.session.markup_since(index)
    labels = [
        button.text
        for row in (
            getattr(markup, "keyboard", None)
            or getattr(markup, "inline_keyboard", None)
            or []
        )
        for button in row
    ]
    R.check("Adminda «Admin panel» tugmasi bor", any("Admin" in x for x in labels))

    # --- Admin panel ---
    index = await sim.send(ADMIN_ID, "Admin panel")
    R.check("Admin paneli ochildi", "Administrator paneli" in sim.joined_texts(index))

    panel_button = None
    for markup in sim.session.all_markups_since(index):
        for row in getattr(markup, "inline_keyboard", []) or []:
            for button in row:
                if button.web_app is not None and "/panel/" in button.web_app.url:
                    panel_button = button
    R.check("Web panel tugmasi Web App sifatida ochiladi", panel_button is not None)
    if panel_button:
        R.check("Panel Telegram kirish manzili", panel_button.web_app.url.endswith("/panel/tg/"))

    stats_cb = sim.find_callback(index, lambda b: b.callback_data == "menu:admin_stats")
    index = await sim.click(ADMIN_ID, stats_cb)
    text = sim.joined_texts(index)
    R.check("Statistika ko'rsatildi", "Umumiy statistika" in text)
    R.check("Foydalanuvchilar soni bor", "Foydalanuvchilar" in text)

    # --- Pullik test yaratish ---
    index = await sim.send(ADMIN_ID, "Test yaratish")
    paid_cb = sim.find_callback(index, lambda b: (b.callback_data or "").endswith("rasch_paid"))
    R.check("Adminda pullik test varianti bor", paid_cb is not None)

    index = await sim.click(ADMIN_ID, paid_cb)
    R.check("Nom so'raldi", "Test nomini kiriting" in sim.joined_texts(index))

    index = await sim.send(ADMIN_ID, "MILLIY SERTIFIKAT MOCK №9")
    R.check("Tuzilma so'raldi", "tuzilmasini tanlang" in sim.joined_texts(index))

    custom_cb = sim.find_callback(index, lambda b: (b.callback_data or "").endswith("structure:custom"))
    index = await sim.click(ADMIN_ID, custom_cb)
    count_cb = sim.find_callback(index, lambda b: (b.callback_data or "").endswith(":20"))
    index = await sim.click(ADMIN_ID, count_cb)
    R.check("Kalit so'raldi", "Javob kalitini kiriting" in sim.joined_texts(index))

    index = await sim.send(ADMIN_ID, "ABCD" * 5)
    duration_cb = sim.find_callback(index, lambda b: (b.callback_data or "").endswith("duration:0"))
    index = await sim.click(ADMIN_ID, duration_cb)
    yes_cb = sim.find_callback(index, lambda b: (b.callback_data or "").endswith("visibility:1"))
    index = await sim.click(ADMIN_ID, yes_cb)
    R.check("Sertifikat so'raldi", "Sertifikat berilsinmi" in sim.joined_texts(index))

    cert_yes = sim.find_callback(index, lambda b: (b.callback_data or "").endswith("certificate:1"))
    index = await sim.click(ADMIN_ID, cert_yes)
    text = sim.joined_texts(index)
    R.check("Pullik test yaratildi", "Pullik test yaratildi" in text)
    R.check("ID kod miqdori so'raldi", "Nechta ID kod" in text)

    exam = await q(lambda: Exam.objects.filter(title="MILLIY SERTIFIKAT MOCK №9").first())
    R.check("Pullik test bazada", exam is not None)
    R.check("Sertifikat yoqilgan", exam.certificate_enabled)
    R.equal("Holat qoralama", exam.status, Exam.Status.DRAFT)

    # --- ID kodlar ---
    qty_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("code:quantity"))
    R.check("ID kod miqdor tugmalari bor", qty_cb is not None)

    index = await sim.click(ADMIN_ID, f"code:quantity:{exam.id}:500")
    text = sim.joined_texts(index)
    R.check("ID kodlar yaratildi", "500 ta ID kod yaratildi" in text)
    R.check("Excel fayl yuborildi", len(sim.session.documents) > 0)
    R.check("Excel fayl nomi to'g'ri",
            sim.session.documents[-1]["filename"].endswith(".xlsx"))
    R.check("Excel fayl bo'sh emas", sim.session.documents[-1]["size"] > 5000)
    R.check("Namuna kodlar ko'rsatildi", "Namuna" in text)

    codes_count = await q(lambda: AccessCode.objects.filter(exam=exam).count())
    R.equal("Bazada 500 ta kod", codes_count, 500)
    await q(exam.refresh_from_db)
    R.equal("Test avtomatik faollashdi", exam.status, Exam.Status.ACTIVE)

    # --- Ishtirokchi pullik testda ---
    code = await q(lambda: AccessCode.objects.filter(exam=exam).first())

    index = await sim.send(USER_ID, "Testda qatnashish")
    index = await sim.send(USER_ID, exam.code)
    text = sim.joined_texts(index)
    R.check("Pullik testda ID kod eslatildi", "ID kod talab qilinadi" in text)

    take_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("exam:take"))
    index = await sim.click(USER_ID, take_cb)
    R.check("ID kod so'raldi", "ID kodingizni kiriting" in sim.joined_texts(index))

    index = await sim.send(USER_ID, "XXXX-YYYY")
    R.check("Noto'g'ri format rad etiladi", "formati noto‘g‘ri" in sim.joined_texts(index))

    index = await sim.send(USER_ID, "Z9Z9-0000")
    R.check("Mavjud bo'lmagan kod rad etiladi", "topilmadi" in sim.joined_texts(index))

    index = await sim.send(USER_ID, code.code)
    text = sim.joined_texts(index)
    R.check("ID tasdiqlandi", "ID tasdiqlandi" in text)
    R.check("Test boshlandi", "Test boshlandi" in text)

    await q(code.refresh_from_db)
    R.equal("Kod faollashtirilgan holatda", code.status, AccessCode.Status.ACTIVATED)

    # --- Javob berish ---
    questions = await q(lambda: list(exam.questions.order_by("order")))
    for position, question in enumerate(questions):
        value = question.correct_key if position < 17 else (
            "A" if question.correct_key != "A" else "B"
        )
        index = await sim.click(USER_ID, f"q:pick:{question.order}:{value}")

    finish_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("q:finish"))
    index = await sim.click(USER_ID, finish_cb)
    submit_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("q:submit"))
    index = await sim.click(USER_ID, submit_cb)
    text = sim.joined_texts(index)
    R.check("Javoblar qabul qilindi", "Javoblaringiz qabul qilindi" in text)
    R.check("RASH natijasi keyinroq deyildi", "e’lon qilgandan" in text)

    await q(code.refresh_from_db)
    R.equal("Javobdan keyin kod ishlatilgan", code.status, AccessCode.Status.USED)
    R.check("Kod urinishga bog'landi", code.attempt_id is not None)

    index = await sim.send(USER_ID, "Testda qatnashish")
    index = await sim.send(USER_ID, exam.code)
    R.check("Qayta qatnashish taqiqlanadi",
            "allaqachon qatnashgansiz" in sim.joined_texts(index))

    # --- Admin: natijalarni hisoblash va e'lon qilish ---
    index = await sim.send(ADMIN_ID, "Testlarim")
    R.check("Testlar ro'yxati ochildi", "testlaringiz" in sim.joined_texts(index).lower())

    index = await sim.click(ADMIN_ID, f"exam:manage:{exam.id}")
    text = sim.joined_texts(index)
    R.check("Boshqaruv kartochkasi ochildi", "MILLIY SERTIFIKAT MOCK №9" in text)
    R.check("ID kodlar ma'lumoti bor", "ID kodlar" in text)

    # Yagona yakunlovchi amal: yopadi, hisoblaydi va e'lon qiladi.
    index = await sim.click(ADMIN_ID, f"exam:finish:{exam.id}")
    text = sim.joined_texts(index)
    R.check("Test tugatildi", "Test tugatildi" in text)
    R.check("Natijalar e'lon qilindi", "e’lon qilindi" in text)
    R.check("Sertifikatlar yaratildi", "Sertifikatlar" in text)

    attempt = await q(lambda: Attempt.objects.filter(exam=exam, status="submitted").first())
    R.check("Ball hisoblandi", attempt.ball is not None)
    R.check("Daraja belgilandi", bool(attempt.grade))

    await asyncio.sleep(0.4)  # fon xabarnomasi yuborilishini kutamiz

    await q(exam.refresh_from_db)
    R.equal("Holat e'lon qilingan", exam.status, Exam.Status.PUBLISHED)
    has_certificate = await q(lambda: Certificate.objects.filter(exam=exam).exists())
    R.check("Sertifikat bazada yaratildi", has_certificate)

    # RASH testida qatnashchi umumiy natijalarni ham PDF ko'rinishida oladi.
    overall = [
        item
        for item in sim.session.documents
        if item["filename"].startswith("umumiy-natijalar")
    ]
    R.check("Umumiy natijalar PDF yuborildi", bool(overall))
    if overall:
        R.check("Umumiy natijalar qatnashchiga yetdi",
                any(item["chat_id"] == USER_ID for item in overall))
        R.check("Umumiy natijalar hajmi ma'noli", overall[-1]["size"] > 1000)

    # --- Ishtirokchi sertifikatni oladi ---
    index = await sim.send(USER_ID, "Sertifikatlar")
    text = sim.joined_texts(index)
    R.check("Sertifikatlar ro'yxati ko'rsatildi", "sertifikatlaringiz" in text.lower())
    R.check("Sertifikat raqami ko'rsatildi", "RM-" in text)

    cert_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("att:certificate"))
    R.check("Sertifikat yuklab olish tugmasi bor", cert_cb is not None)

    documents_before = len(sim.session.documents)
    index = await sim.click(USER_ID, cert_cb)
    R.check("Sertifikat PDF yuborildi", len(sim.session.documents) > documents_before)
    if len(sim.session.documents) > documents_before:
        pdf = sim.session.documents[-1]
        R.check("PDF fayl nomi to'g'ri", pdf["filename"].endswith(".pdf"))
        R.check("PDF hajmi ma'noli", pdf["size"] > 2000)
        R.check("Izohda ball bor", "Ball" in pdf["caption"])

    # --- Eksport ---
    documents_before = len(sim.session.documents)
    index = await sim.click(ADMIN_ID, f"exam:xlsx:{exam.id}")
    R.check("Natijalar Excel yuborildi", len(sim.session.documents) > documents_before)

    documents_before = len(sim.session.documents)
    index = await sim.click(ADMIN_ID, f"exam:pdf:{exam.id}")
    R.check("Natijalar PDF yuborildi", len(sim.session.documents) > documents_before)

    index = await sim.click(ADMIN_ID, f"exam:rating:{exam.id}")
    R.check("Reyting ko'rsatildi", "reyting" in sim.joined_texts(index).lower())

    # --- Savollar qiyinchiligi diagrammasi (faqat asosiy adminga) ---
    # Diagramma keng bo'lgani uchun rasm emas, **hujjat** sifatida ketadi:
    # Telegram uni siqib yuborsa ustun ichidagi sonlar o'qilmay qoladi.
    docs_before = len(sim.session.documents)
    index = await sim.click(ADMIN_ID, f"exam:charts:{exam.id}")
    new_charts = [
        item for item in sim.session.documents[docs_before:]
        if item["filename"].endswith(".png")
    ]
    R.check("Qiyinchilik diagrammasi yuborildi", bool(new_charts))
    if new_charts:
        R.check("Diagramma PNG hujjat sifatida ketdi",
                new_charts[0]["filename"].endswith(".png"))
        R.check("Diagramma hajmi ma'noli", new_charts[0]["size"] > 3000)
        R.check("Diagramma izohi tushunarli",
                "qiyinchilik" in new_charts[0]["caption"].lower())
        R.check("Diagramma faqat adminga ketdi",
                all(item["chat_id"] == ADMIN_ID for item in new_charts))

    # --- Oddiy foydalanuvchi diagrammani ololmaydi ---
    docs_before = len(sim.session.documents)
    index = await sim.click(SECOND_ID, f"exam:charts:{exam.id}")
    new_docs = [
        item for item in sim.session.documents[docs_before:]
        if item["filename"].endswith(".png")
    ]
    R.check("Oddiy foydalanuvchiga diagramma berilmadi", not new_docs)


# ==========================================================================
#  5. Test boshqaruvi: nusxalash va o'chirish
# ==========================================================================


async def scenario_manage(sim: Simulator) -> None:
    from apps.exams.models import Exam

    R.head("5. Testni tugatish va o'chirish (bot orqali)")

    # --- Vaqtinchalik test yaratamiz ---
    index = await sim.send(SECOND_ID, "Test yaratish")
    simple_cb = sim.find_callback(index, lambda b: (b.callback_data or "").endswith("simple"))
    await sim.click(SECOND_ID, simple_cb)
    await sim.send(SECOND_ID, "Ochiriladigan test")
    await sim.click(SECOND_ID, "crt:count:10")
    await sim.send(SECOND_ID, "ABCDABCDAB")
    await sim.click(SECOND_ID, "crt:duration:0")
    index = await sim.click(SECOND_ID, "crt:visibility:1")
    R.check("Vaqtinchalik test yaratildi", "Test yaratildi" in sim.joined_texts(index))

    exam = await q(lambda: Exam.objects.filter(title="Ochiriladigan test").first())
    R.check("Test bazada mavjud", exam is not None)

    # --- Boshqaruv kartochkasi ---
    index = await sim.click(SECOND_ID, f"exam:manage:{exam.id}")
    text = sim.joined_texts(index)
    R.check("Boshqaruv kartochkasi ochildi", "Ochiriladigan test" in text)

    finish_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("exam:finish"))
    copy_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("exam:copy"))
    delete_cb = sim.find_callback(index, lambda b: (b.callback_data or "").startswith("exam:delete:"))
    R.check("«Testni tugatish» tugmasi bor", finish_cb is not None)
    R.check("«Nusxa yaratish» tugmasi olib tashlandi", copy_cb is None)
    R.check("«O'chirish» tugmasi bor", delete_cb is not None)

    # --- Testni tugatish ---
    index = await sim.click(SECOND_ID, finish_cb)
    R.check("Test tugatildi", "tugatildi" in sim.joined_texts(index).lower())

    await q(exam.refresh_from_db)
    R.equal("Tugatilgan test e'lon qilingan", exam.status, Exam.Status.PUBLISHED)

    # --- Testni o'chirish ---
    copy = exam
    index = await sim.click(SECOND_ID, f"exam:delete:{copy.id}")
    text = sim.joined_texts(index).lower()
    R.check("O'chirish tasdiqlash so'raldi", "butunlay o‘chirish" in text or "butunlay o'chirish" in text)
    R.check("Nimalar o'chishi ko'rsatildi", "savollar:" in text)

    confirm_cb = sim.find_callback(
        index, lambda b: (b.callback_data or "").startswith("exam:delete_yes")
    )
    R.check("Tasdiqlash tugmasi bor", confirm_cb is not None)

    copy_id = copy.id
    index = await sim.click(SECOND_ID, confirm_cb)
    R.check("Test o'chirildi", "chirildi" in sim.joined_texts(index).lower())

    exists = await q(lambda: Exam.objects.filter(id=copy_id).exists())
    R.check("Baza tozalandi", not exists)

    # --- Begona testni o'chirib bo'lmaydi ---
    other = await q(lambda: Exam.objects.exclude(owner__telegram_id=SECOND_ID).first())
    if other is not None:
        index = await sim.click(SECOND_ID, f"exam:delete:{other.id}")
        R.check("Begona testni o'chirib bo'lmaydi",
                "faqat administratorlar" in sim.joined_texts(index).lower())

    # --- Web ilova buyrug'i ---
    index = await sim.send(SECOND_ID, "/ilova")
    R.check("Web ilova taklif qilindi", "Web ilova" in sim.joined_texts(index))

    app_button = None
    for markup in sim.session.all_markups_since(index):
        for row in getattr(markup, "inline_keyboard", []) or []:
            for button in row:
                if button.web_app is not None:
                    app_button = button
    R.check("Web ilova tugmasi mavjud", app_button is not None)
    if app_button:
        R.check("Tugma /app/ ga ishora qiladi", "/app/" in app_button.web_app.url)


# ==========================================================================
#  6. Emoji ishlatilmasligini tekshirish
# ==========================================================================


def scenario_no_emoji(sim: Simulator) -> None:
    import re

    R.head("6. Botda emoji ishlatilmasligi")

    emoji_re = re.compile(
        "[\U0001F300-\U0001FAFF\U00002600-\U000027BF"
        "\U00002B00-\U00002BFF\U0001F1E6-\U0001F1FF\U0000FE0F]"
    )
    allowed = "✓✗±·•—–…›‹«»●○■□▰▱°≤≥≠√π∛×÷−⁄"

    def clean(text):
        return "".join(ch for ch in (text or "") if ch not in allowed)

    bad_texts = []
    for item in sim.session.sent:
        if emoji_re.search(clean(item.get("text", ""))):
            bad_texts.append(item["text"][:60])

    R.check(
        f"Yuborilgan {len(sim.session.sent)} ta xabarda emoji yo'q",
        not bad_texts,
        "; ".join(bad_texts[:3]),
    )

    bad_buttons = []
    for item in sim.session.sent:
        markup = item.get("markup")
        if markup is None:
            continue
        for row in getattr(markup, "inline_keyboard", []) or []:
            for button in row:
                if emoji_re.search(clean(button.text)):
                    bad_buttons.append(button.text)
        for row in getattr(markup, "keyboard", []) or []:
            for button in row:
                if emoji_re.search(clean(button.text)):
                    bad_buttons.append(button.text)

    R.check("Tugma yozuvlarida emoji yo'q", not bad_buttons, "; ".join(bad_buttons[:3]))
    R.check(
        "Hujjat izohlarida emoji yo'q",
        not any(emoji_re.search(clean(d.get("caption", ""))) for d in sim.session.documents),
    )
    R.check(
        "Rasm izohlarida emoji yo'q",
        not any(emoji_re.search(clean(p.get("caption", ""))) for p in sim.session.photos),
    )


# ==========================================================================
#  7. Chegaraviy holatlar va himoya
# ==========================================================================


async def scenario_guards(sim: Simulator) -> None:
    R.head("5. Himoya va chegaraviy holatlar")

    # --- Oddiy foydalanuvchi admin paneliga kira olmaydi ---
    index = await sim.send(SECOND_ID, "Admin panel")
    R.check("Oddiy foydalanuvchi admin paneliga kira olmaydi",
            "faqat administratorlar" in sim.joined_texts(index).lower())

    index = await sim.click(SECOND_ID, "menu:admin_stats")
    R.check("Admin callback rad etiladi",
            any("administrator" in alert.lower() for alert in sim.session.alerts[-3:]))

    # --- Obunasiz foydalanuvchi ---
    stranger = 700099
    index = await sim.send(stranger, "/start")
    R.check("Yangi foydalanuvchidan obuna talab qilinadi",
            "a’zo bo‘ling" in sim.joined_texts(index))

    index = await sim.send(stranger, "Testda qatnashish")
    R.check("Obunasiz foydalanuvchi bloklanadi",
            "a’zo bo‘ling" in sim.joined_texts(index))

    # --- Noma'lum buyruq ---
    index = await sim.send(USER_ID, "salom nima gap")
    R.check("Noma'lum matnga javob beriladi",
            "tushunmadim" in sim.joined_texts(index).lower())

    # --- Eskirgan callback ---
    index = await sim.click(USER_ID, "q:pick:1:A")
    R.check("Holatdan tashqari callback ushlanadi",
            any("eskirgan" in alert.lower() for alert in sim.session.alerts[-3:]))

    # --- Bekor qilish ---
    index = await sim.send(USER_ID, "Test yaratish")
    index = await sim.send(USER_ID, "Bekor qilish")
    R.check("Amal bekor qilinadi", "bekor qilindi" in sim.joined_texts(index).lower())

    # --- Yordam ---
    index = await sim.send(USER_ID, "/yordam")
    R.check("Yordam bo'limi ishlaydi", "Yordam" in sim.joined_texts(index))


# ==========================================================================
#  Asosiy oqim
# ==========================================================================


async def run() -> int:
    print("\033[1m" + "═" * 60)
    print("  RASCH TELEGRAM BOT — OQIM SIMULYATSIYASI")
    print("═" * 60 + "\033[0m")
    print(f"Simulyatsiya bazasi: {SIM_DB}\n")

    sim = Simulator()

    try:
        await scenario_registration(sim)
        exam_code = await scenario_create_exam(sim)
        await scenario_take_exam(sim, exam_code)
        await scenario_admin(sim)
        await scenario_manage(sim)
        await scenario_guards(sim)
        scenario_no_emoji(sim)
    except Exception as exc:  # noqa: BLE001
        R.failed += 1
        R.errors.append(f"KUTILMAGAN XATO: {exc}")
        print(f"\n\033[91m✗ Simulyatsiya to'xtadi: {exc}\033[0m")
        traceback.print_exc()

    await sim.bot.session.close()
    return R.summary()


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
