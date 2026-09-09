#!/usr/bin/env python3
from pathlib import Path
import json

from discovery_hybrid import load_hybrid_config
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

    refill = hybrid.get('targeted_refill') or {}
    if refill.get('use_category_discovery_profiles') is not True:
        raise SystemExit('HYBRID CONTRACT FAILED: targeted refill must consume category discovery profiles')

    print(
        'HYBRID DISCOVERY CONTRACT PASS: '
        f"normal_floor={low['normal_floor']} fallback_floor={low['fallback_floor']} "
        f"target={col['daily_target_items']} maximum={low['maximum']} / "
        f"windows={expected_windows} / backlog={backlog['path']} / "
        '3d-animation keypose+rigging tutorial discovery locked'
    )


if __name__ == '__main__':
    main()
