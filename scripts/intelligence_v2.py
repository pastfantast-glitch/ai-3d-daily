#!/usr/bin/env python3
"""Shared AI 3D Daily V2 information-architecture contract.

This module is intentionally presentation-agnostic. It defines the six daily
collection pools, the repository-owned Production Intelligence preference profile,
and validates schema-v3 canonical records. Renderers consume validated data; they
do not decide ranking, category membership, preference weights, or homepage tier.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'intelligence-v2.json'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def _validate_score_map(name, scores, allowed_keys=None):
    if not isinstance(scores, dict) or not scores:
        raise ValueError(f'V2 {name} must be a non-empty object')
    if allowed_keys is not None:
        unknown = set(scores) - set(allowed_keys)
        if unknown:
            raise ValueError(f'V2 {name} has unknown keys: {sorted(unknown)}')
    for key, value in scores.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
            raise ValueError(f'V2 {name}.{key} must be an integer from 0 to 5')


def _validate_preference_profile(cfg, categories):
    effective = str(cfg.get('preference_contract_effective_date', '')).strip()
    if not DATE_RE.fullmatch(effective):
        raise ValueError('V2 preference_contract_effective_date must be YYYY-MM-DD')

    profile = cfg.get('production_intelligence_profile') or {}
    for key in ('purpose', 'category_quota_policy'):
        if not str(profile.get(key, '')).strip():
            raise ValueError(f'V2 production_intelligence_profile.{key} is required')

    ranking = profile.get('ranking') or {}
    dimensions = ranking.get('dimensions_in_priority_order') or []
    if not dimensions or len(dimensions) != len(set(dimensions)):
        raise ValueError('V2 ranking dimensions must be a non-empty unique ordered list')
    for key in ('freshness_rule', 'source_rule', 'selection_rule'):
        if not str(ranking.get(key, '')).strip():
            raise ValueError(f'V2 production_intelligence_profile.ranking.{key} is required')

    category_preferences = profile.get('category_preferences') or {}
    category_ids = [c['id'] for c in categories]
    if set(category_preferences) != set(category_ids):
        missing = sorted(set(category_ids) - set(category_preferences))
        extra = sorted(set(category_preferences) - set(category_ids))
        raise ValueError(
            f'V2 preference categories must exactly match configured categories; '
            f'missing={missing} extra={extra}'
        )

    category_by_id = {c['id']: c for c in categories}
    for cid, pref in category_preferences.items():
        if not isinstance(pref, dict):
            raise ValueError(f'V2 preference {cid} must be an object')
        if not str(pref.get('selection_mode', '')).strip():
            raise ValueError(f'V2 preference {cid}.selection_mode is required')
        scores = pref.get('interest_scores')
        if scores is not None:
            _validate_score_map(
                f'production_intelligence_profile.category_preferences.{cid}.interest_scores',
                scores,
                category_by_id[cid].get('subtypes', []),
            )
        tool_scores = pref.get('tool_interest_scores')
        if tool_scores is not None:
            _validate_score_map(
                f'production_intelligence_profile.category_preferences.{cid}.tool_interest_scores',
                tool_scores,
            )

    hard = profile.get('global_hard_exclude') or []
    downrank = profile.get('global_downrank') or []
    positive = profile.get('global_positive_signals') or []
    if not all(isinstance(x, str) and x.strip() for x in hard + downrank + positive):
        raise ValueError('V2 global preference signal lists must contain non-empty strings')


def load_config():
    """Load and self-validate the collection and preference contracts.

    The JSON file is the sole source of truth for targets, effective dates,
    discovery/fill policy, user-interest preferences and ranking guidance.
    Python only checks internal consistency so future changes cannot drift across
    hard-coded copies in schedulers, QA scripts or renderers.
    """
    cfg = json.loads(CONFIG.read_text('utf-8'))
    categories = cfg.get('categories') or []
    ids = [c.get('id') for c in categories]
    if len(categories) != 6 or len(set(ids)) != 6 or any(not x for x in ids):
        raise ValueError('V2 config must define exactly six unique categories')

    try:
        pool_target = int(cfg['category_pool_target_items'])
        pool_max = int(cfg['category_pool_max_items'])
        pool_min = int(cfg['category_pool_min_items'])
    except Exception as exc:
        raise ValueError('V2 category pool target/min/max must be integers') from exc
    if pool_target <= 0 or pool_min < 0 or pool_max <= 0:
        raise ValueError('V2 category pool target/min/max must be positive-compatible values')
    if not (pool_min <= pool_target <= pool_max):
        raise ValueError('V2 category pool values must satisfy min <= target <= max')

    fill_policy = str(cfg.get('category_fill_policy', '')).strip()
    if not fill_policy:
        raise ValueError('V2 category_fill_policy is required')
    effective = str(cfg.get('collection_contract_effective_date', '')).strip()
    if not DATE_RE.fullmatch(effective):
        raise ValueError('V2 collection_contract_effective_date must be YYYY-MM-DD')

    homepage = cfg.get('homepage') or {}
    if int(homepage.get('top5', 0)) != 5:
        raise ValueError('V2 homepage.top5 must remain 5')
    if int(homepage.get('next10', 0)) != 10:
        raise ValueError('V2 homepage.next10 must remain 10')

    collection = cfg.get('collection') or {}
    candidate_target = int(collection.get('candidate_pool_target_per_category', 0) or 0)
    candidate_stretch = int(collection.get('candidate_pool_stretch_per_category', 0) or 0)
    if candidate_target < pool_target:
        raise ValueError('V2 candidate target must be >= category publish target')
    if candidate_stretch < candidate_target:
        raise ValueError('V2 candidate stretch must be >= candidate target')

    windows = collection.get('discovery_windows') or []
    if not windows or len(windows) != len(set(windows)):
        raise ValueError('V2 discovery_windows must be a non-empty unique ordered list')
    window_policy = collection.get('window_policy') or {}
    if any(not str(window_policy.get(window, '')).strip() for window in windows):
        raise ValueError('V2 every discovery window requires window_policy guidance')
    fill_ladder = collection.get('fill_ladder') or []
    ladder_windows = [str(x).split(':', 1)[0] for x in fill_ladder]
    if ladder_windows != windows:
        raise ValueError('V2 fill_ladder must cover discovery_windows in the same order')

    daily_min = int(collection.get('daily_min_items', 0) or 0)
    daily_target = int(collection.get('daily_target_items', 0) or 0)
    daily_max = int(collection.get('daily_max_items', 0) or 0)
    if not (0 < daily_min <= daily_target <= daily_max):
        raise ValueError('V2 daily totals must satisfy 0 < min <= target <= max')
    if int(collection.get('completeness_trigger_total_items', 0) or 0) != daily_target:
        raise ValueError(f'V2 completeness trigger must equal daily target {daily_target}')
    if not str(collection.get('fill_target_policy', '')).strip():
        raise ValueError('V2 fill_target_policy is required')

    _validate_preference_profile(cfg, categories)
    return cfg


def is_v2_dataset(data):
    return int(data.get('schema_version', 0)) >= 3


def target_fill_applies(data, cfg=None):
    """Return True when the configured target-fill collection contract applies."""
    cfg = cfg or load_config()
    date = str(data.get('date', '')).strip()
    effective = str(cfg.get('collection_contract_effective_date', '')).strip()
    return bool(DATE_RE.fullmatch(date) and date >= effective)


def preference_profile_applies(data_or_date, cfg=None):
    """Return True when repository-owned preference guidance applies to a date."""
    cfg = cfg or load_config()
    if isinstance(data_or_date, dict):
        value = str(data_or_date.get('date', '')).strip()
    else:
        value = str(data_or_date or '').strip()
    effective = str(cfg.get('preference_contract_effective_date', '')).strip()
    return bool(DATE_RE.fullmatch(value) and value >= effective)


def category_map(cfg=None):
    cfg = cfg or load_config()
    return {c['id']: c for c in cfg['categories']}


def category_preference(category_id, cfg=None):
    """Return the source-of-truth preference object for one configured category."""
    cfg = cfg or load_config()
    prefs = cfg['production_intelligence_profile']['category_preferences']
    if category_id not in prefs:
        raise KeyError(f'Unknown V2 category preference: {category_id}')
    return prefs[category_id]


def validate_v2_dataset(data, strict_pool=True):
    """Return contract errors for schema-v3 data.

    Published schema-v3 dates before the configured target-fill effective date
    remain valid historical snapshots. From the effective date onward, release-ready
    data must satisfy the daily total contract. Category preferences never create
    per-category quotas.
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
        errors.append(f'top5 must equal available global ranks 1-{top_limit}')
    expected_next = [x['id'] for x in ordered[top_limit:top_limit + next_limit]]
    actual_next = [x['id'] for x in sorted(tiers['next10'], key=lambda x: int(x.get('rank_global', 10**9)))]
    if actual_next != expected_next:
        errors.append(f'next10 must equal available global ranks {top_limit + 1}-{top_limit + next_limit}')
    expected_category_only = [x['id'] for x in ordered[top_limit + next_limit:]]
    actual_category_only = [x['id'] for x in sorted(tiers['category_only'], key=lambda x: int(x.get('rank_global', 10**9)))]
    if actual_category_only != expected_category_only:
        errors.append(f'category_only must equal available global ranks {top_limit + next_limit + 1}..N')

    if target_fill_applies(data, cfg) and strict_pool:
        collection = cfg.get('collection') or {}
        pool_max = int(cfg['category_pool_max_items'])
        pool_min = int(cfg['category_pool_min_items'])
        daily_min = int(collection['daily_min_items'])
        daily_max = int(collection['daily_max_items'])
    else:
        metadata = data.get('metadata') or {}
        pool_max = int(metadata.get('category_pool_max_items', 10) or 10)
        pool_min = 0
        daily_min = 0
        daily_max = pool_max * len(categories)

    for cid, pool in by_category.items():
        if len(pool) > pool_max:
            errors.append(f'{cid}: category pool exceeds maximum {pool_max}, got {len(pool)}')
        if len(pool) < pool_min:
            errors.append(f'{cid}: category pool below minimum {pool_min}, got {len(pool)}')
    if len(items) < daily_min:
        errors.append(f'V2 daily release minimum is {daily_min} items, got {len(items)}')
    if len(items) > daily_max:
        errors.append(f'V2 daily release maximum is {daily_max} items, got {len(items)}')
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
