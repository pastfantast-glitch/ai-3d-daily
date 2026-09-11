#!/usr/bin/env python3
from pathlib import Path
import json

from discovery_hybrid import (
    coverage_audit_errors,
    load_hybrid_config,
    positive_samples,
    priority_sources,
)
from intelligence_v2 import load_config

ROOT = Path(__file__).resolve().parents[1]


def main():
    intel = load_config()
    hybrid = load_hybrid_config()
    col = intel.get('collection') or {}
    coverage = hybrid.get('coverage_audit') or {}
    low = hybrid.get('low_volume_release') or {}
    backlog = hybrid.get('rolling_backlog') or {}

    expected_windows = list(col.get('discovery_windows') or [])
    if list(coverage.get('required_windows') or []) != expected_windows:
        raise SystemExit('HYBRID CONTRACT FAILED: required_windows drift from intelligence-v2 discovery_windows')

    expected_categories = [c['id'] for c in intel.get('categories') or []]
    if list(coverage.get('required_categories') or []) != expected_categories:
        raise SystemExit('HYBRID CONTRACT FAILED: required_categories drift from intelligence-v2 categories')

    if int(low.get('normal_floor', 0)) != int(col.get('daily_min_items', 0)):
        raise SystemExit('HYBRID CONTRACT FAILED: normal_floor must equal intelligence-v2 daily_min_items')
    if int(low.get('maximum', 0)) != int(col.get('daily_max_items', 0)):
        raise SystemExit('HYBRID CONTRACT FAILED: low-volume maximum must equal intelligence-v2 daily_max_items')

    backlog_path = ROOT / str(backlog.get('path', ''))
    if not backlog_path.exists():
        raise SystemExit(f'HYBRID CONTRACT FAILED: backlog file missing: {backlog_path}')
    data = json.loads(backlog_path.read_text('utf-8'))
    if int(data.get('schema_version', 0)) != 1 or not isinstance(data.get('items'), list):
        raise SystemExit('HYBRID CONTRACT FAILED: rolling backlog must be schema_version=1 with items[]')

    profiles = hybrid.get('category_discovery_profiles') or {}
    animation = profiles.get('3d-animation') or {}
    if animation.get('always_discover') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: 3d-animation discovery profile must always_discover')

    fundamental = [str(x).lower() for x in animation.get('fundamental_animation_topics') or []]
    rigging = [str(x).lower() for x in animation.get('rigging_topics') or []]
    required_fundamental = ('key pose', 'blocking', 'timing and spacing', 'body mechanics')
    required_rigging = ('skeleton hierarchy', 'fk and ik', 'skin weighting', 'game-ready character rigs')
    for token in required_fundamental:
        if not any(token in item for item in fundamental):
            raise SystemExit(f'HYBRID CONTRACT FAILED: 3d-animation fundamental tutorial topic missing: {token}')
    for token in required_rigging:
        if not any(token in item for item in rigging):
            raise SystemExit(f'HYBRID CONTRACT FAILED: 3d-animation rigging tutorial topic missing: {token}')

    tutorial_policy = str(animation.get('tutorial_policy', '')).lower()
    if 'evergreen' not in tutorial_policy or 'production intelligence' not in tutorial_policy:
        raise SystemExit('HYBRID CONTRACT FAILED: animation tutorial policy must admit high-quality evergreen production education')

    samples = positive_samples(hybrid)
    if len(samples) < 6:
        raise SystemExit('HYBRID CONTRACT FAILED: positive-sample registry must contain at least six user-selected examples')
    sample_urls = {str(x.get('url', '')).strip() for x in samples}
    required_80lv_slugs = (
        'breakdown-modeling-a-3d-fantasy-character-based-on-a-2d-concept',
        'tutorial-realistic-procedural-ice-cube-material-in-blender-with-easy-customization',
        'spider-verse-animator-makes-marvel-s-venom-look-absolutely-insane',
        'modeling-and-texturing-a-fan-art-of-alice-from-raid-shadow-legends',
        'try-this-free-cad-data-retopology-tool-for-blender',
        'this-3d-animation-of-a-stylized-vampire-was-inspired-by-marvel-rivals-arcane',
    )
    for slug in required_80lv_slugs:
        if not any('80.lv/articles/' + slug in url for url in sample_urls):
            raise SystemExit(f'HYBRID CONTRACT FAILED: required user positive sample missing: {slug}')

    learning = hybrid.get('preference_learning') or {}
    use_for = set(learning.get('use_for') or [])
    if 'discovery-query-expansion' not in use_for or 'user-interest-fit-ranking' not in use_for:
        raise SystemExit('HYBRID CONTRACT FAILED: positive samples must feed discovery query expansion and ranking')
    policy = str(learning.get('ranking_policy', '')).lower()
    for token in ('registry', 'quality gate', 'full analysis'):
        if token not in policy:
            raise SystemExit(f'HYBRID CONTRACT FAILED: positive-sample ranking guard missing {token}')

    sources = priority_sources(hybrid)
    eighty = next((x for x in sources if x.get('id') == '80-level'), None)
    if not eighty or str(eighty.get('domain', '')).lower() != '80.lv':
        raise SystemExit('HYBRID CONTRACT FAILED: 80 Level priority source missing')
    if eighty.get('required_check') is not True or str(eighty.get('mode', '')).lower() != 'high-recall':
        raise SystemExit('HYBRID CONTRACT FAILED: 80 Level must be a required high-recall source')
    if 'quality' not in str(eighty.get('admission', '')).lower():
        raise SystemExit('HYBRID CONTRACT FAILED: priority source must still pass normal quality admission')

    if coverage.get('require_priority_source_checks') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: Coverage Audit must require priority-source checks')

    refill = hybrid.get('targeted_refill') or {}
    if refill.get('use_category_discovery_profiles') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: targeted refill must consume category discovery profiles')
    if refill.get('use_preference_learning') is not True or refill.get('use_priority_sources') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: targeted refill must consume positive samples and priority sources')

    source_effective = str(coverage.get('priority_source_coverage_effective_date', ''))
    audit = {
        'fill_ladder_exhausted': True,
        'backlog_checked': True,
        'targeted_refill_performed': True,
        'quality_first_confirmed': True,
        'backlog_remaining_eligible': 0,
        'windows': {w: {'status': coverage.get('exhaustion_status', 'exhausted'), 'candidates_found': 0} for w in expected_windows},
        'category_candidates': {cid: {'candidates_considered': 0} for cid in expected_categories},
        'priority_sources': {'80-level': {'status': 'checked', 'candidates_found': 0}},
    }
    fixture = {'date': source_effective, 'metadata': {'discovery_coverage': audit}, 'items': []}
    errors = coverage_audit_errors(fixture, expected_categories, hybrid)
    if errors:
        raise SystemExit(f'HYBRID CONTRACT FAILED: priority source Coverage Audit fixture should pass: {errors}')
    del audit['priority_sources']
    errors = coverage_audit_errors(fixture, expected_categories, hybrid)
    if not any('missing priority source check 80-level' in x for x in errors):
        raise SystemExit('HYBRID CONTRACT FAILED: missing 80 Level source audit must fail closed')

    print(
        'HYBRID DISCOVERY CONTRACT PASS: '
        f"normal_floor={low['normal_floor']} fallback_floor={low['fallback_floor']} "
        f"target={col['daily_target_items']} maximum={low['maximum']} / "
        f"windows={expected_windows} / backlog={backlog['path']} / "
        '3d-animation keypose+rigging tutorials + 80 Level high-recall positive samples locked'
    )


if __name__ == '__main__':
    main()
