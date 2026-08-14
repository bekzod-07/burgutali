/* ==========================================================================
   Telegram Mini App — alohida matematik klaviatura sahifasi.

   Klaviaturaning o'zi umumiy modulda (`static/mathpad/mathpad.js`), shuning
   uchun bu sahifada ham web ilova va boshqaruv panelidagi bilan **aynan bir
   xil** klaviatura chiqadi.

   Bu fayl faqat sahifaga xos qismni bajaradi:
     * javob maydonlarini klaviaturaga ulaydi;
     * serverda SymPy orqali ifodani jonli tekshiradi;
     * yakuniy javobni `Telegram.WebApp.sendData()` orqali botga yuboradi.
   ========================================================================== */

(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

  var body       = document.body;
  var apiUrl     = body.dataset.api || "";
  var questionId = body.dataset.question || "";
  var examCode   = body.dataset.exam || "";
  var parts      = parseInt(body.dataset.parts || "2", 10);

  var inputA  = document.getElementById("answer-a");
  var inputB  = document.getElementById("answer-b");
  var hintA   = document.getElementById("hint-a");
  var hintB   = document.getElementById("hint-b");
  var fieldB  = document.getElementById("field-b");
  var preview = document.getElementById("preview");
  var btnSend = document.getElementById("btn-submit");

  /* ------------------------------------------------------- Telegram sozlash */

  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tg.MainButton) { tg.MainButton.hide(); }
    } catch (err) { /* eski Telegram versiyalari */ }
  }

  if (parts < 2 && fieldB) {
    fieldB.classList.add("is-hidden");
  }

  /* ------------------------------------------------------------ klaviatura */

  window.MathPad.mount({
    inline: true,
    container: document.getElementById("keyboard-slot"),
    onEnter: function (input) {
      /* «⏎» — a) dan b) ga o'tadi, b) da esa javobni yuboradi. */
      if (parts >= 2 && input === inputA && inputB) {
        window.MathPad.open(inputB);
        return true;
      }
      submit();
      return true;
    }
  });

  var fields = parts >= 2 && inputB ? [inputA, inputB] : [inputA];
  fields.forEach(function (input) {
    if (!input) { return; }
    window.MathPad.bind(input, { label: input === inputB ? "b) javob" : "a) javob" });
    input.addEventListener("input", function () {
      scheduleCheck();
      updateSubmitState();
    });
    input.addEventListener("keyup", scheduleCheck);
  });

  /* ---------------------------------------------------- serverda tekshirish */

  var checkTimer = null;

  function scheduleCheck() {
    if (checkTimer) { clearTimeout(checkTimer); }
    checkTimer = setTimeout(runCheck, 350);
  }

  function setHint(element, text, state) {
    if (!element) { return; }
    element.textContent = text || "";
    element.classList.remove("is-ok", "is-error");
    if (state) { element.classList.add(state); }
  }

  function setPreview(text, state) {
    if (!preview) { return; }
    preview.textContent = text;
    preview.classList.remove("is-ok", "is-error");
    if (state) { preview.classList.add(state); }
  }

  function runCheck() {
    var target = window.MathPad.active() || inputA;
    var hint = target === inputB ? hintB : hintA;
    var value = (target && target.value ? target.value : "").trim();

    if (!value) {
      setHint(hint, "");
      setPreview("Javobingizni kiriting", null);
      updateSubmitState();
      return;
    }
    if (!apiUrl) {
      setPreview(value, null);
      updateSubmitState();
      return;
    }

    fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expr: value,
        initData: tg ? (tg.initData || "") : ""
      })
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.ok) {
          var extra = data.value ? " ≈ " + data.value : "";
          setHint(hint, data.pretty + extra, "is-ok");
          setPreview(data.pretty + extra, "is-ok");
        } else {
          setHint(hint, (data && data.error) || "Ifoda noto‘g‘ri", "is-error");
          setPreview((data && data.error) || "Ifoda noto‘g‘ri", "is-error");
        }
        updateSubmitState();
      })
      .catch(function () {
        setHint(hint, "");
        setPreview(value, null);
        updateSubmitState();
      });
  }

  function updateSubmitState() {
    if (!btnSend) { return; }
    var hasA = inputA && inputA.value.trim().length > 0;
    var hasB = inputB && inputB.value.trim().length > 0;
    btnSend.disabled = parts >= 2 ? !(hasA || hasB) : !hasA;
  }

  /* -------------------------------------------------------------- yuborish */

  function submit() {
    var payload = {
      type: "math_answer",
      exam: examCode,
      q: questionId ? parseInt(questionId, 10) : null,
      a: inputA ? inputA.value.trim() : "",
      b: (parts >= 2 && inputB) ? inputB.value.trim() : ""
    };

    if (!payload.a && !payload.b) {
      setPreview("Kamida bitta javob kiriting", "is-error");
      return;
    }

    var text = JSON.stringify(payload);
    if (tg && tg.sendData) {
      try {
        tg.sendData(text);
        return;
      } catch (err) { /* pastdagi zaxira variant */ }
    }
    setPreview("Telegram ilovasi orqali oching", "is-error");
  }

  if (btnSend) {
    btnSend.addEventListener("click", function (event) {
      event.preventDefault();
      submit();
    });
  }

  /* ------------------------------------------------------------ boshlanish */

  window.MathPad.open(inputA);
  updateSubmitState();
  scheduleCheck();
})();
