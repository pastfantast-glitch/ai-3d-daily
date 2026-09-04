#!/usr/bin/env python3
"""Synthetic dry run for the V2 collection contract.

This test never writes canonical data or .ready markers. It builds in-memory fixtures
from config and proves that the configured target passes while common incomplete or
corrupt releases fail closed. Critically, the target is defined on items that SURVIVE
Published Intelligence Registry dedupe: a collection that first reaches the numeric
target and then loses an item to registry dedupe is not release-ready and must refill.
Historical pre-effective variable pools are also kept compatible.
"""
from copy import deepcopy
from datetime import date, timedelta

from intelligence_v2 import load_config, validate_v2_dataset


def fixture_item(cfg, category, rank):
    top_limit = int(cfg['homepage']['top5'])
    next_limit = int(cfg['homepage']['next10'])
    if rank <= top_limit:
        tier = 'top5'
    elif rank <= top_limit + next_limit:
        tier = 'next10'
    else:
        tier = 'category_only'
    return {
        'id': f'dry-{category["id"]}-{rank:02d}',
        'title': f'Dry run item {rank}',
        'summary': 'Synthetic production intelligence fixture.',
        'quick_impact': 'Dry Run ★★★★☆',
        'source_url': f'https://example.invalid/intelligence/{rank:02d}',
        'category': category['id'],
        'subcategory': category['subtypes'][0],
        'ranking_score': 1000 - rank,
        'rank_global': rank,
        'homepage_tier': tier,
        'full_analysis': [
            {'label': '製作流程', 'text': 'Synthetic workflow validation block.'},
            {'label': '製作價值', 'text': 'Synthetic production-value validation block.'},
            {'label': '導入測試', 'text': 'Synthetic adoption-risk validation block.'},
        ],
    }


def target_fixture(cfg):
    target = int(cfg['category_pool_target_items'])
    items = []
    rank = 1
    for category in cfg['categories']:
        for _ in range(target):
            items.append(fixture_item(cfg, category, rank))
            rank += 1
    return {
        'date': cfg['collection_contract_effective_date'],
        'schema_version': int(cfg.get('schema_version', 3)),
        'metadata': {
            'registry_identity_normalization': {
                'stage': 'collection-before-ready',
                'refill_required': False,
                'category_deficits': {},
            }
        },
        'items': items,
    }


def historical_fixture(cfg):
    effective = date.fromisoformat(cfg['collection_contract_effective_date'])
    report_date = (effective - timedelta(days=1)).isoformat()
    items = []
    rank = 1
    for category in cfg['categories']:
        items.append(fixture_item(cfg, category, rank))
        rank += 1
    return {
        'date': report_date,
        'schema_version': int(cfg.get('schema_version', 3)),
        'metadata': {'category_pool_max_items': 10},
        'items': items,
    }


def expect_pass(name, data):
    errors = validate_v2_dataset(data, strict_pool=True)
    if errors:
        raise AssertionError(f'{name} should PASS but failed: {errors}')
    print(f'PASS expected: {name}')


def expect_fail(name, data, expected_fragment):
    errors = validate_v2_dataset(data, strict_pool=True)
    if not errors:
        raise AssertionError(f'{name} should FAIL but passed')
    if expected_fragment and not any(expected_fragment in error for error in errors):
        raise AssertionError(f'{name} failed for the wrong reason: {errors}')
    print(f'FAIL expected: {name} -> {errors[0]}')


def main():
    cfg = load_config()
    target = int(cfg['category_pool_target_items'])
    total = target * len(cfg['categories'])
    base = target_fixture(cfg)

    expect_pass(f'exact configured post-registry target ({len(cfg["categories"])} x {target} = {total})', base)

    post_registry_missing = deepcopy(base)
    post_registry_missing['items'].pop()
    post_registry_missing['metadata']['registry_identity_normalization'] = {
        'stage': 'collection-before-ready',
        'refill_required': True,
        'category_deficits': {
            cfg['categories'][-1]['id']: {'have': target - 1, 'target': target, 'missing': 1}
        },
    }
    expect_fail(
        f'post-registry dedupe removes one item ({total - 1} survivors); collection must refill before ready',
        post_registry_missing,
        'target-fill',
    )

    duplicate_source = deepcopy(base)
    duplicate_source['items'][-1]['source_url'] = duplicate_source['items'][0]['source_url']
    expect_fail('duplicate normalized source URL', duplicate_source, 'duplicate source URL')

    bad_rank = deepcopy(base)
    bad_rank['items'][-1]['rank_global'] = total + 1
    expect_fail('non-contiguous global rank', bad_rank, 'rank_global must be a contiguous')

    expect_pass('pre-effective historical variable-pool compatibility', historical_fixture(cfg))
    print(
        f'COLLECTION CONTRACT DRY RUN PASS: config target={target}/category total={total}; '
        'target is measured after registry dedupe; no files written'
    )


if __name__ == '__main__':
    main()
