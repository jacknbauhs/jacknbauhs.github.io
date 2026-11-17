/* Card pages · board.jacknbauhs.com/pokemon/
   pokemon/index.html (data-page="market-search"): every card in data/market/index.json, searched, sorted, up to four compared.
   pokemon/<slug>.html (data-page="market-card"): one card's price, changes and history from data/market/sets/<set>.json.
   Both files are Mission Control's (board_publish, nightly). The pages themselves are built by pages/build.py.
   Every number is TCGplayer's market price as Mission Control stored it; a change is TCGplayer's number, not confirmed
   by sales. Not financial advice. */
(function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var SVGNS = "http://www.w3.org/2000/svg";
  var LINE = ["#A78BFA", "#34D399", "#FBBF24", "#7DD3FC"];
  var MAX_COMPARE = 4, PAGE = 100;

  function $(s, r) { return (r || document).querySelector(s); }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v == null) return;
      if (k === "text") n.textContent = v; else if (k === "class") n.className = v; else n.setAttribute(k, v);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function svg(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }
  function svgText(attrs, t) { var n = svg("text", attrs); n.textContent = t; return n; }
  function isNum(n) { return typeof n === "number" && isFinite(n); }
  function parseDate(s) { var p = String(s).slice(0, 10).split("-"); return Date.UTC(+p[0], +p[1] - 1, +(p[2] || 1)); }
  function fmtDate(s) { var d = new Date(parseDate(s)); return MONTHS[d.getUTCMonth()] + " " + d.getUTCDate(); }
  function fmtDateYear(s) { var d = new Date(parseDate(s)); return fmtDate(s) + ", " + d.getUTCFullYear(); }
  function money(n) {
    if (!isNum(n)) return "—";
    var whole = Math.abs(n - Math.round(n)) < 0.005 && n >= 100;
    return "$" + n.toLocaleString("en-US", { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2 });
  }
  function pct(n) {
    if (!isNum(n)) return "—";
    return (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toFixed(1) + "%";
  }
  function tone(n) { return !isNum(n) || n === 0 ? "" : n > 0 ? "up" : "down"; }
  function getJSON(path) {
    return fetch(path, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(path + " " + r.status);
      return r.json();
    });
  }
  function displayName(c) { return String(c.title || c.name || "Card"); }
  function label(c) { return displayName(c) + (c.number ? " " + c.number : "") + (c.printing ? " · " + c.printing : ""); }
  function pageOf(c) { return "/pokemon/" + c.slug + ".html"; }
  function niceStep(raw) {
    if (!(raw > 0)) return 1;
    var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }
  function axisMoney(v) { return v >= 1000 ? "$" + (v / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 }) + "k" : "$" + (v < 10 ? v.toFixed(2) : Math.round(v)); }
  function sourceLine(idx) {
    return "Source: " + idx.source + ". Prices as of " + fmtDateYear(idx.as_of) + ". " + idx.note;
  }

  /* A step chart: each stored price holds until the next one (tcgcsv stores a row only when the price changes).
     lines: [{name, color, points: [[iso, value]]}], each run to `end`. opts.fmt formats the y axis and the tip. */
  function stepChart(box, lines, end, opts) {
    opts = opts || {};
    var fmt = opts.fmt || axisMoney, tipFmt = opts.tip || money;
    var W = Math.max(320, Math.round(box.clientWidth || 800)), H = Math.round(Math.min(380, Math.max(220, W * 0.4)));
    var pad = { l: 58, r: 16, t: 14, b: 30 };
    var all = [];
    lines.forEach(function (ln) { ln.points.forEach(function (p) { all.push(p); }); });
    if (!all.length) { box.appendChild(el("p", { class: "muted", text: "No stored prices yet." })); return; }
    var x0 = Math.min.apply(null, all.map(function (p) { return parseDate(p[0]); }));
    var x1 = Math.max(parseDate(end), x0 + 86400000);
    var vals = all.map(function (p) { return p[1]; });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    if (opts.baseline != null) { lo = Math.min(lo, opts.baseline); hi = Math.max(hi, opts.baseline); }
    if (hi === lo) { hi = hi * 1.1 + 1; lo = Math.max(0, lo * 0.9 - 1); }
    var step = niceStep((hi - lo) / 4);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    if (opts.floorZero !== false && lo < 0 && Math.min.apply(null, vals) >= 0) lo = 0;
    function x(iso) { return pad.l + (parseDate(iso) - x0) / (x1 - x0) * (W - pad.l - pad.r); }
    function y(v) { return pad.t + (hi - v) / (hi - lo) * (H - pad.t - pad.b); }
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": opts.aria || "Price history" });
    for (var v = lo; v <= hi + step / 2; v += step) {
      s.appendChild(svg("line", { x1: pad.l, x2: W - pad.r, y1: y(v), y2: y(v), stroke: "rgba(236,234,246,0.08)" }));
      s.appendChild(svgText({ x: pad.l - 8, y: y(v) + 4, "text-anchor": "end", fill: "#9A96B8", "font-size": 11, "font-family": "Geist Mono, monospace" }, fmt(v)));
    }
    if (opts.baseline != null) s.appendChild(svg("line", { x1: pad.l, x2: W - pad.r, y1: y(opts.baseline), y2: y(opts.baseline), stroke: "rgba(236,234,246,0.3)", "stroke-dasharray": "3 4" }));
    // month ticks
    var d = new Date(x0), m = Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1), ticks = [];
    while (m <= x1) { ticks.push(m); var dm = new Date(m); m = Date.UTC(dm.getUTCFullYear(), dm.getUTCMonth() + 1, 1); }
    var every = Math.max(1, Math.ceil(ticks.length / Math.max(2, Math.floor(W / 90))));
    ticks.forEach(function (t, i) {
      if (i % every) return;
      var dt = new Date(t), iso = dt.toISOString().slice(0, 10), xx = x(iso);
      s.appendChild(svg("line", { x1: xx, x2: xx, y1: H - pad.b, y2: H - pad.b + 4, stroke: "#9A96B8" }));
      s.appendChild(svgText({ x: xx, y: H - 8, "text-anchor": "middle", fill: "#9A96B8", "font-size": 11, "font-family": "Geist Mono, monospace" },
        MONTHS[dt.getUTCMonth()] + (dt.getUTCMonth() === 0 ? " " + dt.getUTCFullYear() : "")));
    });
    lines.forEach(function (ln) {
      if (!ln.points.length) return;
      var dpath = "", prev = null;
      ln.points.forEach(function (p, i) {
        var xx = x(p[0]), yy = y(p[1]);
        dpath += (i ? " H" + xx.toFixed(1) + " V" + yy.toFixed(1) : "M" + xx.toFixed(1) + " " + yy.toFixed(1));
        prev = yy;
      });
      dpath += " H" + x(end).toFixed(1);
      s.appendChild(svg("path", { d: dpath, fill: "none", stroke: ln.color, "stroke-width": 2.2, "stroke-linejoin": "round" }));
      ln.points.forEach(function (p) { s.appendChild(svg("circle", { cx: x(p[0]), cy: y(p[1]), r: 2.6, fill: ln.color })); });
    });
    box.appendChild(s);
    // hover: the price in force on the day under the pointer
    var tip = el("div", { class: "mk-tip", hidden: "" }), cross = svg("line", { y1: pad.t, y2: H - pad.b, stroke: "rgba(236,234,246,0.25)", visibility: "hidden" });
    s.appendChild(cross); box.appendChild(tip);
    function at(points, t) { var v = null; points.forEach(function (p) { if (parseDate(p[0]) <= t) v = p[1]; }); return v; }
    function move(ev) {
      var r = s.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
      var sx = px * W / r.width; if (sx < pad.l || sx > W - pad.r) { hide(); return; }
      var t = x0 + (sx - pad.l) / (W - pad.l - pad.r) * (x1 - x0), iso = new Date(t).toISOString().slice(0, 10);
      var parts = lines.map(function (ln) { var v = at(ln.points, t); return v == null ? null : (lines.length > 1 ? ln.name + " " : "") + tipFmt(v); }).filter(Boolean);
      if (!parts.length) { hide(); return; }
      cross.setAttribute("x1", sx); cross.setAttribute("x2", sx); cross.setAttribute("visibility", "visible");
      tip.textContent = fmtDate(iso) + " · " + parts.join(" · ");
      tip.style.left = (px) + "px"; tip.style.top = (pad.t * r.height / H + 8) + "px"; tip.hidden = false;
    }
    function hide() { cross.setAttribute("visibility", "hidden"); tip.hidden = true; }
    s.addEventListener("mousemove", move); s.addEventListener("touchmove", move, { passive: true });
    s.addEventListener("mouseleave", hide);
  }

  function setStatus(idx) { var st = $("#status"); if (st && idx && idx.as_of) st.textContent = "Prices as of " + fmtDate(idx.as_of); }

  /* ---------- one card ---------- */
  function renderCard() {
    var body = document.body, slug = body.getAttribute("data-slug"), set = body.getAttribute("data-set");
    Promise.all([getJSON("/data/market/index.json"), getJSON("/data/market/sets/" + set + ".json").catch(function () { return null; })]).then(function (r) {
      var idx = r[0], shard = r[1];
      setStatus(idx);
      var c = (idx.cards || []).filter(function (x) { return x.slug === slug; })[0];
      if (!c) {
        var m = $("#load-error"); m.textContent = "This card is no longer on the board's index, so its prices aren't updated here. "; m.appendChild(el("a", { href: "/pokemon/", text: "See every card we track →" })); m.hidden = false;
        return;
      }
      var k = $("#kpis");
      [{ l: "Market · " + fmtDate(c.price_date), v: money(c.price), p: c.stale ? "Unchanged for a while: TCGplayer may have few recent sales" : (c.released ? "Released " + fmtDateYear(c.released) : "") },
       { l: "7 days", v: pct(c.ch7), cls: tone(c.ch7), p: "TCGplayer market, to " + fmtDate(idx.as_of) },
       { l: "30 days", v: pct(c.ch30), cls: tone(c.ch30), p: "Not confirmed by sales" },
       { l: "Tracked since", v: c.first ? fmtDate(c.first) : "—", p: c.first ? String(new Date(parseDate(c.first)).getUTCFullYear()) : "" }
      ].forEach(function (q) {
        k.appendChild(el("div", { class: "card kpi" }, [el("span", { class: "label", text: q.l }),
          el("span", { class: "num " + (q.cls || ""), text: q.v }), q.p ? el("p", { text: q.p }) : null]));
      });
      var pts = shard && shard.cards && shard.cards[slug] ? shard.cards[slug].series : [];
      stepChart($("#mk-chart"), [{ name: displayName(c), color: LINE[0], points: pts }], idx.as_of,
        { aria: label(c) + ": TCGplayer market price since " + (c.first || idx.as_of) });
      $("#mk-source").textContent = sourceLine(idx);
      if (c.tcgplayer) $("#mk-tcg").setAttribute("href", c.tcgplayer);
      var rel = $("#mk-related");
      (idx.cards || []).filter(function (x) { return x.set_slug === c.set_slug && x.slug !== c.slug; })
        .sort(function (a, b) { return (b.price || 0) - (a.price || 0); }).slice(0, 12)
        .forEach(function (x) { rel.appendChild(el("li", {}, [el("a", { href: pageOf(x), text: label(x) }), " ", el("span", { class: "num", text: money(x.price) })])); });
      if (!rel.children.length) $(".mk-related").hidden = true;
    }).catch(function (e) { $("#load-error").hidden = false; if (window.console) console.error(e); });
  }

  /* ---------- search, sort, compare ---------- */
  function renderSearch() {
    getJSON("/data/market/index.json").then(function (idx) {
      setStatus(idx);
      var cards = idx.cards || [], shown = PAGE, picked = [];
      var params = new URLSearchParams(location.search);
      (params.get("compare") || "").split(",").forEach(function (s) {
        if (s && picked.length < MAX_COMPARE && cards.some(function (c) { return c.slug === s; })) picked.push(s);
      });
      var q = $("#mk-q"), sort = $("#mk-sort"), body = $("#mk-body");
      if (params.get("q")) q.value = params.get("q");
      if (params.get("sort")) sort.value = params.get("sort");
      $("#mk-count").textContent = cards.length + " cards, prices as of " + fmtDateYear(idx.as_of) + ".";
      $("#mk-source").textContent = sourceLine(idx);
      var hay = cards.map(function (c) { return [c.name, c.number, c.set, c.printing, c.rarity].join(" ").toLowerCase(); });

      function matches() {
        var words = q.value.toLowerCase().split(/\s+/).filter(Boolean);
        var list = cards.filter(function (c, i) { return words.every(function (w) { return hay[i].indexOf(w) >= 0; }); });
        var key = sort.value;
        list.sort(function (a, b) {
          if (key === "name") return label(a).localeCompare(label(b));
          if (key === "released") return String(b.released || "").localeCompare(String(a.released || ""));
          var av = a[key], bv = b[key];
          if (key === "ch7" || key === "ch30") { av = isNum(av) ? Math.abs(av) : -1; bv = isNum(bv) ? Math.abs(bv) : -1; }
          return (bv || 0) - (av || 0);
        });
        return list;
      }
      function draw() {
        var list = matches();
        body.textContent = "";
        list.slice(0, shown).forEach(function (c) {
          var box = el("input", { type: "checkbox", "aria-label": "Compare " + label(c) });
          box.checked = picked.indexOf(c.slug) >= 0;
          box.disabled = !box.checked && picked.length >= MAX_COMPARE;
          box.addEventListener("change", function () {
            if (box.checked && picked.indexOf(c.slug) < 0) picked.push(c.slug);
            if (!box.checked) picked = picked.filter(function (s) { return s !== c.slug; });
            draw(); compare();
          });
          body.appendChild(el("tr", {}, [
            el("td", { class: "pick", "data-label": "Compare" }, [box]),
            el("td", { class: "first" }, [el("a", { href: pageOf(c), text: label(c) })]),
            el("td", { "data-label": "Set", class: "muted", text: c.set || "" }),
            el("td", { "data-label": "Released", class: "num muted", text: c.released ? fmtDateYear(c.released) : "—" }),
            el("td", { "data-label": "Price", class: "num", text: money(c.price) }),
            el("td", { "data-label": "7d", class: "num " + tone(c.ch7), text: pct(c.ch7) }),
            el("td", { "data-label": "30d", class: "num " + tone(c.ch30), text: pct(c.ch30) })
          ]));
        });
        var more = $(".mk-more");
        if (more) more.remove();
        if (list.length > shown) {
          var b = el("button", { class: "mk-more", type: "button", text: "Show more (" + (list.length - shown) + " left)" });
          b.addEventListener("click", function () { shown += PAGE; draw(); });
          body.closest(".table-card").insertBefore(b, $("#mk-source"));
        }
        if (!list.length) body.appendChild(el("tr", {}, [el("td", { colspan: "7", class: "muted", text: "No card matches that search." })]));
        var u = new URLSearchParams();
        if (q.value) u.set("q", q.value);
        if (sort.value !== "price") u.set("sort", sort.value);
        if (picked.length) u.set("compare", picked.join(","));
        history.replaceState(null, "", location.pathname + (String(u) ? "?" + u : ""));
      }
      function compare() {
        var box = $("#mk-compare");
        box.textContent = "";
        var chosen = picked.map(function (s) { return cards.filter(function (c) { return c.slug === s; })[0]; }).filter(Boolean);
        if (!chosen.length) { box.hidden = true; return; }
        box.hidden = false;
        box.appendChild(el("div", { class: "kicker", text: "Compare" }));
        box.appendChild(el("h2", { text: chosen.length === 1 ? "Tick another card to compare" : chosen.length + " cards side by side" }));
        var rows = [["Price", function (c) { return money(c.price); }], ["7 days", function (c) { return pct(c.ch7); }],
          ["30 days", function (c) { return pct(c.ch30); }], ["Released", function (c) { return c.released ? fmtDateYear(c.released) : "—"; }],
          ["Rarity", function (c) { return c.rarity || "—"; }], ["Tracked since", function (c) { return c.first ? fmtDateYear(c.first) : "—"; }]];
        var t = el("table", { class: "data" }, [el("thead", {}, [el("tr", {}, [el("th", { text: "" })].concat(chosen.map(function (c, i) {
          return el("th", {}, [el("a", { href: pageOf(c), text: label(c), style: "color:" + LINE[i] })]); })))]),
          el("tbody", {}, rows.map(function (r) {
            return el("tr", {}, [el("td", { class: "first muted", text: r[0] })].concat(chosen.map(function (c) { return el("td", { "data-label": label(c), class: "num", text: r[1](c) }); })));
          }))]);
        box.appendChild(el("div", { style: "overflow-x:auto" }, [t]));
        if (chosen.length > 1) {
          var chart = el("div", { class: "mk-chart" });
          box.appendChild(el("p", { class: "muted", style: "margin:16px 0 0", text: "Each card's market price as a % change from the first day all of them have a price." }));
          box.appendChild(chart);
          var sets = {}; chosen.forEach(function (c) { sets[c.set_slug] = true; });
          Promise.all(Object.keys(sets).map(function (s) { return getJSON("/data/market/sets/" + s + ".json").catch(function () { return null; }); })).then(function (shards) {
            var series = {}; shards.forEach(function (sh) { if (sh) Object.keys(sh.cards || {}).forEach(function (k) { series[k] = sh.cards[k].series; }); });
            var starts = chosen.map(function (c) { var p = series[c.slug] || []; return p.length ? p[0][0] : null; });
            if (starts.some(function (s) { return !s; })) { chart.appendChild(el("p", { class: "muted", text: "A card here has no stored history yet." })); return; }
            var start = starts.sort().slice(-1)[0];
            var lines = chosen.map(function (c, i) {
              var p = series[c.slug], base = null;
              p.forEach(function (q) { if (q[0] <= start) base = q[1]; });
              var pts = [[start, 0]].concat(p.filter(function (q) { return q[0] > start; }).map(function (q) { return [q[0], (q[1] / base - 1) * 100]; }));
              return { name: displayName(c), color: LINE[i], points: pts };
            });
            stepChart(chart, lines, idx.as_of, { fmt: function (v) { return (v > 0 ? "+" : "") + Math.round(v) + "%"; }, tip: pct, baseline: 0, floorZero: false, aria: "Compared cards, % change" });
            chart.appendChild(el("div", { class: "mk-legend" }, lines.map(function (ln) { return el("span", {}, [el("i", { style: "background:" + ln.color }), ln.name]); })));
          });
        }
        var clear = el("button", { class: "mk-clear", type: "button", text: "Clear the comparison" });
        clear.addEventListener("click", function () { picked = []; draw(); compare(); });
        box.appendChild(clear);
      }
      var timer;
      q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { shown = PAGE; draw(); }, 120); });
      sort.addEventListener("change", function () { shown = PAGE; draw(); });
      draw(); compare();
    }).catch(function (e) {
      $("#mk-body").appendChild(el("tr", {}, [el("td", { colspan: "7", class: "muted", text: "The card list couldn't load. Try again in a minute." })]));
      if (window.console) console.error(e);
    });
  }

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
    var page = document.body.getAttribute("data-page");
    if (page === "market-card") renderCard(); else if (page === "market-search") renderSearch();
  });
})();
