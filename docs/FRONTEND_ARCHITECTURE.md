# AI 3D Daily — Frontend & Publishing Architecture

## Purpose

The homepage and historical daily reports are derived views of canonical Production Intelligence data. Daily content changes; identity, presentation contracts and publishing ownership must not drift with it.

## Canonical data

- `data/daily/YYYY-MM-DD.json` — source of truth for each day's Intelligence records.
- Every Intelligence record uses a stable `id`.
- Homepage and Daily Report cards carry the same `data-intel-id`.
- Full Analysis is authored once in canonical data and rendered into both views.
- Canonical Full Analysis blocks are `label + text`; renderers output semantic `<h4>label</h4><p>text</p>` pairs.

## Canonical visual evidence

Visual identity uses the same stable Intelligence ID. Do not identify images by article-title matching.

Each day's canonical JSON may contain a top-level `visual_evidence` map keyed by Intelligence ID. A visual record may define:

- `enabled`
- `source_url`
- `label`
- `confidence`
- `keywords`
- optional `reason` when disabled

`scripts/extract_visual_assets.py` reads only this canonical map, validates representative image candidates from the source page, and stores successful assets as `assets/visual/<data-intel-id>.jpg`.

`scripts/inject_visual_previews.py` reads `assets/visual/manifest.json` and injects a preview only into a card with the exact matching `data-intel-id`. Preview markup must carry the same ID and link back to the canonical source page.

The legacy `visual-assets.json` title-key manifest is retired and must not return.

## Homepage modules

- `index.html` — current homepage derived view. Keep readable and non-minified.
- `home.css` — foundation and structural layout only.
- `home-content.css` — dark visual theme, information-card content, analysis UI and visual-evidence presentation.
- `home-components.css` — Supplemental, Test Today, Archive and preference-vote components.
- `home.js` — details interaction and browser-local preference voting.
- `canonical-client.js` — shared runtime integrity renderer for canonical Full Analysis.
- `styles.css` — historical daily-report styles and shared base styles.
- `daily.css` / `daily.js` — shared historical report presentation and interaction.

Do not create an emergency stylesheet to patch a selector mismatch. Fix the owning module or renderer contract instead.

## Homepage semantic contract

The section order is fixed:

1. Hero / date / status counts
2. `.top-list > .top-item` — exactly five TOP 5 cards
3. `.more-grid > .more-card` — 6–12 Supplemental cards
4. `.test-section` — Today worth testing
5. `.history-list > a` — archive links

Desktop Supplemental layout is two columns. Mobile layout is one column.

## Single-publish-pipeline rule

`.github/workflows/intelligence-build.yml` is the only GitHub Actions workflow allowed to convert canonical data into derived Homepage / Daily HTML and commit current-day local visual assets.

The sequence is:

1. Resolve latest canonical date.
2. Bootstrap stable IDs only for legacy markup when needed.
3. Render canonical Full Analysis.
4. Extract canonical Visual Evidence.
5. Inject local previews by stable ID.
6. Run Intelligence, Visual, Homepage and Daily contracts.
7. Commit derived views and local visual assets.

Do not create a second workflow that also modifies `index.html` or current daily HTML. In particular, `.github/workflows/visual-assets.yml` is retired because parallel HTML writers create race conditions.

The scheduled daily task owns Intelligence decisions and canonical data. GitHub Actions only renders and enriches that canonical state; it must not invent, reorder or replace Intelligence records.

## Retired architecture

The following were removed and must not return:

- `today-more.json`
- `scripts/inject_today_more.py`
- `.github/workflows/today-more.yml`
- `home-layout-fixes.css`
- `visual-assets.json`
- `.github/workflows/visual-assets.yml`

Retired homepage selectors include:

- `.more-feed`, `.more-group`
- `.test-strip`
- `.archive-list`, `.archive-item`
- `.history-search`, `.search-box`, `.empty-state`
- old homepage `.category-list`
- `.week-summary`, `.week-topic`

## Preference voting

TOP 5 and Supplemental cards receive 👍 / 👎 controls from `home.js`.

Storage key: `ai3d-preferences-v1`.

This data is browser-local only. The scheduled publisher must never claim to have read it unless a separate authorized server-side preference profile exists.

## Cache busting

When a visible or interactive asset changes, bump the corresponding `?v=` reference in the same publication batch. Visual files themselves use stable-ID filenames and are regenerated only from verified canonical evidence.

## Required QA

Run before publication:

```bash
python scripts/check_intelligence_contract.py
python scripts/check_visual_contract.py YYYY-MM-DD
python scripts/check_home_contract.py
python scripts/check_daily_contract.py
```

Publication must fail on Full Analysis drift, semantic hierarchy drift, visual-ID mismatch, missing rendered local assets for successfully extracted visuals, Homepage selector regression, invalid Daily navigation, unsafe external links, or other contract failures.

If QA fails, do not publish first and fix later. Fix the canonical state or owning pipeline, rerun QA, then commit.

## Historical navigation

Older daily reports must link to the real next date when one exists. The newest report must never render a `null` next-day placeholder.

`scripts/repair_daily_state.py` is a structural repair utility for navigation/count/link drift. It is not an Intelligence-content generator.
