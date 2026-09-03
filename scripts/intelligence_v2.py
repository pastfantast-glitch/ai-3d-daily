#!/usr/bin/env python3
"""Shared AI 3D Daily V2 information-architecture contract.

This module is intentionally presentation-agnostic. It defines the six daily
collection pools and validates schema-v3 canonical records. Renderers consume the
validated data; they do not decide ranking, category membership, or homepage tier.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'intelligence-v2.json'


def load_config():
    cfg = json.loads(CONFIG.read_text('utf-8'))
    categories = cfg.get('categories') or []
    ids = [c.get('id') for c in categories]
    if len(categories) != 6 or len(set(ids)) != 6 or any(not x for x in ids):
        raise ValueError('V2 config must define exactly six unique categories')
    if int(cfg.get('category_pool_target_items', 0)) != 5:
        raise ValueError('V2 category_pool_target_items must be 5')
    if int(cfg.get('category_pool_max_items', 0)) != 5:
        raise ValueError('V2 category_pool_max_items must be 5')
    if int(cfg.get('category_pool_min_items', -1)) != 5:
        raise ValueError('V2 category_pool_min_items must be 5')
    if cfg.get('category_fill_policy') != 'target_five_priority_backfill':
        raise ValueError('V2 category_fill_policy must be target_five_priority_backfill')
    effective = str(cfg.get('collection_contract_effective_date', '')).strip()
    if not effective:
        raise ValueError('V2 collection_contract_effective_date is required')
    if int(cfg.get('homepage', {}).get('top5', 0)) != 5:
        raise ValueError('V2 homepage.top5 must be 5')
    if int(cfg.get('homepage', {}).get('next10', 0)) != 10:
        raise ValueError('V2 homepage.next10 must be 10')
    return cfg


def is_v2_dataset(data):
    return int(data.get('schema_version', 0)) >= 3


def target_fill_applies(data, cfg=None):
    """Return True when the five-per-category collection contract applies.

    Existing published schema-v3 dates remain valid historical snapshots. The new
    exact-five contract begins on the configured effective date and is enforced for
    all release-ready datasets from that date onward.
    """
    cfg = cfg or load_config()
    date = str(data.get('date', '')).strip()
    effective = str(cfg.get('collection_contract_effective_date', '')).strip()
    return bool(date and effective and date >= effective)


def category_map(cfg=None):
    cfg = cfg or load_config()
    return {c['id']: c for c in cfg['categories']}


def validate_v2_dataset(data, strict_pool=True):
    """Return contract errors for schema-v3 data.

    Historical V2 snapshots before the five-item contract effective date retain
    their original variable-pool semantics. From the effective date onward,
    release-ready V2 means exactly five valid items in each of the six categories.
    """
    if not is_v2_dataset(data):
        return []
    cfg = load_config()
    categories = category_map(cfg)
    items = data.get('items') or []
    errors = []
    required_text = ('id', 'title', 'summary', 'quick_impact', 'source_url', 'category', 'subcategory')
    seen_ids, seen_sources = set(), set()
    by_category = {cid: [] for cid in categories}
    ranks = []
    tiers = {'top5': [], 'next10': [], 'category_only': []}

    for i, item in enumerate(items, 1):
        rid = str(item.get('id', '')).strip()
        for key in required_text:
            if not str(item.get(key, '')).strip():
                errors.append(f'item {rid or i}: missing {key}')
        if rid:
            if rid in seen_ids:
                errors.append(f'duplicate stable id: {rid}')
            seen_ids.add(rid)
        source = str(item.get('source_url', '')).strip().rstrip('/')
        if source:
            if source in seen_sources:
                errors.append(f'duplicate source URL in same day: {source}')
            seen_sources.add(source)
        cid = item.get('category')
        if cid not in categories:
            errors.append(f'{rid or i}: unknown category {cid!r}')
        else:
            by_category[cid].append(item)
            subtype = item.get('subcategory')
            if subtype not in categories[cid].get('subtypes', []):
                errors.append(f'{rid or i}: invalid subcategory {subtype!r} for {cid}')
        try:
            rank = int(item.get('rank_global'))
            ranks.append(rank)
        except Exception:
            errors.append(f'{rid or i}: rank_global must be an integer')
        tier = item.get('homepage_tier')
        if tier not in tiers:
            errors.append(f'{rid or i}: homepage_tier must be top5|next10|category_only')
        else:
            tiers[tier].append(item)
        try:
            float(item.get('ranking_score'))
        except Exception:
            errors.append(f'{rid or i}: ranking_score must be numeric')
        blocks = item.get('full_analysis') or []
        if len(blocks) < 3:
            errors.append(f'{rid or i}: full_analysis requires at least 3 blocks')

    ordered = sorted(items, key=lambda x: int(x.get('rank_global', 10**9)))
    if ranks and sorted(ranks) != list(range(1, len(items) + 1)):
        errors.append('rank_global must be a contiguous 1..N ordering')

    top_limit = int(cfg['homepage']['top5'])
    next_limit = int(cfg['homepage']['next10'])
    expected_top_count = min(top_limit, len(items))
    expected_next_count = min(next_limit, max(0, len(items) - top_limit))
    if len(tiers['top5']) != expected_top_count:
        errors.append(f'homepage top5 must contain ranks 1-{expected_top_count}, got {len(tiers["top5"])} items')
    if len(tiers['next10']) != expected_next_count:
        errors.append(f'homepage next10 must contain up to {next_limit} items after TOP5, got {len(tiers["next10"])}')
    expected_top = [x['id'] for x in ordered[:top_limit]]
    actual_top = [x['id'] for x in sorted(tiers['top5'], key=lambda x: int(x.get('rank_global', 10**9)))]
    if actual_top != expected_top:
        errors.append('top5 must equal available global ranks 1-5')
    expected_next = [x['id'] for x in ordered[top_limit:top_limit + next_limit]]
    actual_next = [x['id'] for x in sorted(tiers['next10'], key=lambda x: int(x.get('rank_global', 10**9)))]
    if actual_next != expected_next:
        errors.append('next10 must equal available global ranks 6-15')
    expected_category_only = [x['id'] for x in ordered[top_limit + next_limit:]]
    actual_category_only = [x['id'] for x in sorted(tiers['category_only'], key=lambda x: int(x.get('rank_global', 10**9)))]
    if actual_category_only != expected_category_only:
        errors.append('category_only must equal available global ranks 16..N')

    if target_fill_applies(data, cfg) and strict_pool:
        pool_target = int(cfg['category_pool_target_items'])
        pool_max = int(cfg['category_pool_max_items'])
        pool_min = int(cfg['category_pool_min_items'])
    else:
        metadata = data.get('metadata') or {}
        pool_target = None
        pool_max = int(metadata.get('category_pool_max_items', 10) or 10)
        pool_min = 0

    for cid, pool in by_category.items():
        if len(pool) > pool_max:
            errors.append(f'{cid}: category pool exceeds maximum {pool_max}, got {len(pool)}')
        if len(pool) < pool_min:
            errors.append(f'{cid}: category pool below minimum {pool_min}, got {len(pool)}')
        if pool_target is not None and len(pool) != pool_target:
            errors.append(f'{cid}: five-item fill target requires exactly {pool_target} items, got {len(pool)}')
    if len(items) > pool_max * len(categories):
        errors.append(f'V2 dataset exceeds maximum {pool_max * len(categories)} items, got {len(items)}')
    if pool_target is not None and len(items) != pool_target * len(categories):
        errors.append(f'V2 five-item fill target requires exactly {pool_target * len(categories)} items, got {len(items)}')
    return errors


def sorted_items(data):
    return sorted(data.get('items') or [], key=lambda x: int(x.get('rank_global', 10**9)))


def homepage_groups(data):
    ordered = sorted_items(data)
    return (
        [x for x in ordered if x.get('homepage_tier') == 'top5'],
        [x for x in ordered if x.get('homepage_tier') == 'next10'],
    )


def category_items(data, category_id):
    return [x for x in sorted_items(data) if x.get('category') == category_id]
