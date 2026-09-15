#!/usr/bin/env python3
"""Canonical release-input gate with FULL / BRIEF analysis tiers.

Legacy V2 validation still owns the stable dataset invariants. Tier-aware homepage
selection is intentionally NOT reimplemented here: the Published Intelligence
Registry normalizer is the single source of truth for FULL-first / BRIEF-fallback
assignment. This gate applies that same function to an in-memory copy and compares
the canonical dataset against the expected tiers.
"""
from pathlib import Path
import json
import re
import sys

import check_release_input_core as core
from discovery_hybrid import coverage_audit_errors, low_volume_release_allowed
from normalize_registry_identity import assign_homepage_tiers

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


def _validation_date():
    if len(sys.argv) > 1 and re.fullmatch(r'20\d{2}-\d{2}-\d{2}', str(sys.argv[1])):
        return str(sys.argv[1])
    return core.latest_date()


def _brief_policy_for_date(date, depth):
    effective = str(depth.get('brief_reading_contract_effective_date', '9999-12-31'))
    if date >= effective:
        return depth.get('brief_reading') or depth.get('brief') or {}
    return depth.get('brief') or {}


def validate_analysis_tiered(items):
    depth = _depth_config()
    date = _validation_date()
    full_cfg = depth.get('full') or {}
    brief_cfg = _brief_policy_for_date(date, depth)
    base_brief_cfg = depth.get('brief') or {}
    allowed_brief_reasons = set(base_brief_cfg.get('allowed_reasons') or [])

    for item in items:
        rid = item.get('id')
        level = _level(item)
        blocks = item.get('full_analysis') or []
        if level == 'REJECT':
            core.fail(f'{rid}: REJECT items cannot appear in canonical publish')
            continue
        if level not in ('FULL', 'BRIEF'):
            core.fail(f'{rid}: unknown analysis_level={level!r}')
            continue

        policy = brief_cfg if level == 'BRIEF' else full_cfg
        default_min = 3 if level == 'FULL' or date >= str(depth.get('brief_reading_contract_effective_date', '9999-12-31')) else 1
        default_max = 5 if level == 'FULL' else (3 if default_min == 3 else 2)
        minimum = int(policy.get('min_blocks', default_min))
        maximum = int(policy.get('max_blocks', default_max))
        if len(blocks) < minimum or len(blocks) > maximum:
            core.fail(f'{rid}: {level} analysis requires {minimum}-{maximum} blocks')

        if level == 'BRIEF':
            reason = str(item.get('brief_reason') or '').strip()
            if not reason:
                core.fail(f'{rid}: BRIEF requires brief_reason')
            elif allowed_brief_reasons and reason not in allowed_brief_reasons:
                core.fail(f'{rid}: BRIEF brief_reason is not allowed by current depth contract: {reason}')

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
    """Validate tiers with the exact Registry normalizer implementation."""
    items = sorted(data.get('items') or [], key=lambda x: int(x.get('rank_global', 10**9)))
    cfg = core.load_config()
    top_limit = int((cfg.get('homepage') or {}).get('top5', 5))
    next_limit = int((cfg.get('homepage') or {}).get('next10', 10))
    policy = depth.get('top5_policy') or {}

    expected_items = [dict(item) for item in items]
    try:
        assign_homepage_tiers(expected_items, top_limit, next_limit, policy)
    except ValueError as exc:
        return [f'top5 policy rejected by Registry tier assignment: {exc}']

    expected_top = [x for x in expected_items if x.get('homepage_tier') == 'top5']
    expected_next = [x for x in expected_items if x.get('homepage_tier') == 'next10']
    expected_category = [x for x in expected_items if x.get('homepage_tier') == 'category_only']

    actual_top = [x for x in items if x.get('homepage_tier') == 'top5']
    actual_next = [x for x in items if x.get('homepage_tier') == 'next10']
    actual_category = [x for x in items if x.get('homepage_tier') == 'category_only']

    errors = []
    if [x.get('id') for x in actual_top] != [x.get('id') for x in expected_top]:
        errors.append('tier-aware top5 must match normalize_registry_identity.assign_homepage_tiers')
    if [x.get('id') for x in actual_next] != [x.get('id') for x in expected_next]:
        errors.append('tier-aware next10 must match normalize_registry_identity.assign_homepage_tiers')
    if [x.get('id') for x in actual_category] != [x.get('id') for x in expected_category]:
        errors.append('tier-aware category_only must match normalize_registry_identity.assign_homepage_tiers')
    if any(_level(x) == 'REJECT' for x in actual_top):
        errors.append('tier-aware TOP5 contains REJECT item')
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
    # Coverage Audit is a release invariant for every current daily release, not
    # only for low-volume fallback. This is where source-probe/decision-ledger
    # requirements become deterministic pre-ready gates when their effective dates apply.
    errors.extend(coverage_audit_errors(data, category_ids))
    if low_volume_release_allowed(data, category_ids):
        errors = [e for e in errors if not e.startswith('V2 daily release minimum is ')]
    return errors


core.validate_analysis = validate_analysis_tiered
core.validate_v2_dataset = validate_with_hybrid
core.main()
