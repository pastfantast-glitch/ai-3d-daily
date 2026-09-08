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

    print(
        'HYBRID DISCOVERY CONTRACT PASS: '
        f"normal_floor={low['normal_floor']} fallback_floor={low['fallback_floor']} "
        f"target={col['daily_target_items']} maximum={low['maximum']} / "
        f"windows={expected_windows} / backlog={backlog['path']}"
    )


if __name__ == '__main__':
    main()
