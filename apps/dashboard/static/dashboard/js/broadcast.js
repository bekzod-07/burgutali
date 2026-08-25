/* ==========================================================================
   Reklama xabari — jonli ko'rinish va yuborish holati.

   Ikki sahifada ishlaydi:
     * yaratish/tahrirlash — matn, rasm va tugmalar yozilishi bilanoq
       o'ng tomonda Telegramdagi ko'rinish chiziladi;
     * tafsilot — yuborish davom etayotgan bo'lsa, hisoblagichlar
       sahifani yangilamasdan o'zi o'sib boradi.
   ========================================================================== */

(function () {
  "use strict";

  /* Telegram qabul qiladigan teglar (server bilan bir xil ro'yxat). */
  var ALLOWED = "b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler|blockquote";
  var SCHEME_RE = /^(https?:\/\/|tg:\/\/)/i;

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /* Matnni Telegramdagidek chizadi: ruxsat etilgan teglar ishlaydi,
     qolganlari oddiy matn bo'lib ko'rinadi. */
  function renderText(raw) {
    var html = escapeHtml(raw);
    html = html.replace(new RegExp("&lt;(/?)(" + ALLOWED + ")&gt;", "gi"), "<$1$2>");
    html = html.replace(/&lt;a\s+href="([^"]*)"&gt;/gi, function (match, href) {
      if (!SCHEME_RE.test(href)) { return match; }
      return '<a href="' + href.replace(/"/g, "&quot;") + '" target="_blank" rel="noopener">';
    });
    html = html.replace(/&lt;\/a&gt;/gi, "</a>");
    html = html.replace(/&lt;br\s*\/?&gt;/gi, "\n");
    return html.replace(/\n/g, "<br>");
  }

  /* Ko'rinadigan belgilar soni — Telegram chegarani teglarsiz hisoblaydi. */
  function plainLength(raw) {
    var text = String(raw || "").replace(/<br\s*\/?>/gi, "\n");
    var tagRe = new RegExp("<\\s*/?\\s*(" + ALLOWED + "|a)(\\s[^<>]*)?>", "gi");
    return text.replace(tagRe, "").length;
  }

  function renderButtons(raw, host) {
    while (host.firstChild) { host.removeChild(host.firstChild); }
    String(raw || "").split(/\r?\n/).forEach(function (line) {
      line = line.trim();
      if (!line) { return; }
      var row = document.createElement("div");
      row.className = "tg-button-row";
      line.split("||").forEach(function (piece) {
        piece = piece.trim();
        if (!piece) { return; }
        var cut = piece.indexOf("|");
        if (cut === -1) { return; }
        var label = piece.slice(0, cut).trim();
        var url = piece.slice(cut + 1).trim();
        if (!label) { return; }
        var button = document.createElement("a");
        button.className = "tg-button";
        button.textContent = label;
        if (SCHEME_RE.test(url)) {
          button.href = url;
          button.target = "_blank";
          button.rel = "noopener";
        } else {
          button.classList.add("is-invalid");
          button.title = "Havola https:// yoki tg:// bilan boshlanishi kerak";
        }
        row.appendChild(button);
      });
      if (row.childNodes.length) { host.appendChild(row); }
    });
  }

  // ------------------------------------------------------------------
  //  Yaratish / tahrirlash sahifasi
  // ------------------------------------------------------------------
  function setupForm() {
    var form = document.querySelector("[data-broadcast-form]");
    if (!form) { return; }

    var textField = form.querySelector("#id_text");
    var buttonsField = form.querySelector("#id_buttons_raw");
    var imageField = form.querySelector("#id_image");
    var removeField = form.querySelector("#id_remove_image");
    var audienceField = form.querySelector("#id_audience");
    var examRow = form.querySelector("[data-bc-exam-row]");

    var textHost = form.querySelector("[data-bc-text]");
    var buttonHost = form.querySelector("[data-bc-buttons]");
    var photo = form.querySelector("[data-bc-photo]");
    var counter = form.querySelector("[data-bc-counter]");
    var limitLabel = form.querySelector("[data-bc-limit]");

    var captionLimit = parseInt(form.getAttribute("data-caption-limit"), 10) || 1024;
    var textLimit = parseInt(form.getAttribute("data-text-limit"), 10) || 4096;
    var originalPhoto = photo && photo.getAttribute("src");

    function hasPhoto() {
      if (removeField && removeField.checked) { return false; }
      if (imageField && imageField.files && imageField.files.length) { return true; }
      return Boolean(originalPhoto);
    }

    function refresh() {
      var raw = textField ? textField.value : "";
      if (textHost) {
        textHost.innerHTML = renderText(raw);
        textHost.classList.toggle("is-empty", !raw.trim());
        if (!raw.trim()) { textHost.textContent = "Matn kiritilmagan"; }
      }
      if (buttonHost) { renderButtons(buttonsField ? buttonsField.value : "", buttonHost); }

      var limit = hasPhoto() ? captionLimit : textLimit;
      var length = plainLength(raw);
      if (counter) {
        counter.textContent = String(length);
        counter.classList.toggle("is-over", length > limit);
      }
      if (limitLabel) { limitLabel.textContent = String(limit); }

      if (photo) {
        if (removeField && removeField.checked) {
          photo.hidden = true;
        } else if (photo.getAttribute("src")) {
          photo.hidden = false;
        }
      }
    }

    function showChosenImage() {
      if (!photo || !imageField || !imageField.files || !imageField.files.length) { return; }
      var reader = new FileReader();
      reader.onload = function (event) {
        photo.src = event.target.result;
        photo.hidden = false;
        refresh();
      };
      reader.readAsDataURL(imageField.files[0]);
    }

    function toggleExamRow() {
      if (!examRow || !audienceField) { return; }
      examRow.hidden = audienceField.value !== "exam";
    }

    if (textField) { textField.addEventListener("input", refresh); }
    if (buttonsField) { buttonsField.addEventListener("input", refresh); }
    if (imageField) { imageField.addEventListener("change", showChosenImage); }
    if (removeField) { removeField.addEventListener("change", refresh); }
    if (audienceField) { audienceField.addEventListener("change", toggleExamRow); }

    toggleExamRow();
    refresh();
  }

  // ------------------------------------------------------------------
  //  Tafsilot sahifasi — yuborish holati
  // ------------------------------------------------------------------
  function setupProgress() {
    var card = document.querySelector("[data-bc-progress]");
    if (!card || card.getAttribute("data-running") !== "1") { return; }

    var url = card.getAttribute("data-url");
    if (!url || typeof window.fetch !== "function") { return; }

    function put(selector, value) {
      var node = card.querySelector(selector);
      if (node) { node.textContent = String(value); }
    }

    var timer = window.setInterval(function () {
      window.fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (data) {
          if (!data) { return; }
          put("[data-bc-total]", data.total);
          put("[data-bc-sent]", data.sent);
          put("[data-bc-failed]", data.failed);
          put("[data-bc-blocked]", data.blocked);
          put("[data-bc-status-label]", data.status_label);
          var bar = card.querySelector("[data-bc-bar]");
          if (bar) { bar.style.width = data.percent + "%"; }
          if (data.finished) {
            window.clearInterval(timer);
            window.location.reload();
          }
        })
        .catch(function () { /* aloqa uzilsa keyingi urinishda tiklanadi */ });
    }, 3000);
  }

  function start() {
    setupForm();
    setupProgress();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
