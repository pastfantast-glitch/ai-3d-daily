#!/usr/bin/env python3
"""Hybrid-aware release input gate with FULL / BRIEF analysis tiers.

The legacy V2 validator assumes TOP5 is always global ranks 1-5. From the tiered
Full Analysis contract onward that is no longer true: TOP5 is selected from the
highest-ranked FULL survivors, while BRIEF may only enter next10/category views.
This wrapper keeps the shared legacy validator for all other invariants, replaces
only those obsolete homepage-tier errors for tiered dates, and validates the
repo-owned depth policy fail-closed.
"""
from pathlib import Path
import json

import check_release_input_core as core
from discovery_hybrid import low_volume_release_allowed

ROOT = Path(__file__).resolve().parents[1]
DEPTH_PATH = ROOT / 'config' / 'full-analysis-depth.json'
ORIGINAL_VALIDATE = core.validate_v2_dataset


def _level(item):
    return str(item.get('analysis_level') or 'FULL').strip().upper()


def _depth_config():
    return json.loads(DEPTH_PATH.read_text('utf-8'))


def _tiered_applies(data, depth):
    date = str(data.get('date') or '').strip()
    return bool(date and date >= str(depth.get('tiered_effective_date', '9999-12-31')))


def validate_analysis_tiered(items):
    for item in items:
        rid = item.get('id')
        level = _level(item)
        blocks = item.get('full_analysis') or []
        if level == 'REJECT':
            core.fail(f'{rid}: REJECT items cannot appear in canonical publish')
            continue
        minimum = 1 if level == 'BRIEF' else 3
        if len(blocks) < minimum:
            core.fail(f'{rid}: {level} analysis requires >={minimum} blocks')
        for n, block in enumerate(blocks, 1):
            if not str(block.get('label', '')).strip() or not str(block.get('text', '')).strip():
                core.fail(f'{rid}: block {n} requires label + text')


def _is_legacy_tier_error(error):
    return (
        error.startswith('homepage top5 must contain ranks ')
        or error.startswith('homepage next10 must contain up to ')
        or error.startswith('top5 must equal available global ranks ')
        or error.startswith('next10 must equal available global ranks ')
        or error.startswith('category_only must equal available global ranks ')
    )


def _tier_aware_errors(data, depth):
    """Validate homepage tiers exactly as the tier-aware Registry normalizer does."""
    items = sorted(data.get('items') or [], key=lambda x: int(x.get('rank_global', 10**9)))
    cfg = core.load_config()
    top_limit = int((cfg.get('homepage') or {}).get('top5', 5))
    next_limit = int((cfg.get('homepage') or {}).get('next10', 10))
    allow_brief = bool((depth.get('top5_policy') or {}).get('allow_brief', False))

    if allow_brief:
        expected_top = items[:top_limit]
    else:
        expected_top = [x for x in items if _level(x) == 'FULL'][:top_limit]
    top_ids = {str(x.get('id') or '') for x in expected_top}
    remaining = [x for x in items if str(x.get('id') or '') not in top_ids]
    expected_next = remaining[:next_limit]
    next_ids = {str(x.get('id') or '') for x in expected_next}
    expected_category = [x for x in remaining if str(x.get('id') or '') not in next_ids]

    actual_top = [x for x in items if x.get('homepage_tier') == 'top5']
    actual_next = [x for x in items if x.get('homepage_tier') == 'next10']
    actual_category = [x for x in items if x.get('homepage_tier') == 'category_only']

    errors = []
    if [x.get('id') for x in actual_top] != [x.get('id') for x in expected_top]:
        errors.append('tier-aware top5 must equal highest-ranked FULL items allowed by Full Analysis contract')
    if [x.get('id') for x in actual_next] != [x.get('id') for x in expected_next]:
        errors.append('tier-aware next10 must equal highest-ranked remaining items after FULL-only TOP5 selection')
    if [x.get('id') for x in actual_category] != [x.get('id') for x in expected_category]:
        errors.append('tier-aware category_only must contain all remaining canonical items after TOP5+next10')
    if not allow_brief and any(_level(x) != 'FULL' for x in actual_top):
        errors.append('tier-aware TOP5 contains BRIEF item while config/full-analysis-depth.json forbids it')
    return errors


def validate_with_hybrid(data, strict_pool=True):
    errors = ORIGINAL_VALIDATE(data, strict_pool=strict_pool)
    brief_ids = {str(x.get('id')) for x in data.get('items') or [] if _level(x) == 'BRIEF'}
    if brief_ids:
        errors = [
            e for e in errors
            if not (
                'full_analysis requires at least 3 blocks' in e
                and any(e.startswith(rid + ':') for rid in brief_ids)
            )
        ]

    depth = _depth_config()
    if _tiered_applies(data, depth):
        errors = [e for e in errors if not _is_legacy_tier_error(e)]
        errors.extend(_tier_aware_errors(data, depth))

    if not strict_pool:
        return errors
    category_ids = [c['id'] for c in core.load_config().get('categories') or []]
    if low_volume_release_allowed(data, category_ids):
        errors = [e for e in errors if not e.startswith('V2 daily release minimum is ')]
    return errors


core.validate_analysis = validate_analysis_tiered
core.validate_v2_dataset = validate_with_hybrid
core.main()
