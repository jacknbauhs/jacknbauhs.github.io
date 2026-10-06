# Share kit

Turns the board's JSON into ready-to-post images. Same data the board reads, same look, nothing typed in by hand. Change `data/*.json`, run it again, post.

## What it makes (`share/out/`)

| File | What it is |
|---|---|
| `file-<date>-cover.png` | The File (Tue / Thu / Sat): every card in it, its clean move, and the flags headline, plus the headline, dek, stance and labeled lines when `file.json` has them. A market File (`"kind": "market"`) shows its first six TCGplayer moves as bars on one scale instead (name, set, change, price, label) under the headline and dek, and the flags tally. A build File (`"kind": "build"`) shows each card's share of Mission Control's card model with inputs, before and after, as one bar on a 0 to 100% scale with the minimum dashed, its own read (its PSA 10 population) under it, what every card shares said once, the story lines, and "No score shown"; never a score, tier or stance. Its footer tag is the population's source and the day it was read, in full (`PSA population report via Pikawiz · read Oct 6, 2026`), when every row shares them. Slide 1 of a carousel. |
| `file-<date>-<card>.png` | One per card: the sales chart (every sold record, the clean monthly median, flagged sales marked) and the summary, plus the card's stance and labeled lines when its file has them. A card File only: market and build Files have no card files. |
| `flags-<date>-cover.png` | "What got caught": every flagged record on one image with its label and reason. For a market File, "What we couldn't confirm" instead (the moves may be real; nothing was thrown out): every flagged move on one line each (day, card, change, the market price after it), up to 15, with one shared label said once under the list. A build File has no flags, so no flags cover; `site/latest-flags.png` keeps the last one (dated on its face) rather than leave jacknbauhs.com a broken image, and `site/squarespace.md` still lists it. |
| `flag-<sale date>-<card>-<label>.png` | One per flagged record: the price, the label and what it means, the reason, and the card's chart with that record ringed. Nightly-feed flags render too once `flags.json` has items. None for a market File's flags: they are moves, not sold records. |
| `calls-<date>-cover.png` | Every call on the record, on one image. The "check me Oct 30" post. |
| `call-<id>-<dated>.png` | One per call: the call, start, rule, and latest, or the verdict once it's hit or miss. |
| `moving-<YYYY>-W<ww>.png` | "What's moving": up to eight TCGplayer movers from `movers.json` (name, set, price, change, label; Unconfirmed says no checked sales speak to the move). The 7-day list first; when it's empty, the since-yesterday list, said as such. Either way the footnote says the list's rule (a move with no checked sales is in it only up to 60% for the week or 40% for the day, and when TCGplayer's lowest listing moved the same way, so big unbacked jumps are left out); when both are empty, nothing (the run says why). Named by the ISO week of the data, so the week's image is replaced as the nightly data moves. For the Thursday market post and the weekly video. |
| `og-board.png` | The 1200x630 link preview. Copied to `assets/og.png`; the pages point at it, so links to the board unfurl on X, Facebook and Discord. Beside a market File's figure, its headline reads "every move labeled by the sales behind it" instead of "with the fake sales taken out". A build File's figure is its `hero.value` ("0 → 3") with `hero.title` and `hero.note` under it, beside "every number with its source and date", since it has no sales behind it. |
| `site/tile-file.png`, `site/tile-flags.png`, `site/tile-calls.png`, `site/tile-drop.png` | Four 1080x1080 tiles, one number each, at names that never change. Image blocks on jacknbauhs.com point at them and show the newest render. A market File's two tiles are dated by the days their moves are from (`TCGplayer · Oct 2 to Oct 4`), and its flags tile reads "What we couldn't confirm". A build File's file tile shows its `hero.value`, tagged `Mission Control · <as_of>`, with its first `stats` figure under it; its flags tile shows the nightly feed when it has a week, and otherwise says the File is about the card model, so it has no flags (not the "flags start with the first checked sales" placeholder). |
| `site/latest-file.png`, `site/latest-flags.png`, `site/latest-calls.png`, `site/latest-moving.png` | The newest cover of each kind (and the newest What's moving image), at a stable name, for the same reason. |
| `site/squarespace.md` | Ready-to-paste Markdown (image, alt text, link to the board) for a Markdown block on jacknbauhs.com. |
| `.hashes.json` | A hash of each image's filled HTML, so `--changed-only` can skip images that would come out the same. Committed. |
| `captions.md` | A caption and alt text for every image. Plain facts, the source, the board link. |
| `html/` | The filled templates. Open one in a browser to tweak the look, then re-render. Not committed. |

All posts are 1080x1350 (IG 4:5, also fine on X, Facebook and Threads). `--scale 2` gives 2160x2700.

## It runs itself

`.github/workflows/render.yml` runs `render.py --changed-only` on GitHub after every push that touches `data/`, `share/templates/` or `render.py` (the nightly `board_publish` commit from Mission Control counts), and commits what changed: the images, `captions.md`, `.hashes.json`, `assets/og.png` and the `?v=` stamp in the three HTML pages. Unchanged images are left alone, so the repo only grows when the data moves. The Actions tab shows each run; "Run workflow" renders on demand. Pull before you commit anything: the nightly job and this workflow both push to `main`.

This is how jacknbauhs.com stays current without code: Squarespace can't run scripts on the Basic plan, but a Markdown block can show an image by URL, and `share/out/site/*.png` always hold the newest render. Paste `share/out/site/squarespace.md` into a Markdown block once; after that, the site follows the board.

## Run it by hand

Once: `pip install jinja2 playwright` then `playwright install chromium`.

```
python share/render.py                # everything
python share/render.py --only calls   # file, flags, calls, moving, og or site
python share/render.py --html-only    # fill the templates, skip the screenshots
python share/render.py --changed-only # only images whose filled HTML changed
python share/render.py --scale 2
```

Each run drops renders of the kinds it makes that are no longer in the set (a withdrawn call, last week's file; git history keeps the old ones). It ends with a check: anything that overlaps the footer or runs off an edge is listed, and the exit code is 2. Look at those before posting.

After a hand run, commit `share/out`, `assets/og.png` and the three HTML files (the run stamps `assets/og.png?v=<date>` into them so X, Facebook and Discord fetch the new preview instead of a cached one). Pull first: the nightly job and the workflow also push to this repo.

## The look

`templates/share.css` holds the tokens (same values as `assets/board.css`) and every size. `templates/base.html` is the frame: header with the wordmark and a kicker, body, footer with the URL and a tag. Each kind extends it. A template can add styles of its own in base.html's `style` block, as the build File's cover does, so a new kind changes no other image's filled HTML (and `--changed-only` re-renders nothing else). The starfield is drawn by `sky()` in `render.py` with a fixed seed, so it's the same on every run.

Fonts are bundled in `fonts/` (Geist, Geist Mono, Unbounded; SIL Open Font License, licenses alongside), so a render never needs the network.

## What the data has to look like

- `file.json` (The File, kept by hand; git history is its archive): `title`, `as_of`, `pulled`, `cards[]` (ids), `rows[]` (`id`, `name`, `set`, `tier`, `last`, `clean_median`, `change_pct`, `window_label`, `flagged`, `sales`, `note`), `foot`, `flags` (`headline {value, of, label}`, `text`, `stat`, `items[]` of `card`, `date`, `price`, `label`, `why`).
- A market File: `file.json` with `"kind": "market"`, for a story about TCGplayer price moves rather than one graded card's sales (no `featured`, no `cards`, no 130point). A `file.json` without `kind` is a card File and renders as it always has. On top of the story fields below:
  - `rows[]`: `id` (the TCGplayer product id), `name`, `set`, `tier` (like `Raw · TCGplayer market price`; optional, nothing shows it), `prev {price, date}` (the day before), `last {price, date}` (the next day), `change_pct`, `label` (a Sale Integrity label; `UNCONFIRMED` shows as such), `note`, `link` (`https://www.tcgplayer.com/product/<id>`; it opens in a new tab). The board's table: Card (name, set and note, linked), Day before, Next day, Change, Label. The board's hero: every row's change as a bar from zero, with the source and dates under it; the cover: the first six.
  - `hero {title, value, note}`, optional: the board's hero title, its big figure and the short line under it. Without it, the headline and the first row's change.
  - `stats[]` of `{value, label}`, optional, on either kind: the File's own stat tiles, in place of the per-row tiles. A flags tally already among them (`"15 of 30"`) isn't shown twice.
  - `flags` is the same block as a card File's; on a market File its `items[].price` is the market price after the move and `date` the day of the list, and the share kit says so instead of "sold".
  - `source`, `foot`, `as_of`, `pulled` as on a card File. Build the numbers from the board's own `movers.json` history (`git show <sha>:data/movers.json`), not by hand: the day before is `last.price / (1 + change_pct/100)`, so call it "the day before" in prose, since the feed compares against the newest stored price on or before that day.
- A build File: `file.json` with `"kind": "build"`, for a Sat build story about Mission Control itself: what its card model could read on a few cards, before and after a change. No `featured`, no `cards`, no sales, no prices, no `flags`, and no `stance`: a low-confidence read gets none, and a stance on named cards would be a read of them (the board and the share kit both ignore one if it is there). Never a score, tier or cap line, anywhere. A `file.json` without `kind` is still a card File. On top of the story fields below:
  - `model {name, min_coverage, before {version, note}, after {version, since}}`: the model's public name ("Mission Control's card model"), the share of its weight that needs inputs before it gives a read (0.5), and the two method versions, named as the model stores them (`moonshot-m1.0`, `moonshot-m1.1`).
  - `rows[]`, ordered by card number, never by anything the model said: `id`, `name`, `set`, `number`, `tier` (`PSA 10`), `note`, `pop {at_grade, higher, total, source, observed}` (a public population read, its source in plain words and its date; never a licensed source), `before {version, read, coverage, why}`, `after {version, read, coverage, confidence, reads[], not_read[]}`. `coverage` is a fraction; `confidence` is a word (`low`), never a percentage. `reads[]` says what the model used, labeling judgment as Jack's and proposed values as "a proposed value, Jack to confirm"; `not_read[]` what it couldn't, said as not read, never as zero. No `link`: these cards have no card page.
  - The board's hero: each card's before and after as bars on 0 to 100%, the minimum dashed. Its table: Card (with the population line), Before, After (with the reads), Not read yet. The "In The File" flags block hides.
  - `hero {title, value, note}`, `stats[]`, `source`, `foot`, `as_of`, `pulled` as on a market File. Quote the model's numbers only from a real run of each version (`agents.moonshot.assess` with no sales feed, so liquidity reads "not measured"), and re-run them if a table or `METHOD_VERSION` changes before the File goes up.
- `cards/<id>.json`: `name`, `set`, `number`, `tier`, `event`, `window`, `monthly_clean`, `change_label`, `change_pct`, `summary`, `sales[]`. The compared months come from `change_label` ("June to September, clean median"), so keep that line honest.
- The File's story fields, all optional; a File without them renders as it always has.
  - On `file.json`: `date` (YYYY-MM-DD, the day it is The File for; it names the images, and tells the board's "Next File" line that today's is up), `slot` (`Tue story`, `Thu market` or `Sat build`), `stance`, `headline` (takes the place of `title` on the cover), `dek` (one or two sentences under it), `why_now`, `risk`, `what_to_watch`.
  - On a card file: `stance`, `why_now`, `risk`, `what_to_watch`.
  - `stance` is a closed set: `STRONG WATCH`, `WATCH`, `NEUTRAL`, `CAUTION`, `PASS`. Any other value, and any other slot, is left off. A stance is a read on the numbers, not advice; the board says so wherever it shows one, and so do the captions.
  - Where they show: The File's block and the card page on the board ("Why now", "What could break it", "What we're watching"), and the cover and card images, which give up some room for them. Keep each line to one sentence, about 100 characters, or the end-of-run check flags the image.
  - The language rule holds for every one: never "buy", "will increase", "guaranteed", "safe", "can't lose", "sure thing" or a multiple.
  - A filled example (made up; Jack writes the real ones):

  ```json
  {
    "date": "2026-10-06",
    "slot": "Tue story",
    "stance": "WATCH",
    "headline": "The reprint didn't touch the graded Lugia.",
    "dek": "Crystal Lugia PSA 8 kept climbing after the 30th Celebration reprint hit shelves. The raw copies are where a reprint usually lands.",
    "why_now": "The reprint has been on shelves for three weeks, long enough for the first graded sales after it.",
    "risk": "A thin month: four or five sales in October could swing the clean median either way.",
    "what_to_watch": "October's clean median against September's $15,999, once there are at least three clean sales."
  }
  ```

  and on `cards/crystal-lugia-psa-8.json`, next to its other fields: `"stance": "WATCH", "why_now": "…", "risk": "…", "what_to_watch": "…"`.
- `calls.json`: `items[]` of `id`, `dated`, `check_date`, `status` (`open`, `hit`, `miss`; `withdrawn` never renders), `on_record`, `text`, `start`, `method`, `latest`, and once checked `verdict_note` (and `checked`, the date).
- `flags.json` (nightly): `items[]` of `name`, `set`, `claimed_change_pct`, `label`, `why`; rendered only when `pending` is off.
- `movers.json` (nightly): `as_of`, `items[]` (the 7-day movers) and `one_day[]` (since yesterday), each entry `id`, `name`, `set`, `number`, `tier`, `last {price, date}`, `change_pct`, `window_label` (`7d`, `1d`), `clean_change_pct`, `label`, `label_note`, `source`, `observed`. The image's headline counts the cards on the list (never the market: the list is capped and leaves out big unbacked jumps), its lede quotes the lists' floors ($20 and 5% for 7 days, $20 and 3% since yesterday) from `MOVER_RULES` in `render.py`, and the footnote its cap on Unconfirmed moves (60% for 7 days, 40% since yesterday) from `UNCONFIRMED_MAX_PCT`; keep them in step with Mission Control's `config/board.py` (the board reads the same floors and caps from `WEEK` and `ONE_DAY` in `assets/board.js`).
- `meta.json`: `generated_at`, for the "Updated" date on the link preview.

Sale Integrity labels and their one-line meanings are copied from `assets/board.js`; keep the two in step.

## Not here yet

Vertical clips (1080x1920) through the animation pipeline.
