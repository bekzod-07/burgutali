/* ==========================================================================
   Matematik klaviatura — umumiy modul.

   Bitta manba uchta joyda ishlatiladi:
     * web ilova (Mini App) — ochiq javoblar va javob kalitlari varaqasi;
     * boshqaruv paneli     — javob kalitlari maydonlari;
     * /app/klaviatura/     — botning alohida klaviatura sahifasi.

   Modul faqat maydon bilan ishlaydi: matn qo'yadi, kursorni suradi, ortga
   qaytaradi va har bir o'zgarishdan keyin maydonda oddiy `input` hodisasini
   uyg'otadi. Tekshiruv, saqlash va boshqa mantiq chaqiruvchi tomonda qoladi.

   Foydalanish:
       MathPad.mount({ onEnter: fn });        // bir marta
       MathPad.bind(input, { label: "…" });   // har bir maydon uchun
       MathPad.close();

   Emoji ishlatilmaydi — ikonkalar inline SVG.
   ========================================================================== */

(function (global) {
  "use strict";

  var MAX_HISTORY = 80;

  /* =====================================================================
     Ikonkalar (sprite'ga bog'liq emas — alohida sahifada ham ishlaydi)
     ===================================================================== */

  var ICON = {
    close: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
           '<path d="m6 9 6 6 6-6"/></svg>',
    undo: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path d="M9 14 4 9l5-5"/><path d="M4 9h9a6 6 0 0 1 0 12h-3"/></svg>',
    redo: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path d="m15 14 5-5-5-5"/><path d="M20 9h-9a6 6 0 0 0 0 12h3"/></svg>',
    paste: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
           '<rect x="9" y="4" width="12" height="17" rx="2"/>' +
           '<path d="M17 4V3a1 1 0 0 0-1-1h-5a1 1 0 0 0-1 1v1"/>' +
           '<path d="M6 8v11a2 2 0 0 0 2 2h5"/></svg>',
    left: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path d="m15 5-7 7 7 7"/></svg>',
    right: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
           '<path d="m9 5 7 7-7 7"/></svg>',
    enter: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
           '<path d="M20 5v6a3 3 0 0 1-3 3H5"/><path d="m9 10-4 4 4 4"/></svg>',
    del: '<svg class="mpad-ico" viewBox="0 0 24 24" aria-hidden="true">' +
         '<path d="M21 5H9l-6 7 6 7h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z"/>' +
         '<path d="m12 10 5 4M17 10l-5 4"/></svg>'
  };

  /* =====================================================================
     Tugmalar tavsifi:  [yorliq (HTML), qo'yiladigan matn, kursor siljishi]
     ===================================================================== */

  var BOX = '<i class="mpad-box"></i>';

  var ROWS = [
    {
      cols: 10,
      cls: "mpad-num",
      keys: [
        ["1", "1"], ["2", "2"], ["3", "3"], ["4", "4"], ["5", "5"],
        ["6", "6"], ["7", "7"], ["8", "8"], ["9", "9"], ["0", "0"]
      ]
    },
    {
      cols: 9,
      cls: "mpad-sym",
      keys: [
        ["&#960;", "pi"], ["e", "e"], ["a", "a"], ["b", "b"], ["c", "c"],
        ["x", "x"], ["y", "y"], ["z", "z"], [".", "."]
      ]
    },
    {
      cols: 9,
      cls: "mpad-fn",
      keys: [
        ["(", "(", 0, "mpad-op"],
        [")", ")", 0, "mpad-op"],
        /* Kasr: son yozilmagan bo'lsa ham bo'sh to'rtburchaklar chiziladi. */
        ['<span class="mpad-frac">' + BOX + '<i class="mpad-line"></i>' + BOX + "</span>",
          "/", 0, "", "frac"],
        ['<span class="mpad-root">&#8730;' + BOX + "</span>", "sqrt()", -1],
        /*
           Daraja qavs bilan yoziladi: `^()`. Shu sababli ko'rsatkich
           qayerda tugashi aniq bo'ladi — «›» tugmasi bilan darajadan
           chiqib, keyingi sonni pastda yozish mumkin.
        */
        [BOX + "<sup>" + BOX + "</sup>", "^()", -1],
        [BOX + "<sup>2</sup>", "^(2)"],
        [BOX + "<sup>3</sup>", "^(3)"],
        ['<span class="mpad-root"><span class="mpad-deg">3</span>&#8730;' + BOX + "</span>",
          "cbrt()", -1],
        /*
           Ixtiyoriy darajali ildiz. Daraja ham bo'sh to'rtburchak bo'lib
           chiziladi — unga istalgan butun son yoziladi. Kursor avval
           ildiz ostidagi katakka tushadi, «›» bilan daraja katagiga
           o'tiladi (matndagi tartib ham shunday: `root(ifoda, daraja)`).
        */
        ['<span class="mpad-root"><span class="mpad-deg">n</span>&#8730;' + BOX + "</span>",
          "root(,)", -2]
      ]
    },
    {
      cols: 6,
      cls: "mpad-fn",
      keys: [
        ["+", "+", 0, "mpad-op"],
        ["&#8722;", "-", 0, "mpad-op"],
        ["sin" + BOX, "sin()", -1],
        ["cos" + BOX, "cos()", -1],
        ["tan" + BOX, "tan()", -1],
        ["cot" + BOX, "cot()", -1]
      ]
    },
    {
      cols: 4,
      cls: "mpad-fn",
      keys: [
        ["arcsin" + BOX, "arcsin()", -1],
        ["arccos" + BOX, "arccos()", -1],
        ["arctan" + BOX, "arctan()", -1],
        ["arcctg" + BOX, "arcctg()", -1]
      ]
    },
    {
      cols: 4,
      cls: "mpad-fn",
      keys: [
        ["ln" + BOX, "ln()", -1],
        /* Maktab an'anasi: `log` — o'nlik logarifm, `ln` — natural. */
        ["log" + BOX, "log10()", -1],
        /* Ixtiyoriy asos: log(argument, asos) — kursor argument joyiga tushadi. */
        ["log<sub>" + BOX + "</sub>" + BOX, "log(,)", -2],
        ["exp" + BOX, "exp()", -1]
      ]
    }
  ];

  /* Faqat panel uchun: kalitlar varaqasidagi ajratkich va yangi qator. */
  var EXTRA = [
    ["a ; b ajratkich", "sep", "mpad-wide"],
    ["Yangi qator", "newline", "mpad-wide"]
  ];

  /* =====================================================================
     Holat
     ===================================================================== */

  var state = {
    root: null,
    label: null,
    hint: null,
    extra: null,
    undoBtn: null,
    redoBtn: null,
    input: null,
    fields: [],
    opts: {},
    applying: false,
    flashTimer: null,
    hitTimer: null,
    hitButton: null
  };

  /* =====================================================================
     Yordamchilar
     ===================================================================== */

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function caretOf(input) {
    var position = input.selectionStart;
    if (position === null || position === undefined) { return input.value.length; }
    return position;
  }

  function historyOf(input) {
    if (!input.mathpadHistory) {
      input.mathpadHistory = {
        undo: [], redo: [], value: input.value, caret: input.value.length
      };
    }
    return input.mathpadHistory;
  }

  function pushUndo(input) {
    var history = historyOf(input);
    history.undo.push({ value: input.value, caret: caretOf(input) });
    if (history.undo.length > MAX_HISTORY) { history.undo.shift(); }
    history.redo.length = 0;
  }

  /* Maydonga yangi qiymatni qo'yadi va oddiy `input` hodisasini uyg'otadi. */
  function apply(input, value, caret) {
    state.applying = true;
    input.value = value;
    var position = Math.max(0, Math.min(caret, value.length));
    try { input.setSelectionRange(position, position); } catch (error) { /* qo'llamaydi */ }
    try { input.focus({ preventScroll: true }); } catch (error) { input.focus(); }

    var history = historyOf(input);
    history.value = value;
    history.caret = position;

    fire(input, "input");
    state.applying = false;
    refreshTools();
  }

  /* Maydonda oddiy hodisa uyg'otadi (eski brauzerlar uchun zaxira bilan). */
  function fire(input, name) {
    try {
      input.dispatchEvent(new Event(name, { bubbles: true }));
    } catch (error) {
      var legacy = document.createEvent("Event");
      legacy.initEvent(name, true, false);
      input.dispatchEvent(legacy);
    }
  }

  function refreshTools() {
    if (!state.undoBtn) { return; }
    var history = state.input ? historyOf(state.input) : null;
    state.undoBtn.disabled = !history || history.undo.length === 0;
    state.redoBtn.disabled = !history || history.redo.length === 0;
  }

  function setLabel(text, isWarning) {
    if (!state.label) { return; }
    state.label.textContent = text || "";
    state.label.className = "mpad-label" + (isWarning ? " is-warn" : "");
  }

  /* Jonli tekshiruv natijasi: kind — "ok", "error" yoki bo'sh. */
  function setHint(text, kind) {
    if (!state.hint) { return; }
    state.hint.textContent = text || "";
    state.hint.className = "mpad-hint" + (kind ? " is-" + kind : "");
  }

  function labelFor(input) {
    if (!input) { return ""; }
    if (input.dataset.mpadLabel) { return input.dataset.mpadLabel; }
    if (typeof state.opts.labelFor === "function") {
      return state.opts.labelFor(input) || "";
    }
    return "";
  }

  function flash(message) {
    var current = state.input;
    setLabel(message, true);
    if (state.flashTimer) { clearTimeout(state.flashTimer); }
    state.flashTimer = setTimeout(function () {
      if (state.input === current) { setLabel(labelFor(current), false); }
    }, 2200);
  }

  /* Bosilgan tugma qisqa vaqt yonib turadi (bir vaqtda faqat bittasi). */
  function hit(button) {
    if (!button) { return; }
    if (state.hitButton && state.hitButton !== button) {
      state.hitButton.classList.remove("is-hit");
    }
    state.hitButton = button;
    button.classList.add("is-hit");

    if (state.hitTimer) { clearTimeout(state.hitTimer); }
    state.hitTimer = setTimeout(function () {
      button.classList.remove("is-hit");
      if (state.hitButton === button) { state.hitButton = null; }
    }, 200);
  }

  /* =====================================================================
     Tahrirlash amallari
     ===================================================================== */

  function insert(text, shift) {
    var input = state.input;
    if (!input) { flash("Avval javob maydonini tanlang"); return; }

    pushUndo(input);
    var start = caretOf(input);
    var end = input.selectionEnd;
    if (end === null || end === undefined) { end = start; }

    var value = input.value.slice(0, start) + text + input.value.slice(end);
    apply(input, value, start + text.length + (shift || 0));
  }

  /*
     Kursordan oldingi had allaqachon kasrmi.

     Oxirgi had ichida (qavslardan tashqarida) `/` uchrasa — kasr.
     `+`, `-`, `,`, `|` va ochiq qavs hadni tugatadi; `*` esa tugatmaydi
     (u `/` bilan bir darajada).
  */
  function endsWithFraction(text) {
    var depth = 0;
    for (var i = text.length - 1; i >= 0; i -= 1) {
      var ch = text.charAt(i);
      if (ch === ")") { depth += 1; continue; }
      if (ch === "(") {
        if (depth === 0) { return false; }
        depth -= 1;
        continue;
      }
      if (depth) { continue; }
      if (ch === "/") { return true; }
      if ("+-,|".indexOf(ch) !== -1) { return false; }
    }
    return false;
  }

  /*
     Kasr tugmasi.

     To'rtta holat bor:

       * oldida hech narsa, qo'shish/ayirish yoki ochiq qavs turibdi
         (`2+`) — bo'sh kasr chiziladi, yozilgan son o'z joyida qoladi
         (`2 + □/□`), kursor **suratda** turadi;
       * oldida ko'paytirish, bo'lish yoki daraja belgisi turibdi
         (`5/`) — yangi kasr qavs ichida chiziladi, shunda oldingi
         ifoda uning suratiga ko'tarilib ketmaydi va ikkala katak
         ham bo'sh bo'ladi (`5 / (□/□)`);
       * oldida son yoki ifoda turibdi (`455`) — u surat bo'ladi,
         kursor maxrajga tushadi (`455/|`);
       * oldida tayyor kasr turibdi (`455/3`) — u yangi kasrning
         suratiga ko'tarilmaydi: yangi kasr alohida ko'paytuvchi
         bo'lib qo'shiladi (`455/3 · □/□`).
  */
  function insertFraction() {
    var input = state.input;
    if (!input) { flash("Avval javob maydonini tanlang"); return; }

    var before = input.value.slice(0, caretOf(input)).replace(/\s+$/, "");
    var last = before.slice(-1);

    if (last === "" || "+-(,|".indexOf(last) !== -1) {
      insert("/", -1);
    } else if ("*/^".indexOf(last) !== -1) {
      insert("(/)", -2);
    } else if (endsWithFraction(before)) {
      insert("*(/)", -2);
    } else {
      insert("/", 0);
    }
  }

  /*
     Kursor bo'sh tuzilma ichida turibdimi.

     `sqrt(|)`, `2^(|)`, `root(|,3)`, `log(|,)` — bularda o'chirish tugmasi
     bitta belgini emas, butun tuzilmani olib tashlaydi. Aks holda ekranda
     yopilmagan qavs yoki yolg'iz vergul qolib ketardi.

     Natija: [boshi, oxiri] yoki `null`.
  */
  function emptyShell(value, caret) {
    /*
       Qavs ichida faqat shu belgilar bo'lsa, tuzilma bo'sh hisoblanadi.
       Son yozilgan bo'lsa — yo'q: yozilgani bekorga o'chib ketmasin.
    */
    var FILLER = ",/";
    var left = value.charAt(caret - 1);
    var right = value.charAt(caret);
    /* Kursor bo'sh argument joyida bo'lishi shart. */
    if (!left || "(,".indexOf(left) === -1) { return null; }
    if (!right || ",/)".indexOf(right) === -1) { return null; }

    var open = caret - 1;
    while (open >= 0 && value.charAt(open) !== "(") {
      if (FILLER.indexOf(value.charAt(open)) === -1) { return null; }
      open -= 1;
    }
    if (open < 0) { return null; }

    var close = caret;
    while (close < value.length && value.charAt(close) !== ")") {
      if (FILLER.indexOf(value.charAt(close)) === -1) { return null; }
      close += 1;
    }
    if (close >= value.length) { return null; }

    /* Qavsdan oldingi funksiya nomi yoki amal belgisi ham birga ketadi. */
    var from = open;
    while (from > 0 && /[A-Za-z0-9_]/.test(value.charAt(from - 1))) { from -= 1; }
    while (from < open && /[0-9]/.test(value.charAt(from))) { from += 1; }
    if (from === open && "^*".indexOf(value.charAt(from - 1)) !== -1) { from -= 1; }

    return [from, close + 1];
  }

  function backspace() {
    var input = state.input;
    if (!input) { return; }

    var start = caretOf(input);
    var end = input.selectionEnd;
    if (end === null || end === undefined) { end = start; }
    if (start === end && start === 0) { return; }

    var value = input.value;
    pushUndo(input);

    if (start !== end) {
      apply(input, value.slice(0, start) + value.slice(end), start);
      return;
    }

    var shell = emptyShell(value, start);
    if (shell) {
      apply(input, value.slice(0, shell[0]) + value.slice(shell[1]), shell[0]);
      return;
    }

    apply(input, value.slice(0, start - 1) + value.slice(start), start - 1);
  }

  /*
     Kursor tugallanmagan maxrajning oxirida turibdimi.

     `455/3|` — bunda o'ngga siljish uchun joy yo'q, matn tugagan.
     Natija: kasr chizig'ining o'rni yoki -1.
  */
  function openDenominator(value, caret) {
    /* Yopiladigan qavs bilan tugagan bo'lsa, kursor allaqachon tashqarida. */
    if (value.charAt(caret - 1) === ")") { return -1; }

    var depth = 0;
    for (var i = caret - 1; i >= 0; i -= 1) {
      var ch = value.charAt(i);
      if (ch === ")") { depth += 1; continue; }
      if (ch === "(") {
        if (depth === 0) { return -1; }      // ochiq qavs ichidamiz
        depth -= 1;
        continue;
      }
      if (depth) { continue; }
      if (ch === "/") { return i; }
      if ("+-*,|^".indexOf(ch) !== -1) { return -1; }
    }
    return -1;
  }

  /*
     Tuzilma qavsi — `2^(3)` va `455/(3)` dagi qavslar.

     Ular ekranda ko'rinmaydi, shuning uchun kursor ular ustida
     to'xtab o'tirmaydi: «‹» va «›» ularni sakrab o'tadi.
  */
  function hiddenParen(value, index) {
    return value.charAt(index) === "(" &&
      "/^".indexOf(value.charAt(index - 1)) !== -1;
  }

  function moveCaret(step) {
    var input = state.input;
    if (!input) { return; }

    var value = input.value;
    var caret = caretOf(input);

    /*
       Maxrajning oxiridan o'ngga chiqish.

       Matn tugagan joyda kursorning «maxraj ichida» va «kasrdan keyin»
       holatlari bir xil o'ringa to'g'ri keladi. Shuning uchun maxraj
       qavsga olinadi — ko'rinish o'zgarmaydi (`455/3` xuddi shundayligicha
       chiziladi), lekin kursor kasrdan chiqadigan joy paydo bo'ladi.
    */
    if (step > 0 && caret >= value.length) {
      var slash = openDenominator(value, caret);
      if (slash !== -1 && slash + 1 < value.length) {
        pushUndo(input);
        apply(input,
              value.slice(0, slash + 1) + "(" + value.slice(slash + 1) + ")",
              value.length + 2);
        return;
      }
    }

    var position = Math.max(0, Math.min(caret + step, value.length));
    for (var guard = 0; guard < 8 && hiddenParen(value, position); guard += 1) {
      var next = position + step;
      if (next < 0 || next > value.length) { break; }
      position = next;
    }

    try { input.setSelectionRange(position, position); } catch (error) { /* qo'llamaydi */ }
    try { input.focus({ preventScroll: true }); } catch (error) { input.focus(); }
    historyOf(input).caret = position;
    /* Chizilgan formulada kursor yangi joyga ko'chsin. */
    fire(input, "mpad:change");
  }

  function undo() {
    var input = state.input;
    if (!input) { return; }
    var history = historyOf(input);
    if (!history.undo.length) { return; }
    history.redo.push({ value: input.value, caret: caretOf(input) });
    var previous = history.undo.pop();
    apply(input, previous.value, previous.caret);
  }

  function redo() {
    var input = state.input;
    if (!input) { return; }
    var history = historyOf(input);
    if (!history.redo.length) { return; }
    history.undo.push({ value: input.value, caret: caretOf(input) });
    var next = history.redo.pop();
    apply(input, next.value, next.caret);
  }

  function paste() {
    var input = state.input;
    if (!input) { flash("Avval javob maydonini tanlang"); return; }
    if (!global.navigator || !navigator.clipboard || !navigator.clipboard.readText) {
      flash("Buferdan o‘qib bo‘lmadi");
      return;
    }
    navigator.clipboard.readText().then(function (text) {
      var value = String(text || "").replace(/\s+/g, " ").trim();
      if (!value) { flash("Bufer bo‘sh"); return; }
      insert(value, 0);
    }).catch(function () {
      flash("Buferdan o‘qib bo‘lmadi");
    });
  }

  /*
     Kursorni joriy qatorning oxiriga olib boradi.

     «Ajratkich» va «yangi qator» tugmalari mazmunan «shu javobni tugatdim»
     degani — kursor qavs ichida turgan bo'lsa ham (masalan `sqrt(3|)`),
     belgi ifoda o'rtasiga tushib qolmasligi kerak.
  */
  function caretToLineEnd() {
    var input = state.input;
    if (!input) { return; }
    var value = input.value;
    var caret = caretOf(input);
    var end = value.indexOf("\n", caret);
    var position = end === -1 ? value.length : end;
    try { input.setSelectionRange(position, position); } catch (error) { /* qo'llamaydi */ }
    historyOf(input).caret = position;
  }

  function enter() {
    var input = state.input;
    if (!input) { return; }

    if (typeof state.opts.onEnter === "function" && state.opts.onEnter(input) === true) {
      return;
    }
    if ((input.dataset.mpadEnter || "") === "newline") {
      caretToLineEnd();
      insert("\n", 0);
      return;
    }

    var index = state.fields.indexOf(input);
    if (index !== -1 && index + 1 < state.fields.length) {
      open(state.fields[index + 1]);
      return;
    }
    close();
  }

  /* =====================================================================
     Panelni qurish
     ===================================================================== */

  /* [yorliq, matn, kursor siljishi, klass, maxsus amal] */
  function keyHtml(key) {
    var extra = key[3] ? " " + key[3] : "";
    return '<button type="button" class="mpad-key' + extra + '" data-mp="' +
      (key[4] || "ins") + '" data-ins="' + esc(key[1]) +
      '" data-caret="' + (key[2] || 0) + '">' + key[0] + "</button>";
  }

  function buildHtml() {
    var html = '<div class="mpad-bar">' +
      '<button type="button" class="mpad-tool" data-mp="close"' +
      ' aria-label="Klaviaturani yopish" title="Yopish">' + ICON.close + "</button>" +
      '<span class="mpad-label" id="mpad-label"></span>' +
      '<span class="mpad-hint" id="mpad-hint"></span>' +
      '<span class="mpad-tools">' +
      '<button type="button" class="mpad-tool" data-mp="undo"' +
      ' aria-label="Ortga qaytarish" title="Ortga">' + ICON.undo + "</button>" +
      '<button type="button" class="mpad-tool" data-mp="redo"' +
      ' aria-label="Qaytarish" title="Oldinga">' + ICON.redo + "</button>" +
      '<button type="button" class="mpad-tool" data-mp="paste"' +
      ' aria-label="Buferdan qo‘yish" title="Qo‘yish">' + ICON.paste + "</button>" +
      "</span></div>";

    ROWS.forEach(function (row) {
      html += '<div class="mpad-row mpad-row-' + row.cols + " " + row.cls + '">';
      row.keys.forEach(function (key) { html += keyHtml(key); });
      html += "</div>";
    });

    html += '<div class="mpad-row mpad-row-2 mpad-extra" id="mpad-extra" hidden>';
    EXTRA.forEach(function (item) {
      html += '<button type="button" class="mpad-key ' + item[2] +
        '" data-mp="' + item[1] + '">' + esc(item[0]) + "</button>";
    });
    html += "</div>";

    html += '<div class="mpad-navwrap"><div class="mpad-nav">' +
      '<button type="button" data-mp="left" aria-label="Chapga">' + ICON.left + "</button>" +
      '<button type="button" data-mp="right" aria-label="O‘ngga">' + ICON.right + "</button>" +
      '<button type="button" data-mp="enter" aria-label="Keyingisi">' + ICON.enter + "</button>" +
      '<button type="button" class="mpad-del" data-mp="del" aria-label="O‘chirish">' +
      ICON.del + "</button>" +
      "</div></div>";

    return html;
  }

  function onPadClick(event) {
    var button = event.target.closest("[data-mp]");
    if (!button || button.disabled) { return; }
    event.preventDefault();

    var action = button.dataset.mp;
    if (action === "ins") {
      hit(button);
      insert(button.dataset.ins, parseInt(button.dataset.caret, 10) || 0);
    } else if (action === "frac") {
      hit(button);
      insertFraction();
    } else if (action === "del") {
      backspace();
    } else if (action === "left") {
      moveCaret(-1);
    } else if (action === "right") {
      moveCaret(1);
    } else if (action === "enter") {
      enter();
    } else if (action === "undo") {
      undo();
    } else if (action === "redo") {
      redo();
    } else if (action === "paste") {
      paste();
    } else if (action === "close") {
      close();
    } else if (action === "sep") {
      caretToLineEnd();
      insert(" ; ", 0);
    } else if (action === "newline") {
      caretToLineEnd();
      insert("\n", 0);
    }
  }

  function mount(options) {
    if (state.root) { return state.root; }
    state.opts = options || {};

    var root = document.createElement("div");
    root.className = "mpad" + (state.opts.inline ? " mpad-inline" : "");
    root.id = state.opts.id || "mathpad";
    root.innerHTML = buildHtml();

    (state.opts.container || document.body).appendChild(root);

    state.root = root;
    state.label = root.querySelector("#mpad-label");
    state.hint = root.querySelector("#mpad-hint");
    state.extra = root.querySelector("#mpad-extra");
    state.undoBtn = root.querySelector('[data-mp="undo"]');
    state.redoBtn = root.querySelector('[data-mp="redo"]');

    /*
       Tugma bosilganda maydon fokusdan chiqmasin.

       Faqat `mousedown` to'xtatiladi: `touchstart` ni to'xtatish panelni
       aylantirishni ham, ba'zi brauzerlarda `click` hodisasini ham bekor
       qilib qo'yadi. Sensorli ekranda fokus har bir amaldan keyin
       `apply()` ichida qaytariladi.
    */
    root.addEventListener("mousedown", function (event) { event.preventDefault(); });
    root.addEventListener("click", onPadClick);

    if (state.opts.inline) {
      root.classList.add("is-open");
      measure();
      global.addEventListener("resize", measure);
    }

    refreshTools();
    return root;
  }

  /* Panel balandligini CSS o'zgaruvchisiga yozadi — sahifa uni bekitmaydi. */
  function measure() {
    if (!state.root) { return; }
    var height = state.root.classList.contains("is-open") ? state.root.offsetHeight : 0;
    document.documentElement.style.setProperty("--mpad-h", height + "px");
  }

  /* Maydon klaviatura ostida qolib ketmasin. */
  function reveal(input) {
    if (!state.root || state.opts.inline) { return; }
    var pad = state.root.getBoundingClientRect();
    var box = input.getBoundingClientRect();
    var overlap = box.bottom + 14 - pad.top;
    if (overlap <= 0) { return; }
    if (global.scrollBy) {
      try { global.scrollBy({ top: overlap, behavior: "smooth" }); }
      catch (error) { global.scrollBy(0, overlap); }
    }
  }

  /* =====================================================================
     Ochish va yopish
     ===================================================================== */

  function markActive(input) {
    state.fields.forEach(function (field) {
      field.classList.remove("mpad-focus");
      var wrap = field.closest ? field.closest(".answer-field, .field") : null;
      if (wrap) { wrap.classList.remove("is-active"); }
    });
    if (!input) { return; }
    input.classList.add("mpad-focus");
    var box = input.closest ? input.closest(".answer-field, .field") : null;
    if (box) { box.classList.add("is-active"); }
  }

  function open(input) {
    if (!input) { return; }
    if (!state.root) { mount(state.opts); }

    state.input = input;
    historyOf(input);
    markActive(input);
    setLabel(labelFor(input), false);
    setHint("", "");

    if (state.extra) {
      state.extra.hidden = input.dataset.mpadExtra !== "1";
    }

    state.root.classList.add("is-open");
    if (!state.opts.inline) { document.body.classList.add("mpad-open"); }

    try { input.focus({ preventScroll: true }); } catch (error) { input.focus(); }
    refreshTools();
    measure();
    reveal(input);

    if (typeof state.opts.onOpen === "function") { state.opts.onOpen(input); }
  }

  function close() {
    if (!state.root) { return; }
    if (state.opts.inline) { markActive(null); state.input = null; return; }

    state.root.classList.remove("is-open");
    document.body.classList.remove("mpad-open");
    markActive(null);
    state.input = null;
    setLabel("", false);
    setHint("", "");
    measure();
    refreshTools();

    if (typeof state.opts.onClose === "function") { state.opts.onClose(); }
  }

  /* =====================================================================
     Maydonlarni ulash
     ===================================================================== */

  function trackTyping(input) {
    var history = historyOf(input);
    if (state.applying) { return; }
    if (input.value !== history.value) {
      history.undo.push({ value: history.value, caret: history.caret });
      if (history.undo.length > MAX_HISTORY) { history.undo.shift(); }
      history.redo.length = 0;
      history.value = input.value;
    }
    history.caret = caretOf(input);
    refreshTools();
  }

  function bind(input, meta) {
    if (!input || input.dataset.mpadBound === "1") { return; }
    input.dataset.mpadBound = "1";
    meta = meta || {};

    if (meta.label) { input.dataset.mpadLabel = meta.label; }
    if (meta.enter) { input.dataset.mpadEnter = meta.enter; }
    if (meta.extra) { input.dataset.mpadExtra = "1"; }

    input.setAttribute("autocomplete", "off");
    input.setAttribute("spellcheck", "false");

    historyOf(input);
    state.fields.push(input);

    input.addEventListener("focus", function () { open(input); });
    input.addEventListener("click", function () { open(input); });
    input.addEventListener("input", function () { trackTyping(input); });
    input.addEventListener("keyup", function () { historyOf(input).caret = caretOf(input); });

    /*
       Maydon javobni chizilgan formula ko'rinishida ko'rsatadi.
       `raw: true` berilgan maydonlar (ko'p qatorli kalitlar, `a ; b`)
       oddiy matn bo'lib qoladi.
    */
    if (!meta.raw && global.MathField) {
      global.MathField.attach(input);
    }
  }

  function bindAll(scope, selector, meta) {
    var nodes = (scope || document).querySelectorAll(selector);
    Array.prototype.forEach.call(nodes, function (input) {
      var options = typeof meta === "function" ? meta(input) : meta;
      bind(input, options);
    });
    sortFields();
  }

  /* «⏎» hujjatdagi tartib bo'yicha keyingi maydonga o'tishi uchun. */
  function sortFields() {
    state.fields = state.fields.filter(function (field) {
      return field && field.isConnected !== false;
    });
    state.fields.sort(function (a, b) {
      var order = a.compareDocumentPosition(b);
      if (order & Node.DOCUMENT_POSITION_FOLLOWING) { return -1; }
      if (order & Node.DOCUMENT_POSITION_PRECEDING) { return 1; }
      return 0;
    });
  }

  /* Ekran qayta chizilganda eski maydonlarni unutamiz. */
  function reset() {
    state.fields = state.fields.filter(function (field) {
      return field && document.contains(field);
    });
    if (state.input && !document.contains(state.input)) { close(); }
    if (global.MathField) { global.MathField.reset(); }
  }

  /* =====================================================================
     Tashqi interfeys
     ===================================================================== */

  global.MathPad = {
    mount: mount,
    bind: bind,
    bindAll: bindAll,
    open: open,
    close: close,
    reset: reset,
    measure: measure,
    insert: insert,
    hint: setHint,
    active: function () { return state.input; },
    isOpen: function () {
      return !!(state.root && state.root.classList.contains("is-open"));
    }
  };
})(window);
