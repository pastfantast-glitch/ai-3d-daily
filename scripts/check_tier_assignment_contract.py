#!/usr/bin/env python3
"""Deterministic regression guard for FULL-first / BRIEF-fallback homepage tiers.

This fixture exists specifically to catch the boundary that all-BRIEF days cannot:
a higher-ranked BRIEF must not displace an available FULL item, while BRIEF may fill
only the remaining TOP5 slots when the repo-owned policy permits fallback.
"""
from pathlib import Path
import json

from normalize_registry_identity import assign_homepage_tiers

ROOT = Path(__file__).resolve().parents[1]
INTEL = json.loads((ROOT / 'config' / 'intelligence-v2.json').read_text('utf-8'))
DEPTH = json.loads((ROOT / 'config' / 'full-analysis-depth.json').read_text('utf-8'))


def item(rank, level):
    return {
        'id': f'fixture-{rank}-{level.lower()}',
        'rank_global': rank,
        'analysis_level': level,
    }


def ids(items, tier):
    return [x['id'] for x in items if x.get('homepage_tier') == tier]


def main():
    homepage = INTEL.get('homepage') or {}
    top_limit = int(homepage.get('top5', 5))
    next_limit = int(homepage.get('next10', 10))
    policy = DEPTH.get('top5_policy') or {}

    if top_limit != 5:
        raise SystemExit(f'TIER ASSIGNMENT CONTRACT FAILED: fixture expects homepage.top5=5, got {top_limit}')
    if str(policy.get('selection_mode')) != 'full-first-brief-fallback':
        raise SystemExit('TIER ASSIGNMENT CONTRACT FAILED: current fixture expects full-first-brief-fallback mode')
    if policy.get('allow_brief') is not True or policy.get('brief_fallback_only') is not True:
        raise SystemExit('TIER ASSIGNMENT CONTRACT FAILED: BRIEF must be fallback-only in current policy')

    # Dangerous mixed case: rank-1 BRIEF must not push rank-6 FULL out of TOP5.
    mixed = [
        item(1, 'BRIEF'),
        item(2, 'FULL'),
        item(3, 'FULL'),
        item(4, 'BRIEF'),
        item(5, 'BRIEF'),
        item(6, 'FULL'),
    ]
    meta = assign_homepage_tiers(mixed, top_limit, next_limit, policy)
    expected_top = [
        'fixture-1-brief',
        'fixture-2-full',
        'fixture-3-full',
        'fixture-4-brief',
        'fixture-6-full',
    ]
    if ids(mixed, 'top5') != expected_top:
        raise SystemExit(
            'TIER ASSIGNMENT CONTRACT FAILED: mixed FULL/BRIEF TOP5 drift: '
            f"expected={expected_top} actual={ids(mixed, 'top5')}"
        )
    if ids(mixed, 'next10') != ['fixture-5-brief']:
        raise SystemExit('TIER ASSIGNMENT CONTRACT FAILED: mixed-case remainder must flow to next10')
    if meta.get('top5_full_count') != 3 or meta.get('top5_brief_fallback_count') != 2:
        raise SystemExit(f'TIER ASSIGNMENT CONTRACT FAILED: mixed-case metadata drift: {meta}')

    # All-BRIEF case: fallback may fill TOP5, but evidence class must remain BRIEF.
    all_brief = [item(i, 'BRIEF') for i in range(1, 7)]
    meta = assign_homepage_tiers(all_brief, top_limit, next_limit, policy)
    if ids(all_brief, 'top5') != [f'fixture-{i}-brief' for i in range(1, 6)]:
        raise SystemExit('TIER ASSIGNMENT CONTRACT FAILED: all-BRIEF fallback must fill the first five ranked survivors')
    if any(x.get('analysis_level') != 'BRIEF' for x in all_brief):
        raise SystemExit('TIER ASSIGNMENT CONTRACT FAILED: homepage assignment must never promote BRIEF to FULL')
    if meta.get('top5_full_count') != 0 or meta.get('top5_brief_fallback_count') != 5:
        raise SystemExit(f'TIER ASSIGNMENT CONTRACT FAILED: all-BRIEF metadata drift: {meta}')

    print(
        'TIER ASSIGNMENT CONTRACT PASS: Registry is the single tier algorithm; '
        'FULL has TOP5 priority, BRIEF fills only unused slots, and BRIEF is never promoted.'
    )


if __name__ == '__main__':
    main()
