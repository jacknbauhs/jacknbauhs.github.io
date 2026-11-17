#!/usr/bin/env python3
"""Card pages: one static page per card in data/market/index.json, the search page and the sitemap.

Mission Control writes the data every night (data/market/index.json and data/market/sets/<set>.json, its
board_publish job, behind BOARD_MARKET_ENABLED). This turns the index into pages a search engine can read and a
link preview can show:

  pokemon/<slug>.html   one per card: name, set, number and printing in the title and preview; the price, the
                        changes and the history chart are drawn by assets/market.js from the data files, so a
                        page's HTML changes only when the card's name or set does
  pokemon/index.html    every card as a plain link (what a crawler follows), searched and sorted by assets/market.js
  sitemap.xml           the board's pages and every card page
  the Cards link        added after Market in the nav of index.html, card.html, calls.html and how.html, the first
                        time there are pages to link to

The header, sky and footer are read from card.html, so the card pages keep the board's chrome when it changes.
A page is never deleted: a card that leaves the index keeps its page, which then says so.

Run:  python pages/build.py            (writes only what changed; prints a count)
      python pages/build.py --check    (exit 1 when something would change; writes nothing)
.github/workflows/render.yml runs it after every data push.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://board.jacknbauhs.com"
INDEX = ROOT / "data" / "market" / "index.json"
OUT = ROOT / "pokemon"
OG = f"{SITE}/assets/og.png"
STATIC_PAGES = ("", "how.html", "calls.html", "pokemon/")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,160}$")
ASSET_V = "2026-11-17"


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def chrome() -> dict:
    """The sky, the site header and the footer from card.html, with every relative link made absolute."""
    src = (ROOT / "card.html").read_text(encoding="utf-8")

    def block(pattern):
        m = re.search(pattern, src, re.S)
        if not m:
            raise SystemExit(f"card.html: couldn't find {pattern!r}")
        return m.group(0)

    parts = {"sky": block(r'<div class="sky".*?</svg>\s*</div>'),
             "header": block(r'<header class="site-header">.*?</header>'),
             "footer": block(r'<footer class="site-footer">.*?</footer>')}
    for k, v in parts.items():
        v = re.sub(r'href="\./"', 'href="/"', v)
        v = re.sub(r'href="\./#', 'href="/#', v)
        v = re.sub(r'href="(assets/|how\.html|calls\.html|card\.html)', r'href="/\1', v)
        v = v.replace(' aria-current="page"', "")
        parts[k] = v
    return parts


MC_BAR = """<div class="mc-bar">
  <div class="mc-brand">
    <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="8" fill="none" stroke="#C4B5FD" stroke-width="2"/><ellipse cx="16" cy="16" rx="14.5" ry="5" fill="none" stroke="#8B5CF6" stroke-width="1.6" transform="rotate(-20 16 16)"/></svg>
    <strong>MISSION CONTROL</strong><span class="muted" style="font-size:13px">by Astronaut Time</span>
  </div>
  <nav class="mc-nav" aria-label="Mission Control">
    <a href="/#today">Today</a><a href="/#moving">Market</a><a href="/pokemon/" class="is-active">Cards</a><a href="/#flags">Flags</a><a href="/#rip-ev">Rip EV</a><a href="/#calls">Calls</a><a href="/#drops">Drops</a>
  </nav>
  <span class="status" id="status"></span>
</div>"""


def head(title: str, description: str, url: str, extra: str = "") -> str:
    t, d = esc(title), esc(description)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Astronaut Time">
<meta property="og:image" content="{OG}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{OG}">
<meta name="theme-color" content="#0B0A14">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&family=Unbounded:wght@600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/board.css?v=2026-11-15b">
<link rel="stylesheet" href="/assets/market.css?v={ASSET_V}">
{extra}</head>"""


def display_name(c: dict) -> str:
    """The card's name without the number tcgcsv repeats in it (Mission Control's `title`)."""
    return str(c.get("title") or c.get("name") or "Card")


def card_page(c: dict, ch: dict) -> str:
    name, num, set_ = display_name(c), c.get("number") or "", c.get("set") or ""
    printing = c.get("printing") or ""
    label = " ".join(x for x in (name, num) if x)
    title = f"{label} {printing + ' ' if printing else ''}price history · {set_} · Mission Control"
    desc = (f"{label}{' (' + printing + ')' if printing else ''} from {set_}: TCGplayer market price, "
            f"7- and 30-day change and every stored price since Mission Control started tracking it.")
    url = f"{SITE}/pokemon/{c['slug']}.html"
    ld = {"@context": "https://schema.org", "@type": "Product", "name": f"{label} {set_}".strip(),
          "category": "Pokémon trading card", "url": url}
    if c.get("image"):
        ld["image"] = c["image"]
    extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'
    meta = " · ".join(esc(x) for x in (set_, num, c.get("rarity"), printing) if x)
    img = (f'<img class="mk-art" src="{esc(c["image"])}" alt="{esc(label)} card" loading="lazy" '
           f'width="245" height="342" referrerpolicy="no-referrer" onerror="this.remove()">' if c.get("image") else "")
    return f"""{head(title, desc, url, extra)}
<body data-page="market-card" data-slug="{esc(c['slug'])}" data-set="{esc(c.get('set_slug'))}">
{ch['sky']}

{ch['header']}

{MC_BAR}

<main id="main">
  <div class="crumbs"><a href="/pokemon/">&larr; Card prices</a><span class="muted">{esc(set_)}</span></div>
  <div class="mk-top">
    {img}
    <div class="mk-head">
      <div class="card-title"><div><h1>{esc(name)} <span class="muted">{esc(num)}</span></h1><div class="card-meta">{meta}</div></div></div>
      <div class="kpis mk-kpis" id="kpis"></div>
    </div>
  </div>
  <p id="load-error" class="muted" hidden>This card's prices couldn't load. <a href="/pokemon/">Back to card prices</a>.</p>
  <figure class="card chart-card mk-chart-card">
    <div class="kicker">TCGplayer market price</div>
    <div id="mk-chart" class="mk-chart"></div>
  </figure>
  <div class="card table-card mk-facts">
    <div class="table-foot" id="mk-source"></div>
    <div class="table-foot"><a id="mk-tcg" href="https://www.tcgplayer.com/product/{esc(c.get('id'))}" rel="nofollow noopener" target="_blank">See it on TCGplayer →</a> · <a href="/how.html">How we price →</a></div>
  </div>
  <section class="block mk-related" aria-labelledby="related-h">
    <div class="block-head"><div><div class="kicker">Same set</div><h2 id="related-h">More from {esc(set_)}</h2></div></div>
    <ul class="mk-links" id="mk-related"></ul>
  </section>
</main>

{ch['footer']}
<script src="/assets/market.js?v={ASSET_V}"></script>
</body>
</html>
"""


def search_page(cards: list, ch: dict) -> str:
    url = f"{SITE}/pokemon/"
    desc = ("Search Pokémon card prices: TCGplayer market price, 7- and 30-day change and release date for every "
            "card Mission Control tracks, each with its full price history.")
    links = "\n".join(
        f'      <li><a href="/pokemon/{esc(c["slug"])}.html">{esc(display_name(c))} {esc(c.get("number") or "")}'
        f'{" · " + esc(c.get("printing")) if c.get("printing") else ""}</a> <span class="muted">{esc(c.get("set"))}</span></li>'
        for c in cards)
    return f"""{head("Pokémon card prices · Mission Control · Astronaut Time", desc, url)}
<body data-page="market-search">
{ch['sky']}

{ch['header']}

{MC_BAR}

<main id="main">
  <section class="block mk-search-block" aria-labelledby="search-h">
    <div class="block-head"><div><div class="kicker">Card prices</div><h1 id="search-h" class="mk-h1">Every card we track</h1>
      <p>TCGplayer's market price for each card, its 7- and 30-day change and its full stored history. Tick up to four to compare. <span id="mk-count"></span></p></div></div>
    <div class="mk-controls">
      <label class="mk-search"><span class="sr-only">Search</span><input id="mk-q" type="search" placeholder="Search a card, set or number" autocomplete="off"></label>
      <label class="mk-sort">Sort <select id="mk-sort">
        <option value="price">Price</option><option value="ch7">7-day change</option><option value="ch30">30-day change</option>
        <option value="released">Release date</option><option value="name">Name</option></select></label>
    </div>
    <div id="mk-compare" class="card mk-compare" hidden></div>
    <div class="card table-card"><table class="data mk-table">
      <thead><tr><th scope="col"><span class="sr-only">Compare</span></th><th scope="col">Card</th><th scope="col">Set</th><th scope="col">Released</th><th scope="col" class="num">Price</th><th scope="col" class="num">7d</th><th scope="col" class="num">30d</th></tr></thead>
      <tbody id="mk-body"></tbody></table>
      <div class="table-foot" id="mk-source"></div>
    </div>
    <noscript><ul class="mk-links">
{links}
    </ul></noscript>
  </section>
</main>

{ch['footer']}
<script src="/assets/market.js?v={ASSET_V}"></script>
</body>
</html>
"""


def sitemap(cards: list) -> str:
    urls = [f"  <url><loc>{SITE}/{p}</loc></url>" for p in STATIC_PAGES]
    for c in cards:
        lm = f"<lastmod>{esc(c['price_date'])}</lastmod>" if c.get("price_date") else ""
        urls.append(f"  <url><loc>{SITE}/pokemon/{esc(c['slug'])}.html</loc>{lm}</url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")


NAV_PAGES = ("index.html", "card.html", "calls.html", "how.html")
NAV_LINK = '<a href="/pokemon/">Cards</a>'
_MARKET_LINK = re.compile(r'(<a href="(?:\./)?#moving"[^>]*>Market</a>)')


def with_nav(text: str) -> str:
    """The board page with a Cards link after Market in its Mission Control nav (once; unchanged when it has one)."""
    if NAV_LINK in text:
        return text
    return _MARKET_LINK.sub(lambda m: m.group(1) + NAV_LINK, text, count=1)


def plan() -> dict:
    """{path: text} for every file this would write."""
    if not INDEX.exists():
        return {}
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    cards = [c for c in idx.get("cards") or [] if SLUG_RE.match(str(c.get("slug") or ""))]
    ch = chrome()
    out = {OUT / f"{c['slug']}.html": card_page(c, ch) for c in cards}
    out[OUT / "index.html"] = search_page(cards, ch)
    out[ROOT / "sitemap.xml"] = sitemap(cards)
    for name in NAV_PAGES:      # the Cards link goes up with the first pages, never before
        p = ROOT / name
        if p.exists():
            out[p] = with_nav(p.read_text(encoding="utf-8"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when a page would change; write nothing")
    args = ap.parse_args(argv)
    files = plan()
    if not files:
        print("no data/market/index.json yet: nothing to build")
        return 0
    changed = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    if args.check:
        print(f"{len(changed)} of {len(files)} files would change")
        return 1 if changed else 0
    for p in changed:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(files[p], encoding="utf-8")
    cards = sum(1 for p in files if p.parent == OUT and p.name != "index.html")
    print(f"card pages: {cards} cards, {len(changed)} files written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
