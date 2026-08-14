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
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright  # noqa: E402

from tools import video_voice  # noqa: E402
from tools.video_voice import Narrator  # noqa: E402

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

# Ilova faqat Telegram ichida ochiladi; brauzerda `debug_user` bilan kiriladi
# (faqat DEBUG=True da ishlaydi — `apps/miniapp/auth.py`).
APP_URL = f"{SITE}/app/?debug_user={VIDEO_USER_ID}"

# Tezlik koeffitsiyenti: 1.0 — odatiy sur'at.
SPEED = float(os.environ.get("VIDEO_SPEED", "1.0"))

# Ovoz: 0 — jim yozuv; VIDEO_VOICE_WAIT=0 — ovoz keshga yig'iladi, lekin
# sahna uni kutmaydi (oqimni tez sinash uchun).
VOICE_ON = os.environ.get("VIDEO_VOICE_OFF", "") != "1"
VOICE_WAIT = os.environ.get("VIDEO_VOICE_WAIT", "1") != "0"

# Ekran ustidagi matn qatlamlari (pastdagi izoh yo'lagi, chapdagi izoh
# paneli va o'ng yuqoridagi yorliq). Diktor hammasini gapirib bergani
# uchun ular standart holatda o'chirilgan: ekranda faqat ilovaning o'zi
# ko'rinadi. Kerak bo'lsa: VIDEO_CAPTIONS=1.
CAPTIONS = os.environ.get("VIDEO_CAPTIONS", "0") == "1"


def pause(page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000 * SPEED))


def hold(page, seconds: float) -> None:
    """Ovoz uchun kutish — tezlik koeffitsiyentiga bog'liq emas."""
    if seconds > 0:
        page.wait_for_timeout(int(seconds * 1000))


def warn(message: str) -> None:
    print(f"  [!] {message}")


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
    /* Chap izoh paneli ochiq bo'lganda sahifa o'ng tomonga suriladi —
       aks holda panel ilovaning chap qismini yopib qo'yadi. */
    html.ls-shift body { padding-left: 356px !important; }
    /* chapga yopishgan qatlamlar */
    html.ls-shift .finish-bar,
    html.ls-shift .modal-backdrop { left: 356px !important; }
    /* markazlashtirilgan qatlamlar (left 50% + translateX -50%) */
    html.ls-shift .app-bar,
    html.ls-shift .tabbar,
    html.ls-shift .mpad,
    html.ls-shift .toast { left: calc(50% + 178px) !important; }
    html.ls-shift .app-bar,
    html.ls-shift .tabbar { width: calc(100% - 356px) !important;
                            max-width: calc(100% - 356px) !important; }
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
    if (!title && !items) {
      el.style.display = 'none';
      document.documentElement.classList.remove('ls-shift');
      return;
    }
    el.style.display = 'block';
    document.documentElement.classList.add('ls-shift');
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

    def __init__(self, page, narrator: Narrator | None = None) -> None:
        self.page = page
        self._chip = ""
        self._started = time.time()
        self.chapters: list[tuple[float, str]] = []
        self.voice = narrator or Narrator(enabled=False)
        # Diktor stsenariydagi tanaffusdan ko'proq gapirsa, ortiqcha vaqt
        # keyingi jim tanaffuslardan ushlab qolinadi — «o'lik» kadr bo'lmasin.
        self._debt = 0.0

    # ----------------------------------------------------------------
    def now(self) -> float:
        return time.time() - self._started

    def chapter(self, name: str) -> None:
        """Bob boshlanishini vaqti bilan belgilaydi (YouTube uchun)."""
        self.chapters.append((self.now(), name))

    # ----------------------------------------------------------------
    #  Diktor
    # ----------------------------------------------------------------
    def tell(self, text: str, *, block: bool = True, scripted: float = 0.0) -> None:
        """Gapni ovozga qo'yadi va (kerak bo'lsa) tugashini kutadi."""
        if not text:
            return
        started = self.now()
        end = self.voice.queue(text, started)
        spoken = max(0.0, end - started - video_voice.GAP)
        if not spoken:
            return
        if block and VOICE_WAIT:
            hold(self.page, max(0.0, started + spoken - self.now()))
            self._debt = min(8.0, self._debt + max(0.0, spoken - scripted))

    # ----------------------------------------------------------------
    #  Asosiy yordamchilar
    # ----------------------------------------------------------------
    def _ensure(self) -> None:
        self.page.evaluate(OVERLAY_JS)
        if self._chip:
            self.page.evaluate("t => window.__lsChip(t)", self._chip)

    def chip(self, text: str) -> None:
        """O'ng yuqoridagi modul yorlig'i (faqat CAPTIONS rejimida)."""
        if not CAPTIONS:
            return
        self._chip = text
        self._ensure()

    def say(self, text: str, seconds: float = 3.2, *, voice: str | None = None) -> None:
        """Sahna izohi — diktor shu matnni o'qiydi.

        `CAPTIONS` yoqilgan bo'lsa, matn ekran pastida ham chiqadi.
        """
        self._ensure()
        if CAPTIONS:
            self.page.evaluate("t => window.__lsSub(t)", text)
        started = self.now()
        self.tell(voice if voice is not None else text, scripted=seconds)
        left = seconds * SPEED - (self.now() - started)
        if left > 0:
            hold(self.page, left)

    def side(self, title: str, items: list[str], seconds: float = 0.0,
             *, voice: str | None = None) -> None:
        """Uzunroq izoh. Ekranda — faqat CAPTIONS rejimida chap panelda."""
        self._ensure()
        if CAPTIONS:
            self.page.evaluate(
                "([t, i]) => window.__lsSide(t, i)", [title, items]
            )
        pause(self.page, 0.45)
        self.tell(voice if voice is not None else " ".join(items))
        if seconds:
            pause(self.page, seconds)

    def clear_side(self) -> None:
        if not CAPTIONS:
            return
        self._ensure()
        self.page.evaluate("() => window.__lsSide(null, null)")

    def goto(self, url: str, *, wait: float = 1.6) -> None:
        try:
            self.page.goto(url, wait_until="domcontentloaded")
        except Exception:
            warn(f"sahifa sekin ochildi: {url}")
            try:
                self.page.goto(url, wait_until="commit", timeout=20000)
            except Exception:
                warn(f"sahifa ochilmadi: {url}")
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        self._ensure()
        pause(self.page, wait)

    def beat(self, seconds: float = 1.0) -> None:
        """Jim tanaffus. Diktor allaqachon gapirgan bo'lsa — qisqaradi."""
        take = min(self._debt, max(0.0, seconds - 0.7))
        self._debt -= take
        pause(self.page, seconds - take)

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
        voice: str | None = None,
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
        started = self.now()
        if voice:
            pause(self.page, 0.5)
            self.tell(voice, scripted=seconds)
        left = seconds * SPEED - (self.now() - started)
        if left > 0:
            hold(self.page, left)


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
  /* Izohsiz rejim: chap panel yashiriladi, suhbat markazga tortiladi. */
  #wrap.no-note aside { display:none }
  #wrap.no-note main { max-width:900px; margin:0 auto; width:100%;
                       border-left:1px solid rgba(255,255,255,.06);
                       border-right:1px solid rgba(255,255,255,.06) }
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
  window.lsNoNote = () => { document.getElementById('wrap').classList.add('no-note'); };
</script>
</body>"""


class Chat:
    """Telegram suhbatini kadr-kadr ko'rsatadi."""

    def __init__(self, page, lesson: "Lesson | None" = None) -> None:
        self.page = page
        self.lesson = lesson

    def open(self) -> None:
        self.page.set_content(CHAT_SHELL)
        if not CAPTIONS:
            self.page.evaluate("() => window.lsNoNote()")
        pause(self.page, 0.6)

    def note(self, items: list[str], *, voice: str | None = None) -> None:
        """Suhbat bo'limining izohi — diktor uni suhbat ustidan o'qiydi."""
        if CAPTIONS:
            self.page.evaluate("i => window.lsNote(i)", items)
        if self.lesson is not None:
            pause(self.page, 0.5)
            self.lesson.tell(voice if voice is not None else " ".join(items),
                             block=False)

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

    # Javob kalitlari — videoda savollarga to'g'ri javob berish uchun.
    def keys_of(exam) -> dict[int, str]:
        if exam is None:
            return {}
        return {
            q.order: (q.correct_key or "")
            for q in exam.questions.all().order_by("order")
        }

    facts["open_keys"] = keys_of(facts["open_exam"])
    facts["national_keys"] = keys_of(facts["live_national"])

    # Panelda ko'rsatiladigan bitta urinish
    facts["attempt_id"] = None
    try:
        from apps.attempts.models import Attempt

        attempt = (
            Attempt.objects.filter(exam=facts["rasch_exam"])
            .order_by("-id")
            .first()
        )
        facts["attempt_id"] = attempt.pk if attempt else None
    except Exception:
        pass

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
        voice="Assalomu alaykum! Bu videoda men o‘zim ishlab chiqqan "
              "matematika test platformasini boshidan oxirigacha ko‘rsatib "
              "beraman. Platforma Telegram bot va web ilova orqali Milliy "
              "sertifikat formatidagi testlarni o‘tkazadi, natijalarni esa "
              "Rash modeli asosida adolatli baholaydi va sertifikat beradi.",
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
        voice="Darsni olti bosqichga bo‘ldim. Avval platforma bilan "
              "tanishamiz. So‘ng Telegram botni ro‘yxatdan o‘tishdan tortib "
              "natijagacha ko‘ramiz. Uchinchi bosqichda web ilovada testni "
              "o‘zimiz topshiramiz. To‘rtinchisida boshqaruv paneliga "
              "kiramiz va Rash hisobini ko‘ramiz. Beshinchi bosqichda "
              "sertifikatni tekshiramiz, oxirida esa xulosa qilamiz. Men bu "
              "yerda platforma egasi, ya’ni administrator nomidan ish "
              "yuritaman — shuning uchun hamma bo‘limni ichkaridan "
              "ko‘rsataman.",
    )


def scene_home(lesson: Lesson) -> None:
    lesson.title_card(
        "1-bosqich",
        "Platforma bilan tanishuv",
        ["Ommaviy sahifa · imkoniyatlar · baholash shkalasi"],
        seconds=3.6,
        voice="Birinchi bosqich — platforma bilan tanishuv.",
    )
    lesson.chip("1 — TANISHUV")
    lesson.goto(f"{SITE}/")
    lesson.say(
        "Platformaning ommaviy sahifasi. Bu yerda testlar soni, topshirilgan "
        "javoblar va berilgan sertifikatlar ko‘rinib turadi.",
        4.4,
        voice="Mana platformaning ommaviy sahifasi. U ro‘yxatdan o‘tmagan "
              "odamga ham ochiq. Yuqorida jonli hisoblagichlar turibdi: "
              "nechta test o‘tkazilgan, nechta javob topshirilgan va nechta "
              "sertifikat berilgan.",
    )
    lesson.say(
        "Maksimal ball — <b>90.14</b>. Bu Milliy sertifikat shkalasidagi eng yuqori "
        "natija; barcha ballar shu shkalaga keltiriladi.",
        4.2,
        voice="Maksimal ball — to‘qson butun o‘n to‘rt. Bu Milliy sertifikat "
              "shkalasidagi eng yuqori natija; platformadagi barcha ballar "
              "aynan shu shkalaga keltiriladi.",
    )
    lesson.scroll(520)
    lesson.say(
        "Platformaning to‘rt asosiy imkoniyati: uch xil test turi, Rasch baholash, "
        "matematik klaviatura va bir martalik ID kodlar.",
        4.6,
        voice="Platformaning to‘rtta asosiy imkoniyati bor: uch xil test "
              "turi, Rash modeli asosida baholash, matematik klaviatura va "
              "bir martalik Ay-Di kodlar. Bularning har birini video "
              "davomida alohida ko‘rsataman.",
    )
    lesson.scroll(560)
    lesson.say(
        "Rasch modelining mohiyati: har bir savolning qiyinligi javoblar "
        "matritsasidan hisoblanadi, o‘quvchining darajasi esa aynan shu qiyinlikni "
        "hisobga olib baholanadi.",
        5.0,
        voice="Rash modelining mohiyati shunda: har bir savolning qiyinligi "
              "javoblar matritsasidan hisoblab chiqiladi, o‘quvchining "
              "darajasi esa aynan shu qiyinlikni hisobga olib baholanadi. "
              "Ya’ni oson savolga javob bergan bilan qiyin savolni yechgan "
              "bir xil ball olmaydi.",
    )
    lesson.scroll(560)
    lesson.say(
        "Baholash shkalasi: 70 balldan yuqori — A+, 46 balldan past bo‘lsa daraja "
        "berilmaydi. Chegaralar texnik topshiriqqa aynan mos.",
        4.6,
        voice="Baholash shkalasi ham shu yerda. Yetmish balldan yuqori "
              "natija A plyus darajasini beradi, qirq oltidan past bo‘lsa "
              "daraja berilmaydi. Chegaralar texnik topshiriqqa aynan mos "
              "qilib qo‘yilgan.",
    )
    lesson.scroll(600)
    lesson.say(
        "Sahifa oxirida bot va sertifikat tekshiruviga havolalar bor.",
        3.2,
        voice="Sahifaning eng pastida botga va sertifikat tekshiruvi "
              "sahifasiga havolalar turibdi.",
    )


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
        voice="Ikkinchi bosqich — Telegram bot. Ekranda ko‘rinadigan har bir "
              "xabar va tugma botning haqiqiy kodidan olingan: bu montaj "
              "emas, botning o‘z javoblari.",
    )

    chat.open()

    # --- 2.1 Ro'yxatdan o'tish -------------------------------------
    chat.who("Rasch Math Bot", "Sardor Aliyev bilan suhbat")
    chat.note(
        [
            "<b>Ro‘yxatdan o‘tish</b>",
            "Bot avval kanalga a’zolikni tekshiradi.",
            "So‘ng ism-familiya va telefon raqami so‘raladi.",
            "Ism kamida ikki so‘zdan iborat bo‘lishi shart — sertifikatda "
            "to‘liq ism chiqishi uchun.",
        ],
        voice="Foydalanuvchi botni ishga tushirganda birinchi bo‘lib "
              "majburiy obuna tekshiriladi: kanalga a’zo bo‘lmagan odam "
              "testga kira olmaydi. Keyin bot ism-familiyani va telefon "
              "raqamini so‘raydi. Ism kamida ikki so‘zdan iborat bo‘lishi "
              "shart, chunki keyinchalik sertifikatda to‘liq ism chiqishi "
              "kerak. Telefon raqami esa bitta tugma bilan yuboriladi.",
    )
    play(chat, tape.slice(0, 16), bot_wait=2.6)
    lesson.beat(1.4)

    # --- 2.2 Test yaratish ------------------------------------------
    chat.clear()
    chat.who("Rasch Math Bot", "Nodira Qodirova bilan suhbat")
    chat.note(
        [
            "<b>Test yaratish sehrgari</b>",
            "O‘qituvchi test turini tanlaydi, nom beradi, savollar sonini "
            "ko‘rsatadi va javob kalitini kiritadi.",
            "Oxirida test kodi beriladi — o‘quvchilar shu kod bilan kiradi.",
        ],
        voice="Endi o‘qituvchi nomidan test yaratamiz. Bot sehrgar "
              "ko‘rinishida ishlaydi: avval test turini tanlaydi — oddiy "
              "test, bepul Rash testi yoki pullik Rash testi. Keyin testga "
              "nom beradi, savollar sonini ko‘rsatadi va javob kalitini "
              "bitta qatorda kiritadi. Tugash vaqtini tayyor variantdan "
              "yoki kalendardan tanlash mumkin. Oxirida bot test kodini "
              "beradi — o‘quvchilar aynan shu kod bilan kiradi.",
    )
    start = tape.find("Yangi test yaratish")
    play(chat, tape.slice(start - 1, start + 15), bot_wait=2.5)
    lesson.beat(1.6)

    # --- 2.3 Testni topshirish --------------------------------------
    chat.clear()
    chat.who("Rasch Math Bot", "Sardor Aliyev bilan suhbat")
    chat.note(
        [
            "<b>Testni topshirish</b>",
            "O‘quvchi kodni kiritadi. Noto‘g‘ri kod kiritilsa, bot ogohlantiradi.",
            "Har bir javob darhol saqlanadi — internet uzilsa ham yo‘qolmaydi.",
            "Savollar orasida erkin yurish mumkin.",
        ],
        voice="Endi yana o‘quvchi tomoniga qaytamiz. U testga kirish uchun "
              "kodni kiritadi. Noto‘g‘ri kod kiritilsa, bot xatoni "
              "tushuntirib aytadi. Test boshlangach har bir javob darhol "
              "bazaga saqlanadi, shuning uchun internet uzilib qolsa ham "
              "javoblar yo‘qolmaydi.",
    )
    start = tape.find("Test kodini kiriting")
    play(chat, tape.slice(start - 1, start + 8), bot_wait=2.4)

    chat.note(
        [
            "<b>Savollarga javob berish</b>",
            "Progress chizig‘i qancha savol bajarilganini ko‘rsatadi.",
            "Tanlangan variant <b>●</b> belgisi bilan belgilanadi.",
            "«Ko‘rib chiqish» — barcha javoblarni bir ekranda tekshirish.",
        ],
        voice="Savollar birin-ketin keladi. Yuqoridagi chiziq qancha savol "
              "bajarilganini ko‘rsatadi, tanlangan variant esa alohida "
              "belgi bilan ajratiladi. Savollar orasida erkin yurish "
              "mumkin, «Ko‘rib chiqish» tugmasi esa barcha javoblarni "
              "bitta ekranda ko‘rsatadi.",
    )
    q = tape.find("1-savol")
    play(chat, tape.slice(q, q + 10), bot_wait=1.35, me_wait=0.7)

    # --- 2.4 Yakunlash va natija ------------------------------------
    chat.note(
        [
            "<b>Yakunlash</b>",
            "Bot avval tasdiq so‘raydi — yuborilgandan keyin javoblarni "
            "o‘zgartirib bo‘lmaydi.",
            "Natija darhol chiqadi: to‘g‘ri javoblar, foiz va tahlil.",
        ],
        voice="Testni yakunlashda bot avval tasdiq so‘raydi, chunki "
              "yuborilgandan keyin javoblarni o‘zgartirib bo‘lmaydi. "
              "Tasdiqlangach natija darhol chiqadi: to‘g‘ri javoblar soni, "
              "foiz va batafsil tahlil.",
    )
    fin = tape.find("Javoblaringiz</b>")
    if fin < 0:
        fin = tape.find("Javob berilgan")
    play(chat, tape.slice(fin, fin + 8), bot_wait=2.8)
    lesson.beat(1.8)

    chat.note(
        [
            "<b>Javoblar tahlili</b>",
            "Har bir savol bo‘yicha: qaysi javob berilgan va qaysi javob to‘g‘ri.",
            "✓ — to‘g‘ri, ✗ — xato.",
        ],
        voice="Javoblar tahlilida har bir savol bo‘yicha qaysi javob "
              "berilgani va qaysi javob to‘g‘ri ekani yonma-yon "
              "ko‘rsatiladi. To‘g‘ri javoblar belgi bilan, xatolari esa "
              "krestcha bilan ajratiladi. Rash testlarida bunga qo‘shimcha "
              "ravishda har bir savolning qiyinlik darajasi ham qo‘shiladi.",
    )
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
        voice="Uchinchi bosqich — web ilova. Bu Telegram Mini App: u "
              "botning menyu tugmasidan yoki asosiy menyudagi «Ilovani "
              "ochish» tugmasidan ochiladi va Telegramning ichida ishlaydi.",
    )
    lesson.chip("3 — WEB ILOVA")
    lesson.goto(APP_URL, wait=2.6)

    lesson.side(
        "WEB ILOVA",
        [
            "Ilova botning menyu tugmasidan ochiladi.",
            "Kirish <b>Telegram initData</b> imzosi bilan tekshiriladi — "
            "alohida parol kerak emas.",
            "Yuqorida profil va uchta hisoblagich: natijalar, sertifikatlar, "
            "o‘z testlari.",
        ],
        voice="Ilovaga kirish uchun alohida login va parol kerak emas: har "
              "bir so‘rov Telegramning init-data imzosi bilan tekshiriladi. "
              "Ya’ni foydalanuvchi kim ekanini Telegramning o‘zi "
              "tasdiqlaydi. Yuqorida profil va uchta hisoblagich turibdi: "
              "natijalar, sertifikatlar va o‘zi yaratgan testlar soni.",
    )

    lesson.side(
        "TEZ AMALLAR",
        [
            "To‘rtta asosiy amal bir bosishda:",
            "<b>Testda qatnashish</b> — kod orqali testga kirish.",
            "<b>Test yaratish</b> — o‘z testingizni ochish.",
            "<b>Natijalarim</b> — ball, daraja, javoblar tahlili.",
            "<b>Sertifikatlar</b> — PDF yuklab olish.",
        ],
        voice="Pastda tez amallar bo‘limi bor. To‘rtta asosiy ish bir "
              "bosishda bajariladi: testda qatnashish, o‘z testingni "
              "yaratish, natijalarni ko‘rish va sertifikatni yuklab olish. "
              "Agar tugallanmagan test qolgan bo‘lsa, u ham shu yerda "
              "alohida kartochka bo‘lib chiqadi.",
    )
    lesson.beat(1.2)

    # --- Testlar bo'limi --------------------------------------------
    lesson.click(tab(lesson, "exams"), after=2.2)
    lesson.side(
        "TESTLAR",
        [
            "Testga <b>faqat kod orqali</b> kiriladi.",
            "Testlar ro‘yxati ishtirokchilarga ko‘rsatilmaydi — uni faqat "
            "adminlar ko‘radi.",
            "Kod — oddiy ikki yoki uch xonali son, u testdan keyin bo‘shab, "
            "qayta ishlatiladi.",
        ],
        voice="«Testlar» bo‘limi. Bu yerda faqat kod maydoni bor: testga "
              "faqat tashkilotchi bergan kod orqali kiriladi, ro‘yxat esa "
              "ishtirokchilarga umuman ko‘rsatilmaydi — uni faqat adminlar "
              "ko‘radi. Kod oddiy ikki yoki uch xonali son bo‘lgani uchun "
              "uni sinfga aytish oson. Test yakunlangach kod bo‘shaydi va "
              "keyingi testga qayta beriladi.",
    )
    lesson.beat(1.0)


def open_exam(lesson: Lesson, code: str) -> bool:
    """Testga kiradi.

    Ishtirokchiga testlar ro'yxati ko'rsatilmaydi — testga faqat
    tashkilotchi bergan kod orqali kiriladi. Shuning uchun avval kod
    maydoni, so'ng (admin ko'rinishida) ro'yxatdagi kartochka sinaladi.
    """
    page = lesson.page
    field = page.locator("#exam-code").first
    if field.count():
        lesson.type_into(field, str(code), delay=180, after=0.7)
        if lesson.click(page.locator('[data-act="find-exam"]').first, after=2.4):
            if page.locator('[data-act="start-exam"]').first.count():
                return True

    card = page.locator(f'[data-act="open-exam"][data-code="{code}"]').first
    if card.count() == 0:
        warn(f"{code} kodli test ochilmadi")
        return False
    return lesson.click(card, after=2.2)


def sheet_orders(page) -> list[int]:
    """Javoblar varaqasidagi savol tartiblari."""
    try:
        return page.eval_on_selector_all(
            ".qitem", "els => els.map(e => parseInt(e.dataset.order, 10))"
        ) or []
    except Exception:
        return []


def answer(lesson: Lesson, order: int, letter: str, *,
           after: float = 0.6, settle: float = 0.32) -> bool:
    """Varaqadagi bitta savolga javob belgilaydi."""
    choice = lesson.page.locator(
        f'.choice[data-order="{order}"][data-letter="{letter}"]'
    ).first
    if choice.count() == 0:
        warn(f"{order}-savolda «{letter}» varianti topilmadi")
        return False
    return lesson.click(choice, after=after, settle=settle)


def jump_to(lesson: Lesson, order: int, *, after: float = 1.6) -> bool:
    """Palitradan kerakli savolga o'tadi."""
    button = lesson.page.locator(f'.palette button[data-order="{order}"]').first
    if button.count() == 0:
        warn(f"palitrada {order}-savol topilmadi")
        return False
    return lesson.click(button, after=after)


def scene_taking(lesson: Lesson, facts: dict) -> None:
    """Oddiy testni web ilovada haqiqatan topshirish."""
    page = lesson.page
    simple = facts.get("open_exam")
    if simple is None:
        warn("faol oddiy test yo'q — «Testni topshirish» sahnasi tashlab ketildi")
        return

    lesson.side(
        "TESTGA KIRISH",
        [
            "Testlar ro‘yxati ishtirokchiga ko‘rsatilmaydi.",
            "Testga faqat tashkilotchi bergan <b>kod</b> orqali kiriladi.",
            "Kod — oddiy ikki yoki uch xonali son.",
        ],
        voice="Endi testni o‘zimiz topshirib ko‘ramiz. Ishtirokchiga testlar "
              "ro‘yxati ko‘rsatilmaydi: testga faqat tashkilotchi bergan kod "
              "orqali kiriladi. Kod — oddiy ikki yoki uch xonali son, uni "
              "eslab qolish oson.",
    )

    if not open_exam(lesson, simple.code):
        lesson.goto(APP_URL, wait=1.6)
        lesson.click(tab(lesson, "exams"), after=1.6)
        if not open_exam(lesson, simple.code):
            return

    lesson.side(
        "TEST HAQIDA",
        [
            "Boshlashdan oldin: test turi, savollar soni, maksimal ball "
            "va tugash vaqti ko‘rsatiladi.",
            "Pullik testda aynan shu bosqichda <b>ID kod</b> so‘raladi.",
        ],
        voice="Kod to‘g‘ri bo‘lsa, test haqidagi ma’lumot chiqadi: test turi, "
              "savollar soni, maksimal ball va tugash vaqti. Agar bu pullik "
              "test bo‘lsa, aynan shu bosqichda bir martalik Ay-Di kod "
              "so‘raladi.",
    )
    lesson.beat(2.4)

    if not lesson.click(page.locator('[data-act="start-exam"]').first, after=2.6):
        warn("«Boshlash» tugmasi bosilmadi")
        return

    lesson.side(
        "JAVOBLAR VARAQASI",
        [
            "Barcha savollar <b>bitta varaqada</b> — imtihon blankasi kabi.",
            "Yuqorida savollar palitrasi va bajarilish chizig‘i.",
            "Javob tanlanishi bilan darhol serverga saqlanadi.",
        ],
        voice="Mana javoblar varaqasi. Barcha savollar bitta ekranda "
              "joylashgan, xuddi imtihon blankasidek. Eng yuqorida savollar "
              "palitrasi va bajarilish chizig‘i turibdi. Har bir javob "
              "tanlangan zahoti serverga saqlanadi.",
    )

    keys = facts.get("open_keys") or {}
    orders = sheet_orders(page) or sorted(keys)
    wrong_at = {3, 7}          # tahlil bo'sh ko'rinmasligi uchun ataylab xato

    for i, order in enumerate(orders):
        correct = (keys.get(order) or "A")[:1]
        letter = correct if order not in wrong_at else ("A" if correct != "A" else "C")
        fast = i >= 2
        answer(
            lesson, order, letter,
            after=0.55 if fast else 1.3,
            settle=0.3 if fast else 0.6,
        )

        if i == 1:
            lesson.side(
                "JAVOB DARHOL SAQLANADI",
                [
                    "Har bosishdan keyin javob serverga yuboriladi.",
                    "Ilova yopilib qolsa ham javoblar joyida qoladi.",
                    "Bitta javobli savolda tanlov <b>radio</b> kabi ishlaydi: "
                    "ikkinchi variant bosilsa, birinchisi o‘chadi.",
                ],
                voice="E’tibor bering: har bir bosishdan keyin javob darhol "
                      "serverga yuboriladi. Internet uzilib qolsa yoki ilova "
                      "yopilsa ham, javoblar joyida qoladi. Bitta javobli "
                      "savolda tanlov radio tugma kabi ishlaydi: ikkinchi "
                      "variantni bossangiz, birinchisi o‘chadi.",
            )

        if i == 4:
            lesson.side(
                "PALITRA",
                [
                    "Yuqoridagi raqamlar — savollar palitrasi.",
                    "Javob berilgan savol rangi bilan ajralib turadi.",
                    "Istalgan savolga qaytib, javobni o‘zgartirish mumkin.",
                ],
                voice="Yuqoridagi raqamlar — savollar palitrasi. Javob "
                      "berilgan savollar rangi bilan ajralib turadi, shuning "
                      "uchun qaysi savol bo‘sh qolgani bir qarashda "
                      "ko‘rinadi. Istalgan savolga qaytib, javobni "
                      "o‘zgartirish mumkin.",
            )

    # Palitra orqali orqaga qaytish — javobni o'zgartirish mumkinligi
    if orders:
        jump_to(lesson, orders[0], after=1.5)
        lesson.beat(1.2)

    lesson.side(
        "YAKUNLASH",
        [
            "Yuborishdan oldin ilova tasdiq so‘raydi.",
            "Javobsiz savollar qolsa — ularning raqamlari aytiladi.",
            "Yuborilgandan keyin javoblarni o‘zgartirib bo‘lmaydi.",
        ],
        voice="Testni yakunlaymiz. Yuborishdan oldin ilova tasdiq so‘raydi; "
              "agar javobsiz savollar qolgan bo‘lsa, ularning raqamlarini "
              "aytadi. Yuborilgandan keyin javoblarni o‘zgartirib bo‘lmaydi.",
    )
    lesson.click(page.locator('[data-act="finish"]').first, after=1.6)
    lesson.click(page.locator("#modal-ok").first, after=3.2)


def scene_mathpad(lesson: Lesson, facts: dict) -> None:
    """Ochiq savollar va matematik klaviatura."""
    page = lesson.page
    national = facts.get("live_national")
    if national is None:
        warn("faol milliy shablon testi yo'q — klaviatura sahnasi tashlab ketildi")
        return

    lesson.title_card(
        "3-bosqich · davomi",
        "Ochiq savollar va matematik klaviatura",
        [
            "45 savolli milliy sertifikat shabloni",
            "36–45-savollarda variant yo‘q — javob yoziladi",
        ],
        seconds=4.2,
        voice="Endi eng qiziq qismiga o‘tamiz — Milliy sertifikat shabloni. "
              "Bu qirq besh savolli test bo‘lib, uning oxirgi o‘nta savolida "
              "variantlar umuman yo‘q: javobni o‘zingiz yozasiz.",
    )
    lesson.chip("3 — WEB ILOVA")

    lesson.goto(APP_URL, wait=2.0)
    lesson.click(tab(lesson, "exams"), after=1.8)

    lesson.side(
        "MILLIY SHABLON",
        [
            "45 ta savol: <b>1–32</b> — A/B/C/D, <b>33–35</b> — A–F "
            "(moslashtirish, bitta to‘g‘ri javob), <b>36–45</b> — ochiq javob.",
            "Ochiq savollar Rasch matritsasida <b>ikkita birlik</b> sifatida "
            "hisoblanadi: a) va b) qismlari.",
        ],
        voice="Shablon quyidagicha: birinchidan o‘ttiz ikkinchi savolgacha "
              "A, B, C, D variantlari; o‘ttiz uchdan o‘ttiz beshinchisigacha "
              "moslashtirish savollari — A dan F gacha oltita variant, "
              "ulardan bittasi to‘g‘ri; "
              "o‘ttiz oltidan qirq beshinchisigacha esa ochiq savollar. "
              "Ochiq savollar Rash matritsasida ikkita alohida birlik "
              "sifatida hisoblanadi: a va b qismlari.",
    )

    if not open_exam(lesson, national.code):
        return
    if not lesson.click(page.locator('[data-act="start-exam"]').first, after=2.6):
        warn("milliy test boshlanmadi")
        return

    keys = facts.get("national_keys") or {}

    # --- Ko'p javobli savol (33) ------------------------------------
    if jump_to(lesson, 33, after=1.8):
        lesson.side(
            "MOSLASHTIRISH SAVOLI",
            [
                "33–35-savollarda <b>A dan F gacha</b> oltita variant bor.",
                "Ulardan faqat <b>bittasi</b> to‘g‘ri — tanlov «radio» kabi "
                "ishlaydi: ikkinchi variant bosilsa, birinchisi o‘chadi.",
            ],
            voice="Mana o‘ttiz uchinchi savol. Bu yerda A dan F gacha oltita "
                  "variant bor, lekin ulardan faqat bittasi to‘g‘ri. Tanlov "
                  "radio tugma kabi ishlaydi: ikkinchi variantni bossangiz, "
                  "birinchisi avtomatik o‘chadi.",
        )
        answer(lesson, 33, (keys.get(33) or "A")[:1] or "A", after=0.9, settle=0.4)

    # --- Ochiq savol (36) -------------------------------------------
    if not jump_to(lesson, 36, after=2.0):
        return

    lesson.side(
        "MATEMATIK KLAVIATURA",
        [
            "Variantlar o‘rniga — <b>a)</b> va <b>b)</b> javob maydonlari.",
            "Maydon bosilsa, pastdan maxsus klaviatura ochiladi: kasr, "
            "ildiz, daraja, π, e, sin, cos, tg, ctg, ln, log, |x|.",
            "Telefonning oddiy klaviaturasi ochilmaydi.",
        ],
        voice="O‘ttiz oltinchi savol — ochiq savol. Variantlar o‘rniga a va b "
              "javob maydonlari turibdi. Maydonni bossak, pastdan maxsus "
              "matematik klaviatura ochiladi: kasr, ildiz, daraja, pi, "
              "sinus, kosinus, logarifm va modul belgilarigacha. Telefonning "
              "oddiy klaviaturasi umuman ochilmaydi.",
    )

    field = page.locator("#ans-36-a").first
    if field.count():
        lesson.click(field, after=0.9, settle=0.4)
    else:
        warn("36-savolning «a» maydoni topilmadi")

    for ins in ("1", "/", "2"):
        key = page.locator(f'.mpad-key[data-ins="{ins}"]').first
        if key.count():
            lesson.click(key, after=0.8, settle=0.35)
        else:
            warn(f"klaviaturada «{ins}» tugmasi topilmadi")

    lesson.side(
        "JONLI TEKSHIRUV",
        [
            "Yozilgan ifoda darhol serverda <b>SymPy</b> bilan tekshiriladi.",
            "Tekshiruv matematik ekvivalentlik bo‘yicha: "
            "<b>1/2 = 0.5 = 2⁻¹</b>, <b>sin(π/6) = 0.5</b>.",
            "Ya’ni javobning yozilish shakli emas, <b>qiymati</b> muhim.",
        ],
        voice="Yozilgan ifoda darhol serverga yuboriladi va SimPay "
              "kutubxonasi yordamida tekshiriladi. Tekshiruv matematik "
              "ekvivalentlik bo‘yicha ketadi: bir bo‘lingan ikki, nol butun "
              "besh va ikkining minus birinchi darajasi — bularning hammasi "
              "bitta javob hisoblanadi. Ya’ni javobning yozilish shakli "
              "emas, uning qiymati muhim.",
    )
    lesson.beat(2.0)

    lesson.scroll(360, after=1.0)
    lesson.beat(1.6)

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
            voice="Testdan chiqib ketsak ham javoblar saqlanib qoladi. Bosh "
                  "sahifada tugallanmagan test kartochkasi paydo bo‘ladi va "
                  "bir bosishda o‘sha joydan davom ettirish mumkin.",
        )
        lesson.beat(3.0)


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
        voice="Mana natija ekrani. Oddiy testda to‘g‘ri javoblar soni va "
              "foiz ko‘rsatiladi. Rash testida esa bundan ko‘proq: teta — "
              "ya’ni qobiliyat bahosi, to‘qson butun o‘n to‘rtlik shkaladagi "
              "standart ball, daraja va reyting. Quyida har bir savol "
              "bo‘yicha to‘g‘ri va xato javoblar tahlili turibdi.",
    )
    lesson.scroll(420, after=1.2)
    lesson.beat(1.6)
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
        voice="«Natijalarim» bo‘limida foydalanuvchining barcha urinishlari "
              "bitta ro‘yxatda turadi. Rash testlarida ball to‘qson butun "
              "o‘n to‘rtlik shkalada, yonida esa olingan daraja "
              "ko‘rsatiladi. Istalgan kartochkani bossak, javoblar "
              "tahliliga o‘tamiz.",
    )

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
            voice="Tahlilda har bir savol uchun berilgan javob va to‘g‘ri "
                  "javob yonma-yon turadi. Rash testida bunga savolning "
                  "qiyinlik ko‘rsatkichi ham qo‘shiladi. Shu yerdan "
                  "reytingga o‘tish yoki sertifikatni olish mumkin.",
        )
        lesson.scroll(420, after=1.0)
        lesson.beat(1.8)


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
        voice="Sertifikatlar bo‘limi. Sertifikat faqat pullik Rash testi "
              "uchun beriladi va natijalar e’lon qilingandan keyin "
              "avtomatik yaratiladi. Bitta tugma bilan Pe-De-Ef yuklab "
              "olinadi. Hujjat ichida noyob raqam va Kyu-Ar kod bor: uni "
              "skanerlab, sertifikatning haqiqiyligini istalgan odam "
              "tekshira oladi.",
    )

    lesson.click(tab(lesson, "my-exams"), after=2.4)
    lesson.side(
        "TESTLARIM",
        [
            "O‘zi yaratgan testlarni boshqarish: faollashtirish, yopish, "
            "hisoblash, e’lon qilish.",
            "Shu yerdan test nusxalanadi yoki o‘chiriladi.",
            "Test kodi va ID kodlar ham shu bo‘limda.",
        ],
        voice="«Testlarim» bo‘limida foydalanuvchi o‘zi yaratgan testlarni "
              "boshqaradi: testni faollashtiradi, yopadi, natijalarni "
              "hisoblaydi va e’lon qiladi. Shu yerdan testning to‘liq "
              "nusxasini olish yoki uni butunlay o‘chirish mumkin. "
              "O‘chirishdan oldin ilova nima yo‘qolishini oldindan "
              "ko‘rsatadi va tasdiq so‘raydi.",
    )
    lesson.beat(1.0)
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
        voice="To‘rtinchi bosqich — boshqaruv paneli. Bu platforma egasining "
              "asosiy ish joyi: testlar, savollar, ishtirokchilar, Ay-Di "
              "kodlar, Rash hisobi va hisobotlar — hammasi shu yerda.",
    )
    lesson.chip("4 — PANEL")

    lesson.goto(f"{SITE}/panel/kirish/", wait=1.6)
    lesson.say(
        "Panelga kirish. Django ning standart admin paneli ishlatilmaydi — "
        "barcha boshqaruv shu yerda, o‘z dizaynida.",
        4.0,
        voice="Panelga ikki xil kirish mumkin: login va parol bilan yoki "
              "to‘g‘ridan-to‘g‘ri botdagi «Web panel» tugmasi orqali. "
              "E’tibor bering: Django ning standart admin paneli butunlay "
              "olib tashlangan — barcha boshqaruv shu yerda, o‘zbek tilida "
              "va bitta dizaynda.",
    )

    lesson.type_into(page.locator("input[name='username']"), PANEL_USER)
    lesson.type_into(page.locator("input[name='password']"), PANEL_PASSWORD, delay=45)
    lesson.click(page.locator("button[type='submit'], input[type='submit']").first, after=2.6)

    lesson.say(
        "Umumiy ko‘rsatkichlar: foydalanuvchilar, testlar, urinishlar va "
        "sertifikatlar soni bir ekranda.",
        4.2,
        voice="Kirdik. Bosh sahifada umumiy ko‘rsatkichlar: foydalanuvchilar "
              "soni, testlar, urinishlar va berilgan sertifikatlar — "
              "hammasi bitta ekranda ko‘rinadi.",
    )
    lesson.scroll(460)
    lesson.beat(1.8)

    # --- Testlar ro'yxati -------------------------------------------
    lesson.goto(f"{SITE}/panel/testlar/", wait=1.8)
    lesson.say(
        "Testlar ro‘yxati. Har bir test uchun turi, holati, savollar soni "
        "va ishtirokchilar ko‘rinadi.",
        4.2,
        voice="Testlar ro‘yxati. Har bir test uchun uning turi, holati, "
              "savollar soni va nechta ishtirokchi topshirgani ko‘rinib "
              "turibdi.",
    )
    lesson.say(
        "Holatlar zanjiri: <b>Qoralama → Faol → Yopilgan → Hisoblangan → "
        "E’lon qilingan</b>.",
        4.0,
        voice="Testning hayotiy sikli beshta holatdan iborat: qoralama, "
              "faol, yopilgan, hisoblangan va e’lon qilingan. Test yopilgach "
              "admin «Hisoblash» tugmasini bosadi — aynan shu paytda Rash "
              "kalibrlashi ishga tushadi. Natijalar e’lon qilinganda esa "
              "sertifikatlar avtomatik yaratiladi.",
    )

    lesson.goto(f"{SITE}/panel/testlar/yangi/", wait=1.8)
    lesson.say(
        "Test yaratish paneldan ham mumkin — tur, tuzilma, kalitlar va "
        "sozlamalar bitta sahifada.",
        4.4,
        voice="Test yaratish uch joyda mavjud: botdagi sehrgarda, web "
              "ilovada va shu panelda. Uchalasi ham bitta xizmat qatlamidan "
              "foydalanadi, ya’ni natija bir xil bo‘ladi. Panelda esa "
              "hammasi bitta sahifada: test turi, tuzilmasi, javob "
              "kalitlari va sozlamalar.",
    )
    lesson.scroll(420)
    lesson.beat(1.6)

    exam = facts.get("rasch_exam")
    if exam is not None:
        lesson.goto(f"{SITE}/panel/testlar/{exam.pk}/", wait=1.8)
        lesson.say(
            "Test tafsiloti. Bu — 45 savolli milliy sertifikat shabloni: "
            "1–32 bitta javobli, 33–35 ko‘p javobli, 36–45 ochiq savollar.",
            5.0,
            voice="Mana test tafsiloti. Bu qirq besh savolli milliy "
                  "sertifikat shabloni: birinchidan o‘ttiz ikkinchi "
                  "savolgacha bitta javobli, o‘ttiz uchdan o‘ttiz "
                  "beshinchisigacha ko‘p javobli, qolgan o‘ntasi esa ochiq "
                  "savollar.",
        )
        lesson.scroll(440)
        lesson.beat(1.6)

        lesson.goto(f"{SITE}/panel/testlar/{exam.pk}/savollar/", wait=1.8)
        lesson.say(
            "Savollarni to‘liq tahrirlash: matn, turi, variantlar, kalit va "
            "Rasch qiyinligi.",
            4.4,
            voice="Savollar sahifasida har bir savolni to‘liq tahrirlash "
                  "mumkin: savol matni, turi, variantlari, to‘g‘ri javob "
                  "kaliti, ochiq javoblar va Rash qiyinligi. Agar savolning "
                  "qiyinligi oldindan ma’lum bo‘lsa, uni qo‘lda kiritib, "
                  "«qulflab» qo‘yish ham mumkin — u holda kalibrlash bu "
                  "qiymatga tegmaydi.",
        )
        lesson.scroll(420)
        lesson.beat(1.6)

        lesson.goto(f"{SITE}/panel/testlar/{exam.pk}/natijalar/", wait=2.0)
        lesson.say(
            "Natijalar jadvali. Bu yerda Rasch hisobining mevasi ko‘rinadi: "
            "θ qiymati, standart ball va daraja.",
            4.6,
            voice="Natijalar jadvali — bu yerda Rash hisobining natijasi "
                  "ko‘rinadi: har bir ishtirokchi uchun teta qiymati, "
                  "standart ball, foiz va daraja.",
        )
        lesson.scroll(420)
        lesson.say(
            "Ishonchlilik ko‘rsatkichlari — <b>KR-20</b> va ishtirokchilarni "
            "ajratish koeffitsiyenti — testning sifatini baholaydi.",
            4.4,
            voice="Quyida ishonchlilik ko‘rsatkichlari: Ka-Er yigirma va "
                  "ishtirokchilarni ajratish koeffitsiyenti. Ular testning "
                  "o‘zi qanchalik sifatli tuzilganini baholaydi.",
        )
        lesson.scroll(420)
        lesson.say(
            "Savollar qiyinchiligi diagrammasi — ustun balandligi xato javob "
            "bergan ishtirokchilar ulushi. Bu diagramma faqat adminga ko‘rinadi.",
            4.8,
            voice="Mana savollar qiyinchiligi diagrammasi. Har bir ustun "
                  "balandligi — o‘sha savolga xato javob bergan "
                  "ishtirokchilar ulushi. Yashil — oson, sariq — o‘rtacha, "
                  "to‘q sariq — qiyin, qizil esa juda qiyin savol degani. "
                  "Yonida ballar taqsimoti turibdi. Bu diagramma "
                  "ishtirokchilarga ko‘rinmaydi — u faqat admin uchun.",
        )
        lesson.scroll(400)
        lesson.beat(1.6)

    paid = facts.get("paid_exam")
    if paid is not None:
        lesson.goto(f"{SITE}/panel/testlar/{paid.pk}/kodlar/", wait=2.0)
        lesson.say(
            "Pullik test uchun bir martalik ID kodlar. Kod uch holatda bo‘ladi: "
            "<b>Ishlatilmagan → Faollashtirilgan → Ishlatilgan</b>.",
            4.8,
            voice="Pullik test uchun bir martalik Ay-Di kodlar. Kod uchta "
                  "holatda bo‘ladi: ishlatilmagan, faollashtirilgan va "
                  "ishlatilgan. Yaratilgan kodlar adminga Excel fayl "
                  "ko‘rinishida beriladi.",
        )
        lesson.say(
            "Kod faqat javoblar yakuniy yuborilgandan keyin «ishlatilgan» "
            "holatiga o‘tadi — test yarim yo‘lda uzilsa, kod yonib ketmaydi.",
            4.8,
            voice="Muhim detal: kod foydalanuvchi uni kiritgan zahoti "
                  "yopilmaydi. U faqat yakuniy javob bazaga muvaffaqiyatli "
                  "saqlangandan keyin «ishlatilgan» holatiga o‘tadi. Shu "
                  "sababli internet uzilishi kodni kuydirmaydi.",
        )
        lesson.scroll(400)
        lesson.beat(1.4)

    lesson.goto(f"{SITE}/panel/urinishlar/", wait=1.8)
    lesson.say(
        "Barcha urinishlar bitta ro‘yxatda — kim, qaysi testni, qachon "
        "topshirgani va qanday natija olgani.",
        4.4,
        voice="Urinishlar bo‘limida barcha topshiriqlar bitta ro‘yxatda: "
              "kim, qaysi testni, qachon topshirgani va qanday natija "
              "olgani ko‘rinadi.",
    )
    lesson.scroll(380)
    lesson.beat(1.4)

    attempt_id = facts.get("attempt_id")
    if attempt_id:
        lesson.goto(f"{SITE}/panel/urinish/{attempt_id}/", wait=1.8)
        lesson.say(
            "Urinish tafsiloti: har bir javob, qayta baholash, bekor qilish "
            "va sertifikat berish.",
            4.4,
            voice="Bitta urinishni ochsak, uning har bir javobi ko‘rinadi. "
                  "Admin bu yerdan urinishni qayta baholashi, bekor qilishi, "
                  "o‘chirishi yoki qo‘lda sertifikat berishi mumkin.",
        )
        lesson.scroll(420)
        lesson.beat(1.4)

    lesson.goto(f"{SITE}/panel/sertifikatlar/", wait=1.8)
    lesson.say(
        "Berilgan sertifikatlar. Har birining raqami, egasi va berilgan sanasi "
        "bor; kerak bo‘lsa bekor qilish mumkin.",
        4.4,
        voice="Sertifikatlar bo‘limi. Har bir sertifikatning noyob raqami, "
              "egasi va berilgan sanasi bor. Kerak bo‘lsa Pe-De-Ef ni qayta "
              "yaratish, sertifikatni bekor qilish yoki tiklash mumkin.",
    )
    lesson.beat(1.4)

    lesson.goto(f"{SITE}/panel/foydalanuvchilar/", wait=1.8)
    lesson.say(
        "Foydalanuvchilar: rollar, telefon raqamlari va bloklash imkoniyati.",
        3.8,
        voice="Foydalanuvchilar bo‘limi: rollar, telefon raqamlari, "
              "foydalanuvchini bloklash yoki unga admin huquqini berish. "
              "Har bir odamning natijalari va o‘zi yaratgan testlari ham shu "
              "yerdan ko‘rinadi.",
    )
    lesson.beat(1.2)

    lesson.goto(f"{SITE}/panel/tarix/", wait=1.8)
    lesson.say(
        "Amallar tarixi — har bir muhim o‘zgarish yozib boriladi: kim, "
        "qachon, nimani o‘zgartirgan.",
        4.2,
        voice="Va nihoyat amallar tarixi — audit jurnali. Har bir muhim "
              "o‘zgarish shu yerga yozib boriladi: kim, qachon va nimani "
              "o‘zgartirgan. Jurnalni filtrlar bilan saralash mumkin.",
    )
    lesson.beat(1.4)


def scene_verify(lesson: Lesson, facts: dict) -> None:
    page = lesson.page
    lesson.title_card(
        "5-bosqich",
        "Sertifikatni tekshirish",
        ["QR kod yoki sertifikat raqami orqali — hamma uchun ochiq"],
        seconds=3.8,
        voice="Beshinchi bosqich — sertifikatni tekshirish.",
    )
    lesson.chip("5 — SERTIFIKAT")

    lesson.goto(f"{SITE}/verify/", wait=1.8)
    lesson.say(
        "Sertifikatni tekshirish sahifasi ochiq — bu yerga kirish uchun "
        "ro‘yxatdan o‘tish shart emas.",
        4.0,
        voice="Tekshirish sahifasi hamma uchun ochiq: bu yerga kirish uchun "
              "ro‘yxatdan o‘tish ham, Telegram ham kerak emas. Sertifikat "
              "raqamini kiritamiz.",
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
            voice="Sertifikat haqiqiy ekan: egasining ismi, test nomi, ball, "
                  "daraja va berilgan sana ko‘rinib turibdi. Agar sertifikat "
                  "bekor qilingan bo‘lsa yoki bunday raqam umuman bo‘lmasa, "
                  "sahifa buni aniq aytadi.",
        )
        lesson.scroll(360)
        lesson.say(
            "Ish beruvchi yoki oliy o‘quv yurti aynan shu sahifa orqali "
            "sertifikatning haqiqiyligiga ishonch hosil qiladi.",
            4.4,
            voice="Demak ish beruvchi yoki oliy o‘quv yurti aynan shu sahifa "
                  "orqali, Pe-De-Ef dagi Kyu-Ar kodni skanerlab, "
                  "sertifikatning haqiqiyligiga ishonch hosil qiladi.",
        )
        lesson.beat(1.4)


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
        voice="Xulosa qilamiz. Biz botda ro‘yxatdan o‘tdik, test yaratdik va "
              "testni topshirdik. Web ilovada javoblar varaqasini, matematik "
              "klaviaturani va natijalar tahlilini ko‘rdik. Boshqaruv "
              "panelida Rash hisobini, savollar qiyinchiligi diagrammasini, "
              "Ay-Di kodlarni va hisobotlarni ko‘rib chiqdik. Oxirida "
              "sertifikatni ochiq sahifada tekshirdik.",
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
        voice="Agar platformani o‘zingizda sinab ko‘rmoqchi bo‘lsangiz: "
              "ishga tushirish skripti butun tizimni bitta buyruqda "
              "ko‘taradi, to‘xtatish skripti esa hammasini to‘xtatadi. "
              "Namoyish ma’lumotlarini demo data skripti yaratadi. "
              "O‘rnatish, arxitektura va texnik topshiriqqa moslik "
              "hujjatlari hujjatlar papkasida turibdi.",
    )
    lesson.title_card(
        "",
        "Dars tugadi",
        ["Rasch Math Platform · matematik testlarni adolatli baholash"],
        seconds=4.5,
        voice="Dars shu yerda yakunlandi. E’tiboringiz uchun rahmat!",
    )


# ==========================================================================
#  Ishga tushirish
# ==========================================================================


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
    narrator = Narrator(enabled=VOICE_ON)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb"])
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=str(RAW_DIR),
            record_video_size={"width": WIDTH, "height": HEIGHT},
            extra_http_headers={"X-Debug-User": str(VIDEO_USER_ID)},
            device_scale_factor=1,
        )
        # Telegram ning haqiqiy skripti brauzerda kerak emas: u sahifa
        # yuklanishini sekinlashtiradi va o'rnatilgan taqlidni almashtirib
        # yuboradi. Shuning uchun so'rov joyida bo'sh javob bilan yopiladi.
        context.route(
            "**://telegram.org/**",
            lambda route: route.fulfill(
                status=200, content_type="application/javascript",
                body="/* video dars uchun o'chirilgan */",
            ),
        )
        context.add_init_script(TELEGRAM_STUB)
        page = context.new_page()
        page.set_default_timeout(15000)

        lesson = Lesson(page, narrator)
        chat = Chat(page, lesson)
        wall_started = time.time()

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
            # Oxirgi gap tugab ulgursin — video ovozdan qisqa bo'lmasin.
            try:
                tail = narrator.free_at - lesson.now()
                if tail > 0:
                    hold(page, min(tail + 0.6, 30.0))
            except Exception:
                pass
            wall_seconds = time.time() - wall_started
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

    # --- Ovoz yo'lagi -----------------------------------------------
    video_seconds = video_voice.media_duration(target) or wall_seconds
    scale = (video_seconds / wall_seconds) if wall_seconds > 0 else 1.0
    if not 0.9 <= scale <= 1.1:      # kutilmagan farq — vaqtni buzmaymiz
        warn(f"video va soat farqi katta (x{scale:.3f}) — ovoz 1:1 qo'yiladi")
        scale = 1.0

    track = None
    if narrator.clips:
        track = video_voice.build_track(
            narrator.clips, video_seconds, OUT_DIR / "dars_ovoz.wav", scale=scale
        )
        srt = video_voice.write_srt(narrator.clips, OUT_DIR / "dars.srt", scale=scale)
        print(f"Ovoz   : {len(narrator.clips)} ta gap, subtitr: {srt}")

    mp4 = video_voice.mux(target, track, target.with_suffix(".mp4"))
    if mp4:
        print(f"MP4    : {mp4}  ({mp4.stat().st_size / 1024 / 1024:.1f} MB)")

    write_chapters(lesson.chapters, scale=scale)
    return 0


def write_chapters(chapters: list[tuple[float, str]], *, scale: float = 1.0) -> None:
    """Bob taymkodlarini faylga yozadi va ekranga chiqaradi."""
    if not chapters:
        return

    lines = []
    for seconds, name in chapters:
        seconds *= scale
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
