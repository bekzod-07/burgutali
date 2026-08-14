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
         power := atom ('^' expo)?
         expo  := ('+' | '-') expo | power
         atom  := son | nom | funksiya(...) | (ifoda) | |ifoda|

     Shu sababli ekranda ko'ringan narsa SymPy hisoblaydigan narsa bilan
     bir xil bo'ladi: `-2^2` -> −(2²), `1/2x` -> (1/2)·x, `2^3^2` -> 2^(3²),
     `2^(3)4` -> 2³·4.
     ===================================================================== */

  function parse(text) {
    var tokens = tokenize(text);
    var pos = 0;
    var steps = 0;

    function peek() { return tokens[pos]; }
    function at(type) { var token = tokens[pos]; return !!token && token.type === type; }
    function take() { return tokens[pos++]; }
    function guard() { steps += 1; return steps < MAX_STEPS; }

    /* Oxirgi o'qilgan bo'lakdan keyingi o'rin. */
    function lastEnd() {
      var token = tokens[pos - 1];
      return token ? token.start + token.text.length : 0;
    }

    /*
       Tugunga uning matndagi tugash o'rnini yozadi.
       Kursor tuzilmadan (masalan darajadan) chiqqanini shu orqali
       bilamiz — chizishda «quyruq» belgisi qo'yiladi.
    */
    function fin(node) {
      if (node) { node.end = lastEnd(); }
      return node;
    }

    /*
       Modul ichida turgan `|` — yopiluvchi tayoqcha, yangi modulning
       boshi emas. Aks holda `|x-1|` da oxirgi tayoqcha ko'paytuvchi
       bo'lib o'qilib, ifoda tugallanmagan bo'lib qolar edi.
    */
    var bars = 0;

    function startsAtom() {
      var token = peek();
      if (!token) { return false; }
      if (token.type === "|") { return bars === 0; }
      return token.type === "num" || token.type === "name" || token.type === "(";
    }

    function parseExpr() {
      var node = parseUnary();
      while ((at("+") || at("-")) && guard()) {
        var op = take();
        var right = parseUnary();
        node = fin({ type: "bin", op: op.text, left: node, right: right, start: op.start });
      }
      return node;
    }

    function parseUnary() {
      if ((at("+") || at("-")) && guard()) {
        var op = take();
        return fin({ type: "unary", op: op.text, arg: parseUnary(), start: op.start });
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
          node = fin(op.text === "/"
            ? { type: "frac", num: node, den: right, start: op.start }
            : { type: "bin", op: "·", left: node, right: right, start: op.start });
        } else if (startsAtom()) {
          /* Yashirin ko'paytirish: `2x`, `455 sqrt(3)` */
          node = fin({
            type: "juxt", left: node, right: parsePower(),
            start: peek() ? peek().start : 0
          });
        } else {
          break;
        }
      }
      return node;
    }

    function parsePower() {
      var base = parseAtom();
      if (at("^") && guard()) {
        var op = take();
        return fin({ type: "pow", base: base, exp: parseExponent(), opAt: op.start });
      }
      return base;
    }

    /*
       Ko'rsatkich — faqat bitta bo'lak (kerak bo'lsa ishorasi bilan).
       Python/SymPy ham shunday hisoblaydi: `2^3x` = (2³)·x, `2^(3)4` = 8·4,
       `2^3^2` = 2^(3²), `2^-1` = 0,5. Ya'ni darajadan keyin yozilgan son
       ko'rsatkichga qo'shilib ketmaydi — u pastda, asosiy satrda qoladi.
    */
    function parseExponent() {
      if ((at("+") || at("-")) && guard()) {
        var op = take();
        return fin({ type: "unary", op: op.text, arg: parseExponent(), start: op.start });
      }
      return parsePower();
    }

    function parseAtom() {
      var token = peek();
      if (!token) { return null; }

      /*
         Amal belgisi atom o'rnida turibdi — masalan foydalanuvchi son
         yozmasdan kasr yoki daraja tugmasini bosgan (`/`, `^`). Belgini
         yuqoridagi qoidalar o'zi oladi, biz esa bo'sh joy qoldiramiz —
         natijada ekranda bo'sh to'rtburchak chiziladi.
      */
      if (token.type === "/" || token.type === "*" || token.type === "^" ||
          token.type === "," || token.type === ")") {
        return null;
      }

      if (token.type === "num") {
        take();
        return fin({ type: "num", text: token.text, start: token.start });
      }

      if (token.type === "name") {
        take();
        if (at("(")) {
          var open = take();
          var args = [];
          var commas = [];       // bo'sh argument qayerga yozilishini bilish uchun
          if (!at(")")) {
            args.push(parseExpr());
            while (at(",") && guard()) {
              commas.push(take().start);
              args.push(parseExpr());
            }
          }
          var closed = at(")");
          if (closed) { take(); }
          return fin({
            type: "call", name: token.text, args: args, commas: commas,
            closed: closed, start: token.start, openAt: open.start
          });
        }
        return fin({ type: "name", text: token.text, start: token.start });
      }

      if (token.type === "(") {
        take();
        var body = at(")") ? null : parseExpr();
        var hasClose = at(")");
        if (hasClose) { take(); }
        return fin({ type: "group", body: body, closed: hasClose, start: token.start });
      }

      if (token.type === "|") {
        take();
        bars += 1;
        var inside = at("|") ? null : parseExpr();
        bars -= 1;
        var hasBar = at("|");
        if (hasBar) { take(); }
        return fin({ type: "abs", body: inside, closed: hasBar, start: token.start });
      }

      /* Kutilmagan belgi (masalan yopilmagan qavs) — o'zini chiqaramiz. */
      take();
      return fin({ type: "raw", text: token.text, start: token.start });
    }

    /*
       Asosiy ifodadan keyin qolgan bo'laklar (masalan ortiqcha yopiladigan
       qavs) ham chiziladi — hech narsa ko'rinmay qolib ketmasin.
    */
    var parts = [];
    var root = parseExpr();
    if (root) { parts.push(root); }

    while (pos < tokens.length && guard()) {
      var before = pos;
      var extra = parseExpr();
      if (pos === before) {
        var stray = take();
        extra = { type: "raw", text: stray.text, start: stray.start };
      }
      if (extra) { parts.push(extra); }
    }

    if (!parts.length) { return null; }
    if (parts.length === 1) { return parts[0]; }
    return { type: "seq", items: parts, end: parts[parts.length - 1].end };
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

  /*
     Ifoda yopiladigan belgi bilan tugaydimi (`)` yoki `|`).

     Tugasa, o'sha o'rin tuzilmaning aniq chegarasi bo'ladi: kursor
     shu yerga kelganda daraja (yoki ildiz, kasr) ichida emas, balki
     undan tashqarida — asosiy satrda turishi kerak.
  */
  function closesHere(node) {
    if (!node) { return false; }
    switch (node.type) {
      case "group": case "abs": case "call": return !!node.closed;
      case "bin": case "juxt": return closesHere(node.right);
      case "unary": return closesHere(node.arg);
      case "frac": return closesHere(node.den);
      case "pow": return closesHere(node.exp);
      case "seq": return closesHere(node.items[node.items.length - 1]);
      default: return false;
    }
  }

  /*
     «Quyruq» — tuzilmadan keyingi ko'rinmas belgi.

     Ekranda hech narsa chizmaydi, lekin kursor shu o'ringa kelganda
     u tuzilmadan tashqarida turadi. Aynan shu narsa `2^(3)` da «›»
     tugmasidan keyin kursorni darajadan pastga tushiradi.
  */
  function tail(node, when) {
    if (!when || !node || node.hushed || typeof node.end !== "number") { return ""; }
    return '<span class="mf-tail" data-s="' + node.end + '"></span>';
  }

  /*
     Ichkaridagi tuzilmaning quyrug'ini o'chiradi.

     `2^sqrt(3)` da ildiz ham, daraja ham bir xil o'rinda tugaydi. Ikkala
     joyga ham belgi qo'yilsa kursor ichkaridagisiga — daraja ichiga —
     ilashib qolishi mumkin. Shuning uchun ichkaridagisi olib tashlanadi:
     o'sha o'rin endi faqat tashqi tuzilmaga tegishli.
  */
  function hush(node, offset) {
    while (node && node.end === offset) {
      node.hushed = true;
      switch (node.type) {
        case "group": node = node.body; break;
        case "bin": case "juxt": node = node.right; break;
        case "unary": node = node.arg; break;
        case "frac": node = node.den; break;
        case "pow": node = node.exp; break;
        case "seq": node = node.items[node.items.length - 1]; break;
        default: return;
      }
    }
  }

  /*
     Tuzilma ichidagi ifoda.

     Kasr, daraja, ildiz va modul o'zi guruhlab turadi — ichidagi qavslar
     ortiqcha. Shuning uchun `2^(3)` ekranda `2³` bo'lib ko'rinadi,
     `(1+2)/3` esa oddiy kasr bo'lib chiziladi.
  */
  function drawInner(node) {
    if (node && node.type === "group") {
      return draw(node.body) || slot(node.start + 1);
    }
    return draw(node);
  }

  /*
     Ko'paytmaning bir tomoni.

     Kasr o'zi guruhlab turadi, shuning uchun `455/3 · (2/5)` dagi qavslar
     ortiqcha — ikkala kasr yonma-yon chiziladi.
  */
  function factor(node, op) {
    if (op === "·" && node && node.type === "group" &&
        node.body && node.body.type === "frac") {
      return drawInner(node) + tail(node, node.closed);
    }
    return draw(node);
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

      case "seq":
        return node.items.map(draw).join("");

      case "unary":
        return anchor(node.op === "-" ? "−" : "+", node.start, "mf-c mf-op mf-neg") +
          (draw(node.arg) || slot(node.start + 1));

      case "bin":
        return (factor(node.left, node.op) || slot(node.start)) +
          anchor(node.op === "-" ? "−" : node.op, node.start, "mf-c mf-op") +
          (factor(node.right, node.op) || slot(node.start + 1));

      case "juxt":
        return draw(node.left) + '<span class="mf-gap"></span>' + draw(node.right);

      case "frac":
        hush(node.den, node.end);
        return '<span class="mf-frac">' +
          '<span class="mf-fnum">' + (drawInner(node.num) || slot(node.start)) + "</span>" +
          '<span class="mf-fbar" data-s="' + node.start + '"></span>' +
          '<span class="mf-fden">' + (drawInner(node.den) || slot(node.start + 1)) +
          "</span></span>" + tail(node, closesHere(node.den));

      /*
         Daraja. Ko'rsatkich qavs ichida yozilgani uchun qavslarning o'zi
         chizilmaydi — yuqoriga ko'tarilganining o'zi yetarli. Qavs yopilgan
         bo'lsa oxiriga «quyruq» qo'yiladi: kursor darajadan pastga tushadi.
      */
      case "pow":
        hush(node.exp, node.end);
        return (draw(node.base) || slot(node.opAt)) +
          '<sup class="mf-sup">' + (drawInner(node.exp) || slot(node.opAt + 1)) + "</sup>" +
          tail(node, closesHere(node.exp));

      case "group":
        return '<span class="mf-paren" data-s="' + node.start + '">(</span>' +
          (draw(node.body) || slot(node.start + 1)) +
          (node.closed ? '<span class="mf-paren">)</span>' : "") + tail(node, node.closed);

      case "abs":
        return '<span class="mf-bar" data-s="' + node.start + '">|</span>' +
          (drawInner(node.body) || slot(node.start + 1)) +
          (node.closed ? '<span class="mf-bar">|</span>' : "") + tail(node, node.closed);

      case "call":
        return drawCall(node);

      default:
        return "";
    }
  }

  /*
     To'ldirilmagan joy — bo'sh to'rtburchak. `offset` shu joyga yozilganda
     matn qaysi o'ringa tushishini bildiradi: kursor ham aynan shu
     to'rtburchakning ichida ko'rinadi.
  */
  function slot(offset) {
    return '<span class="mf-box"' +
      (offset === undefined || offset === null ? "" : ' data-s="' + offset + '"') +
      "></span>";
  }

  function radical(degree, body, start) {
    /* Daraja hali yozilmagan bo'lsa, to'rtburchakka biroz ko'proq joy kerak. */
    var cls = "mf-deg" + (degree.indexOf("mf-box") === -1 ? "" : " is-empty");
    return '<span class="mf-root">' +
      (degree ? '<span class="' + cls + '">' + degree + "</span>" : "") +
      '<span class="mf-radical" data-s="' + start + '">√</span>' +
      '<span class="mf-rad">' + body + "</span></span>";
  }

  function drawCall(node) {
    return callBody(node) + tail(node, node.closed);
  }

  /*
     Funksiyaning `n`-argumenti chizilgan ko'rinishi.

     Argument bo'sh bo'lsa — bo'sh to'rtburchak chiziladi va u matndagi
     o'z o'rniga bog'lanadi (birinchisi ochiladigan qavsdan keyin,
     qolganlari o'zidan oldingi verguldan keyin). Shu tufayli kursor
     `log(,)` dagi ikkala katakka ham to'g'ri tushadi.
  */
  function callArg(node, index, whole) {
    var args = node.args || [];
    var drawn = args.length > index ? (whole ? draw : drawInner)(args[index]) : "";
    if (drawn) { return drawn; }

    var commas = node.commas || [];
    var at = index === 0
      ? (node.openAt === undefined ? node.start : node.openAt) + 1
      : (commas.length >= index ? commas[index - 1] + 1 : null);
    return slot(at);
  }

  function callBody(node) {
    var name = String(node.name).toLowerCase();
    var args = node.args || [];

    if (name === "sqrt") { return radical("", callArg(node, 0), node.start); }
    if (name === "cbrt") { return radical("3", callArg(node, 0), node.start); }
    if (name === "root") {
      return radical(callArg(node, 1), callArg(node, 0), node.start);
    }
    if (name === "abs") {
      return '<span class="mf-bar" data-s="' + node.start + '">|</span>' +
        callArg(node, 0) + '<span class="mf-bar">|</span>';
    }
    if (name === "log10" || name === "lg") {
      return logHtml(node, "10", callArg(node, 0, true));
    }
    if (name === "log2") {
      return logHtml(node, "2", callArg(node, 0, true));
    }
    if (name === "log" && args.length > 1) {
      return logHtml(node, callArg(node, 1), callArg(node, 0, true));
    }
    if (name === "factorial") {
      return '<span class="mf-paren">(</span>' + callArg(node, 0, true) +
        '<span class="mf-paren">)</span><span class="mf-op">!</span>';
    }

    var body = "";
    for (var i = 0; i < Math.max(args.length, 1); i += 1) {
      if (i) { body += '<span class="mf-op">,</span>'; }
      body += callArg(node, i, true);
    }
    return chars(node.name, node.start, isFunction(node.name) ? "mf-fn" : "mf-var") +
      '<span class="mf-paren">(</span>' + body +
      (node.closed ? '<span class="mf-paren">)</span>' : "");
  }

  function logHtml(node, base, body) {
    return chars("log", node.start, "mf-fn") +
      '<sub class="mf-sub">' + base + "</sub>" +
      '<span class="mf-paren">(</span>' + body +
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

  /* Belgi maydonning ichida necha qavat chuqurlikda turibdi. */
  function depthOf(node, root) {
    var level = 0;
    var walk = node.parentNode;
    while (walk && walk !== root) { level += 1; walk = walk.parentNode; }
    return level;
  }

  /*
     Kursorni chizilgan formulada o'z o'rniga qo'yadi.

     Qoida sodda: matndagi `offset` o'rniga aniq mos keladigan belgi
     topilsa, kursor o'sha belgidan oldin turadi; topilmasa — undan
     oldingi eng yaqin belgidan keyin turadi.

     Bitta o'ringa bir nechta belgi to'g'ri kelsa (masalan daraja tugagan
     joy bilan keyingi ko'paytuvchi boshlangan joy), eng tashqaridagisi
     tanlanadi — shunda kursor daraja ichida qolib ketmaydi.
  */
  function placeCaret(view, offset) {
    var caret = document.createElement("span");
    caret.className = "mf-caret";

    var nodes = view.querySelectorAll("[data-s]");
    var exact = null;
    var exactDepth = 0;
    var exactBox = false;
    var before = null;
    var beforeAt = -1;
    var beforeDepth = 0;

    for (var i = 0; i < nodes.length; i += 1) {
      var node = nodes[i];
      var at = parseInt(node.dataset.s, 10);
      if (isNaN(at)) { continue; }
      var level = depthOf(node, view);

      if (at === offset) {
        /*
           Bo'sh to'rtburchak ustunroq: kursor o'sha katakning ichida
           ko'rinishi kerak. Qolganlarida eng tashqaridagisi tanlanadi —
           shunda kursor daraja yoki ildiz ichida qolib ketmaydi.
        */
        var box = node.classList.contains("mf-box");
        if (!exact || (box && !exactBox) || (box === exactBox && level < exactDepth)) {
          exact = node;
          exactDepth = level;
          exactBox = box;
        }
      } else if (at < offset) {
        if (at > beforeAt || (at === beforeAt && level < beforeDepth)) {
          before = node;
          beforeAt = at;
          beforeDepth = level;
        }
      }
    }

    if (exact) { putCaret(exact, false, caret); return; }
    if (before) { putCaret(before, true, caret); return; }
    view.insertBefore(caret, view.firstChild);
  }

  function putCaret(node, after, caret) {
    /* Bo'sh to'rtburchak — kursor uning ichida turadi. */
    if (node.classList.contains("mf-box")) {
      node.classList.add("is-active");
      node.appendChild(caret);
      return;
    }

    /*
       Kasr chizig'i — kursor chiziq bilan surat orasiga tushib qolmasin:
       chiziqdan oldingi o'rin suratning oxiri, keyingisi esa maxrajning
       boshi hisoblanadi.
    */
    if (node.classList.contains("mf-fbar")) {
      var part = after ? node.nextElementSibling : node.previousElementSibling;
      if (part) {
        if (after) { part.insertBefore(caret, part.firstChild); }
        else { part.appendChild(caret); }
        return;
      }
    }

    node.parentNode.insertBefore(caret, after ? node.nextSibling : node);
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

  /*
     Formulada to'ldirilmagan joy (bo'sh to'rtburchak) bormi.

     Bor bo'lsa, ifoda hali tugallanmagan — jonli tekshiruv bekorga
     «tahlil qilib bo'lmadi» deb ogohlantirmasligi kerak.
  */
  function incomplete(input) {
    var state = stateOf(input);
    if (!state || state.raw) { return false; }
    return state.view.querySelectorAll(".mf-box").length > 0;
  }

  global.MathField = {
    attach: attach,
    refresh: refresh,
    reset: detached,
    setRaw: setRaw,
    incomplete: incomplete,
    /* Sinov va boshqa modullar uchun: matnni HTML ga o'girish. */
    toHtml: function (text) { return draw(parse(String(text || ""))); }
  };
})(window);
