/* ==========================================================================
   Boshqaruv paneli — javoblar varaqasi.

   Varaqaning o'zi umumiy modulda (`static/keysheet/keysheet.js`), shuning
   uchun panelda ham web ilovadagi bilan **aynan bir xil** varaqa chiqadi:
   1–32 uchun A–D, 33–35 uchun A–F tugmalari (har birida faqat bitta
   javob) va ochiq savollar uchun matn maydonlari.

   Bu fayl faqat panelga xos qismni bajaradi:

     * «Yangi test» sahifasida varaqani test turi va tuzilmasiga moslaydi,
       belgilangan javoblarni forma maydonlariga yozib boradi;
     * savollar ro'yxati va savolni tahrirlash sahifalarida harf kalitini
       matn maydoni o'rniga tugmalar bilan tanlatadi.

   Matn ko'rinishidagi maydonlar o'rnida qoladi — tayyor kalitni bir marta
   joylashtirish uchun «Matn ko'rinishida» rejimi bor.
   ========================================================================== */

(function () {
  "use strict";

  var VALIDATE_URL = "/app/api/tekshir/";

  /*
     Javobni serverda tozalatadi — varaqa maydonlari ostidagi izoh uchun.
     Panelda doim **kalit** yoziladi, shuning uchun `as_key` yuboriladi:
     server sinonimlarni ajratib qaytaradi («osmon yoki samo yoki fazo»).
  */
  function validate(expression) {
    return fetch(VALIDATE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expr: expression, as_key: true })
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.ok) { return data; }
        throw new Error((data && data.error) || "Javobni tekshirib bo‘lmadi");
      });
  }

  /* ==================================================================
     1. «Yangi test» — varaqa forma maydonlarini to'ldiradi
     ================================================================== */

  function initCreate() {
    var box = document.getElementById("key-sheet");
    if (!box || !window.KeySheet) { return; }

    var type = document.getElementById("id_exam_type");
    var structure = document.getElementById("id_structure");
    var count = document.getElementById("id_question_count");
    var single = document.getElementById("id_single_keys");
    var multi = document.getElementById("id_multi_keys");
    var open = document.getElementById("id_open_keys");
    var progress = document.getElementById("key-progress");
    var modes = document.getElementById("key-mode");
    var textBox = document.getElementById("key-text");
    var form = document.getElementById("exam-form");
    if (!single || !form) { return; }

    /* Kalit maydonlarida xato bo'lsa sahifa matn rejimida ochiladi. */
    var active = modes ? modes.querySelector("button.is-active") : null;
    var mode = active ? active.dataset.keymode : "sheet";

    function planNow() {
      var national = structure && structure.value === "national" &&
        type && type.value !== "simple";
      return window.KeySheet.plan({
        national: national,
        count: count ? parseInt(count.value, 10) : 0
      });
    }

    function onChange(handle) {
      var keys = handle.serialize();
      var national = handle.plan.national;
      single.value = keys.single_keys;
      if (multi) { multi.value = national ? keys.multi_keys : ""; }
      if (open) { open.value = national ? keys.open_keys : ""; }

      if (progress) {
        var counters = handle.progress();
        progress.textContent = counters.done + " / " + counters.total;
        progress.classList.toggle("is-full", counters.done === counters.total);
      }
    }

    var sheet = window.KeySheet.mount(box, {
      uid: "key",
      plan: planNow(),
      validate: validate,
      onChange: onChange
    });

    function syncPlan() { sheet.setPlan(planNow()); onChange(sheet); }

    [type, structure, count].forEach(function (field) {
      if (!field) { return; }
      field.addEventListener("change", syncPlan);
      field.addEventListener("input", syncPlan);
    });

    /* --- «Javoblar varaqasi» / «Matn ko'rinishida» --- */
    if (modes) {
      modes.addEventListener("click", function (event) {
        var button = event.target.closest("button[data-keymode]");
        if (!button) { return; }
        event.preventDefault();
        mode = button.dataset.keymode;

        Array.prototype.forEach.call(modes.querySelectorAll("button"), function (item) {
          item.classList.toggle("is-active", item === button);
        });
        box.hidden = mode !== "sheet";
        if (textBox) { textBox.hidden = mode !== "text"; }
        if (progress) { progress.hidden = mode !== "sheet"; }
        if (mode === "sheet") { onChange(sheet); }
      });
    }

    /*
       Yuborishdan oldin: varaqa rejimida to'ldirilmagan savol qolmasin.
       Matn rejimida tekshiruv serverda — u yerda ham xabar aniq.
    */
    form.addEventListener("submit", function (event) {
      if (mode !== "sheet") { return; }
      onChange(sheet);

      var counters = sheet.progress();
      if (!counters.missing.length) { return; }

      event.preventDefault();
      var note = document.getElementById("key-missing");
      if (note) {
        note.hidden = false;
        note.textContent = "Javob kaliti to‘ldirilmagan savollar: " +
          counters.missing.slice(0, 30).join(", ") +
          (counters.missing.length > 30 ? " …" : "");
      }
      var row = box.querySelector('[data-ks-row="' + counters.missing[0] + '"]');
      if (row) { row.scrollIntoView({ behavior: "smooth", block: "center" }); }
    });
  }

  /* ==================================================================
     2. Harf kaliti — matn maydoni o'rniga tugmalar

     `data-letters` bo'lgan har bir maydon tugmalar qatoriga aylanadi.
     Maydonning o'zi formada qoladi (yashirin) — server o'zgarishsiz
     ishlaydi.
     ================================================================== */

  function letterPicker(input) {
    var letters = (input.dataset.letters || "ABCD").split("");
    var kind = input.dataset.kind === "multi" ? "multi" : "single";

    var wrap = document.createElement("div");
    wrap.className = "choices cols-" + letters.length + (kind === "multi" ? " multi" : "");

    var current = (input.value || "").trim().toUpperCase();

    letters.forEach(function (letter) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "choice" + (current === letter ? " is-selected" : "");
      button.textContent = letter;
      button.addEventListener("click", function () {
        /* Tanlov «radio» kabi: qayta bosilsa — bekor qilinadi. */
        current = current === letter ? "" : letter;
        input.value = current;
        Array.prototype.forEach.call(wrap.children, function (item) {
          item.classList.toggle("is-selected", item.textContent === current);
        });
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      wrap.appendChild(button);
    });

    input.type = "hidden";
    input.parentNode.insertBefore(wrap, input);
  }

  function initLetterPickers() {
    var fields = document.querySelectorAll("input[data-letters]");
    Array.prototype.forEach.call(fields, letterPicker);
  }

  /* ==================================================================
     3. Ochiq javob maydonlari — varaqadagidek ko'rinish
     ================================================================== */

  function initOpenFields() {
    var fields = document.querySelectorAll(".answer-field input[data-ks-check]");
    if (!fields.length) { return; }

    var timers = {};

    function check(input) {
      var wrap = input.closest(".answer-field");
      var fx = wrap ? wrap.querySelector(".fx") : null;
      if (!fx) { return; }
      var value = input.value.trim();
      if (!value) { fx.textContent = ""; fx.className = "fx"; return; }
      validate(value).then(function (data) {
        var note = data.variants > 1 ? " · " + data.variants + " ta sinonim" : "";
        fx.textContent = "Tekshiruvda: " + data.pretty + note;
        fx.className = "fx ok";
      }).catch(function (error) {
        fx.textContent = error.message;
        fx.className = "fx err";
      });
    }

    Array.prototype.forEach.call(fields, function (input) {
      input.addEventListener("input", function () {
        if (timers[input.id]) { clearTimeout(timers[input.id]); }
        timers[input.id] = setTimeout(function () { check(input); }, 400);
      });
      if (input.value.trim()) { check(input); }
    });
  }

  function init() {
    initCreate();
    initLetterPickers();
    initOpenFields();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
