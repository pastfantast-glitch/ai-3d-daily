# AI 3D Daily — Frontend & Publishing Architecture

## Purpose

Homepage and historical daily reports are views of one Production Intelligence system. Daily content changes; identity, historical snapshots, presentation contracts and publishing ownership must not drift with it.

## Canonical daily data

- `data/daily/YYYY-MM-DD.json` is the canonical Intelligence dataset for that date.
- Every Intelligence record has one stable `id`.
- `slot=top` must contain exactly 5 records; `slot=more` must contain 6–12.
- Full Analysis is authored once as structured `label + text` blocks and rendered into both Homepage and Daily as semantic `<h4>label</h4><p>text</p>` pairs.
- Homepage and Daily cards carry `data-intel-id="..." data-intel-role="card"` from the moment new-date source markup is written.
- New dates must never infer identity from title, card order or source URL. The 2026-08-23 bootstrap/title fallback is a legacy compatibility exception only.

## Published Intelligence Registry

There is no third manually maintained Registry file. The append-only collection of `data/daily/*.json` is the Published Intelligence Registry.

`scripts/check_registry_contract.py` enforces:

- the same source URL may not silently change stable ID;
- when a stable ID appears again on a later date, it is an UPDATE and must declare `status: "UPDATE"` plus a non-empty `delta`;
- a repeated record without a real delta is rejected instead of being republished as new intelligence.

This keeps dedupe history in the same canonical data rather than creating another mutable source.

## Release-ready gate

The scheduled publisher writes files in this order:

1. complete Discovery / dedupe / Intelligence decisions;
2. write `data/daily/YYYY-MM-DD.json`;
3. write the current `index.html` content shell with stable IDs / roles;
4. write `YYYY-MM-DD/index.html` historical snapshot shell with the same IDs / roles;
5. write any required registry/metadata state;
6. **last**, create `data/publish/YYYY-MM-DD.ready`.

The `.ready` marker is the publication gate. `data/daily/**` does **not** trigger the canonical publish workflow, preventing GitHub Actions from rendering while the scheduled task is still writing the other files.

`scripts/check_release_input.py` runs before any derived rendering and verifies date/schema, unique IDs, TOP/Supplemental counts, Full Analysis shape, Visual Evidence IDs, both page shells, exact ID order/sets, roles, source links and analysis shells. If input is incomplete, publication stops before modifying derived output.

## Canonical Full Analysis

`scripts/build_intelligence.py` reads only canonical Full Analysis blocks and replaces the analysis body on the card with the matching stable ID.

Homepage and Daily must therefore contain identical normalized Full Analysis text for the same ID. `scripts/check_intelligence_contract.py` validates block count, `h4 + p` semantic hierarchy, labels, paragraphs and cross-view parity.

## Canonical Visual Evidence

Visual identity uses the same stable Intelligence ID.

Each canonical dataset may contain top-level `visual_evidence` keyed by stable ID with:

- `enabled`
- `source_url`
- `label`
- `confidence`
- `keywords`
- `reason` when disabled

`scripts/extract_visual_assets.py` extracts representative images from canonical source pages using OG/Twitter metadata, JSON-LD and article image candidates. It rejects logos/icons/avatars/ads/placeholders, validates Content-Type and minimum dimensions, and records explicit diagnostic states for missing images.

### Historical visual snapshot rule

Visual files are versioned by date:

`assets/visual/YYYY-MM-DD/<data-intel-id>.jpg`

Each date also gets:

`assets/visual/YYYY-MM-DD/manifest.json`

`assets/visual/manifest.json` is only the current-release convenience manifest. Date-scoped storage is mandatory because an UPDATE may reuse the same stable ID on a later date; overwriting a global `<id>.jpg` would mutate historical reports.

`scripts/inject_visual_previews.py` injects only `status=ok` local assets by exact stable ID. Preview figures carry `data-intel-role="visual"` so Intelligence QA cannot mistake them for cards.

`scripts/check_visual_contract.py` verifies current/per-date manifests, date-scoped paths, local asset existence, source-page identity, card/visual roles and matching Homepage/Daily rendered paths.

## Runtime integrity

`canonical-client.js` is a shared integrity renderer used by Homepage and Daily.

It may rehydrate:

- Full Analysis from `data/daily/YYYY-MM-DD.json`;
- Visual Evidence from `assets/visual/YYYY-MM-DD/manifest.json` and local snapshot assets.

Historical pages therefore read their own visual manifest, never the newest root manifest. Runtime must not remove a valid historical static preview merely because the newest release has a different date.

New dates must already carry stable IDs. Runtime title/source fallback is restricted to the legacy 2026-08-23 snapshot.

`home.js` / `daily.js` load the shared module with the report date as the module cache key instead of a permanently hard-coded 8/23 token.

## Historical navigation

Previous/next links are structural derived state, not Intelligence content.

`scripts/render_daily_navigation.py` scans actual dated report directories and sets `data-previous` / `data-next` for every snapshot. When a new report is added, the previous day's `data-next` is updated in the same atomic publication.

The publisher therefore stages all dated `*/index.html` files that changed structurally, not only the new day's file. `scripts/check_daily_contract.py` verifies actual previous/next dates and rejects literal `null` placeholders.

## Homepage modules

- `index.html` — current Homepage view; readable non-minified HTML.
- `home.css` — foundation / structural layout.
- `home-content.css` — visual theme, Intelligence-card content, Full Analysis and preview presentation.
- `home-components.css` — Supplemental, Test Today, Archive and preference-vote components.
- `home.js` — Homepage interaction and browser-local preference voting.
- `canonical-client.js` — shared runtime integrity renderer.
- `styles.css` — historical/shared base styles.
- `daily.css` / `daily.js` — historical report presentation / interaction.

Do not create an emergency stylesheet to patch a selector mismatch. Fix the owning semantic markup, renderer or component contract.

## Homepage semantic contract

Section order is fixed:

1. Hero / date / status counts
2. `.top-list > .top-item` — exactly five TOP 5 cards
3. `.more-grid > .more-card` — 6–12 Supplemental cards
4. `.test-section` — Today worth testing
5. `.history-list > a` — archive links

Desktop Supplemental is two columns; mobile is one column.

## Cache busting

`scripts/apply_cache_bust.py YYYY-MM-DD` applies a deterministic token based on `date + render_revision` to visible/interactive shell assets. Re-running the same revision is idempotent; changing the day or render revision creates a new URL.

Runtime canonical data and manifests are fetched with no-store semantics; local images are immutable per date snapshot.

## Single atomic publish pipeline

`.github/workflows/intelligence-build.yml` is the only repository writer.

All triggers share one global concurrency lock. Other migration/repair workflows remain read-only QA only.

Scheduled publication is triggered by the `.ready` marker and follows this order:

1. validate pipeline topology;
2. resolve the exact ready-marker/manual/issue date;
3. run 2026-08-23 legacy ID migration only when that exact legacy date is being rebuilt;
4. run release-ready input preflight;
5. validate Published Intelligence Registry / dedupe history;
6. render archive previous/next navigation;
7. render canonical Full Analysis;
8. extract date-versioned Visual Evidence;
9. inject local previews by stable ID;
10. apply deterministic cache bust;
11. run Intelligence / Visual / Homepage / Daily contracts;
12. stage visual assets, Homepage and every changed dated report;
13. create **one** `Publish canonical intelligence YYYY-MM-DD` commit;
14. clean-worktree rebase and push.

There are no intermediate manifest commits. A QA failure leaves no partially published generated state on main.

## Pipeline topology QA

`scripts/check_pipeline_contract.py` verifies:

- only `intelligence-build.yml` has `contents: write`;
- no other workflow contains git commit/push writer commands;
- `data/daily/**` is not a publish trigger;
- release-ready, registry, navigation, render, visual, cache and QA stages remain present;
- retired parallel writers do not return.

## Retired architecture

These must not return:

- `today-more.json`
- `scripts/inject_today_more.py`
- `.github/workflows/today-more.yml`
- `home-layout-fixes.css`
- `visual-assets.json`
- `.github/workflows/visual-assets.yml`

Retired Homepage selectors include `.more-feed`, `.more-group`, `.test-strip`, `.archive-list`, `.archive-item`, `.history-search`, `.search-box`, `.empty-state`, old `.category-list`, `.week-summary`, `.week-topic`.

## Preference voting

TOP 5 and Supplemental cards receive 👍 / 👎 controls from `home.js`.

Storage key: `ai3d-preferences-v1`.

This remains browser-local only. The scheduled publisher must never claim to have read personalization unless a separate authorized server-side preference profile exists.

## Publication completion contract

A release is complete only after all of these pass:

```bash
python scripts/check_pipeline_contract.py
python scripts/check_release_input.py YYYY-MM-DD
python scripts/check_registry_contract.py
python scripts/check_intelligence_contract.py
python scripts/check_visual_contract.py YYYY-MM-DD
python scripts/check_home_contract.py
python scripts/check_daily_contract.py
```

and main contains:

`Publish canonical intelligence YYYY-MM-DD`

If any contract fails, fix the canonical/source state or owning renderer and rerun. Do not publish first and repair later.
