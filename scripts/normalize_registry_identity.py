#!/usr/bin/env python3
"""Normalize a canonical daily dataset against verified published history.

This script is a COLLECTION-STAGE operation and must run before a .ready marker is
created. It never edits derived HTML or presentation surfaces.

Rules:
- Only daily datasets with data/publish/YYYY-MM-DD.done.json state=DONE belong to
  the Published Intelligence Registry. Failed/WIP daily JSON must not reserve IDs
  or source URLs.
- Same normalized source URL without substantive delta => SKIP current item.
- Same normalized source URL with status=UPDATE + non-empty delta => preserve the
  historical stable ID, never mint a new one.
- Re-rank surviving canonical items.
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

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def norm_url(url):
    return (url or '').strip().rstrip('/')


def load_config():
    return json.loads((ROOT / 'config' / 'intelligence-v2.json').read_text('utf-8'))


def selected_tier(rank, total, top5, next10):
    if rank <= min(top5, total):
        return 'top5'
    if rank <= min(top5 + next10, total):
        return 'next10'
    return 'category_only'


def is_verified_published(date):
    receipt_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    if not receipt_path.exists():
        return False
    try:
        receipt = json.loads(receipt_path.read_text('utf-8'))
    except Exception:
        return False
    return str(receipt.get('state', '')).strip().upper() == 'DONE'


def prior_registry(target_date):
    owners = {}
    ids = set()
    for p in sorted((ROOT / 'data' / 'daily').glob('20??-??-??.json')):
        if p.stem >= target_date or not is_verified_published(p.stem):
            continue
        data = json.loads(p.read_text('utf-8'))
        for item in data.get('items', []):
            rid = str(item.get('id', '')).strip()
            src = norm_url(item.get('source_url'))
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
    data = json.loads(data_path.read_text('utf-8'))
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
        item['homepage_tier'] = selected_tier(rank, len(kept), top5, next10)

    data['items'] = kept
    meta = data.setdefault('metadata', {})
    meta['total_items'] = len(kept)
    collection = cfg.get('collection') or {}
    if collection.get('discovery_windows'):
        meta['discovery_windows'] = collection['discovery_windows']

    gate = daily_gate(cfg, kept)
    meta['registry_identity_normalization'] = {
        'dropped_count': len(dropped),
        'rewritten_count': len(rewrites),
        'policy': 'verified-DONE-published-source-without-substantive-delta-skip',
        'stage': 'collection-before-ready',
        'refill_required': not gate['release_ready'],
        'category_deficits': {},
        'daily_release_gate': gate,
    }

    visual = data.get('visual_evidence') or {}
    for old, new in rewrites.items():
        if old in visual and new not in visual:
            visual[new] = visual.pop(old)
    for rec in dropped:
        visual.pop(rec['id'], None)
    data['visual_evidence'] = visual

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    print(f'REGISTRY IDENTITY NORMALIZED: kept={len(kept)} dropped={len(dropped)} rewritten={len(rewrites)}')
    for rec in dropped:
        print(f"SKIP {rec['id']} -> historical {rec['historical_id']} source={rec['source_url']}")
    for old, new in rewrites.items():
        print(f'REWRITE {old} -> {new}')

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
