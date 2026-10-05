#!/usr/bin/env python3
"""Share kit: turns the board's JSON into ready-to-post images.

Reads the same files the board reads (data/file.json, data/cards/*.json, data/flags.json,
data/calls.json, data/movers.json, data/meta.json), fills the templates in share/templates, and screenshots
each one with headless Chromium. Nothing on an image is typed in by hand: change the JSON,
run this again.

What it makes (share/out):
  file-<date>-cover.png            The File (Tue / Thu / Sat): every card in it and the flags headline
                                   (a market File: its TCGplayer moves as bars and the flags tally)
  file-<date>-<card>.png           one per card: the sales chart and the clean move (a card File only)
  flags-<date>-cover.png           "what got caught": every flagged record on one image
  flag-<sale date>-<card>-<label>.png   one per flagged record (hand-checked file and nightly feed)
  calls-<date>-cover.png           every call on the record, on one image
  call-<id>-<dated>.png            one per call (open, hit or miss)
  moving-<YYYY>-W<ww>.png          what's moving: the TCGplayer movers, named by ISO week (the Thursday market post)
  og-board.png                     1200x630 link preview, also copied to assets/og.png
  site/tile-*.png                  four 1080x1080 tiles at stable names (file, flags, calls, next drop)
  site/latest-*.png                the newest file, flags, calls and moving images at stable names
  site/squarespace.md              ready-to-paste Markdown for jacknbauhs.com image blocks
  captions.md                      a caption and alt text for every image
  html/*.html                      the filled templates, open in a browser to tweak the look

The site/ files never change name, so an image block on jacknbauhs.com that points at
https://board.jacknbauhs.com/share/out/site/<name>.png shows the newest render without
anyone touching the site. .github/workflows/render.yml runs this after every data push.

Setup (once):  pip install jinja2 playwright  &&  playwright install chromium
Run:           python share/render.py                 (everything)
               python share/render.py --only calls    (file, flags, calls, moving, og or site)
               python share/render.py --html-only     (no screenshots, just the HTML)
               python share/render.py --scale 2       (2160x2700 images)
               python share/render.py --changed-only  (skip images whose filled HTML didn't change)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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
# The File's stance: a closed set, same as assets/board.js. Any other value is not shown. A stance is a read, not advice.
STANCES = {"STRONG WATCH": "chip-accent", "WATCH": "chip-info", "NEUTRAL": "chip-neutral", "CAUTION": "chip-warn", "PASS": "chip-down"}
SLOTS = ("Tue story", "Thu market", "Sat build")
# What Mission Control's movers lists cover: window label -> (lowest price in $, smallest move in %). Keep in step with
# its config/board.py (MOVER_MIN_CENTS and MOVER_MIN_PCT for 7d; the one_day list for 1d).
MOVER_RULES = {"7d": (20, 5), "1d": (20, 3)}
MOVING_ROWS = 8
# On a mover, a label speaks to the move, so two read differently than on a single sale.
MOVER_MEANINGS = {"ORGANIC": "the sales checked in the window hold up.", "UNCONFIRMED": "no checked sales speak to the move yet."}
# A market File ("kind": "market" in file.json): TCGplayer price moves instead of a graded card's sales. Its cover shows
# this many rows and its flags cover this many moves; the board shows them all.
MARKET_ROWS = 6
MARKET_FLAG_ROWS = 7
POST_W, POST_H = 1080, 1350
OG_W, OG_H = 1200, 630
TILE = 1080
SITE_URL = f"https://{SITE}/share/out/site"
# The newest render of each kind is copied to share/out/site/latest-<kind>.png, a name that never changes.
LATEST = (("file", "file-*-cover.png", "file cover"), ("flags", "flags-*-cover.png", "flags cover"),
          ("calls", "calls-*-cover.png", "calls cover"), ("moving", "moving-*.png", "What's moving image"))


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


def count_word(n: int) -> str:
    return {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}.get(n, str(n))


def stance_of(src: dict):
    """The stance chip for a file or card, or None when it has none or one outside the closed set."""
    key = re.sub(r"\s+", " ", str(src.get("stance") or "")).strip().upper()
    return {"text": key, "chip": STANCES[key]} if key in STANCES else None


def story_of(src: dict) -> list:
    """Why now, what could break it, what we're watching: the labeled lines a file or card has, in that order."""
    rows = [("Why now", src.get("why_now")), ("What could break it", src.get("risk")), ("What we're watching", src.get("what_to_watch"))]
    return [{"label": label, "text": sentence(t)} for label, t in rows if isinstance(t, str) and t.strip()]


def is_market(f) -> bool:
    """A market File is about TCGplayer price moves: no featured card, no card files, no 130point sales.
    A file.json without "kind" is a card File and renders as it always has."""
    return str((f or {}).get("kind") or "").strip().lower() == "market"


def market_rows(f: dict) -> list:
    return [r for r in f.get("rows") or [] if isinstance(r, dict) and str(r.get("name") or "").strip()
            and isinstance(r.get("change_pct"), (int, float))]


def date_span(dates, year: bool = True) -> str:
    """"Oct 2 to Oct 4, 2026" (or the one date) for a list of YYYY-MM-DD dates; year=False leaves the year off."""
    ds = sorted({str(d)[:10] for d in dates if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d or "")[:10])})
    if not ds:
        return ""
    a, b = ds[0], ds[-1]
    end = fmt_date_year(b) if year else fmt_date(b)
    if a == b:
        return end
    return f"{fmt_date(a) if a[:4] == b[:4] or not year else fmt_date_year(a)} to {end}"


def tally_of(f) -> str:
    """The File's flags tally as it shows it ("15 of 30"), or "" when it has none."""
    head = ((f or {}).get("flags") or {}).get("headline") or {}
    return f"{head['value']} of {head['of']}" if head.get("value") is not None and head.get("of") is not None else ""


def tone(v, f) -> str:
    """How a figure reads, the same rule as tone() in assets/board.js: a signed percentage is up or down,
    the File's flags tally is a flag, anything else is plain."""
    v = str(v or "").strip()
    if re.match(r"\+\d", v):
        return "up"
    if re.match(r"[\u2212-]\d", v):
        return "down"
    return "flagc" if v and v == tally_of(f) else ""


def split_figure(v):
    """"15 of 30" -> ("15", "of 30"), so the number and its "of" can sit at two sizes; anything else stays whole."""
    m = re.fullmatch(r"(\S+)\s+(of\s+.+)", str(v or "").strip())
    return (m.group(1), m.group(2)) if m else (str(v or "").strip(), "")


def market_hero(f: dict, rows: list):
    """A market File's hero title and figure: file.json "hero", else the headline and the first row's change."""
    hero = f.get("hero") if isinstance(f.get("hero"), dict) else {}
    title = str(hero.get("title") or "").strip() or str(f.get("headline") or "").strip() or str(f.get("title") or "")
    value = str(hero.get("value") or "").strip() or (pct(rows[0]["change_pct"], 1) if rows else "")
    return title, value


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
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
        # The hash ignores the fonts path, so the same data renders to the same hash on any machine.
        digest = hashlib.sha256(html.replace(self.fonts_url, "FONTS").encode("utf-8")).hexdigest()
        self.pages.append({"name": name, "html": html_path, "png": self.out / f"{name}.png",
                           "w": w, "h": h, "caption": caption, "alt": alt, "hash": digest})

    # --- site tiles: four square images at stable names, for image blocks on jacknbauhs.com ---
    def build_site(self):
        (self.out / "site").mkdir(parents=True, exist_ok=True)
        f = load("file.json") or {}
        as_of = f.get("as_of") or f.get("pulled")
        self.site_alts: dict[str, str] = {}

        def tile(name, kicker, tag, tag_class, ctx, alt):
            ctx = dict(ctx, frame_class="tile", kicker=kicker, tag=tag, tag_class=tag_class)
            self.page("tile.html", f"site/{name}", ctx, caption="", alt=alt, w=TILE, h=TILE)
            self.site_alts[name] = alt

        # 1. The File: the featured card's clean move.
        featured = f.get("featured")
        row = next((r for r in f.get("rows", []) if r.get("id") == featured), None) or (f.get("rows") or [None])[0]
        if row and as_of:
            up = (row.get("change_pct") or 0) >= 0
            tile("tile-file", "The File", f"130point · {fmt_date(as_of)}", "",
                 {"eyebrow": f"{row['name']} {row['tier']}", "big": pct(row.get("change_pct")),
                  "big_class": "up" if up else "down",
                  "l1": sentence(row.get("window_label", "")),
                  "l2": f"{row.get('sales')} sold records, {row.get('flagged')} kept out. "
                        + (f"{row['note']}." if row.get("note") else "")},
                 alt=f"The File: {row['name']} {row['tier']}, {pct(row.get('change_pct'))} on the clean median "
                     f"({row.get('window_label', '')}). {row.get('sales')} sold records, {row.get('flagged')} kept out.")
        else:
            tile("tile-file", "The File", "Mission Control", "",
                 {"eyebrow": "Every sale checked before it counts", "big": "—", "big_size": "md",
                  "l1": "The file starts with the first hand-checked card.", "l2": ""},
                 alt="The File on the Astronaut Time board starts with the first hand-checked card.")

        # 2. What got caught: the hand-checked file first, the nightly feed once it has a week.
        head = (f.get("flags") or {}).get("headline") or {}
        feed = load("flags.json") or {}
        feed_head = feed.get("headline") or {}
        if head.get("value") is not None and as_of:
            tile("tile-flags", "What got caught", f"130point · {fmt_date(as_of)}", "flag",
                 {"eyebrow": f.get("title", "The File"), "big": str(head["value"]), "small": f"of {head.get('of')}",
                  "big_class": "flagc", "l1": sentence(head.get("label", "")),
                  "l2": "Each one is labeled on the board with the reason."},
                 alt=f"What got caught: {head['value']} of {head.get('of')} {head.get('label', '')}, each labeled with the reason.")
        elif feed_head.get("value") is not None and not feed.get("pending"):
            tile("tile-flags", "What got caught", f"Mission Control · {fmt_date(feed.get('as_of'))}", "flag",
                 {"eyebrow": "Last complete week", "big": pct(feed_head["value"]).lstrip("+"), "big_class": "flagc",
                  "l1": sentence(feed_head.get("label", "of sold dollar volume flagged")),
                  "l2": "Suspect pumps, washes and data errors, taken out before the math."},
                 alt=f"What got caught last week: {pct(feed_head['value'])} {feed_head.get('label', '')}.")
        else:
            tile("tile-flags", "What got caught", "Mission Control", "flag",
                 {"eyebrow": "Sale Integrity Layer", "big": "—", "big_size": "md", "big_class": "flagc",
                  "l1": "Flags start with the first checked sales.", "l2": ""},
                 alt="Flags on the Astronaut Time board start with the first checked sales.")

        # 3. Calls on the record.
        c = load("calls.json") or {}
        calls = [i for i in c.get("items", []) if i.get("on_record", True) and i.get("status") != "withdrawn"]
        if calls:
            n = len(calls)
            open_ = [i for i in calls if i.get("status", "open") == "open"]
            hits = sum(1 for i in calls if i.get("status") == "hit")
            misses = sum(1 for i in calls if i.get("status") == "miss")
            dated = max(i["dated"] for i in calls)
            if open_:
                nxt = min(i["check_date"] for i in open_)
                l1 = f"Check me {fmt_date(nxt)}." if len(open_) == n else f"{len(open_)} open, check {fmt_date(nxt)}."
            else:
                l1 = "All checked."
            record = f"{hits} hit, {misses} missed so far. " if (hits or misses) else ""
            tile("tile-calls", "Calls on the record", f"Dated {fmt_date(dated)}", "warn",
                 {"eyebrow": "Dated the day they went public", "big": str(n),
                  "small": "call" if n == 1 else "calls", "l1": l1, "l2": record + "Misses stay up."},
                 alt=f"{n} call{'s' if n != 1 else ''} on the record, dated the day they went public. {l1} Misses stay up.")
        else:
            tile("tile-calls", "Calls on the record", "Mission Control", "warn",
                 {"eyebrow": "Dated, then checked in public", "big": "0", "small": "calls",
                  "l1": "The first call goes up the day it goes public.", "l2": "Misses stay up."},
                 alt="No calls on the record yet. The first goes up the day it goes public; misses stay up.")

        # 4. Next drop: the first release on or after the data's as_of date.
        d = load("drops.json") or {}
        d_as_of = d.get("as_of") or dt.date.today().isoformat()
        upcoming = sorted((i for i in d.get("items", []) if str(i.get("date", ""))[:10] >= d_as_of[:10]), key=lambda i: i["date"])
        if upcoming:
            nd = upcoming[0]
            month_only = nd.get("date_precision") == "month"
            when = MONTHS_LONG[parse_date(nd["date"]).month - 1] if month_only else fmt_date(nd["date"])
            tile("tile-drop", "Next drop", f"Checked {fmt_date(d_as_of)}", "",
                 {"eyebrow": nd.get("game", ""), "big": when, "big_size": "sm", "big_class": "accentc",
                  "l1": nd["name"], "l2": nd.get("detail", "")},
                 alt=f"Next drop: {nd['name']} ({nd.get('game', '')}), {when}. {nd.get('detail', '')}")
        else:
            tile("tile-drop", "Next drop", "Mission Control", "",
                 {"eyebrow": "Release calendar", "big": "—", "big_size": "md", "big_class": "accentc",
                  "l1": "Nothing dated on the calendar right now.", "l2": ""},
                 alt="Nothing dated on the release calendar right now.")

    def place_latest(self, kinds) -> dict:
        """Copy the newest render of each of these kinds to site/latest-<kind>.png, or drop that copy when the kind has none."""
        site = self.out / "site"
        site.mkdir(parents=True, exist_ok=True)
        stable = {}
        for kind, pattern, _ in LATEST:
            if kind not in kinds:
                continue
            found = sorted(self.out.glob(pattern))
            dest = site / f"latest-{kind}.png"
            if found:
                shutil.copyfile(found[-1], dest)
                stable[kind] = dest
                print(f"copied {found[-1].name} -> {dest.relative_to(ROOT)}")
            elif dest.exists():
                dest.unlink()
        return stable

    def place_site(self):
        """Copy the newest covers to stable names and write the Markdown that jacknbauhs.com pastes in."""
        site = self.out / "site"
        stable = self.place_latest({kind for kind, _, _ in LATEST})
        alts = getattr(self, "site_alts", {})
        lines = ["<!-- Paste into a Markdown block on jacknbauhs.com. Written by share/render.py; the images refresh with the board. -->", ""]
        lines += ["## Four tiles (one Markdown block per column, or all four in one block)", ""]
        for name in ("tile-file", "tile-flags", "tile-calls", "tile-drop"):
            if (site / f"{name}.png").exists():
                lines.append(f"[![{alts.get(name, name)}]({SITE_URL}/{name}.png)](https://{SITE})")
                lines.append("")
        lines += ["## The newest covers (4:5)", ""]
        names = {kind: name for kind, _, name in LATEST}
        for kind, dest in stable.items():
            lines.append(f"[![The newest {names[kind]} from the Astronaut Time board]({SITE_URL}/{dest.name})](https://{SITE})")
            lines.append("")
        (site / "squarespace.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {(site / 'squarespace.md').relative_to(ROOT)}")

    # --- The File (Tue / Thu / Sat): the cover and one image per card ---
    def build_file(self):
        f = load("file.json")
        if not f or not f.get("rows"):
            print("file.json: nothing to render")
            return
        as_of = f.get("as_of") or f.get("pulled")
        # The day it is The File for, when Jack dates it (YYYY-MM-DD; anything else falls back to as_of).
        day = f["date"] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(f.get("date") or "")) else as_of
        kicker = f"The File · {fmt_date(day)}"
        tag = f"130point · pulled {fmt_date(f.get('pulled') or as_of)}"
        # The optional story fields (share/README.md): none of them is needed, and an unknown stance or slot isn't shown.
        stance, story = stance_of(f), story_of(f)
        slot = f.get("slot") if f.get("slot") in SLOTS else None
        headline, dek = str(f.get("headline") or "").strip(), str(f.get("dek") or "").strip()
        if is_market(f):
            self.build_file_market(f, day, kicker, stance, slot, headline, dek)
            return
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
        self.page("file-cover.html", f"file-{day}-cover", {
            "kicker": kicker, "tag": tag, "file_title": headline or f["title"], "lede": dek or lede, "rows": rows, "flags": flags_ctx,
            "foot": f.get("foot", ""), "slot": slot, "stance": stance, "story": story,
            "frame_class": "storied" if story else "",
        }, caption=(f"The File, {fmt_date(day)}{f' ({slot})' if slot else ''}: {sentence(headline) if headline else f['title'] + '.'} " +
                    (f"{dek} " if dek else "") +
                    " ".join(f"{r['name']} {r['tier']} {r['pct']}: {r['line3'].split('. ')[0][:1].lower()}{r['line3'].split('. ')[0][1:]}." for r in rows) +
                    (f" {head['value']} of {head.get('of')} sold records don't belong in the math." if flags_ctx else "") +
                    "".join(f" {s_['label']}: {s_['text']}" for s_ in story) +
                    (f" Stance: {stance['text'].capitalize()}, a read on the numbers, not advice." if stance else "") +
                    f" Source: 130point, pulled {fmt_date(f.get('pulled') or as_of)}. {SITE}"),
            alt=f"The File on the Astronaut Time board: {headline or f['title']}, with each card's clean move and how many records were kept out.")

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
            c_stance, c_story = stance_of(card), story_of(card)
            self.page("file-card.html", f"file-{day}-{cid}", {
                "kicker": kicker, "tag": tag, "name": card["name"], "tier": card["tier"], "set": set_line,
                "note": (row or {}).get("note"), "big": pct(card.get("change_pct")), "big_class": "up" if up else "down",
                "beside_1": f"{month_name(k0)} to {month_name(k1)},",
                "beside_2": "clean median.",
                # With a stance or story lines the chart gives up some height so they fit above the footer.
                "chart": sales_chart(card, H=330 if c_story else 390 if c_stance else 430), "legend": legend, "take": card.get("summary", ""),
                "stance": c_stance, "story": c_story, "frame_class": "storied" if c_story else "",
            }, caption=(f"{card['name']} {card['tier']}: {pct(card.get('change_pct'))} on the clean median, "
                        f"{month_name(k0)} to {month_name(k1)} ({money(card['monthly_clean'][k0])} to "
                        f"{money(card['monthly_clean'][k1])}). {card.get('summary', '')} " +
                        "".join(f"{s_['label']}: {s_['text']} " for s_ in c_story) +
                        (f"Stance: {c_stance['text'].capitalize()}, a read on the numbers, not advice. " if c_stance else "") +
                        f"Every dot is a sold record; the flagged ones are marked. Source: 130point, pulled {fmt_date(f.get('pulled') or as_of)}. {SITE}"),
                alt=f"{card['name']} {card['tier']}, {pct(card.get('change_pct'))} on the clean monthly median from {month_name(k0)} to {month_name(k1)}, with every sold record plotted and the flagged ones marked.")

    # --- a market File: the cover only. Its rows are TCGplayer moves, so there are no card files and no per-card images. ---
    def build_file_market(self, f, day, kicker, stance, slot, headline, dek):
        rows = market_rows(f)
        if not rows:
            print("file.json: a market File with no rows, nothing to render")
            return
        span = date_span([(r.get("last") or {}).get("date") for r in rows], year=False)
        source = str(f.get("source") or "TCGplayer market prices via tcgcsv.com").strip()
        shown = rows[:MARKET_ROWS]
        # Bars from zero on one scale: the biggest move fills the track, a drop runs left of zero.
        lo = min(0.0, min(r["change_pct"] for r in shown))
        span_pct = (max(0.0, max(r["change_pct"] for r in shown)) - lo) or 1.0
        bars, present = [], []
        for r in shown:
            v = r["change_pct"]
            text, chip = label_info(r["label"])[:2] if r.get("label") else ("", "")
            if r.get("label") and r["label"] not in present:
                present.append(r["label"])
            bars.append({"name": r["name"], "set": r.get("set", ""), "pct": pct(v, 1), "pct_class": "up" if v >= 0 else "down",
                         "price": money((r.get("last") or {}).get("price")), "chip": chip, "label_text": text,
                         "left": f"{(min(v, 0.0) - lo) / span_pct * 100:.2f}", "width": f"{max(abs(v) / span_pct * 100, 0.6):.2f}"})
        fl = f.get("flags") or {}
        head = fl.get("headline") or {}
        flags_ctx = None
        if head.get("value") is not None:
            flags_ctx = {"value": head["value"], "of": head.get("of"), "text": sentence(fl.get("stat") or head.get("label"))}
        hero_title, hero_value = market_hero(f, rows)
        more = f"The first {len(shown)} are here; all {len(rows)} are on the board." if len(rows) > len(shown) else ""
        meanings = {k: MOVER_MEANINGS.get(k) or (label_info(k)[4][:1].lower() + label_info(k)[4][1:]) for k in present}
        legend = " ".join(f"{label_info(k)[0]}: {meanings[k]}" for k in present if meanings[k])
        title = headline or str(f.get("title") or "")
        self.page("file-market-cover.html", f"file-{day}-cover", {
            "kicker": kicker, "tag": f"TCGplayer · {span}" if span else "TCGplayer", "file_title": title, "lede": dek,
            "rows": bars, "more": more, "flags": flags_ctx, "slot": slot, "stance": stance, "frame_class": "market",
        }, caption=(f"The File, {fmt_date(day)}{f' ({slot})' if slot else ''}: {sentence(title)} " +
                    (f"{dek} " if dek else "") +
                    " ".join(f"{r['name']}" + (f" ({r['set']})" if r.get("set") else "") + ": " +
                             (f"{money(r['prev']['price'])} on {fmt_date(r['prev']['date'])} to " if (r.get("prev") or {}).get("price") is not None and (r.get("prev") or {}).get("date") else "") +
                             f"{money((r.get('last') or {}).get('price'))}" + (f" on {fmt_date(r['last']['date'])}" if (r.get("last") or {}).get("date") else "") +
                             f", {pct(r['change_pct'], 1)}" + (f", {label_info(r['label'])[0].lower()}." if r.get("label") else ".") for r in rows) +
                    (f" {head['value']} of {head.get('of')} {head.get('label', '')}." if flags_ctx else "") +
                    (f" {legend}" if legend else "") +
                    (f" Stance: {stance['text'].capitalize()}, a read on the numbers, not advice." if stance else "") +
                    f" Source: {source}. {SITE}"),
            alt=(f"The File on the Astronaut Time board: {sentence(title)} {hero_title}: {hero_value}. "
                 f"{count_word(len(shown))} one-day TCGplayer moves as bars, each with its change, price and label" +
                 (f", and the flags tally, {head['value']} of {head.get('of')}." if flags_ctx else ".")))

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
                "eyebrow": f.get("title", "The File"),
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

    # --- what's moving: the TCGplayer movers, for the Thursday market post and the weekly video's raw material ---
    def build_moving(self):
        mv = load("movers.json") or {}
        items = [m for m in (mv.get("items") or []) if m and m.get("name")]
        window = (items[0].get("window_label") if items else None) or "7d"
        if not items:  # no 7-day movers yet: since yesterday stands in, said as such
            items = [m for m in (mv.get("one_day") or []) if m and m.get("name")]
            window = "1d"
        if not items:
            why = "no 7-day movers and nothing since yesterday" if "one_day" in mv else "no 7-day movers, and no one_day list in the file yet"
            print(f"movers.json: {why}, so no What's moving image")
            return
        as_of = mv.get("as_of") or items[0].get("observed")
        if not as_of:
            print("movers.json: no as_of date, so no What's moving image")
            return
        year, week, _ = parse_date(as_of).isocalendar()
        days = re.fullmatch(r"(\d+)d", str(window))
        when = "since yesterday" if window == "1d" else f"in the last {days.group(1)} days" if days else "lately"
        n, shown = len(items), items[:MOVING_ROWS]
        rule = MOVER_RULES.get(window)
        if rule:
            headline = f"{count_word(n)} card{'s' if n != 1 else ''} moved {rule[1]}% or more {when}."
            lede = f"Pokémon cards worth ${rule[0]} or more on TCGplayer. Each label says what the checked sales show."
        else:
            headline = f"The biggest TCGplayer moves {when}."
            lede = "Pokémon cards on TCGplayer. Each label says what the checked sales show."
        if n > len(shown):
            lede += f" The {len(shown)} biggest are here; all {n} are on the board."
        rows, present = [], []
        for m in shown:
            text, chip, _, _, _ = label_info(m.get("label"))
            if m.get("label") and m["label"] not in present:
                present.append(m["label"])
            chg = m.get("change_pct")
            rows.append({"name": m["name"], "line2": " · ".join(str(x) for x in (m.get("set"), m.get("number")) if x),
                         "price": money((m.get("last") or {}).get("price")), "pct": pct(chg, 1),
                         "pct_class": "" if chg is None else ("up" if chg >= 0 else "down"),
                         "chip": chip, "label_text": text, "has_label": bool(m.get("label"))})
        meanings = {k: MOVER_MEANINGS.get(k) or (label_info(k)[4][:1].lower() + label_info(k)[4][1:]) for k in present}
        legend = " ".join(f"{label_info(k)[0]}: {meanings[k]}" for k in present if meanings[k])
        # The image says what Unconfirmed means; the caption carries every label's meaning, the board explains them all.
        source = items[0].get("source") or "TCGplayer market prices via tcgcsv.com"
        foot = f"{source}, as of {fmt_date_year(as_of)}."
        if "UNCONFIRMED" in present:
            foot += f" Unconfirmed: {MOVER_MEANINGS['UNCONFIRMED']}"
        self.page("moving.html", f"moving-{year}-W{week:02d}", {
            "kicker": f"What's moving · {fmt_date(as_of)}", "tag": f"TCGplayer · {fmt_date(as_of)}",
            "eyebrow": f"TCGplayer · {'since yesterday' if window == '1d' else 'last ' + (days.group(1) + ' days' if days else str(window))}",
            "headline": headline, "lede": lede, "rows": rows, "dense": len(rows) > 5, "foot": foot,
        }, caption=(f"What's moving on TCGplayer, as of {fmt_date_year(as_of)}. {headline} " +
                    " ".join(f"{r['name']}" + (f" ({r['line2']})" if r["line2"] else "") + f": {r['price']}, {r['pct']}" +
                             (f", {r['label_text'].lower()}." if r["has_label"] else ".") for r in rows) +
                    (f" {legend}" if legend else "") + f" Source: {source}, as of {fmt_date_year(as_of)}. {SITE}"),
            alt=f"What's moving: the {len(rows)} biggest TCGplayer moves {when}, each with its market price, its change and the label for what checked sales show.")

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
    def screenshot(self, changed_only: bool = False):
        from playwright.sync_api import sync_playwright
        problems = []
        hashes_path = self.out / ".hashes.json"
        old_hashes = {}
        if hashes_path.exists():
            try:
                old_hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
            except ValueError:
                old_hashes = {}
        todo = [pg for pg in self.pages
                if not (changed_only and pg["png"].exists() and old_hashes.get(pg["name"]) == pg["hash"])]
        skipped = len(self.pages) - len(todo)
        if skipped:
            print(f"{skipped} unchanged image{'s' if skipped != 1 else ''} kept as is")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": POST_W, "height": POST_H}, device_scale_factor=self.scale)
            page = ctx.new_page()
            for pg in todo:
                pg["png"].parent.mkdir(parents=True, exist_ok=True)
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
        # Remember every rendered page's hash (unchanged pages keep theirs), so --changed-only can skip them next time.
        new_hashes = {k: v for k, v in old_hashes.items() if (self.out / f"{k}.png").exists()}
        new_hashes.update({pg["name"]: pg["hash"] for pg in self.pages})
        hashes_path.write_text(json.dumps(dict(sorted(new_hashes.items())), indent=1) + "\n", encoding="utf-8")
        return problems

    def write_captions(self):
        # Dated by the data, not the clock, so a re-render of the same data writes the same file.
        stamp = str((load("meta.json") or {}).get("generated_at") or (load("file.json") or {}).get("as_of") or dt.date.today())[:10]
        lines = [f"# Captions, board data of {stamp}", "",
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
    ap.add_argument("--only", default="file,flags,calls,moving,og,site", help="comma list of file,flags,calls,moving,og,site")
    ap.add_argument("--out", default=str(SHARE / "out"))
    ap.add_argument("--scale", type=int, default=1, help="device scale factor: 2 gives 2160x2700")
    ap.add_argument("--html-only", action="store_true", help="write the HTML, skip the screenshots")
    ap.add_argument("--changed-only", action="store_true",
                    help="skip the screenshot of any image whose filled HTML is the same as last time (what the nightly workflow uses)")
    args = ap.parse_args()

    kit = Kit(Path(args.out), args.scale)
    wanted = {w.strip() for w in args.only.split(",")}
    if "file" in wanted:
        kit.build_file()
    if "flags" in wanted:
        kit.build_flags()
    if "calls" in wanted:
        kit.build_calls()
    if "moving" in wanted:
        kit.build_moving()
    if "og" in wanted:
        kit.build_og()
    if "site" in wanted:
        kit.build_site()
    kit.write_captions()
    print(f"{len(kit.pages)} pages filled in {kit.html_dir.relative_to(ROOT)}")
    # Only the current set lives in out/: renders of the kinds being rendered whose name isn't in this set go
    # (a call that was withdrawn, the last File). Git history keeps them.
    prefixes = {"file": ("file-",), "flags": ("flags-", "flag-"), "calls": ("calls-", "call-"), "moving": ("moving-",),
                "og": ("og-",), "site": ("site/tile-",)}
    keep = {pg["png"].resolve() for pg in kit.pages} | {pg["html"].resolve() for pg in kit.pages}
    for kind in wanted:
        for pre in prefixes.get(kind, ()):
            for old in list(kit.out.glob(f"{pre}*.png")) + list(kit.html_dir.glob(f"{pre}*.html")):
                if old.resolve() not in keep:
                    old.unlink()
                    print(f"removed {old.relative_to(ROOT)} (no longer in the set)")
    if args.html_only:
        return
    problems = kit.screenshot(changed_only=args.changed_only)
    if "og" in wanted:
        kit.place_og()
    if "site" in wanted:
        kit.place_site()
    else:  # a single kind still refreshes its own stable copy
        kit.place_latest(wanted)
    if problems:
        print("\nLook at these before posting:")
        for pr in problems:
            print("  " + pr)
        sys.exit(2)
    print("\nclean: nothing overlaps or runs off an edge")


if __name__ == "__main__":
    main()
