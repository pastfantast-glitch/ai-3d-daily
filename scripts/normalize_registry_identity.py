#!/usr/bin/env python3
"""Normalize current canonical identity against published daily history.

Rules:
- Published daily datasets are the source-of-truth registry.
- Same normalized source URL without substantive delta => SKIP current item.
- Same normalized source URL with status=UPDATE + non-empty delta => preserve the
  historical stable ID, never mint a new one.
- Re-rank the surviving current dataset and synchronize current homepage/daily
  seed card identities so release preflight sees the same canonical selection.

This is generic and date-independent. Historical datasets/content are never rewritten.
"""
from pathlib import Path
import json
import re
import sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def norm_url(url):
    return (url or '').strip().rstrip('/')


def load_config():
    return json.loads((ROOT/'config'/'intelligence-v2.json').read_text('utf-8'))


def selected_tier(rank, total, top5, next10):
    if rank <= min(top5, total):
        return 'top5'
    if rank <= min(top5 + next10, total):
        return 'next10'
    return 'category_only'


def prior_registry(target_date):
    owners = {}
    ids = set()
    for p in sorted((ROOT/'data'/'daily').glob('20??-??-??.json')):
        if p.stem >= target_date:
            continue
        data = json.loads(p.read_text('utf-8'))
        for item in data.get('items', []):
            rid = str(item.get('id','')).strip()
            src = norm_url(item.get('source_url'))
            if rid:
                ids.add(rid)
            if rid and src and src not in owners:
                owners[src] = rid
    return owners, ids


def sync_seed(path, keep_ids, id_rewrites):
    if not path.exists():
        return False
    original = path.read_text('utf-8')
    soup = BeautifulSoup(original, 'html.parser')
    changed = False
    for card in list(soup.select('[data-intel-role="card"][data-intel-id]')):
        cid = card.get('data-intel-id')
        if cid in id_rewrites:
            card['data-intel-id'] = id_rewrites[cid]
            cid = id_rewrites[cid]
            changed = True
        if cid not in keep_ids:
            card.decompose()
            changed = True
    if changed:
        rendered = soup.prettify()
        if not rendered.endswith('\n'):
            rendered += '\n'
        path.write_text(rendered, 'utf-8')
    return changed


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else ''
    if not DATE_RE.fullmatch(target):
        raise SystemExit('Usage: normalize_registry_identity.py YYYY-MM-DD')
    data_path = ROOT/'data'/'daily'/f'{target}.json'
    if not data_path.exists():
        raise SystemExit(f'Missing canonical dataset: {data_path}')

    cfg = load_config()
    data = json.loads(data_path.read_text('utf-8'))
    owners, prior_ids = prior_registry(target)
    kept = []
    dropped = []
    rewrites = {}

    for item in data.get('items', []):
        rid = str(item.get('id','')).strip()
        src = norm_url(item.get('source_url'))
        status = str(item.get('status','')).strip().upper()
        delta = str(item.get('delta','')).strip()
        historical_owner = owners.get(src) if src else None

        if historical_owner:
            if status == 'UPDATE' and delta:
                if rid != historical_owner:
                    rewrites[rid] = historical_owner
                    item['id'] = historical_owner
                kept.append(item)
            else:
                dropped.append({'id': rid, 'source_url': src, 'historical_id': historical_owner, 'reason': 'published-source-no-substantive-delta'})
            continue

        if rid in prior_ids:
            if status == 'UPDATE' and delta:
                kept.append(item)
            else:
                dropped.append({'id': rid, 'source_url': src, 'historical_id': rid, 'reason': 'repeated-stable-id-no-substantive-delta'})
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
    meta['registry_identity_normalization'] = {
        'dropped_count': len(dropped),
        'rewritten_count': len(rewrites),
        'policy': 'published-source-without-substantive-delta-skip'
    }

    visual = data.get('visual_evidence') or {}
    for old, new in rewrites.items():
        if old in visual and new not in visual:
            visual[new] = visual.pop(old)
    for rec in dropped:
        visual.pop(rec['id'], None)
    data['visual_evidence'] = visual

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    keep_ids = {str(x.get('id','')) for x in kept}
    home_changed = sync_seed(ROOT/'index.html', keep_ids, rewrites)
    daily_changed = sync_seed(ROOT/target/'index.html', keep_ids, rewrites)

    print(f'REGISTRY IDENTITY NORMALIZED: kept={len(kept)} dropped={len(dropped)} rewritten={len(rewrites)}')
    for rec in dropped:
        print(f"SKIP {rec['id']} -> historical {rec['historical_id']} source={rec['source_url']}")
    for old, new in rewrites.items():
        print(f'REWRITE {old} -> {new}')
    print(f'SEED SYNC: homepage={home_changed} daily={daily_changed}')

if __name__ == '__main__':
    main()
