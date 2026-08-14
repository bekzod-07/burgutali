/* ==========================================================================
   Boshqaruv paneli — matematik klaviatura.

   Klaviaturaning o'zi umumiy modulda (`static/mathpad/mathpad.js`), shuning
   uchun panelda ham web ilovadagi bilan **aynan bir xil** klaviatura
   chiqadi. Bu fayl faqat panelga xos qismni bajaradi:

     * `data-mathpad` belgisi bo'lgan maydonlarni klaviaturaga ulaydi;
     * kursor turgan ifodani serverda SymPy orqali jonli tekshiradi;
     * ko'p qatorli kalitlar uchun «a ; b» va «yangi qator» tugmalarini
       yoqadi.

   Rejimlar (`data-mathpad` qiymati):
     * `lines` — ko'p qatorli maydon (har bir qator — bitta savol);
     * `pair`  — bitta maydonda `a ; b` (savollar jadvalidagi kalit);
     * `one`   — bitta ifoda (a) yoki b) javobi).

   Jismoniy klaviatura ham ishlaydi — bu panel unga qo'shimcha.
   ========================================================================== */

(function () {
  "use strict";

  var VALIDATE_URL = "/app/api/tekshir/";
  var checkTimer = null;

  function labelFor(input) {
    if (input.dataset.mathpadLabel) { return input.dataset.mathpadLabel; }
    var own = input.id ? document.querySelector('label[for="' + input.id + '"]') : null;
    if (own) { return own.textContent.trim(); }
    var row = input.closest(".form-row, td, .field");
    var near = row ? row.querySelector("label") : null;
    return near ? near.textContent.trim() : "Javob";
  }

  /*
     Kursor turgan ifodani ajratib oladi: qator chegaralari va `;` bo'yicha.
     Shu sababli `12 ; 3/4` dagi ikkala qism alohida tekshiriladi.
  */
  function currentPiece(input) {
    if (!input) { return ""; }
    var value = input.value;
    var caret = input.selectionStart;
    if (caret === null || caret === undefined) { caret = value.length; }

    var start = 0;
    var end = value.length;
    var i;
    for (i = caret - 1; i >= 0; i -= 1) {
      if (value[i] === "\n" || value[i] === ";") { start = i + 1; break; }
    }
    for (i = caret; i < value.length; i += 1) {
      if (value[i] === "\n" || value[i] === ";") { end = i; break; }
    }
    return value.slice(start, end).trim();
  }

  function scheduleCheck() {
    if (checkTimer) { clearTimeout(checkTimer); }
    checkTimer = setTimeout(runCheck, 400);
  }

  function runCheck() {
    var input = window.MathPad.active();
    if (!input) { return; }

    var expression = currentPiece(input);
    /* Savol raqami bilan boshlangan qator: «36) 12» — raqamni hisobga olmaymiz. */
    expression = expression.replace(/^\s*\d{1,3}\s*(?:[)\:=]|[.\-](?=\s))\s*/, "").trim();

    if (!expression) { window.MathPad.hint("", ""); return; }

    fetch(VALIDATE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expr: expression })
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (window.MathPad.active() !== input) { return; }
        if (data && data.ok) {
          window.MathPad.hint(data.pretty + (data.value ? " ≈ " + data.value : ""), "ok");
        } else {
          window.MathPad.hint((data && data.error) || "Ifoda noto‘g‘ri", "error");
        }
      })
      .catch(function () { window.MathPad.hint("", ""); });
  }

  function init() {
    if (!window.MathPad) { return; }

    var fields = document.querySelectorAll("[data-mathpad]");
    if (!fields.length) { return; }

    window.MathPad.mount({
      onOpen: scheduleCheck,
      onClose: function () { if (checkTimer) { clearTimeout(checkTimer); } }
    });

    Array.prototype.forEach.call(fields, function (input) {
      var mode = input.dataset.mathpad || "one";
      window.MathPad.bind(input, {
        label: labelFor(input),
        enter: mode === "lines" ? "newline" : "next",
        extra: mode === "lines" || mode === "pair",
        /* Ko'p qatorli va `a ; b` maydonlari matn ko'rinishida qoladi. */
        raw: mode !== "one"
      });
      input.addEventListener("input", scheduleCheck);
      input.addEventListener("keyup", scheduleCheck);
    });

    /* Maydondan tashqariga bosilsa — klaviatura yopiladi. */
    document.addEventListener("focusin", function (event) {
      if (!window.MathPad.active()) { return; }
      if (event.target.closest(".mpad")) { return; }
      if (!event.target.hasAttribute || !event.target.hasAttribute("data-mathpad")) {
        window.MathPad.close();
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && window.MathPad.active()) { window.MathPad.close(); }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
