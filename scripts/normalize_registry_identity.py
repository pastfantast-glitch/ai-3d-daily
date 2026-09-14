#!/usr/bin/env python3
"""Normalize a canonical daily dataset against verified published history.

This script is a COLLECTION-STAGE operation and must run before a .ready marker is
created. It never edits derived HTML or presentation surfaces.

Rules:
- Only daily datasets with data/publish/YYYY-MM-DD.done.json state=DONE belong to
  the Published Intelligence Registry. Failed/WIP daily JSON must not reserve IDs
  or source URLs.
- Historical source identity is resolved the same way as registry QA: prefer the
  source URL embedded in the published daily HTML card for a stable ID, then fall
  back to the canonical JSON source_url if the published surface is unavailable.
- Same canonical source URL without substantive delta => SKIP current item.
- Same canonical source URL with status=UPDATE + non-empty delta => preserve the
  historical stable ID, never mint a new one.
- Re-rank surviving canonical items.
- Homepage TOP5 selection is driven by config/full-analysis-depth.json. FULL items
  always have priority; when policy allows, BRIEF may fill only unfilled TOP5 slots
  and remains BRIEF rather than being promoted to FULL.
- A controlled republish of an already-DONE date revalidates Registry identity but
  preserves the original Registry normalization audit counts instead of pretending
  the earlier dedupe never happened.
- After normalization, apply the current repo daily release gate. A deficit means
  discovery is NOT complete: collection must continue through the configured fill
  ladder before .ready may be created.

Exit codes:
- 0: registry-clean and current daily release gate is satisfied.
- 2: normalization succeeded but discovery/refill is still required.
- 1: usage/data error.
"""
from collections import Counter
from pathlib import Path
import json
import re
import sys

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from url_identity import canonicalize_url

DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def norm_url(url):
    return canonicalize_url(url)


def load_config():
    return json.loads((ROOT / 'config' / 'intelligence-v2.json').read_text('utf-8'))


def load_depth_config():
    return json.loads((ROOT / 'config' / 'full-analysis-depth.json').read_text('utf-8'))


def analysis_level(item):
    return str(item.get('analysis_level', 'FULL')).strip().upper()


def assign_homepage_tiers(items, top5, next10, policy):
    """Assign homepage tiers using the repo-owned FULL-first fallback policy.

    FULL candidates always get first claim on TOP5 slots. If the configured policy
    allows BRIEF fallback and fewer than `top5` FULL items survive, only the empty
    slots are filled with the highest-ranked BRIEF survivors. BRIEF remains BRIEF;
    this function changes presentation tier only, never evidence-depth class.
    """
    mode = str(policy.get('selection_mode') or 'full-only').strip()
    allow_brief = bool(policy.get('allow_brief', False))
    fallback_only = bool(policy.get('brief_fallback_only', True))

    if mode not in ('full-only', 'full-first-brief-fallback'):
        raise ValueError(f'Unknown TOP5 selection mode: {mode}')
    if mode == 'full-first-brief-fallback' and not allow_brief:
        raise ValueError('TOP5 selection_mode allows BRIEF fallback but allow_brief=false')

    full_candidates = [item for item in items if analysis_level(item) == 'FULL']
    selected = list(full_candidates[:top5])

    if mode == 'full-first-brief-fallback' and allow_brief and len(selected) < top5:
        selected_ids = {str(item.get('id', '')).strip() for item in selected}
        brief_candidates = [
            item for item in items
            if analysis_level(item) == 'BRIEF'
            and str(item.get('id', '')).strip() not in selected_ids
        ]
        selected.extend(brief_candidates[:top5 - len(selected)])
    elif allow_brief and not fallback_only:
        # Kept for explicit future policy modes; current contract uses fallback-only.
        selected = list(items[:top5])

    top_ids = {str(item.get('id', '')).strip() for item in selected}
    # Presentation order remains canonical global rank order even though FULL gets
    # admission priority over BRIEF for the limited TOP5 slots.
    top_items = [item for item in items if str(item.get('id', '')).strip() in top_ids]
    non_top = [item for item in items if str(item.get('id', '')).strip() not in top_ids]
    next_ids = {
        str(item.get('id', '')).strip()
        for item in non_top[:next10]
    }

    for item in items:
        rid = str(item.get('id', '')).strip()
        if rid in top_ids:
            item['homepage_tier'] = 'top5'
        elif rid in next_ids:
            item['homepage_tier'] = 'next10'
        else:
            item['homepage_tier'] = 'category_only'

    top_full_count = sum(1 for item in top_items if analysis_level(item) == 'FULL')
    top_brief_count = sum(1 for item in top_items if analysis_level(item) == 'BRIEF')
    return {
        'selection_mode': mode,
        'requested_top5': top5,
        'actual_top5': len(top_items),
        'top5_full_count': top_full_count,
        'top5_brief_fallback_count': top_brief_count,
        'top5_full_only': top_brief_count == 0,
        'brief_fallback_allowed': allow_brief,
        'next10': min(next10, len(non_top)),
    }


def is_verified_published(date):
    receipt_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    if not receipt_path.exists():
        return False
    try:
        receipt = json.loads(receipt_path.read_text('utf-8'))
    except Exception:
        return False
    return str(receipt.get('state', '')).strip().upper() == 'DONE'


def published_source_by_id(date):
    """Return source identity from the immutable published daily surface.

    Registry QA intentionally prefers the source URL rendered on the published
    card because that is the identity users actually received. Keep collection
    normalization in lockstep with that rule so a source cannot pass normalization
    and then fail later as identity drift.
    """
    daily_path = ROOT / date / 'index.html'
    sources = {}
    if not daily_path.exists():
        return sources

    soup = BeautifulSoup(daily_path.read_text('utf-8'), 'html.parser')
    for card in soup.select('[data-intel-role="card"][data-intel-id]'):
        rid = str(card.get('data-intel-id', '')).strip()
        anchor = card.select_one('a.source[href]')
        if not rid or not anchor:
            continue
        source = norm_url(anchor.get('href'))
        if source:
            sources[rid] = source
    return sources


def prior_registry(target_date):
    owners = {}
    ids = set()
    for p in sorted((ROOT / 'data' / 'daily').glob('20??-??-??.json')):
        if p.stem >= target_date or not is_verified_published(p.stem):
            continue
        data = json.loads(p.read_text('utf-8'))
        source_by_id = published_source_by_id(p.stem)
        for item in data.get('items', []):
            rid = str(item.get('id', '')).strip()
            src = source_by_id.get(rid) or norm_url(item.get('source_url'))
            if rid:
                ids.add(rid)
            if rid and src and src not in owners:
                owners[src] = rid
    return owners, ids


def daily_gate(cfg, items):
    collection = cfg.get('collection') or {}
    have = len(items)
    minimum = int(collection['daily_min_items'])
    target = int(collection['daily_target_items'])
    maximum = int(collection['daily_max_items'])
    counts = Counter(str(item.get('category', '')).strip() for item in items)
    return {
        'have': have,
        'min': minimum,
        'target': target,
        'max': maximum,
        'missing_to_min': max(0, minimum - have),
        'missing_to_target': max(0, target - have),
        'release_ready': minimum <= have <= maximum,
        'category_counts': {c['id']: counts.get(c['id'], 0) for c in cfg['categories']},
    }


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else ''
    if not DATE_RE.fullmatch(target):
        raise SystemExit('Usage: normalize_registry_identity.py YYYY-MM-DD')

    data_path = ROOT / 'data' / 'daily' / f'{target}.json'
    if not data_path.exists():
        raise SystemExit(f'Missing canonical dataset: {data_path}')

    cfg = load_config()
    depth = load_depth_config()
    data = json.loads(data_path.read_text('utf-8'))
    was_verified_done = is_verified_published(target)
    previous_registry_meta = dict(
        ((data.get('metadata') or {}).get('registry_identity_normalization') or {})
    )
    owners, prior_ids = prior_registry(target)
    kept = []
    dropped = []
    rewrites = {}

    for item in data.get('items', []):
        rid = str(item.get('id', '')).strip()
        src = norm_url(item.get('source_url'))
        status = str(item.get('status', '')).strip().upper()
        delta = str(item.get('delta', '')).strip()
        historical_owner = owners.get(src) if src else None

        if historical_owner:
            if status == 'UPDATE' and delta:
                if rid != historical_owner:
                    rewrites[rid] = historical_owner
                    item['id'] = historical_owner
                kept.append(item)
            else:
                dropped.append({
                    'id': rid,
                    'source_url': src,
                    'historical_id': historical_owner,
                    'reason': 'published-source-no-substantive-delta',
                })
            continue

        if rid in prior_ids:
            if status == 'UPDATE' and delta:
                kept.append(item)
            else:
                dropped.append({
                    'id': rid,
                    'source_url': src,
                    'historical_id': rid,
                    'reason': 'repeated-stable-id-no-substantive-delta',
                })
            continue

        kept.append(item)

    homepage = cfg.get('homepage') or {}
    top5 = int(homepage.get('top5', 5))
    next10 = int(homepage.get('next10', 10))
    for rank, item in enumerate(kept, 1):
        item['rank_global'] = rank
    tier_summary = assign_homepage_tiers(
        kept,
        top5,
        next10,
        depth.get('top5_policy') or {},
    )

    data['items'] = kept
    meta = data.setdefault('metadata', {})
    meta['total_items'] = len(kept)
    meta['homepage_tier_normalization'] = tier_summary
    collection = cfg.get('collection') or {}
    if collection.get('discovery_windows'):
        meta['discovery_windows'] = collection['discovery_windows']

    gate = daily_gate(cfg, kept)
    registry_meta = {
        'dropped_count': len(dropped),
        'rewritten_count': len(rewrites),
        'policy': 'verified-DONE-published-canonical-source-without-substantive-delta-skip',
        'source_identity_precedence': 'published-daily-html-card-then-canonical-json',
        'url_identity': 'scripts/url_identity.py',
        'stage': 'collection-before-ready',
        'refill_required': not gate['release_ready'],
        'category_deficits': {},
        'daily_release_gate': gate,
    }
    if was_verified_done and previous_registry_meta:
        # The already-published release has a truthful record of how many candidates
        # the original Registry pass dropped/rewrote. A policy-only republication
        # must not erase those historical audit facts merely because the clean
        # survivor set is being revalidated.
        for key in (
            'dropped_count',
            'rewritten_count',
            'policy',
            'source_identity_precedence',
            'url_identity',
            'stage',
        ):
            if key in previous_registry_meta:
                registry_meta[key] = previous_registry_meta[key]
        registry_meta['republication_revalidated'] = True
    meta['registry_identity_normalization'] = registry_meta

    visual = data.get('visual_evidence') or {}
    for old, new in rewrites.items():
        if old in visual and new not in visual:
            visual[new] = visual.pop(old)
    for rec in dropped:
        visual.pop(rec['id'], None)
    data['visual_evidence'] = visual

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    print(f'REGISTRY IDENTITY NORMALIZED: kept={len(kept)} dropped={len(dropped)} rewritten={len(rewrites)}')
    if was_verified_done:
        print('REGISTRY AUDIT PRESERVED: controlled republish revalidated the clean survivor set without resetting original dedupe counts')
    for rec in dropped:
        print(f"SKIP {rec['id']} -> historical {rec['historical_id']} source={rec['source_url']}")
    for old, new in rewrites.items():
        print(f'REWRITE {old} -> {new}')
    print(
        'HOMEPAGE TIER NORMALIZED: '
        f"mode={tier_summary['selection_mode']} "
        f"FULL={tier_summary['top5_full_count']} "
        f"BRIEF_FALLBACK={tier_summary['top5_brief_fallback_count']} "
        f"actual_top5={tier_summary['actual_top5']} requested_top5={tier_summary['requested_top5']}"
    )

    if gate['have'] > gate['max']:
        print(f"REGISTRY RELEASE BLOCKED: have={gate['have']} exceeds daily maximum={gate['max']}")
        sys.exit(1)
    if gate['have'] < gate['min']:
        print(f"REGISTRY REFILL REQUIRED: have={gate['have']} minimum={gate['min']} missing={gate['missing_to_min']} target={gate['target']}")
        print('Continue discovery toward the daily target through the configured fill ladder; do not create .ready yet.')
        sys.exit(2)
    print(f"REGISTRY RELEASE GATE PASS: have={gate['have']} minimum={gate['min']} target={gate['target']} maximum={gate['max']} category_counts={gate['category_counts']}")


if __name__ == '__main__':
    main()
