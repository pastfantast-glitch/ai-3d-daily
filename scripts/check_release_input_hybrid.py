#!/usr/bin/env python3
"""Hybrid-aware release input gate used by both prepare and publish."""
import check_release_input_core as core
from discovery_hybrid import low_volume_release_allowed

ORIGINAL_VALIDATE = core.validate_v2_dataset


def validate_with_hybrid(data, strict_pool=True):
    errors = ORIGINAL_VALIDATE(data, strict_pool=strict_pool)
    if not strict_pool:
        return errors
    category_ids = [c['id'] for c in core.load_config().get('categories') or []]
    if not low_volume_release_allowed(data, category_ids):
        return errors
    return [e for e in errors if not e.startswith('V2 daily release minimum is ')]


core.validate_v2_dataset = validate_with_hybrid
core.main()
