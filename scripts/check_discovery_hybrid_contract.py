#!/usr/bin/env python3
from pathlib import Path
import json

from discovery_hybrid import coverage_audit_errors, load_hybrid_config, positive_samples
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
    for token in ('key pose', 'blocking', 'timing and spacing', 'body mechanics'):
        if not any(token in item for item in fundamental):
            raise SystemExit(f'HYBRID CONTRACT FAILED: 3d-animation fundamental tutorial topic missing: {token}')
    for token in ('skeleton hierarchy', 'fk and ik', 'skin weighting', 'game-ready character rigs'):
        if not any(token in item for item in rigging):
            raise SystemExit(f'HYBRID CONTRACT FAILED: 3d-animation rigging tutorial topic missing: {token}')

    tutorial_policy = str(animation.get('tutorial_policy', '')).lower()
    if 'evergreen' not in tutorial_policy or 'production intelligence' not in tutorial_policy:
        raise SystemExit('HYBRID CONTRACT FAILED: animation tutorial policy must admit high-quality evergreen production education')

    samples = positive_samples(hybrid)
    if len(samples) < 6:
        raise SystemExit('HYBRID CONTRACT FAILED: positive-sample registry must contain at least six user-selected examples')
    sample_urls = {str(x.get('url', '')).strip() for x in samples}
    required_slugs = (
        'breakdown-modeling-a-3d-fantasy-character-based-on-a-2d-concept',
        'tutorial-realistic-procedural-ice-cube-material-in-blender-with-easy-customization',
        'spider-verse-animator-makes-marvel-s-venom-look-absolutely-insane',
        'modeling-and-texturing-a-fan-art-of-alice-from-raid-shadow-legends',
        'try-this-free-cad-data-retopology-tool-for-blender',
        'this-3d-animation-of-a-stylized-vampire-was-inspired-by-marvel-rivals-arcane',
    )
    for slug in required_slugs:
        if not any(slug in url for url in sample_urls):
            raise SystemExit(f'HYBRID CONTRACT FAILED: required user positive sample missing: {slug}')

    learning = hybrid.get('preference_learning') or {}
    use_for = set(learning.get('use_for') or [])
    if 'discovery-query-expansion' not in use_for or 'user-interest-fit-ranking' not in use_for:
        raise SystemExit('HYBRID CONTRACT FAILED: positive samples must feed discovery query expansion and ranking')
    policy = str(learning.get('ranking_policy', '')).lower()
    for token in ('registry', 'quality gate', 'full analysis'):
        if token not in policy:
            raise SystemExit(f'HYBRID CONTRACT FAILED: positive-sample ranking guard missing {token}')
    if 'source-domain similarity must contribute zero preference weight' not in policy:
        raise SystemExit('HYBRID CONTRACT FAILED: preference ranking must explicitly assign zero weight to sample-domain similarity')

    source_policy = str(learning.get('sample_source_policy', '')).lower()
    for token in ('provenance', 'hostnames', 'source boosts', 'site-specific'):
        if token not in source_policy:
            raise SystemExit(f'HYBRID CONTRACT FAILED: sample source-neutrality policy missing {token}')

    neutrality = hybrid.get('source_neutrality') or {}
    if neutrality.get('enabled') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: source neutrality must be enabled')
    if neutrality.get('positive_sample_domains_are_provenance_only') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: positive sample domains must be provenance only')
    for key in (
        'domain_weight_from_positive_samples',
        'required_site_checks_from_positive_samples',
        'site_specific_refill_from_positive_samples',
        'source_domain_may_increase_user_interest_fit',
    ):
        if neutrality.get(key) is not False:
            raise SystemExit(f'HYBRID CONTRACT FAILED: source-neutral guard must keep {key}=false')

    if hybrid.get('priority_sources'):
        raise SystemExit('HYBRID CONTRACT FAILED: preference-derived priority_sources must be empty/absent')
    if coverage.get('require_priority_source_checks') is True:
        raise SystemExit('HYBRID CONTRACT FAILED: Coverage Audit must not require preference-derived source checks')

    refill = hybrid.get('targeted_refill') or {}
    if refill.get('use_category_discovery_profiles') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: targeted refill must consume category discovery profiles')
    if refill.get('use_preference_learning') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: targeted refill must consume content preference learning')
    if refill.get('use_source_neutrality') is not True or refill.get('use_priority_sources') is not False:
        raise SystemExit('HYBRID CONTRACT FAILED: targeted refill must be source-neutral and must not consume priority sources')

    audit = {
        'fill_ladder_exhausted': True,
        'backlog_checked': True,
        'targeted_refill_performed': True,
        'quality_first_confirmed': True,
        'backlog_remaining_eligible': 0,
        'windows': {w: {'status': coverage.get('exhaustion_status', 'exhausted'), 'candidates_found': 0} for w in expected_windows},
        'category_candidates': {cid: {'candidates_considered': 0} for cid in expected_categories},
    }
    fixture = {'date': str(hybrid.get('effective_date')), 'metadata': {'discovery_coverage': audit}, 'items': []}
    errors = coverage_audit_errors(fixture, expected_categories, hybrid)
    if errors:
        raise SystemExit(f'HYBRID CONTRACT FAILED: source-neutral Coverage Audit fixture should pass: {errors}')

    print(
        'HYBRID DISCOVERY CONTRACT PASS: '
        f"normal_floor={low['normal_floor']} fallback_floor={low['fallback_floor']} "
        f"target={col['daily_target_items']} maximum={low['maximum']} / "
        f"windows={expected_windows} / backlog={backlog['path']} / "
        'content-preference learning is source-neutral; no sample-domain priority source is allowed'
    )


if __name__ == '__main__':
    main()
