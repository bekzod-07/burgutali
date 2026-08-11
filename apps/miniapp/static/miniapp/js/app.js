/* ==========================================================================
   Rasch Math — Telegram Mini App
   --------------------------------------------------------------------------
   Bir sahifali ilova: barcha ekranlar shu faylda chiziladi, ma'lumot
   /app/api/ dan olinadi. Autentifikatsiya Telegram initData imzosi orqali.
   Emoji ishlatilmaydi — barcha belgilar SVG ikonkalar.
   ========================================================================== */

(function () {
  "use strict";

  var tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
  var API = "/app/api/";
  var body = document.body;

  var DEBUG_USER = new URLSearchParams(location.search).get("debug_user") || "";

  /* Ilova faqat Telegram ichida ishlaydi — brauzerda ochilsa botga yo'naltiramiz. */
  if (!(tg && tg.initData) && !DEBUG_USER) {
    location.replace("https://t.me/" + (body.dataset.bot || ""));
    return;
  }

  /* =====================================================================
     Holat
     ===================================================================== */

  var state = {
    user: null,
    boot: null,
    view: "home",
    params: {},
    stack: [],
    attempt: null,      // {attempt, exam, questions, editable}
    activeField: "",    // "<savol tartibi>-<a|b>" — klaviatura shu maydonga yozadi
    busy: false
  };

  var el = {
    screen: document.getElementById("screen"),
    title: document.getElementById("app-title"),
    subtitle: document.getElementById("app-subtitle"),
    back: document.getElementById("btn-back"),
    refresh: document.getElementById("btn-refresh"),
    logout: document.getElementById("btn-logout"),
    tabbar: document.getElementById("tabbar"),
    toast: document.getElementById("toast"),
    modal: document.getElementById("modal"),
    modalTitle: document.getElementById("modal-title"),
    modalBody: document.getElementById("modal-body"),
    modalOk: document.getElementById("modal-ok"),
    modalCancel: document.getElementById("modal-cancel")
  };

  /* =====================================================================
     Yordamchilar
     ===================================================================== */

  function esc(value) {
    if (value === null || value === undefined) { return ""; }
    return String(value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function ic(name, cls) {
    return '<svg class="icon' + (cls ? " " + cls : "") + '"><use href="#i-' + name + '"></use></svg>';
  }

  function haptic(kind) {
    if (!tg || !tg.HapticFeedback) { return; }
    try {
      if (kind === "ok") { tg.HapticFeedback.notificationOccurred("success"); }
      else if (kind === "err") { tg.HapticFeedback.notificationOccurred("error"); }
      else { tg.HapticFeedback.impactOccurred(kind || "light"); }
    } catch (e) { /* eski versiyalar */ }
  }

  var toastTimer = null;
  function toast(message, isError) {
    el.toast.textContent = message;
    el.toast.classList.toggle("is-error", !!isError);
    el.toast.hidden = false;
    if (toastTimer) { clearTimeout(toastTimer); }
    toastTimer = setTimeout(function () { el.toast.hidden = true; }, 2600);
    haptic(isError ? "err" : "ok");
  }

  var modalResolve = null;
  function confirmDialog(title, html, okText, okClass) {
    el.modalTitle.textContent = title;
    el.modalBody.innerHTML = html;
    el.modalOk.textContent = okText || "Tasdiqlash";
    el.modalOk.className = "btn " + (okClass || "btn-danger");
    el.modal.hidden = false;
    return new Promise(function (resolve) { modalResolve = resolve; });
  }

  function closeModal(value) {
    el.modal.hidden = true;
    if (modalResolve) { modalResolve(value); modalResolve = null; }
  }

  el.modalOk.addEventListener("click", function () { closeModal(true); });
  el.modalCancel.addEventListener("click", function () { closeModal(false); });
  el.modal.addEventListener("click", function (e) {
    if (e.target === el.modal) { closeModal(false); }
  });

  /* =====================================================================
     API
     ===================================================================== */

  function api(path, options) {
    options = options || {};
    var headers = {
      "Content-Type": "application/json",
      /* Sessiyali (brauzer) kirishda server o'zgartiruvchi so'rovlarni
         faqat shu sarlavha bilan qabul qiladi (CSRF himoyasi). */
      "X-Requested-With": "XMLHttpRequest"
    };
    if (tg && tg.initData) { headers["X-Telegram-Init-Data"] = tg.initData; }
    if (DEBUG_USER) { headers["X-Debug-User"] = DEBUG_USER; }

    return fetch(API + path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    }).then(function (response) {
      return response.json().catch(function () {
        return { ok: false, error: "Server javobini o'qib bo'lmadi." };
      }).then(function (data) {
        if (!response.ok || !data.ok) {
          var error = new Error(data.error || "Xatolik yuz berdi.");
          error.payload = data;
          error.status = response.status;
          throw error;
        }
        return data;
      });
    });
  }

  function loading() {
    el.screen.innerHTML = '<div class="loader"><span class="spinner"></span>Yuklanmoqda...</div>';
  }

  function showError(message, retryView) {
    el.screen.innerHTML =
      '<div class="empty">' + ic("alert", "icon-xl") +
      "<b>Xatolik</b><p>" + esc(message) + "</p>" +
      '<button class="btn btn-ghost" data-act="reload">Qayta urinish</button></div>';
  }

  /* =====================================================================
     Navigatsiya
     ===================================================================== */

  var TABS = ["home", "exams", "results", "certificates", "my-exams"];

  var TITLES = {
    "home": ["Rasch Math", "Matematik testlar platformasi"],
    "exams": ["Testlar", "Test kodi orqali kirish"],
    "exam": ["Test", ""],
    "attempt": ["Test topshirish", ""],
    "result": ["Natija", ""],
    "results": ["Natijalarim", "Topshirgan testlaringiz"],
    "certificates": ["Sertifikatlar", "Berilgan sertifikatlar"],
    "my-exams": ["Testlarim", "Siz yaratgan testlar"],
    "create": ["Yangi test", "Test yaratish"],
    "manage": ["Boshqaruv", ""],
    "rating": ["Reyting", ""]
  };

  function setHeader(view, subtitle) {
    var info = TITLES[view] || ["Rasch Math", ""];
    el.title.textContent = info[0];
    el.subtitle.textContent = subtitle !== undefined ? subtitle : info[1];
    el.back.hidden = state.stack.length === 0;

    Array.prototype.forEach.call(el.tabbar.querySelectorAll(".tab"), function (tab) {
      tab.classList.toggle("is-active", tab.dataset.tab === view);
    });

    if (tg && tg.BackButton) {
      try {
        if (state.stack.length) { tg.BackButton.show(); } else { tg.BackButton.hide(); }
      } catch (e) { /* ignore */ }
    }
  }

  function go(view, params, replace) {
    if (!replace && state.view) {
      state.stack.push({ view: state.view, params: state.params });
      if (state.stack.length > 20) { state.stack.shift(); }
    }
    if (TABS.indexOf(view) !== -1) { state.stack = []; }
    state.view = view;
    state.params = params || {};
    render();
  }

  function back() {
    var previous = state.stack.pop();
    if (!previous) { go("home", {}, true); return; }
    state.view = previous.view;
    state.params = previous.params;
    render();
  }

  el.back.addEventListener("click", back);
  el.refresh.addEventListener("click", function () { render(); });

  el.tabbar.addEventListener("click", function (e) {
    var tab = e.target.closest(".tab");
    if (!tab) { return; }
    state.stack = [];
    go(tab.dataset.tab, {}, true);
    haptic("light");
  });

  /* =====================================================================
     Ekranlarni chizish
     ===================================================================== */

  function render() {
    setHeader(state.view);
    loading();
    var view = state.view;

    /* Test topshirish ekranida pastki menyu o'rniga yopishqoq
       «Yakunlash» paneli ko'rsatiladi. */
    body.classList.toggle("attempt-open", view === "attempt");

    if (view === "home") { return viewHome(); }
    if (view === "exams") { return viewExams(); }
    if (view === "exam") { return viewExam(); }
    if (view === "attempt") { return viewAttempt(); }
    if (view === "result") { return viewResult(); }
    if (view === "results") { return viewResults(); }
    if (view === "certificates") { return viewCertificates(); }
    if (view === "my-exams") { return viewMyExams(); }
    if (view === "create") { return viewCreate(); }
    if (view === "manage") { return viewManage(); }
    if (view === "rating") { return viewRating(); }
    return viewHome();
  }

  /* ------------------------------------------------------------ 1. Home */

  function viewHome() {
    api("boshlash/").then(function (data) {
      state.boot = data;
      state.user = data.user;

      var drafts = data.drafts || [];
      var html = "";

      html += '<div class="hero"><div class="hero-row">' +
        '<div class="avatar">' + ic("user") + "</div><div>" +
        "<h2>" + esc(data.user.full_name) + "</h2>" +
        "<p>" + (data.user.is_admin ? "Administrator" : "Ishtirokchi") + "</p>" +
        "</div></div></div>";

      html += '<div class="stats">' +
        '<div class="stat"><b>' + (data.results || []).length + "</b><span>Natija</span></div>" +
        '<div class="stat gold"><b>' + (data.certificates || []).length + "</b><span>Sertifikat</span></div>" +
        '<div class="stat green"><b>' + (data.my_exams || []).length + "</b><span>Testim</span></div>" +
        "</div>";

      if (drafts.length) {
        html += '<div class="section-title">' + ic("hourglass", "icon-sm") + "Tugallanmagan test</div>";
        drafts.forEach(function (draft) {
          html += '<button class="item" data-act="open-attempt" data-id="' + draft.attempt_id + '">' +
            '<div class="ico">' + ic("play") + "</div><div class=\"body\"><b>" + esc(draft.exam_title) + "</b>" +
            "<small>" + draft.current_order + " / " + draft.question_count + "-savolda to‘xtagansiz</small></div>" +
            '<span class="arrow">' + ic("chevron-right") + "</span></button>";
        });
      }

      html += '<div class="section-title">' + ic("grid", "icon-sm") + "Tez amallar</div>";
      html += '<div class="quick-grid">' +
        '<button class="quick" data-act="tab" data-tab="exams"><div class="ico">' + ic("book") +
        "</div><b>Testda qatnashish</b><span>Test kodini kiritib boshlang</span></button>" +

        '<button class="quick" data-act="go" data-view="create"><div class="ico green">' + ic("plus") +
        "</div><b>Test yaratish</b><span>O‘z testingizni oching</span></button>" +

        '<button class="quick" data-act="tab" data-tab="results"><div class="ico purple">' + ic("chart") +
        "</div><b>Natijalarim</b><span>Ball, daraja, javoblar tahlili</span></button>" +

        '<button class="quick" data-act="tab" data-tab="certificates"><div class="ico gold">' + ic("award") +
        "</div><b>Sertifikatlar</b><span>PDF yuklab olish</span></button>" +
        "</div>";

      // Testlar ro'yxati ishtirokchilarga ko'rsatilmaydi — testga faqat
      // tashkilotchi bergan kod orqali kiriladi. Ro'yxatni faqat admin ko'radi.
      var exams = data.exams || [];
      if (exams.length) {
        html += '<div class="section-title">' + ic("book", "icon-sm") + "Faol testlar (admin)</div>";
        exams.slice(0, 4).forEach(function (exam) { html += examItem(exam); });
        if (exams.length > 4) {
          html += '<button class="btn btn-ghost" data-act="tab" data-tab="exams">Barchasi (' + exams.length + ")</button>";
        }
      }

      el.screen.innerHTML = html;
    }).catch(function (error) { handleError(error); });
  }

  /* ----------------------------------------------------------- 2. Exams */

  function examItem(exam) {
    var badge = exam.requires_code
      ? '<span class="badge badge-gold">' + ic("key", "icon-sm") + "ID kod</span>"
      : (exam.uses_rasch ? '<span class="badge badge-purple">RASH</span>'
                         : '<span class="badge badge-accent">Oddiy</span>');
    return '<button class="item" data-act="open-exam" data-code="' + esc(exam.code) + '">' +
      '<div class="ico">' + ic("file") + "</div>" +
      '<div class="body"><b>' + esc(exam.title) + "</b>" +
      '<small><span class="code-pill">' + esc(exam.code) + "</span> · " + exam.question_count + " ta savol</small>" +
      '<div class="chips">' + badge +
      (exam.certificate ? '<span class="badge badge-gold">Sertifikat</span>' : "") +
      "</div></div>" +
      '<span class="arrow">' + ic("chevron-right") + "</span></button>";
  }

  function viewExams() {
    api("testlar/").then(function (data) {
      var html = "";
      html += '<div class="card-flat"><div class="card-head">' + ic("hash") +
        "<h2>Test kodi bo‘yicha kirish</h2></div>" +
        '<div class="field"><input class="input mono" id="exam-code" inputmode="numeric" ' +
        'placeholder="32" autocomplete="off"></div>' +
        '<p class="muted small">Kodni testni o‘tkazayotgan tashkilotchidan oling.</p>' +
        '<button class="btn" data-act="find-exam">' + ic("search") + "Testni topish</button></div>";

      // Ro'yxat faqat adminga ko'rinadi (`list_visible`).
      var exams = data.list_visible ? (data.exams || []) : [];
      if (data.list_visible) {
        html += '<div class="section-title">' + ic("book", "icon-sm") + "Faol testlar (admin)</div>";
        if (!exams.length) {
          html += '<div class="empty">' + ic("book", "icon-xl") +
            "<b>Faol testlar yo‘q</b></div>";
        } else {
          exams.forEach(function (exam) { html += examItem(exam); });
        }
      }
      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  /* ------------------------------------------------------------ 3. Exam */

  function viewExam() {
    var code = state.params.code;
    api("test/" + encodeURIComponent(code) + "/").then(function (data) {
      var exam = data.exam;
      setHeader("exam", exam.title);

      var html = "";
      html += '<div class="card"><div class="card-head">' + ic("file") +
        "<h2>" + esc(exam.title) + "</h2></div>" +
        '<div class="kv-list">' +
        kv("Test kodi", '<span class="code-pill">' + esc(exam.code) + "</span>") +
        kv("Turi", esc(exam.type_label)) +
        kv("Savollar", exam.question_count + " ta") +
        kv("Maksimal ball", exam.max_raw_score) +
        kv("Qatnashganlar", (exam.participants || 0) + " ta") +
        kv("Tugash vaqti", esc(exam.ends_at_human)) +
        (exam.certificate ? kv("Sertifikat", "beriladi") : "") +
        "</div></div>";

      if (exam.description) {
        html += '<div class="card-flat small">' + esc(exam.description) + "</div>";
      }

      if (exam.requires_code) {
        html += '<div class="alert alert-warn">' + ic("key") +
          "<div>Bu testda qatnashish uchun bir martalik <b>ID kod</b> kerak. " +
          "Kod administratordan olinadi va faqat bir marta ishlaydi.</div></div>";
      }

      if (data.draft_attempt_id) {
        html += '<button class="btn btn-green" data-act="open-attempt" data-id="' + data.draft_attempt_id + '">' +
          ic("play") + "Testni davom ettirish</button>";
      } else if (data.can_participate) {
        if (exam.requires_code) {
          html += '<div class="field"><label>ID kod</label>' +
            '<input class="input mono" id="access-code" placeholder="R7K4-8251" autocomplete="off"></div>';
        }
        html += '<button class="btn" data-act="start-exam" data-code="' + esc(exam.code) + '">' +
          ic("play") + "Testni boshlash</button>";
      } else {
        html += '<div class="alert alert-error">' + ic("info") + "<div>" + esc(data.reason) + "</div></div>";
        if (data.my_attempt_id) {
          html += '<button class="btn btn-ghost" data-act="open-result" data-id="' + data.my_attempt_id + '">' +
            ic("chart") + "Natijamni ko‘rish</button>";
        }
      }

      if (exam.show_rating) {
        html += '<button class="btn btn-ghost" data-act="open-rating" data-code="' + esc(exam.code) + '">' +
          ic("trophy") + "Reyting</button>";
      }
      if (data.can_manage) {
        html += '<button class="btn btn-outline" data-act="open-manage" data-code="' + esc(exam.code) + '">' +
          ic("gear") + "Testni boshqarish</button>";
      }

      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  function kv(key, value) {
    return '<div class="kv"><span class="k">' + key + '</span><span class="v">' + value + "</span></div>";
  }

  /* --------------------------------------------------------- 4. Attempt */

  function viewAttempt() {
    var id = state.params.id;
    api("urinish/" + id + "/").then(function (data) {
      state.attempt = data;
      if (!data.editable) { return go("result", { id: id }, true); }
      renderSheet();
    }).catch(handleError);
  }

  function answeredCount() {
    return state.attempt.questions.filter(function (q) { return q.answered; }).length;
  }

  function questionByOrder(order) {
    var list = state.attempt.questions;
    for (var i = 0; i < list.length; i += 1) {
      if (list[i].order === order) { return list[i]; }
    }
    return null;
  }

  /*
     Javoblar varaqasi — barcha savollar bitta oynada.
     Foydalanuvchi varaqni pastga aylantirib istalgan savolga javob beradi;
     yuqoridagi palitra tanlangan savolga sakraydi. Har bir javob darhol
     serverga saqlanadi, sahifa esa qayta chizilmaydi — shu sababli varaq
     joyidan siljimaydi.
  */
  /* Bo'lim sarlavhalari — savol turi o'zgargan joyda ko'rsatiladi. */
  var SECTION_LABELS = {
    single: "Yopiq savollar — bitta javobni tanlang",
    multi: "Ko‘p javobli savollar — bir yoki bir nechta javob belgilanadi",
    open: "Ochiq javoblar — a) va b) qismlarni kiriting"
  };

  function renderSheet() {
    var data = state.attempt;
    var questions = data.questions;
    var total = questions.length;
    var done = answeredCount();
    var hasOpen = questions.some(function (q) { return q.kind === "open"; });

    setHeader("attempt", data.exam.title);

    var html = "";

    html += '<div class="sheet-top">' +
      '<div class="q-progress"><div class="bar"><span style="width:' +
      (total ? Math.round(done / total * 100) : 0) + '%"></span></div>' +
      '<div class="count">' + done + " / " + total + "</div></div>" +
      '<div class="palette">';
    questions.forEach(function (q) {
      html += '<button class="' + (q.answered ? "is-answered" : "") +
        '" data-act="jump" data-order="' + q.order + '">' + q.order + "</button>";
    });
    html += "</div></div>";

    // Ketma-ket bir xil turdagi savollar bitta guruhga yig'iladi.
    var groups = [];
    questions.forEach(function (q) {
      var last = groups[groups.length - 1];
      if (!last || last.kind !== q.kind) {
        groups.push({ kind: q.kind, from: q.order, to: q.order, items: [q] });
      } else {
        last.to = q.order;
        last.items.push(q);
      }
    });

    html += '<div class="sheet">';
    groups.forEach(function (group) {
      if (groups.length > 1) {
        html += '<div class="q-section kind-' + group.kind + '"><b>' +
          group.from + "–" + group.to + "</b><span>" +
          (SECTION_LABELS[group.kind] || "") + "</span></div>";
      }
      group.items.forEach(function (q) { html += questionBlock(q); });
    });
    html += "</div>";

    html += '<button class="btn btn-ghost" data-act="leave">' +
      ic("arrow-left") + "Keyinroq davom ettirish</button>";

    html += '<div class="finish-bar"><button class="btn" data-act="finish">' +
      ic("check-circle") + "Yakunlash va yuborish</button></div>";

    if (hasOpen) { html += renderMathPad(); }

    el.screen.innerHTML = html;
    window.scrollTo(0, 0);

    if (hasOpen) { bindOpenFields(); }
  }

  function questionBlock(question) {
    var html = '<section class="qitem kind-' + question.kind +
      (question.answered ? " is-answered" : "") +
      '" id="q-' + question.order + '" data-order="' + question.order + '">' +
      '<div class="qhead"><span class="qno">' + question.order + "</span>" +
      (question.kind === "multi"
        ? '<span class="qtag">bir nechta javob belgilash mumkin</span>' : "") +
      (question.kind === "open"
        ? '<span class="qtag">a) va b) qismlariga javob kiriting</span>' : "") +
      "</div>";

    if (question.text) { html += '<p class="q-text">' + esc(question.text) + "</p>"; }

    if (question.kind === "single" || question.kind === "multi") {
      html += renderChoices(question);
    } else {
      html += renderOpenFields(question);
      html += '<p class="q-hint">Maydonni bosing — matematik klaviatura ochiladi. ' +
        '<span class="mono">1/2</span>, <span class="mono">0.5</span>, ' +
        '<span class="mono">sqrt(2)</span>, <span class="mono">pi/6</span> ' +
        "ko‘rinishlari qabul qilinadi.</p>";
    }
    html += "</section>";
    return html;
  }

  /*
     Variantlar to'liq kenglikdagi qatorda joylashadi: A–D (bitta javob,
     ko'k) yoki A–F (ko'p javob, sariq-olov). Tanlangan tugma to'liq
     bo'yaladi — video namunadagi ko'rinish.
  */
  function renderChoices(question) {
    var selected = (question.answer.selected || "").split("");
    var isMulti = question.kind === "multi";
    var html = '<div class="choices cols-' + question.choices.length +
      (isMulti ? " multi" : "") + '">';
    question.choices.forEach(function (letter) {
      var isOn = selected.indexOf(letter) !== -1;
      html += '<button class="choice' + (isOn ? " is-selected" : "") +
        '" data-act="choose" data-order="' + question.order + '" data-letter="' + letter + '">' +
        letter + "</button>";
    });
    html += "</div>";
    return html;
  }

  function renderOpenFields(question) {
    var parts = question.parts >= 2;
    var html = '<div class="answer-fields">';
    html += openField(question.order, "a", parts ? "a) javob" : "Javob", question.answer.text_a);
    if (parts) { html += openField(question.order, "b", "b) javob", question.answer.text_b); }
    html += "</div>";
    return html;
  }

  function openField(order, key, label, value) {
    var id = order + "-" + key;
    return '<div class="answer-field" data-field="' + id + '">' +
      "<label>" + label + "</label>" +
      '<input type="text" inputmode="none" autocomplete="off" spellcheck="false" ' +
      'data-order="' + order + '" data-part="' + key + '" ' +
      'id="ans-' + id + '" value="' + esc(value || "") + '" placeholder="masalan: 1/2">' +
      '<div class="fx" id="fx-' + id + '"></div></div>';
  }

  var MATH_KEYS = [
    { title: "Funksiyalar", rows: [
      [["a⁄b", "/", 0], ["√", "sqrt()", -1], ["x²", "^2", 0], ["xⁿ", "^", 0]],
      [["π", "pi", 0], ["e", "e", 0], ["|x|", "abs()", -1], ["∛", "root(,3)", -3]],
      [["sin", "sin()", -1], ["cos", "cos()", -1], ["tg", "tg()", -1], ["ctg", "ctg()", -1]],
      [["ln", "ln()", -1], ["log", "log(,10)", -4], ["log₂", "log(,2)", -3], ["n!", "!", 0]]
    ]},
    { title: "Taqqoslash va qavslar", rows: [
      [["≤", "≤", 0], ["≥", "≥", 0], ["≠", "≠", 0], ["=", "=", 0], ["(", "(", 0], [")", ")", 0]]
    ]}
  ];

  var NUM_KEYS = [
    ["7", "7"], ["8", "8"], ["9", "9"], ["÷", "÷"],
    ["4", "4"], ["5", "5"], ["6", "6"], ["×", "×"],
    ["1", "1"], ["2", "2"], ["3", "3"], ["−", "−"],
    ["0", "0"], [",", "."], ["x", "x"], ["+", "+"]
  ];

  /*
     Klaviatura varaqning pastida turadi va ochiq javob maydoniga
     bosilgandagina ochiladi — shu sababli u barcha savollar uchun bitta
     nusxada bo'ladi va varaqni uzaytirmaydi.
  */
  function renderMathPad() {
    var html = '<div class="mathpad floating" id="mathpad">' +
      '<div class="mathpad-head"><span id="mathpad-label">Javob</span>' +
      '<button class="mathpad-close" data-act="mclose">Yopish</button></div>';
    MATH_KEYS.forEach(function (group) {
      html += '<div class="group-title">' + group.title + "</div>";
      group.rows.forEach(function (row) {
        html += '<div class="row">';
        row.forEach(function (key) {
          html += '<button class="mkey' + (group.title.indexOf("Taqqos") === 0 ? " op" : "") +
            '" data-act="mkey" data-ins="' + esc(key[1]) + '" data-caret="' + key[2] + '">' +
            esc(key[0]) + "</button>";
        });
        html += "</div>";
      });
    });

    html += '<div class="group-title">Raqamlar va amallar</div><div class="pad">';
    NUM_KEYS.forEach(function (key) {
      var isOp = "÷×−+".indexOf(key[0]) !== -1;
      html += '<button class="mkey ' + (isOp ? "op" : "num") + '" data-act="mkey" data-ins="' +
        esc(key[1]) + '" data-caret="0">' + esc(key[0]) + "</button>";
    });
    html += "</div>";

    html += '<div class="row" style="margin-top:5px">' +
      '<button class="mkey clr" data-act="mclear">Tozalash</button>' +
      '<button class="mkey del" data-act="mdel">' + ic("chevron-left") + " o‘chirish</button></div>";

    html += "</div>";
    return html;
  }

  var checkTimers = {};

  function bindOpenFields() {
    Array.prototype.forEach.call(
      el.screen.querySelectorAll(".answer-field input"),
      function (input) {
        var id = input.dataset.order + "-" + input.dataset.part;
        input.addEventListener("focus", function () { openMathPad(id); });
        input.addEventListener("click", function () { openMathPad(id); });
        input.addEventListener("input", function () {
          scheduleCheck(id);
          saveOpenAnswer(parseInt(input.dataset.order, 10));
        });
        if (input.value.trim()) { scheduleCheck(id); }
      }
    );
  }

  function openMathPad(id) {
    state.activeField = id;
    Array.prototype.forEach.call(el.screen.querySelectorAll(".answer-field"), function (field) {
      field.classList.toggle("is-active", field.dataset.field === id);
    });

    var pad = document.getElementById("mathpad");
    if (!pad) { return; }
    pad.classList.add("is-open");
    body.classList.add("pad-open");

    var label = document.getElementById("mathpad-label");
    if (label) {
      var parts = id.split("-");
      label.textContent = parts[0] + "-savol · " + parts[1] + ") javob";
    }
  }

  function closeMathPad() {
    var pad = document.getElementById("mathpad");
    if (pad) { pad.classList.remove("is-open"); }
    body.classList.remove("pad-open");
    Array.prototype.forEach.call(el.screen.querySelectorAll(".answer-field"), function (field) {
      field.classList.remove("is-active");
    });
  }

  function scheduleCheck(id) {
    if (checkTimers[id]) { clearTimeout(checkTimers[id]); }
    checkTimers[id] = setTimeout(function () { runCheck(id); }, 400);
  }

  function runCheck(id) {
    var input = document.getElementById("ans-" + id);
    var fx = document.getElementById("fx-" + id);
    if (!input || !fx) { return; }
    var value = input.value.trim();
    if (!value) { fx.textContent = ""; fx.className = "fx"; return; }

    api("ifoda/", { method: "POST", body: { expr: value } }).then(function (data) {
      fx.textContent = data.pretty + (data.value ? " ≈ " + data.value : "");
      fx.className = "fx ok";
    }).catch(function (error) {
      fx.textContent = error.message;
      fx.className = "fx err";
    });
  }

  function activeInput() {
    return state.activeField ? document.getElementById("ans-" + state.activeField) : null;
  }

  function insertText(text, caretShift) {
    var input = activeInput();
    if (!input) { toast("Avval javob maydonini tanlang.", true); return; }
    var start = input.selectionStart;
    var end = input.selectionEnd;
    if (start === null || start === undefined) { start = input.value.length; end = start; }
    input.value = input.value.slice(0, start) + text + input.value.slice(end);
    var position = Math.max(0, Math.min(start + text.length + (caretShift || 0), input.value.length));
    try { input.setSelectionRange(position, position); } catch (e) { /* ignore */ }
    input.focus({ preventScroll: true });
    haptic("light");
    scheduleCheck(state.activeField);
    saveOpenAnswer(parseInt(input.dataset.order, 10));
  }

  function backspace() {
    var input = activeInput();
    if (!input) { return; }
    var start = input.selectionStart, end = input.selectionEnd;
    if (start === end) {
      if (start === 0) { return; }
      input.value = input.value.slice(0, start - 1) + input.value.slice(end);
      start -= 1;
    } else {
      input.value = input.value.slice(0, start) + input.value.slice(end);
    }
    try { input.setSelectionRange(start, start); } catch (e) { /* ignore */ }
    input.focus({ preventScroll: true });
    haptic("light");
    scheduleCheck(state.activeField);
    saveOpenAnswer(parseInt(input.dataset.order, 10));
  }

  var saveTimers = {};
  function saveOpenAnswer(order) {
    var question = questionByOrder(order);
    if (!question) { return; }
    if (saveTimers[order]) { clearTimeout(saveTimers[order]); }
    saveTimers[order] = setTimeout(function () {
      var a = document.getElementById("ans-" + order + "-a");
      var b = document.getElementById("ans-" + order + "-b");
      var textA = a ? a.value.trim() : "";
      var textB = b ? b.value.trim() : "";
      question.answer.text_a = textA;
      question.answer.text_b = textB;
      question.answered = !!(textA || textB);
      markAnswered(order, question.answered);
      updatePalette();
      api("urinish/" + state.attempt.attempt.id + "/javob/", {
        method: "POST",
        body: { order: order, text_a: textA, text_b: textB }
      }).catch(function (error) { toast(error.message, true); });
    }, 600);
  }

  function markAnswered(order, answered) {
    var block = document.getElementById("q-" + order);
    if (block) { block.classList.toggle("is-answered", !!answered); }
  }

  function updatePalette() {
    state.attempt.questions.forEach(function (q) {
      var button = el.screen.querySelector('.palette button[data-order="' + q.order + '"]');
      if (button) { button.classList.toggle("is-answered", !!q.answered); }
    });
    var done = answeredCount();
    var total = state.attempt.questions.length;
    var bar = el.screen.querySelector(".q-progress .bar span");
    var count = el.screen.querySelector(".q-progress .count");
    if (bar) { bar.style.width = Math.round(done / total * 100) + "%"; }
    if (count) { count.textContent = done + " / " + total; }
  }

  /*
     Variantni belgilash. Bitta javobli savolda tanlov «radio» kabi ishlaydi:
     ikkinchi variant bosilsa, birinchisi avtomatik olib tashlanadi.
     33–35 kabi ko'p javobli savollarda esa bir nechta variant belgilanadi.
  */
  function chooseLetter(order, letter) {
    var question = questionByOrder(order);
    if (!question) { return; }
    var current = (question.answer.selected || "").split("").filter(Boolean);

    if (question.kind === "single") {
      current = current[0] === letter ? [] : [letter];
    } else {
      var position = current.indexOf(letter);
      if (position === -1) { current.push(letter); } else { current.splice(position, 1); }
      current.sort();
    }

    question.answer.selected = current.join("");
    question.answered = current.length > 0;
    haptic("light");

    // Varaqni qayta chizmaymiz — faqat shu savolning tugmalarini yangilaymiz.
    var block = document.getElementById("q-" + order);
    if (block) {
      Array.prototype.forEach.call(block.querySelectorAll(".choice"), function (button) {
        button.classList.toggle(
          "is-selected", current.indexOf(button.dataset.letter) !== -1
        );
      });
    }
    markAnswered(order, question.answered);
    updatePalette();

    api("urinish/" + state.attempt.attempt.id + "/javob/", {
      method: "POST",
      body: { order: order, selected: question.answer.selected }
    }).catch(function (error) { toast(error.message, true); });
  }

  function jumpToQuestion(order) {
    var block = document.getElementById("q-" + order);
    if (!block) { return; }
    block.scrollIntoView({ behavior: "smooth", block: "start" });
    block.classList.add("is-target");
    setTimeout(function () { block.classList.remove("is-target"); }, 1200);
  }

  function finishAttempt() {
    var total = state.attempt.questions.length;
    var done = answeredCount();
    var missing = state.attempt.questions
      .filter(function (q) { return !q.answered; })
      .map(function (q) { return q.order; });

    var html = "Javob berilgan: <b>" + done + " / " + total + "</b>.";
    if (missing.length) {
      html += '<br><br><span class="warn-text">Quyidagi savollarni javobsiz ' +
        "qoldiryapsiz:</span><br><b>" + missing.slice(0, 45).join(", ") + "</b>" +
        (missing.length > 45 ? " ..." : "");
    }
    html += "<br><br>Yuborilgandan keyin javoblarni <b>o‘zgartirib bo‘lmaydi</b>.";

    confirmDialog(
      missing.length ? "Javobsiz savollar bor" : "Javoblarni yuborish",
      html,
      "Ha, yakunlansin",
      "btn-green"
    ).then(function (ok) {
      if (!ok) { return; }
      closeMathPad();
      loading();
      api("urinish/" + state.attempt.attempt.id + "/yuborish/", { method: "POST" })
        .then(function (data) {
          toast("Javoblaringiz qabul qilindi.");
          state.stack = [];
          go("result", { id: data.attempt.id }, true);
        })
        .catch(function (error) { toast(error.message, true); renderSheet(); });
    });
  }

  /* ---------------------------------------------------------- 5. Result */

  function viewResult() {
    var id = state.params.id;
    api("urinish/" + id + "/natija/").then(function (data) {
      var attempt = data.attempt;
      setHeader("result", attempt.exam_title);

      var html = "";

      if (data.pending) {
        html += '<div class="alert alert-warn">' + ic("hourglass") +
          "<div>Natijalar hali e’lon qilinmagan. Tashkilotchi natijalarni " +
          "tasdiqlagandan so‘ng bu yerda ko‘rinadi.</div></div>";
      }

      if (!data.visible) {
        html += '<div class="alert alert-info">' + ic("eye-off") +
          "<div>Bu testda natijalar qatnashchilarga ko‘rsatilmaydi.</div></div>";
        html += '<button class="btn btn-ghost" data-act="tab" data-tab="results">Natijalarim</button>';
        el.screen.innerHTML = html;
        return;
      }

      if (attempt.uses_rasch) {
        html += '<div class="result-hero">' +
          '<div class="lbl">RASH balli</div>' +
          '<div class="big">' + esc(attempt.ball) + "</div>" +
          (attempt.grade ? '<div class="grade">' + esc(attempt.grade) + "</div>" : "") +
          "</div>";
      } else {
        html += '<div class="result-hero">' +
          '<div class="lbl">To‘g‘ri javoblar</div>' +
          '<div class="big">' + attempt.correct + " / " + attempt.max_raw_score + "</div>" +
          '<div class="grade">' + attempt.percent + "%</div></div>";
      }

      html += '<div class="card"><div class="kv-list">' +
        kv("Test", esc(attempt.exam_title)) +
        kv("To‘g‘ri javoblar", attempt.correct + " / " + attempt.max_raw_score) +
        kv("Xato javoblar", attempt.wrong) +
        kv("Javobsiz", attempt.empty) +
        kv("Foiz", attempt.percent + "%") +
        (attempt.rank ? kv("Reyting", attempt.rank + " / " + attempt.total_participants) : "") +
        (attempt.theta !== null && attempt.theta !== undefined
          ? kv("theta (θ)", Number(attempt.theta).toFixed(3)) : "") +
        kv("Topshirgan vaqt", esc(attempt.submitted_at_human)) +
        "</div></div>";

      if (data.certificate) {
        html += '<div class="card"><div class="card-head">' + ic("award") + "<h2>Sertifikat</h2></div>" +
          '<div class="kv-list">' +
          kv("Raqami", '<span class="code-pill">' + esc(data.certificate.number) + "</span>") +
          kv("Ball", esc(data.certificate.ball)) +
          kv("Daraja", esc(data.certificate.grade || "—")) +
          "</div>" +
          '<a class="btn btn-gold" href="' + esc(data.certificate.download_url) + '" target="_blank" rel="noopener">' +
          ic("download") + "Sertifikatni yuklab olish</a>" +
          '<a class="btn btn-ghost" href="' + esc(data.certificate.verify_url) + '" target="_blank" rel="noopener">' +
          ic("qr") + "Haqiqiyligini tekshirish</a></div>";
      } else if (data.certificate_available) {
        html += '<button class="btn btn-gold" data-act="get-certificate" data-id="' + attempt.id + '">' +
          ic("award") + "Sertifikatni olish</button>";
      } else if (data.certificate_reason) {
        html += '<div class="alert alert-info">' + ic("info") + "<div>" + esc(data.certificate_reason) + "</div></div>";
      }

      var review = data.review || [];
      if (review.length) {
        html += '<div class="section-title">' + ic("list", "icon-sm") + "Javoblaringiz</div>";
        html += '<div class="card"><div class="review-grid">';
        review.forEach(function (row) {
          html += '<div class="review-cell ' + row.state + '">' + row.order +
            ic(row.state === "correct" ? "check" : row.state === "wrong" ? "x" :
               row.state === "partial" ? "minus" : "circle") + "</div>";
        });
        html += "</div></div>";

        html += '<div class="card">';
        review.forEach(function (row) {
          html += '<div class="review-row"><span class="no">' + row.order + "</span>" +
            '<span class="st ' + row.state + '">' +
            ic(row.state === "correct" ? "check-circle" : row.state === "wrong" ? "x-circle" :
               row.state === "partial" ? "alert" : "circle") + "</span>" +
            '<span class="val">' + esc(row.given) + "</span>" +
            (row.correct && row.correct !== "—"
              ? '<span class="key">' + esc(row.correct) + "</span>" : "") +
            "</div>";
        });
        html += "</div>";
      }

      if (attempt.show_rating) {
        html += '<button class="btn btn-ghost" data-act="open-rating" data-code="' + esc(attempt.exam_code) + '">' +
          ic("trophy") + "Reyting</button>";
      }

      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  /* --------------------------------------------------------- 6. Results */

  function viewResults() {
    api("boshlash/").then(function (data) {
      state.boot = data;
      var results = data.results || [];
      var html = "";
      if (!results.length) {
        html += '<div class="empty">' + ic("chart", "icon-xl") +
          "<b>Natijalar yo‘q</b><p>Biror testda qatnashib ko‘ring.</p>" +
          '<button class="btn btn-ghost" data-act="tab" data-tab="exams">Testlarni ko‘rish</button></div>';
      } else {
        results.forEach(function (attempt) {
          var pending = attempt.uses_rasch && !attempt.results_published;
          html += '<button class="item" data-act="open-result" data-id="' + attempt.id + '">' +
            '<div class="ico">' + ic(pending ? "hourglass" : "chart") + "</div>" +
            '<div class="body"><b>' + esc(attempt.exam_title) + "</b>" +
            "<small>" + esc(attempt.submitted_at_human) + "</small></div>" +
            '<div class="score">' +
            (pending ? '<b class="muted small">kutilmoqda</b>'
                     : "<b>" + esc(attempt.uses_rasch ? attempt.ball : attempt.percent + "%") + "</b>" +
                       (attempt.grade ? "<small>" + esc(attempt.grade) + "</small>" : "")) +
            "</div></button>";
        });
      }
      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  /* ---------------------------------------------------- 7. Certificates */

  function viewCertificates() {
    api("sertifikatlar/").then(function (data) {
      var items = data.certificates || [];
      var html = "";
      if (!items.length) {
        html += '<div class="empty">' + ic("award", "icon-xl") +
          "<b>Sertifikatlar yo‘q</b>" +
          "<p>Sertifikat pullik RASH testlarida, natijalar e’lon qilingandan " +
          "so‘ng beriladi.</p></div>";
      } else {
        items.forEach(function (item) {
          html += '<div class="card"><div class="card-head">' + ic("award") +
            "<h2>" + esc(item.exam_title) + "</h2></div>" +
            '<div class="kv-list">' +
            kv("Raqami", '<span class="code-pill">' + esc(item.number) + "</span>") +
            kv("Ball", esc(item.ball)) +
            kv("Daraja", esc(item.grade || "—")) +
            kv("Reyting", esc(item.rank)) +
            kv("Test sanasi", esc(item.exam_date)) +
            "</div>" +
            '<a class="btn btn-gold" href="' + esc(item.download_url) + '" target="_blank" rel="noopener">' +
            ic("download") + "PDF yuklab olish</a>" +
            '<a class="btn btn-ghost" href="' + esc(item.verify_url) + '" target="_blank" rel="noopener">' +
            ic("qr") + "Tekshirish sahifasi</a></div>";
        });
      }
      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  /* -------------------------------------------------------- 8. My exams */

  function viewMyExams() {
    api("mening-testlarim/").then(function (data) {
      var exams = data.exams || [];
      var html = '<button class="btn" data-act="go" data-view="create">' + ic("plus") + "Yangi test yaratish</button>";

      if (!exams.length) {
        html += '<div class="empty">' + ic("list", "icon-xl") +
          "<b>Testlaringiz yo‘q</b><p>Birinchi testingizni yarating.</p></div>";
      } else {
        html += '<div class="section-title">' + ic("list", "icon-sm") + exams.length + " ta test</div>";
        exams.forEach(function (exam) {
          html += '<button class="item" data-act="open-manage" data-code="' + esc(exam.code) + '">' +
            '<div class="ico">' + ic("file") + "</div>" +
            '<div class="body"><b>' + esc(exam.title) + "</b>" +
            '<small><span class="code-pill">' + esc(exam.code) + "</span> · " +
            exam.question_count + " ta savol · " + (exam.participants || 0) + " qatnashchi</small>" +
            '<div class="chips">' + statusBadge(exam) + "</div></div>" +
            '<span class="arrow">' + ic("chevron-right") + "</span></button>";
        });
      }
      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  function statusBadge(exam) {
    var map = {
      draft: ["badge-muted", "Qoralama"],
      active: ["badge-green", "Faol"],
      closed: ["badge-gold", "Yopilgan"],
      calculated: ["badge-purple", "Hisoblangan"],
      published: ["badge-accent", "E’lon qilingan"],
      archived: ["badge-muted", "Arxiv"]
    };
    var info = map[exam.status] || ["badge-muted", exam.status_label];
    return '<span class="badge ' + info[0] + '">' + esc(info[1]) + "</span>";
  }

  /* ---------------------------------------------------------- 9. Create */

  function viewCreate() {
    /* Ekran bot menyusidan to'g'ridan-to'g'ri ochilsa, foydalanuvchi
       ma'lumoti hali yuklanmagan bo'ladi — avval uni olamiz, aks holda
       admin uchun «3-tur · Pullik RASH» tugmasi ko'rinmay qoladi. */
    if (!state.user) {
      api("boshlash/").then(function (data) {
        state.boot = data;
        state.user = data.user;
        renderCreateForm();
      }).catch(handleError);
      return;
    }
    renderCreateForm();
  }

  function renderCreateForm() {
    var isAdmin = state.user && state.user.is_admin;
    var html = "";

    html += '<div class="card"><div class="card-head">' + ic("info") + "<h2>Test turi</h2></div>" +
      '<div class="seg" id="seg-type">' +
      '<button data-type="simple" class="is-active">1-tur · Bepul oddiy</button>' +
      '<button data-type="rasch_free">2-tur · Bepul RASH</button>' +
      (isAdmin ? '<button data-type="rasch_paid">3-tur · Pullik RASH</button>' : "") +
      "</div>" +
      '<p class="hint muted small mt" id="type-hint">Natija to‘g‘ri javoblar soni bo‘yicha hisoblanadi.</p>' +
      "</div>";

    html += '<div class="card"><div class="field"><label>Test nomi</label>' +
      '<input class="input" id="f-title" placeholder="MILLIY SERTIFIKAT MOCK №7" maxlength="150"></div>' +

      '<div class="field" id="wrap-structure" hidden><label>Tuzilma</label>' +
      '<div class="seg" id="seg-structure">' +
      '<button data-structure="custom" class="is-active">O‘zim belgilayman</button>' +
      '<button data-structure="national">Milliy shablon (45)</button>' +
      "</div></div>" +

      '<div class="field" id="wrap-count"><label>Savollar soni</label>' +
      '<div class="seg" id="seg-count">' +
      [10, 20, 30, 45, 50, 100].map(function (n) {
        return '<button data-count="' + n + '"' + (n === 20 ? ' class="is-active"' : "") + ">" + n + "</button>";
      }).join("") +
      "</div>" +
      '<input class="input mt" id="f-count" type="number" min="1" max="500" value="20"></div>' +

      '<div class="field"><label>Tugash vaqti</label>' +
      '<div class="seg" id="seg-duration">' +
      [["0", "Cheklovsiz"], ["1", "1 soat"], ["3", "3 soat"], ["24", "24 soat"], ["168", "7 kun"]]
        .map(function (item) {
          return '<button data-hours="' + item[0] + '"' + (item[0] === "0" ? ' class="is-active"' : "") +
            ">" + item[1] + "</button>";
        }).join("") +
      "</div>" +
      '<input class="input mt" id="f-ends-at" type="datetime-local">' +
      '<div class="hint">Yoki aniq sana va vaqtni tanlang (masalan, 21:30).</div>' +
      "</div>" +
      "</div>";

    html += '<div class="card"><div class="card-head">' + ic("key") + "<h2>Javob kalitlari</h2></div>" +
      '<div class="field" id="wrap-single"><label>Bitta javobli savollar (A–D)</label>' +
      '<textarea class="input" id="f-single" placeholder="ABCDABCD... yoki 1-A 2-B 3-C"></textarea>' +
      '<div class="hint" id="hint-single"></div></div>' +

      '<div class="field" id="wrap-multi" hidden><label>Ko‘p javobli savollar (A–F)</label>' +
      '<textarea class="input" id="f-multi" placeholder="AB, ACD, BF"></textarea>' +
      '<div class="hint">Guruhlarni vergul bilan ajrating.</div></div>' +

      '<div class="field" id="wrap-open" hidden><label>Ochiq javoblar (a ; b)</label>' +
      '<textarea class="input" id="f-open" rows="6" placeholder="12 ; 3/4&#10;sqrt(2) ; pi/6"></textarea>' +
      '<div class="hint">Har bir savol uchun alohida qator.</div></div>' +
      "</div>";

    html += '<div class="card"><div class="card-head">' + ic("settings") + "<h2>Sozlamalar</h2></div>" +
      '<div class="switch-row"><div><b>Natija qatnashchilarga ko‘rinsin</b>' +
      "<small>To‘g‘ri va xato javoblarni ko‘ra oladi</small></div>" +
      '<input type="checkbox" id="f-show" checked></div>' +
      '<div class="switch-row" id="wrap-cert" hidden><div><b>Sertifikat berilsin</b>' +
      "<small>Natijalar e’lon qilingandan keyin PDF</small></div>" +
      '<input type="checkbox" id="f-cert"></div>' +
      "</div>";

    html += '<button class="btn btn-green" data-act="create-exam">' + ic("check") + "Testni yaratish</button>";
    html += '<div id="create-errors"></div>';

    el.screen.innerHTML = html;
    bindCreateForm();
  }

  function bindCreateForm() {
    var form = { type: "simple", structure: "custom", count: 20, hours: 0 };
    state.createForm = form;

    function segment(id, attribute, onPick) {
      var box = document.getElementById(id);
      if (!box) { return; }
      box.addEventListener("click", function (e) {
        var button = e.target.closest("button");
        if (!button) { return; }
        Array.prototype.forEach.call(box.querySelectorAll("button"), function (b) {
          b.classList.remove("is-active");
        });
        button.classList.add("is-active");
        onPick(button.dataset[attribute]);
      });
    }

    segment("seg-type", "type", function (value) {
      form.type = value;
      var hints = {
        simple: "Natija to‘g‘ri javoblar soni bo‘yicha hisoblanadi. RASH ishlatilmaydi.",
        rasch_free: "Natija Rasch (IRT-1PL) modeli asosida hisoblanadi. Sertifikat yo‘q.",
        rasch_paid: "Kirish bir martalik ID kod orqali. Sertifikat beriladi."
      };
      document.getElementById("type-hint").textContent = hints[value] || "";
      document.getElementById("wrap-structure").hidden = value === "simple";
      document.getElementById("wrap-cert").hidden = value !== "rasch_paid";
      if (value === "simple") { form.structure = "custom"; }
      applyStructure();
    });

    segment("seg-structure", "structure", function (value) {
      form.structure = value;
      applyStructure();
    });

    segment("seg-count", "count", function (value) {
      form.count = parseInt(value, 10);
      document.getElementById("f-count").value = form.count;
      updateKeyHints();
    });

    segment("seg-duration", "hours", function (value) {
      form.hours = parseInt(value, 10);
      var picker = document.getElementById("f-ends-at");
      if (picker) { picker.value = ""; }   // tayyor variant aniq vaqtni bekor qiladi
    });

    document.getElementById("f-count").addEventListener("input", function () {
      form.count = parseInt(this.value, 10) || 0;
      updateKeyHints();
    });

    function applyStructure() {
      var national = form.structure === "national" && form.type !== "simple";
      document.getElementById("wrap-count").hidden = national;
      document.getElementById("wrap-multi").hidden = !national;
      document.getElementById("wrap-open").hidden = !national;
      updateKeyHints();
    }

    function updateKeyHints() {
      var national = form.structure === "national" && form.type !== "simple";
      var single = national ? 32 : form.count;
      var hint = document.getElementById("hint-single");
      if (hint) { hint.textContent = single + " ta javob kerak (A–D)."; }
    }

    applyStructure();
  }

  function submitCreate() {
    var form = state.createForm || { type: "simple", structure: "custom", count: 20, hours: 0 };
    var national = form.structure === "national" && form.type !== "simple";
    var payload = {
      title: document.getElementById("f-title").value.trim(),
      type: form.type,
      national: national,
      question_count: national ? 45 : (parseInt(document.getElementById("f-count").value, 10) || 0),
      duration_hours: form.hours,
      ends_at: (document.getElementById("f-ends-at") || {}).value || "",
      show_results: document.getElementById("f-show").checked,
      certificate: !!(document.getElementById("f-cert") && document.getElementById("f-cert").checked),
      single_keys: document.getElementById("f-single").value,
      multi_keys: national ? document.getElementById("f-multi").value : "",
      open_keys: national ? document.getElementById("f-open").value : ""
    };

    if (payload.title.length < 3) {
      toast("Test nomini kiriting (kamida 3 ta belgi).", true);
      return;
    }

    var box = document.getElementById("create-errors");
    box.innerHTML = "";
    setBusy(true);

    api("test-yaratish/", { method: "POST", body: payload }).then(function (data) {
      setBusy(false);
      toast("Test yaratildi: " + data.exam.code);
      state.stack = [];
      go("manage", { code: data.exam.code }, true);
    }).catch(function (error) {
      setBusy(false);
      var errors = (error.payload && error.payload.errors) || [];
      var html = '<div class="alert alert-error">' + ic("alert") + "<div><b>" + esc(error.message) + "</b>";
      if (errors.length) {
        html += "<ul style='margin:6px 0 0 16px;padding:0'>";
        errors.forEach(function (item) { html += "<li>" + esc(item) + "</li>"; });
        html += "</ul>";
      }
      html += "</div></div>";
      box.innerHTML = html;
      box.scrollIntoView({ behavior: "smooth", block: "center" });
      haptic("err");
    });
  }

  function setBusy(value) {
    state.busy = value;
    Array.prototype.forEach.call(el.screen.querySelectorAll(".btn"), function (button) {
      button.disabled = value;
    });
  }

  /* --------------------------------------------------------- 10. Manage */

  function viewManage() {
    var code = state.params.code;
    api("test/" + encodeURIComponent(code) + "/boshqaruv/").then(function (data) {
      var exam = data.exam;
      setHeader("manage", exam.title);

      var html = "";
      html += '<div class="card"><div class="card-head">' + ic("file") +
        "<h2>" + esc(exam.title) + "</h2></div>" +
        '<div class="chips mb">' + statusBadge(exam) +
        '<span class="badge badge-accent">' + esc(exam.type_label) + "</span>" +
        (exam.certificate ? '<span class="badge badge-gold">Sertifikat</span>' : "") + "</div>" +
        '<div class="kv-list">' +
        kv("Kod", '<span class="code-pill">' + esc(exam.code) + "</span>") +
        kv("Savollar", exam.question_count + " ta") +
        kv("Qatnashganlar", (exam.participants || 0) + " ta") +
        kv("Tugash vaqti", esc(exam.ends_at_human)) +
        (data.certificates ? kv("Sertifikatlar", data.certificates + " ta") : "") +
        "</div></div>";

      if (data.missing_keys && data.missing_keys.length) {
        html += '<div class="alert alert-warn">' + ic("alert") +
          "<div>Javob kaliti kiritilmagan savollar: <b>" +
          data.missing_keys.join(", ") + "</b></div></div>";
      }

      if (data.codes) {
        html += '<div class="card"><div class="card-head">' + ic("key") + "<h2>ID kodlar</h2></div>" +
          '<div class="stats">' +
          '<div class="stat"><b>' + data.codes.total + "</b><span>Jami</span></div>" +
          '<div class="stat green"><b>' + data.codes.unused + "</b><span>Bo‘sh</span></div>" +
          '<div class="stat red"><b>' + data.codes.used + "</b><span>Ishlatilgan</span></div>" +
          "</div>" +
          '<div class="seg mb" id="seg-codes">' +
          [500, 1000, 1500, 2000, 3000].map(function (n) {
            return '<button data-qty="' + n + '">' + n + "</button>";
          }).join("") + "</div>" +
          '<button class="btn btn-ghost" data-act="make-codes" data-code="' + esc(exam.code) + '">' +
          ic("plus") + "ID kodlar yaratish</button></div>";
      }

      if (data.statistics) {
        var st = data.statistics;
        html += '<div class="card"><div class="card-head">' + ic("chart") + "<h2>Statistika</h2></div>" +
          '<div class="kv-list">' +
          kv("Qatnashchilar", st.participants) +
          kv("O‘rtacha ball", st.avg_ball) +
          kv("Eng yuqori", st.max_ball) +
          kv("Eng past", st.min_ball) +
          kv("O‘rtacha foiz", st.avg_percent + "%") +
          kv("Ishonchlilik (KR-20)", st.reliability) +
          "</div>";
        if (st.grades && st.grades.length) {
          html += '<div class="chips mt">';
          st.grades.forEach(function (row) {
            html += '<span class="badge badge-accent">' + esc(row.grade) + ": " + row.count + "</span>";
          });
          html += "</div>";
        }
        html += "</div>";
      }

      html += '<div class="section-title">' + ic("settings", "icon-sm") + "Amallar</div>";

      if (exam.status === "draft" || exam.status === "closed") {
        html += actionButton("activate", "play", "Faollashtirish", "btn-green");
      }
      if (exam.status === "active") {
        html += actionButton("close", "stop", "Testni yopish", "btn-ghost");
      }
      if (["active", "closed", "calculated", "published"].indexOf(exam.status) !== -1) {
        html += actionButton("calculate", "sigma", "Natijalarni hisoblash", "btn");
      }
      if (["calculated", "published"].indexOf(exam.status) !== -1) {
        html += actionButton("publish", "send", "Natijalarni e’lon qilish", "btn-gold");
      }
      if (exam.certificate && exam.status === "published") {
        html += actionButton("certificates", "award", "Sertifikatlarni yaratish", "btn-ghost");
      }

      html += '<button class="btn btn-ghost" data-act="open-rating" data-code="' + esc(exam.code) + '">' +
        ic("trophy") + "Reyting</button>";

      html += '<a class="btn btn-ghost" href="' + esc(data.exports.results_xlsx) + '" target="_blank" rel="noopener">' +
        ic("sheet") + "Natijalar (Excel)</a>";
      html += '<a class="btn btn-ghost" href="' + esc(data.exports.results_pdf) + '" target="_blank" rel="noopener">' +
        ic("file") + "Natijalar (PDF)</a>";

      html += actionButton("duplicate", "copy", "Nusxa yaratish", "btn-ghost");
      html += actionButton("archive", "save", "Arxivlash", "btn-ghost");

      html += '<button class="btn btn-danger" data-act="delete-exam" data-code="' + esc(exam.code) + '">' +
        ic("trash") + "Testni o‘chirish</button>";

      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  function actionButton(action, icon, label, cls) {
    return '<button class="btn ' + (cls || "btn-ghost") + '" data-act="exam-action" data-action="' +
      action + '">' + ic(icon) + esc(label) + "</button>";
  }

  function runExamAction(action) {
    var code = state.params.code;
    setBusy(true);
    api("test/" + encodeURIComponent(code) + "/amal/", { method: "POST", body: { action: action } })
      .then(function (data) {
        setBusy(false);
        toast(data.message || "Bajarildi.");
        if (action === "duplicate" && data.exam) {
          go("manage", { code: data.exam.code }, true);
          return;
        }
        render();
      })
      .catch(function (error) { setBusy(false); toast(error.message, true); });
  }

  function deleteExam(code) {
    api("test/" + encodeURIComponent(code) + "/ochirish-tekshiruv/").then(function (data) {
      var s = data.summary;
      var html = "<b>" + esc(data.exam.title) + "</b> testi butunlay o‘chiriladi.<br><br>" +
        "Birga o‘chadi:<br>" +
        "• savollar: <b>" + s.questions + "</b> ta<br>" +
        "• urinishlar: <b>" + s.attempts + "</b> ta (topshirilgan: <b>" + s.submitted + "</b>)<br>" +
        "• ID kodlar: <b>" + s.codes + "</b> ta<br>" +
        "• sertifikatlar: <b>" + s.certificates + "</b> ta<br><br>" +
        "<b>Bu amalni ortga qaytarib bo‘lmaydi.</b>";

      confirmDialog("Testni o‘chirish", html, "Ha, o‘chirilsin", "btn-danger").then(function (ok) {
        if (!ok) { return; }
        loading();
        api("test/" + encodeURIComponent(code) + "/ochirish/", {
          method: "POST", body: { confirm: true }
        }).then(function (result) {
          toast(result.message || "Test o‘chirildi.");
          state.stack = [];
          go("my-exams", {}, true);
        }).catch(function (error) { toast(error.message, true); render(); });
      });
    }).catch(function (error) { toast(error.message, true); });
  }

  function makeCodes(code) {
    var active = el.screen.querySelector("#seg-codes button.is-active");
    var quantity = active ? parseInt(active.dataset.qty, 10) : 0;
    if (!quantity) { toast("Avval kodlar sonini tanlang.", true); return; }

    confirmDialog("ID kodlar", quantity + " ta bir martalik ID kod yaratilsinmi?",
      "Yaratish", "btn-green").then(function (ok) {
      if (!ok) { return; }
      loading();
      api("test/" + encodeURIComponent(code) + "/kodlar/", {
        method: "POST", body: { quantity: quantity }
      }).then(function (data) {
        toast(data.message);
        render();
      }).catch(function (error) { toast(error.message, true); render(); });
    });
  }

  /* --------------------------------------------------------- 11. Rating */

  function viewRating() {
    var code = state.params.code;
    api("test/" + encodeURIComponent(code) + "/reyting/").then(function (data) {
      setHeader("rating", data.exam.title);
      var rows = data.rows || [];
      var html = "";

      html += '<div class="card"><div class="card-head">' + ic("trophy") +
        "<h2>" + esc(data.exam.title) + '</h2><span class="sub">' + data.total + " ta</span></div>";

      if (!rows.length) {
        html += '<p class="muted small">Hozircha qatnashchilar yo‘q.</p>';
      } else {
        rows.forEach(function (row) {
          var cls = "rank-row" + (row.place <= 3 ? " top" + row.place : "") + (row.is_me ? " is-me" : "");
          html += '<div class="' + cls + '">' +
            '<span class="place">' + row.place + "</span>" +
            '<span class="nm">' + esc(row.name) + "</span>" +
            '<span class="sc">' +
            esc(row.ball !== null && row.ball !== undefined ? row.ball : row.percent + "%") +
            "</span></div>";
        });
      }
      html += "</div>";
      el.screen.innerHTML = html;
    }).catch(handleError);
  }

  /* =====================================================================
     Xatoliklar
     ===================================================================== */

  function handleError(error) {
    if (error && error.status === 401) {
      /* Brauzerda (Telegram tashqarisida) — kirish sahifasiga yo'naltiramiz. */
      if (!(tg && tg.initData) && !DEBUG_USER) {
        location.href = "/app/kirish/";
        return;
      }
      el.screen.innerHTML = '<div class="empty">' + ic("lock", "icon-xl") +
        "<b>Kirish yopiq</b><p>" + esc(error.message) + "</p>" +
        '<button class="btn btn-ghost" data-act="reload">Qayta urinish</button></div>';
      return;
    }
    showError(error && error.message ? error.message : "Noma'lum xatolik.");
  }

  /* =====================================================================
     Hodisalar
     ===================================================================== */

  el.screen.addEventListener("click", function (e) {
    var target = e.target.closest("[data-act]");
    if (!target) {
      var seg = e.target.closest("#seg-codes button");
      if (seg) {
        Array.prototype.forEach.call(seg.parentNode.querySelectorAll("button"), function (b) {
          b.classList.remove("is-active");
        });
        seg.classList.add("is-active");
      }
      return;
    }

    var act = target.dataset.act;

    if (act === "reload") { render(); return; }
    if (act === "tab") { state.stack = []; go(target.dataset.tab, {}, true); return; }
    if (act === "go") { go(target.dataset.view, {}); return; }
    if (act === "open-exam") { go("exam", { code: target.dataset.code }); return; }
    if (act === "open-attempt") { go("attempt", { id: target.dataset.id }); return; }
    if (act === "open-result") { go("result", { id: target.dataset.id }); return; }
    if (act === "open-rating") { go("rating", { code: target.dataset.code }); return; }
    if (act === "open-manage") { go("manage", { code: target.dataset.code }); return; }

    if (act === "find-exam") {
      var input = document.getElementById("exam-code");
      var code = (input.value || "").trim();
      if (!code) { toast("Test kodini kiriting.", true); return; }
      go("exam", { code: code });
      return;
    }

    if (act === "start-exam") {
      var codeInput = document.getElementById("access-code");
      var payload = codeInput ? { access_code: codeInput.value.trim() } : {};
      setBusy(true);
      api("test/" + encodeURIComponent(target.dataset.code) + "/boshlash/", {
        method: "POST", body: payload
      }).then(function (data) {
        setBusy(false);
        go("attempt", { id: data.attempt_id }, true);
      }).catch(function (error) { setBusy(false); toast(error.message, true); });
      return;
    }

    if (act === "choose") {
      chooseLetter(parseInt(target.dataset.order, 10), target.dataset.letter);
      return;
    }
    if (act === "jump") { jumpToQuestion(parseInt(target.dataset.order, 10)); return; }
    if (act === "finish") { finishAttempt(); return; }
    if (act === "leave") { closeMathPad(); state.stack = []; go("home", {}, true); return; }

    if (act === "mkey") {
      insertText(target.dataset.ins, parseInt(target.dataset.caret, 10) || 0);
      return;
    }
    if (act === "mdel") { backspace(); return; }
    if (act === "mclose") { closeMathPad(); return; }
    if (act === "mclear") {
      var field = activeInput();
      if (field) {
        field.value = "";
        scheduleCheck(state.activeField);
        saveOpenAnswer(parseInt(field.dataset.order, 10));
      }
      return;
    }

    if (act === "get-certificate") {
      setBusy(true);
      api("urinish/" + target.dataset.id + "/sertifikat/", { method: "POST" })
        .then(function () { setBusy(false); toast("Sertifikat tayyor."); render(); })
        .catch(function (error) { setBusy(false); toast(error.message, true); });
      return;
    }

    if (act === "create-exam") { submitCreate(); return; }
    if (act === "exam-action") { runExamAction(target.dataset.action); return; }
    if (act === "delete-exam") { deleteExam(target.dataset.code); return; }
    if (act === "make-codes") { makeCodes(target.dataset.code); return; }
  });

  /* =====================================================================
     Boshlanish
     ===================================================================== */

  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tg.MainButton) { tg.MainButton.hide(); }
      if (tg.BackButton) { tg.BackButton.onClick(back); }
      if (tg.setHeaderColor) { tg.setHeaderColor("secondary_bg_color"); }

      /* Qorong'u mavzuda kontrastni CSS orqali moslash uchun belgi. */
      var syncTheme = function () {
        body.classList.toggle("tg-dark", tg.colorScheme === "dark");
      };
      /* To'liq ekranda Telegram boshqaruv tugmalari uchun joy qoldiriladi. */
      var syncFullscreen = function () {
        body.classList.toggle("tg-fullscreen", !!tg.isFullscreen);
      };
      syncTheme();
      syncFullscreen();
      if (typeof tg.onEvent === "function") {
        try {
          tg.onEvent("themeChanged", syncTheme);
          tg.onEvent("fullscreenChanged", syncFullscreen);
        } catch (e) { /* eski versiyalar */ }
      }

      /* Kompyuterda (desktop/web mijozlar) ilova ochilishi bilan avtomatik
         to'liq ekranga o'tadi — Bot API 8.0+ requestFullscreen. */
      var desktopPlatforms = ["tdesktop", "macos", "weba", "webk", "web", "unigram"];
      if (
        desktopPlatforms.indexOf(tg.platform) !== -1 &&
        typeof tg.isVersionAtLeast === "function" && tg.isVersionAtLeast("8.0") &&
        typeof tg.requestFullscreen === "function" && !tg.isFullscreen
      ) {
        try { tg.requestFullscreen(); } catch (e) { /* qo'llamaydigan mijoz */ }
      }
    } catch (e) { /* eski versiyalar */ }
  }

  /* Brauzer (sessiya) rejimida sarlavhada "Chiqish" tugmasi ko'rinadi. */
  if (el.logout && !(tg && tg.initData)) {
    el.logout.hidden = false;
    el.logout.addEventListener("click", function () {
      location.href = "/app/chiqish/";
    });
  }

  var initialView = body.dataset.initialView || "home";
  var initialParams = {};
  if (body.dataset.initialCode) { initialParams.code = body.dataset.initialCode; }
  if (body.dataset.initialAttempt) { initialParams.id = body.dataset.initialAttempt; }

  var VIEW_ALIASES = { "exam-manage": "manage", "my-exams": "my-exams" };
  initialView = VIEW_ALIASES[initialView] || initialView;

  state.view = initialView;
  state.params = initialParams;
  render();
})();
