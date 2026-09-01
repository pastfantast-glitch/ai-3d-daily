#!/usr/bin/env python3
"""Isolated synthetic test for schema-v3: 6x10 pools -> TOP5 -> next10.

This test never touches canonical data, index.html, archives, or publish markers.
It exercises the shared intelligence_v2 contract using 60 deterministic fake items.
"""
from intelligence_v2 import load_config, validate_v2_dataset, homepage_groups, category_items


def build_dataset():
    cfg = load_config()
    items = []
    rank = 1
    for cat in cfg['categories']:
        subtypes = cat['subtypes']
        for n in range(1, 11):
            tier = 'top5' if rank <= 5 else ('next10' if rank <= 15 else 'category_only')
            items.append({
                'id': f"dry-{cat['id']}-{n:02d}",
                'title': f"Synthetic {cat['label']} {n:02d}",
                'summary': 'Synthetic dry-run record; not publishable editorial content.',
                'quick_impact': 'Dry Run ★★★★★',
                'source_url': f"https://example.invalid/{cat['id']}/{n:02d}",
                'category': cat['id'],
                'subcategory': subtypes[(n - 1) % len(subtypes)],
                'rank_global': rank,
                'ranking_score': 1000 - rank,
                'homepage_tier': tier,
                'full_analysis': [
                    {'label': 'What changed', 'text': 'Synthetic'},
                    {'label': 'Why it matters', 'text': 'Synthetic'},
                    {'label': 'Production impact', 'text': 'Synthetic'},
                ],
            })
            rank += 1
    return {'schema_version': 3, 'date': '2099-01-01', 'items': items}


def main():
    cfg = load_config()
    data = build_dataset()
    errors = validate_v2_dataset(data, strict_pool=True)
    assert not errors, '\n'.join(errors)
    assert len(data['items']) == 60
    top, next10 = homepage_groups(data)
    assert len(top) == 5
    assert len(next10) == 10
    assert [x['rank_global'] for x in top] == list(range(1, 6))
    assert [x['rank_global'] for x in next10] == list(range(6, 16))
    for cat in cfg['categories']:
        pool = category_items(data, cat['id'])
        assert len(pool) == 10, (cat['id'], len(pool))
        assert all(x['category'] == cat['id'] for x in pool)
    assert not ({x['id'] for x in top} & {x['id'] for x in next10})
    print('V3 SYNTHETIC DRY-RUN PASS: 60 items / 6x10 / TOP5 ranks 1-5 / next10 ranks 6-15 / category isolation OK')


if __name__ == '__main__':
    main()
