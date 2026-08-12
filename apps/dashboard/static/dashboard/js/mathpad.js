/* ==========================================================================
   Boshqaruv paneli — matematik klaviatura.

   Javob kalitlari kiritiladigan maydonlarga (`data-mathpad` belgisi bor)
   bosilganda ekran pastidan Mini App dagi bilan bir xil klaviatura chiqadi:
   ikkita sahifa («123» va «f(x)») hamda doimiy x / y / π / e / daraja paneli.

   Rejimlar (`data-mathpad` qiymati):
     * `lines` — ko'p qatorli maydon (har bir qator — bitta savol);
                 «⏎» yangi qator qo'shadi, «a ; b» ajratkichi bor;
     * `pair`  — bitta maydonda `a ; b` (savollar jadvalidagi kalit);
     * `one`   — bitta ifoda (a) yoki b) javobi).

   Jismoniy klaviatura ham ishlaydi — bu panel unga qo'shimcha.
   ========================================================================== */

(function () {
  "use strict";

  var VALIDATE_URL = "/app/api/tekshir/";

  /* [belgi, kiritiladigan matn, kursor siljishi] */
  var STRIP = [
    ["x", "x", 0], ["y", "y", 0], ["π", "pi", 0], ["e", "e", 0], ["□°", "°", 0]
  ];

  var FUNCTIONS = [
    ["□⁄□", "/", 0], ["□²", "^2", 0], ["□^□", "^", 0], ["sin(□)", "sin()", -1],
    ["√□", "sqrt()", -1], ["ⁿ√□", "root(,3)", -3], ["cos(□)", "cos()", -1], ["tg(□)", "tg()", -1],
    ["log□(□)", "log(,10)", -4], ["ln(□)", "ln()", -1], ["ctg(□)", "ctg()", -1], ["|□|", "abs()", -1],
    ["sin⁻¹(□)", "arcsin()", -1], ["cos⁻¹(□)", "arccos()", -1],
    ["tg⁻¹(□)", "arctg()", -1], ["□!", "!", 0]
  ];

  var pad = null;      // klaviatura elementi
  var field = null;    // faol maydon
  var mode = "one";
  var checkTimer = null;

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function key(label, insert, caret, cls) {
    return '<button type="button" class="mp-key' + (cls ? " " + cls : "") +
      '" data-mp="ins" data-ins="' + esc(insert) + '" data-caret="' + (caret || 0) + '">' +
      esc(label) + "</button>";
  }

  function action(label, name, cls, extra) {
    return '<button type="button" class="mp-key' + (cls ? " " + cls : "") +
      '" data-mp="' + name + '"' + (extra || "") + ">" + esc(label) + "</button>";
  }

  function build() {
    var box = document.createElement("div");
    box.className = "mp";
    box.id = "mathpad";
    box.hidden = true;

    var html = '<div class="mp-head">' +
      '<span class="mp-label" id="mp-label">Javob</span>' +
      '<span class="mp-preview" id="mp-preview"></span>' +
      '<span class="mp-tools">' +
      action("Tozalash", "clear", "mp-flat") +
      action("Yopish", "close", "mp-flat") +
      "</span></div>";

    html += '<div class="mp-strip">';
    STRIP.forEach(function (item) { html += key(item[0], item[1], item[2], "sym"); });
    html += "</div>";

    /* --- «123» sahifasi --- */
    html += '<div class="mp-page" id="mp-num"><div class="mp-grid g5">' +
      key("7", "7", 0, "num") + key("8", "8", 0, "num") + key("9", "9", 0, "num") +
      key("×", "×", 0, "op") + key("÷", "÷", 0, "op") +
      key("4", "4", 0, "num") + key("5", "5", 0, "num") + key("6", "6", 0, "num") +
      key("+", "+", 0, "op") + key("−", "−", 0, "op") +
      key("1", "1", 0, "num") + key("2", "2", 0, "num") + key("3", "3", 0, "num") +
      key(",", ".", 0, "op") + action("⌫", "del", "del") +
      action("f(x)", "page", "switch", ' data-page="fn"') +
      key("0", "0", 0, "num") +
      action("‹", "left", "nav") + action("›", "right", "nav") +
      action("⏎", "enter", "enter") +
      "</div>" +
      '<div class="mp-grid g2 mp-extra" id="mp-extra">' +
      action("a ; b  ajratkich", "sep", "wide") +
      action("⏎  yangi savol", "newline", "wide") +
      "</div></div>";

    /* --- «f(x)» sahifasi --- */
    html += '<div class="mp-page" id="mp-fn" hidden><div class="mp-grid g4">';
    FUNCTIONS.forEach(function (item) { html += key(item[0], item[1], item[2], "fn"); });
    html += '</div><div class="mp-grid g6 mp-tail">' +
      action("123", "page", "switch", ' data-page="num"') +
      key("(", "(", 0, "op") + key(")", ")", 0, "op") +
      action("‹", "left", "nav") + action("›", "right", "nav") +
      action("⌫", "del", "del") +
      "</div></div>";

    box.innerHTML = html;
    document.body.appendChild(box);

    /* Tugma bosilganda maydon fokusdan chiqmasin. */
    box.addEventListener("mousedown", function (e) { e.preventDefault(); });
    box.addEventListener("click", onKey);
    return box;
  }

  /* ------------------------------------------------------------ ochish */

  function labelFor(input) {
    if (input.dataset.mathpadLabel) { return input.dataset.mathpadLabel; }
    var own = input.id ? document.querySelector('label[for="' + input.id + '"]') : null;
    if (own) { return own.textContent.trim(); }
    var row = input.closest(".form-row, td, .field");
    var near = row ? row.querySelector("label") : null;
    return near ? near.textContent.trim() : "Javob";
  }

  function open(input) {
    if (!pad) { pad = build(); }
    field = input;
    mode = input.dataset.mathpad || "one";

    pad.hidden = false;
    document.body.classList.add("mp-open");
    document.getElementById("mp-label").textContent = labelFor(input);
    document.getElementById("mp-extra").hidden = mode === "one";

    var enter = pad.querySelector('[data-mp="enter"]');
    if (enter) { enter.textContent = mode === "lines" ? "⏎" : "⏎"; }

    setPage("num");
    scheduleCheck();
  }

  function close() {
    if (pad) { pad.hidden = true; }
    document.body.classList.remove("mp-open");
    field = null;
  }

  function setPage(name) {
    if (!pad) { return; }
    document.getElementById("mp-num").hidden = name === "fn";
    document.getElementById("mp-fn").hidden = name !== "fn";
  }

  /* ---------------------------------------------------------- kiritish */

  function insert(text, caretShift) {
    if (!field) { return; }
    var start = field.selectionStart;
    var end = field.selectionEnd;
    if (start === null || start === undefined) { start = field.value.length; end = start; }
    field.value = field.value.slice(0, start) + text + field.value.slice(end);
    var position = start + text.length + (caretShift || 0);
    position = Math.max(0, Math.min(position, field.value.length));
    setCaret(position);
    changed();
  }

  function backspace() {
    if (!field) { return; }
    var start = field.selectionStart, end = field.selectionEnd;
    if (start === null || start === undefined) { start = field.value.length; end = start; }
    if (start === end) {
      if (start === 0) { return; }
      field.value = field.value.slice(0, start - 1) + field.value.slice(end);
      start -= 1;
    } else {
      field.value = field.value.slice(0, start) + field.value.slice(end);
    }
    setCaret(start);
    changed();
  }

  function moveCaret(step) {
    if (!field) { return; }
    var position = field.selectionStart;
    if (position === null || position === undefined) { position = field.value.length; }
    setCaret(Math.max(0, Math.min(position + step, field.value.length)));
    scheduleCheck();
  }

  function setCaret(position) {
    try { field.setSelectionRange(position, position); } catch (e) { /* ignore */ }
    field.focus({ preventScroll: true });
  }

  function clearField() {
    if (!field) { return; }
    field.value = "";
    setCaret(0);
    changed();
  }

  /*
     Kursorni joriy qatorning oxiriga olib boradi.

     «Yangi savol» va «a ; b» tugmalari mazmunan «shu javobni tugatdim»
     degani — kursor qavs ichida turgan bo'lsa ham (masalan `sqrt(3|)`),
     ajratkich yoki yangi qator ifoda o'rtasiga tushib qolmasligi kerak.
  */
  function caretToLineEnd() {
    if (!field) { return; }
    var value = field.value;
    var caret = field.selectionStart;
    if (caret === null || caret === undefined) { caret = value.length; }
    var end = value.indexOf("\n", caret);
    setCaret(end === -1 ? value.length : end);
  }

  function newLine() {
    caretToLineEnd();
    insert("\n", 0);
  }

  function separator() {
    caretToLineEnd();
    insert(" ; ", 0);
  }

  /* «⏎»: ko'p qatorli maydonda yangi qator, aks holda keyingi maydon. */
  function enter() {
    if (!field) { return; }
    if (mode === "lines") { newLine(); return; }
    var all = Array.prototype.slice.call(document.querySelectorAll("[data-mathpad]"));
    var index = all.indexOf(field);
    if (index !== -1 && index + 1 < all.length) {
      all[index + 1].focus();
      return;
    }
    close();
  }

  function changed() {
    /* Django/boshqa skriptlar uchun oddiy `input` hodisasi. */
    try { field.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) { /* ignore */ }
    scheduleCheck();
  }

  function onKey(event) {
    var button = event.target.closest("[data-mp]");
    if (!button) { return; }
    event.preventDefault();
    var name = button.dataset.mp;

    if (name === "ins") {
      insert(button.dataset.ins, parseInt(button.dataset.caret, 10) || 0);
    } else if (name === "del") {
      backspace();
    } else if (name === "left") {
      moveCaret(-1);
    } else if (name === "right") {
      moveCaret(1);
    } else if (name === "page") {
      setPage(button.dataset.page);
    } else if (name === "enter") {
      enter();
    } else if (name === "newline") {
      newLine();
    } else if (name === "sep") {
      separator();
    } else if (name === "clear") {
      clearField();
    } else if (name === "close") {
      close();
    }
  }

  /* ------------------------------------------------- jonli tekshiruv */

  /*
     Kursor turgan ifodani ajratib oladi: qator chegaralari va `;` bo'yicha.
     Shu sababli `12 ; 3/4` dagi ikkala qism alohida tekshiriladi.
  */
  function currentPiece() {
    if (!field) { return ""; }
    var value = field.value;
    var caret = field.selectionStart;
    if (caret === null || caret === undefined) { caret = value.length; }

    var start = 0, end = value.length, i;
    for (i = caret - 1; i >= 0; i -= 1) {
      if (value[i] === "\n" || value[i] === ";") { start = i + 1; break; }
    }
    for (i = caret; i < value.length; i += 1) {
      if (value[i] === "\n" || value[i] === ";") { end = i; break; }
    }
    return value.slice(start, end).trim();
  }

  function setPreview(text, state) {
    var box = document.getElementById("mp-preview");
    if (!box) { return; }
    box.textContent = text || "";
    box.className = "mp-preview" + (state ? " is-" + state : "");
  }

  function scheduleCheck() {
    if (checkTimer) { clearTimeout(checkTimer); }
    checkTimer = setTimeout(runCheck, 400);
  }

  function runCheck() {
    var expression = currentPiece();
    /* Savol raqami bilan boshlangan qator: «36) 12» — raqamni hisobga olmaymiz. */
    expression = expression.replace(/^\s*\d{1,3}\s*(?:[)\:=]|[.\-](?=\s))\s*/, "").trim();

    if (!expression) { setPreview("", null); return; }

    fetch(VALIDATE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expr: expression })
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.ok) {
          setPreview(data.pretty + (data.value ? " ≈ " + data.value : ""), "ok");
        } else {
          setPreview((data && data.error) || "Ifoda noto‘g‘ri", "error");
        }
      })
      .catch(function () { setPreview("", null); });
  }

  /* ------------------------------------------------------------ ulash */

  function attach(input) {
    if (input.dataset.mathpadReady) { return; }
    input.dataset.mathpadReady = "1";
    input.setAttribute("autocomplete", "off");
    input.setAttribute("spellcheck", "false");
    input.addEventListener("focus", function () { open(input); });
    input.addEventListener("click", function () { open(input); });
    input.addEventListener("input", function () {
      if (field === input) { scheduleCheck(); }
    });
    input.addEventListener("keyup", function () {
      if (field === input) { scheduleCheck(); }
    });
  }

  function init() {
    var fields = document.querySelectorAll("[data-mathpad]");
    if (!fields.length) { return; }
    Array.prototype.forEach.call(fields, attach);

    /* Maydondan tashqariga bosilsa — klaviatura yopiladi. */
    document.addEventListener("focusin", function (event) {
      if (!field) { return; }
      if (event.target.closest(".mp")) { return; }
      if (!event.target.hasAttribute || !event.target.hasAttribute("data-mathpad")) {
        close();
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && field) { close(); }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
