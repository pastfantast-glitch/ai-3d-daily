#!/usr/bin/env python3
from datetime import date, timedelta
from intelligence_v2 import load_config, validate_v2_dataset, category_preference


def item(cfg, rank, cat):
    top = int(cfg['homepage']['top5'])
    nxt = int(cfg['homepage']['next10'])
    tier = 'top5' if rank <= top else ('next10' if rank <= top + nxt else 'category_only')
    return {
        'id': f'dry-{rank:02d}',
        'title': f'Dry {rank}',
        'summary': 'Synthetic production intelligence.',
        'quick_impact': 'Dry ★★★★☆',
        'source_url': f'https://example.invalid/{rank}',
        'category': cat['id'],
        'subcategory': cat['subtypes'][0],
        'ranking_score': 1000 - rank,
        'rank_global': rank,
        'homepage_tier': tier,
        'full_analysis': [
            {'label': '製作流程', 'text': 'Synthetic workflow.'},
            {'label': '製作價值', 'text': 'Synthetic value.'},
            {'label': '導入測試', 'text': 'Synthetic test.'},
        ],
    }


def fixture(cfg, n, category=None):
    cats = cfg['categories']
    return {
        'date': cfg['collection_contract_effective_date'],
        'schema_version': int(cfg.get('schema_version', 3)),
        'metadata': {},
        'items': [
            item(cfg, r, category or cats[(r - 1) % len(cats)])
            for r in range(1, n + 1)
        ],
    }


def expect(name, data, ok, frag=''):
    errors = validate_v2_dataset(data, strict_pool=True)
    if ok and errors:
        raise AssertionError(f'{name} should PASS: {errors}')
    if not ok and not errors:
        raise AssertionError(f'{name} should FAIL')
    if frag and not any(frag in x for x in errors):
        raise AssertionError(f'{name} wrong failure: {errors}')
    print(('PASS' if ok else 'FAIL expected'), name, errors[0] if errors else '')


def main():
    cfg = load_config()
    col = cfg['collection']
    mn = int(col['daily_min_items'])
    tg = int(col['daily_target_items'])
    mx = int(col['daily_max_items'])

    expect('target', fixture(cfg, tg), True)
    expect('23 survivors', fixture(cfg, 23), True)
    expect('minimum', fixture(cfg, mn), True)
    expect('below minimum', fixture(cfg, mn - 1), False, 'daily release minimum')
    expect('above maximum', fixture(cfg, mx + 1), False, 'daily release maximum')
    expect('single-category minimum remains valid', fixture(cfg, mn, cfg['categories'][0]), True)

    dup = fixture(cfg, mn)
    dup['items'][-1]['source_url'] = dup['items'][0]['source_url']
    expect('duplicate source', dup, False, 'duplicate source URL')

    bad = fixture(cfg, mn)
    bad['items'][-1]['rank_global'] = 999
    expect('bad rank', bad, False, 'contiguous')

    effective = date.fromisoformat(cfg['collection_contract_effective_date'])
    hist = fixture(cfg, 6)
    hist['date'] = (effective - timedelta(days=1)).isoformat()
    hist['metadata'] = {'category_pool_max_items': 10}
    expect('historical compatibility', hist, True)

    prefs = cfg['production_intelligence_profile']['category_preferences']
    configured = {c['id'] for c in cfg['categories']}
    if set(prefs) != configured:
        raise AssertionError('preference categories drift from configured categories')
    for cid in configured:
        if category_preference(cid, cfg) is not prefs[cid]:
            raise AssertionError(f'{cid}: category_preference accessor drift')

    print(
        'PREFERENCE CONTRACT PASS: '
        f"effective={cfg['preference_contract_effective_date']} / "
        'six categories covered / signals are non-quota'
    )
    print(
        f'COLLECTION CONTRACT DRY RUN PASS: daily min={mn} target={tg} max={mx}; '
        'categories are non-blocking'
    )


if __name__ == '__main__':
    main()
