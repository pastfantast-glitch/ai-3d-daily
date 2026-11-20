#!/usr/bin/env python3
"""Tier-aware compatibility facade for the legacy intelligence_v2 module.

Python prefers this package over the sibling intelligence_v2.py module. We load
that implementation verbatim, re-export its public API, then replace only
validate_v2_dataset() for dates covered by the FULL / BRIEF / REJECT contract.
This keeps legacy callers (including renderers) source-compatible while removing
obsolete assumptions that every published item needs >=3 analysis blocks and
that homepage TOP5 must always equal global ranks 1-5.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json

PACKAGE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PACKAGE_DIR.parent
ROOT = SCRIPTS_DIR.parent
LEGACY_PATH = SCRIPTS_DIR / 'intelligence_v2.py'
DEPTH_PATH = ROOT / 'config' / 'full-analysis-depth.json'

_spec = spec_from_file_location('_intelligence_v2_legacy', LEGACY_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f'Unable to load legacy intelligence_v2 module: {LEGACY_PATH}')
_legacy = module_from_spec(_spec)
_spec.loader.exec_module(_legacy)

for _name in dir(_legacy):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_legacy, _name)

_legacy_validate_v2_dataset = _legacy.validate_v2_dataset


def _analysis_level(item):
    return str(item.get('analysis_level') or 'FULL').strip().upper()


def _depth_config():
    return json.loads(DEPTH_PATH.read_text('utf-8'))


def _tiered_applies(data, depth):
    date = str(data.get('date') or '').strip()
    effective = str(depth.get('tiered_effective_date', '9999-12-31')).strip()
    return bool(date and date >= effective)


def _is_legacy_homepage_error(error):
    return (
        error.startswith('homepage top5 must contain ranks ')
        or error.startswith('homepage next10 must contain up to ')
        or error.startswith('top5 must equal available global ranks ')
        or error.startswith('next10 must equal available global ranks ')
        or error.startswith('category_only must equal available global ranks ')
    )


def _tier_aware_homepage_errors(data, depth):
    from normalize_registry_identity import homepage_tier_errors
    homepage = load_config().get('homepage') or {}
    return homepage_tier_errors(data.get('items') or [],
        int(homepage.get('top5', 5)), int(homepage.get('next10', 10)),
        depth.get('top5_policy') or {})


def validate_v2_dataset(data, strict_pool=True):
    """Tier-aware wrapper around the legacy schema-v3 validator."""
    errors = _legacy_validate_v2_dataset(data, strict_pool=strict_pool)
    depth = _depth_config()
    if not _tiered_applies(data, depth):
        return errors

    brief_ids = {
        str(x.get('id'))
        for x in data.get('items') or []
        if _analysis_level(x) == 'BRIEF'
    }
    if brief_ids:
        errors = [
            e for e in errors
            if not (
                'full_analysis requires at least 3 blocks' in e
                and any(e.startswith(rid + ':') for rid in brief_ids)
            )
        ]

    errors = [e for e in errors if not _is_legacy_homepage_error(e)]
    errors.extend(_tier_aware_homepage_errors(data, depth))
    return errors


__all__ = [name for name in globals() if not name.startswith('_')]
