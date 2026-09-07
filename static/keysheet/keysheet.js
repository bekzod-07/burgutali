/* ==========================================================================
   Javob kalitlari varaqasi — umumiy modul

   Test yaratuvchi to'g'ri javobni qatnashchi ko'radigan varaqaning **aynan
   o'zida** belgilaydi: 1–32 uchun A–D, 33–35 uchun A–F tugmalari, ochiq
   savollar uchun esa javob maydonlari.

   Modul ikkita joyda ishlatiladi va ikkalasida bir xil ko'rinadi:

     * web ilova  — «Testlarim → Test yaratish» ekrani;
     * boshqaruv paneli — «Yangi test» sahifasi va savollar ro'yxati.

   Ochiq javob — so'z yoki qisqa ibora. Kalitda bir nechta sinonimni
   vergul (yoki `;`, `/`) bilan ajratib yozish mumkin: `osmon, samo, fazo` —
   qatnashchi qaysi birini yozsa ham javob to'g'ri hisoblanadi.

   Ishlatish:

       var sheet = KeySheet.mount(box, {
         plan: KeySheet.plan({ national: true }),
         validate: function (expr) { return Promise.resolve({pretty: "..."}); },
         onChange: function (handle) { ... }
       });
       sheet.serialize();   // {single_keys, multi_keys, open_keys}
       sheet.progress();    // {done, total, missing: [...]}

   Tanlov qoidasi: har bir savolda **faqat bitta** variant belgilanadi —
   A–D da ham, A–F da ham. Belgilangan variant qayta bosilsa, tanlov
   bekor qilinadi.
   ========================================================================== */

(function (global) {
  "use strict";

  var SINGLE_LETTERS = ["A", "B", "C", "D"];
  var MULTI_LETTERS = ["A", "B", "C", "D", "E", "F"];

  /*
     Milliy sertifikat shabloni — 45 ta savol, 51 ball:
       1–32  A–D (32 ball) · 33–35 A–F (3 ball)
       36–39 ochiq, bitta javob (4 ball)
       40–45 ochiq, a) va b) (12 ball)
  */
  var NATIONAL = {
    single: { from: 1, to: 32 },
    multi: { from: 33, to: 35 },
    open: { from: 36, to: 45 },
    openSingle: { from: 36, to: 39 }
  };

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ---------------------------------------------------------------- reja */

  /*
     Test tuzilmasiga qarab qaysi savol qaysi turda ekanini aniqlaydi.
       {national: true}          — 1–32 A–D, 33–35 A–F, 36–45 ochiq;
       {national: false, count}  — barchasi A–D.
  */
  function plan(options) {
    options = options || {};
    if (options.national) {
      return {
        national: true,
        single: { from: NATIONAL.single.from, to: NATIONAL.single.to },
        multi: { from: NATIONAL.multi.from, to: NATIONAL.multi.to },
        open: { from: NATIONAL.open.from, to: NATIONAL.open.to },
        openSingle: { from: NATIONAL.openSingle.from, to: NATIONAL.openSingle.to }
      };
    }
    var count = parseInt(options.count, 10) || 0;
    count = Math.max(1, Math.min(count, 500));
    return { national: false, single: { from: 1, to: count }, multi: null, open: null };
  }

  function samePlan(a, b) {
    return !!a && !!b && JSON.stringify(a) === JSON.stringify(b);
  }

  /* ------------------------------------------------------------- chizish */

  function head(title, note, kind) {
    return '<div class="ks-head kind-' + kind + '"><b>' + esc(title) + "</b>" +
      "<span>" + esc(note) + "</span></div>";
  }

  function letterRow(order, letters, kind, chosen) {
    var html = '<div class="ks-row' + (chosen ? " is-set" : "") +
      '" data-ks-row="' + order + '">' +
      '<span class="ks-no">' + order + "</span>" +
      '<div class="choices cols-' + letters.length + (kind === "multi" ? " multi" : "") + '">';
    letters.forEach(function (letter) {
      html += '<button type="button" class="choice' +
        (chosen === letter ? " is-selected" : "") +
        '" data-ks-choose="' + order + '" data-ks-letter="' + letter + '">' +
        letter + "</button>";
    });
    return html + "</div></div>";
  }

  function openField(uid, order, part, value, labelled) {
    var id = uid + "-" + order + "-" + part;
    var label = labelled ? part + ") to‘g‘ri javob" : "To‘g‘ri javob";
    return '<div class="answer-field" data-field="' + id + '">' +
      "<label>" + label + "</label>" +
      '<input type="text" autocomplete="off" autocapitalize="off" spellcheck="false" ' +
      'data-ks-order="' + order + '" data-ks-part="' + part + '" id="' + id + '" ' +
      'value="' + esc(value) + '" placeholder="masalan: osmon, samo, fazo">' +
      '<div class="fx"></div></div>';
  }

  /* Savol nechta javobdan iborat: 36–39 — bitta, 40–45 — a) va b). */
  function openParts(plan, order) {
    var single = plan && plan.openSingle;
    if (single && order >= single.from && order <= single.to) { return 1; }
    return 2;
  }

  function openRow(uid, order, value, parts) {
    var ready = parts >= 2
      ? !!((value.a || "").trim() && (value.b || "").trim())
      : !!(value.a || "").trim();
    var html = '<div class="ks-row ks-open' + (ready ? " is-set" : "") +
      '" data-ks-row="' + order + '">' +
      '<span class="ks-no">' + order + "</span>" +
      '<div class="answer-fields">' +
      openField(uid, order, "a", value.a || "", parts >= 2);
    if (parts >= 2) {
      html += openField(uid, order, "b", value.b || "", true);
    }
    return html + "</div></div>";
  }

  function render(handle) {
    var p = handle.plan;
    var keys = handle.keys;
    var order;
    var html = '<div class="ksheet">';

    html += head(
      (p.national ? "1–32" : p.single.from + "–" + p.single.to) + " · Yopiq savollar",
      "A–D variantlardan to‘g‘ri javobni belgilang",
      "single"
    );
    for (order = p.single.from; order <= p.single.to; order += 1) {
      html += letterRow(order, SINGLE_LETTERS, "single", keys.letters[order] || "");
    }

    if (p.multi) {
      html += head(
        p.multi.from + "–" + p.multi.to + " · Moslashtirish",
        "A–F variantlardan faqat bittasi to‘g‘ri",
        "multi"
      );
      for (order = p.multi.from; order <= p.multi.to; order += 1) {
        html += letterRow(order, MULTI_LETTERS, "multi", keys.letters[order] || "");
      }
    }

    if (p.open) {
      var note = "Sinonimlarni vergul bilan sanang: osmon, samo, fazo — har biri to‘g‘ri hisoblanadi";
      if (p.openSingle) {
        note = p.openSingle.from + "–" + p.openSingle.to + " bitta javobdan, " +
          (p.openSingle.to + 1) + "–" + p.open.to + " esa a) va b) dan. " + note;
      }
      html += head(p.open.from + "–" + p.open.to + " · Ochiq javob", note, "open");
      for (order = p.open.from; order <= p.open.to; order += 1) {
        html += openRow(
          handle.uid, order, keys.open[order] || { a: "", b: "" }, openParts(p, order)
        );
      }
    }

    return html + "</div>";
  }

  /* ------------------------------------------------------------- hisoblar */

  function progress(handle) {
    var p = handle.plan;
    var keys = handle.keys;
    var done = 0, total = 0, order;
    var missing = [];

    function letters(from, to) {
      for (var i = from; i <= to; i += 1) {
        total += 1;
        if (keys.letters[i]) { done += 1; } else { missing.push(i); }
      }
    }

    letters(p.single.from, p.single.to);
    if (p.multi) { letters(p.multi.from, p.multi.to); }
    if (p.open) {
      for (order = p.open.from; order <= p.open.to; order += 1) {
        var value = keys.open[order] || {};
        var filled = (value.a || "").trim() &&
          (openParts(p, order) < 2 || (value.b || "").trim());
        total += 1;
        if (filled) { done += 1; } else { missing.push(order); }
      }
    }
    return { done: done, total: total, missing: missing };
  }

  /* Ochiq javobni matn rejimidagi kalit satriga xavfsiz qo'shish. */
  function cleanOpen(value) {
    return String(value || "").replace(/\|/g, ",").trim();
  }

  /* Server kutayotgan kalit satrlari. */
  function serialize(handle) {
    var p = handle.plan;
    var keys = handle.keys;
    var single = [], multi = [], open = [];
    var order;

    for (order = p.single.from; order <= p.single.to; order += 1) {
      single.push(keys.letters[order] || "");
    }
    if (p.multi) {
      for (order = p.multi.from; order <= p.multi.to; order += 1) {
        multi.push(keys.letters[order] || "");
      }
    }
    if (p.open) {
      for (order = p.open.from; order <= p.open.to; order += 1) {
        var value = keys.open[order] || {};
        /* `|` — a) va b) ajratkichi. Yaratuvchi uni javob ichida
           «yoki» ma'nosida yozib qo'ysa, javob ikkiga bo'linib ketardi;
           shuning uchun u sinonim ajratkichiga (vergul) aylantiriladi. */
        if (openParts(p, order) < 2) {
          open.push(cleanOpen(value.a));           // bitta javobli savol
        } else {
          open.push(cleanOpen(value.a) + " | " + cleanOpen(value.b));
        }
      }
    }
    return {
      single_keys: single.join(" "),
      multi_keys: multi.join(", "),
      open_keys: open.join("\n")
    };
  }

  /* --------------------------------------------------- jonli tekshiruv */

  /*
     Kiritilgan ifodani serverda tekshiradi va natijani maydon ostida
     ko'rsatadi. Tekshirish funksiyasi qobiqdan keladi, chunki web ilova
     va panel turli manzil va autentifikatsiyadan foydalanadi.
  */
  function checker(handle) {
    var timers = {};

    return function (input) {
      if (!input || !input.id || !handle.validate) { return; }
      var id = input.id;
      if (timers[id]) { clearTimeout(timers[id]); }
      timers[id] = setTimeout(function () {
        var field = document.getElementById(id);
        var wrap = field && field.closest ? field.closest(".answer-field") : null;
        var fx = wrap ? wrap.querySelector(".fx") : null;
        if (!field || !fx) { return; }

        var value = field.value.trim();
        if (!value) { fx.textContent = ""; fx.className = "fx"; return; }

        handle.validate(value).then(function (data) {
          if (document.getElementById(id) !== field) { return; }
          var note = data.variants > 1 ? " · " + data.variants + " ta sinonim" : "";
          fx.textContent = "Tekshiruvda: " + data.pretty + note;
          fx.className = "fx ok";
        }).catch(function (error) {
          if (document.getElementById(id) !== field) { return; }
          fx.textContent = (error && error.message) || "Javob noto‘g‘ri";
          fx.className = "fx err";
        });
      }, 400);
    };
  }

  /* ------------------------------------------------------------- ulanish */

  var counter = 0;

  function mount(container, options) {
    if (!container) { return null; }
    options = options || {};
    counter += 1;

    var handle = {
      box: container,
      uid: options.uid || ("ks" + counter),
      plan: options.plan || plan({ national: false, count: 20 }),
      keys: { letters: {}, open: {} },
      validate: options.validate || null,
      onChange: options.onChange || null
    };

    if (options.keys) {
      handle.keys.letters = Object.assign({}, options.keys.letters || {});
      handle.keys.open = Object.assign({}, options.keys.open || {});
    }

    var check = checker(handle);

    function changed() {
      if (handle.onChange) { handle.onChange(handle); }
    }

    function bindFields() {
      var inputs = container.querySelectorAll(".answer-field input[data-ks-order]");
      Array.prototype.forEach.call(inputs, function (input) {
        if (input.value.trim()) { check(input); }
      });
    }

    function draw() {
      container.innerHTML = render(handle);
      bindFields();
      changed();
    }

    /* Tanlov: bosilgan harf belgilanadi, qayta bosilsa — bekor qilinadi. */
    container.addEventListener("click", function (event) {
      var button = event.target.closest ? event.target.closest("[data-ks-choose]") : null;
      if (!button || !container.contains(button)) { return; }
      event.preventDefault();

      var order = parseInt(button.dataset.ksChoose, 10);
      var letter = button.dataset.ksLetter;
      handle.keys.letters[order] =
        handle.keys.letters[order] === letter ? "" : letter;

      var row = container.querySelector('[data-ks-row="' + order + '"]');
      if (row) {
        row.classList.toggle("is-set", !!handle.keys.letters[order]);
        Array.prototype.forEach.call(row.querySelectorAll(".choice"), function (item) {
          item.classList.toggle(
            "is-selected", item.dataset.ksLetter === handle.keys.letters[order]
          );
        });
      }
      if (options.haptic) { options.haptic("light"); }
      changed();
    });

    container.addEventListener("input", function (event) {
      var input = event.target;
      if (!input.dataset || !input.dataset.ksOrder) { return; }

      var order = parseInt(input.dataset.ksOrder, 10);
      var value = handle.keys.open[order] || { a: "", b: "" };
      value[input.dataset.ksPart] = input.value;
      handle.keys.open[order] = value;

      var row = container.querySelector('[data-ks-row="' + order + '"]');
      if (row) {
        var ready = (value.a || "").trim() &&
          (openParts(handle.plan, order) < 2 || (value.b || "").trim());
        row.classList.toggle("is-set", !!ready);
      }
      check(input);
      changed();
    });

    handle.refresh = draw;
    handle.progress = function () { return progress(handle); };
    handle.serialize = function () { return serialize(handle); };
    handle.setPlan = function (next) {
      if (samePlan(handle.plan, next)) { return; }
      handle.plan = next;
      draw();
    };
    handle.setKeys = function (keys) {
      handle.keys.letters = Object.assign({}, (keys && keys.letters) || {});
      handle.keys.open = Object.assign({}, (keys && keys.open) || {});
      draw();
    };

    draw();
    return handle;
  }

  /* =====================================================================
     Tashqi interfeys
     ===================================================================== */

  global.KeySheet = {
    SINGLE_LETTERS: SINGLE_LETTERS,
    MULTI_LETTERS: MULTI_LETTERS,
    NATIONAL: NATIONAL,
    plan: plan,
    mount: mount
  };
})(window);
