/* ==========================================================================
   Matematik maydon — javobni chizilgan ko'rinishda ko'rsatadi.

   Maydonning qiymati ilgarigidek **oddiy matn** bo'lib qoladi (`1/2`,
   `sqrt(2)`, `log(100,10)`) — baholash, saqlash va SymPy tekshiruvi shu
   matn bilan ishlaydi. Bu modul faqat ko'rinishni o'zgartiradi: matn
   o'qib chiqiladi va ekranda haqiqiy formula ko'rinishida chiziladi:

       1/2          ->   1
                         ─
                         2

       sqrt(2)/2    ->   √2
                         ──
                          2

       2^10         ->   2¹⁰
       root(8,3)    ->   ³√8
       log(100,10)  ->   log₁₀(100)

   Kursor ham chizilgan formulaning ichida ko'rinadi; uni klaviaturaning
   `‹ ›` tugmalari bilan yoki formulani bosib siljitish mumkin.

   Ifoda hali tugallanmagan bo'lsa (masalan `sqrt(` yozilgan bo'lsa) modul
   xato bermaydi — o'sha paytdagi holatni bor ko'rinishida chizadi.

   Har bir maydonning o'ng chetida ikkita tugma bor:
     * klaviatura belgisi — matematik klaviaturani ochadi/yopadi;
     * ro'yxat belgisi    — matn ko'rinishiga o'tkazadi (u yerda oddiy
       klaviatura bilan tahrirlash va nusxa ko'chirish qulay).
   ========================================================================== */

(function (global) {
  "use strict";

  var MAX_STEPS = 4000;   // cheksiz siklga tushmaslik uchun himoya

  var ICON = {
    keyboard: '<svg class="mfield-ico" viewBox="0 0 24 24" aria-hidden="true">' +
      '<rect x="2" y="6" width="20" height="12" rx="2"/>' +
      '<path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h.01M18 14h.01M9 14h6"/></svg>',
    raw: '<svg class="mfield-ico" viewBox="0 0 24 24" aria-hidden="true">' +
      '<path d="M4 7h16M4 12h16M4 17h16"/></svg>'
  };

  /* Ekranda boshqacha ko'rinadigan nomlar. */
  var SYMBOLS = { pi: "π", oo: "∞", theta: "θ", inf: "∞" };

  /* Tik (kursiv emas) yoziladigan funksiya nomlari. */
  var FUNCTIONS = [
    "sin", "cos", "tan", "cot", "sec", "csc", "tg", "ctg",
    "arcsin", "arccos", "arctan", "arcctg", "arctg",
    "asin", "acos", "atan", "acot",
    "sinh", "cosh", "tanh", "ln", "lg", "log", "log10", "log2", "exp",
    "sqrt", "cbrt", "root", "abs", "sign", "floor", "ceiling", "factorial",
    "gcd", "lcm", "binomial", "min", "max"
  ];

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* =====================================================================
     1. Matnni bo'laklarga ajratish (har bo'lakning o'rni saqlanadi)
     ===================================================================== */

  function tokenize(text) {
    var tokens = [];
    var i = 0;
    while (i < text.length) {
      var ch = text[i];
      if (ch === " " || ch === "\t") { i += 1; continue; }

      if (ch >= "0" && ch <= "9") {
        var numStart = i;
        while (i < text.length && ((text[i] >= "0" && text[i] <= "9") || text[i] === ".")) {
          i += 1;
        }
        tokens.push({ type: "num", text: text.slice(numStart, i), start: numStart });
        continue;
      }

      if (/[A-Za-z_]/.test(ch)) {
        var nameStart = i;
        while (i < text.length && /[A-Za-z0-9_]/.test(text[i])) { i += 1; }
        tokens.push({ type: "name", text: text.slice(nameStart, i), start: nameStart });
        continue;
      }

      tokens.push({ type: ch, text: ch, start: i });
      i += 1;
    }
    return tokens;
  }

  /* =====================================================================
     2. Tuzilmani yig'ish

     Grammatika Python (SymPy) bilan bir xil ustunlikda ishlaydi:

         expr  := unary (('+' | '-') unary)*
         unary := ('+' | '-') unary | term
         term  := power (('*' | '/') power | yashirin ko'paytirish)*
         power := atom ('^' unary)?
         atom  := son | nom | funksiya(...) | (ifoda) | |ifoda|

     Shu sababli ekranda ko'ringan narsa SymPy hisoblaydigan narsa bilan
     bir xil bo'ladi: `-2^2` -> −(2²), `1/2x` -> (1/2)·x, `2^3^2` -> 2^(3²).
     ===================================================================== */

  function parse(text) {
    var tokens = tokenize(text);
    var pos = 0;
    var steps = 0;

    function peek() { return tokens[pos]; }
    function at(type) { var token = tokens[pos]; return !!token && token.type === type; }
    function take() { return tokens[pos++]; }
    function guard() { steps += 1; return steps < MAX_STEPS; }

    function startsAtom() {
      var token = peek();
      if (!token) { return false; }
      return token.type === "num" || token.type === "name" ||
             token.type === "(" || token.type === "|";
    }

    function parseExpr() {
      var node = parseUnary();
      while ((at("+") || at("-")) && guard()) {
        var op = take();
        var right = parseUnary();
        node = { type: "bin", op: op.text, left: node, right: right, start: op.start };
      }
      return node;
    }

    function parseUnary() {
      if ((at("+") || at("-")) && guard()) {
        var op = take();
        return { type: "unary", op: op.text, arg: parseUnary(), start: op.start };
      }
      return parseTerm();
    }

    function parseTerm() {
      var node = parsePower();
      for (;;) {
        if (!guard()) { break; }
        if (at("*") || at("/")) {
          var op = take();
          var right = parsePower();
          node = op.text === "/"
            ? { type: "frac", num: node, den: right, start: op.start }
            : { type: "bin", op: "·", left: node, right: right, start: op.start };
        } else if (startsAtom()) {
          /* Yashirin ko'paytirish: `2x`, `455 sqrt(3)` */
          node = { type: "juxt", left: node, right: parsePower(), start: peek() ? peek().start : 0 };
        } else {
          break;
        }
      }
      return node;
    }

    function parsePower() {
      var base = parseAtom();
      if (at("^") && guard()) {
        take();
        return { type: "pow", base: base, exp: parseUnary() };
      }
      return base;
    }

    function parseAtom() {
      var token = peek();
      if (!token) { return null; }

      if (token.type === "num") {
        take();
        return { type: "num", text: token.text, start: token.start };
      }

      if (token.type === "name") {
        take();
        if (at("(")) {
          take();
          var args = [];
          if (!at(")")) {
            args.push(parseExpr());
            while (at(",") && guard()) { take(); args.push(parseExpr()); }
          }
          var closed = at(")");
          if (closed) { take(); }
          return {
            type: "call", name: token.text, args: args,
            closed: closed, start: token.start
          };
        }
        return { type: "name", text: token.text, start: token.start };
      }

      if (token.type === "(") {
        take();
        var body = at(")") ? null : parseExpr();
        var hasClose = at(")");
        if (hasClose) { take(); }
        return { type: "group", body: body, closed: hasClose, start: token.start };
      }

      if (token.type === "|") {
        take();
        var inner = at("|") ? null : parseExpr();
        var hasBar = at("|");
        if (hasBar) { take(); }
        return { type: "abs", body: inner, closed: hasBar, start: token.start };
      }

      /* Kutilmagan belgi (masalan yopilmagan qavs) — o'zini chiqaramiz. */
      take();
      return { type: "raw", text: token.text, start: token.start };
    }

    var root = parseExpr();
    while (pos < tokens.length && guard()) {
      var before = pos;
      var extra = parseExpr();
      if (pos === before) { pos += 1; continue; }
      root = extra && root ? { type: "juxt", left: root, right: extra } : (root || extra);
    }
    return root;
  }

  /* =====================================================================
     3. Chizish
     ===================================================================== */

  /* Har bir belgi alohida o'raladi — kursor aynan shu joyga tushadi. */
  function chars(text, start, cls) {
    var out = "";
    for (var i = 0; i < text.length; i += 1) {
      out += '<span class="mf-c' + (cls ? " " + cls : "") + '" data-s="' +
        (start + i) + '">' + esc(text[i]) + "</span>";
    }
    return out;
  }

  function anchor(symbol, start, cls) {
    return '<span class="' + cls + '" data-s="' + start + '">' + symbol + "</span>";
  }

  function isFunction(name) {
    return FUNCTIONS.indexOf(String(name).toLowerCase()) !== -1;
  }

  function draw(node) {
    if (!node) { return ""; }

    switch (node.type) {
      case "num":
        return chars(node.text, node.start, "mf-num");

      case "name":
        if (SYMBOLS[node.text]) {
          return anchor(SYMBOLS[node.text], node.start, "mf-c mf-var");
        }
        return chars(node.text, node.start,
          node.text.length === 1 && !isFunction(node.text) ? "mf-var" : "mf-fn");

      case "raw":
        return chars(node.text, node.start, "mf-raw");

      case "unary":
        return anchor(node.op === "-" ? "−" : "+", node.start, "mf-c mf-op") +
          draw(node.arg);

      case "bin":
        return draw(node.left) +
          anchor(node.op === "-" ? "−" : node.op, node.start, "mf-c mf-op") +
          draw(node.right);

      case "juxt":
        return draw(node.left) + '<span class="mf-gap"></span>' + draw(node.right);

      case "frac":
        return '<span class="mf-frac">' +
          '<span class="mf-fnum">' + (draw(node.num) || placeholder()) + "</span>" +
          '<span class="mf-fbar" data-s="' + node.start + '"></span>' +
          '<span class="mf-fden">' + (draw(node.den) || placeholder()) + "</span>" +
          "</span>";

      case "pow":
        return draw(node.base) +
          '<sup class="mf-sup">' + (draw(node.exp) || placeholder()) + "</sup>";

      case "group":
        return '<span class="mf-paren" data-s="' + node.start + '">(</span>' +
          draw(node.body) +
          (node.closed ? '<span class="mf-paren">)</span>' : "");

      case "abs":
        return '<span class="mf-bar" data-s="' + node.start + '">|</span>' +
          draw(node.body) +
          (node.closed ? '<span class="mf-bar">|</span>' : "");

      case "call":
        return drawCall(node);

      default:
        return "";
    }
  }

  function placeholder() {
    return '<span class="mf-box"></span>';
  }

  function radical(degree, body, start) {
    return '<span class="mf-root">' +
      (degree ? '<span class="mf-deg">' + degree + "</span>" : "") +
      '<span class="mf-radical" data-s="' + start + '">√</span>' +
      '<span class="mf-rad">' + (body || placeholder()) + "</span></span>";
  }

  function drawCall(node) {
    var name = String(node.name).toLowerCase();
    var args = node.args || [];
    var first = args.length ? draw(args[0]) : "";

    if (name === "sqrt") { return radical("", first, node.start); }
    if (name === "cbrt") { return radical("3", first, node.start); }
    if (name === "root") {
      return radical(args.length > 1 ? draw(args[1]) : "", first, node.start);
    }
    if (name === "abs") {
      return '<span class="mf-bar" data-s="' + node.start + '">|</span>' + first +
        '<span class="mf-bar">|</span>';
    }
    if (name === "log10" || name === "lg") {
      return chars("log", node.start, "mf-fn") + '<sub class="mf-sub">10</sub>' +
        '<span class="mf-paren">(</span>' + first + '<span class="mf-paren">)</span>';
    }
    if (name === "log2") {
      return chars("log", node.start, "mf-fn") + '<sub class="mf-sub">2</sub>' +
        '<span class="mf-paren">(</span>' + first + '<span class="mf-paren">)</span>';
    }
    if (name === "log" && args.length > 1) {
      return chars("log", node.start, "mf-fn") +
        '<sub class="mf-sub">' + draw(args[1]) + "</sub>" +
        '<span class="mf-paren">(</span>' + first + '<span class="mf-paren">)</span>';
    }
    if (name === "factorial") {
      return '<span class="mf-paren">(</span>' + first +
        '<span class="mf-paren">)</span><span class="mf-op">!</span>';
    }

    var body = "";
    for (var i = 0; i < args.length; i += 1) {
      if (i) { body += '<span class="mf-op">,</span>'; }
      body += draw(args[i]);
    }
    return chars(node.name, node.start, isFunction(node.name) ? "mf-fn" : "mf-var") +
      '<span class="mf-paren">(</span>' + (body || placeholder()) +
      (node.closed ? '<span class="mf-paren">)</span>' : "");
  }

  /* =====================================================================
     4. Maydon
     ===================================================================== */

  var fields = [];

  function stateOf(input) { return input.mathFieldState || null; }

  function render(input) {
    var state = stateOf(input);
    if (!state || state.raw) { return; }

    var value = input.value || "";
    var view = state.view;

    if (!value) {
      view.innerHTML = '<span class="mf-ph">' +
        esc(input.getAttribute("placeholder") || "javob") + "</span>";
    } else {
      var html = "";
      try {
        html = draw(parse(value));
      } catch (error) {          // hech qachon bo'lmasligi kerak — himoya
        html = "";
      }
      view.innerHTML = html || chars(value, 0, "mf-raw");
    }

    if (state.focused) { placeCaret(view, caretOf(input)); }
    scrollCaretIntoView(view);
  }

  function caretOf(input) {
    var position = input.selectionStart;
    if (position === null || position === undefined) { return input.value.length; }
    return position;
  }

  function placeCaret(view, offset) {
    var caret = document.createElement("span");
    caret.className = "mf-caret";

    var nodes = view.querySelectorAll("[data-s]");
    for (var i = 0; i < nodes.length; i += 1) {
      if (parseInt(nodes[i].dataset.s, 10) >= offset) {
        nodes[i].parentNode.insertBefore(caret, nodes[i]);
        return;
      }
    }
    view.appendChild(caret);
  }

  function scrollCaretIntoView(view) {
    var caret = view.querySelector(".mf-caret");
    if (!caret) { return; }
    var viewBox = view.getBoundingClientRect();
    var caretBox = caret.getBoundingClientRect();
    if (caretBox.right > viewBox.right - 6) {
      view.scrollLeft += caretBox.right - viewBox.right + 24;
    } else if (caretBox.left < viewBox.left + 6) {
      view.scrollLeft -= viewBox.left - caretBox.left + 24;
    }
  }

  /* Formulani bosganda kursor o'sha joyga tushadi. */
  function caretFromPoint(input, event) {
    var atom = event.target.closest ? event.target.closest("[data-s]") : null;
    if (!atom) { return input.value.length; }

    var offset = parseInt(atom.dataset.s, 10);
    var box = atom.getBoundingClientRect();
    if (event.clientX > box.left + box.width / 2) { offset += 1; }
    return Math.max(0, Math.min(offset, input.value.length));
  }

  function setCaret(input, offset) {
    try { input.setSelectionRange(offset, offset); } catch (error) { /* qo'llamaydi */ }
    try { input.focus({ preventScroll: true }); } catch (error) { input.focus(); }
    render(input);
  }

  function setRaw(input, raw) {
    var state = stateOf(input);
    if (!state) { return; }
    state.raw = !!raw;
    state.wrap.classList.toggle("is-raw", state.raw);
    if (state.raw) {
      try { input.focus({ preventScroll: true }); } catch (error) { input.focus(); }
    } else {
      render(input);
    }
  }

  function attach(input, options) {
    if (!input || input.dataset.mfieldReady === "1") { return; }
    if (input.tagName === "TEXTAREA") { return; }   // ko'p qatorli maydonlar — matn
    input.dataset.mfieldReady = "1";
    options = options || {};

    var wrap = document.createElement("div");
    wrap.className = "mfield";
    input.parentNode.insertBefore(wrap, input);

    var view = document.createElement("div");
    view.className = "mfield-view";

    var tools = document.createElement("div");
    tools.className = "mfield-tools";
    tools.innerHTML =
      '<button type="button" class="mfield-btn" data-mf="keyboard"' +
      ' aria-label="Matematik klaviatura" title="Matematik klaviatura">' +
      ICON.keyboard + "</button>" +
      '<button type="button" class="mfield-btn" data-mf="raw"' +
      ' aria-label="Matn ko‘rinishi" title="Matn ko‘rinishida tahrirlash">' +
      ICON.raw + "</button>";

    wrap.appendChild(view);
    wrap.appendChild(input);
    wrap.appendChild(tools);
    wrap.classList.add("is-live");
    input.classList.add("mfield-src");

    input.mathFieldState = { wrap: wrap, view: view, raw: false, focused: false };
    fields.push(input);

    view.addEventListener("mousedown", function (event) {
      event.preventDefault();
      setCaret(input, caretFromPoint(input, event));
      if (global.MathPad && !global.MathPad.isOpen()) { global.MathPad.open(input); }
    });
    view.addEventListener("touchstart", function () {
      /* Sensorli ekranda `click` keyin keladi — fokusni o'sha yerda beramiz. */
    }, { passive: true });
    view.addEventListener("click", function (event) {
      setCaret(input, caretFromPoint(input, event));
      if (global.MathPad) { global.MathPad.open(input); }
    });

    tools.addEventListener("mousedown", function (event) { event.preventDefault(); });
    tools.addEventListener("click", function (event) {
      var button = event.target.closest("[data-mf]");
      if (!button) { return; }
      event.preventDefault();
      if (button.dataset.mf === "keyboard") {
        if (global.MathPad) {
          if (global.MathPad.active() === input && global.MathPad.isOpen()) {
            global.MathPad.close();
          } else {
            setRaw(input, false);
            global.MathPad.open(input);
          }
        }
      } else {
        setRaw(input, !stateOf(input).raw);
      }
    });

    input.addEventListener("input", function () { render(input); });
    input.addEventListener("keyup", function () { render(input); });
    input.addEventListener("click", function () { render(input); });
    input.addEventListener("focus", function () {
      stateOf(input).focused = true;
      render(input);
    });
    input.addEventListener("blur", function () {
      stateOf(input).focused = false;
      render(input);
    });
    /* Klaviatura kursorni siljitganda ham qayta chiziladi. */
    input.addEventListener("mpad:change", function () { render(input); });

    render(input);
  }

  function refresh(input) {
    if (input) { render(input); return; }
    fields.forEach(function (field) {
      if (document.contains(field)) { render(field); }
    });
  }

  function detached() {
    fields = fields.filter(function (field) { return document.contains(field); });
  }

  global.MathField = {
    attach: attach,
    refresh: refresh,
    reset: detached,
    setRaw: setRaw,
    /* Sinov va boshqa modullar uchun: matnni HTML ga o'girish. */
    toHtml: function (text) { return draw(parse(String(text || ""))); }
  };
})(window);
