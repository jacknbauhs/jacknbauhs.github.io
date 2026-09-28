# Share kit

Turns the board's JSON into ready-to-post images. Same data the board reads, same look, nothing typed in by hand. Change `data/*.json`, run it again, post.

## What it makes (`share/out/`)

| File | What it is |
|---|---|
| `file-<date>-cover.png` | This week's file: every card in it, its clean move, and the flags headline. Slide 1 of a carousel. |
| `file-<date>-<card>.png` | One per card: the sales chart (every sold record, the clean monthly median, flagged sales marked) and the summary. |
| `flags-<date>-cover.png` | "What got caught": every flagged record on one image with its label and reason. |
| `flag-<sale date>-<card>-<label>.png` | One per flagged record: the price, the label and what it means, the reason, and the card's chart with that record ringed. Nightly-feed flags render too once `flags.json` has items. |
| `calls-<date>-cover.png` | Every call on the record, on one image. The "check me Oct 30" post. |
| `call-<id>-<dated>.png` | One per call: the call, start, rule, and latest, or the verdict once it's hit or miss. |
| `og-board.png` | The 1200x630 link preview. Copied to `assets/og.png`; the pages point at it, so links to the board unfurl on X, Facebook and Discord. |
| `captions.md` | A caption and alt text for every image. Plain facts, the source, the board link. |
| `html/` | The filled templates. Open one in a browser to tweak the look, then re-render. Not committed. |

All posts are 1080x1350 (IG 4:5, also fine on X, Facebook and Threads). `--scale 2` gives 2160x2700.

## Run it

Once: `pip install jinja2 playwright` then `playwright install chromium`.

```
python share/render.py                # everything
python share/render.py --only calls   # file, flags, calls or og
python share/render.py --html-only    # fill the templates, skip the screenshots
python share/render.py --scale 2
```

Each run replaces the previous set of the kinds it renders (git history keeps the old ones). It ends with a check: anything that overlaps the footer or runs off an edge is listed, and the exit code is 2. Look at those before posting.

After a run, commit `share/out`, `assets/og.png` and the three HTML files (the run stamps `assets/og.png?v=<date>` into them so X, Facebook and Discord fetch the new preview instead of a cached one). Pull first: the nightly job also pushes to this repo.

## The look

`templates/share.css` holds the tokens (same values as `assets/board.css`) and every size. `templates/base.html` is the frame: header with the wordmark and a kicker, body, footer with the URL and a tag. Each kind extends it. The starfield is drawn by `sky()` in `render.py` with a fixed seed, so it's the same on every run.

Fonts are bundled in `fonts/` (Geist, Geist Mono, Unbounded; SIL Open Font License, licenses alongside), so a render never needs the network.

## What the data has to look like

- `file.json`: `title`, `as_of`, `pulled`, `cards[]` (ids), `rows[]` (`id`, `name`, `set`, `tier`, `last`, `clean_median`, `change_pct`, `window_label`, `flagged`, `sales`, `note`), `foot`, `flags` (`headline {value, of, label}`, `text`, `stat`, `items[]` of `card`, `date`, `price`, `label`, `why`).
- `cards/<id>.json`: `name`, `set`, `number`, `tier`, `event`, `window`, `monthly_clean`, `change_label`, `change_pct`, `summary`, `sales[]`. The compared months come from `change_label` ("June to September, clean median"), so keep that line honest.
- `calls.json`: `items[]` of `id`, `dated`, `check_date`, `status` (`open`, `hit`, `miss`; `withdrawn` never renders), `on_record`, `text`, `start`, `method`, `latest`, and once checked `verdict_note` (and `checked`, the date).
- `flags.json` (nightly): `items[]` of `name`, `set`, `claimed_change_pct`, `label`, `why`; rendered only when `pending` is off.
- `meta.json`: `generated_at`, for the "Updated" date on the link preview.

Sale Integrity labels and their one-line meanings are copied from `assets/board.js`; keep the two in step.

## Not here yet

Vertical clips (1080x1920) through the animation pipeline, and a "what's moving" image from `movers.json` once the feed has a week of prices.
