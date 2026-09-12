#!/usr/bin/env python3
"""Hybrid-aware release input gate with FULL / BRIEF analysis tiers."""
import check_release_input_core as core
from discovery_hybrid import low_volume_release_allowed

ORIGINAL_VALIDATE = core.validate_v2_dataset


def _level(item):
    return str(item.get('analysis_level') or 'FULL').strip().upper()


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
    if not strict_pool:
        return errors
    category_ids = [c['id'] for c in core.load_config().get('categories') or []]
    if low_volume_release_allowed(data, category_ids):
        errors = [e for e in errors if not e.startswith('V2 daily release minimum is ')]
    return errors


core.validate_analysis = validate_analysis_tiered
core.validate_v2_dataset = validate_with_hybrid
core.main()
