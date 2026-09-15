#!/usr/bin/env python3
from pathlib import Path
import json
import re

from discovery_hybrid import (
    candidate_decision_ledger_errors,
    coverage_audit_errors,
    discovery_sources,
    load_hybrid_config,
    positive_samples,
    registered_source_probe_errors,
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

    admission = col.get('admission_policy') or {}
    admission_effective = str(admission.get('effective_date', '')).strip()
    if not str(admission.get('mode', '')).strip():
        raise SystemExit('HYBRID CONTRACT FAILED: collection.admission_policy.mode is required')
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', admission_effective):
        raise SystemExit('HYBRID CONTRACT FAILED: collection.admission_policy.effective_date must be YYYY-MM-DD')
    if str(intel.get('admission_policy_effective_date', '')).strip() != admission_effective:
        raise SystemExit('HYBRID CONTRACT FAILED: admission policy effective date drift')
    if admission.get('evidence_depth_is_admission_gate') is not False:
        raise SystemExit('HYBRID CONTRACT FAILED: evidence depth must not be an admission gate')
    if admission.get('limited_evidence_routes_to_brief') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: limited-evidence admission-pass items must route to BRIEF')
    if admission.get('single_source_can_publish_as_brief_when_verified') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: verified single-source limited-depth items must be eligible for BRIEF')
    if admission.get('topic_repeat_is_duplicate') is not False:
        raise SystemExit('HYBRID CONTRACT FAILED: topic repetition alone must not equal duplicate identity')
    if admission.get('ranking_handles_narrow_impact') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: narrow impact must be handled by ranking instead of automatic rejection')
    if len(admission.get('minimum_requirements') or []) < 3:
        raise SystemExit('HYBRID CONTRACT FAILED: admission policy needs explicit minimum requirements')
    if len(admission.get('substantive_delta_examples') or []) < 5:
        raise SystemExit('HYBRID CONTRACT FAILED: admission policy needs substantive-delta examples')
    if len(admission.get('hard_exclude_only') or []) < 4:
        raise SystemExit('HYBRID CONTRACT FAILED: admission policy hard-exclude set is incomplete')

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

    probe_cfg = hybrid.get('registered_source_coverage_probe') or {}
    if probe_cfg.get('enabled') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: registered source coverage probe must be enabled')
    if probe_cfg.get('scope') != 'all-enabled-discovery-source-pool':
        raise SystemExit('HYBRID CONTRACT FAILED: registered source coverage probe must cover all enabled registered sources')
    if float(probe_cfg.get('ranking_bonus', 0) or 0) != 0 or probe_cfg.get('quota') is not False or probe_cfg.get('admission_bypass') is not False:
        raise SystemExit('HYBRID CONTRACT FAILED: registered source coverage probe must be recall-only with zero ranking bonus/quota/bypass')
    if refill.get('use_registered_source_coverage_probe') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: targeted refill must consume registered source coverage probe results')

    ledger_cfg = hybrid.get('candidate_decision_ledger') or {}
    if ledger_cfg.get('required') is not True or ledger_cfg.get('public_surface') is not False:
        raise SystemExit('HYBRID CONTRACT FAILED: candidate decision ledger must be required and private')
    if '{date}' not in str(ledger_cfg.get('path_template', '')):
        raise SystemExit('HYBRID CONTRACT FAILED: candidate decision ledger path must be date-scoped')
    if not {'published', 'duplicate', 'rejected', 'ranked-out', 'backlog'} <= set(ledger_cfg.get('terminal_decisions') or []):
        raise SystemExit('HYBRID CONTRACT FAILED: candidate decision ledger terminal decisions are incomplete')

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

    feature_date = max(str(probe_cfg.get('effective_date')), str(ledger_cfg.get('effective_date')))
    source_records = {
        str(source['id']): {
            'status': 'checked',
            'method': 'latest-index',
            'candidates_found': 0,
            'candidate_ids': [],
        }
        for source in discovery_sources(hybrid)
    }
    future_audit = dict(audit)
    future_audit['registered_source_probe'] = {'performed': True, 'sources': source_records}
    future_fixture = {
        'date': feature_date,
        'metadata': {'discovery_coverage': future_audit},
        'items': [
            {
                'id': 'fixture-published',
                'source_url': 'https://example.com/published',
            }
        ],
    }
    probe_errors = registered_source_probe_errors(future_fixture, hybrid)
    if probe_errors:
        raise SystemExit(f'HYBRID CONTRACT FAILED: registered source probe positive fixture should pass: {probe_errors}')
    ledger_fixture = {
        'schema_version': int(ledger_cfg.get('schema_version', 1)),
        'date': feature_date,
        'items': [
            {
                'candidate_id': 'fixture-published-candidate',
                'source_url': 'https://example.com/published',
                'discovery_channels': ['web-search'],
                'decision': 'published',
                'canonical_id': 'fixture-published',
            }
        ],
    }
    ledger_errors = candidate_decision_ledger_errors(future_fixture, hybrid, ledger_data=ledger_fixture)
    if ledger_errors:
        raise SystemExit(f'HYBRID CONTRACT FAILED: candidate decision ledger positive fixture should pass: {ledger_errors}')

    missing_source_fixture = json.loads(json.dumps(future_fixture))
    first_source = str(discovery_sources(hybrid)[0]['id'])
    del missing_source_fixture['metadata']['discovery_coverage']['registered_source_probe']['sources'][first_source]
    if not registered_source_probe_errors(missing_source_fixture, hybrid):
        raise SystemExit('HYBRID CONTRACT FAILED: registered source probe must fail when an enabled source has no attempt record')

    probe_candidate_fixture = json.loads(json.dumps(future_fixture))
    probe_candidate_fixture['metadata']['discovery_coverage']['registered_source_probe']['sources'][first_source].update({
        'candidates_found': 1,
        'candidate_ids': ['probe-candidate-1'],
    })
    if not candidate_decision_ledger_errors(probe_candidate_fixture, hybrid, ledger_data=ledger_fixture):
        raise SystemExit('HYBRID CONTRACT FAILED: decision ledger must fail when a registered-source probe candidate is unaccounted for')

    print(
        'HYBRID DISCOVERY CONTRACT PASS: '
        f"normal_floor={low['normal_floor']} fallback_floor={low['fallback_floor']} "
        f"target={col['daily_target_items']} maximum={low['maximum']} / "
        f"windows={expected_windows} / backlog={backlog['path']} / "
        f"admission={admission.get('mode')} / "
        f"registered_sources={len(discovery_sources(hybrid))} / "
        f"probe_effective={probe_cfg.get('effective_date')} / ledger_effective={ledger_cfg.get('effective_date')} / "
        'broad admission + strict ranking + FULL-depth separation + source-neutral preference learning + recall audit trail'
    )


if __name__ == '__main__':
    main()
