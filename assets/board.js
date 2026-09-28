/* Mission Control board · jacknbauhs.com
   Every section reads a JSON file in /data, so the nightly feed only replaces data files. */
(function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var SVGNS = "http://www.w3.org/2000/svg";
  var COLORS = {
    text: "#ECEAF6", muted: "#9A96B8", grid: "rgba(236,234,246,0.08)", accent: "#A78BFA",
    accentText: "#C4B5FD", flag: "#F472B6", flagText: "#F9A8D4", warn: "#FBBF24", neutral: "#9A96B8"
  };
  var LABELS = {
    ORGANIC: { text: "Clean", chip: "chip-ok" },
    RELIST: { text: "Relist", chip: "chip-warn" },
    DUPLICATE: { text: "Duplicate", chip: "chip-neutral" },
    DATA_ERROR: { text: "Doesn't belong", chip: "chip-flag" },
    BEST_OFFER: { text: "Best offer", chip: "chip-info" }
  };

  /* ---------- helpers ---------- */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
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
  function parseDate(s) { var p = s.split("-"); return new Date(Date.UTC(+p[0], +p[1] - 1, +(p[2] || 1))); }
  function fmtDate(s) { var d = parseDate(s); return MONTHS[d.getUTCMonth()] + " " + d.getUTCDate(); }
  function money(n) {
    var whole = Math.abs(n - Math.round(n)) < 0.005;
    return "$" + n.toLocaleString("en-US", { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2 });
  }
  function moneyShort(n) { return n >= 1000 ? "$" + (Math.round(n / 100) / 10).toLocaleString("en-US") + "k" : money(n); }
  function pct(n, digits) {
    var v = Math.abs(n).toFixed(digits == null ? 0 : digits);
    return (n > 0 ? "+" : n < 0 ? "−" : "") + v + "%";
  }
  function chip(label) {
    var info = LABELS[label] || { text: label, chip: "chip-neutral" };
    return el("span", { class: "chip " + info.chip, text: info.text.toUpperCase() });
  }
  function getJSON(path) {
    return fetch(path, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(path + " " + r.status);
      return r.json();
    });
  }
  function daysFromToday(iso) {
    var now = new Date();
    var today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((parseDate(iso).getTime() - today) / 86400000);
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
      var t = svg("text", { x: L - 10, y: y(v) + 4, "text-anchor": "end", "font-size": 12, fill: COLORS.muted, "font-family": "Geist Mono, monospace" });
      t.textContent = "$" + (v / 1000) + "k"; root.appendChild(t);
    }
    // month labels
    var d = parseDate(card.window.start);
    while (d.getTime() <= end) {
      var iso = d.toISOString().slice(0, 10);
      var mid = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 15)).toISOString().slice(0, 10);
      var ml = svg("text", { x: x(mid), y: H - 14, "text-anchor": "middle", "font-size": 12, fill: COLORS.muted, "font-family": "Geist Mono, monospace", "letter-spacing": 1 });
      ml.textContent = MONTHS[d.getUTCMonth()].toUpperCase(); root.appendChild(ml);
      if (iso !== card.window.start) root.appendChild(svg("line", { x1: x(iso), x2: x(iso), y1: T, y2: H - B, stroke: COLORS.grid, "stroke-dasharray": "2 6" }));
      d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
    }
    // event marker
    if (card.event) {
      var ex = x(card.event.date);
      root.appendChild(svg("line", { x1: ex, x2: ex, y1: T - 8, y2: H - B, stroke: COLORS.accentText, "stroke-dasharray": "3 4" }));
      var et = svg("text", { x: ex - 8, y: T + 6, "text-anchor": "end", "font-size": 11, fill: COLORS.accentText, "font-family": "Geist Mono, monospace" });
      et.textContent = fmtDate(card.event.date).toUpperCase() + " · REPRINT ON SHELVES"; root.appendChild(et);
    }
    // clean monthly median steps
    Object.keys(card.monthly_clean).forEach(function (m) {
      var p = m.split("-"), s = Date.UTC(+p[0], +p[1] - 1, 1), e = Date.UTC(+p[0], +p[1], 1);
      var xs = L + (Math.max(s, start) - start) * (W - L - R) / (end - start);
      var xe = L + (Math.min(e, end) - start) * (W - L - R) / (end - start);
      var yy = y(card.monthly_clean[m]);
      root.appendChild(svg("line", { x1: xs + 4, x2: xe - 4, y1: yy, y2: yy, stroke: COLORS.accent, "stroke-width": 4, "stroke-linecap": "round" }));
      var lab = svg("text", { x: (xs + xe) / 2, y: yy - 10, "text-anchor": "middle", "font-size": 12, fill: COLORS.accentText, "font-family": "Geist Mono, monospace" });
      lab.textContent = moneyShort(card.monthly_clean[m]); root.appendChild(lab);
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
        var ot = svg("text", { x: nearRight ? cx - 10 : cx + 9, y: cy + 4, "text-anchor": nearRight ? "end" : "start", "font-size": 11, fill: COLORS.flagText, "font-family": "Geist Mono, monospace" });
        ot.textContent = "↓ " + money(s.price); root.appendChild(ot);
      }
    });
    return root;
  }

  /* ---------- index page ---------- */
  function renderIndex() {
    Promise.all([
      getJSON("data/meta.json"), getJSON("data/movers.json"), getJSON("data/flags.json"), getJSON("data/calls.json"),
      getJSON("data/drops.json"), getJSON("data/rip_ev.json"), getJSON("data/cards/crystal-lugia-psa-8.json"),
      getJSON("data/cards/crystal-charizard-psa-9.json")
    ]).then(function (r) {
      var meta = r[0], movers = r[1], flags = r[2], calls = r[3], drops = r[4], rip = r[5], lugia = r[6], zard = r[7];
      $("#status").textContent = "Updated " + meta.updated_label;

      // hero chart
      var hero = $("#hero-chart");
      hero.appendChild(salesChart(lugia, fitChart(hero, 0.52)));
      $("#hero-change").textContent = pct(lugia.change_pct);

      // stats
      var stats = [
        { v: pct(lugia.change_pct), c: "up", t: "Crystal Lugia PSA 8, clean median June to September. Reprinted." },
        { v: pct(zard.change_pct), c: "up", t: "Crystal Charizard PSA 9, same months. Never reprinted." },
        { v: flags.headline.value + " of " + flags.headline.of, c: "flag", t: "Sold records on those two cards that don't belong in the math." },
        { v: fmtDate(nextDrop(drops).date), c: "", t: "Next release: " + nextDrop(drops).name + "." }
      ];
      var sEl = $("#stats");
      stats.forEach(function (s) {
        sEl.appendChild(el("div", { class: "card stat" }, [
          el("span", { class: "num " + (s.c === "up" ? "up" : ""), style: s.c === "flag" ? "color: var(--flag)" : "", text: s.v }),
          el("p", { text: s.t })
        ]));
      });

      // movers
      $("#movers-note").textContent = movers.live_note;
      var body = $("#movers-body");
      movers.items.forEach(function (m) {
        var nameCell = el("td", { class: "first" }, [
          m.link ? el("a", { href: m.link, class: "name", text: m.name }) : el("span", { class: "name", text: m.name }),
          el("span", { class: "sub", text: m.set + " · " + m.note })
        ]);
        body.appendChild(el("tr", {}, [
          nameCell,
          el("td", { "data-label": "Tier", class: "num", text: m.tier }),
          el("td", { "data-label": "Last sale", class: "num", text: money(m.last.price) + " · " + fmtDate(m.last.date) }),
          el("td", { "data-label": "Clean median", class: "num", text: money(m.clean_median) }),
          el("td", { "data-label": "Change", class: "num " + (m.change_pct >= 0 ? "up" : "down"), text: (m.change_pct >= 0 ? "▲ " : "▼ ") + pct(m.change_pct) }),
          el("td", { "data-label": "Flagged", class: "num", text: m.flagged + " of " + m.sales })
        ]));
      });

      // flags
      $("#flag-count").textContent = flags.headline.value + "/" + flags.headline.of;
      $("#flag-text").textContent = flags.text;
      var fl = $("#flag-list");
      flags.items.forEach(function (f) {
        fl.appendChild(el("li", {}, [
          el("span", {}, [el("strong", { text: f.card }), el("span", { class: "sub", text: fmtDate(f.date) + " · " + money(f.price) })]),
          chip(f.label),
          el("span", { class: "why", text: f.why })
        ]));
      });
      var lg = $("#labels");
      flags.labels.forEach(function (l) {
        lg.appendChild(el("div", { class: "card" }, [chip(l.id), el("p", { text: l.meaning })]));
      });

      // rip ev
      $("#rip-note").textContent = rip.live_note;
      var rb = $("#rip-body");
      function drawRip(game) {
        rb.innerHTML = "";
        var rows = rip.items.filter(function (i) { return i.game === game; });
        if (!rows.length) {
          rb.appendChild(el("tr", {}, [el("td", { colspan: "5", class: "first muted", text: game + " arrives with the Rip EV build, with a confidence tag on every row." })]));
          return;
        }
        rows.forEach(function (i, n) {
          rb.appendChild(el("tr", {}, [
            el("td", { class: "first" }, [el("span", { class: "name", text: i.product })]),
            el("td", { "data-label": "EV per box" }, [el("span", { class: "skeleton", style: "width:" + (56 + (n * 7) % 24) + "px" })]),
            el("td", { "data-label": "Ratio" }, [el("span", { class: "skeleton", style: "width:" + (36 + (n * 5) % 14) + "px" })]),
            el("td", { "data-label": "Hit over $50" }, [el("span", { class: "skeleton", style: "width:" + (34 + (n * 3) % 12) + "px" })]),
            el("td", { "data-label": "Pull rates" }, [el("span", { class: "skeleton", style: "width:64px;height:20px;border-radius:10px" })])
          ]));
        });
      }
      drawRip("Pokémon");
      Array.prototype.forEach.call(document.querySelectorAll("#rip-games button"), function (b) {
        b.addEventListener("click", function () {
          Array.prototype.forEach.call(document.querySelectorAll("#rip-games button"), function (o) { o.setAttribute("aria-pressed", "false"); });
          b.setAttribute("aria-pressed", "true");
          drawRip(b.getAttribute("data-game"));
        });
      });

      // calls
      var on = calls.items.filter(function (c) { return c.on_record; });
      var cWrap = $("#calls-wrap");
      if (!on.length) {
        cWrap.appendChild(el("div", { class: "card empty" }, [
          el("h3", { text: "The first calls go on the record soon." }),
          el("p", { text: "Each one gets a date, a check date and a verdict. Hits and misses both stay up." })
        ]));
      } else {
        var tb = el("tbody");
        on.forEach(function (c) {
          tb.appendChild(el("tr", {}, [
            el("td", { class: "first" }, [el("span", { class: "name num", text: "#" + c.id }), el("span", { class: "sub", text: c.text })]),
            el("td", { "data-label": "Dated", class: "num", text: fmtDate(c.dated) }),
            el("td", { "data-label": "Check", class: "num", text: fmtDate(c.check_date) }),
            el("td", { "data-label": "Status" }, [el("span", { class: "chip chip-accent", text: c.status.toUpperCase() })])
          ]));
        });
        cWrap.appendChild(el("div", { class: "card table-card" }, [el("table", { class: "data" }, [
          el("thead", {}, [el("tr", {}, [el("th", { text: "Call" }), el("th", { text: "Dated" }), el("th", { text: "Check" }), el("th", { text: "Status" })])]), tb
        ])]));
      }

      // drops
      var dw = $("#drops-grid");
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
      $("#drops-source").textContent = "Dates checked Sep 28, 2026: " + drops.source.replace(/, checked Sep 28, 2026$/, "") + ".";
    }).catch(function (e) {
      var m = $("#load-error"); if (m) { m.hidden = false; }
      if (window.console) console.error(e);
    });
  }

  // Draw at the container's real width so chart text stays readable on phones.
  function fitChart(box, ratio) {
    var w = Math.round(Math.max(340, Math.min(1100, box.clientWidth || 700)));
    return { width: w, height: Math.round(Math.max(260, w * ratio)) };
  }

  function sortKey(d) { return d.date_precision === "month" ? d.date.slice(0, 8) + "31" : d.date; }

  function nextDrop(drops) {
    var up = drops.items.filter(function (d) { return d.date_precision === "day" && daysFromToday(d.date) >= 0; })
      .sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    return up[0] || drops.items[0];
  }

  /* ---------- card page ---------- */
  function renderCard() {
    var id = (new URLSearchParams(location.search).get("id") || "crystal-lugia-psa-8").replace(/[^a-z0-9-]/g, "");
    Promise.all([getJSON("data/meta.json"), getJSON("data/cards/" + id + ".json")]).then(function (r) {
      var meta = r[0], c = r[1];
      $("#status").textContent = "Updated " + meta.updated_label;
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
          el("span", { class: "num " + (q.cls === "up" ? "up" : ""), style: q.cls === "flag" ? "color: var(--flag)" : "", text: q.v }),
          q.p ? el("p", { text: q.p }) : null
        ]));
      });
      $("#card-chart").appendChild(salesChart(c, fitChart($("#card-chart"), 0.42)));
      $("#card-summary").textContent = c.summary;
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
