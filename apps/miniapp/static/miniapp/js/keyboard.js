/* ==========================================================================
   Telegram Mini App — matematik klaviatura mantiqi.

   Vazifalari:
     * tugmalar orqali ifodani faol maydonga kiritish;
     * kursor holatini boshqarish (funksiya qavslari ichiga o'tish);
     * serverda SymPy orqali ifodani jonli tekshirish;
     * yakuniy javobni `Telegram.WebApp.sendData()` orqali botga yuborish.
   ========================================================================== */

(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

  var body        = document.body;
  var apiUrl      = body.dataset.api || "";
  var questionId  = body.dataset.question || "";
  var examCode    = body.dataset.exam || "";
  var parts       = parseInt(body.dataset.parts || "2", 10);

  var inputA   = document.getElementById("answer-a");
  var inputB   = document.getElementById("answer-b");
  var hintA    = document.getElementById("hint-a");
  var hintB    = document.getElementById("hint-b");
  var fieldB   = document.getElementById("field-b");
  var preview  = document.getElementById("preview");
  var btnSend  = document.getElementById("btn-submit");
  var btnClear = document.getElementById("btn-clear");
  var btnBack  = document.getElementById("btn-backspace");

  var activeInput = inputA;

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

  /* ------------------------------------------------------- maydonni tanlash */

  function setActive(input) {
    activeInput = input;
    document.querySelectorAll(".field").forEach(function (field) {
      field.classList.toggle("is-active", field.contains(input));
    });
    input.focus({ preventScroll: true });
  }

  [inputA, inputB].forEach(function (input) {
    if (!input) { return; }
    input.addEventListener("focus", function () { setActive(input); });
    input.addEventListener("click", function () { setActive(input); });
    input.addEventListener("input", function () { scheduleCheck(); });
  });

  /* ------------------------------------------------------------- kiritish */

  function insert(text, caretShift) {
    if (!activeInput) { return; }
    var start = activeInput.selectionStart;
    var end = activeInput.selectionEnd;
    if (start === null || start === undefined) {
      start = activeInput.value.length;
      end = start;
    }
    var value = activeInput.value;
    activeInput.value = value.slice(0, start) + text + value.slice(end);

    var position = start + text.length + (caretShift || 0);
    position = Math.max(0, Math.min(position, activeInput.value.length));
    try {
      activeInput.setSelectionRange(position, position);
    } catch (err) { /* ba'zi brauzerlarda mavjud emas */ }

    activeInput.focus({ preventScroll: true });
    haptic("light");
    scheduleCheck();
  }

  function backspace() {
    if (!activeInput) { return; }
    var start = activeInput.selectionStart;
    var end = activeInput.selectionEnd;
    var value = activeInput.value;

    if (start === end) {
      if (start === 0) { return; }
      activeInput.value = value.slice(0, start - 1) + value.slice(end);
      start -= 1;
    } else {
      activeInput.value = value.slice(0, start) + value.slice(end);
    }
    try {
      activeInput.setSelectionRange(start, start);
    } catch (err) { /* ignore */ }
    activeInput.focus({ preventScroll: true });
    haptic("light");
    scheduleCheck();
  }

  function clearAll() {
    if (!activeInput) { return; }
    activeInput.value = "";
    activeInput.focus({ preventScroll: true });
    haptic("medium");
    scheduleCheck();
  }

  function haptic(style) {
    if (tg && tg.HapticFeedback && tg.HapticFeedback.impactOccurred) {
      try { tg.HapticFeedback.impactOccurred(style); } catch (err) { /* ignore */ }
    }
  }

  /* ------------------------------------------------------- tugmalar ulash */

  document.querySelectorAll(".key[data-insert]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      var text = button.getAttribute("data-insert") || "";
      var shift = parseInt(button.getAttribute("data-caret") || "0", 10);
      insert(text, isNaN(shift) ? 0 : shift);
    });
  });

  if (btnBack)  { btnBack.addEventListener("click", function (e) { e.preventDefault(); backspace(); }); }
  if (btnClear) { btnClear.addEventListener("click", function (e) { e.preventDefault(); clearAll(); }); }

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

  function runCheck() {
    var target = activeInput;
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

  function setPreview(text, state) {
    if (!preview) { return; }
    preview.textContent = text;
    preview.classList.remove("is-ok", "is-error");
    if (state) { preview.classList.add(state); }
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
      haptic("medium");
      submit();
    });
  }

  /* ------------------------------------------------------------ boshlanish */

  setActive(inputA);
  updateSubmitState();
  scheduleCheck();
})();
