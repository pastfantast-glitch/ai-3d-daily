# AI 3D Daily — Frontend & Publishing Architecture

## Purpose

The homepage is a generated Production Intelligence surface, but its frontend structure is a stable product contract. Daily content may change; layout ownership must not drift with it.

## Homepage modules

- `index.html` — current homepage content and semantic structure. Keep readable and non-minified.
- `home.css` — foundation and structural layout only.
- `home-content.css` — dark visual theme, information-card content, analysis UI and visual-evidence presentation.
- `home-components.css` — current Supplemental, Test Today, Archive and preference-vote components.
- `home.js` — details interaction and browser-local preference voting.
- `styles.css` — historical daily-report styles and shared base styles.

Do not create an emergency stylesheet to patch a selector mismatch. Fix the owning module instead.

## Homepage semantic contract

The section order is fixed:

1. Hero / date / status counts
2. `.top-list > .top-item` — exactly five TOP 5 cards
3. `.more-grid > .more-card` — 6–12 Supplemental cards
4. `.test-section` — Today worth testing
5. `.history-list > a` — archive links

Desktop Supplemental layout is two columns. Mobile layout is one column.

## Single-writer rule

The daily scheduled publishing task is the only owner allowed to create or replace Intelligence cards in `index.html` and the current `YYYY-MM-DD/index.html` report.

Visual automation is enrichment-only: it may extract, normalize and inject verified visual evidence, but it must not create, delete, reorder or replace TOP 5 / Supplemental Intelligence cards.

Structural repair utilities may repair navigation, link safety, counts and cache state, but must not invent Intelligence content.

## Retired architecture

The following were removed and must not return:

- `today-more.json`
- `scripts/inject_today_more.py`
- `.github/workflows/today-more.yml`
- `home-layout-fixes.css`

They created multiple writers for the homepage and allowed stale cross-day data to contaminate a newer homepage.

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

When a visible or interactive homepage asset changes, bump the corresponding `?v=` reference in `index.html` in the same publication batch.

Assets:

- `home.css`
- `home-content.css`
- `home-components.css`
- `home.js`

Visual-preview automation uses dynamic cache busting and must not hard-code an obsolete date version.

## Required QA

Run before publication:

```bash
python scripts/check_home_contract.py
```

The contract rejects, among other things:

- TOP 5 count other than five
- Supplemental count outside 6–12
- workflow-era `data-supplemental-id` cards on the homepage
- retired selectors or emergency stylesheet references
- minified/single-line `index.html`
- missing current component selectors
- stale homepage search/filter JavaScript
- unsafe homepage `target="_blank"` links
- `null` placeholders in the latest daily report

If QA fails, do not publish first and fix later. Fix the generated state, rerun QA, then commit.

## Historical navigation

Older daily reports must link to the real next date when one exists. The newest report must never render a `null` next-day placeholder.

`scripts/repair_daily_state.py` is a structural repair utility for navigation/count/link drift. It is not an Intelligence-content generator.
