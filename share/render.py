#!/usr/bin/env python3
"""Share kit: turns the board's JSON into ready-to-post images.

Reads the same files the board reads (data/file.json, data/cards/*.json, data/flags.json,
data/calls.json, data/meta.json), fills the templates in share/templates, and screenshots
each one with headless Chromium. Nothing on an image is typed in by hand: change the JSON,
run this again.

What it makes (share/out):
  file-<date>-cover.png            this week's file: every card in it and the flags headline
  file-<date>-<card>.png           one per card: the sales chart and the clean move
  flags-<date>-cover.png           "what got caught": every flagged record on one image
  flag-<sale date>-<card>-<label>.png   one per flagged record (hand-checked file and nightly feed)
  calls-<date>-cover.png           every call on the record, on one image
  call-<id>-<dated>.png            one per call (open, hit or miss)
  og-board.png                     1200x630 link preview, also copied to assets/og.png
  captions.md                      a caption and alt text for every image
  html/*.html                      the filled templates, open in a browser to tweak the look

Setup (once):  pip install jinja2 playwright  &&  playwright install chromium
Run:           python share/render.py                 (everything)
               python share/render.py --only calls    (file, flags, calls or og)
               python share/render.py --html-only     (no screenshots, just the HTML)
               python share/render.py --scale 2       (2160x2700 images)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import re
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent  # the board repo
SHARE = ROOT / "share"
DATA = ROOT / "data"
FONTS = SHARE / "fonts"
SITE = "board.jacknbauhs.com"
OG_URL = f"https://{SITE}/assets/og.png"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]

# Sale Integrity labels, same words as assets/board.js.
LABELS = {
    "ORGANIC": ("Clean", "chip-ok", "okc", "#6EE7B7", "A real sale of the right card. Counts in full."),
    "BEST_OFFER": ("Best offer", "chip-info", "infoc", "#7DD3FC", "Shown at the accepted price, not the asking price."),
    "RELIST": ("Relist", "chip-warn", "warnc", "#FCD34D", "The same listing sold more than once. The first sale may not have gone through. Counts half."),
    "DUPLICATE": ("Duplicate", "chip-neutral", "neutralc", "#9A96B8", "One sale recorded twice. Counted once."),
    "DATA_ERROR": ("Doesn't belong", "chip-flag", "flagc", "#F472B6", "Wrong card, wrong grade, or a price no real copy sells for. Left out."),
    "EVENT_DRIVEN": ("Event", "chip-info", "infoc", "#7DD3FC", "A jump tied to news, like a reprint or a viral pull. Counts half until it holds."),
    "SUPPLY_SHOCK": ("Supply shock", "chip-warn", "warnc", "#FCD34D", "More copies selling while the price sits flat or falls."),
    "THIN_SPIKE": ("Thin spike", "chip-warn", "warnc", "#FCD34D", "Up on a handful of sales, with no volume behind it."),
    "SUSPECT_PUMP": ("Suspect pump", "chip-flag", "flagc", "#F472B6", "A spike with warning signs, like one seller doing most of the selling. Left out."),
    "SUSPECT_WASH": ("Suspect wash", "chip-flag", "flagc", "#F472B6", "The same slab selling in a loop, or bidding that looks staged. Left out."),
    "UNCONFIRMED": ("Unconfirmed", "chip-neutral", "neutralc", "#9A96B8", "No checked sales behind the move yet."),
}
POST_W, POST_H = 1080, 1350
OG_W, OG_H = 1200, 630


# ---------- helpers ----------
def load(name: str):
    p = DATA / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def parse_date(s) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def fmt_date(s) -> str:
    d = parse_date(s)
    return f"{MONTHS[d.month - 1]} {d.day}"


def fmt_date_year(s) -> str:
    d = parse_date(s)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def month_name(key: str) -> str:
    return MONTHS_LONG[int(key[5:7]) - 1]


def money(n) -> str:
    if n is None:
        return "—"
    whole = abs(n - round(n)) < 0.005
    return f"${n:,.0f}" if whole else f"${n:,.2f}"


def money_short(n) -> str:
    if n >= 1000:
        k = round(n / 100) / 10
        return f"${k:,.0f}k" if k == int(k) else f"${k:,.1f}k"
    return money(n)


def pct(n, digits=0) -> str:
    if n is None:
        return "—"
    sign = "+" if n > 0 else ("−" if n < 0 else "")
    return f"{sign}{abs(n):.{digits}f}%"


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    return s or "x"


def label_info(label: str):
    if label in LABELS:
        return LABELS[label]
    text = str(label or "").lower().replace("_", " ").capitalize()
    return (text, "chip-neutral", "neutralc", "#9A96B8", "")


def sentence(t: str) -> str:
    t = str(t or "").strip()
    if not t:
        return ""
    t = t[0].upper() + t[1:]
    return t if t[-1] in ".!?" else t + "."


def change_months(card: dict):
    """The two monthly_clean keys the card's change_pct compares, read from its change_label
    ("June to September, clean median"). Falls back to the first and last months."""
    keys = list(card.get("monthly_clean", {}).keys())
    label = str(card.get("change_label", "")).lower()
    found = []
    for word in re.findall(r"[a-z]+", label):
        for i, m in enumerate(MONTHS_LONG):
            if word == m.lower() or word == MONTHS[i].lower() or word == "sept" and i == 8:
                key = next((k for k in keys if int(k[5:7]) == i + 1), None)
                if key and key not in found:
                    found.append(key)
    if len(found) >= 2:
        return found[0], found[-1]
    return (keys[0], keys[-1]) if keys else (None, None)


def sky(w: int, h: int, seed: int = 7) -> str:
    """The board's starfield and orbit, sized to the frame. Same seed, same sky, every run."""
    rnd = random.Random(seed)
    parts = [f'<svg class="sky" width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true">']
    parts.append(f'<ellipse cx="{w * 0.7:.0f}" cy="{h * 0.22:.0f}" rx="{w * 0.48:.0f}" ry="{h * 0.11:.0f}" fill="none" '
                 f'stroke="rgba(139,92,246,0.16)" stroke-width="1.5" transform="rotate(-8 {w * 0.7:.0f} {h * 0.22:.0f})"/>')
    for _ in range(26):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.choice([0.8, 0.8, 1.0, 1.0, 1.2, 1.6])
        o = rnd.choice([0.25, 0.35, 0.45, 0.6, 0.8])
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ECEAF6" opacity="{o}"/>')
    parts.append("</svg>")
    return "".join(parts)


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


# ---------- the sales chart (a port of salesChart in assets/board.js, sized for the post) ----------
def sales_chart(card: dict, W: int = 936, H: int = 430, highlight=None) -> str:
    """highlight: (date, price) of one sold record to ring and label."""
    L, R, T, B = 96, 30, 48, 58
    start = parse_date(card["window"]["start"]).toordinal()
    end = parse_date(card["window"]["end"]).toordinal()
    in_scale = [s["price"] for s in card["sales"] if (s.get("weight") or 0) > 0]
    lo, hi = min(in_scale), max(in_scale)
    step = 10000 if hi - lo > 20000 else 5000
    y_min = max(0, math.floor((lo * 0.9) / step) * step)
    y_max = math.ceil((hi * 1.06) / step) * step

    def x(iso):
        return L + (parse_date(iso).toordinal() - start) * (W - L - R) / (end - start)

    def y(v):
        return T + (y_max - v) * (H - T - B) / (y_max - y_min)

    mono = 'font-family="Geist Mono, ui-monospace, monospace"'
    keys = list(card["monthly_clean"].keys())
    first, last = card["monthly_clean"][keys[0]], card["monthly_clean"][keys[-1]]
    alt = (f'{card["name"]} {card["tier"]}: every sold record from {fmt_date(card["window"]["start"])} with the clean '
           f'monthly median, from {money(first)} to {money(last)}. Flagged sales are marked.')
    out = [f'<svg class="chart" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(alt)}">']

    v = y_min
    while v <= y_max:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="rgba(236,234,246,0.08)"/>')
        out.append(f'<text x="{L - 14}" y="{y(v) + 6:.1f}" text-anchor="end" font-size="18" fill="#9A96B8" {mono}>${v / 1000:g}k</text>')
        v += step

    d = parse_date(card["window"]["start"]).replace(day=1)
    end_date = parse_date(card["window"]["end"])
    while d <= end_date:
        mid = d.replace(day=15).isoformat()
        out.append(f'<text x="{x(mid):.1f}" y="{H - 18}" text-anchor="middle" font-size="18" fill="#9A96B8" letter-spacing="1.5" {mono}>'
                   f'{MONTHS[d.month - 1].upper()}</text>')
        if d.isoformat() != card["window"]["start"]:
            out.append(f'<line x1="{x(d.isoformat()):.1f}" x2="{x(d.isoformat()):.1f}" y1="{T}" y2="{H - B}" '
                       f'stroke="rgba(236,234,246,0.08)" stroke-dasharray="2 6"/>')
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)

    if card.get("event"):
        ex = x(card["event"]["date"])
        out.append(f'<line x1="{ex:.1f}" x2="{ex:.1f}" y1="{T - 10}" y2="{H - B}" stroke="#C4B5FD" stroke-dasharray="3 4"/>')
        out.append(f'<text x="{ex - 10:.1f}" y="{T + 8}" text-anchor="end" font-size="17" fill="#C4B5FD" {mono}>'
                   f'{fmt_date(card["event"]["date"]).upper()} · REPRINT ON SHELVES</text>')

    hl_month = str(highlight[0])[:7] if highlight else None
    for m, val in card["monthly_clean"].items():
        ms = dt.date(int(m[:4]), int(m[5:7]), 1)
        me = (ms.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        xs = L + (max(ms.toordinal(), start) - start) * (W - L - R) / (end - start)
        xe = L + (min(me.toordinal(), end) - start) * (W - L - R) / (end - start)
        yy = y(val)
        out.append(f'<line x1="{xs + 5:.1f}" x2="{xe - 5:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#A78BFA" stroke-width="5" stroke-linecap="round"/>')
        if m != hl_month:  # the ringed record's month carries its clean median in the ring label instead
            out.append(f'<text x="{(xs + xe) / 2:.1f}" y="{yy - 14:.1f}" text-anchor="middle" font-size="18" fill="#C4B5FD" {mono} '
                       f'paint-order="stroke" stroke="#0B0A14" stroke-width="6">{money_short(val)}</text>')

    floor_y = H - B - 8
    for s in card["sales"]:
        cx = x(s["date"])
        off = s["price"] < y_min
        cy = floor_y if off else y(s["price"])
        lab = s.get("label")
        color = {"DATA_ERROR": "#F472B6", "RELIST": "#FCD34D", "DUPLICATE": "#9A96B8"}.get(lab, "#ECEAF6")
        clean = lab == "ORGANIC"
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{6 if clean else 8}" fill="{"#0B0A14" if clean else color}" '
                   f'stroke="{color}" stroke-width="2.5"/>')
        hit = highlight and s["date"] == highlight[0] and abs(s["price"] - highlight[1]) < 0.01
        if off and not hit:
            near_right = cx > W - R - 150
            out.append(f'<text x="{cx - 14 if near_right else cx + 13:.1f}" y="{cy + 6:.1f}" text-anchor="{"end" if near_right else "start"}" '
                       f'font-size="16" fill="#F9A8D4" {mono}>↓ {money(s["price"])}</text>')
        if hit:
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="17" fill="none" stroke="{color}" stroke-width="2.5" stroke-dasharray="4 4"/>')
            label = f'THIS RECORD · {money(s["price"])}' + (" (OFF THE CHART)" if off else "")
            if hl_month in card["monthly_clean"]:
                label += f' · CLEAN {MONTHS[int(hl_month[5:7]) - 1].upper()} {money_short(card["monthly_clean"][hl_month])}'
            half = len(label) * 10.3 / 2
            tx = min(max(cx, L + half), W - R - half)
            ty = cy - 30 if cy - 30 > T + 26 else cy + 42
            out.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="17" fill="{color}" {mono} '
                       f'paint-order="stroke" stroke="#0B0A14" stroke-width="6">{label}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------- build the pages ----------
class Kit:
    def __init__(self, out: Path, scale: int):
        self.out = out
        self.html_dir = out / "html"
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.scale = scale
        self.env = Environment(loader=FileSystemLoader(str(SHARE / "templates")),
                               autoescape=select_autoescape(["html"]))
        self.pages: list[dict] = []      # {name, html, png, w, h, caption, alt}
        self.fonts_url = FONTS.resolve().as_uri()

    def page(self, template: str, name: str, ctx: dict, caption: str, alt: str, w=POST_W, h=POST_H):
        ctx = dict(ctx)
        ctx.setdefault("title", name)
        ctx["fonts"] = self.fonts_url
        ctx["sky"] = sky(w, h)
        html = self.env.get_template(template).render(**ctx)
        html_path = self.html_dir / f"{name}.html"
        html_path.write_text(html, encoding="utf-8")
        self.pages.append({"name": name, "html": html_path, "png": self.out / f"{name}.png",
                           "w": w, "h": h, "caption": caption, "alt": alt})

    # --- this week's file ---
    def build_file(self):
        f = load("file.json")
        if not f or not f.get("rows"):
            print("file.json: nothing to render")
            return
        as_of = f.get("as_of") or f.get("pulled")
        kicker = f"The file · {fmt_date(as_of)}"
        tag = f"130point · pulled {fmt_date(f.get('pulled') or as_of)}"
        rows = []
        for r in f["rows"]:
            up = (r.get("change_pct") or 0) >= 0
            card = load(f"cards/{r.get('id')}.json") if r.get("id") else None
            if card and card.get("monthly_clean"):
                k0, k1 = change_months(card)
                line3 = (f"Clean median {money(card['monthly_clean'][k1])} in {month_name(k1)}, "
                         f"from {money(card['monthly_clean'][k0])} in {month_name(k0)}. ")
            else:
                line3 = f"Clean median {money(r.get('clean_median'))} ({r.get('window_label', '')}). "
            line3 += (f"Last sale {money(r['last']['price'])} on {fmt_date(r['last']['date'])}. "
                      f"{r.get('sales')} sold records, {r.get('flagged')} kept out.")
            rows.append({
                "name": r["name"], "tier": r["tier"],
                "line2": f"{r['set']} · {r['note']}" if r.get("note") else r["set"],
                "pct": pct(r.get("change_pct")), "pct_class": "up" if up else "down",
                "line3": line3,
            })
        fl = f.get("flags") or {}
        head = fl.get("headline") or {}
        flags_ctx = None
        if head.get("value") is not None:
            flags_ctx = {"value": head["value"], "of": head.get("of"), "text": sentence(fl.get("stat") or head.get("label"))}
        n = len(f["rows"])
        lede = f"{n} card{'s' if n != 1 else ''}, every sold record since {month_name(min(load('cards/' + c + '.json')['window']['start'] for c in f['cards']) ) if f.get('cards') else 'the start of the window'}, each one checked before it counts."
        self.page("file-cover.html", f"file-{as_of}-cover", {
            "kicker": kicker, "tag": tag, "file_title": f["title"], "lede": lede, "rows": rows, "flags": flags_ctx,
            "foot": f.get("foot", ""),
        }, caption=(f"This week's file: {f['title']}. " +
                    " ".join(f"{r['name']} {r['tier']} {r['pct']}: {r['line3'].split('. ')[0][:1].lower()}{r['line3'].split('. ')[0][1:]}." for r in rows) +
                    (f" {head['value']} of {head.get('of')} sold records don't belong in the math." if flags_ctx else "") +
                    f" Source: 130point, pulled {fmt_date(f.get('pulled') or as_of)}. {SITE}"),
            alt=f"This week's file on the Astronaut Time board: {f['title']}, with each card's clean move and how many records were kept out.")

        for cid in f.get("cards", []):
            card = load(f"cards/{cid}.json")
            row = next((r for r in f["rows"] if r.get("id") == cid), None)
            if not card:
                print(f"cards/{cid}.json missing, skipped")
                continue
            k0, k1 = change_months(card)
            up = (card.get("change_pct") or 0) >= 0
            present = {s.get("label") for s in card["sales"]}
            legend = [{"text": label_info(k)[0].lower(), "color": label_info(k)[3]}
                      for k in ["DATA_ERROR", "RELIST", "DUPLICATE"] if k in present]
            set_line = f"{card['set']} {card.get('number', '')}".strip()
            self.page("file-card.html", f"file-{as_of}-{cid}", {
                "kicker": kicker, "tag": tag, "name": card["name"], "tier": card["tier"], "set": set_line,
                "note": (row or {}).get("note"), "big": pct(card.get("change_pct")), "big_class": "up" if up else "down",
                "beside_1": f"{month_name(k0)} to {month_name(k1)},",
                "beside_2": "clean median.",
                "chart": sales_chart(card), "legend": legend, "take": card.get("summary", ""),
            }, caption=(f"{card['name']} {card['tier']}: {pct(card.get('change_pct'))} on the clean median, "
                        f"{month_name(k0)} to {month_name(k1)} ({money(card['monthly_clean'][k0])} to "
                        f"{money(card['monthly_clean'][k1])}). {card.get('summary', '')} "
                        f"Every dot is a sold record; the flagged ones are marked. Source: 130point, pulled {fmt_date(f.get('pulled') or as_of)}. {SITE}"),
                alt=f"{card['name']} {card['tier']}, {pct(card.get('change_pct'))} on the clean monthly median from {month_name(k0)} to {month_name(k1)}, with every sold record plotted and the flagged ones marked.")

    # --- flags: the hand-checked file plus the nightly feed ---
    def build_flags(self):
        f = load("file.json") or {}
        as_of = f.get("as_of") or f.get("pulled")
        rows_by_card = {f"{r['name']} {r['tier']}": r for r in f.get("rows", [])}
        cards_by_name = {}
        for cid in f.get("cards", []):
            c = load(f"cards/{cid}.json")
            if c:
                cards_by_name[f"{c['name']} {c['tier']}"] = c
        fl = f.get("flags") or {}
        items = fl.get("items") or []
        head = fl.get("headline") or {}
        pulled = fmt_date(f.get("pulled") or as_of) if as_of else ""

        if items and head.get("value") is not None:
            cover_items = []
            for it in sorted(items, key=lambda i: i["date"], reverse=True):
                text, chip, color, _, _ = label_info(it["label"])
                cover_items.append({"date": fmt_date(it["date"]), "name": it["card"], "chip": chip, "label_text": text,
                                    "price": money(it["price"]), "color": color, "why": it["why"]})
            self.page("flags-cover.html", f"flags-{as_of}-cover", {
                "kicker": f"What got caught · {fmt_date(as_of)}", "tag": f"130point · pulled {pulled}",
                "eyebrow": f.get("title", "This week's file"),
                "value": head["value"], "of": head.get("of"), "headline": head.get("label", ""),
                "text": fl.get("text", ""), "items": cover_items,
            }, caption=(f"{head['value']} of {head.get('of')} {head.get('label', '')}. {fl.get('text', '')} "
                        f"Every one is labeled on the board with the reason. Source: 130point, pulled {pulled}. {SITE}"),
                alt=f"What got caught: {head['value']} of {head.get('of')} sold records that don't belong in the math, listed with dates, prices and labels.")

        for it in items:
            text, chip, color, _, meaning = label_info(it["label"])
            row = rows_by_card.get(it["card"])
            big = money(it["price"])
            size = "md" if len(big) <= 9 else "sm"
            compare, chart, legend = None, None, []
            card = cards_by_name.get(it["card"])
            if card:
                chart = sales_chart(card, H=350, highlight=(it["date"], it["price"]))
                present = {s_.get("label") for s_ in card["sales"]}
                legend = [{"text": label_info(k)[0].lower(), "color": label_info(k)[3]}
                          for k in ["DATA_ERROR", "RELIST", "DUPLICATE"] if k in present]
            elif row and row.get("clean_median"):
                cm_month = MONTHS_LONG[int(str(row.get("last", {}).get("date", as_of))[5:7]) - 1]
                compare = {"left_label": "This record", "left": big, "left_note": f"Sold {fmt_date_year(it['date'])}",
                           "right_label": "Clean median", "right": money(row["clean_median"]),
                           "right_note": f"{cm_month}, confirmed sales only"}
            self.page("flag.html", f"flag-{it['date']}-{slug(it['card'])}-{slug(text)}", {
                "kicker": f"Flagged · {fmt_date(it['date'])}", "tag": f"130point · pulled {pulled}", "tag_class": "flag",
                "name": it["card"], "sub": f"One sold record, {fmt_date_year(it['date'])}",
                "big": big, "big_size": size, "big_class": color,
                "beside_1": "is what it", "beside_2": "sold for.",
                "chip": chip, "label_text": text, "meaning": meaning, "why": sentence(it["why"]), "compare": compare,
                "chart": chart, "legend": legend,
            }, caption=(f"{it['card']}, sold {fmt_date_year(it['date'])} for {big}. {sentence(it['why'])} "
                        f"Label: {text.lower()}. {meaning} Source: 130point, pulled {pulled}. {SITE}"),
                alt=f"Flagged sold record: {it['card']} for {big} on {fmt_date_year(it['date'])}, labeled {text.lower()}. {sentence(it['why'])}")

        feed = load("flags.json")
        if feed and not feed.get("pending") and feed.get("items"):
            fas = feed.get("as_of") or as_of
            for i, it in enumerate(feed["items"], 1):
                text, chip, color, _, meaning = label_info(it["label"])
                big = pct(it.get("claimed_change_pct"))
                self.page("flag.html", f"flag-{fas}-feed-{i:02d}-{slug(it['name'])}-{slug(text)}", {
                    "kicker": f"Flagged · {fmt_date(fas)}", "tag": f"Mission Control · {fmt_date(fas)}", "tag_class": "flag",
                    "name": it["name"], "sub": it.get("set", ""),
                    "big": big, "big_size": "" if len(big) <= 6 else "md", "big_class": color,
                    "beside_1": "is what the", "beside_2": "chart claims.",
                    "chip": chip, "label_text": text, "meaning": meaning, "why": sentence(it.get("why")), "compare": None,
                    "chart": None, "legend": [],
                }, caption=(f"{it['name']} ({it.get('set', '')}): the chart says {big}. {sentence(it.get('why'))} "
                            f"Label: {text.lower()}. {meaning} {SITE}"),
                    alt=f"Flagged move: {it['name']}, a claimed {big}, labeled {text.lower()}. {sentence(it.get('why'))}")

    # --- calls ---
    def build_calls(self):
        c = load("calls.json")
        items = [i for i in (c or {}).get("items", []) if i.get("on_record", True) and i.get("status") != "withdrawn"]
        if not items:
            print("calls.json: nothing on the record")
            return
        items.sort(key=lambda i: i["id"])

        def status_of(i):
            st = i.get("status", "open")
            chk = i.get("check_date")
            if st == "hit":
                return st, "chip-ok", f"Hit · checked {fmt_date(chk)}", "Hit", "up", f"Hit · checked {fmt_date(chk)}"
            if st == "miss":
                return st, "chip-down", f"Miss · checked {fmt_date(chk)}", "Miss", "down", f"Miss · checked {fmt_date(chk)}"
            return "open", "chip-warn", f"Open · check {fmt_date(chk)}", f"Check {fmt_date(chk)}", "warn", f"Check {fmt_date(chk)}"

        for i in items:
            st, chip, status_text, status_short, tag_class, tag = status_of(i)
            self.page("call.html", f"call-{i['id']}-{i['dated']}", {
                "kicker": f"Call #{i['id']} · {fmt_date(i['dated'])}", "tag": tag, "tag_class": tag_class,
                "id": i["id"], "status": st, "status_chip": chip, "status_text": status_text,
                "dated_long": fmt_date_year(i["dated"]), "text": i["text"], "start": i.get("start", ""),
                "method": i.get("method", ""), "latest": i.get("latest", ""),
                "verdict": i.get("verdict_note") if st in ("hit", "miss") else None,
                "checked_long": fmt_date_year(i.get("checked") or i.get("check_date")),
                "note": (c or {}).get("note", ""),
            }, caption=(f"Call #{i['id']}, on the record {fmt_date_year(i['dated'])}: {i['text']} Start: {i.get('start', '')} "
                        f"Rule: {i.get('method', '')} " +
                        (f"Verdict ({st}): {i.get('verdict_note', '')} " if st in ("hit", "miss") else f"Check me {fmt_date(i['check_date'])}. ") +
                        f"Misses stay up. {SITE}"),
                alt=f"Call #{i['id']}, {status_text.lower()}: {i['text']}")

        dated = max(i["dated"] for i in items)
        checks = sorted({i["check_date"] for i in items if i.get("status", "open") == "open"})
        n = len(items)
        words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}.get(n, str(n))
        headline = f"{words} call{'s' if n != 1 else ''} on the record."
        lede = (f"Dated the day they went public. Check me {fmt_date(checks[0])}. Misses stay up." if checks
                else "Dated the day they went public. Misses stay up.")
        cover_items = []
        for i in items:
            st, chip, status_text, status_short, _, _ = status_of(i)
            cover_items.append({"id": i["id"], "text": i["text"], "start": i.get("start", ""), "status_chip": chip, "status_short": status_short})
        self.page("calls-cover.html", f"calls-{dated}-cover", {
            "kicker": f"On the record · {fmt_date(dated)}", "tag": f"Check {fmt_date(checks[0])}" if checks else "Checked", "tag_class": "warn",
            "headline": headline, "lede": lede, "items": cover_items,
        }, caption=(f"{headline} " + " ".join(f"#{i['id']}: {i['text']}" for i in items) +
                    (f" Check me {fmt_date(checks[0])}." if checks else "") + f" Misses stay up. {SITE}"),
            alt=f"{headline} " + " ".join(f"Number {i['id']}: {i['text']}" for i in items))

    # --- link preview ---
    def build_og(self):
        f = load("file.json") or {}
        meta = load("meta.json") or {}
        updated = (meta.get("generated_at") or f.get("as_of") or dt.date.today().isoformat())[:10]
        stat = None
        featured = f.get("featured")
        row = next((r for r in f.get("rows", []) if r.get("id") == featured), None) or (f.get("rows") or [None])[0]
        if row:
            stat = {"name": f"{row['name']} {row['tier']}", "pct": pct(row.get("change_pct")),
                    "pct_class": "up" if (row.get("change_pct") or 0) >= 0 else "down",
                    "line2": f"{row.get('window_label', '')}. {row.get('sales')} sold records, {row.get('flagged')} kept out."}
        self.page("og.html", "og-board", {
            "frame_class": "og", "kicker": "Mission Control", "tag": f"Updated {fmt_date(updated)}",
            "headline": "The card market, with the fake sales taken out.",
            "lede": "Sales checked one by one, dated calls, release dates. Every number carries its source and its date.",
            "stat": stat,
        }, caption="", alt="Mission Control by Astronaut Time: the card market, with the fake sales taken out.", w=OG_W, h=OG_H)

    # --- render ---
    def screenshot(self):
        from playwright.sync_api import sync_playwright
        problems = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": POST_W, "height": POST_H}, device_scale_factor=self.scale)
            page = ctx.new_page()
            for pg in self.pages:
                page.set_viewport_size({"width": pg["w"], "height": pg["h"]})
                page.goto(pg["html"].as_uri())
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(120)
                report = page.evaluate("""() => {
                    const frame = document.querySelector('.frame').getBoundingClientRect();
                    const pad = parseFloat(getComputedStyle(document.querySelector('.frame')).paddingRight);
                    const bottom = document.querySelector('.bottom').getBoundingClientRect();
                    const out = [];
                    document.querySelectorAll('.body *').forEach(el => {
                        if (el.closest('.watermark')) return;
                        const r = el.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) return;
                        if (r.bottom > bottom.top - 4) out.push('overlaps the footer: ' + el.className + ' "' + (el.textContent || '').trim().slice(0, 40) + '"');
                        if (r.right > frame.right - pad + 1) out.push('runs off the right edge: ' + el.className + ' "' + (el.textContent || '').trim().slice(0, 40) + '"');
                    });
                    const fonts = [...document.fonts].filter(f => f.status === 'error').map(f => f.family + ' ' + f.weight);
                    return {out, fonts};
                }""")
                for msg in report["out"]:
                    problems.append(f"{pg['name']}: {msg}")
                if report["fonts"]:
                    problems.append(f"{pg['name']}: fonts not loaded: {', '.join(report['fonts'])}")
                page.screenshot(path=str(pg["png"]), clip={"x": 0, "y": 0, "width": pg["w"], "height": pg["h"]})
                print(f"wrote {pg['png'].relative_to(ROOT)}")
            browser.close()
        return problems

    def write_captions(self):
        lines = [f"# Captions, {dt.date.today().isoformat()}", "",
                 "One block per image. Caption first, alt text second. Plain facts, the source and the board link; nothing here is a buy.", ""]
        for pg in self.pages:
            if not pg["caption"]:
                continue
            lines += [f"## {pg['png'].name}", "", pg["caption"], "", f"Alt: {pg['alt']}", ""]
        (self.out / "captions.md").write_text("\n".join(lines), encoding="utf-8")

    def place_og(self):
        src = self.out / "og-board.png"
        if not src.exists():
            return
        dest = ROOT / "assets" / "og.png"
        shutil.copyfile(src, dest)
        print(f"copied {dest.relative_to(ROOT)}")
        stamp = (load("meta.json") or {}).get("generated_at") or (load("file.json") or {}).get("as_of") or dt.date.today().isoformat()
        stamp = str(stamp)[:10]
        for name in ("index.html", "card.html", "404.html"):
            p = ROOT / name
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            new = re.sub(r"(https://board\.jacknbauhs\.com/assets/og\.png)(\?v=[0-9-]+)?", rf"\1?v={stamp}", text)
            if new != text:
                p.write_text(new, encoding="utf-8")
                print(f"stamped og:image in {name} (?v={stamp})")


def main():
    ap = argparse.ArgumentParser(description="Render the share kit from the board's JSON.")
    ap.add_argument("--only", default="file,flags,calls,og", help="comma list of file,flags,calls,og")
    ap.add_argument("--out", default=str(SHARE / "out"))
    ap.add_argument("--scale", type=int, default=1, help="device scale factor: 2 gives 2160x2700")
    ap.add_argument("--html-only", action="store_true", help="write the HTML, skip the screenshots")
    args = ap.parse_args()

    kit = Kit(Path(args.out), args.scale)
    wanted = {w.strip() for w in args.only.split(",")}
    # Only the current set lives in out/: old renders of the kinds being rendered go first (git history keeps them).
    prefixes = {"file": ("file-",), "flags": ("flags-", "flag-"), "calls": ("calls-", "call-"), "og": ("og-",)}
    for kind in wanted:
        for pre in prefixes.get(kind, ()):
            for old in list(kit.out.glob(f"{pre}*.png")) + list(kit.html_dir.glob(f"{pre}*.html")):
                old.unlink()
    if "file" in wanted:
        kit.build_file()
    if "flags" in wanted:
        kit.build_flags()
    if "calls" in wanted:
        kit.build_calls()
    if "og" in wanted:
        kit.build_og()
    kit.write_captions()
    print(f"{len(kit.pages)} pages filled in {kit.html_dir.relative_to(ROOT)}")
    if args.html_only:
        return
    problems = kit.screenshot()
    if "og" in wanted:
        kit.place_og()
    if problems:
        print("\nLook at these before posting:")
        for pr in problems:
            print("  " + pr)
        sys.exit(2)
    print("\nclean: nothing overlaps or runs off an edge")


if __name__ == "__main__":
    main()
