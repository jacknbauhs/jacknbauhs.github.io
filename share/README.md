# Share kit

Turns the board's JSON into ready-to-post images. Same data the board reads, same look, nothing typed in by hand. Change `data/*.json`, run it again, post.

## What it makes (`share/out/`)

| File | What it is |
|---|---|
| `file-<date>-cover.png` | The File (Tue / Thu / Sat): every card in it, its clean move, and the flags headline, plus the headline, dek, stance and labeled lines when `file.json` has them. Slide 1 of a carousel. |
| `file-<date>-<card>.png` | One per card: the sales chart (every sold record, the clean monthly median, flagged sales marked) and the summary, plus the card's stance and labeled lines when its file has them. |
| `flags-<date>-cover.png` | "What got caught": every flagged record on one image with its label and reason. |
| `flag-<sale date>-<card>-<label>.png` | One per flagged record: the price, the label and what it means, the reason, and the card's chart with that record ringed. Nightly-feed flags render too once `flags.json` has items. |
| `calls-<date>-cover.png` | Every call on the record, on one image. The "check me Oct 30" post. |
| `call-<id>-<dated>.png` | One per call: the call, start, rule, and latest, or the verdict once it's hit or miss. |
| `moving-<YYYY>-W<ww>.png` | "What's moving": up to eight TCGplayer movers from `movers.json` (name, set, price, change, label; Unconfirmed says no checked sales speak to the move). The 7-day list first; when it's empty, the since-yesterday list, said as such, with its rule in the footnote (a move with no checked sales is in it only up to 40% and when TCGplayer's lowest listing moved the same way, so big unbacked jumps are left out); when both are empty, nothing (the run says why). Named by the ISO week of the data, so the week's image is replaced as the nightly data moves. For the Thursday market post and the weekly video. |
| `og-board.png` | The 1200x630 link preview. Copied to `assets/og.png`; the pages point at it, so links to the board unfurl on X, Facebook and Discord. |
| `site/tile-file.png`, `site/tile-flags.png`, `site/tile-calls.png`, `site/tile-drop.png` | Four 1080x1080 tiles, one number each, at names that never change. Image blocks on jacknbauhs.com point at them and show the newest render. |
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

`templates/share.css` holds the tokens (same values as `assets/board.css`) and every size. `templates/base.html` is the frame: header with the wordmark and a kicker, body, footer with the URL and a tag. Each kind extends it. The starfield is drawn by `sky()` in `render.py` with a fixed seed, so it's the same on every run.

Fonts are bundled in `fonts/` (Geist, Geist Mono, Unbounded; SIL Open Font License, licenses alongside), so a render never needs the network.

## What the data has to look like

- `file.json` (The File, kept by hand; git history is its archive): `title`, `as_of`, `pulled`, `cards[]` (ids), `rows[]` (`id`, `name`, `set`, `tier`, `last`, `clean_median`, `change_pct`, `window_label`, `flagged`, `sales`, `note`), `foot`, `flags` (`headline {value, of, label}`, `text`, `stat`, `items[]` of `card`, `date`, `price`, `label`, `why`).
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
- `movers.json` (nightly): `as_of`, `items[]` (the 7-day movers) and `one_day[]` (since yesterday), each entry `id`, `name`, `set`, `number`, `tier`, `last {price, date}`, `change_pct`, `window_label` (`7d`, `1d`), `clean_change_pct`, `label`, `label_note`, `source`, `observed`. The image's headline quotes the lists' floors ($20 and 5% for 7 days, $20 and 3% since yesterday) from `MOVER_RULES` in `render.py`, and the one-day footnote its 40% cap on Unconfirmed moves from `DAY_UNCONFIRMED_MAX_PCT`; keep them in step with Mission Control's `config/board.py` (the board's Since-yesterday card reads the same floors and cap from `ONE_DAY` in `assets/board.js`).
- `meta.json`: `generated_at`, for the "Updated" date on the link preview.

Sale Integrity labels and their one-line meanings are copied from `assets/board.js`; keep the two in step.

## Not here yet

Vertical clips (1080x1920) through the animation pipeline.
