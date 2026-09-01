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
    if int(cfg.get('category_pool_size', 0)) != 10:
        raise ValueError('V2 category_pool_size must be 10')
    if int(cfg.get('homepage', {}).get('top5', 0)) != 5:
        raise ValueError('V2 homepage.top5 must be 5')
    if int(cfg.get('homepage', {}).get('next10', 0)) != 10:
        raise ValueError('V2 homepage.next10 must be 10')
    return cfg


def is_v2_dataset(data):
    return int(data.get('schema_version', 0)) >= 3


def category_map(cfg=None):
    cfg = cfg or load_config()
    return {c['id']: c for c in cfg['categories']}


def validate_v2_dataset(data, strict_pool=True):
    """Return a list of contract errors for a schema-v3 dataset."""
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

    if ranks and sorted(ranks) != list(range(1, len(items) + 1)):
        errors.append('rank_global must be a contiguous 1..N ordering')
    if len(tiers['top5']) != 5:
        errors.append(f'homepage top5 must contain exactly 5 items, got {len(tiers["top5"])}')
    if len(tiers['next10']) != 10:
        errors.append(f'homepage next10 must contain exactly 10 items, got {len(tiers["next10"])}')
    expected_top = [x['id'] for x in sorted(items, key=lambda x: int(x.get('rank_global', 10**9)))[:5]]
    actual_top = [x['id'] for x in sorted(tiers['top5'], key=lambda x: int(x.get('rank_global', 10**9)))]
    if expected_top and actual_top != expected_top:
        errors.append('top5 must equal global ranks 1-5')
    expected_next = [x['id'] for x in sorted(items, key=lambda x: int(x.get('rank_global', 10**9)))[5:15]]
    actual_next = [x['id'] for x in sorted(tiers['next10'], key=lambda x: int(x.get('rank_global', 10**9)))]
    if expected_next and actual_next != expected_next:
        errors.append('next10 must equal global ranks 6-15')

    pool_size = int(cfg['category_pool_size'])
    for cid, pool in by_category.items():
        if len(pool) > pool_size:
            errors.append(f'{cid}: category pool exceeds {pool_size}, got {len(pool)}')
        if strict_pool and len(pool) != pool_size:
            errors.append(f'{cid}: release-ready V2 pool must contain exactly {pool_size}, got {len(pool)}')
    if strict_pool and len(items) != pool_size * len(categories):
        errors.append(f'V2 release-ready dataset must contain exactly 60 items, got {len(items)}')
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
