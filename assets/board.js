/* Mission Control board · jacknbauhs.com
   Every section reads a JSON file in /data.
   Kept by hand: file.json (The File, Tue / Thu / Sat) and cards/*.json, calls.json, drops.json.
   Written nightly by Mission Control (board_publish): meta.json, movers.json, flags.json, rip_ev.json,
   digest.json and watching.json (the Today strip; both may be missing until Mission Control publishes them).
   A missing or broken file only blanks its own section. */
(function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var SVGNS = "http://www.w3.org/2000/svg";
  var COLORS = {
    text: "#ECEAF6", muted: "#9A96B8", grid: "rgba(236,234,246,0.08)", accent: "#A78BFA",
    accentText: "#C4B5FD", flag: "#F472B6", flagText: "#F9A8D4", warn: "#FBBF24", neutral: "#9A96B8",
    sealed: "#C98500", ev: "#8B5CF6", rip: "#34D399", surface: "#14122A"
  };
  // Sale Integrity labels, in the order the legend shows them.
  var LABELS = {
    ORGANIC: { text: "Clean", chip: "chip-ok", meaning: "A real sale of the right card. Counts in full." },
    BEST_OFFER: { text: "Best offer", chip: "chip-info", meaning: "Shown at the accepted price, not the asking price." },
    RELIST: { text: "Relist", chip: "chip-warn", meaning: "The same listing sold more than once. The first sale may not have gone through. Counts half." },
    DUPLICATE: { text: "Duplicate", chip: "chip-neutral", meaning: "One sale recorded twice. Counted once." },
    DATA_ERROR: { text: "Doesn't belong", chip: "chip-flag", meaning: "Wrong card, wrong grade, or a price no real copy sells for. Left out." },
    EVENT_DRIVEN: { text: "Event", chip: "chip-info", meaning: "A jump tied to news, like a reprint or a viral pull. Counts half until it holds." },
    SUPPLY_SHOCK: { text: "Supply shock", chip: "chip-warn", meaning: "More copies selling while the price sits flat or falls." },
    THIN_SPIKE: { text: "Thin spike", chip: "chip-warn", meaning: "Up on a handful of sales, with no volume behind it." },
    SUSPECT_PUMP: { text: "Suspect pump", chip: "chip-flag", meaning: "A spike with warning signs, like one seller doing most of the selling. Left out." },
    SUSPECT_WASH: { text: "Suspect wash", chip: "chip-flag", meaning: "The same slab selling in a loop, or bidding that looks staged. Left out." },
    UNCONFIRMED: { text: "Unconfirmed", chip: "chip-neutral", meaning: "No checked sales behind the move yet." }
  };
  var GAMES = [
    { id: "pokemon", name: "Pokémon" }, { id: "one_piece", name: "One Piece" },
    { id: "yugioh", name: "Yu-Gi-Oh" }, { id: "sports", name: "Sports" }
  ];
  var TYPES = {
    booster_box: "Booster box", etb: "Elite Trainer Box", booster_bundle: "Booster bundle", bundle: "Bundle",
    case: "Case", pack: "Pack", blaster: "Blaster", hobby_box: "Hobby box", display: "Display", tin: "Tin"
  };
  // The File's stance: a closed set, same as share/render.py. Any other value is not shown. A stance is a read, not advice.
  var STANCES = { "STRONG WATCH": "chip-accent", WATCH: "chip-info", NEUTRAL: "chip-neutral", CAUTION: "chip-warn", PASS: "chip-down" };
  var SLOTS = ["Tue story", "Thu market", "Sat build"];
  var FILE_DAYS = [2, 4, 6]; // The File runs Tue, Thu and Sat, Central time (0 is Sunday)
  var WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  // What Mission Control's since-yesterday list covers (movers.json one_day). Keep in step with its config/board.py.
  var ONE_DAY = { minPrice: 20, minPct: 3 };
  var SOURCES = { youtube: "YouTube", reddit: "Reddit", news: "News" };

  /* ---------- helpers ---------- */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (attrs[k] == null) return;
      if (k === "text") node.textContent = attrs[k];
      else if (k === "class") node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return node;
  }
  function svg(tag, attrs) {
    var node = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    return node;
  }
  function svgText(attrs, text) { var t = svg("text", attrs); t.textContent = text; return t; }
  function parseDate(s) { var p = String(s).slice(0, 10).split("-"); return new Date(Date.UTC(+p[0], +p[1] - 1, +(p[2] || 1))); }
  function fmtDate(s) { var d = parseDate(s); return MONTHS[d.getUTCMonth()] + " " + d.getUTCDate(); }
  function fmtDateYear(s) { var d = parseDate(s); return fmtDate(s) + ", " + d.getUTCFullYear(); }
  function isNum(n) { return typeof n === "number" && isFinite(n); }
  function money(n) {
    if (!isNum(n)) return "—";
    var whole = Math.abs(n - Math.round(n)) < 0.005;
    return "$" + n.toLocaleString("en-US", { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2 });
  }
  function moneyC(c) { return isNum(c) ? money(c / 100) : "—"; }
  function moneyShort(n) { return n >= 1000 ? "$" + (Math.round(n / 100) / 10).toLocaleString("en-US") + "k" : money(n); }
  function pct(n, digits) {
    if (!isNum(n)) return "—";
    var v = Math.abs(n).toFixed(digits == null ? 0 : digits);
    return (n > 0 ? "+" : n < 0 ? "−" : "") + v + "%";
  }
  function share(f) { return isNum(f) ? Math.round(f * 100) + "%" : "—"; }
  function sentence(t, period) {
    t = String(t || "").trim();
    if (!t) return "";
    t = t.charAt(0).toUpperCase() + t.slice(1);
    return period && !/[.!?]$/.test(t) ? t + "." : t;
  }
  function labelInfo(label) {
    if (Object.prototype.hasOwnProperty.call(LABELS, label)) return LABELS[label];
    return { text: String(label || "").toLowerCase().replace(/_/g, " ").replace(/^\w/, function (c) { return c.toUpperCase(); }), chip: "chip-neutral" };
  }
  function chip(label) { var info = labelInfo(label); return el("span", { class: "chip " + info.chip, text: info.text.toUpperCase() }); }
  function getJSON(path) {
    return fetch(path, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) { var err = new Error(path + " " + r.status); err.status = r.status; throw err; }
      return r.json();
    });
  }
  // A file that fails to load comes back as null, so only its own section goes quiet.
  // optional: a file that may not be published yet; its 404 is expected, so it isn't logged.
  function load(path, optional) {
    return getJSON(path).catch(function (e) { if (window.console && !(optional && e.status === 404)) console.warn(e); return null; });
  }
  function safe(fn) { try { fn(); } catch (e) { if (window.console) console.error(e); } }
  function daysFromToday(iso) {
    var now = new Date();
    var today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((parseDate(iso).getTime() - today) / 86400000);
  }
  function updatedLabel(meta) {
    if (!meta) return "";
    if (meta.generated_at) {
      var d = new Date(meta.generated_at);
      if (!isNaN(d.getTime())) {
        try {
          return "Updated " + new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", weekday: "short", month: "short", day: "numeric", year: "numeric" })
            .format(d).replace(",", "");
        } catch (e) { return "Updated " + fmtDateYear(meta.generated_at); }
      }
    }
    return meta.updated_label ? "Updated " + meta.updated_label : "";
  }
  function emptyCard(title, text) {
    return el("div", { class: "card empty-state" }, [el("h3", { text: title }), text ? el("p", { text: text }) : null]);
  }
  function stack(main, sub, cls) {
    return el("span", { class: "stack" }, [el("span", { class: cls || "", text: main }), sub ? el("span", { class: "sub", text: sub }) : null]);
  }
  function niceStep(raw) {
    if (!(raw > 0)) return 1;
    var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }
  function axisMoney(v) { return v >= 1000 ? "$" + (v / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 }) + "k" : "$" + Math.round(v); }
  function isDate(s) { return typeof s === "string" && /^\d{4}-\d{2}-\d{2}/.test(s); }
  function str(s) { return typeof s === "string" ? s.trim() : ""; }
  // Today's date in Central time, YYYY-MM-DD. The File's days and "since yesterday" are Central.
  function centralToday() {
    var now = new Date();
    try {
      var parts = {};
      new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit" })
        .formatToParts(now).forEach(function (p) { parts[p.type] = p.value; });
      if (parts.year && parts.month && parts.day) return parts.year + "-" + parts.month + "-" + parts.day;
    } catch (e) { /* no Intl time zones: fall back to the browser's own day */ }
    return now.getFullYear() + "-" + ("0" + (now.getMonth() + 1)).slice(-2) + "-" + ("0" + now.getDate()).slice(-2);
  }
  // "today" on a File day whose File isn't up yet, else the next Tue, Thu or Sat ("Tuesday, Oct 6").
  function nextFile(file) {
    var today = centralToday(), t0 = parseDate(today).getTime();
    for (var i = 0; i < 8; i++) {
      var day = new Date(t0 + i * 86400000), iso = day.toISOString().slice(0, 10);
      if (FILE_DAYS.indexOf(day.getUTCDay()) === -1) continue;
      if (i === 0) { if (file && file.date === iso) continue; return "today"; }
      return WEEKDAYS[day.getUTCDay()] + ", " + fmtDate(iso);
    }
    return "";
  }
  function stanceChip(stance) {
    var key = str(stance).toUpperCase().replace(/\s+/g, " ");
    if (!Object.prototype.hasOwnProperty.call(STANCES, key)) return null;
    return el("span", { class: "chip " + STANCES[key], title: "A stance is a read on the numbers, not advice", text: "STANCE · " + key });
  }
  // Why now, what could break it, what we're watching: the File's (or a card's) short labeled lines. Null when it has none.
  function storyLines(src) {
    var rows = [["Why now", src.why_now], ["What could break it", src.risk], ["What we're watching", src.what_to_watch]]
      .filter(function (r) { return str(r[1]); });
    if (!rows.length) return null;
    return el("dl", { class: "story-lines" }, rows.map(function (r) {
      return el("div", {}, [el("dt", { text: r[0] }), el("dd", { text: sentence(str(r[1]), true) })]);
    }));
  }

  /* ---------- sales chart: every sale as a dot, the clean monthly median as a step line ---------- */
  function salesChart(card, opts) {
    opts = opts || {};
    var W = opts.width || 860, H = opts.height || 400;
    var L = 64, R = 20, T = 30, B = 44;
    var start = parseDate(card.window.start).getTime(), end = parseDate(card.window.end).getTime();
    var inScale = card.sales.filter(function (s) { return s.weight > 0; }).map(function (s) { return s.price; });
    var lo = Math.min.apply(null, inScale), hi = Math.max.apply(null, inScale);
    var step = hi - lo > 20000 ? 10000 : 5000;
    var yMin = Math.max(0, Math.floor((lo * 0.9) / step) * step), yMax = Math.ceil((hi * 1.06) / step) * step;
    var x = function (iso) { return L + (parseDate(iso).getTime() - start) * (W - L - R) / (end - start); };
    var y = function (v) { return T + (yMax - v) * (H - T - B) / (yMax - yMin); };
    var root = svg("svg", { viewBox: "0 0 " + W + " " + H, class: "chart", role: "img" });
    var first = card.monthly_clean[Object.keys(card.monthly_clean)[0]];
    var lastKey = Object.keys(card.monthly_clean).slice(-1)[0];
    root.setAttribute("aria-label", card.name + " " + card.tier + ": every sold record from " + fmtDate(card.window.start) +
      " with the clean monthly median, from " + money(first) + " to " + money(card.monthly_clean[lastKey]) + ". Flagged sales are marked.");

    for (var v = yMin; v <= yMax; v += step) {
      root.appendChild(svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: COLORS.grid }));
      root.appendChild(svgText({ x: L - 10, y: y(v) + 4, "text-anchor": "end", "font-size": 12, fill: COLORS.muted, "font-family": "Geist Mono, monospace" }, "$" + (v / 1000) + "k"));
    }
    // month labels
    var d = parseDate(card.window.start);
    while (d.getTime() <= end) {
      var iso = d.toISOString().slice(0, 10);
      var mid = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 15)).toISOString().slice(0, 10);
      root.appendChild(svgText({ x: x(mid), y: H - 14, "text-anchor": "middle", "font-size": 12, fill: COLORS.muted, "font-family": "Geist Mono, monospace", "letter-spacing": 1 }, MONTHS[d.getUTCMonth()].toUpperCase()));
      if (iso !== card.window.start) root.appendChild(svg("line", { x1: x(iso), x2: x(iso), y1: T, y2: H - B, stroke: COLORS.grid, "stroke-dasharray": "2 6" }));
      d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
    }
    // event marker
    if (card.event) {
      var ex = x(card.event.date);
      root.appendChild(svg("line", { x1: ex, x2: ex, y1: T - 8, y2: H - B, stroke: COLORS.accentText, "stroke-dasharray": "3 4" }));
      root.appendChild(svgText({ x: ex - 8, y: T + 6, "text-anchor": "end", "font-size": 11, fill: COLORS.accentText, "font-family": "Geist Mono, monospace" }, fmtDate(card.event.date).toUpperCase() + " · REPRINT ON SHELVES"));
    }
    // clean monthly median steps
    Object.keys(card.monthly_clean).forEach(function (m) {
      var p = m.split("-"), s = Date.UTC(+p[0], +p[1] - 1, 1), e = Date.UTC(+p[0], +p[1], 1);
      var xs = L + (Math.max(s, start) - start) * (W - L - R) / (end - start);
      var xe = L + (Math.min(e, end) - start) * (W - L - R) / (end - start);
      var yy = y(card.monthly_clean[m]);
      root.appendChild(svg("line", { x1: xs + 4, x2: xe - 4, y1: yy, y2: yy, stroke: COLORS.accent, "stroke-width": 4, "stroke-linecap": "round" }));
      root.appendChild(svgText({ x: (xs + xe) / 2, y: yy - 10, "text-anchor": "middle", "font-size": 12, fill: COLORS.accentText, "font-family": "Geist Mono, monospace" }, moneyShort(card.monthly_clean[m])));
    });
    // sales
    var floorY = H - B - 6;
    card.sales.forEach(function (s) {
      var cx = x(s.date), off = s.price < yMin, cy = off ? floorY : y(s.price);
      var color = s.label === "DATA_ERROR" ? COLORS.flag : s.label === "RELIST" ? COLORS.warn : s.label === "DUPLICATE" ? COLORS.neutral : COLORS.text;
      var dot = svg("circle", { cx: cx, cy: cy, r: s.label === "ORGANIC" ? 4.5 : 6, fill: s.label === "ORGANIC" ? "#0B0A14" : color, stroke: color, "stroke-width": 2 });
      var title = svg("title", {}); title.textContent = fmtDate(s.date) + ": " + money(s.price) + (s.why ? " · " + s.why : "");
      dot.appendChild(title); root.appendChild(dot);
      if (off) {
        var nearRight = cx > W - R - 110;
        root.appendChild(svgText({ x: nearRight ? cx - 10 : cx + 9, y: cy + 4, "text-anchor": nearRight ? "end" : "start", "font-size": 11, fill: COLORS.flagText, "font-family": "Geist Mono, monospace" }, "↓ " + money(s.price)));
      }
    });
    return root;
  }

  /* ---------- rip or hold chart: sealed price vs EV per box, the rip zone shaded ---------- */
  function ripChart(box, points, product) {
    box.innerHTML = "";
    var size = fitChart(box, 0.52);
    var W = size.width, H = Math.max(240, Math.min(size.height, 340));
    var L = 58, R = 18, T = 20, B = 34;
    var pts = (points || []).filter(function (p) { return isNum(p.sealed_market_cents) && isNum(p.ev_box_cents); })
      .map(function (p) { return { day: p.day, s: p.sealed_market_cents / 100, e: p.ev_box_cents / 100 }; })
      .sort(function (a, b) { return a.day < b.day ? -1 : 1; });
    if (!pts.length) { box.appendChild(el("p", { class: "muted", text: "No price history for this product yet." })); return; }
    var vals = [];
    pts.forEach(function (p) { vals.push(p.s, p.e); });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var step = niceStep(Math.max(hi - lo, hi * 0.2) / 4);
    var yMin = Math.max(0, Math.floor((lo - step * 0.5) / step) * step), yMax = Math.ceil((hi + step * 0.5) / step) * step;
    var t0 = parseDate(pts[0].day).getTime(), t1 = parseDate(pts[pts.length - 1].day).getTime();
    var x = function (p) { return pts.length === 1 || t1 === t0 ? (L + W - R) / 2 : L + (parseDate(p.day).getTime() - t0) * (W - L - R) / (t1 - t0); };
    var y = function (v) { return T + (yMax - v) * (H - T - B) / (yMax - yMin); };
    var name = product.product + (product.set ? ", " + product.set : "");
    var last = pts[pts.length - 1];
    var root = svg("svg", { viewBox: "0 0 " + W + " " + H, class: "chart", role: "img",
      "aria-label": name + ": sealed price and expected value per box from " + fmtDate(pts[0].day) + " to " + fmtDate(last.day) +
        ". Latest: sealed " + money(last.s) + ", EV per box " + money(last.e) + "." });

    for (var v = yMin; v <= yMax + 0.001; v += step) {
      root.appendChild(svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: COLORS.grid }));
      root.appendChild(svgText({ x: L - 10, y: y(v) + 4, "text-anchor": "end", "font-size": 12, fill: COLORS.muted, "font-family": "Geist Mono, monospace" }, axisMoney(v)));
    }
    var xl = [pts[0]];
    if (pts.length > 2) xl.push(pts[Math.floor((pts.length - 1) / 2)]);
    if (pts.length > 1) xl.push(last);
    xl.forEach(function (p, i) {
      var anchor = xl.length === 1 ? "middle" : i === 0 ? "start" : i === xl.length - 1 ? "end" : "middle";
      root.appendChild(svgText({ x: x(p), y: H - 10, "text-anchor": anchor, "font-size": 12, fill: COLORS.muted, "font-family": "Geist Mono, monospace", "letter-spacing": 1 }, fmtDate(p.day).toUpperCase()));
    });

    // rip zone: wherever EV per box sits above the sealed price, split at crossings
    for (var i = 0; i < pts.length - 1; i++) {
      var a = pts[i], b = pts[i + 1], da = a.e - a.s, db = b.e - b.s;
      var ax = x(a), bx = x(b);
      if (da >= 0 && db >= 0) {
        root.appendChild(svg("path", { d: "M" + ax + " " + y(a.e) + " L" + bx + " " + y(b.e) + " L" + bx + " " + y(b.s) + " L" + ax + " " + y(a.s) + " Z", fill: COLORS.rip, "fill-opacity": 0.16 }));
      } else if (da > 0 || db > 0) {
        var t = da / (da - db), cx = ax + (bx - ax) * t, cv = a.s + (b.s - a.s) * t;
        var d = da > 0
          ? "M" + ax + " " + y(a.e) + " L" + cx + " " + y(cv) + " L" + ax + " " + y(a.s) + " Z"
          : "M" + cx + " " + y(cv) + " L" + bx + " " + y(b.e) + " L" + bx + " " + y(b.s) + " Z";
        root.appendChild(svg("path", { d: d, fill: COLORS.rip, "fill-opacity": 0.16 }));
      }
    }
    // lines, or dots when there is a single day
    [["s", COLORS.sealed, 2], ["e", COLORS.ev, 2.5]].forEach(function (spec) {
      if (pts.length === 1) {
        root.appendChild(svg("circle", { cx: x(pts[0]), cy: y(pts[0][spec[0]]), r: 5, fill: spec[1], stroke: COLORS.surface, "stroke-width": 2 }));
      } else {
        root.appendChild(svg("path", { d: pts.map(function (p, n) { return (n ? "L" : "M") + x(p) + " " + y(p[spec[0]]); }).join(" "), fill: "none", stroke: spec[1], "stroke-width": spec[2], "stroke-linejoin": "round", "stroke-linecap": "round" }));
      }
    });
    // direct labels at the latest point, kept apart
    var ly = { s: y(last.s), e: y(last.e) };
    if (Math.abs(ly.s - ly.e) < 16) { if (ly.e <= ly.s) { ly.e -= 8; ly.s += 8; } else { ly.s -= 8; ly.e += 8; } }
    var lx = x(last) - 8;
    var halo = { stroke: COLORS.surface, "stroke-width": 4, "paint-order": "stroke", "stroke-linejoin": "round" };
    root.appendChild(svgText(Object.assign({ x: lx, y: ly.e - 8, "text-anchor": "end", "font-size": 12, fill: COLORS.text, "font-family": "Geist Mono, monospace" }, halo), "EV " + money(Math.round(last.e))));
    root.appendChild(svgText(Object.assign({ x: lx, y: ly.s + 18, "text-anchor": "end", "font-size": 12, fill: COLORS.muted, "font-family": "Geist Mono, monospace" }, halo), "Sealed " + money(Math.round(last.s))));

    // hover: crosshair plus a tooltip for the nearest day
    var cross = svg("line", { x1: 0, x2: 0, y1: T, y2: H - B, stroke: COLORS.muted, "stroke-dasharray": "3 4", visibility: "hidden" });
    root.appendChild(cross);
    var hit = svg("rect", { x: L, y: T, width: W - L - R, height: H - T - B, fill: "transparent" });
    root.appendChild(hit);
    var tip = el("div", { class: "chart-tip", hidden: "hidden" });
    function hide() { cross.setAttribute("visibility", "hidden"); tip.hidden = true; }
    hit.addEventListener("mousemove", function (ev) {
      var rect = root.getBoundingClientRect(), sx = rect.width / W;
      var mx = (ev.clientX - rect.left) / sx, best = pts[0], bd = Infinity;
      pts.forEach(function (p) { var dd = Math.abs(x(p) - mx); if (dd < bd) { bd = dd; best = p; } });
      var px = x(best);
      cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
      tip.textContent = "";
      tip.appendChild(el("strong", { text: fmtDate(best.day) }));
      tip.appendChild(el("span", { text: "EV per box " + money(best.e) }));
      tip.appendChild(el("span", { text: "Sealed " + money(best.s) }));
      tip.appendChild(el("span", { text: (best.e >= best.s ? "Opening beats holding" : "Holding beats opening") }));
      tip.hidden = false;
      tip.style.left = Math.min(Math.max(px * sx, 90), rect.width - 90) + "px";
      tip.style.top = (Math.min(y(best.e), y(best.s)) * sx) + "px";
    });
    hit.addEventListener("mouseleave", hide);
    box.appendChild(root);
    box.appendChild(tip);
  }

  /* ---------- index page ---------- */
  function renderIndex() {
    Promise.all([
      load("data/meta.json"), load("data/file.json"), load("data/movers.json"), load("data/flags.json"),
      load("data/rip_ev.json"), load("data/calls.json"), load("data/drops.json"),
      load("data/digest.json", true), load("data/watching.json", true)
    ]).then(function (r) {
      var meta = r[0], file = r[1], movers = r[2], flags = r[3], rip = r[4], calls = r[5], drops = r[6];
      var digest = r[7], watching = r[8];
      $("#status").textContent = updatedLabel(meta) || $("#status").textContent;
      var ids = file && file.cards ? file.cards : [];
      return Promise.all(ids.map(function (id) { return load("data/cards/" + id + ".json"); })).then(function (cards) {
        var byId = {};
        ids.forEach(function (id, n) { byId[id] = cards[n]; });
        if (!file) { var m = $("#load-error"); if (m) m.hidden = false; }
        safe(function () { renderToday(meta, file, movers, digest, watching, calls); });
        safe(function () { renderFile(file, byId, drops); });
        safe(function () { renderMovers(movers); });
        safe(function () { renderMarketFlags(flags); });
        safe(renderLegend);
        safe(function () { renderRip(rip); });
        safe(function () { renderCalls(calls); });
        safe(function () { renderDrops(drops); });
      });
    }).catch(function (e) {
      var m = $("#load-error"); if (m) { m.hidden = false; }
      if (window.console) console.error(e);
    });
  }

  /* ---------- Today: what changed since yesterday. Each piece hides itself when its file or key is missing. ---------- */
  function renderToday(meta, file, movers, digest, watching, calls) {
    var today = centralToday();
    $("#today-date").textContent = WEEKDAYS[parseDate(today).getUTCDay()].slice(0, 3) + " " + fmtDate(today);
    var line = [];
    var tcg = meta && Array.isArray(meta.sources) ? meta.sources.filter(function (s) { return s && s.id === "tcgcsv"; })[0] : null;
    if (tcg && isDate(tcg.as_of)) line.push("Prices as of " + fmtDateYear(tcg.as_of));
    var nf = nextFile(file);
    if (nf) line.push("Next File: " + nf);
    $("#today-line").textContent = line.join(" · ");

    var daily = digest && digest.daily && typeof digest.daily === "object" ? digest.daily : {};
    var grid = $("#today-grid");
    grid.innerHTML = "";
    var parts = [];
    [function () { return sinceYesterday(movers, daily); }, function () { return dueAndFlagged(daily, calls); },
      function () { return watchingList(watching); }].forEach(function (build) {
      safe(function () { var p = build(); if (p) parts.push(p); });
    });
    parts.forEach(function (p) { grid.appendChild(p); });
    grid.hidden = !parts.length;
  }

  function todayCard(title, note, children) {
    return el("div", { class: "card today-card" }, [el("h3", {}, [title, note ? el("span", { text: note }) : null])].concat(children));
  }

  // movers.json one_day first. The digest's copy only stands in when it has rows: an empty copy can't tell a quiet day
  // from a switched-off file. The digest's 7-day movers are the market table further down, so they don't show here.
  function sinceYesterday(movers, daily) {
    var rows = movers && Array.isArray(movers.one_day) ? movers.one_day
      : Array.isArray(daily.one_day_movers) && daily.one_day_movers.length ? daily.one_day_movers : null;
    if (!rows) return null;
    rows = rows.filter(function (m) { return m && str(m.name); });
    var body;
    if (!rows.length) {
      body = el("p", { class: "today-quiet", text: "Quiet since yesterday: no card worth $" + ONE_DAY.minPrice + " or more moved " + ONE_DAY.minPct + "% or more on TCGplayer." });
    } else {
      body = el("ul", { class: "today-list" });
      rows.slice(0, 5).forEach(function (m) {
        var price = m.last && isNum(m.last.price) ? m.last.price : m.price;
        var has = isNum(m.change_pct), up = m.change_pct >= 0;
        body.appendChild(el("li", { class: "today-mover" }, [
          el("span", { class: "t-main" }, [el("span", { class: "name", text: m.name }), el("span", { class: "sub", text: [m.set, m.number].filter(Boolean).join(" · ") })]),
          el("span", { class: "t-fig" }, [
            el("span", { class: "num " + (has ? (up ? "up" : "down") : ""), text: has ? (up ? "▲ " : "▼ ") + pct(m.change_pct, 1) : "—" }),
            el("span", { class: "sub num", text: money(price) })
          ]),
          m.label ? el("span", { class: "t-label" }, [chip(m.label), m.label_note ? el("span", { class: "sub", text: sentence(m.label_note, true) }) : null]) : null
        ]));
      });
    }
    var asOf = movers && isDate(movers.as_of) ? movers.as_of : rows[0] && isDate(rows[0].observed) ? rows[0].observed : null;
    var source = (rows[0] && str(rows[0].source)) || "TCGplayer market prices via tcgcsv.com";
    return todayCard("Since yesterday", "TCGplayer", [body, el("p", { class: "today-foot", text: source + (asOf ? ", as of " + fmtDateYear(asOf) : "") + "." })]);
  }

  // Calls whose check date has come, and the flagged-sales headline, from digest.json.
  function dueAndFlagged(daily, calls) {
    // A call checked by hand since the digest was built isn't due anymore.
    var status = {};
    (calls && Array.isArray(calls.items) ? calls.items : []).forEach(function (c) { if (c && c.id != null) status[String(c.id)] = c.status; });
    var due = (Array.isArray(daily.calls_due) ? daily.calls_due : []).filter(function (c) {
      return c && str(c.text) && (!Object.prototype.hasOwnProperty.call(status, String(c.id)) || status[String(c.id)] === "open");
    });
    var head = daily.flags_headline && isNum(daily.flags_headline.value) ? daily.flags_headline : null;
    if (!due.length && !head) return null;
    var col = el("div", { class: "today-col" });
    if (due.length) {
      var ul = el("ul", { class: "today-list" });
      due.forEach(function (c) {
        ul.appendChild(el("li", {}, [el("span", { class: "t-main" }, [
          el("span", { class: "call-text" }, [c.id != null ? el("span", { class: "num t-id", text: "#" + c.id }) : null, c.id != null ? " " : null, str(c.text)]),
          isDate(c.check_date) ? el("span", { class: "sub", text: "Check date " + fmtDate(c.check_date) }) : null
        ])]));
      });
      col.appendChild(todayCard("Calls due", "Checked in public", [ul, el("a", { class: "today-more", href: "#calls", text: "Every call on the record →" })]));
    }
    if (head) {
      var label = str(head.label).replace(/\.$/, "");
      col.appendChild(todayCard("Flagged sales", "Across the market", [
        el("div", { class: "flag-head" }, [el("span", { class: "num big-flag", text: (Math.round(head.value * 10) / 10) + "%" }), label ? el("p", { text: label + "." }) : null]),
        el("a", { class: "today-more", href: "#flags", text: "What got caught →" })
      ]));
    }
    return col;
  }

  // "What people are watching": titles and links from watching.json, newest first. Only http(s) links leave the page.
  function watchingList(watching) {
    var items = (watching && Array.isArray(watching.items) ? watching.items : []).filter(function (w) {
      return w && str(w.title) && /^https?:\/\/[^\s]+$/i.test(str(w.url));
    });
    if (!items.length) return null;
    items = items.map(function (w, n) { return { w: w, n: n, d: isDate(w.published) ? w.published : "" }; })
      .sort(function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : a.n - b.n; })
      .slice(0, 6).map(function (x) { return x.w; });
    var ul = el("ul", { class: "today-list" });
    items.forEach(function (w) {
      var src = Object.prototype.hasOwnProperty.call(SOURCES, w.source) ? SOURCES[w.source] : "";
      var bits = [src, str(w.feed), isDate(w.published) ? fmtDate(w.published) : ""].filter(Boolean);
      ul.appendChild(el("li", {}, [el("span", { class: "t-main" }, [
        el("a", { class: "t-link", href: str(w.url), target: "_blank", rel: "noopener noreferrer", text: str(w.title) }),
        bits.length ? el("span", { class: "sub", text: bits.join(" · ") }) : null
      ])]));
    });
    return todayCard("What people are watching", "Links open elsewhere", [ul]);
  }

  function renderFile(file, byId, drops) {
    if (!file) return;
    // The File's date and slot head the hero card, its stance beside them; the story fields sit above its table.
    var day = isDate(file.date) ? file.date : isDate(file.as_of) ? file.as_of : null;
    var slot = SLOTS.indexOf(str(file.slot)) !== -1 ? str(file.slot) : "";
    $("#hero-kicker").textContent = ["The File", day ? fmtDate(day) : "", slot].filter(Boolean).join(" · ");
    var hs = $("#hero-stance"), sc = stanceChip(file.stance);
    hs.innerHTML = "";
    if (sc) hs.appendChild(sc);
    var story = $("#file-story"), headline = str(file.headline), dek = str(file.dek), lines = storyLines(file);
    story.innerHTML = "";
    if (sc || headline || dek || lines) {
      story.appendChild(el("div", { class: "story-top" }, [
        stanceChip(file.stance),
        el("span", { class: "story-meta", text: ["The File", day ? WEEKDAYS[parseDate(day).getUTCDay()].slice(0, 3) + " " + fmtDate(day) : "", slot].filter(Boolean).join(" · ") })
      ]));
      if (headline) story.appendChild(el("h4", { class: "story-h", text: headline }));
      if (dek) story.appendChild(el("p", { class: "story-dek", text: dek }));
      if (lines) story.appendChild(lines);
      if (sc) story.appendChild(el("p", { class: "story-note", text: "A stance is a read on the numbers, not advice." }));
    }
    story.hidden = !story.childNodes.length;

    var featured = byId[file.featured];
    if (featured) {
      var hero = $("#hero-chart");
      hero.innerHTML = "";
      hero.appendChild(salesChart(featured, fitChart(hero, 0.52)));
      $("#hero-title").textContent = featured.name + " " + featured.tier;
      $("#hero-change").textContent = pct(featured.change_pct);
      var cap = $("#hero-caption");
      cap.textContent = file.source + ". Pulled " + fmtDateYear(file.pulled) + ". ";
      cap.appendChild(el("a", { href: "card.html?id=" + featured.id, text: "See every sale →" }));
    }

    // stats: the file's cards, its flag count, the next release
    var sEl = $("#stats");
    sEl.innerHTML = "";
    var stats = (file.rows || []).slice(0, 2).map(function (row) {
      return { v: pct(row.change_pct), c: row.change_pct >= 0 ? "up" : "down", t: row.stat || row.name };
    });
    if (file.flags && file.flags.headline) stats.push({ v: file.flags.headline.value + " of " + file.flags.headline.of, c: "flag", t: file.flags.stat || file.flags.headline.label });
    var nd = drops ? nextDrop(drops) : null;
    if (nd) stats.push({ v: fmtDate(nd.date), c: "", t: "Next release: " + nd.name + "." });
    stats.forEach(function (s) {
      sEl.appendChild(el("div", { class: "card stat" }, [
        el("span", { class: "num " + (s.c === "up" ? "up" : s.c === "down" ? "down" : ""), style: s.c === "flag" ? "color: var(--flag)" : null, text: s.v }),
        el("p", { text: s.t })
      ]));
    });

    // the file's cards
    var body = $("#file-body");
    body.innerHTML = "";
    (file.rows || []).forEach(function (m) {
      body.appendChild(el("tr", {}, [
        el("td", { class: "first" }, [
          m.link ? el("a", { href: m.link, class: "name", text: m.name }) : el("span", { class: "name", text: m.name }),
          el("span", { class: "sub", text: m.set + " · " + m.note })
        ]),
        el("td", { "data-label": "Tier", class: "num", text: m.tier }),
        el("td", { "data-label": "Last sale", class: "num", text: money(m.last.price) + " · " + fmtDate(m.last.date) }),
        el("td", { "data-label": "Clean median", class: "num", text: money(m.clean_median) }),
        el("td", { "data-label": "Change", class: "num " + (m.change_pct >= 0 ? "up" : "down"), text: (m.change_pct >= 0 ? "▲ " : "▼ ") + pct(m.change_pct) }),
        el("td", { "data-label": "Flagged", class: "num", text: m.flagged + " of " + m.sales })
      ]));
    });
    $("#file-foot").textContent = file.foot || "";

    // what the file threw out
    var f = file.flags;
    if (f) {
      $("#flag-count").textContent = f.headline.value + "/" + f.headline.of;
      $("#flag-text").textContent = f.text;
      var fl = $("#flag-list");
      fl.innerHTML = "";
      (f.items || []).forEach(function (it) {
        fl.appendChild(el("li", {}, [
          el("span", {}, [el("strong", { text: it.card }), el("span", { class: "sub", text: fmtDate(it.date) + " · " + money(it.price) })]),
          chip(it.label),
          el("span", { class: "why", text: it.why })
        ]));
      });
    }
  }

  function renderMovers(movers) {
    var wrap = $("#market-movers");
    wrap.innerHTML = "";
    var items = movers && movers.items ? movers.items : [];
    if (!items.length) {
      wrap.appendChild(movers && movers.pending
        ? emptyCard("Market movers start with the nightly feed.",
            "Every Pokémon card worth $20 or more that moved 5% or more in a week on TCGplayer, each one checked against real sales. The list needs a full week of prices before it fills in.")
        : emptyCard("Nothing to show this week.",
            "The list covers Pokémon cards worth $20 or more that moved 5% or more in a week on TCGplayer. It needs a full week of prices, so it fills in about a week after the feed starts."));
      return;
    }
    var win = items[0].window_label || "7d";
    $("#movers-sub").textContent = "TCGplayer · last " + win.replace(/d$/, " days");
    var tb = el("tbody");
    items.forEach(function (m) {
      var bits = [m.set, m.number, m.tier].filter(Boolean).join(" · ");
      tb.appendChild(el("tr", {}, [
        el("td", { class: "first" }, [el("span", { class: "name", text: m.name }), el("span", { class: "sub", text: bits })]),
        el("td", { "data-label": "Market price", class: "num" }, [stack(money(m.last && m.last.price), m.last && m.last.date ? fmtDate(m.last.date) : "")]),
        el("td", { "data-label": "Change", class: "num " + (m.change_pct >= 0 ? "up" : "down"), text: (m.change_pct >= 0 ? "▲ " : "▼ ") + pct(m.change_pct, 1) }),
        el("td", { "data-label": "Clean change", class: "num", text: isNum(m.clean_change_pct) ? pct(m.clean_change_pct, 1) : "—" }),
        el("td", { "data-label": "Label" }, [el("span", { class: "stack" }, [chip(m.label), m.label_note ? el("span", { class: "sub", text: sentence(m.label_note) }) : null])])
      ]));
    });
    wrap.appendChild(el("div", { class: "card table-card" }, [
      el("table", { class: "data" }, [
        el("thead", {}, [el("tr", {}, ["Card", "Market price", "Change · " + win, "Clean change", "Label"].map(function (h) { return el("th", { scope: "col", text: h }); }))]),
        tb
      ]),
      el("div", { class: "table-foot", text: (items[0].source || "TCGplayer market prices") + ", as of " + fmtDateYear(movers.as_of || items[0].observed) +
        ". Top 10 cards worth $20 or more. Clean change: the same move with flagged sales taken out. A dash means no sales were checked yet." })
    ]));
  }

  function renderMarketFlags(flags) {
    var wrap = $("#market-flags");
    wrap.innerHTML = "";
    var items = flags && flags.items ? flags.items : [];
    var head = flags && flags.headline && isNum(flags.headline.value) ? flags.headline : null;
    if (!items.length && (!head || head.value === 0)) {
      wrap.appendChild(flags && flags.pending
        ? emptyCard("The weekly junk rate starts with the nightly feed.",
            "Every week: the share of sold dollar volume across tracked cards that got flagged, and the cards behind it, each with a reason in plain words.")
        : emptyCard("No flagged sales this week.",
            "The junk rate fills in as sales get checked: the share of sold dollar volume across tracked cards that got flagged, and the cards behind it."));
      return;
    }
    var card = el("div", { class: "card flags" });
    if (head) {
      card.appendChild(el("div", { class: "flag-head" }, [
        el("span", { class: "num big-flag", text: (Math.round(head.value * 10) / 10) + "%" }),
        el("p", { text: head.label + (flags.as_of ? ". Through " + fmtDate(flags.as_of) + "." : ".") })
      ]));
    }
    if (items.length) {
      var ul = el("ul", { class: "flag-list" });
      items.forEach(function (it) {
        var claimed = isNum(it.claimed_change_pct) ? "Claimed " + pct(it.claimed_change_pct) : "";
        ul.appendChild(el("li", {}, [
          el("span", {}, [el("strong", { text: it.name }), el("span", { class: "sub", text: [it.set, claimed].filter(Boolean).join(" · ") })]),
          chip(it.label),
          el("span", { class: "why", text: sentence(it.why, true) })
        ]));
      });
      card.appendChild(ul);
    } else {
      card.appendChild(el("p", { class: "muted", text: "No cards flagged this week." }));
    }
    wrap.appendChild(card);
  }

  function renderLegend() {
    var lg = $("#labels");
    lg.innerHTML = "";
    Object.keys(LABELS).forEach(function (id) {
      lg.appendChild(el("div", { class: "card" }, [chip(id), el("p", { text: LABELS[id].meaning })]));
    });
  }

  function renderRip(rip) {
    var products = rip && rip.products ? rip.products : [];
    var seg = $("#rip-games"), rb = $("#rip-body");
    var shareEl = $("#rip-share");
    if (rip && isNum(rip.share_above_1) && products.length) {
      shareEl.textContent = " Today, " + share(rip.share_above_1) + " of tracked products are worth more opened than sealed.";
    }
    var noteBits = [];
    if (rip && rip.note) noteBits.push(rip.note);
    if (rip && rip.data_date && products.length) noteBits.push("Data " + fmtDateYear(rip.data_date) + ".");
    $("#rip-note").textContent = noteBits.join(" ");

    var byGame = {};
    products.forEach(function (p) { (byGame[p.game] = byGame[p.game] || []).push(p); });
    var current = (GAMES.filter(function (g) { return byGame[g.id]; })[0] || GAMES[0]).id;
    seg.innerHTML = "";
    GAMES.forEach(function (g) {
      var b = el("button", { type: "button", "aria-pressed": g.id === current ? "true" : "false", text: g.name });
      b.addEventListener("click", function () {
        Array.prototype.forEach.call(seg.querySelectorAll("button"), function (o) { o.setAttribute("aria-pressed", "false"); });
        b.setAttribute("aria-pressed", "true");
        draw(g.id);
      });
      seg.appendChild(b);
    });

    function select(p, tr) {
      Array.prototype.forEach.call(rb.querySelectorAll("tr"), function (o) { o.classList.remove("is-selected"); o.setAttribute("aria-selected", "false"); });
      if (tr) { tr.classList.add("is-selected"); tr.setAttribute("aria-selected", "true"); }
      $("#rip-chart-title").textContent = p.product + (p.set ? " · " + p.set : "");
      var c = $("#rip-chart-chip");
      c.textContent = "DATA " + fmtDate(p.data_date || rip.data_date).toUpperCase();
      c.className = "chip chip-accent";
      ripChart($("#rip-chart"), rip.series ? rip.series[String(p.id)] : null, p);
      var src = $("#rip-sources");
      src.textContent = "";
      var list = p.rates_sources || [];
      if (list.length) {
        src.appendChild(document.createTextNode("Pull rates: "));
        list.forEach(function (s, n) {
          if (n) src.appendChild(document.createTextNode(", "));
          src.appendChild(s.url ? el("a", { href: s.url, rel: "noopener", target: "_blank", text: s.name }) : document.createTextNode(s.name));
        });
        src.appendChild(document.createTextNode(". Card prices: TCGplayer via tcgcsv."));
      }
    }

    function draw(game) {
      rb.innerHTML = "";
      var rows = (byGame[game] || []).slice().sort(function (a, b) { return (b.ratio_market || 0) - (a.ratio_market || 0); });
      if (!products.length) $("#rip-sources").textContent = "Illustrative. Real price history shows here once the nightly feed is on.";
      if (!rows.length) {
        var gname = GAMES.filter(function (g) { return g.id === game; })[0].name;
        rb.appendChild(el("tr", {}, [el("td", { colspan: "6", class: "first muted", text: products.length
          ? gname + " shows up here once its pull rates are in, with the source on every row."
          : rip && rip.pending
            ? "Rip EV goes live with the nightly feed: every box priced sealed and opened, with the pull-rate source on every row."
            : "No products priced yet. Rows show up as pull rates and prices come in." })]));
        return;
      }
      rows.forEach(function (p, n) {
        var conf = p.confidence ? p.confidence.charAt(0).toUpperCase() + p.confidence.slice(1) + " confidence" : "";
        var type = TYPES[p.product_type] || null;
        if (type && String(p.product).toLowerCase().indexOf(type.toLowerCase()) !== -1) type = null;
        var sub = [p.set, type, conf].filter(Boolean).join(" · ") + (p.confidence === "low" ? ". Rates are estimates." : "");
        var ratio = isNum(p.ratio_market) ? p.ratio_market.toFixed(2) + "×" : "—";
        var tr = el("tr", { class: "is-selectable", tabindex: "0", "aria-selected": "false" }, [
          el("td", { class: "first" }, [el("span", { class: "name", text: p.product }), el("span", { class: "sub", text: sub })]),
          el("td", { "data-label": "Sealed", class: "num" }, [stack(moneyC(p.sealed_market_cents), isNum(p.msrp_cents) ? "MSRP " + moneyC(p.msrp_cents) : "")]),
          el("td", { "data-label": "EV per box", class: "num" }, [stack(moneyC(p.ev_box_cents), "Net " + moneyC(p.ev_net_cents))]),
          el("td", { "data-label": "Ratio", class: "num " + (p.ratio_market >= 1 ? "up" : ""), text: ratio }),
          el("td", { "data-label": "Hit $50+", class: "num" }, [stack(share(p.p_hit_50), "$200+ " + share(p.p_hit_200))]),
          el("td", { "data-label": "Range", class: "num" }, [stack(moneyC(p.floor_p5_cents) + "–" + moneyC(p.ceiling_p95_cents), "Median " + moneyC(p.median_p50_cents))])
        ]);
        tr.addEventListener("click", function () { select(p, tr); });
        tr.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(p, tr); } });
        rb.appendChild(tr);
        if (n === 0) select(p, tr);
      });
    }
    draw(current);
  }

  function renderCalls(calls) {
    var cWrap = $("#calls-wrap");
    cWrap.innerHTML = "";
    var on = calls && calls.items ? calls.items.filter(function (c) { return c.on_record; }) : [];
    if (!on.length) {
      cWrap.appendChild(el("div", { class: "card empty" }, [
        el("h3", { text: "The first calls go on the record soon." }),
        el("p", { text: "Each one gets a date, a check date and a verdict. Hits and misses both stay up." })
      ]));
      return;
    }
    var statusChip = { open: "chip-accent", hit: "chip-ok", miss: "chip-flag" };
    var tb = el("tbody");
    on.slice().sort(function (a, b) { return a.dated < b.dated ? 1 : a.dated > b.dated ? -1 : (a.id < b.id ? 1 : -1); }).forEach(function (c) {
      var days = daysFromToday(c.check_date);
      var status = c.status === "open" && days >= 0 ? (days === 0 ? "Check today" : "Open · " + days + (days === 1 ? " day" : " days")) : c.status;
      tb.appendChild(el("tr", {}, [
        el("td", { class: "first" }, [
          el("span", { class: "name num", text: "#" + c.id }),
          el("span", { class: "call-text", text: c.text }),
          c.start ? el("span", { class: "sub", text: c.start }) : null,
          c.method ? el("span", { class: "sub", text: c.method }) : null,
          c.latest ? el("span", { class: "sub", text: "Latest: " + c.latest }) : null,
          c.verdict_note ? el("span", { class: "sub", text: "Verdict: " + c.verdict_note }) : null,
          c.link ? el("a", { class: "sub", href: c.link, text: "The original post →" }) : null
        ]),
        el("td", { "data-label": "Dated", class: "num", text: fmtDate(c.dated) }),
        el("td", { "data-label": "Check", class: "num", text: fmtDate(c.check_date) }),
        el("td", { "data-label": "Status" }, [el("span", { class: "chip " + (statusChip[c.status] || "chip-neutral"), text: String(status).toUpperCase() })])
      ]));
    });
    cWrap.appendChild(el("div", { class: "card table-card" }, [el("table", { class: "data calls" }, [
      el("thead", {}, [el("tr", {}, [el("th", { scope: "col", text: "Call" }), el("th", { scope: "col", text: "Dated" }), el("th", { scope: "col", text: "Check" }), el("th", { scope: "col", text: "Status" })])]), tb
    ]), el("div", { class: "table-foot", text: calls.note || "" })]));
  }

  function renderDrops(drops) {
    if (!drops) return;
    var dw = $("#drops-grid");
    dw.innerHTML = "";
    var nd = nextDrop(drops);
    drops.items.slice().sort(function (a, b) { return sortKey(a) < sortKey(b) ? -1 : 1; }).forEach(function (dItem) {
      var days = daysFromToday(dItem.date);
      var when = dItem.date_precision === "month" ? "Date TBA" : days > 1 ? "In " + days + " days" : days === 1 ? "Tomorrow" : days === 0 ? "Today" : "Out now";
      var dateText = dItem.date_precision === "month" ? MONTHS[parseDate(dItem.date).getUTCMonth()].toUpperCase() : fmtDate(dItem.date).toUpperCase();
      dw.appendChild(el("article", { class: "card drop" + (dItem === nd ? " is-next" : "") }, [
        el("span", { class: "date", text: dateText }),
        el("span", {}, [el("span", { class: "chip " + (dItem === nd ? "chip-accent" : "chip-neutral"), text: (dItem.game + " · " + when).toUpperCase() })]),
        el("h3", { text: dItem.name }),
        el("p", { text: dItem.detail })
      ]));
    });
    var checked = drops.as_of ? "Dates checked " + fmtDateYear(drops.as_of) + ": " : "";
    $("#drops-source").textContent = checked + String(drops.source || "").replace(/, checked [A-Z][a-z]{2} \d{1,2}, \d{4}$/, "") + ".";
  }

  // Draw at the container's real width so chart text stays readable on phones.
  function fitChart(box, ratio) {
    var w = Math.round(Math.max(320, Math.min(1100, box.clientWidth || 700)));
    return { width: w, height: Math.round(Math.max(260, w * ratio)) };
  }

  function sortKey(d) { return d.date_precision === "month" ? d.date.slice(0, 8) + "31" : d.date; }

  function nextDrop(drops) {
    if (!drops || !drops.items || !drops.items.length) return null;
    var up = drops.items.filter(function (d) { return d.date_precision === "day" && daysFromToday(d.date) >= 0; })
      .sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    return up[0] || null;
  }

  /* ---------- card page ---------- */
  function renderCard() {
    var id = (new URLSearchParams(location.search).get("id") || "crystal-lugia-psa-8").replace(/[^a-z0-9-]/g, "");
    Promise.all([load("data/meta.json"), getJSON("data/cards/" + id + ".json")]).then(function (r) {
      var meta = r[0], c = r[1];
      $("#status").textContent = updatedLabel(meta) || $("#status").textContent;
      document.title = c.name + " " + c.tier + " · Mission Control · Jack Bauhs";
      $("#crumb").textContent = c.set + " / " + c.name + " " + c.number;
      $("#card-name").textContent = c.name + " " + c.tier;
      $("#card-meta").appendChild(el("span", { text: c.set + " · " + c.number + " · " + c.year }));
      if (c.event) $("#card-meta").appendChild(el("span", { class: "chip chip-accent", text: c.event.label.toUpperCase() }));
      var sep = Object.keys(c.monthly_clean).slice(-1)[0];
      var flagged = c.sales.filter(function (s) { return s.label !== "ORGANIC"; }).length;
      var kpis = [
        { l: "Last sale · " + fmtDate(c.last.date), v: money(c.last.price), p: "" },
        { l: "Clean median · " + MONTHS[+sep.split("-")[1] - 1], v: money(c.monthly_clean[sep]), p: "Confirmed sales only" },
        { l: c.change_label, v: pct(c.change_pct), p: "", cls: "up" },
        { l: "Flagged", v: flagged + " of " + c.sales.length, p: "Records left out or counted half", cls: "flag" }
      ];
      var k = $("#kpis");
      kpis.forEach(function (q) {
        k.appendChild(el("div", { class: "card kpi" }, [
          el("span", { class: "label", text: q.l }),
          el("span", { class: "num " + (q.cls === "up" ? "up" : ""), style: q.cls === "flag" ? "color: var(--flag)" : null, text: q.v }),
          q.p ? el("p", { text: q.p }) : null
        ]));
      });
      $("#card-chart").appendChild(salesChart(c, fitChart($("#card-chart"), 0.42)));
      $("#card-summary").textContent = c.summary;
      // The File's read on this card, when its file has one: the stance beside the meta, the labeled lines under the summary.
      safe(function () {
        var sc = stanceChip(c.stance), lines = storyLines(c), story = $("#card-story");
        if (sc) $("#card-meta").appendChild(sc);
        if (!story || !(sc || lines)) return;
        story.appendChild(el("div", { class: "kicker", text: "The File's read" }));
        if (lines) story.appendChild(lines);
        if (sc) story.appendChild(el("p", { class: "story-note", text: "A stance is a read on the numbers, not advice." }));
        story.hidden = false;
      });
      $("#card-source").textContent = "Source: " + c.source + ". Clean median = median of confirmed sales in the month; relists count half, errors and duplicates are left out.";
      var tb = $("#sales-body");
      c.sales.slice().reverse().forEach(function (s) {
        var fmt = s.format === "best_offer" ? "Best offer" + (s.ask ? " (asked " + money(s.ask) + ")" : "") : s.format === "auction" ? "Auction" + (s.bids ? " · " + s.bids : "") : "Buy it now";
        tb.appendChild(el("tr", {}, [
          el("td", { class: "first num", text: fmtDate(s.date) }),
          el("td", { "data-label": "Price", class: "num", text: money(s.price) }),
          el("td", { "data-label": "Format", text: fmt }),
          el("td", { "data-label": "Label" }, [chip(s.label)]),
          el("td", { "data-label": "Why", class: "muted", text: s.why || "" })
        ]));
      });
    }).catch(function (e) {
      var m = $("#load-error"); if (m) { m.hidden = false; }
      if (window.console) console.error(e);
    });
  }

  /* ---------- shared ---------- */
  function wireMenu() {
    var b = $("#menu-button"), nav = $("#site-nav");
    if (!b || !nav) return;
    b.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      b.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireMenu();
    if (document.body.getAttribute("data-page") === "card") renderCard(); else renderIndex();
  });
})();
