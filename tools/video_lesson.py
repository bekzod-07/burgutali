#!/usr/bin/env python
"""
Video dars — avtomatik yozib olish.

Skript haqiqiy ishlayotgan platformani brauzer orqali boshqaradi va butun
jarayonni video qilib yozadi:

  1. Kirish va platforma haqida (ommaviy bosh sahifa)
  2. Telegram bot suhbati (haqiqiy handler'lardan yozib olingan)
  3. Web ilova — test topshirish, natija, sertifikat
  4. Boshqaruv paneli — testlar, natijalar, Rasch hisoblash
  5. Sertifikatni tekshirish
  6. Yakun

Talablar:
  * platforma ishlab turishi kerak (`ishga_tushirish.ps1`);
  * demo ma'lumot yaratilgan bo'lishi kerak (`tools/demo_data.py --reset`);
  * bot suhbati yozilgan bo'lishi kerak (`tools/video_bot_dialog.py`).

Ishga tushirish:

    python tools\\video_lesson.py

Natija: `data/video/dars.webm` va (ffmpeg topilsa) `data/video/dars.mp4`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright  # noqa: E402

# --------------------------------------------------------------------------
#  Sozlamalar
# --------------------------------------------------------------------------
SITE = os.environ.get("VIDEO_SITE", "http://127.0.0.1:8000")
OUT_DIR = BASE_DIR / "data" / "video"
RAW_DIR = OUT_DIR / "raw"
DIALOG_PATH = OUT_DIR / "bot_dialog.json"

WIDTH, HEIGHT = 1280, 720

PANEL_USER = "demo_admin"
PANEL_PASSWORD = "RaschDemo2026"

# Web ilovaga shu foydalanuvchi nomidan kiramiz (demo ishtirokchi).
VIDEO_USER_ID = 900000001

# Tezlik koeffitsiyenti: 1.0 — odatiy sur'at.
SPEED = float(os.environ.get("VIDEO_SPEED", "1.0"))


def pause(page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000 * SPEED))


# ==========================================================================
#  Sahifaga qo'shiladigan uslub va yordamchi funksiyalar
# ==========================================================================

OVERLAY_JS = r"""
(() => {
  if (window.__lessonReady) return;
  window.__lessonReady = true;

  const style = document.createElement('style');
  style.textContent = `
    @keyframes lsFadeUp { from { opacity: 0; transform: translateY(14px); }
                          to   { opacity: 1; transform: translateY(0); } }
    @keyframes lsRing   { from { transform: translate(-50%,-50%) scale(.35); opacity: .85; }
                          to   { transform: translate(-50%,-50%) scale(1.5); opacity: 0; } }
    #ls-sub {
      position: fixed; left: 0; right: 0; bottom: 0; z-index: 2147483000;
      background: linear-gradient(to top, rgba(8,15,30,.97) 72%, rgba(8,15,30,0));
      color: #eef4ff; padding: 30px 56px 26px;
      font: 500 21px/1.5 "Segoe UI", system-ui, sans-serif;
      letter-spacing: .1px; pointer-events: none;
      display: flex; align-items: flex-end; gap: 18px;
      min-height: 96px; box-sizing: border-box;
    }
    #ls-sub .ls-bar { width: 4px; align-self: stretch; border-radius: 4px;
                      background: #f0b429; flex: none; margin-bottom: 3px; }
    #ls-sub .ls-txt { animation: lsFadeUp .35s ease both; max-width: 1080px; }
    #ls-chip {
      position: fixed; top: 22px; right: 26px; z-index: 2147483000;
      background: rgba(8,15,30,.9); color: #f0b429; pointer-events: none;
      font: 700 13px/1 "Segoe UI", system-ui, sans-serif; letter-spacing: 1.4px;
      padding: 9px 15px; border-radius: 7px; text-transform: uppercase;
    }
    #ls-side {
      position: fixed; top: 0; bottom: 0; left: 0; width: 356px; z-index: 2147482000;
      background: #0b1220; color: #dce6f7; box-sizing: border-box;
      padding: 42px 32px; pointer-events: none;
      font: 400 17px/1.62 "Segoe UI", system-ui, sans-serif;
      border-right: 1px solid rgba(255,255,255,.08);
    }
    #ls-side h4 { margin: 0 0 20px; font-size: 13px; letter-spacing: 1.6px;
                  text-transform: uppercase; color: #f0b429; font-weight: 700; }
    #ls-side p  { margin: 0 0 15px; animation: lsFadeUp .35s ease both; }
    #ls-side p b { color: #ffffff; font-weight: 600; }
    #ls-cursor {
      position: fixed; z-index: 2147483600; width: 22px; height: 30px;
      pointer-events: none; left: 0; top: 0; opacity: 0;
      transition: transform .55s cubic-bezier(.33,.72,.25,1), opacity .25s;
      filter: drop-shadow(0 2px 4px rgba(0,0,0,.45));
    }
    #ls-ring {
      position: fixed; z-index: 2147483500; width: 74px; height: 74px;
      border-radius: 50%; border: 3px solid #f0b429; pointer-events: none;
      left: 0; top: 0; opacity: 0;
    }
  `;
  document.documentElement.appendChild(style);

  const mk = (id, html) => {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement('div');
      el.id = id;
      document.documentElement.appendChild(el);
    }
    if (html !== undefined) el.innerHTML = html;
    return el;
  };

  const cursor = mk('ls-cursor',
    '<svg viewBox="0 0 22 30" width="22" height="30">' +
    '<path d="M2 1.5 L2 24 L7.6 18.6 L11.2 27.4 L14.9 25.8 L11.4 17.4 L19 17 Z"' +
    ' fill="#fff" stroke="#12203a" stroke-width="1.7" stroke-linejoin="round"/></svg>');
  mk('ls-ring', '');

  window.__lsSub = (text) => {
    const el = mk('ls-sub');
    el.innerHTML = '<div class="ls-bar"></div><div class="ls-txt">' + text + '</div>';
    el.style.display = text ? 'flex' : 'none';
  };
  window.__lsChip = (text) => {
    const el = mk('ls-chip', text || '');
    el.style.display = text ? 'block' : 'none';
  };
  window.__lsSide = (title, items) => {
    const el = mk('ls-side');
    if (!title && !items) { el.style.display = 'none'; return; }
    el.style.display = 'block';
    el.innerHTML = '<h4>' + (title || '') + '</h4>' +
      (items || []).map(t => '<p>' + t + '</p>').join('');
  };
  window.__lsCursor = (x, y) => {
    cursor.style.opacity = '1';
    cursor.style.transform = 'translate(' + x + 'px,' + y + 'px)';
  };
  window.__lsTap = (x, y) => {
    const ring = document.getElementById('ls-ring');
    ring.style.left = x + 'px';
    ring.style.top = y + 'px';
    ring.style.opacity = '1';
    ring.style.animation = 'none';
    void ring.offsetWidth;
    ring.style.animation = 'lsRing .55s ease-out forwards';
  };
  window.__lsHideCursor = () => { cursor.style.opacity = '0'; };
})();
"""


# ==========================================================================
#  Dars rejissyori
# ==========================================================================


class Lesson:
    """Sahnalarni ketma-ket ko'rsatib, izohlarni ekranga chiqaradi."""

    def __init__(self, page) -> None:
        self.page = page
        self._chip = ""
        self._started = time.time()
        self.chapters: list[tuple[float, str]] = []

    # ----------------------------------------------------------------
    def chapter(self, name: str) -> None:
        """Bob boshlanishini vaqti bilan belgilaydi (YouTube uchun)."""
        self.chapters.append((time.time() - self._started, name))

    # ----------------------------------------------------------------
    #  Asosiy yordamchilar
    # ----------------------------------------------------------------
    def _ensure(self) -> None:
        self.page.evaluate(OVERLAY_JS)
        if self._chip:
            self.page.evaluate("t => window.__lsChip(t)", self._chip)

    def chip(self, text: str) -> None:
        """O'ng yuqoridagi modul yorlig'i."""
        self._chip = text
        self._ensure()

    def say(self, text: str, seconds: float = 3.2) -> None:
        """Pastdagi izoh matni."""
        self._ensure()
        self.page.evaluate("t => window.__lsSub(t)", text)
        pause(self.page, seconds)

    def side(self, title: str, items: list[str], seconds: float = 0.0) -> None:
        """Chap paneldagi izoh (Mini App sahnalari uchun)."""
        self._ensure()
        self.page.evaluate(
            "([t, i]) => window.__lsSide(t, i)", [title, items]
        )
        if seconds:
            pause(self.page, seconds)

    def clear_side(self) -> None:
        self._ensure()
        self.page.evaluate("() => window.__lsSide(null, null)")

    def goto(self, url: str, *, wait: float = 1.6) -> None:
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        self._ensure()
        pause(self.page, wait)

    def beat(self, seconds: float = 1.0) -> None:
        pause(self.page, seconds)

    # ----------------------------------------------------------------
    #  Kursor bilan bosish
    # ----------------------------------------------------------------
    def point(self, locator, *, settle: float = 0.75) -> tuple[float, float] | None:
        """Kursorni element ustiga olib boradi."""
        try:
            locator.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        pause(self.page, 0.25)
        box = locator.bounding_box()
        if not box:
            return None
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        self._ensure()
        self.page.evaluate("([x, y]) => window.__lsCursor(x, y)", [x - 2, y - 4])
        pause(self.page, settle)
        return x, y

    def click(self, locator, *, after: float = 1.6, settle: float = 0.75) -> bool:
        """Kursorni olib borib, bosish animatsiyasi bilan bosadi."""
        spot = self.point(locator, settle=settle)
        if spot is None:
            return False
        self.page.evaluate("([x, y]) => window.__lsTap(x, y)", list(spot))
        pause(self.page, 0.35)
        try:
            locator.click(timeout=8000)
        except Exception:
            try:
                locator.click(timeout=5000, force=True)
            except Exception:
                return False
        try:
            self.page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        self._ensure()
        pause(self.page, after)
        return True

    def type_into(self, locator, text: str, *, delay: int = 70, after: float = 0.9) -> None:
        self.point(locator, settle=0.5)
        try:
            locator.click(timeout=5000)
            locator.type(text, delay=delay)
        except Exception:
            try:
                locator.fill(text)
            except Exception:
                return
        self._ensure()
        pause(self.page, after)

    def scroll(self, distance: int = 520, *, steps: int = 26, after: float = 0.8) -> None:
        """Sahifani silliq aylantiradi."""
        step = distance / steps
        for _ in range(steps):
            self.page.mouse.wheel(0, step)
            pause(self.page, 0.028)
        pause(self.page, after)

    def scroll_top(self) -> None:
        self.page.evaluate("() => window.scrollTo({top: 0, behavior: 'smooth'})")
        pause(self.page, 0.8)

    # ----------------------------------------------------------------
    #  Sarlavha kartasi
    # ----------------------------------------------------------------
    def title_card(
        self,
        eyebrow: str,
        title: str,
        lines: list[str],
        *,
        seconds: float = 4.6,
        accent: str = "#f0b429",
    ) -> None:
        items = "".join(
            f'<li style="animation-delay:{0.25 + i * 0.16}s">{line}</li>'
            for i, line in enumerate(lines)
        )
        html = f"""<!doctype html><meta charset="utf-8"><body style="margin:0">
<div style="width:100vw;height:100vh;box-sizing:border-box;
     background:radial-gradient(1100px 620px at 22% 14%, #16294a 0%, #0a1122 62%);
     background-color:#0a1122;color:#eaf0fb;display:flex;flex-direction:column;
     justify-content:center;padding:0 96px;
     font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden">
  <style>
    @keyframes up {{ from {{opacity:0;transform:translateY(20px)}} to {{opacity:1;transform:translateY(0)}} }}
    h1 {{ font-size:56px; line-height:1.12; margin:0 0 26px; font-weight:700;
          letter-spacing:-.6px; animation:up .5s ease both; animation-delay:.1s }}
    .eb {{ color:{accent}; font-size:14px; letter-spacing:3.4px; font-weight:700;
           text-transform:uppercase; margin-bottom:22px; animation:up .5s ease both }}
    ul {{ margin:0; padding:0; list-style:none; font-size:23px; line-height:1.75;
          color:#a8bad6; max-width:920px }}
    li {{ animation:up .5s ease both; padding-left:26px; position:relative; margin-bottom:6px }}
    li:before {{ content:''; position:absolute; left:0; top:16px; width:11px; height:2px;
                 background:{accent}; border-radius:2px }}
    .rule {{ width:82px; height:4px; background:{accent}; border-radius:4px; margin:0 0 34px }}
  </style>
  <div class="eb">{eyebrow}</div>
  <h1>{title}</h1>
  <div class="rule"></div>
  <ul>{items}</ul>
</div></body>"""
        self.page.set_content(html)
        self._chip = ""
        pause(self.page, seconds)


# ==========================================================================
#  Telegram suhbati sahnasi
# ==========================================================================

CHAT_SHELL = """<!doctype html><meta charset="utf-8"><body style="margin:0">
<div id="wrap" style="width:100vw;height:100vh;display:flex;
     font-family:'Segoe UI',system-ui,sans-serif;background:#0b1220;overflow:hidden">

  <aside id="note" style="width:356px;flex:none;box-sizing:border-box;padding:42px 32px;
       color:#dce6f7;border-right:1px solid rgba(255,255,255,.08)">
    <h4 style="margin:0 0 20px;font-size:13px;letter-spacing:1.6px;text-transform:uppercase;
        color:#f0b429;font-weight:700">TELEGRAM BOT</h4>
    <div id="note-body" style="font-size:17px;line-height:1.62"></div>
  </aside>

  <main style="flex:1;display:flex;flex-direction:column;background:#17212b">
    <header style="flex:none;height:62px;background:#202b36;display:flex;align-items:center;
        gap:14px;padding:0 26px;border-bottom:1px solid rgba(0,0,0,.25)">
      <div style="width:40px;height:40px;border-radius:50%;background:#f0b429;color:#1a2330;
          display:flex;align-items:center;justify-content:center;font-weight:700;font-size:17px">R</div>
      <div>
        <div id="chat-title" style="color:#fff;font-size:15.5px;font-weight:600">Rasch Math Bot</div>
        <div id="chat-sub" style="color:#7d8e9e;font-size:12.5px">bot</div>
      </div>
    </header>

    <div id="feed" style="flex:1;overflow:hidden;padding:22px 30px 16px;
        display:flex;flex-direction:column;gap:9px;justify-content:flex-end"></div>

    <div id="replybar" style="flex:none;padding:0 30px 18px;display:none;
        flex-wrap:wrap;gap:7px"></div>
  </main>
</div>
<style>
  @keyframes pop { from {opacity:0;transform:translateY(12px) scale(.985)} to {opacity:1;transform:none} }
  .msg { max-width:74%; padding:10px 14px; border-radius:14px; font-size:15px; line-height:1.5;
         animation:pop .3s ease both; white-space:pre-wrap; word-break:break-word }
  .bot { background:#212d3b; color:#e9eff5; align-self:flex-start; border-bottom-left-radius:5px }
  .me  { background:#2b5278; color:#fff;    align-self:flex-end;   border-bottom-right-radius:5px }
  .msg b { color:#fff; font-weight:600 }
  .msg i { color:#9fb3c8 }
  .msg code { background:rgba(255,255,255,.12); padding:1px 6px; border-radius:4px;
              font-family:Consolas,monospace; font-size:14px }
  .kb { display:flex; flex-wrap:wrap; gap:6px; margin-top:9px }
  .kb span { background:#31455a; color:#cfe1f2; font-size:13.5px; padding:6px 11px;
             border-radius:8px; border:1px solid rgba(255,255,255,.07) }
  .kb span.hot { background:#f0b429; color:#1a2330; border-color:#f0b429; font-weight:600 }
  .rb { background:#28414f; color:#cfe1f2; font-size:13.5px; padding:8px 13px; border-radius:9px }
  .alert { align-self:center; background:rgba(240,180,41,.16); color:#f5cf7a;
           border:1px solid rgba(240,180,41,.35); font-size:13.5px; padding:6px 14px;
           border-radius:20px; animation:pop .3s ease both }
  .typing { align-self:flex-start; background:#212d3b; border-radius:14px; padding:13px 16px;
            display:flex; gap:5px; animation:pop .2s ease both }
  .typing i { width:7px; height:7px; border-radius:50%; background:#7d8e9e; display:block;
              animation:blink 1.1s infinite }
  .typing i:nth-child(2){animation-delay:.18s} .typing i:nth-child(3){animation-delay:.36s}
  @keyframes blink { 0%,60%,100%{opacity:.3} 30%{opacity:1} }
  #note-body p { margin:0 0 15px; animation:pop .35s ease both }
  #note-body p b { color:#fff; font-weight:600 }
</style>
<script>
  const feed = document.getElementById('feed');
  const replybar = document.getElementById('replybar');

  function trim() {
    while (feed.scrollHeight > feed.clientHeight && feed.children.length > 1) {
      feed.removeChild(feed.firstElementChild);
    }
  }
  window.lsChatTitle = (name, sub) => {
    document.getElementById('chat-title').textContent = name;
    document.getElementById('chat-sub').textContent = sub;
  };
  window.lsNote = (items) => {
    document.getElementById('note-body').innerHTML =
      (items || []).map(t => '<p>' + t + '</p>').join('');
  };
  window.lsTyping = (on) => {
    const old = document.getElementById('tp');
    if (old) old.remove();
    if (on) {
      const d = document.createElement('div');
      d.id = 'tp'; d.className = 'typing';
      d.innerHTML = '<i></i><i></i><i></i>';
      feed.appendChild(d); trim();
    }
  };
  window.lsMsg = (side, html, buttons, hot) => {
    const old = document.getElementById('tp');
    if (old) old.remove();
    const d = document.createElement('div');
    d.className = 'msg ' + (side === 'me' ? 'me' : 'bot');
    let inner = html;
    if (buttons && buttons.length) {
      inner += '<div class="kb">' + buttons.map(b =>
        '<span' + (b === hot ? ' class="hot"' : '') + '>' + b + '</span>').join('') + '</div>';
    }
    d.innerHTML = inner;
    feed.appendChild(d); trim();
  };
  window.lsAlert = (text) => {
    const d = document.createElement('div');
    d.className = 'alert'; d.textContent = text;
    feed.appendChild(d); trim();
  };
  window.lsReply = (buttons) => {
    if (!buttons || !buttons.length) { replybar.style.display = 'none'; return; }
    replybar.style.display = 'flex';
    replybar.innerHTML = buttons.map(b => '<div class="rb">' + b + '</div>').join('');
  };
  window.lsClear = () => { feed.innerHTML = ''; replybar.style.display = 'none'; };
</script>
</body>"""


class Chat:
    """Telegram suhbatini kadr-kadr ko'rsatadi."""

    def __init__(self, page) -> None:
        self.page = page

    def open(self) -> None:
        self.page.set_content(CHAT_SHELL)
        pause(self.page, 0.6)

    def note(self, items: list[str]) -> None:
        self.page.evaluate("i => window.lsNote(i)", items)

    def who(self, name: str, sub: str) -> None:
        self.page.evaluate("([n, s]) => window.lsChatTitle(n, s)", [name, sub])

    def clear(self) -> None:
        self.page.evaluate("() => window.lsClear()")
        pause(self.page, 0.3)

    def me(self, text: str, *, wait: float = 1.0) -> None:
        self.page.evaluate(
            "([s, h, b, k]) => window.lsMsg(s, h, b, k)", ["me", text, None, None]
        )
        pause(self.page, wait)

    def bot(
        self,
        text: str,
        *,
        buttons: list[str] | None = None,
        hot: str | None = None,
        wait: float = 2.4,
        typing: float = 0.7,
    ) -> None:
        if typing:
            self.page.evaluate("() => window.lsTyping(true)")
            pause(self.page, typing)
        self.page.evaluate(
            "([s, h, b, k]) => window.lsMsg(s, h, b, k)", ["bot", text, buttons, hot]
        )
        pause(self.page, wait)

    def alert(self, text: str, *, wait: float = 1.2) -> None:
        self.page.evaluate("t => window.lsAlert(t)", text)
        pause(self.page, wait)

    def reply(self, buttons: list[str] | None) -> None:
        self.page.evaluate("b => window.lsReply(b)", buttons)


# ==========================================================================
#  Suhbat yozuvidan foydalanish
# ==========================================================================


class DialogTape:
    """`video_bot_dialog.py` yozgan suhbatni indeks bo'yicha o'qiydi."""

    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.log: list[dict] = data["log"]
        self.teacher = data["teacher_id"]
        self.student = data["student_id"]

    def slice(self, start: int, end: int) -> list[dict]:
        return self.log[start:end]

    def find(self, needle: str, *, start: int = 0, side: str = "bot") -> int:
        for i in range(start, len(self.log)):
            item = self.log[i]
            if item["side"] == side and needle.lower() in (item.get("text") or "").lower():
                return i
        return -1


def html_of(item: dict) -> str:
    """Bot xabarini chat pufakchasi uchun HTML ga aylantiradi."""
    text = item.get("text") or ""
    return text.replace("\n", "<br>")


def buttons_of(item: dict) -> list[str]:
    rows = item.get("inline") or []
    return [b["text"] for row in rows for b in row]


def reply_of(item: dict) -> list[str] | None:
    rows = item.get("reply")
    if not rows:
        return None
    return [b["text"] for row in rows for b in row]


def play(chat: Chat, items: list[dict], *, hot_next: bool = True,
         bot_wait: float = 2.3, me_wait: float = 1.0) -> None:
    """Suhbat parchasini ketma-ket ko'rsatadi."""
    for i, item in enumerate(items):
        side = item["side"]
        if side == "user":
            chat.me(item.get("text") or "", wait=me_wait)
        elif side == "alert":
            chat.alert(item.get("text") or "", wait=0.9)
        else:
            hot = None
            if hot_next:
                # Keyingi foydalanuvchi harakati qaysi tugma ekanini belgilaymiz
                for nxt in items[i + 1:]:
                    if nxt["side"] == "user":
                        hot = nxt.get("text")
                        break
            chat.bot(
                html_of(item),
                buttons=buttons_of(item) or None,
                hot=hot,
                wait=bot_wait,
            )
            rb = reply_of(item)
            if rb:
                chat.reply(rb)


# ==========================================================================
#  Ma'lumot bazasidan kerakli qiymatlar
# ==========================================================================


def collect_facts() -> dict:
    """Videoda ishlatiladigan kod va raqamlarni bazadan oladi."""
    from core.django_setup import setup_django

    setup_django()

    from apps.certificates.models import Certificate
    from apps.exams.models import Exam
    from apps.accesscodes.models import AccessCode

    facts: dict = {}

    # Panel uchun — yakunlangan, natijalari hisoblangan testlar
    facts["rasch_exam"] = (
        Exam.objects.filter(exam_type="rasch_free", status="published")
        .order_by("id")
        .first()
    )
    facts["paid_exam"] = (
        Exam.objects.filter(exam_type="rasch_paid").order_by("-id").first()
    )

    # Web ilova uchun — hali topshirilmagan faol testlar
    facts["open_exam"] = (
        Exam.objects.filter(exam_type="simple", status="active")
        .order_by("-id")
        .first()
    )
    facts["live_national"] = (
        Exam.objects.filter(status="active", is_national_template=True)
        .order_by("-id")
        .first()
    )

    cert = Certificate.objects.order_by("-id").first()
    facts["certificate"] = cert
    facts["cert_number"] = getattr(cert, "number", "") if cert else ""

    paid = facts["paid_exam"]
    if paid is not None:
        code = AccessCode.objects.filter(exam=paid, status="unused").first()
        facts["access_code"] = code.code if code else ""
    else:
        facts["access_code"] = ""

    return facts


# ==========================================================================
#  Sahnalar
# ==========================================================================


def scene_intro(lesson: Lesson) -> None:
    lesson.title_card(
        "Video dars",
        "Rasch Math Platform",
        [
            "Telegram bot orqali matematik testlar o‘tkazish",
            "Rasch (IRT-1PL) modeli asosida adolatli baholash",
            "Web ilova, boshqaruv paneli va PDF sertifikatlar",
        ],
        seconds=6.0,
    )
    lesson.title_card(
        "Darsda nimalar bor",
        "Olti bosqich",
        [
            "1 — Platforma bilan tanishuv",
            "2 — Telegram bot: ro‘yxatdan o‘tishdan natijagacha",
            "3 — Web ilova: test topshirish va tahlil",
            "4 — Boshqaruv paneli va Rasch hisobi",
            "5 — Sertifikat va uni tekshirish",
            "6 — Xulosa",
        ],
        seconds=6.5,
    )


def scene_home(lesson: Lesson) -> None:
    lesson.title_card(
        "1-bosqich",
        "Platforma bilan tanishuv",
        ["Ommaviy sahifa · imkoniyatlar · baholash shkalasi"],
        seconds=3.6,
    )
    lesson.chip("1 — TANISHUV")
    lesson.goto(f"{SITE}/")
    lesson.say(
        "Platformaning ommaviy sahifasi. Bu yerda testlar soni, topshirilgan "
        "javoblar va berilgan sertifikatlar ko‘rinib turadi.",
        4.4,
    )
    lesson.say(
        "Maksimal ball — <b>90.14</b>. Bu Milliy sertifikat shkalasidagi eng yuqori "
        "natija; barcha ballar shu shkalaga keltiriladi.",
        4.2,
    )
    lesson.scroll(520)
    lesson.say(
        "Platformaning to‘rt asosiy imkoniyati: uch xil test turi, Rasch baholash, "
        "matematik klaviatura va bir martalik ID kodlar.",
        4.6,
    )
    lesson.scroll(560)
    lesson.say(
        "Rasch modelining mohiyati: har bir savolning qiyinligi javoblar "
        "matritsasidan hisoblanadi, o‘quvchining darajasi esa aynan shu qiyinlikni "
        "hisobga olib baholanadi.",
        5.0,
    )
    lesson.scroll(560)
    lesson.say(
        "Baholash shkalasi: 70 balldan yuqori — A+, 46 balldan past bo‘lsa daraja "
        "berilmaydi. Chegaralar texnik topshiriqqa aynan mos.",
        4.6,
    )
    lesson.scroll(600)
    lesson.say("Sahifa oxirida bot va sertifikat tekshiruviga havolalar bor.", 3.2)


def scene_bot(chat: Chat, lesson: Lesson, tape: DialogTape) -> None:
    lesson.title_card(
        "2-bosqich",
        "Telegram bot",
        [
            "Majburiy obuna va ro‘yxatdan o‘tish",
            "Test yaratish sehrgari",
            "Testni topshirish va natijani ko‘rish",
        ],
        seconds=4.4,
    )

    chat.open()

    # --- 2.1 Ro'yxatdan o'tish -------------------------------------
    chat.who("Rasch Math Bot", "Sardor Aliyev bilan suhbat")
    chat.note([
        "<b>Ro‘yxatdan o‘tish</b>",
        "Bot avval kanalga a’zolikni tekshiradi.",
        "So‘ng ism-familiya va telefon raqami so‘raladi.",
        "Ism kamida ikki so‘zdan iborat bo‘lishi shart — sertifikatda "
        "to‘liq ism chiqishi uchun.",
    ])
    play(chat, tape.slice(0, 16), bot_wait=2.6)
    lesson.beat(1.4)

    # --- 2.2 Test yaratish ------------------------------------------
    chat.clear()
    chat.who("Rasch Math Bot", "Nodira Qodirova bilan suhbat")
    chat.note([
        "<b>Test yaratish sehrgari</b>",
        "O‘qituvchi test turini tanlaydi, nom beradi, savollar sonini "
        "ko‘rsatadi va javob kalitini kiritadi.",
        "Oxirida test kodi beriladi — o‘quvchilar shu kod bilan kiradi.",
    ])
    start = tape.find("Yangi test yaratish")
    play(chat, tape.slice(start - 1, start + 15), bot_wait=2.5)
    lesson.beat(1.6)

    # --- 2.3 Testni topshirish --------------------------------------
    chat.clear()
    chat.who("Rasch Math Bot", "Sardor Aliyev bilan suhbat")
    chat.note([
        "<b>Testni topshirish</b>",
        "O‘quvchi kodni kiritadi. Noto‘g‘ri kod kiritilsa, bot ogohlantiradi.",
        "Har bir javob darhol saqlanadi — internet uzilsa ham yo‘qolmaydi.",
        "Savollar orasida erkin yurish mumkin.",
    ])
    start = tape.find("Test kodini kiriting")
    play(chat, tape.slice(start - 1, start + 8), bot_wait=2.4)

    chat.note([
        "<b>Savollarga javob berish</b>",
        "Progress chizig‘i qancha savol bajarilganini ko‘rsatadi.",
        "Tanlangan variant <b>●</b> belgisi bilan belgilanadi.",
        "«Ko‘rib chiqish» — barcha javoblarni bir ekranda tekshirish.",
    ])
    q = tape.find("1-savol")
    play(chat, tape.slice(q, q + 10), bot_wait=1.35, me_wait=0.7)

    # --- 2.4 Yakunlash va natija ------------------------------------
    chat.note([
        "<b>Yakunlash</b>",
        "Bot avval tasdiq so‘raydi — yuborilgandan keyin javoblarni "
        "o‘zgartirib bo‘lmaydi.",
        "Natija darhol chiqadi: to‘g‘ri javoblar, foiz va tahlil.",
    ])
    fin = tape.find("Javoblaringiz</b>")
    if fin < 0:
        fin = tape.find("Javob berilgan")
    play(chat, tape.slice(fin, fin + 8), bot_wait=2.8)
    lesson.beat(1.8)

    chat.note([
        "<b>Javoblar tahlili</b>",
        "Har bir savol bo‘yicha: qaysi javob berilgan va qaysi javob to‘g‘ri.",
        "✓ — to‘g‘ri, ✗ — xato.",
    ])
    ans = tape.find("javoblaringiz")
    if ans > 0:
        play(chat, tape.slice(ans - 1, ans + 1), bot_wait=4.5)
    lesson.beat(1.6)


def tab(lesson: Lesson, name: str):
    return lesson.page.locator(f'.tab[data-tab="{name}"]')


def scene_app(lesson: Lesson, facts: dict) -> None:
    lesson.title_card(
        "3-bosqich",
        "Web ilova",
        [
            "Telegram Mini App — botning menyu tugmasidan ochiladi",
            "Test topshirish, natija tahlili, sertifikat",
        ],
        seconds=4.2,
    )
    lesson.chip("3 — WEB ILOVA")
    lesson.goto(f"{SITE}/app/", wait=2.6)

    lesson.side(
        "WEB ILOVA",
        [
            "Ilova botning menyu tugmasidan ochiladi.",
            "Kirish <b>Telegram initData</b> imzosi bilan tekshiriladi — "
            "alohida parol kerak emas.",
            "Yuqorida profil va uchta hisoblagich: natijalar, sertifikatlar, "
            "o‘z testlari.",
        ],
    )
    lesson.beat(5.2)

    lesson.side(
        "TEZ AMALLAR",
        [
            "To‘rtta asosiy amal bir bosishda:",
            "<b>Testda qatnashish</b> — ochiq testlar va kod orqali kirish.",
            "<b>Test yaratish</b> — o‘z testingizni ochish.",
            "<b>Natijalarim</b> — ball, daraja, javoblar tahlili.",
            "<b>Sertifikatlar</b> — PDF yuklab olish.",
        ],
    )
    lesson.beat(5.0)

    # --- Testlar bo'limi --------------------------------------------
    lesson.click(tab(lesson, "exams"), after=2.2)
    lesson.side(
        "TESTLAR",
        [
            "Ochiq testlar ro‘yxati.",
            "Yopiq test uchun <b>test kodi</b> kiritiladi — kod o‘qituvchida.",
            "Har bir kartochkada test turi va savollar soni ko‘rinadi.",
        ],
    )
    lesson.beat(4.8)


def current_question_no(page, *, fallback: int = 1) -> int:
    """Ekrandagi joriy savol raqamini o'qiydi («7-savol» -> 7)."""
    try:
        text = page.locator(".q-no").first.inner_text(timeout=4000)
        return int(text.split("-")[0].strip())
    except Exception:
        return fallback


def open_exam(lesson: Lesson, code: str) -> bool:
    """Testlar ro'yxatidan berilgan kodli testni ochadi."""
    card = lesson.page.locator(f'[data-act="open-exam"][data-code="{code}"]').first
    if card.count() == 0:
        return False
    return lesson.click(card, after=2.2)


def scene_taking(lesson: Lesson, facts: dict) -> None:
    """Oddiy testni web ilovada haqiqatan topshirish."""
    page = lesson.page
    simple = facts.get("open_exam")
    if simple is None:
        return

    if not open_exam(lesson, simple.code):
        lesson.goto(f"{SITE}/app/", wait=1.6)
        lesson.click(tab(lesson, "exams"), after=1.6)
        open_exam(lesson, simple.code)

    lesson.side(
        "TEST HAQIDA",
        [
            "Boshlashdan oldin: test turi, savollar soni, maksimal ball "
            "va tugash vaqti ko‘rsatiladi.",
            "Pullik testda aynan shu bosqichda <b>ID kod</b> so‘raladi.",
        ],
    )
    lesson.beat(4.4)

    lesson.click(page.locator('[data-act="start-exam"]').first, after=2.4)

    lesson.side(
        "TEST TOPSHIRISH",
        [
            "Yuqorida — <b>savollar palitrasi</b>: qaysi savolga javob "
            "berilgan, qaysisi bo‘sh.",
            "Javob tanlanishi bilan darhol serverga saqlanadi.",
            "Ilova yopilib qolsa ham, javoblar joyida qoladi.",
        ],
    )
    lesson.beat(4.6)

    # --- Savollarga javob berish ------------------------------------
    #  Javob kaliti — «ABCDABCDAB». Joriy savol raqami ekrandan o'qiladi,
    #  shunda javob har doim o'z savoliga tushadi. 3- va 7-savolga ataylab
    #  xato javob beriladi — natija tahlili videoda ko'rinsin.
    key = "ABCDABCDAB"
    wrong_at = {3, 7}
    total = simple.questions.count()
    for i in range(total):
        order = current_question_no(page, fallback=i + 1)
        correct = key[(order - 1) % len(key)]
        letter = correct if order not in wrong_at else ("A" if correct != "A" else "C")

        choice = page.locator(f'.choice[data-letter="{letter}"]').first
        if choice.count() == 0:
            break
        fast = i >= 2
        lesson.click(
            choice,
            after=0.55 if fast else 1.5,
            settle=0.3 if fast else 0.7,
        )

        if i == 1:
            lesson.side(
                "JAVOB DARHOL SAQLANADI",
                [
                    "Har bosishdan keyin javob serverga yuboriladi.",
                    "Bitta javobli savolda ilova <b>o‘zi keyingi savolga</b> "
                    "o‘tadi — ortiqcha bosish shart emas.",
                    "Palitradan istalgan savolga qaytib, javobni "
                    "o‘zgartirish mumkin.",
                ],
            )
            lesson.beat(3.6)

        # Bitta javobli savolda ilova o'zi keyingi savolga o'tadi.
        # Oxirgi savolda o'tish bo'lmaydi — kutish ham shart emas.
        if i < total - 1:
            try:
                page.wait_for_function(
                    "n => { const el = document.querySelector('.q-no');"
                    " return el && parseInt(el.textContent) !== n; }",
                    arg=order,
                    timeout=6000,
                )
            except Exception:
                pass

    # --- Yakunlash --------------------------------------------------
    lesson.side(
        "YAKUNLASH",
        [
            "Yuborishdan oldin ilova tasdiq so‘raydi.",
            "Yuborilgandan keyin javoblarni o‘zgartirib bo‘lmaydi.",
        ],
    )
    lesson.beat(2.2)
    lesson.click(page.locator('[data-act="finish"]').first, after=1.6)
    lesson.click(page.locator("#modal-ok").first, after=3.0)


def scene_mathpad(lesson: Lesson, facts: dict) -> None:
    """Ochiq savollar va matematik klaviatura."""
    page = lesson.page
    national = facts.get("live_national")
    if national is None:
        return

    lesson.title_card(
        "3-bosqich · davomi",
        "Ochiq savollar va matematik klaviatura",
        [
            "45 savolli milliy sertifikat shabloni",
            "36–45-savollarda variant yo‘q — javob yoziladi",
        ],
        seconds=4.2,
    )
    lesson.chip("3 — WEB ILOVA")

    lesson.goto(f"{SITE}/app/", wait=2.0)
    lesson.click(tab(lesson, "exams"), after=1.8)

    lesson.side(
        "MILLIY SHABLON",
        [
            "45 ta savol: <b>1–32</b> — A/B/C/D, <b>33–35</b> — A–F "
            "(bir nechta to‘g‘ri javob), <b>36–45</b> — ochiq javob.",
            "Ochiq savollar Rasch matritsasida <b>ikkita birlik</b> sifatida "
            "hisoblanadi: a) va b) qismlari.",
        ],
    )
    lesson.beat(4.4)

    if not open_exam(lesson, national.code):
        return
    lesson.click(page.locator('[data-act="start-exam"]').first, after=2.6)

    # --- Ko'p javobli savol (33) ------------------------------------
    jump = page.locator('[data-act="jump"][data-index="32"]').first
    if jump.count():
        lesson.click(jump, after=1.8)
        lesson.side(
            "KO‘P JAVOBLI SAVOL",
            [
                "33–35-savollarda <b>A dan F gacha</b> oltita variant bor.",
                "To‘g‘ri javob bittadan ko‘p bo‘lishi mumkin — "
                "belgilar kvadrat shaklda.",
            ],
        )
        lesson.beat(3.6)
        for letter in ("A", "B"):
            choice = page.locator(f'.choice[data-letter="{letter}"]').first
            if choice.count():
                lesson.click(choice, after=0.8, settle=0.4)

    # --- Ochiq savol (36) -------------------------------------------
    jump = page.locator('[data-act="jump"][data-index="35"]').first
    if jump.count():
        lesson.click(jump, after=2.0)

    lesson.side(
        "MATEMATIK KLAVIATURA",
        [
            "Variantlar o‘rniga — <b>a)</b> va <b>b)</b> javob maydonlari.",
            "Pastda maxsus klaviatura: kasr, ildiz, daraja, π, e, "
            "sin, cos, tg, ctg, ln, log, |x|.",
            "Telefon klaviaturasi ochilmaydi — matematik belgilar "
            "shu yerda.",
        ],
    )
    lesson.beat(4.6)

    # Javobni klaviatura orqali kiritamiz: 1/2
    field = page.locator("#ans-a").first
    if field.count():
        lesson.click(field, after=0.7, settle=0.4)
    for label in ("1", "a⁄b", "2"):
        key = page.locator(f'.mkey:has-text("{label}")').first
        if key.count():
            lesson.click(key, after=0.75, settle=0.35)

    lesson.side(
        "JONLI TEKSHIRUV",
        [
            "Yozilgan ifoda darhol serverda <b>SymPy</b> bilan tekshiriladi.",
            "Tekshiruv matematik ekvivalentlik bo‘yicha: "
            "<b>1/2 = 0.5 = 2⁻¹</b>, <b>sin(π/6) = 0.5</b>.",
            "Ya’ni javobning yozilish shakli emas, <b>qiymati</b> muhim.",
        ],
    )
    lesson.beat(5.2)

    lesson.scroll(360, after=1.0)
    lesson.beat(2.6)

    # Testni yakunlamay chiqamiz — javoblar saqlanib qoladi
    leave = page.locator('[data-act="leave"]').first
    if leave.count():
        lesson.click(leave, after=2.0)
        lesson.side(
            "KEYINROQ DAVOM ETTIRISH",
            [
                "Testdan chiqib ketish mumkin — javoblar saqlanib qoladi.",
                "Bosh sahifada <b>«Tugallanmagan test»</b> kartochkasi "
                "paydo bo‘ladi va bir bosishda davom ettiriladi.",
            ],
        )
        lesson.beat(4.2)


def scene_result(lesson: Lesson, facts: dict) -> None:
    page = lesson.page

    lesson.side(
        "NATIJA",
        [
            "Oddiy testda — to‘g‘ri javoblar soni va foiz.",
            "RASH testida — <b>θ</b> (qobiliyat), 90.14 lik shkaladagi "
            "standart ball va daraja.",
            "Quyida har bir savol bo‘yicha to‘g‘ri/xato tahlili.",
        ],
    )
    lesson.beat(4.8)
    lesson.scroll(420, after=1.2)
    lesson.beat(2.2)
    lesson.scroll_top()

    # --- Natijalar bo'limi ------------------------------------------
    lesson.click(tab(lesson, "results"), after=2.2)
    lesson.side(
        "NATIJALARIM",
        [
            "Barcha urinishlar bitta ro‘yxatda.",
            "RASH testlarida ball <b>90.14</b> lik shkalada, yonida daraja.",
            "Kartochkani bosib, javoblar tahliliga o‘tiladi.",
        ],
    )
    lesson.beat(4.6)

    first = page.locator('[data-act="open-result"]').first
    if first.count():
        lesson.click(first, after=2.6)
        lesson.side(
            "JAVOBLAR TAHLILI",
            [
                "Har bir savol: berilgan javob va to‘g‘ri javob.",
                "RASH testida qo‘shimcha ravishda savol qiyinligi <b>b</b> "
                "ham ko‘rsatiladi.",
                "Shu yerdan reytingga va sertifikatga o‘tish mumkin.",
            ],
        )
        lesson.beat(4.4)
        lesson.scroll(420, after=1.0)
        lesson.beat(2.4)


def scene_certificate(lesson: Lesson, facts: dict) -> None:
    page = lesson.page

    lesson.click(tab(lesson, "certificates"), after=2.4)
    lesson.side(
        "SERTIFIKATLAR",
        [
            "Sertifikat faqat <b>pullik RASH testi</b> uchun beriladi.",
            "Bitta tugma — PDF yuklab olinadi.",
            "PDF ichida <b>QR kod</b> bor: uni skanerlab, sertifikat "
            "haqiqiyligini har kim tekshira oladi.",
        ],
    )
    lesson.beat(5.2)

    lesson.click(tab(lesson, "my-exams"), after=2.4)
    lesson.side(
        "TESTLARIM",
        [
            "O‘zi yaratgan testlarni boshqarish: faollashtirish, yopish, "
            "hisoblash, e’lon qilish.",
            "Shu yerdan test nusxalanadi yoki o‘chiriladi.",
            "Test kodi va ID kodlar ham shu bo‘limda.",
        ],
    )
    lesson.beat(4.6)
    lesson.clear_side()


def scene_panel(lesson: Lesson, facts: dict) -> None:
    page = lesson.page
    lesson.title_card(
        "4-bosqich",
        "Boshqaruv paneli",
        [
            "Testlar, savollar, ishtirokchilar va ID kodlar",
            "Rasch hisobi va natijalarni e’lon qilish",
            "Excel va PDF hisobotlar",
        ],
        seconds=4.4,
    )
    lesson.chip("4 — PANEL")

    lesson.goto(f"{SITE}/panel/kirish/", wait=1.6)
    lesson.say(
        "Panelga kirish. Django ning standart admin paneli ishlatilmaydi — "
        "barcha boshqaruv shu yerda, o‘z dizaynida.",
        4.0,
    )

    lesson.type_into(page.locator("input[name='username']"), PANEL_USER)
    lesson.type_into(page.locator("input[name='password']"), PANEL_PASSWORD, delay=45)
    lesson.click(page.locator("button[type='submit'], input[type='submit']").first, after=2.6)

    lesson.say(
        "Umumiy ko‘rsatkichlar: foydalanuvchilar, testlar, urinishlar va "
        "sertifikatlar soni bir ekranda.",
        4.2,
    )
    lesson.scroll(460)
    lesson.beat(2.2)

    # --- Testlar ro'yxati -------------------------------------------
    lesson.goto(f"{SITE}/panel/testlar/", wait=1.8)
    lesson.say(
        "Testlar ro‘yxati. Har bir test uchun turi, holati, savollar soni "
        "va ishtirokchilar ko‘rinadi.",
        4.2,
    )
    lesson.say(
        "Holatlar zanjiri: <b>Qoralama → Faol → Yopilgan → Hisoblangan → "
        "E’lon qilingan</b>.",
        4.0,
    )

    exam = facts.get("rasch_exam")
    if exam is not None:
        lesson.goto(f"{SITE}/panel/testlar/{exam.pk}/", wait=1.8)
        lesson.say(
            "Test tafsiloti. Bu — 45 savolli milliy sertifikat shabloni: "
            "1–32 bitta javobli, 33–35 ko‘p javobli, 36–45 ochiq savollar.",
            5.0,
        )
        lesson.scroll(440)
        lesson.beat(2.0)

        lesson.goto(f"{SITE}/panel/testlar/{exam.pk}/natijalar/", wait=2.0)
        lesson.say(
            "Natijalar jadvali. Bu yerda Rasch hisobining mevasi ko‘rinadi: "
            "θ qiymati, standart ball va daraja.",
            4.6,
        )
        lesson.scroll(420)
        lesson.say(
            "Ishonchlilik ko‘rsatkichlari — <b>KR-20</b> va ishtirokchilarni "
            "ajratish koeffitsiyenti — testning sifatini baholaydi.",
            4.4,
        )
        lesson.scroll(420)
        lesson.beat(2.0)

    paid = facts.get("paid_exam")
    if paid is not None:
        lesson.goto(f"{SITE}/panel/testlar/{paid.pk}/kodlar/", wait=2.0)
        lesson.say(
            "Pullik test uchun bir martalik ID kodlar. Kod uch holatda bo‘ladi: "
            "<b>Ishlatilmagan → Faollashtirilgan → Ishlatilgan</b>.",
            4.8,
        )
        lesson.say(
            "Kod faqat javoblar yakuniy yuborilgandan keyin «ishlatilgan» "
            "holatiga o‘tadi — test yarim yo‘lda uzilsa, kod yonib ketmaydi.",
            4.8,
        )
        lesson.scroll(400)
        lesson.beat(1.8)

    lesson.goto(f"{SITE}/panel/urinishlar/", wait=1.8)
    lesson.say(
        "Barcha urinishlar bitta ro‘yxatda — kim, qaysi testni, qachon "
        "topshirgani va qanday natija olgani.",
        4.4,
    )
    lesson.scroll(380)
    lesson.beat(1.8)

    lesson.goto(f"{SITE}/panel/sertifikatlar/", wait=1.8)
    lesson.say(
        "Berilgan sertifikatlar. Har birining raqami, egasi va berilgan sanasi "
        "bor; kerak bo‘lsa bekor qilish mumkin.",
        4.4,
    )
    lesson.beat(1.6)

    lesson.goto(f"{SITE}/panel/foydalanuvchilar/", wait=1.8)
    lesson.say(
        "Foydalanuvchilar: rollar, telefon raqamlari va bloklash imkoniyati.",
        3.8,
    )
    lesson.beat(1.4)

    lesson.goto(f"{SITE}/panel/tarix/", wait=1.8)
    lesson.say(
        "Amallar tarixi — har bir muhim o‘zgarish yozib boriladi: kim, "
        "qachon, nimani o‘zgartirgan.",
        4.2,
    )
    lesson.beat(1.6)


def scene_verify(lesson: Lesson, facts: dict) -> None:
    page = lesson.page
    lesson.title_card(
        "5-bosqich",
        "Sertifikatni tekshirish",
        ["QR kod yoki sertifikat raqami orqali — hamma uchun ochiq"],
        seconds=3.8,
    )
    lesson.chip("5 — SERTIFIKAT")

    lesson.goto(f"{SITE}/verify/", wait=1.8)
    lesson.say(
        "Sertifikatni tekshirish sahifasi ochiq — bu yerga kirish uchun "
        "ro‘yxatdan o‘tish shart emas.",
        4.0,
    )

    number = facts.get("cert_number") or ""
    if number:
        field = page.locator("input[type='text'], input[name]").first
        lesson.type_into(field, number, delay=60)
        lesson.click(
            page.locator("button[type='submit'], input[type='submit']").first,
            after=2.6,
        )
        lesson.say(
            "Sertifikat haqiqiy: egasi, test nomi, ball, daraja va berilgan sana "
            "ko‘rinib turibdi.",
            4.6,
        )
        lesson.scroll(360)
        lesson.say(
            "Ish beruvchi yoki oliy o‘quv yurti aynan shu sahifa orqali "
            "sertifikatning haqiqiyligiga ishonch hosil qiladi.",
            4.4,
        )
        lesson.beat(1.6)


def scene_outro(lesson: Lesson) -> None:
    lesson.title_card(
        "Xulosa",
        "Nimalarni ko‘rdik",
        [
            "Bot: ro‘yxatdan o‘tish, test yaratish, test topshirish",
            "Web ilova: topshirish, tahlil, sertifikat",
            "Panel: Rasch hisobi, ID kodlar, hisobotlar",
            "Sertifikat: PDF va ochiq tekshiruv",
        ],
        seconds=6.5,
    )
    lesson.title_card(
        "Keyingi qadam",
        "Foydali buyruqlar",
        [
            "ishga_tushirish.ps1 — butun tizimni bitta buyruqda ishga tushirish",
            "toxtatish.ps1 — to‘xtatish",
            "tools/demo_data.py --reset — namoyish ma’lumotlari",
            "docs/ — o‘rnatish, arxitektura va texnik topshiriq hujjatlari",
        ],
        seconds=6.5,
        accent="#63b3ed",
    )
    lesson.title_card(
        "",
        "Dars tugadi",
        ["Rasch Math Platform · matematik testlarni adolatli baholash"],
        seconds=4.5,
    )


# ==========================================================================
#  Ishga tushirish
# ==========================================================================


def find_ffmpeg() -> str | None:
    """To'liq imkoniyatli ffmpeg ni topadi.

    Playwright bilan kelgan ffmpeg faqat video yozish uchun qurilgan —
    unda H.264 kodlagichi yo'q. Shuning uchun avval `imageio-ffmpeg`
    paketidagi to'liq binar, so'ng tizimdagi ffmpeg qidiriladi.
    """
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return shutil.which("ffmpeg")


def convert_to_mp4(webm: Path) -> Path | None:
    """Videoni keng qo'llab-quvvatlanadigan mp4 formatiga o'giradi."""
    exe = find_ffmpeg()
    if not exe:
        print("  [i] ffmpeg topilmadi — video faqat webm formatida qoldi.")
        return None

    mp4 = webm.with_suffix(".mp4")
    cmd = [
        exe, "-y", "-i", str(webm),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(mp4),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  [!] mp4 ga o'girish bajarilmadi:")
        print("     ", (result.stderr or "")[-400:])
        return None
    return mp4


def main() -> int:
    if not DIALOG_PATH.exists():
        print(f"[XATO] {DIALOG_PATH} topilmadi.")
        print("       Avval: python tools\\video_bot_dialog.py")
        return 1

    facts = collect_facts()
    tape = DialogTape(DIALOG_PATH)

    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR, ignore_errors=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Video yozish boshlandi...")
    started = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb"])
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=str(RAW_DIR),
            record_video_size={"width": WIDTH, "height": HEIGHT},
            extra_http_headers={"X-Debug-User": str(VIDEO_USER_ID)},
            device_scale_factor=1,
        )
        context.add_init_script(TELEGRAM_STUB)
        page = context.new_page()
        page.set_default_timeout(12000)

        lesson = Lesson(page)
        chat = Chat(page)

        scenes = [
            ("Kirish", lambda: scene_intro(lesson)),
            ("Platforma bilan tanishuv", lambda: scene_home(lesson)),
            ("Telegram bot", lambda: scene_bot(chat, lesson, tape)),
            ("Web ilova", lambda: scene_app(lesson, facts)),
            ("Testni topshirish", lambda: scene_taking(lesson, facts)),
            ("Natija va tahlil", lambda: scene_result(lesson, facts)),
            ("Matematik klaviatura", lambda: scene_mathpad(lesson, facts)),
            ("Sertifikat va testlarim", lambda: scene_certificate(lesson, facts)),
            ("Boshqaruv paneli", lambda: scene_panel(lesson, facts)),
            ("Sertifikatni tekshirish", lambda: scene_verify(lesson, facts)),
            ("Xulosa", lambda: scene_outro(lesson)),
        ]

        try:
            for name, run in scenes:
                lesson.chapter(name)
                run()
                print(f"  · {name.lower()}")
        finally:
            context.close()
            browser.close()

    # --- Faylni joyiga ko'chirish -----------------------------------
    files = sorted(RAW_DIR.glob("*.webm"), key=lambda f: f.stat().st_size, reverse=True)
    if not files:
        print("[XATO] Video fayl yaratilmadi.")
        return 1

    target = OUT_DIR / "dars.webm"
    if target.exists():
        target.unlink()
    shutil.move(str(files[0]), str(target))
    shutil.rmtree(RAW_DIR, ignore_errors=True)

    size_mb = target.stat().st_size / 1024 / 1024
    minutes = (time.time() - started) / 60
    print()
    print(f"Tayyor: {target}  ({size_mb:.1f} MB, ~{minutes:.1f} daqiqa)")

    mp4 = convert_to_mp4(target)
    if mp4:
        print(f"MP4    : {mp4}  ({mp4.stat().st_size / 1024 / 1024:.1f} MB)")

    write_chapters(lesson.chapters)
    return 0


def write_chapters(chapters: list[tuple[float, str]]) -> None:
    """Bob taymkodlarini faylga yozadi va ekranga chiqaradi."""
    if not chapters:
        return

    lines = []
    for seconds, name in chapters:
        stamp = f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"
        lines.append(f"{stamp} {name}")

    path = OUT_DIR / "boblar.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("Boblar (YouTube tavsifiga qo'yish uchun):")
    for line in lines:
        print(f"  {line}")
    print(f"Fayl   : {path}")


# Telegram Mini App muhitini taqlid qiluvchi minimal obyekt.
TELEGRAM_STUB = r"""
window.Telegram = {
  WebApp: {
    initData: '', initDataUnsafe: {},
    colorScheme: 'light', themeParams: {},
    version: '7.0', platform: 'web',
    isExpanded: true,
    viewportHeight: window.innerHeight,
    viewportStableHeight: window.innerHeight,
    headerColor: '#ffffff', backgroundColor: '#ffffff',
    BackButton: { show(){}, hide(){}, onClick(){}, offClick(){} },
    MainButton: { show(){}, hide(){}, setText(){}, onClick(){}, offClick(){},
                  showProgress(){}, hideProgress(){}, setParams(){} },
    HapticFeedback: { impactOccurred(){}, notificationOccurred(){}, selectionChanged(){} },
    ready(){}, expand(){}, close(){}, sendData(){},
    openLink(u){ location.href = u; }, openTelegramLink(){},
    showAlert(m){ console.log('ALERT', m); },
    showConfirm(m, cb){ cb && cb(true); },
    showPopup(p, cb){ cb && cb(''); },
    onEvent(){}, offEvent(){}, setHeaderColor(){}, setBackgroundColor(){},
    enableClosingConfirmation(){}, disableClosingConfirmation(){},
  }
};
"""


if __name__ == "__main__":
    raise SystemExit(main())
